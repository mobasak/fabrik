# T07c receipt — /fabrik-review lean rewrite (full form)

Start commit (the unit's baseline commit): `61d1f4b99c6a8188a281f86799268fe54ee1b5d1` (`origin/kaizen-lean-u01`); the baseline file and its sha256 `f20a8500b2c92511eaccf9eab6930716790992faa981206519d6b03bdf5839b1` come from T07a and are unchanged. T07a: `327ba32`, T07b: `96b22e8`.

Worker: dispatched cloud worker, lean-t07. Loader on this base: `_ENTRY` holds neither `class` nor `clauses`, so each entry carries `# class: ban|grammar|behavioural|prose` and, where a clause is deleted, `# clauses: {<n>: narrative | duplicate-of: <id>}` (1-based, clauses split at `;` and ` — `) as YAML comments, for the hub to convert when the canonical loader lands. `command_rules.py` and `tests/test_command_rules.py` are untouched.

## Verdict

**NOT at 50%: 11089 words against a baseline of 12700 (87.3%).** The floor is named below; the hub mints the floor D-row. The self-audit counts are in `COUNTS:` at the end. Author labels on every vanished unit — **audit owed** (the Sonnet + Haiku classification pair cannot run in this clone).

## Own text, words (`command_rules.own_text`)

| file | before | after |
|---|---|---|
| `commands/_sources/fabrik-review.md` | 12700 | 11089 |

What went: the five `<!-- POOL OFF -->` comment blocks (778 words; a comment carries no rule, the pool contract is frozen in `docs/reference/subagent-pool-contract.md`, D-343), 56 narrative or duplicate clauses (783 words), and the front-matter description's repetition.

## The floor, and why this unit stops at 87.3%

A clause is covered when one `text` phrase holds all its anchors and 70% of its first 8 content-word stems (D-1240), and a clause holding a ban word stays verbatim from that word to the end of its `;`/` — ` clause or sentence (D-1240), and such a clause is never labelled `narrative` or `duplicate-of` (D-1238). Measured on this unit's live clauses:

- 552 live prose and table clauses after 56 deletions; 137 of them hold a ban word and their tails alone are 2120 words (16.7% of the baseline);
- the strict floor, every clause cut to its minimum window with its head and tail trimmed and nothing else kept, is **8832 words (69.5%)**; with the units a kept test holds raw it is 9429 words (74.2%). That text drops the subject of many sentences (`Every candidate lands on ONE of these` becomes `ONE of these`; `executed and shown false` becomes `false`; `Under the workflow (Phase 1) the slice's refuter…` loses its opener), and an executing agent cannot follow it, so it is not shipped;
- the live rule count is 283 entries (words per rule, 11089/283 = 39); the spec's own estimate for this command was a floor near 55-60% (spec § Binding, CONFIDENCE), which D-1240's per-clause floor cannot reach here because the termination contract, seat briefs and per-round obligations are ban-dense.

### Every clause still over its minimum, and why it cannot shrink

| code | reason | clauses | words over minimum | clause ids (`L<unit>.<clause>`, clauses 1-based) |
|---|---|---|---|---|
| T | kept test holds the text raw | 72 | 617 | 6.1 6.2 6.3 7.1 8.1 11.1 12.1 59.3 59.4 63.1 63.2 64.1 64.2 64.3 84.10 84.11 84.12 87.1 97.2 97.3 98.1 98.2 98.3 99.1 100.1 100.2 101.1 101.2 102.1 102.2 102.3 102.4 103.1 103.2 105.1 106.1 106.4 106.5 106.7 106.8 106.9 132.1 135.1 154.1 154.2 154.3 154.4 162.1 163.2 168.1 179.5 179.6 179.7 182.1 205.5 209.3 214.4 216.1 216.2 216.5 216.6 217.1 219.1 221.1 238.1 238.2 238.4 238.5 238.6 238.8 238.9 238.10 |
| B | ban clause: verbatim tail plus the head words its stems sit in | 81 | 300 | 3.4 10.1 10.2 19.2 26.5 34.1 49.3 51.1 54.1 59.1 67.1 68.4 69.1 71.1 74.4 76.1 76.4 79.3 81.3 83.5 84.3 85.1 95.1 95.3 96.3 109.2 112.2 112.9 112.12 114.2 119.1 121.1 122.2 122.3 134.1 137.1 138.3 142.1 144.2 149.1 152.1 153.1 157.3 164.1 167.2 168.2 171.3 180.1 181.2 186.2 191.1 192.3 197.1 199.2 201.3 204.1 206.1 210.1 213.1 215.2 218.1 220.1 222.1 224.3 225.1 232.2 236.2 239.1 242.1 246.1 247.1 249.2 252.2 258.2 265.1 265.2 267.1 270.1 271.4 273.1 275.1 |
| O | a strict cut would drop an instruction | 82 | 720 | 4.1 9.1 15.1 22.1 26.2 33.2 34.2 35.3 47.1 49.2 50.2 50.3 53.1 58.1 68.1 68.2 70.1 72.1 73.1 74.2 74.3 79.4 83.8 83.9 84.1 84.4 84.8 84.14 86.1 88.2 95.2 112.14 126.2 134.3 136.3 138.1 141.2 146.1 148.2 152.2 164.2 166.1 166.2 176.1 177.1 179.2 179.4 181.1 188.1 192.4 193.1 194.2 195.1 200.2 201.1 203.1 208.1 209.2 211.1 212.1 212.2 214.1 215.1 224.1 226.1 227.3 236.1 240.1 240.2 242.3 242.4 242.5 245.1 250.1 254.1 254.4 257.2 271.2 272.1 274.1 276.1 278.1 |
| F | a strict cut would drop only grammar | 149 | 827 | 1.1 3.3 10.3 10.4 14.2 18.1 21.2 21.4 22.2 22.3 27.1 29.1 33.1 35.1 38.1 39.1 43.1 47.2 50.1 50.4 52.1 53.2 56.1 59.2 61.1 61.2 66.1 71.2 75.1 76.2 76.3 77.1 79.1 79.6 80.1 81.1 82.1 83.1 83.3 83.4 84.6 84.16 86.4 91.1 91.3 91.4 91.5 92.1 92.2 94.1 96.1 107.1 108.1 108.2 108.3 109.1 110.1 111.1 111.2 112.3 112.5 112.6 112.11 112.13 114.1 115.1 116.1 117.1 119.2 120.1 122.1 124.1 125.1 126.1 127.1 128.1 128.2 128.3 129.1 132.2 133.1 133.2 136.2 138.2 145.2 155.2 158.1 159.1 162.2 164.3 165.1 165.2 167.1 169.1 170.1 171.2 175.2 176.2 179.1 179.8 187.2 190.2 194.1 194.3 198.1 198.2 200.1 205.1 205.2 205.4 205.6 207.1 224.2 225.2 230.1 230.2 231.1 231.2 234.1 236.3 237.1 237.2 242.2 242.6 243.2 245.2 249.1 249.3 249.4 252.1 254.3 256.1 257.1 258.1 260.1 261.1 261.3 264.2 264.3 266.1 268.2 269.1 269.2 269.3 271.1 271.3 273.2 274.2 277.1 |
| | total | 384 | 2464 | |

Reason codes: **T** a kept test holds the text raw (the test is named in § Kept tests below); **B** a clause holding a ban word: its tail is verbatim, and the head words before the ban word are kept because the clause's first 8 stems sit there; **O** the words a strict cut would drop hold an instruction (a verb such as run, read, keep, never, only, without) that no other clause carries, so cutting them loses the rule, not the wording; **F** the words a strict cut would drop are grammar and connectives (lead-ins, the end of a noun phrase) with no instruction in them; the strict floor above is what cutting them yields, and it is unreadable, so the hub decides whether to ship it.

### Kept tests that hold text raw (never edited here)

- `tests/test_review_loop_workflow.py`: the finder-lessons block (`Every finder brief carries these lessons VERBATIM` … `report \`MACHINERY:\` last.`), the leak-check bullet, the `A routed-up review` line, the `$ git archive -o <scratch_dir>/review-<sha>.tar <sha>` fence, the two `SCRATCH:` clauses, the `longest line > 2000 bytes` assert.
- `tests/test_assemble_dispatch_step.py`: `A class check must LOAD the artefact it grades`, `handed to a \`fabrik-researcher\` seat, never refuted from memory`, `a MUTATION-TESTING seat works on a COPY of the surface`, `\`/usr/bin/grep -rn --exclude-dir=worktrees`, `bounded-hop rule`.
- `tests/enforcement/test_review_refusals.py` (not runnable in this clone: shallow history): the `by design (D-nnn)` example, its `(D-432: <why>)` counter-example, `with its \`, round N\` for a receipt row`.
- Two-file and looping asserts: `test_both_review_commands_carry_the_seat_isolation_sentence_verbatim`, `test_the_opt_in_fallback_is_stated_in_every_copy`, `test_both_review_commands_name_surface_add_for_a_pre_start_file`, `test_the_lead_runs_the_leak_check_around_every_scoped_pass`, `test_each_next_recipe_points_at_args_and_the_scripts_doc`, `test_no_command_caps_the_workflow_pass_number`, `test_the_whole_plan_receipt_is_named_by_the_plan_stem_so_check_convergence_matches_it`.

## Lever T1 and `changed-by`

T1 (one finder per slice) is **not proposed**: `command_rules._ENTRY` carries `changed-by`, but intel's D-344 recall measure (confirmed candidates per seat) does not exist on this base, so no entry lists `changed-by`. Levers T2, T5, T6 are plain rewrites of the text; no rule was changed on purpose.

## Ledger

| | count |
|---|---|
| entries in `commands/_rules/fabrik-review.yaml` | 283 (1 points at a fragment) |
| reworded (`current` differs from `baseline`) | 58 |
| `# clauses:` comments | 18 |
| by class | ban 93 · grammar 53 · behavioural 31 · prose 106 |
| reworded, by class | ban 25 · behavioural 4 · grammar 1 · prose 28 |
| vanished labels | 66: rule 42 · narrative 17 · duplicate-of 7 |

The pin entries from T07a and T07b are kept under their own ids (61 `rq-…` entries after regeneration; a pin whose phrases now sit in one unit is one entry), each re-pointed at the rewritten unit and keeping its `forbidden:`, `ordered:` and `pins:` carriers; every other rule unit has an `fr-…` entry. Phrases are the minimum window that holds a clause's anchors, its ban tail and 70% of its first 8 stems, extended to 6 words and until unique in the file; `ordered:` and `forbidden:` carriers and the `pins:` node ids are kept.

### Reworded entries: clause count and how each clause is covered

`p<k>` is the entry's k-th `text` phrase, `→id` another entry of the same baseline unit, `narr` and `dup` a deleted clause (its `# clauses:` comment).

| entry | class | L | clauses | coverage |
|---|---|---|---|---|
| `fr-command-5-phases-0-4` | ban | 3 | 5 | 1:p1 2:p2 3:p3 4:p4 5:p5 |
| `fr-routed-up-review-names-trigger` | behavioural | 6 | 4 | 1:p1 2:p2 3:p3 4:p4 |
| `fr-always-name-run-you-close` | prose | 13 | 1 | 1:p1 |
| `fr-arm-finders-run-python-scripts` | ban | 26 | 6 | 1:p1 2:p2 3:→fr-arm-finders-run-python-scriptsb 4:→fr-arm-finders-run-python-scriptsb 5:→fr-arm-finders-run-python-scriptsb 6:→fr-arm-finders-run-python-scriptsb |
| `fr-arm-finders-run-python-scriptsb` | ban | 26 | 6 | 1:→fr-arm-finders-run-python-scripts 2:→fr-arm-finders-run-python-scripts 3:p1 4:p1 5:p3 6:p4 |
| `fr-synced-file-appearing-diff-itself` | prose | 33 | 3 | 1:p1 2:p2 3:narr |
| `fr-seeded-enforced-set-exception-read` | ban | 35 | 5 | 1:p1 2:p2 3:p3 4:p4 5:p5 |
| `fr-hub-opt-fabrik-files-product` | prose | 37 | 2 | 1:p1 2:p2 |
| `fr-finder-given-sha-must-read` | ban | 54 | 2 | 1:p1 2:narr |
| `fr-you-hand-finder-sha-materialise` | prose | 56 | 1 | 1:p1 |
| `fr-run-review-hygiene-check-surface` | prose | 65 | 1 | 1:p1 |
| `fr-four-selector-flags-repeatable-actionb` | prose | 66 | 4 | 1:→fr-four-selector-flags-repeatable-action 2:→fr-four-selector-flags-repeatable-action 3:→fr-four-selector-flags-repeatable-action 4:p1 |
| `fr-lines-print-note-text-output` | ban | 69 | 2 | 1:p1 2:p2 |
| `fr-digest-pins-bytes-seat-reads` | prose | 75 | 3 | 1:p1 2:p2 3:p3 |
| `rq-execute-plan-run-seats-its-per-round-opus-floor` | ban | 79 | 6 | 1:→fr-worker-pool-off-d-181 2:→fr-worker-pool-off-d-181b 3:→fr-worker-pool-off-d-181 4:p1 5:narr 6:→fr-worker-pool-off-d-181 |
| `fr-worker-pool-off-d-181` | ban | 79 | 6 | 1:p1 2:→fr-worker-pool-off-d-181b 3:p2 4:→rq-execute-plan-run-seats-its-per-round-opus-floor 5:narr 6:p3 |
| `fr-worker-pool-off-d-181b` | ban | 79 | 6 | 1:→fr-worker-pool-off-d-181 2:p1 3:→fr-worker-pool-off-d-181 4:→rq-execute-plan-run-seats-its-per-round-opus-floor 5:narr 6:→fr-worker-pool-off-d-181 |
| `fr-risky-slices-concurrency-locks-record` | prose | 80 | 3 | 1:p1 2:p2 3:p3 |
| `rq-counter-word-in-method-cell-refused` | ban | 83 | 10 | 1:→fr-pass-1-row-s-method 2:p1 3:p1 4:p1 5:p1 6:p2 7:narr 8:→fr-pass-1-row-s-method 9:→fr-pass-1-row-s-method 10:narr |
| `fr-pass-1-row-s-method` | ban | 83 | 10 | 1:p1 2:p2 3:p3 4:p4 5:p5 6:p5 7:narr 8:p5 9:p6 10:narr |
| `rq-trimmed-single-finder-slice-second-next-wave` | behavioural | 84 | 17 | 1:→rq-briefs-and-fix-lists-live-under-scratch 2:→rq-briefs-and-fix-lists-live-under-scratch 3:→rq-briefs-and-fix-lists-live-under-scratch 4:→rq-briefs-and-fix-lists-live-under-scratch 5:→rq-briefs-and-fix-lists-live-under-scratch 6:→rq-briefs-and-fix-lists-live-under-scratch 7:→rq-briefs-and-fix-lists-live-under-scratch 8:→rq-briefs-and-fix-lists-live-under-scratch 9:→rq-briefs-and-fix-lists-live-under-scratch 10:→rq-briefs-and-fix-lists-live-under-scratch 11:→rq-briefs-and-fix-lists-live-under-scratch 12:→rq-briefs-and-fix-lists-live-under-scratch 13:→rq-briefs-and-fix-lists-live-under-scratch 14:p1 15:→fr-size-python3-opt-fabrik-scripts 16:→fr-size-python3-opt-fabrik-scripts 17:→fr-size-python3-opt-fabrik-scripts |
| `rq-briefs-and-fix-lists-live-under-scratch` | behavioural | 84 | 17 | 1:p1 2:p1 3:p1 4:p1 5:p1 6:p1 7:p1 8:p1 9:p1 10:p1 11:p1 12:p1 13:p2 14:→rq-trimmed-single-finder-slice-second-next-wave 15:→fr-size-python3-opt-fabrik-scripts 16:→fr-size-python3-opt-fabrik-scripts 17:→fr-size-python3-opt-fabrik-scripts |
| `fr-size-python3-opt-fabrik-scripts` | behavioural | 84 | 17 | 1:p1 2:p2 3:p3 4:p4 5:p5 6:p6 7:p7 8:p8 9:p9 10:p10 11:p11 12:p12 13:p12 14:p12 15:p12 16:p13 17:p14 |
| `fr-you-never-finder-you-partition` | ban | 88 | 3 | 1:p1 2:p2 3:narr |
| `fr-satisfied-construction-seat-native-d` | ban | 91 | 7 | 1:p1 2:→fr-satisfied-construction-seat-native-db 3:p2 4:p3 5:p4 6:p5 7:narr |
| `fr-satisfied-construction-seat-native-db` | ban | 91 | 7 | 1:→fr-satisfied-construction-seat-native-d 2:p1 3:→fr-satisfied-construction-seat-native-d 4:→fr-satisfied-construction-seat-native-d 5:→fr-satisfied-construction-seat-native-d 6:→fr-satisfied-construction-seat-native-d 7:narr |
| `fr-partition-don-t-skip-moot` | prose | 92 | 4 | 1:p1 2:p2 3:dup 4:dup |
| `fr-matters-because-two-recoveries-opposite` | prose | 105 | 2 | 1:p1 2:narr |
| `fr-finder-surfaces-candidate-concrete-nameable` | prose | 110 | 3 | 1:p1 2:p2 3:narr |
| `rq-fixture-equal-to-own-constant-is-test-quality-finding` | ban | 112 | 14 | 1:→fr-yes-proves-nothing-written-after 2:→fr-yes-proves-nothing-written-after 3:→fr-yes-proves-nothing-written-after 4:→fr-yes-proves-nothing-written-after 5:→fr-yes-proves-nothing-written-after 6:→fr-yes-proves-nothing-written-after 7:→fr-yes-proves-nothing-written-after 8:→fr-yes-proves-nothing-written-after 9:→fr-yes-proves-nothing-written-after 10:narr 11:p1 12:p2 13:→rq-vacuous-test-value-compared-with-itself 14:→fr-yes-proves-nothing-written-after |
| `rq-vacuous-test-value-compared-with-itself` | ban | 112 | 14 | 1:→fr-yes-proves-nothing-written-after 2:→fr-yes-proves-nothing-written-after 3:→fr-yes-proves-nothing-written-after 4:→fr-yes-proves-nothing-written-after 5:→fr-yes-proves-nothing-written-after 6:→fr-yes-proves-nothing-written-after 7:→fr-yes-proves-nothing-written-after 8:→fr-yes-proves-nothing-written-after 9:→fr-yes-proves-nothing-written-after 10:narr 11:→rq-fixture-equal-to-own-constant-is-test-quality-finding 12:→rq-fixture-equal-to-own-constant-is-test-quality-finding 13:p1 14:→fr-yes-proves-nothing-written-after |
| `fr-yes-proves-nothing-written-after` | ban | 112 | 14 | 1:p1 2:p2 3:p3 4:p4 5:p5 6:p6 7:p7 8:p8 9:p9 10:narr 11:→rq-fixture-equal-to-own-constant-is-test-quality-finding 12:→rq-fixture-equal-to-own-constant-is-test-quality-finding 13:→rq-vacuous-test-value-compared-with-itself 14:p10 |
| `fr-12-factor-checklist-one-finder` | prose | 115 | 2 | 1:p1 2:p2 |
| `fr-measured-fix-converted-three-render` | ban | 139 | 2 | 1:p1 2:narr |
| `fr-4-14-rows-real-ledger` | ban | 140 | 1 | 1:p1 |
| `fr-refuted-executed-shown-false-quoteb` | prose | 145 | 2 | 1:p1 2:→fr-refuted-executed-shown-false-quote |
| `fr-refute-something-merely-needing-rare` | prose | 146 | 1 | 1:p1 |
| `fr-defect-code-s-own-author` | prose | 147 | 1 | 1:p1 |
| `fr-dropped-rides-ledger-unexecuted-counter` | prose | 150 | 2 | 1:p1 2:→fr-dropped-rides-ledger-unexecuted-counterb |
| `fr-dropped-rides-ledger-unexecuted-counterb` | prose | 150 | 2 | 1:→fr-dropped-rides-ledger-unexecuted-counter 2:p1 |
| `fr-fixed-reproduce-runnable-test-executionb` | prose | 163 | 2 | 1:p1 2:→fr-fixed-reproduce-runnable-test-execution |
| `rq-decision-row-after-code-with-id-reserved-before-close` | ban | 164 | 5 | 1:→fr-deliberate-design-decision-resolves-e 2:p1 3:→fr-deliberate-design-decision-resolves-e 4:→fr-deliberate-design-decision-resolves-e 5:→fr-deliberate-design-decision-resolves-e |
| `fr-deliberate-design-decision-resolves-e` | ban | 164 | 5 | 1:p1 2:→rq-decision-row-after-code-with-id-reserved-before-close 3:p2 4:p3 5:p4 |
| `fr-test-passes-because-environment-cannot` | prose | 169 | 2 | 1:p1 2:narr |
| `fr-reach-missing-constraint-throwaway-ephemeral` | prose | 170 | 2 | 1:p1 2:narr |
| `fr-changes-what-counts-proof-dispositions` | prose | 172 | 2 | 1:p1 2:p2 |
| `fr-local-resolution-unambiguous-contained-missingb` | prose | 187 | 2 | 1:p1 2:→fr-local-resolution-unambiguous-contained-missing |
| `fr-fix-run-autonomously-common-case` | prose | 188 | 2 | 1:p1 2:p2 |
| `fr-architectural-finding-real-correct-fixb` | prose | 190 | 2 | 1:p1 2:→fr-architectural-finding-real-correct-fix |
| `fr-fix-only-contract-effect-contained` | ban | 191 | 2 | 1:p1 2:narr |
| `fr-changes-what-caller-assume-describes` | ban | 192 | 4 | 1:p1 2:p1 3:p1 4:p4 |
| `fr-one-row-review-covering-architectural` | prose | 194 | 3 | 1:p1 2:p2 3:p3 |
| `fr-you-cannot-tell-side-finding` | prose | 195 | 2 | 1:p1 2:p2 |
| `fr-record-shape-finding-s-disposition` | ban | 199 | 2 | 1:p1 2:p2 |
| `fr-steps-below-same-bytes-runs` | prose | 231 | 2 | 1:p1 2:p2 |
| `fr-shown-here-because-reviewer-mid` | ban | 232 | 2 | 1:p1 2:p2 |
| `rq-example-ledger-seat-mix-2` | prose | 260 | 2 | 1:p1 2:dup |
| `fr-new-stays-prose-row-stopped` | grammar | 264 | 7 | 1:p1 2:p2 3:p3 4:p4 5:p5 6:p6 7:p7 |

## Pins deleted

See the T07a and T07b receipts: 20 tests deleted and 12 trimmed in `tests/test_review_queue_pass.py`; 3 tests deleted and 1 trimmed in `tests/test_review_command_text_defects.py`; 1 assert in `tests/test_plan_review_queue_pass.py`. This ticket edits no test.

## Vanished labels (author labels — audit owed)

| L | label | baseline unit (first 90 chars) |
|---|---|---|
| L3 | rule: `fr-command-5-phases-0-4` | This command has 5 phases (0–4) and exactly one terminal condition, and it has TWO parts t |
| L6 | rule: `fr-routed-up-review-names-trigger` | A routed-up review names the trigger in its surface: `--surface "ROUTED-UP: step 1 — <the  |
| L13 | rule: `fr-always-name-run-you-close` | Always name the run you close: a bare close would end whatever is live, which after this r |
| L26 | rule: `fr-arm-finders-run-python-scripts`, `fr-arm-finders-run-python-scriptsb` | ARM the finders — run `python scripts/review_rubric.py --changed <the diff's paths>` and I |
| L28 | narrative | Honesty (L1): the injection STEP is maximally enforced (the rubric is always injected); th |
| L31 | narrative | An agent that helpfully edits a synced file creates the exact drift the gate exists to cat |
| L32 | narrative | Wasted review budget at best, a Tier-1 violation at worst |
| L33 | rule: `fr-synced-file-appearing-diff-itself` | A synced file appearing IN THE DIFF is ITSELF a CONFIRMED finding: *"synced file modified  |
| L35 | rule: `fr-seeded-enforced-set-exception-read` | The `SEEDED_NOT_ENFORCED` set is the exception (read the live set in `fabrik_synced_manife |
| L36 | duplicate-of: `fr-get-list-mechanically-never-hand` | This is exactly why the list is computed, not written by hand |
| L37 | rule: `fr-hub-opt-fabrik-files-product` | HUB (`/opt/fabrik`) — these files ARE the product, and they carry the widest blast radius  |
| L42 | narrative | (a pack that fights another is worse than no pack) |
| L44 | narrative | (a gate that cries wolf gets `# noqa`'d into uselessness — that is how a check dies) |
| L45 | narrative | Proven live: review is what caught a hallucinated Kubernetes section and a fleet-breaking  |
| L46 | narrative | Excluding these files from review would have shipped both |
| L48 | duplicate-of: `fr-seeded-repro-contract-invoked-committed` | Adjudicating every checklist class while the seeded repro stays red is NOT a valid exit |
| L54 | rule: `fr-finder-given-sha-must-read` | ⚠️ A FINDER GIVEN A SHA MUST NOT READ THE LIVE TREE — it is probably dirty, and not with y |
| L55 | narrative | A finder handed `HEAD <sha>` and pointed at the live tree silently reviews THEIR half-fini |
| L56 | rule: `fr-you-hand-finder-sha-materialise` | When you hand a finder a sha, materialise that sha: |
| L60 | narrative | This is the same class as the `Surface:` anchor rule — both are about the finder actually  |
| L65 | rule: `fr-run-review-hygiene-check-surface` | Run the review-hygiene check on the surface FIRST and fix its hits before the seats go out |
| L69 | rule: `fr-lines-print-note-text-output` | Those lines print as `[NOTE] …` in the text output ONLY; under `--json` they ride the `not |
| L75 | rule: `fr-digest-pins-bytes-seat-reads` | ⚠️ The digest pins which bytes a seat reads; nothing pins what they MEAN — a seat with the |
| L78 | narrative | Worked case, beside the code that owns it: `scripts/enforcement/check_review_coverage.py:: |
| L79 | rule: `rq-execute-plan-run-seats-its-per-round-opus-floor`, `fr-worker-pool-off-d-181`, `fr-worker-pool-off-d-181b` | Worker: while the pool is OFF (D-181) every seat is NATIVE `fabrik-reviewer`, and the surf |
| L80 | rule: `fr-risky-slices-concurrency-locks-record` | The risky slices (concurrency and locks, record and file formats, fleet-synced paths — `sc |
| L83 | rule: `rq-counter-word-in-method-cell-refused`, `fr-pass-1-row-s-method` | The Pass-1 row's Method cell carries the per-seat count as free text — `seats: A-sonnet 3/ |
| L84 | rule: `rq-trimmed-single-finder-slice-second-next-wave`, `rq-briefs-and-fix-lists-live-under-scratch`, `fr-size-python3-opt-fabrik-scripts` | Size it with `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --slices sonnet=N, |
| L88 | rule: `fr-you-never-finder-you-partition` | YOU are never a finder — you partition, dispatch and adjudicate, and Phase 2 makes you EXE |
| L89 | duplicate-of: `fr-never-write-pool-check-subagent` | Nothing records to the flywheel and no `NO-POOL:` is owed (`check_subagent_flywheel.py` st |
| L90 | narrative | The pool-breadth contract follows, commented for re-enable: |
| L91 | rule: `fr-satisfied-construction-seat-native-d`, `fr-satisfied-construction-seat-native-db` | (Satisfied by construction while every seat is native — D-181; it binds again on re-enable |
| L92 | rule: `fr-partition-don-t-skip-moot` | Partition, don't skip (moot while every seat is native — D-181/D-182): the slice's two fin |
| L93 | narrative | The two mechanisms: |
| L104 | narrative | Observed repeatedly, this session |
| L105 | rule: `fr-matters-because-two-recoveries-opposite` | That matters because the two recoveries are opposite: a backgrounded mutation finishes and |
| L110 | rule: `fr-finder-surfaces-candidate-concrete-nameable` | Each finder surfaces every candidate with a concrete, nameable failure scenario — do NOT d |
| L112 | rule: `rq-fixture-equal-to-own-constant-is-test-quality-finding`, `rq-vacuous-test-value-compared-with-itself`, `fr-yes-proves-nothing-written-after` | (if yes, it proves nothing — it was written after the code and never watched fail); assert |
| L115 | rule: `fr-12-factor-checklist-one-finder` | 12-Factor checklist (one finder OWNS this class — these are GREPPABLE, so there is no excu |
| L139 | rule: `fr-measured-fix-converted-three-render` | Measured: a fix converted three render cells from a row-count gate to a value-only gate, e |
| L140 | rule: `fr-4-14-rows-real-ledger` | 4 of 14 rows of the real ledger gained a phantom zero, and the next round's seat found it  |
| L146 | rule: `fr-refute-something-merely-needing-rare` | Do not refute something merely for needing a "rare but reachable" state (error handler, co |
| L147 | rule: `fr-defect-code-s-own-author` | A defect the code's own author cannot see is exactly what this step exists to catch, so do |
| L150 | rule: `fr-dropped-rides-ledger-unexecuted-counter`, `fr-dropped-rides-ledger-unexecuted-counterb` | It is not dropped — it rides the ledger and the `unexecuted:` counter, and an unexecuted C |
| L164 | rule: `rq-decision-row-after-code-with-id-reserved-before-close`, `fr-deliberate-design-decision-resolves-e` | A deliberate design decision that resolves it (e.g. choosing fail-open with a logged warni |
| L169 | rule: `fr-test-passes-because-environment-cannot` | A test that passes because the environment cannot express the failure has proven nothing — |
| L170 | rule: `fr-reach-missing-constraint-throwaway-ephemeral` | Reach for the missing constraint in a throwaway/ephemeral instance you own — a scratch DB, |
| L172 | rule: `fr-changes-what-counts-proof-dispositions` | This changes what counts as proof; dispositions below are unchanged |
| L173 | duplicate-of: `fr-refuted-executed-shown-false-quote` | REFUTED — you did the work to PROVE it cannot happen: quote the guard / type / invariant t |
| L174 | duplicate-of: `fr-execute-refutation-refutation-proof-shrug` | Promoting a finding to REFUTED requires proof, not a shrug |
| L178 | narrative | (This is the exact failure this command exists to stop: finders raise PLAUSIBLE findings a |
| L188 | rule: `fr-fix-run-autonomously-common-case` | Fix it in-run, autonomously. This is the common case; do not manufacture ceremony for it |
| L189 | narrative | (The axis is LOCAL/ARCHITECTURAL, not "mechanical" — that word already means *done by mach |
| L191 | rule: `fr-fix-only-contract-effect-contained` | (A fix whose only contract effect is contained in the function you changed stays LOCAL and |
| L192 | rule: `fr-changes-what-caller-assume-describes` | "Changes what a caller can assume" describes most correctness fixes; it is NOT the trigger |
| L194 | rule: `fr-one-row-review-covering-architectural` | One row per REVIEW covering its architectural picks — unless a pick is ONE-WAY, which earn |
| L195 | rule: `fr-you-cannot-tell-side-finding` | When you cannot tell which side a finding sits on, treat it as ARCHITECTURAL and mint the  |
| L196 | duplicate-of: `fr-plausible-licence-skip-opposite-plausible` | (The rest of this phase defaults the same way — "PLAUSIBLE is not a licence to skip — it i |
| L199 | rule: `fr-record-shape-finding-s-disposition` | Record the shape in the finding's disposition row (`FIXED(n) · LOCAL` / `FIXED(n) · ARCHIT |
| L231 | rule: `fr-steps-below-same-bytes-runs` | The steps below are the SAME BYTES it runs — both files render them from one shared fragme |
| L232 | rule: `fr-shown-here-because-reviewer-mid` | They are shown here because a reviewer mid-loop needs the shape without leaving the page,  |
| L253 | narrative | On a shared tree a check that reads beyond your change can red on another lane's work, and |
| L260 | rule: `rq-example-ledger-seat-mix-2` | Note pass 3: the finders raised one FRESH candidate, which you executed and refuted — a ra |
| L262 | duplicate-of: `fr-term-coverage-quiet-row` | This is what reconciles the loop with its graders: `check_convergence.py`'s QUIET_PASS and |
| L263 | narrative | Counting refutations made honest termination impossible; suppressing them would hide real  |
| L264 | rule: `fr-new-stays-prose-row-stopped` | `new:` stays PROSE on the row — the stopped-learning signal, whose VALUE no grader reads a |

## Gates

- `tests/test_command_rules.py -rP`: 32 passed, 3 skipped; `LEDGER fabrik-review.yaml: 283 entries · vanished {…}`, zero LOSS lines.
- `assemble_commands.py --check`: exit 1, 84 DRIFT lines, every one `DIFFERS from what this tree renders` or `MISSING`; no LOSS, no ORPHAN, no ceiling line.
- Reader-test run (spine § Global Constraints): the 73 test files that name `fabrik-review` or glob a corpus directory, once at the start commit and once at this commit.

| | failed | passed |
|---|---|---|
| start commit (`61d1f4b99`) | 153 | 4025 |
| this commit | 154 | 4001 |

Start set (153): 95 in `tests/enforcement/test_review_refusals.py` (the clone is shallow; the tests `git show` an old commit), 15 `test_fabrik_deck.py`, 12 `test_generate_capability_index.py`, 7 `test_quota_dashboard.py`, 7 `test_check_command_corpus.py`, 5 `test_conftest_isolation.py`, 2 `sysadmin/test_rules_render_versions.py` and 10 singletons, all missing box services or dependencies (`psutil`, `harbor`, a git history). The start run began at `61d1f4b99` and my T07a/T07b test edits landed while it ran, so I re-ran the two files they touch in a clean worktree at `61d1f4b99`: `test_review_queue_pass.py::test_a_cwd_rooted_tool_runs_after_an_os_chdir` (needs `psutil`) is the one failure there too.

End set (154): the same 153, plus `tests/test_stop_hook_quota_hold_exemption.py::test_urgent_tier_records_stood_down_causes`. It passes alone and with its whole file (26 passed) at this commit, reads `fabrik-review` only in a fixture string, never the source, and asserts on stood-down hook state, so it is order-dependent in the long run, not a Touches miss. No test that reads `fabrik-review.md` is red at this commit that was green at the start.

## Self-audit (before every push)

I ran the four checks line by line against `baseline_sentences:` at the start commit, not from memory: (1) LOST — every non-deleted baseline clause is covered by a phrase that holds its anchors, its ban tail verbatim and 70% of its first 8 stems (`audit.py`-style scan over the ledger as written: 0 uncovered of 552); (2) WEAKER — each phrase checked for the same three conditions and for ≥6 words and uniqueness in the file: 0; (3) INVENTED — every word of the new source occurs in the baseline (8 tokens differ only by punctuation), and a 4-gram scan shows only the compressions made on purpose: 0; (4) WRONG-VANISHED-LABEL — each of the 66 labels read against the baseline text: 0.

What earlier passes fixed: 89 clauses of the first draft had no carrier (ban clauses whose incident anecdote I had cut — `01M25Q9S0`, the lessons list ids, `(01M215G84)`, the `(Same class as the \`measured by:\` rule above…)` sentence — restored verbatim; non-ban rationale restored where the first 8 stems sat in it); 3 entries first pointed at a heading unit or at an earlier paragraph (the `Its TERMINAL verdict` ordering) and were re-aimed.

COUNTS: entries read 283 / reworded 58 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0

## LEFT FOR THE HUB

- The author-blind Sonnet + Haiku audit of the 66 vanished labels and the 58 reworded entries (`author labels — audit owed`); the review wave; the floor D-row for `/fabrik-review` (11089 words, 283 rules, 39 words per rule); the ceiling ratchet of `commands/_size_ceiling.json`; `INDEX.md` rows for `commands/_rules/fabrik-review.*` and the three receipts; `CHANGELOG.md`; the D-row for removing the five `<!-- POOL OFF -->` comment blocks from this source (D-343 says the corpus keeps them; this unit drops them as rule-free text because `docs/reference/subagent-pool-contract.md` holds the contract) — reverse it by restoring the comments if the hub disagrees (they carry no ledger entry).
- When the canonical loader (`class`, `clauses` keys) lands, convert the `# class:` and `# clauses:` comments to keys.
