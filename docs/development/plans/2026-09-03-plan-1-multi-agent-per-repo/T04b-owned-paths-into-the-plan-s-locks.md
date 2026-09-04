# T04b — owned_paths into the plan's locks (the locks STAY in-repo, per spec r11)

## Scope
Two source edits (spec § Chain consolidation (e), § Live locks). (1) `commands/_sources/fabrik-plan-after-chat.md` seeds the spine's `## File Scope (owned paths)` (`:581`) from the epic's frontmatter `owned_paths` when the plan was fed by an epic-born spec, and writes ONE header line `Epic: docs/development/epics/<file>` on the spine — the interface T05a enforces. **It also makes the spec's `**Owner:**` line mandatory** (spec § Ownership surfaces — the field T15's PLANS table reads): `/fabrik-plan-after-chat` emits `**Owner:** <CLAUDE_AGENT>` on every new spine, filled from the environment at creation rather than by hand, so the ownership column is never empty for a plan this chain produced. The convention is live but unwritten today — 9 line-start occurrences across 8 of 118 project plans. (2) `commands/_sources/fabrik-execute-plan.md`: **the lock DIRECTORY does not move** — spec r11 withdrew the relocation (D-117), so every `.fabrik/plan-locks/` reference in this file stays exactly as it is and the five enforcement tickets that existed to chase the move are deleted. What this ticket still changes there: the dispatcher REFUSES a ticket whose Touches fall outside the spine's `Epic:` owned_paths — using the SAME glob-aware comparison T05a defines, never a prefix test (a prefix match returns False for `src/a/x.py` against `src/a/**` and would refuse every legitimate dispatch) (the containment T05a gates at emit, enforced at dispatch); the merge target is the CURRENT branch (`git branch --show-current`), never a named default (audit R10); and the two-level worktree rule replaces the one-run "Don't nest a worktree" note (`:92-97`) — subagent worktrees nest inside an agent's worktree as ordinary git (`$GIT_COMMON_DIR` is shared). ⚠️ **Per-worktree locks are now the design, not a compromise** (spec § Live locks): each agent's lock lives in its own tree, which is where every lock that agent's own resume needs already is; cross-agent contention cannot cause data loss because agents commit to their own branches and only the merge owner writes `master`. R6 probe as a WRITTEN step: in a scratch repo, `claude -p --worktree agent-alpha` with a brief that adds a nested worktree, commits in it and merges into `worktree-agent-alpha`; default if the enforcement blocks it — subagents dispatch on branches inside the agent's worktree. SPLIT NOTE: T04's other half is T04a (the read budget). DO-NOT: touch `fabrik-spec.md` (T04a) or any enforcement script (T05a/T05b).

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
- **Given** `/fabrik-execute-plan` acquires a lock, **When** the lock file is written, **Then** its path is unchanged at `.fabrik/plan-locks/<plan-id>.json` — r11 withdrew the relocation, so this ticket must NOT move it (commands/_sources/fabrik-execute-plan.md:83)
- **Given** a spine carrying `Epic:` and a ticket whose Touches escape the epic's `owned_paths`, **When** dispatch is attempted, **Then** the dispatcher refuses and names the offending path (commands/_sources/fabrik-execute-plan.md:374)
- **Given** a subagent worktree merges back, **When** the merge target is resolved, **Then** it is `git branch --show-current`, never `master` by name (commands/_sources/fabrik-execute-plan.md:92)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
