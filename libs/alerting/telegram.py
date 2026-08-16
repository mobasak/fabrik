"""Direct Telegram Bot API delivery (fallback when SSH/Apprise is unavailable).

⚠️ THE CREDENTIAL IS SPLIT IN `/opt/fabrik/.env` — this is the bug that killed alerting.
`TELEGRAM_BOT_TOKEN` there holds ONLY the *secret half* (`AAHw…`, no colon). A usable
Telegram token is `<bot_id>:<secret>`; posting to `/bot<secret>/sendMessage` returns
HTTP 404 `Not Found`, which reads like a dead endpoint rather than a malformed
credential. `~/.claude/bin/claude-sound.sh` already knew this and composed the halves;
this module did not, so every direct-Telegram fallback 404'd (measured 2026-08-16).

Resolution order (:func:`resolve_bot_token`):
  1. ``TELEGRAM_FULL_BOT_TOKEN`` — the complete `id:secret`, preferred.
  2. ``TELEGRAM_BOT_ID`` + ``TELEGRAM_BOT_TOKEN`` — composed.
  3. ``TELEGRAM_BOT_TOKEN`` alone, but ONLY if it is already colon-shaped.
A colon-less result is never sent: it cannot work, and failing loudly at resolution
beats a 404 the operator has to reverse-engineer.

Env vars:
    TELEGRAM_FULL_BOT_TOKEN  Complete bot token from @BotFather (`id:secret`)
    TELEGRAM_BOT_ID          Numeric bot id (composed with the secret below)
    TELEGRAM_BOT_TOKEN       Secret half, or a complete colon-shaped token
    TELEGRAM_CHAT_ID         Target chat/user ID
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

from ._attempt import DeliveryAttempt

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
TIMEOUT = 8
METHOD = "telegram-direct"


def resolve_bot_token() -> tuple[str, str]:
    """Return ``(token, source)`` — the usable `id:secret` token and where it came from.

    Returns ``("", "<reason>")`` when no colon-shaped token can be assembled; the
    reason is written straight into the failure detail so the operator learns which
    variable to set rather than that "Telegram is broken".
    """
    full = os.getenv("TELEGRAM_FULL_BOT_TOKEN", "").strip()
    if full:
        if ":" not in full:
            return "", "TELEGRAM_FULL_BOT_TOKEN is set but is not `id:secret` shaped"
        return full, "TELEGRAM_FULL_BOT_TOKEN"

    secret = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    bot_id = os.getenv("TELEGRAM_BOT_ID", "").strip()

    if secret and ":" in secret:
        return secret, "TELEGRAM_BOT_TOKEN (already complete)"
    if bot_id and secret:
        return f"{bot_id}:{secret}", "TELEGRAM_BOT_ID + TELEGRAM_BOT_TOKEN (composed)"
    if secret and not bot_id:
        return "", (
            "TELEGRAM_BOT_TOKEN holds only the secret half (no colon) and "
            "TELEGRAM_BOT_ID / TELEGRAM_FULL_BOT_TOKEN are unset"
        )
    if bot_id and not secret:
        # Distinct from "no vars set": the operator configured half of it. Saying
        # "nothing is set" here would send them looking for the wrong problem — the
        # entire point of this rewrite is that the diagnosis names the real gap.
        return "", "TELEGRAM_BOT_ID is set but TELEGRAM_BOT_TOKEN is empty"
    return "", "no TELEGRAM_FULL_BOT_TOKEN / TELEGRAM_BOT_ID / TELEGRAM_BOT_TOKEN set"


def try_send(title: str, body: str) -> DeliveryAttempt:
    """Attempt delivery and report the outcome with its cause."""
    token, source = resolve_bot_token()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token:
        return DeliveryAttempt(METHOD, False, f"no usable bot token — {source}", "unconfigured")
    if not chat_id:
        return DeliveryAttempt(
            METHOD, False, "TELEGRAM_CHAT_ID is not set", f"token from {source}"
        )

    config = f"token from {source}, chat_id={chat_id}"
    text = f"*{title}*\n{body}"[:4096]  # Telegram message limit
    payload = json.dumps(
        {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    ).encode()

    req = urllib.request.Request(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 — fixed https host
            if resp.status == 200:
                return DeliveryAttempt(METHOD, True, "message accepted by Telegram", config)
            return DeliveryAttempt(METHOD, False, f"HTTP {resp.status} from Telegram", config)
    except urllib.error.HTTPError as exc:
        # 404 here means "no bot with this token", NOT "endpoint missing" — spell that
        # out, because the raw status is what sent the last investigation down the
        # wrong path. 401 is the same class; 400 is usually a bad chat_id/markdown.
        hint = {
            404: "bot token rejected (no such bot) — check TELEGRAM_FULL_BOT_TOKEN",
            401: "bot token unauthorized/revoked — reissue via @BotFather",
            400: "request rejected — usually a wrong TELEGRAM_CHAT_ID or bad Markdown",
            403: "bot blocked by the target chat — /start the bot from that chat",
        }.get(exc.code, "Telegram rejected the request")
        return DeliveryAttempt(METHOD, False, f"HTTP {exc.code}: {hint}", config)
    except urllib.error.URLError as exc:
        return DeliveryAttempt(METHOD, False, f"network unreachable: {exc.reason}", config)
    except Exception as exc:  # noqa: BLE001 — delivery must never raise into the caller
        return DeliveryAttempt(METHOD, False, f"{type(exc).__name__}: {exc}", config)


def send(title: str, body: str) -> bool:
    """Back-compatible boolean wrapper around :func:`try_send`."""
    attempt = try_send(title, body)
    if not attempt.ok:
        logger.debug("Telegram delivery failed: %s", attempt.detail)
    return attempt.ok
