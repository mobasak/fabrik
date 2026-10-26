# T03c receipt — Shared fragment term-coverage, the rewrite

Start commit (the unit's baseline commit): `61d1f4b99c6a8188a281f86799268fe54ee1b5d1`; this ticket builds on the T03a/T03b commits on the same branch.

## Own text
`commands/_fragments/term-coverage.md` (`wc -w`): 6109 -> 5651 words (92.5%). **The 50% target is not met.** Floor below.

## The floor (for the hub's floor D-row)
- Live rule count: 92 ledger entries over 280 kept baseline clauses (97 baseline units; 22 clauses labelled narrative or duplicate and removed).
- D-1240 mechanical minimum: every kept clause cut to its anchors plus 6 of its first 8 content stems, ban clauses kept verbatim from the ban word to the end of their `;`/`—` clause or sentence: 4173 words (68% of the baseline). The text sits at 5651 because the clauses that carry the rule's action past their first 8 content words were kept whole (cutting to the minimum would keep the subject and drop the action, e.g. `a fix landing in both a function and its CLI half;`), and because 53 of 92 entries are ban clauses whose tails are verbatim.
- Even the mechanical minimum is 68%, not 50%: 280 clauses x the 6-word phrase minimum, 53 ban entries, clause anchors that span the clause (backticked tokens, D-ids, paths), and 15 reader tests outside this ticket's Touches that pin phrases verbatim (`tests/enforcement/test_review_exit_contract.py`, `tests/test_review_loop_workflow.py`, `tests/test_review_receipt.py`, plus the looping tests kept in Touches). 50% is reachable only by deleting rules.
- Recommended floor: 68% of the baseline by the D-1240 mechanical minimum; 92.5% at the readable text this ticket ships.

## Ledger
92 entries (one per rule unit; a unit whose clauses sit in two rewritten units has two). By class: ban 53, prose 33, grammar 5, behavioural 1 (the canonical row template, which the review-receipt and exit-contract tests parse with the graders). Reworded entries (current unit differs from the baseline unit): 23 of 92. Classes are `# class:` comments and uncovered clauses `# clauses:` comments (the loader on this base has no such keys). Entries were drafted by a coverage tool that finds, per baseline clause, the smallest rewritten phrase holding every anchor and 70% of the first 8 content stems (the ban tail verbatim), and then read and labelled by hand; no phrase was weakened to pass it.

| reworded entry | class | carriers | clauses labelled |
|---|---|---|---|
| tc-u02-loop-runs-until | prose | 2 carrier phrases | - |
| tc-u11-prior-surface-comparable | grammar | 3 carrier phrases | - |
| tc-u12-let-degrade-silently | prose | 1 carrier phrases | {2: narrative} |
| tc-u14-persist-exception-below | ban | 3 carrier phrases | - |
| tc-u16-form-makes-later | ban | 8 carrier phrases | {2: duplicate-of U14c1} |
| tc-u21-coverage-checklist-row | prose | 1 carrier phrases | - |
| tc-u22-row-starts-unchecked | prose | 1 carrier phrases | - |
| tc-u24-round-1-full | ban | 4 carrier phrases | - |
| tc-u26-commands-surface-diff | prose | 4 carrier phrases | {3: narrative} |
| tc-u27-surface-hash-git | grammar | 1 carrier phrases | - |
| tc-u35-cobra-d-253 | ban | 24 carrier phrases | {2: narrative} |
| tc-u36-4-grader-proven | ban | 15 carrier phrases | {10: narrative} |
| tc-u50-scope-already-adjudicated | ban | 2 carrier phrases | {3: duplicate-of U49c1} |
| tc-u51-row-adjudicated | prose | 2 carrier phrases | - |
| tc-u52-unchecked-rows | prose | 1 carrier phrases | - |
| tc-u59-mechanical-gates-green | prose | 2 carrier phrases | {2: narrative} |
| tc-u70-slice-handed-capped | ban | 2 carrier phrases | - |
| tc-u80-stop-scope-outstanding | ban | 1 carrier phrases | {2: narrative} |
| tc-u82-stop-suspends-new | ban | 6 carrier phrases | {3: narrative} |
| tc-u87-cobra-d-253 | ban | 1 carrier phrases | {2: narrative, 3: narrative} |
| tc-u88-own-fix-evidenced | ban | 1 carrier phrases | {1: narrative, 2: narrative} |
| tc-u89-d-278-supersedes | prose | 1 carrier phrases | {2: narrative} |
| tc-u90-stall-breaker-cannot | prose | 1 carrier phrases | {2: narrative} |

## Pins retired (`pins:` on the entries that now carry them)
The 19 test node ids of the T03a/T03b receipts, carried over unchanged. No test is edited in this ticket.

## Vanished labels (author labels — audit owed)
- L2: {'rule': ['tc-u02-loop-runs-until']}
- L5: {'duplicate-of': 'tc-u02-loop-runs-until'}
- L11: {'rule': ['tc-u11-prior-surface-comparable']}
- L12: {'rule': ['tc-u12-let-degrade-silently']}
- L14: {'rule': ['tc-u14-persist-exception-below']}
- L16: {'rule': ['tc-u16-form-makes-later']}
- L19: {'duplicate-of': 'tc-u14-persist-exception-below'}
- L21: {'rule': ['tc-u21-coverage-checklist-row']}
- L22: {'rule': ['tc-u22-row-starts-unchecked']}
- L24: {'rule': ['tc-u24-round-1-full']}
- L26: {'rule': ['tc-u26-commands-surface-diff']}
- L27: {'rule': ['tc-u27-surface-hash-git']}
- L35: {'rule': ['tc-u35-cobra-d-253']}
- L36: {'rule': ['tc-u36-4-grader-proven']}
- L50: {'rule': ['tc-u50-scope-already-adjudicated']}
- L51: {'rule': ['tc-u51-row-adjudicated']}
- L52: {'rule': ['tc-u52-unchecked-rows']}
- L59: {'rule': ['tc-u59-mechanical-gates-green']}
- L64: narrative
- L66: narrative
- L70: {'rule': ['tc-u70-pass-overrun-budget', 'tc-u70-slice-handed-capped']}
- L80: {'rule': ['tc-u80-stop-scope-outstanding']}
- L81: narrative
- L82: {'rule': ['tc-u82-stop-suspends-new']}
- L87: {'rule': ['tc-u87-cobra-d-253']}
- L88: {'rule': ['tc-u88-own-fix-evidenced']}
- L89: {'rule': ['tc-u89-d-278-supersedes']}
- L90: {'rule': ['tc-u90-stall-breaker-cannot']}

## Failure sets (reader-test run, spine § Global Constraints; 40 test files, the 41 of the start run minus the deleted `test_term_coverage_round_zero.py`)
- Start commit: 52 failed (`tests/test_fabrik_deck.py`, `test_generate_capability_index.py`, `test_quota_dashboard.py`, `test_check_command_corpus.py`, `test_conftest_isolation.py`, `sysadmin/test_rules_render_versions.py`, 1 each in `test_agent_definitions.py`, `test_assemble_dispatch_step.py`, `test_command_run.py`, `test_review_queue_pass.py`): the clone lacks box services.
- End: the same 52, plus 2 `test_assemble_dispatch_step.py` orphan/stray tests that failed only while two test runs shared `/root/.claude` and pass alone (rerun: 4 passed). The set did not grow.
- `tests/test_command_rules.py`: 32 passed, LEDGER line `92 entries`, zero LOSS. `assemble_commands.py --check`: exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING`.

## Self-audit
One fresh subagent, given only the baseline file, the rewrite and the ledger, ran the four checks. Pass 1 found: 1 LOST (a false `duplicate-of` on the Pass-1-row clause of the draft path), 4 WEAKER (the `or call path` / round-trip tail, `from the first draft`, `like any matcher above`, one unlabelled reason tail), 1 WRONG-VANISHED-LABEL (L19, whose examples were labelled a duplicate). Fixes: the Pass-1 parenthetical, `or call path` and the round-trip tail, `from the first draft` and `like any matcher above` were restored; the L19 form enumeration now sits in the clause it elaborates, so L19 is a true duplicate. Reason tails kept inside covered clauses (`fixes are the least-reviewed code...`, `since there is no diff to hash`, `because a dead function-level mutant...`) are labelled in this receipt as reasons dropped from covered clauses, no rule among them. No second blind pass was run.
COUNTS: 92 entries read / 23 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels (pass 1 counts before fixes: 92 / 20 / 4 / 1 / 0 / 1; the closing counts are the author's re-check of each finding, not a second blind pass)

## LEFT FOR THE HUB
- The author-blind Sonnet + Haiku audit of every reworded entry (old against new), and the review wave.
- The floor D-row (68% mechanical, 92.5% readable) and the `commands/_size_ceiling.json` ratchet (not touched here).
- `CHANGELOG.md`, `INDEX.md` rows (new `commands/_rules/_shared/term-coverage.*`, the deleted `tests/test_term_coverage_round_zero.py`) and the D-rows.
- Converting the `# class:` / `# clauses:` comments to keys when the canonical loader lands.

## Floor table: every kept clause still over its minimum by 4 or more words
(`*` = the clause was reworded, so "kept" is the length of its carrier phrase.)

| baseline clause | baseline words | kept in text | D-1240 minimum | why it cannot shrink |
|---|---|---|---|---|
| U3c1 | 15 | 15 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U4c1 | 17 | 17 | 12 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U7c1 | 10 | 10 | 6 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U9c1 | 19 | 19 | 13 | ban tail verbatim (1 words from the ban word) |
| U10c1 | 12 | 12 | 8 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U13c1 | 18 | 18 | 6 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U14c1 | 45 | 44* | 40 | ban tail verbatim (6 words from the ban word) |
| U14c3 | 50 | 50 | 46 | 5 anchors span the clause |
| U16c4 | 14 | 14 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U16c7 | 14 | 14 | 7 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U16c9 | 11 | 11 | 6 | a test names it: test_review_receipt.py |
| U17c1 | 43 | 43 | 35 | ban tail verbatim (9 words from the ban word) |
| U20c1 | 10 | 10 | 6 | ban tail verbatim (6 words from the ban word) |
| U20c3 | 14 | 14 | 8 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U21c1 | 42 | 42 | 33 | 4 anchors span the clause |
| U23c2 | 16 | 16 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U23c3 | 15 | 15 | 10 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U24c1 | 24 | 24 | 20 | ban tail verbatim (20 words from the ban word) |
| U25c1 | 15 | 15 | 7 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U27c1 | 21 | 12* | 6 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U28c2 | 13 | 13 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U28c3 | 27 | 27 | 22 | 4 anchors span the clause |
| U28c4 | 20 | 20 | 15 | ban tail verbatim (9 words from the ban word) |
| U28c5 | 21 | 21 | 12 | ban tail verbatim (3 words from the ban word) |
| U28c6 | 31 | 31 | 26 | ban tail verbatim (7 words from the ban word) |
| U29c3 | 11 | 11 | 7 | a test names it: test_bounded_hop_new_output.py, test_review_loop_workflow.py |
| U29c5 | 34 | 34 | 29 | ban tail verbatim (19 words from the ban word) |
| U30c1 | 22 | 22 | 7 | a test names it: enforcement/test_review_exit_contract.py |
| U30c2 | 91 | 91 | 82 | ban tail verbatim (40 words from the ban word) |
| U30c3 | 42 | 42 | 34 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U30c4 | 21 | 21 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U30c5 | 31 | 31 | 15 | 3 anchors span the clause |
| U31c4 | 22 | 22 | 10 | a test names it: test_review_loop_workflow.py |
| U31c5 | 155 | 155 | 150 | ban tail verbatim (90 words from the ban word); a test names it: enforcement/test_review_exit_contract.py, test_review_loop_workflow.py |
| U31c11 | 25 | 25 | 20 | ban tail verbatim (19 words from the ban word) |
| U31c12 | 39 | 39 | 25 | a test names it: test_plan_review_queue_pass.py, test_plan_review_recurring_rules.py |
| U31c13 | 58 | 58 | 53 | ban tail verbatim (5 words from the ban word); a test names it: test_plan_review_recurring_rules.py, test_review_loop_workflow.py |
| U31c18 | 46 | 46 | 34 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U31c19 | 37 | 37 | 11 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U31c22 | 24 | 24 | 12 | ban tail verbatim (10 words from the ban word) |
| U32c1 | 46 | 46 | 42 | ban tail verbatim (31 words from the ban word); a test names it: test_plan_review_queue_pass.py |
| U33c1 | 17 | 17 | 8 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U33c2 | 124 | 124 | 110 | ban tail verbatim (29 words from the ban word); a test names it: test_plan_review_queue_pass.py, test_review_scoped_queue_pass.py |
| U34c2 | 14 | 14 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U35c4 | 23 | 23 | 6 | a test names it: test_review_command_text_defects.py |
| U35c6 | 60 | 60 | 32 | a test names it: test_review_command_text_defects.py |
| U35c9 | 16 | 16 | 12 | ban tail verbatim (10 words from the ban word) |
| U35c10 | 17 | 17 | 7 | a test names it: enforcement/test_review_exit_contract.py |
| U35c11 | 84 | 84 | 20 | a test names it: enforcement/test_review_exit_contract.py, test_review_queue_pass.py |
| U35c14 | 21 | 21 | 10 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U35c15 | 48 | 48 | 41 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U35c21 | 23 | 23 | 11 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U35c22 | 57 | 57 | 15 | a test names it: enforcement/test_review_exit_contract.py |
| U35c23 | 14 | 14 | 8 | a test names it: enforcement/test_review_exit_contract.py |
| U35c24 | 56 | 56 | 51 | ban tail verbatim (44 words from the ban word); a test names it: enforcement/test_review_exit_contract.py |
| U35c25 | 18 | 18 | 13 | ban tail verbatim (5 words from the ban word); a test names it: enforcement/test_review_exit_contract.py |
| U35c26 | 16 | 16 | 11 | a test names it: enforcement/test_review_exit_contract.py |
| U36c2 | 78 | 78 | 59 | a test names it: test_review_loop_workflow.py |
| U36c3 | 22 | 22 | 18 | ban tail verbatim (18 words from the ban word); a test names it: test_review_loop_workflow.py |
| U36c7 | 47 | 47 | 43 | ban tail verbatim (43 words from the ban word); a test names it: test_review_queue_pass.py |
| U36c8 | 15 | 15 | 11 | ban tail verbatim (6 words from the ban word) |
| U36c9 | 18 | 18 | 12 | ban tail verbatim (7 words from the ban word); a test names it: test_review_scoped_queue_pass.py |
| U36c11 | 35 | 12* | 7 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U36c12 | 29 | 29 | 22 | a test names it: enforcement/test_review_exit_contract.py |
| U36c14 | 33 | 33 | 29 | ban tail verbatim (11 words from the ban word) |
| U36c15 | 31 | 31 | 24 | ban tail verbatim (19 words from the ban word) |
| U36c16 | 17 | 17 | 10 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U37c1 | 13 | 13 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U37c2 | 59 | 59 | 45 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U38c1 | 17 | 17 | 8 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U40c1 | 18 | 18 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U42c3 | 13 | 13 | 7 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U43c3 | 33 | 33 | 27 | ban tail verbatim (27 words from the ban word) |
| U43c6 | 13 | 13 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U45c1 | 21 | 21 | 16 | 3 anchors span the clause |
| U45c2 | 25 | 25 | 21 | ban tail verbatim (21 words from the ban word) |
| U45c3 | 14 | 14 | 6 | 3 anchors span the clause |
| U46c1 | 42 | 42 | 35 | a test names it: enforcement/test_review_exit_contract.py |
| U46c2 | 17 | 17 | 13 | a test names it: enforcement/test_review_exit_contract.py |
| U47c1 | 10 | 10 | 6 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U47c3 | 13 | 13 | 8 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U47c4 | 37 | 37 | 33 | a test names it: enforcement/test_review_exit_contract.py, test_review_receipt.py |
| U47c6 | 25 | 25 | 8 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U48c1 | 19 | 19 | 14 | 4 anchors span the clause |
| U49c1 | 25 | 25 | 19 | ban tail verbatim (2 words from the ban word) |
| U50c1 | 19 | 19 | 11 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U53c1 | 10 | 10 | 6 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U54c1 | 19 | 19 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U56c2 | 32 | 32 | 27 | ban tail verbatim (19 words from the ban word) |
| U57c1 | 12 | 12 | 7 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U58c1 | 16 | 16 | 11 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U60c1 | 19 | 19 | 14 | ban tail verbatim (7 words from the ban word) |
| U61c4 | 15 | 15 | 10 | ban tail verbatim (2 words from the ban word) |
| U62c2 | 29 | 29 | 22 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U62c4 | 19 | 19 | 11 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U63c2 | 36 | 36 | 32 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U67c2 | 23 | 23 | 17 | ban tail verbatim (15 words from the ban word) |
| U67c3 | 30 | 30 | 23 | ban tail verbatim (7 words from the ban word) |
| U68c1 | 41 | 41 | 33 | ban tail verbatim (3 words from the ban word) |
| U69c2 | 22 | 22 | 6 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U70c1 | 30 | 30 | 10 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U70c3 | 27 | 27* | 10 | 4 anchors span the clause |
| U72c1 | 12 | 12 | 6 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U72c2 | 12 | 12 | 8 | ban tail verbatim (8 words from the ban word) |
| U72c3 | 12 | 12 | 8 | a test names it: enforcement/test_review_exit_contract.py, test_command_run.py |
| U72c5 | 20 | 20 | 14 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U74c1 | 15 | 15 | 8 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U76c1 | 11 | 11 | 6 | a test names it: enforcement/test_review_exit_contract.py |
| U76c2 | 13 | 13 | 8 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U77c2 | 37 | 37 | 33 | a test names it: test_check_command_corpus.py |
| U78c1 | 24 | 24 | 13 | 3 anchors span the clause |
| U78c2 | 24 | 24 | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U79c1 | 45 | 45 | 36 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U79c2 | 35 | 35 | 31 | ban tail verbatim (22 words from the ban word); a test names it: enforcement/test_review_exit_contract.py, test_command_run.py |
| U80c1 | 22 | 22 | 10 | ban tail verbatim (5 words from the ban word) |
| U82c1 | 18 | 18 | 13 | ban tail verbatim (11 words from the ban word) |
| U82c2 | 19 | 19* | 9 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U82c5 | 13 | 13 | 8 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U82c6 | 10 | 10 | 6 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U85c1 | 14 | 14 | 9 | 3 anchors span the clause |
| U85c2 | 24 | 24 | 15 | ban tail verbatim (8 words from the ban word) |
| U86c3 | 16 | 16 | 8 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U88c3 | 27 | 27* | 23 | ban tail verbatim (23 words from the ban word) |
| U93c2 | 26 | 26 | 17 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U94c2 | 10 | 10 | 6 | predicate sits past the first 8 content words: the minimum would keep the subject and drop the action |
| U97c1 | 21 | 21 | 12 | 3 anchors span the clause |
