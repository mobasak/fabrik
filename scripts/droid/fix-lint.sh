#!/bin/bash

# Droid Lint Fix Script
# Automatically fixes lint violations that require semantic understanding
#
# Usage: ./scripts/droid/fix-lint.sh [directory]
# Example: ./scripts/droid/fix-lint.sh src
#
# Environment variables:
#   CONCURRENCY - Number of parallel processes (default: 5)
#   DRY_RUN - Set to "true" to preview without changes
#
# Note: For simple formatting issues, use ruff --fix first.
# This script handles complex issues that need AI understanding.

set -e

# Configuration
CONCURRENCY=${CONCURRENCY:-5}
DRY_RUN=${DRY_RUN:-false}
TARGET_DIR="${1:-.}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Temp files for tracking
TEMP_DIR=$(mktemp -d)
LINT_OUTPUT="$TEMP_DIR/lint_output.txt"
FILES_WITH_ISSUES="$TEMP_DIR/files.txt"
MODIFIED_COUNT=0
PROCESSED_COUNT=0

# Cleanup on exit
trap "rm -rf $TEMP_DIR" EXIT

# Function to process a single file
process_file() {
    local filepath="$1"
    local issues="$2"

    echo -e "${BLUE}Processing: $filepath${NC}"
    echo -e "  Issues: $issues"

    # The AI prompt for fixing lint issues
    local prompt="Fix the following lint issues in $filepath:

$issues

Guidelines:
1. Fix each issue while preserving the code's functionality
2. For type errors: Add proper type annotations
3. For unused imports: Remove them
4. For undefined names: Either import them or fix the typo
5. For complexity issues: Refactor into smaller functions
6. For Fabrik conventions:
   - Replace hardcoded localhost with os.getenv('HOST', 'localhost')
   - Replace Alpine images with bookworm-slim
   - Ensure health checks test actual dependencies

Return the complete fixed file.
DO NOT add new comments explaining the fixes."

    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${YELLOW}  [DRY RUN] Would fix issues${NC}"
        return 0
    fi

    # Get original file hash for comparison
    local original_hash=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$filepath")

    # Run droid to fix lint issues
    if droid exec --auto low "$prompt" 2>/dev/null; then
        # Check if file was modified
        local new_hash=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$filepath")
        if [ "$original_hash" != "$new_hash" ]; then
            echo -e "${GREEN}  ✓ Fixed${NC}"
            ((MODIFIED_COUNT++)) || true
        else
            echo -e "  No changes needed"
        fi
        ((PROCESSED_COUNT++)) || true
    else
        echo -e "${RED}  ✗ Failed to process${NC}"
    fi
}

# Export function and variables
export -f process_file
export DRY_RUN GREEN YELLOW BLUE RED NC

# Main execution
echo -e "${BLUE}=== Droid Lint Fix ===${NC}"
echo -e "${BLUE}Directory: $TARGET_DIR${NC}"
echo -e "${BLUE}Concurrency: $CONCURRENCY${NC}"
[ "$DRY_RUN" = "true" ] && echo -e "${YELLOW}DRY RUN MODE${NC}"
echo ""

# Step 1: Run ruff --fix first for simple issues
echo -e "${BLUE}Step 1: Running ruff --fix for simple issues...${NC}"
if command -v ruff &> /dev/null; then
    ruff check "$TARGET_DIR" --fix --quiet 2>/dev/null || true
    echo -e "${GREEN}  ✓ Simple fixes applied${NC}"
else
    echo -e "${YELLOW}  ruff not installed, skipping auto-fix${NC}"
fi

# Step 2: Get remaining lint issues
echo -e "\n${BLUE}Step 2: Finding remaining issues for AI fix...${NC}"
if command -v ruff &> /dev/null; then
    ruff check "$TARGET_DIR" --output-format=text 2>/dev/null > "$LINT_OUTPUT" || true
elif command -v flake8 &> /dev/null; then
    flake8 "$TARGET_DIR" > "$LINT_OUTPUT" 2>/dev/null || true
else
    echo -e "${RED}No linter found. Install ruff: pip install ruff${NC}"
    exit 1
fi

# Parse lint output to get unique files with issues
if [ -s "$LINT_OUTPUT" ]; then
    # Extract unique files from lint output
    grep -oE "^[^:]+\.py" "$LINT_OUTPUT" | sort -u > "$FILES_WITH_ISSUES" || true

    FILE_COUNT=$(wc -l < "$FILES_WITH_ISSUES" | tr -d ' ')

    if [ "$FILE_COUNT" -eq 0 ]; then
        echo -e "${GREEN}No lint issues found!${NC}"
        exit 0
    fi

    echo -e "${BLUE}Found $FILE_COUNT files with lint issues${NC}\n"

    # Process each file with its specific issues
    while IFS= read -r file; do
        if [ -f "$file" ]; then
            # Get issues specific to this file
            issues=$(grep "^$file:" "$LINT_OUTPUT" | head -20)
            process_file "$file" "$issues"
        fi
    done < "$FILES_WITH_ISSUES"
else
    echo -e "${GREEN}No lint issues found!${NC}"
    exit 0
fi

# Show summary
echo -e "\n${BLUE}=== Summary ===${NC}"
echo -e "${GREEN}Files with issues: $FILE_COUNT${NC}"
echo -e "${GREEN}Files processed: $PROCESSED_COUNT${NC}"
[ "$DRY_RUN" = "false" ] && echo -e "${GREEN}Files modified: $MODIFIED_COUNT${NC}"

# Run linter again to verify
if [ "$DRY_RUN" = "false" ] && [ "$MODIFIED_COUNT" -gt 0 ]; then
    echo -e "\n${BLUE}Verifying fixes...${NC}"
    if ruff check "$TARGET_DIR" --quiet 2>/dev/null; then
        echo -e "${GREEN}  ✓ All lint issues resolved${NC}"
    else
        echo -e "${YELLOW}  Some issues remain - may need manual review${NC}"
    fi

    echo -e "\n${BLUE}Next steps:${NC}"
    echo "  git diff                    # Review changes"
    echo "  pytest                      # Run tests"
    echo "  git add -A                  # Stage changes"
    echo "  git commit -m 'fix: resolve lint issues'"
fi
