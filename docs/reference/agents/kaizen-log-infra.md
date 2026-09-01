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
| 2026-08-31 | — | — | — | 12.2 (n=8) | — | — | 62 filed / 33 none / 0 unstated |
