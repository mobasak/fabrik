#!/bin/bash
# droid-review.sh - Wrapper for droid exec code reviews using adaptive meta-prompt
#
# Usage:
#   ./scripts/droid-review.sh <files...>
#   ./scripts/droid-review.sh --plan <plan-file>
#   ./scripts/droid-review.sh --code <file1> <file2>
#   ./scripts/droid-review.sh --update-docs <files...>  # Review + auto-update docs
#
# Always uses the adaptive meta-prompt from templates/droid/review-meta-prompt.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FABRIK_ROOT="$(dirname "$SCRIPT_DIR")"
export PYTHONPATH="$FABRIK_ROOT:${PYTHONPATH:-}"
META_PROMPT="$FABRIK_ROOT/templates/droid/review-meta-prompt.md"

# Check meta-prompt exists
if [[ ! -f "$META_PROMPT" ]]; then
    echo "ERROR: Meta-prompt not found at $META_PROMPT" >&2
    exit 1
fi

# Get recommended models for dual-model review (Fabrik convention: use BOTH)
# Also validates that models have known price multipliers
MODELS=($(python3 -c "
from scripts.droid_models import get_scenario_recommendation
from scripts.droid_model_updater import is_model_safe_for_auto
models = get_scenario_recommendation('code_review').get('models', ['gpt-5.1-codex-max', 'gemini-3-flash-preview'])
safe_models = [m for m in models if is_model_safe_for_auto(m)[0]]
print(' '.join(safe_models if safe_models else ['gpt-5.1-codex-max', 'gemini-3-flash-preview']))
" 2>/dev/null || echo "gpt-5.1-codex-max gemini-3-flash-preview"))
CUSTOM_MODEL=""  # Set if user provides --model flag

# Parse arguments
REVIEW_TYPE="code"
UPDATE_DOCS=false
FILES=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --plan)
            REVIEW_TYPE="plan"
            shift
            ;;
        --code)
            REVIEW_TYPE="code"
            shift
            ;;
        --update-docs)
            UPDATE_DOCS=true
            shift
            ;;
        --model|-m)
            if [[ $# -lt 2 ]] || [[ "$2" == --* ]]; then
                echo "ERROR: --model requires a value" >&2
                exit 1
            fi
            CUSTOM_MODEL="$2"  # Override dual-model with single custom model
            shift 2
            ;;
        *)
            FILES+=("$1")
            shift
            ;;
    esac
done

if [[ ${#FILES[@]} -eq 0 ]]; then
    echo "Usage: $0 [--plan|--code] [--update-docs] [--model MODEL] <files...>"
    echo ""
    echo "Examples:"
    echo "  $0 src/fabrik/scaffold.py"
    echo "  $0 --plan docs/development/plans/my-plan.md"
    echo "  $0 --code src/file1.py src/file2.py"
    echo "  $0 --update-docs src/file.py  # Review + auto-update CHANGELOG/docs"
    exit 1
fi

# Build content based on review type
CONTENT=""
for file in "${FILES[@]}"; do
    if [[ -f "$file" ]]; then
        CONTENT+="
--- $file ---
$(cat "$file")
"
    else
        echo "WARNING: File not found: $file" >&2
    fi
done

# Build the full prompt
if [[ "$REVIEW_TYPE" == "plan" ]]; then
    FULL_PROMPT="$(cat "$META_PROMPT")

PLAN:
$CONTENT"
else
    FULL_PROMPT="$(cat "$META_PROMPT")

CODE:
$CONTENT"
fi

# Determine which models to use
if [[ -n "$CUSTOM_MODEL" ]]; then
    REVIEW_MODELS=("$CUSTOM_MODEL")
    echo "🔍 Running droid review with custom model: $CUSTOM_MODEL"
else
    REVIEW_MODELS=("${MODELS[@]}")
    echo "🔍 Running DUAL-MODEL review (Fabrik convention)"
    echo "   Models: ${MODELS[*]}"
fi
echo "📁 Files: ${FILES[*]}"
echo ""

# KPI: Emit task_start event
TASK_ID=$(python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || echo "unknown")
EVENT_ID_START=$(python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || echo "unknown")
TS_START=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())" 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)
mkdir -p .droid
echo "{\"event_id\": \"$EVENT_ID_START\", \"event_type\": \"task_start\", \"timestamp\": \"$TS_START\", \"task_id\": \"$TASK_ID\"}" >> .droid/kpis.jsonl || true

# Write prompt to temp file to avoid ARG_MAX issues with large files
PROMPT_FILE=$(mktemp)
trap "rm -f $PROMPT_FILE" EXIT
echo "$FULL_PROMPT

DO NOT make any changes. Only provide review feedback." > "$PROMPT_FILE"

# Initialize token accumulators and failure tracking for KPI
TOTAL_TOKENS_INPUT=0
TOTAL_TOKENS_OUTPUT=0
LAST_MODEL=""
ANY_FAILURE=false

# Run droid exec for each model with JSON output for token tracking
# Note: --auto medium required because meta-prompt triggers context gathering
for MODEL in "${REVIEW_MODELS[@]}"; do
    LAST_MODEL="$MODEL"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📋 Review with: $MODEL"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Run with JSON output for token tracking
    OUTPUT=$(droid exec -m "$MODEL" -o json --auto medium --file "$PROMPT_FILE" 2>&1)
    EXEC_EXIT_CODE=$?
    if [[ $EXEC_EXIT_CODE -ne 0 ]]; then
        ANY_FAILURE=true
    fi

    # Extract and display the result
    RESULT=$(echo "$OUTPUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('result', 'No result'))" 2>/dev/null || echo "$OUTPUT")
    echo "$RESULT"

    # Log token usage and accumulate for KPI
    TOKEN_USAGE=$(echo "$OUTPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    usage = d.get('usage', {})
    session_id = d.get('session_id', 'unknown')
    inp = usage.get('input_tokens', 0)
    out = usage.get('output_tokens', 0)
    if usage:
        from scripts.droid_session import log_token_usage
        log_token_usage(session_id, usage, model='$MODEL', context_key='code-review')
        print(f'{inp} {out}')  # Output for accumulation
        print(f'   📊 Tokens: {inp} in, {out} out', file=sys.stderr)
    else:
        print('0 0')
except:
    print('0 0')
" 2>&1) || echo "0 0"
    # Parse and accumulate tokens
    MODEL_TOKENS_IN=$(echo "$TOKEN_USAGE" | head -1 | awk '{print $1}')
    MODEL_TOKENS_OUT=$(echo "$TOKEN_USAGE" | head -1 | awk '{print $2}')
    TOTAL_TOKENS_INPUT=$((TOTAL_TOKENS_INPUT + MODEL_TOKENS_IN))
    TOTAL_TOKENS_OUTPUT=$((TOTAL_TOKENS_OUTPUT + MODEL_TOKENS_OUT))
    echo ""
done

# KPI: Emit task_end event
if [[ "$ANY_FAILURE" == "true" ]]; then
    REVIEW_STATUS="failure"
else
    REVIEW_STATUS="success"
fi
TS_END=$(python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())" 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)
EVENT_ID_END=$(python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null || echo "unknown")
# Calculate duration in seconds
DURATION=$(python3 -c "
from datetime import datetime
try:
    start = datetime.fromisoformat('$TS_START'.replace('Z', '+00:00'))
    end = datetime.fromisoformat('$TS_END'.replace('Z', '+00:00'))
    print(round((end - start).total_seconds(), 2))
except: print(0)
" 2>/dev/null || echo "0")
# Build model field - use single model if only one, otherwise omit
if [[ ${#REVIEW_MODELS[@]} -eq 1 ]]; then
    MODEL_FIELD=", \"model\": \"$LAST_MODEL\""
else
    MODEL_FIELD=""
fi
echo "{\"event_id\": \"$EVENT_ID_END\", \"event_type\": \"task_end\", \"timestamp\": \"$TS_END\", \"task_id\": \"$TASK_ID\", \"tokens_input\": $TOTAL_TOKENS_INPUT, \"tokens_output\": $TOTAL_TOKENS_OUTPUT, \"duration_seconds\": $DURATION, \"status\": \"$REVIEW_STATUS\"$MODEL_FIELD}" >> .droid/kpis.jsonl || true

# After review, check if docs need updating
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 Documentation Sync Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python3 "$FABRIK_ROOT/scripts/docs_sync.py" || true

# If --update-docs flag is set, trigger automatic documentation update
if [[ "$UPDATE_DOCS" == "true" ]]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 Auto-Updating Documentation (CHANGELOG, etc.)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    # Pass all files to docs_updater for automatic update
    for file in "${FILES[@]}"; do
        if [[ -f "$file" ]]; then
            echo "Updating docs for: $file"
            python3 "$FABRIK_ROOT/scripts/docs_updater.py" --file "$file" || true
        fi
    done
    echo ""
    echo "✅ Documentation update complete"
fi
