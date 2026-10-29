# Kaizen log — infra (weekly, Monday after the cron batch; ≤90 min timebox)

One row per pass. The five pinned metrics are SYSTEM-level (the repo/mesh this role's
runs move through), measured from this role's seat — reading another beat's logs to fill
a cell is reading, never beat-crossing; the role-specific SIGNALS drive the analysis and
the friction column. Metrics per the roles spec — pinned small; metric theater is muda.

Column ownership: the mechanical metric cells are upserted into this week's row by the daily
`kaizen_collect_v2.py --daily` run (the wake-proof `weekly_catchup.sh` cron; `kaizen_metrics.py`
is retired — M1 T09); `Top friction fixed` and `Filed` are the analyst's and a re-run never overwrites them. A `—`
means no real source supports that metric — the reason is in the hand-off mail and
`~/.claude/kaizen.log`; it is missing instrumentation, never a healthy zero. See
`docs/workstation/kaizen.md`.

| Date | Gate first-pass rate | Death-classes /wk | Lesson-class recurrence | Review rounds /plan | Missed crons | Top friction fixed | Filed (spec/mail) |
|---|---|---|---|---|---|---|---|
| 2026-08-12 | — | — | — | — | — | (baseline row — first real pass fills metrics) | — |
| 2026-08-22 | 50% (1/2) | — | — | — | — | — | — |
| 2026-08-30 | 100% (1/1) | — | — | 9.7 (n=21) | — | — | 18 filed / 9 none / 17 unstated |
| 2026-09-06 | — | 0 occ / 0 cls | — | 20.8 (n=23) | — | — | 62 filed / 33 none / 0 unstated |
| 2026-09-08 | — | 0 occ / 0 cls | — | 9.7 (n=38) | — | — | 327 filed / 2059 none / 0 unstated |
| 2026-09-20 | — | 0 occ / 0 cls | — | 6.3 (n=49) | — | — | 491 filed / 240 none / 0 unstated |
| 2026-09-26 | — | — | — | 32.7 (n=9) | — | — | 5 filed / 4 none / 0 unstated |
| 2026-10-04 | — | — | — | 23.7 (n=19) | — | none fixed in-pass — top friction is the run-record Stop block firing every turn while background review seats run (premature_stop_rate 53%, 461/865; ~40 such blocks in one infra session 2026-10-05); a synced-hook change owing a full review, so W-4c7edc74 raised to P1 | 18 filed / 15 none / 0 unstated · W-4c7edc74 (P1), W-54b0e523, W-67fc4aad |
| 2026-10-11 | — | 0 occ / 0 cls | — | 23.8 (n=24) | — | merge requests refused on a fetch timeout during network blips (4 re-sends on 2026-10-12): an unreachable remote now defers and the next run retries it (b03ba9505, D-775); a 0-row parity leg could shrink the merge denominator (6ecb3e4cc, D-763) | 32 filed / 124 none / 0 unstated; W-cd73ac65 (hole_count 105 vs coroner 0 for 10-11), W-6c06c35d (collector leaves kaizen logs dirty), W-5713c693 |
| 2026-10-25 | 67% (4/6) | 0 occ / 0 cls | — | 5.1 (n=105) | — | none fixed in-pass — top friction is the Stop hook's `coordinator` cause: 1,201 of W43's 5,729 stop_block events (913 blocked, 158 warned through, 130 stood down; blocked by action continue 227 · claim 155 · mail 143 · feedback 119 · owned 116); its 158 warned-through episodes record no subject (`final_gate_stop.py:5521-5523`), so the loop no session clears is unattributable — filed W-dc65dae2 (the run-record cause's 2,732 stood-down rows are the hold working, not friction) | 98 filed / 248 none / 0 unstated · W-dc65dae2 |
| 2026-10-27 | 100% (4/4) | 0 occ / 0 cls | — | 3.3 (n=95) | — | — | 16 filed / 73 none / 0 unstated |
