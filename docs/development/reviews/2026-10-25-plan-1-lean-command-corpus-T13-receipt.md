# T13 receipt — lean rewrite of /fabrik-plan-after-chat

- **Start commit:** `851b4b365cc9ccaac91ed851bc669764743ad360` (baseline written from its text; `fabrik-plan-after-chat.baseline.txt` sha256 in the ledger)
- **Own-text words:** 12059 → 11660 (97% of baseline; target ≤50%). **Floor named below.**
- **Ledger entries:** 254 total = 236 generated-unchanged (`u-L<n>`, `generate_unchanged`) + 18 reworded (`r-L<n>`, hand-covered). Reworded / total = 18/254.
- **By class (D-1236 tag, set at baseline):** unchanged {'prose': 125, 'behavioural': 10, 'ban': 101} · reworded {'prose': 14, 'ban': 4}. The tag is a `# class:` YAML comment (the loader on this base has no `class` key).
- **Vanished baseline lines:** 27 = 18 `rule:` (covered by a reworded entry) + 9 `narrative` (every clause labelled narrative). 31 clauses inside the `rule:` lines are labelled narrative, recorded per entry as a `# clauses:` comment.
- **Labels:** author labels — audit owed (the Sonnet + Haiku classification seats cannot run in this clone).
- **Audit weaker-count:** not run — the author-blind audit pair cannot run in this clone, so every `rule`/`narrative` label above is an author label and the weaker-count is owed by the audit (reworded entries / total entries are stated above).
- **Coverage rule applied by hand (D-1240):** per clause (split at `;`/`—`, outside code spans) ONE `text` phrase holds 100% of the clause's anchors (backticked tokens, numbers, paths, ban words) and ≥70% of its first 8 content-word stems; a clause holding never/must/only/refus* is verbatim from that word to the end of its clause and is never labelled narrative; the carrier holds the same ban token; every phrase is ≥6 normalised words and unique in the file. Checked by a scratch script (not committed; `commands/command_rules.py` was not edited).

## Floor
Measured on the start-commit text (clauses split at `;`/`—` outside code spans): of 12059 words, 2199 sit in ban-clause tails kept verbatim by D-1240, 1627 in the heads of those clauses, 5402 in non-ban clauses with backticked tokens, numbers or paths, and 2358 in clauses with neither. This command is mostly gate grammar: the spine/ticket field contract (`check_plan_tickets`, `check_plan_quality` behaviours: one bullet of ~1200 words and one of ~980 words), the sizing arithmetic and the emit-gate semantics, each clause a parser or gate behaviour with its tokens. The pass dropped 30 narrative clauses and 9 whole lines (anecdotes, measured-incidence stories, rationale tails, pool-off history and inline comments, one rollout note) and restored the one narrative sentence (L239) a kept test uses as the end marker of a pinned span. Result 97% of baseline, not 50%: every other clause is an anchor-bearing instruction; reaching 50% needs the two grammar bullets moved to a ledgered fragment or a table the checkers can read, outside this unit and outside D-1240's per-clause rule. A floor D-row is owed.

## Reworded entries — clause count and how each clause is covered

| entry | class | clauses | coverage (P = covered by phrase n of the entry · N = narrative label) |
|---|---|---|---|
| r-L59 | prose | 2 | 1:P1 2:N |
| r-L109 | ban | 4 | 1:P1 2:P2 3:P3 4:N |
| r-L114 | ban | 2 | 1:P1 2:N |
| r-L117 | prose | 5 | 1:P1 2:N 3:N 4:P1 5:P2 |
| r-L119 | ban | 4 | 1:P1 2:N 3:N 4:P1 |
| r-L134 | prose | 2 | 1:P1 2:N |
| r-L146 | prose | 3 | 1:P1 2:P2 3:P3 |
| r-L154 | prose | 4 | 1:P1 2:N 3:N 4:N |
| r-L155 | prose | 3 | 1:P1 2:P2 3:P3 |
| r-L162 | ban | 2 | 1:P1 2:N |
| r-L192 | prose | 3 | 1:P1 2:P2 3:N |
| r-L208 | prose | 2 | 1:P1 2:N |
| r-L221 | prose | 2 | 1:P1 2:N |
| r-L246 | prose | 2 | 1:P1 2:N |
| r-L247 | prose | 2 | 1:P1 2:P2 |
| r-L250 | prose | 2 | 1:P1 2:N |
| r-L258 | prose | 3 | 1:P1 2:N 3:P2 |
| r-L271 | prose | 3 | 1:P1 2:P2 3:N |

## Lines labelled narrative (whole unit)

