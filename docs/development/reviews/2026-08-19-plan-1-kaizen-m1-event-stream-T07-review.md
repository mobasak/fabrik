# T07 review — outcome tier (rework miner + fleet-health sweep + premature-stop)

## Rounds — 3 to the no-op

Finders per round: pool deepseek/deepseek-v3.2-exp (gemini-3-flash-preview errored region-403
every round — VPN egress) + native fabrik-reviewer, grounded live in the worktree,
repro-before-report. Pool yield: 0 across all rounds (round-1 partition swept clean with a
reasoned NO FINDINGS). Native yield: 7 → 6 → **0**.

| Round | Found | Fixed in | The load-bearing ones |
|---|---|---|---|
| 1 | 7 (3 CONFIRMED) | 9fa1b454 | stop_block_causes fabricated "clean" when nothing was measured (paired-dash rule now enforced); `hotfix` regex precedence matched anywhere in a subject (docs mentions inflated rework — live-reproduced); sweep timeout orphaned grandchildren past the budget (start_new_session + killpg, with a real forked-sleeper repro); premature_stop aligned to T06's PREMATURE_CAUSES (imported, cross-referenced) so it no longer counts legitimate gate-red holds |
| 2 | 6 (1 CONFIRMED) | 1223a59a | bare post-SIGKILL reap unbounded (now wait(5) → "timeout (unreapable)", fail-open); `hotfix\b` ("hotfixture:" reproduced matching); PREMATURE_CAUSES import guarded (vocab hole dashes only the stops pair — rework/sweep still run); event-unit consistency in the histogram; rc-passthrough pin; timeout-test leak hygiene |
| 3 | **0** | — | every class refuted with evidence: the int/str marker flow is isinstance-guarded at all four call sites, registry() is static-tuple-independent of the vocab import, units are intentional and cross-referenced, the always-raising-wait fake is faithful |

Every functional fix red-first (per-finding RED runs recorded by the coder; two red-on-revert
proofs with md5-verified byte-identical restores). 15 → 28 tests. Live `--sweep --only fabrik`
smoked on every round's final code (65.8–66s < 300s budget), real events store untouched.

## Close

Orchestrator re-verified first-hand at 1223a59a: 28 passed · ruff clean · mypy clean.
**found: 0, fixed: 0 — T07 accepted.** Commits 1f94cb4d + 9fa1b454 + 1223a59a, squash-applied
at merge (2 files, both new — no conflicts possible).

Forward items recorded for the spine/T09: `fleet_health` needs its EVENT_TYPES row +
schema-doc entry (T09); the T06-side cross-reference in `METRIC_DEFS` is deliberately NOT
edited (a formula-string change mutates `premature_stop_rate@v1`'s def_hash — the versioned-
definitions law makes that a version bump, T09's call); the sweep's honest finding that a
clean HEAD clone of fabrik fails its suite install-less (pytest rc=2) is a REAL repo finding,
tracked outside this ticket.
