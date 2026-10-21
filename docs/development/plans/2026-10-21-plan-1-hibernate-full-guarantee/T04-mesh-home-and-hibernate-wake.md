# T04 — Mesh scripts get a tracked home and the hibernate wake
Appetite: 180

## Scope
Implements spec § Chosen approach L3 (the self-watch's `hibernate` and `resume` wake) and L4 (the sweep's builder leg). Copies the live `~/.claude/bin/claude-selfwatch.sh`, `claude-reboot-sweep.sh` and `claude-mesh-test.sh` into a tracked home `scripts/sysadmin/mesh/` (first commit: byte copies, so the diff is the change), then edits them there: the lift branch (live :44-73) gains `hibernate)` and `resume)` cases, the death branch's three-answer streak and storm jitter (live :138-156), and re-reads field 2 after the gate (routed I13), every RESUME line keeping the `— this self-watch STAYS ARMED` clause `selfwatch_arm.sh:49` cuts; the sweep drops the `CLAUDE_MESH_AUTONOMOUS=1` re-export (:222) and the `claude -p --resume` leg, consuming autonomous markers with a note, keeps `state="${MESH_STATE_DIR:-$HOME/.claude/state/autonomous}"` byte-identical (`tests/test_session_orient_hook.py:347-367`), and adds a builder leg: wait for the user bus within `MESH_BUS_WAIT`, then for each repo `agents_bat.py --list` prints run `agents_up.sh --detach <repo>` (T05), noting `uncapped-boot` in the sweep log when the wait expires; the harness gains W10f/W10g and R20 and rewrites R1/R4/R8/R14 for the retired resume. `scripts/sysadmin/install_mesh.sh` installs a reviewed copy: backup to `~/.claude/bin/backups/<f>.backup.<ts>`, `bash -n`, the harness on `MESH_TEST_SRC=scripts/sysadmin/mesh`, then an atomic replace; it is never run by this ticket. `scripts/sysadmin/agents_bat.py` gains `--list`. DO-NOT: write anything under `~/.claude/bin` (T06's operator gate).

Depends: T01
Parallel: ⚡
Complexity: native
Gate: bash scripts/sysadmin/mesh/claude-mesh-test.sh
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_install_mesh.py tests/test_agents_bat.py -q
Docs: none in this ticket (T06 updates hooks-index.md:101 and claude-config-backup-restore.md:39, which call the mesh box-local)

Grounded at: `scripts/sysadmin/selfwatch_arm.sh:49` (the STAYS ARMED cut), `scripts/dr_claude_backup.sh:91` (the DR mirror), `scripts/sysadmin/agents_bat.py:144` (the `--print` probe)

## Touches
- scripts/sysadmin/mesh/claude-selfwatch.sh — PRIMARY PATH
- scripts/sysadmin/mesh/claude-reboot-sweep.sh
- scripts/sysadmin/mesh/claude-mesh-test.sh
- scripts/sysadmin/install_mesh.sh
- scripts/sysadmin/agents_bat.py
- tests/test_install_mesh.py
- tests/test_agents_bat.py

## Behavior Contract
- **Given** a `.holdlifted` reading `<epoch> hibernate`, **When** the self-watch's lift branch fires, **Then** it waits for three API answers and jitter and prints the hibernate RESUME line ending in the STAYS ARMED clause (scripts/sysadmin/selfwatch_arm.sh:49; spec § Chosen approach L3)
- **Given** the kind is replaced while the gate waits, **When** the gate passes, **Then** the printed line uses the kind read after the gate (scripts/sysadmin/selfwatch_arm.sh:22; spec § Chosen approach L3)
- **Given** a boot, **When** the reboot sweep runs, **Then** it builds every registered grid detached and never resumes a session with `claude -p` (scripts/sysadmin/agents_bat.py:144; spec § Chosen approach L4)
- **Given** the installer and a reviewed mesh copy, **When** it runs, **Then** the live file is backed up first, the copy passes `bash -n`, and the replace is atomic (scripts/dr_claude_backup.sh:91; spec § Lifecycle)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- scripts/sysadmin/selfwatch_arm.sh
- scripts/sysadmin/agents_bat.py
- tests/test_agents_bat.py
- scripts/dr_claude_backup.sh
