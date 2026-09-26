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
  PAUSE_REDIS_TIMEOUT_SEC          — Redis connect/read timeout, default 2.
  PAUSE_DEGRADED_LOG_INTERVAL_SEC  — minimum gap between degraded warnings, default 60.

Posture when Redis is unreachable: FAIL-OPEN, declared and counted
----------------------------------------------------------------
A pause flag OPTIMISES (it saves wasted attempts); it protects nothing a breach cannot recover
from, so when Redis is down the read answers "not paused" and work proceeds (58-resilience.md
§ When the resilience substrate itself fails). The degrade is never silent:
  • every failed call counts in `degraded_count()` and, with prometheus_client installed, in
    `pause_redis_degraded_total{op}` — registered on this package's `metrics.REGISTRY` (the one
    /metrics serves) when there is one, else on the default registry. op is `read`, `set` or
    `clear` for a Redis failure, `client` when the client cannot be built (no redis package, a
    malformed REDIS_URL); the client connects lazily, so an unreachable server shows as `read`.
  • `pause_redis_degraded` is logged at most once per PAUSE_DEGRADED_LOG_INTERVAL_SEC, and
    `pause_redis_recovered` only after a logged degrade — a down or flapping Redis yields at most
    two lines per interval, never one per poll.
  • each Redis command (KEYS, GET, SETEX, DEL) is bounded by PAUSE_REDIS_TIMEOUT_SEC, so a
    black-holed Redis costs a few timeouts per call (redis-py may retry), not the OS connect timeout.

Add project-specific resources by extending TRANSIENT_PATTERNS below.
See 58-resilience.md § Error Classifier for the full pattern.

Canonical reference: fabrik/templates/scaffold/python/pause_state.py
Production example: /opt/youtube/pause_state.py (YouTube pipeline)
"""

from __future__ import annotations

import os
import threading
import time

import structlog

logger = structlog.get_logger(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "service")
PAUSE_KEY_PREFIX = os.getenv("PAUSE_KEY_PREFIX", f"{SERVICE_NAME}:pause:")

_TIMEOUT_SEC = float(os.getenv("PAUSE_REDIS_TIMEOUT_SEC", "2"))
_LOG_INTERVAL_SEC = float(os.getenv("PAUSE_DEGRADED_LOG_INTERVAL_SEC", "60"))


def _metrics_registry():
    """The registry this package's /metrics serves, or None (no metrics module: file-worker)."""
    try:
        from .metrics import REGISTRY

        return REGISTRY
    except ImportError:
        return None


def _degraded_metric():
    try:
        from prometheus_client import Counter
    except ImportError:
        return None
    registry = _metrics_registry()
    try:
        return Counter(
            "pause_redis_degraded_total",
            "Pause-flag Redis calls that failed and fell open (work proceeded unpaused)",
            ["op"],
            **({"registry": registry} if registry is not None else {}),
        )
    except ValueError as exc:  # already registered in this process (a reload, a second import name)
        logger.warning("pause_redis_metric_unavailable", error=str(exc))
        return None


_DEGRADED_METRIC = _degraded_metric()
_lock = threading.RLock()  # re-entered: _redis() -> _degrade()
_client = None
_degraded_total = 0
_degraded = False
_last_log: float | None = None
_logged_since_recovery = False


def degraded_count() -> int:
    """Pause-flag Redis calls that have failed open in this process."""
    return _degraded_total


def _degrade(op: str, exc: BaseException) -> None:
    """Record one fail-open: always counted, logged at most once per interval.

    The log is emitted under the lock so a concurrent recovery can never print before it.
    """
    global _degraded_total, _degraded, _last_log, _logged_since_recovery
    with _lock:
        _degraded_total += 1
        entering = not _degraded
        _degraded = True
        now = time.monotonic()
        if _DEGRADED_METRIC is not None:
            _DEGRADED_METRIC.labels(op=op).inc()
        if _last_log is None or now - _last_log >= _LOG_INTERVAL_SEC:
            _last_log = now
            _logged_since_recovery = True
            logger.warning(
                "pause_redis_degraded",
                op=op,
                error=type(exc).__name__,
                entering=entering,
                failed_calls=_degraded_total,
                posture="fail-open: pause flags read as not paused until Redis returns",
            )


def _recovered() -> None:
    global _degraded, _logged_since_recovery
    if not _degraded:  # fast path: a healthy call never takes the lock
        return
    with _lock:
        if not _degraded:
            return
        _degraded = False
        if _logged_since_recovery:
            _logged_since_recovery = False
            logger.warning("pause_redis_recovered")


def _redis():
    """The cached Redis client, built once per process, or None (counted and logged)."""
    global _client
    if _client is not None:  # fast path: the lock guards only the build
        return _client
    with _lock:
        if _client is None:
            try:
                import redis as _redis_mod

                _client = _redis_mod.from_url(
                    os.getenv("REDIS_URL", "redis://redis-main:6379/0"),
                    decode_responses=True,
                    socket_connect_timeout=_TIMEOUT_SEC,
                    socket_timeout=_TIMEOUT_SEC,
                )
            except Exception as exc:  # noqa: BLE001
                _degrade("client", exc)
                return None
        return _client


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
        found = None
        for k in keys or []:
            v = rc.get(k)
            if v:
                found = f"{k[len(PAUSE_KEY_PREFIX) :]}:{v}"
                break
    except Exception as exc:  # noqa: BLE001
        _degrade("read", exc)
        return None
    _recovered()
    return found


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
    except Exception as exc:  # noqa: BLE001
        _degrade("set", exc)
        return
    _recovered()
    logger.warning(
        "pause_set",
        resource=resource,
        reason=reason[:80],
        ttl_sec=ttl_sec,
    )


def clear_global_pause(resource: str) -> None:
    """Remove a specific pause flag (resource recovered). Idempotent."""
    rc = _redis()
    if rc is None:
        return
    try:
        deleted = rc.delete(PAUSE_KEY_PREFIX + resource)
    except Exception as exc:  # noqa: BLE001
        _degrade("clear", exc)
        return
    _recovered()
    if deleted:
        logger.warning("pause_cleared", resource=resource)


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
