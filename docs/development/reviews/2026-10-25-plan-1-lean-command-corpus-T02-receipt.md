# T02 receipt — /fabrik-review-scoped (full form) — BELOW TARGET, floor reported

Start commit (baseline): `61d1f4b99c6a8188a281f86799268fe54ee1b5d1` (origin/kaizen-lean-u01). Branch `claude/lean-t02`. Loader on this base: `_ENTRY` has no `class`/`clauses` keys, so each entry carries `# class:` and `# clauses:` YAML comments (hub converts when infra-3's loader lands). T01d is NOT on this base: the 9 shared files are uncut here.

## Result (own-text words = sum of `command_rules.units()` words, comments excluded)
| file | before | after | share |
|:--|--:|--:|--:|
| commands/_sources/fabrik-review-scoped.md | 4713 | 4393 | 93.2% |
| commands/_fragments/scope-growth-exit.md | 333 | 309 | 92.8% |
| pilot part owned by T02 | 5046 | 4702 | 93.2% |
| 9 shared files (T01d, uncut on this base, `wc -w`) | 16463 | 16463 | 100% (T01d's numbers replace these at merge) |

Words per rule (live words / live entries): source 4393/73 = 60.2; with the fragment 4702/79 = 59.5. Entries: source 73 (29 reworded, 41 ban, 29 prose, 3 grammar), fragment 6 (3 reworded; 3 ban, 2 grammar, 1 prose). Vanished labels: source 46 `rule`, 3 `narrative` whole-unit (L7, L65, L79) plus clause labels (L1.c2, L9.c3, L33.c1, L53.c3, L56.c1, L69.c0/c1, L76.c5/c6); fragment L7 narrative. "author labels — audit owed" (no Sonnet+Haiku classification ran).

Gates: `tests/test_command_rules.py` 32 passed 3 skipped (LEDGER lines for fabrik-review-scoped.yaml and scope-growth-exit.yaml, zero LOSS); `assemble_commands.py --check` exit 1, every DRIFT line DIFFERS/MISSING only; reader-test run (50 files, spine § Global Constraints): start commit (clean worktree) 55 failed / 2830 passed / 17 skipped; end 55 failed / 2827 passed / 17 skipped (3 fewer passes = the 3 deleted pin tests); the failure sets are identical (comm: 0 new, 0 fixed) — all 55 are box-service/env reds (fabrik_deck, quota_dashboard, conftest_isolation, generate_capability_index, check_command_corpus, etc.).

## Why not 50% — the floor (KILL input)
The strict D-1240 reading leaves little to cut: 896 of 4709 baseline words (19%) sit in ban clauses that stay verbatim from the ban word to the end of the `;`/`—` clause (many run 40-100 words, e.g. L36 101, L47 75, L73 75); ~320 words are phrases kept tests outside Touches pin (RUN_SCRATCH/SCRATCH_HOME clauses, the Seat-isolation sentence through "roots)", the Workflow-absent clause, STAMPED/PIN/DIFF/REFUTED sentences); every command line and `Workflow({...})` call is anchor text; and a clause's first 8 content words often sit in an aside that must stay.
Experiment: a mechanical pass deleting every comma/parenthesis chunk that the checker still passes reached 80.8% (3807 words) but left operative sentences gutted or ungrammatical (e.g. the Sweep search instruction, "or read its slice yourself and record the round", the red-first definition), so it was not shipped. A readable cut that keeps every operative sentence is 93.2%. Two author-blind audit passes (below) found operative tails dropped by cheaper cuts; those were restored. Nothing here is a floor D-row (hub mints it); live rule count 73 + 6.
Clauses over their anchors-plus-6 minimum, by reason: (a) ban clause verbatim — L3, L5 tail, L9, L10, L11, L13, L14, L16, L17, L25, L27, L31, L32, L34, L36-L38, L41, L44, L45, L47, L49-L51, L53, L54, L56, L59-L63, L68, L69.c2, L71, L73, L74, L77, L78, L80, L82, L84, L85; (b) command grammar / anchors — L5, L33, L41, L59, L71, L72, L73, L80; (c) pinned by a kept test outside Touches — L11, L39, L41, L47, L52, L53, L63, L71, L73, L78; (d) tail kept as operative sentence beyond the first 8 stems — the rest (a shrink there is allowed by D-1240 coverage but removes an instruction; hub to rule).

## Pins deleted (tests/test_review_scoped_queue_pass.py, Touches)
Whole tests: `::test_escape_variants_are_asked_from_round_one`, `::test_a_shell_written_brief_quotes_its_backticks`, `::test_a_fix_finds_the_rules_home_before_drafting_its_sentence` (listed under `pins:` of their entries). Single assertions removed, test kept: `::test_the_command_applies_seat_isolation_to_every_brief_that_runs_tests` ("not restated here"), `::test_a_guard_brief_states_its_model_boundary` (MODEL BOUNDARY phrase), `::test_the_closing_reader_clause_cites_d118_not_d066` (presence line; absence pin stays), `::test_a_small_pin_is_pasted_inline_and_the_escape_ask_hunts_false_reds` (first phrase), `::test_a_delta_brief_carries_the_bounded_hops_reader_run_inputs` (src pointer/step-4 asserts; catalogue/DECISIONS asserts stay), `::test_a_rule_or_recipe_a_fix_adds_runs_over_round_zeros_input_classes_before_the_pin` (sentence assert; term-coverage asserts stay). Multi-file loops (`test_spec_review_queue_pass::test_no_command_caps_the_workflow_pass_number`) untouched; their text kept verbatim. The other 3 Touches tests pass unedited.

## Vanished labels
L7, L65, L79 narrative; every other vanished unit `rule:` of the entries in the tables. Fragment: L7 narrative (maintenance note).

## Self-audit
Pass 1 fixed: L74 wrong narrative on a ban clause (D-344 restored), L33 wrong duplicate label (term-edit pointer restored), L5/L8/L17/L25/L26/L35/L47/L61/L66/L84 dropped tails restored, L37/L39/L40/L70 unlabelled clauses restored. Pass 2 fixed: L23 example, L9/L59 path labels (dangling "path (ii)"), L71 "chunk 6b", L73 "(D-335)", doubled "search" in L25, L55 anecdote restored (not purely narrative). Residual noted, not fixed: citation-only ids dropped unlabelled (01M2368XB, 01M236V84, 01M23ESF5, 01M1VVPJS); L9.c3 D-315 labelled narrative though arguable.
COUNTS: entries read 73 / reworded 29 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0 (last pass reported 4 weaker, 1 wrong label; all fixed after it, no third pass run)

## LEFT FOR THE HUB
Author-blind Sonnet+Haiku audit; review wave; floor D-rows (source 93.2%, fragment 92.8%); KILL test with T01d's numbers; ceiling ratchet (`commands/_size_ceiling.json` untouched); converting `# class`/`# clauses` comments to keys; D-1255 provenance label; CHANGELOG/INDEX/DECISIONS rows; whether to widen tail-truncation (80.8% mechanical floor).

## Entry coverage (id | class | state | phrases | per baseline line: clause → phrase index p<n> / label)
| pool-off-banner | prose | reworded | 1 | L1[4cl] c0:p1 c1:p1 c2:narr c3:p1 |
| pool-off-native | prose | unchanged | 3 | L2[3cl] c0:p1 c1:p2 c2:p3 |
| pool-off-no-declaration | ban | reworded | 1 | L3[1cl] c0:p1; L4[1cl] c0:p1 |
| dispatch-step | ban | unchanged | 3 | L5[3cl] c0:p1 c1:p2 c2:p3 |
| light-half-of-pair | prose | reworded | 4 | L6[2cl] c0:p1 c1:p2; L8[2cl] c0:p3 c1:p4 |
| route-up-classification | ban | reworded | 8 | L9[13cl] c0:p1 c1:p2 c2:p3 c3:p1 c4:p4 c5:p5 c6:p5 c7:p5 c8:p1 c9:p6 c10:p7 c11:p8 c12:p8 |
| route-up-coverage | ban | reworded | 3 | L10[4cl] c0:p1 c1:p2 c2:p2 c3:p3 |
| route-up-profile-small-exception | ban | reworded | 2 | L11[2cl] c0:p1 c1:p1; L17[3cl] c0:p1 c1:p1 c2:p2 |
| scope-this-sessions-work | ban | reworded | 4 | L13[6cl] c0:p1 c1:p2 c2:p2 c3:p3 c4:p4 c5:p4 |
| scope-list-files-route-up | ban | unchanged | 2 | L14[3cl] c0:p1 c1:p1 c2:p2 |
| scope-surface-add | prose | unchanged | 1 | L15[1cl] c0:p1 |
| scope-surface-add-top-only | ban | unchanged | 1 | L16[1cl] c0:p1 |
| scope-step5-verdict-decides-exit | prose | reworded | 1 | L18[1cl] c0:p1 |
| arm-rubric | grammar | unchanged | 2 | L19[2cl] c0:p1 c1:p2 |
| pass1-wide-hunt-armed | prose | reworded | 1 | L20[1cl] c0:p1; L21[1cl] c0:p1 |
| finding-fixed-or-refuted | prose | unchanged | 1 | L22[2cl] c0:p1 c1:p1 |
| behaviour-fix-red-first | prose | unchanged | 1 | L23[1cl] c0:p1 |
| fix-test-named-in-evidence | prose | unchanged | 2 | L24[2cl] c0:p1 c1:p2 |
| rule-sentence-sweep-first | ban | unchanged | 2 | L25[2cl] c0:p1 c1:p2 |
| claim-executed-or-deleted | prose | reworded | 1 | L26[2cl] c0:p1 c1:p1 |
| already-stated-pointed-or-quoted | ban | unchanged | 1 | L27[1cl] c0:p1 |
| local-vs-architectural-fix | prose | reworded | 5 | L28[5cl] c0:p1 c1:p2 c2:p2 c3:p3 c4:p4; L29[1cl] c0:p5; L30[1cl] c0:p5 |
| architectural-adds-no-exit | ban | reworded | 3 | L31[2cl] c0:p1 c1:p2; L32[1cl] c0:p3 |
| record-each-pass-round | grammar | reworded | 4 | L33[7cl] c0:p1 c1:p1 c2:p3 c3:p4 c4:p4 c5:p2 c6:p2 |
| confirmed-every-round | ban | reworded | 2 | L34[3cl] c0:p1 c1:p2 c2:p2 |
| round-ledger-is-artifact | prose | reworded | 3 | L35[3cl] c0:p1 c1:p2 c2:p3 |
| own-fix-evidenced | ban | unchanged | 2 | L36[2cl] c0:p1 c1:p2 |
| loop-delta-rounds | ban | unchanged | 3 | L37[3cl] c0:p1 c1:p2 c2:p3 |
| done-only-on-closing-pass | ban | unchanged | 2 | L38[2cl] c0:p1 c1:p2 |
| seats-stamped-first | prose | reworded | 1 | L39[2cl] c0:p1 c1:p1 |
| ruff-before-each-pin | prose | reworded | 3 | L40[3cl] c0:p1 c1:p2 c2:p3 |
| seat-brief-names-pin | ban | unchanged | 2 | L41[2cl] c0:p1 c1:p2 |
| delta-brief-previous-pin | prose | reworded | 1 | L42[1cl] c0:p1 |
| pin-manifest-bytes | prose | unchanged | 2 | L43[2cl] c0:p1 c1:p2 |
| pin-committed-surface | ban | unchanged | 2 | L44[3cl] c0:p1 c1:p2 c2:p2 |
| pin-partly-committed | ban | unchanged | 3 | L45[3cl] c0:p1 c1:p2 c2:p3 |
| pin-base-sha-read-back | prose | unchanged | 1 | L46[1cl] c0:p1 |
| seats-read-copies | ban | reworded | 3 | L47[7cl] c0:p1 c1:p2 c2:p3 c3:other-entry c4:other-entry c5:other-entry c6:other-entry |
| adjudicate-pin-moved-live-moved | ban | reworded | 4 | L47[7cl] c0:other-entry c1:other-entry c2:other-entry c3:p1 c4:p2 c5:p3 c6:p4 |
| seats-out-no-edit | prose | unchanged | 2 | L48[2cl] c0:p1 c1:p2 |
| seat-still-out-open-question | ban | unchanged | 1 | L49[1cl] c0:p1 |
| failed-seat-redispatch | ban | unchanged | 3 | L50[3cl] c0:p1 c1:p2 c2:p3 |
| unverified-candidates-executed | ban | unchanged | 2 | L51[2cl] c0:p1 c1:p2 |
| probe-catalogue-by-shape | prose | unchanged | 2 | L52[2cl] c0:p1 c1:p2 |
| seat-isolation-whole | ban | reworded | 3 | L53[4cl] c0:p1 c1:p2 c2:p3 c3:narr |
| brief-states-question-not-answer | ban | unchanged | 2 | L54[2cl] c0:p1 c1:p2 |
| check-impossible-burns-seat | prose | unchanged | 2 | L55[2cl] c0:p1 c1:p2 |
| rule-applied-to-motivating-case | ban | reworded | 2 | L56[3cl] c0:p1 c1:narr c2:p2 |
| second-round-two-causes | prose | reworded | 4 | L57[3cl] c0:p1 c1:p2 c2:p3; L58[2cl] c0:p4 c1:p4 |
| escalate-route-up-one-liner | ban | reworded | 11 | L59[14cl] c0:p1 c1:p1 c2:p2 c3:p3 c4:p4 c5:p5 c6:p5 c7:p6 c8:p7 c9:p8 c10:p9 c11:p10 c12:p10 c13:p11 |
| scope-growth-opposite | ban | unchanged | 2 | L60[2cl] c0:p1 c1:p2 |
| scope-growth-name-and-reverify | prose | reworded | 2 | L61[2cl] c0:p1 c1:p2 |
| scope-growth-close-normally | ban | unchanged | 1 | L62[2cl] c0:p1 c1:p1 |
| further-own-fix-recorded | ban | unchanged | 1 | L63[1cl] c0:p1 |
| closing-pass-independent-reader | ban | reworded | 3 | L64[3cl] c0:p1 c1:p2 c2:p2; L69[3cl] c0:narr c1:narr c2:p3 |
| guard-or-rule-escape-variants | prose | reworded | 3 | L66[6cl] c0:p1 c1:p2 c2:p2 c3:p2 c4:p2 c5:p3 |
| ask-verbatim-probe-catalogue | prose | unchanged | 2 | L67[3cl] c0:p1 c1:p2 c2:p2 |
| ask-brief-answer-reader | ban | unchanged | 1 | L68[2cl] c0:p1 c1:p1 |
| floor-three-readers-round-one | prose | reworded | 3 | L70[4cl] c0:p1 c1:p2 c2:p2 c3:p3 |
| workflow-launch-args | ban | unchanged | 9 | L71[10cl] c0:p1 c1:p2 c2:p2 c3:p3 c4:p4 c5:p3 c6:p6 c7:p7 c8:p8 c9:p9 |
| read-pass-ledger | grammar | unchanged | 1 | L72[1cl] c0:p1 |
| later-pass-sizing | ban | unchanged | 3 | L73[3cl] c0:p1 c1:p2 c2:p3 |
| partition-rule-never-applies | ban | unchanged | 2 | L74[3cl] c0:p1 c1:p2 c2:p2 |
| leak-check | prose | unchanged | 1 | L75[1cl] c0:p1 |
| seats-stamped-union | prose | reworded | 4 | L76[7cl] c0:p1 c1:p1 c2:p2 c3:p3 c4:p4 c5:narr c6:narr |
| seat-must-have-returned | ban | unchanged | 1 | L77[1cl] c0:p1 |
| agent-tool-fallback | ban | unchanged | 1 | L78[1cl] c0:p1 |
| gate-and-close | ban | unchanged | 6 | L80[10cl] c0:p1 c1:p2 c2:other-entry c3:other-entry c4:other-entry c5:other-entry c6:p3 c7:p4 c8:p5 c9:p6 |
| scope-growth-converging-close | prose | unchanged | 1 | L81[2cl] c0:p1 c1:p1 |
| converging-close-names-reader | ban | unchanged | 2 | L82[2cl] c0:p1 c1:p2 |
| commit-push-exit | prose | unchanged | 1 | L83[1cl] c0:p1 |
| untrusted-input | ban | unchanged | 1 | L84[1cl] c0:p1 |
| next-command-gate-not-stage | ban | unchanged | 2 | L85[3cl] c0:p1 c1:p2 c2:p2 |

## Fragment entries
| sge-printed-verdict | grammar | reworded | 2 | L1[2cl] c0:p1 c1:p2 |
| sge-scope-growth | grammar | reworded | 1 | L2[2cl] c0:p1 c1:p1 |
| sge-escalate-uncomputable | ban | reworded | 2 | L3[3cl] c0:p1 c1:p1 c2:p2 |
| sge-silence-not-a-verdict | prose | unchanged | 3 | L4[3cl] c0:p1 c1:p2 c2:p3 |
| sge-silence-never-means | ban | unchanged | 1 | L5[1cl] c0:p1 |
| sge-nested-lane-v2 | ban | unchanged | 3 | L6[4cl] c0:p1 c1:p2 c2:p3 c3:p1 |

## Re-ledger round (branch claude/lean-t02-rl, canonical D-1236/D-1240 loader)

The tables above describe the first pass and are superseded for the ledger layout: every `# class:` / `# clauses:` comment is now a real key, clause numbers are 1-based over the entry's own `baseline` split (parentheticals no longer split, so the old `L9.c3`-style labels were re-derived, not copied), and each entry now carries ONE phrase, its whole `current` unit (exempt from lint C's 6-word minimum), so one phrase holds every anchor and stem of every clause it covers.

**Numbers** (own text = whitespace words of the rendered command, delta from the `REPORT fabrik-review-scoped` line of `tests/test_command_rules.py`, because this run had no shell for `command_rules.own_text`; 34416 → 34095 rendered words, −321):
| file | baseline | before (first pass) | now | share of baseline |
|:--|--:|--:|--:|--:|
| commands/_sources/fabrik-review-scoped.md | 4713 | 4393 | ≈4067 | ≈86.3% |
| commands/_fragments/scope-growth-exit.md | 333 | 309 | ≈314 | ≈94.3% |
| pilot part owned by T02 | 5046 | 4702 | ≈4381 | ≈86.8% |
The fragment grew 5 words: `(D-355)` and "the artifact's own defects:" were restored because the first pass had dropped an anchor (`355`) and four of the first eight content stems of the `↗ ESCALATE` clause. LOSS before → after: 29 → 0 (28 in `fabrik-review-scoped.yaml`, 1 in `_shared/scope-growth-exit.yaml`); `--check` exit 4 comes only from other units' `_shared` ledgers, every `fabrik-review-scoped` line is `DIFFERS` drift. Reworded/total entries: 39/73 (72 first-pass entries, `ask-brief-answer-reader` dropped as a restatement, one fragment-pointer entry added). Classes: 40 ban, 31 prose, 2 grammar.

**What changed in the ledger.** `record-each-pass-round`, `sge-printed-verdict` and `sge-scope-growth` moved from grammar to prose (their clauses are reworded, and a grammar class needs every clause verbatim). `seats-read-copies` / `adjudicate-pin-moved-live-moved` now carry their own clause range of L47 (clauses 1-3 and 4-7) instead of both carrying the whole line, because clauses 6 and 7 hold ban words and cannot be labelled a duplicate of the other entry. `seat-isolation-whole`, `check-impossible-burns-seat` and `floor-three-readers-round-one` use real `clauses: {n: narrative}` labels (a "not restated here" aside, a measured example, a citation). `round-two-silence-in-fragment` is a pointer entry (`file: commands/_fragments/scope-growth-exit.md`) that carries L58, which restated the included fragment's round-2/silence rule; L58 is `duplicate-of` it. L17 is `duplicate-of` `route-up-profile-small-exception` (its ban clause survives there as "never the heavy command per ticket on THIS trigger"). L68 is `duplicate-of` `brief-states-question-not-answer`. L18's tail (which exit each defect kind takes) restated the fragment's two verdicts and was cut; L18 stays `rule: [scope-step5-verdict-decides-exit]` because the head of that sentence is carried there. L7, L65, L79 stay `narrative` (none holds a ban word); L69 stays `rule` because "never added, which two self-sweeps had read straight past" holds a ban word and D-1238 forbids a narrative label on it.

**Cuts this round** (all on clauses without a ban word, or on the part of a ban clause before its ban word): banner and dispatch-step parentheticals reduced to their anchors (`D-186`); L17's tail merged into L11; the red-first example; the Sweep-search wording; the `--own-fix`/`--confirmed` fragment-availability note; `ruff` rationale; "the floor paragraph below" pointers; the L13 `uncommitted` gloss; L35/L76 asides; the L52 hub-path aside and list tail; L55's measured example; L56's incident; L59's reason sentence and multi-seat aside; L61's non-qualifying-round rationale; L70's reason and citation; L71's "chunk 6b" and return-value tail; L80's converging-close aside; L75's reason; L26's "do not re-derive" aside; L58 and L68 as duplicates.

**Gates.** `tests/test_command_rules.py -rP`: 56 passed, 1 failed (the live-corpus test, red from other units' `_shared` LOSS lines only; none names `fabrik-review-scoped.yaml` or `_shared/scope-growth-exit.yaml`). The reader-test run: the three batches holding this ticket's text tests ran green BEFORE the first edit and after the last (271, 399 and 241 passed, the same counts, since only assertions were removed). The other five batches were first run after the edits (I ran only three at the start commit): 413 and 415 passed in two, 607 passed with one red in a third; the reds are `tests/test_assemble_dispatch_step.py` (13 tests) and `tests/test_assemble_orch_retired.py` (1), all `fatal: not a git repository` or an uninstalled `~/.claude` in the throwaway clone; `tests/test_conftest_isolation.py::test_the_two_live_box_tests_pass_a_merge_check_on_a_drifted_box` (uninstalled agents dir); `tests/test_command_measure.py::test_check_exit_order_loss_then_ceiling_then_drift` (its step 1 needs a corpus with no LOSS, which T01d's shared ledgers still deny). None of the 16 reads a line this ticket edited, but without a start-commit run of those five batches the claim "the failure set did not grow" is by reading each red's cause, not by `comm`.

**Pin edits** (`tests/test_review_scoped_queue_pass.py`, in Touches; assertions only, no test removed): `test_the_command_applies_seat_isolation_to_every_brief_that_runs_tests` (the "runs found missing. Its § Seat isolation" adjacency, the pointer list it needed is cut), `test_both_review_commands_name_surface_add_for_a_pre_start_file` (the scoped-side sentence assert; the fabrik-review side stays), `test_a_small_pin_is_pasted_inline_and_the_escape_ask_hunts_false_reds` (trailing "The ASK is the", sentence removed as a duplicate), `test_the_lead_runs_the_leak_check_around_every_scoped_pass` (the scoped-side sentence asserts; the fabrik-review bullet pin stays).

**Floor table** (every clause still over its anchors-plus-6 minimum; ≈86% is the floor this loader allows here, the unreachable 50% is explained by A+B+C below, which are ≈70% of the live words):
| reason | where | why it cannot shrink |
|:--|:--|:--|
| A ban span verbatim (D-1240) | route-up-classification c3 (≈48 words from `never count`); route-up-coverage c2; route-up-profile-small-exception c2; scope-this-sessions-work (one clause, first ban word at word 17, ≈100 words); scope-list-files-route-up; scope-surface-add-top-only; rule-sentence-sweep-first c1; already-stated-pointed-or-quoted; architectural-adds-no-exit c2; confirmed-every-round c1-c3; own-fix-evidenced c1 (≈100) and c2; loop-delta-rounds c2; done-only-on-closing-pass; seat-brief-names-pin c1 (from `read-only`) and c2; pin-committed-surface c3 (≈65); pin-partly-committed c2; seats-read-copies c1, c2; adjudicate-pin-moved-live-moved c3 (≈85, from `must write it`) and c4; seat-still-out-open-question; failed-seat-redispatch c3; unverified-candidates-executed; seat-isolation-whole c1; brief-states-question-not-answer c2; rule-applied-to-motivating-case c2; escalate-route-up-one-liner c3 (≈110, from `never \`handoff\``); scope-growth-opposite c2; scope-growth-close-normally c2; further-own-fix-recorded; workflow-launch-args c2 (≈85, from `only the seats' copies`); later-pass-sizing c1 (≈110, from `only the units`); partition-rule-never-applies c1; seat-must-have-returned; agent-tool-fallback (from `never calls`); gate-and-close c4, c5; converging-close-names-reader c2; untrusted-input; next-command-gate-not-stage c2 | D-1238 point 1 / D-1240: a ban-bearing clause is verbatim from its ban word to the end of its `;`/`—` clause, and a parenthetical opened after the ban word stays whole. Several ban words sit near the start of a one-clause sentence (scope-this-sessions-work, later-pass-sizing, workflow-launch-args), so the whole tail is the span. |
| B code anchors held whole | dispatch-step c1, c2; record-each-pass-round c1 (the `round` command with its `— D-278; …` note inside the span); escalate-route-up-one-liner c3 (the `done … && start …` one-liner, ≈70 words); gate-and-close c3 (the `done --evidence … --feedback …` command); read-pass-ledger; workflow-launch-args c2 (`Workflow({…})`); later-pass-sizing; seat-brief-names-pin c1; arm-rubric; the SCRATCH paragraphs | a backticked span is one anchor, held whole in the phrase; the first pass had dropped `— D-278` from inside one, which is why this entry was restored. |
| C pinned by a kept test outside Touches | workflow-launch-args c2 (`RUN_SCRATCH_CLAUSE` ≈50 words and `SCRATCH_HOME_CLAUSE` ≈70 words, `tests/test_review_loop_workflow.py`); seat-isolation-whole c1+c2 (≈120 words, equal to `/fabrik-review`'s copy, `tests/test_review_queue_pass.py`); seats-stamped-first ("Every pass's seats are STAMPED first"), seat-brief-names-pin ("Every seat brief names a PIN"), route-up-classification ("counted on the DIFF surface"), adjudicate (…"the previous seat's REFUTED list verbatim"), all `tests/test_assemble_dispatch_step.py`; route-up-classification's operator-named-work clause (`tests/test_governance_template_split.py`); later-pass-sizing's `--ids` window (`tests/test_review_command_text_defects.py`); `pass: <n>`, the next pass number (unbounded) (`tests/test_spec_review_queue_pass.py`) | those tests are kept behavioural tests this ticket never edits; each pinned phrase survives verbatim. |
| D operative condition beyond the first 8 stems | route-up-classification c3 prefix (the lane carve-out in parentheses: reversible, trips none of row 5's module tests, settles no trade-off); route-up-coverage c1 (the reach-back rule); scope-surface-add; behaviour-fix-red-first (the written-first / red-on-revert definition); local-vs-architectural-fix c4, c5 (the definition of ARCHITECTURAL); record-each-pass-round c3; round-ledger-is-artifact; ruff-before-each-pin c1 (`ruff check`, `ruff format --check`, scope of files); pin-manifest-bytes and pin-partly-committed c3 (a kept pin test asserts the contiguous span); seats-read-copies c3 (the paste is judged on line counts); escalate c2 (what makes defects the artifact's); scope-growth-name-and-reverify; closing-pass-independent-reader c2, c3 (the reason is the rule's one-clause reason); guard-or-rule-escape-variants (the class definition of ESCAPE VARIANTS); ask-verbatim-probe-catalogue (the quoted probe rule); floor-three-readers-round-one c1, c3, c4 | the tail is the instruction itself (a condition, a definition, a scope), not an aside; D-1240 would allow dropping it, but the reader then loses what to do. Each of these is a candidate for the hub's floor D-row if it rules the other way. |

**Self-audit.** NOT a fresh subagent: this run could dispatch none, so the zero-counts pass below is my own line-by-line pass over the baseline file, the rewrite and the ledger; the hub's author-blind audit pair covers it. Findings fixed during the pass: L75 had vanished unclassified after the leak-check cut (label added); `rule-sentence-sweep-first` had lost "for a rule already stated elsewhere", the purpose of the Sweep search (restored); the first draft's L33 note and L18 tail were relabelled as above. Open for the hub: L18's tail and L58 rest on the fragment carrying them; L69 keeps a 22-word tail only because of its ban word.
COUNTS: entries read 73 / reworded 39 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0 (author pass, not a fresh subagent)
