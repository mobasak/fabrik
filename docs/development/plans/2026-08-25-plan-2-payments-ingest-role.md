# Plan — payments-ingest DB role in the fabrik registrar

Status: CONVERGED (/fabrik-plan-review 2026-08-25 — 2 passes, md5-verified no-op aeb74e2f; RETURNING-policy hardened + ingest-only scope resolved)
Spec: docs/superpowers/specs/2026-08-23-payments-ingest-role-design.md (CONVERGED, 3 review passes)
Owner: fleet (registrar). Build split: registrar code = fleet; `.windsurf/rules` doc slice = infra (mail handoff, Phase D).
Date: 2026-08-25

## Grounded surface (pinned against fabrik-lib payments — refines the spec's deferred set)

`PgWebhookStore` (`/opt/fabrik-lib/payments/payments/store.py`) — the fabrik-lib ingest path — issues
EXACTLY these cross-tenant statements as the service role (verified this turn):

| store.py | statement | table | op | policy the ingest role needs |
|---|---|---|---|---|
| :153 | `SELECT org_id FROM subscriptions WHERE provider=%s AND provider_subscription_id=%s` | subscriptions | READ | `FOR SELECT USING (true)` |
| :162 | `SELECT org_id FROM customers WHERE provider=%s AND provider_customer_id=%s` | customers | READ | `FOR SELECT USING (true)` |
| :188 | `INSERT INTO webhook_events (…) ON CONFLICT (provider,event_id) DO NOTHING RETURNING event_id` | webhook_events | WRITE+read-back | `FOR INSERT WITH CHECK (true)` **and** `FOR SELECT USING (true)` (RETURNING reads the row) |

Two refinements of the spec's "exact set pinned in the plan":
- **`plans` is OUT** — the store never reads it (the spec over-included it; `plans` is the worker/entitlement
  path, project code). The registrar provisions policies on **subscriptions, customers, webhook_events ONLY**.
- **`jobs` is PROJECT-owned** — `store.py:223` also does `INSERT INTO jobs (queue, payload)` (the workers-jobs
  queue, NOT a payments table). The registrar cannot reliably policy a project-defined table whose RLS status
  is project-specific → the `jobs` grant/policy is the **consuming project's** responsibility (documented in
  Phase D, not registrar-provisioned). This keeps the registrar's surface deterministic + testable.

All four payments tables are `ENABLE`+`FORCE` RLS with a `_tenant_isolation` policy carrying `WITH CHECK`
(`/opt/fabrik-lib/payments/db/schema.sql:112-135`), so a non-GUC role is default-denied without these
permissive policies.

Template to mirror: `create_watchdog_roles` (`src/fabrik/drivers/postgres.py:612`) + `_wd_role_names` (:509).

---

## Phase A — Shape flag `needs_payments_ingest`

**Steps**
- `src/fabrik/spec_loader.py:205` (`class Shape`) — add `needs_payments_ingest: bool = Field(False, description="Project vendors fabrik-lib payments; provision a scoped cross-tenant ingest role + PAYMENTS_INGEST_DATABASE_URL. Requires needs_database.")`. Mirror the existing `needs_cache`/`has_search_feature` Field style (:324).
- Add a model validator (or extend the existing shape-consistency check) asserting `needs_payments_ingest → needs_database` (fail loud on `needs_payments_ingest: true` + `needs_database: false`).

**Behavior Contract (tests — `tests/` beside the existing spec_loader tests)**
- `Shape(**{…, "needs_payments_ingest": True, "needs_database": True})` loads; default is `False` when absent.
- `needs_payments_ingest: true` + `needs_database: false` raises a validation error (watched-fail-first: write the assert, see it fail before the validator exists).

**Gate:** `/fabrik-review` on the changed surface → CLEAN. `final_gate.py --json` success.
**Evidence:** `path:line` of the new Field + validator; fenced pytest output of the two tests green.
**Self-audit:** default `False` (additive, zero effect on existing specs); the flag name matches the spec.

## Phase B — `create_payments_ingest_role` in the postgres driver

**Steps** (`src/fabrik/drivers/postgres.py`, mirror `create_watchdog_roles`:612 + `_wd_role_names`:509)
- `_payments_ingest_role_name(db_name)` → `f"{db_name}_payments_ingest"` with `_validate_identifier` + the
  63-char guard (mirror `_wd_role_names`; `_payments_ingest` is 16 chars → guard catches long db names).
