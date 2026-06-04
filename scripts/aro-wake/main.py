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

Binding: 127.0.0.1:8002 (loopback) + 10.99.0.<host>:8002 (wg0 mesh).
NEVER 0.0.0.0. Spokes have UFW rules allowing only :22, :80, :443, :51820
inbound from public; UFW + DOCKER-USER prevent public reach to :8002 even
if accidentally bound wider.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

# ── Config (env-driven; defaults sane for vps1 hub) ───────────────────────

HOST_NAME = os.environ.get("ARO_WAKE_HOST_NAME", "vps1")
HOST_ROLE = os.environ.get("ARO_WAKE_HOST_ROLE", "hub")
HOST_IP = os.environ.get("ARO_WAKE_HOST_IP", "10.99.0.1")
PEER_HOSTS = json.loads(os.environ.get("ARO_WAKE_PEER_HOSTS", '{"vps2":"10.99.0.2","vps3":"10.99.0.3"}'))
WAKE_TIMEOUT = int(os.environ.get("ARO_WAKE_TIMEOUT", "300"))
RATE_LIMIT_PER_HOUR = int(os.environ.get("ARO_WAKE_RATE_LIMIT", "20"))
PENDING_QUEUE_PATH = Path(os.environ.get("ARO_WAKE_QUEUE_PATH", "/var/lib/aro-wake/pending.jsonl"))
PENDING_TTL_SECONDS = int(os.environ.get("ARO_WAKE_PENDING_TTL", str(24 * 3600)))
PENDING_MAX_ENTRIES = int(os.environ.get("ARO_WAKE_PENDING_MAX", "1000"))
PROJECT_DIR = Path(os.environ.get("ARO_WAKE_PROJECT_DIR", "/opt/fabrik"))
SYSTEM_PROMPT_PATH = Path(os.environ.get("ARO_WAKE_SYSTEM_PROMPT", "/opt/fabrik/scripts/sysadmin/system-prompt.txt"))
ACTIONS_LOG_PATH = Path(os.environ.get("ARO_WAKE_ACTIONS_LOG", "/opt/fabrik/logs/sysadmin-actions.jsonl"))

# ── Logging ───────────────────────────────────────────────────────────────

