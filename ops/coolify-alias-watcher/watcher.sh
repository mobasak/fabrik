#!/usr/bin/env bash
# Coolify alias watcher — event-driven (no polling).
# Listens to Docker events; when a container in MAP starts, ensures it has
# the friendly DNS alias on the coolify network.
#
# Affected services lose their aliases on every Coolify redeploy because
# Coolify regenerates compose with only UUID-based aliases. This watcher
# re-applies them within ~1s of container start.

set -euo pipefail

# T2-04 G-J3: data-driven alias map loaded from JSON. The orchestrator's
# `add_alias()` writes to this file when new admin-dashboard services
# deploy with `spec.coolify.alias` set. The watcher reloads on
# `systemctl restart` (sub-second). Keys are container-name PREFIXES
# (excluding the trailing `-<timestamp>` suffix Coolify appends on
# every Application redeploy); values are the friendly Docker DNS
# aliases Gatus / inter-service URLs depend on.
ALIASES_PATH=/opt/coolify-alias-watcher/aliases.json
declare -A ALIASES
while IFS=$'\t' read -r prefix alias; do
    ALIASES["$prefix"]="$alias"
done < <(jq -r '.aliases | to_entries[] | "\(.key)\t\(.value)"' "$ALIASES_PATH")

NETWORK=coolify
LOG_TAG=coolify-alias-watcher

log() { logger -t "$LOG_TAG" "$*"; echo "$(date -Is) $*"; }

# Ensure alias exists on container — idempotent
ensure_alias() {
    local container=$1
    local alias=$2

    # Check if alias already attached
    local current_aliases
    current_aliases=$(docker inspect "$container" \
        --format "{{range \$net := .NetworkSettings.Networks}}{{range \$net.Aliases}}{{.}} {{end}}{{end}}" 2>/dev/null || echo "")

    if echo " $current_aliases " | grep -q " $alias "; then
        log "container=$container already has alias=$alias"
        return 0
    fi

    log "applying alias=$alias to container=$container"
    docker network disconnect "$NETWORK" "$container" 2>/dev/null || true
    if docker network connect --alias "$alias" "$NETWORK" "$container"; then
        log "SUCCESS alias=$alias applied to $container"
    else
        log "FAILED to apply alias=$alias to $container"
        return 1
    fi
}

# Reconcile all known containers at startup
log "watcher starting — reconciling all known containers"
for prefix in "${!ALIASES[@]}"; do
    alias="${ALIASES[$prefix]}"
    container=$(docker ps --format "{{.Names}}" | grep "^${prefix}-" | head -1 || true)
    if [[ -n "$container" ]]; then
        ensure_alias "$container" "$alias" || true
    else
        log "no running container for prefix=$prefix (alias=$alias)"
    fi
done

# Event loop: react to container starts in real-time
log "entering event loop (docker events --filter event=start)"
docker events --filter "event=start" --filter "type=container" --format "{{.Actor.Attributes.name}}" |
while IFS= read -r container_name; do
    for prefix in "${!ALIASES[@]}"; do
        if [[ "$container_name" == "${prefix}-"* ]]; then
            alias="${ALIASES[$prefix]}"
            log "DETECTED start container=$container_name prefix=$prefix alias=$alias"
            # Brief delay so Coolify finishes its own network attach
            sleep 2
            ensure_alias "$container_name" "$alias" || true
            break
        fi
    done
done
