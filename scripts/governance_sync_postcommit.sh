#!/usr/bin/env bash
# AFTER-EDIT: .pre-commit-config.yaml (the governance-sync hook entry + its files: regex), CLAUDE.md § Sync-consciousness
#
# POST-COMMIT (and POST-MERGE) governance-sync dispatcher (operator decision 2026-08-29).
#
# WHY post-commit: as a pre-commit hook the sync was the slowest hook (~30s x 47 repos), which made
# it the widest window for pre-commit's tree-delta detection to catch an UNRELATED concurrent
# writer (a live session regenerating .windsurf/rules/ai blocks) — aborting rules commits with
# "files were modified by this hook" while the sync itself had already succeeded (two sessions hit
# it on 2026-08-29; the sync writes NOTHING inside /opt/fabrik). It runs as a PLAIN git hook
# (scripts/install_post_commit_hook.sh), never pre-commit's post-commit stage, whose stash reverts siblings' edits (D-369).
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
#
# ⚠️ WHAT SYNCS AND WHAT DOES NOT, in the main checkout (/opt/fabrik) only — a worktree syncs nothing:
#   SYNCS   — `git commit` (post-commit, incl. a conflicted merge or a squash concluded by `git commit`);
#             `git merge`, fast-forward or `--no-ff`, and a merging `git pull` (post-merge).
#   DOES NOT — `git pull --rebase`, `git rebase <branch>`, `git reset --hard <branch>` and any plumbing
#             (`commit-tree`/`update-ref`): git fires no hook for the commits they bring in (a rebase
#             fires post-commit only for each LOCAL commit it replays), so
#             trigger paths they bring in are NOT distributed. The hub's flow is `git merge --no-ff` by
#             the merge owner, so no post-rewrite hook exists by design. After any of those, run
#             `scripts/sync_enforcement_to_projects.py --force` yourself.
set -uo pipefail

[ "$(pwd)" = "/opt/fabrik" ] || exit 0  # never from a worktree (the renderer-prune class)

# MODE: `post-commit` (the default — the post-commit hook passes nothing) or `post-merge` (the
# post-merge hook passes it). A worktree commit syncs nothing (the guard above), so a governance-sync
# path reaches the fleet only when it is MERGED into this checkout — and `git merge`, fast-forward or
# `--no-ff`, fires no post-commit hook. The post-merge hook is that path (spec
# 2026-09-29-hub-worktree-cutover-design § D3 (b)).
MODE="${1:-post-commit}"
case "$MODE" in
  post-commit|post-merge) ;;
  *) echo "[governance-sync] unknown mode '$MODE' — SYNC NOT RUN; run scripts/sync_enforcement_to_projects.py --force yourself"; exit 1 ;;
esac

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
)" || { echo "[governance-sync $MODE] cannot read the files: filter from .pre-commit-config.yaml — SYNC NOT RUN; run scripts/sync_enforcement_to_projects.py --force yourself"; exit 1; }

# ⚠️ An EMPTY filter is fail-OPEN, so refuse it explicitly: the heredoc prints `hook.get("files","")`
# and exits 0, so a governance-sync hook that merely LOST its `files:` key yields FILTER="" — which
# `grep -qE ""` matches on every line, silently syncing on every commit and defeating the
# single-sourcing contract this block exists to uphold. The `||` above cannot see it (exit was 0).
[ -n "$FILTER" ] || { echo "[governance-sync $MODE] the governance-sync files: filter is EMPTY — refusing to treat every commit as a trigger; fix .pre-commit-config.yaml"; exit 1; }

