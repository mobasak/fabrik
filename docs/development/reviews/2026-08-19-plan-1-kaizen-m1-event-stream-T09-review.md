# T09 review — integration: daily cutover, kaizen_metrics retirement, docs, receipts

## Rounds — 2 to convergence

Finders per round: pool deepseek/deepseek-v3.2-exp (gemini-3-flash-preview errored region-403 —
VPN egress) + native fabrik-reviewer grounded live in the worktree AND against the live box
(crontab, real store). Pool yield: 0 (NO FINDINGS, reasoned). Native yield: 5 → 4 (round 2 all
doc-truthfulness/notes — zero functional survivors).

| Round | Found | Fixed in | The load-bearing ones |
|---|---|---|---|
| 1 | 5 (2 CONFIRMED) | 7f29344c | the retirement trap — post-merge, the live crontab's retired `kaizen_metrics.py` line would have errored rc=2 HOURLY forever (now: retired-key branch, rc=0 + a stamp-checked once-per-day nudge, red-proven all three contract points); AFTER-EDIT header pre-move path; liveness max_age 30→54 with the arithmetic stated; the wave also closed the coder's own standing items — kaizen_outcomes --stops/review_rounds era crash (red-proven live: `premature_stop: 17% (1/6)` on the real mixed store), instrument_alarm vocabulary + doc row, grounded stale-ref sweep across 5 docs |
| 2 | 4 (2 CONFIRMED doc) | folded at merge | docs asserted the cutover cron LIVE while the crontab swap rides the operator's pending post-wipe restore — pending-caveat folded into fleet.md, infra.md, wsl-startup-inventory.md and the kaizen_outcomes docstring; liveness.md's stale weekly-06:45 cross-reference corrected; the era-narrowing now recorded in-band as a POPULATION NOTE (formula strings stay verbatim — a formula edit is a def-hash version bump) |

Round-2 residue recorded as forward notes, no code owed: `weekly_catchup.sh` has no automated
test harness (pre-existing class; the retired-key branch was manually verified twice — coder and
finder independently, all three contract points); the finder's refutation ledger retired every
other candidate with evidence (flock release, case ordering, `.get()` registry reads,
`_emit_alarm` shape parity at both call sites).

Build evidence (wave 1, f21bdae6): era filter red-proven at the exact predicted crash
(`AttributeError` at compute_metrics on the real store's 11,253 transcript rows — 148 in the
current ISO week); fleet_health vocabulary red-proven; the def-hash proof (`87e33255…` identical
before/after the non-hashed cross_reference); the cutover's job-table semantics red-proven
(retired stamp no longer masks, daily keys fire once); the live `--daily` smoke derived 341 real
sessions, published 3 series, and re-ran as a 0-append idempotent no-op; seam battery 301 → 333
with the retired-module suites.

## Close

Orchestrator re-verified first-hand on the merged tree (see the merge commit's battery run).
**found: 0 functional, fixed: 0 — T09 accepted.** Commits f21bdae6 + 7f29344c squash-applied
with the round-2 doc folds.

Standing operator dependency (named, not claimable): the two daily cron lines +
the full crontab restore ride ONE operator `crontab` install (classifier-blocked for agents);
until it lands the daily collector and sweep run only by hand, and liveness correctly reports
the surfaces unscheduled. The M1→M2 gate clock (7 days of daily event collection) STARTS at the
first cron-driven daily run, not at this merge.
