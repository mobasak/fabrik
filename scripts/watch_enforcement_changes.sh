#!/usr/bin/env bash
# Auto-sync enforcement files when Fabrik governance files are modified
# Monitors /opt/fabrik governance files and triggers sync_enforcement_to_projects.py on changes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[enforcement-watcher]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[enforcement-watcher]${NC} $*"
}

# Check inotify-tools installed
if ! command -v inotifywait &>/dev/null; then
    warn "inotifywait not found. Installing inotify-tools..."
    sudo apt-get update && sudo apt-get install -y inotify-tools
fi

DEBOUNCE_SECS=5
DEBOUNCE_STAMP="/tmp/.fabrik-enforcement-watcher-last-run"

# Governance files to watch (from sync_enforcement_to_projects.py)
WATCH_FILES=(
    "${FABRIK_ROOT}/AGENTS.md"
    "${FABRIK_ROOT}/AGENTS-compact.md"
    "${FABRIK_ROOT}/CLAUDE.md"
    "${FABRIK_ROOT}/opencode.json"
    "${FABRIK_ROOT}/.windsurfrules"
)

# Watch entire .windsurf/rules directory
WATCH_DIRS=(
    "${FABRIK_ROOT}/.windsurf/rules"
)

# Core scripts to watch
WATCH_SCRIPTS=(
    "${FABRIK_ROOT}/scripts/final_gate.py"
    "${FABRIK_ROOT}/scripts/kilo_code_review.py"
    "${FABRIK_ROOT}/scripts/kilo_docs_enforcer.py"
    "${FABRIK_ROOT}/scripts/docs_updater.py"
    "${FABRIK_ROOT}/scripts/update_agents_toc.py"
    "${FABRIK_ROOT}/scripts/health_checker.py"
    "${FABRIK_ROOT}/scripts/rund"
    "${FABRIK_ROOT}/scripts/rundsh"
    "${FABRIK_ROOT}/scripts/runc"
    "${FABRIK_ROOT}/scripts/runk"
    "${FABRIK_ROOT}/scripts/runls"
    "${FABRIK_ROOT}/scripts/runlast"
    "${FABRIK_ROOT}/scripts/runwait"
    "${FABRIK_ROOT}/scripts/runtail"
    "${FABRIK_ROOT}/scripts/runclean"
    "${FABRIK_ROOT}/scripts/sync_cascade_backup.sh"
    "${FABRIK_ROOT}/scripts/sync_extensions.sh"
)

# Reference docs to watch
WATCH_DOCS=(
    "${FABRIK_ROOT}/docs/reference/windsurf/cascade-models.md"
    "${FABRIK_ROOT}/docs/reference/long-command-monitoring.md"
)

# Build inotifywait command
INOTIFY_ARGS=(-m -e modify,create,close_write,delete,move --format '%w%f')

# Add files
for file in "${WATCH_FILES[@]}"; do
    if [ -f "$file" ]; then
        INOTIFY_ARGS+=("$file")
    fi
done

# Add directories (recursive)
for dir in "${WATCH_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        INOTIFY_ARGS+=(-r "$dir")
    fi
done

# Add scripts
for script in "${WATCH_SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        INOTIFY_ARGS+=("$script")
    fi
done

# Add docs
for doc in "${WATCH_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        INOTIFY_ARGS+=("$doc")
    fi
done

if [ ${#INOTIFY_ARGS[@]} -le 3 ]; then
    warn "No governance files found to watch. Exiting."
    exit 0
fi

log "Watching Fabrik governance files for changes..."
log "Press Ctrl+C to stop"

# Monitor governance files and trigger sync on changes
inotifywait "${INOTIFY_ARGS[@]}" 2>/dev/null | while read -r changed_file; do
    # Debounce: skip if last sync was less than DEBOUNCE_SECS ago
    if [ -f "$DEBOUNCE_STAMP" ]; then
        LAST_AGE=$(( $(date +%s) - $(stat -c %Y "$DEBOUNCE_STAMP") ))
        if [ "$LAST_AGE" -lt "$DEBOUNCE_SECS" ]; then
            continue
        fi
    fi
    touch "$DEBOUNCE_STAMP"

    log "Detected change: $changed_file"
    log "Running sync_enforcement_to_projects.py..."

    if python3 "${FABRIK_ROOT}/scripts/sync_enforcement_to_projects.py"; then
        log "✅ Enforcement sync complete"
    else
        warn "❌ sync_enforcement_to_projects.py failed"
    fi
done
