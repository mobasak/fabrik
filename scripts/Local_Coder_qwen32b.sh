#!/bin/bash
# Windsurf Cascade Wrapper - Coding Agent
# Calls the Kilo CLI coding agent with hardware safety (Global Sequential Guard)
#
# Usage:
#   fabrik-coder.sh "implement feature X"
#   echo "fix bug Y" | fabrik-coder.sh
#
# Hardware: 32B model, hybrid-cpu (Ryzen AI 9 + RAM)
# Speed: ~15-25 tok/s

set -euo pipefail

CLI_AGENT="$HOME/.traycer/cli-agents/coding-1-fabrik-coder-qwen32b-local-o0000-ppd999.sh"

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
    echo "Usage: fabrik-coder.sh \"your prompt here\"" >&2
    exit 1
fi

# Set minimal Traycer environment (inherited by kilo_dispatch.py)
export TRAYCER_TASK_ID="${TRAYCER_TASK_ID:-cascade-$(date +%s)}"
export TRAYCER_PHASE_ID="${TRAYCER_PHASE_ID:-$TRAYCER_TASK_ID}"
export TRAYCER_WORKFLOW="${TRAYCER_WORKFLOW:-windsurf-cascade}"
export KILO_DEBUG="${KILO_DEBUG:-0}"

# Dispatch through kilo_dispatch.py for context injection (AGENTS-compact, packs, cross-cutting)
exec python3 /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "coding-1-fabrik-coder" \
    --task "$PROMPT" \
    --project "$(pwd)" \
    --template code \
    $DRY_RUN
