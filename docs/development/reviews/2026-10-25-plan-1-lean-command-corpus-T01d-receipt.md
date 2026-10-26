# T01d receipt — lean unit 01 shared files, redo under D-1236 (cloud worker, v2)

**Start commit:** 8ac547a6139658fed456bb3f3f069596856d6316 (baseline and frozen copy for the after-window sample).
**Branches:** attempt 1 `claude/lean-t01d` (72a70afc8, c7e25e07b on `kaizen-lean-u01`); this redo `claude/lean-t01d-v2`.

## Words (`wc -w`, the shell's count)

| file | start | attempt 1 | now | now/start | floor and why |
|---|---|---|---|---|---|
| no-workflow-hub.md | 148 | 142 | 111 | 75% | the ban object (`git rev-parse --show-toplevel`, `/opt/fabrik/.claude/worktrees/`) and the two ban sentences are ~85 words; nothing else is left |
| run-record.md | 646 | 457 | 491 | 76% | fence and the two close lines are grammar `check_command_corpus` polices; each remaining clause holds a backticked token or number |
| orient.md | 345 | 228 | 196 | 56% | fence + `ORIENT:` line are grammar (~75 words); the rest is operative |
| close-chain.md | 461 | 451 | 336 | 73% | four numbered calls and their order are asserted by `test_producing_command_fragments` (kept: ordering by index); every other clause carries an anchor |
| close-feedback.md | 2352 | 1436 | 1523 | 65% | FEEDBACK grammar + axis list + mail fence are grammar read by `command_run.py` tests; the rest are operative duties |
| review-probe-catalogue.md | 6870 | 6854 | 6864 | 99.9% | see "Catalogue floor" below |
| fabrik-reviewer.md | 2059 | 1774 | 1858 | 90% | the house-rules paragraph is the seat's only rule source (`omitClaudeMd: true`); its 670 words are bans and recipes with 40 backticked anchors; `test_review_loop_workflow` keeps ~25 phrases cross-file |
| fabrik-researcher.md | 2650 | 2089 | 2115 | 80% | six fetch-failure shapes are operative; each clause holds a tool name or flag |
| fabrik-gui.md | 611 | 452 | 451 | 74% | ban + toolset; front matter (75 words) is grammar |
| **total** | **16142** | **13883** | **13945** | **86%** | |

**This redo does not beat attempt 1 on words** (+62). Attempt 1's count included silent drops the new lints catch — "recursively", "side by side", `git grep` / `git rev-parse` / `git worktree list`, "you may not read", "instead of refusing", `(CLAUDE.md § HARD STOPS)` and about 45 ban sentences — and the loader now forces those back. What D-1236 buys is bounded by its own anchor and coverage rules, not by pins: 123 of the catalogue's 273 baseline clauses (45%) hold a backticked token, number, path or `never/must/only/refus…` word and survive nearly verbatim; the other 55% may be paraphrased but must keep 70% of their content stems (all of them up to 8 stems).

### Catalogue floor (6864 / 6870)

All 70 baseline units are probe bullets; 65 survive as exact units. The only narrative T01d found was ~400 words of plain-word parentheticals (examples), 6% of the file. Removing them is allowed by D-1236 but I did not: each is the one example that tells a seat what the clause covers, and the audit pair has not read them. A trial paraphrase of the longest bullet ("The premise", 340 words) came out at ~300, i.e. about 12%, so paraphrasing every long bullet would take ~800 more words (to ~88% of start) for an unaudited rewording of seat-facing recipe text; I stopped there and left it to the hub (lever 7). **Hub lever, not done here (needs a D-row):** § Seat isolation is ~2,400 words (35% of the file) restating `PIN_IMPORT`/`PYTEST_PINS`/`GATE_PINS`, which `.claude/workflows/fabrik-review-loop.js` already carries and `test_review_loop_workflow` grades; replacing the recipe by a pointer to those constants would remove ≈1,600 words (estimate, not run), leaving this file near 77% of start. The other files have the same shape: their remaining words are bans, grammar or operative clauses.

