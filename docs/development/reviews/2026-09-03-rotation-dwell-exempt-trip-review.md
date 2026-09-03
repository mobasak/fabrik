# Review — rotation: a trip flip is never held by the 30-minute dwell (2026-09-03)

**Command:** `/fabrik-review` (operator directive: "this is not the correct way … session limits immediately stop all running agents … I don't want my running agents stopped while I pay for 4 Max accounts") · **Scope:** `scripts/sysadmin/claude_rotate.py::_fleet_flip_leg` (+ byte-identical twin `scripts/aro-wake/claude_rotate.py`), `tests/test_claude_rotate_v2.py` (+1), the rotation reference § Dwell, hooks-index § 2c, CHANGELOG, D-104 · **Method:** NO-POOL (standing directive), in-line finders · **Verdict:** CONVERGED — round 2 re-swept every class with 0 findings; gate green.

## Phase 0 — Scope digest

One kwarg: the tick's trip flip calls `_flip_active(slug, at_pct=at_pct, ignore_dwell=True)`. Measured before touching it: 3 `flip … within dwell — holding` lines in the tick log; today's — mob@ cap-walled, `flip to ob within dwell (30m of the last flip) — holding` repeated on every board-invoked tick until the operator's `POST /switch ob` — was the day's second manual rescue.

## Phase 1 — Finders

| # | Class | Candidate | Verdict |
|---|---|---|---|
| 1 | churn | without the dwell, can two accounts ping-pong? | **REFUTED** — the target predicate (`_flip_candidate_verdict`) never picks a sibling at/over `ROTATE_THRESHOLD`, without 5h budget (> 85), walled or cap-walled; the flip-away trigger needs the ACTIVE account at the line. A → B → A needs B at the line within one tick of receiving the pointer — then B was not a valid target |
| 2 | boundary/sentinel | both legs exempt? | **CLEAN** — one call site serves the session line and the weekly cap; `test_a_trip_flip_is_never_held_by_the_dwell` asserts `ignore_dwell=True` on both (seen red first) |
| 3 | fail-open | pause marker / stale-chain refusals | **CLEAN** — untouched: `ignore_dwell` skips only the dwell block; pause (unless manual) and the liveness gate still refuse |
| 4 | contract/twin | aro-wake twin | **CLEAN** — copied, `cmp` identical |
| 5 | docs-stale | rotation reference § Dwell, hooks-index § 2c ("under the 30-min dwell" — written by me an hour earlier), `_fleet_active_wall_advisory` docstring premise | **FIXED** — all three updated; the advisory's dwell-held branch is now reachable only through the pause and says so |
| 6 | cost/quota | none — no new probes, no new timers | **CLEAN** |
| 7 | behavior-without-a-test | the legacy tick keeps its dwell (`test_t3_dwell_blocks_then_allows`, unchanged and green) | **CLEAN** |

## Phase 2 — Verify

Rotation suite 116 green (1 new, seen red first); `cmp` twin identical; ruff clean.

## Phase 3 — Prove

Gate (`final_gate.py --check --json`, run on this tree):

```json
{
  "status": "success",
  "passed": 56,
  "failed": 0,
  "skipped": 0
}
```

## Phase 4 — Converge

| Round | classes swept | found | new | note |
|---|---|---|---|---|
| 1 | churn · boundary/sentinel · fail-open · contract/twin · docs-stale · cost/quota · behavior-without-a-test | 1 | docs-stale | three passages fixed |
| 2 (method: re-derivation) | same ledger after the fix: suite re-run, `cmp` re-run, `grep -n dwell` over the three docs re-read | **0** | — | TERMINAL |

Standing classes: fail-open **CLEAN** (3) · cost/quota **CLEAN** (6) · boundary/sentinel **CLEAN** (2) · behavior-without-a-test **CLEAN** (2, 7).
