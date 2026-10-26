# T24 receipt — lean rewrite of `fabrik-ui-design` (light form, D-1236/D-1238/D-1240)

Run: cloud worker, branch `claude/lean-t23-grp`, TASK slug lean-t23-grp. Start commit: `f08bd02 (T23 commit; baseline file text identical to 851b4b3 — T23 does not touch this source)` (the baseline commit). Baseline sha256 `ffe74466fce7fa1bd4263c4734e16203e04327259405d4b656a583dbc0fec14f` (144 keyed lines, `commands/_rules/fabrik-ui-design.baseline.txt`).

## Own text

- `commands/_sources/fabrik-ui-design.md`: 4368 words → 4037 words (92% of baseline; `wc -w` of `command_rules.own_text`, frontmatter included).
- Target ≤ 50% **not met.** Floor: what survives is (a) ban clauses (never/must/only/refuse), kept verbatim from the ban word to the end of their `;`/`—` clause, parentheticals included (D-1240); (b) backticked anchors, numbers and paths, which D-1240 keeps per clause; (c) lines a behavioural or after-text test reads (`assemble_commands.EXTRACT` after-text, the D-191 dispatch step, the `DECISION NEEDED` block); (d) the frontmatter (`description`/`allowed-tools`, ledgered by no unit). What was cut is narrative, incident ids/dates, analogy sentences and duplicated restatements; cutting further needs a rule removed on purpose (a `retired:` row + D-row), which this unit may not do. A D-row for the floor is the hub's.

## Ledger

- entries total 114: 108 generated unchanged (`generate_unchanged`: ban 32, prose 71, behavioural 3), 6 hand-written reworded (ban 1, prose 5, grammar 0, behavioural 0); reworded/total = 6/114
- vanished baseline lines 19: {'rule': 7, 'narrative': 3, 'duplicate-of': 9} (author labels — audit owed)

| entry | class | baseline lines | clauses | how each clause is covered |
|---|---|---|---|---|
| ui-design-r1 | prose | L1 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 2 clause span(s) labelled narrative (skip list below) |
| ui-design-r2 | ban | L75, L76 | 4 | 4 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-r3 | prose | L77 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-r4 | prose | L84 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-r5 | prose | L123 | 4 | 4 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-r6 | prose | L129 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |

Clause spans labelled narrative (none holds a ban word; checked):
- L1: `(D-181; mechanism revised by D-182 — the provider credentials stay provisioned, so a `fanout` would still dispatch and SPEND: this text is t`
- L1: `(left in place, or in `<!-- POOL OFF -->` comments, for re-enable)`
- L75: `(causes 2 and 3)`
- L77: `(trade-intelligence, 2026-08-28)`
- L84: `do not conflate it with the design-convergence contract at the top of this command: that one froze `docs/ui-design.md` (the *truth*, at desi`
- L123: `(screens are independent → verify them concurrently, don't serialize)`
- L129: `(the design-time analogue of `/fabrik-spec-review`)`

Coverage method (hand-applied D-1240, by a scratch checker that is not committed and not the loader): per baseline clause (split at `;` and ` — `), ONE `text` phrase holds every anchor (backticked token, number, path) and ≥70% of the clause's first 8 content-word stems (stemmed by suffix strip; stopwords dropped); a clause with a ban word is verbatim from the ban word to the clause end in the carrier; phrases are whole new units (≥6 words, unique in the file); no ban-word clause is labelled narrative/duplicate-of. The loader in this base has no `class`/`clauses` keys (`_ENTRY` lacks them), so each entry's class is a `# class:` YAML comment and the narrative clause spans are the skip list above plus `# clauses narrative:` comments on the `vanished:` rows — the hub converts them when the canonical loader lands. `commands/command_rules.py` and `tests/test_command_rules.py` untouched.

## Vanished labels (author labels — audit owed)