## Ledgers (`commands/_rules/_shared/*.yaml`)

| ledger | entries | reworded (carrier ≠ baseline) | class: ban / grammar / behavioural / prose | clauses labelled narrative · dup | baseline units | vanished (rule · narrative) |
|---|---|---|---|---|---|---|
| no-workflow-hub | 4 | 2 | 3 / 0 / 0 / 1 | 0 · 0 | 4 | 2 (2 · 0) |
| run-record | 21 | 10 | 5 / 3 / 0 / 13 | 5 · 0 | 22 | 11 (9 · 2) |
| orient | 7 | 5 | 2 / 2 / 0 / 3 | 4 · 0 | 9 | 6 (5 · 1) |
| close-chain | 9 | 7 | 3 / 1 / 0 / 5 | 3 · 1 | 9 | 7 (7 · 0) |
| close-feedback | 55 | 28 | 17 / 5 / 0 / 33 | 12 · 0 | 78 | 49 (44 · 5) |
| review-probe-catalogue | 68 | 10 | 43 / 0 / 0 / 25 | 0 · 0 | 70 | 5 (4 · 1) |
| fabrik-reviewer | 39 | 21 | 13 / 7 / 0 / 19 | 3 · 0 | 41 | 16 (16 · 0) |
| fabrik-researcher | 74 | 39 | 22 / 11 / 0 / 41 | 7 · 1 | 68 | 30 (28 · 2) |
| fabrik-gui | 18 | 15 | 7 / 2 / 0 / 9 | 1 · 1 | 22 | 16 (15 · 1) |
| **total** | **295** | **138** | | **35 · 4** | | |

Reworded/total = 138/295 entries. Attempt 1 had 422 entries; merging entries that shared one baseline text (pin entry + full entry for one sentence) removed 127 duplicates. `behavioural` is 0 on purpose: no kept test asserts a carrier on *emitted* output; every kept pin is a plain file-text assert inside a test that also asserts another file or an ordering (spine § Global Constraints keeps those), and those phrases sit verbatim in the `ban`/`grammar`/`prose` entries.

**Defects of attempt 1 found by the new lints and fixed:**
- 65 entries (close-feedback 37, reviewer 28) carried an author-written paraphrase as their `baseline`, not baseline text. They are re-based on the real baseline unit (`_check` now refuses any entry whose `baseline` is not text of its baseline file).
- Dropped words and anchors: the catalogue's "recursively" and "side by side"; researcher `<loc>/<lastmod>`-class tokens, "you may not read", "hard refusal"; reviewer `git grep`/`git rev-parse`/`git worktree list`, `>>` appends, "instead of refusing"; close-feedback `change: make it faster`, "only", "cannot", "Phase-0". Each is back in the file or its clause is labelled.
- Ban-bearing entries whose carrier lacked the ban token: the loader refuses them now; all 295 pass.
- 6 clause labels that the recall rule made unnecessary were pruned automatically; the 39 that remain are listed in the audit brief below.

## Tooling (`commands/command_rules.py`, `tests/test_command_rules.py`, `docs/reference/command-corpus-check.md`)

D-1236's counters, as loader lints (this is tooling the ticket's DO-NOT list names; the payload's `class:` needs it):
- an entry may carry `class` and `clauses`; every entry of a live `_shared/` ledger needs a `class`;
- a ban token in an unlabelled baseline clause needs a `text` carrier holding a ban token;
- a `prose` phrase is ≥ 6 normalised words and unique in its file (`losses()`);
- every baseline clause (split at `;` / ` — ` outside backticks and parentheses) is inside a `text` phrase, labelled `narrative` / `duplicate-of`, or covered: every backticked token, number, path and `never/must/only/refus…` word held, and for an anchor-free clause 70% of its content stems (all of them up to 8 stems). Decision/work/mail ids, ISO dates and parentheticals citing them are history, not anchors;
- an entry's `baseline` must be text of its baseline file.

