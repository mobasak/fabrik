# Comprehensive scenario validation — every angle, all three providers

**Date:** 2026-06-17
**Status:** Plan
**Purpose:** Validate every executable path of the GPU surface against real provider accounts. Prior live testing (LIVE-1 through LIVE-18) covered the most expensive scenarios; this pass covers the remaining matrix corners without burning >$2 total spend.

---

## §0. State going in

| Test class | Already verified |
|---|---|
| Unit tests | ✅ 59/59 pass |
| Comprehensive scenarios | ✅ 26/26 pass (S1–S10) |
| Live pod-mode | ✅ RunPod (G-LIVE-2/3), Modal (G-LIVE-7/8), Vast (G-LIVE-5) |
| Live serverless | ✅ RunPod (G-LIVE-1), Modal echo (LIVE-12), Modal vLLM lifecycle (LIVE-13 partial), Vast endpoint (LIVE-14), Vast vLLM lifecycle (LIVE-15 partial) |
| Live reaper | ✅ Vast orphan (LIVE-17), cross-provider read (LIVE-16) |
| Auto-routing | ✅ Dry-run only (LIVE-18) — **not yet real-executed** |
| Final gate | ✅ status=success |

## §1. Scenarios this plan ADDS (NEW live coverage)

| ID | Scenario | Provider | Cost target | Why it matters |
|---|---|---|---|---|
| **CSV-1** | `--provider auto` for serverless, REAL execution (not dry-run) | auto→Modal | <$0.05 | Verifies that auto-routing's recommendation actually produces a working `rent()` call end-to-end |
| **CSV-2** | `--provider auto` for pod-mode | auto→RunPod | <$0.05 | Same but on the pod path |
| **CSV-3** | `--keep-warm-after-use` on RunPod COMMUNITY pod-rtx-4090 | RunPod | <$0.01 | Verifies the keep-warm flag actually leaves the pod alive after CLI exit (then we manually destroy) |
| **CSV-4** | `--keep-on-failure` with a work_fn that raises | Modal | <$0.05 | Verifies the pod survives when keep_on_failure=True |
| **CSV-5** | Cost guard live-trip (`--max-cost 0.001`) | each | $0 | Verifies GPUBudgetExceededError fires BEFORE any provider call |
| **CSV-6** | `fabrik gpu list / status / destroy` against a LIVE session per provider | each | <$0.05 | Verifies provider-aware CLI dispatch end-to-end |
| **CSV-7** | Modal orphan cleanup via reaper `--auto-destroy --provider modal` | Modal | <$0.05 | Parallel to LIVE-17 (Vast); proves reaper works on Modal too |
| **CSV-8** | Simultaneous multi-provider orphans → `reconcile --provider all --auto-destroy` cleans both | Modal+Vast | <$0.10 | Stress test: one orphan on each, single reconcile run drops both |
| **CSV-9** | Invalid template name fails BEFORE create | Modal | $0 | Defensive — bad input shouldn't bill anything |
| **CSV-10** | Daily envelope guard live-trip (`MAX_DAILY_GPU_COST=0.01`) | each | $0 | Verifies the per-day cap is enforced live |
| **CSV-11** | `fabrik gpu compare` produces a valid recommendation per (kind, util, flags) tuple | n/a | $0 | Decision-as-code sanity |
| **CSV-12** | `fabrik gpu history` shows entries from all 3 providers | n/a | $0 | Audit-log readability |
| **CSV-13** | Vast workergroup recruitment timeout → driver returns cleanly | Vast | <$0.05 | Edge case: marketplace can't supply a worker; the lifecycle still cleans up |

**Total spend ceiling: $0.50** (real spend will be ≤$0.10 given how short these are).

## §2. Scenarios deliberately OUT OF SCOPE (already verified or not worth re-testing)

| Scenario | Why skipping |
|---|---|
| Re-run LIVE-12/14/16/17 | Already GREEN; would just waste credit |
| Re-run pod-mode lifecycle on RunPod/Modal/Vast | Already GREEN in earlier gates |
| vLLM inference completion (LIVE-13/15 inference path) | Workload-tuning concern, not Fabrik invariant. Documented in CHANGELOG |
| 26-scenario suite | Will re-run as part of FINAL gate |
| 59 unit tests | Will re-run as part of FINAL gate |

## §3. Execution order (cheap → expensive, parallel where independent)

| Step | Scenario IDs | Mode |
|---|---|---|
| 1 | CSV-9 (invalid template) + CSV-5 (cost guard) + CSV-10 (daily envelope) + CSV-11 (compare) + CSV-12 (history) | dry-run / zero-spend; can run in parallel |
| 2 | CSV-2 (auto→RunPod pod-mode) | live, ~$0.005 |
| 3 | CSV-1 (auto→Modal serverless echo) | live, ~$0.005 |
| 4 | CSV-3 (keep-warm RunPod) — then manual destroy | live, ~$0.005 |
| 5 | CSV-4 (keep-on-failure Modal) | live, ~$0.01 |
| 6 | CSV-6 (gpu list/status/destroy via CLI) — one per provider against actual sessions | live, ~$0.02 total |
| 7 | CSV-7 (Modal orphan + reaper) | live, ~$0.05 |
| 8 | CSV-8 (multi-provider simultaneous orphans) | live, ~$0.05 |
| 9 | CSV-13 (Vast workergroup timeout) | live, ~$0.05 |
| 10 | Final: re-run 26 scenarios + 59 unit tests + final_gate.py + orphan paranoia | $0 |

## §4. Validation gates (per scenario)

Every scenario asserts:

1. **Pre-state**: orphan check on the relevant provider returns 0 active
2. **Action**: scenario command runs
3. **Outcome**: matches expected result (exit code, returned dict shape, log line presence)
4. **Post-state**: orphan check returns 0 (or the explicitly-kept-warm resource gets manually destroyed before next scenario)
5. **Cost recorded**: scenario reports its actual spend, accumulates in a session ledger

## §5. Failure criteria

- ANY scenario leaves an orphan after its cleanup → STOP, manual destroy, report
- Cost guard fails to fire when budget exceeded → STOP, drive bug fix
- `--provider auto` picks a provider that fails to execute → STOP, drive bug fix
- Final gate fails → STOP, drive bug fix

## §6. Convergence criterion

All 13 CSV scenarios + the comprehensive suite + unit tests + final gate ALL pass on a single uninterrupted run, with zero orphans at end, ≤$0.50 total spend.

