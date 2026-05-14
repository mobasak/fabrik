"""Gatus health-monitoring endpoint provisioning via SSH + scp.

Adds / removes a single YAML file per project under
``/opt/monitoring/configs/gatus/apps/`` on the Fabrik VPS, then restarts
the Coolify-managed ``gatus-*`` container so the new endpoint is picked up.

Design notes
------------
* **One file per project.** Safer than editing a shared config — an
  invalid project YAML only breaks its own endpoint, not the whole
  monitoring stack. Deletion is a single ``rm -f``.
* **External HTTPS URL, not container name.** Coolify-managed containers
  carry unpredictable UUID suffixes and may live on different Docker
  networks; having Gatus probe the public URL matches what end users
  see, and inherits Traefik + Let's Encrypt TLS as a freebie.
* **Container resolution by prefix.** The Coolify ``gatus-*`` suffix
  changes on re-create. We match ``^gatus-`` in ``docker ps`` output at
  call time, not a baked-in UUID.
* **Idempotent** by filesystem check (``test -f``). A subsequent call
  with the same ``project_name`` is a no-op and does NOT restart the
  container (which would be a ~2 s service blip for every re-apply).
* **Rollback** is handled by :func:`remove_endpoint`, invoked from
  ``DeploymentRollback._rollback_gatus``. Best-effort; never raises.
* **Atomic write.** The config is staged to ``/tmp/gatus-endpoint-<project>.yaml``
  on the VPS, then ``sudo mv``'d into the final path so Gatus never
  observes a partially-written file (critical because Gatus watches the
  directory for changes).
"""

from __future__ import annotations

import logging
import re
import shlex
import tempfile
from pathlib import Path

import yaml as yaml_lib

from fabrik.drivers.ssh import scp_to_vps, ssh

logger = logging.getLogger(__name__)

GATUS_CONFIG_DIR = "/opt/monitoring/configs/gatus/apps"
"""VPS directory holding one YAML file per project."""

DEFAULT_HEALTH_PATH = "/health"
"""Convention enforced by CSF §6 — every Fabrik service exposes ``/health``."""

DEFAULT_INTERVAL = "60s"
"""Gatus poll interval. Matches existing production endpoints (2026-04-17 audit)."""

DEFAULT_FAILURE_THRESHOLD = 3
"""Number of consecutive failures before alert fires. Matches audit baseline."""

_PROJECT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
"""Project name validator. Enforces filesystem safety — the project name
becomes a filename (``<name>.yaml``) so we exclude slashes, dots, spaces,
and shell metacharacters."""

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-zA-Z0-9-]{1,63}(?<!-)"
    r"(\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*$"
)
"""Conservative hostname validator. Excludes paths, schemes, and ports."""


def _validate_project_name(name: str) -> None:
    if not isinstance(name, str) or not _PROJECT_RE.match(name):
        raise ValueError(
            f"Invalid project name {name!r}: must match [a-zA-Z0-9][a-zA-Z0-9_-]{{0,63}}"
        )


def _validate_domain(domain: str) -> None:
    if not isinstance(domain, str) or not _DOMAIN_RE.match(domain):
        raise ValueError(f"Invalid domain {domain!r}: must be a bare hostname")


def _validate_health_path(path: str) -> None:
    if not isinstance(path, str) or not path.startswith("/") or "'" in path or '"' in path:
        raise ValueError(f"Invalid health path {path!r}: must start with / and contain no quotes")


def _build_endpoint_yaml(
    project_name: str,
    domain: str,
    health_path: str,
    interval: str,
    failure_threshold: int,
) -> str:
    """Render the Gatus endpoint YAML for a single project.

    The structure matches the existing production endpoint audit
    (2026-04-17) so operators can diff `/opt/monitoring/configs/gatus/apps/*.yaml`
    without surprise.
    """
    endpoint = {
        "endpoints": [
            {
                "name": project_name,
                "group": "apps",
                "url": f"https://{domain}{health_path}",
                "interval": interval,
                "client": {"timeout": "30s"},
                "conditions": ["[STATUS] == 200"],
                "alerts": [
                    {
                        "type": "custom",
                        "failure-threshold": failure_threshold,
                        "send-on-resolved": True,
                    }
                ],
            }
        ]
    }
    return yaml_lib.dump(endpoint, default_flow_style=False, sort_keys=False)


