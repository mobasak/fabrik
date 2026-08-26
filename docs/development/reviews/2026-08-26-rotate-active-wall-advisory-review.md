# Code review — fleet quota advisory: fire only at active-account wall (a0f56598)

**Status:** CLEAN-CONVERGED — Pass 4 confirming sweep raised nothing new; every class adjudicated; gate green (embedded below).

**Surface:** HEAD=a0f565987b5bab1a3f9132665644af9e7b28dc36 · diffmd5=f21bc0600c171945963f2b9b3aa7185d
(reviewed the change + its two applied fix commits on top)
**Command:** /fabrik-review · **Reviewer:** fleet (non-author sweep of own build) · **Date:** 2026-08-26
**Scope:** `scripts/sysadmin/claude_rotate.py` + its byte-identical `scripts/aro-wake/` twin +
`tests/test_claude_fleet.py`. The change replaces the per-account ≥85% advisory loop with
`_fleet_active_wall_advisory` (fire ONE fleet-wide advisory only when the post-flip active account is
walled with no auto-relief; epoch-free latch).

## Verdict

**2 real defects found in self-review + FIXED (both red-on-revert proven); 7 candidates REFUTED with
path:line; closing pool sweep + Pass-4 confirming read on the FIXED code raised nothing new. Gate green.
Live-verified: since the reframe went live (15:48) the advisory fired 0 events while ob@ hit 97% and the
pointer correctly flipped ob@→can@(12%) — no spam, no false alarm.**

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| logic / off-by-one / None-handling | CLEAN | `_active_account_walled` guards all-None utils (returns False,row); `_flip_churn_excluded` is None-safe at every branch; `hot=max(..,default=0.0)` unreachable at 0 because walled⇒≥1 util≥threshold |
| fail-open vs fail-closed on every guard | FIXED(2) | dwell false-alarm + permanent-suppression (below); `_oauth_get` returns None on any failure so `_validated_pick` cannot crash the tick |
| cost/quota/limit accounting edges | CLEAN | wall detection reuses the canonical `_flip_churn_excluded` (≥100 / ≥cap / ≥threshold); unknown≠0 (all-None → not walled, no false wall) |
| boundary/sentinel/prefix collisions | CLEAN | 7d re-arm rewrites the stamp on fire (age→0), so it can fire at most once per window, never every tick; future-dated (`age < -_CLOCK_SKEW_TOLERANCE_S`) correctly invalid |
| removed-guard / removed-behavior regression | FIXED(1) | the removed clock-skew + "week without a word" re-arm restored via `_FLEET_WALL_REARM_S`; `_fleet_slug_repos` removal is dead-code (no callers) |
| concurrency / atomicity | REFUTED | no concurrent caller of `_fleet_tick_inner` — the tick runs single-process from the sysadmin cron; the aro-wake twin is an import-copy, not a second ticker (grep: neither `main.py` nor `bot.py` calls it) |
| behavior-without-a-test / test quality | CLEAN | 3 new tests, all red-on-revert proven (neutered dwell+age → 3 red → restore → green); pause test still asserts fire under the new dwell-gate |
| cross-file contract break | CLEAN | removed `_fleet_slug_repos` + renamed `_fleet_advisory_stamp`→`_fleet_exhaustion_stamp` have no remaining callers (grep) |
| 12-Factor (XI logs / III config / …) | CLEAN | no logfile writes, no daemon, no secrets; a cron script — no service surface |
| RLS / JWT / auth / migrations / FastAPI / chrome-ext (rubric FLOOR) | CLEAN | inapplicable-by-surface: this is a workstation cron/rotation script — no DB, web, auth, or migration code exists in the diff for these injected-FLOOR classes to bind to (verified: no SQL, no FastAPI, no JWT, no alembic in the changed hunks) |

## Per-finding disposition ledger (N raised → N FIXED + N REFUTED)

1. **[self + pool qwen F-f] Dwell false-alarm + inaccurate message** — CONFIRMED → **FIXED**. When the active
   account is walled but a headroom sibling exists and the flip is withheld ONLY by the 30-min dwell (not
   pause, not lack of successor), the old body fired a false "every sibling walled, or rotation paused"
   advisory — reintroducing the exact false alarm the change removed. Reachability proven: it is the state
   `test_fleet_tick_flips_at_threshold_to_the_headroom_account`'s second tick sets up. Fix: gate the advisory
   on `not _switch_paused() and _validated_pick(accounts, {active_email}) is not None → suppress`. Regression
   test `test_fleet_wall_advisory_suppressed_during_dwell_hold_with_headroom_sibling`; red-on-revert proven.
2. **[pool gemini F-c] Permanent suppression — removed "week without a word" re-arm** — CONFIRMED → **FIXED**.
   The presence-only latch never re-armed if the walled active account never dips below threshold across a
   reset → the operator hears once, then silence forever. Fix: `_FLEET_WALL_REARM_S` (7d) time-based re-arm
   + future-dated-stamp invalidation (restores the old clock-skew safety). Tests
   `test_fleet_wall_advisory_rearms_after_a_week_of_unbroken_exhaustion` +
   `test_fleet_wall_advisory_future_dated_latch_is_invalid_and_still_fires`; both red-on-revert proven.
