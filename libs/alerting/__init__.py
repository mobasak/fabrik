"""
fabrik-lib/alerting — fire-and-forget alert delivery.

Delivery chain:
  1. SSH → VPS Apprise → Telegram (primary)
  2. Direct Telegram Bot API (fallback if SSH fails)
  3. Log a per-method post-mortem (if both fail)

Never raises. Never blocks the caller more than TIMEOUT seconds.

⚠️ WHY STEP 3 IS NOT JUST A ONE-LINER (2026-08-16 liveness audit). This module used to
log ``Alert FAILED (all delivery methods): <title>`` and nothing else. Every alert the
box raises — quota drain, keepalive failure, CI health, watchdog — routes through here,
so when both legs broke the operator received silence and the log said only that
"delivery" failed. It had been failing for an unknown period with two independent
causes, neither visible. Now every attempt reports which method, and why.

Usage:
    from alerting import send_alert

    send_alert(
        title="PAUSED: iproyal_bw",
        body="IPRoyal returned 402. Top up at dashboard.iproyal.com",
        severity="critical",
    )

Prove the path end-to-end (an operator or a cron can run this):

    python -m alerting --selftest          # attempts real delivery, exits 1 if none worked
    python -m alerting --selftest --dry-run  # config-only, sends nothing

Env vars:
    ALERT_ENABLED            1 to enable, 0 to disable (default: 1 if any delivery var set)
    ALERT_MIN_INTERVAL       Dedup window in seconds (default: 300)
    ALERT_VPS_HOST           SSH config alias for VPS (default: vps)
    ALERT_APPRISE_URL        Internal Apprise URL on VPS (default: http://apprise:8000)
    TELEGRAM_FULL_BOT_TOKEN  Complete Telegram bot token (`id:secret`) — preferred
    TELEGRAM_BOT_ID          Numeric bot id, composed with TELEGRAM_BOT_TOKEN
    TELEGRAM_BOT_TOKEN       Secret half of the token (or a complete colon-shaped token)
    TELEGRAM_CHAT_ID         Telegram chat/user ID for delivery
"""

from __future__ import annotations

import logging
import os
import os as _os
import time

from ._attempt import DeliveryAttempt
from ._dotenv import load_env

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
    return bool(
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("TELEGRAM_FULL_BOT_TOKEN")
        or os.getenv("ALERT_VPS_HOST")
    )


def _min_interval() -> int:
    return int(os.getenv("ALERT_MIN_INTERVAL", "300"))


def attempt_delivery(title: str, body: str) -> list[DeliveryAttempt]:
    """Run the full delivery chain and return EVERY attempt, in order.

    Stops at the first success (delivery is fire-and-forget, not fan-out), so the
    returned list is "what we tried until something worked". Never raises: an
    import failure or an unexpected exception inside a leg becomes a failed
    attempt with the cause in ``detail``, because a delivery layer that throws is
    a delivery layer that also loses the alert it was throwing about.
    """
    attempts: list[DeliveryAttempt] = []

    for method, module_name in (("ssh-apprise", "apprise"), ("telegram-direct", "telegram")):
        try:
            module = __import__(f"{__name__}.{module_name}", fromlist=["try_send"])
            attempt = module.try_send(title, body)
        except Exception as exc:  # noqa: BLE001 — a broken leg must not kill the chain
            attempt = DeliveryAttempt(
                method, False, f"delivery module unusable: {type(exc).__name__}: {exc}"
            )
        attempts.append(attempt)
        if attempt.ok:
            break

    return attempts


def format_diagnosis(title: str, attempts: list[DeliveryAttempt]) -> str:
    """Render a multi-line, operator-actionable post-mortem for a failed alert."""
    lines = [
        f"Alert FAILED — no delivery method worked ({len(attempts)} tried): {title}",
    ]
    for i, attempt in enumerate(attempts, 1):
        lines.append(f"  [{i}] {attempt.render()}")
    lines.append(
        "  → prove the path with: python -m alerting --selftest"
        " (from a dir under the repo whose .env holds the Telegram keys)"
    )
    return "\n".join(lines)


