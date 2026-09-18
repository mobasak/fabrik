# Review — the Fable band clamp (`_fleet_band`)

Status: IN-PROGRESS

Surface: `0a019413f` — `scripts/sysadmin/claude_rotate.py` (+ the byte-identical `scripts/aro-wake`
twin) and `tests/test_claude_fleet.py`. 24/1 lines in each twin, 60/0 in the grader.

## What shipped

`_fleet_band` takes a keyword-only `account_fable_pct` and, on the `fable=True` path only, clamps the
returned band UP to `_band_of(account_fable_pct, …)` when the active account's own Fable window is
hotter than the fleet's reading. Wired at the `band_fable` call site in `_quota_posture` (passing
`fb_u`); the `band` call for the two REQUIRED windows is untouched and keeps Delta 9 seat A F3's
decoupling. New module constant `_BAND_SEVERITY`.

## Why

The relief leg flips on `hot` = max(`five_hour`, `seven_day`) — `_fleet_tick_inner`, `hot >= drain_thr`
— and never reads the Fable window. So an active account at its Fable wall is never a flip trigger,
and the fleet's cool Fable reading names headroom no tick will ever move an unpinned session onto.
Measured live 2026-09-18: the posture carried `band_account_fable: RED` beside `band_fable: GREEN`
with `minutes_to_wall: 0.0`, the fleet reading Fable 21% at `can` — whose weekly 88% also keeps the
relief leg bouncing off it (`--switch can` 09:18:31, tick relief 09:19:12 `at_pct=88.0`, twice).
Every Fable session on that account was told to work normally until the operator reported it.

## Evidence (this session, executed)

- Watched RED: the new grader run in a throwaway `git worktree add --detach` at HEAD with only the
  test file copied to its exact path (source unfixed, marker `grep -c` = 0) → `- RED / + GREEN`.
- `tests/test_claude_fleet.py tests/test_quota_posture.py` → `366 passed in 116.46s`.
- `final_gate.py --json --check` with the changed files STAGED → one failure, `Doc Sync Matrix`
  (CHANGELOG), closed by `3185a8133`/`afdac2e8b`; ruff re-run in scope after staging (the first run
  was SCOPE-NARROWED and asserted nothing about the two changed `.py` files).
- Blast radius: two production callers of `_fleet_band`, both in `_quota_posture`; only the
  `band_fable` one passes the new argument, and `quota_posture_hook.py:407-409` is its only reader.

## REJECTED in this run — do not re-propose

Excluding drain-band-weekly accounts from `_fleet_readings` itself. It broke 7 existing graders,
one citing the 2026-09-17 operator ruling directly, because it collapses the fleet weekly AMBER into
"the active account only": hot-on-weekly (≥ 85) IS the drain band, so no reachable sibling can ever
supply an AMBER weekly reading. Reverted before commit; recorded in D-295.

## Pass ledger

| Pass | Finders | Found | Method |
|---|---|---|---|
| Pass 1 | author (self-review, no independent seat) | found: 2 | method: read every changed hunk plus the enclosing function and both callers; ran the two suites; red-on-revert in a throwaway worktree |

Pass 1's two findings were both the author's own and both fixed in-run: the first clamp keyed on
`account_band` (= `_band_of(hot_f)`, the hottest of all THREE windows) would have banded a cool Fable
session RED off its account's weekly — the 2026-09-17 "as if only one account exists" defect on this
path; and the broader `_fleet_readings` predicate above. No independent reader has seen this diff.

## RESUME

This run is HANDED OFF, not converged: the surface classifies as **operator-named work**, which the
rendered `/fabrik-review-scoped` names as a route-up trigger to the full `/fabrik-review`, and the
closing pass owes an independent non-authoring reader that this session has not dispatched.

Resume with `/fabrik-review` over `0a019413f` (its `start` naming
`--surface "ROUTED-UP: step 1 — operator-named work · 0a019413f"`). The attack list is in the
handoff reason and in this file's REJECTED and Pass-ledger sections; the open question a fresh seat
should answer first is (8) below.

Open rows for the successor:

1. Is the clamp keyed on the right quantity, and does the `account_fable_pct=4.0` / `account_band="RED"`
   pin actually fail if the argument is swapped back to `account_band`?
2. `_BAND_SEVERITY` against every value `_band_of` and the hold path can produce (`WALL`, `None`) —
   the hold/WALL early return precedes the clamp; prove it rather than reading it.
3. The one-directional claim: a cool account must never cool a HOT fleet reading.
4. Doc Sync — the three CLAUDE.md band bullets say a Fable session is banded on the hottest of 5h,
   weekly and Fable. Is that still true after the clamp, and is a contract edit owed?
5. Should the relief leg itself become Fable-aware (the capability fix), making the fleet reading
   TRUE rather than merely reported honestly? That changes flip policy and is the operator's call.

## Deferred, with its reason

Not deferred for convenience: at the time of the handoff the active account `can` sat at weekly 91%
against a cap of 99 with `wall in ~85m`, and the operator's `--pause-switch` marker was deliberately
held — so no relief flip could fire. Dispatching a multi-seat review onto that account risked walling
the fleet with its automatic successor disabled. The disposition is the operator's.
