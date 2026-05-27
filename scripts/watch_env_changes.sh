#!/usr/bin/env bash
# Monitor /opt/*/.env files for changes and run audit on modification.
# NEVER writes secrets anywhere. Detects violations and logs warnings.
#
# Started by wsl_startup_hook.sh as a persistent background process.
# Sends violations to stdout (captured in .tmp/env_watcher.log).

set -euo pipefail

FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"
VENV_PYTHON="$FABRIK_ROOT/.venv/bin/python"
AUDIT_SCRIPT="$FABRIK_ROOT/scripts/audit_envs.py"

log() { echo "[env-watcher $(date '+%H:%M:%S')] $*"; }

# Check inotify-tools installed
if ! command -v inotifywait &>/dev/null; then
    log "ERROR: inotifywait not found. Install: sudo apt-get install -y inotify-tools"
    exit 1
fi

DEBOUNCE_SECS=10
DEBOUNCE_STAMP="/tmp/.fabrik-env-watcher-last-run"

# Build watch list: every /opt/<project>/.env EXCEPT fabrik's own.
shopt -s nullglob
WATCH_FILES=()
for env_file in /opt/*/.env; do
    [ "$env_file" = "/opt/fabrik/.env" ] && continue
    WATCH_FILES+=("$env_file")
done
shopt -u nullglob

if [ ${#WATCH_FILES[@]} -eq 0 ]; then
    log "No project .env files found. Exiting."
    exit 0
fi

log "Monitoring ${#WATCH_FILES[@]} project .env files"

# Monitor and run audit on changes
inotifywait -m -e modify,create,close_write --format '%w%f' "${WATCH_FILES[@]}" 2>/dev/null | while read -r changed_file; do
    # Debounce
    if [ -f "$DEBOUNCE_STAMP" ]; then
        LAST_AGE=$(( $(date +%s) - $(stat -c %Y "$DEBOUNCE_STAMP") ))
        if [ "$LAST_AGE" -lt "$DEBOUNCE_SECS" ]; then
            continue
        fi
    fi
    touch "$DEBOUNCE_STAMP"

    log "Change detected: $changed_file"

    # Run audit (exit code 1 = violations found)
    if ! $VENV_PYTHON "$AUDIT_SCRIPT" 2>&1; then
        log "VIOLATIONS DETECTED — check audit output above"
    fi
done
