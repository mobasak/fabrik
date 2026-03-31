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

# Read prompt from argument or stdin
if [ $# -gt 0 ]; then
    PROMPT="$*"
else
    PROMPT=$(cat)
fi

if [ -z "$PROMPT" ]; then
    echo "ERROR: No prompt provided" >&2
    echo "Usage: fabrik-docs.sh \"your prompt here\"" >&2
    exit 1
fi

# Set minimal Traycer environment to avoid errors in CLI script
export TRAYCER_PROMPT="$PROMPT"
export TRAYCER_TASK_ID="${TRAYCER_TASK_ID:-cascade-$(date +%s)}"
export TRAYCER_PHASE_ID="${TRAYCER_PHASE_ID:-$TRAYCER_TASK_ID}"
export TRAYCER_WORKFLOW="${TRAYCER_WORKFLOW:-windsurf-cascade}"
export KILO_DEBUG="${KILO_DEBUG:-0}"

# Call CLI agent (inherits all hardware safety logic + fast-path optimization)
exec "$CLI_AGENT"