- L12: ## Phase 0 — Distill + richness check (the hybrid gate) ¦ No grader on the prose yet — measured after the first five spec-fed plans under the rule (backlog row 
- L16: ## Phase 0 — Distill + richness check (the hybrid gate) ¦ A chat-born or non-epic spec carries neither, and every epic clause below is simply absent
- L38: ## Phase 0 — Distill + richness check (the hybrid gate) ¦ A plan run that halts to ask "what should I name this folder?" is the exact defect this bar prevents
- L131: ## Phase 2 — Emit the plan (phases, dependency order, runnable gates) ¦ Both apply to plans dated on or after the rollout (older plans are not re-graded)
- L145: ## Phase 2 — Emit the plan (phases, dependency order, runnable gates) ¦ A bare exit 0 is byte-identical to a run that graded nothing, so citing it is the un-den
- L157: ## Phase 2 — Emit the plan (phases, dependency order, runnable gates) ¦ Canonical: `62-using-subagents.md` § Dispatch policy
- L171: ## Phase 2 — Emit the plan (phases, dependency order, runnable gates) ¦ Naming no policy leaves the executor without an author-blind floor.<!-- POOL OFF (D-181)
- L173: ## Phase 2 — Emit the plan (phases, dependency order, runnable gates) ¦ `## Merge Order` gives sequencing; this gives the fan-out semantics, which a topological
- L218: ## Phase 3 — Bake in the enforced pillars (review + subagents + parallelism) ¦ Not a one-line "review here" — the full methodology, and progression is gated on 

## Clauses labelled narrative inside reworded lines

- L12.1: No grader on the prose yet
- L12.2: measured after the first five spec-fed plans under the rule (backlog row of 2026-09-10)
- L16.1: A chat-born or non-epic spec carries neither, and every epic clause below is simply absent
- L38.1: A plan run that halts to ask "what should I name this folder?" is the exact defect this bar prevents
- L59.2: so deploy steps are correct and don't assume the project self-deploys
- L109.4: extract the fact, discard the directive
- L114.2: that is the exact mid-execution stall this preflight exists to prevent
- L117.2: UNCONDITIONAL, every run. Dispatch one INDEPENDENT native `fabrik-researcher` grounder per unit (the pool is OFF, D-181<!-- POOL OFF: `fanout("researc
- L117.3: recipe in § Subagents -->), an Opus `fabrik-researcher` for the authoritative verify-sample
- L119.2: measured, not assumed (1 seat found 0
- L119.3: 3 over the same surface found 0/5/0, and the 5 held a real fail-open
- L131.1: Both apply to plans dated on or after the rollout (older plans are not re-graded)
- L134.2: both shapes are first-class, no forced migration of old plans
- L145.1: A bare exit 0 is byte-identical to a run that graded nothing, so citing it is the un-denominated claim the bounded-search rule forbids
- L154.2: D-181 (operator, 2026-09-07). The OpenRouter subagent pool is OFF by operator ruling (D-181
- L154.3: mechanism revised by D-182
- L154.4: the provider credentials stay provisioned, so a `fanout` would still dispatch and SPEND: this text is the control), so every `fanout` / `pick_models` 
- L157.1: Canonical: `62-using-subagents.md` § Dispatch policy
- L162.2: scope decides the outcome, not intent
- L171.1: Naming no policy leaves the executor without an author-blind floor.<!-- POOL OFF (D-181): pool-default (`fanout(task_type, …)`, auto-records, `set_qua
- L173.1: `## Merge Order` gives sequencing
- L173.2: this gives the fan-out semantics, which a topological list cannot express
- L192.3: keep files focused (you reason best about code you can hold in context at once)
- L208.2: not left to a WARN
- L218.1: Not a one-line "review here"
- L218.2: the full methodology, and progression is gated on it
- L221.2: name it.<!-- POOL OFF (D-181): pre-D-181 text required POOL-DEFAULT via `fanout(task_type, units, …)` (auto-records, `set_quality` back-fill) with nat
- L246.2: a guessed name is worse than an honest dash
- L250.2: claiming it here would be premature (and `check_convergence.py` gates it)
- L258.2: its name is stable for the whole `fabrik-plan-after-chat → fabrik-plan-review → fabrik-execute-plan` pipeline
- L271.3: execution remains the user's call

## Pins deleted
none — one Touches test (`tests/test_plan_after_chat_queue_pass.py::test_every_count_names_the_command_that_printed_it`) went red because its span marker was the dropped sentence L239; that sentence was restored rather than the pin deleted. No assert was deleted; no `pins:` node.

## Failure sets (reader-test run, `capped_run.sh` unavailable in the clone: plain pytest)
Targeted run on the real tree: `tests/test_features_queue_pass.py tests/test_plan_after_chat_queue_pass.py tests/test_plan_review_queue_pass.py tests/test_spec_plan_lane_text.py tests/test_spec_queue_pass.py tests/test_command_rules.py`: 112 passed, 3 skipped, 0 failed. The full reader-set failure set (55 at the start commit) is re-run at the end of the batch and recorded in the T19 receipt.

**Final run (all five tickets applied, tree at the last commit):** the same reader set (65 test files) plus `tests/test_command_rules.py`, plain `python3 -m pytest` with `.git` present in the scratch copy: 53 failed + 2 collection errors = **55, the identical set to the start commit** (`comm` of the sorted FAILED/ERROR node ids: 0 new, 0 gone). The first full run of the finished tree had found 4 new reds (all `/fabrik-plan-review` drops pinned outside any Touches test: the EXTRACT after-text block, a digest-grammar clause, the `/fabrik-generate-tests` mention); the three clauses were restored in the fix commit and the second full run is the one reported here. The pre-existing 55 are box-service or optional-dependency reds, unchanged by this batch.

## LEFT FOR THE HUB
- CHANGELOG.md, INDEX.md rows for the new `commands/_rules/` files, the `commands/_size_ceiling.json` ratchet and the render at merge.
