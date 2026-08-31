"""Per-service Redis logical-DB index allocation on the shared ``redis-main``.

Closes ``DEPLOYMENT.md §9.9 G4`` — until now every Fabrik service that
needed Redis shared the same Coolify Redis with no namespace isolation,
so a stray ``FLUSHDB`` in one service would silently nuke another's
state. This driver hands each service a unique logical DB index
(0..15 — Redis's stock `databases` setting) and persists the mapping
in a registry file on the VPS.

Design notes
------------
* **Registry on disk, not in Redis.** A sidecar JSON file at
  ``/opt/monitoring/configs/redis/assignments.json`` is the source of
  truth. Storing the registry inside Redis itself would be
  self-referential — a service that calls ``FLUSHDB`` on the registry
  DB destroys the very mapping that should have isolated it. The file
  lives next to the existing monitoring configs (Gatus, Prometheus)
  so ops already have the right backup / git-versioning patterns.
* **Atomic write via ``sudo mv``.** Same pattern as
  :mod:`fabrik.drivers.gatus` — stage to ``/tmp/...``, then ``mv`` so
  a torn write can never corrupt the registry.
* **Idempotent** — calling :func:`acquire_db_index` twice with the same
  ``service_name`` returns the same index without reallocation. This
  is the property the orchestrator relies on for ``fabrik redeploy
  --refresh-infra``.
* **DB 0 is reserved.** The default Redis CLI lands you on DB 0; we
  hand out 1..15 so an interactive ``redis-cli`` session never collides
  with a service's namespace. 15 services is plenty — when we outgrow
  it, the fix is a second ``redis-isolated-N`` container, not raising
  the cap. (Redis docs explicitly recommend separate instances over
  >16 logical DBs for production.)
* **Capacity** — emits a ``RuntimeError`` if all 15 indices are taken,
  rather than silently returning DB 0. A noisy failure is the only way
  the operator finds out fast enough to act.
* **No live Redis touch.** This driver only manipulates the registry
  file; it does NOT call into the Redis container. The actual
  ``REDIS_URL=redis://redis-main:6379/<n>`` injection happens in
  :class:`fabrik.orchestrator.infrastructure.InfrastructureProvisioner`
  via the SSH+Compose deployer's ``.env`` merge + ``docker compose up
  -d`` restart, the same pattern used for ``SENTRY_DSN``.
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fabrik.drivers.ssh import scp_to_vps, ssh
from fabrik.locks_local import file_lock

logger = logging.getLogger(__name__)

REDIS_REGISTRY_PATH = "/opt/monitoring/configs/redis/assignments.json"
"""VPS path holding ``{service_name: db_index}`` JSON map."""

REDIS_CONTAINER = "redis-main"
"""Verified container name on VPS (2026-05-05). Same instance shared by
every Fabrik service. Coolify's own Redis (``coolify-redis``) is for
the platform itself and explicitly off-limits to user services."""

REDIS_FIRST_INDEX = 1
"""Lowest DB index handed out. ``0`` is reserved for ad-hoc CLI use so
``redis-cli`` interactive sessions never collide with a service."""

REDIS_LAST_INDEX = 15
"""Highest DB index handed out. Matches Redis's stock ``databases 16``
setting; raising it requires a Redis config change AND a doc update."""

_SERVICE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
"""Service-name validator. Same charset as Gatus's project-name regex
so the two drivers agree on what a 'service name' looks like."""


def _validate_service_name(name: str) -> None:
    if not isinstance(name, str) or not _SERVICE_RE.match(name):
        raise ValueError(
            f"Invalid service name {name!r}: must match [a-zA-Z0-9][a-zA-Z0-9_-]{{0,63}}"
        )


def extract_assignments(data: dict) -> dict[str, int]:
    """Return the ``{service: db_index}`` map from either registry shape.

    The live file is a versioned ENVELOPE — ``{"version": 1, "last_updated":
    ..., "assignments": {...}, "free_indexes": [...]}`` (same convention as
    the postgres driver's allocations file); the flat ``{service: index}``
    map is the legacy shape this driver used to assume. Bare ``int()`` over
    envelope values crashed on the ``last_updated`` timestamp and the deploy
    printed green anyway (finding 01M1CKEK, tryton-crm 2026-08-31) — so the
    envelope had NEVER been read successfully. Shared with ``audit_redis``,
    which had the same blind spot (``sid in <envelope>`` is always False).
    """
    if isinstance(data.get("assignments"), dict):
        version = data.get("version")
        if version is not None and version != 1:
            raise RuntimeError(
                f"Redis registry at {REDIS_REGISTRY_PATH} is version {version!r}; this "
                f"driver understands version 1 only — refusing to read (a write here "
                f"would silently downgrade the newer schema)"
            )
        inner = data["assignments"]
    else:
        inner = data
    out: dict[str, int] = {}
    for k, v in inner.items():
        # bool first: it subclasses int, and True silently becoming index 1
        # would double-book whoever legitimately holds 1. int() (not
        # .isdigit()) does the string parse so historically-accepted forms
        # like " 7" keep working while unicode digits int() rejects fail.
        if isinstance(v, bool) or not isinstance(v, int | str):
            raise RuntimeError(
                f"Redis registry entry {k!r} has non-integer db index {v!r} — "
                f"fix {REDIS_REGISTRY_PATH} by hand before deploying"
            )
        try:
            idx = int(v)
        except ValueError:
            raise RuntimeError(
                f"Redis registry entry {k!r} has non-integer db index {v!r} — "
                f"fix {REDIS_REGISTRY_PATH} by hand before deploying"
            ) from None
        if not 0 <= idx <= REDIS_LAST_INDEX:
            raise RuntimeError(
                f"Redis registry entry {k!r} has out-of-range db index {idx} "
                f"(valid 0..{REDIS_LAST_INDEX}) — fix {REDIS_REGISTRY_PATH}"
            )
        out[str(k)] = idx
    by_index: dict[int, list[str]] = {}
    for svc, idx in out.items():
        by_index.setdefault(idx, []).append(svc)
    double_booked = {i: svcs for i, svcs in by_index.items() if len(svcs) > 1}
    if double_booked:
        raise RuntimeError(
            f"Redis registry double-books db index(es) {double_booked} — two services "
            f"sharing one logical DB defeats the isolation this registry exists for; "
            f"fix {REDIS_REGISTRY_PATH} by hand before deploying"
        )
    return out


def _read_registry() -> dict[str, int]:
    """Load the registry, returning ``{}`` when the file is absent.

    Absent file == fresh install; we lazily create it on first write.
    """
    raw = ssh(
        f"sudo test -f {shlex.quote(REDIS_REGISTRY_PATH)} && "
        f"sudo cat {shlex.quote(REDIS_REGISTRY_PATH)} || echo '{{}}'",
        timeout=15,
    )
    try:
        data = json.loads(raw.strip() or "{}")
    except json.JSONDecodeError as e:
        # Don't let a manually-edited bad file silently allocate a fresh
        # DB index — that would double-book whoever's already in there.
        raise RuntimeError(f"Redis registry at {REDIS_REGISTRY_PATH} is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError(f"Redis registry at {REDIS_REGISTRY_PATH} must be a JSON object")
    return extract_assignments(data)


def _write_registry(registry: dict[str, int]) -> None:
    """Atomically replace the registry file, always in the envelope shape.

    The envelope is what lives on the box and what the postgres driver's
    allocations file also uses; writing the legacy flat map here would
    strip the metadata the envelope carries. ``free_indexes`` lists every
    unassigned index over the full ``0..15`` range — index 0 appears free
    in the FILE because it is unassigned; the driver's own allocator still
    never hands it out (``REDIS_FIRST_INDEX`` reserves it for CLI use).
    """
    used = set(registry.values())
    envelope = {
        "version": 1,
        "last_updated": datetime.now(UTC).isoformat(timespec="seconds"),
        "assignments": dict(sorted(registry.items())),
        "free_indexes": [i for i in range(REDIS_LAST_INDEX + 1) if i not in used],
    }
    body = json.dumps(envelope, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(body)
        local_tmp = f.name
    vps_tmp = "/tmp/redis-assignments.json"  # nosec B108 — single-tenant VPS staging file for scp+mv into /opt/monitoring/configs/redis/
    try:
        # Ensure parent dir exists; -p is idempotent.
        ssh(
            f"sudo mkdir -p {shlex.quote(str(Path(REDIS_REGISTRY_PATH).parent))}",
            timeout=10,
        )
        scp_to_vps(local_tmp, vps_tmp)
        ssh(
            f"sudo mv {shlex.quote(vps_tmp)} {shlex.quote(REDIS_REGISTRY_PATH)} && "
            f"sudo chown root:root {shlex.quote(REDIS_REGISTRY_PATH)} && "
            f"sudo chmod 644 {shlex.quote(REDIS_REGISTRY_PATH)}"
        )
    finally:
        Path(local_tmp).unlink(missing_ok=True)


def _next_free_index(registry: dict[str, int]) -> int:
    """Return the lowest unused DB index in ``[FIRST_INDEX, LAST_INDEX]``.

    Raises:
        RuntimeError: All 15 slots are full. Operator must either drop
            a stale assignment (``release_db_index``) or stand up a
            second Redis container.
    """
    used = set(registry.values())
    for i in range(REDIS_FIRST_INDEX, REDIS_LAST_INDEX + 1):
        if i not in used:
            return i
    raise RuntimeError(
        f"Redis logical-DB pool exhausted "
        f"({REDIS_LAST_INDEX - REDIS_FIRST_INDEX + 1} slots in use). "
        f"Drop a stale assignment via release_db_index or provision "
        f"a second Redis instance."
    )


def acquire_db_index(
    service_name: str,
    container: str = REDIS_CONTAINER,
    dry_run: bool = False,
) -> dict:
    """Reserve (or look up) a Redis logical-DB index for ``service_name``.

    Idempotent. The first call allocates the lowest free index in
    ``[1, 15]``; subsequent calls return the same index without
    reallocation — that's what makes ``fabrik redeploy --refresh-infra``
    safe to run repeatedly.

    Args:
        service_name: Service name. Becomes the registry key.
        container: Redis container name. Used only for the returned
            ``redis_url``; the registry file itself is container-agnostic.
        dry_run: Skip the registry write; return the would-be index.

    Returns:
        ``{"status": "created" | "exists" | "dry_run",
           "service": service_name,
           "db_index": int,
           "redis_url": "redis://<container>:6379/<n>"}``

    Raises:
        ValueError: ``service_name`` failed validation.
        RuntimeError: Registry parse error, SSH failure, or pool full.
    """
    _validate_service_name(service_name)

    # WSL-side serialization of the read-modify-write, mirroring
    # postgres.py's allocations lock — two concurrent `fabrik apply` runs
    # otherwise both read the same lowest-free index and the second write
    # silently double-books it (last-writer-wins on the scp+mv).
    with file_lock("redis-assignments", timeout_seconds=15.0):
        return _acquire_locked(service_name, container, dry_run)


def _acquire_locked(service_name: str, container: str, dry_run: bool) -> dict:
    registry = _read_registry()
    if service_name in registry:
        idx = registry[service_name]
        logger.info("Redis DB index already assigned: %s -> %d", service_name, idx)
        return {
            "status": "exists",
            "service": service_name,
            "db_index": idx,
            "redis_url": f"redis://{container}:6379/{idx}",
        }

    idx = _next_free_index(registry)

    if dry_run:
        logger.info("[DRY RUN] Would assign Redis DB %d to %s", idx, service_name)
        return {
            "status": "dry_run",
            "service": service_name,
            "db_index": idx,
            "redis_url": f"redis://{container}:6379/{idx}",
        }

    registry[service_name] = idx
    _write_registry(registry)
    logger.info("Assigned Redis DB index: %s -> %d", service_name, idx)

    return {
        "status": "created",
        "service": service_name,
        "db_index": idx,
        "redis_url": f"redis://{container}:6379/{idx}",
    }


def release_db_index(
    service_name: str,
    flushdb: bool = False,
    container: str = REDIS_CONTAINER,
    dry_run: bool = False,
) -> bool:
    """Free a Redis DB index (best-effort, used by rollback + destroy).

    Args:
        service_name: Service whose assignment to release.
        flushdb: When ``True``, run ``FLUSHDB`` against the released
            index so the next service to acquire it starts clean. Off
            by default — same fail-closed data-preservation policy as
            :func:`fabrik.drivers.postgres.drop_database`. Caller opts
            in explicitly via ``fabrik destroy --drop-data``.
        container: Redis container name (for the FLUSHDB exec only).
        dry_run: Log intent and return True.

    Returns:
        True on successful release (or dry_run / not-found), False on
        SSH failure. Never raises so rollback can continue unwinding.
    """
    _validate_service_name(service_name)

    if dry_run:
        logger.info(
            "[DRY RUN] Would release Redis DB index for %s (flushdb=%s)",
            service_name,
            flushdb,
        )
        return True

    try:
        registry = _read_registry()
    except Exception as e:  # noqa: BLE001
        logger.warning("Redis registry unreadable, treating release as no-op: %s", e)
        return False

    if service_name not in registry:
        logger.info("Redis DB index already absent for %s", service_name)
        return True

    idx = registry.pop(service_name)
    try:
        _write_registry(registry)
    except Exception as e:  # noqa: BLE001
        logger.warning("Redis registry rewrite failed (non-fatal): %s", e)
        return False

    if flushdb:
        try:
            # ``redis-cli -n <db> FLUSHDB`` — needs the right DB selected
            # first. ``redis:7-alpine`` ships redis-cli inside the same
            # image so a single ``docker exec`` is enough.
            ssh(f"sudo docker exec {shlex.quote(container)} redis-cli -n {idx} FLUSHDB")
            logger.info("FLUSHDB on Redis DB %d (was %s)", idx, service_name)
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis FLUSHDB failed (non-fatal): %s", e)

    logger.info("Released Redis DB index %d (was %s)", idx, service_name)
    return True


def list_assignments() -> dict[str, int]:
    """Return the full ``{service: db_index}`` mapping.

    Used by ``fabrik vps-sync --verify`` to detect orphan assignments
    (registry entries for services no longer in ``data/projects.yaml``).
    """
    return _read_registry()


__all__ = (
    "REDIS_REGISTRY_PATH",
    "REDIS_CONTAINER",
    "REDIS_FIRST_INDEX",
    "REDIS_LAST_INDEX",
    "acquire_db_index",
    "release_db_index",
    "list_assignments",
)
