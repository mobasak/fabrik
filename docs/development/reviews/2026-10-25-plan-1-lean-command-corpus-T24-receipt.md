OWN TEXT: 4368 -> 3695 (85%)

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

## Re-ledger round (canonical loader, W-9cd8653d / D-1245; branch `claude/lean-t24-rl`)

Own text, `commands/_sources/fabrik-ui-design.md` (whitespace words, frontmatter and `{{include}}` markers included): baseline 4368 -> fix round 4037 (92%) -> now 3695 (85%). The target ≤ 50% is **not met**; the floor is named below. The count is the fix round's own `wc -w` figure (4037) minus this round's net change, tallied edit by edit (372 words removed, 30 anchor words restored: −342). Cross-check: the `--check` REPORT line fell 20,655 -> 20,313 rendered words, also −342. It is not a fresh `wc` (the write lane has no `wc`).

LOSS for `fabrik-ui-design.yaml`: before 1 (`ui-design-r2`: lint B) -> after 0. (Converting the `# class:`/`# clauses` comments to real keys also switched the lints on for the five reworded entries the old comment form hid — r1, r3, r4, r5, r6 — and r1, r3, r6 failed lint B as written: a `narrative` label covers a whole `;`/`—` clause, never a span inside one. The fix is in the live text, not the ledger: the dropped anchors came back — r1 `D-182` and the `<!-- POOL OFF -->` span, r2 `(causes 2 and 3)`, r3 `2026-08-28`, r6 `/fabrik-spec-review`; r4 and r5 take whole-clause `narrative` labels.) `_shared/*.yaml` LOSS lines are T01d's and untouched.

Ledger: 111 entries (ban 33, prose 73, behavioural 3, grammar 2), every one with a real `class:` key; 27 reworded / 111 total (r1–r6 and u-L6, L7, L10, L16, L17, L24, L30, L34, L35, L37, L40, L49, L52, L98, L112, L113, L115, L121, L122, L126, L143). The 84 unchanged entries alias one `&aN` string as `baseline`/`current`/`text`. Vanished 43 baseline lines: `rule` 28, `narrative` 6 (L78, L96, L120, L128, L130, L134), `duplicate-of` 9 (unchanged).