- `_payments_ingest_drop_role_sql(db_name)` (mirror `_wd_drop_role_sql`:527) for the decommission path.
- `create_payments_ingest_role(db_name, container=…, dry_run=False)`:
  - `_role_exists` check; `pw = None if exists else _generate_password()`.
  - **Split CREATE** (its own `\set ON_ERROR_STOP on` invocation, like :692): `CREATE ROLE "<role>" WITH
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '<pw>'` — **NO `BYPASSRLS`** (the whole point).
  - **Idempotent grant+policy batch** (`ON_ERROR_STOP`, re-applied every call), each table **guarded on
    existence** (`SELECT to_regclass('public.<t>')` / `information_schema.tables` → skip when NULL, so it
    self-heals on the apply after the app's schema lands):
    - `subscriptions`, `customers`: `GRANT SELECT ON <t> TO "<role>"`; `DROP POLICY IF EXISTS
      payments_ingest_sel ON <t>; CREATE POLICY payments_ingest_sel ON <t> FOR SELECT TO "<role>" USING (true);`
    - `webhook_events`: `GRANT INSERT, SELECT ON webhook_events TO "<role>"`; drop+create TWO least-privilege
      policies — `payments_ingest_sel … FOR SELECT … USING (true)` and `payments_ingest_ins … FOR INSERT …
      WITH CHECK (true)` (NO UPDATE/DELETE grant or policy — the store never issues them). **The SELECT
      policy is REQUIRED, not optional**: `record_event` (store.py:186-193) runs `INSERT … ON CONFLICT DO
      NOTHING RETURNING event_id`, and under RLS a RETURNING clause requires the returned row to satisfy the
      SELECT policy or *Postgres throws* — "inserted or updated rows to be returned are never silently
      ignored" (postgresql.org/docs/current/sql-createpolicy.html, verified 2026-08-25). Omit it and every
      new event errors at insert. The Phase-B write test MUST exercise `… RETURNING` (not a bare INSERT), or
      it would pass while the real store breaks.
  - Return `{"user": role, "password": pw, "status": …}` (fresh `password` only on new create — mirror
    :656-660, so the caller injects a DSN only once).

**Behavior Contract (tests — mirror the `create_watchdog_roles` tests in `tests/`; real-PG, skipped without `TEST_DATABASE_URL`)**
- **Non-BYPASSRLS (watched-fail-first):** after create, `SELECT rolbypassrls, rolsuper FROM pg_roles WHERE
  rolname = '<role>'` → both `false`. (This is the security invariant — see it fail against a BYPASSRLS role first.)
- **Cross-tenant READ under FORCE RLS:** connect as the role (no `SET app.current_org`), insert two tenants'
  rows as the owner, `SELECT org_id FROM subscriptions WHERE …` returns the row (and same for `customers`).
- **Cross-tenant WRITE under FORCE RLS:** as the role, `INSERT INTO webhook_events (…) … RETURNING event_id`
  succeeds (both the INSERT `WITH CHECK` and the RETURNING read), and a duplicate `ON CONFLICT DO NOTHING`
  returns no row.
- **Table-existence guard + idempotency:** run against a DB missing `webhook_events` → no error, policy skipped;
  create the table; re-run → policy now present; a third run is a no-op (idempotent, no duplicate-policy error).
- **Fresh-password-only:** second call on an existing role returns `password: None`.

**Gate:** `/fabrik-review` → CLEAN. `final_gate.py --json` success.
**Evidence:** `path:line` of the new fns; fenced pytest output; the `rolbypassrls=false` assertion output.
**Self-audit:** no `BYPASSRLS`; no UPDATE/DELETE grant; only the 3 pinned tables; guard proven to self-heal.

## Phase C — wire into `_provision_postgres`

**Steps** (`src/fabrik/orchestrator/infrastructure.py:486`+)
- After `create_database` (and alongside the `provision_watchdog_roles` branch at :577-591), add a
  `if shape.needs_payments_ingest and not dry_run:` branch calling `create_payments_ingest_role(db_name, …)`.
- Inject `PAYMENTS_INGEST_DATABASE_URL = postgresql://<role>:<pw>@postgres-main:5432/<db>` **only when a fresh
  password is returned** (mirror the watchdog DSN injection :583-591, incl. the `# noqa` CSPRNG comment).
- Own `try/except` so a role failure logs + continues (mirror the watchdog branch's isolation :575-577).

**Behavior Contract (tests — mirror the watchdog wiring tests)**
- `_provision_postgres` with `shape.needs_payments_ingest = True` calls `create_payments_ingest_role` and injects
  `PAYMENTS_INGEST_DATABASE_URL` (assert on a mocked deployer.inject_env, as the watchdog test does).
- With the flag `False` (default): neither called — zero behavior change (regression guard).
- Re-provision (existing role, `password: None`): no DSN injected (idempotent).

**Gate:** `/fabrik-review` → CLEAN. `final_gate.py --json` success.
**Evidence:** `path:line` of the branch; pytest output; a `fabrik plan` preview on a scratch spec with the flag set.
**Self-audit:** flag-gated; DSN only on fresh password; try/except isolation matches watchdog.

## Phase D — docs + infra handoff (fleet does NOT touch `.windsurf/rules/`)

**Steps**
- **Registrar docs (fleet):** document `needs_payments_ingest` + `create_payments_ingest_role` where the
  watchdog roles are documented (grep first — likely `docs/reference/` for the postgres driver / registrar);
  `CHANGELOG.md` (Added); `INDEX.md` if a file is added. Document the **consuming-project wiring** (NOT built):
  the project calls `verify_service_role(conn, allow_policy_based=True)` at boot, uses `PAYMENTS_INGEST_DATABASE_URL`
  for ingest, and — if its `jobs`/queue table is RLS'd — adds its OWN policy for `{db}_payments_ingest` on that
  project-owned table (out of the registrar's scope; see § Grounded surface).
- **Data-contract:** none owed (DB-role provisioning, no app fields) — state it.
- **Infra handoff (mail, NOT a fleet edit):** `mail.py send --to fabrik --to-agent infra --kind request` — ask
  infra to document `needs_payments_ingest` + the least-privilege ingest-role contract in the rules pack
  (`.windsurf/rules/saas/95-multi-tenant-saas.md` § Admin & Maintenance, near the existing `fabrik_admin` text, or
  the payments pack). `.windsurf/rules/` is a governance-sync trigger AND infra is actively editing it → fleet
  must NOT touch it. Include the grounded facts (the 3-table policy set; non-BYPASSRLS; `verify_service_role
  allow_policy_based=True`).

**Gate:** `/fabrik-docs-review` (scoped to the touched docs) → green; `/fabrik-review` → CLEAN.
**Evidence:** the doc diffs; the sent mail id; `docs_updater.py --check` green.
**Self-audit:** no `.windsurf/rules/` file staged by fleet; the mail handoff exists; consuming-project surface documented.

---

## Residuals / resolved in /fabrik-plan-review
- **Ingest-only scope — RESOLVED (the worker needs no cross-tenant grant).** The README's "one service role"
  for ingest+worker is a simplification: only the INGEST path is cross-tenant *by necessity* (it resolves the
  org before the tenant is known, and `record_event` writes with no GUC — store.py:184). The WORKER runs
  AFTER resolution and receives the resolved `org_id` in its job payload (`enqueue_fulfilment` puts `org_id`
  in the `jobs` payload, store.py:210-219), so it runs as the ordinary tenant-scoped app role with
  `SET app.current_org = <org_id>` and needs **zero** cross-tenant privilege. Therefore the registrar role is
  correctly **ingest-store-only** — provisioning cross-tenant WRITE on `subscriptions`/`customers` for a
  hypothetical worker would be a gratuitous blast-radius expansion the worker does not need.
- **webhook_events policy shape — RESOLVED:** split SELECT+INSERT (least privilege, no UPDATE/DELETE), and
  the SELECT half is mandatory for the store's `RETURNING` (see Phase B).
- Role-name length: `{db}_payments_ingest` caps db_name at 47 chars — the 63-guard raises; confirm no live
  payments-vendoring db name is that long (advisory; the guard fails loud, never silently truncates).

## Self-audit (plan-level)
Every phase grounds in a real `path:line`; every user-observable behavior has a test (risky ones watched-fail-first);
each boundary gates on `/fabrik-review`; the `.windsurf/rules` slice is a mail handoff, never a fleet edit; the
surface is pinned from `store.py` (not invented). Next: `/fabrik-plan-review`.
