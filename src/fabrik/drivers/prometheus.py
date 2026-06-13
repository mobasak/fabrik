"""Prometheus scrape-target registration for Fabrik services exposing ``/metrics``.

Closes ``DEPLOYMENT.md §9.9 G5`` — services with ``shape.exposes_metrics``
are now registered as Prometheus scrape targets automatically. Until
this driver landed, ``/metrics`` endpoints were invisible to Prometheus
unless an operator hand-edited
``/opt/monitoring/configs/prometheus/prometheus.yml`` and reloaded.

Design notes
------------
* **Single shared config, surgical edit.** Unlike Gatus (one YAML file
  per project, dropped into ``apps/``), Prometheus only reads a single
  ``prometheus.yml``. We surgically append / remove a ``- job_name:
  fabrik-<name>`` block under ``scrape_configs:`` rather than touching
  the global section or the existing infrastructure jobs (node, cadvisor,
  loki, etc.). This keeps human-curated infra jobs and machine-managed
  service jobs visually separated in diffs.
* **Round-trip via PyYAML, not regex.** Prometheus's YAML is
  whitespace-significant (alerting block, scrape_configs list); a
  regex-based append would corrupt the file the first time someone
  reorders sections. We parse → mutate → dump and rely on Prometheus's
  own YAML loader being equally tolerant of key order.
* **Atomic write via ``sudo mv``.** Same pattern as
  :mod:`fabrik.drivers.gatus` and :mod:`fabrik.drivers.redis`.
* **Reload via lifecycle endpoint, fallback to restart.** Prometheus
  reloads its config on ``POST /-/reload`` only when started with
  ``--web.enable-lifecycle``. We try the endpoint first (fast, no
  scrape-gap) and fall back to a container restart on HTTP failure.
  The restart costs ~3 s of scrape-gap but always works.
* **Public-HTTPS scrape targets by default.** Coolify-managed container
  names carry unpredictable UUID suffixes that change on rebuild — same
  reason :mod:`fabrik.drivers.gatus` probes the public domain. The
  driver emits ``targets: ['<domain>:443']`` + ``scheme: https`` +
  ``metrics_path: /metrics``. Internal-network scraping (faster, no
  TLS) is supported via the ``target`` kwarg for infra services with
  stable container names.
* **Idempotent** — if a job named ``fabrik-<name>`` already exists,
  :func:`add_scrape_target` returns ``status=exists`` without rewriting
  or reloading.
* **No auth wiring yet.** ``/metrics`` endpoints are assumed to be
  reachable without credentials. When a service stands up bearer-token
  auth on ``/metrics``, the caller passes ``bearer_token`` to embed
  Prometheus's ``authorization`` block.
"""

from __future__ import annotations

import logging
import re
import shlex
import tempfile
from pathlib import Path
from typing import Any

import yaml as yaml_lib

from fabrik.drivers.ssh import scp_to_vps, ssh

logger = logging.getLogger(__name__)

PROMETHEUS_CONFIG_PATH = "/opt/monitoring/configs/prometheus/prometheus.yml"
"""VPS path holding the single prometheus.yml file."""

# Local source-controlled mirror of the VPS config. Until 2026-06-13 the
# driver wrote to vps1 LIVE only, never to git, so the file in this repo
# silently drifted from production (md5 mismatch verified). The dual-write
# in `_write_config` below now updates both atomically: vps1 first (since
# that's the runtime gate — reload failure surfaces there), then the git
# mirror gets the same body on success. Operators commit the resulting
# diff like any other code change. See [`configs/prometheus/README.md`].
try:
    from fabrik.config import FABRIK_ROOT as _FABRIK_ROOT_FOR_LOCAL_MIRROR

    _LOCAL_PROMETHEUS_CONFIG_PATH = (
        _FABRIK_ROOT_FOR_LOCAL_MIRROR / "configs" / "prometheus" / "prometheus.yml"
    )
except Exception:  # noqa: BLE001 — defensive: tests can monkeypatch
    _LOCAL_PROMETHEUS_CONFIG_PATH = None

