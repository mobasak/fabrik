# T10 receipt — lean rewrite of /fabrik-command-improve (full form)

Start (baseline) commit: `61d1f4b99c6a8188a281f86799268fe54ee1b5d1` (origin/kaizen-lean-u01). Branch: `claude/lean-t10`. Cloud worker; author labels — audit owed (no Sonnet+Haiku pair could run here; one fresh subagent ran the four-check audit twice, see Self-audit).

## Own text, before → after
| file | words before | words after | share |
|---|---|---|---|
| commands/_sources/fabrik-command-improve.md | 6219 | 5970 | 96.0% |
| commands/_fragments/agent-feedback.md | 473 | 452 | 95.6% |

**Target ≤50% NOT met — floor named.** Measured with `command_rules.units()` word counts. Live rule count: 148 command entries + 20 fragment entries. The D-1240 floor for this text: summing, per baseline clause, the clause minimum (ban clauses whole from the ban word; other clauses anchors + first six content words) gives about 4,500 words (about 71%) with every rule kept, before any further narrative deletion. Ban-bearing clauses are a quarter of the words, test pins in `tests/test_command_improve_drive.py` and `tests/test_command_feedback_report.py` hold the Drive, D-711, lock-bullet and trailer text verbatim, and most remaining sentences carry backticked anchors that must sit in the same phrase as their stems. The rewrite is above even that floor because the first audit pass found about twenty dropped conditions and exceptions in tails past the sixth content word, which were restored (see Self-audit): where a tail held an exception, bound or condition it was kept, and only history, examples, rationale and restatements were cut or labelled. The hub should mint the floor D-row (spec § Target); I mint none. A cheaper shrink needs an operator decision on whether tails past the first eight content words may drop conditions.

Ticket-mandated addition (spec § Loop changes, L1/L2 wording): one sentence in PHASE 3's weight paragraph — an edit must fit its command's size ceiling and pass its rule ledger, and a grouped `remove:` candidate is a ledger check, never permission to delete. It reconciles with the existing size paragraph (no second copy) and names no path, because naming `commands/_size_ceiling.json` made the ceiling file part of the command's own reads (exit 5 at `--check`). It has no baseline unit and no ledger entry (the audit lists it as INFO, not INVENTED).

## Entries
### Ledger commands/_rules/fabrik-command-improve.yaml
- entries 148 · reworded 32 · unchanged 116
- by class (all): {'ban': 54, 'behavioural': 7, 'grammar': 5, 'prose': 82}; reworded by class: {'ban': 9, 'prose': 23}

| entry | clauses | coverage |
|---|---|---|
| ci-pool-off-d-181-operator | 5 | c1:phrase c2:phrase c3:phrase c4:phrase c5:phrase |
| ci-canonical-dispatch-policy | 1 | c1:phrase |
| ci-this-command-is-the-reader | 1 | c1:phrase |
| ci-a-command-whose-queue-deserves | 1 | c1:phrase |
| ci-every-count-and-claim-the | 2 | c1:phrase c2:narrative |
| ci-the-lead-copies-each-handle | 2 | c1:phrase c2:phrase |
| ci-then-take-the-queue-s | 1 | c1:phrase |
| ci-expect-to-dominate-the-backlog | 2 | c1:phrase c2:narrative |
| ci-do-not-trust-any-figure | 2 | c1:phrase c2:phrase |
| ci-rows-a-previous-run-answered | 2 | c1:phrase c2:phrase |
| ci-this-used-to-be-a | 2 | c1:narrative c2:phrase |
| ci-rows-whose-edit-already-landed | 2 | c1:phrase c2:narrative |
| ci-read-the-row-then-read | 2 | c1:phrase c2:phrase |
| ci-the-one-to-think-about | 3 | c1:phrase c2:narrative c3:phrase |
| ci-group-the-rows-by-what | 1 | c1:phrase |
| ci-a-edit-is-a-fleet | 2 | c1:phrase c2:phrase |
| ci-only-then-read-the-locks | 2 | c1:phrase c2:phrase |
| ci-run-for-today-s-depth | 2 | c1:phrase c2:phrase |
| ci-mail-it-and-close | 1 | c1:phrase |
| ci-an-append-that-restates-what | 1 | c1:phrase |
| ci-before-an-edit-widens-a | 3 | c1:phrase c2:phrase c3:phrase |
| ci-an-edit-to-what-a | 2 | c1:phrase c2:phrase |
| ci-reports-the-delta-against-the | 1 | c1:phrase |
| ci-a-sentence-that-describes-what | 8 | c1:phrase c2:phrase c3:phrase c4:phrase c5:phrase c6:phrase c7:phrase c8:phrase |
| ci-a-sentence-a-edit-adds | 1 | c1:phrase |
| ci-for-a-edit-the-brief | 1 | c1:phrase |
| ci-the-trailer-block-must-be | 1 | c1:phrase |
| ci-verify-empty-output-means-the | 2 | c1:phrase c2:phrase |
| ci-then-mark-the-rows-answered | 2 | c1:phrase c2:narrative |
| ci-the-sha-and-must-name | 3 | c1:phrase c2:phrase c3:phrase |
| ci-same-list-as-the-trailer | 2 | c1:phrase c2:phrase |
| ci-next-re-run-this-command | 3 | c1:phrase c2:phrase c3:narrative |

