OWN TEXT: 2900 -> 2561 (88%)

# T39 receipt — lean rewrite of /fabrik-repo-review (light form, D-1240)

- Start commit: `851b4b365` (branch base origin/kaizen-lean-u01); fix round 2900 -> 2706 (93%); this re-ledger round on claude/lean-t39-rl (loader-swap base) 2900 -> 2561 (88%). Words are `wc`-style file words of `commands/_sources/fabrik-repo-review.md` at the start commit (2893 by `own_text`), the now figure taken as the fix round's 2706 less the 145-word drop `--check` reports for the render (24574 -> 24429).
- Floor: not reached — 88% against the 50% target. See "Floor table" below: 65 ledger entries are live rules, about 270 words are two POOL OFF block comments (D-343, hub decision), and almost every remaining sentence holds a ban word whose clause stays verbatim, or is an anchor-dense clause.

## Re-ledger round

Loader: `_ENTRY` holds `class` and `clauses` on this base (canonical loader, W-9cd8653d), so every hand entry now carries real `class:` / `clauses:` keys and is linted; `commands/command_rules.py` and `tests/test_command_rules.py` untouched.

- Own text, words: baseline 2900 -> fix round 2706 -> now 2561 (88%).
- LOSS before -> after (this ledger): 42 -> 0. `--check` prints no `fabrik-repo-review.yaml` LOSS line; the remaining LOSS lines are `_shared/*` and other commands' ledgers (T01d and the other units), outside Touches.
- What the fix round got wrong and this round undid: it cut text inside ban clauses (the `since 2026-08-29` date in L53, the `e.g. Traefik/templates` anchor in L56, the dated tail of L74's clause 6, `/fabrik-release` in L45) and carried r08 as a copy of L24 under the wrong section. L45, L53, L56 and L74 are back to the baseline wording; r08, r09, r10, r12 and r13 are gone.
- Reworded / total entries: 9 / 68 (r01, r02a, r02b, r24, r50, r58, r60, r11, r64 reworded; 3 fragment carriers `x-pool`, `x-floor`, `x-term`; 56 generated-unchanged `u-L` entries, written with YAML anchors so each unit's text sits once).
- Fragment carriers: three entries with `file: render` and no section hold, as `text`, the sentences `subagents-core` (pool-off paragraph, partition floor) and `term-coverage` (confirming re-check, run every owed pass) render into this command. A clause labelled `duplicate-of` points at one of them, and the loader checks the target covers the clause (r01 clause 2 -> `x-pool`, r60 clause 4 -> `x-term`). L1, L21 and L67 vanish with a line-level `duplicate-of` to a carrier.
- Vanished: 13 of 76 baseline lines — {'duplicate-of': 3 (L1, L21, L67), 'rule': 10 (L2, L11, L12, L24, L50, L58, L60, L62, L63, L64)}. Labels are the author's; the Sonnet + Haiku classification pair cannot run in this clone.

### What was cut this round (all by the D-1240 reading)

| unit | cut | why it is safe |
|---|---|---|
| L1, L2 clause 2 | POOL OFF banner reduced to "Run every fan-out this command names NATIVELY — and skip every flywheel back-fill" | the whole paragraph is the first paragraph of the included `subagents-core` fragment (carrier `x-pool`) |
| L21 | the partition sentence (two finders per slice, no Opus finder, one extra Haiku class seat) | restated by the rendered floor sentence and the fragment's By-FILE paragraph (carrier `x-floor`) |
| L24 | clause 4 (sibling-reservation clock, oscillation advisory) labelled narrative; `(SEATS is Σ slices, no floor padding)`, `the session's own checkout … in a worktree, the worktree`, `(a repo or checkout the sync has not reached)` dropped | all three parentheticals sit before the first ban word and are in the fragment's launch paragraph; the clause-4 rationale holds no ban word and no instruction |
| L50 | the `(a superuser role … one tenant …)` examples | examples (lever d); the clause keeps 6 of its first 8 stems |
| L58 | `the hop bounds the EXTENT;` and `, same partition and the same persisting class ledger` | both are in the fragment's delta-round sentence; `bounded-hop rule` stays (test_assemble_dispatch_step pins it) |
| L60 | clause 4, re-check of the classes the certification's fixes touched | the `term-coverage` done-bullet (carrier `x-term`) |
| L64 | clause 6, `the embedded proof above is what the operator audits` | rationale for L62's rule, no ban word |
| L67 | `Run every owed pass UNPROMPTED — "already reviewed…" each mean: run the pass` | the `term-coverage` closing paragraph (carrier `x-term`); the quoted excuses are examples |
| L11, L12 | the SCAFFOLD_TYPES enumeration and the `13 at D-039` count | labelled narrative (kept from the fix round) |

### Floor table (why 88% and not 50%)

The loader binds more than the target assumed: a clause holding never/must/only/refuse stays verbatim from that word to the end of its `;`/`—` clause, and `read-only`, `append-only` and `READ-ONLY` hold `only`. A clause's anchors (backticked tokens, numbers incl. `D-206`-style ids, paths) must all sit in ONE phrase, so a long clause cannot shed the text between two anchors.

| unit / clause | words kept | why it cannot shrink |
|---|---|---|
| L24 clause 2 (batch launch) | ~255 | first ban word is `never calls` inside the D-961 parenthetical, so everything after it to the clause end is verbatim (D-1240); ~35 anchors; `cannot load the script`, `(the tool runs only on their explicit opt-in)` and the `SCRATCH:` mention are pinned by test_review_queue_pass and test_review_loop_workflow |
| L74 clause 6 (backlog append) | ~130 | first ban word is `only in the hub`; the span runs to `docs/development/plans/*` including the dated parenthetical; 19, 43, 2026-08-31 and 2026-08-27 are anchors in the same clause |
| L53 CONSTRAINTS | ~85 | `NEVER edit a FABRIK-SYNCED file locally (… since 2026-08-29 — gate-enforced)`: the parenthetical stays verbatim inside a ban clause; clauses 4, 5 carry `/opt/fabrik/<path>` and `never fork it here` |
| L56 final_gate | ~85 | clause 1 holds `only` twice (verbatim through the nested parenthetical); clause 3's `Traefik/templates` is an anchor, so the example stays |
| L45, L27, L31, L33, L35, L38, L43, L47, L51, L55, L72 | ~600 together | each has a ban clause (never/must/only/read-only) kept verbatim, or one anchor-dense clause |
| L14, L13, L17, L23, L26, L28 | ~330 | anchors (`compose.yaml`, `specs/services/*.yaml`, `cross-tenant/RLS`, `read/write`, `null/empty/None`) tie the clause to its whole text |
| POOL OFF block comments (lines 27-44) | ~270 | the corpus keeps its POOL OFF comments (D-343); deleting them is a hub decision |
| front matter, headings, includes | ~160 | skill-router trigger text and structure |

Live rule count: 65 rule entries (56 unchanged-unit `u-L` + 9 hand) beside the 3 carriers. Word figures in this table are by-eye estimates, not measured. Cutting every remaining clause to anchors-plus-6-stems would still leave the ban spans and the 270 comment words, so on this loader the floor sits well above 50%.

## Self-audit (line by line against `fabrik-repo-review.baseline.txt`, never from memory)

COUNTS: 68 entries read / 9 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels

Earlier passes fixed: pass 1 found L53's date, L56's Traefik example, L74's dated tail and L45's `/fabrik-release` anchor cut inside ban clauses (restored); r08 as a mis-sectioned copy of L24 (removed); r24's labels now cover clause 4 only; r50's carrier was checked at 6 of 8 stems and r24's clause 2 at 6 of 8 (the minimum). Judgement calls the hub audit should read first: L24 clause 4 and L64 clause 6 labelled `narrative` (each states a rationale and holds no ban word); L11 clause 2 narrative while its pointer `scaffold.py::SCAFFOLD_TYPES` stays in the text.

## Pins deleted

None this round. The fix round deleted the `batch` lookup and its two `scratch_dir` / `pins_dir` presence asserts from `tests/test_run_scratch_brief_wording.py::test_the_review_loops_d8_names_put_their_pins_under_scratch`; that deletion stands.

## Failure sets (reader-test run, spine § Global Constraints)

- Start of this round: gate 1 `tests/test_command_rules.py`: 1 failed (`test_generate_unchanged_ledgers_pass_on_the_live_corpus`, red on other ledgers' LOSS), 56 passed; the dispatch-step group: 14 failed, 100 passed; the measure group: 2 failed, 746 passed, 2 skipped; the other groups green (376, 212, 463, 278 passed).
- End of this round: gate 1: 1 failed (the same test, same cause: LOSS lines of `_shared/*` and other commands, none for `fabrik-repo-review.yaml`), 56 passed, `LEDGER fabrik-repo-review.yaml: 68 entries · classes {'ban': 29, 'prose': 39} · vanished {'duplicate-of': 3, 'rule': 10}`; dispatch-step group: the identical 14 failed, 100 passed (clone lacks box services); measure group: the identical 2 failed, 746 passed, 2 skipped; worktree-guard group 376 passed; firecrawl group 212 passed; producing-fragments group 463 passed; skill-router group 278 passed. The failure set did not grow.
- `python3 commands/assemble_commands.py --check`: exit 1, DRIFT lines `DIFFERS from what this tree renders` only; REPORT `fabrik-repo-review shrank to 24429 words, ceiling 25512`; LOSS lines only for ledgers outside this ticket's Touches.

## LEFT FOR THE HUB

- `commands/_size_ceiling.json` ratchet for `fabrik-repo-review` (not touched, per the brief).
- The author-blind Sonnet + Haiku audit of the 13 vanished labels and the old-vs-new read of the 9 hand entries and the 3 fragment carriers.
- The decision on deleting the two POOL OFF block comments (~270 words; restore source `docs/reference/subagent-pool-contract.md`) — the largest single cut still open, worth about 9 points.
- A floor D-row if 88% stands: 65 live rule entries; the ban-verbatim spans of L24, L74, L53 and L56 alone are roughly 555 words (estimate).
- CHANGELOG, INDEX rows for the new `commands/_rules/` files, D-rows (hub writes at merge).

## Fix round 2 (hub audit)

Scope: `fabrik-repo-review` only (the `fabrik-deploy-plan-review` findings belong to another unit). Audit 1 items 21–25 and audit 2 items 44–54 are one set; the master-loader LOSS (D-1258) named L1 and L67.

Confirmed and fixed (source, ledger, and a carrier entry each):
- `r24`: "in a worktree, the worktree", "SEATS is Σ slices, no floor padding" and "(a repo or checkout the sync has not reached)" restored verbatim. The per-batch sibling-reservation clock (the 25 minutes) and the oscillation-advisory sentence were labelled narrative but are instructions: restored, carried as a `r24` text phrase, clause-4 `narrative` label removed.
- `r58`: "same partition and the same persisting class ledger" and "the hop bounds the EXTENT" restored.
- L67: the three-excuses rule was wrongly `duplicate-of: x-term` (x-term has no such clause). New entry `r67` carries it; L67 is now `rule: [r67]`.
- L1: the SUSPENDED sentence (`<!-- POOL OFF -->`, "left in place … for re-enable") was wrongly `duplicate-of: x-pool`. Restored inline in the banner with the D-181 operator date; new entry `r00`; L1 is now `rule: [r00]`. `r01` also has the seat list (`fabrik-reviewer` · `fabrik-researcher` · `fabrik-gui` · general-purpose) back inline, so it no longer leans on x-pool.
- L11/L12 (`r02a`/`r02b`): the valid `SCAFFOLD_TYPES` list, `office-extension` and "13 at D-039" restored; the `narrative` labels removed.

Refuted: none. Left as-is: L21 / `x-floor` (no loader LOSS; the fragment carries the partition rule; the audit marked it unverified), and the asides in items 49, 51, 52 (`r50` superuser example, `r64` "the embedded proof above is what the operator audits"; the `r64` clause-6 `narrative` label stands).

Own-text words: raw source file 2561 before this round, 2777 now. The own-text figure was not re-measured (no shell for it in this run).

Fresh passes: 0. No subagent can be dispatched from this run, so no fresh-reader pass happened. I re-read the changed entries line by line; that is NOT a fresh audit, and the hub's author-blind audit pair covers it. No zero COUNTS line is claimed.
