# Lean command corpus — T46 integration close-out receipt

Plan: `docs/development/plans/2026-10-25-plan-1-lean-command-corpus/2026-10-25-plan-1-lean-command-corpus.md` · Work item: W-96f36043 (the P0 lean program, D-1216) · Measured on master `c812b5cbf` (2026-10-28), after the batch 3 merge `ceadce76c` and its ceiling ratchet `381c3e177`.

**One line:** all 40 commands pass the rule check (0 LOSS over 63 rule ledgers, 5,425 entries); rendered words 596,988 → 579,853, 97.1% of baseline. **The 50% size goal was missed**: no command and no shared file reached it, and every one closed under the floor ruling D-1254. D-1259 recorded why: once every rule the audit flags is restored, rewriting a command lands at 49.8–100% of its own text (median ~91%), so the 50% headline was retired for per-file floors. D-1293 then had the remaining units finish with every rule kept, leaving the rules themselves for a later program.

## What this receipt is, and is not

- It is T46's close-out: the per-file ratio table, the size measures, the whole-plan doc checks, the seam test, the gate and convergence runs, and the L1/L2 check.
- It is **not** a D7 whole-plan adversarial validation. No cross-ticket finder round ran over the cumulative diff. Each unit was closed by its own receipt instead, on D-1254's terms: "0 LOSS under master's canonical loader + a self-audit pass with all-zero COUNTS + a per-file floor table whenever own text stays over 50%". The spine's `Status:` therefore stays `IN-PROGRESS`. The coordinator decides the closing status (CLAUDE.md, coordinator job 7), given T05a–c not run and the T46 gaps below.

### T46's own contract, item by item

| Behavior Contract item | Met? |
|---|---|
| 1. Each file at or under 50% or naming its floor D-row | **Met as a citation.** Every row names D-1254, but 13 of the 49 unit receipts record no per-file floor table (Step 1). |
| 2. No command's full measure has grown | **NOT met.** On the spec's measure (render + reads), 10 commands grew, all through reads in docs outside `commands/` (Step 2). |
| 3. `final_gate.py --check --json` and `check_convergence.py` succeed, with output embedded | **Met** (§ Gates). |
| 4. `remove:` rows flowing, with their `none` share | **NOT met.** L2 has not landed, and 0 rows carry the field (Step 4). |
| Step 3: `/fabrik-docs-review` over the range | **Not run** (Step 3). |

## Ticket Board outcome

- This commit changes 54 board rows (T01d–T46): 51 ✅ and 3 🔴. With T01a–c, which an earlier commit already ticked, the board now holds 57 rows: 54 ✅ and 3 🔴, and none ⬜.
- 50 of the 54 ✅ rows name the master commit that brought their unit to 0 LOSS. T01a–c read "this commit", as they were written in the T01 pilot's own commits. T46 names `1677dd6f7` plus its review-fix commit.
- T46 is ✅ only in the sense that its work landed here. Two of its contract items are unmet, as the table above shows.
- 🔴 T05a, T05b, T05c: the subagents-core, grounding, intake and test-loop fragments. They had not started when D-1259's KILL ruled that "no NEW rewrite unit starts", so their ten fragments carry no ledger: `chat-intake`, `delegated-reads`, `grounding-artifact`, `grounding-code`, `grounding-rules`, `injection`, `questionbar`, `repo-identity`, `subagents-core`, `test-generation-loop`. No lean unit edited them, so nothing was cut there.

## Step 1 — ratio table (own text, unit start commit vs master)

Method, per the ticket: for each ledger, the baseline is the parent of the commit that added the ledger to master. Command sources are counted through `command_rules.own_text`, and shared files are counted whole. Every row is over 50%, so every row names the floor ruling D-1254 (`python3 scripts/decisions.py D-1254` finds it). Floor arithmetic, where it exists, sits in each unit's receipt (`docs/development/reviews/2026-10-25-plan-1-lean-command-corpus-T*-receipt.md`). **13 of those 49 receipts record no per-file floor table** (a case-insensitive grep for "no per-file floor" or "no floor table" matches 13). Examples are T08:198 ("so no floor table"), T12, T21, T24 and T26 ("retired (D-1257), so no floor table"), and T11, T29 and T33 in similar words. Several of them give hand-estimated figures. A unit receipt measured at its own base can differ from this table: T08's receipt records an own-text baseline of 4263 for `/fabrik-task`, where this table's start commit gives 4425.