**Interpretation to confirm (the audit pair and the hub):** D-1236 says each clause is "inside a `text` phrase". Read literally that is verbatim containment and forbids rewording; I read it as *covered* — verbatim, or anchors held plus 70% stem recall. A stricter reading means every reworded clause above carries a label. Cobra (D-253) for the recall rule is in the docstring and the doc: pad a carrier with the clause's vocabulary. `tests/test_command_rules.py` gains 6 tests (reworded entry passes; dropped ban token / anchor refused; clause label grammar; 6-word and uniqueness; unknown class and edited baseline; live shared entry needs a class).

## Pins

Retired by T01a/T01c (already deleted on `kaizen-lean-u01`, now listed under `pins:`): 71 test nodes across 11 test files (`test_review_scoped_queue_pass` 32, `test_review_queue_pass` 27, `test_agent_definitions` 3, two each/one each in six more) — recovered from `git diff 1659737..8ac547a -- tests` and matched to the entries whose baseline holds the deleted literal.

Deleted in this commit (plain string-in-file presence of one cut file; the rest of each test kept):
- `tests/test_review_queue_pass.py::test_every_workflow_command_carries_the_no_workflow_in_the_hub_note` — the five banner phrases (the `launching`/hub-copy assertions stay) → `no-workflow-hub` entries;
- `tests/test_review_queue_pass.py::test_briefs_durable_unchanged_slices_said_guards_round_trip_counts_from_receipt` — the close-chain sentence → `cc-briefs-durable-unchanged-slices-said-guards`;
- `tests/test_command_improve_queue_pass.py::test_a_weakening_recurrence_routes_and_ledger_prose_follows_the_closing_pass` — the close-chain sentence → `cc2-recheck-after-pass`;
- `tests/test_producing_command_fragments.py::test_the_close_chain_gates_before_it_pushes` — two reason/consequence phrases (the ordering asserts stay) → `cc-then-1`.

## Reader tests (58 files, clone environment: root, no services)