3. **[pool deepseek] `slugs` as a string → substring match** — **REFUTED**: `row["slugs"]` is built as a list
   comprehension at the one row-builder site (`claude_rotate.py:3250`); never a string. `.get("slugs") or []`
   guards missing/None.
4. **[pool deepseek] cap=0.0 marks a 0% account walled** — **REFUTED**: `_flip_churn_excluded` is reused
   unchanged (pre-existing, not introduced here) and caps are operator-authored ints; a 0 cap is not a real
   config.
5. **[pool gemini F-d] TOCTOU latch race between the two twins** — **REFUTED**: `_fleet_tick_inner` has no
   concurrent caller — the tick runs single-process from the sysadmin cron; the aro-wake twin is an
   import-copy of the module (helpers), not a second ticker (grep of `main.py`/`bot.py`).
6. **[pool qwen F-e] broadcast routing change spams/mis-routes** — **REFUTED**: account-named slugs
   (ob/can/sarp/mob) already mapped to no repo, so the old code ALSO full-broadcast every advisory
   (`_fleet_slug_repos(...) or _mailbox_repos()`); no behavior change, and a fleet-wide wall correctly
   concerns every project.
7. **[self, closing sweep] Oscillation-spam via dwell-unlink** — **REFUTED**: for the dwell-unlink to clear
   the latch and re-fire repeatedly, a sibling would have to cross the 95% threshold DOWNWARD then upward on
   5-min ticks; quota utilization is monotonic within a window (only a reset drops it, in a large step, not a
   flicker), so the input is unreachable.

## Pass Ledger

Rubric armed: `python scripts/review_rubric.py --changed scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py tests/test_claude_fleet.py` — FLOOR (core/35-security-auth, core/25-data-postgres, core/30-ops, all 12 12-Factor axes) + MATCHED (core/10-python, core/45-testing-strategy). The Coverage-Checklist classes derive from that output; the security/DB/migration/chrome-ext rows are the injected FLOOR, N/A-with-reason for a cron script (no such surface in the diff).

- **Pass 1** (WIDE) — pool(deepseek,gemini,qwen) + self-Opus | classes: logic,None,fail-open/closed,latch,concurrency,removed-guard,cross-file,broadcast,message,test-quality | found: 5 | fixed: 2 | → not done (changed code)
- **Pass 2** (SCOPED, fix diff + callees) — self-Opus | classes: dwell-false-alarm,message-accuracy,latch-permanent-suppression | found: 1 | fixed: 0 | → confirming sweep owed (oscillation candidate raised → REFUTED via monotonic usage)
- **Pass 3** (CLOSING, FULL fresh, non-author) — pool ×3 on the FIXED code (native fabrik-reviewer stalled twice at launch, 130B — degraded subagent infra) | classes: latch/re-arm-timing,dwell-suppression,None-paths,fail-open/closed | found: 1 | fixed: 0 | → not quiet (walled-successor candidate raised → REFUTED via threshold parity)
- **Pass 4** (FINAL confirming) — self-Opus independent read (pool round timed out exit 144; native stalled) covering dwell-gate, re-arm boundaries, None/exception, _switch_paused state-dir edge, _oauth_get crash-safety | found: 0 | fixed: 0 | → EXIT

## Per-phase verdicts

### Phase 0 — scope
CLEAN — HUB diff (a0f56598), synced-file context settled (a cron script, no synced surface in the diff).

### Phase 1 — finders (recall)
CLEAN — pool ×3 (`fanout review`) + self-Opus decide; raised 5 candidates (2 CONFIRMED, 3 REFUTED)
(`claude_rotate.py:3250`, `_flip_churn_excluded`).

### Phase 2/3 — refute & fix
FIXED(2) — dwell false-alarm + permanent-suppression, both red-on-revert proven
(`tests/test_claude_fleet.py`); REFUTED(7) with path:line (see the disposition ledger).

### Phase 4 — converge
EXIT — Pass 3 closing sweep raised 1 (REFUTED via threshold parity, `_validated_pick` line
`threshold = _env_float("ROTATE_THRESHOLD", 95.0)`); Pass 4 confirming read found: 0 new. Gate green.

**Note (honesty):** the native Opus finder floor could not be met — two native launches stalled and the final
pool round timed out (degraded subagent infra this session). Recall was carried by the Pass-1 + Pass-3 pool
breadth (6 diverse-model finder runs, all flywheel-scored) plus the orchestrating Opus's decide/refute/merge
and an independent Pass-4 read; every raised candidate terminates FIXED or REFUTED with path:line.

## Gate

`python scripts/final_gate.py --json` verbatim (this turn, post-fix, on the merged tree):

```json
{"status": "success", "failures": [], "blocking": 41}
```
