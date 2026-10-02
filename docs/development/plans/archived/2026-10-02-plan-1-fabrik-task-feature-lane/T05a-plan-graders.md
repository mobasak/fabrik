# T05a — Plan graders: Appetite per phase and the Size-small spec rule

## Scope
Implements spec § The delta D10 (grader half) and D11 (grader half). A NEW module `scripts/enforcement/plan_appetite.py` holds `LANE_ROLLOUT_DATE = "2026-10-03"` and the two rules, so neither grader imports the other: `appetite_findings(plan_text, plan_date)` — a plan dated on or after the rollout date needs `Appetite: <positive integer minutes>` in every phase (monolith) or ticket (set); `small_profile_findings(plan_text, spec_text)` — a `Profile: small` plan (the profile regex is `scripts/enforcement/check_plan_tickets.py:241`) whose spec is `Status: DRAFT` without a `Size: small` line is refused. `check_plan_tickets.py` and `check_plan_quality.py` each call them.

DO NOT re-grade plans dated before `LANE_ROLLOUT_DATE`.

Depends: —
Parallel: ⚡
Complexity: native
Appetite: 60
Gate: python -m pytest tests/test_plan_appetite_size.py tests/enforcement/test_check_plan_tickets.py tests/enforcement/test_plan_shape_gates.py -q
Docs: none

## Touches
- scripts/enforcement/plan_appetite.py — PRIMARY PATH
- scripts/enforcement/check_plan_tickets.py
- scripts/enforcement/check_plan_quality.py
- tests/test_plan_appetite_size.py

## Behavior Contract
- **Given** a plan dated `2026-10-03` with one ticket lacking `Appetite:`, or carrying `Appetite: 0` or `Appetite: soon`, **When** the graders run, **Then** they refuse it naming the ticket; a plan dated `2026-10-02` is not refused (spec § Validation V10; § The delta D11)
- **Given** a `Profile: small` plan whose spec is `Status: DRAFT` without `Size: small`, **When** the graders run, **Then** they refuse it; with `Size: small` they pass; a `CONVERGED` spec passes either way (spec § The delta D10)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- scripts/enforcement/check_plan_quality.py
