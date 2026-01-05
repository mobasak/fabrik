#!/bin/bash

# Droid Error Message Improvement Script
# Improves error messages to be more descriptive and user-friendly
#
# Usage: ./scripts/droid/improve-errors.sh [directory]
# Example: ./scripts/droid/improve-errors.sh src
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
ERRORS_FOUND="$TEMP_DIR/errors_found.txt"
MODIFIED_COUNT=0
PROCESSED_COUNT=0
ERRORS_IMPROVED=0

# Cleanup on exit
trap "rm -rf $TEMP_DIR" EXIT

# Function to process a single file
process_file() {
    local filepath="$1"

    # Check if file contains error raising patterns
    if ! grep -qE "raise .*(Error|Exception)|click\.(echo|secho).*err=True|logging\.(error|warning)" "$filepath" 2>/dev/null; then
        return 0
    fi

    # Count error instances for reporting
    local error_count=$(grep -cE "raise .*(Error|Exception)" "$filepath" 2>/dev/null || echo 0)

    echo -e "${BLUE}Processing: $filepath${NC}"
    echo -e "  Found $error_count error raising statement(s)"

    # The AI prompt for improving error messages
    local prompt="Improve the error messages in $filepath:

Find all error raising statements (raise ValueError, raise RuntimeError, click.echo with err=True, etc.)
and improve their error messages following these guidelines:

1. Make messages more descriptive and actionable
2. Include context about what went wrong
3. Suggest potential fixes when appropriate
4. Use user-friendly language (avoid technical jargon)
5. Include relevant details without exposing sensitive data

Examples of improvements:

- 'Invalid config' → 'Configuration file is invalid: missing required field \"domain\". Please check your spec file format.'
- 'File not found' → 'Spec file not found at {path}. Run \"fabrik new\" to create one or verify the path.'
- 'Connection failed' → 'Failed to connect to Coolify API at {url}. Verify COOLIFY_API_URL and COOLIFY_API_TOKEN in your .env file.'
- 'Invalid template' → 'Template \"{name}\" not found. Available templates: {list}. Run \"fabrik templates\" to see all options.'

Only modify the error message strings, preserve all other code.
Return the complete file with improved error messages."

    if [ "$DRY_RUN" = "true" ]; then
        echo -e "${YELLOW}  [DRY RUN] Would improve $error_count error message(s)${NC}"
        echo "$error_count" >> "$ERRORS_FOUND"
        return 0
    fi

    # Get original file hash for comparison
    local original_hash=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$filepath")

    # Run droid to improve error messages
    if droid exec --auto low "$prompt" 2>/dev/null; then
        # Check if file was modified
        local new_hash=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$filepath")
        if [ "$original_hash" != "$new_hash" ]; then
            echo -e "${GREEN}  ✓ Improved error messages${NC}"
            ((MODIFIED_COUNT++)) || true
            ((ERRORS_IMPROVED+=error_count)) || true
        else
            echo -e "  No changes needed"
        fi
        ((PROCESSED_COUNT++)) || true
    else
        echo -e "${RED}  ✗ Failed to process${NC}"
    fi
}

# Export function and variables for parallel execution
export -f process_file
export DRY_RUN GREEN YELLOW BLUE RED NC ERRORS_FOUND

# Main execution
echo -e "${BLUE}=== Droid Error Message Improvement ===${NC}"
echo -e "${BLUE}Directory: $TARGET_DIR${NC}"
echo -e "${BLUE}Concurrency: $CONCURRENCY${NC}"
[ "$DRY_RUN" = "true" ] && echo -e "${YELLOW}DRY RUN MODE${NC}"
echo ""

# Find Python files containing error patterns
find "$TARGET_DIR" -type f -name "*.py" \
    ! -path "*/__pycache__/*" \
    ! -path "*/.venv/*" \
    ! -path "*/venv/*" \
    ! -path "*/.git/*" \
    ! -path "*/dist/*" \
    ! -path "*/build/*" \
    ! -path "*/.tmp/*" \
    -exec grep -l "raise \|Error\|Exception" {} \; 2>/dev/null > "$FILES_LIST" || true

FILE_COUNT=$(wc -l < "$FILES_LIST" | tr -d ' ')

if [ "$FILE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}No files with error patterns found${NC}"
    exit 0
fi

echo -e "${BLUE}Found $FILE_COUNT files with error patterns${NC}\n"

# Process files
while IFS= read -r file; do
    process_file "$file"
done < "$FILES_LIST"

# Calculate total errors found in dry run
if [ "$DRY_RUN" = "true" ] && [ -f "$ERRORS_FOUND" ]; then
    TOTAL_ERRORS=$(awk '{sum+=$1} END {print sum}' "$ERRORS_FOUND" 2>/dev/null || echo 0)
fi

# Show summary
echo -e "\n${BLUE}=== Summary ===${NC}"
echo -e "${GREEN}Files scanned: $FILE_COUNT${NC}"
echo -e "${GREEN}Files processed: $PROCESSED_COUNT${NC}"

if [ "$DRY_RUN" = "true" ]; then
    [ -n "$TOTAL_ERRORS" ] && echo -e "${YELLOW}Error messages to improve: $TOTAL_ERRORS${NC}"
else
    echo -e "${GREEN}Files modified: $MODIFIED_COUNT${NC}"
    [ "$ERRORS_IMPROVED" -gt 0 ] && echo -e "${GREEN}Error messages improved: ~$ERRORS_IMPROVED${NC}"
fi

if [ "$DRY_RUN" = "false" ] && [ "$MODIFIED_COUNT" -gt 0 ]; then
    echo -e "\n${BLUE}Next steps:${NC}"
    echo "  git diff                    # Review changes"
    echo "  pytest                      # Run tests"
    echo "  git add -A                  # Stage changes"
    echo "  git commit -m 'refactor: improve error messages for better UX'"
fi
