#!/usr/bin/env bash
# fabrik-alert-canary.sh — prove the alerting path can still page you; self-heal + escalate OUT-OF-BAND if not.
#
# WHY THIS EXISTS
# On 2026-07-08 two things died at once on vps1: (1) `alertmanager` (a Docker reboot race), and (2) the
# Gatus → Apprise → Telegram path, which was silently answering every alert with `204 No Content` (Apprise
# had no stateful "alerts" config). Gatus dutifully logged 5,893 failed checks. The operator got NOTHING for
# four days. Nobody was watching the WATCHER: a monitoring stack that cannot page you looks exactly like
# "all quiet". This canary is that missing check.
#
# THE KEY IDEA: if the alert path is dead, it cannot report its own death. So on breakage this escalates via
# a DIRECT Telegram API call (api.telegram.org) that bypasses Apprise entirely.
#
# MODES
#   (default)  CHEAP + SILENT config probe — `POST /get/alerts`: 200 = the stateful "alerts" config exists,
#              204 = MISSING (the exact broken state). Sends NO Telegram message ⇒ safe to run hourly.
#   --e2e      TRUE end-to-end — `POST /notify/alerts`: 200 = Apprise actually DELIVERED to Telegram
#              (204 = silently dropped, 424 = send failed). Sends ONE message ⇒ run weekly as a heartbeat.
#
# On breakage: repairs the "alerts" config from Apprise's own APPRISE_STATELESS_URLS, re-verifies, then
# escalates out-of-band regardless of whether the repair worked.
#
# Usage:  sudo bash fabrik-alert-canary.sh [--e2e]
# Exit:   0 = alert path healthy · 1 = was broken (repair + out-of-band escalation attempted)
#
# AFTER-EDIT: docs/TROUBLESHOOTING.md, scripts/sysadmin/ensure-apprise-alerts-config.sh
set -uo pipefail

E2E=0
[ "${1:-}" = "--e2e" ] && E2E=1
TS="$(date -u '+%Y-%m-%d %H:%M:%SZ')"
log() { echo "[alert-canary $TS] $*"; }

ac() { docker exec apprise "$@" 2>/dev/null; }   # run inside the apprise container

# --- out-of-band escalation: DIRECT Telegram API, bypassing Apprise entirely ---------------------------
escalate() {
  local msg="$1" raw creds token chat code
  raw="$(ac printenv APPRISE_STATELESS_URLS)"           # tgram://<bot_token>/<chat_id>
  creds="${raw#tgram://}"; token="${creds%%/*}"; chat="${creds#*/}"; chat="${chat%%/*}"
  if [ -z "$token" ] || [ -z "$chat" ]; then
    log "CRITICAL: cannot escalate — no usable tgram creds in APPRISE_STATELESS_URLS"; return 1
  fi
  code="$(curl -s -o /dev/null -w '%{http_code}' -X POST \
      "https://api.telegram.org/bot${token}/sendMessage" \
      --data-urlencode "chat_id=${chat}" \
      --data-urlencode "text=🚨 FABRIK ALERT-PATH CANARY

${msg}

(sent DIRECT to Telegram, bypassing Apprise — the normal alert path was not working.)")"
  [ "$code" = "200" ] && log "out-of-band Telegram escalation: delivered" \
                      || log "CRITICAL: out-of-band escalation FAILED (HTTP $code) — you are flying blind"
}

# --- probes ---------------------------------------------------------------------------------------------
probe_config() {  # silent: does the stateful "alerts" config exist? (no notification sent)
  ac curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:8000/get/alerts
}
probe_e2e() {     # true end-to-end: 200 means Apprise actually delivered to Telegram
  ac curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' \
    -d '{"title":"[fabrik] alert-path canary","body":"Weekly heartbeat: the Gatus/sysadmin → Apprise → Telegram alert path is alive. If this ever stops arriving, the notifier is dead."}' \
    http://localhost:8000/notify/alerts
}

# --- main -----------------------------------------------------------------------------------------------
if ! docker ps --format '{{.Names}}' | grep -qx apprise; then
  log "BROKEN: apprise container is not running"
  escalate "Apprise is DOWN — no alert can be delivered through the normal path."
  exit 1
fi

code="$(probe_config)"
if [ "$code" != "200" ]; then
  log "BROKEN: /get/alerts → $code (204 = the 'alerts' config is MISSING — every alert would be silently dropped)"
  log "repairing from APPRISE_STATELESS_URLS…"
  ac sh -c 'curl -s -o /dev/null -X POST -d "urls=$APPRISE_STATELESS_URLS" http://localhost:8000/add/alerts'
  after="$(probe_config)"
  if [ "$after" = "200" ]; then
    escalate "The alert path was BROKEN (Apprise had no 'alerts' config → every alert was being silently discarded with HTTP 204).

It has been AUTO-REPAIRED and is delivering again. Alerts sent while it was broken are LOST — check Gatus/Prometheus for anything you missed."
    log "REPAIRED: /get/alerts → 200"
  else
    escalate "The alert path is BROKEN (Apprise /get/alerts → ${after}) and AUTO-REPAIR FAILED.

You are currently receiving NO alerts through Gatus or the sysadmin scripts. Manual fix:
  sudo bash scripts/sysadmin/ensure-apprise-alerts-config.sh"
    log "CRITICAL: repair failed (/get/alerts → $after)"
  fi
  exit 1
fi

if [ "$E2E" = 1 ]; then
  code="$(probe_e2e)"
  if [ "$code" != "200" ]; then
    log "BROKEN: /notify/alerts → $code (config exists but delivery failed: 204=dropped, 424=send error)"
    escalate "The alert path has a config but is NOT DELIVERING (/notify/alerts → HTTP ${code}).
424 = Apprise could not reach Telegram · 204 = silently dropped. Investigate Apprise + the Telegram bot token."
    exit 1
  fi
  log "OK: end-to-end delivery verified (/notify/alerts → 200, heartbeat sent to Telegram)"
  exit 0
fi

log "OK: alert path healthy (/get/alerts → 200; no message sent)"
exit 0
