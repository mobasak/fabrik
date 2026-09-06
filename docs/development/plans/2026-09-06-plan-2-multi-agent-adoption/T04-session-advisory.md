# T04 — `session_orient.py`: one line at SessionStart when N ≥ 2 sessions share this main checkout

## Scope
`.claude/hooks/session_orient.py` (fleet-synced AGENT_HOOK_FILES; self-contained — hooks import nothing from `scripts/`) gains `_sessions_line(cwd: str) -> str`: a self-contained copy of the `/proc` scan (processes whose `comm` is `claude` and whose `cwd` resolves to `cwd`, unreadable entries skipped, never raises, ≤50 ms) returning `""` when the count is < 2, when `cwd` contains `/.claude/worktrees/`, or when the repo is the hub (`(Path(cwd) / "scripts" / "fabrik_synced_manifest.py").is_file()` — the same test `_identity_line` uses at `session_orient.py:139`); otherwise ONE bullet: `- ⚠️ **N sessions share this main checkout.** The multi-agent model puts agents 2..N in worktrees — `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>` — and one merge owner in the main checkout; adopt once with `python scripts/docs_updater.py --adopt <names>` (docs: /opt/fabrik/docs/reference/multi-agent-operating-model.md).` It is appended to the ORIENT block right after `_identity_line(cwd)` in `main()` (`session_orient.py:294`). The `hooks-index.md` row for `session_orient.py` gains the clause. DO-NOT: count from `git worktree list`; read `/proc/<pid>/environ`; print anything at 1 session; import `docs_updater`.

Depends: —
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_session_orient_hook.py -q
Docs: `docs/workstation/hooks-index.md` (Touches, the session_orient row) · CHANGELOG (Deltas)

## Touches
- .claude/hooks/session_orient.py — PRIMARY PATH
- tests/test_session_orient_hook.py
- docs/workstation/hooks-index.md

## Behavior Contract
- **Given** the hook run through the existing `_run` harness with `_sessions_line`'s scan monkeypatched (via an env override the test sets, `FABRIK_SESSIONS_SHARING_OVERRIDE=3`, read only when set) in a non-hub scratch cwd, **When** it runs, **Then** the ORIENT block carries exactly one line starting `- ⚠️ **3 sessions share this main checkout.**` placed after the identity line (.claude/hooks/session_orient.py:294)
- **Given** the override set to 1, **When** it runs, **Then** the block carries no `sessions share` line and is byte-identical to today's output for that cwd (.claude/hooks/session_orient.py:287)
- **Given** the override set to 3 and a cwd whose path contains `/.claude/worktrees/`, or a cwd carrying `scripts/fabrik_synced_manifest.py` (hub identity), **When** it runs, **Then** no `sessions share` line is printed (.claude/hooks/session_orient.py:139)
- **Given** no override and a live scan, **When** `_sessions_line` runs on this box, **Then** it returns within 200 ms and never raises even when a `/proc/<pid>` entry disappears mid-scan (simulated by a pid list that includes a dead pid) (.claude/hooks/session_orient.py:211)

## Context Files
- .windsurf/rules/core/10-python.md
- .claude/hooks/session_orient.py
- tests/test_session_orient_hook.py
- docs/workstation/hooks-index.md
- docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md
