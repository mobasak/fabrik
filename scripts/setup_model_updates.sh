#!/bin/bash
# Setup automated model updates via cron
# Runs daily at 9 AM to check Factory docs for model changes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/.tmp"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Cron entry
CRON_CMD="0 9 * * * cd $PROJECT_ROOT && python3 scripts/droid_model_updater.py >> $LOG_DIR/model-updates.log 2>&1"

# Check if already installed
if crontab -l 2>/dev/null | grep -q "droid_model_updater.py"; then
    echo "✓ Model auto-updater already in crontab"
    echo "  Current schedule:"
    crontab -l | grep droid_model_updater.py
else
    # Add to crontab
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    echo "✓ Added model auto-updater to crontab"
    echo "  Schedule: Daily at 9 AM"
    echo "  Log file: $LOG_DIR/model-updates.log"
fi

echo ""
echo "To remove: crontab -e and delete the droid_model_updater.py line"
echo "To run manually: python3 scripts/droid_model_updater.py"
