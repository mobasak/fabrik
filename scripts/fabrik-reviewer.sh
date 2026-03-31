#!/bin/bash
# Windsurf Cascade Wrapper - Code Review Agent
# Calls the Kilo CLI reviewing agent with hardware safety (Global Sequential Guard)
#
# Usage:
#   fabrik-reviewer.sh "review these changes"
#   echo "check this implementation" | fabrik-reviewer.sh
#
# Hardware: 70B model, CPU-only (Ryzen AI 9 + RAM)
# Speed: ~8-12 tok/s

set -euo pipefail

CLI_AGENT="$HOME/.traycer/cli-agents/reviewing-1-fabrik-reviewer-llama70b-local-o0000-ppd999.sh"

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
    echo "Usage: fabrik-reviewer.sh \"your prompt here\"" >&2
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
