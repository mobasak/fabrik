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

## Re-ledger round (canonical D-1236 loader, branch claude/lean-t04-rl)
- LOSS (own ledger `_shared/term-edit.yaml`): 11 -> 0 (`test_command_rules.py -rP` prints no term-edit LOSS line; its LEDGER line reads 62 entries, classes ban 40 / grammar 4 / prose 18, vanished narrative 2 / rule 12). `assemble_commands.py --check` exits 4, LOSS lines only in the other units' `_shared` ledgers.
- Keys: all 62 `# class:` and the 10 `# clauses:` comments are now real keys. Causes of the 11 LOSS: the comment labels were invisible to the loader, and four label indexes were written under the old clause split (L6 `{6,16}`, L13 `{8}`, L28 `{13}`, L51 `{3}`). Fixed: L13 `{6}`, L28 `{2,11}`, L6 and L51 none; L6 clause 2 and clause 10 restored to the baseline text from their ban word (D-1240 lint D); L51 "— D-219" restored (anchor).
- Cuts added this round (clause-level, no ban word, no kept-test pin): L11 clause 4 (narrative), L30 clause 2 (narrative), L41 clause 2 (narrative), L49 the "Three thoughts ..." sentence. Restored after my own audit: L6 clause 9 and clause 12 parentheticals (per-clause stems 4/8 and a dropped `1` anchor), L16 "(mechanical, not vibes)".
- Own-text words, UTF-8 `wc -w`: baseline 5354 -> before 5129 -> now about 5112 (**95.5%**). This runner has no `wc`, so the figure is the previous receipt's measured 5129 minus 62 removed plus 45 restored words, counted by hand; the hub's measure decides.
- Entries reworded: 12 of 62 (L6, L11, L13, L28, L30, L32, L36, L40, L41, L48, L49, L54); L43/L44 vanished as narrative.
- Why it is still over 50%: the previous floor table stands (ban-word clauses verbatim 21%, phrases pinned by kept tests 10%, free clauses 69%). The pins that hold the largest free text are `test_review_exit_contract` (rule (3), the scope-growth hand-over, the D4/D5 phrases), `test_review_queue_pass` / `test_plan_review_queue_pass` / `test_review_scoped_queue_pass` (round-zero rules (1)-(3) and the guard round-trip sentence), `test_assemble_dispatch_step` (the `--doc` sentence run in step 3), `test_bounded_hop_new_output`, `test_review_loop_workflow` (the closing-seat reason and its § 4.7 quote). Per entry:

| Entry (baseline line) | Why its remaining clauses cannot shrink |
|---|---|
| L3, L5, L37, L38, L39, L46, L47, L49, L50, L52, L53, L57-L60 | every clause holds a ban word; verbatim from the ban word to the end of its `;`/`—` clause, and the pre-ban words are inside the anchors-plus-6 window |
| L4, L6, L7 | ban clauses (L4 c2/c4, L6 c1/c2/c10/c15, L7 c3) verbatim; L6 c9/c11/c12 pinned by `test_review_exit_contract` (D4, D5) and anchor-dense (`I#` `D#` `G#` `T##` `path:line`) |
| L20, L22, L23, L25, L26, L28 | ban clauses cover the long parentheticals (L23 c1 and c6, L22 `only`-clauses); L22 `--doc` sentences, L25 round-zero rule (1) and the guard sentences, L26, L28 rule (3) text are pinned verbatim by the kept tests above |
| L12, L13, L29, L31, L33, L35, L41, L42, L45, L48, L51, L54-L56, L61 | one to three clauses of 10-45 words whose first 8 stems end inside the clause; the free tail past the window is an operative instruction (what to run, what to record), not narrative, so I left it rather than truncate to anchors plus 6 stems |
| L62-L65 | grammar rows, verbatim by class |
Truncating every free clause to anchors plus 6 of 8 stems would reach about 61% (previous receipt's measure); I did not do it, and the hub decides whether to order it.
- Self-audit: no subagent can be dispatched from this runner, so the pass below is my own line-by-line read of the baseline against the rewrite, NOT a fresh subagent; the hub's author-blind audit pair covers the zero-counts requirement. Pass 1 (own) found and fixed: L6 c9 WEAKER, L6 c12 WEAKER (dropped anchor), L16 WEAKER (restored), L51 lost anchor D-219, stale vanished labels L16/L51 (removed), wrong clause-label indexes on L6/L13/L28/L51. Judgement calls for the blind pair: L11 c4, L28 c2 (`denominator-honesty` pointer), L36 c2 trim, L44, L48 c3, L49.
COUNTS: 62 entries read / 12 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels (own pass 2 after the fixes, not a fresh subagent)
- Failure sets (reader-test run, 8 groups): start and end both 95 failed (all in `test_review_refusals.py`) plus 1 failed (`test_conftest_isolation.py::test_the_two_live_box_tests_pass_a_merge_check_on_a_drifted_box`); every other group passed (435, 100, 126, plus the assemble/corpus groups); set did not grow.
