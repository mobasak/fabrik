#!/bin/bash
# WSL Startup Hook - Daily Fabrik Maintenance
# Source this in ~/.bashrc to run daily updates on WSL startup
#
# Add to ~/.bashrc:
#   source /opt/fabrik/scripts/wsl_startup_hook.sh
#
# Pipeline:
# 1. Env watcher: monitors /opt/*/.env changes → auto-consolidates into /opt/fabrik/.env (persistent)
# 2. Project registry sync: project.yaml → data/projects.yaml + BUSINESS_MODEL.md + PORTS.md (daily)
# 3. Cascade backup freshness check (daily)
# 4. Health summary (daily)
# 5. Kilo agent workflow (daily, deterministic — no LLM):
#      a. kilo_agents_db.py all              — sync model catalog from Kilo CLI + Ollama
#      b. update_kilo_benchmarks.py --force  — scrape Arena ELO + Terminal-Bench
#      c. scrape_artificial_analysis.py      — scrape throughput (tokens/sec) + TTFT
#      d. role_mapper.py                     — pre_filter → selector → post_filter → DB
#      e. export_traycer_registry.py         — refresh scripts/kilo_47_agents_final.json from DB
#      f. generate_kilo_agents.py            — emit Traycer CLI agent scripts
# 6. Extensions sync: auto-update Windsurf extensions documentation (daily)
#
# Full reference: docs/workflows/DATA_SYNC_WORKFLOW.md

FABRIK_ROOT="/opt/fabrik"
VENV_PYTHON="$FABRIK_ROOT/.venv/bin/python"
DB_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/kilo_agents_db.py"
BENCHMARK_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/update_kilo_benchmarks.py"
AA_SCRAPER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/scrape_artificial_analysis.py"
ROLE_MAPPER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/role_mapper.py"
TRAYCER_EXPORT_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/export_traycer_registry.py"
AGENT_SCRIPT="$FABRIK_ROOT/scripts/generate_kilo_agents.py"
EXTENSIONS_SCRIPT="$FABRIK_ROOT/scripts/sync_extensions.sh"
ENV_WATCHER_SCRIPT="$FABRIK_ROOT/scripts/watch_env_changes.sh"
ENV_WATCHER_LOG="$FABRIK_ROOT/.tmp/env_watcher.log"
SYNC_PROJECTS_SCRIPT="$FABRIK_ROOT/scripts/sync_projects.py"
CASCADE_BACKUP_SCRIPT="$FABRIK_ROOT/scripts/sync_cascade_backup.sh"
HEALTH_SUMMARY_SCRIPT="$FABRIK_ROOT/scripts/health_summary.py"
LOG_FILE="$FABRIK_ROOT/scripts/kilo-benchmarks/cache/update.log"
LOCK_FILE="/tmp/.fabrik_daily_$(date +%Y%m%d)"

# --- Log rotation (keep logs under 500KB, 1 backup) ---
MAX_LOG_SIZE=512000  # 500KB
for logfile in "$LOG_FILE" "$ENV_WATCHER_LOG"; do
    if [ -f "$logfile" ] && [ "$(stat -c%s "$logfile" 2>/dev/null || echo 0)" -gt "$MAX_LOG_SIZE" ]; then
        mv "$logfile" "${logfile}.1"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Log rotated" > "$logfile"
    fi
done

# --- Persistent process: env watcher (runs continuously, not daily) ---
# Start only if not already running
if ! pgrep -f "watch_env_changes.sh" > /dev/null 2>&1; then
    mkdir -p "$FABRIK_ROOT/.tmp"
    nohup bash "$ENV_WATCHER_SCRIPT" >> "$ENV_WATCHER_LOG" 2>&1 &
fi

# --- Daily pipeline (runs once per WSL boot day) ---
# Run update if not already run today
if [ ! -f "$LOCK_FILE" ]; then
    touch "$LOCK_FILE"
    mkdir -p "$(dirname "$LOG_FILE")"
    # Run full pipeline in background (chained to ensure order)
    # Project sync → Cascade backup check → Health summary → Kilo agents → Extensions
    nohup bash -c "
        echo '' >> $LOG_FILE
        echo '=== Fabrik Daily Pipeline — '$(date '+%Y-%m-%d %H:%M:%S')' ===' >> $LOG_FILE
        cd $FABRIK_ROOT && $VENV_PYTHON $SYNC_PROJECTS_SCRIPT >> $LOG_FILE 2>&1 && \
        cd $FABRIK_ROOT && bash $CASCADE_BACKUP_SCRIPT >> $LOG_FILE 2>&1 ; \
        cd $FABRIK_ROOT && $VENV_PYTHON $HEALTH_SUMMARY_SCRIPT >> $LOG_FILE 2>&1 ;
        # === KILO AGENT BENCHMARK WORKFLOW ===
        # Deterministic role assignment (pre_filter → selector → post_filter)
        # Runs in ~50ms, $0 cost, byte-identical re-runs
        # Re-enabled 2026-05-13 after switching from LLM to deterministic algorithm
        if [ \"\${FABRIK_DISABLE_KILO_WORKFLOW:-0}\" = \"1\" ]; then
            echo \"[\$(date +%H:%M:%S)] kilo benchmark workflow skipped (FABRIK_DISABLE_KILO_WORKFLOW=1)\" >> $LOG_FILE
        else
            $VENV_PYTHON $DB_SCRIPT all >> $LOG_FILE 2>&1 && \
            $VENV_PYTHON $BENCHMARK_SCRIPT --force >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $AA_SCRAPER_SCRIPT >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $ROLE_MAPPER_SCRIPT >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT/scripts/kilo-benchmarks && $VENV_PYTHON $TRAYCER_EXPORT_SCRIPT >> $LOG_FILE 2>&1 && \
            cd $FABRIK_ROOT && $VENV_PYTHON $AGENT_SCRIPT >> $LOG_FILE 2>&1
        fi
        cd $FABRIK_ROOT && bash $EXTENSIONS_SCRIPT >> $LOG_FILE 2>&1
        echo '=== Pipeline complete — '$(date '+%Y-%m-%d %H:%M:%S')' ===' >> $LOG_FILE
    " &
fi
