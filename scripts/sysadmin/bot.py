#!/usr/bin/env python3
# AFTER-EDIT: docs/infrastructure/vps-ai-sysadmin.md
"""
VPS AI Sysadmin Telegram Bot.

Bridges Telegram messages to Claude Code (Opus) sessions running locally on the VPS.
Each conversation is a session. Follow-ups resume the same session.
Session ends on "done" / end-words or 10 minutes of silence.

Health endpoint at :8017/health for Gatus monitoring.
Daily heartbeat at 08:00 local time.

Usage:
    TELEGRAM_BOT_TOKEN=... TELEGRAM_OWNER_ID=... python3 scripts/sysadmin/bot.py

Systemd: /etc/systemd/system/vps-sysadmin-bot.service
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

# Co-located Claude usage-limit/rotation wrapper (vendored byte-identical into aro-wake too).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import claude_rotate  # noqa: E402  (sys.path adjusted above so the co-located module resolves)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("sysadmin-bot")

# ── Config ────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OWNER_ID = int(os.environ["TELEGRAM_OWNER_ID"])
PROJECT_DIR = os.environ.get("SYSADMIN_PROJECT_DIR", "/opt/fabrik")
SYSTEM_PROMPT_FILE = Path(__file__).parent / "system-prompt.txt"
HEALTH_PORT = int(os.environ.get("SYSADMIN_HEALTH_PORT", "8017"))
HEALTH_HOST = os.environ.get("SYSADMIN_HEALTH_HOST", "127.0.0.1")
MODEL = os.environ.get("SYSADMIN_MODEL", "opus")

SESSION_TIMEOUT_SECONDS = 600  # 10 minutes idle → session ends
CLAUDE_TIMEOUT_SECONDS = 300  # 5 minutes max per call (audits can be long)
HEARTBEAT_HOUR = 8  # daily heartbeat at 08:00 local time

END_WORDS = frozenset({"done", "bye", "thanks", "thx", "end", "exit", "quit"})

# ── State ─────────────────────────────────────────────────────────────────

_session_id: str | None = None
_last_activity: float = 0.0
_last_heartbeat_date: str = ""
_lock = asyncio.Lock()
_boot_time = time.time()
_calls_total = 0
_calls_failed = 0


def _load_system_prompt() -> str:
    if SYSTEM_PROMPT_FILE.exists():
        return SYSTEM_PROMPT_FILE.read_text(encoding="utf-8").strip()
    logger.warning("System prompt file not found: %s", SYSTEM_PROMPT_FILE)
    return "You are a VPS system administrator. Act autonomously, report concisely."


SYSTEM_PROMPT = _load_system_prompt()

# ── Health endpoint (for Gatus) ───────────────────────────────────────────


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            uptime = int(time.time() - _boot_time)
            body = json.dumps(
                {
                    "status": "ok",
                    "uptime_seconds": uptime,
                    "model": MODEL,
                    "session_active": _session_id is not None,
                    "calls_total": _calls_total,
                    "calls_failed": _calls_failed,
                    "last_activity": int(_last_activity) if _last_activity else 0,
                }
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress access log noise


def _start_health_server():
    server = HTTPServer((HEALTH_HOST, HEALTH_PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health endpoint listening on :%d/health", HEALTH_PORT)


# ── Change log + shift notes ──────────────────────────────────────────────

LOGS_DIR = Path(PROJECT_DIR) / "logs"
ACTION_LOG = LOGS_DIR / "sysadmin-actions.jsonl"
SHIFT_NOTES = LOGS_DIR / "sysadmin-shift-notes.md"


def _ensure_logs_dir():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _log_action(message: str, response: str, session: str):
    """Append to persistent action log — survives between sessions."""
    _ensure_logs_dir()
    entry = json.dumps(
        {
            "ts": datetime.now().isoformat(),
            "session": session[:8] if session else "none",
            "message": message[:200],
            "response_preview": response[:300],
        }
    )
    with open(ACTION_LOG, "a") as f:
        f.write(entry + "\n")


# ── Session helpers ───────────────────────────────────────────────────────


def _session_alive() -> bool:
    return _session_id is not None and (time.time() - _last_activity) < SESSION_TIMEOUT_SECONDS


def _run_claude(message: str, resume_session: str | None = None) -> tuple[str, str | None]:
    """Run claude -p with Opus model and return (response, session_id)."""
    global _calls_total, _calls_failed
    _calls_total += 1

    # Quota governor (single-key ob@): an operator request is incident-priority — run on ob@ when
    # there's headroom, but when ob@ is at its quota WALL, tell the operator rather than burn a
    # capped call. Lock-FREE capped() check (no single-flight side effect); fail-open if the
    # governor is unavailable so a broken governor never silences the bot.
    try:
        from quota_governor import QuotaGovernor  # co-located; sys.path set at import time

        if QuotaGovernor().capped():
            return (
                "⏳ ob@ is at its quota wall right now — try again after the window resets "
                "(the governor is conserving quota).",
                None,
            )
    except Exception:  # noqa: BLE001 — governor unavailable → proceed on ob@ (fail-open)
        pass

    cmd = [
        "claude",
        "-p",
        message,
        "--model",
        MODEL,
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
    ]

    if resume_session:
        cmd.extend(["--resume", resume_session])
    else:
        new_id = str(uuid.uuid4())
        cmd.extend(
            [
                "--session-id",
                new_id,
                "--system-prompt",
                SYSTEM_PROMPT,
            ]
        )

    env = os.environ.copy()
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

    try:
        # Route through claude_rotate: on a usage/quota-limit OR a 401 (dead creds) it rotates to
        # another Claude account and retries; a 401 also fires a Telegram alert from claude_rotate.
        # Only a still-failing result (all accounts exhausted) reaches the error branch below. Same
        # cwd/env contract as the bare subprocess call.
        result = claude_rotate.run_claude(
            cmd,
            timeout=CLAUDE_TIMEOUT_SECONDS,
            cwd=PROJECT_DIR,
            env=env,
        )
        raw_output = result.stdout.strip()

        # Handle auth failure
        if result.returncode != 0 and "401" in (result.stderr or ""):
            _calls_failed += 1
            return "🔥 Claude auth expired. Run `claude auth login` on VPS to fix.", None

        # Handle resume failure — fall back to new session
        if resume_session and not raw_output and "session" in (result.stderr or "").lower():
            logger.warning("Resume failed for %s, starting new session", resume_session[:8])
            return _run_claude(message, None)  # retry as new session

        # Extract result from JSON output (--output-format json returns {"result": "..."})
        response = ""
        if raw_output:
            try:
                data = json.loads(raw_output)
                if isinstance(data, dict):
                    response = data.get("result", "")
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "result" in item:
                            response = item["result"]
                            break
            except json.JSONDecodeError:
                response = raw_output  # fallback: use raw text if not valid JSON

        if not response and result.stderr:
            _calls_failed += 1
            response = f"⚠️ Error: {result.stderr[:500]}"
        if not response:
            response = "⚠️ Empty response."

        sid = resume_session if resume_session else new_id
        return response, sid

    except subprocess.TimeoutExpired:
        _calls_failed += 1
        return "⚠️ Timed out (5 min). Try a simpler question or a specific audit command.", None
    except Exception as e:
        _calls_failed += 1
        return f"⚠️ Error: {e}", None


# ── Telegram handlers ─────────────────────────────────────────────────────


async def _send_long_message(update: Update, text: str) -> None:
    """Send message, splitting if >4096 chars."""
    max_len = 4000
    if len(text) <= max_len:
        await update.message.reply_text(text)
        return
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = line
        else:
            current = current + "\n" + line if current else line
    if current:
        chunks.append(current)
    for chunk in chunks:
        await update.message.reply_text(chunk)
        await asyncio.sleep(0.3)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming Telegram message from owner."""
    global _session_id, _last_activity

    if update.effective_user.id != OWNER_ID:
        return

    text = update.message.text.strip()
    if not text:
        return

    async with _lock:
        # Session end
        if text.lower() in END_WORDS:
            if _session_id:
                _session_id = None
                await update.message.reply_text("Session ended. ✅")
            else:
                await update.message.reply_text("No active session.")
            return

        if _session_alive():
            assert _session_id is not None  # _session_alive() guarantees a live session id
            logger.info("Resume %s: %s", _session_id[:8], text[:50])
            response, sid = await asyncio.to_thread(_run_claude, text, _session_id)
            _last_activity = time.time()
        else:
            _session_id = None
            logger.info("New session: %s", text[:50])
            response, sid = await asyncio.to_thread(_run_claude, text)
            _session_id = sid if sid else None
            _last_activity = time.time()

        # Persistent action log — survives between sessions
        _log_action(text, response, sid or "none")

        await _send_long_message(update, response)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Bot error: %s", context.error)


