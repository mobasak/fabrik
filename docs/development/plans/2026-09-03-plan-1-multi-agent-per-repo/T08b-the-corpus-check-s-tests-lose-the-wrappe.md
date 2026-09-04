# T08b — the corpus check's tests lose the wrapper fixtures

## Scope
`tests/test_check_command_corpus.py` (188,050 B (184 KB); 12 references to `_traycer-skills`): remove the fixtures and assertions covering the orchestrator-wrapper audit T08a deleted — namely everything exercising the names **`TRAYCER_SKILLS`**, **`_orch_corpus`** and its call site's "wrapper tree missing in the hub" problem string. Those three names ARE the consumed interface: `scripts/enforcement/check_command_corpus.py` is deliberately NOT a Context File here because the pair exceeds the read budget (284,847 B vs 262,144 — the very collision that split T08), and `git show` of T08a's commit is the executor's view of the diff. Grep the test for those three names and delete what they anchor. ⚠️ **THREE assertions must also change and carry NONE of those anchors, so the grep cannot find them** — the anti-vacuity canary counts at `tests/test_check_command_corpus.py:2792` ("10 canaries over 6 of the eight predicates" → 8), `:2875` ("17 canaries over 8" → 15) and `:2946` ("11 canaries over 7" → 9). **The expected drop is exactly −2 in each**, the two orchestrator-wrapper canaries T08a removes; any other delta means a real canary was lost and is a STOP, not a number to update. Baseline today is `17 canaries over 8 … (12 of 18 problem emitters)`; after T08a it is `15 over 8 … (10 of 13)`. pytest prints the actual number, so this is under-specification, not unsatisfiability — but updating a canary count blind is exactly how an anti-vacuity check stops being one; and assert the three new sources pass the per-source predicates with no special case. ⚠️ This file carries a SIBLING's uncommitted edits in the hub tree (measured 2026-09-03, still dirty 2026-09-04) — `git status --porcelain tests/test_check_command_corpus.py` must be CLEAN before this ticket edits it; dirty → message the author and wait, never stash, never commit their hunks (§ Global Constraints). DO-NOT: touch `scripts/enforcement/check_command_corpus.py` (T08a).

Depends: T08a
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_check_command_corpus.py -q
Gate: test "$(grep -c '_traycer-skills' tests/test_check_command_corpus.py)" = 0   # RED today (12 occurrences): the wrapper anchors are still in the test. `Depends: T08a` also reds the suite, but that is a dependency's redness, not this ticket's.
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- tests/test_check_command_corpus.py — PRIMARY PATH

## Behavior Contract
- **Given** the test module, **When** grepped for `_traycer-skills` or `_orch_corpus`, **Then** the count is 0 (tests/test_check_command_corpus.py:1)
- **Given** a fixture repo containing `fabrik-epics-review.md` with no close-feedback line, **When** the suite runs, **Then** a test asserts the same finding fires as for any source (tests/test_check_command_corpus.py:1)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
