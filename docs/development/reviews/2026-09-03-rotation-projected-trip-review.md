# Review — auto-switch: the tick trips on the PROJECTED reading; the board's fast path fires at the drain line when blind (2026-09-03)

**Command:** `/fabrik-review` (operator-named: "session limit passed 95% and it did not switch automatically? fix it … second time today … check both daily session and weekly limits") · **Scope:** the uncommitted diff — `scripts/sysadmin/claude_rotate.py` (+ byte-identical twin `scripts/aro-wake/claude_rotate.py`), `tests/test_claude_rotate_v2.py` (+4), `scripts/sysadmin/quota_dashboard.py`, `tests/test_quota_dashboard.py` (+3), three workstation docs, CHANGELOG, D-103 · **Method:** NO-POOL (standing directive) — in-line finders over a fixed class ledger; every survivor executed · **Verdict:** CONVERGED — round 2 re-swept every class with 0 findings; gate green.

## Phase 0 — Scope digest and the measurement that drove it

| Episode (tick log, no timestamps — order by line) | What the machinery said | Verdict |
|---|---|---|
| 19:50–20:10, ob@ active | `active ob@ at 89% … 93% … 96% — session below 98%, no flip`; next tick: ob@ at 100%, the operator had switched by hand (ledger `ob → can via switch` 20:10) | **Defect 1** — a 98 trip point checked every 5 min is unobservable when the inter-tick burn is 3–4% |
| same window, the board | `probe failed (TimeoutExpired … --status --json … 60.0 seconds)` × 7 consecutive, then `active ob session 100% >= 98%` (too late) | **Defect 2** — the 20 s fast path evaluated only the last GOOD reading (96 < 98) while blind |
| ~01:07, can@ active | `active can@ at 100% but NO successor has headroom`; ob 92 ≥ cap 80, sarp 91 ≥ cap 90, mob at 95 | **Not a defect** — the operator's caps spent the pool; the manual override to sarp was theirs |
| ~12:10, mob@ active | one tick `mob@ at 98% but NO successor` then `flipped mob → can` (ledger via tick, 98%) | transient, self-healed |

Probe timing now: `--status --json` 1.4–1.8 s (healthy API); 136 `TimeoutExpired` lines in the current log file (spans several restarts).

## Phase 1 — Finders (in-line, class-partitioned)

| # | Class | Candidate | Verdict |
|---|---|---|---|
| 1 | correctness | `_tick_burn` infers a burn across an account change / a rolled-over window / a stale memory | **REFUTED by test** — same email, same reset epoch per window, memory ≤ 900 s; `test_projection_needs_the_same_account_same_window_and_a_recent_reading` |
| 2 | fail-open | corrupt or unwritable `tick-last-reading.json` | **CLEAN** — degrades to the plain threshold, never raises (`test_projection_never_raises_on_a_corrupt_memory`); swallows exactly `_STATE_DIR_ERRORS` like every other state file |
| 3 | churn | a one-turn spike (85 → 95) projects 105 and flips at 95 | **CLEAN by design** — the operator's rule is "never hit the wall"; the candidate predicate (≥ threshold excluded) and the 30-min dwell bound ping-pong; the flip line says `(projected — reading + burn since the last tick)` so the ledger shows why |
| 4 | boundary/sentinel | the weekly leg with a cap: projection applies (78 → 79 at cap 80 trips) | **CLEAN** — `test_weekly_cap_leg_also_trips_on_the_projection`; weekly burns are ≤1%/tick so the projection is a no-op except at the edge |
| 5 | cost/quota | `_tick_burn` runs once per tick (the flip leg only — `grep` shows one call site); the blind fast path runs a tick at most once per cooldown (120 s) | **CLEAN** |
| 6 | contract/twin | `scripts/aro-wake/claude_rotate.py` is a byte-identical twin (AFTER-EDIT header) | **FIXED** — copied, `cmp` clean |
| 7 | correctness | the dashboard's `probe_failed` flag survives a later successful probe | **REFUTED by test** — `_probe()` returns a fresh dict; `test_a_sighted_probe_clears_the_blind_flag` |
| 8 | behavior-without-a-test | the blind bar below the drain line stays quiet; the blind path honours the cooldown | **CLEAN** — both asserted (`test_a_blind_probe_below_the_drain_line_stays_quiet`, cooldown assertion in the trigger test) |
| 9 | denominator-honesty | "136 timeouts since the last restart" | **FIXED** — the log spans several restarts; reworded |
| 10 | docs-stale | hooks-index § 2c said fleet mode has "structurally NO account switch" | **FIXED** — the flip leg has existed since the 2026-08-15 redesign; sentence rewritten with the projection |
| 11 | mypy | 4 errors in `claude_rotate.py` | **REFUTED as mine** — all four pre-exist at HEAD (lines 1216, 1862, 2191, 3273; none in the diff) |
| 13 | correctness (found by the LIVE tick, not the tests) | the reset epoch the usage endpoint reports jitters by a fraction of a second per call (1788470999.95 → 1788471000.35), so the exact-equality "same window" check never matched and the burn was ALWAYS 0 in production — the unit tests used identical epochs | **FIXED** — same window = epochs within 60 s; `test_projection_tolerates_reset_epoch_jitter_between_probes` (seen red first); proven live: a seeded memory 4 points lower printed `at 86% (+4 since last tick)` |
| 12 | dwell | a flip withheld "within dwell (30m of the last flip)" — seen once today after a manual switch | **OUT OF SCOPE, stated** — not today's cause; a manual switch followed by a wall inside 30 min would be held; the operator's `--switch` is the escape hatch |

## Phase 2 — Verify / refute

Every FIXED/CLEAN row was executed: rotation suite 115 green (5 new, 3 seen red first: 92 → 96 at 98, 78 → 79 at cap 80); dashboard suite 44 green (3 new, 2 seen red first); a live `--tick` on the box printed the burn-aware line and wrote the memory file; the board restarted on the new code with a sighted probe (`probe_failed: None`).

## Phase 3 — Prove

```
$ pytest -q tests/test_claude_rotate_v2.py tests/test_claude_rotate_capture.py → 115 passed
$ pytest -q tests/test_quota_dashboard.py → 44 passed
$ python3 scripts/sysadmin/claude_rotate.py --tick | grep '^tick: active'
tick: active can@ocoron.com at 86% (+4 since last tick) — session below 98%, weekly below cap 99, no flip
$ cmp scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py → identical
```

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

| Round | classes swept | found | new classes | note |
|---|---|---|---|---|
| 1 | correctness · fail-open · churn · boundary/sentinel · cost/quota · contract/twin · behavior-without-a-test · denominator-honesty · docs-stale | 4 | contract/twin · docs-stale · live-vs-fixture | twin copied, wording fixed, § 2c rewritten, reset-epoch jitter (the live tick's finding) tolerated |
| 2 (method: re-derivation) | the same ledger after the fixes: suites re-run, `cmp` re-run, live tick re-run, the log re-read | **0** | — | TERMINAL |

Standing classes: fail-open **CLEAN** (row 2) · cost/quota **CLEAN** (row 5) · boundary/sentinel **CLEAN** (row 4) · behavior-without-a-test **CLEAN** (row 8; the one untested path is the live cron cadence itself — proven by the next real crossing, which the ledger will show as a `(projected …)` flip).
