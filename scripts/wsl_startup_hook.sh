#!/bin/bash
# WSL Startup Hook - Daily Fabrik Maintenance
# Source this in ~/.bashrc to run daily updates on WSL startup
#
# Add to ~/.bashrc:
#   source /opt/fabrik/scripts/wsl_startup_hook.sh
#
# Pipeline:
# Kilo agent workflow: sync models → scrape benchmarks → AI role assignment → generate CLI scripts

FABRIK_ROOT="/opt/fabrik"
VENV_PYTHON="$FABRIK_ROOT/.venv/bin/python"
DB_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/kilo_agents_db.py"
BENCHMARK_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/update_kilo_benchmarks.py"
ROLE_MAPPER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/role_mapper.py"
AGENT_SCRIPT="$FABRIK_ROOT/scripts/generate_kilo_agents.py"
LOG_FILE="$FABRIK_ROOT/scripts/kilo-benchmarks/cache/update.log"
LOCK_FILE="/tmp/.fabrik_daily_$(date +%Y%m%d)"

# Run update if not already run today
if [ ! -f "$LOCK_FILE" ]; then
    touch "$LOCK_FILE"
    mkdir -p "$(dirname "$LOG_FILE")"
    # Run full pipeline in background (chained to ensure order)
    # Sync models → Scrape benchmarks → AI role assignment → Generate CLI scripts
    nohup bash -c "
        $VENV_PYTHON $DB_SCRIPT all >> $LOG_FILE 2>&1 && \
        $VENV_PYTHON $BENCHMARK_SCRIPT --force >> $LOG_FILE 2>&1 && \
        cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $ROLE_MAPPER_SCRIPT >> $LOG_FILE 2>&1 && \
        cd $FABRIK_ROOT && $VENV_PYTHON $AGENT_SCRIPT >> $LOG_FILE 2>&1
    " &
fi
