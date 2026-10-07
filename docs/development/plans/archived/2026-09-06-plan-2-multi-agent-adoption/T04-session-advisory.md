# T04 — `session_orient.py`: one line at SessionStart when N ≥ 2 sessions share this main checkout

## Scope
`.claude/hooks/session_orient.py` (fleet-synced AGENT_HOOK_FILES; self-contained — hooks import nothing from `scripts/`) gains `_sessions_line(cwd: str) -> str`: a self-contained copy of the `/proc` scan (processes under `proc_root` whose `comm` is `claude` and whose `cwd` symlink resolves to `cwd`, unreadable or vanished entries skipped, never raises, ≤50 ms; `proc_root` is `/proc` unless the env `FABRIK_PROC_ROOT` names a directory — the same env-driven test seam the harness already uses for `CLAUDE_MESH_HEADLESS` at `tests/test_session_orient_hook.py:131-140`, and a fake tree exercises the REAL scan rather than overriding its count) returning `""` when the count is < 2, when `cwd` contains `/.claude/worktrees/`, or when the repo is the hub (`(Path(cwd) / "scripts" / "fabrik_synced_manifest.py").is_file()` — the same test `_identity_line` uses at `session_orient.py:139`); otherwise ONE bullet: `- ⚠️ **N sessions share this main checkout.** The multi-agent model puts agents 2..N in worktrees — `CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>` — and one merge owner in the main checkout; adopt once with `python scripts/docs_updater.py --adopt <names>` (docs: /opt/fabrik/docs/reference/multi-agent-operating-model.md).` It is appended to the ORIENT block right after `_identity_line(cwd)` in `main()` (`session_orient.py:294`). The `hooks-index.md` row for `session_orient.py` gains the clause. DO-NOT: count from `git worktree list`; read `/proc/<pid>/environ`; print anything at 1 session; import `docs_updater`.

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
- **Given** the hook run through the existing `_run` harness with `FABRIK_PROC_ROOT` pointing at a fake tree holding three `claude` entries whose `cwd` symlinks resolve to a non-hub scratch cwd (plus one `bash` entry and one entry with no `cwd`), **When** it runs, **Then** the ORIENT block carries exactly one line starting `- ⚠️ **3 sessions share this main checkout.**` placed after the identity line (.claude/hooks/session_orient.py:294)
- **Given** a fake tree with one `claude` entry in that cwd, **When** it runs, **Then** the block carries no `sessions share` line and is byte-identical to today's output for that cwd (.claude/hooks/session_orient.py:287)
- **Given** three entries and a cwd whose path contains `/.claude/worktrees/`, or a cwd carrying `scripts/fabrik_synced_manifest.py` (hub identity), **When** it runs, **Then** no `sessions share` line is printed (.claude/hooks/session_orient.py:139)
- **Given** no `FABRIK_PROC_ROOT` and the live `/proc`, **When** `_sessions_line` runs on this box, **Then** it returns within 200 ms and never raises even when an entry disappears mid-scan (a fake tree entry whose `cwd` symlink dangles) (.claude/hooks/session_orient.py:211)

## Context Files
- .windsurf/rules/core/10-python.md
- .claude/hooks/session_orient.py
- tests/test_session_orient_hook.py
- docs/workstation/hooks-index.md
- docs/superpowers/specs/2026-09-06-multi-agent-adoption-design.md
