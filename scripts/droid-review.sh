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
MODELS=($(python3 -c "from scripts.droid_models import get_scenario_recommendation; print(' '.join(get_scenario_recommendation('code_review').get('models', ['gpt-5.1-codex-max', 'gemini-3-flash-preview'])))" 2>/dev/null || echo "gpt-5.1-codex-max gemini-3-flash-preview"))
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

# Write prompt to temp file to avoid ARG_MAX issues with large files
PROMPT_FILE=$(mktemp)
trap "rm -f $PROMPT_FILE" EXIT
echo "$FULL_PROMPT

DO NOT make any changes. Only provide review feedback." > "$PROMPT_FILE"

# Run droid exec for each model
# Note: --auto medium required because meta-prompt triggers context gathering
for MODEL in "${REVIEW_MODELS[@]}"; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📋 Review with: $MODEL"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    droid exec -m "$MODEL" --auto medium --file "$PROMPT_FILE"
    echo ""
done

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