| File | Ledger | Baseline own words | Master own words | Ratio | Ledger entries | Lines moved (rule) / narrative / duplicate | Floor |
|---|---|---:|---:|---:|---:|---|---|
| `commands/_fragments/agent-feedback.md` | `commands/_rules/_shared/agent-feedback.yaml` | 475 | 461 | 97.1% | 20 | 2 / 2 / 0 | D-1254 |
| `commands/_fragments/autonomy-run.md` | `commands/_rules/_shared/autonomy-run.yaml` | 1173 | 1151 | 98.1% | 38 | 20 / 0 / 0 | D-1254 |
| `commands/_fragments/cert-board-contract.md` | `commands/_rules/_shared/cert-board-contract.yaml` | 1124 | 936 | 83.3% | 31 | 12 / 3 / 0 | D-1254 |
| `commands/_fragments/cert-execution.md` | `commands/_rules/_shared/cert-execution.yaml` | 617 | 617 | 100.0% | 17 | 13 / 0 / 0 | D-1254 |
| `commands/_fragments/cert-handoff-grammar.md` | `commands/_rules/_shared/cert-handoff-grammar.yaml` | 280 | 273 | 97.5% | 5 | 4 / 0 / 0 | D-1254 |
| `commands/_fragments/cert-visual-deliverable.md` | `commands/_rules/_shared/cert-visual-deliverable.yaml` | 153 | 153 | 100.0% | 3 | 2 / 0 / 0 | D-1254 |
| `commands/_fragments/close-chain.md` | `commands/_rules/_shared/close-chain.yaml` | 473 | 479 | 101.3% | 9 | 4 / 0 / 0 | D-1254 |
| `commands/_fragments/close-feedback.md` | `commands/_rules/_shared/close-feedback.yaml` | 2436 | 2281 | 93.6% | 68 | 40 / 1 / 0 | D-1254 |
| `commands/_fragments/deploy-chain.md` | `commands/_rules/_shared/deploy-chain.yaml` | 364 | 359 | 98.6% | 14 | 4 / 0 / 0 | D-1254 |
| `commands/_fragments/design-critique.md` | `commands/_rules/_shared/design-critique.yaml` | 817 | 804 | 98.4% | 22 | 13 / 1 / 0 | D-1254 |
| `commands/_fragments/design-gate-panel.md` | `commands/_rules/_shared/design-gate-panel.yaml` | 653 | 646 | 98.9% | 19 | 6 / 0 / 0 | D-1254 |
| `commands/_agents/design-review.md` | `commands/_rules/_shared/design-review.yaml` | 831 | 799 | 96.1% | 45 | 9 / 2 / 0 | D-1254 |
| `commands/_agents/fabrik-gui.md` | `commands/_rules/_shared/fabrik-gui.yaml` | 637 | 627 | 98.4% | 14 | 4 / 0 / 0 | D-1254 |
| `commands/_agents/fabrik-researcher.md` | `commands/_rules/_shared/fabrik-researcher.yaml` | 2728 | 2474 | 90.7% | 76 | 51 / 1 / 0 | D-1254 |
| `commands/_agents/fabrik-reviewer.md` | `commands/_rules/_shared/fabrik-reviewer.yaml` | 2104 | 2119 | 100.7% | 35 | 15 / 0 / 0 | D-1254 |
| `commands/_fragments/judge-panel.md` | `commands/_rules/_shared/judge-panel.yaml` | 253 | 254 | 100.4% | 5 | 1 / 0 / 0 | D-1254 |
| `commands/_fragments/no-workflow-hub.md` | `commands/_rules/_shared/no-workflow-hub.yaml` | 151 | 150 | 99.3% | 4 | 1 / 0 / 0 | D-1254 |
| `commands/_fragments/orient.md` | `commands/_rules/_shared/orient.yaml` | 361 | 347 | 96.1% | 8 | 8 / 0 / 0 | D-1254 |
| `commands/_fragments/review-probe-catalogue.md` | `commands/_rules/_shared/review-probe-catalogue.yaml` | 6908 | 6582 | 95.3% | 66 | 49 / 1 / 0 | D-1254 |
| `commands/_fragments/run-record.md` | `commands/_rules/_shared/run-record.yaml` | 665 | 664 | 99.8% | 24 | 3 / 0 / 0 | D-1254 |
| `commands/_fragments/scope-growth-exit.md` | `commands/_rules/_shared/scope-growth-exit.yaml` | 333 | 314 | 94.3% | 6 | 3 / 1 / 0 | D-1254 |
| `commands/_fragments/term-coverage.md` | `commands/_rules/_shared/term-coverage.yaml` | 6109 | 5890 | 96.4% | 31 | 24 / 3 / 1 | D-1254 |
| `commands/_fragments/term-edit.md` | `commands/_rules/_shared/term-edit.yaml` | 5354 | 5269 | 98.4% | 63 | 6 / 1 / 0 | D-1254 |
| `commands/_sources/design-review.md` | `commands/_rules/design-review.yaml` | 1348 | 1329 | 98.6% | 34 | 6 / 1 / 0 | D-1254 |
| `commands/_sources/fabrik-catchup.md` | `commands/_rules/fabrik-catchup.yaml` | 2329 | 2282 | 98.0% | 53 | 26 / 1 / 0 | D-1254 |
| `commands/_sources/fabrik-command-improve.md` | `commands/_rules/fabrik-command-improve.yaml` | 6382 | 6280 | 98.4% | 150 | 34 / 5 / 0 | D-1254 |
| `commands/_sources/fabrik-conformance-review.md` | `commands/_rules/fabrik-conformance-review.yaml` | 2507 | 2264 | 90.3% | 91 | 42 / 11 / 0 | D-1254 |
| `commands/_sources/fabrik-data-contract.md` | `commands/_rules/fabrik-data-contract.yaml` | 3498 | 3462 | 99.0% | 105 | 64 / 0 / 0 | D-1254 |
| `commands/_sources/fabrik-decommission.md` | `commands/_rules/fabrik-decommission.yaml` | 2570 | 2472 | 96.2% | 71 | 39 / 0 / 0 | D-1254 |
| `commands/_sources/fabrik-deploy-checklist.md` | `commands/_rules/fabrik-deploy-checklist.yaml` | 3826 | 3571 | 93.3% | 106 | 47 / 3 / 0 | D-1254 |
| `commands/_sources/fabrik-deploy-plan-review.md` | `commands/_rules/fabrik-deploy-plan-review.yaml` | 4330 | 4143 | 95.7% | 81 | 31 / 1 / 0 | D-1254 |
| `commands/_sources/fabrik-deploy-plan.md` | `commands/_rules/fabrik-deploy-plan.yaml` | 4785 | 4744 | 99.1% | 110 | 12 / 1 / 1 | D-1254 |
| `commands/_sources/fabrik-deploy-verify.md` | `commands/_rules/fabrik-deploy-verify.yaml` | 4583 | 4389 | 95.8% | 129 | 62 / 0 / 0 | D-1254 |
| `commands/_sources/fabrik-deploy.md` | `commands/_rules/fabrik-deploy.yaml` | 4898 | 4766 | 97.3% | 106 | 50 / 0 / 0 | D-1254 |
| `commands/_sources/fabrik-doc-converge.md` | `commands/_rules/fabrik-doc-converge.yaml` | 1661 | 1647 | 99.2% | 43 | 15 / 0 / 0 | D-1254 |
| `commands/_sources/fabrik-docs-review.md` | `commands/_rules/fabrik-docs-review.yaml` | 2786 | 2786 | 100.0% | 84 | 0 / 1 / 0 | D-1254 |
| `commands/_sources/fabrik-epics-review.md` | `commands/_rules/fabrik-epics-review.yaml` | 7498 | 7186 | 95.8% | 140 | 83 / 6 / 1 | D-1254 |
| `commands/_sources/fabrik-epics.md` | `commands/_rules/fabrik-epics.yaml` | 7715 | 7392 | 95.8% | 223 | 60 / 2 / 0 | D-1254 |
| `commands/_sources/fabrik-execute-plan.md` | `commands/_rules/fabrik-execute-plan.yaml` | 17726 | 17422 | 98.3% | 406 | 26 / 10 / 3 | D-1254 |
| `commands/_sources/fabrik-features.md` | `commands/_rules/fabrik-features.yaml` | 1873 | 1723 | 92.0% | 60 | 36 / 2 / 0 | D-1254 |
| `commands/_sources/fabrik-flows-review.md` | `commands/_rules/fabrik-flows-review.yaml` | 2446 | 2128 | 87.0% | 68 | 30 / 10 / 0 | D-1254 |
| `commands/_sources/fabrik-flows.md` | `commands/_rules/fabrik-flows.yaml` | 2838 | 2705 | 95.3% | 80 | 30 / 2 / 1 | D-1254 |
| `commands/_sources/fabrik-generate-tests.md` | `commands/_rules/fabrik-generate-tests.yaml` | 2314 | 2315 | 100.0% | 40 | 13 / 0 / 0 | D-1254 |
| `commands/_sources/fabrik-plan-after-chat.md` | `commands/_rules/fabrik-plan-after-chat.yaml` | 12059 | 11999 | 99.5% | 261 | 25 / 2 / 0 | D-1254 |
| `commands/_sources/fabrik-plan-review.md` | `commands/_rules/fabrik-plan-review.yaml` | 7347 | 7146 | 97.3% | 167 | 35 / 5 / 0 | D-1254 |
| `commands/_sources/fabrik-release.md` | `commands/_rules/fabrik-release.yaml` | 2582 | 2383 | 92.3% | 72 | 64 / 3 / 1 | D-1254 |
| `commands/_sources/fabrik-repo-review.md` | `commands/_rules/fabrik-repo-review.yaml` | 2900 | 2777 | 95.8% | 70 | 12 / 0 / 1 | D-1254 |
| `commands/_sources/fabrik-reverse-engineer.md` | `commands/_rules/fabrik-reverse-engineer.yaml` | 1631 | 1567 | 96.1% | 39 | 8 / 0 / 0 | D-1254 |
| `commands/_sources/fabrik-review-scoped.md` | `commands/_rules/fabrik-review-scoped.yaml` | 5108 | 4998 | 97.8% | 74 | 13 / 2 / 1 | D-1254 |
| `commands/_sources/fabrik-review.md` | `commands/_rules/fabrik-review.yaml` | 12700 | 12270 | 96.6% | 276 | 37 / 16 / 0 | D-1254 |
| `commands/_sources/fabrik-rivals.md` | `commands/_rules/fabrik-rivals.yaml` | 2859 | 2631 | 92.0% | 95 | 66 / 8 / 0 | D-1254 |
| `commands/_sources/fabrik-rules-review.md` | `commands/_rules/fabrik-rules-review.yaml` | 2056 | 2021 | 98.3% | 70 | 28 / 2 / 0 | D-1254 |
| `commands/_sources/fabrik-service-test.md` | `commands/_rules/fabrik-service-test.yaml` | 3741 | 3643 | 97.4% | 85 | 17 / 0 / 0 | D-1254 |
| `commands/_sources/fabrik-spec-review.md` | `commands/_rules/fabrik-spec-review.yaml` | 4839 | 4533 | 93.7% | 131 | 21 / 3 / 0 | D-1254 |
| `commands/_sources/fabrik-spec.md` | `commands/_rules/fabrik-spec.yaml` | 9182 | 8767 | 95.5% | 158 | 105 / 5 / 0 | D-1254 |
| `commands/_sources/fabrik-task.md` | `commands/_rules/fabrik-task.yaml` | 4425 | 4188 | 94.6% | 100 | 88 / 0 / 0 | D-1254 |
| `commands/_sources/fabrik-ui-design-review.md` | `commands/_rules/fabrik-ui-design-review.yaml` | 2875 | 2675 | 93.0% | 82 | 39 / 6 / 0 | D-1254 |
| `commands/_sources/fabrik-ui-design.md` | `commands/_rules/fabrik-ui-design.yaml` | 4368 | 4160 | 95.2% | 122 | 28 / 3 / 1 | D-1254 |
| `commands/_sources/fabrik-upstream.md` | `commands/_rules/fabrik-upstream.yaml` | 3659 | 3166 | 86.5% | 84 | 66 / 8 / 1 | D-1254 |
| `commands/_sources/fabrik-user-test.md` | `commands/_rules/fabrik-user-test.yaml` | 5118 | 4576 | 89.4% | 85 | 83 / 11 / 0 | D-1254 |
| `commands/_sources/fabrik-vision.md` | `commands/_rules/fabrik-vision.yaml` | 13442 | 13234 | 98.5% | 582 | 201 / 7 / 6 | D-1254 |
| `commands/_sources/fabrik-workflow-review.md` | `commands/_rules/fabrik-workflow-review.yaml` | 1342 | 1201 | 89.5% | 43 | 29 / 2 / 0 | D-1254 |
| `commands/_sources/hibernate.md` | `commands/_rules/hibernate.yaml` | 880 | 861 | 97.8% | 26 | 14 / 1 / 0 | D-1254 |
| **total (63 files)** | | **226025** | **217451** | **96.2%** | | | |

