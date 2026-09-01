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

# ⚠️ An EMPTY filter is fail-OPEN, so refuse it explicitly: the heredoc prints `hook.get("files","")`
# and exits 0, so a governance-sync hook that merely LOST its `files:` key yields FILTER="" — which
# `grep -qE ""` matches on every line, silently syncing on every commit and defeating the
# single-sourcing contract this block exists to uphold. The `||` above cannot see it (exit was 0).
[ -n "$FILTER" ] || { echo "[governance-sync post-commit] the governance-sync files: filter is EMPTY — refusing to treat every commit as a trigger; fix .pre-commit-config.yaml"; exit 1; }

# HEAD's own paths (first-parent view — on this shared box a merged-in trigger commit was already
# synced when ITS author committed it).
#
# ⚠️ NO PIPELINE HERE, and it must stay that way now that `pipefail` is on. `git log … | grep -qE`
# is a SIGPIPE trap: `grep -q` exits at the FIRST match and closes the pipe, so git dies with 141,
# and under pipefail the PIPELINE reports 141 — the `if` goes FALSE and the sync is SKIPPED on
# exactly the commit that DID touch a trigger path. Measured 2026-09-01 with the real filter:
# 0/20 nonzero at 500 changed files, 2/20 at 1000, 20/20 at 2000. Latent on ordinary commits (max
# 36 files across the last 400 hub commits) and certain on a bulk rename, an archive move or a
# scaffold-wide regeneration — i.e. it fails exactly when the blast radius is widest. Capturing
# first and matching a here-string keeps pipefail AND removes the pipe.
NAMES="$(git log -1 --format= --name-only)"
if grep -qE "$FILTER" <<<"$NAMES"; then
  # SYNC_CMD exists so the fail-loud branch below is TESTABLE — a fail-open path that no test can
  # exercise is how the unreachable `||` shipped in the first place. Defaults to the real sync.
  ${SYNC_CMD:-/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sync_enforcement_to_projects.py --force} 2>&1 | tail -3 \
    || { echo "[governance-sync post-commit] SYNC FAILED — the commit landed but did NOT distribute; run scripts/sync_enforcement_to_projects.py --force"; exit 1; }
fi
exit 0
