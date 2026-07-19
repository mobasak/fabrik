---
activation: glob
globs: ["**/tenants/**", "**/rls/**", "**/organizations/**"]
description: Multi-tenant SaaS discipline — tenant isolation, PostgreSQL RLS, context propagation, cross-tenant prevention
trigger: glob
---
<!-- CONSUMER: Coding agents building multi-tenant backends
     GOAL: PostgreSQL RLS, tenant context propagation, fail-closed default, caching, offboarding
     TRAYCER USAGE: Injects as Context File for every backend ticket in a multi-tenant SaaS project.
     AGENT USAGE: Follow verbatim. Every tenant-scoped table gets RLS. Every query is tenant-scoped. -->

# Multi-Tenant SaaS Rules

Apply when working on tenant isolation, row-level security, tenant context propagation, or multi-tenant data access. Skip for single-tenant services, pure UI, or infrastructure work.

## Isolation Strategy

- **Shared database with PostgreSQL Row-Level Security (RLS)** is the default isolation model. Single migration path, single backup, engine-enforced filtering.
- **Database-per-tenant** is banned — exhausts connection limits and RAM on a single VPS.
- **Schema-per-tenant** is banned unless tenant count is guaranteed < 100 and explicitly approved. Migration management (Alembic per schema) becomes untenable at scale.
- **Application-level filtering** (`WHERE tenant_id = ...` in queries) is banned as the primary isolation mechanism — it relies on developer discipline and fails silently when forgotten.

## RLS Setup

- Every table containing tenant-specific data must have RLS enabled:
  ```sql
  ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
  ALTER TABLE <table> FORCE ROW LEVEL SECURITY;
  ```
