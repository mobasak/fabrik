# Design — least-privilege payments-ingest DB role in the fabrik registrar

Status: DRAFT
Owner: fleet (registrar is fleet's beat)
Date: 2026-08-23
Stage: 1-design → next: /fabrik-spec-review

## Problem

fabrik-lib's `payments` module resolves a provider webhook to its owning tenant via
`PgWebhookStore.resolve_org()`, which **must read `subscriptions` + `customers` with no tenant
context** — the tenant is the unknown being discovered. Under the multi-tenant RLS model (RLS
`ENABLE` + `FORCE`; the app connects as a tenant-scoped role that does
`SET LOCAL app.current_org = '<uuid>'` per request), that lookup returns `None` for every event
whose tenant is not carried in a *signed* payload field. Paddle survives (signed `custom_data`);
**iyzico has no signed org field, so every iyzico webhook is unattributable** and payments ingest
is silently blocked — `resolve_org()` returning `None` is indistinguishable from "first-time
customer" (fabrik-lib README § Gotchas; reported by transdoc 2026-08-23).

`fabrik apply` provisions exactly one DB role today (`_provision_postgres`, `infrastructure.py:486`
— a dedicated non-superuser role that OWNS the DB). It provisions **no** cross-tenant ingest role,
so a payments-vendoring project cannot wire ingest correctly.

## Grounding — what the routed request got wrong, and the real authority

The routing mail (fabrik-mail `01M0PX55QK`) states *"the RLS pack `.windsurf/rules/95-multi-tenant-saas.md`
MANDATES a `fabrik_admin` BYPASSRLS role."* **Both halves are ungrounded** (verified this session):

- `.windsurf/rules/95-multi-tenant-saas.md` **does not exist**; the multi-tenant/payments rules live in
  `.windsurf/rules/saas/00-domain-saas.md` and `core/85-payments-billing.md`, and **neither names
  `fabrik_admin` or `BYPASSRLS`** (grep-clean).
- The **real authority** for the two-role requirement is fabrik-lib's own contract:
  `/opt/fabrik-lib/payments/README.md:109-118` + `SPEC.md:58`. It requires a cross-tenant **service
  role** for ingest and **explicitly supports two ways to satisfy it**: a `BYPASSRLS` role *or* an
  "equivalent service *policy*" (`verify_service_role(conn, allow_policy_based=True)`). So a
  non-BYPASSRLS, policy-based role is a **first-class, already-supported** path — not a workaround.

## External grounding (live, cited)

PostgreSQL 17 docs — Row Security Policies
(<https://www.postgresql.org/docs/current/ddl-rowsecurity.html>, fetched 2026-08-23):

- A **PERMISSIVE** policy `... FOR SELECT USING (true)` grants **unrestricted cross-tenant SELECT** on
  that table — exactly the scoped discovery read `resolve_org` needs.
- **`BYPASSRLS` is GLOBAL, not table-scopeable**: *"Superusers and roles with the BYPASSRLS attribute
  always bypass the row security system when accessing a table"* — i.e. on **every** RLS table the role
  touches, not just `subscriptions`/`customers`.
- Table owners bypass RLS by default; `FORCE ROW LEVEL SECURITY` makes the owner subject to policies
  (why connecting ingest as the table-owner role under FORCE still fails — the transdoc symptom).

## Decision (fleet owns the security posture): policy-based, per-table — NOT global BYPASSRLS

The registrar provisions a **dedicated login role scoped to a permissive `USING(true)` SELECT policy on
`subscriptions` + `customers` only**, with **no `BYPASSRLS` attribute**, exposed as a separate
`PAYMENTS_INGEST_DATABASE_URL`. Rationale: `PAYMENTS_INGEST_DATABASE_URL` is used by an internet-facing
webhook endpoint; if it leaks, a BYPASSRLS role reads **every tenant's rows on every RLS table**, while
a policy-scoped role reads cross-tenant on **only those two tables**. Same functional result, an
order-of-magnitude smaller blast radius — the least-privilege choice for a single-operator fleet
(threat model: a leaked ingest DSN, not an insider). The consuming app asserts the wiring at boot with
`verify_service_role(ingest_conn, allow_policy_based=True)`.

## Approaches considered

| # | Approach | Verdict |
|---|---|---|
| A | **Full `BYPASSRLS` service role** (fabrik-lib default). Simplest; `verify_service_role` passes with no flag. | **Rejected** — global bypass; a leaked ingest DSN exposes all RLS tables, all tenants. |
| **B** | **Policy-based per-table role** — login role, no BYPASSRLS, `GRANT SELECT` + permissive `USING(true)` SELECT policy on `subscriptions`+`customers`; app passes `allow_policy_based=True`. | **Chosen** — least privilege; fabrik-lib-supported; scoped blast radius. |
| C | **`SECURITY DEFINER` resolver function** owned by a privileged role, called by the tenant role. | **Rejected** — `resolve_org()` issues direct queries, not a function call; adopting this forks fabrik-lib's `PgWebhookStore`. Out of scope. |

## Vendor verdict (fabrik-lib ladder + hub-tooling)

- **Registrar side = ENHANCE existing hub tooling** (not a new module). The change follows the exact
  precedent of `provision_watchdog_roles` (`infrastructure.py:577-591` → `create_watchdog_roles` in
  `src/fabrik/drivers/postgres.py`): a shape-flag-gated secondary-role mint + a second injected
  connection string. Build there.
- **Consumer side = fabrik-lib `payments`, already built.** No new fabrik-lib module; ingest just wires
  `PAYMENTS_INGEST_DATABASE_URL` + `verify_service_role(..., allow_policy_based=True)`. N/A for a vendor
  candidate — the capability exists, it is the *registrar* that must provision the role.

## Design (build shape — details converge in the plan)

1. **Shape flag** — add `needs_payments_ingest: bool` to `Shape` (`spec_loader.py:205`), default `false`.
   Docstring: "project vendors fabrik-lib `payments`; provision a scoped cross-tenant ingest role +
   `PAYMENTS_INGEST_DATABASE_URL`." Requires `needs_database: true`.
2. **Registrar** — in `_provision_postgres`, when `shape.needs_payments_ingest` (and `needs_database`),
   call a new `create_payments_ingest_role(db_name)` in `drivers/postgres.py` (mirror
   `create_watchdog_roles`): mint `<db>_payments_ingest` (LOGIN, CSPRNG password, **no BYPASSRLS**),
   `GRANT SELECT ON subscriptions, customers`, and `CREATE POLICY ... FOR SELECT TO <role> USING (true)`
   on those two tables. Inject `PAYMENTS_INGEST_DATABASE_URL` (mirror the watchdog RO/RW URL injection,
   `infrastructure.py:583-591`).
3. **Consumer wiring** (documented for the vendoring project, not built here): ingest connects with
   `PAYMENTS_INGEST_DATABASE_URL` and calls `verify_service_role(conn, allow_policy_based=True)` at boot.

### ⚠️ Open design point for /fabrik-spec-review (sequencing)

The policy `CREATE POLICY ... ON subscriptions` references tables that come from the **project's**
`db/schema.sql`, applied by the app at deploy — they may **not exist** when `fabrik apply` runs the
registrar. Resolution options to converge: (a) make role+grant+policy idempotent and run/repair it
**after** first schema apply (a post-deploy registrar step, like the watchdog roles' re-check); (b) the
project's schema migration creates the policy itself and the registrar only mints the *role* + injects
the DSN. **(b) is the leaner split** (registrar owns identity + secret; the project owns its own
table policies) and avoids the registrar reaching into project-defined tables — provisionally preferred,
to be confirmed in review.

## Blast radius + build split (sync-consciousness)

- **Registrar code** (`src/fabrik/spec_loader.py`, `src/fabrik/orchestrator/infrastructure.py`,
  `src/fabrik/drivers/postgres.py`) — **fleet's beat, collision-free** (not a governance-sync trigger).
- **Rule-pack doc** (documenting the ingest-role contract + `needs_payments_ingest` in the SaaS/payments
  packs under `.windsurf/rules/`) — **infra's beat**; `.windsurf/rules/` is a **governance-sync trigger**
  distributing fleet-wide, and infra is **actively editing the rulesets now**. The plan MUST hand the
  pack-doc slice to infra (mail request), and fleet must NOT touch `.windsurf/rules/` concurrently.
- Consumer impact: every project vendoring fabrik-lib `payments` (transdoc first). Additive + flag-gated
  (`default false`) → zero effect on projects that don't set it.

## Success criteria

- `Shape` accepts `needs_payments_ingest`; `fabrik plan` on a spec with it set previews the ingest role +
  `PAYMENTS_INGEST_DATABASE_URL`.
- `fabrik apply` mints a **non-BYPASSRLS** `<db>_payments_ingest` role and injects the DSN.
- With the project's policy in place, `resolve_org()` returns the org for an unsigned (iyzico) webhook;
  `verify_service_role(conn, allow_policy_based=True)` passes; the role reads **only**
  `subscriptions`/`customers` cross-tenant (a leaked DSN cannot read other RLS tables).
- The rule-pack documentation slice is filed to infra, not committed by fleet.
