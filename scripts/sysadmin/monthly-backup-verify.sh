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

RESULT=$(claude -p --model opus \
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

if [ -z "$RESULT" ]; then
  RESULT="⚠️ Monthly backup verification: Claude failed to analyze. Check logs."
fi

ESCAPED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")

sudo docker run --rm --network coolify curlimages/curl:latest -sf -X POST "http://apprise:8000/notify/alerts" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"💾 Monthly Backup Verify\",\"body\":${ESCAPED}}" \
  >/dev/null 2>&1

echo "$(date -Iseconds) Monthly backup verification sent"
