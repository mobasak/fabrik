# T01b — The status checks and the deadline header
Appetite: 120

## Scope
Implements spec § Chosen approach L2's `status` checks in `scripts/sysadmin/hibernate.py` `status` (:430-477). Check 1: a live `sdk-*` session whose parent chain reaches no live agent is its own row — BLOCKS before T-3, `held (headless)` non-blocking from T-3. Check 2: an agent with live `sdk-*` seats BLOCKS before T-3; from T-3 it BLOCKS unless its closed record names at least as many abandoned seats; the table lists them. Check 3: the uncommitted row names up to five paths then `+N more` (`worktree_state`, :413-414). Check 4: with a mark, the header names the pause, T-3, T and the time left. Check 5: a non-self agent whose record closed `blocked`/`handoff` with `updated_ts`+1 ≥ floor(`paused_at`) (`scripts/command_run.py:2273-2275` writes whole seconds) and no readable `resume_seed`/`resume_copy` BLOCKS; a `done` after the mark is its own non-blocking `done since the mark — verify` row. Check 6: an agent whose self-watch lock is not held by a live process BLOCKS — the lock dir read directly (`$CLAUDE_SOUND_LOCKDIR`, else `/tmp/claude-sound-locks-<uid>`), names compared after the tick's `_selfwatch_safe` rule, a missing dir BLOCKS, an outside-`/opt` agent judged the same (routed I2, I3). The minute-cron check: `$ROTATE_STATE_DIR/battery-tick-last` older than 180 s or absent → BLOCKS `no minute cron`. SAFE prints only after two reads 5 s apart (an env seam makes the gap 0 in tests). Re-expects `test_status_says_safe_only_when_every_agent_worktree_is_clean_pushed_and_idle` (:345) and `test_status_checks_the_callers_own_tree_but_not_its_own_run_and_skips_pool_sessions` (:432) with an armed-lock and a heartbeat fixture, and rewrites :432's pool clause for check 1. Inherited from T01a's review (routed under its scope-growth stop): `_default_home()` falls back to `os.path.expanduser("~")` when the passwd lookup raises `KeyError` (a uid with no passwd entry), so `paused` never exits 1 on an error of its own; `test_g2` patches `_terminal` so it passes under `-s` from a real terminal; the module docstring names `<passwd home>/.claude/state`. DO-NOT: change the verbs T01a owns beyond these three.

Depends: T01a
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_hibernate.py -q
Docs: docs/reference/hibernate.md § status (the six checks; T01a owns the file's other sections and lands first)

Grounded at: `scripts/sysadmin/hibernate.py:430` (`status`), `scripts/sysadmin/hibernate.py:414` (the uncommitted row), `scripts/sysadmin/claude_rotate.py:7417` (`_armed_sids`, the armed rule)

## Touches
- scripts/sysadmin/hibernate.py — PRIMARY PATH
- tests/test_hibernate.py
- docs/reference/hibernate.md

## Behavior Contract
- **Given** a live headless `sdk-*` session that is no agent's seat, **When** `status` runs before T-3, **Then** it is a BLOCKS row, and after T-3 a `held (headless)` row (scripts/sysadmin/hibernate.py:433; spec § Chosen approach L2)
- **Given** an agent with live seats, **When** `status` runs after T-3, **Then** it blocks until the agent's closed record names as many abandoned seats (scripts/sysadmin/hibernate.py:186; spec § Chosen approach L2)
- **Given** an agent whose self-watch is not armed, **When** `status` runs, **Then** it BLOCKS, an outside-`/opt` agent included (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** no minute-cron heartbeat for 3 minutes, **When** `status` runs, **Then** it BLOCKS with `no minute cron` (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** an uncommitted tree, **When** `status` runs, **Then** the row names up to five paths, then `+N more` (scripts/sysadmin/hibernate.py:414; spec § Chosen approach L2)
- **Given** a run closed `blocked` without a seed after the mark, **When** `status` runs, **Then** it BLOCKS, and a `done` close after the mark is its own non-blocking row (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** a marked pause, **When** `status` prints, **Then** the header names the pause, T-3, T and the time left, and SAFE prints only after two reads (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)
- **Given** a uid with no passwd entry, **When** `hibernate.py paused` runs, **Then** it reads the marker under `$HOME` and never exits 1 on that error (scripts/sysadmin/hibernate.py:936; T01a review P4-keyerror)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/hibernate.py
- tests/test_hibernate.py
