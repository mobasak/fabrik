# T01a — The pause marker and the hibernate.py verbs
Appetite: 120

## Scope
Implements spec § Chosen approach L2 (`mark --deadline`, `paused`, `brief --deadline`) and L3 (`woke`, `lift`) in `scripts/sysadmin/hibernate.py`, and the spine's Interface M. The marker resolver: `$ROTATE_STATE_DIR/hibernate.json` when set, else `<home>/.claude/state/hibernate.json`; the tests set `ROTATE_STATE_DIR` to the Box fixture's `home/.claude/state` (conftest pins `ROTATE_STATE_DIR` per test, `tests/conftest.py:275`), and `woke` reads the rotate ledger from the same dir. `update_marker` holds `fcntl.flock` on `hibernate.json.lock` across read-modify-write; `mark` keeps no old keys. `paused` exits 0 marked-and-unlifted, 1 otherwise (no marker file included), and 2 when the marker file exists but cannot be read or parsed — it reads the file raw, never through `read_marker`, whose empty-dict fallback would read as unmarked — or on any other error of its own. `lift`: the caller's session is the nearest live claude session, agent or `sdk-*` pool session alike, whose pid is an ancestor of the `lift` process, found by walking the ppid chain to pid 1 with no hop cap (the pool walk at `scripts/sysadmin/hibernate.py:186-194` stops at 8 hops and matches agents only — not reused), its name from CLAUDE_AGENT or the identity binding; it passes when that name is the ledger's merge owner (`decisions.py --merge-owner`, `FABRIK_DECISIONS_PY` seam) or when the walk reaches pid 1 with no claude session on it AND stdin is a terminal (the operator's plain shell, the last resort — a process detached with `setsid` or `systemd-run --user` has no terminal; a `FABRIK_LIFT_TTY` seam fakes it in tests); any other caller is refused with exit 3 and a `hibernate-lift-refused` row in the rotate ledger; a pass writes `lifted_at` and `lift_path=hub` only (the tick clears the tier). `woke` answers RESUME only after `lifted_at`, only while the session has started no run after it (any state), never after 24 h, and never for `lift_path=migration`; it lists seeds globbed from `<command-runs>/seeds/<safe_sid>*` newer than `paused_at`, newest first, with each abandoned seat's state (`still running (pid N)`, `finished (output at <path>)`, `exited, no output`) and one `get_chat` line. `brief --deadline` prints T-3 and T as clock times; 'Exit 0 means the box slept' (`scripts/sysadmin/hibernate.py:260-261`) goes. Rewrites `tests/test_hibernate.py`'s resume-wake-alone cases at :515, :553, :565 for the lift-only rule (routed I4). DO-NOT: touch `status` (T01b), the tick, the hooks or a launcher; DO-NOT import `claude_rotate.py`.

Depends: —
Parallel: ⛓️
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_hibernate.py -q
Docs: docs/reference/hibernate.md (the timeline, `paused`, `mark --deadline`, `lift`, `woke`); commands/_sources/hibernate.md (render at merge from master only; the 'ALWAYS lift' wording at its After-the-wake section goes)

Grounded at: `scripts/sysadmin/hibernate.py:511` (`lift`), `scripts/sysadmin/hibernate.py:336` (`woke`), `scripts/command_run.py:7740` (`resume_seed` only inside `_wall`)

## Touches
- scripts/sysadmin/hibernate.py — PRIMARY PATH
- tests/test_hibernate.py
- docs/reference/hibernate.md
- commands/_sources/hibernate.md

## Behavior Contract
- **Given** a pause marked with `--deadline 10m`, **When** `hibernate.py paused` runs, **Then** it exits 0, 1 after a lift or with no marker file, and 2 on a marker file it cannot parse (scripts/sysadmin/hibernate.py:507; spec § Chosen approach L2)
- **Given** two writers updating the marker at once, **When** both finish, **Then** neither key set is lost (scripts/sysadmin/hibernate.py:291; spec § Chosen approach L3)
- **Given** a lifted pause, **When** `woke` runs for a session that started a run after the lift, 24 h after it, or under `lift_path=migration`, **Then** it exits 1 `no pending resume` (scripts/sysadmin/hibernate.py:336; spec § Chosen approach L3)
- **Given** a held session that is not the merge owner's, a headless `sdk-*` session, or a detached process with no terminal, **When** it runs `hibernate.py lift`, **Then** the lift is refused with exit 3 and a `hibernate-lift-refused` ledger row (scripts/sysadmin/hibernate.py:511; spec § Chosen approach L2)
- **Given** the merge owner's session or a plain shell with no claude ancestor, **When** it runs `hibernate.py lift`, **Then** it writes `lifted_at` and `lift_path=hub` and touches no stamp (scripts/sysadmin/hibernate.py:511; spec § Chosen approach L3)
- **Given** `mark --deadline 10m`, **When** `brief --deadline` prints, **Then** it names T-3 and T as clock times and no longer says the exit means the box slept (scripts/sysadmin/hibernate.py:260; spec § Chosen approach L2)
- **Given** seeds written since the mark, **When** `woke` answers RESUME, **Then** it lists them newest first with each abandoned seat's state and a `get_chat` line (scripts/sysadmin/hibernate.py:336; spec § Chosen approach L3)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/hibernate.py
- tests/test_hibernate.py
- docs/reference/hibernate.md
- commands/_sources/hibernate.md
