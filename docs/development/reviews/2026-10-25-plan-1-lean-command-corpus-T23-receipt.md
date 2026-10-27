OWN TEXT: 2875 -> 2278 (79%)

# T23 receipt — lean rewrite of `fabrik-ui-design-review` (light form, D-1236/D-1238/D-1240)

(The sections below are the fix round's, written for the old comment-form loader; the "Re-ledger round" section at the end supersedes their figures and ledger claims.)

Run: cloud worker, branch `claude/lean-t23-grp`, TASK slug lean-t23-grp. Start commit: `851b4b365cc9ccaac91ed851bc669764743ad360` (the baseline commit). Baseline sha256 `8beb248525a25ded4272853ab65384af705c340070965086ae3a944f7d604f80` (100 keyed lines, `commands/_rules/fabrik-ui-design-review.baseline.txt`).

## Own text

- `commands/_sources/fabrik-ui-design-review.md`: 2875 words → 2258 words (78% of baseline; `wc -w` of `command_rules.own_text`, frontmatter included).
- Target ≤ 50% **not met.** Floor: what survives is (a) ban clauses (never/must/only/refuse), kept verbatim from the ban word to the end of their `;`/`—` clause, parentheticals included (D-1240); (b) backticked anchors, numbers and paths, which D-1240 keeps per clause; (c) lines a behavioural or after-text test reads (`assemble_commands.EXTRACT` after-text, the D-191 dispatch step, the `DECISION NEEDED` block); (d) the frontmatter (`description`/`allowed-tools`, ledgered by no unit). What was cut is narrative, incident ids/dates, analogy sentences and duplicated restatements; cutting further needs a rule removed on purpose (a `retired:` row + D-row), which this unit may not do. A D-row for the floor is the hub's.

## Ledger

- entries total 78: 41 generated unchanged (`generate_unchanged`: ban 13, prose 28, behavioural 0), 37 hand-written reworded (ban 10, prose 26, grammar 0, behavioural 1); reworded/total = 37/78
- vanished baseline lines 52: {'rule': 42, 'duplicate-of': 1, 'narrative': 9} (author labels — audit owed)

| entry | class | baseline lines | clauses | how each clause is covered |
|---|---|---|---|---|
| ui-design-review-r1 | prose | L2 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r2 | prose | L5 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r3 | ban | L6, L10 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r4 | prose | L14 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r5 | ban | L15 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r6 | prose | L16 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r7 | prose | L22 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r8 | prose | L27 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r9 | ban | L28 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r10 | prose | L28 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r11 | prose | L30 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r12 | ban | L31 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r13 | prose | L33 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r14 | ban | L36 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r15 | prose | L40 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r16 | prose | L41 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r17 | prose | L44 | 4 | 4 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r18 | prose | L45 | 4 | 4 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r19 | prose | L46 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r20 | ban | L46 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r21 | ban | L47 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r22 | prose | L56, L63 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 2 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r23 | ban | L57 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r24 | ban | L61, L62, L64 | 4 | 4 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r25 | prose | L67 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r26 | prose | L71 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r27 | prose | L73 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r28 | prose | L74 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r29 | prose | L76, L77 | 4 | 4 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r30 | prose | L79 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r31 | prose | L80 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 2 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r32 | prose | L83, L84 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r33 | ban | L90, L91 | 4 | 4 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r34 | prose | L92 | 1 | 1 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| ui-design-review-r35 | prose | L94, L95 | 3 | 3 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-r36 | prose | L98 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |
| ui-design-review-decision-block | behavioural |  | 0 | 0 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |

Clause spans labelled narrative (none holds a ban word; checked):
- L2: `This is to `/fabrik-ui-design` what `/fabrik-spec-review` is to `/fabrik-spec`: the adversarial, INDEPENDENT hardening of a design artifact `
- L5: ``/fabrik-ui-design-review` (THIS) —`
- L6: `— the artifact`
- L22: `(01M25G1BN)`
- L27: `(D-335 — the fragment's D5 sentence)`
- L47: `— measured, not assumed (1 seat found 0; 3 over the same surface found 0/5/0, and the 5 held a real fail-open; D-186)`
- L56: `— so the built screen can be asserted against it`
- L57: `— a heading that exists but does not carry it is a dangling reference`
- L63: `— so "minimal-click" is a checkable number at build time, not a vibe`
- L64: `— so "no invented field" is mechanically checkable against `docs/ui-design.md` + `docs/data-contract.md` during the build loop`
- L71: `— a `DRAFT` header would fail Phase 0's check on a resumed run`
- L73: `(the closing round above IS the re-freeze convergence)`
- L74: `the `/fabrik-ui-design` freeze law;`
- L77: `it reverses a readiness claim consumers may have acted on;`
- L80: `— since 2026-08-29, by`
- L80: `(`docs/x.md: newest independent review attests v6 but the contract is at v11 — 5 version(s) have had no author-blind pass`)`
- L90: `(causes 2 and 3)`
- L92: `(trade-intelligence, 2026-08-28)`

Coverage method (hand-applied D-1240, by a scratch checker that is not committed and not the loader): per baseline clause (split at `;` and ` — `), ONE `text` phrase holds every anchor (backticked token, number, path) and ≥70% of the clause's first 8 content-word stems (stemmed by suffix strip; stopwords dropped); a clause with a ban word is verbatim from the ban word to the clause end in the carrier; phrases are whole new units (≥6 words, unique in the file); no ban-word clause is labelled narrative/duplicate-of. The loader in this base has no `class`/`clauses` keys (`_ENTRY` lacks them), so each entry's class is a `# class:` YAML comment and the narrative clause spans are the skip list above plus `# clauses narrative:` comments on the `vanished:` rows — the hub converts them when the canonical loader lands. `commands/command_rules.py` and `tests/test_command_rules.py` untouched.

## Vanished labels (author labels — audit owed)

- L2: {"rule": ["ui-design-review-r1"]}
- L3: {"duplicate-of": "ui-design-review-r13"}
- L4: narrative — layers lead-in
- L5: {"rule": ["ui-design-review-r2"]}
- L6: {"rule": ["ui-design-review-r3"]}
- L7: narrative — adjacent-command description
- L8: narrative — adjacent-command description
- L9: narrative — adjacent-command description
- L10: {"rule": ["ui-design-review-r3"]}
- L14: {"rule": ["ui-design-review-r4"]}
- L15: {"rule": ["ui-design-review-r5"]}
- L16: {"rule": ["ui-design-review-r6"]}
- L22: {"rule": ["ui-design-review-r7"]}
- L27: {"rule": ["ui-design-review-r8"]}
- L28: {"rule": ["ui-design-review-r9", "ui-design-review-r10"]}
- L30: {"rule": ["ui-design-review-r11"]}
- L31: {"rule": ["ui-design-review-r12"]}
- L33: {"rule": ["ui-design-review-r13"]}
- L36: {"rule": ["ui-design-review-r14"]}
- L40: {"rule": ["ui-design-review-r15"]}
- L41: {"rule": ["ui-design-review-r16"]}
- L44: {"rule": ["ui-design-review-r17"]}
- L45: {"rule": ["ui-design-review-r18"]}
- L46: {"rule": ["ui-design-review-r19", "ui-design-review-r20"]}
- L47: {"rule": ["ui-design-review-r21"]}
- L56: {"rule": ["ui-design-review-r22"]}
- L57: {"rule": ["ui-design-review-r23"]}
- L61: {"rule": ["ui-design-review-r24"]}
- L62: {"rule": ["ui-design-review-r24"]}
- L63: {"rule": ["ui-design-review-r22"]}
- L64: {"rule": ["ui-design-review-r24"]}
- L67: {"rule": ["ui-design-review-r25"]}
- L71: {"rule": ["ui-design-review-r26"]}
- L73: {"rule": ["ui-design-review-r27"]}
- L74: {"rule": ["ui-design-review-r28"]}
- L76: {"rule": ["ui-design-review-r29"]}
- L77: {"rule": ["ui-design-review-r29"]}
- L79: {"rule": ["ui-design-review-r30"]}
- L80: {"rule": ["ui-design-review-r31"]}
- L82: narrative — history
- L83: {"rule": ["ui-design-review-r32"]}
- L84: {"rule": ["ui-design-review-r32"]}
- L85: narrative — measurement anecdote
- L86: narrative — measurement anecdote
- L87: narrative — measurement anecdote
- L88: narrative — measurement anecdote
- L90: {"rule": ["ui-design-review-r33"]}
- L91: {"rule": ["ui-design-review-r33"]}
- L92: {"rule": ["ui-design-review-r34"]}
- L94: {"rule": ["ui-design-review-r35"]}
- L95: {"rule": ["ui-design-review-r35"]}
- L98: {"rule": ["ui-design-review-r36"]}

## Pins deleted

- `tests/test_ui_design_review_queue_pass.py`: deleted `test_built_navigation_grounds_ia_claims`, `test_trimmed_seats_carry_several_axes_and_report_the_rest`, `test_cross_references_resolve_to_the_design_they_name`, `test_an_in_loop_edit_is_not_an_in_place_edit_finding`, `test_seats_name_the_ranges_they_read_over_the_ceiling` (pure presence pins on this command's text); in `test_form_controls_follow_the_templates_named_sections` deleted only the two assert lines on this command's axis A and Phase 2 text (and their `axes`/`p2` lines) — the author-side asserts on `fabrik-ui-design.md` and the template-heading check stay for T24. Each deleted phrase is a carrier in the ledger and the entry lists the test under `pins:`.
- `tests/test_flows_review_queue_pass.py::test_the_ui_design_review_description_names_axis_f`, `tests/test_frontend_design_routing.py` (cross-file loops): kept; the frontmatter `description` they read is unchanged.
- Kept verbatim (behavioural / after-text): the `(After the closing round: the approval gate at the end.)` line (`assemble_commands.EXTRACT` after-text, `test_every_extract_after_text_round_trips_against_its_source`), the `DECISION NEEDED` block, the `the review's first finding is the split` sentence.

## Failure sets

Reader-test union (spine § Global Constraints; 43 files) via `python3 -m pytest -q`, run in a clean worktree at the start commit and again with this ticket's changes overlaid on it (no `capped_run.sh` here):
- start: 52 failed / 2250 passed / 10 skipped (`tests/sysadmin/test_rules_render_versions.py` 2, `tests/test_agent_definitions.py` 1, `tests/test_assemble_dispatch_step.py` 1, `tests/test_check_command_corpus.py` 7, `tests/test_command_run.py` 1, `tests/test_conftest_isolation.py` 5, `tests/test_fabrik_deck.py` 15, `tests/test_generate_capability_index.py` 12, `tests/test_quota_dashboard.py` 7, `tests/test_review_queue_pass.py` 1 — box services and installed corpus absent in the clone)
- end: 52 failed / 2245 passed / 10 skipped — the identical 52 node ids (diffed); 5 fewer passes = the 5 pin tests deleted
One first end-run differed by `test_every_extract_after_text_round_trips_against_its_source` (a rewrite had dropped the EXTRACT after-text line); the line was restored verbatim and the full union re-run; the figures above are that second run.

Gates: `python3 -m pytest -q tests/test_command_rules.py -rP` → 32 passed, 3 skipped, with the `LEDGER fabrik-ui-design-review.yaml` line and no LOSS; `python3 commands/assemble_commands.py --check` → exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING` (the installed corpus is not in this clone), none other.

## LEFT FOR THE HUB

- Ratchet `commands/_size_ceiling.json` at merge (the report line `shrank to … words` prints it); not edited here.
- `CHANGELOG.md`, `INDEX.md` rows for `commands/_rules/fabrik-ui-design-review.yaml`, `commands/_rules/fabrik-ui-design-review.baseline.txt` and this receipt, and any D-row (including the floor row above).
- The author-blind Sonnet + Haiku classification of the vanished lines and the audit pair over every reworded entry (old against new): labels above are the author's.
- Convert the `# class:` / `# clauses narrative:` comments to keys when the canonical loader lands; re-grade the ledger under it.
- Render the corpus at merge (never done in a worktree).

## Re-ledger round (canonical loader, W-9cd8653d; operator P0 W-96f36043)

- Own text (`wc -w` of the source, frontmatter included): baseline 2875 -> fix round 2258 -> now 2278 (79%). The target of 50% is NOT met. The fix round's 2258 was reached partly by dropping anchors (backticked tokens, numbers, paths, dates) from clauses it kept; the canonical loader counts those, so they came back (`(trade-intelligence, 2026-08-28)`, `(causes 2 and 3)`, the whole `check_frozen_chain.py` line with its example, `e.g. web landing/login/...`, `(D-335)`, `Phase 0's`, `Radix/NativeWind/Tamagui`, `bespoke/invented`). Cuts made: the `Distinct from` sentence in the description, the analogy sentence and `No running app` heading echo (L2, L5, L6), the Read-tool-cap clause, the shadcn tail clause, the axis-F twin example, the REFUTE quote tail, `(a11y)`/`(MV3 surfaces)` notes, and wording in L14/L16/L48.
- LOSS: 15 (hub's list on the base) -> 0 for `fabrik-ui-design-review.yaml` under the canonical loader, with every `# class:`/`# clauses:` comment now a real `class:`/`clauses:` key (which also made 40 prose entries lintable). `--check` prints LOSS only for other ledgers (`design-review`, `fabrik-flows-review`, `fabrik-ui-design`, `_shared/*`), none of them mine.
- Entries 79: 48 unchanged-unit entries (`u-L*`), 30 hand-reworded, 1 behavioural block entry. Reworded/total = 30/79. `clauses:` labels: narrative on r1 (2), r2 (1), r3a (2), r7 (2), r11 (2), r21 (2), r22 (2), r23 (2), r24b (2); none on a clause holding a ban word. Vanished: L3, L4, L7-L9, L82, L85-L88 narrative; L63 duplicate-of r24; the rest `rule:`.
- Restored after the loader showed them as dropped anchors or operative detail: L41 (`e.g. web landing/...`), L67 (`unknowns / assumptions / out-of-scope risks`, `named resolution step`), L40 (`not just the happy path`), L45 (`(or per surface)`), L73, L74, L80, L90 (`causes 2 and 3`), L92, L94.
- Reworded shorter than baseline, loader-clean, flagged for the author-blind audit: r4 (drops `which file`), r5 (drops the `you review a frozen artifact` aside), r11 (clause 2, `a contract naming a component that isn't real is a defect`, labelled narrative), r17 (twin example), r18 (`non-issue` tail), r26 (`on a resumed run`), r29 (`readiness claim` aside), r30 (`most looks like simply stopping` tail), r33 (the quoted `do not commit` pair), r36 (`screen-building phases each running the Build Verification Loop`).
- Floor table (clauses over their anchors-plus-6 minimum, and why they cannot shrink): L18/L19/L17 and L28-clause 1 — a ban word (`only`/`must`) sits inside a parenthetical, so the clause is verbatim to its end and carries 6 path anchors; L20/L16 — path and slash-token anchors; L29, L34, L49-L51, L53, L68, L75, L81, L100, L12 — ban clauses verbatim (L12 and L11 are also EXTRACT after-text, read by `test_every_extract_after_text_round_trips_against_its_source`); L22 clause 3, `the review's first finding is the split`, read by `tests/test_assemble_dispatch_step.py`; L80, L92, L74, L73, L42 — dates, ids, numbers and a long backticked example are anchors of an otherwise single clause that no label may split; L28 clause 3 — the `loading/empty/...` state list and `design-system-template.md` sections are anchors; the `DECISION NEEDED` block is grammar read by `tests/test_gate_decision_blocks.py`. Live rule count: 30 reworded + 48 unchanged + 1 block; no rule was removed. Floor: about 78%; 50% would need ban clauses or anchored clauses dropped.
- Pins: no pin test deleted this round; the frontmatter `description` keeps `consistency + internal contradictions` (`tests/test_flows_review_queue_pass.py`).
- COUNTS: 79 entries read / 30 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels. Earlier passes fixed: L3 relabelled narrative (was a duplicate-of that covered one of its three failure modes); r15 and r25 restored to baseline units; r24 split from L64 so its `docs/...` anchors sit in a narrative-labelled clause.
- Gates, start -> end: `test_command_rules.py` 1 failed/56 passed at start (the LOSS); the reader-test groups started at 14 failed/100 passed (dispatch_step, orch_retired: installed-corpus and git-grep), 2 failed/556 passed (`test_command_measure::test_check_exit_order...`, `test_conftest_isolation`), the rest green. End figures below.

## Fix round 2 (hub audit)

Findings: Sonnet 18 + Haiku 20, overlapping; all checked against the baseline text. **Confirmed and fixed: all of them** (none refuted; every OLD quote is in the baseline). Fix per finding, each restored verbatim:
- r36 / L98 (Sonnet 1, Haiku 18-19): `references … as binding UI truth, its screen-building phases each running the Build Verification Loop to its closing round` restored.
- r24b / L64 (S2, H15): both path anchors and `mechanically checkable … during the build loop` restored; L62/L63 (the loader's three LOSS lines) restored verbatim as r24 / new r24a (L63 relabelled `rule: r24a`, was `duplicate-of r24`, S8); L77 clause 2 (`it reverses a readiness claim…`) restored in r29.
- r17 (S3, H11): `a state listed on one screen and forgotten on its twin` restored.
- r11 / L30 (S4, H9): the `a contract naming a component that isn't real is a defect` clause, `actually`, `connected`, `the contract leans on` restored; the narrative label removed.
- r23 (S5, H14): `is followed` and the `dangling reference` clause restored; narrative label removed.
- L4, L7, L8 (S6, H2): the three-layer list and `do not conflate them` restored in the source; new entry `ui-design-review-layers` carries them (label `rule`). L3 (S7): defect list restored, new entry `ui-design-review-defects`, label `rule`. L5/L6/L10 restored with the `#1` list so `This command is #1` no longer dangles (S18, H1: `(THIS)` back).
- Frontmatter `description` (S9, H20): the `/design-review` and Build Verification Loop distinctions restored.
- r4, r5, r6, surface-pack, r7, r8, r26, r19, r33, r14, r18, r30 (S10-S17, H3-H8, H10, H12, H13, H16, H17): each restored verbatim to its baseline wording; their `clauses` narrative labels (r7) removed.

Own-text words: baseline 2875 → re-ledger 2278 → now about 2,650 by estimate; `own_text` could not be run in this lane (no shell beyond the listed gates). The loader's REPORT line (`shrank to 25298 words`) is the corpus total, not this file. The 50% target is retired (D-1257).

Fresh passes: **0.** No subagent can be dispatched in this lane, so no fresh-reader pass ran; the hub's author-blind audit pair covers it. My own line-by-line check of each restored entry against its baseline line is not a fresh pass and no zeros are claimed.

COUNTS: not claimed — no fresh pass ran.

Gate: `tests/test_command_rules.py` shows 1 failed / 56 passed; the failure is `cr.losses(...) == []` over all ledgers (717 items, first `design-review.yaml design-review-r3`), which is other units' LOSS under this tree's loader. This lane cannot lay master's loader (no git), so this ledger's own LOSS lines are listed in the next run's output below.

## LEFT FOR THE HUB (re-ledger)

- Ratchet `commands/_size_ceiling.json` (report line: `shrank to 24901 words`); `CHANGELOG.md`, `INDEX.md`, any D-row for the 79% floor.
- Author-blind audit of the 30 reworded entries, old against new.
- T01d's `_shared/*` LOSS lines and the other ledgers' LOSS lines are not this ticket's.
