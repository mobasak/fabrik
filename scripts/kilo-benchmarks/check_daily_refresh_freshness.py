#!/usr/bin/env python3
"""Heartbeat check for daily_refresh.sh — fires an alert when stale.

daily_refresh.sh writes a UTC timestamp to
`scripts/kilo-benchmarks/cache/daily_refresh_last_success.txt` at the
end of every successful run. This script reads that timestamp at the
START of every run and fires a Telegram alert if it's older than
`max_age_hours` (default 36 hours — catches "yesterday's run never
completed" without false-positiving on the operator running the cron
slightly late).

If the timestamp file is missing entirely, that's a first-run
condition — don't alert.

Per docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md
(Phase 5 cron-skip heartbeat deliverable).

Usage
-----
  python check_daily_refresh_freshness.py
  python check_daily_refresh_freshness.py --max-age-hours 48

Exit codes
----------
  0  fresh / first-run (no alert fired)
  0  stale + alert fired (still exit 0 so daily_refresh.sh keeps going)
  1  unexpected error (caller decides what to do)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# load_dotenv before importing alerting so TELEGRAM_BOT_TOKEN is in env.
try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]

    load_dotenv(SCRIPT_DIR.parents[1] / ".env", override=False)
except ImportError:
    pass

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
_LIBS = (
    SCRIPT_DIR.parents[1] / "libs"
)  # the ONE alerting implementation (D-112): a same-named shim in this directory self-imported and this file's `except ImportError` made the stale-heartbeat alert a silent no-op (FD6)
sys.path[:] = [p for p in sys.path if p != str(_LIBS)]
sys.path.insert(
    0, str(_LIBS)
)  # FIRST, unconditionally: a libs entry already LATER on sys.path left SCRIPT_DIR ahead of it — the resolution order D-112 exists to prevent (FE7)
os.environ.setdefault(
    "FABRIK_NO_AUTOLOAD", "1"
)  # the ONLY .env this checker reads is the hub's (above): the boot hook runs it from /opt/session-recall, where the package's cwd autoload read THAT repo's .env (FE6)

TIMESTAMP_FILE_DEFAULT = SCRIPT_DIR / "cache" / "daily_refresh_last_success.txt"
MAX_AGE_HOURS_DEFAULT = 36

# The ranker's own output doc. Watching ONLY daily_refresh_last_success.txt leaves a hole:
# daily_refresh.sh writes that timestamp even when rank_task_subagents exits non-zero (its
# call site ends `|| true` and the script has no `set -e`), and since Phase A.0 a BROKEN
# flywheel read deliberately KEEPS the previous doc rather than overwriting it. So a
# permanently broken flywheel is invisible to the heartbeat while the fleet drifts onto an
# ever-staler selection doc. Past select.py's 14-day staleness gate every vendored
# pick_models silently falls back to the baked-in _TABLE — so alert well before that.
SELECTION_DOC_DEFAULT = SCRIPT_DIR.parents[1] / "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"
DOC_MAX_AGE_DAYS_DEFAULT = 3
_DOC_DATE = re.compile(r"^Last refresh:\s*(\d{4}-\d{2}-\d{2})", re.M)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _read_timestamp(path: Path) -> datetime | None:
    """Return the timestamp from the file (UTC-aware), or None if missing."""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        # Accept ISO 8601 with or without timezone; treat naive as UTC.
        ts = datetime.fromisoformat(text)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts
    except ValueError:
        return None


def check(
    timestamp_file: Path = TIMESTAMP_FILE_DEFAULT,
    max_age_hours: int = MAX_AGE_HOURS_DEFAULT,
    now: datetime | None = None,
) -> dict[str, object]:
    """Pure function: returns the check result without firing the alert.

    Result dict:
      status: "fresh" | "stale" | "first_run"
      age_hours: float (None if first_run)
      timestamp: ISO string (None if first_run)
      threshold_hours: int
    """
    now = now or _now_utc()
    ts = _read_timestamp(timestamp_file)
    if ts is None:
        return {
            "status": "first_run",
            "age_hours": None,
            "timestamp": None,
            "threshold_hours": max_age_hours,
        }
    age = now - ts
    age_hours = age.total_seconds() / 3600.0
    status = "stale" if age > timedelta(hours=max_age_hours) else "fresh"
    return {
        "status": status,
        "age_hours": age_hours,
        "timestamp": ts.isoformat(),
        "threshold_hours": max_age_hours,
    }


def check_selection_doc(
    doc: Path = SELECTION_DOC_DEFAULT,
    max_age_days: int = DOC_MAX_AGE_DAYS_DEFAULT,
    now: datetime | None = None,
) -> dict[str, object]:
    """Is the ranker's OUTPUT actually being refreshed? Pure function.

    status: "fresh" | "stale" | "stub" | "missing" | "undated" | "future"
    """
    now = now or _now_utc()
    if not doc.exists():
        return {"status": "missing", "age_days": None, "threshold_days": max_age_days}
    try:
        text = doc.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {
            "status": "unreadable",
            "age_days": None,
            "threshold_days": max_age_days,
        }  # a permission slip on the fleet-synced doc silenced this leg as "missing" (FE6)
    if "AGGREGATION FAILED" in text:
        return {"status": "stub", "age_days": None, "threshold_days": max_age_days}
    m = _DOC_DATE.search(text)
    if not m:
        return {"status": "undated", "age_days": None, "threshold_days": max_age_days}
    try:
        stamped = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        # `_DOC_DATE` accepts any \d{4}-\d{2}-\d{2}, so `2026-13-45` matches and then raises
        # out of main() — the same "an unhealthy doc kills the check" class this module
        # already fixed once. An unparseable date is `undated`, not a crash.
        return {"status": "undated", "age_days": None, "threshold_days": max_age_days}
    # rank_task_subagents stamps date.today() (LOCAL; this box is UTC+3) and we parse as UTC,
    # so a doc written after 21:00 UTC legitimately reads up to a day in the future. Tolerate
    # exactly that much. Beyond it the stamp is bogus (clock skew, a forged date, a hand-edit)
    # and must NOT read as "refreshed today" — select.py's staleness gate trusts this same
    # date, so a far-future stamp silences both legs forever.
    raw_age = (now - stamped).total_seconds() / 86400.0
    if raw_age < -1.5:
        return {
            "status": "future",
            "age_days": raw_age,
            "stamped": m.group(1),
            "threshold_days": max_age_days,
        }
    age_days = max(0.0, raw_age)
    return {
        "status": "stale" if age_days > max_age_days else "fresh",
        "age_days": age_days,
        "stamped": m.group(1),
        "threshold_days": max_age_days,
    }


def _why() -> str:
    """Why `send_alert` returned False: an explicit mute, no delivery keys, or every method failed."""
    if os.getenv("ALERT_ENABLED", "").strip() == "0":
        return "ALERT_ENABLED=0 is set"
    try:
        from alerting import _is_enabled  # type: ignore[import-not-found]

        if not _is_enabled():
            return "alerting disabled — no TELEGRAM_*/ALERT_VPS_HOST in the environment"
    except Exception:  # noqa: BLE001 - the diagnosis must never read as the send failing
        return "reason unavailable"
    return "every delivery method failed (see the diagnosis above)"


def maybe_alert_selection_doc(result: dict[str, object]) -> bool:
    """Fire an alert when the ranker's output has stopped being refreshed."""
    if result["status"] in ("fresh", "missing"):
        return False
    # Built per-status, NOT eagerly: the "stale" body formats age_days, which is None for
    # "stub" and "undated". Because the key EXISTS, `.get("age_days", 0)`'s default never
    # applied and both of those states raised TypeError out of main() — so the two worst
    # cases (the flywheel has NEVER succeeded; the doc lost its date header) delivered no
    # alert at all, and daily_refresh.sh swallowed the non-zero exit into a logfile.
    status = str(result["status"])
    if status == "stale":
        body = (
            f"TASK_SUBAGENT_SELECTION.md is stamped {result.get('stamped')} "
            f"({float(result['age_days'] or 0):.1f} days old > {result['threshold_days']}d). "
            "daily_refresh.sh may still be 'succeeding' while rank_task_subagents fails: a "
            "BROKEN flywheel read keeps the previous doc by design, so the heartbeat stays "
            "green. Past 14 days select.py treats it as stale and every vendored pick_models "
            "falls back to the baked-in _TABLE. Check the postgres/sudo path on this host."
        )
    elif status == "stub":
        body = (
            "TASK_SUBAGENT_SELECTION.md is the AGGREGATION FAILED stub — the flywheel read "
            "has never succeeded on this host. pick_models is running on the baked-in _TABLE."
        )
    elif status == "future":
        body = (
            f"TASK_SUBAGENT_SELECTION.md is stamped {result.get('stamped')}, which is "
            f"{abs(float(result['age_days'] or 0)):.1f} days in the FUTURE. Clock skew or a "
            "hand-edited date. select.py's 14-day staleness gate reads this same line, so a "
            "future stamp makes the doc look permanently fresh to every vendored pick_models."
        )
    elif status == "unreadable":
        body = (
            "TASK_SUBAGENT_SELECTION.md exists but cannot be READ (a permission slip on the "
            "fleet-synced doc) — its staleness cannot be checked and every vendored pick_models "
            "may already be on the baked-in _TABLE."
        )
    elif status == "undated":
        body = (
            "TASK_SUBAGENT_SELECTION.md has no parseable 'Last refresh:' line, so its "
            "staleness cannot be checked. The renderer may have changed."
        )
    else:
        return False

    try:
        from alerting import send_alert  # type: ignore[import-not-found]
    except ImportError:
        print(
            f"[heartbeat] selection doc {result['status']} (alerting unavailable)", file=sys.stderr
        )
        return False
    title = f"TASK_SUBAGENT_SELECTION.md is {status}"
    try:
        sent = bool(send_alert(title=title, body=body, severity="critical"))
        if not sent:
            print(f"[heartbeat] alert NOT delivered ({_why()}): {title}", file=sys.stderr)  # FE6
        return sent
    except Exception as exc:  # noqa: BLE001 — never break the refresh pipeline
        print(f"[heartbeat] alert failed: {type(exc).__name__}", file=sys.stderr)
        return False


