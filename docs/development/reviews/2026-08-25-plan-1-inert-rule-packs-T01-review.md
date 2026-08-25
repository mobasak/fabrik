# Review — T01 (D7 live-request pin) · phase-1 of 2026-08-25-plan-1-inert-rule-packs

Status: IN-PROGRESS

Surface: `commands/_sources/fabrik-execute-plan.md` (D7 clause) + `tests/test_execute_plan_d7.py`.
Commits: `b589a1b8` (build), `c7fa2335` (review fixes).

## Pass Ledger

| Pass | finders | found | fixed | refuted | notes |
|---:|---|---:|---:|---:|---|
| 1 | pool 4 (deepseek-v3.2-exp, gemini-3-flash, qwen3-max, deepseek-v4-flash) + orchestrator Opus | 5 | 2 | 3 | see adjudication |
| 2 | native Opus authoritative pass | 17 | 3 | — | **found what all 4 pool finders missed**, incl. a LIVE fleet breakage |
| 3 | confirming round — OWED, not yet run | — | — | — | exit NOT claimed; `found: 0, fixed: 0` not reached |

`Finders: pool deepseek-v3.2-exp×1 + gemini-3-flash×1 + qwen3-max×1 + deepseek-v4-flash×1 — round 1`
`Finders: native opus×1 — round 2`

⚠️ **This review has NOT reached its exit.** Round 2 made three fixes, so by the termination
contract the next round is owed and this file must not claim a quiet pass. Recorded here rather
than asserted, because the round that made edits is never the last one.

## Adjudication

**FIXED**

1. **cwd-dependent source path** (CONFIRMED). The pin opened `./commands/_sources/fabrik-execute-plan.md`
   relative to cwd: `pytest tests/test_execute_plan_d7.py` from the repo root passed while
   `cd tests && pytest test_execute_plan_d7.py` died with `FileNotFoundError`. Reproduced before the
   fix, both invocations green after. Path now resolves from `__file__`.
2. **Mutation stripped both signals at once** (CONFIRMED — raised independently by the orchestrator
   and by qwen3-max). `test_d7_pin_is_not_vacuous` removed the live-request phrase AND the
   `## Evidence` reference in one mutation, so it could not show which signal the predicate depended
   on; a pin keyed solely on `## Evidence` would have passed it unchanged. Two per-signal mutation
   tests added and proven non-vacuous by red-on-revert: a pin weakened to evidence-only and one
   weakened to live-request-only are BOTH caught.

**REFUTED — each against the code, not by argument**

3. *"A reworded D7 heading makes the pin pass vacuously."* False. `_d7_section` returns `''` on a
   heading it cannot find, and the test asserts `assert d7` BEFORE reaching the predicate — so a
   reword makes the test FAIL LOUDLY. Verified by substituting an en-dash/title-case heading and
   observing an empty section. The brittleness is real; its direction is fail-safe.
4. *"`## Evidence` could leak in from a later section via a boundary error."* The section slice stops
   at the first following `###`/`##`; the requirement text and the `## Evidence` reference are both
   inside D7's own body. No path found where a later section's text enters the slice.
5. *"The pin should accept semantic equivalents ('Evidence block', 'Evidence section')."* Declined as
   a defect: loosening the predicate weakens the pin, which is the thing under test. The exact-token
   requirement is the contract; a reword that breaks it fails loudly and is corrected deliberately.

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| fail-open vs fail-closed on the pin | CLEAN | every failure direction is loud: missing section → `assert d7` fails; missing clause → predicate False; reworded heading → empty slice → fails. No silent pass path found |
| cost/quota/limit accounting | REFUTED | no metered call, no LLM dispatch, no quota surface — the ticket is a prose clause plus a file-reading test |
| boundary/sentinel/prefix collisions | FIXED | the section-boundary slice is the sentinel here; verified it stops at the next `###`/`##` and that a reworded heading yields an empty slice rather than a wrong one |
| behavior-without-a-test | FIXED | both Behavior-Contract rows now carry tests, and the second row's test was strengthened from one combined mutation to two independent ones, each proven red-on-revert |
| cwd / environment dependence | FIXED | finding 1 — proven by running pytest from two directories |
| prose-pin honesty (ticket-specific) | FIXED | both signals proven independently load-bearing; two weakened-pin variants both caught |

## Evidence

Watched RED before the D7 edit, in the orchestrator's own turn — the failure dumped the real D7
section text, proving the pin reads the file rather than a fixture:

```
>       assert _pins_live_request(d7), "Test setup: D7 should contain the requirement before mutation"
E       AssertionError: Test setup: D7 should contain the requirement before mutation
E       assert False
E        +  where False = _pins_live_request('### D7 — Final validation + terminal states\n\n**The Integration ticket runs BEFORE validation ...')
2 failed in 0.09s
```

GREEN after, and green from both invocation directories after the review fix:

