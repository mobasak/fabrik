#!/usr/bin/env bash
# dr_env_watcher_loop.sh — long-running watcher driving dr_env_backup.sh.
#
# Watches the DIRECTORY /opt/fabrik/ (not the .env file directly) so that
# save-via-tempfile-rename editors (vim, sed -i, VSCode, etc.) are caught
# via moved_to in addition to close_write on direct appends. Filters output
# to only /opt/fabrik/.env so unrelated files don't trigger a push.
#
# Why dir-not-file: when an editor replaces .env by renaming a temp file
# over it, the inode behind the watch changes. A watch on the file is on
# the old (now orphaned) inode. A watch on the parent dir survives.
#
# 5s debounce collapses a rapid sequence of writes (e.g. an editor that
# touches the file multiple times during save) into one push.
#
# Invoked by fabrik-dr-watcher.service. Standalone for systemd-escape
# cleanliness — avoids all the %/\\ escaping headaches that come with
# putting this pipeline directly in ExecStart.
set -uo pipefail

WATCH_DIR="${WATCH_DIR:-/opt/fabrik}"
TARGET_PATH="${TARGET_PATH:-/opt/fabrik/.env}"
BACKUP_SCRIPT="${BACKUP_SCRIPT:-/opt/fabrik/scripts/dr_env_backup.sh}"
DEBOUNCE_SEC="${DEBOUNCE_SEC:-5}"

[ -d "$WATCH_DIR" ] || { echo "FAIL: $WATCH_DIR does not exist" >&2; exit 1; }
[ -x "$BACKUP_SCRIPT" ] || { echo "FAIL: $BACKUP_SCRIPT not executable" >&2; exit 1; }
command -v inotifywait >/dev/null || { echo "FAIL: inotifywait not installed" >&2; exit 1; }

echo "$(date -u +%FT%TZ) watcher starting: dir=$WATCH_DIR target=$TARGET_PATH debounce=${DEBOUNCE_SEC}s"

# Output one line per event in the form "<full-path> <event-mask>"
inotifywait -m -e close_write,moved_to --format '%w%f %e' "$WATCH_DIR" 2>&1 |
  while read -r path events; do
    # Only fire when the event affects our exact target file.
    [ "$path" = "$TARGET_PATH" ] || continue
    echo "$(date -u +%FT%TZ) event $events on $path"
    "$BACKUP_SCRIPT"
    sleep "$DEBOUNCE_SEC"
  done
