# T03 — `check_convergence.py` QUIET_PASS follows the new grammar

## Scope
In `scripts/enforcement/check_convergence.py` (fleet-synced with `scripts/enforcement/`), replace `QUIET_PASS` at `:200` (line numbers at 8092e8a8 — the working tree carries a sibling's uncommitted edit that shifts this file by three lines; today `found:\s*0\b[^\n]*?fixed:\s*0\b`, `re.I`; its single call site is `:772` inside `_check_executed_plan`, searched over the WHOLE cited review text read at `:768`) with the spec's regex VERBATIM (docs/superpowers/specs/2026-09-08-review-convergence-redesign-design.md:171, V13 `:244`, DD9 `:276`): `found:\s*0\b(?![^\n]*(?<![\w-])(?:confirmed\s*:\s*\d|unexecuted\s*:\s*\d*[1-9]))[^\n]*?fixed:\s*0\b|confirmed\s*:\s*0+\b(?![^\n]*(?<![\w-])unexecuted\s*:\s*\d*[1-9])[^\n]*?fixed:\s*0+\b` — the old pair applies only to a row carrying no NUMERIC `confirmed:` counter and no `unexecuted:` above zero; the lookaheads are anchored to a digit so a prose `CONFIRMED: see residual` label on an honest old-grammar row keeps its quiet match (this gate runs `re.I` and a label-killed match would fail a genuinely converged receipt — the zero-false-positive promise at `:186-190`, `:188` "deliberately ZERO-FALSE-POSITIVE signal"); `0+` so a zero-padded `confirmed: 00` reads the same at both gates; this gate stays a PRESENCE test (`:196`, "evidence PRESENCE, not truth"). Rewrite the comment block `:186-199` to name the new pair and D-206 (the supersede row; D-203 is the ruling) in place of the D-048-era wording; keep the D-053 same-line rule (`[^\n]`). Add the V13 tests to `tests/test_check_convergence.py` beside the existing quiet fixtures (`:130-153` ADJUDICATED_REVIEW, `:205-226` TRAILING_FOUND_REVIEW) and a corpus-parity test: over `git ls-files docs/development/reviews/*.md` (275) the set of receipts quiet under the old regex and under the new one is identical (166 and 166, 0 flips — assert the count AND the set). The AFTER-EDIT header at `:2` names `tests/test_check_convergence.py`, `fabrik-execute-plan.md` and `fabrik-plan-review.md` — the two command sources are T07's/the corpus's; state in the commit body that the coupled sources carry no `found: 0` wording that changes (grep them: 0 occurrences of `QUIET_PASS`-shaped text), so the WARN is answered. DO-NOT: change any other regex in the file (`_REDERIVATION_ROW` at `:124-126` grades a PLAN's own ledger and is out of scope); touch `check_review_coverage.py` (T01/T02); import `_ledger_shapes` (this file imports six names from the coverage gate at `:429-446` and must keep exactly those — one of them, `VERDICT` (imported at `:429` and `:439`), is applied at `:477` (8092e8a8) to grade checklist rows, and T02 widens it to the four RECORDED forms; that widening reaches this gate through the import with no edit here, and a RECORDED checklist row stops being `noverdict` at `:477` on T02's merge — say so in the commit body).

Depends: —
Parallel: ⚡
Complexity: never-route
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_check_convergence.py -q
Gate: python3 scripts/enforcement/check_convergence.py
Docs: CHANGELOG entry (Deltas)

## Touches
- scripts/enforcement/check_convergence.py — PRIMARY PATH
- tests/test_check_convergence.py

## Behavior Contract
- **Given** D9's round-18 row, V1's round-19 row, `| u | x | found: 0 | fixed: 0 | unexecuted: 2 |`, `| 19 | found: 0 | confirmed: 00 | fixed: 0 |` and `| 18 | found: 0, confirmed: 3, fixed: 0 |`, **When** `QUIET_PASS` is searched, **Then** the results are no match, match, no match, match, no match (scripts/enforcement/check_convergence.py:200)
- **Given** the 275 committed receipts, **When** the old and the new `QUIET_PASS` run whole-text over each, **Then** the quiet set is identical — 166 of 275 under both, 0 flips — asserted by the test over `git ls-files docs/development/reviews/*.md` (scripts/enforcement/check_convergence.py:768-772)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/enforcement/check_convergence.py
- tests/test_check_convergence.py
- docs/superpowers/specs/2026-09-08-review-convergence-redesign-design.md

## Implementation notes
- Red-first: the five-row test fails on today's regex on rows 2, 3 and 5 — V1's round-19 row (`found: N, new: N, confirmed: 0, fixed: 0`, spec `:232`; a non-zero `found:`) is no-match today and quiet under the new regex, while the `unexecuted: 2` row and the `confirmed: 3` row both match today's pair and are not quiet under the new one (the last is the `confirmed:`-lookahead branch's own red); D9's round-18 row (`found: 11, fixed: 3`) is a positive control already no-match today, and the `confirmed: 00` row fails only on the intermediate `\b`-only form.
- The 75 existing tests carry no `confirmed`/`unexecuted` token (0 of 1,349 lines), so none flips; run the file whole.
- The parity test loads the old regex as a literal in the test (it is the value being retired), never by importing HEAD's module.
