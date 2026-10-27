OWN TEXT: 4839 -> 4461 (92%)

# T14 receipt — lean rewrite of /fabrik-spec-review

- **Start commit:** `851b4b365cc9ccaac91ed851bc669764743ad360` (baseline written from its text; `fabrik-spec-review.baseline.txt` sha256 in the ledger)
- **Own-text words:** 4839 → 4661 (96% of baseline; target ≤50%). **Floor named below.**
- **Ledger entries:** 133 total = 126 generated-unchanged (`u-L<n>`, `generate_unchanged`) + 7 reworded (`r-L<n>`, hand-covered). Reworded / total = 7/133.
- **By class (D-1236 tag, set at baseline):** unchanged {'prose': 84, 'ban': 38, 'behavioural': 4} · reworded {'prose': 6, 'behavioural': 1}. The tag is a `# class:` YAML comment (the loader on this base has no `class` key).
- **Vanished baseline lines:** 9 = 7 `rule:` (covered by a reworded entry) + 2 `narrative` (every clause labelled narrative). 12 clauses inside the `rule:` lines are labelled narrative, recorded per entry as a `# clauses:` comment.
- **Labels:** author labels — audit owed (the Sonnet + Haiku classification seats cannot run in this clone).
- **Audit weaker-count:** not run — the author-blind audit pair cannot run in this clone, so every `rule`/`narrative` label above is an author label and the weaker-count is owed by the audit (reworded entries / total entries are stated above).
- **Coverage rule applied by hand (D-1240):** per clause (split at `;`/`—`, outside code spans) ONE `text` phrase holds 100% of the clause's anchors (backticked tokens, numbers, paths, ban words) and ≥70% of its first 8 content-word stems; a clause holding never/must/only/refus* is verbatim from that word to the end of its clause and is never labelled narrative; the carrier holds the same ban token; every phrase is ≥6 normalised words and unique in the file. Checked by a scratch script (not committed; `commands/command_rules.py` was not edited).

## Floor
Measured on the start-commit text (clauses split at `;`/`—` outside code spans): of 4839 words, 564 sit in ban-clause tails kept verbatim by D-1240, 482 in the heads of those clauses, 1865 in non-ban clauses with backticked tokens, numbers or paths, and 1664 in clauses with neither. The pass dropped 12 narrative clauses and 2 whole lines (the framing sentence, the live-incident anecdotes, the incidence statistic) and left every audit axis (A0, A0b, A-E), the 12-Factor audit table, the partition/`Workflow` mechanics and the approval-gate grammar, each of which is an anchor-bearing instruction. Result 96% of baseline, not 50%. Reaching 50% needs the partition/`Workflow` paragraph (703 words) and the liveness-oracle bullet, which `/fabrik-plan-review` repeats nearly word for word, moved into one ledgered fragment; D-1240's per-clause rule does not allow that inside this unit. A floor D-row is owed.

## Reworded entries — clause count and how each clause is covered

| entry | class | clauses | coverage (P = covered by phrase n of the entry · N = narrative label) |
|---|---|---|---|
| r-L1 | prose | 2 | 1:P1 2:N |
| r-L3 | prose | 4 | 1:P1 2:N 3:N 4:N |
| r-L14 | behavioural | 2 | 1:P1 2:N |
| r-L19 | prose | 3 | 1:P1 2:P2 3:P3 |
| r-L41 | prose | 2 | 1:P1 2:N |
| r-L48 | prose | 2 | 1:P1 2:P2 |
| r-L93 | prose | 3 | 1:P1 2:N 3:N |

## Lines labelled narrative (whole unit)

- L23: ## Phase 1 — Adversarial grounding to a fixed point (the section partition) ¦ This axis is the checking half of the authoring contract; without it the inventory
- L32: ## Phase 1 — Adversarial grounding to a fixed point (the section partition) ¦ Live 2026-08-27 (fabrik-lib): a WebFetch answer supplied a sentence that is nowher

## Clauses labelled narrative inside reworded lines

