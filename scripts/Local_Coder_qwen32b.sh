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

# Read prompt from argument or stdin
if [ $# -gt 0 ]; then
    PROMPT="$*"
else
    PROMPT=$(cat)
fi

if [ -z "$PROMPT" ]; then
    echo "ERROR: No prompt provided" >&2
    echo "Usage: fabrik-coder.sh \"your prompt here\"" >&2
    exit 1
fi

# Set minimal Traycer environment to avoid errors in CLI script
export TRAYCER_PROMPT="$PROMPT"
export TRAYCER_TASK_ID="${TRAYCER_TASK_ID:-cascade-$(date +%s)}"
export TRAYCER_PHASE_ID="${TRAYCER_PHASE_ID:-$TRAYCER_TASK_ID}"
export TRAYCER_WORKFLOW="${TRAYCER_WORKFLOW:-windsurf-cascade}"
export KILO_DEBUG="${KILO_DEBUG:-0}"

# Call CLI agent (inherits all hardware safety logic)
exec "$CLI_AGENT"
