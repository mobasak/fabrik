#!/bin/bash

# Droid Import Refactoring Script
# Organizes imports across Python files in the codebase
#
# Usage: ./scripts/droid/refactor-imports.sh [directory]
# Example: ./scripts/droid/refactor-imports.sh src
#
# Environment variables:
#   CONCURRENCY - Number of parallel processes (default: 5)
#   DRY_RUN - Set to "true" to preview without changes

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
FILES_LIST="$TEMP_DIR/files.txt"
MODIFIED_COUNT=0
PROCESSED_COUNT=0

# Cleanup on exit
trap "rm -rf $TEMP_DIR" EXIT

# Function to process a single file
process_file() {
    local filepath="$1"
    local filename=$(basename "$filepath")

    # Check if file has imports
    if ! grep -qE "^import |^from .* import" "$filepath" 2>/dev/null; then
        return 0
    fi

    echo -e "${BLUE}Processing: $filepath${NC}"

    # The AI prompt for refactoring imports
    local prompt="Refactor the imports in $filepath:

1. Group imports in this order with blank lines between:
   - Standard library imports (os, sys, pathlib, etc.)
   - Third-party packages (click, pydantic, httpx, etc.)
   - Local/relative imports (from fabrik.*, from .*)

2. Sort alphabetically within each group
3. Remove unused imports
4. Use 'from X import Y' style consistently
5. Consolidate duplicate imports from same module

Only modify imports, preserve all other code exactly.
Return the complete refactored file."

    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${YELLOW}  [DRY RUN] Would refactor imports${NC}"
        return 0
    fi

    # Get original file hash for comparison
    local original_hash=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$filepath")

    # Run droid to refactor the file
    if droid exec --auto low "$prompt" 2>/dev/null; then
        # Check if file was modified
        local new_hash=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$filepath")
        if [ "$original_hash" != "$new_hash" ]; then
            echo -e "${GREEN}  ✓ Refactored${NC}"
            ((MODIFIED_COUNT++)) || true
        fi
        ((PROCESSED_COUNT++)) || true
    else
        echo -e "${RED}  ✗ Failed to process${NC}"
    fi
}

# Export function and variables for parallel execution
export -f process_file
export DRY_RUN GREEN YELLOW BLUE RED NC

# Main execution
echo -e "${BLUE}=== Droid Import Refactoring ===${NC}"
echo -e "${BLUE}Directory: $TARGET_DIR${NC}"
echo -e "${BLUE}Concurrency: $CONCURRENCY${NC}"
[ "$DRY_RUN" = "true" ] && echo -e "${YELLOW}DRY RUN MODE${NC}"
echo ""

# Find Python files
find "$TARGET_DIR" -type f -name "*.py" \
    ! -path "*/__pycache__/*" \
    ! -path "*/.venv/*" \
    ! -path "*/venv/*" \
    ! -path "*/.git/*" \
    ! -path "*/dist/*" \
    ! -path "*/build/*" \
    ! -path "*/.tmp/*" \
    > "$FILES_LIST"

FILE_COUNT=$(wc -l < "$FILES_LIST" | tr -d ' ')

if [ "$FILE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}No Python files found${NC}"
    exit 0
fi

echo -e "${BLUE}Found $FILE_COUNT files to check${NC}\n"

# Process files (sequential for now, parallel can cause issues with droid)
while IFS= read -r file; do
    process_file "$file"
done < "$FILES_LIST"

# Show summary
echo -e "\n${BLUE}=== Summary ===${NC}"
echo -e "${GREEN}Files checked: $FILE_COUNT${NC}"
echo -e "${GREEN}Files processed: $PROCESSED_COUNT${NC}"
[ "$DRY_RUN" = "false" ] && echo -e "${GREEN}Files modified: $MODIFIED_COUNT${NC}"

if [ "$DRY_RUN" = "false" ] && [ "$MODIFIED_COUNT" -gt 0 ]; then
    echo -e "\n${BLUE}Next steps:${NC}"
    echo "  git diff                    # Review changes"
    echo "  ruff check .                # Verify lint"
    echo "  git add -A                  # Stage changes"
    echo "  git commit -m 'refactor: organize imports'"
fi
