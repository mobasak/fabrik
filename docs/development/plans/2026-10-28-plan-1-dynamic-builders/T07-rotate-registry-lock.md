# T07 — rotate_session.py re-points the registry under the agents lock
Appetite: 45

## Scope
W-14219e6f point 3: `rotate_session._repoint_registry` (`scripts/sysadmin/rotate_session.py:252-320`) reads, rewrites and `os.replace`s `.fabrik/session-agents.json` (`:300-313`) outside any lock, so a rotation landing inside an `add` or `remove` (which hold the repo's agents lock across their registry write — spec § The delta D2, `docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:96-99`) can lose one of the two writes; its own comment concedes the window (`:305`). Fix the class at its root: `_repoint_registry` takes the SAME lock for its whole read-modify-write.

1. Load `agents_spawn.py` from `rotate_session.py`'s own directory by file path (`importlib.util.spec_from_file_location`, the pattern `.claude/hooks/agent_role.py:96-106` uses) and call its `lock_path(repo)` (T06), so the lock path rule exists once.
2. Take `fcntl.flock(LOCK_EX | LOCK_NB)` on that path, retrying every 0.2 s for up to 30 s; never obtained → return `"refused:agents lock busy"` (the function's existing `refused:<why>` outcome family, `:292`, `:304`, `:312`) and write nothing. Held from before the re-read of the registry until after `os.replace` (`:300-313`), released in `finally`.
3. The comment at `:305` is replaced by one naming the lock and who else holds it (`agents_spawn.py add|remove`).

DO-NOT: change the outcome strings callers already read (`repointed`, `current`, `no-entry`, the existing `refused:` reasons, `:290-319`), the rotation flow around the call (`:1188-1194`), or `resolve()`'s pane lookup (`:467-482`, which already filters the base session and so reads grouped windows once).

Depends: T06
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_rotate_session.py tests/test_agents_spawn.py -q
Docs: docs/workstation/session-history-retention.md — the sentence that describes the re-point (`docs/workstation/session-history-retention.md:177`) gains "under the repo's agents lock (`refused:agents lock busy` after 30 s)"; it is the one doc among rotate_session.py's AFTER-EDIT targets (`scripts/sysadmin/rotate_session.py:2`) that describes the re-point (hooks-index.md's fabrik-rotate row does not, and is T04's file)

## Touches
- scripts/sysadmin/rotate_session.py — PRIMARY PATH
- tests/test_rotate_session.py
- docs/workstation/session-history-retention.md

## Behavior Contract
- **Given** a process holding the repo's agents lock while it adds a registry row, **When** a rotation re-points another row of the same registry, **Then** the rotation waits for the lock and the file afterwards holds both changes (scripts/sysadmin/rotate_session.py:300-313; W-14219e6f point 3)
- **Given** the agents lock held for longer than the bound, **When** the rotation re-points, **Then** the outcome is `refused:agents lock busy` and the registry is byte-identical (scripts/sysadmin/rotate_session.py:290-319)
- **Given** `agents_spawn.lock_path(<repo>)`, **When** rotate_session resolves the lock for the same repo, **Then** both name the same file (seam test; spec § The delta D2)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/rotate_session.py
- tests/test_rotate_session.py
- scripts/sysadmin/agents_spawn.py
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
