OWN TEXT: 7347 -> 6472 (88%)

# T12 receipt — lean rewrite of /fabrik-plan-review

## Re-ledger round (canonical loader, W-9cd8653d / D-1245)

- **Own-text words (`wc -w` of the source, the measure the fix round used):** baseline 7347 → fix round 6652 (91%) → now 6472 (88%). Target ≤50% **not met**; floor below.
- **LOSS for `fabrik-plan-review.yaml`:** 12 lines on the base (r-L27, r-L28 ×2, r-L35, r-L48, r-L75, r-L84, r-L121 D+B, r-L141, r-L147, r-L184) → **0** (`assemble_commands.py --check`: no `fabrik-plan-review.yaml` LOSS line; the remaining LOSS lines are other commands' and `_shared/` ledgers, outside this ticket). Converting the 168 `# class:` and 28 `# clauses:` comments to real keys made every entry lintable, which is why the base showed only 12 and the keys surfaced more: stale clause numbers (the comments counted clauses the old way, the canonical loader does not split inside a parenthetical), junk carrier phrases (r-L47 carried L121/L20 text, r-L184 and r-L155 carried unrelated phrases) and a ban clause whose inline `<!-- POOL OFF … -->` text the fix round had dropped from the live source (r-L121 clause 5, restored word for word).
- **Reworded / total entries:** 35 / 167 (132 unchanged `u-L<n>` + 35 reworded `r-L<n>`). Classes now real keys: ban 75 · behavioural 15 · prose 77.
- **Vanished labels:** 45 = 35 `rule:` + 10 whole-line `narrative` (L36, L37, L49, L64, L67, L86, L94, L167, L175, L181).
- **COUNTS: 167 entries read / 35 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels** (my own line-by-line pass against `fabrik-plan-review.baseline.txt`; no seat can run here, so the hub's author-blind audit is still owed).
- **What the self-audit passes fixed before this line:** (1) eleven fix-round drops labelled `narrative` were operative instructions and went back into the live text: L5 "do not stop after one pass", L31 "Findings the checker raises are review findings: fix them in the set, don't route around the gate", L47 "The File Scope IS the changed-path set — glob matching works on it unmodified", L48 "The whole output is the default", L57 "coarser, same and finer for a lookup; every install layout the repo's docs teach for a path rule", L61 "YOUR audit owns whether the quotes are load-bearing rather than decorative", L75 "a dead or hallucinated citation is a defect", L143 "if any is missing from the plan, add it", L152 "call out explicitly which steps fan out and where the merge happens", L155 "add it", L147 "— can see it" (these units are verbatim again, `u-L5 u-L31 u-L46 u-L47 u-L48 u-L57 u-L61 u-L75 u-L143 u-L152 u-L155`); (2) r-L121's inline `<!-- POOL OFF … -->` restored for its ban clause; (3) stale `clauses:` numbers recomputed against the canonical splitter for every reworded entry; (4) junk phrases removed from r-L47/L48/L84/L119/L155/L184.
- **New cuts this round (−180 words net of the restorations, 6652 → 6472):** the "Why this command specifically" paragraph and the transdoc anecdote (L64, L65 clause 1, L66 clause 1 narrative; the ban tail of L66 and "only armed review" kept verbatim), the brand-identiy-creator incident (L88 clauses 1-2), the L37 measured basis, the L93 conformance-review tail, the L97 five-vs-seven history and `CHANGELOG.md` rationale, the L108 live-defect head, the L127 finder anecdote, the L144 consequence tail, the L160 grep rationale, the L162 decision-ledger aside, the L176 "lesson from a real run" frame.
- **Floor (why not ≤50%):** every remaining clause is one of: a ban clause (verbatim from its ban word to the end of its `;`/`—` clause — L24, L26, L28, L56, L72-76, L102-106, L112-115, L122, L126, L134, L137-139, L145, L148-149, L159, L163, L165, L173-174, L179-182; 75 of the 167 entries are ban-class), a clause whose backticked tokens, paths, commands and numbers must all survive (L7-L16 are additionally byte-pinned by `ac.EXTRACT`'s after-text and by `test_plan_review_small_gate.py`; the `Workflow`/ledger/round command lines L122-125 and the receipt grammar L129-130), or a behavioural-class unit (15 entries, every clause verbatim). What is left to compress is the non-anchor tail of instruction clauses; cutting it to "anchors + 6 of the first 8 stems" is formally allowed by D-1240 but deletes operative instruction words (e.g. "state which file you are grounding", "OPEN it and confirm the call site"), so it was not done here. Live rule count 167. A floor D-row is owed through Deltas if the hub wants the formal minimum instead.
- **Pins:** no test file edited this round — none of the cut sentences is pinned by `tests/test_plan_review_queue_pass.py`, `test_plan_review_recurring_rules.py`, `test_plan_review_small_gate.py`, `test_plan_after_chat_queue_pass.py` or `test_spec_review_queue_pass.py` (the pinned spans — set-hash recipe, PIN_IMPORT clause, substituted-test-value rule, closed-token field rule, script-mode clause, ledger-home sentence, small-spec section — are untouched).
- **Gates (start → end):** `test_command_rules.py` 1 failed / 56 passed → 1 failed / 56 passed (the failure is the corpus-wide LOSS assert, red on every ledger outside this ticket; this ledger prints `LEDGER fabrik-plan-review.yaml: 167 entries` with 0 LOSS); `--check` exit 4 (LOSS from other ledgers only, no DIFFERS/MISSING/ORPHAN beyond `fabrik-plan-review.md: DIFFERS`); flip-gate/dispatch set 13 failed / 132 passed → 13 failed / 132 passed (same orphan/installed-tree tests); orch-retired set 2 failed / 354 passed → same; feedback-report set 1 failed / 706 passed → same (`test_check_exit_order_loss_then_ceiling_then_drift`); conftest-isolation set 1 failed / 413 passed / 2 skipped → same; firecrawl set 264 passed → 264 passed; plan-review set 300 passed → 300 passed; skill-router set 278 passed → 278 passed; research-tier set 235 passed → 235 passed. Failure set did not grow.

### LEFT FOR THE HUB
- The author-blind audit pair (Sonnet + Haiku) on the 35 reworded entries and the 10 narrative lines.
- A floor D-row for T12 (167 live rules, 6472 words ≈ 39 words per rule) or a decision to apply the formal anchors-plus-6 compression.
- `CHANGELOG.md`, `INDEX.md`, the `commands/_size_ceiling.json` ratchet and the render at merge (unchanged from the fix round).

## Fix round (earlier, written for the old loader)

- **Start commit:** `851b4b365cc9ccaac91ed851bc669764743ad360` (baseline written from its text; `fabrik-plan-review.baseline.txt` sha256 in the ledger)
- **Own-text words:** 7347 → 6652 (91% of baseline; target ≤50%). **Floor named below.**
- **Ledger entries:** 168 total = 132 generated-unchanged (`u-L<n>`, `generate_unchanged`) + 36 reworded (`r-L<n>`, hand-covered). Reworded / total = 36/168.
- **By class (D-1236 tag, set at baseline):** unchanged {'ban': 63, 'prose': 57, 'behavioural': 12} · reworded {'prose': 21, 'ban': 12, 'behavioural': 3}. The tag is a `# class:` YAML comment (the loader on this base has no `class` key).
- **Vanished baseline lines:** 45 = 36 `rule:` (covered by a reworded entry) + 9 `narrative` (every clause labelled narrative). 49 clauses inside the `rule:` lines are labelled narrative, recorded per entry as a `# clauses:` comment.
- **Labels:** author labels — audit owed (the Sonnet + Haiku classification seats cannot run in this clone).
- **Audit weaker-count:** not run — the author-blind audit pair cannot run in this clone, so every `rule`/`narrative` label above is an author label and the weaker-count is owed by the audit (reworded entries / total entries are stated above).
- **Coverage rule applied by hand (D-1240):** per clause (split at `;`/`—`, outside code spans) ONE `text` phrase holds 100% of the clause's anchors (backticked tokens, numbers, paths, ban words) and ≥70% of its first 8 content-word stems; a clause holding never/must/only/refus* is verbatim from that word to the end of its clause and is never labelled narrative; the carrier holds the same ban token; every phrase is ≥6 normalised words and unique in the file. Checked by a scratch script (not committed; `commands/command_rules.py` was not edited).

## Floor
Measured on the start-commit text (clauses split at `;`/`—` outside code spans): of 7347 words, 1160 sit in ban-clause tails kept verbatim by D-1240, 806 in the heads of those clauses, 3039 in non-ban clauses with backticked tokens, numbers or paths (all anchors must survive) and 2044 in clauses with neither. The pass dropped what is explanatory or anecdotal (49 clauses and 9 whole lines labelled narrative: measured-incidence stories, live-defect anecdotes, rationale tails, the pool-off history and its inline comments) and nothing else; the remaining text is the seat/ledger/round mechanics (the partition and `Workflow` call, the pass-ledger and receipt grammar, the set-wide gates), each clause an anchor-bearing instruction. Result 91% of baseline, not 50%. Reaching 50% needs those mechanics moved into a fragment or re-expressed without their commands, which the per-clause coverage rule of D-1240 does not allow inside this unit; a floor D-row is owed. Three drops from the first pass were restored after the full reader-set run (Touches misses, outside this ticket's test files and never edited): the `[Flip preconditions …]` block and everything up to `{{include:design-critique}}` (byte-pinned by `ac.EXTRACT`'s after-text, `test_assemble_dispatch_step::test_every_extract_after_text_round_trips_against_its_source`), the digest-grammar clause (`tests/enforcement/test_rule_grounding.py`) and the `/fabrik-generate-tests` mention (`check_command_corpus.py` caller claim of `fabrik-generate-tests.md`).

## Reworded entries — clause count and how each clause is covered

| entry | class | clauses | coverage (P = covered by phrase n of the entry · N = narrative label) |
|---|---|---|---|
| r-L1 | prose | 4 | 1:P1 2:N 3:N 4:N |
| r-L2 | prose | 3 | 1:P1 2:P2 3:P3 |
| r-L5 | prose | 2 | 1:P1 2:N |
| r-L27 | ban | 2 | 1:P1 2:N |
| r-L28 | ban | 7 | 1:P1 2:P2 3:P3 4:P4 5:P5 6:N 7:P6 |
| r-L30 | prose | 2 | 1:P1 2:N |
| r-L35 | ban | 3 | 1:P1 2:N 3:P2 |
| r-L37 | prose | 3 | 1:P1 2:N 3:N |
| r-L39 | prose | 2 | 1:P1 2:N |
| r-L41 | prose | 2 | 1:P1 2:N |
| r-L42 | ban | 2 | 1:P1 2:P2 |
| r-L43 | prose | 2 | 1:N 2:P1 |
| r-L45 | prose | 2 | 1:P1 2:N |
| r-L46 | behavioural | 1 | 1:P1 |
| r-L47 | prose | 2 | 1:P1 2:P2 |
| r-L48 | ban | 3 | 1:N 2:P1 3:P2 |
| r-L52 | behavioural | 3 | 1:P1 2:P2 3:N |
| r-L57 | behavioural | 4 | 1:P1 2:N 3:N 4:P2 |
| r-L61 | prose | 2 | 1:P1 2:N |
| r-L75 | ban | 4 | 1:P1 2:P2 3:P3 4:N |
| r-L79 | prose | 2 | 1:P1 2:N |
| r-L84 | ban | 2 | 1:P1 2:P2 |
| r-L95 | prose | 2 | 1:P1 2:N |
| r-L100 | prose | 2 | 1:P1 2:N |
| r-L119 | prose | 3 | 1:P1 2:N 3:P2 |
| r-L121 | ban | 9 | 1:P1 2:P2 3:P3 4:P4 5:P5 6:N 7:N 8:P6 9:P7 |
| r-L141 | ban | 2 | 1:P1 2:N |
| r-L143 | prose | 2 | 1:P1 2:N |
| r-L147 | ban | 3 | 1:P1 2:P2 3:N |
| r-L151 | prose | 2 | 1:P1 2:N |
| r-L152 | prose | 2 | 1:P1 2:N |
| r-L155 | prose | 2 | 1:P1 2:P2 |
| r-L166 | prose | 2 | 1:P1 2:N |
| r-L171 | prose | 2 | 1:P1 2:N |
| r-L176 | ban | 2 | 1:P1 2:P2 |
| r-L184 | ban | 3 | 1:P1 2:P2 3:P3 |

## Lines labelled narrative (whole unit)

- L31: ## Phase 0 — Establish scope ¦ Findings the checker raises are review findings: fix them in the set, don't route around the gate
- L36: ## Phase 0 — Establish scope ¦ Each flagged ticket prints its components (Touches areas · Behavior-Contract rows · code+governance mix), a predicted round cost,
- L49: ## Phase 1 — Grounding passes (adversarial, to a fixed point) ¦ An un-armed reviewer works from whatever occurs to them; a rubric names the classes this surface
- L67: ## Phase 1 — Grounding passes (adversarial, to a fixed point) ¦ A checklist can still be filled without real hunting; it raises a floor, it does not guarantee a
- L86: ## Phase 1 — Grounding passes (adversarial, to a fixed point) ¦ Measured 2026-08-28 across 236 real tickets in the fleet: a mechanical "backticked symbol absent
- L94: ## Phase 1 — Grounding passes (adversarial, to a fixed point) ¦ Plan review is the last point where a dropped requirement costs a paragraph instead of a rebuild
- L167: ## Convergence & residuals ¦ A plan that converges with a deferred question is a plan that WILL stall `/fabrik-execute-plan` to ask the user (the exact failure 
- L175: ## Convergence & residuals ¦ (This is the lesson from a real run: a plan converged with "[OPEN → resolve the DSN with the coding-selection AI at Phase C start]"
- L181: ## Plan lifecycle — a FINISHED plan is ARCHIVED (not left in the active dir) ¦ A finished plan left in the active `docs/development/plans/` directory is clutter

## Clauses labelled narrative inside reworded lines

- L1.2: D-181 (operator, 2026-09-07). The OpenRouter subagent pool is OFF by operator ruling (D-181
- L1.3: mechanism revised by D-182
- L1.4: the provider credentials stay provisioned, so a `fanout` would still dispatch and SPEND: this text is the control), so every `fanout` / `pick_models` 
- L5.2: do not stop after one pass
- L27.2: author-blindness is the point of this command
- L28.6: so the precondition command above is the guarantee YOU own
- L30.2: the summary is what a convergence artifact can EMBED as proof
- L31.1: Findings the checker raises are review findings: fix them in the set, don't route around the gate
- L35.2: the output is what matters
- L36.1: Each flagged ticket prints its components (Touches areas · Behavior-Contract rows · code+governance mix), a predicted round cost, a concrete split, an
- L36.2: in the footer
- L36.3: its own measured accuracy
- L37.2: a 5-class ticket cost 8 rounds and 34 fixups
- L37.3: a one-line ticket cost 1 (`docs/reference/ticket-breadth.md`)
- L39.2: it is a screen, not a verdict, and roughly half of its flags are on tickets that turned out cheap
- L41.2: the threshold is provisional, your reasoning is the calibration signal
- L43.1: Test surfaces are excluded from the score for this reason
- L45.2: two mechanical obligations, both prerequisites, not warm-up
- L48.1: The whole output is the default
- L49.1: An un-armed reviewer works from whatever occurs to them
- L49.2: a rubric names the classes this surface is *known* to fail
- L52.3: so the closing pass re-derives verdicts and the flip adds no content
- L57.2: coarser, same and finer for a lookup
- L57.3: every install layout the repo's docs teach for a path rule
- L61.2: YOUR audit owns whether the quotes are load-bearing rather than decorative
- L67.1: A checklist can still be filled without real hunting
- L67.2: it raises a floor, it does not guarantee a ceiling
- L75.4: a dead or hallucinated citation is a defect
- L79.2: those heal a transient fault, while a permanent provider death needs a SWAP no retry loop can make, and a stall with no progress alarm is invisible fo
- L86.1: Measured 2026-08-28 across 236 real tickets in the fleet: a mechanical "backticked symbol absent from the read set" detector fires on 23.7%, and inspe
- L86.2: the regex cannot make the consume-vs-introduce call, so it is not shippable as a gate
- L94.1: Plan review is the last point where a dropped requirement costs a paragraph instead of a rebuild
- L95.2: there is no mechanical check for it and this row does not pretend otherwise
- L100.2: its absence is the #1 cause of a plan that stalls mid-execution to ask the user
- L119.2: a deferred question inside a ticket stalls the dispatched coder exactly like one inside a monolith phase
- L121.6: the pool is OFF, D-181<!-- POOL OFF: `fanout("research", …, mode="read_only", web_tools=["web_search","web_scrape","docs_lookup"])` for live search
- L121.7: recipe in § Subagents -->)
- L141.2: (a) and (b) alone are satisfied by a check that matches nothing (01M1VDFYH)
- L143.2: if any is missing from the plan, add it
- L147.3: can see it, and any executor other than the full dispatcher path has no floor (live defect 2026-08-10: a 14-ticket set, reviewed and CONVERGED, contai
- L151.2: flag it and fix the plan.<!-- POOL OFF (D-181): the pre-D-181 text required POOL-DEFAULT (`fanout(task_type, units, …)`, auto-records to the flywheel,
- L152.2: call out explicitly which steps fan out and where the merge happens
- L166.2: NOT mid-execution
- L167.1: A plan that converges with a deferred question is a plan that WILL stall `/fabrik-execute-plan` to ask the user (the exact failure this gate exists to
- L171.2: it is a deferred question
- L175.1: (This is the lesson from a real run: a plan converged with "[OPEN → resolve the DSN with the coding-selection AI at Phase C start]", and execution dut
- L175.2: when the answer was self-service all along
- L181.1: A finished plan left in the active `docs/development/plans/` directory is clutter that misleads the next agent into treating it as still-open work
- L181.2: the exact confusion this rule prevents

## Pins deleted
Deleted (presence pins on reworded text, Touches tests only): the whole tests `tests/test_plan_review_queue_pass.py::test_a_seat_grades_its_pinned_plan_set_copy` and `::test_round_one_hands_the_seats_an_input_grid` (each held only the deleted assert), one assert of `::test_a_run_lives_in_the_plan_and_is_re_run_before_each_later_pin`, and one of `tests/test_plan_review_recurring_rules.py::test_checklist_rows_are_adjudicated_before_the_closing_pass_and_new_code_runs_before_the_pin`; each node is listed under `pins:` on the entries covering its text (L32-33, L52, L55-58). Passing pins on unchanged text were left.

## Failure sets (reader-test run, `capped_run.sh` unavailable in the clone: plain pytest)
Targeted run on the real tree after the deletions: `tests/test_plan_review_queue_pass.py tests/test_plan_review_recurring_rules.py tests/test_plan_review_small_gate.py tests/test_plan_after_chat_queue_pass.py tests/test_spec_review_queue_pass.py`: 69 passed; `tests/test_command_rules.py`: 32 passed, 3 skipped. Before the deletions the same files had 4 reds, all in the two edited files. The full reader-set failure set (55 at the start commit: 15 `test_fabrik_deck`, 12 `test_generate_capability_index`, 7 `test_quota_dashboard`, 5 `test_conftest_isolation`, 3 `test_governance_template_split`, 2+2 corpus/render-version tests, 9 singles, 2 collection errors) is re-run once at the end of the batch and recorded in the T19 receipt.

**Final run (all five tickets applied, tree at the last commit):** the same reader set (65 test files) plus `tests/test_command_rules.py`, plain `python3 -m pytest` with `.git` present in the scratch copy: 53 failed + 2 collection errors = **55, the identical set to the start commit** (`comm` of the sorted FAILED/ERROR node ids: 0 new, 0 gone). The first full run of the finished tree had found 4 new reds (all `/fabrik-plan-review` drops pinned outside any Touches test: the EXTRACT after-text block, a digest-grammar clause, the `/fabrik-generate-tests` mention); the three clauses were restored in the fix commit and the second full run is the one reported here. The pre-existing 55 are box-service or optional-dependency reds, unchanged by this batch.

## LEFT FOR THE HUB
- CHANGELOG.md, INDEX.md rows for the new `commands/_rules/` files, the `commands/_size_ceiling.json` ratchet and the render at merge.
