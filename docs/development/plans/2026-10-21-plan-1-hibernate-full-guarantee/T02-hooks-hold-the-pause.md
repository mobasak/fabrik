# T02 — The hooks hold the pause
Appetite: 120

## Scope
Implements spec § Chosen approach L2's hook invariants in the two hooks. `.claude/hooks/quota_stop.py` (synced): a stamp whose raw line 2 reads `hibernate` (read raw like `_stamp_is_battery`, :668 — never added to `_STAMP_TIERS`, :642) holds through a stale, unknown or missing tick age (the fail-open at :717-722) while the marker (Interface M, read inline as JSON, no hub import, a missing file reading as unmarked) is unlifted; the exact forms `python3 /opt/fabrik/scripts/sysadmin/hibernate.py (status|woke|paused)` with a closed argument class (`--json`, `--self <sid>`) and `python3 /opt/fabrik/scripts/sysadmin/hibernate.py lift` join `_ALLOWED_BASH` (:88-127) beside `selfwatch_arm.sh`'s (:111); the caller check is `hibernate.py`'s (T01a), never the hook's (routed I14); `_reason` (:762) gains a HIBERNATE head. `scripts/sysadmin/quota_posture_hook.py`: while the marker is unlifted, `main` denies `Agent` and every `command_run.py start` (review family included) for every session BEFORE the `:1089` return (which fires for a walled stamp or a missing posture), so neither the T-3 tier nor a missing posture reopens intake (routed I16: `_wall_stamp_stands`, :255-271, is True only for `walled`). DO-NOT: touch `final_gate_stop.py` (T06).

Depends: T01a
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_quota_stop_hook.py tests/test_quota_posture.py tests/test_hibernate_hooks.py -q
Docs: none in this ticket (T06 owns docs/workstation/hooks-index.md)

Grounded at: `.claude/hooks/quota_stop.py:717` (fail-open), `.claude/hooks/quota_stop.py:107` (allow-list), `scripts/sysadmin/quota_posture_hook.py:1089` (the early return)

## Touches
- .claude/hooks/quota_stop.py — PRIMARY PATH
- scripts/sysadmin/quota_posture_hook.py
- tests/test_quota_stop_hook.py
- tests/test_quota_posture.py
- tests/test_hibernate_hooks.py

## Behavior Contract
- **Given** the `hibernate` tier and an unlifted mark, **When** the tick log is days old or missing, **Then** `quota_stop` still holds world-changing tools (.claude/hooks/quota_stop.py:717; spec § Chosen approach L2)
- **Given** the `hibernate` tier, **When** a held session runs `python3 /opt/fabrik/scripts/sysadmin/hibernate.py status`, **Then** the hook allows it (.claude/hooks/quota_stop.py:107; spec § Chosen approach L2)
- **Given** a marked pause, **When** a session with a live run calls `Agent` or `command_run.py start`, **Then** the posture hook denies it, before and after T-3 (scripts/sysadmin/quota_posture_hook.py:1089; spec § Chosen approach L2)
- **Given** a marked pause and no posture file, **When** a session calls `Agent`, **Then** the posture hook denies it, its marker check running before the `:1089` return (scripts/sysadmin/quota_posture_hook.py:1089; spec § Chosen approach L2)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- .claude/hooks/quota_stop.py
- scripts/sysadmin/quota_posture_hook.py
- tests/test_quota_stop_hook.py
- tests/test_battery_hold.py
