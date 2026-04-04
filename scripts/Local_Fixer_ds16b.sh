#!/bin/bash
# Windsurf Cascade Wrapper - Bug Fixing Agent
# Calls the Kilo CLI fixing agent with hardware safety (Global Sequential Guard)
#
# Usage:
#   fabrik-fixer.sh "fix this error"
#   echo "debug issue X" | fabrik-fixer.sh
#
# Hardware: 16B model, hybrid-gpu (GPU primary + RAM spillover)
# Speed: ~40-60 tok/s

set -euo pipefail

CLI_AGENT="$HOME/.traycer/cli-agents/fixing-1-fabrik-fixer-ds16b-local-o0000-ppd999.sh"

if [ ! -x "$CLI_AGENT" ]; then
    echo "ERROR: CLI agent not found: $CLI_AGENT" >&2
    echo "Run: python scripts/generate_kilo_agents.py to create CLI agents" >&2
    exit 1
fi

# Parse --dry-run flag before reading prompt
DRY_RUN=""
ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then
        DRY_RUN="--dry-run"
    else
        ARGS+=("$arg")
    fi
done

# Read prompt from remaining arguments or stdin
if [ ${#ARGS[@]} -gt 0 ]; then
    PROMPT="${ARGS[*]}"
else
    PROMPT=$(cat)
fi

if [ -z "$PROMPT" ]; then
    echo "ERROR: No prompt provided" >&2
    echo "Usage: fabrik-fixer.sh \"your prompt here\"" >&2
    exit 1
fi

# Set minimal Traycer environment (inherited by kilo_dispatch.py)
export TRAYCER_TASK_ID="${TRAYCER_TASK_ID:-cascade-$(date +%s)}"
export TRAYCER_PHASE_ID="${TRAYCER_PHASE_ID:-$TRAYCER_TASK_ID}"
export TRAYCER_WORKFLOW="${TRAYCER_WORKFLOW:-windsurf-cascade}"
export KILO_DEBUG="${KILO_DEBUG:-0}"

# Dispatch through kilo_dispatch.py for context injection (AGENTS-compact, packs, cross-cutting)
exec python3 /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "fixing-1-fabrik-fixer" \
    --task "$PROMPT" \
    --project "$(pwd)" \
    --template fix \
    $DRY_RUN
