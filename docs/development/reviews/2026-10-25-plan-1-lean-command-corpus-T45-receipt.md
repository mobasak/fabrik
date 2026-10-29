# T45 receipt — /fabrik-workflow-review (light form, D-1236)

- Start commit: 8ac547a6139658fed456bb3f3f069596856d6316 (origin/kaizen-lean-u01)
- Own text (`command_rules.own_text`): 1342 words -> 797 (59%). **Target 50% missed; floor named:** the rest is the Phase 0 table, the seven finder classes (each a distinct checked failure class), the ban clauses, and the paths/commands the rule test requires verbatim; further cuts would drop a live rule.
- Entries: 36 total = 12 generated unchanged (`generate_unchanged`) + 24 hand-written reworded entries (24/36 reworded). Hand entries by class: ban 6 · grammar 1 · prose 17 · behavioural 0 (class kept as `# class:` YAML comments).
- Pins deleted: none (no string-in-file presence pin on this command's text exists in the Touches tests; the skill-router description phrases are behavioural and the front matter is untouched).
- Vanished labels: 37 baseline lines vanished; 35 `rule: [ids]`, 2 `narrative` (L5, L7) — author labels, audit owed (no Sonnet/Haiku seats in the clone); no weaker-count available.
- Gates: `tests/test_command_rules.py` 32 passed, 3 skipped, LEDGER line printed for fabrik-workflow-review, zero LOSS. `assemble_commands.py --check` rc 1, only DIFFERS/MISSING drift.
- Reader tests (test_trigger_routing, test_producing_command_fragments, test_skill_router_hook, test_assemble_dispatch_step, test_final_gate_stop_hook): end commit 1 failed / 493 passed (`test_the_gate_reports_a_malformed_orphan_position_instead_of_crashing[a broken symlink]`); start-commit set: identical (same 1 failure, pre-existing: broken-symlink case; the set did not grow).
- LEFT FOR THE HUB: ceiling ratchet for `commands/_size_ceiling.json`; Sonnet+Haiku audit of the 35 rule labels and of the 24 reworded entries old-vs-new; CHANGELOG/INDEX rows for the two new `commands/_rules/` files.

## Fix round 1

Two author-blind audits (Sonnet 14 findings, Haiku 31, overlapping) checked against the before-text.

- **Confirmed and fixed (all substantive items):** pool-off banner (five tokens, SUSPENDED/re-enable, author-blind, `NO-POOL:` ban restored to sentence end with `check_subagent_flywheel.py` / `_POOL_POLICY_ON = False` / D-182); Reads ban (never by an item count, interview inputs, upstream mapping, "do not open it to review"); Phase 0 ("Load the matching…", "counts drift", and the lost `only the type argument selects the yardstick` — L7 was wrongly `narrative`, now `rule: p0-yardstick-no-item-count`); Phase 1 seats (artifact + criteria + yardstick input set, independent, native, authoritative pass, `/fabrik-review` § Breadth seats, `≥1`, item numbers drift, classes THIS artifact can fail); field completeness (Path A/B, nothing silently dropped); trigger-vs-value ("not a pass"); hollow and dangling citation split back into two, with `must`, "archived", "before accepting it"; grounding condition (when the artifact touches a vendor); refute "line/anchor"; "in the ledger"; closing round "via" ban verbatim plus the unchanged-pass case; Phase 3 routing (trigger, per-doer mapping, "when it must change", "routing is not convergence"); autonomous-return, neither-human-gate (R25 tag, `type`, "already passed", "operator's explicit go"), epics-review "NOT a type here", em dash, and `Converge here.`
- **Wrong `vanished:` labels fixed:** L7 (`narrative` → `rule`). L6 ("separate, fresh-context pass that forces the closing round") is now carried in `p2-closing-round-md5`; L55 is now carried by `ac-converge-here`, which includes `Converge here.`.
- **Refuted:** none outright; the 70%-stem-pass items (grounding, citations) were restored anyway as cheap.
- **Invented rules:** none found.
- **Own-text words:** baseline 1342 → first cut 797 → after fix 1124.
- Gates: `tests/test_command_rules.py` 32 passed, 3 skipped; `assemble_commands.py --check` exit 0.

## Re-ledger round

Canonical loader (`_lint`, `_covered`, `_ban_span`, `_clauses`, `_baseline_clauses`) read first; ledger rebuilt one entry per baseline line (the fix round's merged multi-line baselines produced most of the 17 LOSS lines), every `# class:` / `# clauses:` comment converted to a real key.

- Own text (`command_rules.own_text`): baseline 1342 -> fix round 1124 -> now 971 (72.4%). **Target 50% missed; floor below.**
- LOSS lines for `fabrik-workflow-review.yaml`: 17 before -> 0 after (`assemble_commands.py --check`; the only LOSS left are `_shared/*` ledgers, another unit's).
- Entries: 43 = 17 generated unchanged (`generate_unchanged`/`u-L`, four of them re-pinned under the shortened Phase 0 heading) + 26 hand entries, all 26 reworded (ban 8 · prose 18 as real `class:` keys; 3 carry `clauses:` narrative labels for checklist-locator clauses). 36 vanished labels: 29 `rule`, 2 `duplicate-of` (L31, L41 -> the banner entry), 5 `narrative` (L5, L6, L10, L49, L50).
- `COUNTS: entries read 43 / reworded 26 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0`
- What earlier passes fixed (kept): `NO-POOL:` ban to sentence end, Reads ban `never by an item count)`, `only the type argument` ban with its CC1 parenthetical verbatim, `Never a token 1–2` / `must MATCH Phase 3's back-fill --> Cover, …` (the baseline's inline pool-off comment is live text to the loader, so it stays inline), `must inline the decision or tag`, `must change (…)`, `This loop never edits the upstream … wrong direction.`, `never typed by hand) running after it`, `only` in the producer-doers line, `Never leave a ledger row … re-invoke. Converge here.`.
- Tests (start -> end, same set): `test_the_live_corpus_has_no_loss` red at both (now only `_shared/review-probe-catalogue` + `_shared/close-chain` LOSS, not this unit) + the 12 pre-existing `test_assemble_dispatch_step.py` orphan/corrupt-install reds (clone lacks box dirs); 13 failed / 535 passed / 3 skipped at both ends. `test_a_coroner_reaped_nested_session_still_blocks_end_to_end` is flaky in a 5-file run and passes alone. No test pin deleted (none pins this command's text).
- Why the rest cannot shrink further (a Cobra check: a greedy word-deleter that keeps zero LOSS reaches 664 words, but its output is ungrammatical, e.g. "NOTHING else artifact under review upstream `## Acceptance Criteria` 0 never by an item count)." — that meets the measure and loses the rule, so it was rejected):

| Clause | Floor | Why it stays |
|---|---|---|
| L1 banner | 38 words | D-181, 2026-09-07, D-182 and five backticked tokens are anchors and share one clause with the rule; the clause needs 6 of its first 8 stems (operator, OpenRouter, subagent, pool, ruling, revised) |
| L3 `NO-POOL:` ban | 22 | ban clause verbatim to sentence end |
| L7 only-type | 17 | ban clause verbatim through the CC1 parenthetical |
| L8 Reads | 47 | one clause (the `;` and ` — ` sit inside parentheses); anchors `## Acceptance Criteria`, `0`, `never`; the upstream-per-type parenthetical kept (names which inputs to read) |
| L21 seats (6 clauses) | 105 | anchors: three code spans, D-181, D-191, `--units`, `/fabrik-review`, `≥1`, the `fanout(…)` call; two ban clauses verbatim |
| L23 trigger-vs-value | 28 | the example's backticked tokens are anchors |
| L27 grounding | 28 | `external/vendor` and `exa/brave/firecrawl/official-docs` are path anchors in one clause |
| L39 route upstream | 75 | four code spans + `must change (…)` ban verbatim |
| L40, L51, L53, L54 | 85 | ban clauses verbatim to clause or sentence end |
| L36, L34, L17 | 50 | ban clauses, unchanged |
| L44-L46 | 29 | unchanged, anchors (`python scripts/final_gate.py …`, `CLAUDE.md`) |

- LEFT FOR THE HUB: (1) confirm the five `narrative` labels, especially L49/L50 (human-gate recital with the north-star R14/R25 quotes: restated contract, operative rule is L48 + L51) and L6 (positioning analogy), which the fix-round audits had restored; restoring them costs about 100 words. (2) A floor D-row for the 50% shortfall, or a decision that anchors inside history-bearing clauses (D-ids, dates) may be dropped; the loader forces them into the carrier. (3) Ceiling ratchet at merge; CHANGELOG/INDEX rows. (4) `_shared/*` LOSS, not this unit.

## Hub adjudication (kaizen, batch 3, 2026-10-27)

- Inputs: `claude/lean-t45-rl` under master's loader read **2 LOSS** (L31 and L41 labelled `duplicate-of: pool-off-native-seats`, which carries neither clause); the hub audit pair (Sonnet 8 items, Haiku 6, overlapping) refuted the receipt's zero COUNTS. Each item was checked against `git show lean-baseline-2026-10-25:commands/_sources/fabrik-workflow-review.md`; the unit was at its stop (round 2), so the hub fixed it in place instead of firing a third round.
- **Fixed, at baseline wording:** L31 `YOU keep refute/merge/decide` and L41 the no-flywheel-back-fill sentence (the two LOSS); L49/L50 the human-gate scope rule and the plan-in routing to `/fabrik-spec-review`, with their R14/R25 canonical tags (wrong `narrative` labels — they state who owns which gate); the POOL OFF banner's SPEND reason and `left in place, or in … comments`; the finders' yardstick (`against the artifact + its acceptance criteria + the yardstick items`); `(Path A vs Path B; …)` and `the acceptance criteria require`; the Phase 3 route qualifiers (`behind a decomposition or an expanded epic`, `behind an expanded epic`); `which self-converges`; `the matching doer twin … those two ARE the yardstick`; the flavor-branch item pointer and `applied correctly`; the Phase 0 heading with its `type` anchor (L10, wrong `narrative`); `Haiku mechanical seats`, `§ Breadth seats`, the checklist item pointers; the description's routing lines (artifact path + type, the cross-epic exclusion, `the doer produces, THIS forces convergence`, `fires on a workflow ARTIFACT, not source code`). Refuted: none.
- Grade: **0 LOSS** over 50 ledgers under master's loader (`grade_tree.py`, batch-3 tree); the five restored units (L10, L31, L41, L49, L50) are no longer vanished.
- Own text: baseline 1342 → **1201 words (89.5%)**. Floor: the table above plus the restored rules; every restored clause is a rule, its anchor or its qualifier.
