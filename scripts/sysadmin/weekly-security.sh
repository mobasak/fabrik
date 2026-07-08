#!/bin/bash
# Weekly security patrol — runs Monday 08:30 via cron.
# Runs the security audit script, Claude analyzes, sends findings to Telegram.
#
# Cron: 30 8 * * 1 root /opt/fabrik/scripts/sysadmin/weekly-security.sh

set -uo pipefail

PROJECT_DIR="/opt/fabrik"
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

RESULT=$("$PROJECT_DIR/scripts/sysadmin/claude-run.sh" -p --model opus \
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

if [ -z "$RESULT" ]; then
  RESULT="⚠️ Weekly security patrol: Claude failed to analyze. Check logs."
fi

ESCAPED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")

sudo docker run --rm --network coolify curlimages/curl:latest -sf -X POST "http://apprise:8000/notify/alerts" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"🔒 Weekly Security\",\"body\":${ESCAPED}}" \
  >/dev/null 2>&1

echo "$(date -Iseconds) Weekly security patrol sent"
