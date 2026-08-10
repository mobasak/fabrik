#!/usr/bin/env bash
# AFTER-EDIT: docs/infrastructure/vps-status.md CHANGELOG.md | deploy: scp to /usr/local/bin/fabrik-autoheal on every VPS (cron * * * * *)
# fabrik-autoheal — restart containers Docker marks UNHEALTHY (fleet invariant, operator
# directive 2026-08-10: "unhealthy-but-alive gets auto-restarted, for all types of projects").
#
# Docker's restart policy only covers EXITED containers; a wedged process that still answers
# PID 1 but fails its healthcheck runs forever. This closes that gap deterministically:
#   unhealthy (already debounced by the healthcheck's own retries) → docker restart.
#
# Guards:
#   * restart-storm cap: max MAX_RESTARTS per container per WINDOW_S — beyond it we STOP
#     restarting (hold-down) so a crash-looping service stays visibly unhealthy and the
#     existing Gatus/Prometheus alerting fires loud instead of being masked by restarts.
#   * opt-out label: containers with fabrik.autoheal=false are never touched (for services
#     where a blind restart is worse than the wedge — declare it in the compose).
#   * state in /run/fabrik-autoheal (tmpfs): counters reset on reboot by design.
#
# Runs from root cron every minute on every VPS. Logs to syslog (tag: fabrik-autoheal) —
# journald/Loki pick it up; no log file to rotate.
set -u
STATE_DIR=/run/fabrik-autoheal
MAX_RESTARTS="${AUTOHEAL_MAX_RESTARTS:-3}"
WINDOW_S="${AUTOHEAL_WINDOW_S:-1800}"
mkdir -p "$STATE_DIR" 2>/dev/null || true

# Single-instance guard: `docker restart` blocks ~10s per container, so several unhealthy
# containers push one run past the 60s cron cadence — an overlapping second instance would
# double-restart and corrupt the counters (review finding). Skip, never queue: the next
# minute's tick handles whatever is still unhealthy.
exec 9> "$STATE_DIR/.lock"
if ! flock -n 9; then
  logger -t fabrik-autoheal "SKIP-RUN: previous instance still running"
  exit 0
fi

# Maintenance pause (review finding B3, 2026-08-10): during a migration/init window a
# container can be legitimately unhealthy for longer than its healthcheck tolerates —
# autoheal restarting it mid-migration corrupts the work (live case: tryton-crm's 8-10 min
# module init vs a ~3.2 min worst-case time-to-unhealthy). `touch $STATE_DIR/pause` before
# the window, `rm` after; a stale pause (>2h) is ignored so a forgotten one can't disable
# healing forever.
if [ -f "$STATE_DIR/pause" ]; then
  page=$(( $(date +%s) - $(stat -c %Y "$STATE_DIR/pause" 2>/dev/null || echo 0) ))
  if [ "$page" -lt 7200 ]; then
    logger -t fabrik-autoheal "PAUSED (maintenance window, ${page}s old) — no restarts this tick"
    exit 0
  fi
  logger -t fabrik-autoheal "STALE pause file (>2h) ignored — healing resumes"
fi

now=$(date +%s)

docker ps --filter health=unhealthy --format '{{.Names}}' 2>/dev/null | while read -r name; do
  [ -n "$name" ] || continue
  # opt-out label
  optout=$(docker inspect --format '{{index .Config.Labels "fabrik.autoheal"}}' "$name" 2>/dev/null)
  if [ "$optout" = "false" ]; then
    logger -t fabrik-autoheal "SKIP $name (fabrik.autoheal=false label)"
    continue
  fi
  # restart-storm guard: prune window, count, cap
  sf="$STATE_DIR/$name.restarts"
  recent=""
  if [ -f "$sf" ]; then
    while read -r ts; do
      case "$ts" in ''|*[!0-9]*) continue ;; esac
      [ $((now - ts)) -lt "$WINDOW_S" ] && recent="$recent$ts
"
    done < "$sf"
  fi
  count=$(printf '%s' "$recent" | grep -c . || true)
  if [ "$count" -ge "$MAX_RESTARTS" ]; then
    logger -t fabrik-autoheal "HOLD-DOWN $name: $count restarts in ${WINDOW_S}s — leaving unhealthy for the alert layer"
    printf '%s' "$recent" > "$sf"
    continue
  fi
  if docker restart "$name" >/dev/null 2>&1; then
    printf '%s%s\n' "$recent" "$now" > "$sf"
    logger -t fabrik-autoheal "RESTARTED $name (unhealthy; $((count + 1))/$MAX_RESTARTS in window)"
  else
    logger -t fabrik-autoheal "RESTART-FAILED $name (docker restart non-zero)"
  fi
done
