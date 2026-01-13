#!/bin/bash
# Check Cascade backup freshness and remind user to update if stale
# Memories and global rules can only be exported by Cascade in conversation
# This hook reminds the user when the backup is outdated

set -e

BACKUP_FILE="docs/reference/CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md"
MAX_AGE_DAYS=7

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "⚠️  CASCADE BACKUP MISSING"
    echo "   Ask Cascade: 'Export memories and global rules to CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md'"
    exit 0
fi

# Get file age in days
if [[ "$OSTYPE" == "darwin"* ]]; then
    FILE_AGE_DAYS=$(( ( $(date +%s) - $(stat -f %m "$BACKUP_FILE") ) / 86400 ))
else
    FILE_AGE_DAYS=$(( ( $(date +%s) - $(stat -c %Y "$BACKUP_FILE") ) / 86400 ))
fi

if [ "$FILE_AGE_DAYS" -ge "$MAX_AGE_DAYS" ]; then
    echo "⚠️  CASCADE BACKUP STALE (${FILE_AGE_DAYS} days old)"
    echo "   Ask Cascade: 'Update the cascade backup file with current memories and global rules'"
else
    echo "Cascade backup OK (${FILE_AGE_DAYS} days old)"
fi

exit 0
