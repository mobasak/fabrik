# T08b — the corpus check's tests lose the wrapper fixtures

## Scope
`tests/test_check_command_corpus.py` (169 KB; 10 references to `_traycer-skills`): remove the fixtures and assertions covering the orchestrator-wrapper audit T08a deleted — namely everything exercising the names **`TRAYCER_SKILLS`**, **`_orch_corpus`** and its call site's "wrapper tree missing in the hub" problem string. Those three names ARE the consumed interface: `scripts/enforcement/check_command_corpus.py` is deliberately NOT a Context File here because the pair exceeds the read budget (278,365 B vs 262,144 — the very collision that split T08), and `git show` of T08a's commit is the executor's view of the diff. Grep the test for those three names and delete what they anchor; and assert the three new sources pass the per-source predicates with no special case. ⚠️ This file carries a SIBLING's uncommitted edits in the hub tree (measured 2026-09-03, still dirty 2026-09-04) — `git status --porcelain tests/test_check_command_corpus.py` must be CLEAN before this ticket edits it; dirty → message the author and wait, never stash, never commit their hunks (§ Global Constraints). DO-NOT: touch `scripts/enforcement/check_command_corpus.py` (T08a).

Depends: T08a
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_check_command_corpus.py -q
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- tests/test_check_command_corpus.py — PRIMARY PATH

## Behavior Contract
- **Given** the test module, **When** grepped for `_traycer-skills` or `_orch_corpus`, **Then** the count is 0 (tests/test_check_command_corpus.py:1)
- **Given** a fixture repo containing `fabrik-epics-review.md` with no close-feedback line, **When** the suite runs, **Then** a test asserts the same finding fires as for any source (tests/test_check_command_corpus.py:1)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
