"""aro-wake — push-trigger entry point for this host's veteran-sysadmin AI.

Trio plan §3 (docs/development/plans/2026-06-04-three-sysadmin-trio.md).
One FastAPI service per host. Sleeps when no signal; wakes Claude on POST /wake.

First-ship (Phase 3) verbs:
  - source=consult — peer asks "what do you see from your side?"
  - source=manual  — operator-side curl for testing

Deferred (Phase 4):
  - source=alertmanager — Prometheus rule fires routed to the affected host
  - source=apprise      — Gatus/GlitchTip/Backrest hooks routed via aro-wake
                          before Telegram

Calling convention: mirrors scripts/sysadmin/bot.py::_run_claude verbatim
(operator's working production sysadmin pattern since 2026-05-29).

Binding: 127.0.0.1:8201 (loopback) + 10.99.0.<host>:8201 (wg0 mesh).
NEVER 0.0.0.0. Spokes have UFW rules allowing only :22, :80, :443, :51820
inbound from public; UFW + DOCKER-USER prevent public reach to :8201 even
if accidentally bound wider.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# Co-located Claude usage-limit/rotation wrapper (vendored byte-identical from sysadmin).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import claude_rotate  # noqa: E402  (sys.path adjusted above so the co-located module resolves)

# ── Config (env-driven; defaults sane for vps1 hub) ───────────────────────

HOST_NAME = os.environ.get("ARO_WAKE_HOST_NAME", "vps1")
HOST_ROLE = os.environ.get("ARO_WAKE_HOST_ROLE", "hub")
HOST_IP = os.environ.get("ARO_WAKE_HOST_IP", "10.99.0.1")


def _parse_peer_hosts(raw: str) -> dict[str, str]:
    """Parse the ARO_WAKE_PEER_HOSTS env var.

    Accepts either CSV (``name:ip,name:ip``) or JSON (``{"name":"ip",...}``).
    CSV is the preferred form because systemd's ``Environment=`` directive
    strips bare double-quotes when an embedded-JSON value isn't itself
    wrapped in escaped outer quotes — so the JSON form is fragile across
    systemd unit renders (verified 2026-06-04). CSV has no quoting hazard.
    """
    raw = (raw or "").strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        return json.loads(raw)
    out: dict[str, str] = {}
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        name, _, ip = token.partition(":")
        if name and ip:
            out[name.strip()] = ip.strip()
    return out


PEER_HOSTS = _parse_peer_hosts(
    os.environ.get("ARO_WAKE_PEER_HOSTS", "vps2:10.99.0.2,vps3:10.99.0.3")
)
WAKE_TIMEOUT = int(os.environ.get("ARO_WAKE_TIMEOUT", "300"))
RATE_LIMIT_PER_HOUR = int(os.environ.get("ARO_WAKE_RATE_LIMIT", "20"))
PENDING_QUEUE_PATH = Path(os.environ.get("ARO_WAKE_QUEUE_PATH", "/var/lib/aro-wake/pending.jsonl"))
PENDING_TTL_SECONDS = int(os.environ.get("ARO_WAKE_PENDING_TTL", str(24 * 3600)))
PENDING_MAX_ENTRIES = int(os.environ.get("ARO_WAKE_PENDING_MAX", "1000"))
PROJECT_DIR = Path(os.environ.get("ARO_WAKE_PROJECT_DIR", "/opt/fabrik"))
SYSTEM_PROMPT_PATH = Path(
    os.environ.get("ARO_WAKE_SYSTEM_PROMPT", "/opt/fabrik/scripts/sysadmin/system-prompt.txt")
)
ACTIONS_LOG_PATH = Path(
    os.environ.get("ARO_WAKE_ACTIONS_LOG", "/opt/fabrik/logs/sysadmin-actions.jsonl")
)

# ── Logging ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=os.environ.get("ARO_WAKE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s aro-wake %(message)s",
)
log = logging.getLogger(__name__)


# ── Rate limiter ──────────────────────────────────────────────────────────


class RateLimiter:
    """Per-(source, topic) tracker; drops events past the hourly cap.

    Thread-safe via threading.Lock — uvicorn handles concurrent /wake requests
    via asyncio + asyncio.to_thread, so two requests can hit allow() at the
    same wall-clock instant on different OS threads.
    """

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._buckets: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, source: str, topic: str) -> bool:
        now = time.time()
        key = (source, topic)
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            # Evict events older than 1 hour
            while bucket and now - bucket[0] > 3600:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(now)
            return True


_rate = RateLimiter(RATE_LIMIT_PER_HOUR)


# ── Loop-prevention guards (4 layers) ─────────────────────────────────────
#
# Spoke↔spoke routing went LIVE 2026-06-06 (ufw route allow in on wg0 out on
# wg0 on vps1; spokes already had AllowedIPs 10.99.0.0/24). With direct peer
# reach now possible, the protocol needs hardened cycle prevention. The four
# guards, in order of when they trip:
#
#   1. Trace-id dedup     — same trace_id arriving twice on this host (via
#                           any path) within 5 min is dropped. Catches the
#                           "different code paths re-injected the same
#                           logical event" case.
#   2. Hop cap (backstop) — len(seen_by) > fleet_size means a bug in
#                           seen_by handling. Cheap insurance.
#   3. Forward-target intersection — _try_forward refuses to send to any
#                           host already in payload.seen_by. PRIMARY guard;
#                           naturally terminates chains when all peers are
#                           covered.
#   4. Storm breaker      — per-target-host rolling-10-min cap on outbound
#                           forwards from THIS host. Trips at 8/10min.
#                           Prevents incident storms from amplifying.
#
# All state is in-memory: restart = reset = safe default (no recent activity).

_DEDUP_TTL = int(os.environ.get("ARO_WAKE_DEDUP_TTL", "300"))  # 5 min
_DEDUP_MAX = int(os.environ.get("ARO_WAKE_DEDUP_MAX", "500"))
_HOP_LIMIT = int(os.environ.get("ARO_WAKE_HOP_LIMIT", str(len(PEER_HOSTS) + 1)))
_STORM_WINDOW = int(os.environ.get("ARO_WAKE_STORM_WINDOW", "600"))  # 10 min
_STORM_THRESHOLD = int(os.environ.get("ARO_WAKE_STORM_THRESHOLD", "8"))

_recent_traces: OrderedDict[str, float] = OrderedDict()
_forwards_by_host: dict[str, deque[float]] = {}
_storm_alerted_at: dict[str, float] = {}
_guards_lock = threading.Lock()


def _dedup_trace(trace_id: str) -> bool:
    """True if trace_id was already seen on this host within _DEDUP_TTL."""
    now = time.time()
    with _guards_lock:
        # Evict expired entries from the front (OrderedDict insertion-ordered)
        while _recent_traces:
            oldest_id, oldest_ts = next(iter(_recent_traces.items()))
            if now - oldest_ts > _DEDUP_TTL:
                _recent_traces.popitem(last=False)
            else:
                break
        if trace_id in _recent_traces:
            return True
        _recent_traces[trace_id] = now
        # Bound memory: drop oldest if over cap
        while len(_recent_traces) > _DEDUP_MAX:
            _recent_traces.popitem(last=False)
        return False


def _storm_check(target_host: str) -> tuple[bool, int]:
    """Per-target-host rolling-window forward counter.

    Returns (ok_to_forward, current_count_in_window). When ok_to_forward is
    False, the caller should drop the forward (log + apprise once per window).
    """
    now = time.time()
    with _guards_lock:
        forwards = _forwards_by_host.setdefault(target_host, deque())
        while forwards and now - forwards[0] > _STORM_WINDOW:
            forwards.popleft()
        if len(forwards) >= _STORM_THRESHOLD:
            return False, len(forwards)
        forwards.append(now)
        return True, len(forwards)


def _storm_should_alert(target_host: str) -> bool:
    """True iff we haven't alerted for this host within the current window.

    Prevents log/apprise spam when the breaker is stuck-tripped.
    """
    now = time.time()
    with _guards_lock:
        last = _storm_alerted_at.get(target_host, 0.0)
        if now - last < _STORM_WINDOW:
            return False
        _storm_alerted_at[target_host] = now
        return True


# ── Prometheus SLI metrics (agent-sre framing per docs/reference/AI for ──
# Autonomous System Administration.md). Mounted at /metrics on the existing
# 0.0.0.0:8201 binding (no new port; UFW already permits 10.0.0.0/8 → 8201
# per PORTS.md). Counters are cumulative since process start (acceptable
# baseline; Prometheus rate() handles restart resets).
from prometheus_client import (  # noqa: E402
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
)

_REGISTRY = CollectorRegistry()
M_REQUESTS = Counter(
    "aro_wake_requests_total",
    "Total /wake requests processed, by source and outcome",
    ["source", "status"],
    registry=_REGISTRY,
)
M_COST = Counter(
    "aro_wake_cost_usd_total",
    "Cumulative Claude USD cost across /wake calls, by source",
    ["source"],
    registry=_REGISTRY,
)
M_DEDUP = Counter(
    "aro_wake_dedup_drops_total",
    "Duplicate trace_id drops (loop guard #1)",
    registry=_REGISTRY,
)
M_HOP = Counter(
    "aro_wake_hop_limit_exceeded_total",
    "len(seen_by) > _HOP_LIMIT drops (loop guard #2)",
    registry=_REGISTRY,
)
M_FWD_SUPPR = Counter(
    "aro_wake_forward_suppressed_total",
    "Outbound forward suppressions, by target and reason",
    ["target_host", "reason"],
    registry=_REGISTRY,
)
M_STORM = Counter(
    "aro_wake_storm_breaker_trips_total",
    "Storm-breaker trips, by target host (loop guard #4)",
    ["target_host"],
    registry=_REGISTRY,
)
M_QUEUE = Gauge(
    "aro_wake_pending_queue_size",
    "Current pending.jsonl queue depth",
    registry=_REGISTRY,
)
M_SESSIONS = Gauge(
    "aro_wake_active_sessions",
    "Active (source, topic) Claude session-id entries",
    registry=_REGISTRY,
)
# Phase: fleet-hardening 2026-06-17 — daily digest forwards from spokes.
# Plan §2.1: spokes POST their digest to hub /digest-input; hub combines
# all and sends ONE Telegram message.
M_DIGEST_INPUT = Counter(
    "aro_wake_digest_input_total",
    "Spoke digests received at /digest-input",
    ["from_host"],
    registry=_REGISTRY,
)


# ── Fleet-digest in-memory inbox ─────────────────────────────────────────
# 24h TTL is enforced lazily on /digest-inbox drains (we don't need a
# background prune — operator wakes once/day and drains).
from collections import defaultdict as _defaultdict  # noqa: E402

DIGEST_INBOX: dict[str, deque] = _defaultdict(lambda: deque(maxlen=30))


def _wg0_peer_to_host_local(client_ip: str) -> str:
    """Map a wg0 mesh IP (10.99.0.N) to a fleet hostname.

    Hub is 10.99.0.1 → vps1; spokes increment from .2. For Phase 4 this
    can be made configurable (read from /etc/wireguard/wg0.conf), but
    for the 3-host fleet today a static map suffices.
    """
    # Static map matches docs/infrastructure/vps-ai-sysadmin.md
    static = {
        "10.99.0.1": "vps1",
        "10.99.0.2": "vps2",
        "10.99.0.3": "vps3",
    }
    return static.get(client_ip, f"unknown-{client_ip}")


# ── Per-(source, topic) session memory (warm prompt cache) ────────────────

# Maps (source, topic) → Claude session-id. Lifetime 1h; new topic = new sid.
# Lock guards against the race where two simultaneous wakes on the same
# (source, topic) both observe "no session" and both spawn a fresh Claude
# session — wastes one warm-cache cycle.
_sessions: dict[tuple[str, str], tuple[str, float]] = {}
_sessions_lock = threading.Lock()


# Module-level set of background asyncio tasks (used by the alertmanager
# async-response path). Holding strong refs here prevents the event loop
# from garbage-collecting in-flight tasks mid-execution (a known asyncio
# pitfall). `task.add_done_callback(_bg_tasks.discard)` cleans up on
# completion.
_bg_tasks: set[asyncio.Task] = set()


def _session_for(source: str, topic: str) -> str | None:
    key = (source, topic)
    with _sessions_lock:
        entry = _sessions.get(key)
        if entry is None:
            return None
        sid, ts = entry
        if time.time() - ts > 3600:
            del _sessions[key]
            return None
        return sid


def _set_session(source: str, topic: str, sid: str) -> None:
    with _sessions_lock:
        _sessions[(source, topic)] = (sid, time.time())


# ── Pending queue (disk-backed; replays on mesh recovery) ─────────────────
#
# A single asyncio.Lock guards every read+write of pending.jsonl. Without
# it, _queue_pending() (called from a /wake handler) and _drain_pending_loop
# (background task) could race: drain reads the file, queue appends + may
# truncate, drain writes back its now-stale view. Lock is per-event-loop
# and held only across the read+write critical section; the actual peer
# HTTP forwards inside drain run OUTSIDE the lock (so a slow forward to
# one peer doesn't block /wake handlers from queueing for another peer).

_pending_lock = asyncio.Lock()


async def _queue_pending(intended_for: str, payload: dict[str, Any]) -> None:
    """Append a failed forward to /var/lib/aro-wake/pending.jsonl."""
    PENDING_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.time(),
        "ttl_until": time.time() + PENDING_TTL_SECONDS,
        "intended_for": intended_for,
        "payload": payload,
        "attempts": 1,
    }
    async with _pending_lock:
        # Bound the queue (overflow drops oldest first)
        if PENDING_QUEUE_PATH.exists():
            lines = PENDING_QUEUE_PATH.read_text().splitlines()
            if len(lines) >= PENDING_MAX_ENTRIES:
                log.warning(
                    "pending_queue_overflow: dropping %d oldest entries",
                    len(lines) - PENDING_MAX_ENTRIES + 1,
                )
                lines = lines[-(PENDING_MAX_ENTRIES - 1) :]
                PENDING_QUEUE_PATH.write_text("\n".join(lines) + "\n")
        with PENDING_QUEUE_PATH.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")


async def _drain_pending_loop() -> None:
    """Background loop: retry pending entries every 30s; drop on TTL."""
    while True:
        await asyncio.sleep(30)
        if not PENDING_QUEUE_PATH.exists():
            continue
        # Snapshot under lock, forward outside lock (so slow forwards don't
        # block /wake handlers), write back under lock.
        async with _pending_lock:
            try:
                snapshot = PENDING_QUEUE_PATH.read_text().splitlines()
            except OSError:
                continue
        if not snapshot:
            continue
        now = time.time()
        keep: list[str] = []
        for raw in snapshot:
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if entry["ttl_until"] < now:
                log.warning(
                    "pending entry expired: intended_for=%s topic=%s",
                    entry["intended_for"],
                    entry["payload"].get("topic"),
                )
                continue
            ok_fwd = await _try_forward(entry["intended_for"], entry["payload"])
            if not ok_fwd:
                entry["attempts"] = entry.get("attempts", 0) + 1
                keep.append(json.dumps(entry))
        # Merge any entries queued by /wake handlers DURING our drain.
        async with _pending_lock:
            try:
                final = PENDING_QUEUE_PATH.read_text().splitlines()
            except OSError:
                final = []
            seen_snapshot = set(snapshot)
            new_during_drain = [line for line in final if line not in seen_snapshot]
            PENDING_QUEUE_PATH.write_text(
                "\n".join(keep + new_during_drain) + ("\n" if keep or new_during_drain else "")
            )


# ── Forwarding (cross-host consult) ───────────────────────────────────────


async def _try_forward(target_host: str, payload: dict[str, Any]) -> bool:
    """POST a wake payload to a peer's aro-wake. Returns True on 2xx.

    Applies two loop guards BEFORE the network call:
      (a) forward-target intersection — refuses to forward to any host that's
          already in payload.seen_by (PRIMARY chain-termination guard).
      (b) storm breaker — refuses if this host has authored >=_STORM_THRESHOLD
          forwards to target_host in the last _STORM_WINDOW seconds. Logs
          loudly + alerts once per window on first trip.

    Returns False for both suppression cases so callers (alertmanager forward
    path + _drain_pending_loop) treat them the same as a network failure —
    the pending queue then retries the unforwardable payload, which itself
    is bounded by TTL.
    """
    target_ip = PEER_HOSTS.get(target_host)
    if not target_ip:
        log.error("unknown peer host: %s", target_host)
        return False
    seen_by = payload.get("seen_by") or []
    trace_id = payload.get("trace_id", "?")
    if target_host in seen_by:
        log.warning(
            "forward SUPPRESSED (forward_target_in_seen_by): target=%s seen_by=%s trace=%s",
            target_host,
            seen_by,
            trace_id[:8],
        )
        M_FWD_SUPPR.labels(target_host=target_host, reason="seen_by").inc()
        return False
    ok, count = _storm_check(target_host)
    if not ok:
        if _storm_should_alert(target_host):
            log.error(
                "forward SUPPRESSED (storm_breaker): target=%s count=%d/%d in %ds "
                "— operator should investigate runaway origin trace=%s",
                target_host,
                count,
                _STORM_THRESHOLD,
                _STORM_WINDOW,
                trace_id[:8],
            )
        else:
            log.warning(
                "forward SUPPRESSED (storm_breaker, alerted earlier): target=%s trace=%s",
                target_host,
                trace_id[:8],
            )
        M_FWD_SUPPR.labels(target_host=target_host, reason="storm").inc()
        M_STORM.labels(target_host=target_host).inc()
        return False
    url = f"http://{target_ip}:8201/wake"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload)
        return resp.status_code < 300
    except (httpx.HTTPError, OSError) as e:
        log.warning("forward to %s failed: %s", target_host, e)
        return False


# ── Claude subprocess (mirrors bot.py::_run_claude pattern verbatim) ──────


def _run_claude(
    message: str,
    *,
    source: str,
    topic: str,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Spawn `claude -p ...` with the host's veteran-sysadmin prompt.

    Uses --session-id + --resume to keep the prompt cache warm across calls
    on the same (source, topic). Same calling convention as the production
    sysadmin bot.
    """
    cmd = [
        "claude",
        "-p",
        message,
        "--model",
        os.environ.get("ARO_WAKE_MODEL", "opus"),
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
    ]
    resume_sid = _session_for(source, topic)
    if resume_sid:
        cmd.extend(["--resume", resume_sid])
        sid = resume_sid
    else:
        sid = str(uuid.uuid4())
        cmd.extend(["--session-id", sid])
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

    env = os.environ.copy()
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

    try:
        # Route through claude_rotate: rotates to another account + retries on a
        # usage/quota-limit; a 401 returns unchanged for the returncode branch below.
        proc = claude_rotate.run_claude(
            cmd,
            timeout=WAKE_TIMEOUT,
            cwd=str(PROJECT_DIR),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "claude_timeout", "session_id": sid}
    except FileNotFoundError as e:
        return {"ok": False, "error": f"claude binary missing: {e}", "session_id": sid}

    if proc.returncode != 0:
        # Resume can fail if session was pruned; drop sid and retry as new
        # (same fallback as bot.py and llm_client.py). Lock-guarded — without
        # the lock, a concurrent /wake on the same (source, topic) could
        # observe a stale sid mid-pop and resume against a session we just
        # decided to drop.
        if resume_sid and "session" in (proc.stderr or "").lower():
            with _sessions_lock:
                _sessions.pop((source, topic), None)
            return _run_claude(message, source=source, topic=topic, system_prompt=system_prompt)
        return {
            "ok": False,
            "error": f"claude exited {proc.returncode}",
            "stderr": (proc.stderr or "")[:500],
            "session_id": sid,
        }

    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "stdout not JSON",
            "stdout_head": proc.stdout[:200],
            "session_id": sid,
        }
    # Some Claude versions stream a list of events instead of a single
    # envelope. Defensive parse mirrors fabrik-lib/watchdog/sidecar/
    # llm_client.py: take the last dict element that carries a result.
    if isinstance(envelope, list):
        envelope = next(
            (e for e in reversed(envelope) if isinstance(e, dict) and "result" in e),
            {},
        )
    if not isinstance(envelope, dict):
        return {
            "ok": False,
            "error": "stdout JSON not a dict or event-list",
            "stdout_head": proc.stdout[:200],
            "session_id": sid,
        }
    # Store the EFFECTIVE session id (whatever Claude actually used) so a
    # future --resume targets the right session. If Claude returned a
    # session_id different from the one we passed via --session-id, the
    # local `sid` we used to spawn would be the wrong one to resume against.
    effective_sid = envelope.get("session_id", sid) or sid
    _set_session(source, topic, effective_sid)
    return {
        "ok": True,
        "result": envelope.get("result", ""),
        "cost_usd": envelope.get("total_cost_usd", 0.0),
        "session_id": effective_sid,
    }


