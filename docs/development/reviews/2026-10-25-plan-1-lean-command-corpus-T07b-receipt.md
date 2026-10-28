# T07b receipt — /fabrik-review ledger and pin migration, part b

Start commit (the unit's baseline commit, unchanged from T07a): `61d1f4b99c6a8188a281f86799268fe54ee1b5d1`. The baseline file is untouched (sha256 `f20a8500…39b1`).

## Own text

`commands/_sources/fabrik-review.md`: 12,700 words before, 12,700 after (cuts nothing).

## Ledger

| | count |
|---|---|
| entries written by this ticket | 8 (65 in the ledger with part a) |
| reworded | 0 |
| classes | assigned in T07c |

Carriers: `text` on each, `forbidden:` on three absence pins (`making no code or doc claim`, `staged in the fix commit`, `every other check reads whole directories`).

## Pins deleted

- `tests/test_review_command_text_defects.py`, whole test: `test_recorded_measured_carries_a_routed_out_of_round_defect`, `test_the_decision_row_lands_after_the_code_with_its_id_reserved_before_the_close`, `test_the_gate_scope_sentence_states_the_ruff_scope_and_points_at_the_reference`.
- `tests/test_review_command_text_defects.py`, the `fabrik-review.md` assert only: `test_a_synced_path_matching_its_lock_entry_is_a_sync_write_never_reverted` (the behavioural `check_synced_unmodified.py` run stays).
- `tests/test_plan_review_queue_pass.py`, the `fabrik-review.md` assert only: `test_the_opus_floor_and_the_half_blocked_split_are_stated` (its subagents-core and plan-review asserts stay).

Kept on purpose, each a two-file or looping assert: `tests/test_review_command_text_defects.py::test_each_next_recipe_points_at_args_and_the_scripts_doc` (loops over four commands; the `--ids <the confirmed ids>` recipe window and the `which keeps its \`files\`)` window stay verbatim); `tests/test_execute_plan_d7.py::test_the_whole_plan_receipt_is_named_by_the_plan_stem_so_check_convergence_matches_it` (D7 and Reporting name the same receipt); `tests/test_spec_review_queue_pass.py::test_no_command_caps_the_workflow_pass_number` (loops over four commands); `tests/test_command_improve_queue_pass.py` (its `fabrik-review.md` hits are path-existence and a `grep -rlw review-probe-catalogue` set, so the rewrite keeps that word in the source).

## Vanished labels

None.

## Gates

- `tests/test_command_rules.py -rP`: 32 passed, 3 skipped; `LEDGER fabrik-review.yaml: 65 entries · vanished {}`, zero LOSS.
- `assemble_commands.py --check`: exit 1, every DRIFT line `DIFFERS` or `MISSING`.
- `test_command_improve_queue_pass.py test_execute_plan_d7.py test_plan_review_queue_pass.py test_review_command_text_defects.py test_spec_review_queue_pass.py`: 80 passed.

## LEFT FOR THE HUB

The author-blind audit, the review wave, `INDEX.md`, `CHANGELOG.md`, every D-row, the ceiling ratchet.
