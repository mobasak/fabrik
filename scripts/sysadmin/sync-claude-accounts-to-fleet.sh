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
#   scripts/sysadmin/sync-claude-accounts-to-fleet.sh                    # push SNAPSHOTS to all hosts (safe)
#   SYNC_ACTIVE=1 scripts/sysadmin/sync-claude-accounts-to-fleet.sh      # ALSO repoint each host's active
#                                                                        #   to the WSL active (backs up first)
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

# SYNC_ACTIVE=auto — GUARDED active-sync (the cure for the 2026-08-04 OAuth-exhaustion incidents).
# OAuth refresh tokens are single-use; when 4 boxes refresh the same 3 accounts they invalidate each
# other's copies, and the manager-account SNAPSHOTS this script pushes go stale within hours (they
# only update on a WSL account switch) — so snapshot-sync alone kept distributing dead creds. The
# durable shape is a SINGLE REFRESH OWNER: push the WSL *active* (in constant use → always fresh) to
# every host hourly, so VPS copies always hold a <1h-old token and never need to self-refresh.
# `auto` enables that ONLY when the WSL active verifiably IS a fleet account (its organizationUuid
# matches one of the snapshots) — a non-fleet / org-less account the operator happened to switch to
# is never propagated (the footgun the SYNC_ACTIVE=1 warning below describes).
if [ "${SYNC_ACTIVE:-0}" = "auto" ]; then
    # Posture: ALLOW unless PROVABLY foreign. Real fleet .credentials.json files often carry NO
    # organizationUuid (claude_rotate.py's own identity docstring: never rely on it), so requiring a
    # positive org match would block the cure on exactly the creds the fleet runs. Only the 3 fleet
    # accounts ever log in on this box; the guard's job is just to stop a PROVABLY different org.
    SYNC_ACTIVE=0
    if [ -f "$CLAUDE_DIR/.credentials.json" ]; then
        SYNC_ACTIVE=1
        active_org=$(CREDS_PATH="$CLAUDE_DIR/.credentials.json" python3 -c \
            "import json,os;print(json.load(open(os.environ['CREDS_PATH'])).get('organizationUuid') or '')" 2>/dev/null)
        if [ -n "$active_org" ]; then
            any_snap_org=0
            org_matched=0
            for name in "${snapshots[@]}"; do
                snap_org=$(CREDS_PATH="$ACCOUNTS_DIR/$name/.credentials.json" python3 -c \
                    "import json,os;print(json.load(open(os.environ['CREDS_PATH'])).get('organizationUuid') or '')" 2>/dev/null)
                [ -n "$snap_org" ] && any_snap_org=1
                if [ "$snap_org" = "$active_org" ]; then org_matched=1; break; fi
            done
            # Refuse ONLY on positive evidence of a foreign org: active has an org, at least one
            # snapshot has an org, and none of them match.
            if [ "$any_snap_org" = "1" ] && [ "$org_matched" = "0" ]; then
                SYNC_ACTIVE=0
            fi
        fi
    fi
    log "SYNC_ACTIVE=auto → ${SYNC_ACTIVE} (refuse only a PROVABLY-foreign active org)"
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

    # 3. OPTIONALLY repoint the remote ACTIVE account to the WSL box's active one. OFF by default
    #    (set SYNC_ACTIVE=1 to enable). Overwriting a host's active is a footgun for a routine
    #    "refresh the standbys" sync: the WSL active may be a non-fleet / org-less account the
    #    operator happened to switch to, so this would silently repoint all hosts' sysadmin identity;
    #    and it clobbers the host's own self-refreshed active token with the WSL's frozen (possibly
    #    staler) copy. Snapshots (Step 2) are always safe to push; the active is not. When enabled,
    #    back the host's outgoing active up first (a raw scp, unlike rotation, keeps no .prev).
    if [ "${SYNC_ACTIVE:-0}" = "1" ] && [ -f "$CLAUDE_DIR/.credentials.json" ]; then
        run ssh "$dest" "cp -p .claude/.credentials.json .claude/.credentials.json.sync-bak 2>/dev/null || true"
        if ! run scp -pq "$CLAUDE_DIR/.credentials.json" "$dest:.claude/.credentials.json"; then
            log "ERROR: ${host} — scp of active creds failed"; host_ok=0; rc=1
        fi
    fi

    # 4. Belt-and-suspenders: reinforce 0600 on every remote creds file. `scp -p` already
    #    carried the source mode and the local snapshots are 0600, so this is redundant.
    #    `find … -exec chmod` tolerates a host with no active-creds file yet (matches nothing
    #    → exit 0, no false failure); a genuine chmod error is surfaced as a non-fatal WARN
    #    (the sync itself already succeeded via scp -p, so it does not fail the host).
    if ! run ssh "$dest" "find .claude -maxdepth 3 -name .credentials.json -exec chmod 600 {} +"; then
        log "WARN: ${host} — remote chmod belt-step reported an error"
    fi

    [ "$host_ok" = "1" ] && log "OK: ${host} synced ${#snapshots[@]} account(s)"
done
exit $rc
