# T14f — command_run stops owing a report to a deleted command

## Scope
Split out of T14b by READ BUDGET (the combined functional sweep measured 594,710 B against 262,144). These are the references the author-blind review proved are FUNCTIONAL rather than prose: left in place they do not merely read stale, they resolve to paths and command names this plan deletes, and T14b's zero-references gate could never pass. **This ticket owns `scripts/command_run.py`:** `:1236` hard-codes `"fab-mega-04-validate"` in the set of commands whose `done` is refused without a report. T07a deletes that command, so the entry becomes dead weight while its real successor, `/fabrik-epics-review`, owes no report at all — the obligation silently moves from enforced to absent. Re-key it on `fabrik-epics-review`. Its test coverage (`tests/test_command_run.py:1568,1575`) moves with it. DO-NOT: touch `check_review_coverage.py` (T14e).

Depends: T07a, T06c
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_command_run.py -q
Gate: test -z "$(git grep -n 'fab-mega-04-validate' -- scripts/command_run.py tests/test_command_run.py)"
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- scripts/command_run.py — PRIMARY PATH
- tests/test_command_run.py

## Behavior Contract
- **Given** `/fabrik-epics-review` closes with `done` and no report artifact, **When** `command_run.py` validates the close, **Then** it refuses exactly as it does today for `fab-mega-04-validate` (scripts/command_run.py:1236)
- **Given** the module after this ticket, **When** grepped for `fab-mega-04-validate`, **Then** the count is 0 in both the script and its test (tests/test_command_run.py:1575)

## Context Files
- .windsurf/rules/core/10-python.md
