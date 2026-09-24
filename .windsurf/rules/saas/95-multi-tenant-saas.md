---
activation: glob
globs: ["**/tenants/**", "**/rls/**", "**/organizations/**"]
applies_to: ["saas-skeleton"]
description: Multi-tenant SaaS discipline — tenant isolation, PostgreSQL RLS, context propagation, what RLS does not cover, the fabrik-lib modules' tenancy contracts
trigger: glob
currency_pass: 2026-09-24
---
<!-- CONSUMER: coding agents building multi-tenant backends + the planning commands when a product is multi-tenant
     GOAL: engine-enforced tenant isolation that fails closed — RLS, context propagation, caching, offboarding
     AGENT USAGE: every tenant-scoped table gets FORCE RLS; every transaction sets the tenant context from a validated membership. -->

# Multi-Tenant SaaS Rules

Apply when working on tenant isolation, row-level security, tenant context propagation, or multi-tenant data access. Skip for single-tenant services, pure UI, or infrastructure work.

**Sources:** PostgreSQL and practice facts re-grounded on 2026-09-24 (`docs/reference/research/2026-09-24-multi-tenant-saas-currency-ledger.md`); the load-bearing ones are in `.windsurf/rules/CLAIMS.yaml` (`pack: saas/95-multi-tenant-saas.md`). Module behaviour is cited to `/opt/fabrik-lib/`.

## Isolation Strategy

- **Shared database with PostgreSQL Row-Level Security (RLS)** is the default isolation model. Single migration path, single backup, engine-enforced filtering.
- **Database-per-tenant** is banned — exhausts connection limits and RAM on a single VPS.
- **Schema-per-tenant** is banned unless tenant count is guaranteed < 100 and explicitly approved. Migration management (Alembic per schema) becomes untenable at scale.
- **Application-level filtering** (`WHERE tenant_id = ...` in queries) is banned as the primary isolation mechanism — it relies on developer discipline and fails silently when forgotten. OWASP's multi-tenant guidance calls an ORM-level tenant filter "defense in depth, not complete enforcement", and separately has the request path connect as "a least-privileged role that is neither a superuser nor a BYPASSRLS role".

## What the Platform Ships