- L1: {"rule": ["ui-design-r1"]}
- L75: {"rule": ["ui-design-r2"]}
- L76: {"rule": ["ui-design-r2"]}
- L77: {"rule": ["ui-design-r3"]}
- L78: narrative — file-ownership statement
- L84: {"rule": ["ui-design-r4"]}
- L90: {"duplicate-of": "u-L87"}
- L106: {"duplicate-of": "u-L10"}
- L109: {"duplicate-of": "u-L51"}
- L110: {"duplicate-of": "u-L42"}
- L111: {"duplicate-of": "u-L56"}
- L114: {"duplicate-of": "u-L86"}
- L117: {"duplicate-of": "u-L11"}
- L118: {"duplicate-of": "u-L11"}
- L120: narrative — lead-in
- L123: {"rule": ["ui-design-r5"]}
- L125: {"duplicate-of": "u-L3"}
- L129: {"rule": ["ui-design-r6"]}
- L130: narrative — layer distinction already stated by the pipeline fence

## Pins deleted

- `tests/test_ui_design_queue_pass.py`: deleted `test_phase_zero_names_a_re_freeze_mode`, `test_the_size_ceiling_is_measured_by_a_whole_file_read`, `test_phase_six_checks_unique_ids_and_every_enum_value`, `test_re_freeze_close_out_sweeps_mirrors_and_names_the_review_gate` (presence pins on this command's text). Kept: `test_the_quoted_warn_is_what_the_check_prints_after_a_re_freeze` and `test_the_uniqueness_recipe_counts_definitions_not_mentions` (behavioural: they run `check_frozen_chain` and the Phase 6 `grep … uniq -d` recipe extracted from the source, so that recipe and its `## Phase 6`/`## Phase 7` headings stay).
- `tests/test_ui_design_review_queue_pass.py::test_form_controls_follow_the_templates_named_sections`: deleted only the three assert lines (and the `p5` line) that pin this command's Phase 5 text; the template-heading check stays. The phrases are carriers of generated entries that list the test under `pins:`.
- `tests/test_frontend_design_routing.py`, `tests/enforcement/test_check_frozen_chain.py`, `tests/test_assemble_dispatch_step.py`: cross-file/behavioural, kept; the `Split history (retired screens, superseded versions) into …` sentence, the D-191 dispatch step, the `(This command owns the AUTHOR'S self-convergence; …)` after-text line (`assemble_commands.EXTRACT`) and the `independent review attests` WARN quote are kept verbatim.

## Failure sets

Reader-test union (spine § Global Constraints; 43 files) via `python3 -m pytest -q`, run in a clean worktree at the start commit and again with this ticket's changes overlaid on it (no `capped_run.sh` here):
- start: 52 failed / 2245 passed (the T23 end state; the same 52 node ids as the start commit)
- end: 52 failed / 2241 passed / 10 skipped — the identical 52 node ids (diffed); 4 fewer passes = the 4 pin tests deleted
The end run was re-run once after restoring the clause `, and is not a checklist you run once` (a distinct instruction the 8-stem coverage test would have let go); figures are that run.

Gates: `python3 -m pytest -q tests/test_command_rules.py -rP` → 32 passed, 3 skipped, with the `LEDGER fabrik-ui-design.yaml` line and no LOSS; `python3 commands/assemble_commands.py --check` → exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING` (the installed corpus is not in this clone), none other.

## LEFT FOR THE HUB

- Ratchet `commands/_size_ceiling.json` at merge (the report line `shrank to … words` prints it); not edited here.
- `CHANGELOG.md`, `INDEX.md` rows for `commands/_rules/fabrik-ui-design.yaml`, `commands/_rules/fabrik-ui-design.baseline.txt` and this receipt, and any D-row (including the floor row above).
- The author-blind Sonnet + Haiku classification of the vanished lines and the audit pair over every reworded entry (old against new): labels above are the author's.
- Convert the `# class:` / `# clauses narrative:` comments to keys when the canonical loader lands; re-grade the ledger under it.
- Render the corpus at merge (never done in a worktree).
