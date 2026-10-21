# T02 — The hooks hold the pause
Appetite: 120

## Scope
Implements spec § Chosen approach L2's hook invariants in the two synced hooks. `.claude/hooks/quota_stop.py`: a stamp whose raw line 2 reads `hibernate` (read raw, like `_stamp_is_battery` at :668 — never added to `_STAMP_TIERS` at :642) holds through a stale or unknown tick age (the fail-open at :717-722) while the marker (interface M, read inline as JSON from `$ROTATE_STATE_DIR/hibernate.json` or `~/.claude/state/hibernate.json`, no hub import) is unlifted; the exact `python3 /opt/fabrik/scripts/sysadmin/hibernate.py (lift|status|woke|paused)` forms join `_ALLOWED_BASH` (:88-127) beside `selfwatch_arm.sh`'s at :111, with a closed argument class; the merge-owner check for `lift` lives in `hibernate.py` (T01), never in the hook (routed I14: no subprocess on the held path); `_reason` (:762) gains a HIBERNATE head. `scripts/sysadmin/quota_posture_hook.py`: while the marker is unlifted, `decide` denies `Agent` and every `command_run.py start` (review family included) for every session, and that check runs before the `:1089` stamp pass, which returns early only for a `walled` read (`_wall_stamp_stands`, :255-271 — routed I16). DO-NOT: touch `final_gate_stop.py` (T06 owns it, over budget).

Depends: T01
Parallel: ⚡
Complexity: native
Gate: /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_quota_stop_hook.py tests/test_quota_posture.py tests/test_hibernate_hooks.py -q
Docs: none in this ticket (T06 owns docs/workstation/hooks-index.md)

Grounded at: `.claude/hooks/quota_stop.py:717` (fail-open), `.claude/hooks/quota_stop.py:107` (allow-list), `scripts/sysadmin/quota_posture_hook.py:1089` (the stamp pass)

## Touches
- .claude/hooks/quota_stop.py — PRIMARY PATH
- scripts/sysadmin/quota_posture_hook.py
- tests/test_quota_stop_hook.py
- tests/test_quota_posture.py
- tests/test_hibernate_hooks.py

## Behavior Contract
- **Given** the `hibernate` tier and an unlifted mark, **When** the tick log is days old, **Then** `quota_stop` still holds world-changing tools (.claude/hooks/quota_stop.py:717; spec § Chosen approach L2)
- **Given** the `hibernate` tier, **When** a held session runs `python3 /opt/fabrik/scripts/sysadmin/hibernate.py status`, **Then** the hook allows it (.claude/hooks/quota_stop.py:107; spec § Chosen approach L2)
- **Given** a marked pause, **When** a session with a live run calls `Agent` or `command_run.py start`, **Then** the posture hook denies it, before and after T-3 (scripts/sysadmin/quota_posture_hook.py:1089; spec § Chosen approach L2)
- **Given** the stamp's tier reads `hibernate`, **When** `quota_posture_hook` evaluates the RED branch, **Then** the marker check runs before the walled-stamp pass (scripts/sysadmin/quota_posture_hook.py:270; spec § Chosen approach L2)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- .claude/hooks/quota_stop.py
- scripts/sysadmin/quota_posture_hook.py
- tests/test_quota_stop_hook.py
- tests/test_battery_hold.py
