# Code review — fleet quota advisory: fire only at active-account wall (a0f56598)

**Status:** IN-PROGRESS — closing confirming round dispatched; ledger/verdict finalized from its actual report.

**Surface:** HEAD=a0f565987b5bab1a3f9132665644af9e7b28dc36 · diffmd5=f21bc0600c171945963f2b9b3aa7185d
(reviewed the change + its two applied fix commits on top)
**Command:** /fabrik-review · **Reviewer:** fleet (non-author sweep of own build) · **Date:** 2026-08-26
**Scope:** `scripts/sysadmin/claude_rotate.py` + its byte-identical `scripts/aro-wake/` twin +
`tests/test_claude_fleet.py`. The change replaces the per-account ≥85% advisory loop with
`_fleet_active_wall_advisory` (fire ONE fleet-wide advisory only when the post-flip active account is
walled with no auto-relief; epoch-free latch).

## Verdict

**2 real defects found in self-review + FIXED (both red-on-revert proven); 4 pool candidates REFUTED
with path:line; 1 self-found candidate REFUTED. Closing native Opus sweep on the fixed code: PENDING
(verdict finalized from its actual report).**

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
| RLS / JWT / auth / migrations / FastAPI / chrome-ext (rubric MATCHED) | N/A | workstation rotation script — no DB/web/auth/migration surface exists to review |

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

```
Pass 1 (WIDE) — finders: pool(deepseek,gemini,qwen via fanout review) + self(Opus decide) | classes: logic,
   None, fail-open/closed, latch, concurrency, removed-guard, cross-file, broadcast, message, test-quality
   | found: 5 raised (2 CONFIRMED → dwell, permanent-suppression; 3 REFUTED → slugs, cap0, TOCTOU/broadcast)
   | fixed: 2 | → not done (changed code)
   (native Opus finder #1 stalled at launch — 130B, no findings; re-dispatched fresh for the closing sweep)
Pass 2 (SCOPED, fix diff + callees) — self(Opus) | classes: dwell-false-alarm, message-accuracy,
   latch-permanent-suppression | found: 1 raised (oscillation) → REFUTED | fixed: 0 | → confirming sweep owed
Pass 3 (CLOSING, FULL fresh, non-author) — pool ×3 (deepseek, gemini, qwen via fanout review) on the FIXED
   code (native fabrik-reviewer stalled twice at launch — 130B, likely the quota degradation this change
   addresses; the pool is the non-author breadth) | classes: latch/re-arm timing, dwell false-suppression,
   None/exception, fail-open/closed | found: 1 raised (dwell-gate suppressing a real exhaustion IF
   `_validated_pick` returned a WALLED account as a false successor) → REFUTED (finding 7: `_validated_pick`
   uses the SAME `ROTATE_THRESHOLD` and `_flip_churn_excluded` excludes ≥threshold, so a returned successor is
   genuine headroom by the same definition) | fixed: 0 | → not quiet (raised 1) → confirming round owed
Pass 4 (FINAL confirming, non-author) — pool ×3 with finding 7 stated as adjudicated | RUNNING (result filled
   from its actual report — never pre-claimed)
```

**Verdict is NOT final until Pass 4 returns found: 0 and the gate JSON is embedded below.**

## Gate

(final_gate.py --json verbatim — appended after the closing sweep)
