---
activation: glob
globs: ["**/tenants/**", "**/middleware/**", "**/rls/**", "**/organizations/**"]
description: Multi-tenant SaaS discipline — tenant isolation, PostgreSQL RLS, context propagation, cross-tenant prevention
trigger: glob
---

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

- When a tenant cancels, soft-delete their data (set a `deleted_at` timestamp). A background job purges data after a retention period.
- Test deletion logic explicitly to verify it does not cascade to other tenants' data.
- For data export: with RLS active and tenant context set, a simple `SELECT *` from each table produces a clean, tenant-scoped export.

## Background Jobs

- Tenant-aware background jobs must carry the `tenant_id` in the job payload. The worker sets `SET LOCAL app.tenant_id` before executing any DB queries.
- Never rely on the enqueueing request's connection context — the worker runs in a separate process/transaction.

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

---

## Done When

- [ ] All tenant-scoped tables have `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.
- [ ] RLS policies use `current_tenant_id()` function — fail-closed when tenant context is unset.
- [ ] Tenant context set via `SET LOCAL app.tenant_id` per transaction — never at connection level.
- [ ] FastAPI middleware resolves tenant ID into a `ContextVar` — no global state.
- [ ] Every `tenant_id` column has a B-tree index.
- [ ] Redis keys prefixed with `t:{tenant_id}:` — no unprefixed tenant data.
- [ ] Background jobs carry `tenant_id` in payload and set context before DB access.
- [ ] Application DB user does not have `BYPASSRLS` — only `fabrik_admin` does.
- [ ] Tenant offboarding uses soft-delete with tested cascade isolation.
- [ ] Tenant context is only set after verifying authenticated user's membership in the requested tenant.
