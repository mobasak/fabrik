"""
Shared pause-flag primitives — used by dispatchers and workers to coordinate
"stop all work that depends on a saturated/exhausted resource until it recovers".

Why this module exists
----------------------
Without coordination, when a shared dependency starts failing:

  • Each worker picks up a job, hits the same failure, defers the job.
    Each defer re-queues a fresh message.
  • Beat tasks re-dispatch deferred jobs once TTL elapses.
  • Orphan sweeps re-dispatch orphans.
  • Result: queue grows 10× faster than workers drain it, while every
    attempt burns resources on a guaranteed-fail cascade.

The pause flag pattern fixes this:

  1. `classify_transient_error(error_msg)` returns `(resource, ttl_sec)`
     or `None` if the error isn't pause-worthy.
  2. The caller raises a sliding-TTL pause via `set_global_pause(...)`.
  3. Dispatchers and workers check `is_globally_paused()` and bail.
  4. Pause auto-clears when the TTL expires — no human reset needed.
  5. If failures continue, the next-failing worker re-stamps the flag
     (`SETEX` replaces the TTL) so the pause stays active as long as
     the resource is unhealthy.

Configuration
-------------
  PAUSE_KEY_PREFIX — env var `PAUSE_KEY_PREFIX`, defaults to `{SERVICE_NAME}:pause:`.
  REDIS_URL        — env var, defaults to `redis://redis-main:6379/0`.
  PAUSE_TTL_*      — per-resource TTL override env vars (e.g. PAUSE_TTL_NETWORK=30).

Add project-specific resources by extending TRANSIENT_PATTERNS below.
See 58-resilience.md § Error Classifier for the full pattern.

Canonical reference: fabrik/templates/scaffold/python/pause_state.py
Production example: /opt/youtube/pause_state.py (YouTube pipeline)
"""

from __future__ import annotations

import os

import structlog

logger = structlog.get_logger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "service")
PAUSE_KEY_PREFIX = os.getenv("PAUSE_KEY_PREFIX", f"{SERVICE_NAME}:pause:")


def _redis():
    """Lazy Redis client. Returns None on connection failure so callers
    degrade gracefully (no pause is enforced)."""
    try:
        import redis as _redis_mod
        return _redis_mod.from_url(
            os.getenv("REDIS_URL", "redis://redis-main:6379/0"),
            decode_responses=True,
        )
    except Exception:  # noqa: BLE001
        return None


def is_globally_paused() -> str | None:
    """Return `<resource>:<reason>` if ANY pause flag is set, else None.

    Callers use the result as a truthy/falsy gate; the string is for logs.
    Cost: one Redis KEYS scan against the pause prefix.
    """
    rc = _redis()
    if rc is None:
        return None
    try:
        keys = rc.keys(PAUSE_KEY_PREFIX + "*")
        if not keys:
            return None
        for k in keys:
            v = rc.get(k)
            if v:
                resource = k[len(PAUSE_KEY_PREFIX):]
                return f"{resource}:{v}"
        return None
    except Exception:  # noqa: BLE001
        return None


def set_global_pause(resource: str, reason: str, ttl_sec: int) -> None:
    """Set <prefix><resource> = <reason> EX ttl_sec.

    Sliding TTL — repeated calls reset the expiry. Lets a burst of
    failures sustain the pause; a single blip auto-expires.
    """
    rc = _redis()
    if rc is None:
        return
    try:
        rc.setex(PAUSE_KEY_PREFIX + resource, max(10, int(ttl_sec)), reason[:200])
        logger.warning(
            "pause_set",
            resource=resource,
            reason=reason[:80],
            ttl_sec=ttl_sec,
        )
    except Exception:  # noqa: BLE001
        pass


def clear_global_pause(resource: str) -> None:
    """Remove a specific pause flag (resource recovered). Idempotent."""
    rc = _redis()
    if rc is None:
        return
    try:
        if rc.delete(PAUSE_KEY_PREFIX + resource):
            logger.warning("pause_cleared", resource=resource)
    except Exception:  # noqa: BLE001
        pass


# ── Error Classifier ─────────────────────────────────────────────────────
# ONE file maps error patterns to (resource, ttl). All worker except blocks
# and HTTP middleware call this single classifier. Adding a new transient
# pattern means editing THIS list — never inline pattern matching elsewhere.
#
# See 58-resilience.md § Error Classifier for the full rule.
#
# CUSTOMIZE: add project-specific patterns below. Remove the examples
# that don't apply to your project.

TRANSIENT_PATTERNS: list[tuple[str, str, int]] = [
    # (substring_to_match, resource_name, default_ttl_seconds)
    # Order matters — most specific first.

    # Vendor credit/billing — human must top up. Long TTL.
    # ("insufficient credit", "vendor_credit", 1800),
    # ("payment required", "vendor_credit", 1800),

    # Network / DNS — usually short blips.
    ("name resolution", "network", 30),
    ("nameresolutionerror", "network", 30),
    ("temporary failure", "network", 30),
    ("connectionpool", "network", 30),
    ("max retries exceeded", "network", 30),

    # SSL / connection mid-stream issues.
    ("ssl syscall", "network_ssl", 30),
    ("unexpected_eof", "network_ssl", 30),
    ("504 gateway timeout", "network_ssl", 30),

    # PostgreSQL connection pool exhaustion.
    ("pool exhausted", "db_pool", 120),
    ("too many connections", "db_pool", 120),
]


def classify_transient_error(error_msg: str) -> tuple[str, int] | None:
    """Return `(resource, ttl_sec)` if `error_msg` matches a known
    transient failure mode, else `None`.

    TTL is read from env var `PAUSE_TTL_<RESOURCE_UPPER>` if set,
    otherwise uses the default from TRANSIENT_PATTERNS.
    """
    if not error_msg:
        return None
    lo = error_msg.lower()

    for pattern, resource, default_ttl in TRANSIENT_PATTERNS:
        if pattern in lo:
            ttl = int(os.getenv(f"PAUSE_TTL_{resource.upper()}", str(default_ttl)))
            return (resource, ttl)

    return None


def maybe_pause_from_error(error_msg: str) -> str | None:
    """Convenience wrapper — classify + pause in one call. Returns the
    paused resource name if pause was raised, else None."""
    cls = classify_transient_error(error_msg)
    if cls is None:
        return None
    resource, ttl = cls
    set_global_pause(resource, error_msg[:200], ttl_sec=ttl)
    return resource
