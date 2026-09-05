#!/usr/bin/env bash
# dr_env_backup.sh — DR mirror of credential files to private GitHub repo.
#
# Part of W9 of the 2026-05-31 fleet-hardening plan. Runs three ways:
#   1. inotifywait close-write trigger (fabrik-dr-watcher.service) — change-driven
#   2. Daily cron (30 3 * * *) — safety net
#   3. @reboot cron (sleep 60 && ...) — catch up after WSL boots
#
# Credential sources mirrored:
#   - /opt/fabrik/.env                          (local; dev-WSL is canonical source)
#   - vps:/opt/fabrik/.env.sysadmin             (vps1-only; SSH-pull, added 2026-06-01 deep-review)
#   - vps2:/opt/backrest/.env                   (vps2 Backrest B2 creds; W11, 2026-06-01)
#   - vps2:/opt/backrest/.restic-password       (vps2 restic password — Lesson 67: without this, vps2 backups unreadable)
#   - vps3:/opt/backrest/.env                   (vps3 Backrest B2 creds; W11)
#   - vps3:/opt/backrest/.restic-password       (vps3 restic password — Lesson 67)
#
# B6 fix from v3.4 external-AI review: only commit when CONTENT changed
# (cmp -s), so a no-op trigger doesn't create a noise commit. Timestamped
# snapshot only written alongside a real change.
#
# Recovery: see docs/operations/credential-recovery.md
set -euo pipefail

REPO="${REPO:-/opt/fabrik-dr-store}"
ENV_PATH="${ENV_PATH:-/opt/fabrik/.env}"
SYSADMIN_REMOTE_HOST="${SYSADMIN_REMOTE_HOST:-vps}"
SYSADMIN_REMOTE_PATH="${SYSADMIN_REMOTE_PATH:-/opt/fabrik/.env.sysadmin}"
SPOKE_HOSTS=( ${SPOKE_HOSTS:-vps2 vps3} )
SPOKE_BACKREST_ENV="${SPOKE_BACKREST_ENV:-/opt/backrest/.env}"
SPOKE_RESTIC_PASSWORD="${SPOKE_RESTIC_PASSWORD:-/opt/backrest/.restic-password}"
TS=$(date -u +%Y%m%dT%H%M%SZ)

[ -d "$REPO/.git" ] || { echo "$(date -u +%FT%TZ) FAIL: $REPO is not a git repo"; exit 1; }
mkdir -p "$REPO/env"

CHANGED=0

# Mirror one file: source -> $REPO/env/$latest_name (+ timestamped snapshot).
# Rotates snapshots: retain last 60, older history stays in git.
# Sets CHANGED=1 on real diff.
mirror_one() {
  local src="$1" latest_name="$2" snapshot_prefix="$3"
  if [ -f "$REPO/env/$latest_name" ] && cmp -s "$src" "$REPO/env/$latest_name"; then
    return 0
  fi
  cp "$src" "$REPO/env/$latest_name"
  cp "$src" "$REPO/env/${snapshot_prefix}-${TS}"
  ls -1t "$REPO/env/${snapshot_prefix}-"* 2>/dev/null | tail -n +61 | xargs -r rm -f
  CHANGED=1
}

# SSH-pull a remote file via sudo cat into a temp file, then mirror.
# Soft-required: failure logs WARN, does not abort.
ssh_pull_and_mirror() {
  local host="$1" remote_path="$2" latest_name="$3" snapshot_prefix="$4"
  local tmp
  tmp=$(mktemp /tmp/dr-pull.XXXXXX)
  if ssh -o BatchMode=yes -o ConnectTimeout=8 "$host" \
         "sudo cat $remote_path" > "$tmp" 2>/dev/null && [ -s "$tmp" ]; then
    mirror_one "$tmp" "$latest_name" "$snapshot_prefix"
    rm -f "$tmp"
  else
    rm -f "$tmp"
    echo "$(date -u +%FT%TZ) WARN: could not pull $host:$remote_path (unreachable or sudo failed) — continuing"
  fi
}

# --- 1. Main env (local file, hard-required) ---
[ -f "$ENV_PATH" ] || { echo "$(date -u +%FT%TZ) FAIL: $ENV_PATH missing"; exit 1; }
mirror_one "$ENV_PATH" latest fabrik-env

# --- 2. Sysadmin env (vps1-only, soft-optional) ---
ssh_pull_and_mirror "$SYSADMIN_REMOTE_HOST" "$SYSADMIN_REMOTE_PATH" \
                    sysadmin-latest fabrik-env-sysadmin

# --- 3. Spoke Backrest creds (vps2 + vps3 each contribute 2 files) ---
# Per-spoke restic passwords are INDEPENDENT (compromise of one doesn't read others).
# Without these in the DR store, the spoke's backups become permanently unreadable on
# disk loss — same Lesson 67 risk as vps1's BACKREST_RESTIC_PASSWORD.
for spoke in "${SPOKE_HOSTS[@]}"; do
    ssh_pull_and_mirror "$spoke" "$SPOKE_BACKREST_ENV" \
                        "${spoke}-backrest-env-latest" "fabrik-env-${spoke}-backrest"
    ssh_pull_and_mirror "$spoke" "$SPOKE_RESTIC_PASSWORD" \
                        "${spoke}-restic-password-latest" "fabrik-${spoke}-restic-password"
done

if [ "$CHANGED" = "0" ]; then
  echo "$(date -u +%FT%TZ) no change"
  exit 0
fi

cd "$REPO"
DR_PATHS="env/"  # the ONE list both the add and the commit pathspec read (D-129)
git add -- "$DR_PATHS"
# PATHSPEC, never a bare commit: a bare `git commit` takes the WHOLE index (fleet 01M1QB46 —
# update_vps_docs.py shipped a sibling's staged files that way, 5b9c420d). The store is a dedicated
# repo today; the discipline is the same everywhere a script commits.
git commit -m "dr-env: ${TS}" -- "$DR_PATHS" >/dev/null
git push origin main >/dev/null 2>&1
echo "$(date -u +%FT%TZ) OK: pushed ${TS}"
