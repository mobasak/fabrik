#!/usr/bin/env bash
# Authelia config sync watcher.
# Watches /opt/authelia/config/configuration.yml (working copy) and on every
# write, copies it into the Docker volume that Authelia actually loads, then
# restarts the Authelia container (NEVER SIGHUP — Authelia exits on SIGHUP).
#
# Solves the 'Authelia config drift' issue documented in
# vps-complete-inventory.md Issue #2.

set -euo pipefail

WORKING_COPY="/opt/authelia/config/configuration.yml"
WORKING_DIR="$(dirname "$WORKING_COPY")"
WORKING_BASENAME="$(basename "$WORKING_COPY")"
CONTAINER_NAME="authelia-hks48k8sg8o4co4co08co00o"
LOG_TAG="authelia-config-sync"

log() { logger -t "$LOG_TAG" "$*"; echo "$(date -Is) $*"; }

resolve_volume_target() {
    local mount_src
    mount_src=$(docker inspect "$CONTAINER_NAME" \
        --format '{{ range .Mounts }}{{ if eq .Destination "/config" }}{{ .Source }}{{ end }}{{ end }}' \
        2>/dev/null)
    if [[ -z "$mount_src" ]]; then
        return 1
    fi
    echo "${mount_src}/${WORKING_BASENAME}"
}

sync_now() {
    if [[ ! -f "$WORKING_COPY" ]]; then
        log "working copy missing at $WORKING_COPY (deleted? skip)"
        return 0
    fi

    local volume_target
    if ! volume_target=$(resolve_volume_target); then
        log "ERROR cannot resolve authelia volume mount; container running?"
        return 1
    fi

    if [[ ! -f "$volume_target" ]]; then
        log "WARN volume target $volume_target does not exist yet — copying"
    fi

    if cmp -s "$WORKING_COPY" "$volume_target" 2>/dev/null; then
        log "already in sync (cmp identical) — skip"
        return 0
    fi

    log "syncing $WORKING_COPY → $volume_target"
    cp -f "$WORKING_COPY" "$volume_target"
    chmod 600 "$volume_target"

    log "restarting Authelia container (NEVER SIGHUP)"
    docker restart "$CONTAINER_NAME" > /dev/null
    log "sync + restart complete"
}

log "starting; reconciling at startup"
sync_now || log "startup reconcile failed (non-fatal)"

log "watching $WORKING_DIR for changes to $WORKING_BASENAME"
inotifywait -q -m -e close_write,moved_to,create --format '%f' "$WORKING_DIR" |
while IFS= read -r filename; do
    if [[ "$filename" == "$WORKING_BASENAME" ]]; then
        log "DETECTED change to $filename"
        sleep 1
        sync_now || log "sync failed (non-fatal, will retry on next event)"
    fi
done
