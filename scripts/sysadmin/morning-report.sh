#!/bin/bash
# Daily morning report — runs at 08:00 via cron.
# Collects compact system state + trends, Claude formats a Telegram briefing.
#
# Cron: 0 8 * * * root /opt/fabrik/scripts/sysadmin/morning-report.sh

set -uo pipefail

PROJECT_DIR="/opt/fabrik"
# Operator overrides (CLAUDE_MORNING_MODEL, …) live in .env.sysadmin — cron's env is minimal,
# so without this source the documented override is inoperative (audit finding 6).
if [ -r /opt/fabrik/.env.sysadmin ]; then
    # shellcheck disable=SC1091
    set -a; . /opt/fabrik/.env.sysadmin 2>/dev/null; set +a
fi
SYSTEM_PROMPT_FILE="$PROJECT_DIR/scripts/sysadmin/system-prompt.txt"
SHIFT_NOTES="$PROJECT_DIR/logs/sysadmin-shift-notes.md"
ACTION_LOG="$PROJECT_DIR/logs/sysadmin-actions.jsonl"
CONTEXT_FILE="/tmp/morning-report-context.txt"

# ── Collect state into a file ─────────────────────────────────────────────

{
  echo "=== MORNING REPORT DATA ==="
  echo ""
  echo "--- Containers ---"
  sudo docker ps --format '{{.Names}} {{.Status}}' | sort
  echo "Total: $(sudo docker ps -q | wc -l) running"

  echo ""
  echo "--- Host ---"
  free -h | head -2
  echo "Swap: $(swapon --show --noheadings 2>/dev/null | awk '{print $4}' || echo "none")"
  echo "Disk: $(df -h / | tail -1 | awk '{print $5, "used", $4, "free"}')"
  echo "Load: $(cat /proc/loadavg | awk '{print $1, $2, $3}')"
  echo "Uptime: $(uptime -p)"

  echo ""
  echo "--- Unhealthy/Restarting ---"
  sudo docker ps --format '{{.Names}} {{.Status}}' | grep -iE 'unhealthy|restarting|Exited' || echo 'none'

  echo ""
  echo "--- Firing alerts ---"
  sudo docker exec prometheus wget -qO- 'http://localhost:9090/api/v1/alerts' 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    alerts=[a for a in d['data']['alerts'] if a['state']=='firing']
    if alerts:
        for a in alerts: print(f'  FIRING: {a[\"labels\"].get(\"alertname\",\"?\")}')
    else: print('  none')
except: print('  cannot query')
" 2>/dev/null || echo '  cannot query'

  echo ""
  echo "--- TLS cert expiry ---"
  # coolify.vps1 removed 2026-08-30 (audit): the subdomain was decommissioned 2026-05-31 —
  # proactive-check dropped it 2026-06-01; this loop had kept silently probing a dead name.
  for domain in ocoron.com status.vps1.ocoron.com monitor.vps1.ocoron.com errors.vps1.ocoron.com; do
    expiry=$(echo | timeout 5 openssl s_client -servername "$domain" -connect "$domain":443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
    if [ -n "$expiry" ]; then
      expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null)
      now_epoch=$(date +%s)
      days_left=$(( (expiry_epoch - now_epoch) / 86400 ))
      echo "  $domain: ${days_left}d remaining"
    else
      # loud, not silent: an unprobeable domain hid the dead coolify.vps1 for 3 months (audit f8)
      echo "  $domain: PROBE FAILED (no cert / unreachable)"
    fi
  done

  echo ""
  echo "--- Dangling resources ---"
  echo "Volumes: $(sudo docker volume ls -f dangling=true --format '{{.Name}}' | wc -l)"
  echo "Images: $(sudo docker images -f dangling=true --format '{{.ID}}' | wc -l)"

  echo ""
  echo "--- Disk consumers ---"
  echo "Docker: $(sudo du -sh /var/lib/docker/ 2>/dev/null | cut -f1)"
  echo "Logs: $(sudo du -sh /var/log/ 2>/dev/null | cut -f1)"
  echo "Journal: $(sudo journalctl --disk-usage 2>/dev/null | grep -oP '\d+\.\d+[MGK]' || echo 'unknown')"

  echo ""
  echo "--- Yesterday's actions ---"
  if [ -f "$ACTION_LOG" ]; then
    # BOTH writer formats: bot.py writes ISO strings, aro-wake/daily-digest write float epochs —
    # the old date-string grep silently excluded every autonomous action (audit finding 12).
    python3 - "$ACTION_LOG" <<'PYEOF2' || echo 'none'
import json, sys, time
from datetime import datetime
def ep(v):
    if isinstance(v,(int,float)) and not isinstance(v,bool): return float(v)
    if isinstance(v,str):
        try: return datetime.fromisoformat(v).timestamp()
        except ValueError: return None
    return None
day_ago = time.time() - 86400
rows = []
for line in open(sys.argv[1]):
    try: e = json.loads(line)
    except ValueError: continue
    t = ep(e.get("ts"))
    if t is not None and t >= day_ago:
        rows.append(line.rstrip())
print("\n".join(rows[-10:]) if rows else "none")
PYEOF2
  else
    echo 'no action log yet'
  fi

  echo ""
  echo "--- Shift notes ---"
  if [ -f "$SHIFT_NOTES" ]; then
    tail -20 "$SHIFT_NOTES" 2>/dev/null
  else
    echo 'no shift notes'
  fi
} > "$CONTEXT_FILE" 2>&1

