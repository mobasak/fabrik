# T14e — check_review_coverage stops keying on a deleted command

## Scope
**The first draft of this ticket stated a root cause that is false, and the author-blind pass disproved it.** `fab-mega-04-validate` appears in `scripts/enforcement/check_review_coverage.py` at exactly two places, and BOTH are prose: `:581` a section comment, `:1314` the operator-facing remedy sentence *"Re-run fab-mega-04-validate against the current set"*. Routing does not use the command name at all — a mega report is recognised by `MEGA_REPORT_H1 = re.compile(r"\A#\s+Cross-Epic Validation Report\b")` (`:604`) OR the reserved filename regex `\bmega-(?:.*-)?validation-review\.md$` (`:606`), dispatched by `_is_mega_report` (`:610`). Deleting the command changes neither. So this ticket's real job is small and honest: **re-word the two prose strings** to name `/fabrik-epics-review`, so the remedy line stops telling an operator to run a command that no longer exists.

⚠️ **The genuine coupling lives in T06c, not here, and it is the inverse of what the first draft claimed.** If `/fabrik-epics-review` emits its report under a name lacking `mega-…-validation-review.md` and an H1 other than `# Cross-Epic Validation Report`, the mega grammar stops routing and the report silently falls through to the ordinary review grammar — the exact fail-open the file documents at `:599-602`. T06c now carries a Behavior-Contract row pinning both, and § Interfaces states them verbatim; this ticket depends on T06c so the pin exists before the re-wording lands. DO-NOT: touch `command_run.py` (T14f) or `review_rubric.py` (T14d).

Depends: T07a, T06c
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_check_review_coverage_precommit.py tests/test_check_review_coverage_rederivation.py -q   # the file the first draft named does not exist; `|| <fallback>` masked a usage error as green
Gate: test -z "$(git grep -n 'fab-mega-04-validate' -- scripts/enforcement/check_review_coverage.py)"
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- scripts/enforcement/check_review_coverage.py — PRIMARY PATH
- tests/test_check_review_coverage_rederivation.py

## Behavior Contract
- **Given** a report emitted by `/fabrik-epics-review` at the pinned filename and H1, **When** `_is_mega_report` runs, **Then** it routes through the mega grammar — the routing predicate is unchanged by this ticket, which is the point (scripts/enforcement/check_review_coverage.py:610)
- **Given** a report whose hash was not computed, **When** the check emits its remedy line, **Then** it names `/fabrik-epics-review`, a command that exists (scripts/enforcement/check_review_coverage.py:1314)

## Context Files
- .windsurf/rules/core/10-python.md
