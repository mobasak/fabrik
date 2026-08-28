# Whole-plan review — canary grounding (2026-08-28-plan-1-canary-grounding)

Surface: HEAD e29bc938d7e7beabf41f60ecc44e3727730d143f · diff md5 6f4bcea471bcfa9d566ac9288d3e889e (range 0bfdb98c..HEAD)

Scope: the CUMULATIVE diff `0bfdb98c..HEAD` (+ the live-regenerated selection doc) across all
three phases — the cross-phase net the per-phase reviews cannot see. Per-phase reviews (each to a
clean round, artifacts in this directory): phase-A (pool ×2, 2 fixed), phase-B (pool ×3 + native
Opus, 2 BLOCKING + 3 MAJOR fixed), phase-C (pool ×2 + docs-review no-op). Finders this pass:
pool deepseek/deepseek-v4-flash over the four cross-phase seams + orchestrator adjudication +
the LIVE end-to-end smoke as executable evidence.

## Rubric

Derived from `review_rubric.py --changed <File Scope>` runs recorded verbatim in the phase-B and
phase-C artifacts (same generator, same surfaces — this pass re-used those armed checklists for
the cross-phase sweep; re-run: `python scripts/review_rubric.py --changed <the File Scope paths>`).

## Coverage Checklist

| Class | Verdict |
|---|---|
| Harness row shape ↔ CANARY_QUERY expectations | CLEAN — proven EXECUTABLY by the live smoke: a real 3-model × 2-probe batch ($0.0017) wrote ordinary rows and `_query_canary_rows()` returned all three models at 5.0; the regenerated production doc shows real `✓` cells |
| Judge instruction ↔ judging rule ↔ doc | CLEAN — instruct-strict/judge-lenient is the deliberate design (spec re-freeze 0bfdb98c); all three texts agree on the prefix rule |
| Cadence ↔ window ↔ floor | CLEAN — weekly ≥2 probes/model always satisfies the ≥2-agent floor inside 30 days; a dead cron decays to `—` (no signal), never a wrong penalty |
| Doc promises vs shipped code | CLEAN — every claim verified in the docs-review no-op; the multiplier is documented as filed-upstream/visibility-only, which is exactly its state (mail 01M157W2GK) |
| Cross-phase signature consistency | CLEAN — `project="canary-grounding"` + `task_type="review"` literals identical across harness, queries, and tests (both halves tested against the same `SUBAGENT_RUNS_DDL`) |
| Regression into earlier phases | CLEAN — Phase B's review-fixes re-ran the Phase A suite each time (final: 27/27 across both suites) |
| Fail-open vs fail-closed (whole-axis) | CLEAN — every degraded direction lands on "no signal": non-done units unscored, floor-blocked models `—`, stale data decayed, canary query errors render `—`, organic rankings exclude canary rows |
| Cost/quota accounting | CLEAN — the measured-cost line sums KNOWN costs only (unknown counted separately, never as 0); the live batch printed $0.0017 against the $0.10 alarm threshold; pool review spend all cents-scale, every unit scored |
| Behavior-without-a-test (whole plan) | CLEAN — 27 tests, every non-trivial behavior red-first; width invariant red-on-revert; the one untestable-here behavior (the `select.py` multiplier) is the declared fabrik-lib residual |

## Requirements coverage (plan "What we already agreed" → shipped)

| Agreement | Delivered by |
|---|---|
| Per-model canary probes, explicit-model dispatch, binary prefix judge | 5cbeb833 (harness + 16 tests; judge PREFIX per the re-frozen spec) |
| Ordinary tagged rows, zero DDL | live rows under `project="canary-grounding"` (smoke batch) |
| Hub-side aggregation + `grounding` column (all emitters, `n` last) | ec05a490 (+ the organic-QUERY contract fixes the review forced) |
| Weekly cadence, fail-soft, operator cron, liveness row | 5cbeb833 docstring + c3f11d85 (registry row `canary-grounding-weekly`) |
| fabrik-lib multiplier filed upstream (REQUIRED note) | mail `01M157W2GK` (ack required) |
| Criterion 1 (≥2 rows/model + measured cost) | MEASURED LIVE: 2/model, $0.0017 printed |
| Criterion 3 (mechanical judge, test-proven) | judge suite (fabricating→0, refusing→5) |
| Criterion 5 (doc surfaces the signal) | live `✓` cells in TASK_SUBAGENT_SELECTION.md |
| Criteria 2 + 4-behavior (`pick_models` re-orders; no-data→1.0) | DEFERRED by design — the fabrik-lib enhancement (declared residual #1, filed) |

## Pass ledger

| Pass | finders | found | new | fixed |
|---:|---|---:|---:|---:|
| Pass 1 | pool ×1 (4 seams) + orchestrator + live smoke | 0 | 0 | 0 |
| Pass 2 | suites re-run post-doc-regen (27/27), fresh Tier-2 gate, requirements walk | 0 | 0 | 0 |

found: 0, fixed: 0 — coverage-adjudicated exit.

## Proofs

```
$ CANARY_ROSTER_N=1 .venv/bin/python scripts/sysadmin/canary_grounding.py --probes-per-model 2
| deepseek/deepseek-v4-flash | 5 | $0.0001 | … (6 units, 3 models × 2)
measured cost: $0.0017
$ _query_canary_rows() → ("ok", {"deepseek/deepseek-v4-flash": 5.0, "deepseek/deepseek-v4-pro": 5.0, "minimax/minimax-m2.5": 5.0})
$ TEST_DATABASE_URL=… uv run pytest scripts/kilo-benchmarks/tests/test_canary_grounding_column.py tests/test_canary_grounding.py -q → 27 passed
```