# ── Ask Claude to format the morning briefing ─────────────────────────────

SYS_PROMPT=""
[ -f "$SYSTEM_PROMPT_FILE" ] && SYS_PROMPT=$(cat "$SYSTEM_PROMPT_FILE")

# Model: the morning report is a FORMATTING task (summarize a pre-collected context file into
# 20 phone lines) — not diagnosis. Sonnet does it indistinguishably for a fraction of the Opus
# quota; on the single-key ob@ this is the cheapest daily saving (audit 2026-08-30). Override
# with CLAUDE_MORNING_MODEL=opus to restore the old behavior.
RESULT=$("$PROJECT_DIR/scripts/sysadmin/claude-run.sh" -p --model "${CLAUDE_MORNING_MODEL:-sonnet}" \
  "Generate a concise daily morning report for Telegram. Format:

💚 or ⚠️ or 🔥 — one-line overall status

Key numbers: containers, disk, RAM, load (one line)
Cert status: days to earliest expiry (one line)
Issues: anything that needs attention (numbered, or 'none')
Trends: anything trending in a concerning direction
Yesterday: actions taken or 'quiet day'
Shift notes: anything to carry forward

Keep it under 20 lines. Phone screen friendly. If everything is fine, say so briefly." \
  --system-prompt "$SYS_PROMPT" \
  --no-session-persistence \
  < "$CONTEXT_FILE" 2>/dev/null)
  # bypassPermissions dropped (audit finding 7): this is a FORMATTING job over a pre-collected
  # context file — it needs no tools, so it gets no autonomous authority. Headless -p denies
  # tool calls by default; the report text is unaffected.

GOV_RC=$?  # exit status of the claude-run.sh call above (75 = governor quota-conservation shed)
if [ "$GOV_RC" -eq 75 ]; then
  # Governor shed (quota >= reserve). The daily heartbeat must NEVER silently vanish (operator
  # rule 2026-08-30: "taken care of" > "menu of options") — the data is ALREADY collected, only
  # the Claude prose is skipped. Send the raw summary at zero quota cost.
  RESULT="⛔ quota-conserved (governor shed the Claude formatting) — raw report:
$(head -c 3000 "$CONTEXT_FILE")"
fi
if [ -z "$RESULT" ]; then
  RESULT="⚠️ Morning report: Claude failed to generate. Check /var/log/sysadmin-proactive.log"
fi

# printf '%s' (NOT echo) — echo mangles backslash sequences (\n, \t) and a leading -n/-e/-E
# in Claude's output, silently corrupting the alert body before python json-encodes it.
ESCAPED=$(printf '%s' "$RESULT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")

rm -f "$CONTEXT_FILE"

# Gate on delivery: `docker run -sf … >/dev/null 2>&1` discards its exit status, so a down/
# unreachable Apprise (or a wrong docker network) would silently drop the report while the log
# claimed "sent". Check the exit and surface a real failure (matches proactive-check's APPRISE_SEND).
if sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^apprise$' && \
   sudo docker run --rm --network fabrik curlimages/curl:latest -sf -X POST "http://apprise:8000/notify/alerts" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"☀️ Morning Report\",\"body\":${ESCAPED}}" \
  >/dev/null 2>&1; then
  echo "$(date -Iseconds) Morning report sent"
elif bash /opt/fabrik/scripts/sysadmin/send-telegram.sh "☀️ Morning Report
$RESULT" >/dev/null 2>&1; then
  # Apprise is HUB-ONLY — on spokes the docker path always fails; direct Telegram
  # (send-telegram.sh, the daily-digest pattern) is the fleet-wide delivery path.
  echo "$(date -Iseconds) Morning report sent via direct Telegram fallback"
else
  echo "$(date -Iseconds) Morning report FAILED via BOTH Apprise and Telegram fallback" >&2
  exit 1
fi
