#!/bin/bash
# AFTER-EDIT: wsl_startup_hook.sh, daily_refresh.sh (both call this)
#
# Fire one critical Telegram alert from a pipeline step.
#
# daily_refresh.sh's two HEARTBEAT alerts (:530, :534) now route through here. Its two RANKER
# and ORACLE alerts (:425, :480) deliberately stay inline: test_flywheel_safety.py::test_the_alert_can_actually_fire_not_just_exist pins
# that form for the ranker line specifically. The heartbeat pair were migrated because they had
# NO load_dotenv at all and were therefore silent no-ops — alerting._is_enabled() reads
# TELEGRAM_BOT_TOKEN from the process env, so a disk-full heartbeat failure alerted nobody.
# An earlier version of this header said daily_refresh carried "two" inlined copies; it carried
# FOUR, and the two the header omitted were exactly the broken ones. The header's inaccuracy is
# what hid them — which is why it now enumerates all four.
#
# Extracted 2026-08-15 because the call sites live INSIDE wsl_startup_hook.sh's double-quoted
# `nohup bash -c "…"` string, where an inline `python -c "…"` needs its quotes escaped and a
# single missed backslash is a syntax error that `bash -n` on the outer file DOES catch but
# that is trivially reintroduced. A helper keeps the call site a single unquoted word list.
#
# ⚠️ load_dotenv BEFORE importing alerting: `alerting` reads TELEGRAM_BOT_TOKEN from the
# process env and does not load .env itself, so a call without this is a SILENT no-op — the
# exact defect check_daily_refresh_freshness.py:39-43 documents and that A.0 gate 3 exists to
# prevent. Never "simplify" this by dropping the dotenv line.
#
# Usage: bash pipeline_alert.sh <title> <body>
# Never fails: alerting must not be able to break a boot or a refresh.
set -u

FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"
TITLE="${1:-pipeline alert}"
BODY="${2:-(no body)}"

# FABRIK_ROOT is passed IN rather than hardcoded in the python: the interpreter came from the
# variable while sys.path and .env were pinned to /opt/fabrik, so under an override the helper
# either sent nothing or read the wrong repo's .env — silently, since every path exits 0.
PY_BIN="$FABRIK_ROOT/.venv/bin/python"
if [ ! -x "$PY_BIN" ]; then
  # a rebuilt or interrupted venv: the heredoc never ran and NOTHING was said — the one alert
  # for "the chain never started" exited 0 in silence (FC6)
  echo "[pipeline_alert] NOT delivered (no interpreter at $PY_BIN): $TITLE" >&2
  exit 0
fi
"$PY_BIN" - "$TITLE" "$BODY" "$FABRIK_ROOT" <<'PY' 2>&1 || true
import os, sys, pathlib
os.environ.setdefault("FABRIK_NO_AUTOLOAD", "1")  # the ONLY env source is FABRIK_ROOT/.env below — the package's cwd autoload read whatever directory the caller sat in (FC6)
root = pathlib.Path(sys.argv[3])
sys.path.insert(0, str(root / "libs"))  # the REPAIRED package: the vendored kilo-benchmarks copy posted the split Telegram token raw (FC6)
env_file = root / ".env"
try:
    from dotenv import load_dotenv
    if not load_dotenv(env_file, override=False):
        print(f"[pipeline_alert] no .env at {env_file}", file=sys.stderr)  # a MISSING .env was silent; only an unreadable one was said (FC6)
except Exception as exc:  # noqa: BLE001 — SAID, never swallowed: an unreadable .env was a silent no-op (FB10)
    print(f"[pipeline_alert] .env not loaded: {type(exc).__name__}: {exc}", file=sys.stderr)
try:
    import alerting
    # send_alert returns False — no exception, no log line — when alerting is DISABLED (no token,
    # a fresh .env) or when EVERY delivery method failed; dedup cannot fire across processes
    # (its dict lives in this interpreter). The cause is named, not guessed (FB10/FC6)
    if not alerting.send_alert(title=sys.argv[1], body=sys.argv[2], severity="critical"):
        why = "alerting disabled — no TELEGRAM_*/ALERT_VPS_HOST in the environment" if not alerting._is_enabled() else "every delivery method failed (see the diagnosis above)"
        print(f"[pipeline_alert] NOT delivered ({why}): {sys.argv[1]}", file=sys.stderr)
except Exception as exc:  # noqa: BLE001 — an alert failure must never break the pipeline
    print(f"[pipeline_alert] send failed: {type(exc).__name__}: {exc}", file=sys.stderr)
PY
exit 0