- L1.2: do not stop after one pass
- L3.2: and the two this pass exists to catch
- L3.3: are (1) an external fact taken from training memory or backed by a dead/hallucinated citation, and (2) a fabrik-lib verdict that reinvents what alread
- L3.4: both invisible until someone re-verifies against the real world
- L14.2: a Status-reading gate skips a DRAFT, so the unflipped spec passes over nothing
- L23.1: This axis is the checking half of the authoring contract
- L23.2: without it the inventory is graded by the agent it constrains
- L32.1: Live 2026-08-27 (fabrik-lib): a WebFetch answer supplied a sentence that is nowhere in the page AND inverted the mechanism it described
- L32.2: the fabricated quote survived the author's self-review and carried the spec's central build-vs-buy verdict
- L41.2: that file is a curated index, not a manifest (the same report found a leaked third-party planning doc inside one)
- L93.2: those four heal a TRANSIENT fault
- L93.3: a permanent provider death needs a SWAP no retry loop can make

## Pins deleted
none — no Touches test went red (`tests/test_spec_plan_lane_text.py tests/test_spec_queue_pass.py tests/test_spec_review_queue_pass.py`), so no assert was deleted and no `pins:` node recorded.

## Failure sets (reader-test run, `capped_run.sh` unavailable in the clone: plain pytest)
Targeted run on the real tree: `tests/test_spec_plan_lane_text.py tests/test_spec_queue_pass.py tests/test_spec_review_queue_pass.py tests/test_command_rules.py`: 77 passed, 3 skipped, 0 failed. The full reader-set failure set (55 at the start commit) is re-run at the end of the batch and recorded in the T19 receipt.

**Final run (all five tickets applied, tree at the last commit):** the same reader set (65 test files) plus `tests/test_command_rules.py`, plain `python3 -m pytest` with `.git` present in the scratch copy: 53 failed + 2 collection errors = **55, the identical set to the start commit** (`comm` of the sorted FAILED/ERROR node ids: 0 new, 0 gone). The first full run of the finished tree had found 4 new reds (all `/fabrik-plan-review` drops pinned outside any Touches test: the EXTRACT after-text block, a digest-grammar clause, the `/fabrik-generate-tests` mention); the three clauses were restored in the fix commit and the second full run is the one reported here. The pre-existing 55 are box-service or optional-dependency reds, unchanged by this batch.

## Re-ledger round (canonical loader, W-9cd8653d / D-1245)

- **Own-text words:** baseline 4839 → fix round 4661 → now 4461 (92% of baseline; target ≤50%, not reached — floor table below). Measured as the render's word delta from `assemble_commands.py --check` (34335 → 34135, every edit inside own text).
- **LOSS before → after (this ledger):** 0 → 0 under master's loader on the base; it stayed 0 after the cut. `--check` still prints LOSS lines for `_shared/*.yaml` and for other commands' ledgers (T01d and the other tickets): not mine, untouched.
- **Ledger keys:** every `# class:` / `# clauses:` comment is now a real `class:` / `clauses:` key (131 entries: ban 38, behavioural 5, prose 88). Unchanged units are carried by one entry each (`baseline` + the same string as its `text`, via a YAML alias); the separator row `|---|---|` has no entry (a pipe-only phrase is not unique in the render, and `vanished()` already keeps the row).
- **Reworded / total entries:** 21 / 131 (`r-L<n>`); 24 vanished baseline lines = 21 `rule:` + 3 `narrative` (L3, L23, L32).
- **Reworded this round (OLD → NEW cut):** r-L2 (drops "defines it", "adversarial", "before it is trusted"), r-L7 (clause 2 "CONVERGED means ready-to-build…" narrative), r-L8 ("actually", "(the ship already happened)"), r-L21 ("the exact defect the operator chases"), r-L25 (the "does it take into account roles?" incident, the transdoc anecdote, "nobody's persona asked for"), r-L29 ("over the document", "satisfies the letter of", "its purpose"), r-L30 ("hit live … on a martinfowler.com quote"), r-L34 (clause 2, the three example claims, narrative), r-L36 ("grep it, line anchors drift", "deliberately"), r-L37 (clause 2 "instructing it to … fail (reported by fabrik-lib `01M14V7KH4` …)", narrative), r-L42 (the parenthetical gloss of "approach"), r-L44 (clause 3 "the review is the second chance…", narrative; "you are about to make"), r-L59 (the D-425 incident, id kept), r-L64 (the roles/growth/doc-home incident), r-L81 (the Litmus parenthetical), r-L95 ("deliberately … advisory wallpaper"), r-L97 (clause 2, the Stripe example, narrative), r-L105 ("a repo or checkout the sync has not reached"); carried over and converted to keys: r-L14, r-L41, r-L93.
- **Fixed from the fix round (a pass found them):** L1 "— do not stop after one pass" and L19 "do NOT trust it" were dropped and covered by `text` phrases borrowed from other lines (a stub carrier, D-253); both restored word for word, so L1 and L19 no longer vanish. L48 "— the #1 spec defect" restored for the same reason (its second phrase was the L21 sentence). L3 was covered by a phrase from L25; it is now an honest `narrative` label (a framing sentence; the failure classes are rules in A and B).
- **Class tags:** unchanged from the fix round (u-L6, u-L33, u-L101, u-L102 and r-L14 stay `behavioural`; their text is verbatim). No pin test was deleted: every kept assertion in `tests/test_spec_plan_lane_text.py`, `tests/test_spec_queue_pass.py` and `tests/test_spec_review_queue_pass.py` still reads text this round left verbatim, so no `pins:` node.
- **Clause coverage (D-1240) by hand, then by the loader:** each reworded entry has one `text` phrase equal to the whole new unit; every clause keeps all anchors and at least 6 of its first 8 content stems; every ban clause stands verbatim from its ban word to the end of its `;`/`—` clause (D-1238 point 1, D-1240).
- **COUNTS: 131 entries read / 21 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels** (self-audit, line by line against the baseline file and the live source; fixed by earlier passes: the L1, L19, L48, L3 findings above).

