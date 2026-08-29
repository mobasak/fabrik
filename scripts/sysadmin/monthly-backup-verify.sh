#!/bin/bash
# Monthly backup verification — runs 1st of each month at 04:00 via cron.
# Runs the backup audit script, Claude analyzes against the backup checklist,
# and reports backup coverage, freshness, and recovery readiness.
#
# This does NOT perform an actual restore (destructive) — it verifies:
# 1. Backrest is running and plans are scheduled
# 2. Last snapshot is fresh (within 24h)
# 3. All critical volumes are covered
# 4. Retention policies are set
# 5. B2 bucket is reachable
#
# Cron: 0 4 1 * * root /opt/fabrik/scripts/sysadmin/monthly-backup-verify.sh

set -uo pipefail

PROJECT_DIR="/opt/fabrik"
SYSTEM_PROMPT_FILE="$PROJECT_DIR/scripts/sysadmin/system-prompt.txt"

echo "$(date -Iseconds) Running monthly backup verification..."

# Run the backup audit script
AUDIT_OUTPUT=$(sudo bash "$PROJECT_DIR/scripts/audit/06-backup.sh" 2>&1)

# Load the backup checklist
CHECKLIST=""
CHECKLIST_FILE="$PROJECT_DIR/docs/infrastructure/audit-prompts/06-backup-disaster-recovery.md"
[ -f "$CHECKLIST_FILE" ] && CHECKLIST=$(cat "$CHECKLIST_FILE")

SYS_PROMPT=""
[ -f "$SYSTEM_PROMPT_FILE" ] && SYS_PROMPT=$(cat "$SYSTEM_PROMPT_FILE")

RESULT=$("$PROJECT_DIR/scripts/sysadmin/claude-run.sh" -p --model opus \
  "Monthly backup verification. Analyze the audit output against the backup checklist.

CHECKLIST:
$CHECKLIST

AUDIT OUTPUT:
$AUDIT_OUTPUT

Format a Telegram report:

💾 Monthly Backup Verification

Status: HEALTHY / AT RISK / CRITICAL
Backrest: running/stopped, last snapshot age
Coverage: X critical volumes backed up / Y total
Retention: policies set? (keepDaily/weekly/monthly)
Gaps: anything NOT backed up that should be (numbered)
Recovery confidence: HIGH / MEDIUM / LOW with 1-line reason

Be concise. Focus on gaps and risks, not on what's working." \
  --system-prompt "$SYS_PROMPT" \
  --permission-mode bypassPermissions \
  --no-session-persistence \
  2>/dev/null)

GOV_RC=$?  # exit status of the claude-run.sh call above (75 = governor quota-conservation shed)
if [ "$GOV_RC" -eq 75 ]; then exit 0; fi  # routine shed — skip this best-effort run silently, no false alarm
if [ -z "$RESULT" ]; then
  RESULT="⚠️ Monthly backup verification: Claude failed to analyze. Check logs."
fi

# printf '%s' (NOT echo) — echo mangles backslash sequences (\n, \t) and a leading -n/-e/-E
# in Claude's output, silently corrupting the alert body before python json-encodes it.
ESCAPED=$(printf '%s' "$RESULT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")

# Gate on delivery: `docker run -sf … >/dev/null 2>&1` discards its exit status, so a down/
# unreachable Apprise (or a wrong docker network) would silently drop the report while the log
# claimed "sent" — worst here, since a dropped backup-verification alert hides backup failure.
# Check the exit and surface a real failure (matches proactive-check's APPRISE_SEND).
if sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^apprise$' && \
   sudo docker run --rm --network fabrik curlimages/curl:latest -sf -X POST "http://apprise:8000/notify/alerts" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"💾 Monthly Backup Verify\",\"body\":${ESCAPED}}" \
  >/dev/null 2>&1; then
  echo "$(date -Iseconds) Monthly backup verification sent"
elif bash /opt/fabrik/scripts/sysadmin/send-telegram.sh "💾 Monthly Backup Verify
$RESULT" >/dev/null 2>&1; then
  # Apprise is HUB-ONLY — direct Telegram (send-telegram.sh) is the fleet-wide path.
  # A dropped backup-verification alert hides backup failure — both legs must fail before we do.
  echo "$(date -Iseconds) Monthly backup verification sent via direct Telegram fallback"
else
  echo "$(date -Iseconds) Monthly backup verification FAILED via BOTH Apprise and Telegram fallback" >&2
  exit 1
fi
