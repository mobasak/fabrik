# T08 receipt — lean rewrite of /fabrik-task (full form)

Start commit (baseline): `61d1f4b99c6a8188a281f86799268fe54ee1b5d1`; `baseline_sha256` 557c3d14c5e453fc64cda7a7adb64705a5edb20690bb4440e535fdd152179582. Branch `claude/lean-t08`. Loader: `_ENTRY` has no `class`/`clauses` keys, so classes are `# class:` comments and clause labels `# clauses:` comments (the hub converts them). Vanished labels are author labels — audit owed.

## Own text before -> after

| measure | before | after | ratio |
|---|---|---|---|
| `command_rules.units()` words | 4263 | 3617 | 84.8% |
| `wc -w` of the source | 4425 | 3779 | 85.4% |

**Target <=50% NOT met.** Floor under the D-1240 reading as applied: ban tails verbatim (915 baseline words in 58 ban-bearing clauses; the 240-word `never a source read or a proxy:` clause and the 67-word `never in it (…)` clause alone are 307), five fenced command lines kept verbatim (201 words), every anchor of a clause inside ONE phrase, and 70% of each clause's first 8 stems. Words those rules require: 2349 of the 3565 entry words (+52 heading words) = 2401, i.e. 56% of the baseline, and reaching it means deleting ~1160 grammar-glue words (articles were removed mechanically, the rest left for readability). The hub mints the floor D-row: live rules 99 entries, ~36 words per rule.

## Entries

99 entries total; reworded: 90 (the rest are carried verbatim: fences and short units). By class: ban 44, prose 49, behavioural 5 (the four fenced command lines the parser tests run, plus the capture line), grammar 1 (`UPGRADE:` token rule). Each entry has ONE `text` phrase = its whole new unit (>=6 words, unique in the file); coverage of every baseline clause it names was checked by a separate lint (anchors all present, >=70% of first-8 stems, ban tail verbatim to the end of its `;`/` — ` clause).

Per-entry table (kept words, words D-1240 requires, why the rest stays):

