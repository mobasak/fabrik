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

# ============================================================================
# Phase: fleet-hardening 2026-06-17 — missed-digest detector (G2 fix)
# Scans the JSONL for last 48h; if any `daily_digest` row has no matching
# `daily_digest_sent` row, prepend a ⚠️ MISSED DIGESTS warning. Plan §2.2.
# ============================================================================
MISSED_WARN=$(python3 <<PYEOF
import json, time
deadline = time.time() - 48*3600
sent_dates, attempted_dates = set(), set()
try:
    with open("$ACTIONS_LOG") as f:
        for line in f:
            try: r = json.loads(line)
            except Exception: continue
            if r.get("ts", 0) < deadline: continue
            d = time.strftime("%Y-%m-%d", time.gmtime(r["ts"]))
            if r.get("source") == "daily_digest": attempted_dates.add(d)
            elif r.get("source") == "daily_digest_sent": sent_dates.add(d)
except FileNotFoundError:
    pass
missed = attempted_dates - sent_dates
today = time.strftime("%Y-%m-%d", time.gmtime())
missed.discard(today)
if missed:
    print(f"⚠️ MISSED DIGESTS — {len(missed)} day(s) generated but no Telegram delivery: {sorted(missed)}")
PYEOF
)

# ============================================================================
# Phase: fleet-hardening 2026-06-17 — bullet extractor (G3 fix)
# Pulls last-24h `result_excerpt` from alertmanager/consult/manual rows,
# truncates to 180 chars/row, max 5 rows. Plan §2.3.
# ============================================================================
ACTION_BULLETS=$(python3 <<PYEOF
import json, time
deadline = time.time() - 24*3600
bullets = []
try:
    with open("$ACTIONS_LOG") as f:
        for line in f:
            try: r = json.loads(line)
            except Exception: continue
            if r.get("ts", 0) < deadline: continue
            src = r.get("source")
            if src not in ("alertmanager", "consult", "manual"): continue
            ex = (r.get("result_excerpt") or "")[:180]
            if not ex: continue
            ts_str = time.strftime("%H:%M:%SZ", time.gmtime(r["ts"]))
            bullets.append(f"  • [{ts_str}] {ex}")
            if len(bullets) >= 5: break
except FileNotFoundError:
    pass
for b in bullets:
    print(b)
PYEOF
)

DIGEST=$(cat <<EOF
${MISSED_WARN:+${MISSED_WARN}
}[${HOST_NAME}] Daily digest $(date -u +"%Y-%m-%d %H:%M UTC")
  Actions:        ${TIER_A_COUNT} Tier A
  Escalations:    ${ESCALATIONS}
  Consults recv:  ${CONSULTS_RECV}
  Health:         claude OAuth ${KEEPALIVE_STATUS}
                  aro-wake ${ARO_WAKE_STATUS}
                  mesh ${MESH_STATUS}${ACTION_BULLETS:+

Actions in last 24h:
${ACTION_BULLETS}}
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

# ============================================================================
# Phase: fleet-hardening 2026-06-17 — hub vs spoke routing (G1 fix)
# Spokes (vps2, vps3): POST digest to hub aro-wake at http://10.0.0.1:8201
# with 5s timeout + 2 retries + 1s/2s backoff. On hub-unreachable: fall
# back to direct Telegram via per-host bot token. Plan §2.1.
# Hub (vps1): drain /digest-inbox from local aro-wake, combine with own
# digest body, then send the combined message via Apprise (preferred) or
# send-telegram.sh (fallback). Plan §2.1.
# ============================================================================
TELEGRAM_OK=0  # set to 1 when delivery succeeds; gates the _sent row write

if [ "$HOST_NAME" != "vps1" ]; then
    # ---------- SPOKE PATH ----------
    forwarded=0
    forward_body=$(jq -cn --arg t "$DIGEST" --argjson m "$DIGEST_JSON" \
                  '{text: $t, metrics: $m}')
    for attempt in 1 2 3; do
        if curl -sf --max-time 5 -X POST \
             "http://10.0.0.1:8201/digest-input" \
             -H "Content-Type: application/json" \
             -d "$forward_body" >/dev/null 2>&1; then
            echo "$(date -Is) spoke digest forwarded to hub (attempt $attempt)"
            forwarded=1
            TELEGRAM_OK=1
            break
        fi
        [ "$attempt" -lt 3 ] && sleep "$attempt"
    done
    if [ "$forwarded" = "0" ]; then
        # Hub unreachable — try direct Telegram via per-host bot token
        if bash /opt/fabrik/scripts/sysadmin/send-telegram.sh "$DIGEST" 2>/dev/null; then
            echo "$(date -Is) spoke digest sent via direct Telegram fallback"
            TELEGRAM_OK=1
        else
            echo "$(date -Is) spoke digest BOTH forward + direct fallback FAILED" >&2
        fi
    fi
else
    # ---------- HUB PATH (vps1) ----------
    # Drain spoke inbox; combine with own digest; send ONE combined message.
    INBOX_JSON=$(curl -sf --max-time 5 "http://localhost:8201/digest-inbox?since=$(date -d '6 hours ago' +%s 2>/dev/null || echo 0)" 2>/dev/null || echo '[]')
    COMBINED=$(python3 <<PYEOF
import json
own = """${DIGEST}"""
try:
    inbox = json.loads("""${INBOX_JSON}""") if """${INBOX_JSON}""".strip() else []
except Exception:
    inbox = []
sections = [own]
for spoke in sorted(inbox, key=lambda x: x.get("source_host", "")):
    sections.append("\n---\n" + (spoke.get("text") or ""))
combined = "\n".join(sections)
if len(combined) > 3500:
    combined = combined[:3500] + "\n…(truncated)"
print(combined)
PYEOF
)
    # Prefer Apprise (matches proactive-check.sh path); fall back to send-telegram.sh
    if command -v docker >/dev/null && sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^apprise$'; then
        escaped=$(python3 -c "import json,sys; print(json.dumps(sys.stdin.read().strip()))" <<< "$COMBINED")
        if sudo docker run --rm --network fabrik curlimages/curl:latest -sf -X POST \
            "http://apprise:8000/notify/alerts" \
            -H "Content-Type: application/json" \
            -d "{\"title\":\"[fleet] daily digest\",\"body\":${escaped}}" >/dev/null 2>&1; then
            echo "$(date -Is) hub combined digest sent via Apprise"
            TELEGRAM_OK=1
        fi
    fi
    if [ "$TELEGRAM_OK" = "0" ]; then
        if bash /opt/fabrik/scripts/sysadmin/send-telegram.sh "$COMBINED" 2>/dev/null; then
            echo "$(date -Is) hub combined digest sent via direct Telegram fallback"
            TELEGRAM_OK=1
        else
            echo "$(date -Is) hub combined digest BOTH Apprise + direct fallback FAILED" >&2
        fi
    fi
fi

# ============================================================================
# Phase: fleet-hardening 2026-06-17 — _sent JSONL row (G2 marker)
# Only written when delivery succeeded — drives the missed-detector that
# runs at start of every digest. Plan §2.2.
# ============================================================================
if [ "$TELEGRAM_OK" = "1" ]; then
    DIGEST_SENT_JSON=$(python3 -c "
import json, time
print(json.dumps({
    'ts': time.time(),
    'host': '$HOST_NAME',
    'source': 'daily_digest_sent',
    'date': time.strftime('%Y-%m-%d', time.gmtime()),
}))
")
    echo "$DIGEST_SENT_JSON" >> "$ACTIONS_LOG"
fi

# Always print to stdout so the cron log shows it
echo "$DIGEST"
