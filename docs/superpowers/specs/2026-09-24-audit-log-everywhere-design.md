# The audit log in every Fabrik project, made append-only by a non-owner app role

**Status:** DRAFT
**Profile:** delta — every intake item maps to code that exists today (the Postgres registrar, the scaffolder, the vendored module); the delta adds a consumer-facing contract (a second DSN), so `## Personas`, `## Lifecycle` and the constraints digest are written in full.
**Stage:** 1-design · **Beat:** fleet (scaffolder + registrar) · **Decisions:** D-368 (the mandate), D-385 (this design and its DSN contract, adopted on the operator's delegation)
**Sources:** fleet mails 01M37RTQ0NX8MJQAAXAHHMG723, 01M37RV3WG528WN7ZG6HRHCCF3, 01M37SPA86MGV4Z7DDJFY4E4DJ · research ledger `docs/reference/research/2026-09-24-audit-log-everywhere-ledger.md`

## Personas

- **PRIMARY — the operator, in their own words (D-368):** *"very important one. all project must have this properly and fabrik-lib modules must be modified if needed by fabrik-lib agents"*. Their loop is to be able to say, for any project, "it has an audit log, it cannot be rewritten by the app, and it is checked". **Step budget: 3** — (1) the project is deployed or re-applied through `fabrik apply`; (2) the registrar reports the app role and the audit grants as applied; (3) the weekly job's last run reads clean. Anything that makes that loop longer (a manual VPS step, a hand-run revoke) is a design defect.
- **The project agent** (each of the ~41 project repos' Claude sessions) — holds the per-repo work: vendoring the module, folding the table into the project's schema, recording its sensitive operations, and repointing its migration step and runtime DDL at the owner DSN before cutover. Receives one mail per repo.
- **The hub fleet agent** (this beat) — holds the registrar change, the scaffolder change, the cutover flag and the pre-cutover check, and runs the migration waves.
- **fabrik-lib** — holds the module (async writer, per-prefix retention end dates, IdP fail-loud; mail 01M37RT50PAADKY3Y5NR8GRCZK) and a Node port for `node-api`/`file-api`.
- **infra** — holds the rule pack `core/app-audit-log.md`, whose owner-role caveats go stale when this ships, and the `docs/COMPLIANCE.md` allowlist conflict.
- **Automated consumers:** the running app (writes audit rows as `<db>_app`); the scheduled retention job (deletes expired rows as the owner); the weekly verification job (reads the chain, checks the watchdog role's privileges); the watchdog sidecar (its `<db>_wd_rw` role must lose `UPDATE`/`DELETE`/`TRUNCATE` on `audit_log`); a project's `migrate` service and any runtime-DDL library (connect as the owner after cutover).

Every mechanism below names which of these holds it.

## Goal

Every Fabrik project has the app-audit-log "properly" — the five points of `.windsurf/rules/core/app-audit-log.md:22-45` — and its `audit_log` table is append-only against the application, which PostgreSQL can give only when the app does not connect as the table's owner.

## Why this exists

- **The mandate is unmet.** 0 of 12 emitted scaffold schemas carries the table and 4 of 41 project repos call `record_event` (D-368's census; fleet mail 01M37RTQ0NX8MJQAAXAHHMG723, corrected by 01M37RV3WG528WN7ZG6HRHCCF3).
- **Append-only is impossible today.** The registrar makes each project's single role the database OWNER (`src/fabrik/drivers/postgres.py:409`, `ALTER DATABASE "{db_name}" OWNER TO "{db_user}"`) and injects only that DSN as `DATABASE_URL` (`src/fabrik/orchestrator/infrastructure.py:638-643`). PostgreSQL: *"The right to modify or destroy an object is inherent in being the object's owner, and cannot be granted or revoked in itself"* (https://www.postgresql.org/docs/current/ddl-priv.html, fetched 2026-09-24). So the module's `REVOKE UPDATE, DELETE` cannot bind the app, and the pack has to tell every project its chain is tamper-evidence only (`core/app-audit-log.md:26-31`).
- **The watchdog can delete audit rows.** `<db>_wd_rw` gets `SELECT, INSERT, UPDATE, DELETE ON ALL TABLES` plus the same by default privileges (`src/fabrik/drivers/postgres.py:710-730`), and the watchdog is on for every project (`core/30-ops.md:209-211`). Today the pack asks each project to revoke it by hand after every provisioning run (`core/app-audit-log.md:31-36`), which the ops pack forbids (`core/30-ops.md:420`).

How the design removes exactly that: a second, non-owning login role becomes the app's connection; the owner is kept for schema changes and retention; the registrar applies the audit grants and the watchdog revoke on every deploy; the scaffolder emits the module, table, grants and jobs so a new project is compliant at creation.

## What exists today (grounded)

- **Registrar, owner role:** `create_database` (`src/fabrik/drivers/postgres.py:289`) creates the role `LOGIN PASSWORD` (`:393-400`), `GRANT ALL PRIVILEGES ON DATABASE` (`:403`) and makes it owner (`:409`). Role name = database name (`src/fabrik/orchestrator/infrastructure.py:614`). The DSN is injected only on a fresh create; a re-apply never overwrites it (`src/fabrik/drivers/postgres.py:340-342`, `src/fabrik/orchestrator/infrastructure.py:633-637`).
- **Registrar, scoped-role precedent:** `create_payments_ingest_role` (`src/fabrik/drivers/postgres.py:829-878`) mints `CREATE ROLE ... WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS` only when missing, re-applies its grants on every call, and injects `PAYMENTS_INGEST_DATABASE_URL` only when freshly minted (`src/fabrik/orchestrator/infrastructure.py:705-714`); it is gated by `shape.needs_payments_ingest` (`src/fabrik/spec_loader.py:333-345`).
- **Watchdog roles:** `<db>_wd_ro` / `<db>_wd_rw` (`src/fabrik/drivers/postgres.py:612-746`), rw with DML on all tables and by default privileges `FOR ROLE <owner>` (`:710-730`).
- **Migrations:** Fabrik runs none; a project applies `db/schema.sql` itself, as the owner (`src/fabrik/scaffold.py:2113-2114`).
- **Scaffolder:** every type gets a placeholder `db/schema.sql` (`src/fabrik/scaffold.py:1484`); only the saas backend (saas-skeleton, static-site, office-extension) gets a real `server/db/schema.sql` (`:2111`, `:3270`). No scaffolder vendors app-audit-log; the saas scaffold ships a stdout `AuditLogger` stub (`:2477`). Only the saas worker has a scheduler — a beat loop with an advisory-lock leader whose periodic-task hook is a comment (`:2773-2804`). The vendoring precedent is `_vendor_fastapi_user_auth` (`:3290-3305`).
- **Module:** `/opt/fabrik-lib/app-audit-log` — `audit_log` table with a hash chain (`schema.sql:28-71`); it ships no grants, only a commented template (`schema.sql:18-26`); retention is `data_retention.sql`; `record_event` is synchronous (psycopg); `verify_chain` is synchronous and read-only.
- **Live fleet (measured 2026-09-24):** 22 of 72 live specs carry `needs_database: true`, 19 with a repo on this box. Four run migrations at deploy time through `DATABASE_URL` (calendar-orchestration-engine's entrypoint; site-provisioner, tojlo-mail and transdoc via a compose `migrate` service); three run DDL from app code (seo, web-ecommerce-factory, whatsapp-agent); vendored libraries create tables at runtime in almost every repo (`libs/subagents/pg_ledger.py:44`, `CREATE TABLE IF NOT EXISTS subagent_runs`).

## Chosen approach — the delta

### 1. A non-owner app role (registrar; holder: hub fleet agent)

For every project database the registrar mints `<db>_app`, following the payments-ingest shape:

- `CREATE ROLE "<db>_app" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD '<32 chars>'` only when missing; the password comes from the existing `_generate_password` (32 characters, `[a-zA-Z0-9]`, `core/35-security-auth.md:320-324`). The role is never granted membership of the owner role, because members inherit the owner's rights (https://www.postgresql.org/docs/current/role-membership.html).
- Grants, re-applied on every provisioning run: `CONNECT` on the database; `USAGE, CREATE` on schema `public` (so runtime-DDL libraries create and own their own tables); `SELECT, INSERT, UPDATE, DELETE` on all existing tables and `USAGE, SELECT` on all existing sequences; `ALTER DEFAULT PRIVILEGES FOR ROLE <owner> IN SCHEMA public` granting the same on future tables and sequences. Default privileges cover only objects created later, by that role, so existing tables need the explicit grant (https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html).
- On `audit_log`, owned by the owner: `REVOKE UPDATE, DELETE, TRUNCATE ... FROM "<db>_app"` and `GRANT INSERT, SELECT`. Writes still work: the chain lock is `pg_advisory_xact_lock`, which needs no table privilege (`core/app-audit-log.md:205-207`).
- Where the project defines the Pattern A-compat group roles (`anon` / `authenticated` / `service_role`, `NOLOGIN NOINHERIT`, `core/35-security-auth.md:91`), `<db>_app` is granted the same memberships the owner holds, so `SET LOCAL role` keeps working.
- The watchdog: `REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM "<db>_wd_rw"` on every provisioning run, after its default grants — the registrar-side fix for the hand-run revoke.

### 2. The DSN contract (holder: registrar; decided in D-385)

- `DATABASE_URL` is the app role. The owner DSN is injected as **`DATABASE_URL_OWNER`**, named after the existing second-DSN precedent `DATABASE_URL_DIRECT` (`core/25-data-postgres.md:254`), and is used only by migrations, `schema.sql`, the retention job and any runtime-DDL step that must own what it alters.
- **New projects** get both at creation.
- **Existing projects** switch one at a time through an explicit spec flag, never on a routine re-apply (the registrar's preservation of an existing `DATABASE_URL` stays the default). Before the switch the registrar runs a **pre-cutover check**: the app role exists with its grants; a probe connected as `<db>_app` can `SELECT`/`INSERT` on a sample table, use a sequence, and is refused `DELETE` on `audit_log`; and the project declares that its migrate step and runtime DDL read `DATABASE_URL_OWNER`. A failed check refuses the switch.
- **Rollback** for a project: put the owner DSN back into `DATABASE_URL` (the same flag, reversed). The owner DSN is never removed, which is the published rollback pattern (github.com/jrkphani/GeDe/issues/36, fetched 2026-09-24).
- Neither DSN has a default in code: a missing value fails at boot (`core/35-security-auth.md:273-274`).

### 3. The scaffolder (holder: hub fleet agent)

- **Python-backed types** — saas-skeleton, python-api, python-api-gpu, file-worker, and the `server/` that office-extension, chrome-extension, mobile-app and static-site emit (`core/app-audit-log.md:50-51`): vendor the module following `_vendor_fastapi_user_auth`; fold `schema.sql` (table, indexes, chain-check view) and the grants into the project's schema file; replace the stdout `AuditLogger` stub (`src/fabrik/scaffold.py:2477`) with the real writer.
- **Jobs:** a retention job (the module's `data_retention.sql`, run as the owner via `DATABASE_URL_OWNER`) and a weekly job that runs `verify_chain(strict=True)` from a persisted cursor (`core/app-audit-log.md:43-45`) and checks `has_table_privilege('<db>_wd_rw','audit_log','UPDATE'|'DELETE')`. The saas beat loop schedules both; the other Python types get a scheduled companion service with the owner DSN overridden, because a companion otherwise inherits the app's env (`core/30-ops.md:161`).
- **Node types** (node-api, file-api): the table and grants; the writer waits on fabrik-lib's Node port (`core/app-audit-log.md:51-52`).
- **Backend-less types** (desktop-app, docusaurus): no module; they record through the backend they call or state they have no sensitive operation (`core/app-audit-log.md:52-54`).

### 4. Migrating the existing fleet (holders: hub fleet agent + each project agent)

- **Pilot** one low-risk database project, then waves.
- Per project: (1) the registrar mints `<db>_app` — inert until the switch; (2) the project agent, mailed one per repo, vendors the module, folds the table, records its sensitive operations, and repoints its migrate step and runtime DDL at `DATABASE_URL_OWNER`; (3) the pre-cutover check; (4) the switch; (5) a verification run as the app role.
- The ~19 project repos without a database record through a backend or state none, per the pack.

## Rejected alternatives

- **Add `APP_DATABASE_URL` and keep `DATABASE_URL` as the owner** (judge panel: 1 of 3 ranked it first). Nothing changes under a live app until its code reads the new variable, but every database-backed project needs a code change before it is protected, and the fleet carries two meanings of "the DSN" indefinitely. The chosen flip changes no app code in the projects that only read and write data, and its risk is bounded by the pre-cutover check.
- **Keep the owner role; enforce append-only with `BEFORE UPDATE/DELETE` triggers** (disqualified by all three judges). The owner can `DISABLE` or `DROP` the trigger (https://www.postgresql.org/docs/current/sql-altertable.html, https://www.postgresql.org/docs/current/sql-droptrigger.html), so it is tamper-evident only; field practice treats triggers as defense-in-depth (dev.to/gentlyding, fetched 2026-09-24).
- **pgaudit instead of the module.** It logs SQL statements to the server log, not application actor/action/target events (github.com/pgaudit/pgaudit README, fetched 2026-09-24).
- **Retention by partition drop.** Field practice (anishgandhi.com, fetched 2026-09-24) partitions and drops; the module's retention is a row `DELETE` by legal period, and changing its storage is fabrik-lib's call, not this spec's.
- **Grant the app role no `CREATE` on schema.** Tighter, but 47 of 48 synced repos create tables at runtime through vendored libraries; they would fail at the switch. With `CREATE`, the app owns only the tables it creates, and `audit_log` stays the owner's.
- **Per-project opt-in forever.** Rejected: the mandate is "all project"; new projects get the contract at creation and the waves cover the rest.

## Constraints digest (verbatim, re-read 2026-09-24)

| Pack:line | Rule (verbatim) | Relevance |
|---|---|---|
| `core/app-audit-log.md:26-28` | "⚠️ Append-only is a ROLE-SEPARATION property, not a grant: Fabrik's registrar makes the app's role the database OWNER, and an owner can always re-grant itself `DELETE`, so the module's `REVOKE UPDATE, DELETE` cannot bind it." | The reason for § 1 |
| `core/app-audit-log.md:40-42` | "4. **Retention scheduled** — `data_retention.sql` from the project's scheduler, as the owner role" | Retention uses `DATABASE_URL_OWNER` |
| `core/app-audit-log.md:50-52` | "`node-api` and `file-api` (both Node) have no fabrik-lib port yet (filed to fabrik-lib); until it lands it owes the table plus a writer that hashes byte-identically to `canonical_payload`." | § 3 Node types |
| `core/10-python.md:133` | "**Config convention:** apps read a complete `DATABASE_URL`" | The app keeps reading `DATABASE_URL` (§ 2) |
| `core/25-data-postgres.md:254` | "must connect directly to `postgres-main:5432` via a separate `DATABASE_URL_DIRECT` env var" | Naming precedent for `DATABASE_URL_OWNER` |
| `core/25-data-postgres.md:331` | "Config via `get_settings().database_url` (Pydantic Settings) — no raw `os.getenv("DATABASE_URL")`." | The owner DSN is read through Settings too |
| `core/30-ops.md:161` | "the scaffolder emits a 2nd compose service that shares the app's build/image + env + `DATABASE_URL`/`REDIS_URL`, overriding only `command` + `container_name` + `memory`." | The jobs companion needs the owner DSN overridden |
| `core/30-ops.md:420` | "\| Manual VPS edits / registrar fix-ups \| `fabrik apply` / `reconcile-all` (spec-driven) \|" | The watchdog revoke and the cutover are registrar work |
| `core/30-ops.md:444-445` | "A one-shot **`migrate` compose service** the app services gate on: … Same image, same env" | A migrate service must read `DATABASE_URL_OWNER` after cutover |
| `core/35-security-auth.md:273` | "# DSNs and secrets get NO fallback — a missing value fails LOUDLY at boot" | Neither DSN has a default |
| `core/35-security-auth.md:321` | "- **32 characters**, charset `[a-zA-Z0-9]` only (no symbols — survives `.env` round-trip + shell quoting)." | The app role's password |
| `core/40-documentation.md:186` | "**Rule:** Edit existing docs instead of creating new ones." | `docs/COMPLIANCE.md` is not in the allowlist — routed to infra |

## fabrik-lib verdict

| Capability | Verdict | Module · note |
|---|---|---|
| Audit table, hash chain, writer, verifier, retention SQL | VENDOR | `app-audit-log` — as-is; pending module changes are fabrik-lib's (01M37RT50PAADKY3Y5NR8GRCZK) |
| Async writer for asyncpg apps | VENDOR + ENHANCE upstream | fabrik-lib owns it; until then the pack's helper recipe (`core/app-audit-log.md:217-222`) |
| Node writer | upstream | fabrik-lib Node port (filed by infra) |
| App role, grants, DSN, cutover | BUILD in the hub | registrar code; nothing in fabrik-lib provisions roles |

## Shape and infra implications

No new `shape:` flag for the role itself — every `needs_database: true` project gets it. The existing-project switch is one new spec field (the cutover flag); its exact name and home are the plan's to settle. New env var: `DATABASE_URL_OWNER`. No new container except the jobs companion for Python types without a scheduler.

## Lifecycle

- **Adoption:** new projects are compliant at `fabrik apply`; existing projects move in waves after a pilot.
- **Growth:** the audit table grows with sensitive operations only; the retention job bounds it by legal period. If one project's table passes 10 million rows, or `verify_chain` runs longer than its weekly window, the verification narrows to the cursor window (already the design) and the storage question goes to fabrik-lib (partitioning).
- **Failure:** a missing grant makes the app's audit write fail, and the pack requires the business operation to abort or escalate rather than continue (`core/app-audit-log.md:248`); the weekly job reports a chain break or a watchdog privilege as an incident. A failed pre-cutover check refuses the switch.
- **Retirement:** superseded only if PostgreSQL gains owner-proof append-only, or the fleet leaves Postgres; the owner DSN stays as the rollback path for the life of each project.

## Validation

- Registrar: an integration test against a scratch PostgreSQL provisions a project, then connects as `<db>_app` and asserts `INSERT`/`SELECT` on `audit_log` succeed and `UPDATE`/`DELETE`/`TRUNCATE` are refused; the same as `<db>_wd_rw`. Proven red by removing the revoke.
- Re-apply idempotence: a second provisioning run changes no password and re-applies the grants.
- Pre-cutover check: refuses a project whose probe fails.
- Scaffolder: every scaffold type emitted into scratch carries the table, the grants and the jobs where its type requires them (the per-type rules of `core/app-audit-log.md:50-55`).

## Documentation landing sites

- Hub: `docs/reference/` gets the registrar's role model in the existing Postgres registrar documentation (extended, not a new doc); `docs/CONFIGURATION.md` and `.env.example` in the scaffold templates gain `DATABASE_URL_OWNER`; `docs/OPERATIONS.md` / `docs/RESILIENCE.md` §7 templates list the two jobs; `CHANGELOG.md`; `docs/DECISIONS.md` (D-385).
- Projects: each project's own `docs/CONFIGURATION.md`, `docs/OPERATIONS.md` and `docs/RESILIENCE.md` §7, updated by its agent during its wave.
- The rule pack's caveats are infra's to update when the registrar ships.

## Contract deltas

- `DATABASE_URL` changes meaning, per project at its switch: from the owner to the app role. `DATABASE_URL_OWNER` is new.
- The project `db/schema.sql` gains the audit table and grants. `docs/data-contract.md` is re-frozen in each project that has one, during its wave.

## Cost

No new paid service. Registrar and scaffolder work in the hub; one pass per database-backed project, done by that project's agent.

## Open / blocking unknowns

- **Resolved:** whether a non-owner can write the chain (yes — advisory lock, no table privilege); whether runtime-DDL libraries survive (yes, with `CREATE` on schema); whether default privileges cover existing tables (no — explicit grants).
- **Open, resolution step named:** the cutover flag's field name and where the pre-cutover check reads a project's "migrate step reads the owner DSN" declaration — settled in `/fabrik-plan-after-chat`. The three database specs with no repo on this box (test-saas-log, translator, zitadel) — the plan inventories them before the waves. Pattern A-compat membership: which projects define `anon`/`authenticated`/`service_role` — measured per project in its wave.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | D-368: *"all project must have this properly"* | IN | Goal; § 3; § 4 |
| I2 | mail 01M37RTQ item 1: "none of the 12 scaffoldable types emits the audit log" | IN | § 3 |
| I3 | mail 01M37RTQ item 2: "only trade-intelligence (5), youtube (8), transdoc (3) and iterative_image_editor (10) call it" | IN | § 4 |
| I4 | mail 01M37SPA: "provision a second, non-owning app role per project" | IN | § 1 |
| I5 | mail 01M37SPA: "The watchdog `rw` role … can also delete audit rows; exclude audit_log from it" | IN | § 1 (watchdog) |
| I6 | mail 01M37RTQ: "wires the retention job (as a DELETE-holding role) and a weekly `verify_chain`" | IN | § 3 (jobs) |
| I7 | mail 01M37RV3: "the count is 37 of 41 project repos, not 39 of 43" | IN | Why this exists |
| I8 | mail 01M37RTQ: "The fabrik-lib module changes this depends on (an async writer, per-prefix retention end dates, IdP fail-loud)" | OUT-OF-SCOPE | fabrik-lib, mail 01M37RT50PAADKY3Y5NR8GRCZK |
| I9 | The pack's owner-role caveats (`core/app-audit-log.md:26-31`, `:40-41`) go stale at ship | OUT-OF-SCOPE | infra, mailed when the registrar ships (plan's Finish step) |
| I10 | The ~41 existing repos and their live databases must be migrated, not only new scaffolds (the brief) | IN | § 2 (cutover), § 4 |

Intake: 10 items — 8 IN, 2 OUT-OF-SCOPE (each named above), 0 ASK.
