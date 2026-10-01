# T05a — Plan graders: Appetite per phase and the Size-small spec rule

## Scope
Implements spec § The delta D10 (grader half) and D11 (grader half). `scripts/enforcement/check_plan_tickets.py` (the profile regex is `scripts/enforcement/check_plan_tickets.py:241`) and `check_plan_quality.py` refuse a plan dated on or after the rollout date with a phase or ticket lacking `Appetite: <minutes>`, never re-grading older plans; and refuse a `Profile: small` plan whose spec is DRAFT unless the spec carries `Size: small`. The rollout date is one constant both graders import.

DO NOT re-grade plans dated before the rollout constant.

Depends: —
Parallel: ⚡
Complexity: native
Appetite: 60
Gate: python -m pytest tests/test_plan_appetite_size.py tests/test_check_plan_tickets*.py -q
Docs: none

## Touches
- scripts/enforcement/check_plan_tickets.py — PRIMARY PATH
- scripts/enforcement/check_plan_quality.py
- tests/test_plan_appetite_size.py

## Behavior Contract
- **Given** a plan dated on or after the rollout date with one phase lacking `Appetite:`, **When** the graders run, **Then** they refuse it naming the phase; a plan dated before is not refused (spec § Validation V10; § The delta D11)
- **Given** a `Profile: small` plan whose spec is `Status: DRAFT` without `Size: small`, **When** the graders run, **Then** they refuse it; with `Size: small` they pass (spec § The delta D10)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- scripts/enforcement/check_plan_quality.py