## Step 2 — size measures (rendered words, L1's own measure, the spec's full measure)

Rendered words were measured by rendering each tree with its own renderer: tag `lean-baseline-2026-10-25` (`7ed30f4bc`) and master `c812b5cbf`. The other two columns come from `command_measure.measure_all` on master:
- The **own measure** is what L1's ceiling gates: `own` = render + seats + the files under `commands/` that the render names. It is compared against `baseline_own` in `commands/_size_ceiling.json`.
- The **full measure** is the spec's `measure(cmd) = render + reads`, computed as `own + reads_total` against `baseline_own` plus the ceiling file's frozen baseline `reads.total`.

**No command's own measure grew** (93.7% to 98.2% of baseline). **Ten commands' full measure grew** (/fabrik-catchup +165, /fabrik-decommission +52, /fabrik-deploy +13, /fabrik-deploy-plan +104, /fabrik-doc-converge +82, /fabrik-generate-tests +128, /fabrik-plan-after-chat +121, /fabrik-reverse-engineer +793, /fabrik-task +377, /hibernate +399), so Behavior Contract item 2 is NOT met. Every one of those increases comes from reads: docs outside `commands/` that other work edited during the program, listed in the `read grew` lines below (`command-run-protocol.md` alone grew 582 words and is read by all 40). No lean unit edited those docs, and the ticket's DO-NOT puts them outside this plan, so the growth is reported here and not sent back to any unit. L1 does not gate reads (`command_measure.py` reports a read's growth and never fails on it).

