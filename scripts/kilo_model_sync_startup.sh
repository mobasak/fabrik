#!/bin/bash
# Kilo Model Sync - WSL Startup Hook
# Runs model sync on WSL startup (via .bashrc or systemd)
#
# Installation:
#   1. Add to ~/.bashrc:
#      [ -f /opt/fabrik/scripts/kilo_model_sync_startup.sh ] && /opt/fabrik/scripts/kilo_model_sync_startup.sh
#
#   2. Or create systemd user service (see below)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRIK_DIR="/opt/fabrik"
LOG_DIR="$FABRIK_DIR/.droid"
LOG_FILE="$LOG_DIR/kilo_model_sync.log"
LOCK_FILE="/tmp/kilo_model_sync.lock"
LAST_RUN_FILE="$LOG_DIR/.kilo_sync_last_run"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    pid=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sync already running (PID: $pid), skipping" >> "$LOG_FILE"
        exit 0
    fi
fi
echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

# Check if already run today (avoid duplicate runs on multiple terminal opens)
TODAY=$(date +%Y-%m-%d)
if [ -f "$LAST_RUN_FILE" ]; then
    LAST_RUN=$(cat "$LAST_RUN_FILE" 2>/dev/null || echo "")
    if [ "$LAST_RUN" = "$TODAY" ]; then
        # Already ran today, skip
        exit 0
    fi
fi

# Run sync in background (don't block shell startup)
(
    echo "" >> "$LOG_FILE"
    echo "========================================" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WSL Startup Sync" >> "$LOG_FILE"
    echo "========================================" >> "$LOG_FILE"
    
    cd "$FABRIK_DIR"
    python3 scripts/kilo_model_sync.py --sync >> "$LOG_FILE" 2>&1
    
    # Mark as run today
    echo "$TODAY" > "$LAST_RUN_FILE"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sync complete" >> "$LOG_FILE"
) &

# Disown so it doesn't block shell
disown
