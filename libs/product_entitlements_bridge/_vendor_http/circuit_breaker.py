"""Asyncio-native circuit breaker for upstream API calls.

Prevents thundering herd when an upstream is rate-limiting (429) or
failing (5xx). Three states:

    CLOSED    — traffic flows normally. Trips to OPEN after threshold
                consecutive failures within the sliding window.
    OPEN      — all calls short-circuited for OPEN_SECONDS. Then
                transitions to HALF_OPEN.
    HALF_OPEN — one probe allowed. Success → CLOSED, failure → OPEN again.

Default trip thresholds (configurable via env):
    - 5 consecutive 429s within 60s window
    - 3 consecutive 5xx within 60s window

Safe under asyncio.gather — all state guarded by asyncio.Lock.
Process-local. If scaling to multi-worker, move to Redis-backed
pause-state/ module instead.

Usage:
    from libs.async_http_client.circuit_breaker import BREAKERS

    if not await BREAKERS.allow("openai"):
        raise CircuitOpen("openai is circuit-broken")

    try:
        resp = await client.get(...)
        if resp.status_code == 429:
            await BREAKERS.record_failure("openai", kind="429")
        elif resp.status_code >= 500:
            await BREAKERS.record_failure("openai", kind="5xx")
        else:
            await BREAKERS.record_success("openai")
    except httpx.HTTPError:
        await BREAKERS.record_failure("openai", kind="5xx")
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum


class _State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


OPEN_SECONDS: float = float(os.getenv("CB_OPEN_SECONDS", "300"))
WINDOW_SECONDS: float = float(os.getenv("CB_WINDOW_SECONDS", "60"))
FAIL_429_THRESHOLD: int = int(os.getenv("CB_FAIL_429_THRESHOLD", "5"))
FAIL_5XX_THRESHOLD: int = int(os.getenv("CB_FAIL_5XX_THRESHOLD", "3"))
# A HALF_OPEN probe that never reports back (caller cancelled / crashed between
# allow() and record_*) must not wedge the breaker shut forever. If a probe has
# been in flight longer than this, allow() issues a fresh one.
PROBE_TIMEOUT_SECONDS: float = float(os.getenv("CB_PROBE_TIMEOUT_SECONDS", "30"))


@dataclass
class _Breaker:
    """Per-upstream breaker state."""

    state: _State = _State.CLOSED
    opened_at: float = 0.0
    recent_429: list[float] = field(default_factory=list)
    recent_5xx: list[float] = field(default_factory=list)
    half_open_probe_inflight: bool = False
    half_open_started: float = 0.0  # when the current HALF_OPEN probe was issued


class CircuitBreakerRegistry:
    """Registry of per-upstream circuit breakers. Asyncio-safe."""

    def __init__(self) -> None:
        self._breakers: dict[str, _Breaker] = {}
        self._lock = asyncio.Lock()

    async def _get(self, upstream: str) -> _Breaker:
        b = self._breakers.get(upstream)
        if b is None:
            b = _Breaker()
            self._breakers[upstream] = b
        return b

    async def allow(self, upstream: str) -> bool:
        """Pre-call check. True = caller may proceed.

        Transitions:
            OPEN + expired  → HALF_OPEN (one probe allowed)
            OPEN + fresh    → False
            HALF_OPEN + probe in flight → False
        """
        now = time.monotonic()
        async with self._lock:
            b = await self._get(upstream)
            if b.state is _State.CLOSED:
                return True
            if b.state is _State.OPEN:
                if now - b.opened_at >= OPEN_SECONDS:
                    b.state = _State.HALF_OPEN
                    b.half_open_probe_inflight = True
                    b.half_open_started = now
                    return True
                return False
            # HALF_OPEN
            if b.half_open_probe_inflight:
                # A probe that never reported back (caller cancelled/crashed) must
                # not block recovery forever — re-issue once it's gone stale.
                if now - b.half_open_started >= PROBE_TIMEOUT_SECONDS:
                    b.half_open_started = now
                    return True
                return False
            b.half_open_probe_inflight = True
            b.half_open_started = now
            return True

    async def record_success(self, upstream: str) -> None:
        """Reset counters and close the breaker."""
        async with self._lock:
            b = await self._get(upstream)
            b.recent_429.clear()
            b.recent_5xx.clear()
            b.state = _State.CLOSED
            b.half_open_probe_inflight = False

    async def record_failure(self, upstream: str, *, kind: str) -> None:
        """Record a failure. ``kind`` is ``"429"`` or ``"5xx"``.

        Trips the breaker when threshold is hit within the sliding window.
        HALF_OPEN failures always re-open immediately.
        """
        now = time.monotonic()
        async with self._lock:
            b = await self._get(upstream)
            cutoff = now - WINDOW_SECONDS

            if kind == "429":
                b.recent_429 = [t for t in b.recent_429 if t >= cutoff]
                b.recent_429.append(now)
                tripped = len(b.recent_429) >= FAIL_429_THRESHOLD
            elif kind == "5xx":
                b.recent_5xx = [t for t in b.recent_5xx if t >= cutoff]
                b.recent_5xx.append(now)
                tripped = len(b.recent_5xx) >= FAIL_5XX_THRESHOLD
            else:
                return

            if b.state is _State.HALF_OPEN or tripped:
                b.state = _State.OPEN
                b.opened_at = now
                b.half_open_probe_inflight = False

    async def snapshot(self) -> dict[str, dict[str, object]]:
        """Current state of all breakers (for /health or debugging)."""
        async with self._lock:
            return {
                name: {
                    "state": b.state.value,
                    "recent_429": len(b.recent_429),
                    "recent_5xx": len(b.recent_5xx),
                }
                for name, b in self._breakers.items()
            }

    async def reset(self) -> None:
        """Clear all breakers. For testing only."""
        async with self._lock:
            self._breakers.clear()


# Module-level singleton — all upstreams share one registry.
BREAKERS = CircuitBreakerRegistry()

__all__ = [
    "BREAKERS",
    "CircuitBreakerRegistry",
    "OPEN_SECONDS",
    "WINDOW_SECONDS",
    "FAIL_429_THRESHOLD",
    "FAIL_5XX_THRESHOLD",
]
