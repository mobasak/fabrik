#!/usr/bin/env bash
# dr_env_recovery_test.sh — weekly DR self-test for the W9 chain.
#
# Reads the DR-mirrored /opt/fabrik-dr-store/env/latest (NOT the live
# /opt/fabrik/.env), extracts the restic + B2 credentials, and confirms they
# can read the B2 restic repo through Backrest's in-container restic
# (Lesson 68 + external-AI-review B1 fix — host-side restic is NOT installed
# on this WSL).
#
# State handling:
#   - restic snapshots succeeds with N >= 0 → OK, log "N snapshots readable"
#   - restic reports "repository does not exist" / "no such file" → pre-W2
#     state; DR pipeline is correctly configured but the repo hasn't been
#     init'd yet. Exit 0 with a "AWAITING-W2" message so weekly cron doesn't
#     fake a DR failure.
#   - Anything else (network, ssh down, wrong creds, malformed env) → FAIL
#     exit 1.
#
# Part of W9 of the 2026-05-31 fleet-hardening plan.
set -uo pipefail  # NOTE: not -e — we handle restic exit codes ourselves

LATEST="${LATEST:-/opt/fabrik-dr-store/env/latest}"
B2_REPO="${B2_REPO:-s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups}"
SSH_HOST="${SSH_HOST:-vps}"
TS=$(date -u +%FT%TZ)

err() { echo "$TS FAIL: $*" >&2; exit 1; }

# --- Precondition: DR snapshot present ---
[ -f "$LATEST" ] || err "no DR snapshot at $LATEST — has fabrik-dr-watcher.service or dr_env_backup.sh run?"

# --- Extract creds ---
RESTIC_PW=$(grep '^BACKREST_RESTIC_PASSWORD=' "$LATEST" | cut -d= -f2-)
B2_KEY=$(grep '^B2_KEY_ID=' "$LATEST" | cut -d= -f2-)
B2_SECRET=$(grep '^B2_APPLICATION_KEY=' "$LATEST" | cut -d= -f2-)

[ -n "$RESTIC_PW" ] || err "BACKREST_RESTIC_PASSWORD missing in $LATEST"
[ -n "$B2_KEY" ]    || err "B2_KEY_ID missing in $LATEST"
[ -n "$B2_SECRET" ] || err "B2_APPLICATION_KEY missing in $LATEST"

# --- Probe restic via Backrest container on vps1 ---
# B1 fix: restic isn't on this WSL; we route through `sudo docker exec backrest /bin/restic`.
OUTPUT=$(ssh -o ConnectTimeout=10 "$SSH_HOST" "sudo docker exec \
  -e RESTIC_PASSWORD='${RESTIC_PW}' \
  -e AWS_ACCESS_KEY_ID='${B2_KEY}' \
  -e AWS_SECRET_ACCESS_KEY='${B2_SECRET}' \
  backrest /bin/restic -r '${B2_REPO}' snapshots --json 2>&1")
RC=$?

if [ $RC -eq 0 ]; then
  COUNT=$(echo "$OUTPUT" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
  echo "$TS OK: ${COUNT} snapshots readable with recovered creds"
  exit 0
fi

# --- Distinguish pre-W2 state from real failure ---
if echo "$OUTPUT" | grep -qiE "repository does not exist|specified key does not exist|no such file"; then
  echo "$TS AWAITING-W2: DR pipeline configured + creds valid; restic repo not yet init'd on B2 (run W2 to populate)"
  exit 0
fi

err "restic snapshots failed (rc=$RC): $(echo "$OUTPUT" | head -3)"