def _log_action(record: dict[str, Any]) -> None:
    """Append a JSON line to /opt/fabrik/logs/sysadmin-actions.jsonl."""
    try:
        ACTIONS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with ACTIONS_LOG_PATH.open("a") as fh:
            fh.write(json.dumps({"ts": time.time(), "host": HOST_NAME, **record}) + "\n")
    except OSError as e:
        log.error("action log write failed: %s", e)


# ── System prompt loader (with host substitution) ─────────────────────────

_prompt_cache: str | None = None


def _load_prompt() -> str:
    global _prompt_cache
    if _prompt_cache is not None:
        return _prompt_cache
    if not SYSTEM_PROMPT_PATH.exists():
        raise RuntimeError(f"system prompt not found at {SYSTEM_PROMPT_PATH}")
    text = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    text = text.replace("{{ HOST_NAME }}", HOST_NAME)
    text = text.replace("{{ HOST_IP }}", HOST_IP)
    text = text.replace("{{ HOST_ROLE }}", HOST_ROLE)
    peer_str = ", ".join(f"{n} ({ip})" for n, ip in PEER_HOSTS.items())
    text = text.replace("{{ PEER_HOSTS }}", peer_str)
    _prompt_cache = text
    return text


# ── FastAPI app ───────────────────────────────────────────────────────────


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Startup
    PENDING_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Sanity-check the prompt is loadable; fail fast at startup, not on first wake.
    _load_prompt()
    drain_task = asyncio.create_task(_drain_pending_loop())
    log.info(
        "aro-wake up: host=%s role=%s ip=%s peers=%s timeout=%ds rate_limit=%d/h",
        HOST_NAME,
        HOST_ROLE,
        HOST_IP,
        list(PEER_HOSTS.keys()),
        WAKE_TIMEOUT,
        RATE_LIMIT_PER_HOUR,
    )
    try:
        yield
    finally:
        # Shutdown — give the drain loop one tick to finish cleanly.
        drain_task.cancel()
        try:
            await drain_task
        except asyncio.CancelledError:
            pass
        log.info("aro-wake shutting down")