# The paths to test: HEAD's own first-parent diff (post-commit), or everything the merge brought in
# (post-merge — commits made in a worktree synced nothing when their author made them).
#
# ⚠️ NO PIPELINE HERE, and it must stay that way now that `pipefail` is on. `git log … | grep -qE`
# is a SIGPIPE trap: `grep -q` exits at the FIRST match and closes the pipe, so git dies with 141,
# and under pipefail the PIPELINE reports 141 — the `if` goes FALSE and the sync is SKIPPED on
# exactly the commit that DID touch a trigger path. Measured 2026-09-01 with the real filter:
# 0/20 nonzero at 500 changed files, 2/20 at 1000, 20/20 at 2000. Latent on ordinary commits (max
# 36 files across the last 400 hub commits) and certain on a bulk rename, an archive move or a
# scaffold-wide regeneration — i.e. it fails exactly when the blast radius is widest. Capturing
# first and matching a here-string keeps pipefail AND removes the pipe.
# ⚠️ `--first-parent` is REQUIRED, not decorative. Without it `git log -1 --name-only` on a MERGE
# commit suppresses the diff entirely and emits NOTHING — so every merge that carried a trigger
# path silently skipped the sync, while this very comment claimed a "first-parent view" the flag
# was never there to provide. The old justification ("a merged-in trigger commit was already
# synced when ITS author committed it") does not cover a merge that RESOLVES A CONFLICT in a
# trigger file: that blob exists in no parent, was never synced by anyone, and never would be.
# Probed 2026-09-01 on a scratch repo: plain `--name-only` on a merge -> empty; with
# `--first-parent` -> the changed paths.
# ⚠️ And the capture needs its own failure branch. Every other step here fails LOUD (FILTER has
# one, SYNC has one); an unchecked `NAMES=` would fail SILENT-SKIP on a corrupt index or unborn
# HEAD — the exact shape this script exists to make impossible.
# post-merge reads every path the merge BROUGHT IN — `ORIG_HEAD..HEAD`, which git sets before a
# fast-forward and a `--no-ff` merge alike — not HEAD's first-parent diff: a fast-forward's HEAD is the
# branch tip, whose own diff misses a trigger path touched by any commit below it. A `--squash` leaves
# ORIG_HEAD == HEAD (nothing listed); the squash is committed later and reaches post-commit. A conflicted
# merge concluded by `git commit` reaches post-commit too, whose first-parent read already lists it.
# ⚠️ `--no-renames` on BOTH reads: with rename detection (git's default) a move lists only its
# DESTINATION, so moving a file OUT of a trigger path read as a non-trigger change and the fleet kept
# the stale copy. Without it a move lists both the deleted source and the added destination.
if [ "$MODE" = post-merge ]; then
  NAMES="$(git diff --no-renames --name-only ORIG_HEAD HEAD)" \
    || { echo "[governance-sync post-merge] cannot read the merged paths (ORIG_HEAD..HEAD) — SYNC NOT RUN; run scripts/sync_enforcement_to_projects.py --force yourself"; exit 1; }
else
  NAMES="$(git log -1 --first-parent --no-renames --format= --name-only)" \
    || { echo "[governance-sync post-commit] cannot read HEAD's paths — SYNC NOT RUN; run scripts/sync_enforcement_to_projects.py --force yourself"; exit 1; }
fi
if grep -qE "$FILTER" <<<"$NAMES"; then
  # SYNC_CMD exists so the fail-loud branch below is TESTABLE — a fail-open path that no test can
  # exercise is how the unreachable `||` shipped in the first place.
  # ⚠️ It is honoured ONLY under an explicit test sentinel. A bare `${SYNC_CMD:-…}` would let any
  # exported variable in an operator's shell silently REPLACE the fleet-wide sync on every commit,
  # from inside a git hook — a much worse footgun than the untestable branch it was added to fix.
  SYNC="/opt/fabrik/.venv/bin/python /opt/fabrik/scripts/sync_enforcement_to_projects.py --force"
  if [ "${GOVERNANCE_SYNC_TEST:-}" = "1" ] && [ -n "${SYNC_CMD:-}" ]; then
    SYNC="$SYNC_CMD"
  fi
  # Intentionally unquoted: $SYNC is a command line that must word-split.
  # shellcheck disable=SC2086
  $SYNC 2>&1 | tail -3 \
    || { echo "[governance-sync $MODE] SYNC FAILED — the ${MODE#post-} landed but did NOT distribute; run scripts/sync_enforcement_to_projects.py --force"; exit 1; }
fi
exit 0
