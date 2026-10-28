# T01 — whoami spawner-only binding (null pid, `spawned: true`)
Appetite: 75

## Scope
Implements spec § The delta D2 step (4) — the spawner-only binding subcommand (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:109-126`) — and its § Contract deltas row (`docs/superpowers/specs/2026-10-28-dynamic-builders-design.md:267-268`), with W-14219e6f point 10 (enforce who may call it, not only mark the row) and plan-review pass 1, A2, A6-A9, A12.

The CLI form, decided here (the spec names the subcommand, not its spelling): `whoami_agent.py --spawned <name> --session-id <uuid> --repo <dir> --lock-fd <n>`, a third member of the existing mutually exclusive mode group, which has two today (`--as`, `scripts/whoami_agent.py:471`; `--who`, `scripts/whoami_agent.py:476`).

Invariants:
1. **Caller proof (W-14219e6f point 10; plan-review pass 1, A2).** Refuse (exit 2, said, no row) unless ALL hold: `--lock-fd <n>` is an open descriptor; `os.readlink(f"/proc/self/fd/{n}")` equals `<git common dir of --repo>/fabrik-agents.lock`; `fcntl.flock(n, LOCK_EX | LOCK_NB)` on the PASSED descriptor succeeds (it already holds the lock, so this is a no-op re-assertion — an unlocked descriptor to the file while another process holds the lock fails here); and a FRESH `open()` of the path with `flock(LOCK_EX | LOCK_NB)` fails with `EWOULDBLOCK` (the lock is held — by the passed description). `agents_spawn.py` (T06) holds that lock across every `add` and passes the descriptor with `subprocess.run(..., pass_fds=(fd,))`.
2. **Fresh id.** Refuse (exit 2) a session id that appears in ANY store row, and one that is not a lowercase UUID (`scripts/sysadmin/agents_up.sh:120`'s `SID` shape).
3. **Flag scoping (A6).** `--session-id`, `--repo` or `--lock-fd` given without `--spawned` refuses (exit 2, usage message), as does `--spawned` without all three.
4. **The row.** `pid` and `pid_start` are `None` and the row carries `"spawned": true` (the writer otherwise stamps the CALLER's process, `scripts/whoami_agent.py:411-420`). `toplevel` is `--repo`'s common dir, read by `_toplevel()` given an optional `cwd` parameter and run with `GIT_DIR`, `GIT_COMMON_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE` removed from its environment (A7 — the same as `lock_path` in T06 and `scripts/sysadmin/agents_up.sh:114`); the default (no `cwd`) keeps today's behaviour for every existing caller (`scripts/whoami_agent.py:183-194`).
5. **No window logic (A8).** `--spawned` sets `same_window` False and records no `predecessor` (`scripts/whoami_agent.py:376-401`): the spawner's own process is never this row's window.
6. **The holder scan stays** (`scripts/whoami_agent.py:385-409`, `force=False`): a name a LIVE pid-bearing row holds in this scope refuses.
7. **Exit codes (A9), for `--spawned` only:** 0 written · 1 a live holder holds the name · 2 refused (usage, caller proof, known or malformed id) · 3 an unexpected exception (today's catch-all at `scripts/whoami_agent.py:488-493` returns 1, which T06 could not tell from a collision; `--as`/`--who` keep their codes).
8. **Docstring.** `session_id()`'s "from the environment ONLY — never an argument" (`scripts/whoami_agent.py:72-78`) names this one exception and the lock that bounds it; the COBRA line states the cheapest bypass (a caller that takes the lock itself) and why it is accepted (only `agents_spawn.py` and `rotate_session.py` take it, both hub tooling).

DO-NOT: change `--as`/`--who` behaviour or codes, the trim rule (`scripts/whoami_agent.py:423-448`), or `resolve_agent_name`'s order; touch `agents_up.sh` (T02 consumes the row).

Depends: —
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_whoami_agent.py -q
Docs: docs/workstation/agent-identity.md (the new subcommand, its caller proof, its exit codes and its null-pid gap) — the script's AFTER-EDIT header (`scripts/whoami_agent.py:2`) names it

## Touches
- scripts/whoami_agent.py — PRIMARY PATH (governance-sync trigger — lane row 1; a worktree commit distributes nothing until the hub merges it)
- tests/test_whoami_agent.py
- docs/workstation/agent-identity.md

## Behavior Contract
- **Given** the caller holds `<common dir>/fabrik-agents.lock` and passes its descriptor, **When** `whoami_agent.py --spawned b-1 --session-id <fresh uuid> --repo <R> --lock-fd <n>` runs, **Then** it exits 0 and the store's last row is `{session_id: <uuid>, name: b-1, toplevel: <R's common dir>, spawned: true, pid: null, pid_start: null}` with no `predecessor` (scripts/whoami_agent.py:411-420; spec § The delta D2)
- **Given** that row and a linked worktree `<R>/.claude/worktrees/b-1` in a repo with no registry, **When** `agents_up.sh --print <R>` runs, **Then** it prints a `pane b-1 <uuid> …` line (scripts/sysadmin/agents_up.sh:192-200; spec § Validation)
- **Given** no descriptor, a descriptor to another file, or a lock path nobody holds, **When** `--spawned` runs, **Then** it exits 2 naming the failed condition and writes no row (W-14219e6f point 10)
- **Given** a descriptor open on the lock file but NOT locked while another process holds the lock, **When** `--spawned` runs with it, **Then** it exits 2 and writes no row (plan-review pass 1, A2)
- **Given** the session id already in any store row, or a non-UUID id, **When** `--spawned` runs with it, **Then** it exits 2 naming the id and writes no row (scripts/whoami_agent.py:360-368)
- **Given** a LIVE pid-bearing row binding b-1 in the same scope, **When** `--spawned b-1` runs, **Then** it exits 1 with the live-holder refusal, and an exception inside the spawned bind exits 3 (scripts/whoami_agent.py:403-409; plan-review pass 1, A9)
- **Given** `GIT_DIR` set to another repo in the caller's environment, **When** `--spawned` runs, **Then** the row's toplevel is still `--repo`'s common dir (scripts/sysadmin/agents_up.sh:114; plan-review pass 1, A7)
- **Given** `--spawned` with `--as`, or `--session-id`/`--repo`/`--lock-fd` without `--spawned`, **When** parsed, **Then** it exits 2 with a usage error (scripts/whoami_agent.py:470-476; plan-review pass 1, A6)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/whoami_agent.py
- tests/test_whoami_agent.py
- docs/workstation/agent-identity.md
- docs/superpowers/specs/2026-10-28-dynamic-builders-design.md