def maybe_alert(result: dict[str, object]) -> bool:
    """Fire an alert if the result is stale. Returns True if alert was sent."""
    if result["status"] != "stale":
        return False
    try:
        from alerting import send_alert  # type: ignore[import-not-found]
    except ImportError:
        print(
            f"[heartbeat] STALE but alerting module unavailable: "
            f"last success {result['timestamp']} "
            f"({result['age_hours']:.1f}h ago > {result['threshold_hours']}h)",
            file=sys.stderr,
        )
        return False
    # Defensive: if send_alert raises (network blip, malformed alerting
    # config, etc.) we still want the heartbeat script to exit cleanly so
    # daily_refresh.sh continues with its other steps. Logging the failure
    # to stderr means the operator still sees it in the daily refresh log.
    title = "kilo-benchmarks daily refresh is stale"
    try:
        sent = bool(
            send_alert(
                title=title,
                body=(
                    f"daily_refresh.sh last completed successfully at "
                    f"{result['timestamp']} UTC "
                    f"({result['age_hours']:.1f} hours ago — threshold "
                    f"{result['threshold_hours']}h). The cron may be skipped or the "
                    f"refresh pipeline is hanging. Investigate: "
                    f"scripts/kilo-benchmarks/cache/update.log (the real log — "
                    f".droid/daily_refresh.log does not exist), and note the heartbeat is "
                    f"written by whichever entry point wins the daily lockfile: "
                    f"wsl_startup_hook.sh on a booted workstation, daily_refresh.sh from cron."
                ),
                severity="critical",
            )
        )
        if not sent:
            print(
                f"[heartbeat] alert NOT delivered ({_why()}): {title}",
                file=sys.stderr,
            )  # a False return was silent on both legs — the one alert for "the pipeline stopped running" said nothing (FE6)
        return sent
    except Exception as e:
        print(
            f"[heartbeat] send_alert raised {type(e).__name__}: {e}; "
            f"alert NOT delivered (stale state: {result['timestamp']}, "
            f"{result['age_hours']:.1f}h ago)",
            file=sys.stderr,
        )
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp-file", type=Path, default=TIMESTAMP_FILE_DEFAULT)
    parser.add_argument("--max-age-hours", type=int, default=MAX_AGE_HOURS_DEFAULT)
    parser.add_argument("--selection-doc", type=Path, default=SELECTION_DOC_DEFAULT)
    parser.add_argument("--doc-max-age-days", type=int, default=DOC_MAX_AGE_DAYS_DEFAULT)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    try:
        result = check(args.timestamp_file, args.max_age_hours)
    except Exception as e:
        print(f"[heartbeat] check failed: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        if result["status"] == "first_run":
            print(f"[heartbeat] FIRST RUN (no prior timestamp at {args.timestamp_file})")
        elif result["status"] == "fresh":
            print(f"[heartbeat] FRESH ({result['age_hours']:.1f}h since last success)")
        else:
            print(
                f"[heartbeat] STALE ({result['age_hours']:.1f}h "
                f"> {result['threshold_hours']}h threshold)"
            )

    fired = maybe_alert(result)
    if fired and not args.quiet:
        print("[heartbeat] alert fired")

    # Second, independent leg: is the ranker's OUTPUT actually being refreshed? The heartbeat
    # above can be green while this is stale (see SELECTION_DOC_DEFAULT).
    doc_result = check_selection_doc(args.selection_doc, args.doc_max_age_days)
    if not args.quiet:
        age = doc_result.get("age_days")
        detail = f"{age:.1f}d" if isinstance(age, float) else str(doc_result["status"])
        print(f"[heartbeat] selection doc: {doc_result['status']} ({detail})")
    if maybe_alert_selection_doc(doc_result) and not args.quiet:
        print("[heartbeat] selection-doc alert fired")
    return 0


if __name__ == "__main__":
    sys.exit(main())
