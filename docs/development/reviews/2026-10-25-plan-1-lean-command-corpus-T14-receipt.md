# T14 receipt — lean rewrite of /fabrik-spec-review

- **Start commit:** `851b4b365cc9ccaac91ed851bc669764743ad360` (baseline written from its text; `fabrik-spec-review.baseline.txt` sha256 in the ledger)
- **Own-text words:** 4839 → 4661 (96% of baseline; target ≤50%). **Floor named below.**
- **Ledger entries:** 133 total = 126 generated-unchanged (`u-L<n>`, `generate_unchanged`) + 7 reworded (`r-L<n>`, hand-covered). Reworded / total = 7/133.
- **By class (D-1236 tag, set at baseline):** unchanged {'prose': 84, 'ban': 38, 'behavioural': 4} · reworded {'prose': 6, 'behavioural': 1}. The tag is a `# class:` YAML comment (the loader on this base has no `class` key).
- **Vanished baseline lines:** 9 = 7 `rule:` (covered by a reworded entry) + 2 `narrative` (every clause labelled narrative). 12 clauses inside the `rule:` lines are labelled narrative, recorded per entry as a `# clauses:` comment.
- **Labels:** author labels — audit owed (the Sonnet + Haiku classification seats cannot run in this clone).
- **Audit weaker-count:** not run — the author-blind audit pair cannot run in this clone, so every `rule`/`narrative` label above is an author label and the weaker-count is owed by the audit (reworded entries / total entries are stated above).
- **Coverage rule applied by hand (D-1240):** per clause (split at `;`/`—`, outside code spans) ONE `text` phrase holds 100% of the clause's anchors (backticked tokens, numbers, paths, ban words) and ≥70% of its first 8 content-word stems; a clause holding never/must/only/refus* is verbatim from that word to the end of its clause and is never labelled narrative; the carrier holds the same ban token; every phrase is ≥6 normalised words and unique in the file. Checked by a scratch script (not committed; `commands/command_rules.py` was not edited).

## Floor
Measured on the start-commit text (clauses split at `;`/`—` outside code spans): of 4839 words, 564 sit in ban-clause tails kept verbatim by D-1240, 482 in the heads of those clauses, 1865 in non-ban clauses with backticked tokens, numbers or paths, and 1664 in clauses with neither. The pass dropped 12 narrative clauses and 2 whole lines (the framing sentence, the live-incident anecdotes, the incidence statistic) and left every audit axis (A0, A0b, A-E), the 12-Factor audit table, the partition/`Workflow` mechanics and the approval-gate grammar, each of which is an anchor-bearing instruction. Result 96% of baseline, not 50%. Reaching 50% needs the partition/`Workflow` paragraph (703 words) and the liveness-oracle bullet, which `/fabrik-plan-review` repeats nearly word for word, moved into one ledgered fragment; D-1240's per-clause rule does not allow that inside this unit. A floor D-row is owed.

## Reworded entries — clause count and how each clause is covered

| entry | class | clauses | coverage (P = covered by phrase n of the entry · N = narrative label) |
|---|---|---|---|
| r-L1 | prose | 2 | 1:P1 2:N |
| r-L3 | prose | 4 | 1:P1 2:N 3:N 4:N |
| r-L14 | behavioural | 2 | 1:P1 2:N |
| r-L19 | prose | 3 | 1:P1 2:P2 3:P3 |
| r-L41 | prose | 2 | 1:P1 2:N |
| r-L48 | prose | 2 | 1:P1 2:P2 |
| r-L93 | prose | 3 | 1:P1 2:N 3:N |

## Lines labelled narrative (whole unit)

- L23: ## Phase 1 — Adversarial grounding to a fixed point (the section partition) ¦ This axis is the checking half of the authoring contract; without it the inventory
- L32: ## Phase 1 — Adversarial grounding to a fixed point (the section partition) ¦ Live 2026-08-27 (fabrik-lib): a WebFetch answer supplied a sentence that is nowher

## Clauses labelled narrative inside reworded lines

- L1.2: do not stop after one pass
- L3.2: and the two this pass exists to catch
- L3.3: are (1) an external fact taken from training memory or backed by a dead/hallucinated citation, and (2) a fabrik-lib verdict that reinvents what alread
- L3.4: both invisible until someone re-verifies against the real world
- L14.2: a Status-reading gate skips a DRAFT, so the unflipped spec passes over nothing
- L23.1: This axis is the checking half of the authoring contract
- L23.2: without it the inventory is graded by the agent it constrains
- L32.1: Live 2026-08-27 (fabrik-lib): a WebFetch answer supplied a sentence that is nowhere in the page AND inverted the mechanism it described
- L32.2: the fabricated quote survived the author's self-review and carried the spec's central build-vs-buy verdict
- L41.2: that file is a curated index, not a manifest (the same report found a leaked third-party planning doc inside one)
- L93.2: those four heal a TRANSIENT fault
- L93.3: a permanent provider death needs a SWAP no retry loop can make

## Pins deleted
none — no Touches test went red (`tests/test_spec_plan_lane_text.py tests/test_spec_queue_pass.py tests/test_spec_review_queue_pass.py`), so no assert was deleted and no `pins:` node recorded.

## Failure sets (reader-test run, `capped_run.sh` unavailable in the clone: plain pytest)
Targeted run on the real tree: `tests/test_spec_plan_lane_text.py tests/test_spec_queue_pass.py tests/test_spec_review_queue_pass.py tests/test_command_rules.py`: 77 passed, 3 skipped, 0 failed. The full reader-set failure set (55 at the start commit) is re-run at the end of the batch and recorded in the T19 receipt.

**Final run (all five tickets applied, tree at the last commit):** the same reader set (65 test files) plus `tests/test_command_rules.py`, plain `python3 -m pytest` with `.git` present in the scratch copy: 53 failed + 2 collection errors = **55, the identical set to the start commit** (`comm` of the sorted FAILED/ERROR node ids: 0 new, 0 gone). The first full run of the finished tree had found 4 new reds (all `/fabrik-plan-review` drops pinned outside any Touches test: the EXTRACT after-text block, a digest-grammar clause, the `/fabrik-generate-tests` mention); the three clauses were restored in the fix commit and the second full run is the one reported here. The pre-existing 55 are box-service or optional-dependency reds, unchanged by this batch.

## LEFT FOR THE HUB
- CHANGELOG.md, INDEX.md rows for the new `commands/_rules/` files, the `commands/_size_ceiling.json` ratchet and the render at merge.
