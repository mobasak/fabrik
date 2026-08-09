#!/usr/bin/env bash
# WIP safety net: snapshot every dirty /opt git repo's ENTIRE working tree
# (staged + unstaged + untracked) into refs/wip/autobackup and push it to
# origin. Uses an ISOLATED index — never touches the real index, HEAD, stash
# list, or any branch, so concurrent agents are completely unaffected.
#
# Recovery (any repo):
#   git log refs/wip/autobackup            # see what/when
#   git checkout refs/wip/autobackup -- <path>     # restore one file
#   git cherry-pick -n refs/wip/autobackup         # restore everything as WIP
# Point-in-time: dated local refs refs/wip/bak-<UTC-ts> are kept 7 days.
#
# Cron: */15 * * * *  flock -n /tmp/wip-backup.lock /opt/fabrik/scripts/wip_backup.sh
set -u

KEEP_DAYS=7
LOG_PREFIX="[wip-backup]"
ROOT="${WIP_BACKUP_ROOT:-/opt}"

# Bound the cron log (append-only otherwise; review finding).
_wlog="/tmp/wip-backup.log"
if [ "$(stat -c %s "$_wlog" 2>/dev/null || echo 0)" -gt 1048576 ]; then
    tail -c 262144 "$_wlog" > "$_wlog.tmp" 2>/dev/null && mv "$_wlog.tmp" "$_wlog" 2>/dev/null || true
fi

for repo in "$ROOT"/*/; do
    repo="${repo%/}"
    [ -e "$repo/.git" ] || continue   # -e not -d: linked WORKTREES have a .git FILE (review finding)
    case "$repo" in */archived|*/archived/*) continue ;; esac

    cd "$repo" || continue
    # Prune dated refs older than KEEP_DAYS — for EVERY visited repo (a repo
    # that went clean must still expire its old snapshots; review finding).
    cutoff="$(date -u -d "-${KEEP_DAYS} days" +%Y%m%dT%H%M%SZ)"
    git for-each-ref --format='%(refname)' 'refs/wip/bak-*' 2>/dev/null | while read -r ref; do
        t="${ref#refs/wip/bak-}"
        [ "$t" \< "$cutoff" ] && git update-ref -d "$ref" 2>/dev/null
    done
    # Anything to protect?
    [ -n "$(git status --porcelain 2>/dev/null)" ] || continue

    ts="$(date -u +%Y%m%dT%H%M%SZ)"
    tmp_index="$(mktemp "/tmp/wip-index-$(basename "$repo").XXXXXX")"
    rm -f "$tmp_index"   # git wants to create it

    # Isolated index SEEDED FROM HEAD, then add -A: tracked-but-gitignored
    # files stay present (an empty index + add -A applied ignore rules to them
    # and recorded DELETIONS — the documented recovery then deleted the files;
    # review finding, /opt/proxy carries 1342 such files).
    if ! GIT_INDEX_FILE="$tmp_index" git read-tree HEAD 2>/dev/null \
       || ! GIT_INDEX_FILE="$tmp_index" git add -A 2>/dev/null; then
        rm -f "$tmp_index"; continue
    fi
    tree="$(GIT_INDEX_FILE="$tmp_index" git write-tree 2>/dev/null)"
    rm -f "$tmp_index"
    [ -n "$tree" ] || continue

    head="$(git rev-parse HEAD 2>/dev/null)" || continue
    # Skip if identical to the previous snapshot (dirty but unchanged since).
    prev="$(git rev-parse -q --verify refs/wip/autobackup^{tree} 2>/dev/null || true)"
    [ "$tree" = "$prev" ] && continue

    commit="$(git commit-tree "$tree" -p "$head" -m "wip-backup $ts (automatic safety snapshot; not a work commit)" 2>/dev/null)"
    [ -n "$commit" ] || continue

    git update-ref "refs/wip/autobackup" "$commit"
    git update-ref "refs/wip/bak-$ts" "$commit"

    # Off-box: push the rolling ref (force — it's a backup ref, never a branch).
    if git remote get-url origin >/dev/null 2>&1; then
        git push -q --force origin "refs/wip/autobackup:refs/wip/autobackup" 2>/dev/null \
            || echo "$LOG_PREFIX push failed for $repo (offline/auth?) — local snapshot kept"
    fi

    echo "$LOG_PREFIX $repo snapshotted ($commit)"
done
exit 0