### Floor table (why the file stays over 50%)
Live rule count: 131 ledgered units, 38 of them ban-bearing. Measured on the start text by the fix round's clause split: 564 words sit in ban-clause tails the loader keeps verbatim, 482 in the heads of those clauses, 1865 in non-ban clauses holding a backticked token, number or path (each such anchor must survive in the same phrase), and 1664 in clauses with neither. This round cut every clause that is history, an incident, an example or a restated reason and was not itself a ban clause or an anchor carrier. What remains cannot shrink further without dropping a rule:

| group | words (start text) | why it cannot shrink |
|---|---|---|
| ban tails (L45, L46, L61, L62, L64, L99, L100, L104, L105, L107, L109, L126, L132, L133, L142 and the 12-Factor rows IV, XI) | ~564 | verbatim from the ban word to the end of its clause; a ban word inside a parenthesis or in `internal-only` / `read-only` / `shell-only` starts the span early, so the rest of the sentence is carried (L45, L100, L104 run to the sentence end) |
| pinned phrases (L100 `RUN-SCRATCH:` and `SCRATCH:` clauses, `pins_dir`, `pin_manifest`; L102 round recipe; L104 `--ids … --args …` window; L26/L30 firecrawl `proxy: "basic"` clauses; L107 `**Command:**` receipt line; the DECISION block fence) | ~700 | kept behavioural tests in `tests/test_review_loop_workflow.py`, `tests/test_review_command_text_defects.py`, `tests/test_firecrawl_proxy_basic.py`, `tests/test_research_tier_order.py`, `tests/test_gate_decision_blocks.py`, `tests/test_final_gate_stop_deferral.py` read them; the grammar is a fence or a parser's input |
| anchor carriers (L6, L9, L11-L13, L26, L33, L60, L63, L65, L91, L92, L137-L140, the 12-Factor rows) | ~1300 | backticked tokens, paths, numbers and dates must all sit in one phrase; each clause is already the anchors plus its operative words, so only an anchor-free tail can go (done where one existed) |
| single-clause units with a history parenthetical (L6, L33, L45, L126) | ~220 | the whole unit is one clause, so its date, id and mail-id anchors cannot be labelled narrative |
| short rules (L10, L16, L17, L22, L28, L31, L35, L40, L49-L58, L66-L67, L96, L98, L111-L118, L120-L123, L125, L128, L130-L131, L134-L141) | ~900 | clauses of 3-9 content stems need 100% of them under the 70% rule, and the phrase must be 6+ words |

Reaching 50% means moving the partition/`Workflow` paragraph (L99-L109, about 880 words) and the liveness-oracle bullet (L33-L40, about 330 words, repeated nearly word for word in `/fabrik-plan-review`) into one ledgered fragment, which D-1240's per-clause rule does not allow inside this unit. A floor D-row is owed.

