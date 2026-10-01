# T05c — Plan review holds the small-spec gate; execute-plan passes phase appetite

## Scope
Implements spec § The delta D10 (plan-review half) and D11 (execute half). `commands/_sources/fabrik-plan-review.md:17` gains the exception: for a `Size: small` spec it starts with `--surface` naming the plan AND the spec path, grades the spec's sections with the plan in one loop, flips both to CONVERGED, mints the approval row and ends at the operator's design-approval gate (today `commands/_sources/fabrik-spec-review.md:280-294`). `commands/_sources/fabrik-execute-plan.md` (§ Execution Loop `:389-438`) passes each phase's appetite with `step --appetite <minutes>` and shows `elapsed <m>/<appetite>` from `command_run.py line`; dispatcher mode's coder timeout (`:527-529`) is unchanged.

DO NOT change dispatcher mode's coder timeout (`commands/_sources/fabrik-execute-plan.md:527-529`).

Depends: —
Parallel: ⚡
Complexity: never-route
Appetite: 45
Gate: python -m pytest tests/test_plan_review_small_gate.py tests/test_check_command_corpus.py -q
Docs: none

## Touches
- commands/_sources/fabrik-plan-review.md — PRIMARY PATH
- commands/_sources/fabrik-execute-plan.md
- tests/test_plan_review_small_gate.py

## Behavior Contract
- **Given** the `/fabrik-plan-review` source, **When** its small-spec exception is read, **Then** it names `--surface` with the spec path, the joint loop, both flips, the approval row and the design-approval gate instead of the auto-handoff (spec § The delta D10)
- **Given** the `/fabrik-execute-plan` source, **When** § Execution Loop is read, **Then** each phase start passes `step --appetite <minutes>` and the phase marker reads `elapsed <m>/<appetite>` (spec § The delta D11)

## Context Files
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- commands/_sources/fabrik-plan-review.md
- commands/_sources/fabrik-execute-plan.md
