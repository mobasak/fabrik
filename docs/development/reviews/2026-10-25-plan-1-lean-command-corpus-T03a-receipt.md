# T03a receipt — Shared fragment term-coverage, ledger and pin migration part a

Start commit (the unit's baseline commit): `61d1f4b99c6a8188a281f86799268fe54ee1b5d1`
Baseline: `commands/_rules/_shared/term-coverage.baseline.txt`, 97 units, sha256 `523ae269d7867f408329e23b6f382d6435bffff10029bef2baa00457742bbd75`.

No text was cut: `commands/_fragments/term-coverage.md` is byte-identical to the start commit (md5 `9d3b076cab2e2167fb88e34fafc8be1a`).

## Ledger
17 entries written by hand, one per pinned rule unit (a rule whose phrases sit in two units has two entries), each with `id`, `file`, `section`, `baseline` (the `;`/`—` clause holding the phrase), `current` (the unit as `command_rules.units()` returns it), at least one `text` carrier, `pins:` (the retired test node ids) and a `# class:` comment (the loader on this base has no `class` key). Classes: ban 6, grammar 2, prose 9 (counted by entry).

## Pins deleted (test node ids)
- tests/test_command_improve_queue_pass.py::test_a_widened_subject_and_a_recipe_meet_their_breaking_inputs_before_the_pin (the `coverage`/`classes` assert only; the rest of the test stays)
- tests/test_review_queue_pass.py::test_a_scope_growth_remainder_round_restates_every_slice (function)
- tests/test_review_queue_pass.py::test_the_scope_paragraph_says_where_round_zero_and_rule_five_bind (function)
- tests/test_review_queue_pass.py::test_rule_three_pointer_is_opened_before_the_pin (function)
- tests/test_review_queue_pass.py::test_round_zero_opens_a_pointer_from_every_repo_the_surface_ships_to (function)
- tests/test_review_queue_pass.py::test_round_zero_writes_one_owner_for_a_fact_from_the_first_draft (function)
- tests/test_review_queue_pass.py::test_rule_three_rewrites_a_heuristic_picker_at_its_first_residue (function; its absence pin `a heuristic that SELECTS` is a `forbidden:` carrier)
- tests/test_review_queue_pass.py::test_obligation_three_names_the_committed_fix_form_where_it_starts (function)
- tests/test_review_queue_pass.py::test_an_equivalent_mutant_is_discarded_never_reported_as_a_test_gap (the fragment assert only; the catalogue assert stays)
- tests/test_review_queue_pass.py::test_a_fix_is_probed_against_every_shape_the_form_it_replaces_held (the two fragment asserts only)
- tests/test_review_queue_pass.py::test_a_review_whose_fixes_are_committed_makes_its_receipt_once (the fragment clause loop only; the source and task asserts stay)
- tests/test_review_queue_pass.py::test_rule_three_rewrite_first_asks_whether_the_branch_can_go (the single-file `picker` assert only)
- tests/test_review_scoped_queue_pass.py::test_a_mutant_is_killed_against_whole_test_files_after_each_fix (the rule-4 assert only)
- tests/test_review_scoped_queue_pass.py::test_a_rule_or_recipe_a_fix_adds_runs_over_round_zeros_input_classes_before_the_pin (the two fragment asserts only)
- tests/test_review_scoped_queue_pass.py::test_a_probed_count_is_never_replaced_by_a_seats_re_derivation (the fragment assert only; its two-file absence loop stays)

## Kept (assert loops over two files, spine § Global Constraints)
test_round_zero_runs_a_guard_the_fix_adds_over_the_fix_itself and test_briefs_durable_unchanged_slices_said_guards_round_trip_counts_from_receipt (loops over `term-coverage` and `term-edit`); the phrases they hold stay verbatim in the rewrite.

## Gates
- `python3 -m pytest -q tests/test_command_rules.py -rP`: 32 passed, 3 skipped; prints `LEDGER term-coverage.yaml: 17 entries · vanished {}`, zero LOSS.
- `python3 commands/assemble_commands.py --check`: exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING`.
- the three Touches tests: 109 passed, 1 failed; the failure (`test_a_cwd_rooted_tool_runs_after_an_os_chdir`) is red at the start commit too (the clone lacks the box's cwd tooling).
