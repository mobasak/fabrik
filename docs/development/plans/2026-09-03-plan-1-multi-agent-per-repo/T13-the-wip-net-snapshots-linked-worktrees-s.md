# T13 — The wip-net snapshots linked worktrees (spec residual R2)

## Scope
`scripts/wip_backup.sh:26` walks `"$ROOT"/*/` — a linked worktree under `<repo>/.claude/worktrees/<agent>` is inside the repo dir but is its own working tree with its own index and dirt, and the loop never visits it (the `-e` test at `:28` only tolerates a worktree's `.git` FILE when the loop happens to land on one). Add, per visited repo, an inner loop over `git worktree list --porcelain` entries whose path is under `<repo>/.claude/worktrees/`: snapshot each dirty worktree with the same isolated-index recipe (`:46-56`) into **`refs/wip/wt-<name>-<UTC-timestamp>`**. The timestamp suffix is load-bearing: the existing prune at `:35` globs `refs/wip/bak-*` and parses the time out of the ref NAME (`t="${ref#refs/wip/bak-}"`), so a bare `refs/wip/wt-beta` would match no glob and carry no time to compare — it would never expire. Widen the prune to sweep `refs/wip/wt-*` under the same `KEEP_DAYS` cutoff, stripping the `wt-<name>-` prefix before the comparison. ⚠️ **Placement:** the inner worktree loop goes ABOVE `:40` `[ -n "$(git status --porcelain …)" ] || continue`, which skips the rest of the repo body when the MAIN tree is clean — placed below it, this ticket's own test case (a dirty worktree in an otherwise clean repo) would never execute. A clean, locked or missing worktree is skipped without aborting the repo loop. Watched-red test in `tests/test_wip_backup.py`: a scratch repo with one dirty linked worktree — before the change no `refs/wip/wt-*` exists after a run; after, one does, and the main tree's own snapshot is unchanged. DO-NOT: change the main-tree snapshot semantics or `KEEP_DAYS`.

Depends: —
Parallel: ⚡
Complexity: complex
Gate: python -m pytest tests/test_wip_backup.py -q
Docs: docs/workstation/hooks-index.md is NOT touched (T02 owns it); the wip-net's own doc row lives in docs/reference (T15) · CHANGELOG.md — orchestrator-applied

## Touches
- scripts/wip_backup.sh — PRIMARY PATH
- tests/test_wip_backup.py

## Behavior Contract
- **Given** a repo with a dirty linked worktree at `.claude/worktrees/beta`, **When** `wip_backup.sh` runs, **Then** a ref matching `refs/wip/wt-beta-*` exists and its tree holds the worktree's uncommitted change, even though the MAIN tree is clean (scripts/wip_backup.sh:40)
- **Given** the same repo with the worktree clean, **When** the script runs, **Then** no `refs/wip/wt-beta-*` ref is created and the main snapshot is byte-identical to a run without the worktree (scripts/wip_backup.sh:40)
- **Given** a worktree whose directory was deleted without `git worktree prune`, **When** the script runs, **Then** it skips that entry, logs one line, and still snapshots the repo's main tree (scripts/wip_backup.sh:28)
- **Given** a `refs/wip/wt-<name>-<ts>` ref older than `KEEP_DAYS` and one inside the window, **When** the script runs, **Then** the widened prune deletes the old one and keeps the recent one (scripts/wip_backup.sh:35)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/10-python.md
