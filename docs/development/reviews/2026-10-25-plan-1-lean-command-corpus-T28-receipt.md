# T28 receipt — lean rewrite of `fabrik-flows-review` (light form, D-1236/D-1238/D-1240)

Run: cloud worker, branch `claude/lean-t23-grp`, TASK slug lean-t23-grp. Start commit: `b53c5a6 (T24 commit; this source is untouched by T23/T24, baseline text identical to 851b4b3)` (the baseline commit). Baseline sha256 `01f798b5819d145b43b8b94dabdbb0ba872de094864171e39ad31b03e9bd02a8` (86 keyed lines, `commands/_rules/fabrik-flows-review.baseline.txt`).

## Own text

- `commands/_sources/fabrik-flows-review.md`: 2446 words → 2060 words (84% of baseline; `wc -w` of `command_rules.own_text`, frontmatter included).
- Target ≤ 50% **not met.** Floor: what survives is (a) ban clauses (never/must/only/refuse), kept verbatim from the ban word to the end of their `;`/`—` clause, parentheticals included (D-1240); (b) backticked anchors, numbers and paths, which D-1240 keeps per clause; (c) lines a behavioural or after-text test reads (`assemble_commands.EXTRACT` after-text, the D-191 dispatch step, the `DECISION NEEDED` block); (d) the frontmatter (`description`/`allowed-tools`, ledgered by no unit). What was cut is narrative, incident ids/dates, analogy sentences and duplicated restatements; cutting further needs a rule removed on purpose (a `retired:` row + D-row), which this unit may not do. A D-row for the floor is the hub's.

## Ledger

- entries total 68: 59 generated unchanged (`generate_unchanged`: ban 15, prose 43, behavioural 1), 9 hand-written reworded (ban 3, prose 5, grammar 0, behavioural 1); reworded/total = 9/68
- vanished baseline lines 21: {'rule': 11, 'narrative': 10} (author labels — audit owed)

| entry | class | baseline lines | clauses | how each clause is covered |
|---|---|---|---|---|
| flows-review-r1 | prose | L2 | 4 | 4 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 2 clause span(s) labelled narrative (skip list below) |
| flows-review-r2 | ban | L18 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| flows-review-r3 | ban | L37, L40 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| flows-review-r4 | prose | L65 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| flows-review-r5 | prose | L66 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 2 clause span(s) labelled narrative (skip list below) |
| flows-review-r6 | prose | L69, L70 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| flows-review-r7 | ban | L76, L77 | 4 | 4 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| flows-review-r8 | prose | L78 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| flows-review-decision-block | behavioural |  | 0 | 0 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |

Clause spans labelled narrative (none holds a ban word; checked):
- L2: `This is to `/fabrik-flows` what `/fabrik-spec-review` is to `/fabrik-spec`:`
- L2: `(the live lesson: a journey gap survived TWO frozen, convergence-verified artifact versions because every verifying pass was run by the arti`
- L18: `— measured, not assumed (1 seat found 0; 3 over the same surface found 0/5/0, and the 5 held a real fail-open; D-186)`
- L40: `A gate whose numbers are re-derived per reviewer is an advisory wearing a gate's clothes ·`
- L66: `— since 2026-08-29, by`
- L66: `(`docs/x.md: newest independent review attests v6 but the contract is at v11 — 5 version(s) have had no author-blind pass`)`
- L76: `(causes 2 and 3)`
- L78: `(trade-intelligence, 2026-08-28)`

Coverage method (hand-applied D-1240, by a scratch checker that is not committed and not the loader): per baseline clause (split at `;` and ` — `), ONE `text` phrase holds every anchor (backticked token, number, path) and ≥70% of the clause's first 8 content-word stems (stemmed by suffix strip; stopwords dropped); a clause with a ban word is verbatim from the ban word to the clause end in the carrier; phrases are whole new units (≥6 words, unique in the file); no ban-word clause is labelled narrative/duplicate-of. The loader in this base has no `class`/`clauses` keys (`_ENTRY` lacks them), so each entry's class is a `# class:` YAML comment and the narrative clause spans are the skip list above plus `# clauses narrative:` comments on the `vanished:` rows — the hub converts them when the canonical loader lands. `commands/command_rules.py` and `tests/test_command_rules.py` untouched.

## Vanished labels (author labels — audit owed)

- L2: {"rule": ["flows-review-r1"]}
- L4: narrative — pointer to the closing section
- L18: {"rule": ["flows-review-r2"]}
- L32: narrative — consequence anecdote
- L35: narrative — rationale + incident
- L37: {"rule": ["flows-review-r3"]}
- L38: narrative — rationale
- L39: narrative — measurement anecdote
- L40: {"rule": ["flows-review-r3"]}
- L65: {"rule": ["flows-review-r4"]}
- L66: {"rule": ["flows-review-r5"]}
- L68: narrative — explains what the preceding sentence grades
- L69: {"rule": ["flows-review-r6"]}
- L70: {"rule": ["flows-review-r6"]}
- L71: narrative — measurement anecdote
- L72: narrative — measurement anecdote
- L73: narrative — measurement anecdote
- L74: narrative — measurement anecdote
- L76: {"rule": ["flows-review-r7"]}
- L77: {"rule": ["flows-review-r7"]}
- L78: {"rule": ["flows-review-r8"]}

## Pins deleted

- `tests/test_flows_review_queue_pass.py`: deleted `test_one_bump_and_one_row_per_review_run` (two presence pins on this command's text; the entry for that sentence lists the test under `pins:`). Kept: `test_the_dispatch_line_names_the_exact_invocation_and_it_counts_the_axes` (it ties the lettered axis count to the `--units` number in the dispatch line — a structure assert, so the dispatch line stays verbatim), `test_the_description_names_every_axis` and `test_the_ui_design_review_description_names_axis_f` (frontmatter `description`, unchanged).
- `tests/enforcement/test_trigger_routing.py` (the Turkish trigger phrase in the frontmatter), `tests/test_assemble_axes_match_source.py`, `tests/test_assemble_dispatch_step.py`: kept, unchanged text.

## Failure sets

Reader-test union (spine § Global Constraints; 43 files) via `python3 -m pytest -q`, run in a clean worktree at the start commit and again with this ticket's changes overlaid on it (no `capped_run.sh` here):
- start: 52 failed / 2241 passed (the T24 end state; the same 52 node ids as the start commit)
- end: 52 failed / 2240 passed / 10 skipped — the identical 52 node ids (diffed); 1 fewer pass = the 1 pin test deleted


Gates: `python3 -m pytest -q tests/test_command_rules.py -rP` → 32 passed, 3 skipped, with the `LEDGER fabrik-flows-review.yaml` line and no LOSS; `python3 commands/assemble_commands.py --check` → exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING` (the installed corpus is not in this clone), none other.

## LEFT FOR THE HUB

- Ratchet `commands/_size_ceiling.json` at merge (the report line `shrank to … words` prints it); not edited here.
- `CHANGELOG.md`, `INDEX.md` rows for `commands/_rules/fabrik-flows-review.yaml`, `commands/_rules/fabrik-flows-review.baseline.txt` and this receipt, and any D-row (including the floor row above).
- The author-blind Sonnet + Haiku classification of the vanished lines and the audit pair over every reworded entry (old against new): labels above are the author's.
- Convert the `# class:` / `# clauses narrative:` comments to keys when the canonical loader lands; re-grade the ledger under it.
- Render the corpus at merge (never done in a worktree).