| Command | Rendered words, baseline → master | Own measure, L1's quantity (render + seats + files under `commands/` it names) | Full measure, the spec's (own + reads) |
|---|---|---|---|
| /design-review | 14942 → 14663 (98.1%) | 23194 → 22578 (97.3%) | 113817 → 113783 (100.0%) |
| /fabrik-catchup | 7326 → 7115 (97.1%) | 10542 → 10063 (95.5%) | 74147 → 74312 (100.2%) **grew +165** |
| /fabrik-command-improve | 10536 → 10270 (97.5%) | 22453 → 21701 (96.7%) | 77285 → 77115 (99.8%) |
| /fabrik-conformance-review | 17515 → 16878 (96.4%) | 24448 → 23520 (96.2%) | 69619 → 69001 (99.1%) |
| /fabrik-data-contract | 17266 → 16970 (98.3%) | 24199 → 23612 (97.6%) | 110900 → 110895 (100.0%) |
| /fabrik-decommission | 7369 → 7107 (96.4%) | 10585 → 10055 (95.0%) | 41566 → 41618 (100.1%) **grew +52** |
| /fabrik-deploy | 9415 → 9114 (96.8%) | 12631 → 12062 (95.5%) | 42498 → 42511 (100.0%) **grew +13** |
| /fabrik-deploy-checklist | 18612 → 18092 (97.2%) | 25545 → 24734 (96.8%) | 124743 → 124514 (99.8%) |
| /fabrik-deploy-plan | 9302 → 9092 (97.7%) | 12518 → 12040 (96.2%) | 42385 → 42489 (100.2%) **grew +104** |
| /fabrik-deploy-plan-review | 14249 → 13807 (96.9%) | 21182 → 20449 (96.5%) | 97230 → 97079 (99.8%) |
| /fabrik-deploy-verify | 9806 → 9443 (96.3%) | 15351 → 14673 (95.6%) | 57438 → 57342 (99.8%) |
| /fabrik-doc-converge | 16097 → 15823 (98.3%) | 23030 → 22465 (97.5%) | 134010 → 134092 (100.1%) **grew +82** |
| /fabrik-docs-review | 16363 → 16104 (98.4%) | 30204 → 29328 (97.1%) | 117138 → 116844 (99.7%) |
| /fabrik-epics | 16864 → 16366 (97.0%) | 23797 → 23008 (96.7%) | 93412 → 93205 (99.8%) |
| /fabrik-epics-review | 21681 → 21109 (97.4%) | 28614 → 27751 (97.0%) | 125160 → 124879 (99.8%) |
| /fabrik-execute-plan | 21366 → 20898 (97.8%) | 40554 → 39412 (97.2%) | 121252 → 121241 (100.0%) |
| /fabrik-features | 16317 → 15907 (97.5%) | 23250 → 22549 (97.0%) | 129129 → 129010 (99.9%) |
| /fabrik-flows | 16621 → 16228 (97.6%) | 23554 → 22870 (97.1%) | 109717 → 109615 (99.9%) |
| /fabrik-flows-review | 18140 → 17542 (96.7%) | 25073 → 24184 (96.5%) | 111654 → 111347 (99.7%) |
| /fabrik-generate-tests | 7097 → 6934 (97.7%) | 14030 → 13576 (96.8%) | 57707 → 57835 (100.2%) **grew +128** |
| /fabrik-plan-after-chat | 21575 → 21340 (98.9%) | 28508 → 27982 (98.2%) | 127378 → 127499 (100.1%) **grew +121** |
| /fabrik-plan-review | 23211 → 22729 (97.9%) | 37052 → 35953 (97.0%) | 129771 → 129254 (99.6%) |
| /fabrik-release | 6736 → 6373 (94.6%) | 9952 → 9321 (93.7%) | 50153 → 50123 (99.9%) |
| /fabrik-repo-review | 17835 → 17317 (97.1%) | 24768 → 23959 (96.7%) | 70981 → 70482 (99.3%) |
| /fabrik-reverse-engineer | 5638 → 5410 (96.0%) | 8230 → 8003 (97.2%) | 41947 → 42740 (101.9%) **grew +793** |
| /fabrik-review | 27571 → 26747 (97.0%) | 41412 → 39971 (96.5%) | 103589 → 102458 (98.9%) |
| /fabrik-review-scoped | 9551 → 9257 (96.9%) | 34855 → 33640 (96.5%) | 73225 → 72295 (98.7%) |
| /fabrik-rivals | 12612 → 12135 (96.2%) | 19545 → 18777 (96.1%) | 110293 → 110107 (99.8%) |
| /fabrik-rules-review | 16324 → 16029 (98.2%) | 23257 → 22671 (97.5%) | 109346 → 109342 (100.0%) |
| /fabrik-service-test | 17484 → 16786 (96.0%) | 24417 → 23428 (95.9%) | 83963 → 83349 (99.3%) |
| /fabrik-spec | 19105 → 18516 (96.9%) | 38097 → 37157 (97.5%) | 99277 → 98919 (99.6%) |
| /fabrik-spec-review | 20672 → 20085 (97.2%) | 34513 → 33309 (96.5%) | 127573 → 126951 (99.5%) |
| /fabrik-task | 8714 → 8294 (95.2%) | 11306 → 10887 (96.3%) | 63790 → 64167 (100.6%) **grew +377** |
| /fabrik-ui-design | 14053 → 13596 (96.7%) | 20986 → 20238 (96.4%) | 147272 → 147234 (100.0%) |
| /fabrik-ui-design-review | 18565 → 18085 (97.4%) | 25498 → 24727 (97.0%) | 154306 → 154245 (100.0%) |
| /fabrik-upstream | 8670 → 8013 (92.4%) | 15603 → 14655 (93.9%) | 49111 → 48745 (99.3%) |
| /fabrik-user-test | 18885 → 17743 (94.0%) | 27137 → 25658 (94.5%) | 75608 → 74439 (98.5%) |
| /fabrik-vision | 22541 → 22158 (98.3%) | 32333 → 31431 (97.2%) | 157259 → 156939 (99.8%) |
| /fabrik-workflow-review | 15521 → 15120 (97.4%) | 22454 → 21762 (96.9%) | 112344 → 112234 (99.9%) |
| /hibernate | 4841 → 4658 (96.2%) | 4841 → 4658 (96.2%) | 34920 → 35319 (101.1%) **grew +399** |
| **all 40** | **596988 → 579853 (97.1%)** | **919518 → 888817 (96.7%)** | **3772913 → 3765568 (99.8%)** |

