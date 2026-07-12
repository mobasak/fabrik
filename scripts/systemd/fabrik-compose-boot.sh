#!/usr/bin/env bash
# fabrik-compose-boot.sh — reconcile EVERY /opt/*/compose.yaml stack to running on boot. Idempotent.
#
# WHY: Docker's `restart: unless-stopped` policy does NOT resume a container that had already fully
# exited (non-zero) at the moment dockerd stopped — e.g. a service that crashes with exit 255 during a
# host reboot. On 2026-07-08 vps1's alertmanager died exactly this way during a kernel-upgrade reboot and
# stayed down 4 days (silent, because the down service WAS the alert pipeline). This oneshot closes that
# race fleet-wide: `docker compose up -d` restores any stack member that isn't running, and is a no-op for
# those already up. Runs After=docker.service via fabrik-compose-boot.service (see the .service unit).
#
# Installed to /usr/local/bin/fabrik-compose-boot.sh on every fleet host (hub + spokes).
# AFTER-EDIT: scripts/systemd/fabrik-compose-boot.service, scripts/systemd/README.md, scripts/bootstrap/bootstrap-vps.sh
set -u
shopt -s nullglob

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

log() { echo "[fabrik-compose-boot] $*"; }

# Shared-infra stacks first so dependent app stacks find them ready (avoids brief connect crash-loops on a
# cold boot); every other stack follows. Names not present on this host are skipped harmlessly.
PRIORITY=(postgres redis traefik authelia meilisearch monitoring monitoring-agent)

up_stack() {
  local dir="$1"
  [ -f "$dir/compose.yaml" ] || return 0
  if [ "$DRY_RUN" = 1 ]; then
    log "would up: $dir"
    return 0
  fi
  log "up: $dir"
  if ! docker compose -f "$dir/compose.yaml" up -d 2>&1 | sed 's/^/[fabrik-compose-boot]   /'; then
    log "WARN: 'docker compose up -d' failed for $dir (see above) — continuing"
  fi
}

seen=" "
for name in "${PRIORITY[@]}"; do
  [ -d "/opt/$name" ] || continue
  up_stack "/opt/$name"
  seen+="/opt/$name "
done
for f in /opt/*/compose.yaml; do
  dir=$(dirname "$f")
  case "$seen" in *" $dir "*) continue ;; esac
  up_stack "$dir"
done

log "reconcile complete"
exit 0   # never fail the boot transaction — warnings are journaled, not fatal
