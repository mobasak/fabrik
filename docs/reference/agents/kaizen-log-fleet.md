# Kaizen log — fleet (weekly, Monday after the cron batch; ≤90 min timebox)

One row per pass. The five pinned metrics are SYSTEM-level (the repo/mesh this role's
runs move through), measured from this role's seat — reading another beat's logs to fill
a cell is reading, never beat-crossing; the role-specific SIGNALS drive the analysis and
the friction column. The FIVE pinned metrics are the spec's single set for both roles (comparable
across roles by design — intel audits both); fleet's raw SIGNALS (deploy failures, apply skips,
monitoring gaps, DR results) live in the charter and feed the analysis, not the columns.

Column ownership: the mechanical metric cells are upserted into this week's row by the daily
`kaizen_collect_v2.py --daily` run (the wake-proof `weekly_catchup.sh` cron; `kaizen_metrics.py`
is retired — M1 T09); `Top friction fixed` and `Filed` are the analyst's and a re-run never overwrites them. A `—`
means no real source supports that metric — the reason is in the hand-off mail and
`~/.claude/kaizen.log`; it is missing instrumentation, never a healthy zero. See
`docs/workstation/kaizen.md`.

| Date | Gate first-pass rate | Death-classes /wk | Lesson-class recurrence | Review rounds /plan | Missed crons | Top friction fixed | Filed (spec/mail) |
|---|---|---|---|---|---|---|---|
| 2026-08-12 | — | — | — | — | — | (baseline row — first real pass fills metrics) | — |
| 2026-08-19 | — | 221 occ / 4 cls | — | 2.5 (n=11/14) | 17/27 | **Missed crons 17/27 (63%) = the 2026-08-19 whole-table `crontab <file>` wipe (Lesson 128) — blast radius: rotation tick, keepalive, dashboard refresh, DR mirrors, all project crons. HEALED 08-23: crontab restored to 41 jobs; root-caused a deeper latent bug — `claude` absent from cron's PATH (`~/.local/bin` excluded) silently failed every keepalive/refresh ping (817479d1). Quota-advisory duplicate storm (mob 85→87→90→91/tick) fixed — dedup keyed on the sliding 5h reset (51181918).** (death 221/4cls: classes in `~/.claude/kaizen.log`; this pass's high-blast item was the cron wipe.) | 817479d1 (cron-PATH) · 627f8815 (oauth retry) · 51181918 (advisory dedup) |
| 2026-08-22 | 50% (1/2) | — | — | — | — | — | — |
