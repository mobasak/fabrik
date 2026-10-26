# T04a-c receipt — shared fragment `term-edit.md`

Start commit (baseline): 61d1f4b99c6a8188a281f86799268fe54ee1b5d1. Commits: T04a e068fc8, T04b 4b4771c, T04c (this one).

## Size
- Own text: 5354 words (UTF-8 `wc -w`; 5187 in the C locale) -> 5129 / 4975. **95.8%, not 50%.** No ceiling row touched.
- Entries: 62 total, 14 reworded (the rest are byte-identical units, one entry each), classes ban 40 / prose 18 / grammar 4 / behavioural 0.
- Class and clause labels are `# class:` / `# clauses:` YAML comments (`_ENTRY` on this base has no such keys).

## Why it stays over 50% (floor table, measured per baseline clause, 5232 clause words)
| Reason | Words | Share |
|---|---|---|
| ban word, verbatim from the ban word to the end of its `;`/`—` clause (D-1240) | 1103 | 21% |
| phrase pinned verbatim by a kept test (`test_review_exit_contract`, `test_review_loop_workflow`, `test_assemble_dispatch_step`, `test_bounded_hop_new_output`, cross-file loops in Touches tests, `test_review_receipt`, `test_review_refusals`) | 528 | 10% |
| free clauses | 3601 | 69% |

Of the free words I cut narrative/history/rationale clauses (below) and left operative tails whole. Truncating every free clause to its anchors plus 6 of its first 8 stems would reach ~61% (3206 words) but deletes operative tails (e.g. L6 "further full-pass waves ... before any delta pass", L28 durable-row rule). I did not do that: the author-blind audit flagged even small dropped detail. The hub decides whether to mint a floor D-row near 96% or order the truncation.

Cuts: L43, L44 dropped (narrative); clause-level narrative labels on L6 (c6, c16), L13 (c8), L28 (c2, c13), L32 (c2), L36 (c3), L40 (c1), L48 (c3), L51 (c3), L54 (c2); L11 clause 2 duplicate-of `te-artifact-own-rule-run-as-a-script`. Tail trims: L6 c10, c14; L36; L16 ("mechanical, not vibes").

## Pins deleted (plain presence asserts)
- tests/test_review_scoped_queue_pass.py::test_term_edit_pin_clause_does_not_license_a_mid_window_edit (presence half; absence half stays and is also `forbidden:`)
- tests/test_review_scoped_queue_pass.py::test_a_probed_count_is_never_replaced_by_a_seats_re_derivation (term-edit half)
- tests/test_plan_review_queue_pass.py::test_a_scripted_fix_replaces_exactly_once (function)
- tests/test_plan_review_recurring_rules.py::test_the_flip_copy_recipe_is_the_matrix_rows_method (function)
- tests/test_review_command_text_defects.py: the term-edit halves of test_the_closing_pass_confirms_zero_defects_present_not_claims_executed_true, test_the_pre_pin_sweep_lists_the_pinned_literal_term_only, test_a_trimmed_round_one_sweeps_its_unread_slices_before_any_delta_pass
- tests/test_spec_plan_lane_text.py::test_fabrik_spec_review_fetches_live_and_keeps_mechanism_in_the_plan (term-edit assert only)
- tests/test_spec_review_queue_pass.py: test_the_residue_reread_reaches_the_sections_an_edit_touches (function); test_an_executable_rule_is_run_from_round_one_not_only_at_the_close reduced to its non-term-edit include assert (its absence asserts went with the index slicing they depend on; hub: review)
Cross-file loops (HOMES, round-zero needles, mail-triage sentences) stay; their phrases are verbatim in the rewrite.

## Vanished labels (author labels — audit owed)
L43, L44 narrative; L6, L10, L11, L13, L16, L20, L28, L32, L36, L40, L41, L48, L51, L54 `rule: [own entry]`.
Note: paragraphs are single-line (a wrapped raw phrase broke two kept tests); the diff is large only because of that.

## Failure sets
Start commit, reader-test union (42 files): 147 failed / 2048 passed (box-service, quota, deck, capability-index, refusals-corpus tests; environment). End: the full union run found 149 with 2 new in `test_review_exit_contract.py` (wrapped raw phrases); fixed by unwrapping; re-run of the 15 files holding term-edit pins: 97 failures, all in the start set, 0 new. `test_command_rules.py` 32 passed; `assemble_commands.py --check` rc 1, 0 LOSS, only DIFFERS/MISSING drift.

## Self-audit
Pass 1 (fresh subagent, 4 checks): found LOST L6 c8 seat-mix parenthetical, L13 c4 grader detail, L20 example; WEAKER L10, L16; WRONG LABEL L41 c3. All six cuts restored; none remain.
COUNTS: 65 entries read / 14 reworded (8 after restores) / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels (self-assessed after fixes; no second blind pass run)

## LEFT FOR THE HUB
Author-blind Sonnet+Haiku audit; review wave; floor D-row for term-edit (see table); `_size_ceiling.json` ratchet; CHANGELOG/INDEX/D-rows; converting `# class:`/`# clauses:` comments to keys when infra-3's loader lands.
