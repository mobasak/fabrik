# T05c — Plan review holds the small-spec gate; execute-plan shows phase appetite

## Scope
Implements spec § The delta D10 (plan-review half) and D11 (execute half). `commands/_sources/fabrik-plan-review.md:17` gains the exception: for a `Size: small` spec it grades the spec's sections with the plan in one loop, flips both to CONVERGED, ends at the operator's design-approval gate (today `commands/_sources/fabrik-spec-review.md:280-294`) and mints that approval row there. `commands/_sources/fabrik-execute-plan.md` (§ Execution Loop `:389-438`) passes each phase's appetite with `step --appetite`, prints `elapsed <m>/<appetite>` in the one-line phase marker and, past 2×, the standing re-plan order; dispatcher mode's coder timeout (`:527-529`) is unchanged.

DO NOT change dispatcher mode's coder timeout (`commands/_sources/fabrik-execute-plan.md:527-529`).

Depends: —
Parallel: ⚡
Complexity: never-route
Appetite: 45
Gate: python commands/assemble_commands.py --check && python -m pytest tests/test_plan_review_small_gate.py tests/test_command_corpus*.py -q
Docs: none

## Touches
- commands/_sources/fabrik-plan-review.md — PRIMARY PATH
- commands/_sources/fabrik-execute-plan.md
- tests/test_plan_review_small_gate.py

## Behavior Contract
- **Given** a `Size: small` spec, **When** `/fabrik-plan-review` converges, **Then** it flips the spec and the plan to CONVERGED, mints the approval row, and ends at the design-approval gate instead of auto-handing off (spec § The delta D10)
- **Given** a plan phase with `Appetite: 60`, **When** `/fabrik-execute-plan` enters and finishes it, **Then** the phase marker reads `elapsed <m>/60`, and past 120 minutes the re-plan order is printed (spec § The delta D11)

## Context Files
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- commands/_sources/fabrik-plan-review.md
- commands/_sources/fabrik-execute-plan.md
