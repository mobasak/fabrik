# T09 — integration: daily cutover, kaizen_metrics retirement, docs, receipts

Depends: T07, T08
Parallel: —
Integration: true
Complexity: native
## Touches
- scripts/sysadmin/weekly_catchup.sh
- scripts/sysadmin/kaizen_metrics.py
- scripts/sysadmin/archived/kaizen_metrics.py
- .fabrik/liveness-registry.json
- docs/workstation/kaizen.md
- docs/workstation/kaizen-event-stream.md
- tests/test_kaizen_collect_v2.py

## Context Files
- docs/workstation/kaizen-shrink-audit.md
- scripts/sysadmin/weekly_catchup.sh
- docs/workstation/kaizen.md
- docs/workstation/kaizen-event-stream.md
- .fabrik/liveness-registry.json



## Steps

1. **Cross-ticket seam run:** every producer ticket's Behavior-Contract tests + every seam test on
   the integrated tree (the D5/D7 requirement) — one command list, outputs embedded in the spine's
   Evidence.
2. **Live end-to-end smoke:** one real session window exercises the chain — session_start →
   run_open/close → gate_run → collector `--daily` on today's events → the kaizen-log row rendered
   with the new metric cells (`—` where the metric needs history, with reasons).
3. **Cutover:** add the DAILY collector job to `weekly_catchup.sh`'s job table
   (`kaizen_collect_v2.py --daily`, period 1 day, stamp-checked hourly — the wake-proof pattern);
   RETIRE `kaizen_metrics.py` per the operator ruling: `git mv` to
   `scripts/sysadmin/archived/kaizen_metrics.py`, remove its catch-up job entry, and re-point the
   liveness registry's `kaizen-measurement` surface (`cron_match: kaizen_collect_v2.py`) —
   `kaizen_metrics.py` is NOT in CORE_SCRIPTS (hub-local), so no manifest/sync step.
4. **Docs converge:** rewrite `docs/workstation/kaizen.md` (daily loop, event-era metrics, the
   analysis half unchanged); finalize `docs/workstation/kaizen-event-stream.md`; INDEX rows for
   the new doc + scripts; CHANGELOG entry; spec erratum if any deliverable diverged (stated, never
   silent).
5. **Whole-plan receipts:** `check_doc_sync.py --range <baseline>..HEAD` +
   `check_doc_stubs.py --range` + `/fabrik-docs-review` over the touched docs +
   `final_gate.py --check --json` embedded verbatim + `check_convergence.py` green.
6. **Post-plan observation note (the M-gate honesty):** the spine's completion stamp states the
   7-day event-collection window START date; the M1→M2 gate review (7 days of events, variance
   sign-off, denominators vs hand-counts) is a NAMED follow-up the operator triggers — not
   claimable at execution end.

## Behavior Contract

- **Given** the cutover, **When** the daily collector cron is live, **Then** `kaizen_metrics.py` is
  archived (operator ruling executed), its catch-up slot repointed, and the kaizen logs carry the
  new daily rows (scripts/sysadmin/weekly_catchup.sh).

Docs: docs/workstation/kaizen.md (rewrite) + docs/workstation/kaizen-event-stream.md (finalize) +
INDEX + CHANGELOG (via Deltas).
Gate: the step-5 receipt battery, all green, embedded.
