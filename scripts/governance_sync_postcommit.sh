#!/usr/bin/env bash
# AFTER-EDIT: .pre-commit-config.yaml (the governance-sync hook entry + its files: regex), CLAUDE.md § Sync-consciousness
#
# POST-COMMIT governance-sync dispatcher (operator decision 2026-08-29).
#
# WHY post-commit: as a pre-commit hook the sync was the slowest hook (~30s x 47 repos), which made
# it the widest window for pre-commit's tree-delta detection to catch an UNRELATED concurrent
# writer (a live session regenerating .windsurf/rules/ai blocks) — aborting rules commits with
# "files were modified by this hook" while the sync itself had already succeeded (two sessions hit
# it on 2026-08-29; measured: the sync writes NOTHING inside /opt/fabrik). Post-commit cannot abort
# a commit and has no stash window; distribution still happens at commit time.
#
# WHY this wrapper exists: MEASURED 2026-08-29 in a scratch repo — at the post-commit stage
# pre-commit passes NO file list, so a `files:`-filtered hook is ALWAYS "(no files to check)
# Skipped". A naive stage move silently disables the sync fleet-wide. So the hook runs
# `always_run: true` and THIS script re-implements the filter against HEAD's own paths — reading
# the regex FROM .pre-commit-config.yaml's governance-sync `files:` key, so the trigger set stays
# single-sourced where CLAUDE.md § Sync-consciousness says it lives.
# ⚠️ `pipefail` is LOAD-BEARING, not hygiene. The sync below is `python … | tail -3 || { echo
# "SYNC FAILED"; exit 1; }`, and without pipefail the `||` tests TAIL's status, which is always 0 —
# so the failure branch was UNREACHABLE and a sync that died on repo 12 of 48 exited 0 with no
# warning and no re-run command, while CLAUDE.md § Sync-consciousness promises it "prints loudly".
# Probed 2026-09-01: `set -u; (exit 3) | tail -3 || echo TAKEN` prints nothing, rc=0.
set -uo pipefail

[ "$(pwd)" = "/opt/fabrik" ] || exit 0  # never from a worktree (the renderer-prune class)

FILTER="$(/opt/fabrik/.venv/bin/python - <<'PY'
import yaml
cfg = yaml.safe_load(open("/opt/fabrik/.pre-commit-config.yaml"))
for repo in cfg.get("repos", []):
    for hook in repo.get("hooks", []):
        if hook.get("id") == "governance-sync":
            print(hook.get("files", ""))
            raise SystemExit(0)
raise SystemExit(1)
PY
)" || { echo "[governance-sync post-commit] cannot read the files: filter from .pre-commit-config.yaml — SYNC NOT RUN; run scripts/sync_enforcement_to_projects.py --force yourself"; exit 1; }

# HEAD's own paths (first-parent view — on this shared box a merged-in trigger commit was already
# synced when ITS author committed it).
if git log -1 --format= --name-only | grep -qE "$FILTER"; then
  /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sync_enforcement_to_projects.py --force 2>&1 | tail -3 \
    || { echo "[governance-sync post-commit] SYNC FAILED — the commit landed but did NOT distribute; run scripts/sync_enforcement_to_projects.py --force"; exit 1; }
fi
exit 0
