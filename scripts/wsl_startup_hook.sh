#!/bin/bash
# WSL Startup Hook for Kilo Agents Database Updates
# Source this in ~/.bashrc to run daily updates on WSL startup
#
# Add to ~/.bashrc:
#   source /opt/fabrik/scripts/wsl_startup_hook.sh
#
# Pipeline: sync → update → snapshot → export → generate CLI agents

FABRIK_ROOT="/opt/fabrik"
VENV_PYTHON="$FABRIK_ROOT/.venv/bin/python"
DB_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/kilo_agents_db.py"
AGENT_SCRIPT="$FABRIK_ROOT/scripts/generate_kilo_agents.py"
LOG_FILE="$FABRIK_ROOT/scripts/kilo-benchmarks/cache/update.log"
LOCK_FILE="/tmp/.fabrik_daily_$(date +%Y%m%d)"

# Run update if not already run today
if [ ! -f "$LOCK_FILE" ]; then
    touch "$LOCK_FILE"
    mkdir -p "$(dirname "$LOG_FILE")"
    # Run full pipeline in background (chained to ensure order)
    # 1. sync → 2. update → 3. snapshot → 4. export → 5. generate CLI agents
    nohup bash -c "
        $VENV_PYTHON $DB_SCRIPT sync >> $LOG_FILE 2>&1 && \
        $VENV_PYTHON $DB_SCRIPT update >> $LOG_FILE 2>&1 && \
        $VENV_PYTHON $DB_SCRIPT snapshot >> $LOG_FILE 2>&1 && \
        $VENV_PYTHON $DB_SCRIPT export >> $LOG_FILE 2>&1 && \
        $VENV_PYTHON $AGENT_SCRIPT >> $LOG_FILE 2>&1
    " &
fi
