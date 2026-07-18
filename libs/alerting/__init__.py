"""
fabrik-lib/alerting — fire-and-forget alert delivery.

Delivery chain:
  1. SSH → VPS Apprise → Telegram (primary)
  2. Direct Telegram Bot API (fallback if SSH fails)
  3. Log warning (if both fail)

Never raises. Never blocks the caller more than TIMEOUT seconds.

Usage:
    from alerting import send_alert

    send_alert(
        title="PAUSED: iproyal_bw",
        body="IPRoyal returned 402. Top up at dashboard.iproyal.com",
        severity="critical",
    )

Env vars:
    ALERT_ENABLED         1 to enable, 0 to disable (default: 1 if any delivery var set)
    ALERT_MIN_INTERVAL    Dedup window in seconds (default: 300)
    ALERT_VPS_HOST        SSH config alias for VPS (default: vps)
    ALERT_APPRISE_URL     Internal Apprise URL on VPS (default: http://apprise:8000)
    TELEGRAM_BOT_TOKEN    Direct Telegram Bot API token
    TELEGRAM_CHAT_ID      Telegram chat/user ID for delivery
"""


import os as _os

from ._dotenv import load_env
import logging
import os
import time

logger = logging.getLogger(__name__)

# Dedup state: title → last_sent_epoch
_last_sent: dict[str, float] = {}

SEVERITY_EMOJI = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "ℹ️",
}


def _is_enabled() -> bool:
    val = os.getenv("ALERT_ENABLED", "").strip()
    if val == "0":
        return False
    if val == "1":
        return True
    # Auto-enable if any delivery var is present
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("ALERT_VPS_HOST"))


def _min_interval() -> int:
    return int(os.getenv("ALERT_MIN_INTERVAL", "300"))


def send_alert(title: str, body: str, severity: str = "warning") -> bool:
    """Send an alert. Returns True if delivered, False otherwise.

    Args:
        title:    Short subject, used for dedup (same title = same alert).
        body:     Detail text, up to ~500 chars.
        severity: "critical" | "warning" | "info"
    """
    if not _is_enabled():
        return False

    now = time.time()
    last = _last_sent.get(title, 0)
    if now - last < _min_interval():
        logger.debug("Alert suppressed (dedup): %s", title)
        return False

    emoji = SEVERITY_EMOJI.get(severity, "🟡")
    full_title = f"{emoji} {title}"

    # Try primary: SSH → Apprise
    delivered = False
    try:
        from alerting import apprise as _apprise

        delivered = _apprise.send(full_title, body)
    except Exception as exc:
        logger.debug("Apprise delivery failed: %s", exc)

    # Fallback: direct Telegram
    if not delivered:
        try:
            from alerting import telegram as _telegram

            delivered = _telegram.send(full_title, body)
        except Exception as exc:
            logger.debug("Telegram direct delivery failed: %s", exc)

    if delivered:
        _last_sent[title] = now
        logger.info("Alert sent [%s]: %s", severity, title)
    else:
        logger.warning(
            "Alert FAILED (all delivery methods): %s — %s", title, body[:100]
        )

    return delivered


# Autoload the curated keys AT IMPORT so a bare os.getenv(...) works from any cwd — a bare
# python/agent/CLI/test call never sources `.env`. NON-OVERRIDING (real env / container vars win),
# never raises. Opt out with FABRIK_NO_AUTOLOAD=1.
if _os.getenv("FABRIK_NO_AUTOLOAD") != "1":
    try:
        load_env(_os.getcwd())
    except Exception:  # noqa: BLE001 — import must never fail on a best-effort env autoload
        pass
