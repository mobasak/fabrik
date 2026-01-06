#!/bin/bash
# Rollback script for hook consolidation
set -e

HOOKS_JSON=~/.factory/hooks.json
SETTINGS_JSON=~/.factory/settings.json
BACKUP_DIR=~/.factory/backups

echo "Rolling back hook configuration..."

# Find latest backup
LATEST_BACKUP=$(ls -t $BACKUP_DIR/hooks.json.bak.* 2>/dev/null | head -n1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "No backup found! Cannot rollback."
    exit 1
fi

echo "Restoring from $LATEST_BACKUP"
cp "$LATEST_BACKUP" "$HOOKS_JSON"

# Restore settings if backup exists
LATEST_SETTINGS_BACKUP=$(ls -t $BACKUP_DIR/settings.json.bak.* 2>/dev/null | head -n1)
if [ -n "$LATEST_SETTINGS_BACKUP" ]; then
    echo "Restoring settings from $LATEST_SETTINGS_BACKUP"
    cp "$LATEST_SETTINGS_BACKUP" "$SETTINGS_JSON"
fi

echo "Rollback complete."
