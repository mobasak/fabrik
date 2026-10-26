# T12 receipt — lean rewrite of /fabrik-plan-review

- **Start commit:** `851b4b365cc9ccaac91ed851bc669764743ad360` (baseline written from its text; `fabrik-plan-review.baseline.txt` sha256 in the ledger)
- **Own-text words:** 7347 → 6584 (90% of baseline; target ≤50%). **Floor named below.**
- **Ledger entries:** 168 total = 127 generated-unchanged (`u-L<n>`, `generate_unchanged`) + 41 reworded (`r-L<n>`, hand-covered). Reworded / total = 41/168.
- **By class (D-1236 tag, set at baseline):** unchanged {'ban': 61, 'prose': 55, 'behavioural': 11} · reworded {'prose': 23, 'behavioural': 4, 'ban': 14}. The tag is a `# class:` YAML comment (the loader on this base has no `class` key).
- **Vanished baseline lines:** 50 = 41 `rule:` (covered by a reworded entry) + 9 `narrative` (every clause labelled narrative). 54 clauses inside the `rule:` lines are labelled narrative, recorded per entry as a `# clauses:` comment.
- **Labels:** author labels — audit owed (the Sonnet + Haiku classification seats cannot run in this clone).
- **Coverage rule applied by hand (D-1240):** per clause (split at `;`/`—`, outside code spans) ONE `text` phrase holds 100% of the clause's anchors (backticked tokens, numbers, paths, ban words) and ≥70% of its first 8 content-word stems; a clause holding never/must/only/refus* is verbatim from that word to the end of its clause and is never labelled narrative; the carrier holds the same ban token; every phrase is ≥6 normalised words and unique in the file. Checked by a scratch script (not committed; `commands/command_rules.py` was not edited).

## Floor
Measured on the start-commit text (clauses split at `;`/`—` outside code spans): of 7347 words, 1160 sit in ban-clause tails kept verbatim by D-1240, 806 in the heads of those clauses, 3039 in non-ban clauses with backticked tokens, numbers or paths (all anchors must survive) and 2044 in clauses with neither. The pass dropped what is explanatory or anecdotal (54 clauses and 9 whole lines labelled narrative: measured-incidence stories, live-defect anecdotes, rationale tails, the pool-off history and its inline comments) and nothing else; the remaining text is the seat/ledger/round mechanics (the partition and `Workflow` call, the pass-ledger and receipt grammar, the set-wide gates), each clause an anchor-bearing instruction. Result 90% of baseline, not 50%. Reaching 50% needs those mechanics moved into a fragment or re-expressed without their commands, which the per-clause coverage rule of D-1240 does not allow inside this unit; a floor D-row is owed.

## Reworded entries — clause count and how each clause is covered

| entry | class | clauses | coverage (P = covered by phrase n of the entry · N = narrative label) |
|---|---|---|---|
| r-L1 | prose | 4 | 1:P1 2:N 3:N 4:N |
| r-L2 | prose | 3 | 1:P1 2:P2 3:P3 |
| r-L5 | prose | 2 | 1:P1 2:N |
| r-L10 | behavioural | 2 | 1:P1 2:N |
| r-L13 | ban | 5 | 1:P1 2:P2 3:P3 4:P4 5:N |
| r-L16 | ban | 2 | 1:P1 2:N |
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
| r-L62 | prose | 2 | 1:P1 2:N |
| r-L75 | ban | 4 | 1:P1 2:P2 3:P3 4:N |
| r-L79 | prose | 2 | 1:P1 2:N |
| r-L84 | ban | 2 | 1:P1 2:P2 |
| r-L95 | prose | 2 | 1:P1 2:N |
| r-L100 | prose | 2 | 1:P1 2:N |
| r-L103 | prose | 3 | 1:P1 2:P2 3:N |
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
- L10.2: the joint loop does not continue past that point
- L13.5: the operator's answer, in a LATER turn, is minted by that turn's session, and changes re-open the loop
- L16.2: a plan review without that gate dispatches no critiques
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
- L62.2: a table the checker cannot read leaves its quotes ungraded
- L67.1: A checklist can still be filled without real hunting
- L67.2: it raises a floor, it does not guarantee a ceiling
- L75.4: a dead or hallucinated citation is a defect
- L79.2: those heal a transient fault, while a permanent provider death needs a SWAP no retry loop can make, and a stall with no progress alarm is invisible fo
- L86.1: Measured 2026-08-28 across 236 real tickets in the fleet: a mechanical "backticked symbol absent from the read set" detector fires on 23.7%, and inspe
- L86.2: the regex cannot make the consume-vs-introduce call, so it is not shippable as a gate
- L94.1: Plan review is the last point where a dropped requirement costs a paragraph instead of a rebuild
- L95.2: there is no mechanical check for it and this row does not pretend otherwise
- L100.2: its absence is the #1 cause of a plan that stalls mid-execution to ask the user
- L103.3: flag it and add the contract (the emitted plan can note the cheap pool authors these via `/fabrik-generate-tests`)
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

## LEFT FOR THE HUB
- CHANGELOG.md, INDEX.md rows for the new `commands/_rules/` files, the `commands/_size_ceiling.json` ratchet and the render at merge.