def add_endpoint(
    project_name: str,
    domain: str,
    health_path: str = DEFAULT_HEALTH_PATH,
    interval: str = DEFAULT_INTERVAL,
    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
    dry_run: bool = False,
) -> dict:
    """Add a Gatus health-check endpoint for ``project_name``.

    Idempotent: if ``<GATUS_CONFIG_DIR>/<project_name>.yaml`` already
    exists on the VPS, returns ``status=exists`` without rewriting or
    restarting Gatus.

    Args:
        project_name: Project name. Must match ``[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}``.
            Becomes the YAML filename.
        domain: Public hostname to probe (e.g. ``"app.vps1.ocoron.com"``).
            No scheme, no port, no path.
        health_path: Path appended to ``https://{domain}``. Defaults to
            ``/health`` per CSF §6. Must begin with ``/`` and contain
            no quote characters.
        interval: Gatus poll interval (Go duration string). Default ``60s``.
        failure_threshold: Consecutive failures before the endpoint
            alerts. Default 3.
        dry_run: Log the intended write + restart and return without
            touching the VPS.

    Returns:
        ``{"status": "created" | "exists" | "dry_run", "endpoint": project_name}``.

    Raises:
        ValueError: any input failed validation.
        RuntimeError: the underlying ``ssh``/``scp`` call failed.
    """
    _validate_project_name(project_name)
    _validate_domain(domain)
    _validate_health_path(health_path)

    config_file = f"{GATUS_CONFIG_DIR}/{project_name}.yaml"

    if dry_run:
        logger.info(
            "[DRY RUN] Would add Gatus endpoint %s -> https://%s%s",
            project_name,
            domain,
            health_path,
        )
        return {"status": "dry_run", "endpoint": project_name}

    # Idempotency check — safe, read-only.
    check = ssh(f"test -f {shlex.quote(config_file)} && echo exists || echo missing")
    if check.strip() == "exists":
        logger.info("Gatus endpoint already exists for %s", project_name)
        return {"status": "exists", "endpoint": project_name}

    yaml_body = _build_endpoint_yaml(
        project_name=project_name,
        domain=domain,
        health_path=health_path,
        interval=interval,
        failure_threshold=failure_threshold,
    )

    # Stage locally → scp → sudo mv (atomic from Gatus's POV).
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_body)
        local_tmp = f.name
    # Hardcoded VPS-side /tmp path is intentional: this is a transient
    # staging file on the remote (YAML body scp'd up, then mv'd into
    # /opt/monitoring/configs/gatus/apps/, then the tmp is removed). The
    # remote VPS is a single-tenant host (no other user sessions), so /tmp
    # symlink-attack vectors do not apply. `project_name` is validated
    # upstream by the spec loader's `id` regex.
    vps_tmp = f"/tmp/gatus-endpoint-{project_name}.yaml"  # nosec B108

    try:
        scp_to_vps(local_tmp, vps_tmp)
        ssh(
            f"sudo mv {shlex.quote(vps_tmp)} {shlex.quote(config_file)} && "
            f"sudo chown root:root {shlex.quote(config_file)}"
        )
        # Restart Gatus — prefix-matched because the Coolify UUID changes on recreate.
        ssh(
            "GATUS_CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep '^gatus-') "
            '&& sudo docker restart "$GATUS_CONTAINER"'
        )
        logger.info("Added Gatus endpoint: %s -> https://%s%s", project_name, domain, health_path)
    finally:
        Path(local_tmp).unlink(missing_ok=True)

    return {"status": "created", "endpoint": project_name}


def remove_endpoint(project_name: str, dry_run: bool = False) -> bool:
    """Rollback handler — remove a Gatus endpoint file and restart Gatus.

    Best-effort: any SSH error is caught and logged at WARNING, returning
    ``False`` so the rollback orchestrator can continue unwinding other
    registrars rather than re-raising.

    Args:
        project_name: Project name whose YAML file to delete.
        dry_run: Log intent and return True.

    Returns:
        True on success (or dry_run), False on SSH failure.
    """
    _validate_project_name(project_name)
    config_file = f"{GATUS_CONFIG_DIR}/{project_name}.yaml"

    if dry_run:
        logger.info("[DRY RUN] Would remove Gatus endpoint: %s", project_name)
        return True

    try:
        ssh(f"sudo rm -f {shlex.quote(config_file)}")
        ssh(
            "GATUS_CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep '^gatus-') "
            '&& sudo docker restart "$GATUS_CONTAINER"'
        )
        logger.info("Removed Gatus endpoint: %s", project_name)
        return True
    except Exception as e:  # noqa: BLE001 — rollback must not raise
        logger.warning("Gatus endpoint removal failed (non-fatal): %s", e)
        return False


__all__ = (
    "GATUS_CONFIG_DIR",
    "DEFAULT_HEALTH_PATH",
    "DEFAULT_INTERVAL",
    "DEFAULT_FAILURE_THRESHOLD",
    "add_endpoint",
    "remove_endpoint",
)
