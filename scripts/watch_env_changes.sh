#!/usr/bin/env bash
# Auto-consolidate .env files when any project .env is modified
# Monitors /opt/*/.env and triggers consolidate_envs.py on changes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[env-watcher]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[env-watcher]${NC} $*"
}

# Check inotify-tools installed
if ! command -v inotifywait &>/dev/null; then
    warn "inotifywait not found. Installing inotify-tools..."
    sudo apt-get update && sudo apt-get install -y inotify-tools
fi

DEBOUNCE_SECS=5
DEBOUNCE_STAMP="/tmp/.fabrik-env-watcher-last-run"

# Build watch list: every /opt/<proj>/.env EXCEPT /opt/fabrik/.env itself.
# Rationale (design intent, see docs/LESSONS_LEARNT.md §8.16):
#   The consolidator's SINK is /opt/fabrik/.env. If we watch it too, any
#   manual Fabrik-native edit (FABRIK_CORE additions, trailing appends)
#   races with the consolidator's own regeneration cycle — trailing-append
#   edits get silently dropped because parse_env_file(..., stop_at_project_sections=True)
#   doesn't see them. Per design: watch SOURCES, not the SINK.
shopt -s nullglob
WATCH_FILES=()
for env_file in /opt/*/.env; do
    [ "$env_file" = "/opt/fabrik/.env" ] && continue
    WATCH_FILES+=("$env_file")
done
shopt -u nullglob

if [ ${#WATCH_FILES[@]} -eq 0 ]; then
    warn "No project .env files found under /opt/*/ (excluding fabrik). Exiting."
    exit 0
fi

log "Monitoring ${#WATCH_FILES[@]} project .env files (fabrik excluded by design)"
log "Press Ctrl+C to stop"

# Monitor all project .env files under /opt/*/ EXCEPT /opt/fabrik/.env
inotifywait -m -e modify,create,close_write --format '%w%f' "${WATCH_FILES[@]}" 2>/dev/null | while read -r changed_file; do
    # Debounce: skip if last consolidation was less than DEBOUNCE_SECS ago
    # (uses a stamp file because pipeline runs in a subshell)
    if [ -f "$DEBOUNCE_STAMP" ]; then
        LAST_AGE=$(( $(date +%s) - $(stat -c %Y "$DEBOUNCE_STAMP") ))
        if [ "$LAST_AGE" -lt "$DEBOUNCE_SECS" ]; then
            continue
        fi
    fi
    touch "$DEBOUNCE_STAMP"

    log "Detected change: $changed_file"
    log "Running consolidate_envs.py --apply..."

    if python3 "${FABRIK_ROOT}/scripts/consolidate_envs.py" --apply; then
        log "✅ .env consolidation complete"
    else
        warn "❌ consolidate_envs.py failed"
    fi
done
