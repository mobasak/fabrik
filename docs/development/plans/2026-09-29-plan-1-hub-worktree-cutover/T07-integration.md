# T07 — Integration: the hub cut-over, whole-plan validation, receipt

## Scope
Implements spec § The delta D6 (the migration) and § Validation V1, V10, and owns the whole-plan receipt. The orchestrator, in the main checkout, after every ticket is merged: installs the post-merge hook (`bash scripts/install_post_commit_hook.sh`); renders the corpus from the main checkout (render → `--check` → commit); appends the `MERGE OWNER: infra` ledger row (a governance file, orchestrator-applied, id via `--reserve-id`); restores `libs/subagents/*` to HEAD once fabrik-lib confirms its re-vendor hook is removed (mail 01M3PTHG); messages fleet and intel to commit their work and `EnterWorktree` into `.claude/worktrees/fleet` and `.claude/worktrees/intel`, then copies the gitignored `.env` into each (`cp -p /opt/fabrik/.env .claude/worktrees/<name>/.env`) whether or not `.worktreeinclude` fired — the spec's U1 — since a gitignored copy is no ticket's file; hand-runs `bash scripts/governance_sync_postcommit.sh` after each plumbing commit on a sync path. Then runs V1 (the main checkout's `git status` lists only infra's and the pipeline's work, each worktree only its agent's) and V10, the whole-plan `final_gate.py --check --json`, `check_convergence.py`, `check_doc_sync.py --range` and `check_doc_stubs.py --range`, `/fabrik-docs-review`, and writes the receipt. DO-NOT: write any file a work ticket owns.

Depends: T06a, T06b, T06c
Parallel: ⛓️
Complexity: native
Integration: true
Gate: python scripts/final_gate.py --check --json
Docs: none (the receipt)

## Touches
- docs/development/reviews/2026-09-29-plan-1-hub-worktree-cutover-review.md

## Behavior Contract
- **Given** every ticket merged and fleet and intel moved, **When** `git status --porcelain` runs in `/opt/fabrik` and in each hub worktree, **Then** the main checkout lists no uncommitted path created by fleet or intel, and each worktree lists only its own agent's (spec § Validation V1)
- **Given** fleet's and intel's worktrees after the move, **When** each root is listed, **Then** `.env` is present (spec § Open / blocking unknowns U1)
- **Given** the cut-over, **When** `python3 scripts/decisions.py --merge-owner /opt/fabrik` runs, **Then** it prints `infra`; fabrik-lib's and trade-intelligence's ledgers each carry a row adopting the model (spec § Validation V7, V10)

## Context Files
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- docs/reference/multi-agent-operating-model.md
