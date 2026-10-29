# T07 — rotate_session.py re-points the registry under the agents lock
Appetite: 60

## Scope
W-14219e6f point 3, with plan-review pass 1, A4, A5, A14: `rotate_session._repoint_registry` (`scripts/sysadmin/rotate_session.py:252-320`) lstat's, reads, rewrites and `os.replace`s `.fabrik/session-agents.json` outside any lock, so a rotation landing inside an `add` or `remove` (which hold the repo's agents lock across their registry write — spec § The delta D2, `docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:96-99`) can lose one of the two writes; its own comment concedes the window (`:305`). Fix at the root: the whole function runs under the SAME lock.

Invariants and touchpoints:
1. **Lock before the first read (A4).** The lock is taken before the `os.lstat` at `:258` and the first `read_bytes` at `:277`, and released in `finally` after `os.replace` (`:313`) — the whole read-modify-write, not only the re-read.
2. **One lock path rule.** Load `agents_spawn.py` from `rotate_session.py`'s own directory by file path (`importlib.util.spec_from_file_location`, the `.claude/hooks/agent_role.py:96-106` pattern) and call its `lock_path(repo)` (T06), the repo derived from the registry path as `path.parents[1]` (`<repo>/.fabrik/session-agents.json`).
3. **Never an exception (A5).** A missing `agents_spawn.py`, an import error, or a `lock_path` failure (git failing) returns `"refused:agents lock unavailable"` and writes nothing — the function's contract is "every failure is a returned state, never an exception" (`:253-256`).
4. **Bounded wait (A14).** `fcntl.flock(LOCK_EX | LOCK_NB)` retried every 0.2 s for up to `_wait_s(30)` seconds (`:219-224`, so `ROTATE_WAIT_S` shortens it in tests — note the suite's fixture already sets `ROTATE_WAIT_S=3`, `tests/test_rotate_session.py:164`, which shortens this wait too); never obtained → `"refused:agents lock busy"`, nothing written.
5. **Precedence (plan-review pass 2, record-only).** The lock comes first, so a registry that is missing AND a git failure resolving the lock returns `refused:agents lock unavailable`, not `absent`.
6. The comment at `:305` is replaced by one naming the lock and its other holders (`agents_spawn.py add|remove`).

Note (panel PF3): this ticket's lock can still return `refused:agents lock busy`, after which the rotation flow continues (`:1188-1194`); the stale row is healed by `add`/`remove` (`heal_registry`, T08b), which the seam row below proves.

DO-NOT: change the outcome strings callers already read (`repointed`, `current`, `no-entry`, `absent`, the existing `refused:` reasons, `:257-319`), the rotation flow around the call (`:1188-1194`), or `resolve()` (`:467-482`, which filters the base session and so reads grouped windows once).

Depends: T06, T08b
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_rotate_session.py tests/test_agents_spawn.py -q
Docs: docs/workstation/session-history-retention.md — the sentence describing the re-point (`docs/workstation/session-history-retention.md:177`) gains "under the repo's agents lock (`refused:agents lock busy` after 30 s; `refused:agents lock unavailable` when the lock cannot be resolved)"; it is the one doc among rotate_session.py's AFTER-EDIT targets (`scripts/sysadmin/rotate_session.py:2`) that describes the re-point

## Touches
- scripts/sysadmin/rotate_session.py — PRIMARY PATH
- tests/test_rotate_session.py
- docs/workstation/session-history-retention.md

## Behavior Contract
- **Given** a process holding the repo's agents lock while it adds a registry row, **When** a rotation re-points another row of the same registry, **Then** the rotation waits for the lock and the file afterwards holds both changes (scripts/sysadmin/rotate_session.py:300-313; W-14219e6f point 3)
- **Given** a competing writer that takes the lock and rewrites the registry after the rotation's first read would have happened, **When** both finish, **Then** both changes hold, because the rotation's lock precedes its first lstat and read (scripts/sysadmin/rotate_session.py:258-277; plan-review pass 1, A4)
- **Given** the agents lock held past the bound with `ROTATE_WAIT_S=1`, **When** the rotation re-points, **Then** the outcome is `refused:agents lock busy` and the registry is byte-identical (scripts/sysadmin/rotate_session.py:219-224; plan-review pass 1, A14)
- **Given** `agents_spawn.py` missing from the script directory, or `lock_path` raising, **When** the rotation re-points, **Then** the outcome is `refused:agents lock unavailable`, no exception escapes, and the registry is byte-identical (scripts/sysadmin/rotate_session.py:253-256; plan-review pass 1, A5)
- **Given** a rotation refused `agents lock busy` that left the registry row on the old id, **When** the next `add` runs, **Then** the row names the live pane's id (seam test with T08b's `heal_registry`; panel PF3)
- **Given** `agents_spawn.lock_path(<repo>)`, **When** rotate_session resolves the lock from `<repo>/.fabrik/session-agents.json`, **Then** both name the same file (seam test; spec § The delta D2)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/rotate_session.py
- tests/test_rotate_session.py
- scripts/sysadmin/agents_spawn.py
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
