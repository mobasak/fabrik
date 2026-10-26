OWN TEXT: 1873 -> 1411 (75%)

# T19 receipt — lean rewrite of /fabrik-features

- **Start commit:** `851b4b365cc9ccaac91ed851bc669764743ad360` (baseline written from its text; `fabrik-features.baseline.txt` sha256 in the ledger)
- **Own-text words:** 1873 → 1750 (93% of baseline; target ≤50%). **Floor named below.**
- **Ledger entries:** 61 total = 53 generated-unchanged (`u-L<n>`, `generate_unchanged`) + 8 reworded (`r-L<n>`, hand-covered). Reworded / total = 8/61.
- **By class (D-1236 tag, set at baseline):** unchanged {'prose': 34, 'ban': 15, 'behavioural': 4} · reworded {'prose': 4, 'ban': 2, 'behavioural': 2}. The tag is a `# class:` YAML comment (the loader on this base has no `class` key).
- **Vanished baseline lines:** 10 = 8 `rule:` (covered by a reworded entry) + 2 `narrative` (every clause labelled narrative). 11 clauses inside the `rule:` lines are labelled narrative, recorded per entry as a `# clauses:` comment.
- **Labels:** author labels — audit owed (the Sonnet + Haiku classification seats cannot run in this clone).
- **Audit weaker-count:** not run — the author-blind audit pair cannot run in this clone, so every `rule`/`narrative` label above is an author label and the weaker-count is owed by the audit (reworded entries / total entries are stated above).
- **Coverage rule applied by hand (D-1240):** per clause (split at `;`/`—`, outside code spans) ONE `text` phrase holds 100% of the clause's anchors (backticked tokens, numbers, paths, ban words) and ≥70% of its first 8 content-word stems; a clause holding never/must/only/refus* is verbatim from that word to the end of its clause and is never labelled narrative; the carrier holds the same ban token; every phrase is ≥6 normalised words and unique in the file. Checked by a scratch script (not committed; `commands/command_rules.py` was not edited).

## Floor
Measured on the start-commit text (clauses split at `;`/`—` outside code spans): of 1873 words, 207 sit in ban-clause tails kept verbatim by D-1240, 124 in the heads of those clauses, 626 in non-ban clauses with backticked tokens, numbers or paths, and 708 in clauses with neither. The pass dropped 11 narrative clauses and 2 whole lines (the restated guardrail, the public-documentation remark, rationale tails) and kept the two-mode (EARLY / REFRESH / scoped REFRESH) contract, the reconciliation rules and the guardrails, each an instruction with tokens or a never-clause. Result 93% of baseline, not 50%. The unanchored 708 words are the rule statements of the Phase 2 reconciliation and the Guardrails list, which are not narrative; cutting them would delete rules, so a floor D-row is owed rather than a deeper cut.

## Reworded entries — clause count and how each clause is covered

| entry | class | clauses | coverage (P = covered by phrase n of the entry · N = narrative label) |
|---|---|---|---|
| r-L6 | prose | 2 | 1:N 2:P1 |
| r-L14 | ban | 3 | 1:P1 2:N 3:P2 |
| r-L19 | behavioural | 2 | 1:P1 2:N |
| r-L23 | ban | 2 | 1:P1 2:P2 |
| r-L35 | prose | 2 | 1:P1 2:N |
| r-L65 | prose | 2 | 1:P1 2:N |
| r-L67 | behavioural | 2 | 1:P1 2:N |
| r-L68 | prose | 2 | 1:P1 2:N |

## Lines labelled narrative (whole unit)

- L51: ## Phase 2 — Reconcile bidirectionally + make every row EXERCISABLE ¦ This file doubles as public feature documentation — write for the customer, cite for the a
- L66: ## Guardrails — never ¦ Leave a `README`/`QUICKSTART` claim unmapped — vapor claims are findings, not decoration

## Clauses labelled narrative inside reworded lines

- L6.1: This command's own guardrail says the same thing: *the CODE is the denominator
- L14.2: on a tree other agents commit to, a line moves before the plan reads it
- L19.2: those rows were written before the plan's final review fixed the code under them
- L35.2: each is a user-visible capability ("sends receipts", "full-text search")
- L51.1: This file doubles as public feature documentation
- L51.2: write for the customer, cite for the agent
- L65.2: a removed feature is stated in the run report (the operator may be tracking it)
- L66.1: Leave a `README`/`QUICKSTART` claim unmapped
- L66.2: vapor claims are findings, not decoration
- L67.2: certification takes the full one
- L68.2: an unconverged cross-check silently shrinks the gauntlet

## Pins deleted
none — no Touches test went red (`tests/test_features_queue_pass.py`), so no assert was deleted and no `pins:` node recorded.

## Failure sets (reader-test run, `capped_run.sh` unavailable in the clone: plain pytest)
Targeted run on the real tree: `tests/test_features_queue_pass.py tests/test_command_rules.py`: 38 passed, 3 skipped, 0 failed.

