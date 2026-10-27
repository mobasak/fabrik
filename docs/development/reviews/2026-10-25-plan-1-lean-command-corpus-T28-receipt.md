OWN TEXT: 2446 -> 1967 (80%)

# T28 receipt — lean rewrite of `fabrik-flows-review` (light form, D-1236/D-1238/D-1240)

Run: cloud worker, branch `claude/lean-t23-grp`, TASK slug lean-t23-grp. Start commit: `b53c5a6 (T24 commit; this source is untouched by T23/T24, baseline text identical to 851b4b3)` (the baseline commit). Baseline sha256 `01f798b5819d145b43b8b94dabdbb0ba872de094864171e39ad31b03e9bd02a8` (86 keyed lines, `commands/_rules/fabrik-flows-review.baseline.txt`).

## Own text

- `commands/_sources/fabrik-flows-review.md`: 2446 words → 2060 words (84%) in the fix round → ~1967 words (~80%) after the re-ledger round (frontmatter included; the ~1967 is the 2060 less the `--check` REPORT delta of the rendered word total, since no word-count command was available on the write lane).
- Target ≤ 50% **not met.** Floor, live rule count and why: the ledger holds 68 live rule entries over 86 baseline keyed lines (a rule = a step, a ban, a threshold, a format, a close condition). 18 entries carry a ban word and are verbatim from the ban word to the end of their `;`/`—` clause (D-1240): u-L3, u-L5, u-L8, u-L11, u-L16, u-L30, u-L31, u-L36 (a 150-word axis whose first clause alone is verbatim ~40 words and whose later clauses carry 9 anchors), u-L44, u-L45, u-L46, u-L59, u-L61, u-L67, u-L86, r2, r3, r7. The frontmatter (~150 words, `description` + `argument-hint`) is read by tests and the trigger router, ledgered by no unit. Every other kept clause is held to its anchors (backticked tokens, numbers, paths, dates) plus 6 of its first 8 content stems; the dates inside non-narrative clauses (u-L22 `2026-08-29`, r5, r8) are anchors, so the clause that holds the rule keeps the date. Going further needs a rule removed on purpose (a `retired:` row + D-row), which this unit may not do. A D-row for the floor is the hub's.

### Clauses still over their anchors-plus-6 minimum, and why they cannot shrink

| entry | why it cannot shrink |
|---|---|
| u-L5, u-L11, u-L16, u-L44, u-L45, u-L46, u-L61, u-L67, u-L86 | whole clause is a ban clause (never/must/only), verbatim to the end of its clause |
| u-L3 | the ban word `never` sits inside the parenthetical of clause 3; clause 4 (`or a journey serving no criterion. All are invisible…`) needs 6 of its first 8 stems, which sit in the second sentence |
| u-L36 | clause 1 is a ban clause (never … only), clause 5 carries `fabrik-flows.md`, `Length discipline:`, `hard split at 50`, 30, 50 as anchors inside one parenthetical clause |
| u-L22 | clause 3 holds the date `2026-08-29` as an anchor beside the rule it dates |
| u-L23, u-L24, u-L28, u-L49, u-L52, u-L55, u-L57, u-L58 | short clauses whose first 8 stems are the whole clause |
| u-L62, u-L63 | one clause each; the first 8 stems and the `Status: DRAFT` / `docs/DECISIONS.md` anchors cover nearly all of it |
| r4 | the backticked `blocked --command … --feedback "<...>"` token is one anchor |
| r5 | clause 2 holds `2026-08-29`, `check_frozen_chain.py`, two backticked tokens and the `docs/x.md: …` example as anchors; the example token must stay verbatim |
| r7 | clause 1 anchors `CLAUDE.md`, 2, 3; clause 2 is a ban clause |

## Re-ledger round (loader: canonical D-1245, `class`/`clauses` real keys)