| entry | class | baseline clause words | kept | required | why not smaller |
|---|---|---|---|---|---|
| ft-sequences-machinery | prose | 35 | 26 | 15 | anchors + first-8 stems; the 11 others are grammar glue between required spans |
| ft-slices-never-bundled | ban | 17 | 14 | 12 | ban tail 5w verbatim + anchors + first-8 stems; the 2 others are grammar glue between required spans |
| ft-lane-versions | prose | 25 | 23 | 20 | anchors + first-8 stems; the 3 others are grammar glue between required spans |
| ft-lane-v2-mechanisms | ban | 36 | 28 | 25 | ban tail 13w verbatim + anchors + first-8 stems; the 3 others are grammar glue between required spans |
| ft-lane-start-done-refused | ban | 28 | 27 | 23 | ban tail 11w verbatim + anchors + first-8 stems; the 4 others are grammar glue between required spans |
| ft-handoff-third-terminal | prose | 11 | 10 | 8 | anchors + first-8 stems; the 2 others are grammar glue between required spans |
| ft-durable-is-scratch | ban | 36 | 30 | 25 | ban tail 4w verbatim + anchors + first-8 stems; the 5 others are grammar glue between required spans |
| ft-worktree-scratch-copy | ban | 53 | 52 | 46 | ban tail 38w verbatim + anchors + first-8 stems; the 6 others are grammar glue between required spans |
| ft-size-lane-table | prose | 23 | 16 | 11 | anchors + first-8 stems; the 5 others are grammar glue between required spans |
| ft-size-start-line | behavioural | 36 | 36 | 9 | fence: grammar a parser/test reads, verbatim; the 27 others are grammar glue between required spans |
| ft-size-consumers | prose | 12 | 10 | 8 | anchors + first-8 stems; the 2 others are grammar glue between required spans |
| ft-size-heavy-operator-named | prose | 15 | 14 | 10 | anchors + first-8 stems; the 4 others are grammar glue between required spans |
| ft-size-file-repeatable | prose | 8 | 8 | 6 | anchors + first-8 stems; the 2 others are grammar glue between required spans |
| ft-size-new-path-declared | ban | 76 | 68 | 38 | ban tail 11w verbatim + anchors + first-8 stems; the 30 others are grammar glue between required spans |
| ft-size-code-surface-only | ban | 33 | 29 | 22 | ban tail 8w verbatim + anchors + first-8 stems; the 7 others are grammar glue between required spans |
| ft-size-tool-prints | ban | 45 | 40 | 30 | ban tail 12w verbatim + anchors + first-8 stems; the 10 others are grammar glue between required spans |
| ft-size-sync-skipped | prose | 13 | 12 | 9 | anchors + first-8 stems; the 3 others are grammar glue between required spans |
| ft-size-refusal-is-answer | ban | 29 | 27 | 23 | ban tail 15w verbatim + anchors + first-8 stems; the 4 others are grammar glue between required spans |
| ft-size-cobra | prose | 47 | 40 | 22 | anchors + first-8 stems; the 18 others are grammar glue between required spans |
| ft-measure-failure-replay | ban | 64 | 62 | 57 | ban tail 48w verbatim + anchors + first-8 stems; the 5 others are grammar glue between required spans |
| ft-measure-miss-is-finding | ban | 49 | 43 | 35 | ban tail 27w verbatim + anchors + first-8 stems; the 8 others are grammar glue between required spans |
| ft-measure-proposed-fix-replayed | prose | 37 | 23 | 13 | anchors + first-8 stems; the 10 others are grammar glue between required spans |
| ft-measure-unreachable-tool | ban | 22 | 19 | 11 | ban tail 3w verbatim + anchors + first-8 stems; the 8 others are grammar glue between required spans |
| ft-measure-record-to-file | ban | 86 | 85 | 78 | ban tail 67w verbatim + anchors + first-8 stems; the 7 others are grammar glue between required spans |
| ft-measure-fetch-diff | prose | 30 | 22 | 17 | anchors + first-8 stems; the 5 others are grammar glue between required spans |
| ft-measure-prior-record | prose | 41 | 28 | 17 | anchors + first-8 stems; the 11 others are grammar glue between required spans |
| ft-measure-population | ban | 119 | 97 | 64 | ban tail 42w verbatim + anchors + first-8 stems; the 33 others are grammar glue between required spans |
| ft-measure-contracts-live | ban | 13 | 12 | 10 | ban tail 3w verbatim + anchors + first-8 stems; the 2 others are grammar glue between required spans |
| ft-measure-execute-real-path | ban | 273 | 268 | 247 | ban tail 240w verbatim + anchors + first-8 stems; the 21 others are grammar glue between required spans |
| ft-measure-grader-red | prose | 23 | 18 | 7 | anchors + first-8 stems; the 11 others are grammar glue between required spans |
| ft-measure-select-rules | prose | 13 | 12 | 9 | anchors + first-8 stems; the 3 others are grammar glue between required spans |
| ft-design-six-fields | prose | 17 | 19 | 10 | anchors + first-8 stems; the 9 others are grammar glue between required spans |
| ft-design-copied-mechanism | prose | 23 | 17 | 7 | anchors + first-8 stems; the 10 others are grammar glue between required spans |
| ft-design-read-before-copy | prose | 35 | 24 | 16 | anchors + first-8 stems; the 8 others are grammar glue between required spans |
| ft-design-input-table | prose | 53 | 44 | 9 | anchors + first-8 stems; the 35 others are grammar glue between required spans |
| ft-design-parser-grammar | prose | 21 | 16 | 13 | anchors + first-8 stems; the 3 others are grammar glue between required spans |
| ft-design-table-live-rows | ban | 35 | 30 | 10 | ban tail 2w verbatim + anchors + first-8 stems; the 20 others are grammar glue between required spans |
| ft-design-marker-block-states | ban | 20 | 19 | 18 | ban tail 17w verbatim + anchors + first-8 stems; the 1 others are grammar glue between required spans |
| ft-design-parser-tag-quoted | prose | 19 | 18 | 7 | anchors + first-8 stems; the 11 others are grammar glue between required spans |
| ft-design-plan-locks | prose | 66 | 39 | 20 | anchors + first-8 stems; the 19 others are grammar glue between required spans |
| ft-design-pre-seat-checklist | ban | 55 | 43 | 33 | ban tail 4w verbatim + anchors + first-8 stems; the 10 others are grammar glue between required spans |
| ft-design-brief-execute | ban | 115 | 100 | 64 | ban tail 18w verbatim + anchors + first-8 stems; the 36 others are grammar glue between required spans |
| ft-design-brief-pins-tree | prose | 41 | 32 | 11 | anchors + first-8 stems; the 21 others are grammar glue between required spans |
| ft-design-wait-in-turn | prose | 20 | 14 | 8 | anchors + first-8 stems; the 6 others are grammar glue between required spans |
| ft-design-concern-accepted | ban | 48 | 40 | 37 | ban tail 23w verbatim + anchors + first-8 stems; the 3 others are grammar glue between required spans |
| ft-design-second-approach | ban | 34 | 30 | 15 | ban tail 5w verbatim + anchors + first-8 stems; the 15 others are grammar glue between required spans |
| ft-design-before-record | prose | 68 | 49 | 32 | anchors + first-8 stems; the 17 others are grammar glue between required spans |
| ft-design-step-line | behavioural | 13 | 13 | 6 | fence: grammar a parser/test reads, verbatim; the 7 others are grammar glue between required spans |
| ft-design-terminal-amend | ban | 46 | 44 | 32 | ban tail 16w verbatim + anchors + first-8 stems; the 12 others are grammar glue between required spans |
| ft-design-no-decision-amend | prose | 13 | 11 | 7 | anchors + first-8 stems; the 4 others are grammar glue between required spans |
| ft-design-stores-text | prose | 8 | 8 | 6 | anchors + first-8 stems; the 2 others are grammar glue between required spans |
| ft-design-refusal-discards | ban | 26 | 25 | 25 | ban tail 25w verbatim + anchors + first-8 stems |
| ft-design-behaviours-cap | prose | 19 | 16 | 12 | anchors + first-8 stems; the 4 others are grammar glue between required spans |
| ft-design-paths-named | ban | 102 | 95 | 54 | ban tail 17w verbatim + anchors + first-8 stems; the 41 others are grammar glue between required spans |
| ft-design-amend-top-record | ban | 16 | 13 | 11 | ban tail 5w verbatim + anchors + first-8 stems; the 2 others are grammar glue between required spans |
| ft-mirror-mandatory | ban | 63 | 58 | 26 | ban tail 2w verbatim + anchors + first-8 stems; the 32 others are grammar glue between required spans |
| ft-mirror-search-scope | ban | 201 | 132 | 47 | ban tail 11w verbatim + anchors + first-8 stems; the 85 others are grammar glue between required spans |
| ft-mirror-fail-direction | prose | 19 | 17 | 12 | anchors + first-8 stems; the 5 others are grammar glue between required spans |
| ft-mirror-names-exist | prose | 21 | 19 | 8 | anchors + first-8 stems; the 11 others are grammar glue between required spans |
| ft-mirror-untouched-reader | prose | 21 | 18 | 9 | anchors + first-8 stems; the 9 others are grammar glue between required spans |
| ft-design-fields-are-d-row | prose | 24 | 20 | 9 | anchors + first-8 stems; the 11 others are grammar glue between required spans |
| ft-design-pipe-escape | prose | 16 | 13 | 11 | anchors + first-8 stems; the 2 others are grammar glue between required spans |
| ft-build-lock-recheck | prose | 18 | 15 | 10 | anchors + first-8 stems; the 5 others are grammar glue between required spans |
| ft-build-red-first | ban | 39 | 35 | 24 | ban tail 7w verbatim + anchors + first-8 stems; the 11 others are grammar glue between required spans |
| ft-build-commits | ban | 42 | 41 | 34 | ban tail 8w verbatim + anchors + first-8 stems; the 7 others are grammar glue between required spans |
| ft-build-graders | prose | 61 | 56 | 20 | anchors + first-8 stems; the 36 others are grammar glue between required spans |
| ft-build-no-formatter | ban | 10 | 10 | 10 | ban tail 10w verbatim + anchors + first-8 stems |
| ft-build-gate-helpers | ban | 43 | 41 | 41 | ban tail 36w verbatim + anchors + first-8 stems |
| ft-build-store-tests | prose | 69 | 55 | 18 | anchors + first-8 stems; the 37 others are grammar glue between required spans |
| ft-review-invoke | ban | 66 | 63 | 55 | ban tail 20w verbatim + anchors + first-8 stems; the 8 others are grammar glue between required spans |
| ft-review-full-over-committed | prose | 59 | 46 | 28 | anchors + first-8 stems; the 18 others are grammar glue between required spans |
| ft-review-seat-questions | ban | 80 | 61 | 23 | ban tail 4w verbatim + anchors + first-8 stems; the 38 others are grammar glue between required spans |
| ft-review-untouched-declared | ban | 32 | 30 | 18 | ban tail 8w verbatim + anchors + first-8 stems; the 12 others are grammar glue between required spans |
| ft-review-decision-changed | prose | 52 | 41 | 21 | anchors + first-8 stems; the 20 others are grammar glue between required spans |
| ft-review-sized | prose | 43 | 38 | 25 | anchors + first-8 stems; the 13 others are grammar glue between required spans |
| ft-review-urgent-checkpoint | prose | 32 | 25 | 12 | anchors + first-8 stems; the 13 others are grammar glue between required spans |
| ft-close-doc-sync | prose | 12 | 11 | 9 | anchors + first-8 stems; the 2 others are grammar glue between required spans |
| ft-close-d-row | prose | 22 | 18 | 11 | anchors + first-8 stems; the 7 others are grammar glue between required spans |
| ft-close-changelog | prose | 8 | 7 | 6 | anchors + first-8 stems; the 1 others are grammar glue between required spans |
| ft-close-final-gate | prose | 6 | 6 | 5 | anchors + first-8 stems; the 1 others are grammar glue between required spans |
| ft-close-commit-capture | prose | 18 | 16 | 7 | anchors + first-8 stems; the 9 others are grammar glue between required spans |
| ft-close-capture-line | behavioural | 58 | 58 | 12 | fence: grammar a parser/test reads, verbatim; the 46 others are grammar glue between required spans |
| ft-close-push-then-close | ban | 21 | 20 | 17 | ban tail 4w verbatim + anchors + first-8 stems; the 3 others are grammar glue between required spans |
| ft-close-done-line | behavioural | 22 | 22 | 5 | fence: grammar a parser/test reads, verbatim; the 17 others are grammar glue between required spans |
| ft-close-v1-undeclared | ban | 16 | 14 | 11 | ban tail 2w verbatim + anchors + first-8 stems; the 3 others are grammar glue between required spans |
| ft-close-v2-undeclared-refuses | ban | 25 | 24 | 21 | ban tail 12w verbatim + anchors + first-8 stems; the 3 others are grammar glue between required spans |
| ft-close-contract-newsource-refuses | ban | 25 | 25 | 23 | ban tail 15w verbatim + anchors + first-8 stems; the 2 others are grammar glue between required spans |
| ft-close-receipt-range-tip | ban | 205 | 195 | 131 | ban tail 53w verbatim + anchors + first-8 stems; the 64 others are grammar glue between required spans |
| ft-close-review-before-commit | prose | 29 | 27 | 18 | anchors + first-8 stems; the 9 others are grammar glue between required spans |
| ft-close-evidence-split | prose | 29 | 23 | 16 | anchors + first-8 stems; the 7 others are grammar glue between required spans |
| ft-upgrade-crossing | ban | 84 | 72 | 45 | ban tail 4w verbatim + anchors + first-8 stems; the 27 others are grammar glue between required spans |
| ft-upgrade-token-begins | grammar | 50 | 49 | 34 | ban tail 14w verbatim + anchors + first-8 stems; the 15 others are grammar glue between required spans |
| ft-upgrade-to-spec-chain | prose | 21 | 20 | 14 | anchors + first-8 stems; the 6 others are grammar glue between required spans |
| ft-upgrade-handoff-line | behavioural | 22 | 22 | 5 | fence: grammar a parser/test reads, verbatim; the 17 others are grammar glue between required spans |
| ft-upgrade-in-place | prose | 57 | 54 | 36 | anchors + first-8 stems; the 18 others are grammar glue between required spans |
| ft-upgrade-done-not-handoff | prose | 6 | 6 | 6 | anchors + first-8 stems |
| ft-upgrade-sync-refused | ban | 27 | 24 | 17 | ban tail 1w verbatim + anchors + first-8 stems; the 7 others are grammar glue between required spans |
| ft-upgrade-v2-last-four | ban | 38 | 37 | 27 | ban tail 9w verbatim + anchors + first-8 stems; the 10 others are grammar glue between required spans |
| ft-upgrade-typing-early | ban | 23 | 23 | 22 | ban tail 16w verbatim + anchors + first-8 stems; the 1 others are grammar glue between required spans |

