# T03 — Flywheel safety: un-mute the tripwire and prove the read

## Scope

Make the operator's binding constraint — *"we should not break flywheel"* — testable, and fix the defect
that makes a break invisible today.

The reader (`rank_task_subagents.py`) already distinguishes a **broken** flywheel read from a
**genuinely empty** one and returns exit 1 on broken, with a distinct stub, precisely so the "Last refresh"
date cannot advance on a lie. That safety property is real. **But the call site swallows it**:
`daily_refresh.sh` invokes the ranker with `|| echo "… (non-fatal)"`, so a broken read today publishes a
stub selection doc, fleet-syncs it to 49 vendored copies, and alerts nobody. The relocation is the single
event most likely to break that read — the reader authenticates through `sudo -n -u postgres psql`, a
property of the invoking CONTEXT, not of the file's path — so the detection path must work before anything
moves.

Three deliverables: a positive-proof probe (real, non-empty read — "it didn't crash" is not evidence when
the code fail-opens by design), a regression test pinning the `error → exit 1` + distinct-stub tripwire,
and the un-muting of the swallowed exit code so a break surfaces instead of echoing into a log nobody reads.

DO-NOT: do not alter the fail-open floor itself (`select.py:479-483`) — it bounds a break to staleness
rather than an outage and is the migration's safety net. This ticket makes breaks VISIBLE, it does not make
them fatal to `pick_models`.

**Environment preflight — run this FIRST, before writing anything.** The positive-proof probe depends on a
passwordless-sudo context that no manifest declares and that differs between the operator's shell, cron, and
any other user:

```
$ sudo -n -u postgres psql -d fabrik_analytics -tAc "SELECT 1"
1
```

Non-zero or a password prompt means the probe cannot run as written here — that is a BLOCKING condition to
report, not something to work around by weakening the assertion to "did not crash". The regression test for
the tripwire must NOT depend on this: it simulates the failure (monkeypatched subprocess), so it runs
anywhere.

Depends: —
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/catalog_contract/test_flywheel_safety.py -q
Docs: docs/TROUBLESHOOTING.md (recurring symptom: silent stub selection doc) — sole owner of this row; T05 does not duplicate it

## Touches
- scripts/kilo-benchmarks/daily_refresh.sh — PRIMARY PATH
- tests/catalog_contract/test_flywheel_safety.py

## Behavior Contract
- **Given** the flywheel read fails (psql/sudo unavailable), **When** `rank_task_subagents` runs, **Then** it emits the distinct broken stub and returns exit 1 rather than an empty-but-healthy result (scripts/kilo-benchmarks/rank_task_subagents.py:1374)
- **Given** the ranker returns exit 1, **When** `daily_refresh.sh` invokes it, **Then** an alert is fired on the same channel `check_daily_refresh_freshness.py` uses — propagating a non-zero exit is NOT sufficient (scripts/kilo-benchmarks/check_daily_refresh_freshness.py:1)
- **Given** a healthy flywheel, **When** the positive-proof probe runs, **Then** it asserts state `ok` AND a non-empty row set, failing if rows are empty (scripts/kilo-benchmarks/rank_task_subagents.py:175)
- **Given** the probe cannot reach the database at all (no passwordless sudo / no psql), **When** it runs, **Then** it FAILS loudly and never reports success or skips (docs/superpowers/specs/2026-07-26-catalog-extraction-design.md:240)
- **Given** the flywheel is genuinely empty but reachable, **When** the ranker runs, **Then** it exits 0 and does NOT emit the broken-read stub (scripts/kilo-benchmarks/rank_task_subagents.py:1114)
- **Given** the un-muting change, **When** an unrelated non-fatal step fails in the same run, **Then** the run's other `|| echo` non-fatal steps keep their existing behaviour (scripts/kilo-benchmarks/daily_refresh.sh:115)

## Context Files
- .windsurf/rules/core/55-observability.md
- .windsurf/rules/core/45-testing-strategy.md
- .windsurf/rules/core/58-resilience.md
- docs/superpowers/specs/2026-07-26-catalog-extraction-design.md
- scripts/kilo-benchmarks/rank_task_subagents.py
- libs/subagents/select.py
- scripts/kilo-benchmarks/check_daily_refresh_freshness.py
