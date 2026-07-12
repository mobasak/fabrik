#!/usr/bin/env bash
# ensure-apprise-alerts-config.sh — guarantee Apprise's stateful "alerts" config exists. Idempotent.
#
# WHY: the fleet's notification convention is `POST http://apprise:8000/notify/alerts` — used by Gatus
# (configs/gatus/_base.yaml), scripts/sysadmin/{morning-report,weekly-security,daily-digest}.sh, and the AI
# sysadmin (system-prompt.txt). That is Apprise's *stateful* endpoint (key = "alerts"). Apprise, however, is
# deployed with only the STATELESS target (`APPRISE_STATELESS_URLS=tgram://…`, served at bare `/notify`).
# With no "alerts" config, Apprise answers `/notify/alerts` with **204 No Content** — accepted, but NOTHING
# is sent. Every alert from every caller was silently discarded.
#
# That is why vps1's alertmanager could sit dead for 4 days (2026-07-08 → 07-12) with Gatus dutifully
# logging 5,893 failed checks and the operator receiving nothing.
#
# This script (re)creates the "alerts" stateful config from the container's own APPRISE_STATELESS_URLS, so
# `/notify/alerts` returns 200 and delivers to Telegram. The config persists in the `apprise-config` volume —
# BUT it is NOT reproducible from git, so any apprise volume rebuild silently re-breaks the path. Run this
# after any apprise (re)deploy. Safe to run repeatedly / from cron.
#
# Usage:  sudo bash scripts/sysadmin/ensure-apprise-alerts-config.sh [--check]
#         --check  → report status only, change nothing (exit 1 if the path is broken)
#
# AFTER-EDIT: docs/TROUBLESHOOTING.md
set -uo pipefail

CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

probe() {  # → HTTP code for the /notify/alerts path (200 = delivering, 204 = silently dropping)
  docker exec apprise curl -s -o /dev/null -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' \
    -d '{"title":"[fabrik] apprise alerts-path probe","body":"idempotent config check"}' \
    http://localhost:8000/notify/alerts 2>/dev/null
}

if ! docker ps --format '{{.Names}}' | grep -qx apprise; then
  echo "ERROR: apprise container is not running" >&2
  exit 1
fi

code="$(probe)"
if [ "$code" = "200" ]; then
  echo "OK: apprise /notify/alerts → 200 (delivering)"
  exit 0
fi

echo "BROKEN: apprise /notify/alerts → ${code} (204 = accepted but NOTHING sent — no 'alerts' config)"
if [ "$CHECK_ONLY" = 1 ]; then
  echo "  (--check: not repairing). Fix: re-run without --check."
  exit 1
fi

echo "repairing: creating the 'alerts' stateful config from APPRISE_STATELESS_URLS…"
add_code="$(docker exec apprise sh -c \
  'curl -s -o /dev/null -w "%{http_code}" -X POST -d "urls=$APPRISE_STATELESS_URLS" http://localhost:8000/add/alerts')"
if [ "$add_code" != "200" ]; then
  echo "ERROR: /add/alerts returned ${add_code} — is APPRISE_STATELESS_URLS set on the container?" >&2
  exit 1
fi

code="$(probe)"
if [ "$code" = "200" ]; then
  echo "FIXED: apprise /notify/alerts → 200 (delivering; a probe message was sent to Telegram)"
  exit 0
fi
echo "ERROR: still ${code} after repair — investigate apprise config" >&2
exit 1
