# T06 — The rotation tick's hold, lifts and step snapshot (Integration)
Appetite: 240

## Scope
Implements spec § Chosen approach L2's arm, L3's lifts and fan-out, L1's step snapshot and the Stop hook's mirror in the four over-budget files this ticket owns (both `claude_rotate.py` copies byte-identical, `scripts/sysadmin/test_bot_rotation_wire.py:50`). Arm: `--battery-tick` (:7251) writes `battery-tick-last` every run (Interface H, routed I11) and, holding `update_marker`'s flock and re-reading the marker under it, arms the `hibernate` tier at T−3 unless the mark is lifted, T has passed, or the wall gap since `tick-last-end` exceeds `_resume_gap_s()` (routed I7, I12 — never a 7-minute gap; the spec's Validation line 'a 7-minute sleep under the mark lifts by (a)' is superseded by receipt N2); a `walled` or `battery` stamp at T−3 becomes `hibernate` with line 1 carried raw. Keep: `_clear_stamp` (:7061) keeps the tier before its low-battery branch (:7075); `_battery_lift` (:7213) refuses while the mark is unlifted; the advisory's latch (:8208-8221) treats a `hibernate` stamp as `battery_held` so `_touch_stamp` (:8265) never rewrites it. Lift leg, run in the tick's `finally` AFTER `_resume_leg` (:3391): `_resume_leg` (:7328) writes its `resume-wake` row under the tier; the pause lifts by (a) a `resume-wake` row whose gap starts after the mark, (b) an outage starting at or after T for two slots with three answers back, (c) T+30 (T = the mark when no `deadline_at`), and also clears a `hibernate` stamp whose mark the hub already lifted; each writes `lifted_at`/`lift_path` through `hibernate.py`'s `update_marker` (a missing hub path — the aro-wake ship — does nothing), hands the stamp to the quota or battery tier when either is hot (no wake), and fans out `.holdlifted hibernate`, replacing a pending `resume` file only (routed I8; `named` :7480); `_open_wall_episode` (:7864) skips `site: hibernate`. Migration: before merge, the live 12:22 marker gets `lifted_at` and `lift_path=migration` by hand with no fan-out, so the first new tick wakes nobody. `.claude/hooks/final_gate_stop.py`: the stamp branch (:4849-4854) holds for an unlifted `hibernate` tier on a stale or missing tick log, with a HIBERNATE message head. `scripts/command_run.py` `step` (after `save`, :6542): a detached (`start_new_session`, devnull, no wait) single-repo `wip_backup.sh` run (`WIP_BACKUP_ONLY`, T03a) when `/opt/fabrik/scripts/wip_backup.sh` exists, under `flock -n /tmp/wip-backup.lock`, at most once per 2 minutes per repo (a stamp under the run-record state dir), behind a `FABRIK_STEP_SNAPSHOT_BIN` seam so existing step tests spawn nothing. Re-expects `tests/test_claude_fleet.py::test_a_standing_hold_suppresses_the_resume_wake` (:9694) and splits `test_a_resume_wakes_once_and_never_overwrites_a_pending_lift` (:9714). Owns the whole-plan gates, the `/fabrik-review` receipt, `/fabrik-docs-review`, the seam tests of Interfaces S and H, the docs (hooks-index.md :101, :103, :124; claude-account-rotation.md § Cron :428-449; kaizen.md's pause skip; claude-config-backup-restore.md :39), and three operator-gated steps behind ONE DECISION block: the crontab line `* * * * * flock -n $HOME/.claude/state/battery.lock python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --battery-tick >> $HOME/.claude/battery-tick.log 2>&1`; `install_mesh.sh` for the three mesh scripts; the three drills (lid close, `wsl --shutdown`, network off), whose `wsl --shutdown` run also sizes `MESH_BUS_WAIT` (U8). Mails youtube to check `hibernate.py paused` in its claim-pool launcher. DO-NOT: run the installer or edit the crontab without the operator's word.

Depends: T01b, T02, T03a, T03b, T04
Parallel: ⛓️
Complexity: native
Integration: true
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_hibernate_hold.py tests/test_battery_hold.py tests/test_final_gate_stop_hook.py -q
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_claude_fleet.py -q -k "resume or battery or hibernate or stamp"
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python scripts/final_gate.py --check --json
Docs: docs/workstation/hooks-index.md; docs/workstation/claude-account-rotation.md; docs/workstation/kaizen.md; docs/workstation/claude-config-backup-restore.md; docs/reference/health-monitoring.md and docs/CONFIGURATION.md (T03a's launchers' pause-skip lines)

