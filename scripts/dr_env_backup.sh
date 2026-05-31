#!/usr/bin/env bash
# dr_env_backup.sh — DR mirror of /opt/fabrik/.env to private GitHub repo.
#
# Part of W9 of the 2026-05-31 fleet-hardening plan. Runs three ways:
#   1. inotifywait close-write trigger (fabrik-dr-watcher.service) — change-driven
#   2. Daily cron (30 3 * * *) — safety net
#   3. @reboot cron (sleep 60 && ...) — catch up after WSL boots
#
# B6 fix from the v3.4 external-AI review: only commit when env CONTENT changed
# (cmp -s), so a no-op trigger doesn't create a noise commit. Timestamped copy
# only written alongside a real change.
#
# Recovery: see docs/operations/credential-recovery.md
set -euo pipefail

ENV_PATH="${ENV_PATH:-/opt/fabrik/.env}"
REPO="${REPO:-/opt/fabrik-dr-store}"
TS=$(date -u +%Y%m%dT%H%M%SZ)

# Preconditions
[ -f "$ENV_PATH" ] || { echo "$(date -u +%FT%TZ) FAIL: $ENV_PATH missing"; exit 1; }
[ -d "$REPO/.git" ] || { echo "$(date -u +%FT%TZ) FAIL: $REPO is not a git repo"; exit 1; }

mkdir -p "$REPO/env"

# B6: skip if content unchanged. cmp -s exits 0 on identical, 1 on differ.
if [ -f "$REPO/env/latest" ] && cmp -s "$ENV_PATH" "$REPO/env/latest"; then
  echo "$(date -u +%FT%TZ) no change"
  exit 0
fi

cp "$ENV_PATH" "$REPO/env/latest"
cp "$ENV_PATH" "$REPO/env/fabrik-env-${TS}"

# Retain last 60 timestamped snapshots; older history remains in git anyway.
ls -1t "$REPO/env/fabrik-env-"* 2>/dev/null | tail -n +61 | xargs -r rm -f

cd "$REPO"
git add env/
git commit -m "dr-env: ${TS}" >/dev/null
git push origin main >/dev/null 2>&1
echo "$(date -u +%FT%TZ) OK: pushed ${TS}"
