#!/bin/bash
# AFTER-EDIT: wsl_startup_hook.sh, daily_refresh.sh (both alert through this)
#
# Fire one critical Telegram alert from a pipeline step.
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

"$FABRIK_ROOT/.venv/bin/python" - "$TITLE" "$BODY" <<'PY' 2>&1 || true
import sys, pathlib
kb = pathlib.Path("/opt/fabrik/scripts/kilo-benchmarks")
sys.path.insert(0, str(kb))
try:
    from dotenv import load_dotenv
    load_dotenv(kb.parents[1] / ".env", override=False)
except Exception:
    pass
try:
    from alerting import send_alert
    send_alert(title=sys.argv[1], body=sys.argv[2], severity="critical")
except Exception as exc:  # noqa: BLE001 — an alert failure must never break the pipeline
    print(f"[pipeline_alert] send failed: {type(exc).__name__}: {exc}", file=sys.stderr)
PY
exit 0