**Final run (all five tickets applied, tree at the last commit):** the same reader set (65 test files) plus `tests/test_command_rules.py`, plain `python3 -m pytest` with `.git` present in the scratch copy: 53 failed + 2 collection errors = **55, the identical set to the start commit** (`comm` of the sorted FAILED/ERROR node ids: 0 new, 0 gone). The first full run of the finished tree had found 4 new reds (all `/fabrik-plan-review` drops pinned outside any Touches test: the EXTRACT after-text block, a digest-grammar clause, the `/fabrik-generate-tests` mention); the three clauses were restored in the fix commit and the second full run is the one reported here. The pre-existing 55 are box-service or optional-dependency reds, unchanged by this batch.

## LEFT FOR THE HUB
- CHANGELOG.md, INDEX.md rows for the new `commands/_rules/` files, the `commands/_size_ceiling.json` ratchet and the render at merge.

## Re-ledger round (canonical loader, W-9cd8653d / D-1245)

- **Own-text words (whole file, `wc -w`):** baseline 1873 -> fix round 1750 (93%) -> now 1411 (75%). The 50% target is NOT reached; the floor is named below. The front matter (two long lines, not a baseline unit) was left alone.
- **LOSS for `fabrik-features.yaml`:** before 1 (`r-L14` lint B), after 0 (`--check` prints no `LOSS fabrik-features` line; `test_command_rules.py -rP` prints `LEDGER fabrik-features.yaml: 54 entries`). The LOSS lines that remain belong to other tickets' and `_shared/` ledgers.
- **Reworded / total entries:** 29 / 54 (25 unchanged `u-L<n>`, 29 reworded `r-L<n>`). Classes {ban 17, behavioural 1, prose 36}. The `# class:` / `# clauses:` comments are now real `class:` / `clauses:` keys.
- **Vanished:** 38 baseline lines = 31 `rule`, 4 `duplicate-of` (L53 -> u-L60, L56 -> r-L55, L62 -> u-L29, L66 -> u-L36), 3 `narrative` (L3, L6, L51). Clause labels: `narrative` on r-L2.1, r-L14.2, r-L18.3-4, r-L19.2, r-L23.2, r-L34.2, r-L35.2, r-L37.1, r-L63.2, r-L68.2; `duplicate-of` on r-L14.3 -> r-L19, r-L59.2 -> u-L27, r-L64.2 -> r-L45. No clause holding a ban word is labelled.
- **Changed from the fix round:** L65 and L67 were rewordings carried by r-L65 / r-L67; both are now `vanished` rules pointing at the carriers of the ban (L65 -> r-L17 `never silently delete` and u-L42 `state the removal`; L67 -> r-L23 `never hands off to certification`). L66 was `narrative` and is now `duplicate-of u-L36`. The guardrail list is cut from 7 items to 3 (L62, L65, L66, L67 now live in Phases 0-2).
- **Class retags (hub: confirm by D-row if the tag is held immutable):** the fix round tagged L12, L15, L19, L63 and L67 `behavioural`; their pins were string-in-file tests, not tests of emitted output, so the reworded entries r-L12, r-L15, r-L19, r-L63 are `prose`. u-L43 stays `behavioural` (verbatim, uncut).
- **Pins deleted (own command, `tests/test_features_queue_pass.py`):** the guardrail assert `Hand off to certification from a scoped REFRESH` (L67 is carried by r-L23). The two bullet anchors of `test_a_planned_row_quotes_every_condition_of_its_spec_clause` were re-pointed to the new bullet heads (`- **EARLY**`, `- **REFRESH** (post-build`). No `pins:` node is listed: no whole test was retired.
- **COUNTS: 54 entries read / 29 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels** (weaker read formally per D-1240: every anchor held, at least 70% of the first 8 stems in one phrase, ban clauses verbatim to their clause end). Earlier passes fixed: r-L21 dropped the anchor `Given/When/Then` (restored as `(Given/When/Then rows)`); the L65/L66/L67 labels named no carrier of the dropped words (relabelled above); a `duplicate-of r-L20` for L26's second clause failed the 70% reading (clause restored, entry back to unchanged u-L26). Self-audit only: no author-blind pass could run in this clone.

## Floor (why 75%, not 50%)

