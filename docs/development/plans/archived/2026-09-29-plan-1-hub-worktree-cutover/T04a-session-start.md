# T04a — SessionStart: adopt at any count, the move line, live bindings

## Scope
Implements spec § The delta D1 (the adopt prompt at any session count) and D5 (a), and V6's bindings half and V7's prompt half. `.claude/hooks/session_orient.py`: (1) in the main checkout of an unadopted repo, prompt `docs_updater.py --adopt` whatever the live-session count (today `_sessions_line` returns "" below two, `.claude/hooks/session_orient.py:330-333`, and `:223` states the single-session silence); (2) in a main checkout whose declared merge owner differs from this session's resolved name, print the move line (`EnterWorktree` into `.claude/worktrees/<name>`; the conversation follows) — OUTSIDE the hub early-returns at `:227` and `:321`, so the hub's own non-owner sessions (fleet, intel) see it; an unnamed session (resolved name "") is told to bind first with `python3 /opt/fabrik/scripts/whoami_agent.py --as <name>` and then move; (3) list the repo's live `whoami_agent.py` bindings (store rows whose pid is live, scoped to the repo's common dir) with the stated limit that launch-time `CLAUDE_AGENT` sessions write none; (4) the hub test at `:227, :321, :382` becomes the manifest + common-dir rule (spec § The delta D4). DO-NOT: touch `check_commit_trailers.py` (T04b).

Depends: —
Parallel: ⚡
Complexity: never-route
Gate: python -m pytest tests/test_session_orient_hook.py -q
Docs: none (hooks-index rows are T06b's)

## Touches
- .claude/hooks/session_orient.py — PRIMARY PATH
- tests/test_session_orient_hook.py

## Behavior Contract
- **Given** one live session in the main checkout of a repo with no `MERGE OWNER:` row, **When** SessionStart runs, **Then** the output names `docs_updater.py --adopt` (spec § Validation V7)
- **Given** a repo whose merge owner is `alpha` and a session resolved as `beta` in its main checkout, **When** SessionStart runs, **Then** the output tells it to move into `.claude/worktrees/beta` with `EnterWorktree` and says the conversation follows (spec § The delta D5)
- **Given** the hub's main checkout with a declared merge owner `infra` and a session resolved as `fleet`, **When** SessionStart runs, **Then** the move line appears there too (spec § The delta D5)
- **Given** two live bindings in the whoami store for the repo's common dir, **When** SessionStart runs, **Then** both names are listed, and a dead-pid row is not (spec § Validation V6)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- .claude/hooks/session_orient.py
- scripts/whoami_agent.py