vanished labels:
- L1: {'rule': ['ci-pool-off-d-181-operator']}
- L4: {'rule': ['ci-canonical-dispatch-policy']}
- L6: narrative
- L7: narrative
- L8: narrative
- L10: {'rule': ['ci-this-command-is-the-reader']}
- L11: {'duplicate-of': 'ci-it-improves-one-command-per'}
- L13: {'rule': ['ci-a-command-whose-queue-deserves']}
- L29: {'rule': ['ci-every-count-and-claim-the']}
- L41: {'rule': ['ci-the-lead-copies-each-handle']}
- L43: {'rule': ['ci-then-take-the-queue-s']}
- L56: {'rule': ['ci-expect-to-dominate-the-backlog']}
- L57: {'rule': ['ci-do-not-trust-any-figure']}
- L60: {'rule': ['ci-rows-a-previous-run-answered']}
- L61: {'rule': ['ci-this-used-to-be-a']}
- L63: narrative
- L64: {'rule': ['ci-rows-whose-edit-already-landed']}
- L65: {'rule': ['ci-read-the-row-then-read']}
- L68: {'rule': ['ci-the-one-to-think-about']}
- L70: {'duplicate-of': 'ci-a-verdict-is-evidence-never'}
- L73: {'rule': ['ci-group-the-rows-by-what']}
- L75: {'rule': ['ci-a-edit-is-a-fleet']}
- L91: {'rule': ['ci-only-then-read-the-locks']}
- L96: {'rule': ['ci-run-for-today-s-depth']}
- L97: {'rule': ['ci-mail-it-and-close']}
- L102: {'rule': ['ci-an-append-that-restates-what']}
- L108: {'rule': ['ci-before-an-edit-widens-a']}
- L109: {'rule': ['ci-an-edit-to-what-a']}
- L111: narrative
- L113: {'rule': ['ci-reports-the-delta-against-the']}
- L121: {'rule': ['ci-a-sentence-that-describes-what']}
- L124: {'rule': ['ci-a-sentence-a-edit-adds']}
- L130: {'rule': ['ci-for-a-edit-the-brief']}
- L143: {'rule': ['ci-the-trailer-block-must-be']}
- L144: {'rule': ['ci-verify-empty-output-means-the']}
- L145: {'rule': ['ci-then-mark-the-rows-answered']}
- L147: {'rule': ['ci-the-sha-and-must-name']}
- L148: {'rule': ['ci-same-list-as-the-trailer']}
- L158: {'rule': ['ci-next-re-run-this-command']}

### Ledger commands/_rules/_shared/agent-feedback.yaml
- entries 20 · reworded 3 · unchanged 17
- by class (all): {'ban': 5, 'grammar': 1, 'prose': 14}; reworded by class: {'grammar': 1, 'prose': 2}

