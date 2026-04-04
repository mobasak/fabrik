#!/bin/bash
# Windsurf Cascade Wrapper - Documentation Agent
# Calls the Kilo CLI documentation agent with hardware safety (Global Sequential Guard + Fast-Path)
#
# Usage:
#   fabrik-docs.sh "update README with X"
#   echo "generate changelog entry" | fabrik-docs.sh
#
# Hardware: 8B model, GPU (RTX 5070)
# Speed: ~80-100 tok/s (instant on GPU)
# Fast-Path: Bypasses lock if 5.5GB VRAM free + GPU idle

set -euo pipefail

CLI_AGENT="$HOME/.traycer/cli-agents/documentation-1-fabrik-docs-llama8b-local-o0000-ppd999.sh"

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
    echo "Usage: fabrik-docs.sh \"your prompt here\"" >&2
    exit 1
fi

# Set minimal Traycer environment (inherited by kilo_dispatch.py)
export TRAYCER_TASK_ID="${TRAYCER_TASK_ID:-cascade-$(date +%s)}"
export TRAYCER_PHASE_ID="${TRAYCER_PHASE_ID:-$TRAYCER_TASK_ID}"
export TRAYCER_WORKFLOW="${TRAYCER_WORKFLOW:-windsurf-cascade}"
export KILO_DEBUG="${KILO_DEBUG:-0}"

# Dispatch through kilo_dispatch.py for context injection (AGENTS-compact, packs, cross-cutting)
exec python3 /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "documentation-1-fabrik-docs" \
    --task "$PROMPT" \
    --project "$(pwd)" \
    --template code \
    $DRY_RUN