`python3 commands/assemble_commands.py --check` → rc 0. It printed 11 lines: the render banner (`rendered 40 commands -> <tmp> …`) and the 10 below. It printed no DRIFT line.

```
REPORT read grew .windsurf/rules/core/ocoron-design-system.md 5438→5566 in 2 command(s): fabrik-ui-design-review, fabrik-ui-design
REPORT read grew .windsurf/rules/mobile-app/89-mobile-launch-checklist.md 3251→3270 in 1 command(s): fabrik-release
REPORT read grew docs/CAPABILITIES.md 8981→9195 in 1 command(s): fabrik-task
REPORT read grew docs/CONFIGURATION.md 11075→11140 in 4 command(s): fabrik-catchup, fabrik-doc-converge, fabrik-plan-after-chat, fabrik-service-test
REPORT read grew docs/reference/agents/coordinator.md 1523→1526 in 1 command(s): fabrik-execute-plan
REPORT read grew docs/reference/command-run-protocol.md 10365→10947 in 40 command(s): design-review, fabrik-catchup, fabrik-command-improve, fabrik-conformance-review, fabrik-data-contract, fabrik-decommission, fabrik-deploy-checklist, fabrik-deploy-plan-review, fabrik-deploy-plan, fabrik-deploy-verify, fabrik-deploy, fabrik-doc-converge, fabrik-docs-review, fabrik-epics-review, fabrik-epics, fabrik-execute-plan, fabrik-features, fabrik-flows-review, fabrik-flows, fabrik-generate-tests, fabrik-plan-after-chat, fabrik-plan-review, fabrik-release, fabrik-repo-review, fabrik-reverse-engineer, fabrik-review-scoped, fabrik-review, fabrik-rivals, fabrik-rules-review, fabrik-service-test, fabrik-spec-review, fabrik-spec, fabrik-task, fabrik-ui-design-review, fabrik-ui-design, fabrik-upstream, fabrik-user-test, fabrik-vision, fabrik-workflow-review, hibernate
REPORT read grew docs/reference/multi-agent-operating-model.md 5547→6010 in 1 command(s): fabrik-execute-plan
REPORT read grew docs/reference/work-tracking.md 8895→8978 in 1 command(s): fabrik-execute-plan
REPORT read grew docs/workstation/mcp-roster.md 4074→4512 in 1 command(s): fabrik-reverse-engineer
check OK — installed commands + skills match rendered sources
```

