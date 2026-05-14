#!/bin/bash
# run_kilo_workflow.sh — Manual trigger for the Kilo agent benchmark workflow.
#
# This is the same workflow that used to run inside the WSL daily startup
# pipeline (steps 5a-5d) but was disabled 2026-05-09 due to role_mapper.py
# hangs. Run this manually when you want fresh kilo benchmarks + role
# assignments + per-agent CLI scripts.
#
# Steps:
#   1. kilo_agents_db.py all              — rebuild agent database
#   2. update_kilo_benchmarks.py --force  — scrape external benchmark sites
#   3. role_mapper.py                     — AI-assigned roles via Kilo CLI
#                                           (THIS is the step that was hanging)
#   4. generate_kilo_agents.py            — generate per-agent CLI scripts
#
# Watchdog: this script enforces a 30-minute hard timeout on role_mapper.py
# (it has internal 5-min per-model timeouts but those weren't firing reliably
# in the pre-2026-05-09 hang case). If role_mapper.py exceeds 30 min wall
# clock, it is killed and the script aborts before generate_kilo_agents.

set -e

FABRIK_ROOT="/opt/fabrik"
VENV_PYTHON="$FABRIK_ROOT/.venv/bin/python"
DB_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/kilo_agents_db.py"
BENCHMARK_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/update_kilo_benchmarks.py"
ROLE_MAPPER_SCRIPT="$FABRIK_ROOT/scripts/kilo-benchmarks/role_mapper.py"
AGENT_SCRIPT="$FABRIK_ROOT/scripts/generate_kilo_agents.py"
LOG_FILE="$FABRIK_ROOT/scripts/kilo-benchmarks/cache/manual_workflow.log"

ROLE_MAPPER_TIMEOUT=1800  # 30 minutes hard cap on role_mapper.py
mkdir -p "$(dirname "$LOG_FILE")"

echo "" >> "$LOG_FILE"
echo "=== Manual Kilo Workflow — $(date '+%Y-%m-%d %H:%M:%S') ===" | tee -a "$LOG_FILE"

echo "[1/4] Rebuild agent database..." | tee -a "$LOG_FILE"
"$VENV_PYTHON" "$DB_SCRIPT" all 2>&1 | tee -a "$LOG_FILE"

echo "[2/4] Scrape external benchmarks..." | tee -a "$LOG_FILE"
"$VENV_PYTHON" "$BENCHMARK_SCRIPT" --force 2>&1 | tee -a "$LOG_FILE"

echo "[3/4] AI role assignment via Kilo CLI (max ${ROLE_MAPPER_TIMEOUT}s)..." | tee -a "$LOG_FILE"
cd "$FABRIK_ROOT/scripts/kilo-benchmarks"
if timeout "$ROLE_MAPPER_TIMEOUT" "$VENV_PYTHON" "$ROLE_MAPPER_SCRIPT" 2>&1 | tee -a "$LOG_FILE"; then
    echo "    role_mapper completed within timeout" | tee -a "$LOG_FILE"
else
    rm_exit=$?
    echo "    ERROR: role_mapper.py exceeded ${ROLE_MAPPER_TIMEOUT}s or failed (exit $rm_exit)" | tee -a "$LOG_FILE"
    echo "    Killing any stuck kilo agent processes..." | tee -a "$LOG_FILE"
    pkill -9 -f "kilocode/cli" 2>/dev/null || true
    pkill -9 -f "role_mapper.py" 2>/dev/null || true
    echo "=== Manual Kilo Workflow ABORTED at step 3 — $(date '+%Y-%m-%d %H:%M:%S') ===" | tee -a "$LOG_FILE"
    exit 1
fi

echo "[4/4] Generate per-agent CLI scripts..." | tee -a "$LOG_FILE"
cd "$FABRIK_ROOT"
"$VENV_PYTHON" "$AGENT_SCRIPT" 2>&1 | tee -a "$LOG_FILE"

echo "=== Manual Kilo Workflow complete — $(date '+%Y-%m-%d %H:%M:%S') ===" | tee -a "$LOG_FILE"