PROMETHEUS_RELOAD_URL = "http://prometheus:9090/-/reload"
"""Lifecycle endpoint for hot-reload. Reachable from the VPS host via
the ``coolify`` Docker network alias; we curl it from inside the
``alertmanager`` container which sits on the same network. (The VPS
host itself does NOT join the monitoring network.)"""

DEFAULT_METRICS_PATH = "/metrics"
"""Standard Prometheus convention. Override per-call if the service
exposes metrics under a different path."""

DEFAULT_INTERVAL = "30s"
"""Scrape interval. Half of Gatus's 60s health-check cadence — metrics
need finer resolution to catch transient blips, alerts need coarser
to avoid pager noise."""

JOB_PREFIX = "fabrik-"
"""Prefix every Fabrik-managed scrape job receives. Lets the operator
``grep '^- job_name: fabrik-'`` to see only Fabrik-owned targets and
distinguish them from hand-curated infra jobs."""

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
"""Service-name validator. Same charset as Gatus and Redis drivers."""

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-zA-Z0-9-]{1,63}(?<!-)"
    r"(\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*$"
)
"""Conservative hostname validator (same regex Gatus uses)."""


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValueError(
            f"Invalid scrape target name {name!r}: must match [a-zA-Z0-9][a-zA-Z0-9_-]{{0,63}}"
        )


def _validate_domain(domain: str) -> None:
    if not isinstance(domain, str) or not _DOMAIN_RE.match(domain):
        raise ValueError(f"Invalid domain {domain!r}: must be a bare hostname")


def _job_name(service_name: str) -> str:
    return f"{JOB_PREFIX}{service_name}"


def _read_config() -> dict[str, Any]:
    """Load prometheus.yml from the VPS as a Python dict."""
    raw = ssh(
        f"sudo cat {shlex.quote(PROMETHEUS_CONFIG_PATH)}",
        timeout=15,
    )
    data = yaml_lib.safe_load(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"prometheus.yml at {PROMETHEUS_CONFIG_PATH} did not parse to a mapping")
    # Normalize: ensure scrape_configs exists.
    data.setdefault("scrape_configs", [])
    return data


def _write_config(data: dict[str, Any]) -> None:
    """Atomically replace prometheus.yml on the VPS — AND mirror to git.

    Order:
      1. Dump YAML body once.
      2. scp + sudo install on vps1 (runtime gate — if reload would fail,
         it'll fail here and we know not to mirror).
      3. Mirror the same body to the local source-controlled copy under
         ``configs/prometheus/prometheus.yml`` (best-effort; never throws).

    The git mirror was added 2026-06-13 after a drift audit found
    `configs/prometheus/prometheus.yml` md5 != vps1's for an unknown number
    of weeks — every `add_scrape_target` / `add_aro_wake_target` call since
    PR1 had written to vps1 only. With the mirror, the operator's `git
    status` surfaces the diff on the next commit; the snapshot stays
    truthful instead of bit-rotting.
    """
    body = yaml_lib.dump(data, default_flow_style=False, sort_keys=False)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(body)
        local_tmp = f.name
    vps_tmp = "/tmp/prometheus.yml.staged"  # nosec B108 — single-tenant VPS staging file for scp+mv into /opt/monitoring/configs/prometheus/
    try:
        scp_to_vps(local_tmp, vps_tmp)
        ssh(
            f"sudo mv {shlex.quote(vps_tmp)} {shlex.quote(PROMETHEUS_CONFIG_PATH)} && "
            f"sudo chown root:root {shlex.quote(PROMETHEUS_CONFIG_PATH)} && "
            f"sudo chmod 644 {shlex.quote(PROMETHEUS_CONFIG_PATH)}"
        )
    finally:
        Path(local_tmp).unlink(missing_ok=True)
    # Git mirror — best-effort. A read-only filesystem, missing directory,
    # or unset FABRIK_ROOT in CI/test must not block the runtime write.
    if _LOCAL_PROMETHEUS_CONFIG_PATH is not None:
        try:
            _LOCAL_PROMETHEUS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            _LOCAL_PROMETHEUS_CONFIG_PATH.write_text(body)
            logger.debug("mirrored prometheus.yml to %s", _LOCAL_PROMETHEUS_CONFIG_PATH)
        except Exception as e:  # noqa: BLE001 — mirror is best-effort
            logger.warning("failed to mirror prometheus.yml to git: %s", e)


