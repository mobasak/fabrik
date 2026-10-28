# Lean command program — final report for the operator

Answers W-ee67bd9f (operator 2026-10-26: "when the command lean work finished, i want to see a full report what changed against yesterday morning state of the commands … against the finished work"). The comparison is the tag `lean-baseline-2026-10-25` (`7ed30f4bc`, the morning the program started) against master `c812b5cbf` (2026-10-28, after the last lean merge).

## The numbers

- **Rules kept: all of them.** Across the 40 commands and 23 shared files there are 63 rule ledgers, holding 5,425 entries, and the rule check reports 0 LOSS. A ledger lists every rule-bearing line of a file's starting text. When a line vanished from its file, the ledger names where it went: 1,979 lines moved to another file (each proven by the check), and the rest were classed as narrative or duplicates.
- **Rendered words (what an agent loads when it runs a command), all 40 commands:** 596,988 → 579,853, **97.1%** of the starting size.
- **Full measure (the command plus its seat definitions and the files it orders read):** 919,518 → 888,817, **96.7%**.
- **Own text of the 63 ledgered files:** 226,025 → 217,451 words, **96.2%**.

## The 50% goal was missed — and why

The program's goal was every command at half its size or less with no rule lost. **No command and no shared file reached 50%.** Each one closed instead on a recorded floor under the coordinator's ruling D-1254: 0 LOSS, an independent audit with zero counts, and a floor table showing why its own text cannot go lower without dropping a rule.

The reason was measured, not guessed (D-1259, 2026-10-26). The pilot, /fabrik-review-scoped, reached only 89% against a 60% kill bar. Across about 17 light units with independent audits, the result was 49.8–100% (median ~91%) once every rule an auditor flagged as cut had been restored. The words in these commands are mostly rules, and the rules are what make them long. The pre-agreed KILL test therefore fired: no new rewrite unit started, and the 50% headline was retired in favour of per-file floors. You then ruled (D-1293, W-8d2815a8 answer A): finish the units already running, keep every rule, spend the API and cloud credits first, and rework the rules themselves in a later program.

## What changed in how the commands work

- **No command does anything differently.** By design, every rule survived: a lost or reworded rule is a LOSS, and the check exits red on it. The rewrites removed repetition, stories and restatements, and tightened wording. Behaviour is unchanged.
- **Two guards now stand on the corpus:**
  1. **The rule check (live).** `python3 commands/assemble_commands.py --check` fails on any LOSS. A future edit cannot silently drop a rule from a ledgered file.
  2. **The size ceiling, L1 (live).** Each command has a ceiling in `commands/_size_ceiling.json`. An edit that grows a command past its ceiling fails `--check` (exit 5) unless a decision row licenses the raise. Every merge lowers each ceiling to 3% above the command's new size (`--ratchet`) and never raises one. A command can therefore grow by at most 3% without a recorded decision.
- **Not landed: L2, the `remove:` field.** This is the required "what could be removed" answer at every command close, and it is the part of the program that asks the feedback loop for leanness. Its code is infra-2's open item W-a9b5e763. Until it lands, the spec keeps `/fabrik-command-improve` paused.
- **Not run: T05a–c.** Ten shared fragments (`subagents-core`, three `grounding-*`, `chat-intake`, `delegated-reads`, `injection`, `questionbar`, `repo-identity`, `test-generation-loop`) had not started when the KILL test fired. They are unchanged and have no ledger yet.

## Every command

Rendered words are what the agent loads. The full measure adds the seat definitions and the command's own reads, against the baseline published in `commands/_size_ceiling.json`.