## Step 3 — whole-plan doc checks

Range `1659737af..c812b5cbf`: the ticket's `<base>`, the parent of T01a's first commit `c312a59fc`, to master. That is 572 commits (`git rev-list --count`). The same two checks also ran rc 0, silent, over the lock's recorded `baseline_commit` `63d148626`, two commits earlier.

```
$ python3 scripts/enforcement/check_doc_sync.py --range 1659737af248326e6f54b909e06cd04760be7976..c812b5cbf
(no output) rc=0
$ python3 scripts/enforcement/check_doc_stubs.py --range 1659737af248326e6f54b909e06cd04760be7976..c812b5cbf
(no output) rc=0
```

`/fabrik-docs-review` was **not run** over this range. The range is every agent's master history across four days (572 commits). This plan's own changes are command sources, rule ledgers and their receipts, and each unit's receipt already reconciled its own docs. RECORDED.

## Step 4 — L1, L2 and the standing ledger gate

- **L1 (size ceiling) — live, over the own measure only.** `commands/_size_ceiling.json` carries every command's ceiling, and `--check` exits 5 when the own measure breaches it. Reads are reported, never gated. `--ratchet` only lowers a ceiling, and the coordinator runs it by hand after the merge queue drains (`command_measure.py`'s docstring). It ran after the batch 3 merge as `381c3e177`, which lowered four ceilings: `fabrik-review` 41614 → 41171, `fabrik-upstream` 15603 → 15095, `fabrik-workflow-review` 22561 → 22415 and `fabrik-reverse-engineer` 8310 → 8244. Each new ceiling is the master own measure × 1.03, rounded up.
- **Standing ledger gate — live.** `--check` runs `command_rules.losses()` before drift (a LOSS exits 4), and the seam test below shows 63 LEDGER lines and 0 LOSS.
- **L2 (the required `remove:` field on every FEEDBACK close) — NOT landed.** In `~/.claude/state/command-feedback.jsonl` (4,765 rows), 0 rows carry a `remove` field, and neither `scripts/command_run.py` nor `commands/_fragments/close-feedback.md` names it. The code is infra-2's open item W-a9b5e763 (tagged `queued`, `waits-quota`). Spec § Program holds keeps `/fabrik-command-improve` paused until L1 and L2 land, so that hold still stands. This is a CLOSE-OUT gap reported to the coordinator, not fixed here (DO-NOT: tooling files).

## Gates