What this round cut (every clause named by its entry's `clauses:` key; none holds a ban word):
- u-L7 c1, c2 (who reads the contract); u-L10 c2, u-L16 c2, u-L30 c2–c3, u-L35 c2, u-L52 c2, u-L98 c3, u-L112 c2, u-L113 c2–c3, u-L115 c3, u-L126 c3, u-L143 c2: rationale or restatement clauses.
- u-L40 c2 (the "decided HERE, once" gloss); `ui-design-r4` c2 (the "that one froze" history clause); u-L122 c1–c4: the disabled `<!-- POOL OFF -->` re-enable recipe (the one live sentence in c1, "Nothing records to the flywheel", is kept in the live text); `ui-design-r5` c4.
- Whole units deleted, vanished `narrative`: L96 ("verifies against reality, not hope"), L128 ("Freezing here is the AUTHOR's convergence…"), L134 (why the 2-contract chain has seams).
- Shortened inside a covered clause (anchors kept, first-8 stems held): u-L6, L17, L24, L34, L37, L49, L121 (examples and glosses past the first 8 stems).
- Wording of u-L122 now says "secrets carve-out — never inline secret-material content into a pool unit; … never a pool worker" as one live sentence; both ban spans are verbatim.

Pins: none deleted this round (the four pin tests were deleted in the fix round). `tests/test_ui_design_queue_pass.py`, `tests/test_ui_design_review_queue_pass.py`, `tests/test_frontend_design_routing.py` read only text kept here (Phase 0 "skips its one-time seeding and its planning hand-off", the Phase 6 `grep … uniq -d` recipe, the `frontend-design:frontend-design` + `core/63-frontend-design.md` paragraph).

### Floor (why it stops at 85%)

D-1245 reads a ban-bearing clause in every class, a `narrative` label only on a whole non-ban clause, and every anchor (backticked token, number, path, slash pair) of an unlabelled clause. This file is anchor-dense and ban-dense, so what remains is not narrative: 111 live rule entries (ban 33, prose 73, behavioural 3, grammar 2). The units still over their anchors-plus-6-stems minimum:

| unit | words | why it cannot shrink |
|---|---|---|
| frontmatter `description` + `argument-hint` | ~140 | ledgered by no unit; the TRIGGER (EN/TR) text is what the skill router reads |
| u-L5 dispatch step | ~125 | class behavioural: `test_assemble_dispatch_step` reads the emitted step, every clause verbatim |
| u-L19 Mode | ~100 | `only` sits inside the re-freeze parenthetical, so D-1240 keeps the parenthetical verbatim to the clause end; the test asserts "skips its one-time seeding and its planning hand-off" |
| u-L22 ladder | ~95 | `never`, `only`, plus anchors: 2026, 08, 29, 1–3, `saas/60-saas-ui.md`, `docs/design-system.md`, `For-Your-Developer/Design-Tokens/` |
| u-L23 ADOPT | ~85 | `ONLY` inside the parenthetical (verbatim to its close), three `.windsurf/rules/core/…` paths |
| u-L32 | ~140 | `never copied …` runs verbatim to the sentence end (~60 words); two backticked error strings, `25000`, `2.2` |
| u-L63 | ~100 | class behavioural: the `grep … uniq -d` recipe is run by a test; every clause verbatim |
| u-L69 | ~70 | class grammar: the freeze quotation is emitted into projects |
| u-L70/L71 | ~140 | `never carry them` and `only` inside one clause with `frontend-design:frontend-design`, `/design-review`, `npm i -D …`, `tests/ui/`, `violations == []` |
| u-L79 | ~85 | `Traycer-only` (ban `only`) parenthetical, trailing anchor `/fabrik-review`, `found: 0, fixed: 0` |
| u-L92–L99 | ~330 | every backticked tool is an anchor; `only` in "macOS-only job" binds its parenthetical |
| u-L95 | ~100 | anchors `375`/`768`/`1440`, the `goto(…)` and `toHaveScreenshot` tokens; the stems are the instruction itself |
| u-L135, L140 | ~65, ~60 | `only`/`must` spans run through the incident parenthetical; L140's example is one backticked anchor |
| the two fences (pipeline, flow template) | ~80 | a fence is one unit; rewording makes the baseline line vanish |
| u-L2, L3, L11, L12 | ~190 | ban clauses and the `assemble_commands.EXTRACT` after-text line |

Going under 50% needs rules removed on purpose (`retired:` rows + a D-row), which this unit may not do, or a loader reading that frees parentheticals and anchors. D-1240 / D-1245 do not.

### Self-audit (line by line against the files, never from memory)

Pass 1 found and fixed: (a) r1, r3, r6 failed lint B once `class:` became a key — spans cannot be labelled, so the anchors went back into the live text; (b) r2 lint B (the one start LOSS): `(causes 2 and 3)` restored; (c) the u-L34 first-8 stems held 5 of 8 after the gloss cut — "to find the real component" restored; (d) u-L24 had lost "(do not restate the rule here)", an instruction — restored. Pass 2 (re-read of every reworded entry, old against new) found nothing.

Checks: LOST — none (every baseline clause is in a phrase, labelled `narrative` on a non-ban clause, or in a `vanished` row; L134/L128/L96 carry no ban word). WEAKER — none by D-1240 (each reworded phrase holds all anchors of each unlabelled clause and ≥70% of its first 8 stems; ban spans verbatim; the loader passes). INVENTED — none. WRONG-VANISHED-LABEL — two judgement calls for the audit pair: u-L112 c2 ("the contract feeds Traycer OR `/fabrik-plan-after-chat`") is labelled `narrative` though u-L79 states it (`duplicate-of` fails the cover reading); u-L122 c1 is labelled `narrative` although its first sentence "Nothing records to the flywheel" is a live rule — it is kept in the live text and also stated by u-L2 ("a native seat records nothing").

COUNTS: 111 entries read / 27 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels

### Failure sets

- `tests/test_command_rules.py`: start 1 failed / 56 passed; end 1 failed / 56 passed. The one red is the live-ledger test, which lists LOSS lines of other tickets' ledgers and `_shared/` (731 items); none names `fabrik-ui-design.yaml`. PASSES carries `LEDGER fabrik-ui-design.yaml: 111 entries · classes {'ban': 33, 'behavioural': 3, 'grammar': 2, 'prose': 73} · vanished {'duplicate-of': 9, 'narrative': 6, 'rule': 28}`.
- `python3 commands/assemble_commands.py --check`: no LOSS line names `fabrik-ui-design.yaml`; the other LOSS lines are `_shared/` and other tickets; the rest DIFFERS/MISSING drift.
- final-gate/frontend-design batch (`test_frontend_design_routing.py` among them): start 402 passed, 2 skipped; end 402 passed, 2 skipped.
- skill-router/ui-design queue batch: start 282 passed; end 282 passed.
- The other three batches were first run after my first source edit (the start run was not made before editing), so their start set is not measured; no failure below reads this command's text. End:
  - frozen-chain/dispatch-step batch: 13 failed / 134 passed — `test_assemble_dispatch_step.py` installed-tree and orphan tests (corrupted/orphan/symlinked/fifo/non-UTF-8 installed files, `test_v7_the_retired_d191_seat_mix_literal_survives_nowhere`); their `--check` output carries only `_shared/review-probe-catalogue.yaml` LOSS lines (T01d's) and the clone has no installed trees.
  - orch-retired/corpus batch: 1 failed / 345 passed — `test_git_grep_for_retired_tokens_prints_nothing` (`fatal: not a git repository`: the clone has no `.git`).
  - improve-queue/measure batch: 2 failed / 573 passed — `test_check_exit_order_loss_then_ceiling_then_drift` and `test_the_two_live_box_tests_pass_a_merge_check_on_a_drifted_box` (no `origin/master`, and the `_shared/` LOSS the first one meets).

## LEFT FOR THE HUB (re-ledger round)

- Ratchet `commands/_size_ceiling.json` at merge (not edited here).
- `CHANGELOG.md`, `INDEX.md` rows, any D-row for the floor above.
- The author-blind audit pair over the 27 reworded entries and the 3 new `narrative` deletions (L96, L128, L134), plus the two judgement labels named in the self-audit.
- Re-grade under master's loader after T01d lands; render the corpus at merge.