| Command | Rendered words, baseline | Rendered words, master | Ratio | Full measure (own + seats + own reads), ceiling baseline → master |
|---|---:|---:|---:|---|
| /design-review | 14942 | 14663 | 98.1% | 23194 → 22578 (97.3%) |
| /fabrik-catchup | 7326 | 7115 | 97.1% | 10542 → 10063 (95.5%) |
| /fabrik-command-improve | 10536 | 10270 | 97.5% | 22453 → 21701 (96.7%) |
| /fabrik-conformance-review | 17515 | 16878 | 96.4% | 24448 → 23520 (96.2%) |
| /fabrik-data-contract | 17266 | 16970 | 98.3% | 24199 → 23612 (97.6%) |
| /fabrik-decommission | 7369 | 7107 | 96.4% | 10585 → 10055 (95.0%) |
| /fabrik-deploy | 9415 | 9114 | 96.8% | 12631 → 12062 (95.5%) |
| /fabrik-deploy-checklist | 18612 | 18092 | 97.2% | 25545 → 24734 (96.8%) |
| /fabrik-deploy-plan | 9302 | 9092 | 97.7% | 12518 → 12040 (96.2%) |
| /fabrik-deploy-plan-review | 14249 | 13807 | 96.9% | 21182 → 20449 (96.5%) |
| /fabrik-deploy-verify | 9806 | 9443 | 96.3% | 15351 → 14673 (95.6%) |
| /fabrik-doc-converge | 16097 | 15823 | 98.3% | 23030 → 22465 (97.5%) |
| /fabrik-docs-review | 16363 | 16104 | 98.4% | 30204 → 29328 (97.1%) |
| /fabrik-epics | 16864 | 16366 | 97.0% | 23797 → 23008 (96.7%) |
| /fabrik-epics-review | 21681 | 21109 | 97.4% | 28614 → 27751 (97.0%) |
| /fabrik-execute-plan | 21366 | 20898 | 97.8% | 40554 → 39412 (97.2%) |
| /fabrik-features | 16317 | 15907 | 97.5% | 23250 → 22549 (97.0%) |
| /fabrik-flows | 16621 | 16228 | 97.6% | 23554 → 22870 (97.1%) |
| /fabrik-flows-review | 18140 | 17542 | 96.7% | 25073 → 24184 (96.5%) |
| /fabrik-generate-tests | 7097 | 6934 | 97.7% | 14030 → 13576 (96.8%) |
| /fabrik-plan-after-chat | 21575 | 21340 | 98.9% | 28508 → 27982 (98.2%) |
| /fabrik-plan-review | 23211 | 22729 | 97.9% | 37052 → 35953 (97.0%) |
| /fabrik-release | 6736 | 6373 | 94.6% | 9952 → 9321 (93.7%) |
| /fabrik-repo-review | 17835 | 17317 | 97.1% | 24768 → 23959 (96.7%) |
| /fabrik-reverse-engineer | 5638 | 5410 | 96.0% | 8230 → 8003 (97.2%) |
| /fabrik-review | 27571 | 26747 | 97.0% | 41412 → 39971 (96.5%) |
| /fabrik-review-scoped | 9551 | 9257 | 96.9% | 34855 → 33640 (96.5%) |
| /fabrik-rivals | 12612 | 12135 | 96.2% | 19545 → 18777 (96.1%) |
| /fabrik-rules-review | 16324 | 16029 | 98.2% | 23257 → 22671 (97.5%) |
| /fabrik-service-test | 17484 | 16786 | 96.0% | 24417 → 23428 (95.9%) |
| /fabrik-spec | 19105 | 18516 | 96.9% | 38097 → 37157 (97.5%) |
| /fabrik-spec-review | 20672 | 20085 | 97.2% | 34513 → 33309 (96.5%) |
| /fabrik-task | 8714 | 8294 | 95.2% | 11306 → 10887 (96.3%) |
| /fabrik-ui-design | 14053 | 13596 | 96.7% | 20986 → 20238 (96.4%) |
| /fabrik-ui-design-review | 18565 | 18085 | 97.4% | 25498 → 24727 (97.0%) |
| /fabrik-upstream | 8670 | 8013 | 92.4% | 15603 → 14655 (93.9%) |
| /fabrik-user-test | 18885 | 17743 | 94.0% | 27137 → 25658 (94.5%) |
| /fabrik-vision | 22541 | 22158 | 98.3% | 32333 → 31431 (97.2%) |
| /fabrik-workflow-review | 15521 | 15120 | 97.4% | 22454 → 21762 (96.9%) |
| /hibernate | 4841 | 4658 | 96.2% | 4841 → 4658 (96.2%) |
| **all 40** | **596988** | **579853** | **97.1%** | **919518 → 888817 (96.7%)** |

## Every rule-ledgered file (commands and shared files)

Own text at the unit's start commit against master. 'Lines moved' counts baseline lines that left the file and are proven present elsewhere; 'narrative' and 'duplicate' count lines the ledger classed as carrying no rule. Every ledger currently reports 0 LOSS. The floor column names the ruling each file closed under; its per-file floor arithmetic is in the unit's receipt under `docs/development/reviews/2026-10-25-plan-1-lean-command-corpus-T*-receipt.md`.

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

Unledgered (T05a-c, never started — D-1259): `commands/_fragments/chat-intake.md`, `commands/_fragments/delegated-reads.md`, `commands/_fragments/grounding-artifact.md`, `commands/_fragments/grounding-code.md`, `commands/_fragments/grounding-rules.md`, `commands/_fragments/injection.md`, `commands/_fragments/questionbar.md`, `commands/_fragments/repo-identity.md`, `commands/_fragments/subagents-core.md`, `commands/_fragments/test-generation-loop.md`

## Where the proof lives

- Close-out receipt with every command output: `docs/development/reviews/2026-10-25-plan-1-lean-command-corpus-review.md`
- The ledgers: `commands/_rules/*.yaml` and `commands/_rules/_shared/*.yaml`; the check: `commands/command_rules.py` (run by `python3 commands/assemble_commands.py --check`)
- Rulings: D-1216 (the program), D-1217 (the spec), D-1254 (floors), D-1259 (KILL), D-1293 (finish, keep every rule)