```
$ /opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest tests/test_command_rules.py -q -rP
LEDGER design-review.yaml: 34 entries · classes {'ban': 13, 'behavioural': 2, 'grammar': 4, 'prose': 15} · vanished {'narrative': 1, 'rule': 6} · provenance 0
LEDGER fabrik-catchup.yaml: 53 entries · classes {'ban': 28, 'prose': 25} · vanished {'narrative': 1, 'rule': 26} · provenance 0
LEDGER fabrik-command-improve.yaml: 150 entries · classes {'ban': 55, 'prose': 95} · vanished {'narrative': 5, 'rule': 34} · provenance 0
LEDGER fabrik-conformance-review.yaml: 91 entries · classes {'ban': 25, 'prose': 66} · vanished {'narrative': 11, 'rule': 42} · provenance 0
LEDGER fabrik-data-contract.yaml: 105 entries · classes {'ban': 30, 'prose': 75} · vanished {'rule': 64} · provenance 0
LEDGER fabrik-decommission.yaml: 71 entries · classes {'ban': 32, 'grammar': 2, 'prose': 37} · vanished {'rule': 39} · provenance 0
LEDGER fabrik-deploy-checklist.yaml: 106 entries · classes {'ban': 36, 'prose': 70} · vanished {'narrative': 3, 'rule': 47} · provenance 0
LEDGER fabrik-deploy-plan-review.yaml: 81 entries · classes {'ban': 36, 'grammar': 1, 'prose': 44} · vanished {'narrative': 1, 'rule': 31} · provenance 0
LEDGER fabrik-deploy-plan.yaml: 110 entries · classes {'ban': 45, 'prose': 65} · vanished {'duplicate-of': 1, 'narrative': 1, 'rule': 12} · provenance 0
LEDGER fabrik-deploy-verify.yaml: 129 entries · classes {'ban': 62, 'prose': 67} · vanished {'rule': 62} · provenance 0
LEDGER fabrik-deploy.yaml: 106 entries · classes {'ban': 52, 'grammar': 3, 'prose': 51} · vanished {'rule': 50} · provenance 0
LEDGER fabrik-doc-converge.yaml: 43 entries · classes {'ban': 17, 'prose': 26} · vanished {'rule': 15} · provenance 0
LEDGER fabrik-docs-review.yaml: 84 entries · classes {'ban': 22, 'grammar': 1, 'prose': 61} · vanished {'narrative': 1} · provenance 0
LEDGER fabrik-epics-review.yaml: 140 entries · classes {'ban': 66, 'behavioural': 1, 'grammar': 1, 'prose': 72} · vanished {'duplicate-of': 1, 'narrative': 6, 'rule': 83} · provenance 0
LEDGER fabrik-epics.yaml: 223 entries · classes {'ban': 72, 'prose': 151} · vanished {'narrative': 2, 'rule': 60} · provenance 0
LEDGER fabrik-execute-plan.yaml: 406 entries · classes {'ban': 152, 'prose': 254} · vanished {'duplicate-of': 3, 'narrative': 10, 'rule': 26} · provenance 0
LEDGER fabrik-features.yaml: 60 entries · classes {'ban': 22, 'behavioural': 1, 'prose': 37} · vanished {'narrative': 2, 'rule': 36} · provenance 0
LEDGER fabrik-flows-review.yaml: 68 entries · classes {'ban': 18, 'behavioural': 1, 'prose': 49} · vanished {'narrative': 10, 'rule': 30} · provenance 0
LEDGER fabrik-flows.yaml: 80 entries · classes {'ban': 22, 'prose': 58} · vanished {'duplicate-of': 1, 'narrative': 2, 'rule': 30} · provenance 0
LEDGER fabrik-generate-tests.yaml: 40 entries · classes {'ban': 16, 'prose': 24} · vanished {'rule': 13} · provenance 0
LEDGER fabrik-plan-after-chat.yaml: 261 entries · classes {'ban': 105, 'behavioural': 10, 'prose': 146} · vanished {'narrative': 2, 'rule': 25} · provenance 0
LEDGER fabrik-plan-review.yaml: 167 entries · classes {'ban': 75, 'behavioural': 15, 'prose': 77} · vanished {'narrative': 5, 'rule': 35} · provenance 0
LEDGER fabrik-release.yaml: 72 entries · classes {'ban': 24, 'prose': 48} · vanished {'duplicate-of': 1, 'narrative': 3, 'rule': 64} · provenance 0
LEDGER fabrik-repo-review.yaml: 70 entries · classes {'ban': 29, 'prose': 41} · vanished {'duplicate-of': 1, 'rule': 12} · provenance 0
LEDGER fabrik-reverse-engineer.yaml: 39 entries · classes {'ban': 16, 'prose': 23} · vanished {'rule': 8} · provenance 0
LEDGER fabrik-review-scoped.yaml: 74 entries · classes {'ban': 40, 'grammar': 2, 'prose': 32} · vanished {'duplicate-of': 1, 'narrative': 2, 'rule': 13} · provenance 0
LEDGER fabrik-review.yaml: 276 entries · classes {'ban': 91, 'behavioural': 27, 'grammar': 52, 'prose': 106} · vanished {'narrative': 16, 'rule': 37} · provenance 0
LEDGER fabrik-rivals.yaml: 95 entries · classes {'ban': 38, 'prose': 57} · vanished {'narrative': 8, 'rule': 66} · provenance 0
LEDGER fabrik-rules-review.yaml: 70 entries · classes {'ban': 17, 'prose': 53} · vanished {'narrative': 2, 'rule': 28} · provenance 0
LEDGER fabrik-service-test.yaml: 85 entries · classes {'ban': 34, 'grammar': 4, 'prose': 47} · vanished {'rule': 17} · provenance 0
LEDGER fabrik-spec-review.yaml: 131 entries · classes {'ban': 38, 'behavioural': 5, 'prose': 88} · vanished {'narrative': 3, 'rule': 21} · provenance 0
LEDGER fabrik-spec.yaml: 158 entries · classes {'ban': 84, 'prose': 74} · vanished {'narrative': 5, 'rule': 105} · provenance 0
LEDGER fabrik-task.yaml: 100 entries · classes {'ban': 45, 'prose': 55} · vanished {'rule': 88} · provenance 0
LEDGER fabrik-ui-design-review.yaml: 82 entries · classes {'ban': 24, 'behavioural': 3, 'prose': 55} · vanished {'narrative': 6, 'rule': 39} · provenance 0
LEDGER fabrik-ui-design.yaml: 122 entries · classes {'ban': 41, 'behavioural': 3, 'grammar': 2, 'prose': 76} · vanished {'duplicate-of': 1, 'narrative': 3, 'rule': 28} · provenance 0
LEDGER fabrik-upstream.yaml: 84 entries · classes {'ban': 28, 'prose': 56} · vanished {'duplicate-of': 1, 'narrative': 8, 'rule': 66} · provenance 0
LEDGER fabrik-user-test.yaml: 85 entries · classes {'ban': 25, 'prose': 60} · vanished {'narrative': 11, 'rule': 83} · provenance 0
LEDGER fabrik-vision.yaml: 582 entries · classes {'ban': 107, 'prose': 475} · vanished {'duplicate-of': 6, 'narrative': 7, 'rule': 201} · provenance 0
LEDGER fabrik-workflow-review.yaml: 43 entries · classes {'ban': 13, 'prose': 30} · vanished {'narrative': 2, 'rule': 29} · provenance 0
LEDGER hibernate.yaml: 26 entries · classes {'ban': 6, 'grammar': 2, 'prose': 18} · vanished {'narrative': 1, 'rule': 14} · provenance 0
LEDGER agent-feedback.yaml: 20 entries · classes {'ban': 5, 'prose': 15} · vanished {'narrative': 2, 'rule': 2} · provenance 0
LEDGER autonomy-run.yaml: 38 entries · classes {'ban': 20, 'prose': 18} · vanished {'rule': 20} · provenance 0
LEDGER cert-board-contract.yaml: 31 entries · classes {'ban': 16, 'prose': 15} · vanished {'narrative': 3, 'rule': 12} · provenance 0
LEDGER cert-execution.yaml: 17 entries · classes {'ban': 7, 'prose': 10} · vanished {'rule': 13} · provenance 0
LEDGER cert-handoff-grammar.yaml: 5 entries · classes {'ban': 4, 'prose': 1} · vanished {'rule': 4} · provenance 0
LEDGER cert-visual-deliverable.yaml: 3 entries · classes {'prose': 3} · vanished {'rule': 2} · provenance 0
LEDGER close-chain.yaml: 9 entries · classes {'ban': 5, 'grammar': 1, 'prose': 3} · vanished {'rule': 4} · provenance 0
LEDGER close-feedback.yaml: 68 entries · classes {'ban': 21, 'grammar': 5, 'prose': 42} · vanished {'narrative': 1, 'rule': 40} · provenance 0
LEDGER deploy-chain.yaml: 14 entries · classes {'ban': 3, 'prose': 11} · vanished {'rule': 4} · provenance 0
LEDGER design-critique.yaml: 22 entries · classes {'ban': 7, 'prose': 15} · vanished {'narrative': 1, 'rule': 13} · provenance 0
LEDGER design-gate-panel.yaml: 19 entries · classes {'ban': 6, 'prose': 13} · vanished {'rule': 6} · provenance 0
LEDGER design-review.yaml: 45 entries · classes {'ban': 2, 'grammar': 1, 'prose': 42} · vanished {'narrative': 2, 'rule': 9} · provenance 0
LEDGER fabrik-gui.yaml: 14 entries · classes {'ban': 4, 'grammar': 2, 'prose': 8} · vanished {'rule': 4} · provenance 0
LEDGER fabrik-researcher.yaml: 76 entries · classes {'ban': 24, 'grammar': 11, 'prose': 41} · vanished {'narrative': 1, 'rule': 51} · provenance 0
LEDGER fabrik-reviewer.yaml: 35 entries · classes {'ban': 12, 'grammar': 7, 'prose': 16} · vanished {'rule': 15} · provenance 0
LEDGER judge-panel.yaml: 5 entries · classes {'ban': 3, 'prose': 2} · vanished {'rule': 1} · provenance 0
LEDGER no-workflow-hub.yaml: 4 entries · classes {'ban': 2, 'prose': 2} · vanished {'rule': 1} · provenance 0
LEDGER orient.yaml: 8 entries · classes {'ban': 3, 'grammar': 2, 'prose': 3} · vanished {'rule': 8} · provenance 0
LEDGER review-probe-catalogue.yaml: 66 entries · classes {'ban': 44, 'prose': 22} · vanished {'narrative': 1, 'rule': 49} · provenance 0
LEDGER run-record.yaml: 24 entries · classes {'ban': 9, 'grammar': 3, 'prose': 12} · vanished {'rule': 3} · provenance 0
LEDGER scope-growth-exit.yaml: 6 entries · classes {'ban': 3, 'prose': 3} · vanished {'narrative': 1, 'rule': 3} · provenance 0
LEDGER term-coverage.yaml: 31 entries · classes {'ban': 11, 'prose': 20} · vanished {'duplicate-of': 1, 'narrative': 3, 'rule': 24} · provenance 0
LEDGER term-edit.yaml: 63 entries · classes {'ban': 40, 'grammar': 4, 'prose': 19} · vanished {'narrative': 1, 'rule': 6} · provenance 0
72 passed in 146.64s (0:02:26)
$ python3 scripts/enforcement/check_convergence.py
⚠ check_convergence ADVISORY — committed plan(s) needing attention:
  ⚠ docs/development/plans/archived/2026-08-07-plan-1-autotrigger-and-commands/2026-08-07-plan-1-autotrigger-and-commands.md: claims EXECUTED but its cited whole-plan review is missing on disk or not coverage-adjudicated …
  ⚠ docs/development/plans/archived/2026-08-15-plan-1-login-once-credentials/2026-08-15-plan-1-login-once-credentials.md: claims EXECUTED but its cited whole-plan review is missing on disk or not coverage-adjudicated …
  … (6 `⚠ docs/` lines in all, every one under docs/development/plans/archived/; 0 about this plan)
rc=0
```

```
$ .venv/bin/python scripts/final_gate.py --check --json   # on this receipt's staged change, before this block was pasted
"status": "success"
"skipped_checks": ["static tier"]   # diff-sensed: only .md files in the diff, so lint/type debt is not asserted
check outcomes: 34 pass · 22 advisory · 1 skipped · 0 fail
```

The gate is re-run on the final text before the commit; the commit's own gate line is the authority.
