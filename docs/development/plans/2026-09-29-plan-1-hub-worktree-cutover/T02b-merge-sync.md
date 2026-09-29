# T02b — Merges distribute governance

## Scope
Implements spec § The delta D3 (b) and V2. `scripts/governance_sync_postcommit.sh` gains a post-merge mode that computes the paths a merge brought in with `git diff --name-only ORIG_HEAD HEAD` instead of the first-parent read (`scripts/governance_sync_postcommit.sh:43-47`), keeping the `pwd` guard (`:26`) and the filter; `scripts/install_post_commit_hook.sh` installs a `post-merge` hook beside the post-commit one (`scripts/install_post_commit_hook.sh:26-28, :43`). DO-NOT: change the governance-sync filter regex or `sync_enforcement_to_projects.py`.

Depends: —
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/test_merge_sync.py -q
Docs: none (hooks-index row is T06b's)

## Touches
- scripts/governance_sync_postcommit.sh — PRIMARY PATH
- scripts/install_post_commit_hook.sh
- tests/test_merge_sync.py

## Behavior Contract
- **Given** a scratch repo with a branch whose NON-tip commit touches a path the filter matches, **When** that branch is merged by fast-forward and, separately, by `git merge --no-ff`, **Then** the post-merge mode reports that path as a trigger both times (spec § Validation V2)
- **Given** a commit made in a linked worktree, **When** the post-commit hook runs, **Then** nothing is distributed (spec § Validation V2)
- **Given** `install_post_commit_hook.sh` run in a scratch repo, **When** its hooks dir is listed, **Then** both `post-commit` and `post-merge` exist and each execs the sync script (spec § The delta D3)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- scripts/governance_sync_postcommit.sh
- scripts/install_post_commit_hook.sh