| entry | clauses | coverage |
|---|---|---|
| af-findings-about-the-subject-you | 2 | c1:phrase c2:narrative |
| af-machinery-check-secrets-py-88 | 3 | c1:phrase c2:phrase c3:phrase |
| af-write-real-ones-and-note | 2 | c1:phrase c2:phrase |

vanished labels:
- L2: narrative
- L6: {'rule': ['af-findings-about-the-subject-you']}
- L13: {'rule': ['af-write-real-ones-and-note']}
- L14: narrative

## Pins deleted (tests/test_command_improve_queue_pass.py; no other test edited)
Whole pin tests deleted (24), each now a `pins:` node on the entries carrying its phrase:
- `tests/test_command_improve_queue_pass.py::test_phase_three_executes_what_a_new_sentence_says_a_script_does`
- `tests/test_command_improve_queue_pass.py::test_phase_five_tests_before_the_commit_and_marks_only_covered_rows`
- `tests/test_command_improve_queue_pass.py::test_phase_three_reads_what_already_governs_the_subject`
- `tests/test_command_improve_queue_pass.py::test_phase_three_runs_verbs_end_to_end_and_recipes_on_real_artifacts`
- `tests/test_command_improve_queue_pass.py::test_phase_three_reads_the_executor_the_fan_out_and_every_branch`
- `tests/test_command_improve_queue_pass.py::test_phase_three_checks_an_added_rule_on_the_edit_and_its_origin_case`
- `tests/test_command_improve_queue_pass.py::test_a_reject_reason_cites_a_line_the_command_reaches`
- `tests/test_command_improve_queue_pass.py::test_a_rule_lands_where_its_writers_load_it_and_a_mechanism_meets_its_consumer`
- `tests/test_command_improve_queue_pass.py::test_a_row_prescribing_how_the_command_works_goes_to_the_panel_first`
- `tests/test_command_improve_queue_pass.py::test_the_held_subject_search_reads_the_reasons_view`
- `tests/test_command_improve_queue_pass.py::test_phase_three_points_at_a_rule_stated_elsewhere_without_a_gloss`
- `tests/test_command_improve_queue_pass.py::test_a_claim_about_a_gate_is_grounded_in_its_code_and_run_on_the_rows_case`
- `tests/test_command_improve_queue_pass.py::test_grounding_reads_the_governing_spec_and_a_copied_recipe_names_its_form`
- `tests/test_command_improve_queue_pass.py::test_a_recurrence_is_searched_by_its_step_and_answered_rejects_flag_a_line`
- `tests/test_command_improve_queue_pass.py::test_the_audit_seat_reads_the_source_and_briefs_name_pins_and_consumers`
- `tests/test_command_improve_queue_pass.py::test_test_fragment_and_removed_word_rules`
- `tests/test_command_improve_queue_pass.py::test_a_script_description_points_at_the_doc_that_owns_the_script`
- `tests/test_command_improve_queue_pass.py::test_a_lengthened_paragraph_is_rewrapped_whole_by_a_word_checking_script`
- `tests/test_command_improve_queue_pass.py::test_a_widened_or_split_sentence_rereads_the_clauses_already_in_it`
- `tests/test_command_improve_queue_pass.py::test_phase_three_reads_the_path_pointed_files_and_the_neighbouring_items`
- `tests/test_command_improve_queue_pass.py::test_the_audit_seat_returns_text_and_quotes_what_it_cites`
- `tests/test_command_improve_queue_pass.py::test_a_size_capped_target_is_sized_before_the_draft`
- `tests/test_command_improve_queue_pass.py::test_the_copy_recipe_is_named_by_its_constant_and_the_rewrap_is_bounded`
- `tests/test_command_improve_queue_pass.py::test_the_review_seats_check_each_rows_timing_and_venue`