```
$ python -m pytest tests/test_execute_plan_d7.py -q
....                                                                     [100%]
4 passed in 0.06s
$ cd tests && python -m pytest test_execute_plan_d7.py -q
....                                                                     [100%]
4 passed in 0.06s
```

Independent signal probe (orchestrator, not the coder's test):

```
real section pins: True
A: strip only 'live request'      -> False (want False)
B: strip only '## Evidence'       -> False (want False)
```

Red-on-revert for the two new mutation tests:

```
weakened pin 'evidence-only':     live-strip->True   => CAUGHT by the new tests: True
weakened pin 'live-request-only': evidence-strip->True => CAUGHT by the new tests: True
```

Corpus integrity after the D7 edit:

```
$ python scripts/enforcement/check_command_corpus.py
✓ command corpus: web-tool names, chain targets, script paths, trailer models, run records — all sound across 44 corpus file(s)
```

## Round 2 — the native Opus authoritative pass

The pool ran four finders across four axes and returned mostly non-defects. The single native Opus
finder returned 17 candidates, including three the pool did not raise at all — one of them a live
production breakage. This is the "pool breadth + native authority, never either/or" floor earning
its keep, recorded because a review that only ran the cheap layer would have shipped all three.

**FIXED in round 2**

3. **A LIVE FLEET BREAKAGE the change had already shipped** (CONFIRMED, executable proof).
   `select_rules.py` and `review_rubric.py` now `import rules_match` at MODULE SCOPE. Both are in
   `CORE_SCRIPTS` and both are governance-sync trigger surfaces; `rules_match.py` was in neither. The
   T04 commit therefore fired the sync, shipped the rewired pair to every project, and left the
   dependency behind. Measured: 49 projects carry `select_rules.py`, **48 were missing
   `rules_match.py`**, and `/opt/transdoc`'s copy died at import with
   `ModuleNotFoundError: No module named 'rules_match'` — a tool `CLAUDE.md` § Orient step 4 makes
   MANDATORY before planning. Fixed in `3f7b8bd2`: added to `CORE_SCRIPTS` + the `.pre-commit-config.yaml`
   files-filter, force-synced, verified 47 synced / 0 missing / transdoc runs again.
   **The rule this encodes: a synced script's IMPORTS are part of the synced surface.**
4. **The pin checked PRESENCE, not FORCE** (CONFIRMED). It returned True for a section reworded to
   *"is fine on green suites alone; a live request is nice to have"* — both signals present, meaning
   inverted. The orchestrator's own earlier probes tested only DELETION of each signal, which is
   exactly why they missed it. A first repair keyed on "same sentence" ALSO passed, because the clause
   ends `LIVE REQUEST.**` so the stop is followed by markdown bold and sentence-splitting borrowed
   `requires` from the neighbour. Fixed in `fca968d7` by pinning modality and subject as ONE ADJACENT
   PHRASE, plus an inversion control test that asserts both signals survive the mutation first.
5. **cwd-relative source path** — already fixed in round 1 (`c7fa2335`); Opus independently confirmed
   it and noted the sibling `tests/test_rules_match.py` had done it correctly all along.

**CONFIRMED and STILL OPEN — carried to round 3, not closed**

6. **`packs_for_paths` does NOT answer the same question as `review_rubric.py --changed`.** The rubric
   emits floor packs into its FLOOR section and then skips them in MATCHED; `packs_for_paths` has no
   such exclusion. Proven: `review_rubric.py --changed db/schema.sql` → `MATCHED — none`, while
   `packs_for_paths(['db/schema.sql'])` → `['core/25-data-postgres.md']`. **T04's first
   Behavior-Contract row, the module docstring, and the `--changed` help text all assert an
   equivalence that is false.**
7. **T04's equivalence test passes only because its hard-coded paths dodge the divergent case.**
   Adding `db/schema.sql` or `Dockerfile` to its `changed` list makes it fail. A test whose pass
   depends on the input avoiding the failure proves nothing its docstring claims.
8. **Doc Sync Matrix**: three files added, zero `INDEX.md` rows, no `CHANGELOG` entry for the pair.
9. **`select_rules.py --changed` returns before the Kaizen M1 sensor block**, so that invocation
   emits no `rule_activation` event — the M1 denominator silently shrinks for agents that adopt it.
10. **21 ruff W291/W293** in the new test file.

**REFUTED in round 2**

11. *"`rules_match.py` lacks an `AFTER-EDIT` header"* — present at line 2.
12. *"The `lru_cache` on `_tree_paths` is a new staleness regression"* — pre-dates this change
    (`HEAD~1:select_rules.py:96`); moved, not introduced. Opus independently confirmed distinct roots
    yield distinct cache keys, so there is no cross-root staleness.
13. Opus ran a differential harness — 27 globs × 19 paths against the HEAD single-path matcher, and
    17 globs × 4 root spellings against the HEAD tree matcher — and found **0 divergences**. That is
    a stronger purity result than the orchestrator's byte-identical CLI comparison, which only covers
    globs the current corpus happens to contain.
