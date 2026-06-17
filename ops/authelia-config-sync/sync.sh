#!/usr/bin/env bash
# Authelia config sync watcher.
# With bind-mount setup (/opt/authelia/config:/config), the working copy IS
# the config Authelia reads — no copy needed. Just restart on change.
# NEVER SIGHUP — Authelia exits on SIGHUP (see LESSONS_LEARNT).

set -euo pipefail

WORKING_COPY="/opt/authelia/config/configuration.yml"
WORKING_DIR="$(dirname "$WORKING_COPY")"
WORKING_BASENAME="$(basename "$WORKING_COPY")"
CONTAINER_NAME="authelia"
LOG_TAG="authelia-config-sync"

log() { logger -t "$LOG_TAG" "$*"; echo "$(date -Is) $*"; }

sync_now() {
    if [[ ! -f "$WORKING_COPY" ]]; then
        log "working copy missing at $WORKING_COPY (deleted? skip)"
        return 0
    fi

    log "restarting Authelia container (bind mount — no copy needed, NEVER SIGHUP)"
    docker restart "$CONTAINER_NAME" > /dev/null
    log "restart complete"
}

log "starting; watching $WORKING_DIR for changes to $WORKING_BASENAME"

inotifywait -q -m -e close_write,moved_to,create --format '%f' "$WORKING_DIR" |
while IFS= read -r filename; do
    if [[ "$filename" == "$WORKING_BASENAME" ]]; then
        log "DETECTED change to $filename"
        sleep 1
        sync_now || log "restart failed (non-fatal, will retry on next event)"
    fi
done
