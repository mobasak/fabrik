# T04 — The in-lane review stops hunting at the first own-fix-only round

## Scope
Implements spec § The delta D8. Adds `scope_growth_rounds(stack)` per the spine § Interfaces `task_lane` API: it returns `(1, 1)` when the LAST entry of `stack` (a list of parent record dicts, each with a `command` key, built at `scripts/command_run.py:3752-3759`) has `command == "fabrik-task"`, else today's `(3, 2)` (`SCOPE_GROWTH_ROUNDS`/`_QUALIFY`, `:429`/`:435`). `scripts/enforcement/check_review_coverage.py` keeps `_OWN_FIX_ROUNDS_FOR_STOP = 2` (`:400`, asserted equal to `SCOPE_GROWTH_QUALIFY` by `tests/test_check_review_coverage_scope_growth.py:202`) and adds `_LANE_OWN_FIX_ROUNDS_FOR_STOP = 1`, used by the window test (`:491-493`) only for a receipt carrying the exact line `**Lane:** fabrik-task`; a new lockstep test pins it to `task_lane.scope_growth_rounds([{"command": "fabrik-task"}])[1]`.

DO NOT change `_OWN_FIX_ROUNDS_FOR_STOP` or `/fabrik-review`'s own convergence rules, and DO NOT edit `scripts/command_run.py` (T08 passes the stack).

Depends: T03b
Parallel: ⛓️
Complexity: native
Appetite: 60
Gate: python -m pytest tests/test_task_lane_review_stop.py tests/test_check_review_coverage_scope_growth.py tests/test_check_review_coverage_rederivation.py -q
Docs: none

## Touches
- scripts/task_lane.py
- scripts/enforcement/check_review_coverage.py — PRIMARY PATH
- tests/test_task_lane_review_stop.py

## Behavior Contract
- **Given** a stack whose last entry is `{"command": "fabrik-task"}`, **When** `scope_growth_rounds` runs, **Then** it returns `(1, 1)`; for an empty stack, or one whose last entry is another command with `fabrik-task` deeper, it returns `(3, 2)` (spec § The delta D8)
- **Given** a receipt with the exact line `**Lane:** fabrik-task` whose round 2 confirms only own-fix defects followed by a quiet closing row, **When** `check_review_coverage.py` runs, **Then** it passes; the same receipt without that line, or with `**Lane:** fabrik-task-x`, keeps the two-round rule (spec § Validation V8)
- **Given** both constants, **When** the lockstep test runs, **Then** `_LANE_OWN_FIX_ROUNDS_FOR_STOP` equals `scope_growth_rounds([{"command": "fabrik-task"}])[1]` and `_OWN_FIX_ROUNDS_FOR_STOP` still equals `SCOPE_GROWTH_QUALIFY` (spec § The delta D8)

## Context Files
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- scripts/enforcement/check_review_coverage.py
- tests/test_check_review_coverage_scope_growth.py
