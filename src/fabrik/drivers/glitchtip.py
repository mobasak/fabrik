"""GlitchTip error-tracking project provisioning (Sentry-compatible API).

Wraps three live-captured GlitchTip API endpoints (see
``docs/reference/glitchtip-api.md`` — probe-anchored 2026-04-18):

* ``POST /api/0/teams/{org}/{team}/projects/`` — create project, returns 201
* ``GET  /api/0/projects/{org}/{slug}/keys/``  — fetch DSN, returns 200
* ``DELETE /api/0/projects/{org}/{slug}/``     — cleanup, returns 204

The driver is **opt-in by shape**: only projects that declare error
tracking (``shape.has_error_tracking`` truthy OR, as a convenience,
``shape.kind in {"service", "worker", "wordpress"}``) go through this
registrar. See :func:`applies_to` for the canonical predicate — same
pattern as :mod:`fabrik.drivers.meilisearch`.

Design notes
------------

* **Idempotent create.** GlitchTip returns HTTP 400 when a name collides
  (verified against the probe). The driver first GETs the project; if
  it exists, it short-circuits and fetches the DSN for the EXISTING
  project rather than failing. This mirrors the behavior expected by
  the orchestrator (Phase 4h) — rerunning ``fabrik apply`` on the same
  project must never error out on "already provisioned".

* **DSN stored as-is.** The captured probe shows GlitchTip emits DSNs
  with ``localhost:8000`` as the host (the service's own
  ``GLITCHTIP_DOMAIN`` env var is unset upstream). This is a deployment
  gap documented in ``docs/reference/glitchtip-api.md §"Known
  configuration gap"`` — the driver intentionally does NOT post-process
  the DSN. Misconfiguration surfaces to the operator rather than being
  masked.

* **DSN injection verification.** :func:`verify_dsn_injection` polls
  the deployed container via SSH+``printenv`` until ``SENTRY_DSN``
  matches the value the driver stored — ground truth for "Coolify's
  PATCH + deploy(force=True) actually propagated the env var to the
  running container". Without this check, a silent Coolify error
  would leave the app running with a stale/missing DSN.

* **Never logs the token.** Auth header building is encapsulated in
  :func:`_headers` and the token is only ever retrieved via
  ``os.getenv`` (not passed as a function argument) so it cannot be
  captured in stack traces or log payloads.

Environment
-----------

The following keys must live in FABRIK_CORE of ``/opt/fabrik/.env``
(per LESSONS_LEARNT §8.16, above the ``AUTO_BEGIN_SENTINEL``):

* ``GLITCHTIP_AUTH_TOKEN`` — Bearer token with ``project:read|write|admin``
  + ``team:admin`` scopes (bitfield mask 71). Generate via GlitchTip
  UI → Profile → Auth Tokens, OR via the in-container
  ``manage.py shell`` recipe in the Phase 4-pre artifacts.
* ``GLITCHTIP_ORG_SLUG`` — organization slug (``ocoron`` on the Fabrik VPS).
* ``GLITCHTIP_TEAM_SLUG`` — team slug (``vps1`` on the Fabrik VPS).
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import requests

from fabrik.drivers.ssh import ssh

logger = logging.getLogger(__name__)

GLITCHTIP_URL = "https://errors.vps1.ocoron.com"
"""Public base URL. The driver targets the REST API (``/api/0/*``) only;
this URL never serves a human UI in driver code paths."""

SHAPE_FLAG = "has_error_tracking"
"""Primary shape-gating key. Parallel to :mod:`fabrik.drivers.meilisearch`'s
``has_search_feature``. A project opts in via ``fabrik scaffold
--has-error-tracking`` or by setting the flag in ``spec.yaml``."""

SERVICE_KINDS = frozenset({"service", "worker", "wordpress"})
"""Project kinds that default to error-tracking if the explicit flag is
absent. Matches the Deployment Workflow §6b default matrix."""

_DEFAULT_TIMEOUT = 15
"""HTTP timeout for all GlitchTip calls. 15s is well above the probe's
observed p99 latency (~400ms) and below the orchestrator's step budget."""

_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,127}$")
"""GlitchTip project-name validator. Stricter than GlitchTip's own
(accepts leading alphanumeric + ``_``/``-``, max 128 chars). Rationale:
same regex as :mod:`fabrik.drivers.meilisearch` for cross-driver
consistency — the scaffold emits one project name that must satisfy
every downstream registrar's constraints."""


def applies_to(shape: dict[str, Any]) -> bool:
    """Return True iff this driver should provision an error-tracking project.

    Two independent triggers — either is sufficient:

    1. **Explicit opt-in**: ``shape[SHAPE_FLAG]`` is truthy. This is
       the canonical path (set via ``fabrik scaffold --has-error-tracking``
       or ``spec.yaml``).
    2. **Kind-based default**: ``shape["kind"]`` is in
       :data:`SERVICE_KINDS`. Rationale: services/workers/WordPress
       sites essentially always want error reporting; requiring an
       extra flag for them creates avoidable friction in the common
       case. A project can opt OUT by setting ``has_error_tracking: False``
       explicitly — an explicit False overrides the kind-based default.

    Non-dict input, missing keys, or a truthy ``SHAPE_FLAG`` default
    all fall back to the conservative "don't provision".

    Args:
        shape: Project shape dict.

    Returns:
        True if the orchestrator should call :func:`create_project`.
    """
    if not isinstance(shape, dict):
        return False
    # Explicit opt-out takes precedence over kind-based default
    if SHAPE_FLAG in shape and shape.get(SHAPE_FLAG) in (False, None):
        return False
    if shape.get(SHAPE_FLAG):
        return True
    return shape.get("kind") in SERVICE_KINDS


def _validate_name(name: str) -> None:
    """Raise :class:`ValueError` if ``name`` is not a safe project name."""
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValueError(
            f"Invalid GlitchTip project name {name!r}: must match [a-zA-Z0-9][a-zA-Z0-9_-]{{0,127}}"
        )


def _headers() -> dict[str, str]:
    """Build the Bearer auth header. Never logs or returns the token."""
    token = os.getenv("GLITCHTIP_AUTH_TOKEN")
    if not token:
        raise RuntimeError(
            "GLITCHTIP_AUTH_TOKEN not set in /opt/fabrik/.env "
            "(FABRIK_CORE section — above the AUTO_BEGIN_SENTINEL). "
            "Create a personal auth token (scopes: project:read, "
            "project:write, project:admin, team:admin) in the GlitchTip "
            "UI → Profile → Auth Tokens, OR follow the manage.py shell "
            "recipe in docs/reference/glitchtip-api.md."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _org_team() -> tuple[str, str]:
    """Read the org+team slugs from env. Raises with a remediation hint."""
    org = os.getenv("GLITCHTIP_ORG_SLUG")
    team = os.getenv("GLITCHTIP_TEAM_SLUG")
    if not org or not team:
        raise RuntimeError(
            "GLITCHTIP_ORG_SLUG and GLITCHTIP_TEAM_SLUG must be set in "
            "/opt/fabrik/.env (FABRIK_CORE section). On the Fabrik VPS "
            "the canonical values are GLITCHTIP_ORG_SLUG=ocoron and "
            "GLITCHTIP_TEAM_SLUG=vps1 — capture them via the live "
            "`/api/0/organizations/{slug}/teams/` probe if unsure."
        )
    return org, team


def _project_url(org: str, name: str) -> str:
    return f"{GLITCHTIP_URL}/api/0/projects/{org}/{name}/"


def _keys_url(org: str, name: str) -> str:
    return f"{GLITCHTIP_URL}/api/0/projects/{org}/{name}/keys/"


def _project_exists(org: str, name: str, headers: dict[str, str]) -> bool:
    """Return True iff GET ``/api/0/projects/{org}/{name}/`` returns 200."""
    resp = requests.get(_project_url(org, name), headers=headers, timeout=_DEFAULT_TIMEOUT)
    if resp.status_code == 200:
        return True
    if resp.status_code == 404:
        return False
    # Any other status is a real error — don't silently treat as "doesn't
    # exist" because that would make create_project blindly POST and
    # potentially double-create or surface a misleading 400.
    resp.raise_for_status()
    return False  # unreachable


def _fetch_dsn(org: str, name: str, headers: dict[str, str]) -> str:
    """Fetch the public DSN for an existing project.

    Returns the first key's ``dsn.public`` value — verified shape
    matches ``docs/reference/glitchtip-api.md §Endpoint 2``.
    """
    resp = requests.get(_keys_url(org, name), headers=headers, timeout=_DEFAULT_TIMEOUT)
    resp.raise_for_status()
    keys = resp.json()
    if not isinstance(keys, list) or not keys:
        raise RuntimeError(
            f"GlitchTip project {name!r} has no client keys — "
            f"expected auto-created default key, got {keys!r}"
        )
    dsn = keys[0].get("dsn", {}).get("public")
    if not isinstance(dsn, str) or not dsn:
        raise RuntimeError(f"GlitchTip project {name!r}: missing dsn.public in keys payload")
    return dsn


def create_project(
    name: str,
    platform: str = "python",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a GlitchTip project and return its DSN. Idempotent on ``name``.

    Args:
        name: Project slug. Must match ``[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}``.
        platform: One of GlitchTip's platform tags (``python``, ``javascript``,
            ``node``, etc.). Used only for UI filtering; not security-relevant.
        dry_run: Skip all network calls.

    Returns:
        ``{"status": "created" | "exists" | "dry_run",
           "project": name,
           "dsn": <public-DSN-or-None>}``

    Raises:
        ValueError: ``name`` or ``platform`` failed validation.
        RuntimeError: required env vars missing, project has no keys, or
            the create call failed with a non-idempotent 4xx/5xx.
        requests.HTTPError: transport-layer error (bubbles up; the
            orchestrator decides whether to retry).
    """
    _validate_name(name)
    _validate_name(platform)  # same charset constraints; small whitelist anyway

    if dry_run:
        logger.info("[DRY RUN] Would create GlitchTip project: %s", name)
        return {"status": "dry_run", "project": name, "dsn": None}

    org, team = _org_team()
    headers = _headers()

    # Idempotency check — cheaper than a POST and deterministic regardless
    # of whether GlitchTip returns 400, 409, or something else on collision.
    if _project_exists(org, name, headers):
        logger.info("GlitchTip project already exists: %s", name)
        return {
            "status": "exists",
            "project": name,
            "dsn": _fetch_dsn(org, name, headers),
        }

    create_resp = requests.post(
        f"{GLITCHTIP_URL}/api/0/teams/{org}/{team}/projects/",
        json={"name": name, "platform": platform},
        headers=headers,
        timeout=_DEFAULT_TIMEOUT,
    )
    if create_resp.status_code not in (200, 201):
        # Probe-confirmed success is 201 — 200 accepted for version drift
        create_resp.raise_for_status()

    dsn = _fetch_dsn(org, name, headers)
    logger.info("GlitchTip project %s created (dsn prefix=%s...)", name, dsn[:30])
    return {"status": "created", "project": name, "dsn": dsn}


def delete_project(name: str, dry_run: bool = False) -> bool:
    """Rollback handler — best-effort project delete. Never raises.

    Args:
        name: Project slug.
        dry_run: No-op, returns True.

    Returns:
        True on success (HTTP 204, 200, or 404 — all acceptable outcomes
        for a rollback); False on any network/auth error (logged at
        WARNING, not re-raised — the orchestrator's rollback pass must
        never fail harder than the original deploy).
    """
    _validate_name(name)

    if dry_run:
        logger.info("[DRY RUN] Would delete GlitchTip project: %s", name)
        return True

    try:
        org, _ = _org_team()
        resp = requests.delete(
            _project_url(org, name),
            headers=_headers(),
            timeout=_DEFAULT_TIMEOUT,
        )
        # 204 = success per probe; 200 accepted for version drift; 404 = already gone.
        if resp.status_code in (200, 204, 404):
            logger.info("Deleted GlitchTip project %s (status=%d)", name, resp.status_code)
            return True
        logger.warning(
            "GlitchTip delete_project %s returned HTTP %d (non-fatal): %s",
            name,
            resp.status_code,
            resp.text[:200],
        )
        return False
    except Exception as e:  # noqa: BLE001 — rollback must not raise
        logger.warning("GlitchTip delete_project %s failed (non-fatal): %s", name, e)
        return False


def verify_dsn_injection(
    project_name: str,
    expected_dsn: str,
    max_wait: int = 60,
    poll_interval: float = 2.0,
    coolify_app_uuid: str | None = None,
) -> bool:
    """Poll the running container until ``SENTRY_DSN`` matches ``expected_dsn``.

    Coolify's ``PATCH /services/{uuid}/env`` + ``POST /deploy?force=true``
    returns before the new env vars land in the running container — the
    container has to be re-created with the updated env-file mount. This
    is the ground-truth check for "DSN injection actually happened".

    Resolution strategy — the container is found by **name prefix match**,
    not by an exact container name (Coolify suffixes every container with
    a UUID that changes on recreate). Same pattern as
    :mod:`fabrik.drivers.gatus.restart_endpoint_container`.

    Args:
        project_name: The Coolify project's short name. The container
            will be named ``<project_name>-<uuid>``.
        expected_dsn: The DSN value :func:`create_project` returned.
        max_wait: Total seconds to wait before giving up.
        poll_interval: Seconds between checks. 2s is the sweet spot —
            fast enough to catch the redeploy mid-bounce, slow enough
            not to spam the VPS.

    Returns:
        True if a matching ``SENTRY_DSN`` is observed within ``max_wait``;
        False otherwise. Does NOT raise — the orchestrator decides
        whether to rollback (:func:`delete_project`) or escalate.
    """
    if not expected_dsn:
        raise ValueError("expected_dsn must be non-empty")

    start = time.time()
    attempts = 0
    while time.time() - start < max_wait:
        attempts += 1
        # Match container by either:
        #   1. Coolify's auto-name ``<name>-<uuid>-<ts>`` (prefix + trailing dash)
        #   2. An explicit ``container_name: <name>`` set by the compose
        #      template (exact match, no suffix)
        #   3. Coolify's app-uuid embedded in the name as ``<svc>-<uuid>-<ts>``
        #      when the compose service is generic (e.g. ``app:``) — the
        #      project_name prefix won't match in that case but the Coolify
        #      app uuid is unique per resource and always present.
        # A project may be recreated mid-deploy, so the container name may
        # not exist yet for the first few polls.
        if coolify_app_uuid:
            grep_expr = f"^{project_name}(-|$)|-{coolify_app_uuid}-"
        else:
            grep_expr = f"^{project_name}(-|$)"
        container = ssh(
            f"sudo docker ps --format '{{{{.Names}}}}' | grep -E '{grep_expr}' | head -1"
        ).strip()
        if container:
            # Read the env var from Docker daemon metadata rather than
            # ``docker exec printenv``. The latter requires a shell in the
            # image (fails on scratch/distroless/whoami with
            # ``OCI runtime exec failed``), while ``docker inspect`` is a
            # daemon-side read that works for any image. Format string
            # extracts just the SENTRY_DSN value from Config.Env.
            actual = ssh(
                f"sudo docker inspect {container} "
                f"--format '{{{{range .Config.Env}}}}{{{{println .}}}}{{{{end}}}}' "
                f"2>/dev/null | grep '^SENTRY_DSN=' | cut -d= -f2- || echo ''"
            ).strip()
            if actual == expected_dsn:
                logger.info(
                    "SENTRY_DSN injection verified for %s after %d attempt(s)",
                    project_name,
                    attempts,
                )
                return True
        time.sleep(poll_interval)

    logger.warning(
        "SENTRY_DSN injection NOT verified for %s after %ds (%d attempts)",
        project_name,
        max_wait,
        attempts,
    )
    return False


__all__ = (
    "GLITCHTIP_URL",
    "SHAPE_FLAG",
    "SERVICE_KINDS",
    "applies_to",
    "create_project",
    "delete_project",
    "verify_dsn_injection",
)
