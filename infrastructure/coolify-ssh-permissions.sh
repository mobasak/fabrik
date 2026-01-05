#!/bin/bash
# Coolify SSH Key Permissions Self-Healing Script
# Ensures SSH keys have correct permissions to prevent deployment failures
# Run via systemd timer every 5 minutes

set -euo pipefail

COOLIFY_SSH_DIR="/data/coolify/ssh"
COOLIFY_KEYS_DIR="/data/coolify/ssh/keys"
COOLIFY_UID=9999
COOLIFY_GID=9999

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Ensure directories exist
if [[ ! -d "$COOLIFY_SSH_DIR" ]]; then
    log "ERROR: Coolify SSH directory not found: $COOLIFY_SSH_DIR"
    exit 1
fi

# Fix directory permissions (must be 700 for SSH)
current_ssh_perms=$(stat -c '%a' "$COOLIFY_SSH_DIR")
if [[ "$current_ssh_perms" != "700" ]]; then
    log "Fixing $COOLIFY_SSH_DIR permissions: $current_ssh_perms -> 700"
    chmod 700 "$COOLIFY_SSH_DIR"
fi

if [[ -d "$COOLIFY_KEYS_DIR" ]]; then
    current_keys_perms=$(stat -c '%a' "$COOLIFY_KEYS_DIR")
    if [[ "$current_keys_perms" != "700" ]]; then
        log "Fixing $COOLIFY_KEYS_DIR permissions: $current_keys_perms -> 700"
        chmod 700 "$COOLIFY_KEYS_DIR"
    fi

    # Fix all private key files (must be 600)
    for keyfile in "$COOLIFY_KEYS_DIR"/ssh_key@*; do
        if [[ -f "$keyfile" ]]; then
            current_perms=$(stat -c '%a' "$keyfile")
            if [[ "$current_perms" != "600" ]]; then
                log "Fixing $keyfile permissions: $current_perms -> 600"
                chmod 600 "$keyfile"
            fi
        fi
    done
fi

# Fix ownership (Coolify container runs as uid 9999)
chown -R "$COOLIFY_UID:$COOLIFY_GID" "$COOLIFY_SSH_DIR"

log "SSH permissions check complete"