app = FastAPI(title="aro-wake", version="0.1.0", lifespan=_lifespan)

# Prometheus exposition endpoint on the SAME 8201 binding (no new port).
# Use a regular route (not ASGI mount) so /metrics doesn't 307→/metrics/.
# Gauges refresh inline at scrape time — Prometheus default 15s interval is
# the de-facto refresh cadence.
from fastapi.responses import Response as _PromResponse  # noqa: E402


@app.get("/metrics")
async def metrics() -> _PromResponse:
    try:
        M_SESSIONS.set(len(_sessions))
        if PENDING_QUEUE_PATH.exists():
            M_QUEUE.set(sum(1 for ln in PENDING_QUEUE_PATH.read_text().splitlines() if ln.strip()))
        else:
            M_QUEUE.set(0)
    except OSError:
        pass
    return _PromResponse(content=generate_latest(_REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health() -> dict[str, Any]:
    pending_count = 0
    if PENDING_QUEUE_PATH.exists():
        try:
            pending_count = sum(1 for _ in PENDING_QUEUE_PATH.read_text().splitlines() if _.strip())
        except OSError:
            pending_count = -1
    return {
        "ok": True,
        "host": HOST_NAME,
        "role": HOST_ROLE,
        "pending_queue_count": pending_count,
        "active_sessions": len(_sessions),
    }


def _extract_alertmanager_host(body: dict[str, Any]) -> tuple[str | None, str]:
    """Return (host, alert_summary) from an Alertmanager v4 webhook payload.

    Looks at commonLabels.host, alerts[*].labels.host, then alerts[*].labels.instance
    (parsed for hostname). Returns None if no host can be resolved — the receiver
    will then process locally with a low_quality_alert tag for operator review.
    """
    host: str | None = None
    common = body.get("commonLabels", {}) or {}
    if isinstance(common, dict):
        host = common.get("host") or host
    if not host:
        for alert in body.get("alerts", []) or []:
            labels = (alert.get("labels", {}) or {}) if isinstance(alert, dict) else {}
            host = labels.get("host")
            if not host:
                inst = labels.get("instance", "")
                # instance is often "host:port" or "host" — take first token
                if isinstance(inst, str) and inst:
                    host = inst.split(":")[0].split(".")[0]
            if host:
                break
    # Build a one-line summary of the alert set for Claude
    parts: list[str] = []
    status = body.get("status", "firing")
    alerts = body.get("alerts", []) or []
    parts.append(f"status={status} alerts={len(alerts)}")
    for a in alerts[:5]:  # cap to 5 to keep prompt size sane
        if not isinstance(a, dict):
            continue
        lbls = a.get("labels", {}) or {}
        ann = a.get("annotations", {}) or {}
        nm = lbls.get("alertname", "?")
        sev = lbls.get("severity", "?")
        ctr = lbls.get("container") or lbls.get("instance") or "?"
        summary = ann.get("summary") or ann.get("description") or ""
        parts.append(f"  [{sev}] {nm} on {ctr}: {summary}"[:200])
    return host, "\n".join(parts)


@app.post("/digest-input")
async def digest_input(request: Request) -> JSONResponse:
    """Accept a spoke's daily digest forward.

    Phase: fleet-hardening 2026-06-17 (plan §2.1). Mesh-only trust
    boundary — UFW restricts to 10.99.0.0/24 (bootstrap-vps.sh:1137),
    same boundary as `/wake`'s peer-consult path.

    Body: ``{"text": "<digest text>", "metrics": {...JSONL row...}}``
    Response: ``{"accepted": true, "queue_depth": N}``
    """
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    client_ip = request.client.host if request.client else "unknown"
    from_host = _wg0_peer_to_host_local(client_ip)
    DIGEST_INBOX[from_host].append(
        {
            "ts": time.time(),
            "source_host": from_host,
            "text": body.get("text", ""),
            "metrics": body.get("metrics", {}),
        }
    )
    M_DIGEST_INPUT.labels(from_host=from_host).inc()
    log.info(
        "digest_input received from %s (metrics_keys=%s, queue_depth=%d)",
        from_host,
        list((body.get("metrics") or {}).keys()),
        len(DIGEST_INBOX[from_host]),
    )
    return JSONResponse({"accepted": True, "queue_depth": len(DIGEST_INBOX[from_host])})


@app.get("/digest-inbox")
async def digest_inbox(since: float = 0) -> JSONResponse:
    """Hub-only drain endpoint. Returns entries newer than `since`
    (unix epoch) AND removes them from the deque. Plan §2.1.

    Called by the hub's daily-digest.sh once per day at the cron-fired
    minute. Entries older than 24h are GC'd here too.
    """
    drained: list[dict] = []
    cutoff_24h = time.time() - 86400
    for host, items in list(DIGEST_INBOX.items()):
        kept: deque = deque(maxlen=30)
        for it in items:
            if it["ts"] < cutoff_24h:
                continue  # stale → drop
            if it["ts"] >= since:
                drained.append(it)
            else:
                kept.append(it)
        DIGEST_INBOX[host] = kept
    return JSONResponse(drained)


@app.post("/wake")
async def wake(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="body not JSON")
    source = body.get("source") or "manual"
    topic = body.get("topic") or "untagged"
    from_host = body.get("from_host")
    trace_id = body.get("trace_id") or str(uuid.uuid4())
    seen_by = body.get("seen_by") or []
    payload = body.get("payload") or {}

    # Loop guard #1 — trace_id dedup (5-min in-memory LRU).
    # Same trace_id arriving twice on THIS host means it reached us via two
    # paths (legitimate alertmanager retry, or a cross-host re-injection).
    # Drop the duplicate before any work. Operator who genuinely wants to
    # re-fire a trace_id manually should mint a new uuid.
    if _dedup_trace(trace_id):
        log.info("wake DROP duplicate trace=%s source=%s topic=%s", trace_id[:8], source, topic)
        M_DEDUP.inc()
        return JSONResponse(
            content={
                "ok": False,
                "reason": "duplicate",
                "trace_id": trace_id,
                "from_host": HOST_NAME,
            }
        )

    # Loop guard #2 — hop cap (belt-and-suspenders).
    # On a 3-host fleet, legitimate max(seen_by) = 3 (all hosts saw it). If
    # we receive a payload where seen_by already exceeds fleet size, that's
    # a bug in seen_by handling somewhere upstream. Drop loudly.
    if len(seen_by) > _HOP_LIMIT:
        log.warning(
            "wake DROP hop_limit_exceeded trace=%s seen_by=%s limit=%d",
            trace_id[:8],
            seen_by,
            _HOP_LIMIT,
        )
        M_HOP.inc()
        return JSONResponse(
            content={
                "ok": False,
                "reason": "hop_limit_exceeded",
                "trace_id": trace_id,
                "from_host": HOST_NAME,
                "seen_by": seen_by,
                "limit": _HOP_LIMIT,
            }
        )

    # Alertmanager webhook payloads don't carry our internal source/topic
    # shape — they have alerts[], commonLabels, etc. Wrap them into our
    # format so the rest of the handler (rate limit + dedupe + cycle) just
    # works. The host label drives routing: if the alert is about a peer's
    # host, forward to that peer's aro-wake; otherwise process locally.
    alertmanager_target_host: str | None = None
    is_alertmanager = (source == "alertmanager") or (
        "alerts" in body and isinstance(body.get("alerts"), list)
    )
    if is_alertmanager:
        source = "alertmanager"
        alertmanager_target_host, am_summary = _extract_alertmanager_host(body)
        # Derive a stable topic from the alert group key (Alertmanager dedupe key)
        if not body.get("topic"):
            topic = (body.get("groupKey") or "alertmanager_unknown")[:120]
        # If host is a peer, forward (only if mesh is reachable). Process
        # locally otherwise (host = this host, or no label).
        # Cycle pre-check: if the target peer already appears in seen_by, the
        # forward would be SUPPRESSED by _try_forward's guard AND then
        # queued+retried-pointlessly every 30s until TTL. Skip both: fall
        # through to local processing as the cycle fallback.
        if (
            alertmanager_target_host
            and alertmanager_target_host in PEER_HOSTS
            and alertmanager_target_host in seen_by
        ):
            log.warning(
                "alertmanager target %s already in seen_by=%s — falling back "
                "to local processing on %s (cycle prevention) trace=%s",
                alertmanager_target_host,
                seen_by,
                HOST_NAME,
                trace_id[:8],
            )
            # Same operator-visible event as _try_forward's seen_by suppress;
            # this branch is the optimized path that avoids the _try_forward
            # call altogether (so _try_forward's metric would never fire here).
            M_FWD_SUPPR.labels(target_host=alertmanager_target_host, reason="seen_by").inc()
            alertmanager_target_host = None  # forces local-processing branch
        if alertmanager_target_host and alertmanager_target_host in PEER_HOSTS:
            fwd_payload = {
                **body,
                "source": "alertmanager",  # peer normalizes back via is_alertmanager check
                "from_host": HOST_NAME,
                "trace_id": trace_id,
                "seen_by": [*seen_by, HOST_NAME] if HOST_NAME not in seen_by else seen_by,
                "topic": topic,
            }
            ok_fwd = await _try_forward(alertmanager_target_host, fwd_payload)
            if ok_fwd:
                return JSONResponse(
                    content={
                        "ok": True,
                        "from_host": HOST_NAME,
                        "trace_id": trace_id,
                        "forwarded_to": alertmanager_target_host,
                    }
                )
            # Forward failed → queue for retry + still surface 5xx to
            # Alertmanager so its `continue: true` route picks up the
            # telegram fallback.
            await _queue_pending(alertmanager_target_host, fwd_payload)
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "error": f"peer {alertmanager_target_host} unreachable; queued for retry",
                    "trace_id": trace_id,
                },
            )
        # Local processing: pack the summary into payload so Claude has it.
        # Don't bloat the payload with the full alertmanager_body — only the
        # parsed summary reaches Claude via the prompt; the body itself is
        # consumed in _extract_alertmanager_host above.
        payload = {
            "alert_summary": am_summary,
            "host_label": alertmanager_target_host or "(unset — low_quality_alert)",
        }
        if not alertmanager_target_host:
            log.warning("low_quality_alert source=alertmanager topic=%s no host label", topic)
        # ASYNC PATTERN for alertmanager: return 202 immediately + process
        # Claude in a background task. Reason: Alertmanager's webhook_configs
        # default timeout (~10s) is much less than Claude's wall-clock
        # (60-180s). Without the async hop, Alertmanager would time out,
        # retry per its retry policy, and we'd get duplicate wakes. consult
        # + manual paths STAY synchronous (caller needs the response).
        # Rate-limit check runs synchronously before scheduling so we don't
        # leak background tasks past the cap.
        if not _rate.allow(source, topic):
            M_REQUESTS.labels(source=source, status="rate_limited").inc()
            return JSONResponse(
                status_code=429,
                content={"ok": False, "error": "rate_limited", "trace_id": trace_id},
            )
        is_cycle_am = HOST_NAME in seen_by
        if not is_cycle_am:
            seen_by = [*seen_by, HOST_NAME]
        message_am = (
            f"ALERTMANAGER WEBHOOK (trace_id={trace_id[:8]}, topic={topic}):\n"
            f"{payload['alert_summary']}\n"
            f"\n"
            f"Affected host label: {payload['host_label']}.\n"
            f"You are running on {HOST_NAME}; act per your veteran-sysadmin "
            f"authority for THIS host only. If the alert targets a different "
            f"host, this is a routing fallback — diagnose locally only.\n"
            f"\n"
            f"Per the incident_playbooks section of your system prompt:\n"
            f"  - For CONTAINER OOM, RESTART LOOP, DISK HIGH: act per playbook\n"
            f"  - For MONITORING-tier alerts: read-only, escalate\n"
            f"  - For CRITICAL-INFRA: read-only, escalate\n"
            f"  - Use deconfliction rule (check for *-watchdog sidecar) before any restart\n"
            f"Report what you did + evidence."
        )

        # Spawn background processing; we hold the task reference on a
        # module-level set so the event loop doesn't GC it mid-flight (a
        # known asyncio pitfall — see Python docs for asyncio.create_task).
        async def _bg_alertmanager() -> None:
            try:
                result_bg = await asyncio.to_thread(
                    _run_claude,
                    message_am,
                    source=source,
                    topic=topic,
                    system_prompt=_load_prompt() if _session_for(source, topic) is None else None,
                )
                _log_action(
                    {
                        "source": source,
                        "topic": topic,
                        "from_host": from_host,
                        "trace_id": trace_id,
                        "cycle": is_cycle_am,
                        "claude_ok": result_bg.get("ok", False),
                        "cost_usd": result_bg.get("cost_usd", 0.0),
                        "result_excerpt": (
                            result_bg.get("result", "") or result_bg.get("error", "")
                        )[:200],
                        "async": True,
                    }
                )
                M_REQUESTS.labels(
                    source=source,
                    status="success" if result_bg.get("ok") else "failure",
                ).inc()
                M_COST.labels(source=source).inc(float(result_bg.get("cost_usd", 0.0)))
            except Exception as e:  # noqa: BLE001
                log.exception("background alertmanager processing failed: %s", e)

        task = asyncio.create_task(_bg_alertmanager())
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)
        log.info("wake source=alertmanager topic=%s trace=%s scheduled-async", topic, trace_id[:8])
        return JSONResponse(
            status_code=202,
            content={
                "ok": True,
                "accepted": True,
                "from_host": HOST_NAME,
                "trace_id": trace_id,
                "scope": "local",
            },
        )

    # Rate limit per (source, topic)
    if not _rate.allow(source, topic):
        M_REQUESTS.labels(source=source, status="rate_limited").inc()
        return JSONResponse(
            status_code=429,
            content={"ok": False, "error": "rate_limited", "trace_id": trace_id},
        )

    # Cycle prevention — if our own host is already in seen_by, we answer
    # with current state ONLY; do NOT re-consult anywhere.
    is_cycle = HOST_NAME in seen_by
    if not is_cycle:
        seen_by = [*seen_by, HOST_NAME]

    # Compose the prompt for Claude
    if source == "consult":
        message = (
            f"PEER CONSULT from {from_host} (trace_id={trace_id[:8]}):\n"
            f"topic: {topic}\n"
            f"their view: {payload.get('my_view', '(empty)')}\n"
            f"asking: {payload.get('asking', '(empty)')}\n"
            f"\n"
            f"Respond as their veteran-sysadmin peer. Answer ONLY with what you "
            f"see from {HOST_NAME}'s side. Do NOT take action — consult "
            f"responses are diagnosis-only per peer-protocol.md §3.3. If you "
            f"see a correlation with the peer's view, name it. Keep response "
            f"under 200 words.\n"
            + (
                "\n(NOTE: cycle detected — your host is already in seen_by; "
                "answer with current state only, do not forward.)\n"
                if is_cycle
                else ""
            )
        )
    else:
        # NOTE: source="alertmanager" never reaches this branch — handled
        # synchronously above with rate-limit + cycle + scheduled-async
        # background task + 202 return. The legacy elif here was removed
        # 2026-06-05 batch-6 review pass when the async pattern shipped.
        message = (
            f"WAKE from source={source} topic={topic}:\n"
            f"{json.dumps(payload, indent=2)}\n"
            f"\n"
            f"Diagnose and act per your veteran-sysadmin authority on {HOST_NAME}."
        )

    log.info(
        "wake source=%s topic=%s from=%s trace=%s cycle=%s",
        source,
        topic,
        from_host,
        trace_id[:8],
        is_cycle,
    )
    result = await asyncio.to_thread(
        _run_claude,
        message,
        source=source,
        topic=topic,
        system_prompt=_load_prompt() if _session_for(source, topic) is None else None,
    )
    _log_action(
        {
            "source": source,
            "topic": topic,
            "from_host": from_host,
            "trace_id": trace_id,
            "cycle": is_cycle,
            "claude_ok": result.get("ok", False),
            "cost_usd": result.get("cost_usd", 0.0),
            "result_excerpt": (result.get("result", "") or result.get("error", ""))[:200],
        }
    )
    M_REQUESTS.labels(
        source=source,
        status="success" if result.get("ok") else "failure",
    ).inc()
    M_COST.labels(source=source).inc(float(result.get("cost_usd", 0.0)))

    if not result["ok"]:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": result.get("error"), "trace_id": trace_id},
        )

    raw = result["result"] or ""
    # Strip the canonical "[<host>]" Telegram-prefix the veteran-sysadmin
    # prompt instructs the model to add — for consult responses going to
    # peers, the prefix is noise. The caller already knows from_host from
    # the JSON envelope. Defense in depth: model sometimes echoes the
    # prefix at start, sometimes not.
    cleaned = raw.lstrip()
    if cleaned.startswith(f"[{HOST_NAME}]"):
        cleaned = cleaned[len(f"[{HOST_NAME}]") :].lstrip()

    response_body: dict[str, Any] = {
        "ok": True,
        "from_host": HOST_NAME,
        "trace_id": trace_id,
        "seen_by": seen_by,
    }
    if source == "consult":
        # Match the response shape documented in peer-protocol.md §2.1:
        # {from_host, trace_id, view, correlation, no_action}.
        # We can't reliably split the model's free text into view +
        # correlation; put the whole answer in `view` and leave
        # `correlation` empty for the caller to parse (or just read view).
        response_body["view"] = cleaned
        response_body["correlation"] = ""
        response_body["no_action"] = True
    else:
        # For non-consult sources (alertmanager, manual, future), keep
        # the unstructured `result` field — these consumers parse the
        # full report directly.
        response_body["result"] = cleaned
        response_body["no_action"] = False

    return JSONResponse(content=response_body)