Start (attempt 1 head, separate worktree): 61 failed + 1 collection error, 2840 passed. Final (commit cd38168, run in a clean worktree): 60 failed + 1 collection error, 2847 passed — a strict subset of the start set, no node new. The set is environmental: `tests/test_fabrik_deck.py` 15, `test_generate_capability_index.py` 12, `test_quota_dashboard.py` 7, `test_check_command_corpus.py` 7, `test_conftest_isolation.py` 5, `test_gate_check_canaries.py` 3 (it was 4: the `check_lint_ratchet` canary passed this time, it does not read these files), `test_review_loop_ledger.py` 3, two in `sysadmin/test_rules_render_versions.py`, one each in `test_seat_guard`, `test_review_queue_pass`, `test_command_run`, `test_assemble_dispatch_step`, `test_agent_definitions`, `enforcement/test_check_review_hygiene`, and `test_scrape_ledger.py` failing to collect. One transient red in between (`test_own_fix_guards_helper_contracts_and_pinned_versions`: a line over 120 columns from a ledger-driven edit) was fixed before the final run. `tests/test_command_rules.py` + `test_command_measure.py`: 50 passed, 3 skipped before the 6 new tests; 38 passed after. `assemble_commands.py --check`: exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING`, no LOSS, no ceiling line.

## Left for the hub

1. **Author-blind Sonnet + Haiku audit of every reworded entry, old against new** — 138 entries; brief them with `baseline` vs `current`/`text` and the 39 clause labels (35 `narrative`: close-feedback 12, run-record 5, orient 4, researcher 7, close-chain 3, reviewer 3, gui 1; 4 `duplicate-of`): `cf-11 cf-16 cf-17 cf-19 cf-21 cf-24 cf-33 cf-36` · `rr-surface rr-done rr-sync-excluded rr-hub-copy-read-only runrec-both-hold…` · `or-cobra or-surface-paths` · `cc-then-1 cc-briefs-durable… cc2-before-seven-line` · `sha-pin agent-kept-seat-never-disguises` · researcher `html-docs-page absence tables L22 L32 L68`. Also the 11 narrative `vanished` lines.
2. The review wave over `command_rules.py` (new lints) and the ledgers.
3. **T4 D-row** (Opus + Fable panel, dispatched by the coordinator): briefs carry the question and the pin; house rules stay in `fabrik-reviewer.md` (open floor 1858/2059, W-f723cb66 = `house-never-execute-surface`). The two catalogue folds stand: `env -C <scratch>/arch python -P -B` (W-9ad5860f catalogue half) and a gitignored generated file copied into the archive tree, named UNPINNED (W-6effedda).
4. A D-row for the recall-rule reading above, and for "class is set at baseline and changed only by a D-row" (not mechanised: no history to compare; `changed-by` is the hook).
5. The ceiling ratchet at merge (`assemble_commands.py --ratchet`, never by hand); `INDEX.md`/`CHANGELOG.md` rows for the new lints and this receipt.
6. The § Seat isolation pointer lever (≈ −1,600 words, needs a D-row).
7. Paraphrase pass over the catalogue's long anchor-free bullets (≈ −800 words) once the audit pair has read the first pass.

## Fix round v3 (cloud worker, branch `claude/lean-t01d-v3`, base `claude/lean-t01d-v2`)

**Loader swap (first commit, "not T01d work").** `commands/command_rules.py`, `tests/test_command_rules.py` and `docs/reference/command-corpus-check.md` taken from `origin/infra-3-d1236-lints` (cf90e45; `git log origin/master --grep=W-9cd8653d` printed no merge). Never edited afterwards; the hub drops them from this branch's diff at merge.

**LOSS 72 → 0.** Reproduced first (72 lines: A 10, B 33, D 22, labels 7). Clearing the 7 "malformed" entries then exposed 21 further lines the loader had been masking behind them (researcher 22, reviewer 16, close-chain 6, gui and no-workflow-hub); all cleared. `python3 commands/assemble_commands.py --check` now prints no `LOSS` line (exit 1, MISSING drift only: this clone has no installed corpus). `pytest tests/test_command_rules.py`: 50 passed, 3 skipped.

**How.** Every ban clause is restored verbatim from its ban word to the end of its `;`/`—`/sentence clause in the live file (and in the entry's `current`/`text`); uncovered clauses are covered by ONE phrase; no ban-bearing clause or line is labelled `narrative`/`duplicate-of`; baseline lines L44/L56 (close-feedback), L5 (orient), L4/L13 (run-record), L26 (researcher) now have real carriers (`cf-65`, `cf-64`, `or-hub-absolute`, `rr-protects-only-if-opened`, `rr-only-witness`, `rsr-L26-measured-in-one-run`). Where a clause's rewording had dropped a rule, the rule is back; `class` and `clauses` were already real keys in v2 (no comments to convert).

### Words (`wc -w`): start 8ac547a61 → v2 → v3
| file | start | v2 | v3 |
|---|---|---|---|
| close-chain.md | 461 | 336 | 462 |
| close-feedback.md | 2352 | 1523 | 2083 |
| run-record.md | 646 | 491 | 570 |
| orient.md | 345 | 196 | 345 |
| no-workflow-hub.md | 148 | 111 | 120 |
| fabrik-researcher.md | 2650 | 2115 | 2435 |
| fabrik-reviewer.md | 2059 | 1858 | 1984 |
| fabrik-gui.md | 611 | 451 | 538 |
| review-probe-catalogue.md | 6870 | 6864 | 6864 |

The canonical loader makes most of v2's cut a lost rule: close-chain and orient return to their start size. The honest v3 saving is what the rewrite can shed once every ban clause and anchor is kept (the hub should measure it with `wc -w` on the merged tree).

### Reworded / total entries per ledger (reworded = no text phrase and no `current` equals the baseline, whitespace-normalised)
close-chain 2/9 · close-feedback 19/70 (63 at first count + 7 new carriers) · fabrik-gui 9/19 · fabrik-researcher 11/76 · fabrik-reviewer 13/39 · no-workflow-hub 2/4 · orient 0/9 · review-probe-catalogue 0/68 (untouched) · run-record 6/24. (Counts taken before the last two carrier additions; the ledgers hold the live numbers.)

### Self-audit (three author-blind passes by fresh subagents, baseline vs rewrite vs ledger, line by line)
- Pass 1 found and I fixed: one invented ban (reviewer "never execute the surface under review itself…"), the dropped git-stash incident clause, `wf-refuter`'s `unverified` rewrite, 5 lost rules behind wrong `vanished` pointers (close-feedback L24/L27/L29/L33/L34/L49), cc2-four-calls' override list, cc2-before-seven-line, an input's "first", orient surface-paths/cobra/"read and cited", banner "or unit's", run-record "fifth cause".
- Pass 2 found and I fixed: cf-11's wrong L10 carrier, L17 mislabelled narrative (new `cf-71`), L13 (new `rr-only-witness`), `wf-structured`'s check definition, cf-36's "will not accept either".
- Pass 3 found and I fixed: L20 (`cf-72`), L71 (`cf-73`), cf-35's consequence, the BLOCKED clause of `runrec-both-hold…`, gui L21 (`gui-design-review-complement`).
- `COUNTS: entries read 239 / reworded ~70 / weaker 12 (pass 3, before its fixes) / lost 3 / invented 0 / wrong vanished labels 4` — NOT zeros: pass 3's report is the last full pass, and I fixed its lost items and the four wrong pointers afterwards without a fourth pass. Remaining known, history-only or low items (each dropped text holds no ban word): close-feedback L38 (error string and `01M14V7KH4`), L41 `invalid choice`, L56/L58 rhetoric, cf-16 clause 3; researcher L25 tail, L26 WebFetch half and its id, L34 "in both directions" and `01M1KMS2…`, L22 clause 2 rationale (`$HOME/.claude*` stays in L8), L8 "and the page is lost"; gui L7 "console, network, perf, DOM", L16 "(or arm a Monitor)"; no-workflow-hub round-1/delta/wave enumeration; run-record L7 numbers, L8 `CLAUDE_AGENT`, L21–L22 rationale. The hub's author-blind audit decides whether any must come back.

### The three tests outside "edits no test" (v2 deletions, kept)
- `tests/test_command_improve_queue_pass.py`: removes a close-chain presence pin; its phrase spans `cc2-recheck-after-pass` (now carries the examples verbatim) and `cc-briefs…`, and the test is listed under `cc2-recheck-after-pass` `pins:` → kept.
- `tests/test_producing_command_fragments.py`: removes the two `cc-then-1` reason pins; both clauses are live again in `cc-then-1` (clause 7 no longer labelled narrative), test listed under its `pins:` → kept.
- `tests/test_review_queue_pass.py`: removes the banner phrase pins and the `cc-briefs` sentence pin; every phrase is a live carrier (`banner-*` entries; `-3` and `-4` now list the test under `pins:`, `cc-briefs…` lists its own) → kept. Nothing restored.

### Reader tests (94 test files that reference fragments/agents/rules/assemble/command_rules, clone environment as root, no services)
Start commit (v2, separate worktree): 143 FAILED/ERROR lines. End (final tree, v3): 143, `comm -13` of the two sets empty — no node new. (The clone lacks box services, so the reds pre-exist.)

### LEFT FOR THE HUB
1. The author-blind audit of record (last pass above was not zero; see the remaining list).
2. Measure the real v3 saving on the merged tree; consider a D-row if the ban-verbatim reading (cf-63/64, rr-only-witness restore ~150 words of history around one ban word) is judged too costly: the loader gives no way to label such a clause.
3. A decision on `cf-32`'s `class: grammar` (forces its clause verbatim) and `cf-55`/orient fenced units (comment text restored to satisfy grammar).
4. Re-run `--ratchet` and the ceiling at merge; INDEX/CHANGELOG rows.

## Cut pass v4 (branch claude/lean-t01d-v4, cloud worker; base v3)

**Result: the 50% target is NOT met.** v4 totals 13,364 of 16,463 start words (81%); v3 was 95%. Every file stays under its start and ZERO LOSS (`assemble_commands.py --check` prints no LOSS line; `tests/test_command_rules.py` 50 passed, 3 skipped). Per-file words (`wc -w`, start = 8ac547a61), with the ban-clause floor:

| file | payload baseline | start wc -w | v3 | v4 | v4 % of start | ban V-span floor (words, %) |
|---|---|---|---|---|---|---|
| close-chain | 473 | 473 | 470 (99%) | 475 | **100%** | 58 (12%) |
| close-feedback | 2436 | 2436 | 2147 (88%) | 2023 | **83%** | 419 (17%) |
| fabrik-gui | 637 | 637 | 559 (87%) | 598 | **93%** | 90 (14%) |
| fabrik-researcher | 2728 | 2728 | 2507 (91%) | 2175 | **79%** | 414 (15%) |
| fabrik-reviewer | 2104 | 2104 | 2023 (96%) | 2003 | **95%** | 673 (31%) |
| no-workflow-hub | 151 | 151 | 121 (80%) | 139 | **92%** | 10 (6%) |
| orient | 361 | 361 | 361 (100%) | 277 | **76%** | 33 (9%) |
| review-probe-catalogue | 6908 | 6908 | 6902 (99%) | 5059 | **73%** | 1406 (20%) |
| run-record | 665 | 665 | 585 (87%) | 615 | **92%** | 97 (14%) |

Entries by class before (v3) → after (v4), reworded/total:

| **total** | 16463 | 16463 | 15675 (95%) | 13364 | **81%** | 3200 |

| file | entries v3 → v4 | classes v3 | classes v4 | reworded / total (baseline-keyed) | clause+line narrative labels |
|---|---|---|---|---|---|
| close-chain | 9 → 8 | {'ban': 3, 'grammar': 1, 'prose': 5} | {'ban': 4, 'grammar': 1, 'prose': 3} | 4 / 8 | 0 |
| close-feedback | 65 → 65 | {'ban': 19, 'grammar': 5, 'prose': 41} | {'ban': 19, 'grammar': 4, 'prose': 42} | 44 / 65 | 6 |
| fabrik-gui | 19 → 14 | {'ban': 7, 'grammar': 2, 'prose': 10} | {'ban': 4, 'grammar': 2, 'prose': 8} | 4 / 12 | 1 |
| fabrik-researcher | 75 → 76 | {'ban': 23, 'grammar': 11, 'prose': 41} | {'ban': 24, 'grammar': 10, 'prose': 42} | 51 / 63 | 2 |
| fabrik-reviewer | 39 → 34 | {'ban': 13, 'grammar': 7, 'prose': 19} | {'ban': 11, 'grammar': 7, 'prose': 16} | 17 / 27 | 1 |
| no-workflow-hub | 4 → 3 | {'ban': 3, 'prose': 1} | {'ban': 1, 'prose': 2} | 1 / 3 | 0 |
| orient | 8 → 8 | {'ban': 3, 'grammar': 2, 'prose': 3} | {'ban': 3, 'grammar': 1, 'prose': 4} | 7 / 8 | 3 |

### Why no file reaches 50% (the floor, measured)

A ban clause stays verbatim from its ban word to the end of its clause (D-1236/D-1240); a kept non-ban clause must hold every anchor and ≥6 of its first 8 content stems; text pinned by kept tests stays as pinned. Summed over the nine files:

| file | baseline unit words | ban V-span (verbatim) | non-ban clauses: count, minimum words (anchors + 6/8 stems) | pinned by kept tests (clause words) | v4 own text |
|---|---|---|---|---|---|
| close-chain | 473 | 58 | 18 clauses, ~126 | 142 | 475 |
| close-feedback | 2429 | 419 | 106 clauses, ~739 | 203 | 2023 |
| fabrik-gui | 546 | 90 | 30 clauses, ~179 | 0 | 598 |
| fabrik-researcher | 2505 | 414 | 114 clauses, ~698 | 159 | 2175 |
| fabrik-reviewer | 1959 | 673 | 70 clauses, ~416 | 532 | 2003 |
| no-workflow-hub | 151 | 10 | 5 clauses, ~39 | 13 | 139 |
| orient | 362 | 33 | 19 clauses, ~143 | 14 | 277 |
| review-probe-catalogue | 6870 | 1406 | 204 clauses, ~1232 | 520 | 5059 |
| run-record | 663 | 97 | 33 clauses, ~250 | 144 | 615 |
| **total** | 15958 | 3200 | 599 clauses, ~3822 | 1727 | 13364 |

Ban V-spans (3,200) + non-ban minimum (~3,822) + ban prefixes ≈ 48% of the baseline words is the strict mechanical floor *before* the test-pinned wording and the cross-file quotes; a mechanical cutter at that floor was built and rejected (it garbled the prose to ~70% overall and broke pinned phrases). v4 is a quality-first rewrite, so every clause over its minimum is kept for a stated reason in one of three classes: (a) test-pinned or cross-file-quoted wording (counted in the 'pinned' column); (b) qualifiers an independent audit found were dropped and restored (catalogue L35, L45, L54, L56, L66; close-feedback; researcher; reviewer; gui; close-chain); (c) bold labels, literal newlines and single-line paragraph shapes the tests hold. The remaining gap to 50% (~4,300 words) is clause-by-clause prose compression that needs the hub's decision on D-1236 point 1 (ban clauses carrying whole sentences), not more cutting here.

### Class changes and carried decisions
- Three v3 `grammar` entries (cf-32, rsr-L68, rr-step-each-phase) were not restored verbatim: classes moved to `prose` where their clauses were re-covered by anchors+stems (see the class table: close-feedback grammar 5→4, researcher 11→10, orient 2→1, run-record 3→2). Hub to confirm or restore.
- Eight retired pin tests were deleted per D-1236 step 7 (3 in `tests/test_review_queue_pass.py`, 5 in `tests/test_review_scoped_queue_pass.py`); each was listed under its ledger `pins:`.

### Self-audit
Three fresh audit seats (four checks LOST/WEAKER/INVENTED/WRONG-VANISHED-LABEL) over all nine files. Catalogue audit: lost 28 / weaker 8; the five most consequential were restored in this pass (L35 trigger, L54 removal conditions, L56 fix's-own-path and heading-grep rules, L66 same-hunk option); the minor qualifier drops they list (e.g. L4, L15, L26, L27, L47, L60) are within the 70% rule and are left. The other six files' findings were restored (commits per file). `COUNTS: entries read 239 / reworded ~190 / weaker 8 (catalogue, minor ones left) / lost 23 (catalogue, minor tails left; others 0 after restore) / invented 0 / wrong vanished labels 0` — NOT zeros: the catalogue's remaining minor tails are an open item for the hub.

### Reader tests (58 test files referencing the nine files)
Start (v3): 62 FAILED/ERROR lines (clone has no box services). End (v4): 62, `comm -13` of the two sets empty — no node new.

## Fix pass v5 (branch claude/lean-t01d-v5, cloud worker; base v4 131da325e)

OWN TEXT: 16463 -> 15150 (92%)

v5 does not cut further (the hub accepts the ~55% floor); it makes v4 mergeable under master's stricter loader and clears every item v4's self-audit left. Loader swap to master 545817887 is its own commit (`commands/command_rules.py`, `tests/test_command_rules.py`, `docs/reference/command-corpus-check.md`, never edited afterwards).

### Per-file words (`wc -w`, v4 -> v5)

| file | start | v4 | v5 | v5 % of start |
|---|---|---|---|---|
| close-chain | 473 | 475 | 461 | 97% |
| close-feedback | 2436 | 2023 | 2173 | 89% |
| fabrik-gui | 637 | 598 | 599 | 94% |
| fabrik-researcher | 2728 | 2175 | 2370 | 87% |
| fabrik-reviewer | 2104 | 2003 | 2019 | 96% |
| no-workflow-hub | 151 | 139 | 147 | 97% |
| orient | 361 | 277 | 332 | 92% |
| review-probe-catalogue | 6908 | 5059 | 6404 | 93% |
| run-record | 665 | 615 | 645 | 97% |
| **total** | 16463 | 13364 | 15150 | **92%** |

The words rise from v4 because every audit leftover, "minor tails" and the articles inside ban clauses included, is restored verbatim; D-1240's shortest wording is used where a clause is reworded.

### LOSS under master's loader: 0
`python3 commands/assemble_commands.py --check` prints no LOSS line (rc 1 is DRIFT only: the clone has no installed `/root/.claude` corpus). `tests/test_command_rules.py`: 54 passed, 3 skipped (v4's loader copy: 50 passed). The two LOSS lines master's loader printed on v4 are cleared:
- `close-feedback.yaml cf-17`: ban clause "REFUSED at the close exactly like the unkeyed one" restored, with the "it was not, until 2026-09-15, …" clause.
- `orient.yaml or-fence`: the fenced block restored verbatim (comments included), class `grammar`.

### Restored items
- Catalogue (audit round 1: 146 lost incl. 44 examples/rationale on 45 of 70 baseline lines, 7 weaker, 2 invented): L4, L15, L26, L27, L47, L60 and every other line the audit listed (L6, L9, L13, L24, L33, L34, L35, L45, L56-L59, L62, L66, L68-L70 …) restored; the two invented sentences (`env -C … python -P -B`, "copy a gitignored GENERATED file") deleted with their entries (commit 72a70af added them, no kept test pins them). Round 2 restored the 14 qualifiers, 9 weaker items and the articles inside all ban spans; round 3 the 7 optional meaning restores and the two spurious `vanished:` keys (L4, L56).
- close-feedback: cf-2/L3, cf-18, cf-72, cf-19, cf-20, cf-66, cf-23, cf-68, cf-29, cf-31, cat-L38, cf-33, cf-35, cf-39, cat-L49, cf-42, cf-46, cf-64, cf-47, cf-60, cf-61, cf-21, cf-17, cf-71, cf-4, cf-65 (`current:`), plus ledger entries for L8, L50, L73; stale `vanished:` label L39 deleted.
- close-chain: row count, "still sees it", entry for L6. run-record: "here too", hub-copy warning and evidence parenthetical, "the machinery friction", entries for L7, L8, L11, L21; stale `vanished:` L6 deleted. no-workflow-hub: "a relaunch, a wave", "account switch's", entry L1. orient: "(D-335 § 5 item 7)", L5-L9 qualifiers, `Right after`, the or-cobra consequence clause; gui: duplicated "(spec D8)" removed, L16 budget clause, L4, L8; reviewer: L1, L4, L7, L8, L11, L19, L22, L31, V1-V3; researcher: 18 lost, 14 weaker, W1/W4-1, R1-R9 (incl. rsr-L26 narrative label dropped, anchors restored).

### The four grammar entries
Restored verbatim with `class: grammar` (v3 text): `cf-32`, `rsr-L68` (with its tail "not a contradiction to fight" and parenthetical), `rr-step-each-phase`; `or-fence` is also `grammar`. No D-row is minted here; the hub owns class changes.

### Self-audit
Four fresh-subagent passes (LOST / WEAKER / INVENTED / WRONG-VANISHED-LABEL, baseline own text vs rewrite vs ledger; word-level diffs, ban spans checked to the end of their `;`/`—` clause). Findings per round, catalogue / the other eight: round 1 146+24 lost, round 2 14+1, round 3 0+1 (borderline); round 4 (after the round-3 fixes) found nothing in either set. A final rewrap of six lines over 120 columns restored a kept test's cap (`test_own_fix_guards_helper_contracts_and_pinned_versions`).

COUNTS: entries read 237+62 / lost 0 / weaker 0 / invented 0 / wrong vanished labels 0

### Reader tests (58 test files naming the nine stems or globbing corpus dirs, clone as root)
Start (v4): 62 FAILED/ERROR lines; End (v5): 62, `comm -13` of the two sets empty — no node new. The set is the clone's missing box services/psutil, and `tests/test_scrape_ledger.py` fails to collect in both.
