# T03b receipt — Shared fragment term-coverage, ledger and pin migration part b

Start commit: the T03a commit on this branch (the unit's baseline commit stays `61d1f4b99c6a8188a281f86799268fe54ee1b5d1`; the baseline and its sha256 are unchanged).

No text was cut: `commands/_fragments/term-coverage.md` is byte-identical (md5 `9d3b076cab2e2167fb88e34fafc8be1a`).

## Ledger
Six entries added by hand to the part-a ledger (17 → 23): `tc-closing-pass-confirms-zero-defects` (prose), `tc-fix-touched-slice-added-by-hand` (prose, with the `forbidden:` carrier `builds slices only from the `--ids` passed`), `tc-prepin-sweep-lists-literal-term` (prose), `tc-round-zero-header` (grammar), `tc-round-zero-input-space-duty-leads` (prose), `tc-round-zero-mutation-battery-follows` (prose). Each lists its retired test node under `pins:`.

## Pins deleted (test node ids)
- tests/test_review_command_text_defects.py::test_the_closing_pass_confirms_zero_defects_present_not_claims_executed_true (the `tc` presence assert only; the term-edit assert and the two-file absence loop stay)
- tests/test_review_command_text_defects.py::test_a_fix_touched_slice_with_no_candidate_is_added_by_hand (the `tc` presence and absence asserts only; the behavioural half that drives `review_loop_ledger.py` stays)
- tests/test_review_command_text_defects.py::test_the_pre_pin_sweep_lists_the_pinned_literal_term_only (the term-coverage presence assert only; the term-edit assert, the two-file absence loop and the behavioural `check_review_hygiene.py` run stay)
- tests/test_term_coverage_round_zero.py::test_the_input_space_duty_leads_round_zero (the whole file: its only test asserted nothing but the fragment's text)

## Kept (assert loops over two files, never migrated into one ledger)
tests/test_bounded_hop_new_output.py (parametrized over three homes), tests/test_plan_review_queue_pass.py::test_round_zero_scripts_step_references_and_mutant_predictions and ::test_a_behavioural_fix_claim_cites_its_branch_in_both_round_zero_homes, tests/test_plan_review_recurring_rules.py::test_round_zero_cites_the_callee_in_both_review_contracts. The phrases they hold stay verbatim in the rewrite.

## Gates
- `tests/test_command_rules.py -rP`: all passed, one LEDGER line for `term-coverage.yaml`, zero LOSS.
- `assemble_commands.py --check`: exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING`.
- the five Touches tests: green.
