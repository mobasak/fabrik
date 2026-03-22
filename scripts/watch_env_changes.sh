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

log "Monitoring .env files in /opt/*/..."
log "Press Ctrl+C to stop"

# Monitor all .env files under /opt/*/
inotifywait -m -e modify,create,close_write --format '%w%f' /opt/*/.env 2>/dev/null | while read -r changed_file; do
    log "Detected change: $changed_file"
    log "Running consolidate_envs.py --apply..."

    if python3 "${FABRIK_ROOT}/scripts/consolidate_envs.py" --apply; then
        log "✅ .env consolidation complete"
    else
        warn "❌ consolidate_envs.py failed"
    fi
done
