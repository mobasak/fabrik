# T14e — check_review_coverage stops keying on a deleted command

## Scope
Split out of T14b by READ BUDGET (the combined functional sweep measured 594,710 B against 262,144). These are the references the author-blind review proved are FUNCTIONAL rather than prose: left in place they do not merely read stale, they resolve to paths and command names this plan deletes, and T14b's zero-references gate could never pass. **This ticket owns `scripts/enforcement/check_review_coverage.py`:** `:581` keys the cross-epic report parser on `fab-mega-04-validate` and `:1314` tells the operator to "Re-run fab-mega-04-validate against the current tree" — a command **T07a deletes**. After the retirement the parser matches nothing and the remedy text names a command that no longer exists: a live check that fails OPEN and an instruction that cannot be followed. Re-key both on `fabrik-epics-review`, the assembled successor (T06c). DO-NOT: touch `command_run.py` (T14f) or `review_rubric.py` (T14d).

Depends: T07a, T06c
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_check_review_coverage.py -q 2>/dev/null || python3 scripts/enforcement/check_review_coverage.py
Gate: test -z "$(git grep -n 'fab-mega-04-validate' -- scripts/enforcement/check_review_coverage.py)"
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- scripts/enforcement/check_review_coverage.py — PRIMARY PATH

## Behavior Contract
- **Given** a cross-epic validation report produced by `/fabrik-epics-review`, **When** `check_review_coverage` parses it, **Then** it is recognised exactly as a `fab-mega-04-validate` report is today (scripts/enforcement/check_review_coverage.py:581)
- **Given** a report whose hash was not computed, **When** the check emits its remedy line, **Then** it names `/fabrik-epics-review`, a command that exists (scripts/enforcement/check_review_coverage.py:1314)

## Context Files
- .windsurf/rules/core/10-python.md
