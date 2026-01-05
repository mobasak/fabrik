#!/bin/bash
# Fabrik Command Logger Hook - PreToolUse
#
# Logs all bash commands executed by droid for audit trail.
# Useful for debugging and compliance.

input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name // ""')
command=$(echo "$input" | jq -r '.tool_input.command // ""')
session_id=$(echo "$input" | jq -r '.session_id // ""')

# Only log Bash commands
if [ "$tool_name" != "Bash" ]; then
  exit 0
fi

# Log to file
LOG_DIR="${HOME}/.factory/logs"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/droid-commands-$(date +%Y-%m-%d).log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] session=$session_id command=\"$command\"" >> "$LOG_FILE"

exit 0