## Clause labels (comments) and vanished lines

Clause-level: {1: narrative}; {1: narrative}; {1: narrative}; {1: narrative}.

Vanished lines: 88 labelled (87 `rule: [ids]`, 1 `narrative`: L2 — `L53.1`, `L21.1`, `L31.1`, `L84.1` are clause-level narrative inside covered lines, each a gloss or id cited as history, none holds a ban word). Every duplicate-of label from the first pass was withdrawn after the audit.

## Pins deleted (test node ids)

Whole functions removed or reduced to their absence/behaviour asserts, in the four Touches test files; every phrase is a ledger carrier or was cut:

- `tests/test_command_improve_queue_pass.py`
- `test_fabrik_task_third_queue_pass_lines`
- `tests/test_fabrik_task_queue_pass.py`
- `test_size_check_ignores_each_new_path`
- `test_size_checks_each_declared_path_before_declaring_it`
- `test_measure_executes_the_real_path`
- `test_the_lane_critique_brief_asks_seats_to_execute`
- `test_the_pre_record_checklist_sits_before_the_record_call`
- `test_mirror_searches_the_whole_tree_and_names_fail_direction`
- `test_second_pass_names_the_specific_steps_in_their_phases`
- `test_phase_four_names_the_committed_work_receipt_up_front`
- `test_the_plan_lock_check_runs_before_the_design_is_recorded`
- `test_measure_finds_exact_set_asserts_and_behaviours_carry_a_copied_scripts_settled_failures`
- `test_measure_greps_config_and_env_values_and_design_reads_a_copied_rule_first`
- `test_review_fix_commits_go_through_the_capture_and_mirror_censuses_the_whole_ast`
- `test_measure_greps_a_work_items_cited_line_before_the_design_takes_its_wording`
- `test_a_phase_2_critique_naming_an_unsettled_second_approach_is_the_upgrade_crossing`
- `test_build_re_runs_the_population_measurement_for_a_changed_check_or_guard`
- `test_measure_replays_the_items_proposed_fix_and_reads_an_unreachable_source`
- `test_measure_greps_the_prior_record_by_the_items_id`
- `test_design_tables_a_written_files_malformed_shapes`
- `test_the_brief_fetches_provider_docs_for_seats_without_web`
- `test_design_amend_runs_while_the_task_record_is_on_top`
- `test_the_inputs_table_comes_from_measures_read_of_the_live_rows`
- `test_design_tables_each_new_parser_tag_quoted_inside_its_content`
- `test_the_vendored_copy_census_counts_the_worktrees_apart`
- `test_a_second_design_is_ignored_with_only_a_note`
- `test_review_amends_each_path_a_fix_touches_at_phase_4_after_the_nested_review`
- `test_mirror_searches_other_checkouts_tests_for_a_changed_path`
- `test_plan_locks_are_read_before_the_critique_seats_and_the_terminal_before_design`
- `test_measure_says_a_zero_count_is_no_fail_direction`
- `tests/test_fabrik_task_source.py`
- `test_measure_lists_what_phase_1_executes_before_the_design`
- `(renamed, absence pins only) test_the_command_source_shows_the_space_form_of_multi_commit_only`
- `test_design_note_names_behaviours_cap_and_the_design_amend_remedy`
- `test_build_and_review_sections_name_multicommit_sync_commit_and_full_review`
- `test_close_section_refuses_undeclared_and_close_time_contract_hits`
- `(renamed, absence pins only) test_upgrade_section_never_describes_the_close_raised_tokens_as_typed_by_hand`
- `test_upgrade_section_gains_the_four_close_raised_tokens`
- `test_independent_slices_are_several_task_runs`
- `tests/test_review_queue_pass.py`

