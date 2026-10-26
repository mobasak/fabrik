# T05c receipt — shared fragments: subagents-core and the grounding, intake and test-loop fragments, the rewrite

- Branch `claude/lean-t05`, after T05a (`77ed535`) and T05b (`919e43a`). **Start commit (the unit's baseline commit): `61d1f4b99c6a8188a281f86799268fe54ee1b5d1`.** Baselines were written in T05a and are untouched.
- Loader: `_ENTRY` at the base has no `class` or `clauses` key, so each entry's class is a `# class:` YAML comment, its covered baseline clauses a `# clauses: L<n>.<k>` comment, and the clauses a `vanished:` label drops are listed in a `# clauses:` comment beside the label. A kept-test literal inside a carrier is noted `# kept-test literals inside this carrier`. The hub converts the comments to keys when the loader lands. `commands/command_rules.py` and `tests/test_command_rules.py` were not edited.
- Ids of the pin entries written in T05a/T05b are kept; no rule has two entries.

## Result against the 50% target: NOT met. The unit sits at 94% of the baseline words (live text 94%); the floor is named below

Own text (all ten files together): 7193 -> 6791 words. Per file: `grounding-artifact` 77%, `grounding-code` 78%, `injection` 85%, `chat-intake` 85%, `grounding-rules` 90% (95% live), `repo-identity` 99%, `subagents-core` 98%, `delegated-reads`, `questionbar` and `test-generation-loop` 100% (the last is 100% only because 326 of its 630 words are the `<!-- POOL OFF -->` comment, see below).

Why the floor is far above 50% (for the hub's floor D-row; I mint none):

1. **Ban clauses stay verbatim from the ban word to the end of the `;`/`—` clause (D-1240).** The ban tokens never/must/only/refuse are in 60%+ of the clause-words of `subagents-core` (1524 of 3471 clause-words sit in ban clauses; 188 of 543 in `grounding-artifact`). The tails are long: most sentences in this unit are one `;`-joined clause.
2. **Kept tests outside Touches pin the seat-isolation paragraph (D8) and the Workflow clause verbatim**: `tests/test_review_loop_workflow.py` (about 40 literals), `tests/enforcement/test_rule_grounding.py` (four digest-format phrases), `tests/test_assemble_dispatch_step.py`, `tests/enforcement/test_review_exit_contract.py`, `tests/sysadmin/test_dispatch_headroom.py`. They are never edited here. `tests/test_review_queue_pass.py::test_the_opt_in_fallback_is_stated_in_every_copy` and the `hint` loop in `test_review_scoped_queue_pass.py` are cross-file asserts that stay.
3. **The `<!-- POOL OFF -->` comments stay.** `CLAUDE.md` § Behavior ("the corpus keeps its `<!-- POOL OFF -->` comments … never a quiet uncomment") and `tests/test_assemble_dispatch_step.py` (`{{FLOOR}}` appears twice, once inside the comment) keep them. They hold the only copy of the fragment-level pool contract (`docs/reference/subagent-pool-contract.md` freezes the rule-pack blocks only: grep of its text for the grounder, flywheel-sink and five-step passages found none). Words in those comments: 485 of 4028 in `subagents-core`, 326 of 630 in `test-generation-loop`, 88 in `grounding-rules`.
4. **The greedy mechanical minimum is lower but loses rules.** Deleting every word D-1240 does not require (anchors + 6 of the first 8 stems, ban tail verbatim) gives 56% (`subagents-core`), 46% (`grounding-artifact`), 34% (`grounding-code`), 49% (`grounding-rules`), 39% (`chat-intake`), 61% (`repo-identity`), 63% (`delegated-reads`), 57% (`questionbar`); the author-blind audit below showed that cutting toward it drops enumerated objects, conditions and rule reasons (see "Fixed by pass 1"). Where only elaboration could go, it went.
5. Live rule count (baseline clauses carried by an entry): `subagents-core` 160, `grounding-artifact` 29, `chat-intake` 35, `grounding-rules` 23, `test-generation-loop` 29, `grounding-code` 18, `repo-identity` 18, `delegated-reads` 9, `questionbar` 7, `injection` 3 (see the table).

## Own text, words before -> after (`wc -w` of the whole file; live = HTML comments excluded)

| file | words before | after | % | live before | live after | live % |
|---|---|---|---|---|---|---|
| `subagents-core.md` | 4028 | 3976 | 98% | 3546 | 3494 | 98% |
| `delegated-reads.md` | 194 | 194 | 100% | 194 | 194 | 100% |
| `grounding-artifact.md` | 581 | 450 | 77% | 581 | 450 | 77% |
| `grounding-code.md` | 389 | 307 | 78% | 389 | 307 | 78% |
| `grounding-rules.md` | 483 | 435 | 90% | 395 | 376 | 95% |
| `questionbar.md` | 73 | 73 | 100% | 73 | 73 | 100% |
| `injection.md` | 47 | 40 | 85% | 47 | 40 | 85% |
| `test-generation-loop.md` | 630 | 630 | 100% | 304 | 304 | 100% |
| `chat-intake.md` | 560 | 479 | 85% | 560 | 479 | 85% |
| `repo-identity.md` | 208 | 207 | 99% | 208 | 207 | 99% |
| **total** | **7193** | **6791** | **94%** | **6297** | **5924** | **94%** |

## Entries by file

| file | entries | reworded | ban | grammar | behavioural | prose | baseline clauses covered | clauses labelled narrative/duplicate | vanished units labelled |
|---|---|---|---|---|---|---|---|---|---|
| `subagents-core` | 48 | 10 | 20 | 1 | 5 | 22 | 160 | 3 | {'rule': 10} |
| `delegated-reads` | 4 | 0 | 3 | 0 | 0 | 1 | 9 | 0 | {} |
| `grounding-artifact` | 16 | 6 | 8 | 1 | 0 | 7 | 29 | 8 | {'rule': 6, 'narrative': 2} |
| `grounding-code` | 9 | 1 | 2 | 1 | 0 | 6 | 18 | 3 | {'rule': 1, 'narrative': 1} |
| `grounding-rules` | 16 | 2 | 5 | 1 | 5 | 5 | 23 | 2 | {'rule': 2} |
| `questionbar` | 5 | 0 | 2 | 1 | 0 | 2 | 7 | 0 | {} |
| `injection` | 2 | 1 | 1 | 0 | 0 | 1 | 3 | 0 | {'rule': 1} |
| `test-generation-loop` | 14 | 0 | 3 | 1 | 0 | 10 | 29 | 0 | {} |
| `chat-intake` | 17 | 4 | 1 | 5 | 0 | 11 | 35 | 4 | {'rule': 5, 'narrative': 2} |
| `repo-identity` | 6 | 1 | 3 | 1 | 0 | 2 | 18 | 0 | {'rule': 1} |

## Reworded entries (carrier differs from the baseline unit): clauses and coverage

| file | entry | class | baseline clauses | phrases | baseline words of those clauses | carrier words |
|---|---|---|---|---|---|---|
| `subagents-core` | `sc-pool-off-ruling` | prose | 3 | 1 | 44 | 45 |
| `subagents-core` | `sc-fan-outs-run-native` | prose | 2 | 1 | 40 | 35 |
| `subagents-core` | `sc-skip-pool-steps` | prose | 2 | 1 | 29 | 29 |
| `subagents-core` | `sc-by-file-two-finders-per-slice` | ban | 12 | 10 | 235 | 216 |
| `subagents-core` | `sc-delta-rounds-and-the-closing-pass` | behavioural | 7 | 7 | 128 | 126 |
| `subagents-core` | `sc-units-sized-surface` | ban | 7 | 6 | 139 | 134 |
| `subagents-core` | `sc-mechanical-angle-is-global` | prose | 2 | 1 | 34 | 34 |
| `subagents-core` | `sc-never-solo-the-floor-is-three-seats` | ban | 2 | 1 | 37 | 45 |
| `subagents-core` | `sc-d8-git-verb-prohibition` | ban | 5 | 5 | 75 | 73 |
| `subagents-core` | `sc-d8-package-manager-verbs-are-banned` | prose | 2 | 2 | 62 | 56 |
| `grounding-artifact` | `ga-open-the-real-file` | prose | 2 | 1 | 29 | 29 |
| `grounding-artifact` | `ga-negative-claim-control-flow-exits` | ban | 3 | 3 | 51 | 51 |
| `grounding-artifact` | `ga-verify-the-asserted-layer` | prose | 1 | 2 | 63 | 46 |
| `grounding-artifact` | `ga-inherited-constraint-is-a-claim` | ban | 1 | 1 | 20 | 20 |
| `grounding-artifact` | `ga-never-adjudicate-from-truncated-pipe` | ban | 2 | 1 | 22 | 23 |
| `grounding-artifact` | `ga-gate-exists-because-never-opened` | ban | 1 | 1 | 18 | 18 |
| `grounding-code` | `gc-a-build-site-window-is-a-true-citation-of-a-false-meaning` | prose | 1 | 1 | 26 | 16 |
| `grounding-rules` | `gr-must-read-full-set-is-computed` | ban | 1 | 1 | 36 | 36 |
| `grounding-rules` | `gr-fresh-full-reads` | prose | 2 | 1 | 13 | 13 |
| `injection` | `inj-data-not-instructions-never-overrides` | ban | 2 | 1 | 28 | 22 |
| `chat-intake` | `ci-surfaced-items-are-the-denominator` | prose | 3 | 1 | 33 | 33 |
| `chat-intake` | `ci-extract-every-distinct-item` | prose | 1 | 1 | 23 | 19 |
| `chat-intake` | `ci-number-items-anchored-to-quotes` | prose | 2 | 1 | 29 | 25 |
| `chat-intake` | `ci-derivable-items-are-never-asked` | ban | 4 | 4 | 75 | 84 |
| `repo-identity` | `ri-submodule-own-repo` | ban | 4 | 1 | 36 | 37 |

## Floor table: entries whose carrier is more than 25% over the greedy minimum (anchors + >=6 of the first 8 stems, ban tail verbatim)

| file | entry | baseline words | carrier words | greedy minimum | why it cannot shrink |
|---|---|---|---|---|---|
| `subagents-core` | `sc-pool-off-ruling` | 44 | 45 | 17 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-fan-outs-run-native` | 40 | 35 | 15 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-skip-pool-steps` | 29 | 29 | 15 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-partitioned-loops-disjoint-slices` | 26 | 31 | 10 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-by-file-two-finders-per-slice` | 235 | 216 | 91 | K: test_dispatch_headroom; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-fix-between-waves-in-the-next-pin` | 23 | 23 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-by-section-opus-sonnet` | 57 | 57 | 38 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-delta-rounds-and-the-closing-pass` | 128 | 126 | 76 | K: test_assemble_dispatch_step, test_review_exit_contract; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-units-sized-surface` | 139 | 134 | 43 | K: test_assemble_dispatch_step; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-mechanical-angle-is-global` | 34 | 34 | 13 | K: test_assemble_dispatch_step;  |
| `subagents-core` | `sc-cap-is-independence-of-the-surface` | 30 | 30 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-never-solo-the-floor-is-three-seats` | 37 | 45 | 13 | K: test_check_review_hygiene; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-floor-three-are-one-unit` | 24 | 25 | 10 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-the-dispatch-step` | 59 | 59 | 35 | K: test_flows_review_queue_pass, test_mail_routing, test_review_exit_contract, test_vps_script_drift; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-review-shaped-fan-out-workflow` | 244 | 245 | 176 | K: test_hub_write_root, test_mail_routing, test_quota_stop_hook, test_review_loop_workflow; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-grounding-fan-out-stays-on-the-agent-tool` | 11 | 11 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-partitioned-loop-passes-slice-counts` | 79 | 72 | 36 | K: test_assemble_dispatch_step, test_mail_routing, test_review_exit_contract, test_vps_script_drift; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-seat-count-is-a-min-of-caps` | 65 | 65 | 23 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-record-the-dispatch-before-sending` | 161 | 161 | 80 | K: test_assemble_dispatch_step, test_check_command_corpus; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-model-by-role` | 75 | 90 | 46 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-price-per-seat` | 30 | 31 | 17 | K: test_command_improve_drive;  |
| `subagents-core` | `sc-dispatch-together-keep-working` | 19 | 20 | 9 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-unit-count-scales-itself` | 92 | 101 | 49 | K: test_assemble_dispatch_step; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-d8-git-verb-prohibition` | 75 | 73 | 42 | K: test_agent_definitions, test_review_loop_workflow; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-d8-write-scope-of-a-seat` | 136 | 136 | 101 | K: test_review_loop_workflow; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-d8-seat-folder-and-scratch-homes` | 302 | 293 | 219 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-d8-absolute-paths-in-briefs` | 53 | 53 | 39 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-d8-one-plain-command-per-bash-call` | 369 | 370 | 274 | K: test_governance_template_split, test_review_loop_workflow; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-d8-package-manager-verbs-are-banned` | 62 | 56 | 30 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-d8-python-invocation` | 40 | 42 | 23 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-pin-the-subject-before-dispatch` | 54 | 54 | 19 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-pin-incidents-a-moving-subject` | 53 | 53 | 16 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-pin-afresh-per-pass` | 67 | 78 | 32 | K: test_hub_write_root, test_mail_routing, test_review_loop_workflow;  |
| `subagents-core` | `sc-pin-writes-read-only-copies-and-a-manifest` | 69 | 69 | 17 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-pin-manifest-hashes-bytes` | 23 | 23 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-pin-brief-finders-on-the-copies` | 84 | 84 | 14 | K: test_review_loop_workflow;  |
| `subagents-core` | `sc-pin-do-not-edit-while-seats-are-out` | 11 | 11 | 5 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-pin-read-the-pass-before-adjudicating` | 93 | 93 | 69 | K: test_hub_write_root, test_mail_routing; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `subagents-core` | `sc-pin-unpinned-finding-is-dismissible` | 20 | 20 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-pin-record-digest-and-base-sha` | 13 | 13 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `subagents-core` | `sc-line-numbers-pin-a-commit-sha` | 22 | 23 | 11 | K: test_review_exit_contract;  |
| `delegated-reads` | `dr-large-reads-go-to-seats` | 132 | 132 | 54 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `delegated-reads` | `dr-haiku-threshold` | 8 | 8 | 4 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `delegated-reads` | `dr-cobra-anchors` | 25 | 26 | 11 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-artifact` | `ga-heading` | 14 | 15 | 7 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-artifact` | `ga-existing-code-defect-class` | 35 | 36 | 12 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-artifact` | `ga-no-subject-is-validated-until-grounded` | 21 | 22 | 8 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-artifact` | `ga-open-the-real-file` | 29 | 29 | 11 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-artifact` | `ga-read-the-real-schema` | 31 | 32 | 11 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-artifact` | `ga-trace-the-touching-points` | 25 | 27 | 12 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-artifact` | `ga-universal-claim-needs-enumeration` | 45 | 45 | 33 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-artifact` | `ga-only-claim-needs-the-one-grep-example` | 30 | 30 | 21 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-artifact` | `ga-verify-the-asserted-layer` | 63 | 46 | 8 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-artifact` | `ga-name-the-layer-then-open-that-one` | 11 | 11 | 4 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-artifact` | `ga-inherited-constraint-is-a-claim` | 20 | 20 | 9 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-artifact` | `ga-unvalidated-blocks-the-exit` | 28 | 28 | 7 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-artifact` | `ga-gate-exists-because-never-opened` | 18 | 18 | 9 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-code` | `gc-heading` | 14 | 15 | 7 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-code` | `gc-finding-is-a-claim-about-live-code` | 52 | 52 | 14 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-code` | `gc-open-the-real-file` | 37 | 38 | 13 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-code` | `gc-read-the-real-schema` | 37 | 38 | 13 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-code` | `gc-cite-the-emit-site` | 44 | 44 | 27 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-code` | `gc-a-build-site-window-is-a-true-citation-of-a-false-meaning` | 26 | 16 | 7 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-code` | `gc-a-build-site-read-above-a-pop-is-the-class` | 33 | 33 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-code` | `gc-reproduce-before-you-report` | 35 | 36 | 9 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-code` | `gc-the-mirror-also-binds` | 25 | 26 | 13 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-rules` | `gr-heading` | 14 | 15 | 8 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-rules` | `gr-census-and-must-read-full-set` | 11 | 11 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-rules` | `gr-must-read-full-set-is-computed` | 36 | 36 | 19 | K: test_check_vendored_drift, test_rules_match; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-rules` | `gr-fresh-full-reads` | 13 | 13 | 8 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-rules` | `gr-digest-column-headers` | 70 | 70 | 16 | K: test_rule_grounding;  |
| `grounding-rules` | `gr-digest-heading-and-table-header` | 33 | 33 | 15 | K: test_rule_grounding;  |
| `grounding-rules` | `gr-digest-row-shape` | 19 | 19 | 8 | K: test_rule_grounding;  |
| `grounding-rules` | `gr-quote-matching` | 21 | 21 | 7 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-rules` | `gr-no-elision-and-pipe-escape` | 13 | 13 | 5 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-rules` | `gr-checker-grades-the-countable-subset` | 24 | 25 | 14 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-rules` | `gr-subsequent-selection-cites-a-row` | 10 | 10 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-rules` | `gr-colliding-recommendation-is-dead` | 19 | 20 | 11 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `grounding-rules` | `gr-incomplete-digest-blocks-exit` | 17 | 17 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `grounding-rules` | `gr-self-assertion-never-counts` | 10 | 10 | 6 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `questionbar` | `qb-otherwise-decide` | 34 | 35 | 12 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `injection` | `inj-data-not-instructions-never-overrides` | 28 | 22 | 13 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `injection` | `inj-ground-externally` | 18 | 18 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `test-generation-loop` | `tgl-heading` | 12 | 13 | 5 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `test-generation-loop` | `tgl-pool-off-native-seats` | 28 | 29 | 13 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `test-generation-loop` | `tgl-suggest-one-seat-per-area` | 54 | 55 | 27 | K: test_flows_review_queue_pass; B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `test-generation-loop` | `tgl-a-single-suggester-is-the-blind-spot` | 13 | 14 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `test-generation-loop` | `tgl-curate-the-union` | 11 | 12 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `test-generation-loop` | `tgl-you-own-what-gets-tested` | 14 | 14 | 5 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `test-generation-loop` | `tgl-author-one-seat-per-behavior` | 35 | 36 | 17 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `test-generation-loop` | `tgl-authors-touch-only-their-own-test-file` | 23 | 23 | 15 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `test-generation-loop` | `tgl-report-without-the-flywheel` | 14 | 15 | 8 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `test-generation-loop` | `tgl-list-authored-files-and-pytest-result` | 13 | 13 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `test-generation-loop` | `tgl-fix-review-quality-and-mutate` | 40 | 41 | 10 | K: test_final_gate_registration, test_kaizen_shrink_audit;  |
| `test-generation-loop` | `tgl-test-every-behavior-costs-minutes` | 20 | 21 | 9 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-heading` | 15 | 16 | 7 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-run-invoked-on-a-conversation` | 7 | 7 | 3 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-surfaced-items-are-the-denominator` | 33 | 33 | 14 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-first-act-enumerate-before-design` | 10 | 11 | 7 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-reread-the-whole-conversation` | 30 | 31 | 13 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-extract-every-distinct-item` | 23 | 19 | 6 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-number-items-anchored-to-quotes` | 29 | 25 | 10 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-artifact-carries-the-inventory-heading` | 10 | 11 | 7 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-inventory-table-header` | 10 | 10 | 3 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-disposition-is-exactly-in-out-or-ask` | 63 | 63 | 12 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-ask-has-a-bar-derive-first` | 58 | 58 | 18 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-derivable-items-are-never-asked` | 75 | 84 | 43 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `chat-intake` | `ci-zero-silent-drops` | 34 | 35 | 12 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-undeclared-out-of-scope-is-the-defect` | 17 | 17 | 8 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-say-the-split-when-you-finish` | 37 | 39 | 22 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `chat-intake` | `ci-no-intake-line-hides-the-denominator` | 11 | 11 | 5 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `repo-identity` | `ri-heading` | 14 | 15 | 7 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `repo-identity` | `ri-top-abort-if-empty` | 35 | 37 | 23 | K: test_quota_stop_hook;  |
| `repo-identity` | `ri-worktree-test-normalized-paths` | 28 | 28 | 19 | O: operative condition/object/predicate; no narrative, example or restated rule left to drop |
| `repo-identity` | `ri-linked-worktree-identity-is-main` | 55 | 55 | 26 | B: ban clause(s), tail verbatim from the first ban word to the clause end |
| `repo-identity` | `ri-submodule-own-repo` | 36 | 37 | 22 | B: ban clause(s), tail verbatim from the first ban word to the clause end |

## Pins deleted

None in this ticket (its pins were migrated by T05a and T05b; this ticket edits no test). Node ids: see the T05a and T05b receipts.

## Vanished labels

Every vanished baseline unit has a label in each ledger's `vanished:` map, with the per-clause split in the trailing `# clauses:` comment. **Author labels — audit owed:** the Sonnet + Haiku classification seats cannot run in this clone. Narrative labels: `subagents-core` (L2.3 `mechanism revised by D-182`, L15.3 the 0/5/0 anecdote), `grounding-artifact` (L7.4, L10.2, L11.1, L13.2, L14.1, L14.2, L15.3, L18.2), `grounding-code` (L7.1-L7.3), `grounding-rules` (L4.2, L5.2), `chat-intake` (L4.1, L15.1, L15.3, L16.1). One duplicate label: `subagents-core` L13.3 -> `sc-units-sized-surface`. No clause that holds a ban word is labelled.

## Gates

- `python3 -m pytest -q tests/test_command_rules.py -rP` -> 32 passed, 3 skipped; ten `LEDGER` lines for this unit, no LOSS.
- `python3 commands/assemble_commands.py --check` -> exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING`; no LOSS, no exit 4 or 5.
- Reader-test run (spine § Global Constraints) over the union of 49 files: **start commit `61d1f4b`: 55 failed, 2170 passed, 10 skipped, 4 errors; end of this ticket: 55 failed, 2167 passed, 10 skipped, 4 errors. The 59 FAILED/ERROR node ids are identical at both ends (`comm` of the two sorted lists is empty both ways).** The three fewer passes are the test functions T05a/T05b deleted. The reds are pre-existing: missing `psutil`/`dotenv` and box services in this clone. No test outside Touches was edited.

## Self-audit before the push (hub re-runs it author-blind)

One fresh Opus seat per group read only the baseline file, the rewrite and the ledger, and ran the four checks (LOST, WEAKER, INVENTED, WRONG-VANISHED-LABEL).

Pass 1 found: `subagents-core` 4 weaker (dropped "for any dispatch after it landed"; dropped ", as every fix is in the pin cut after it"; "whichever newer model replaces them" broadened; the deleted L8.10 left the `unless … TRIMMED partition` exception with no antecedent), 1 invented (L38 turned a two-incident anecdote into a general claim), 8 wrong labels (`in two shapes` marked duplicate; L8.10 duplicate of the wrong entry; L10.2 and L36.2 marked narrative though they are cross-reference and rationale; four `# clauses:` comments naming an entry that does not hold the clause). `delegated-reads` 1 weaker + 1 wrong label (two dropped list objects). `repo-identity` 1 wrong label (L2.3). `chat-intake` 1 lost (L17.2), 1 invented (a garbled quote), 2 wrong labels. `test-generation-loop` 1 lost (L5.2), 2 wrong labels (L5, L14.2). The five grounding/injection files: no findings.

Fixed by pass 1: every flagged text restored to the baseline wording (the L36-L38 pin preamble, L8.10, L8.4 tail, L9.1, the `in two shapes` clause, the Floor-line clause, the fabrik-lib module tree and prior transcript, the `documented no-op` clause, the L17.2 consequence, the L19.3 purpose, the L5/L14.2 rationale, the exact `"successor spec or explicit cuts — yours"` quote); the six labels removed; the tool now assigns each clause to the carrier phrase that holds most of its stems, which corrected the four `# clauses:` comments. After the fixes the ledgers load clean and every flagged unit is byte-identical to the baseline (checked with `command_rules.vanished`). The grounding group's two notes (rationale-not-history on `narrative` labels L11 and L13.2 of `grounding-artifact`) are carried as is.

Pass 2 (mechanical): `command_rules.vanished` over the final text lists the units that still differ (`subagents-core` 10, `grounding-artifact` 8, `chat-intake` 7, `grounding-code` 2, `grounding-rules` 2, `repo-identity` 1, `injection` 1); each is covered by the entry coverage check (anchors 100%, >= 70% of the first 8 stems, ban tail verbatim) with zero uncovered clause. No second LLM pass was run on the post-fix text.

COUNTS: entries read 137 / reworded 25 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0 (pass 1 read 133, found 5 weaker, 2 lost, 2 invented, 14 wrong labels; the post-fix state is verified by pass 2's mechanical check only)


## LEFT FOR THE HUB

- The author-blind Sonnet + Haiku audit of the `vanished:` labels and every reworded entry (a seat reading old against new will find what the greedy minimum could shed).
- The floor D-row for the 50% shortfall (live rule counts and reasons above), and the ceiling ratchet in `commands/_size_ceiling.json` (not edited here).
- The review wave, `CHANGELOG.md`, `INDEX.md` rows for the new `commands/_rules/_shared/*.yaml` and `*.baseline.txt` files, and the conversion of the `# class:` / `# clauses:` comments to keys once the loader takes them.
- A decision for the hub: the loader's `_BAN` reads "refused" in a narrative clause (for example `chat-intake` L15.2, "the operator refused") as a ban clause, so incident text stays in a ban carrier.