| Module | Tenant column / table | Context it reads | Policy shape |
|---|---|---|---|
| `fastapi-user-auth` (the saas-skeleton IdP) | `tenant_id` → `tenants` | native: `app.tenant_id` + `app.user_id`; compat: `request.jwt.claims` | native: `tenant_id = current_tenant_id()` (`rls/native.sql`); compat: `rls/compat.sql`'s example is a membership-set predicate; `rls/admin.sql` creates `fabrik_admin` |
| `tenancy` (orgs, memberships, invitations) | `org_id` → `organizations` | `auth.uid()` — reads `app.user_id` first, then `request.jwt.claims ->> 'sub'`; its context call also sets `app.tenant_id` to the org id (native) or clears it (compat) | `org_id IN (orgs the user belongs to)` — every org the user is a member of, not one selected tenant |
| `payments` | `org_id` | `app.current_org` | `org_id` = that setting |
| `cost-budget` (`cost_reservations` only), `gdpr-data-rights`, `rag`, `oauth-login` | per module (`rag`'s `tenant_id` is `TEXT`) | `app.tenant_id` | per module |

**Set every context variable your vendored modules read, in the same transaction, from the same validated tenant** — a project with the IdP and `payments` sets both `app.tenant_id` and `app.current_org`. A module whose variable is unset fails closed and returns nothing, which reads as an empty table rather than an error — except `rag`, whose policy compares the raw setting with no `NULLIF`, so an unset context matches rows whose `tenant_id` is `''` (filed). When the IdP and `tenancy` are both vendored, pick ONE membership table as the source of tenant identity — both write `app.tenant_id`, from different tables. Converging the modules on one variable and one column name is fabrik-lib's (filed). Your own tables use `tenant_id` and the selected-tenant predicate `tenant_id = (SELECT current_tenant_id())` — never `tenancy`'s membership-set predicate, which would let a user acting in org A read and write org B's rows in the same query; it is for `tenancy`'s own three tables (and `rls/compat.sql`'s example policy has the same shape). **Compat mode alone gives user-scoped isolation only** — a user in orgs A and B sees both in every request; a compat project that needs one selected tenant also sets `app.tenant_id` per transaction — after `tenancy`'s context call, which clears it in compat mode — and scopes its tables with `current_tenant_id()` — copy the function from `rls/native.sql`, not the whole file, which also creates the example `tenant_items` table and a second policy on it (`compat.sql` does not define the function). Never rename a vendored module's `org_id`. `tenancy`'s context call drops every transaction to `authenticated`, so with `tenancy` vendored every tenant table also needs `GRANT SELECT, INSERT, UPDATE, DELETE … TO authenticated`.

## RLS Setup

- Every tenant-scoped table carries `tenant_id UUID NOT NULL REFERENCES tenants(id)` — `UUID` to match the helper, `NOT NULL` so no row is invisible to everyone, the FK so offboarding finds every row.
- Every table containing tenant-specific data has RLS enabled and forced:
  ```sql
  ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
  ALTER TABLE <table> FORCE ROW LEVEL SECURITY;
  ```
- `FORCE ROW LEVEL SECURITY` is mandatory — the table owner otherwise bypasses every policy, and the registrar makes each app's role the database owner today (a non-owning app role is designed, D-385 / D-386; its plan is in progress). `FORCE` does not bind superusers or `BYPASSRLS` roles: they always bypass RLS.
- One policy per table, with both clauses written out:
  ```sql
  CREATE POLICY tenant_isolation ON <table>
  FOR ALL TO PUBLIC
  USING (tenant_id = (SELECT current_tenant_id()))
  WITH CHECK (tenant_id = (SELECT current_tenant_id()));
  ```
  `WITH CHECK` gates what an `INSERT` or `UPDATE` may write (a failing row errors); omitted on an `ALL` policy it reuses `USING`, but write it out so an edit to one clause cannot silently loosen the other. Never add a second permissive policy `TO PUBLIC` or to the request role — permissive policies are OR'd, so a later `USING (true)` opens the table; a policy scoped `TO` one dedicated role (the payments ingest role below) is the sanctioned exception. (The IdP's own `rls/native.sql` example is not yet wrapped in the sub-select below.)
- **Wrap the helper in a sub-select** — `(SELECT current_tenant_id())` lets the planner evaluate it once per query instead of once per row (Supabase measured 179 ms → 9 ms on a large table). Valid only because the value does not depend on the row.
- **Index every column a policy reads** — a B-tree on `tenant_id` at minimum; composite indexes lead with it: `(tenant_id, email)`, `(tenant_id, status, created_at)`.

## Fail-Closed Default

The helper returns `NULL` — and the policy therefore denies every row — when the context is unset, empty, or malformed. `current_setting(name, true)` returns `NULL` for a setting never set; after a transaction-local set ends it reads `''`, which `NULLIF` turns into `NULL`:

```sql
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.tenant_id', true), '')::UUID;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;
```

> **Hard invariant (every mode).** `current_tenant_id()` and (compat) `auth.uid()` return `NULL` on unset, empty, or malformed context — never raise, never default. A helper that defaults turns one missing claim into a cross-tenant read; one that raises turns a deny into a 500. The `EXCEPTION` block is expensive to enter, which the sub-select wrapper above pays once per query. Prove it with a no-context probe: the helper returns `NULL` and a tenant-scoped `SELECT` returns 0 rows.

⚠️ The saas-skeleton's `server/db/schema.sql` redefines `current_tenant_id()` as a plain SQL function without the `EXCEPTION` clause, while the IdP's `rls/native.sql` has it; whichever file runs last wins (filed to fleet). Apply `rls/native.sql` last (then wrap the skeleton's existing policies in `(SELECT …)` and drop the example `tenant_items` table it creates), or keep one definition.

## Tenant Context Propagation

- Set the context at the start of every database **transaction** with `SELECT set_config('app.tenant_id', %s, true)` — the transaction-local form of `SET LOCAL` that accepts a bind parameter. `SET` / `SET LOCAL` cannot take a server-side bound parameter (a PostgreSQL protocol limit — psycopg 3 and asyncpg both refuse it); psycopg2's `%s` is client-side quoting and acceptable (`rag` uses it); string formatting never. `fastapi-user-auth`'s `apply_tenant_context` / `tenant_session` do this for you.
- **Never** set it at session or pool level — the transaction-local value clears when the transaction ends, so the next request on the same pooled connection cannot inherit it; a session value would be inherited, and session-level `SET` is incompatible with PgBouncer transaction pooling. OWASP: "Re-establish the tenant context for every transaction."
- **Never give a context variable a role- or database-level default** (`ALTER ROLE … SET app.tenant_id`, `ALTER DATABASE … SET …`): `RESET` restores that default, not `''`, so a pooled connection resets straight into another tenant — fail-OPEN, and no `NULLIF` can catch it (`payments/db/schema.sql` documents the same trap for `app.current_org`).
- In FastAPI, carry the tenant through the request in a `ContextVar` (empty default = fail-closed); global or module state races under `asyncio`.

```python
from contextvars import ContextVar

tenant_context: ContextVar[str] = ContextVar("tenant_id", default="")
```

## Tenant Resolution and Membership

- Middleware extracts the tenant from the `X-Tenant-ID` header, the subdomain (`acme.app.com`), or a JWT claim, stores it in the `ContextVar`, and the database dependency sets the context. Queries stay plain (`SELECT * FROM invoices`); the policy adds the filter.
- **Validate membership before setting any context.** A client-supplied tenant id is a selector, never an authorization (OWASP): check the authenticated user belongs to it, and answer 403 when not — never set context and let RLS return an empty result. `tenant_session` raises `TenantAccessError` for exactly this; `tenancy` checks membership through a `service_role` connection before it drops to `authenticated` with `SET LOCAL role`.
- ⚠️ **`tenancy` puts a BYPASSRLS role within reach of the request connection:** `set_tenant_context` as shipped checks membership (which needs `service_role`) and drops to `authenticated` on the same connection that then serves the queries, so the request login role must be a member of `service_role` (`GRANT service_role TO your_app_login_role`) — and any SQL the request path can issue, an injection included, can `SET ROLE service_role` and read every tenant. OWASP: "Do not serve ordinary tenant-scoped requests through a privileged connection." Split it: call `verify_membership` on a separate privileged pool; on the request pool, set the context variables and drop to `authenticated` with a login role that is a member of `authenticated` only (filed: a two-pool API). Nothing on the request path may `SET ROLE` to a role that bypasses RLS.
- A JWT tenant claim is acceptable only if FastAPI issued it after verifying membership; re-verify claims from external identity providers.

## What RLS Does Not Cover

- **`TRUNCATE` and `REFERENCES`** are whole-table operations, not subject to row security — never grant them to the app role. ⚠️ While the registrar makes the app role the table owner (D-385 / D-386 change this), it holds them implicitly — and can `ALTER TABLE … NO FORCE` or `DROP POLICY` too — so no guard exists against `TRUNCATE` or DDL from the request path until the non-owner role lands. A FORCE'd policy on `tenants` and no `CASCADE` from `tenants` limit only the `DELETE FROM tenants` path; the saas-skeleton and the IdP both ship `ON DELETE CASCADE` from `tenants` today (filed).
- **Unique, primary-key and foreign-key checks bypass RLS**, so they leak existence across tenants (PostgreSQL calls these covert channels): scope every uniqueness to the tenant — `UNIQUE (tenant_id, email)`, never a global `UNIQUE (email)` on tenant data — and make foreign keys between tenant tables composite, `(tenant_id, parent_id) REFERENCES parent (tenant_id, id)` over a `UNIQUE (tenant_id, id)`, as `payments` does.
- **Cascades cross tenants:** referential integrity bypasses RLS (above), so an `ON DELETE CASCADE` from `tenants` removes rows under FORCE RLS in every tenant. `tenants` — and any parent a tenant table cascades from — is privileged: the app role holds no `DELETE` on it (or its policy is `id = (SELECT current_tenant_id())`), and offboarding's hard-delete runs as a privileged role, never through the request role — enforceable once the app role stops being the owner (above). The saas-skeleton's `tenants` has no RLS today (filed to fleet).
- **Views run with the view owner's policies** unless created `WITH (security_invoker = true)` — create every view over tenant tables that way.
- **Materialized views hold their own copy of the rows** and `CREATE POLICY` targets tables — do not expose a materialized view of tenant data to the app role.
- **`SECURITY DEFINER` functions run as their owner**, so they bypass RLS whenever the owner does — keep them narrow, pin `search_path` to trusted schemas with `pg_temp` last (e.g. `SET search_path = pg_catalog, public, pg_temp`) and schema-qualify, so a caller cannot mask the objects it uses; `REVOKE EXECUTE … FROM PUBLIC` (new functions are executable by `PUBLIC` by default), then `GRANT` it to the one role that needs it. `tenancy`'s membership check pins `search_path = public` and revokes from `PUBLIC`; its commented `handle_new_user` template does neither — add both if you use it.
- **Backups and bulk loads:** `pg_dump` turns `row_security` off and errors unless the role can bypass RLS — run `pg_dump --role=fabrik_admin` from a dedicated backup login role that is the only member of `fabrik_admin` (the role is `NOLOGIN`; never make the request login role a member), or as a superuser. `rls/admin.sql` grants table DML only — add sequence and extra-schema (`auth`) grants for a full dump. `COPY FROM` is refused on RLS tables; bulk-load as `fabrik_admin` or with `INSERT`s.
- **Side channels:** never expose `EXPLAIN` or raw SQL to a tenant (`EXPLAIN ANALYZE` prints "Rows Removed by Filter" — other tenants' row counts); prefer UUID keys (the scaffold uses UUIDv7) so shared sequences do not leak other tenants' insert volume.

## Dual-Mode RLS

Two context contracts; a project uses **one**, and both keep `FORCE ROW LEVEL SECURITY` and a `fabrik_admin BYPASSRLS` break-glass role.

| | **native** (default) | **compat** (migrating off Supabase Auth) |
|---|---|---|
| Auth pattern | Pattern A (`core/35-security-auth.md`) | Pattern A-compat (`core/35` § Pattern A-compat) |
| Context | `app.tenant_id` (+ `app.user_id`) | `request.jwt.claims` (+ `role`) |
| Set per transaction | `set_config('app.tenant_id', …, true)` | `set_config('role', 'authenticated', true)`; `set_config('request.jwt.claims', '{"sub":…,"role":…}', true)` |
| Helper | `current_tenant_id()` | `auth.uid()` / `auth.jwt()` / `auth.role()` |
| Policy predicate | `tenant_id = (SELECT current_tenant_id())` | existing `… = auth.uid()` policies, unchanged |
| Use when | new projects | preserving existing Supabase RLS policies with zero rewrite |

**compat** keeps Supabase's contract — PostgREST sets `request.jwt.claims` and switches `role` per request, and Supabase's `auth.uid()` reads the claims' `sub` — so a project migrating off Supabase Auth keeps every `auth.uid()` policy, `auth.users` FK and `authenticated` / `service_role` grant. FastAPI owns the `auth` schema and sets the settings itself; token lifecycle is Pattern A. Reference build: trade-intelligence `web/db/migrations/000_native_auth.sql` + `053_force_rls_and_admin.sql`; `fastapi-user-auth` ships `rls/compat.sql`.

```sql
-- auth.uid(): the JWT `sub`, fail-closed to NULL so `user_id = auth.uid()` denies.
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE plpgsql STABLE AS $$
BEGIN
  RETURN nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'sub', '')::uuid;
EXCEPTION WHEN OTHERS THEN
  RETURN NULL;
END;
$$;
```

Define `auth.jwt()` (the claims jsonb, `coalesce` to `'{}'`) and `auth.role()` (claims `->> 'role'`, else `current_setting('role')`) beside it; `GRANT USAGE ON SCHEMA auth` and `GRANT EXECUTE` on all three to `anon, authenticated, service_role` (without the schema `USAGE` every query as `authenticated` fails before any policy runs), created `NOLOGIN NOINHERIT` (`service_role` with `BYPASSRLS`), and `GRANT authenticated TO <request login role>` so the role drop can happen. Never mix native and compat context in one project, beyond setting `app.tenant_id` for a selected tenant (above).

## Hardening and the Cross-Tenant Probe

- `FORCE ROW LEVEL SECURITY` on every RLS-enabled table; apply it idempotently across the schema in one migration (loop `pg_class WHERE relrowsecurity AND NOT relforcerowsecurity`).
- **`fabrik_admin`** (`NOLOGIN NOINHERIT BYPASSRLS`) for backups, exports and cross-tenant DML only — create it with `fastapi-user-auth`'s `rls/admin.sql` (the registrar does not). It owns nothing, so it cannot run DDL: migrations run as the table owner. `BYPASSRLS` skips policies, not table grants, so the role still needs its `GRANT`s. The app role never connects as it and never holds `BYPASSRLS`.
- **Cross-tenant probe (required test):** set context for tenant A, write and read a row; switch to tenant B and assert A's row is invisible (`count(*) = 0`); set no context and assert the helper returns `NULL` and the read denies. See `core/45-testing-strategy.md`.
- ⚠️ **The role your tests connect as must be neither superuser nor `BYPASSRLS`** — otherwise the probe proves nothing, silently. Assert it inside the suite so it fails rather than skips:

  ```sql
  SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;  -- both MUST be false
  ```

  Measured at transdoc (2026-08-23): the test database was owned by `postgres`, so every RLS assertion ran against a role RLS does not apply to; rebuilt under a `NOSUPERUSER NOBYPASSRLS` owner, 29 of 32 conformance tests failed. A green RLS suite is evidence only if its role is subject to RLS.

## Admin and Maintenance Access

- The request path's login role holds no `BYPASSRLS` and is a member of no role that does. `fabrik_admin` and, with compat or `tenancy`, `service_role` are the only `BYPASSRLS` roles, reachable only from a separate privileged pool.
- **Cross-tenant payments ingest is not an admin case** — never route webhook ingest through `fabrik_admin` (it is `NOLOGIN`) or any `BYPASSRLS` role. Set `shape.needs_payments_ingest: true` (requires `needs_database: true`) and `fabrik apply` mints a per-project `LOGIN NOSUPERUSER NOBYPASSRLS` role whose cross-tenant reach comes only from permissive policies on the payments tables — `SELECT` on `customers` / `subscriptions`, `INSERT` + `SELECT` on `webhook_events` — (the `SELECT` half on `webhook_events` exists because `record_event`'s `INSERT … RETURNING` fails without it), injected as `PAYMENTS_INGEST_DATABASE_URL` — never hand-set. A leaked ingest DSN is confined to those three tables (plus a project `jobs` table if it adds the ingest policy below). Assert the role at boot: `SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user` must return false, false (the hub's own contract: `/opt/fabrik/docs/CONFIGURATION.md` § Payments webhook ingest). The worker never uses it: it holds the resolved `org_id` and runs as the tenant role with the context set — though a tenant-role worker cannot yet record a PayTR one-off (`purchases` has only a `SELECT` policy; `core/85` § Payment Providers carries the open blocker). An RLS'd `jobs` table the ingest role writes needs its own ingest policy, added by the project.

## URL and Domain Strategy

- **Default:** a subdomain per tenant (`<org>.productname.example.com`), resolved by middleware.
- **Custom domains** (premium): provisioned by the site-provisioner at `fabrik apply`, not during development — defer unless a core differentiator.
- DNS is a deployment concern. Development uses localhost with the org slug in the path or a header.

## Tenant-Scoped Caching

- Redis keys carry the tenant: `t:{tenant_id}:settings`; unprefixed keys are reserved for explicitly global data (`global:`).
- In-memory caches are partitioned or cleared per tenant per request — a shared unscoped cache is a cross-tenant leak.

## Per-Tenant Rate Limiting

- Rate-limit per tenant so a noisy neighbour cannot exhaust the VPS — counters keyed by tenant id, applied in middleware before business logic, limits from the plan tier (`saas/88-saas-launch-checklist.md`).

## Tenant Offboarding

- On cancellation, set `deleted_at` on the `tenants` row only — the one soft-delete `core/25-data-postgres.md` permits — and hard-delete the tenant's rows in a background job after the retention period. ⚠️ The saas-skeleton's `tenants` has no `deleted_at` column (the IdP's schema does; whichever `CREATE TABLE IF NOT EXISTS` runs first wins) — add it (filed to fleet).
- Test that deletion cannot cascade into another tenant's data.
- Export: with RLS on and the tenant's context set, `SELECT *` per table yields a clean tenant-scoped export.

## Background Jobs

- Tenant-aware jobs carry the tenant id in the payload; the worker validates it and sets the context before any query.
- The saas-skeleton's `jobs` queue is not RLS-protected (the worker drains across tenants; the API filters by `tenant_id` when it enqueues and reads) — the one sanctioned exception to application-level filtering: keep tenant data out of the queue beyond ids, treat the payload as untrusted, and re-validate the tenant in the worker (filed to fleet).
- Never rely on the enqueueing request's context — the worker runs in another process and transaction.

---

## Supabase Auth (legacy)

New projects use native mode with Pattern A. A project still on Supabase Auth migrates to native or compat mode (`agents-fabrik.md` § Supabase); until then `auth.uid()` scopes users, and tenant isolation still needs `tenant_id` + RLS, with the tenant carried as a custom JWT claim. `FORCE` / `ENABLE ROW LEVEL SECURITY` apply identically.

---

## Related Rule Packs

- `core/35-security-auth.md` — Pattern A / A-compat / B auth
- `core/45-testing-strategy.md` — tenant-isolation testing
- `saas/60-saas-ui.md` — tenant UI: org switcher, team management
- `core/75-workers-jobs.md` — the worker and queue patterns tenant-aware jobs run on
- `core/85-payments-billing.md` — tenant-scoped billing and the ingest role
- `core/25-data-postgres.md` — the pooler and the soft-delete exception
- `saas/88-saas-launch-checklist.md` — per-tenant rate limiting in planning
- `saas/00-domain-saas.md` — tenancy architecture decisions

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Database-per-tenant on a single VPS | Shared DB with PostgreSQL RLS |
| Schema-per-tenant at scale (>100 tenants) | Shared DB with PostgreSQL RLS |
| Manual `WHERE tenant_id = ...` as the isolation | RLS policies with `current_tenant_id()` |
| `SET` at session or pool level | `set_config('app.tenant_id', …, true)` per transaction |
| `SET LOCAL app.tenant_id` built with string formatting | `set_config('app.tenant_id', %s, true)` with a bound value |
| Global or module state for tenant context | Python `ContextVar` |
| Policy calling the helper per row | `(SELECT current_tenant_id())` |
| View over tenant tables without `security_invoker` | `CREATE VIEW … WITH (security_invoker = true)` |
| Global `UNIQUE` on tenant data | `UNIQUE (tenant_id, …)` |
| Redis keys without a tenant prefix | `t:{tenant_id}:…` |
| Application DB user with `BYPASSRLS` | `fabrik_admin` for maintenance only |
| Webhook ingest via `fabrik_admin` or any `BYPASSRLS` role | `shape.needs_payments_ingest` → the scoped ingest role |
| RLS-protected table without a `tenant_id` index | B-tree index on `tenant_id` |
| Trusting `X-Tenant-ID` without a membership check | Validate membership before setting context |
| A helper that defaults on unset context | `EXCEPTION WHEN OTHERS THEN RETURN NULL` |
| Rewriting `auth.uid()` policies to leave Supabase Auth | compat mode |
| Mixing native and compat context in one project | Pick one mode |
| Setting only one module's context variable | Set every variable your vendored modules read |
| A role- or database-level default for a context variable | Set it per transaction only; `RESET` must land on `''` |
| Request pool's login role a member of `service_role` or `fabrik_admin` | A separate privileged pool for the membership check and for dumps |
| App role with `DELETE` on `tenants` (cascading into every tenant) | Offboarding hard-delete as `fabrik_admin` (the owner only once it is no longer the request role, D-385 / D-386) |
| `SECURITY DEFINER` without a pinned `search_path` and `REVOKE … FROM PUBLIC` | Pin the search path (`pg_temp` last); grant `EXECUTE` to one role |

---

## Done When

- [ ] Every tenant-scoped table has `ENABLE` and `FORCE ROW LEVEL SECURITY`, a policy with explicit `USING` and `WITH CHECK`, and an index on its tenant column.
- [ ] Policies call the helper through a sub-select; the helper returns `NULL` on unset/empty/malformed context, proven by a no-context probe.
- [ ] One RLS mode chosen (native or compat); every context variable the vendored modules read is set in the same transaction; compat projects that need a selected tenant also set `app.tenant_id`.
- [ ] compat: the `auth` schema, `auth.uid()` / `jwt()` / `role()` and `anon` / `authenticated` / `service_role` are owned natively; existing `auth.uid()` policies unchanged.
- [ ] Context set with `set_config(..., true)` per transaction, only after membership is validated (403 otherwise).
- [ ] Cross-tenant probe passes under a test role that is neither superuser nor `BYPASSRLS`.
- [ ] Uniqueness and foreign keys scoped per tenant; views over tenant tables use `security_invoker = true`; no materialized view of tenant data reaches the app role; the app role cannot delete `tenants`.
- [ ] Middleware resolves the tenant into a `ContextVar`; no context variable has a role- or database-level default; the request pool cannot reach `service_role` or `fabrik_admin`.
- [ ] Redis keys prefixed `t:{tenant_id}:`; background jobs carry the tenant and set context before DB access.
- [ ] The app DB user has no `BYPASSRLS`; `fabrik_admin` exists for backups and exports; migrations run as the owner.
- [ ] Offboarding: `deleted_at` on the `tenants` row only; a background job hard-deletes after retention.
