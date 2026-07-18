"""
Direct Telegram Bot API delivery (fallback when SSH/Apprise unavailable).

Env vars:
    TELEGRAM_BOT_TOKEN   Bot token from @BotFather
    TELEGRAM_CHAT_ID     Target chat/user ID
"""

import logging
import os
import urllib.request
import urllib.parse
import json

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
TIMEOUT = 8


def send(title: str, body: str) -> bool:
    """Send via direct Telegram Bot API. Returns True on success."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        logger.debug("Telegram not configured (missing BOT_TOKEN or CHAT_ID)")
        return False

    text = f"*{title}*\n{body}"[:4096]  # Telegram message limit

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
    ).encode()

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if resp.status == 200:
                return True
            logger.debug("Telegram HTTP %d", resp.status)
            return False
    except Exception as exc:
        logger.debug("Telegram exception: %s", exc)
        return False