def send_alert(title: str, body: str, severity: str = "warning") -> bool:
    """Send an alert. Returns True if delivered, False otherwise.

    Args:
        title:    Short subject, used for dedup (same title = same alert).
        body:     Detail text, up to ~500 chars.
        severity: "critical" | "warning" | "info"
    """
    if not _is_enabled():
        return False

    # Dedup keys on (severity, title), not title alone. With a title-only key an `info`
    # alert silently swallowed the `critical` escalation of the SAME condition for the
    # whole window — precisely the "operator receives nothing" failure this module is
    # being repaired for. Repeat noise at one severity is still suppressed.
    dedup_key = f"{severity}:{title}"
    now = time.time()
    last = _last_sent.get(dedup_key, 0)
    if now - last < _min_interval():
        logger.debug("Alert suppressed (dedup): %s", dedup_key)
        return False

    emoji = SEVERITY_EMOJI.get(severity, "🟡")
    full_title = f"{emoji} {title}"

    attempts = attempt_delivery(full_title, body)
    delivered = any(a.ok for a in attempts)

    if delivered:
        _last_sent[dedup_key] = now
        logger.info("Alert sent [%s]: %s", severity, title)
    else:
        # LOUD and diagnosable. The old single line named neither the methods nor
        # the causes, which is how two independent breakages stayed invisible.
        logger.warning("%s\n  body: %s", format_diagnosis(title, attempts), body[:200])

    return delivered


def selftest_report(dry_run: bool = False) -> tuple[int, list[str]]:
    """Prove the alert path end-to-end. Returns ``(exit_code, report_lines)``.

    Returning the report instead of emitting it keeps this library free of direct
    stdout writes (the gate's Print/Console.log ban covers `libs/`, and rightly: a
    library that writes to stdout cannot be embedded) and makes the outcome directly
    assertable in tests without capturing streams. ``__main__.py`` owns the one write.

    ``dry_run`` reports configuration only and sends nothing — useful in CI or on a
    box where a real Telegram message would be noise. Without it, a real alert is
    delivered, which is the only way to prove the path actually works: a config that
    *looks* right is exactly what shipped a 404 for an unknown number of weeks.
    """
    from . import telegram as _telegram

    token, source = _telegram.resolve_bot_token()
    lines = [
        "alerting selftest",
        f"  ALERT_ENABLED resolves to: {_is_enabled()}",
        f"  telegram token: {'RESOLVED' if token else 'UNRESOLVED'} — {source}",
        f"  TELEGRAM_CHAT_ID: {'set' if os.getenv('TELEGRAM_CHAT_ID') else 'MISSING'}",
        f"  ALERT_VPS_HOST: {os.getenv('ALERT_VPS_HOST', 'vps')} (default 'vps')",
    ]

    if dry_run:
        ok = bool(token and os.getenv("TELEGRAM_CHAT_ID"))
        state = "complete" if ok else "incomplete"
        lines.append(
            f"{'PASS' if ok else 'FAIL'}: configuration {state} (dry-run — nothing sent)"
        )
        return (0 if ok else 1), lines

    if not _is_enabled():
        lines.append("FAIL: alerting is disabled (ALERT_ENABLED=0 or no delivery var set)")
        return 1, lines

    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    attempts = attempt_delivery(
        "ℹ️ alerting selftest",
        f"Delivery-path selftest at {stamp}. If you can read this, alerts work.",
    )
    lines.extend(f"  [{i}] {a.render()}" for i, a in enumerate(attempts, 1))

    if any(a.ok for a in attempts):
        lines.append("PASS: alert delivered — the alert path works end to end")
        return 0, lines
    lines.append(format_diagnosis("alerting selftest", attempts))
    lines.append("FAIL: no delivery method worked")
    return 1, lines


def _main(argv: list[str] | None = None) -> int:
    """CLI entry. Writes the report to stdout and returns the exit code."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="alerting", description="Prove the alert delivery path works end to end"
    )
    parser.add_argument("--selftest", action="store_true", help="Run the delivery selftest")
    parser.add_argument(
        "--dry-run", action="store_true", help="Report configuration only; send nothing"
    )
    args = parser.parse_args(argv)
    if not args.selftest:
        parser.print_help()
        return 2
    code, lines = selftest_report(dry_run=args.dry_run)
    sys.stdout.write("\n".join(lines) + "\n")
    return code


# Autoload the curated keys AT IMPORT so a bare os.getenv(...) works from any cwd — a bare
# python/agent/CLI/test call never sources `.env`. NON-OVERRIDING (real env / container vars win),
# never raises. Opt out with FABRIK_NO_AUTOLOAD=1.
if _os.getenv("FABRIK_NO_AUTOLOAD") != "1":
    try:
        load_env(_os.getcwd())
    except Exception:  # noqa: BLE001 — import must never fail on a best-effort env autoload
        pass


if __name__ == "__main__":
    raise SystemExit(_main())
