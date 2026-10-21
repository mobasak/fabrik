# T04 — Mesh scripts get a tracked home and the hibernate wake
Appetite: 180

## Scope
Implements spec § Chosen approach L3 (the self-watch's `hibernate`/`resume` wake) and L4 (the sweep's builder leg). Copies the live `~/.claude/bin/claude-selfwatch.sh`, `claude-reboot-sweep.sh` and `claude-mesh-test.sh` into `scripts/sysadmin/mesh/` (first commit: byte copies, so the next diff is the change), then edits them there. The harness takes each file from `MESH_TEST_SRC` when present there, else from `~/.claude/bin` (live :19 copies `claude-sound.sh` and `claude-stop-decider.py` unconditionally, :20-21 the rest when present), so it runs on the tracked edits with the untracked mesh files beside them. The lift branch (live :44-73) gains `hibernate)` and `resume)` cases, the death branch's three-answer streak and jitter (live :138-156), and re-reads field 2 after the gate (routed I13); the `hibernate` line reads `lift_path` from the marker (Interface M, read with a `python3 -c` one-liner, `unknown` on any error) for its `(<why>)`; every RESUME line keeps `— this self-watch STAYS ARMED`, the clause `scripts/sysadmin/selfwatch_arm.sh:49` cuts. The sweep drops the `CLAUDE_MESH_AUTONOMOUS=1` re-export (:222) and the `claude -p --resume` leg (consuming autonomous markers with a note; R1/R4/R8/R14 rewritten), keeps the `state=` line byte-identical (pinned by a new test in `tests/test_install_mesh.py` that reads the TRACKED copy, since `tests/test_session_orient_hook.py:347-367` reads only the live one), and adds a builder leg: wait up to `MESH_BUS_WAIT` (default 120 s) for the user bus, then for each path `agents_bat.py --list` prints run `agents_up.sh --detach <path>` (T05), a `note` `uncapped-boot` when the wait expires (the sweep's only sink is its note log — the spec's 'ledger row'), and Leg B sends no resume-by-hand notice for a session the builder leg relaunched: before each `--detach` the leg reads that grid's `pane <name> <sid> <folder> <status>` lines from `agents_up.sh --print <path>` (`scripts/sysadmin/agents_up.sh:16`) and appends each sid to `<lockdir>/.boot-relaunched`, which Leg B skips and the next boot's sweep truncates; the harness gains W10f, W10g and R20 (stubbed `tmux`, `systemctl`, `agents_up.sh`). `scripts/sysadmin/agents_bat.py --list` prints the absolute path of every registered repo (`.fabrik/session-agents.json` or `.claude/worktrees`) without the `--print` probe, so a not-yet-answering bus never empties it. `scripts/sysadmin/install_mesh.sh` installs a reviewed copy: backup to `~/.claude/bin/backups/<f>.backup.<ts>`, `bash -n`, the harness, an atomic replace; never run by this ticket. DO-NOT: write anything under `~/.claude/bin` (T06's operator gate).

Depends: T01a, T05
Parallel: ⛓️
Complexity: native
Gate: MESH_TEST_SRC="$PWD/scripts/sysadmin/mesh" bash scripts/sysadmin/mesh/claude-mesh-test.sh
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_install_mesh.py tests/test_agents_bat.py -q
Docs: docs/reference/repo-coordinator-rollout.md (`agents_bat.py --list`, per its AFTER-EDIT header); T06 updates hooks-index.md:101 and claude-config-backup-restore.md:39

Grounded at: `scripts/sysadmin/selfwatch_arm.sh:49` (the STAYS ARMED cut), `scripts/dr_claude_backup.sh:91` (the DR mirror), `scripts/sysadmin/agents_bat.py:209` (the `--print` probe)

## Touches
- scripts/sysadmin/mesh/claude-selfwatch.sh — PRIMARY PATH
- scripts/sysadmin/mesh/claude-reboot-sweep.sh
- scripts/sysadmin/mesh/claude-mesh-test.sh
- scripts/sysadmin/install_mesh.sh
- scripts/sysadmin/agents_bat.py
- tests/test_install_mesh.py
- tests/test_agents_bat.py

## Behavior Contract
- **Given** a `.holdlifted` reading `<epoch> hibernate`, **When** the self-watch's lift branch fires, **Then** it waits for three API answers and jitter and prints the hibernate RESUME line, naming `lift_path`, ending in the STAYS ARMED clause (scripts/sysadmin/selfwatch_arm.sh:49; spec § Chosen approach L3)
- **Given** the kind is replaced while the gate waits, **When** the gate passes, **Then** the printed line uses the kind read after the gate (~/.claude/bin/claude-selfwatch.sh:55; spec § Chosen approach L3)
- **Given** a boot, **When** the reboot sweep runs, **Then** it builds every registered grid detached and never resumes a session with `claude -p` (~/.claude/bin/claude-reboot-sweep.sh:222; spec § Chosen approach L4)
- **Given** a builder the boot leg relaunched, **When** the sweep's notify leg runs, **Then** it sends no resume-by-hand notice for it (scripts/sysadmin/agents_up.sh:16; spec § Chosen approach L4)
- **Given** the installer and a reviewed mesh copy, **When** it runs, **Then** the live file is backed up first, the copy passes `bash -n`, and the replace is atomic (scripts/dr_claude_backup.sh:91; spec § Lifecycle)
- **Given** the tracked harness, **When** it runs with `MESH_TEST_SRC` on `scripts/sysadmin/mesh`, **Then** W10f, W10g and R20 pass on the tracked edits with the untracked mesh files taken from `~/.claude/bin` (~/.claude/bin/claude-mesh-test.sh:10; spec § Chosen approach L3, L4)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/selfwatch_arm.sh
- scripts/sysadmin/agents_bat.py
- tests/test_agents_bat.py
- scripts/dr_claude_backup.sh