- `FORCE ROW LEVEL SECURITY` is mandatory — without it, the table owner (the application's DB user) bypasses all policies.
- Create a single reusable policy pattern per table:
  ```sql
  CREATE POLICY tenant_isolation ON <table>
  FOR ALL TO PUBLIC
  USING (tenant_id = current_tenant_id())
  WITH CHECK (tenant_id = current_tenant_id());
  ```

## Fail-Closed Default

- If `app.tenant_id` is not set or is empty, the `current_tenant_id()` function must return `NULL`. Since `NULL != NULL` in SQL, this causes the policy to deny all rows — **fail-closed by default**.
- Define the helper function once:
  ```sql
  CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS UUID AS $$
  BEGIN
      RETURN NULLIF(current_setting('app.tenant_id', true), '')::UUID;
  EXCEPTION WHEN OTHERS THEN
      RETURN NULL;
  END;
  $$ LANGUAGE plpgsql STABLE;
  ```

> **Hard invariant (every mode).** `current_tenant_id()` AND (compat mode) `auth.uid()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed context — body wrapped in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one empty/bad claim into a full cross-tenant read. This is the single most security-critical line in a multi-tenant build — prove it with a no-context probe (helper returns `NULL`; a tenant-scoped `SELECT` returns 0 rows).

## Dual-Mode RLS (canonical)

Two canonical RLS context contracts. A project uses **one**; both enforce the same fail-closed guarantee and the same hardening (`FORCE ROW LEVEL SECURITY` + a `fabrik_admin BYPASSRLS` break-glass role).

| | **native** (default) | **compat** (migrating off Supabase Auth) |
|---|---|---|
| Auth pattern | Pattern A (`35-security-auth.md`) — the default | Pattern A-compat (`35` § Pattern A-compat) |
| Context GUC | `app.tenant_id` | `request.jwt.claims` (+ `role`) |
| Set per txn | `SET LOCAL app.tenant_id = '<uuid>'` | `SET LOCAL role = 'authenticated'; SET LOCAL request.jwt.claims = '{"sub":…,"role":…}'` |
| Helper | `current_tenant_id()` | `auth.uid()` / `auth.jwt()` / `auth.role()` |
| Policy predicate | `tenant_id = current_tenant_id()` | existing `… = auth.uid()` policies, **unchanged** |
| Use when | new projects | preserve existing Supabase RLS policies with zero rewrite |

**native** (`app.tenant_id` + `current_tenant_id()`, documented above) is the default for all new projects — Pattern A owns the `auth` schema and issues its own JWTs (`fabrik-lib/fastapi-user-auth`, per `agents-fabrik.md § Supabase`). **compat** is the **migration path**: it keeps Supabase's PostgreSQL contract so a project *migrating off Supabase Auth* keeps every `auth.uid()` policy, `auth.users` FK, and `authenticated`/`service_role` grant working unchanged — FastAPI owns the `auth` schema and sets the GUCs itself (token lifecycle is still Pattern A). Canonical reference build: trade-intelligence `000_native_auth.sql` + `053_force_rls_and_admin.sql`.

### compat mode — the `auth.*` helpers (fail-closed)

Own the `auth` schema natively; reimplement Supabase's helpers over the `request.jwt.claims` GUC:

```sql
-- auth.uid(): the JWT `sub`, fail-closed to NULL so `user_id = auth.uid()` denies
-- (never leaks) when no/invalid context is set.
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
LANGUAGE plpgsql STABLE AS $$
BEGIN
  RETURN nullif(current_setting('request.jwt.claims', true)::jsonb ->> 'sub', '')::uuid;
EXCEPTION WHEN OTHERS THEN          -- unset / malformed claims → fail-closed
  RETURN NULL;
END;
$$;
```

Define `auth.jwt()` (the claims jsonb, `coalesce` to `'{}'`) and `auth.role()` (claims `->> 'role'`, else `current_setting('role')`) alongside it; `GRANT EXECUTE` all three to `anon, authenticated, service_role`. Create those three roles `NOLOGIN NOINHERIT` (`service_role` with `BYPASSRLS`). The app sets the GUCs per transaction exactly as Supabase's PostgREST did — `auth.uid()` then drives the existing policies with zero predicate edits.

### Both modes — hardening + cross-tenant probe

- `FORCE ROW LEVEL SECURITY` on **every** RLS-enabled table (so even the table owner is subject to its policies). Apply idempotently across the whole schema in one migration (loop `pg_class WHERE relrowsecurity AND NOT relforcerowsecurity`).
- A dedicated **`fabrik_admin`** role `NOLOGIN NOINHERIT BYPASSRLS` for migrations / backups / exports only — the public app role **never** connects as it.
- **Cross-tenant probe (required test):** set context for tenant A, write/read a row; switch context to tenant B and assert A's row is invisible (`count(*) = 0`); then set **no** context and assert the helper returns `NULL` and the read denies. See `45-testing-strategy.md`.

## Tenant Context Propagation

- Set tenant context using `SET LOCAL app.tenant_id = '<uuid>'` at the start of every database **transaction**. `SET LOCAL` is automatically cleared when the transaction ends, preventing context leakage to subsequent requests sharing the same pooled connection.
- **Never** set `app.tenant_id` at the connection pool level — concurrent requests sharing the pool will overwrite each other's tenant context.
- In FastAPI, use Python `ContextVar` to propagate the tenant ID through the async request lifecycle. Global variables or module-level state cause race conditions under `asyncio` concurrency.

```python
from contextvars import ContextVar

tenant_context: ContextVar[str] = ContextVar("tenant_id", default="")
```

## Tenant Resolution

- Extract the tenant ID from the incoming request via middleware — from `X-Tenant-ID` header, subdomain (`acme.app.com`), or JWT claim.
- Store it in the `ContextVar`, then the database dependency reads it and executes `SET LOCAL`.
- The developer writes standard queries (`SELECT * FROM invoices`). PostgreSQL appends the tenant filter automatically via the RLS policy.

## URL & Domain Strategy

- **Default:** Subdomain per tenant — `<org>.productname.ocoron.com` or `<org>.customdomain.com`. Resolved via middleware that extracts org from subdomain.
- **Custom domains (premium feature):** Tenants bring their own domain (e.g., `projects.clientcompany.com`). Provisioned via site-provisioner during deployment (`fabrik apply`), not during development. Deferred to a later epic unless it's a core product differentiator.
- **DNS is a deployment concern.** Site-provisioner handles domain provisioning, Cloudflare DNS, SSL. Development uses localhost with org slug in path or header. Do not engineer DNS during implementation — the deploy pipeline handles it.

## Tenant Membership Validation

- Before executing `SET LOCAL app.tenant_id`, the resolved tenant ID must be validated against the authenticated user's allowed tenant memberships. Never trust a user-supplied `X-Tenant-ID` header without verifying the user actually belongs to that tenant.
- If the user is not a member of the requested tenant, reject with 403 immediately — do not set tenant context and let RLS silently return empty results.
- JWT-based tenant claims are acceptable only if the JWT was issued by FastAPI after membership verification. Do not trust tenant claims from external identity providers without re-verification.

## Tenant ID Column

- All tenant-scoped tables must include a `tenant_id UUID NOT NULL` column with a foreign key to the central `tenants` table.
- Consistency: always name the column `tenant_id`, always type `UUID`.

## Indexing

- Every RLS-protected table must have a **B-tree index on `tenant_id`**. Without it, every query triggers a full table scan as the engine checks every row against the policy.
- For queries filtering on additional columns, use **composite indexes**: `(tenant_id, email)`, `(tenant_id, status, created_at)`, etc. The tenant_id prefix lets the planner narrow to the tenant's rows first.

## Tenant-Scoped Caching

- When using Redis, all keys must include the tenant ID as a prefix: `t:{tenant_id}:settings`. Keys without a tenant prefix are reserved for explicitly global data (prefixed `global:`).
- In-memory (L1) caches must be partitioned or cleared per-tenant per-request. A shared in-memory cache without tenant scoping is a cross-tenant leak vector.

## Admin & Maintenance Access

- Create a dedicated `fabrik_admin` database role with `BYPASSRLS`. This role is strictly for migrations, backups, data exports, and internal admin panels.
- The public-facing application must **never** use the `BYPASSRLS` role. The application DB user must always be subject to RLS policies.

## Per-Tenant Rate Limiting

- Implement per-tenant rate limiting to prevent a "noisy neighbor" from exhausting VPS resources. Key rate limit counters by tenant ID.

## Tenant Offboarding

- When a tenant cancels, set `deleted_at` on the **`tenants` table row only** (this is the sole permitted soft-delete column per `25-data-postgres.md`). A background job hard-deletes all tenant-scoped data from other tables after the retention period — do not add `deleted_at` to every tenant-scoped table.
- Test deletion logic explicitly to verify it does not cascade to other tenants' data.
- For data export: with RLS active and tenant context set, a simple `SELECT *` from each table produces a clean, tenant-scoped export.

## Background Jobs

- Tenant-aware background jobs must carry the `tenant_id` in the job payload. The worker sets `SET LOCAL app.tenant_id` before executing any DB queries.
- Never rely on the enqueueing request's connection context — the worker runs in a separate process/transaction.

---

## Supabase Auth RLS Note (legacy — migrate to self-hosted)

**Legacy only.** New projects use native mode with Pattern A (`fabrik-lib/fastapi-user-auth`); a project already on Supabase Auth (Pattern B) should migrate to native or compat mode (`agents-fabrik.md § Supabase`). For a project *still* on Supabase Auth, RLS context works differently:

- Supabase automatically sets `auth.uid()` from the JWT — no manual `SET LOCAL` needed for user-level isolation.
- For **tenant-level** isolation (org/workspace), you still need `tenant_id` + RLS policies. Set tenant context via a Supabase Edge Function or by embedding `tenant_id` as a custom JWT claim.
- Supabase's `FORCE ROW LEVEL SECURITY` and `ENABLE ROW LEVEL SECURITY` rules apply identically.
- The `current_tenant_id()` function pattern above works alongside Supabase's built-in `auth.uid()`. Use `auth.uid()` for user-scoping, `current_tenant_id()` for tenant-scoping.

Once migrated, compat mode owns the `auth.*` helpers natively (§ compat mode above) — no Supabase runtime dependency remains.

---

## Related Rule Packs

- `35-security-auth.md` — Pattern A / A-compat / B auth; Pattern A-compat pairs with this pack's compat-mode RLS
- `45-testing-strategy.md` — tenant isolation testing (query as A, verify B invisible)
- `60-saas-ui.md` — tenant UI: org switcher, team management, tenant-scoped nav
- `75-workers-jobs.md` — background jobs must carry `tenant_id` in payload
- `85-payments-billing.md` — tenant-scoped subscription data
- `88-saas-launch-checklist.md` — per-tenant rate limiting in planning
- `00-domain-saas.md` — SaaS domain module §4 (tenancy architecture decisions)

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Database-per-tenant on single VPS | Shared DB with PostgreSQL RLS |
| Schema-per-tenant at scale (>100 tenants) | Shared DB with PostgreSQL RLS |
| Manual `WHERE tenant_id = ...` in application queries | RLS policies with `current_tenant_id()` |
| `SET app.tenant_id` at connection pool level | `SET LOCAL app.tenant_id` per transaction |
| Global variables / module-level state for tenant context | Python `ContextVar` |
| Redis keys without tenant prefix (`user_session_1`) | `t:{tenant_id}:user_session_1` |
| Application DB user with `BYPASSRLS` | Dedicated `fabrik_admin` role for maintenance only |
| RLS-protected table without `tenant_id` index | B-tree index on `tenant_id` (minimum) |
| Trusting `X-Tenant-ID` without membership check | Validate user belongs to tenant before `SET LOCAL` |
| `current_tenant_id()` / `auth.uid()` that raises or defaults on unset context | `EXCEPTION WHEN OTHERS THEN RETURN NULL` (fail-closed deny) |
| Rewriting `auth.uid()` policies to migrate off Supabase Auth | compat mode — own `auth.*` + `request.jwt.claims` GUC; policies unchanged |
| Mixing `app.tenant_id` (native) and `request.jwt.claims` (compat) in one project | Pick one mode; both share FORCE RLS + `fabrik_admin` |

---

## Done When

- [ ] All tenant-scoped tables have `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.
- [ ] RLS mode chosen (native `app.tenant_id` / `current_tenant_id()` OR compat `request.jwt.claims` / `auth.uid()`) — not both in one project.
- [ ] Helper is fail-closed: `current_tenant_id()` / `auth.uid()` return `NULL` on unset/invalid context, verified by a no-context probe (helper `NULL`, scoped read denies).
- [ ] compat mode: `auth` schema + `auth.uid()/jwt()/role()` + `anon`/`authenticated`/`service_role` owned natively; existing `auth.uid()` policies left unchanged.
- [ ] Cross-tenant probe passes: write as A, assert invisible to B, assert deny with no context.
- [ ] Tenant context set via `SET LOCAL app.tenant_id` per transaction — never at connection level.
- [ ] FastAPI middleware resolves tenant ID into a `ContextVar` — no global state.
- [ ] Every `tenant_id` column has a B-tree index.
- [ ] Redis keys prefixed with `t:{tenant_id}:` — no unprefixed tenant data.
- [ ] Background jobs carry `tenant_id` in payload and set context before DB access.
- [ ] Application DB user does not have `BYPASSRLS` — only `fabrik_admin` does.
- [ ] Tenant offboarding: `deleted_at` on `tenants` row only; background job hard-deletes scoped data after retention period.
- [ ] Tenant context is only set after verifying authenticated user's membership in the requested tenant.