Also removed inside kept tests: presence asserts on cut text in `tests/test_fabrik_task_queue_pass.py` (test_design_tabulates_its_inputs_and_the_close_captures_by_subject, test_measure_executes_the_incidents_sequel…, test_v1_commits_once…, test_the_third_review_question…, test_the_receipt_range_tip_is_the_last_commit), `tests/test_fabrik_task_source.py::test_the_run_files_live_in_the_scratch_path_start_prints` (incl. the `raw.count("<durable>") == 11` count pin), `tests/test_review_queue_pass.py::test_a_review_whose_fixes_are_committed_makes_its_receipt_once` (the three fabrik-task asserts). Absence pins stay. Ordering pins became `ordered:` carriers (phase 5 steps; plan-locks → pre-seat checklist → brief → record).

## Failure sets (reader-test run, 61 files)

Start commit: 59 failed, 3125 passed, 25 skipped (59 pre-existing reds: box services/ssh/rotate etc.)
End: 59 failed, 3092 passed, 25 skipped (identical set to the start)
New failures vs start: see line above; no new failure; 33 fewer passes = the 33 deleted pin tests.

## Self-audit

Pass 1 (author-blind Opus subagent over baseline/rewrite/ledger): weaker 1 (dropped `Two`), invented 2, wrong labels 4, sentence-drops 12. All restored or relabelled in pass 2 (restored: `Two`, D7 qualifier, golden/snapshot condition, the L25 pointer as carried text, `design_amends`, resume artifacts, sibling write paths, unmerged-branch, population measurement, store tests, unit/guard table rows, duplicates-of-key, close-ORDER steps, runway sizing, `or none`, evidence `on or before`, and the other meaning-changing cuts it listed). Mechanical audit (`audit.py`, reads only the committed ledger/source/baseline): LOST 0, WEAKER 0, WRONG 0.

