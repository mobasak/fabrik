# T06 — The rotation tick's hold, lifts and step snapshot (Integration)
Appetite: 240

## Scope
Implements spec § Chosen approach L2's arm, L3's lifts and fan-out, L1's step snapshot, and the Stop hook's mirror, in the four over-budget files this ticket owns. `scripts/sysadmin/claude_rotate.py` (and its byte-identical twin): `--battery-tick` (:7251) writes the heartbeat `battery-tick-last` every run (interface H, routed I11) and arms the `hibernate` tier at T−3 unless the pause is lifted, T has passed, or the wall gap since the tick's last end exceeds `_resume_gap_s()` (routed I7, I12 — never a 7-minute gap); a `walled` or `battery` stamp at T−3 becomes `hibernate` with line 1 carried raw; `_clear_stamp` (:7061) keeps the tier before its low-battery branch (:7075); `_battery_lift` (:7213) refuses while the pause is unlifted; `_resume_leg` (:7328) writes its `resume-wake` row under the tier; the tick's lift leg lifts the pause by (a) a sleep, (b) an outage starting at or after T for two slots and three answers back, (c) T+30 (T = the mark when no deadline), writes `lifted_at` and `lift_path` through `hibernate.py`'s `update_marker`, hands the stamp to the quota or battery tier when either is hot, and fans out `.holdlifted hibernate`, replacing a pending `resume` file only (routed I8; `_wake_held_sessions` `named` set :7480); `_open_wall_episode` (:7864) skips `site: hibernate`. `.claude/hooks/final_gate_stop.py`: `_hold_in_force` (:4854) holds for the unlifted `hibernate` tier on a stale tick log, with a hibernate message head. `scripts/command_run.py` `step` (after `save` at :6542): a detached, rate-limited `wip_backup.sh` single-repo run (T03's scope) when the hub script exists, under the cron's `flock -n /tmp/wip-backup.lock`, behind a `FABRIK_STEP_SNAPSHOT_BIN` seam so existing step tests spawn nothing. Re-expects `tests/test_claude_fleet.py::test_a_standing_hold_suppresses_the_resume_wake` (:9694) and splits `test_a_resume_wakes_once_and_never_overwrites_a_pending_lift` (:9714). Owns the whole-plan gates, the `/fabrik-review` receipt, `/fabrik-docs-review`, the seam tests of the spine's Interfaces S and H, the doc updates (hooks-index.md :101, :103, :124; claude-account-rotation.md § Cron :428-449; kaizen.md's pause skip; claude-config-backup-restore.md :39), and three operator-gated steps behind a DECISION block: the crontab line `* * * * * flock -n $HOME/.claude/state/battery.lock python3 /opt/fabrik/scripts/sysadmin/claude_rotate.py --battery-tick` (its output to its own log, never `rotate-tick.log`); `install_mesh.sh` for the three mesh scripts; the three drills (lid close, `wsl --shutdown`, network off). Mails youtube to check `hibernate.py paused` in its claim-pool launcher. DO-NOT: run the installer or edit the crontab without the operator's word.

Depends: T02, T03a, T03b, T05
Parallel: ⛓️
Complexity: native
Integration: true
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_hibernate_hold.py tests/test_battery_hold.py tests/test_final_gate_stop_hook.py -q
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_claude_fleet.py -q -k "resume or battery or hibernate or stamp"
Gate: python3 scripts/final_gate.py --check --json
Docs: docs/workstation/hooks-index.md; docs/workstation/claude-account-rotation.md; docs/workstation/kaizen.md; docs/workstation/claude-config-backup-restore.md

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

## Behavior Contract
- **Given** a marked pause with T-3 reached and no sleep since the last tick end, **When** the minute cron runs, **Then** it writes the `hibernate` tier and its heartbeat (scripts/sysadmin/claude_rotate.py:7251; spec § Chosen approach L2)
- **Given** a quota relief or a low battery under the `hibernate` tier, **When** the tick clears its stamp, **Then** the `hibernate` tier stays (scripts/sysadmin/claude_rotate.py:7061; spec § Chosen approach L2)
- **Given** a sleep under the hold, **When** the tick runs, **Then** it writes a `resume-wake` row and lifts the pause by path (a), writing `lifted_at` and `.holdlifted hibernate` (scripts/sysadmin/claude_rotate.py:7328; spec § Chosen approach L3)
- **Given** an outage that starts and ends before T, **When** ticks run, **Then** nothing lifts (scripts/sysadmin/claude_rotate.py:3391; spec § Chosen approach L3)
- **Given** a pending `.holdlifted resume`, **When** the hibernate lift fans out, **Then** the file reads `hibernate` (scripts/sysadmin/claude_rotate.py:7480; spec § Chosen approach L3)
- **Given** a `command_run.py step` in a repo with a hub `wip_backup.sh`, **When** the step saves, **Then** a detached single-repo snapshot starts, at most once per 2 minutes per repo, and never when the cron's lock is held (scripts/command_run.py:6542; spec § Chosen approach L1)
- **Given** the `hibernate` tier and an unlifted mark, **When** the Stop hook reads a stale tick log, **Then** it still yields as under a hold (.claude/hooks/final_gate_stop.py:4854; spec § Chosen approach L2)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- tests/test_battery_hold.py
