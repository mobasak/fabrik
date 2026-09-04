# T13 — The wip-net snapshots linked worktrees (spec residual R2)

## Scope
`scripts/wip_backup.sh:26` walks `"$ROOT"/*/` — a linked worktree under `<repo>/.claude/worktrees/<agent>` is inside the repo dir but is its own working tree with its own index and dirt, and the loop never visits it (the `-e` test at `:28` only tolerates a worktree's `.git` FILE when the loop happens to land on one). Add, per visited repo, an inner loop over `git worktree list --porcelain` entries whose path is under `<repo>/.claude/worktrees/`: snapshot each dirty worktree with the same isolated-index recipe (`:46-56`) into `refs/wip/wt-<name>` (dated ref beside `refs/wip/bak-*`, pruned by the same `KEEP_DAYS` rule at `:34-38`), pushed with the repo's other refs; a clean, locked or missing worktree is skipped without aborting the repo loop. Watched-red test in `tests/test_wip_backup.py`: a scratch repo with one dirty linked worktree — before the change no `refs/wip/wt-*` exists after a run; after, one does, and the main tree's own snapshot is unchanged. DO-NOT: change the main-tree snapshot semantics or `KEEP_DAYS`.

Depends: —
Parallel: ⚡
Complexity: complex
Gate: python -m pytest tests/test_wip_backup.py -q
Docs: docs/workstation/hooks-index.md is NOT touched (T02 owns it); the wip-net's own doc row lives in docs/reference (T15) · CHANGELOG.md — orchestrator-applied

## Touches
- scripts/wip_backup.sh — PRIMARY PATH
- tests/test_wip_backup.py

## Behavior Contract
- **Given** a repo with a dirty linked worktree at `.claude/worktrees/beta`, **When** `wip_backup.sh` runs, **Then** `refs/wip/wt-beta` exists and its tree contains the worktree's uncommitted change (scripts/wip_backup.sh:26)
- **Given** the same repo with the worktree clean, **When** the script runs, **Then** no `refs/wip/wt-beta` is created and the main snapshot is byte-identical to a run without the worktree (scripts/wip_backup.sh:41)
- **Given** a worktree whose directory was deleted without `git worktree prune`, **When** the script runs, **Then** it skips that entry, logs one line, and still snapshots the repo's main tree (scripts/wip_backup.sh:28)
- **Given** a `refs/wip/wt-*` ref older than `KEEP_DAYS`, **When** the script runs, **Then** the ref is deleted by the same prune loop (scripts/wip_backup.sh:34)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/10-python.md