Presence asserts removed from mixed tests, their recipe/script/file asserts kept (8):
- `tests/test_command_improve_queue_pass.py::test_phase_five_runs_every_test_that_names_the_edited_source`
- `tests/test_command_improve_queue_pass.py::test_a_fragment_edit_names_its_by_path_consumers_too`
- `tests/test_command_improve_queue_pass.py::test_a_reject_search_reads_the_render_and_a_seat_rule_lands_in_every_home`
- `tests/test_command_improve_queue_pass.py::test_the_mark_step_says_a_handle_is_the_whole_ts_with_its_fraction`
- `tests/test_command_improve_queue_pass.py::test_a_widened_subject_and_a_recipe_meet_their_breaking_inputs_before_the_pin`
- `tests/test_command_improve_queue_pass.py::test_a_weakening_recurrence_routes_and_ledger_prose_follows_the_closing_pass`
- `tests/test_command_improve_queue_pass.py::test_a_fragment_pointed_at_by_path_is_a_write_and_lock_target`
- `tests/test_command_improve_queue_pass.py::test_the_lock_check_names_the_appended_fragment_and_how_an_entry_owns_a_path`

Kept untouched: `test_a_count_lives_at_its_list` (CLAUDE.md), `test_fabrik_task_third_queue_pass_lines` (fabrik-task.md), `test_the_lock_check_set_of_scripts_that_mention_owned_paths_is_pinned` (scans scripts/), the close-chain pin in `test_a_weakening_recurrence_…` (another file's text). `tests/test_command_improve_drive.py` and `tests/test_command_feedback_report.py` are not edited and pass; their phrases stayed verbatim. Order pins became `ordered:` carriers on `ci-run-the-edit-s-tests` (tests, trailer fence, MARK) and `ci-the-assembler-also-appends-two` (appended fragments, ONLY THEN, entry owns).

## Vanished labels
Author labels — audit owed. Seven whole-unit narrative labels (L6, L7, L8, L63, L95, L111, L142), two duplicate-of (L11 of the "improves ONE command" entry, L70 of "A verdict is evidence, never authority"), clause-level narrative labels recorded as `# clauses:` comments (pool-off mechanism-revised, recalled-number reason, empty-queue "nothing here to act on", axis-convention date, old `git log --grep` step description, change-verdict anecdote, other-agents'-words rationale, the two quoted example verdicts, "step that makes the queue fall", second-deepest-queue anecdote; fragment: the code/screen/fact example). The three history sentences that hold a ban word (relay digest "never changes", old step "never once performed", "easy to refuse") are kept, not labelled, per D-1240.

## Loader
`_ENTRY` on this base has no `class`/`clauses` keys, so each entry records `# class: ban|grammar|behavioural|prose` and `# clauses: {n: narrative | duplicate-of: id}` as YAML comments for the hub to convert. Behavioural: the seven `--take` output lines (asserted on emitted script output by tests/test_command_feedback_report.py). Grammar: fences. `command_rules.py` and `tests/test_command_rules.py` untouched.

## Gates
- `pytest tests/test_command_rules.py -rP`: 32 passed, 3 skipped; PASSES shows `LEDGER fabrik-command-improve.yaml: 148 entries` and `LEDGER agent-feedback.yaml: 20 entries`, zero LOSS.
- `assemble_commands.py --check`: exit 1, every DRIFT line `MISSING` (installed corpus is master's); no LOSS, no CEILING. Ceiling file untouched (coordinator ratchets).
- Reader-test run (35 files: stem readers + corpus-glob tests): failure set at start commit 52 failures (tests/test_command_improve_queue_pass etc. all green; reds are box-service tests); at end the same 52, 0 new. Start-set names are in the branch log; the end set must be a subset.

## Floor table — clauses still over their anchors+6 minimum
Entries kept more than two words above their clause minimum (83 command, 7 fragment). Entries sharing one rewritten sentence count that sentence for each.

| entry | kept words | clause minimum | why it cannot shrink |
|---|---|---|---|
| ci-pool-off-d-181-operator | 45 | 32 | one rewritten sentence carries 2 baseline units (ci-canonical-dispatch-policy), so kept counts the shared unit |
| ci-run-every-fan-out-this | 27 | 24 | the clause is within two words of its minimum |
| ci-canonical-dispatch-policy | 45 | 5 | one rewritten sentence carries 2 baseline units (ci-pool-off-d-181-operator), so kept counts the shared unit |
| ci-the-dispatch-step-d-191 | 64 | 44 | pinned verbatim by a kept test: test_check_command_corpus.py |
| ci-a-fleet-window-or-a | 27 | 13 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “its verdict at its own close and the queue is worked from the hub” |
| ci-an-unnamed-hub-window-names | 19 | 10 | pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-the-fable-band-is-raised | 34 | 27 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “read the line, not the account percentages” |
| ci-a-session-the-operator-has | 56 | 27 | pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-seats-sized-from-the-box | 59 | 48 | pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-the-target-is-a-quiet | 69 | 55 | 33 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240); pinned verbatim by a kept test: test_command_improve_drive.py, test_command_run.py |
| ci-grounding-before-drafting-not-after | 136 | 104 | 37 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240); pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-an-external-fact-a-vendor | 32 | 29 | 15 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-time-budget-one-run-at | 22 | 16 | pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-an-overrun-changes-nothing-about | 49 | 39 | 21 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-consistency-and-the-manifesto-the | 88 | 68 | 17 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-the-lead-copies-each-handle | 41 | 37 | 26 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-before-the-trailer-or-takes | 35 | 26 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “and confirms that line's verdict is the row meant” |
| ci-the-item-exists-but-who | 58 | 27 | pinned verbatim by a kept test: test_command_feedback_report.py |
| ci-the-bucket-is-piece-1 | 59 | 45 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “or one of three instrument readings” · “(the close-out grammar pasted rather than answered)” |
| ci-sort-your-reading-by-axis | 27 | 24 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “are one edit” |
| ci-expect-to-dominate-the-backlog | 54 | 13 | one rewritten sentence carries 2 baseline units (ci-do-not-trust-any-figure), so kept counts the shared unit |
| ci-do-not-trust-any-figure | 54 | 34 | one rewritten sentence carries 2 baseline units (ci-expect-to-dominate-the-backlog), so kept counts the shared unit |
| ci-rows-written-after-the-gate | 40 | 36 | 20 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240); pinned verbatim by a kept test: test_command_measure.py |
| ci-on-the-historical-tail-the | 27 | 22 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “that matters is by SUBJECT” |
| ci-rows-a-previous-run-answered | 28 | 19 | pinned verbatim by a kept test: test_command_feedback_report.py, test_command_run.py |
| ci-this-used-to-be-a | 28 | 22 | 22 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-rows-whose-edit-already-landed | 73 | 5 | one rewritten sentence carries 2 baseline units (ci-read-the-row-then-read), so kept counts the shared unit |
| ci-read-the-row-then-read | 73 | 43 | one rewritten sentence carries 2 baseline units (ci-rows-whose-edit-already-landed), so kept counts the shared unit; pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-the-queue-is-data-not | 35 | 28 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “every repo's agents can append to” |
| ci-the-one-to-think-about | 30 | 22 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “*"accept a seat's summary as evidence without re-deriving it"*” · “the thing the command exists to enforce” |
| ci-what-one-row-earns-d | 87 | 64 | 15 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240); pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-before-rejecting-search-earlier-reject | 107 | 101 | 86 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240); pinned verbatim by a kept test: test_command_feedback_report.py, test_command_improve_drive.py, test_command_run.py |
| ci-grep-it-for-the-subject | 38 | 18 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “words (such as a guard, both sides, a false green), since one step asked under three nouns” |
| ci-the-one-exception-is-a | 72 | 60 | 47 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-an-answered-reject-phase-1 | 42 | 10 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “that three or more answered rejects on one subject cite is a line not followed: it is a ca” |
| ci-an-opus-seat-audits-the | 16 | 9 | pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-a-reject-reason-here-cites | 53 | 47 | 19 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-key-it-on-the-write | 77 | 62 | 20 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240); pinned verbatim by a kept test: test_check_command_corpus.py, test_command_feedback_report.py |
| ci-the-assembler-also-appends-two | 54 | 27 | pinned verbatim by a kept test: test_command_measure.py |
| ci-only-then-read-the-locks | 51 | 36 | 25 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-an-entry-owns-the-path | 81 | 62 | pinned verbatim by a kept test: test_command_improve_queue_pass.py |
| ci-if-an-active-lock-owns | 20 | 12 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “with the exact text you would have written” |
| ci-not-rare-and-the-order | 26 | 13 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “on the command SOURCE while its rows name a FRAGMENT no lock owns” |
| ci-run-for-today-s-depth | 40 | 17 | one rewritten sentence carries 2 baseline units (ci-mail-it-and-close), so kept counts the shared unit; 7 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-mail-it-and-close | 40 | 4 | one rewritten sentence carries 2 baseline units (ci-run-for-today-s-depth), so kept counts the shared unit |
| ci-a-verdict-that-wants-a | 100 | 75 | 37 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-a-verdict-about-the-machinery | 34 | 16 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “(the ledger, the close, the report) → file it to infra and note it in the FEEDBACK line” |
| ci-read-the-command-source-whole | 31 | 17 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “belong INSIDE a section that already exists (CLAUDE.md § READ BEFORE YOU EDIT)” |
| ci-an-append-that-restates-what | 14 | 10 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “two sources of truth in one document” |
| ci-before-the-first-draft-the | 97 | 33 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “at by path for the same subject are read too (a review command's probe catalogue), and so ” · “text leaves standing unless the row is a decision settled as the decision sentence below s” |
| ci-the-tests-that-pin-a | 81 | 38 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “and the new text goes where its subject reads, a pinned span it lands inside or beside re-” |
| ci-a-row-that-prescribes-how | 66 | 38 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “settled before the first draft in CLAUDE.md § Autonomy's order ("the self-service sources ” |
| ci-before-an-edit-widens-a | 89 | 33 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “the sentence or places text between a pronoun (or an "above") and what it names, each clau” · “sentence or item pointing back into either” · “lands, since a clause written for one subject or one antecedent then binds whatever the wi” |
| ci-commands-are-rules-not-changelogs | 21 | 9 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “in the present tense as the rule, and DELETE what it replaces” |
| ci-weight-is-a-cost-and | 71 | 62 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “that points at it by path” |
| ci-reports-the-delta-against-the | 36 | 16 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “either way: read its ⚠ line, not its exit code, and if the surface grew say in the commit ” |
| ci-a-target-a-test-caps | 57 | 19 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “search, read for a cap) is sized to that cap before the draft or the cap is raised in that” |
| ci-and-size-the-edit-to | 27 | 15 | pinned verbatim by a kept test: test_command_feedback_report.py |
| ci-check-the-claim-not-the | 116 | 111 | 76 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240); pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-a-rule-the-edit-adds | 59 | 56 | 46 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-a-mechanism-the-edit-adds | 45 | 42 | 27 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-a-sentence-that-describes-what | 236 | 153 | 47 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-a-rule-whose-subject-the | 42 | 12 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “first pin, through the rule's own search methods, on a sample of the new subject, since a ” |
| ci-a-sentence-a-edit-adds | 21 | 13 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “that have its subject (for example a review loop or a round count) and binds no other” |
| ci-sized-by-the-surface-one | 34 | 27 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “to answer, not merely for style” |
| ci-for-a-edit-the-brief | 35 | 14 | pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-a-seat-that-cannot-find | 46 | 23 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “is the finding” · “the row's step, and says whether that line also states when the step runs and in which pha” |
| ci-a-sentence-a-round-rewords | 43 | 25 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “(drafted now if not yet written), before that round's pin, and each hit is reworded with t” |
| ci-run-the-edit-s-tests | 75 | 59 | 21 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-the-commit-is-the-provenance | 30 | 16 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “which is read across runs) uses to connect an edit to its evidence” |
| ci-the-answered-index-writes-is | 37 | 26 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “for WHY an edit was made” · “sha so the two agree:” |
| ci-agent-role-primary-agent-context | 18 | 8 | pinned verbatim by a kept test: test_command_feedback_report.py |
| ci-nothing-grades-that-prediction-yet | 32 | 19 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “§ Q3), and an edit is not held back waiting for it” |
| ci-the-trailer-block-must-be | 35 | 21 | one rewritten sentence carries 2 baseline units (ci-verify-empty-output-means-the), so kept counts the shared unit; 21 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-verify-empty-output-means-the | 35 | 13 | one rewritten sentence carries 2 baseline units (ci-the-trailer-block-must-be), so kept counts the shared unit; pinned verbatim by a kept test: test_command_feedback_report.py |
| ci-then-mark-the-rows-answered | 8 | 5 | the clause is within two words of its minimum |
| ci-python3-opt-fabrik-scripts-command-3 | 18 | 8 | pinned verbatim by a kept test: test_command_feedback_report.py, test_command_improve_drive.py, test_command_run.py |
| ci-the-sha-and-must-name | 72 | 30 | 10 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240); pinned verbatim by a kept test: test_command_improve_drive.py |
| ci-it-refuses-a-commit-that | 38 | 31 | 15 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-the-same-call-also-closes | 22 | 19 | the clause is within two words of its minimum |
| ci-next-re-run-this-command | 41 | 26 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “sorts by what a close COSTS, this sorts by how many verdicts are waiting, and on live data” |
| ci-anything-it-had-to-route | 68 | 44 | 13 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240) |
| ci-one-edit-committed-and-rendered | 195 | 173 | 108 words sit in ban clause(s), verbatim from the ban word to the end of the clause (D-1240); pinned verbatim by a kept test: test_command_improve_drive.py |

