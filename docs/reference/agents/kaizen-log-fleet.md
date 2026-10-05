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
| 2026-08-30 | 100% (1/1) | — | — | 9.7 (n=21) | — | — | 18 filed / 9 none / 17 unstated |
| 2026-09-06 | — | 0 occ / 0 cls | — | 20.8 (n=23) | — | **The relief wake could reach almost nobody: the Stop decider's 2-hour mtime prune deleted every self-watch's never-touched lock file — 25 of 30 watcher processes on the box held a deleted inode, invisible to the tick's armed census, and every re-arm the nag ordered died the same way two hours later (heavy review R1 of plan 2026-09-07-plan-1-relief-wake). Fixed at both ends with graders seen red first — the prune skips flock-held files, the watch exits when its lock vanishes (harness W11) — 11898a4b. Second: old fleet tests wrote real lift files into the live lock dir and woke three sessions bogusly — `tests/conftest.py` pins `CLAUDE_SOUND_LOCKDIR` for every test (dd294a3f). Review rounds/plan 20.8 is the week's own cost signal: 13 docs-review passes, most chasing line numbers my comment fixes shifted — the `numstat N/N` rule is now in the run feedback.** | 62 filed / 33 none / 0 unstated (auto) · fleet this week: 01M1XBD4PHR3DS8JEF7S5CSC6R, 01M1XGZFDBQAZNWQ8QSEEJKEP0, 01M1XJ3XTQSZ17RBFVHQ586MKF, 01M1XXNFMYHKKGB3R11JX9D62Z, 01M1Y86PQF7R658QRNX52GGMX6, 01M1YA36XE8S1HHZR30H4T6YXC, 01M1YPN9D4R858K6KNJFSXABRJ |
| 2026-09-08 | — | 0 occ / 0 cls | — | 9.7 (n=38) | — | — | 327 filed / 2059 none / 0 unstated |
| 2026-09-20 | — | 0 occ / 0 cls | — | 6.3 (n=49) | — | — | 491 filed / 240 none / 0 unstated |
| 2026-09-26 | — | — | — | 32.7 (n=9) | — | — | 5 filed / 4 none / 0 unstated |
| 2026-09-30 | — | — | — | 22.9 (n=15) | — | **The `fabrik-zitadel` scrape target was down from 2026-08-29 and its critical `ServiceUnhealthy` alert fired 747 hours: `/debug/metrics` answered Go's bare 404 (no Prometheus exporter registered) while `/debug/healthz` answered 200 on the same host. The spec now names `ZITADEL_INSTRUMENTATION_METRIC_EXPORTER_TYPE: prometheus`, guarded by `tests/test_zitadel_spec.py` (seen red) — 9e5a79cbb, 1ef93040f; live once the operator runs `fabrik apply specs/services/zitadel.yaml`. My first root cause ("v4.17.1 defaults it to none") was wrong: the legacy `Metrics.Type: otel` default should register one, so why the running container has none stays unverified. Review rounds/plan 22.9 is the week's cost signal: this fix's own review took 3 rounds, one of them re-opened for a docstring my claim sweep missed.** | 18 filed / 15 none / 0 unstated (auto) · fleet this week: W-714ae2cf (RegistrarDrift ×4), W-4801e4c3 (Prometheus ContainerHighMemory at 46% working set), W-e8014a88, W-00ae4256, 01M3WQ8GHE, 01M3WQBFJ3 · 10-05 pass (collection 01M45SMW, 23/23 targets up, 2 alerts firing): W-0d604e43 — the two `FabrikRegistrarDrift` alerts firing since 10-03 are D-524's two real drifts, paper Backrest plans `zitadel-data` and `tryton-crm-data` (audit_backrest: "paper plan …: remove it"); they had no owning item until this pass; removal is an operator-window write |