logging.basicConfig(
    level=os.environ.get("ARO_WAKE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s aro-wake %(message)s",
)
log = logging.getLogger(__name__)


# ── Rate limiter ──────────────────────────────────────────────────────────

class RateLimiter:
    """Per-(source, topic) tracker; drops events past the hourly cap."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._buckets: dict[tuple[str, str], deque[float]] = {}

    def allow(self, source: str, topic: str) -> bool:
        now = time.time()
        key = (source, topic)
        bucket = self._buckets.setdefault(key, deque())
        # Evict events older than 1 hour
        while bucket and now - bucket[0] > 3600:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return False
        bucket.append(now)
        return True


_rate = RateLimiter(RATE_LIMIT_PER_HOUR)


# ── Per-(source, topic) session memory (warm prompt cache) ────────────────

# Maps (source, topic) → Claude session-id. Lifetime 1h; new topic = new sid.
_sessions: dict[tuple[str, str], tuple[str, float]] = {}


def _session_for(source: str, topic: str) -> str | None:
    key = (source, topic)
    entry = _sessions.get(key)
    if entry is None:
        return None
    sid, ts = entry
    if time.time() - ts > 3600:
        del _sessions[key]
        return None
    return sid


def _set_session(source: str, topic: str, sid: str) -> None:
    _sessions[(source, topic)] = (sid, time.time())


# ── Pending queue (disk-backed; replays on mesh recovery) ─────────────────

def _queue_pending(intended_for: str, payload: dict[str, Any]) -> None:
    """Append a failed forward to /var/lib/aro-wake/pending.jsonl."""
    PENDING_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.time(),
        "ttl_until": time.time() + PENDING_TTL_SECONDS,
        "intended_for": intended_for,
        "payload": payload,
        "attempts": 1,
    }
    # Bound the queue (overflow drops oldest first)
    if PENDING_QUEUE_PATH.exists():
        lines = PENDING_QUEUE_PATH.read_text().splitlines()
        if len(lines) >= PENDING_MAX_ENTRIES:
            log.warning("pending_queue_overflow: dropping %d oldest entries", len(lines) - PENDING_MAX_ENTRIES + 1)
            lines = lines[-(PENDING_MAX_ENTRIES - 1):]
            PENDING_QUEUE_PATH.write_text("\n".join(lines) + "\n")
    with PENDING_QUEUE_PATH.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


async def _drain_pending_loop() -> None:
    """Background loop: retry pending entries every 30s; drop on TTL."""
    while True:
        await asyncio.sleep(30)
        if not PENDING_QUEUE_PATH.exists():
            continue
        try:
            lines = PENDING_QUEUE_PATH.read_text().splitlines()
        except OSError:
            continue
        now = time.time()
        keep: list[str] = []
        for raw in lines:
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if entry["ttl_until"] < now:
                log.warning("pending entry expired: intended_for=%s topic=%s", entry["intended_for"], entry["payload"].get("topic"))
                continue
            ok = await _try_forward(entry["intended_for"], entry["payload"])
            if not ok:
                entry["attempts"] = entry.get("attempts", 0) + 1
                keep.append(json.dumps(entry))
        PENDING_QUEUE_PATH.write_text("\n".join(keep) + ("\n" if keep else ""))


# ── Forwarding (cross-host consult) ───────────────────────────────────────

async def _try_forward(target_host: str, payload: dict[str, Any]) -> bool:
    """POST a wake payload to a peer's aro-wake. Returns True on 2xx."""
    target_ip = PEER_HOSTS.get(target_host)
    if not target_ip:
        log.error("unknown peer host: %s", target_host)
        return False
    url = f"http://{target_ip}:8002/wake"
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
        "-p", message,
        "--model", os.environ.get("ARO_WAKE_MODEL", "opus"),
        "--output-format", "json",
        "--permission-mode", "bypassPermissions",
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
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=WAKE_TIMEOUT,
            cwd=str(PROJECT_DIR),
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "claude_timeout", "session_id": sid}
    except FileNotFoundError as e:
        return {"ok": False, "error": f"claude binary missing: {e}", "session_id": sid}

    if proc.returncode != 0:
        # Resume can fail if session was pruned; drop sid and retry as new
        # (same fallback as bot.py and llm_client.py).
        if resume_sid and "session" in (proc.stderr or "").lower():
            _sessions.pop((source, topic), None)
            return _run_claude(message, source=source, topic=topic, system_prompt=system_prompt)
        return {
            "ok": False,
            "error": f"claude exited {proc.returncode}",
            "stderr": (proc.stderr or "")[:500],
            "session_id": sid,
        }

    _set_session(source, topic, sid)
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "error": "stdout not JSON",
            "stdout_head": proc.stdout[:200],
            "session_id": sid,
        }
    return {
        "ok": True,
        "result": envelope.get("result", ""),
        "cost_usd": envelope.get("total_cost_usd", 0.0),
        "session_id": envelope.get("session_id", sid),
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

app = FastAPI(title="aro-wake", version="0.1.0")


@app.on_event("startup")
async def _startup() -> None:
    PENDING_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Sanity-check the prompt is loadable; fail fast at startup, not on first wake.
    try:
        _load_prompt()
    except RuntimeError as e:
        log.error("startup failed: %s", e)
        raise
    asyncio.create_task(_drain_pending_loop())
    log.info(
        "aro-wake up: host=%s role=%s ip=%s peers=%s timeout=%ds rate_limit=%d/h",
        HOST_NAME, HOST_ROLE, HOST_IP, list(PEER_HOSTS.keys()), WAKE_TIMEOUT, RATE_LIMIT_PER_HOUR,
    )


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

    # Rate limit per (source, topic)
    if not _rate.allow(source, topic):
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
            + ("\n(NOTE: cycle detected — your host is already in seen_by; "
               "answer with current state only, do not forward.)\n" if is_cycle else "")
        )
    else:
        message = (
            f"WAKE from source={source} topic={topic}:\n"
            f"{json.dumps(payload, indent=2)}\n"
            f"\n"
            f"Diagnose and act per your veteran-sysadmin authority on {HOST_NAME}."
        )

    log.info("wake source=%s topic=%s from=%s trace=%s cycle=%s",
             source, topic, from_host, trace_id[:8], is_cycle)
    result = await asyncio.to_thread(
        _run_claude,
        message,
        source=source,
        topic=topic,
        system_prompt=_load_prompt() if _session_for(source, topic) is None else None,
    )
    _log_action({
        "source": source,
        "topic": topic,
        "from_host": from_host,
        "trace_id": trace_id,
        "cycle": is_cycle,
        "claude_ok": result.get("ok", False),
        "cost_usd": result.get("cost_usd", 0.0),
        "result_excerpt": (result.get("result", "") or result.get("error", ""))[:200],
    })

    if not result["ok"]:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": result.get("error"), "trace_id": trace_id},
        )

    return JSONResponse(content={
        "ok": True,
        "from_host": HOST_NAME,
        "trace_id": trace_id,
        "seen_by": seen_by,
        "result": result["result"],
        "no_action": (source == "consult"),
    })
