# T07a receipt — /fabrik-review ledger and pin migration, part a

Start commit (the unit's baseline commit): `61d1f4b99c6a8188a281f86799268fe54ee1b5d1` (`origin/kaizen-lean-u01`).
Baseline: `commands/_rules/fabrik-review.baseline.txt`, 278 units, sha256 `f20a8500b2c92511eaccf9eab6930716790992faa981206519d6b03bdf5839b1`, written with `command_rules.write_baseline(own_text(source))`.

## Own text

`commands/_sources/fabrik-review.md`: 12,700 words before, 12,700 after (the source is byte-identical; this ticket cuts nothing).

## Ledger

| | count |
|---|---|
| entries written by this ticket | 57 |
| reworded | 0 (no text moved) |
| classes | assigned to every entry in T07c, where the entries are regenerated with their class |

Carriers: `text` on each, `forbidden:` on 6 absence pins (`a fresh hunt of their own slice`, `A seat that returns nothing is a FAILED seat`, `or from the new one`, `matcher clause`, `owners only`, `opus×1 + sonnet×3`), `ordered:` on 3 groups (the checklist fill before the close ORDER, the four close steps, the slices rule before the TERMINAL sentence).

## Pins deleted (`tests/test_review_queue_pass.py`)

Whole test deleted: `test_agent_tool_shape_covers_a_review_the_operator_did_not_invoke`, `test_a_failed_refuters_candidates_are_executed_by_the_lead`, `test_the_delta_brief_names_its_must_read_files`, `test_next_rows_merge_into_slices_by_name`, `test_a_refuter_that_returns_nothing_is_not_re_dispatched_as_a_finder`, `test_close_order_stages_before_the_in_progress_gate`, `test_trimmed_single_finder_slice_gets_its_second_next_wave`, `test_the_round_grammar_names_own_fix`, `test_the_checklist_is_filled_before_the_in_progress_gate_run`, `test_the_receipt_sentence_says_owners_only_inside_the_by_design_parentheses`, `test_the_slices_ledger_is_defined_with_its_closing_example`, `test_a_fixture_equal_to_the_codes_own_literal_is_a_test_quality_finding`, `test_the_gate_runs_before_the_closing_pin_so_a_gate_fix_is_reviewed`, `test_an_in_surface_red_at_the_close_reopens_a_closing_pass_over_the_fix`, `test_a_duplicate_raise_of_a_confirmed_defect_is_not_a_residual_row`, `test_a_seat_proposed_behaviour_change_is_probed_against_its_bound`, `test_a_later_pass_brief_carries_the_environment_earlier_seats_set`, `test_a_generated_script_names_each_root_only_path_as_a_referent`, `test_the_example_ledger_names_the_file_loops_seat_mix`, `test_a_routed_fix_carries_its_invariant_and_shapes`.

SRC asserts removed, rest of the test kept: `test_phase_one_points_at_the_probe_catalogue`, `test_a_callers_plan_flip_follows_the_post_flip_gate_run`, `test_the_closing_method_cell_rule_matches_the_gate`, `test_an_agent_tool_seat_gets_the_pin_import_placement`, `test_a_fix_is_probed_against_every_shape_the_form_it_replaces_held` (its catalogue and term-coverage asserts and the `2026-` absence stay), `test_the_fourth_pass_answers_its_recurring_subjects_in_their_homes` (catalogue asserts stay), `test_a_by_design_d_owner_is_a_ledger_row_and_the_refusals_point_at_the_gate`, `test_briefs_durable_unchanged_slices_said_guards_round_trip_counts_from_receipt`, `test_the_close_order_is_a_numbered_list_with_the_embed_its_own_step` (the list-shape assert on raw text stays), `test_a_counter_word_in_a_method_cell_is_named_as_refused`, `test_a_review_whose_fixes_are_committed_makes_its_receipt_once`, `test_a_seat_scratch_repo_is_checked_and_git_runs_hermetic`.

Kept on purpose (rule: a two-file or looping assert stays; a behavioural test keeps its pins):
- `tests/test_review_queue_pass.py`: `test_the_opt_in_fallback_is_stated_in_every_copy`, `test_every_workflow_command_carries_the_no_workflow_in_the_hub_note`, `test_both_review_commands_carry_the_seat_isolation_sentence_verbatim`, `test_next_prints_name_and_ledger_rows_and_nothing_for_no_ids`, `test_the_receipt_template_shows_the_gate_scope_line_the_gate_accepts_filled`.
- `tests/test_review_scoped_queue_pass.py`: no assert deleted. Every assert there that reads `fabrik-review.md` relates it to `fabrik-review-scoped.md` or the catalogue (`test_the_pre_pin_section_reads_as_every_pin_not_only_the_first`, `test_both_review_commands_name_surface_add_for_a_pre_start_file`, `test_the_lead_runs_the_leak_check_around_every_scoped_pass`, `test_a_fix_reshaping_a_rule_subject_lists_the_old_cases_before_drafting`), so each of those sentences stays verbatim in the rewrite.

Each retired node is listed under `pins:` of its entry.

## Vanished labels

None (nothing is cut here).

## Gates

- `tests/test_command_rules.py -rP`: 32 passed, 3 skipped; `LEDGER fabrik-review.yaml: 57 entries · vanished {}`, zero LOSS.
- `assemble_commands.py --check`: exit 1, every DRIFT line is `DIFFERS` or `MISSING`.
- `tests/test_review_queue_pass.py tests/test_review_scoped_queue_pass.py`: 61 passed, 1 failed. The failure, `test_a_cwd_rooted_tool_runs_after_an_os_chdir`, needs `psutil`, absent in this clone, and fails the same at the start commit.

## LEFT FOR THE HUB

The author-blind audit, the review wave, the `INDEX.md` row for the new `commands/_rules/fabrik-review.*` files, `CHANGELOG.md`, every D-row, the ceiling ratchet.
