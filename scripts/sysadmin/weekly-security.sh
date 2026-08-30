#!/bin/bash
# Weekly security patrol — runs Monday 08:30 via cron.
# Runs the security audit script, Claude analyzes, sends findings to Telegram.
#
# Cron: 30 8 * * 1 root /opt/fabrik/scripts/sysadmin/weekly-security.sh

set -uo pipefail

PROJECT_DIR="/opt/fabrik"
# Operator overrides (CLAUDE_SYSADMIN_MODEL, …) live in .env.sysadmin — cron's env is minimal (audit f6).
if [ -r /opt/fabrik/.env.sysadmin ]; then
    # shellcheck disable=SC1091
    set -a; . /opt/fabrik/.env.sysadmin 2>/dev/null; set +a
fi
SYSTEM_PROMPT_FILE="$PROJECT_DIR/scripts/sysadmin/system-prompt.txt"

echo "$(date -Iseconds) Running weekly security patrol..."

# Run the security audit script
AUDIT_OUTPUT=$(sudo bash "$PROJECT_DIR/scripts/audit/03-security.sh" 2>&1)

# Load the security checklist so Claude knows what to check against
CHECKLIST=""
CHECKLIST_FILE="$PROJECT_DIR/docs/infrastructure/audit-prompts/03-security-hardening.md"
[ -f "$CHECKLIST_FILE" ] && CHECKLIST=$(cat "$CHECKLIST_FILE")

SYS_PROMPT=""
[ -f "$SYSTEM_PROMPT_FILE" ] && SYS_PROMPT=$(cat "$SYSTEM_PROMPT_FILE")

RESULT=$("$PROJECT_DIR/scripts/sysadmin/claude-run.sh" -p --model "${CLAUDE_SYSADMIN_MODEL:-opus}" \
  "Weekly security patrol. Analyze the audit output below against the security checklist.

CHECKLIST:
$CHECKLIST

AUDIT OUTPUT:
$AUDIT_OUTPUT

Format a Telegram report:

🔒 Weekly Security Patrol

Overall: GREEN/YELLOW/RED
Checklist: X/Y items passing
Issues: (anything failing, numbered by severity)
Changes since last check: (new ports, containers, rule changes, cert renewals)
Recommendations: (hardening improvements, if any)

Be concise. If everything is clean, say so in 3 lines. Only elaborate on actual findings." \
  --system-prompt "$SYS_PROMPT" \
  --permission-mode bypassPermissions \
  --no-session-persistence \
  2>/dev/null)

GOV_RC=$?  # exit status of the claude-run.sh call above (75 = governor quota-conservation shed)
if [ "$GOV_RC" -eq 75 ]; then exit 0; fi  # routine shed — skip this best-effort run silently, no false alarm
if [ -z "$RESULT" ]; then
  RESULT="⚠️ Weekly security patrol: Claude failed to analyze. Check logs."
fi

# printf '%s' (NOT echo) — echo mangles backslash sequences (\n, \t) and a leading -n/-e/-E
# in Claude's output, silently corrupting the alert body before python json-encodes it.
ESCAPED=$(printf '%s' "$RESULT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")

# Gate on delivery: `docker run -sf … >/dev/null 2>&1` discards its exit status, so a down/
# unreachable Apprise (or a wrong docker network) would silently drop the report while the log
# claimed "sent". Check the exit and surface a real failure (matches proactive-check's APPRISE_SEND).
if sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^apprise$' && \
   sudo docker run --rm --network fabrik curlimages/curl:latest -sf -X POST "http://apprise:8000/notify/alerts" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"🔒 Weekly Security\",\"body\":${ESCAPED}}" \
  >/dev/null 2>&1; then
  echo "$(date -Iseconds) Weekly security patrol sent"
elif bash /opt/fabrik/scripts/sysadmin/send-telegram.sh "🔒 Weekly Security
$RESULT" >/dev/null 2>&1; then
  # Apprise is HUB-ONLY — direct Telegram (send-telegram.sh) is the fleet-wide path.
  echo "$(date -Iseconds) Weekly security patrol sent via direct Telegram fallback"
else
  echo "$(date -Iseconds) Weekly security patrol FAILED via BOTH Apprise and Telegram fallback" >&2
  exit 1
fi