Every one of the 54 entries is live rule text: ban clauses stand verbatim from the ban word to the end of their `;`/`—` clause (u-L5, r-L11, r-L13 whose `only`/`never` span runs to the end of its sentence, r-L17, r-L55, u-L41, u-L47-49, u-L60), and each other clause keeps its backticked anchors plus at least 6 of its first 8 stems. The levers used: narrative/restatement deletes (L3, L6, L51, L53, L56, L62, L65-L67 and the tails of L2, L14, L18, L19, L23, L34, L35, L37, L63, L68) and compression of reworded clauses. What is left over 50% is the ban-clause floor plus the front matter; cutting further would delete rules. Thin but formally covered rewordings for the author-blind audit to read: r-L11 (drops "minted by the spec approval ... rows here transcribe it"), r-L17 (drops "an EARLY symbol of the code it extended is not the new endpoint" and "honest addition"), r-L18 (c3/c4 labelled narrative as restated CLAUDE.md § EXIT / the decision ledger), r-L57 (drops "sample the old"), r-L24 (drops "then reconcile", "the code outranks the spec once it exists").

## Gates (this clone; no box services)
The start failure set was not captured (the first reader-test run overlapped my first edits). End: features/queue group 406 passed, 2 skipped; fragments/review group 459 passed; spec-lane group 40 passed; corpus/feedback group 413 passed; `test_command_rules.py` 56 passed, 1 failed (`test_the_live_corpus_has_no_lo0`: other tickets' ledgers, none `fabrik-features`); dispatch/agents group 14 failed (symlink-orphan, FIFO and `git grep` tests, no `.git` in the clone); improve/measure group 573 passed, 2 failed (`test_check_exit_order_loss_then_ceiling_then_drift`: other ledgers' LOSS; `test_the_two_live_box_tests_pass_a_merge_check_on_a_drifted_box`: box). None reads a line of `fabrik-features`.

## LEFT FOR THE HUB (re-ledger)
- The 50% target is not met (75%). Class retags (behavioural -> prose) on r-L12, r-L15, r-L19, r-L63. The `commands/_size_ceiling.json` ratchet and the render at merge.

## Fix round 2 (hub audit)

**Findings.** All 18 Sonnet and 19 Haiku findings were checked against the baseline lines and confirmed. None was refuted (the two reports overlap and were treated as pairs).

**Fixed by restoring the baseline wording in `commands/_sources/fabrik-features.md`, with a matching carrier in the ledger:**
- `r-L4`: the trigger "whose source resolves to a doc" and the quoted "FEATURES.md documents what the project BUILT" half.
- `r-L11`: "the decision itself was MINTED by the spec approval's … rows here transcribe it".
- `r-L14` clause 3: "and the plan re-grounds it" is now carried by `r-L14` itself. The `duplicate-of: r-L19` label was wrong, because `r-L19` covers `## Deltas` rows only.
- `r-L15`: "(a hub item is not in a project's store)".
- `r-L17`: "fill or re-ground … + how-to-exercise — an EARLY symbol … is not the new endpoint", and "scope creep or an honest addition".
- `r-L18`: the stage-and-commit step and the classify-at-mint step. These were wrongly labelled narrative.
- `r-L21`: "several … can map to one".
- `r-L23`: "certification takes the full REFRESH". The ledger label for it was wrongly `narrative`.
- `r-L24`: "first, then reconcile", "the code outranks the spec once it exists" and "in the same file".
- `r-L25`: "that template IS the canonical shape: category sections".
- `r-L34`, `r-L35`: "every screen a user reaches is a feature surface", "storage, search", and "each is a user-visible capability". These were wrongly labelled narrative.
- `r-L45`: both glosses.
- `r-L55` and `L56`: the population sources and the two re-sweep questions. `L56` is now labelled `rule: [r-L55]`.
- `r-L57`: "sample the old".
- `r-L59`: the "no row contradicts …" check is back in the Phase 3 consistency item. The `duplicate-of: u-L27` label was wrong, because `u-L27` is a Phase 0 read step.
- `L51`: restored as `r-L51` ("write for the customer, cite for the agent").
- `L53`: restored as `r-L53`.
- `L62`, `L65`, `L66`, `L67`: restored as guardrail entries `r-L62`, `r-L65`, `r-L66`, `r-L67`. This also cures the D-1258 LOSS lines and the Haiku finding that the `L65` label narrowed the silent-delete ban to Planned rows.

**Ledger.** LOSS lines for `fabrik-features.yaml`: 0. `test_command_rules.py -rP` shows `LEDGER fabrik-features.yaml: 60 entries`. The one failing test there fails on other units' ledgers (for example `fabrik-plan-after-chat.yaml`), not this one. `--check` reports only `fabrik-features.md: DIFFERS` drift for this command.

**Words.** Own-text words (baseline → re-ledger → now): the exact count was not measured, because the shell here allows only the listed gate commands. The report line shows the rendered command at 23100 words. Both auditors estimated the previous rewrite at about 1,330–1,800 of about 1,900–2,300 body words; this round restores roughly 250–300 words of rules.

**Fresh passes.** No subagent can be dispatched in this run, so the zero-counts self-audit pass is NOT a fresh subagent. I checked each audit finding line by line against the baseline. The hub's author-blind audit pair covers the fresh pass.

COUNTS: entries read 60 / reworded 17 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0 (author line-by-line check; 0 fresh passes)
