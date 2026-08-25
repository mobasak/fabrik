# Code review — payments-ingest registrar role

Reviewed surface: the payments-ingest build (commits `ff5bef2f` A, `71167e4b` B, `2e4841ca` C,
`a6f1fc5f` D) — `src/fabrik/spec_loader.py`, `src/fabrik/drivers/postgres.py`,
`src/fabrik/orchestrator/infrastructure.py` + tests + docs.
Command: `/fabrik-review` · Reviewer: fleet (non-author sweep of my own build) · Date: 2026-08-25

## Verdict

**1 real defect found + fixed; 4 candidates refuted with `path:line`; round-2 fresh sweep of 9 classes = `found: 0`.**

## Finding (FIXED)

**F1 — `_payments_ingest_drop_role_sql` was created but never wired into `drop_database` → orphan-role / stale-DSN wedge.**
- `drop_database` (postgres.py) drops the watchdog + subagent roles at BOTH its sites (`:1080` orphan-cleanup-when-DB-absent, `:1098` normal path) but did **not** drop the payments-ingest role — my helper (`postgres.py:788`) was dead code.
- **Failure scenario:** a DB drop+recreate leaves `{db}_payments_ingest` behind with its old password → the next `fabrik apply`'s `_role_exists` returns True → no fresh password minted → `PAYMENTS_INGEST_DATABASE_URL` stuck stale/wrong (the exact wedge the helper's own docstring describes).
- **Fix (`f6a2a0bd`):** wired `_payments_ingest_drop_role_sql(db_name)` into both drop sites. Regression tests for both the normal-drop and orphan-cleanup paths; **red-on-revert proven** (neutering the normal-path wiring fails `test_drop_database_also_drops_payments_ingest_role`).

## Refuted candidates (checked, not defects)

- **Sequence grant for `webhook_events` INSERT** — refuted: the real schema (`/opt/fabrik-lib/payments/db/schema.sql:94-104`) has no serial/identity (`event_id` is text; `received_at DEFAULT now()` is a function). No `USAGE ON SEQUENCE` needed; the granted `INSERT, SELECT` suffices.
- **Hyphenated db names** (`trade-intelligence`) — refuted: `db_name` is sanitized `name.replace("-", "_")` (`infrastructure.py:520/525`) before ALL three role calls (`create_database`/`create_watchdog_roles`/`create_payments_ingest_role` take the same `db_name`), so the path is identical to the deployed, working watchdog.
- **`resolve_applicability` consumers breaking on the new `payments_ingest` key** — refuted: every consumer (`infrastructure.py:430`, `destroyer.py:536`, `dev_tools.py:122-123`) uses a dict comprehension / `.items()`; no code asserts a fixed key set or count.
- **The "skips all 9 registrars" docstring** (`test_spec_loader.py:6`) — refuted as a defect: it's an illustrative module docstring, already stale before this change (the real count was ~10), and its point (shape=None → all registrars skipped) holds. Not introduced by this diff.

## Per-phase verdict

| Phase | Verdict |
|---|---|
| A — Shape flag + validator | CLEAN — additive, default false, `needs_database` validator + tests |
| B — `create_payments_ingest_role` | CLEAN after F1 fix — non-BYPASSRLS, scoped policies, drop now wired; 5 RLS invariants proven live |
| C — `_provision_postgres` wiring | CLEAN — flag-gated, fresh-password-only DSN, non-fatal try/except |
| D — docs + handoff | CLEAN — CONFIGURATION.md/drivers.md/CHANGELOG; `.windsurf/rules` slice handed to infra by mail |

## Classes swept to `found: 0` (round 2)

sql-correctness · role-lifecycle · policy-correctness · dsn-injection · shape-validator ·
applicability-consumers · drop-orphan-wedge · partial-failure-heal · drop-ordering.

## Gate

```json
{
 "status": "success",
 "failures": [],
 "blocking": 38
}

`final_gate.py --json` verbatim: status:success, 0 failures (2026-08-25, post-fix f6a2a0bd).
```
