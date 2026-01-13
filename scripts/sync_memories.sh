#!/bin/bash
# Sync Cascade memories to documentation
# Uses droid exec to export all memories from AI context
# Runs on pre-commit but only if file is >24 hours old (to minimize API calls)

set -e

MEMORIES_FILE="docs/reference/MEMORIES.md"
MAX_AGE_HOURS=24

# Check if droid is available
if ! command -v droid &> /dev/null; then
    echo "Warning: droid CLI not available, skipping memory sync"
    exit 0
fi

# Check if file exists and is recent
if [ -f "$MEMORIES_FILE" ]; then
    # Get file age in hours
    if [[ "$OSTYPE" == "darwin"* ]]; then
        FILE_AGE=$(( ( $(date +%s) - $(stat -f %m "$MEMORIES_FILE") ) / 3600 ))
    else
        FILE_AGE=$(( ( $(date +%s) - $(stat -c %Y "$MEMORIES_FILE") ) / 3600 ))
    fi

    if [ "$FILE_AGE" -lt "$MAX_AGE_HOURS" ]; then
        echo "Memories file is ${FILE_AGE}h old (max: ${MAX_AGE_HOURS}h), skipping sync"
        exit 0
    fi
    echo "Memories file is ${FILE_AGE}h old, updating..."
else
    echo "Memories file not found, creating..."
    mkdir -p "$(dirname "$MEMORIES_FILE")"
fi

# Create prompt for droid exec
PROMPT="You MUST output the FULL TEXT of every memory in your context. Do NOT summarize.

FORMAT (output this EXACTLY):

# Cascade Memories

**Exported:** $(date +%Y-%m-%d)
**Workspace:** $(basename $(pwd))

## Memory 1: [Title from memory]
[FULL VERBATIM TEXT of memory - every word, every line]

## Memory 2: [Title from memory]
[FULL VERBATIM TEXT of memory - every word, every line]

... continue for ALL memories ...

CRITICAL RULES:
- Output the COMPLETE text of each memory, not a summary
- Include ALL memories you can see in your context
- Do NOT add commentary or explanations
- Do NOT skip any memory
- Do NOT truncate content"

# Run droid exec to export memories
echo "Running droid exec to export memories..."
RESULT=$(droid exec --auto low -o text "$PROMPT" 2>&1) || {
    echo "Warning: droid exec failed, skipping memory sync"
    exit 0
}

# Extract markdown content (everything after the header)
echo "$RESULT" > "$MEMORIES_FILE"

# Check if file was created successfully
if [ -s "$MEMORIES_FILE" ]; then
    echo "Updated $MEMORIES_FILE"
    git add "$MEMORIES_FILE" 2>/dev/null || true
else
    echo "Warning: Memory export produced empty file"
    exit 0
fi
