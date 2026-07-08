#!/usr/bin/env bash
# AFTER-EDIT: scripts/sysadmin/test_sync_accounts.py, docs/CONFIGURATION.md
#
# WSL → fleet Claude-account credential sync. Runs on the operator's WSL box and pushes
# every local manager-account snapshot (~/.claude/manager-accounts/*/.credentials.json)
# plus the active ~/.claude/.credentials.json to each VPS — so a quota rotation on any
# host lands on a still-valid account. (Only the *active* account self-refreshes; idle
# standby snapshots go stale on a host with no claude-manager, which silently broke the
# fleet.)
#
# N-host + N-account by design:
#   - Accounts are discovered by glob → a new `can-*` snapshot is picked up automatically.
#   - Hosts come from CLAUDE_FLEET_HOSTS (space-separated) → add a new VPS by extending it.
#
# Security: creds copied with `scp -p` (source 0600 preserved) + an explicit remote
# `chmod 600`; account dir names are charset-validated before being interpolated into a
# remote command (defense-in-depth against a hostile snapshot name); NO token bytes are
# ever echoed or logged (only host + account-dir names). All remote paths are
# $HOME-relative (ssh + scp both default to the remote home) — no ~ vs cwd divergence.
#
# Usage:
#   scripts/sysadmin/sync-claude-accounts-to-fleet.sh                    # sync all hosts
#   DRY_RUN=1 scripts/sysadmin/sync-claude-accounts-to-fleet.sh          # print, touch nothing
#   CLAUDE_FLEET_HOSTS="vps vps2 vps3 vps4" scripts/.../sync-...sh       # add a 4th host
set -uo pipefail

HOSTS="${CLAUDE_FLEET_HOSTS:-vps vps2 vps3}"
# NON-root: creds live in ~ozgur/.claude, and root SSH after bootstrap trips fail2ban (AFCL).
SSH_USER="${CLAUDE_FLEET_SSH_USER:-ozgur}"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
ACCOUNTS_DIR="$CLAUDE_DIR/manager-accounts"
LOG="${CLAUDE_FLEET_SYNC_LOG:-$HOME/.cache/claude-fleet-sync.log}"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "$(dirname "$LOG")"
log() { echo "$(date -Is) $*" | tee -a "$LOG" >&2; }
run() { if [ "$DRY_RUN" = "1" ]; then echo "DRY_RUN: $*"; else "$@"; fi; }

# Parse hosts into an array. A whitespace-only value must NOT silently sync zero hosts.
read -ra host_arr <<<"$HOSTS"
if [ ${#host_arr[@]} -eq 0 ]; then
    log "ERROR: CLAUDE_FLEET_HOSTS is empty — nothing to sync"
    exit 1
fi

# Discover local snapshot dirs. Only accept safe names — the name is interpolated into a
# remote shell command, so a name with shell metacharacters is skipped (defense-in-depth;
# real account dirs look like `mob-ocoron-com-s-organization`).
shopt -s nullglob
snapshots=()
for d in "$ACCOUNTS_DIR"/*/; do
    [ -f "${d}.credentials.json" ] || continue
    name="$(basename "$d")"
    if [[ ! "$name" =~ ^[A-Za-z0-9._-]+$ ]]; then
        log "WARN: skipping account dir with unsafe name: ${name}"
        continue
    fi
    snapshots+=("$name")
done
shopt -u nullglob

if [ ${#snapshots[@]} -eq 0 ]; then
    log "ERROR: no valid account snapshots under $ACCOUNTS_DIR — capture accounts via claude-manager first"
    exit 1
fi
log "syncing ${#snapshots[@]} account(s) [${snapshots[*]}] to ${#host_arr[@]} host(s): ${host_arr[*]}"

rc=0
for host in "${host_arr[@]}"; do
    dest="$SSH_USER@$host"

    # 1. Ensure remote manager-account dirs exist (bootstrap creates none). Home-relative;
    #    a single command string the remote shell runs — no nested $()/quotes (AFCL trap).
    remote_mkdirs="mkdir -p .claude/manager-accounts"
    for name in "${snapshots[@]}"; do
        remote_mkdirs+=" .claude/manager-accounts/${name}"
    done
    if ! run ssh "$dest" "$remote_mkdirs"; then
        log "ERROR: ${host} — remote mkdir failed (skipping host)"; rc=1; continue
    fi

    host_ok=1
    # 2. Push each account snapshot (scp -p preserves the source 0600).
    for name in "${snapshots[@]}"; do
        if ! run scp -pq "$ACCOUNTS_DIR/$name/.credentials.json" \
                "$dest:.claude/manager-accounts/$name/.credentials.json"; then
            log "ERROR: ${host} — scp of snapshot ${name} failed"; host_ok=0; rc=1
        fi
    done

    # 3. Refresh the remote active account to match the local active one.
    if [ -f "$CLAUDE_DIR/.credentials.json" ]; then
        if ! run scp -pq "$CLAUDE_DIR/.credentials.json" "$dest:.claude/.credentials.json"; then
            log "ERROR: ${host} — scp of active creds failed"; host_ok=0; rc=1
        fi
    fi

    # 4. Belt-and-suspenders chmod (scp -p already set 0600). Surface a failure as a WARN —
    #    do NOT swallow it and still claim OK.
    if ! run ssh "$dest" "chmod 600 .claude/.credentials.json .claude/manager-accounts/*/.credentials.json"; then
        log "WARN: ${host} — remote chmod belt-step failed (scp -p already set 0600)"
    fi

    [ "$host_ok" = "1" ] && log "OK: ${host} synced ${#snapshots[@]} account(s)"
done
exit $rc
