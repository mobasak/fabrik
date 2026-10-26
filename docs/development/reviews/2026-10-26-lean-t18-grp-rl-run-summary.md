# Re-ledger round summary — t18, t43, t41, t35 (W-96f36043)

Branches: claude/lean-t18-rl, claude/lean-t43-rl, claude/lean-t41-rl, claude/lean-t35-rl (each: loader-swap commit, then the ticket commit; each receipt has a "Re-ledger round" section).

| branch | own text baseline -> fix -> now | own-ledger LOSS | entries / reworded |
|---|---|---|---|
| t18 fabrik-catchup | 2329 -> 1967 -> 2026 (87%) | 73 -> 0 | 53 / 51 |
| t43 fabrik-rules-review | 2056 -> 1709 -> 1975 (96%) | 68 -> 0 | 70 / 63 |
| t41 fabrik-decommission | 2570 -> 1939 -> 2409 (94%) | 60 -> 0 | 71 / 67 |
| t35 fabrik-deploy | 4898 -> 3950 -> 4699 (96%) | 46 -> 0 | 106 / 102 |

Self-audit (one Sonnet auditor per branch, findings fixed afterwards; pre-fix COUNTS entries/reworded/weaker/lost/invented/wrong): t18 53/51/2/2/0/0 · t43 70/63/9/0/0/1 · t41 71/67/5/1/0/2 · t35 106/102/3/0/0/3. Post-fix recount not run; the loader reports zero LOSS. Hub author-blind audit still owed.

Reader-test failure sets: start 52-53 failed, end 66-67 failed on every branch. The new reds are the same 9 tests everywhere (test_command_rules::test_the_live_corpus_has_no_loss, test_command_measure::test_check_exit_order_loss_then_ceiling_then_drift, test_conftest_isolation drifted-box test, 6-7 test_assemble_dispatch_step orphan/corrupt tests): they assert the live corpus has no LOSS, which the canonical loader now reports for `_shared/*.yaml` (T01d's) and for other tickets' ledgers on the base. None names a ticket ledger above.

50% target NOT met; text grew vs the fix round. The canonical loader forces ban clauses verbatim to clause end (parentheticals/history included, D-1238 pt 1 forbids labelling them narrative) and one phrase per clause holding every anchor. Pure-telegraphic floor measured at 47-55% of unit words, unreadable. Hub decision needed on that policy.

Cloud-Dispatch: done unknown