## Failure sets (reader-test run, `capped_run.sh`)
Start (this branch, before any edit): gate 1 `tests/test_command_rules.py` 1 failed / 56 passed; gate 2 14 failed / 100 passed; gate 3 1 failed / 358 passed; gate 4 1 failed / 706 passed; gate 5 1 failed / 413 passed / 2 skipped; gate 6 205 passed; gate 7 464 passed; gate 8 2 failed / 300 passed. End (after the cut): gate 1 1 failed / 56 passed, with the `LEDGER fabrik-spec-review.yaml: 131 entries` line; gate 2 14 failed / 100 passed (the same 14 node ids); gate 3 1 failed / 358 passed (`test_quiet_pass_is_set_identical_to_the_retired_regex_over_the_committed_receipts`, no git history in the clone); gate 4 1 failed / 706 passed (`test_check_exit_order_loss_then_ceiling_then_drift`); gate 5 1 failed / 413 passed / 2 skipped (`test_the_two_live_box_tests_pass_a_merge_check_on_a_drifted_box`); gate 6 205 passed; gate 7 464 passed; gate 8 2 failed / 300 passed (the two `test_vision_reads_work_stores` `--check` tests). The failure set is identical to the start set: 0 new, 0 gone. Every one is red at the start too, because `--check` exits 4 on other commands' and `_shared` ledgers outside this ticket, or because the clone has no git history or box services. `--check` prints 0 LOSS lines for `fabrik-spec-review.yaml`.

## LEFT FOR THE HUB
- CHANGELOG.md, INDEX.md rows for the new `commands/_rules/` files, the `commands/_size_ceiling.json` ratchet and the render at merge.
- A floor D-row for `/fabrik-spec-review` (131 live rules, ban tails and pinned phrases above), or the shared-fragment move named in the floor table.
- The author-blind audit pair (Sonnet + Haiku) over the 21 reworded entries; every label here is an author label.

## Fix round 2 (hub audit)

Findings from the Sonnet and Haiku hub audits, checked against the baseline text (the two reports overlap; a pair counts as one):

| finding | verdict | fix |
|---|---|---|
| r-L36 "grep it, line anchors drift" dropped (both) | confirmed | restored: "the frontmatter key — grep it, line anchors drift" |
| r-L81 / L81 Litmus parenthetical dropped, vanished label wrong (both) | confirmed | restored "(Litmus: could this be open-sourced today without leaking credentials?)" in source and `text` |
| r-L42 "(the current best-practice / leanest / low-maintenance research)" dropped | confirmed | restored in source and `text` |
| r-L37 "instructing it to is instructing it to fail" labelled narrative, id `01M14V7KH4` dropped | confirmed | restored the clause and the `01M14V7KH4` id; only the "after a grounder substituted WebFetch and said so" tail stays `narrative` (clause 2) |
| r-L44 "the review is the second chance, not a rubber stamp" labelled narrative | confirmed | restored; the `clauses:` label is removed |
| r-L93 "a permanent provider death needs a SWAP no retry loop can make" labelled narrative | confirmed | restored; clause 3 is now carried, and only clause 2 ("those four heal a TRANSIENT fault") stays `narrative` |
| r-L105 "(a repo or checkout the sync has not reached)" dropped | confirmed | restored in source and `text` |
| r-L2 "before it is trusted" dropped (Haiku, flagged qualifier only) | confirmed | restored "before it is trusted"; "the adversarial" stays cut (an adjective, no instruction) |
| L135 `DECISION NEEDED (ground: gate)` block has no entry (both) | refuted as a loss | the block is verbatim in the source fence; it is grammar kept in place, not a vanished unit, and the loader prints 0 LOSS for this ledger |

- **Own-text words:** baseline 4839 → re-ledger 4461 → now about 4540 (+~80: the eight restored phrases). Estimated, not measured: this run cannot execute the word-count one-liner.
- **Floor table:** the table above stands. The 50% target is retired (D-1257).
- **Gates:** `python3 commands/assemble_commands.py --check` prints no LOSS line for `fabrik-spec-review.yaml` (only the DIFFERS drift line and the REPORT line). `tests/test_command_rules.py` has one failure, the full-corpus no-loss test over other commands' and `_shared` ledgers. The other reader-test gates were not re-run after the edits.
- **Fresh pass:** NOT RUN. This run cannot dispatch a subagent, so the check below is the author's line-by-line read of the eight fixes, not a fresh reader. The hub's author-blind audit pair covers it.
- **COUNTS (author re-read, not a fresh pass; 0 fresh passes ran):** entries read 131 / reworded 21 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0