COUNTS: 99 entries read / 90 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels — as measured by the mechanical audit; the author-blind pass-2 re-audit is owed to the hub.

## Fix round 2 (hub audit)

Findings: two author-blind audits (Sonnet 24, Haiku 29, overlapping) plus 5 master-loader LOSS lines. Confirmed 29 distinct, refuted 0; every one was checked against the baseline line and found real.

Restored (source and ledger `current`/`text` together): `ft-mirror-search-scope` (UI, docs, hardcoded values, "outside it", "by the file's name", "every Python reader of a name"); `ft-design-brief-pins-tree` (no provider client built); `ft-design-plan-locks` (no CLI does; a locked path stops the run before a seat is spent); `ft-design-before-record` (lock taken while the seats ran); `ft-design-concern-accepted` (drift noted); `ft-design-wait-in-turn` (will not hold you); `ft-design-stores-text` (D-314, outlives the scratch); `ft-measure-select-rules` (path-scoped form); `ft-size-sync-skipped` (that test did NOT run); `ft-close-commit-capture` (the `HEAD` read and its reason); `ft-design-read-before-copy`; `ft-design-copied-mechanism`; `ft-review-full-over-committed`; `ft-review-seat-questions`; `ft-sequences-machinery` (keep their own text); `ft-size-lane-table`; `ft-size-new-path-declared`; `ft-measure-population` (every host it runs on, the transport handing a new env var); `ft-measure-grader-red`; `ft-measure-prior-record`; `ft-build-graders`; `ft-build-store-tests`; `ft-review-urgent-checkpoint`; Haiku-only: `ft-lane-v2-mechanisms` (every ... below), `ft-size-code-surface-only` (articles), `ft-worktree-scratch-copy` (parentheses), `ft-size-refusal-is-answer` (A), `ft-size-cobra` (their counters), `ft-measure-proposed-fix-replayed` (same way, on a copy; builds on).