- own text: baseline 2446 → fix round 2060 → now ~1967 words (80%).
- LOSS for this ledger before: 3 under the canonical loader at the base (`flows-review-r2` B, `flows-review-r3` B, `flows-review-r7` B), and every `# class:` comment dormant — converting the 60 comments to keys turned on the linter for the prose entries. After: 0 for `fabrik-flows-review.yaml`. The other LOSS lines `--check` prints are other commands' ledgers and `_shared/*.yaml` (T01d), not edited here.
- reworded/total entries: 27 of 68 (reworded: u-L3, L8, L9, L10, L12, L13, L17, L19, L25, L26, L29, L30, L31, L34, L36, L41, L51, L59 and r1–r8).
- Converted: every `# class:` comment → `class:` key (ban 18, prose 49, behavioural 1 — the loader's own LEDGER line); the `# clauses narrative:` comments → `clauses:` keys on u-L3 (clause 2), u-L29 (clause 1), r1 (clauses 2 and 4), r2 (clause 2). No clause holding a ban word is labelled.
- Fixed at this round: r2 (clause 2 `measured, not assumed (…; D-186)` labelled narrative, ban clause 1 verbatim); r3 (clause 2 `A gate whose numbers are re-derived per reviewer…` is the ban clause's own text, carried verbatim with `Mermaid only where genuinely multi-party`); r7 (anchors `2`, `3` from `(causes 2 and 3)` restored in the carrier); u-L48, u-L56, u-L64 (phrases under 6 words) given `current`, the whole-unit exemption; r5 (the date and example anchors carried in clause 2, no longer dropped); r8 (the anchor date `2026-08-28` kept, the history `trade-intelligence` dropped).
- Restored after the first audit pass (WEAKER/LOST, content a stem count would not catch): u-L17 `axes E … and F … are the grep-able ones` (they are the `--mechanical 2` units); u-L19 `spec line / pack rule`; u-L36 `whose entire job is naming entities, fields and consumer docs` (without it `axis G below REQUIRES exactly that` had no referent); u-L54 `separating resolved from still-open`; u-L13 `(UI types)`; u-L60 `classify at mint — plain row normally`.
- u-L17 changed class from the old `# class: behavioural` comment to `prose`: no behavioural test reads its text (the pin is a source-text structure assert in `tests/test_flows_review_queue_pass.py`, kept, and its phrase `dispatch_headroom.py --units 8 --mechanical 2 --risky 2` — one unit per axis A–G plus E2` stands verbatim). Hub: confirm or reclassify.

| entry | class | baseline lines | how each clause is covered |
|---|---|---|---|
| u-L* (59 entries) | 15 ban / 44 prose | one each | unchanged or tail-trimmed text; one `text` phrase per entry holds every anchor and the stems; ban clauses verbatim |
| flows-review-r1 | prose | L2 | clauses 1 and 3 by the phrase; clauses 2 (`This is to /fabrik-flows what /fabrik-spec-review is to /fabrik-spec`) and 4 (`the live lesson …`) narrative |
| flows-review-r2 | ban | L18 | clause 1 verbatim; clause 2 (`measured, not assumed …`) narrative |
| flows-review-r3 | ban | L37, L40 | both lines by two phrases |
| flows-review-r4 | prose | L65 | 3 clauses by one phrase |
| flows-review-r5 | prose | L66 | 2 clauses by one phrase |
| flows-review-r6 | prose | L69, L70 | 2 clauses by one phrase |
| flows-review-r7 | ban | L76, L77 | clause 1 and 2 by two phrases, clause 2 verbatim from `only` |
| flows-review-r8 | prose | L78 | 1 clause by one phrase |
| flows-review-decision-block | behavioural | — | the `DECISION NEEDED (ground: gate)` fence lines, verbatim |

## Vanished labels (author labels — audit owed)

- narrative: L4 (pointer to the closing section), L32, L35, L38, L39 (rationale and incidents), L68, L71, L72, L73, L74 (the measurement anecdote).
- rule: L2→r1, L3→u-L3, L8→u-L8, L9→u-L9, L10→u-L10, L12→u-L12, L13→u-L13, L17→u-L17, L18→r2, L19→u-L19, L25→u-L25, L26→u-L26, L29→u-L29, L30→u-L30, L31→u-L31, L34→u-L34, L36→u-L36, L37→r3, L40→r3, L41→u-L41, L51→u-L51, L59→u-L59, L65→r4, L66→r5, L69→r6, L70→r6, L76→r7, L77→r7, L78→r8. (Labels for lines the rewrite left exact are surplus and harmless.)

COUNTS: 68 entries read / 27 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels

Self-audit (author, line by line against the files, no subagent available): pass 1 found 6 weaker/lost items (listed under "Restored"), all fixed and re-run; pass 2 found nothing. Known judgement calls for the hub's author-blind audit: u-L25 drops `with no confirmed end state`, u-L26 drops two example lists (lever d), u-L12 drops the domain-pack examples, u-L41 drops `the written spec can itself be wrong`.

## Pins deleted

- `tests/test_flows_review_queue_pass.py`: `test_one_bump_and_one_row_per_review_run` deleted in the fix round (its entry u-L59 lists the node under `pins:`). This round deleted no test.
- `tests/enforcement/test_trigger_routing.py` (the Turkish trigger phrase in the frontmatter), `tests/test_assemble_axes_match_source.py`, `tests/test_assemble_dispatch_step.py`: kept, unchanged.

## Failure sets

Reader-test gates, this write lane (`capped_run.sh`, the clone lacks box services):
Start (before the first edit) → end (after the last edit), failed / passed:
- `tests/test_command_rules.py -rP`: 1 / 56 → 1 / 56 (the one red is `test_the_live_corpus_has_no_loss`: it asserts every ledger in the corpus, so it stays red on other commands' and `_shared/` LOSS; the `LEDGER fabrik-flows-review.yaml` line prints, 68 entries, and `--check` prints no `fabrik-flows-review.yaml` LOSS line).
- axes / routing / agent-definition group: 0 / 60 → 0 / 60.
- dispatch-step group (`test_assemble_dispatch_step.py`, `test_assemble_orch_retired.py`, …): 14 / 223 → 14 / 223 (orphan/symlink/fifo/installed-tree reds and the retired-token `git grep`, box-state reds).
- feedback-report / measure / conftest group: 2 / 621 → 2 / 621 (`test_check_exit_order_loss_then_ceiling_then_drift`, `test_the_two_live_box_tests_pass_a_merge_check_on_a_drifted_box`).
- domain-pack / final-gate / flows-review-queue group: 0 / 458 (2 skipped) → 0 / 458 (2 skipped).
- research-tier / review-queue / skill-router group: 0 / 493 → 0 / 493.
- `test_spec_review_queue_pass.py`: 0 / 9 → 0 / 9.
- frontend-design-routing / gate-decision-blocks / capability-index group: no start result (both background runs hit the 10-minute limit); the end run, given a longer timeout, 0 / 342.
The failure set did not grow; no pin test of this unit changed.

## LEFT FOR THE HUB

- The strict D-1240 floor for this command is the table above; a floor D-row (live rules × words-per-rule) is the hub's.
- Ratchet `commands/_size_ceiling.json` at merge; not edited here.
- `CHANGELOG.md`, `INDEX.md` rows, any D-row.
- The author-blind audit pair over every reworded entry; the vanished labels above are the author's.
- `tests/test_command_rules.py::test_generate_unchanged_ledgers_pass_on_the_live_corpus` fails on every base because of `_shared/*.yaml` (T01d) and sibling-command LOSS.
- Render the corpus at merge (never done in a worktree).

## Fix round 2 (hub audit)

Findings: 2 reports, 18 distinct items. **All confirmed against the before-text; none refuted.** Each fixed by restoring the baseline wording verbatim in the source and in the ledger carrier phrase (the 50% target is retired, D-1257):

- `flows-review-r1` (Sonnet 1, Haiku 8): the role clause `This is to /fabrik-flows what /fabrik-spec-review is to /fabrik-spec: the adversarial, INDEPENDENT hardening of an artifact its author already self-converged` was labelled narrative; restored, clause-2 label removed, and `the Termination contract's closing round` restored in clause 1. Clause 4 (`the live lesson …`) stays narrative (an incident, no instruction).
- `L4` (Sonnet 2, Haiku 6): relabelled `duplicate-of: u-L81` (the order closing round → approval gate is carried by `Once the closing round (confirmed: 0) earns the attestation, the panel answers it` and the `## After the attestation` heading).
- `u-L25` `with no confirmed end state`; `u-L13` `hot-spots and state flags speak its language`; `u-L34` both `not just …` exclusions; `u-L12` `(auth · payments · multi-tenant)`; `u-L26` both example lists; `u-L8` `(you review a frozen artifact, you don't finish its authoring)`; `u-L17` `a type that is not UI-bearing` and `the rest are judgement`; `u-L30` `the journey exercised deeply`; `u-L41` `the written spec can itself be wrong`; `u-L51` `their own grader raises`; `u-L59` `(the closing round IS the re-freeze convergence)`; `r4` `and this disposition is the one that most looks like simply stopping`; `r7` `so "do not commit" and "commit your own work NOW" cannot both be obeyed`; `r2` `measured, not assumed (…; D-186)` (clause-2 narrative label removed, now carried).
- Sub-threshold trims Haiku listed (u-L3 aside, u-L9, u-L10, u-L31, r5) left as they pass the D-1240 test; `L32, L35, L38, L39, L68, L71–L74` stay narrative (incident and rationale, no instruction, no ban word). `flows-review-decision-block` empty `baseline:` is the behavioural entry's convention, unchanged.

Own-text words: baseline 2446 → re-ledger ~1967 → now ~2060 (estimate: the restored phrases add about 90 words; no word-count command was available on this lane).

Gates: `tests/test_command_rules.py` ran 1 failed / 56 passed at start and again after the edits (same red, `test_the_live_corpus_has_no_loss`, which asserts the whole corpus; the loader in this tree is not master's and I could not lay master's loader over it on this lane, so I could not isolate this ledger's LOSS lines from the output). The other gate groups were not re-run after these edits: they read the `fabrik-flows-review` source only through the frontmatter and the dispatch-recipe phrase, both unchanged.

Fresh passes: **0.** No subagent could be dispatched on this lane, so the zero-counts self-audit is NOT a fresh pass; the hub's author-blind audit pair covers it. Line-by-line check by the author of every restored phrase against the baseline text (not a fresh reader):

COUNTS: entries read 68 / reworded 18 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0
