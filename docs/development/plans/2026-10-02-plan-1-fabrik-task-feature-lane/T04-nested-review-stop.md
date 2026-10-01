# T04 — The in-lane review stops hunting at the first own-fix-only round

## Scope
Implements spec § The delta D8. `task_lane.scope_growth_rounds(stack) -> (rounds, qualify)` returns `(1, 1)` when the review record's parent on the record stack is `fabrik-task`, else today's `(3, 2)` (`scripts/command_run.py:429`, `:435`; the stack at `:3752-3759`; the advisory `scope_growth_warning` at `:473` gains the stack in T08). `scripts/enforcement/check_review_coverage.py` reads `**Lane:** fabrik-task` and applies `_OWN_FIX_ROUNDS_FOR_STOP = 1` to that receipt only (`:400`, the window test `:491-493`). `commands/_fragments/scope-growth-exit.md` states the lane variant in one sentence.

DO NOT change `/fabrik-review`'s own convergence rules or the default two-round stop for receipts without `**Lane:** fabrik-task`.

Depends: T03
Parallel: ⛓️
Complexity: native
Appetite: 60
Gate: python -m pytest tests/test_task_lane_review_stop.py tests/test_check_review_coverage*.py -q
Docs: none

## Touches
- scripts/task_lane.py
- scripts/enforcement/check_review_coverage.py — PRIMARY PATH
- commands/_fragments/scope-growth-exit.md
- tests/test_task_lane_review_stop.py

## Behavior Contract
- **Given** a review record whose parent is `fabrik-task` and whose round 2 confirms only own-fix defects, **When** the advisory runs, **Then** it prints the stop; with no `fabrik-task` parent it stays silent until round 3 (spec § Validation V8)
- **Given** a receipt with `**Lane:** fabrik-task` whose last own-fix-only round is followed by a quiet closing row, **When** `check_review_coverage.py` runs, **Then** it passes; the same receipt without the `**Lane:**` line keeps today's two-round rule (spec § The delta D8)
- **Given** the rendered scope-growth fragment, **When** it is read, **Then** it names the lane variant and that the review still closes only on a confirmed-zero pass (spec § The delta D8; D-355)

## Context Files
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- scripts/enforcement/check_review_coverage.py
- commands/_fragments/scope-growth-exit.md
