# T01 — whoami spawner-only binding (null pid, `spawned: true`)
Appetite: 60

## Scope
Implements spec § The delta D2 step (4) — the spawner-only binding subcommand (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:109-126`) — and the matching row of § Contract deltas (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:267-268`), with W-14219e6f point 10 (enforce who may call it, not only mark the row).

The new CLI form, decided here (the spec names the subcommand, not its spelling): `whoami_agent.py --spawned <name> --session-id <uuid> --repo <dir> --lock-fd <n>`, a fourth member of the existing mutually exclusive mode group (`scripts/whoami_agent.py:470-476`). It writes through the existing locked writer (`bind`/`_bind_locked`, `scripts/whoami_agent.py:328-351`, `:354-462`) with these differences, nothing else:

1. **Enforcement (W-14219e6f point 10).** It refuses (exit 2, said, no row) unless the caller HOLDS the repo's agents lock: `--lock-fd <n>` is an open descriptor, `os.readlink(f"/proc/self/fd/{n}")` equals `<git common dir of --repo>/fabrik-agents.lock`, and a FRESH `open()` of that path with `fcntl.flock(fd, LOCK_EX | LOCK_NB)` fails with `EWOULDBLOCK` (the lock is held, by the description the caller passed down). `agents_spawn.py` (T06) holds that lock across every `add` and passes the descriptor with `subprocess.run(..., pass_fds=(fd,))`. It also refuses a session id that appears in ANY store row (a spawned id is freshly minted, so a known one is a misuse), and a session id that is not a lowercase UUID (`agents_up.sh:120`'s `SID` shape).
2. **The row.** `pid` and `pid_start` are `None` and the row carries `"spawned": true` (the writer otherwise stamps the CALLER's process, `scripts/whoami_agent.py:411-420`, which would make the coordinator the holder of the builder's name — spec D2). `toplevel` is the common dir of `--repo`, read by `_toplevel()` given an optional `cwd` parameter (today it reads the process cwd, `scripts/whoami_agent.py:183-194`); the default stays the process cwd for every existing caller.
3. **The holder scan stays** (`scripts/whoami_agent.py:385-409`, run with `force=False`): a name a LIVE pid-bearing row holds in this scope refuses (exit 1), exactly as `--as` does.
4. **Docstring.** `session_id()`'s "from the environment ONLY — never an argument" (`scripts/whoami_agent.py:72-78`) is amended in the same change to name this one exception and the lock that bounds it; the COBRA line states the cheapest bypass (a caller that takes the lock itself) and why it is accepted (the lock is taken only by `agents_spawn.py` and `rotate_session.py`, both hub tooling).

DO-NOT: change `--as`/`--who` behaviour, the trim rule (`scripts/whoami_agent.py:423-448`), or `resolve_agent_name`'s order; touch `agents_up.sh` (T02 consumes the row).

Depends: —
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_whoami_agent.py -q
Docs: docs/workstation/agent-identity.md (the new subcommand, its lock condition and its null-pid gap) — the script's own AFTER-EDIT header (`scripts/whoami_agent.py:2`) names it

## Touches
- scripts/whoami_agent.py — PRIMARY PATH (governance-sync trigger: `^scripts/(…|whoami_agent|…)\.py$` in `.pre-commit-config.yaml` — lane row 1; a worktree commit distributes nothing until infra merges it)
- tests/test_whoami_agent.py
- docs/workstation/agent-identity.md

## Behavior Contract
- **Given** the caller holds `<common dir>/fabrik-agents.lock` and passes its descriptor, **When** `whoami_agent.py --spawned b-1 --session-id <fresh uuid> --repo <R> --lock-fd <n>` runs, **Then** it exits 0 and the store's last row is `{session_id: <uuid>, name: b-1, toplevel: <R's common dir>, spawned: true, pid: null, pid_start: null}` (scripts/whoami_agent.py:411-420; spec § The delta D2)
- **Given** that row and a linked worktree `<R>/.claude/worktrees/b-1` in a repo with no registry, **When** `agents_up.sh --print <R>` runs, **Then** it prints a `pane b-1 <uuid> …` line (scripts/sysadmin/agents_up.sh:192-200; spec § Validation "the session-id binding form writes the row the resolver reads")
- **Given** no descriptor, a descriptor to another file, or a lock path nobody holds, **When** `--spawned` runs, **Then** it exits 2 naming the failed condition and writes no row (W-14219e6f point 10)
- **Given** the session id already appears in any store row, **When** `--spawned` runs with it, **Then** it exits 2 naming the id and writes no row (scripts/whoami_agent.py:360-368)
- **Given** a LIVE pid-bearing row binding b-1 in the same scope, **When** `--spawned b-1` runs, **Then** it exits 1 with the live-holder refusal (scripts/whoami_agent.py:403-409)
- **Given** the spawned row, **When** the builder's own session runs `whoami_agent.py --as b-1 --force`, **Then** its new row carries its own pid and `resolve_agent_name()` in that session returns b-1 (spec § The delta D3, the first-turn re-bind)
- **Given** `--spawned` combined with `--as` or `--who`, **When** parsed, **Then** argparse refuses with a usage error, exit 2 (scripts/whoami_agent.py:470-476)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/whoami_agent.py
- tests/test_whoami_agent.py
- docs/workstation/agent-identity.md
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
