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
