#!/bin/bash
# droid-review.sh - Wrapper for droid exec code reviews using adaptive meta-prompt
#
# Usage:
#   ./scripts/droid-review.sh <files...>
#   ./scripts/droid-review.sh --plan <plan-file>
#   ./scripts/droid-review.sh --code <file1> <file2>
#
# Always uses the adaptive meta-prompt from templates/droid/review-meta-prompt.md

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FABRIK_ROOT="$(dirname "$SCRIPT_DIR")"
META_PROMPT="$FABRIK_ROOT/templates/droid/review-meta-prompt.md"

# Check meta-prompt exists
if [[ ! -f "$META_PROMPT" ]]; then
    echo "ERROR: Meta-prompt not found at $META_PROMPT" >&2
    exit 1
fi

# Get recommended model using Python import (reliable)
MODEL=$(python3 -c "from scripts.droid_models import get_scenario_recommendation; print(get_scenario_recommendation('code_review').get('models', ['gemini-3-flash-preview'])[0])" 2>/dev/null || echo "gemini-3-flash-preview")

# Parse arguments
REVIEW_TYPE="code"
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
        --model|-m)
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
    echo "Usage: $0 [--plan|--code] [--model MODEL] <files...>"
    echo ""
    echo "Examples:"
    echo "  $0 src/fabrik/scaffold.py"
    echo "  $0 --plan docs/development/plans/my-plan.md"
    echo "  $0 --code src/file1.py src/file2.py"
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