def _reload_prometheus() -> bool:
    """Hot-reload Prometheus; fall back to container restart on failure.

    Returns True if either path succeeded. We always succeed-or-warn
    because the config is already written — a reload failure means
    "the new target won't show up until next restart", not "the deploy
    is broken".
    """
    # Hot-reload first (fast, no scrape-gap). Run from inside alertmanager
    # since it shares the monitoring Docker network and has curl.
    # Container name pattern: `^<name>(-|$)` matches both the canonical bare
    # name (e.g. `alertmanager` — what's live since the Coolify migration)
    # AND any legacy `<name>-<suffix>` form. The old pattern `^alertmanager-`
    # silently no-matched the bare names and `_reload_prometheus` always
    # fell through to "non-fatal" — verified live 2026-06-08 during the vps4
    # drill follow-up cleanup.
    try:
        ssh(
            f"sudo docker exec $(sudo docker ps --format '{{{{.Names}}}}' "
            f"| grep -E '^alertmanager(-|$)' | head -1) "
            f"wget -qO- --post-data='' {shlex.quote(PROMETHEUS_RELOAD_URL)}",
            timeout=15,
        )
        logger.info("Prometheus hot-reload succeeded")
        return True
    except Exception as e:  # noqa: BLE001 — bounded fallback
        logger.info("Prometheus hot-reload failed (%s); trying container restart", e)

    try:
        ssh(
            "PROM_CONTAINER=$(sudo docker ps --format '{{.Names}}' "
            "| grep -E '^prometheus(-|$)' | head -1) && "
            'sudo docker restart "$PROM_CONTAINER"',
            timeout=30,
        )
        logger.info("Prometheus container restarted")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("Prometheus reload AND restart both failed (non-fatal): %s", e)
        return False


def _build_job_block(
    service_name: str,
    target: str,
    metrics_path: str,
    scheme: str,
    interval: str,
    bearer_token: str | None,
) -> dict[str, Any]:
    """Render the YAML mapping for a single scrape job."""
    job: dict[str, Any] = {
        "job_name": _job_name(service_name),
        "scheme": scheme,
        "metrics_path": metrics_path,
        "scrape_interval": interval,
        "static_configs": [{"targets": [target]}],
    }
    if bearer_token:
        # Prometheus uses the ``authorization`` block (not the older
        # ``bearer_token`` shortcut, which is deprecated as of 2.26).
        job["authorization"] = {"type": "Bearer", "credentials": bearer_token}
    return job


