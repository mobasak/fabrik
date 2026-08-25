# Design — least-privilege payments-ingest DB role in the fabrik registrar

Status: CONVERGED
Owner: fleet (registrar is fleet's beat)
Date: 2026-08-23
Stage: 1-design (converged via /fabrik-spec-review, md5-verified no-op) → next: operator approval → /fabrik-plan-after-chat

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

## Grounding — the routed request, corrected

The routing mail (fabrik-mail `01M0PX55QK`) states *"the RLS pack `.windsurf/rules/95-multi-tenant-saas.md`
MANDATES a `fabrik_admin` BYPASSRLS role that `fabrik apply` never creates."* Corrected against the tree
(an earlier review pass of this spec wrongly called the whole claim ungrounded — it is not):

- **The pack EXISTS** — at `.windsurf/rules/saas/95-multi-tenant-saas.md` (the mail's path dropped the
  `saas/` prefix). It **does** mandate a `fabrik_admin` role: `NOLOGIN NOINHERIT BYPASSRLS`, *"for
  migrations / backups / exports only — the public app role never connects as it"* (95:92, 154-155, 230).
- **BUT `fabrik_admin` is neither a `fabrik apply` gap nor usable for ingest.** It is created by the
  **project's own migration** (canonical `053_force_rls_and_admin.sql`, 95:57/68), not the registrar; and
  it is **`NOLOGIN`** — it has no connection string and can never serve a webhook-ingest path. The mail
  conflated two distinct roles.
- **The REAL gap this spec fills** is a **`LOGIN` cross-tenant READ role** for the ingest path — which
  the pack does **not** provide (it defines only `fabrik_admin` NOLOGIN + the RLS-subject app role).
- The pack's own least-privilege rules **reinforce** the policy-based choice: *"the public-facing
  application must never use the BYPASSRLS role; the application DB user must always be subject to RLS"*
  (95:155/230), and the mandatory cross-tenant probe must run under `NOSUPERUSER NOBYPASSRLS` (95:94-102).
- The **consuming authority** is fabrik-lib's contract (`/opt/fabrik-lib/payments/README.md:109-118` +
  `SPEC.md:58`): a cross-tenant **service role** for ingest, satisfiable **two ways** — a `BYPASSRLS` role
  *or* an "equivalent service *policy*" (`verify_service_role(conn, allow_policy_based=True)`). The
  non-BYPASSRLS policy-based role is a **first-class, already-supported** path, not a workaround.

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

This is not a novel posture — it is the registrar's **existing default**: the watchdog RO role
(`{db}_wd_ro`) is the same class of non-owner role under FORCE RLS, and the driver documents the same
answer — *"a multi-tenant app that needs cross-tenant diagnosis must add a policy … least privilege is
the default here"* (`postgres.py:645-649`). The payments-ingest role reuses that established pattern.

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
   `create_watchdog_roles`, incl. its split CREATE-then-idempotent-GRANT and fresh-password-only DSN
   injection): mint `{db}_payments_ingest` (LOGIN NOSUPERUSER, CSPRNG password, **no BYPASSRLS**), then
   **idempotently re-apply** `GRANT SELECT ON subscriptions, customers` + `CREATE POLICY … FOR SELECT TO
   {db}_payments_ingest USING (true)` on those tables — the policy step **guarded on table existence**
   (self-heals on the apply after the app's schema lands; see § Sequencing). Inject
   `PAYMENTS_INGEST_DATABASE_URL` only on fresh creation (mirror the watchdog RO/RW URL injection,
   `infrastructure.py:583-591`).
3. **Consumer wiring** (documented for the vendoring project, not built here): ingest connects with
   `PAYMENTS_INGEST_DATABASE_URL` and calls `verify_service_role(conn, allow_policy_based=True)` at boot.

### Sequencing (RESOLVED in review — grounded, the watchdog precedent settles it)

The policy `CREATE POLICY ... ON subscriptions` references tables from the **project's**
`db/schema.sql`, which the **dedicated owner role applies itself** at deploy (`postgres.py:404`) —
*after* `fabrik apply` runs the registrar. So the tables do **not** exist when the role is minted.
This is the **exact** situation `create_watchdog_roles` already handles: its
"**Schema/table GRANTs are re-applied every call (idempotent, additive) so … tables added by a later
migration are covered**" (`postgres.py:639-643`), and its RO role is the **identical class** to ours —
"a multi-tenant app that needs cross-tenant diagnosis **must add a policy for `{db}_wd_ro`** … least
privilege is the default here" (`postgres.py:645-649`).

**Resolution (registrar owns role + grant + policy, idempotently re-applied — NOT the project schema):**
- Registrar mints `{db}_payments_ingest` (LOGIN, NOSUPERUSER, **no BYPASSRLS**, CSPRNG password) — a
  role is DB-global, safe to create before any table exists — and injects `PAYMENTS_INGEST_DATABASE_URL`
  only on fresh creation (the watchdog password-lifecycle rule, `postgres.py:657-660`).
- The `GRANT SELECT` + `CREATE POLICY … USING (true)` on `subscriptions`/`customers` is **idempotent and
  re-applied on every apply** (the watchdog additive-GRANT model), so it self-heals on the first apply
  **after** the app's schema lands. Unlike a GRANT (coverable pre-table via `ALTER DEFAULT PRIVILEGES FOR
  ROLE <owner>`), `CREATE POLICY` needs the table to exist — so the policy step is **guarded on table
  existence** (skip-if-absent, applied on the next apply once present). This keeps provisioning in ONE
  place (the registrar) and does not make the project author RLS policy for a fabrik-minted role.

The earlier "project schema owns the policy" option is **rejected**: it forces every payments-vendoring
project to hardcode the registrar's role name into its migrations and re-implement the guard the
registrar already owns for `{db}_wd_ro`.

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
- With the registrar-provisioned policy in place, `resolve_org()` returns the org for an unsigned (iyzico) webhook;
  `verify_service_role(conn, allow_policy_based=True)` passes; the role reads **only**
  `subscriptions`/`customers` cross-tenant (a leaked DSN cannot read other RLS tables).
- The rule-pack documentation slice is filed to infra, not committed by fleet.