Loader LOSS: `ft-review-invoke` — the baseline has "never reaches the lane — it routes", the ledger `baseline` and live text had `;`; both now carry the dash. The L21, L31, L53, L84 LOSS lines are cleared by restoring the text and dropping the `clauses: narrative` labels on `ft-size-sync-skipped`, `ft-measure-select-rules`, `ft-design-stores-text`, `ft-close-commit-capture` (they were instructions, not narrative).

Relabelled: baseline L2 ("New here: ...") was `narrative`; it is a scoping statement, now carried by new entry `ft-new-here` (restored in the source after the opening paragraph).

Own-text words: baseline 4263 → re-ledger 3617 (84.8%) → now about 3780 (estimate, +about 160 restored words); not re-measured with `command_rules.own_text`, since this run could run no ad-hoc command. The per-file floor stays above 50%, so no floor table.

Gates: `tests/test_command_rules.py` — the only failure is the live-corpus test, whose LOSS list holds `_shared/*.yaml` lines alone (total 718, unchanged); no `fabrik-task.yaml` LOSS line prints first or elsewhere that was visible. `assemble_commands.py --check` exit 4 (`_shared` LOSS, `fabrik-task.md` DIFFERS drift). The reader-test groups show failures in the live-box/`_shared` tests (for instance `test_the_two_live_box_tests_pass_a_merge_check_on_a_drifted_box`); a pre-edit baseline set of this run was not captured, so "set did not grow" is not proven here.

Fresh pass: NOT run. No subagent can be dispatched in this run; the pass was a line-by-line re-read of the 29 findings against the restored text by the author, which is not a fresh reader. The hub's author-blind audit pair covers it.

COUNTS: entries read 100 / reworded 91 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0 — author re-read only, 0 fresh passes; not a fresh-pass count.

## LEFT FOR THE HUB

- author-blind Sonnet+Haiku classification of the vanished labels (author labels — audit owed) and the review wave;
- the floor D-row for /fabrik-task (84.8% as built; D-1240 strict floor 56%);
- `commands/_size_ceiling.json` ratchet, CHANGELOG, INDEX row for `commands/_rules/fabrik-task.*`, converting the `# class:` / `# clauses:` comments to keys when the loader lands.

