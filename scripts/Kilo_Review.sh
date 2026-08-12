#!/bin/bash
# RETIRED 2026-07-19 — Kilo CLI stack retired (operator directive: LLM access = Claude Max OAuth + OpenRouter only). Zero runtime callers; kept for history — do not use.
# Windsurf Cascade Wrapper - Code Review via Kilo CLI
# Calls kilo_code_review.py with hardware-safe local agents
#
# Usage:
#   fabrik-review.sh staged                    # Review git staged files
#   fabrik-review.sh changed                   # Review working tree changes
#   fabrik-review.sh review src/file.py        # Review specific files
#   fabrik-review.sh auto-fix src/ --max-iterations 3
#
# Uses fabrik-reviewer-llama70b (70B, CPU, ~8-12 tok/s) for reviews
# Uses fabrik-fixer-ds16b (16B, hybrid-gpu, ~40-60 tok/s) for fixes

set -euo pipefail

FABRIK_ROOT="/opt/fabrik"
REVIEW_SCRIPT="$FABRIK_ROOT/scripts/kilo_code_review.py"
VENV_PYTHON="$FABRIK_ROOT/.venv/bin/python"

# Fall back to system python if venv not available
if [ ! -x "$VENV_PYTHON" ]; then
    VENV_PYTHON="python3"
fi

if [ ! -f "$REVIEW_SCRIPT" ]; then
    echo "ERROR: Review script not found: $REVIEW_SCRIPT" >&2
    exit 1
fi

# Pass all arguments to kilo_code_review.py
# It will automatically use local agents (fabrik-reviewer, fabrik-fixer)
# via the Kilo CLI agent selection mechanism
exec "$VENV_PYTHON" "$REVIEW_SCRIPT" "$@"