def add_scrape_target(
    service_name: str,
    domain: str | None = None,
    *,
    target: str | None = None,
    metrics_path: str = DEFAULT_METRICS_PATH,
    scheme: str = "https",
    interval: str = DEFAULT_INTERVAL,
    bearer_token: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Register ``service_name`` as a Prometheus scrape target.

    Idempotent: a job named ``fabrik-<service_name>`` already in
    ``scrape_configs`` returns ``status=exists`` without rewriting.

    Args:
        service_name: Service name. Becomes the suffix of the job name
            (``fabrik-<service_name>``).
        domain: Public domain (e.g. ``"app.vps1.ocoron.com"``). Used to
            derive the default target ``<domain>:443`` and is REQUIRED
            unless ``target`` is provided explicitly.
        target: Optional explicit target like ``"my-service:8080"`` for
            internal-network scraping. When set, ``domain`` is ignored
            (and ``scheme`` defaults should be flipped to ``http``).
        metrics_path: HTTP path Prometheus scrapes. Default ``/metrics``.
        scheme: ``"https"`` (default) or ``"http"``. Flip to ``http``
            when scraping over the internal Docker network.
        interval: Go-style duration string. Default ``30s``.
        bearer_token: Optional bearer token for protected ``/metrics``
            endpoints. Embedded as ``authorization: {type: Bearer, ...}``.
        dry_run: Log intent and return without touching the VPS.

    Returns:
        ``{"status": "created" | "exists" | "dry_run",
           "job": "fabrik-<name>",
           "target": "<resolved-target>"}``

    Raises:
        ValueError: any input failed validation.
        RuntimeError: SSH or YAML parse failure.
    """
    _validate_name(service_name)
    if target is None:
        if domain is None:
            raise ValueError("add_scrape_target requires either domain or explicit target")
        _validate_domain(domain)
        target = f"{domain}:443" if scheme == "https" else f"{domain}:80"
    if metrics_path[:1] != "/" or '"' in metrics_path or "'" in metrics_path:
        raise ValueError(
            f"Invalid metrics_path {metrics_path!r}: must start with / and contain no quotes"
        )

    job_name = _job_name(service_name)

    if dry_run:
        logger.info(
            "[DRY RUN] Would add Prometheus scrape target %s -> %s://%s%s",
            job_name,
            scheme,
            target,
            metrics_path,
        )
        return {"status": "dry_run", "job": job_name, "target": target}

    config = _read_config()
    scrape_configs: list[dict[str, Any]] = config.setdefault("scrape_configs", [])

    for job in scrape_configs:
        if isinstance(job, dict) and job.get("job_name") == job_name:
            logger.info("Prometheus scrape target already exists: %s", job_name)
            return {"status": "exists", "job": job_name, "target": target}

    scrape_configs.append(
        _build_job_block(
            service_name=service_name,
            target=target,
            metrics_path=metrics_path,
            scheme=scheme,
            interval=interval,
            bearer_token=bearer_token,
        )
    )

    _write_config(config)
    _reload_prometheus()
    logger.info(
        "Added Prometheus scrape target: %s -> %s://%s%s",
        job_name,
        scheme,
        target,
        metrics_path,
    )
    return {"status": "created", "job": job_name, "target": target}


def remove_scrape_target(service_name: str, dry_run: bool = False) -> bool:
    """Remove the Fabrik-managed scrape target for ``service_name``.

    Best-effort: any failure is logged at WARNING and returns False so
    rollback / destroy can continue unwinding other registrars.

    Args:
        service_name: Service name to remove (looks for
            ``fabrik-<service_name>``).
        dry_run: Log intent and return True.

    Returns:
        True on successful removal, ``not_found``, or dry_run; False on
        SSH/YAML failure.
    """
    _validate_name(service_name)
    job_name = _job_name(service_name)

    if dry_run:
        logger.info("[DRY RUN] Would remove Prometheus scrape target: %s", job_name)
        return True

    try:
        config = _read_config()
    except Exception as e:  # noqa: BLE001
        logger.warning("Prometheus config unreadable, removal skipped: %s", e)
        return False

    scrape_configs: list[dict[str, Any]] = config.get("scrape_configs", []) or []
    before = len(scrape_configs)
    scrape_configs[:] = [
        job
        for job in scrape_configs
        if not (isinstance(job, dict) and job.get("job_name") == job_name)
    ]
    if len(scrape_configs) == before:
        logger.info("Prometheus scrape target already absent: %s", job_name)
        return True

    config["scrape_configs"] = scrape_configs
    try:
        _write_config(config)
    except Exception as e:  # noqa: BLE001
        logger.warning("Prometheus config rewrite failed (non-fatal): %s", e)
        return False

    _reload_prometheus()
    logger.info("Removed Prometheus scrape target: %s", job_name)
    return True


def list_scrape_targets() -> list[dict[str, Any]]:
    """Return the full list of scrape jobs (Fabrik + infra).

    Used by ``fabrik vps-sync --verify`` to detect orphan jobs (jobs
    for services no longer in ``data/projects.yaml``).
    """
    config = _read_config()
    return list(config.get("scrape_configs") or [])


# ---------------------------------------------------------------------------
# aro-wake job: add/remove spoke targets inside the SHARED `aro-wake` scrape
# job (NOT a new `fabrik-<spoke>` job — the trio uses a single job with one
# `static_configs` entry per fleet host). Used by `fabrik vultr provision`
# to make a new spoke metrics-visible, and by `... destroy --reverse-fleet-add`
# to remove it cleanly. Added 2026-06-08 after the live vps4 drill caught
# that `provision` left the spoke invisible to Prometheus.
# ---------------------------------------------------------------------------

ARO_WAKE_JOB_NAME = "aro-wake"
ARO_WAKE_PORT = 8201


def add_aro_wake_target(spoke_name: str, mesh_ip: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Add ``<spoke_name>`` as a target inside the existing ``aro-wake`` job.

    Appends a ``{targets: [<mesh_ip>:8201], labels: {host: <spoke>, role: spoke}}``
    entry — matching the live shape verified 2026-06-08:

        - job_name: aro-wake
          static_configs:
            - targets: ['10.0.1.1:8201']
              labels: {host: vps1, role: hub}
            - targets: ['10.99.0.2:8201']
              labels: {host: vps2, role: spoke}
            ...

    Idempotent: if ``<mesh_ip>:8201`` is already in any ``static_configs``
    entry of the ``aro-wake`` job, returns ``status=exists`` without
    rewriting the file.

    Raises ``RuntimeError`` if the ``aro-wake`` job itself doesn't exist
    in ``prometheus.yml`` — the caller should not have asked us to graft
    a spoke onto a non-existent job.
    """
    _validate_name(spoke_name)
    target = f"{mesh_ip}:{ARO_WAKE_PORT}"
    if dry_run:
        logger.info("[DRY RUN] Would add aro-wake target %s (host=%s)", target, spoke_name)
        return {"status": "dry_run", "target": target, "host": spoke_name}

    config = _read_config()
    job = next(
        (j for j in config.get("scrape_configs", []) if j.get("job_name") == ARO_WAKE_JOB_NAME),
        None,
    )
    if job is None:
        raise RuntimeError(
            f"aro-wake job not present in {PROMETHEUS_CONFIG_PATH}; cannot add spoke target"
        )

    for sc in job.get("static_configs", []) or []:
        if target in (sc.get("targets") or []):
            logger.info("Prometheus aro-wake already has target %s; no-op", target)
            return {"status": "exists", "target": target, "host": spoke_name}

    job.setdefault("static_configs", []).append(
        {
            "targets": [target],
            "labels": {"host": spoke_name, "role": "spoke"},
        }
    )
    _write_config(config)
    _reload_prometheus()
    logger.info("Added aro-wake target %s (host=%s)", target, spoke_name)
    return {"status": "created", "target": target, "host": spoke_name}


def remove_aro_wake_target(spoke_name: str, *, dry_run: bool = False) -> bool:
    """Remove ``<spoke_name>`` from the ``aro-wake`` job's static_configs.

    Matches by ``labels.host`` (NOT by target IP) — so even if the spoke's
    mesh IP rotated between provision and destroy, we still pull the right
    entry. Idempotent: returns True when nothing matched.
    """
    _validate_name(spoke_name)
    if dry_run:
        logger.info("[DRY RUN] Would remove aro-wake target with host=%s", spoke_name)
        return True

    config = _read_config()
    job = next(
        (j for j in config.get("scrape_configs", []) if j.get("job_name") == ARO_WAKE_JOB_NAME),
        None,
    )
    if job is None:
        logger.info("aro-wake job not in prometheus.yml; nothing to remove")
        return True

    static_configs = job.get("static_configs", []) or []
    before = len(static_configs)
    job["static_configs"] = [
        sc for sc in static_configs if (sc.get("labels") or {}).get("host") != spoke_name
    ]
    if len(job["static_configs"]) == before:
        logger.info("aro-wake had no target for host=%s; nothing to remove", spoke_name)
        return True

    _write_config(config)
    _reload_prometheus()
    logger.info("Removed aro-wake target for host=%s", spoke_name)
    return True


__all__ = (
    "PROMETHEUS_CONFIG_PATH",
    "PROMETHEUS_RELOAD_URL",
    "DEFAULT_METRICS_PATH",
    "DEFAULT_INTERVAL",
    "JOB_PREFIX",
    "ARO_WAKE_JOB_NAME",
    "ARO_WAKE_PORT",
    "add_scrape_target",
    "remove_scrape_target",
    "list_scrape_targets",
    "add_aro_wake_target",
    "remove_aro_wake_target",
)
