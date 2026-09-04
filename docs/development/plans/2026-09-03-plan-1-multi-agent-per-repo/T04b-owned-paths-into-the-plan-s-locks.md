# T04b — owned_paths into the plan's locks, and the live locks leave the tree

## Scope
Two source edits (spec § Chain consolidation (e), § Live locks). (1) `commands/_sources/fabrik-plan-after-chat.md` seeds the spine's `## File Scope (owned paths)` (`:581`) from the epic's frontmatter `owned_paths` when the plan was fed by an epic-born spec, and writes ONE header line `Epic: docs/development/epics/<file>` on the spine — the interface T05a enforces. (2) `commands/_sources/fabrik-execute-plan.md`: the lock reads/writes move from `.fabrik/plan-locks/<id>.json` (`:50,52,81,83,323,532,1007`) to `~/.claude/state/plan-locks/<repo-basename>/<id>.json` — the box-local pattern `scripts/command_run.py:87` and `scripts/thread_anchor.py:53` already use, keyed by the main-checkout basename `.claude/hooks/mail_notify.py:41-52` derives (`.fabrik/` is TRACKED, so a lock minted in one worktree is invisible in another until committed, and writing into the main checkout from a worktree is what the isolation enforcement blocks); the lock's `owned_paths` semantics at `:374` are unchanged; the dispatcher REFUSES a ticket whose Touches fall outside the spine's `Epic:` owned_paths; the merge target is the CURRENT branch (`git branch --show-current`), never a named default (audit R10); and the two-level worktree rule replaces the one-run "Don't nest a worktree" note (`:92-97`) — subagent worktrees nest inside an agent's worktree as ordinary git (`$GIT_COMMON_DIR` is shared). R6 probe as a WRITTEN step: in a scratch repo, `claude -p --worktree agent-alpha` with a brief that adds a nested worktree, commits in it and merges into `worktree-agent-alpha`; default if the enforcement blocks it — subagents dispatch on branches inside the agent's worktree. SPLIT NOTE: T04's other half is T04a (the read budget). DO-NOT: touch `fabrik-spec.md` (T04a) or any enforcement script (T05a/T05b).

Depends: —
Parallel: ⚡
Complexity: native
Gate: python3 commands/assemble_commands.py --check
Gate: python3 scripts/enforcement/check_command_corpus.py
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- commands/_sources/fabrik-plan-after-chat.md — PRIMARY PATH
- commands/_sources/fabrik-execute-plan.md

## Behavior Contract
- **Given** an epic-born spec, **When** `/fabrik-plan-after-chat` emits the spine, **Then** `## File Scope (owned paths)` is seeded from the epic's `owned_paths` and the header carries `Epic: docs/development/epics/<file>` (commands/_sources/fabrik-plan-after-chat.md:581)
- **Given** `/fabrik-execute-plan` acquires a lock, **When** the lock file is written, **Then** its path is `~/.claude/state/plan-locks/<repo-basename>/<plan-id>.json` and nothing is written under `.fabrik/plan-locks/` (commands/_sources/fabrik-execute-plan.md:83)
- **Given** a spine carrying `Epic:` and a ticket whose Touches escape the epic's `owned_paths`, **When** dispatch is attempted, **Then** the dispatcher refuses and names the offending path (commands/_sources/fabrik-execute-plan.md:374)
- **Given** a subagent worktree merges back, **When** the merge target is resolved, **Then** it is `git branch --show-current`, never `master` by name (commands/_sources/fabrik-execute-plan.md:92)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