| entry | kept words | clause minimum | why it cannot shrink |
|---|---|---|---|
| af-anything-you-noticed-and-did | 18 | 13 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “and you have no mailbox” |
| af-findings-about-the-machinery-you | 59 | 18 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “that fired on a legitimate pattern or stayed silent on a real defect, a rule pack that con” |
| af-class-2-goes-in-a | 27 | 21 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “and the command you actually ran” |
| af-machinery-check-secrets-py-88 | 31 | 21 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “a script that is not on disk (I ran it” |
| af-write-real-ones-and-note | 36 | 18 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “resolves every such reference in the corpus and an illustrative placeholder would register” |
| af-a-machinery-defect-you-absorb | 30 | 21 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “the work of hitting it is already done” |
| af-if-your-brief-lets-you | 36 | 11 | the words past the 6th content word state a distinct act, bound or exception, so cutting them changes what an agent does (rationale, example and history tails are already cut or labelled); tail kept: “the surface you were dispatched to, fix it at the root with its regression guard (the FIX ” |

## Self-audit
Pass 1 (fresh subagent, four checks) found 1 lost, 9 firm + 11 low weaker, 1 wrong label, 0 invented; all restored (tails with conditions/exceptions, the appended-fragment routing clause, the dangling-"It" sentence, the "best practice" clause relabel removed). Pass 2 result: restored every item pass 2 named (bounds, since-clauses, L95, L142, L17/L19, clause-3 labels) instead of relabelling
COUNTS: 164 read / 44 reworded / 14 weaker found, all restored after the pass / 0 lost / 0 invented (1 INFO) / 5 wrong labels found, all restored after the pass (no third pass run; my mechanical clause check after the fixes shows 0 uncovered, 0 below 70% outside labelled clauses)

## LEFT FOR THE HUB
- author-blind Sonnet+Haiku audit of the vanished labels and reworded entries; the review wave.
- floor D-row for the 50% target (above); the `commands/_size_ceiling.json` ratchet at merge; CHANGELOG, INDEX rows for the two new baseline files and ledgers, D-rows.
- converting the `# class` / `# clauses` comments to keys once the canonical loader lands.
