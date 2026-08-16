# Kaizen log — fleet (weekly, Monday after the cron batch; ≤90 min timebox)

One row per pass. The five pinned metrics are SYSTEM-level (the repo/mesh this role's
runs move through), measured from this role's seat — reading another beat's logs to fill
a cell is reading, never beat-crossing; the role-specific SIGNALS drive the analysis and
the friction column. The FIVE pinned metrics are the spec's single set for both roles (comparable
across roles by design — intel audits both); fleet's raw SIGNALS (deploy failures, apply skips,
monitoring gaps, DR results) live in the charter and feed the analysis, not the columns.

Column ownership: the five metric cells are written by the Monday 06:45 `kaizen_metrics.py --once`
cron; `Top friction fixed` and `Filed` are the analyst's and a re-run never overwrites them. A `—`
means no real source supports that metric — the reason is in the hand-off mail and
`~/.claude/kaizen.log`; it is missing instrumentation, never a healthy zero. See
`docs/workstation/kaizen.md`.

| Date | Gate first-pass rate | Death-classes /wk | Lesson-class recurrence | Review rounds /plan | Missed crons | Top friction fixed | Filed (spec/mail) |
|---|---|---|---|---|---|---|---|
| 2026-08-12 | — | — | — | — | — | (baseline row — first real pass fills metrics) | — |
