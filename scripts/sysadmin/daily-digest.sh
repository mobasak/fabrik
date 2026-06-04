#!/bin/bash
#
# daily-digest.sh — per-host AI-ops daily digest (trio plan §2.8).
#
# Fires at hash-slotted minute 09:XX UTC per host. Roll-up of:
#   - Tier A actions count in the last 24h (from sysadmin-actions.jsonl)
#   - Escalations count (Tier C)
#   - Reversals count (lessons-pending.jsonl entries from §5.1.a)
#   - Consults sent + received (via aro-wake's actions log)
#   - Health heartbeats: claude OAuth fresh? aro-wake up? mesh handshakes?
#                        pending queue depth?
#
# Operator gets one digest per host per day instead of per-action chatter.
#
# Routing: depends on operator decision (trio plan §7 Q1) — three @BotFather
# bots vs one shared. Until that lands, this script writes the digest to
# /opt/fabrik/logs/sysadmin-actions.jsonl with source=daily_digest so the
# data is at least captured; the Telegram-send step is TODO once the bot
# routing is wired into bot.py.
#
# Cron line (in /etc/cron.d/vps-sysadmin): {{DIGEST_MINUTE}} 9 * * * root /opt/fabrik/scripts/sysadmin/daily-digest.sh

set -uo pipefail

# Load host identity. .env.sysadmin is mode 600; we run as root via cron.
if [ -r /opt/fabrik/.env.sysadmin ]; then
    set -a
    # shellcheck disable=SC1091
    . /opt/fabrik/.env.sysadmin
    set +a
fi

HOST_NAME="${SYSADMIN_HOST_NAME:-$(hostname -s)}"
ACTIONS_LOG="/opt/fabrik/logs/sysadmin-actions.jsonl"
NOW_EPOCH=$(date +%s)
DAY_AGO=$((NOW_EPOCH - 86400))

# ── Roll-up from sysadmin-actions.jsonl over the last 24h ─────────────────

if [ -r "$ACTIONS_LOG" ]; then
    TIER_A_COUNT=$(python3 -c "
import json
import sys
n = 0
with open('$ACTIONS_LOG') as fh:
    for line in fh:
        try:
            r = json.loads(line)
            if r.get('ts', 0) >= $DAY_AGO and r.get('result_excerpt', '').lower().startswith('tier a'):
                n += 1
        except (json.JSONDecodeError, ValueError):
            pass
print(n)
" 2>/dev/null || echo "0")
    ESCALATIONS=$(python3 -c "
import json
n = 0
with open('$ACTIONS_LOG') as fh:
    for line in fh:
        try:
            r = json.loads(line)
            if r.get('ts', 0) >= $DAY_AGO and 'escalate' in r.get('result_excerpt', '').lower():
                n += 1
        except (json.JSONDecodeError, ValueError):
            pass
print(n)
" 2>/dev/null || echo "0")
    CONSULTS_RECV=$(python3 -c "
import json
n = 0
with open('$ACTIONS_LOG') as fh:
    for line in fh:
        try:
            r = json.loads(line)
            if r.get('ts', 0) >= $DAY_AGO and r.get('source') == 'consult':
                n += 1
        except (json.JSONDecodeError, ValueError):
            pass
print(n)
" 2>/dev/null || echo "0")
else
    TIER_A_COUNT=0
    ESCALATIONS=0
    CONSULTS_RECV=0
fi

# ── Health heartbeats ──────────────────────────────────────────────────────

KEEPALIVE_LOG=/var/log/claude-keepalive.log
if [ -e "$KEEPALIVE_LOG" ]; then
    KEEPALIVE_AGE_MIN=$(( (NOW_EPOCH - $(stat -c %Y "$KEEPALIVE_LOG")) / 60 ))
    KEEPALIVE_STATUS="fresh (mtime ${KEEPALIVE_AGE_MIN}m ago)"
else
    KEEPALIVE_STATUS="MISSING — keepalive cron may be dead"
fi

ARO_WAKE_STATUS="not enabled"
if systemctl is-active --quiet aro-wake.service 2>/dev/null; then
    if curl -sf --max-time 5 "http://${SYSADMIN_HOST_IP:-127.0.0.1}:8201/health" >/dev/null 2>&1; then
        ARO_WAKE_STATUS="up + healthy"
    else
        ARO_WAKE_STATUS="systemd active but /health not responding"
    fi
fi

MESH_STATUS="not configured"
if command -v wg >/dev/null && [ -e /etc/wireguard/wg0.conf ]; then
    MESH_STATUS=$(sudo wg show wg0 latest-handshakes 2>/dev/null \
        | awk -v now="$NOW_EPOCH" '
            { pubkey=substr($1,1,12); age = now - $2; printf "%s=%ds ", pubkey, age }
            END { if (NR==0) print "no peers" }' || echo "wg show failed")
fi

# ── Compose + emit digest ─────────────────────────────────────────────────

DIGEST=$(cat <<EOF
[${HOST_NAME}] Daily digest $(date -u +"%Y-%m-%d %H:%M UTC")
  Actions:        ${TIER_A_COUNT} Tier A
  Escalations:    ${ESCALATIONS}
  Consults recv:  ${CONSULTS_RECV}
  Health:         claude OAuth ${KEEPALIVE_STATUS}
                  aro-wake ${ARO_WAKE_STATUS}
                  mesh ${MESH_STATUS}
EOF
)

# Log to sysadmin-actions.jsonl (captured data even if Telegram routing
# isn't wired yet)
DIGEST_JSON=$(python3 -c "
import json
import sys
import time
print(json.dumps({
    'ts': time.time(),
    'host': '$HOST_NAME',
    'source': 'daily_digest',
    'tier_a_count': $TIER_A_COUNT,
    'escalations': $ESCALATIONS,
    'consults_received': $CONSULTS_RECV,
    'keepalive_status': '''$KEEPALIVE_STATUS''',
    'aro_wake_status': '''$ARO_WAKE_STATUS''',
    'mesh_status': '''$MESH_STATUS''',
}))
")
mkdir -p /opt/fabrik/logs
echo "$DIGEST_JSON" >> "$ACTIONS_LOG"

# Telegram send: route via Apprise (consistent with proactive-check.sh).
# This works today on vps1 where Apprise + apprise: hostname are wired.
# Spoke routing TBD per trio plan §7 Q1 — when 3-bots-vs-1 decision lands,
# bot.py's daily-digest sender replaces this curl.
if command -v docker >/dev/null && sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^apprise$'; then
    escaped=$(python3 -c "import json,sys; print(json.dumps(sys.stdin.read().strip()))" <<< "$DIGEST")
    sudo docker run --rm --network fabrik curlimages/curl:latest -sf -X POST \
        "http://apprise:8000/notify/alerts" \
        -H "Content-Type: application/json" \
        -d "{\"title\":\"[${HOST_NAME}] daily digest\",\"body\":${escaped}}" >/dev/null 2>&1 \
        && echo "$(date -Is) daily digest sent to Apprise" \
        || echo "$(date -Is) daily digest Apprise send FAILED"
fi

# Always print to stdout so the cron log shows it
echo "$DIGEST"