Grounded at: `scripts/sysadmin/claude_rotate.py:7328` (`_resume_leg`), `scripts/command_run.py:6542` (the step save), `.claude/hooks/final_gate_stop.py:4854` (`_hold_in_force`)

## Touches
- docs/development/reviews/2026-10-21-plan-1-hibernate-full-guarantee-review.md
- scripts/sysadmin/claude_rotate.py — PRIMARY PATH
- scripts/aro-wake/claude_rotate.py
- .claude/hooks/final_gate_stop.py
- scripts/command_run.py
- tests/test_claude_fleet.py
- tests/test_battery_hold.py
- tests/test_hibernate_hold.py
- tests/test_final_gate_stop_hook.py
- docs/workstation/hooks-index.md
- docs/workstation/claude-account-rotation.md
- docs/workstation/kaizen.md
- docs/workstation/claude-config-backup-restore.md
- docs/reference/health-monitoring.md
- docs/CONFIGURATION.md

## Behavior Contract
- **Given** a marked pause with T-3 reached and no sleep since the last tick end, **When** the minute cron runs, **Then** it writes the `hibernate` tier and its heartbeat, and with the mark lifted or T past it writes the heartbeat only (scripts/sysadmin/claude_rotate.py:7251; spec § Chosen approach L2)
- **Given** a `walled` or `battery` stamp at T-3, **When** the minute cron arms, **Then** the stamp becomes the `hibernate` tier with line 1 kept (scripts/sysadmin/claude_rotate.py:7197; spec § Chosen approach L2)
- **Given** a quota relief, a low battery or a promise coming due under the `hibernate` tier, **When** the tick touches its stamp, **Then** the `hibernate` tier stays (scripts/sysadmin/claude_rotate.py:7061; spec § Chosen approach L2)
- **Given** a sleep under the hold, **When** the tick runs, **Then** it writes a `resume-wake` row and lifts the pause by path (a), writing `lifted_at` and `.holdlifted hibernate` (scripts/sysadmin/claude_rotate.py:7328; spec § Chosen approach L3)
- **Given** an outage that starts and ends before T, **When** ticks run, **Then** nothing lifts, and one starting after T that lasts two slots lifts by (b) (scripts/sysadmin/claude_rotate.py:3391; spec § Chosen approach L3)
- **Given** no sleep and no outage, **When** T+30 passes, **Then** the pause lifts by (c), T being the mark when there is no deadline (scripts/sysadmin/claude_rotate.py:3391; spec § Chosen approach L3)
- **Given** a lift while the quota is hot or the battery low, **When** the lift leg runs, **Then** the stamp goes to that tier and nobody is woken (scripts/sysadmin/claude_rotate.py:7213; spec § Chosen approach L2)
- **Given** the hub lifted the mark while the tier stands, **When** the next tick runs, **Then** it clears the tier and writes `.holdlifted hibernate` (scripts/sysadmin/claude_rotate.py:7437; spec § Chosen approach L3)
- **Given** a pending `.holdlifted resume`, **When** the hibernate lift fans out, **Then** the file reads `hibernate` (scripts/sysadmin/claude_rotate.py:7480; spec § Chosen approach L3)
- **Given** a hibernate lift row, **When** the wall advisory looks for an open episode, **Then** the row ends no quota episode (scripts/sysadmin/claude_rotate.py:7864; spec § Chosen approach L3)
- **Given** a `command_run.py step` in a repo with a hub `wip_backup.sh`, **When** the step saves, **Then** a detached single-repo snapshot starts, at most once per 2 minutes per repo, and never when the cron's lock is held (scripts/command_run.py:6542; spec § Chosen approach L1)
- **Given** the `hibernate` tier and an unlifted mark, **When** the Stop hook reads a stale or missing tick log, **Then** it still yields as under a hold (.claude/hooks/final_gate_stop.py:4854; spec § Chosen approach L2)
- **Given** the stamp's raw line 2 is `hibernate`, **When** `quota_stop` evaluates a held session's tool, **Then** it holds on the tier the minute cron writes (.claude/hooks/quota_stop.py:668; spec § Chosen approach L2)
- **Given** the minute cron's heartbeat file, **When** `hibernate.py status` reads it, **Then** a fresh file passes the check and a 3-minute-old one blocks (scripts/sysadmin/hibernate.py:430; spec § Chosen approach L2)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- tests/test_battery_hold.py
