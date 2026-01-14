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

# Get recommended model using Python import (reliable)
MODEL=$(python3 -c "from scripts.droid_models import get_scenario_recommendation; print(get_scenario_recommendation('code_review').get('models', ['gemini-3-flash-preview'])[0])" 2>/dev/null || echo "gemini-3-flash-preview")
MODEL=${MODEL:-gemini-3-flash-preview}  # Ensure MODEL is never empty

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
            MODEL="$2"
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

echo "🔍 Running droid review with model: $MODEL"
echo "📁 Files: ${FILES[*]}"
echo ""

# Run droid exec (read-only, no --auto flag)
droid exec -m "$MODEL" "$FULL_PROMPT

DO NOT make any changes. Only provide review feedback."

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
