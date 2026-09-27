#!/bin/bash
# RETIRED 2026-09-25 (D-415). Still run by the operator's ~/.bashrc hook: do not move it before that hook and the cron line go (D-432).
# The Kilo model sync; the Kilo CLI it fed retired 2026-07-19. Do not use or install it. Find the hook with
# `grep -n kilo_model_sync_startup ~/.bashrc`; it calls this script on every shell start. The last-run file below is written
# only after the background sync finishes, so a shell opened while a sync is running starts another one (most days in the
# log show 1-3 runs; some show up to 17). No repo code calls it.
# It runs scripts/kilo_model_sync.py, which the operator's crontab (59 11 * * *) also runs directly.
# The hook as it was installed (shown so it can be found and removed, not copied):
#   [ -f /opt/fabrik/scripts/kilo_model_sync_startup.sh ] && /opt/fabrik/scripts/kilo_model_sync_startup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRIK_DIR="${FABRIK_ROOT:-/opt/fabrik}"
LOG_DIR="$FABRIK_DIR/.droid"
LOG_FILE="$LOG_DIR/kilo_model_sync.log"
LOCK_FILE="$FABRIK_DIR/.tmp/kilo_model_sync.lock"
LAST_RUN_FILE="$LOG_DIR/.kilo_sync_last_run"

# Ensure directories exist
mkdir -p "$LOG_DIR"
mkdir -p "$FABRIK_DIR/.tmp"

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