# ── Daily heartbeat ───────────────────────────────────────────────────────


async def _heartbeat_loop(app: Application) -> None:
    """Send daily heartbeat at HEARTBEAT_HOUR local time."""
    global _last_heartbeat_date
    while True:
        await asyncio.sleep(60)  # check every minute
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        if now.hour == HEARTBEAT_HOUR and _last_heartbeat_date != today:
            _last_heartbeat_date = today
            uptime_h = int((time.time() - _boot_time) / 3600)
            msg = (
                f"💚 Sysadmin Bot — Daily Heartbeat\n\n"
                f"Uptime: {uptime_h}h | Model: {MODEL}\n"
                f"Calls: {_calls_total} total, {_calls_failed} failed\n"
                f"Session: {'active' if _session_alive() else 'idle'}"
            )
            try:
                await app.bot.send_message(chat_id=OWNER_ID, text=msg)
                logger.info("Heartbeat sent")
            except Exception as e:
                logger.error("Heartbeat failed: %s", e)


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    logger.info(
        "Starting VPS Sysadmin Bot (owner=%d, model=%s, health=:%d, project=%s)",
        OWNER_ID,
        MODEL,
        HEALTH_PORT,
        PROJECT_DIR,
    )

    _start_health_server()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    # Start heartbeat as a post-init task
    async def post_init(application: Application) -> None:
        asyncio.create_task(_heartbeat_loop(application))

    app.post_init = post_init

    logger.info("Bot running. Waiting for Telegram messages.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
