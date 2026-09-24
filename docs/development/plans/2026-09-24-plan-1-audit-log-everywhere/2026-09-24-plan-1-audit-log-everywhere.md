# The audit log in every Fabrik project — non-owner app role, DSN contract, pre-cutover check, scaffolder

Status: DRAFT
**Owner:** fleet
Spec: docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md (CONVERGED 799b1434a, D-387; approved D-389; design D-385 as corrected by D-386; mandate D-368)

## Goal

Every `needs_database` project gets a non-owning `<db>_app` login role from the registrar, against which `audit_log` is append-only (no `UPDATE`/`DELETE`/`TRUNCATE` for the app, the watchdog rw role or the Pattern A group roles). New projects are born connecting as that role, with the owner DSN in `DATABASE_URL_OWNER` and the module, table, revokes and jobs emitted by the scaffolder. Existing projects switch one at a time behind a spec flag, and only after a measured pre-cutover check passes. This plan builds the hub side. The per-project migration waves are a follow-up plan (§ Residual unknowns).

## What we already agreed (from the spec + this conversation)

- A second, non-owning app role per project; the owner is kept for schema changes and retention (mail 01M37SPA; spec § 1 → T02, T04).
- `USAGE` on `public`, never `CREATE`; `audit_log` ownership is re-asserted by the registrar, which runs as the superuser; the audit revokes go to the app role, `<db>_wd_rw` and every Pattern A group role; group memberships are `WITH INHERIT FALSE, SET TRUE` (D-386 → T02).
- `DATABASE_URL` is the app role and `DATABASE_URL_OWNER` is the owner. New projects get both at creation; existing projects switch through an explicit spec flag, never on a routine re-apply; rollback is the same flag reversed (D-385, spec § 2 → T01, T04).
- The pre-cutover check is measured, not declared: table ownership, a privilege probe as the app role and as each group role, and a scan of the repo for DDL and migration invocations. A failed check refuses the switch and names what failed (D-386, spec § 2 → T03, T04).
- Third-party images (evolution-api, zitadel) keep the owner and are never switched (D-386). T03's check refuses them structurally: there is no repo on this box to scan.
- The registrar step runs outside `create_database`, which returns early once the database exists (`src/fabrik/drivers/postgres.py:340-342`). Its failure is a registrar failure and denies `fabrik apply` its green (`src/fabrik/cli.py:531-545`) → T04.
- The scaffolder vendors the module, folds the table with its same-transaction revokes, replaces the stdout stub, and schedules retention plus a weekly verify through the saas beat loop or a jobs companion (spec § 3 → T05).
- The operator delegated both the DSN decision and the design gate ("figure out yourself"; "i cant tell"), then said "go" at the design gate (D-389).
- The operator also delegated the choices this plan settles (D-390): the flag's name and home, the scan patterns, the cutover resetting the app password rather than storing a staging key, and "Python type with a database" as the scaffolder's trigger.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § 1 — the non-owner role, grants, ownership re-assertion, revokes, group memberships, watchdog revoke | IN | T02 |
| I2 | spec § 1 "Where it runs" — its own registrar step, a failure denies success | IN | T04 |
| I3 | spec § 2 — `DATABASE_URL` / `DATABASE_URL_OWNER`, new vs existing, rollback, third-party images | IN | T01 (flag), T04 (injection + cutover + rollback) |
| I4 | spec § 2 — the measured pre-cutover check (ownership, probe, repo scan) | IN | T03 |
| I5 | spec § 3 — vendoring, schema fold with revokes, stub replaced, jobs, Node table, backend-less types | IN | T05 |
| I6 | spec § Open unknowns — "the cutover flag's field name and the exact patterns of the pre-cutover code scan — settled in `/fabrik-plan-after-chat`" | IN | T01 (`shape.database_url_app_role`), T03 (the pattern table) |
| I7 | spec § Cost — "its size is the plan's to set" (the jobs companion memory) | IN | T05 (measured in the ticket, § Residual unknowns) |
| I8 | spec § Open unknowns — inventory fabrik-smoke-test, test-saas-log, translator before the waves | OUT-OF-SCOPE — a waves-plan input, not a hub build step | § Residual unknowns |
| I9 | spec § 4 — pilot plus waves, one mail per repo | OUT-OF-SCOPE — a follow-up plan opened after this one executes; the hub side comes first (the brief) | § Residual unknowns |
| I10 | spec § Documentation landing sites — the registrar role model in the existing Postgres registrar doc, CONFIGURATION, the scaffold doc templates | IN | T04 (drivers.md, fabrik-lifecycle.md), T05 (CONFIGURATION.md, the templates) |
| I11 | spec I8/I9 — the fabrik-lib module changes (01M37RT50) and the pack's owner-role caveats | OUT-OF-SCOPE — fabrik-lib and infra; infra is mailed at Finish (T05) | T05 receipt |
| I12 | the grounding seats' two scaffold bugs: the python-api `--db` `.env.example` replace is a no-op (`src/fabrik/scaffold.py:1975-1977`); the saas family ships no `DATABASE_URL` in `.env.example` | IN | T05 |
| I13 | "DATABASE_URL_OWNER in the shared project `.env`" means append-only holds against the app's own code paths and SQL injection, not against code execution in the container | OUT-OF-SCOPE — stated as a limit in the docs T04 writes; backlog row for a migrate-only env file | T04 Docs, STRATEGIC_BACKLOG (Deltas) |

Intake: 13 items — 9 IN, 4 OUT-OF-SCOPE (I8, I9, I11, I13 — each named), 0 ASK.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | `shape.database_url_app_role` flag + generator default | — | ⚡ | ⬜ | |
| T02 | `<db>_app` role driver: mint, grants, audit revokes, probe, drop | — | ⚡ | ⬜ | |
| T03 | Pre-cutover check + `fabrik app-role-check` | T02 | ⛓️ | ⬜ | |
| T04 | Registrar step: DSN injection, cutover, rollback, docs | T01, T02, T03 | ⛓️ | ⬜ | |
| T05 | Integration: scaffolder emits module, table, revokes, jobs; receipt | T04 | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T02
3. T03
4. T04
5. T05

## Interfaces

- **T02 → T03, T04 (`src/fabrik/drivers/postgres.py`):**
  - `app_role_name(db_name: str) -> str` returns `f"{db_name}_app"`, validated by `_validate_identifier`, with the payments role's 63-character guard.
  - `ensure_app_role(db_name: str, owner: str, container: str = POSTGRES_CONTAINER, dry_run: bool = False, reset_password: bool = False) -> dict` returns `{"user": str, "password": str | None, "status": "created" | "exists" | "reset" | "dry_run"}`. A password is returned only on `created` or `reset`. Every call re-applies the grants, default privileges, `audit_log` ownership and revokes, the watchdog revoke and the group memberships.
  - `probe_app_role(db_name: str, owner: str, container: str = POSTGRES_CONTAINER) -> list[str]` returns one human-readable failure per violated property; empty means pass.
  - Seam tests:
    - `tests/test_app_role_check.py::test_check_uses_driver_probe` (T03, consumer): asserts `run_check` calls `probe_app_role` and carries its failures verbatim.
    - `tests/test_app_role_provision.py` (T04, consumer): asserts the step calls `ensure_app_role` with the owner name and `reset_password` exactly at a cutover.
- **T03 → T04 (`src/fabrik/app_role_check.py`):**
  - `run_check(db_name: str, owner: str, repo_dir: Path, container: str = POSTGRES_CONTAINER) -> CheckResult`, where `CheckResult(ok: bool, failures: list[str])`.
  - A missing `repo_dir` is a failure (`"no repo at <path> — cannot scan"`), never a pass.
  - Seam test: `tests/test_app_role_provision.py::test_cutover_refused_when_check_fails` (T04, consumer).
- **T02 → T05 (test helper):** `tests/test_app_role_real_pg.py::scratch_pg()`, a context manager that starts a throwaway `postgres:16` container and yields a `run_sql(sql: str) -> str` bound to it. It skips with its reason when docker is unavailable. Seam test: `tests/test_scaffold_audit_log.py::test_schema_has_no_default_privilege_window` (T05, consumer) imports it.
- **T01 → T04:** `Shape.database_url_app_role: bool = False`, which requires `needs_database` (a validator mirroring `_payments_ingest_needs_database`, `src/fabrik/spec_loader.py:380-389`). The step reads it through `spec["shape"]`. Seam test: `tests/test_app_role_provision.py::test_flag_false_fresh_create_injects_owner_in_both` (T04, consumer).
- **T01 → T05:** `generate_spec(..., use_database=True)` emits `shape.database_url_app_role: true`, so every newly scaffolded database project is born on the app role. Seam test: `tests/test_scaffold_audit_log.py::test_scaffolded_spec_carries_app_role_flag` (T05, consumer).
- **T04 → T05 (the env contract):** a fresh create injects `DATABASE_URL` (the app DSN when the flag is true) and `DATABASE_URL_OWNER` (always the owner DSN), both with scheme `postgresql://`, host `postgres-main:5432`, rewritten for spokes by `_rewrite_shared_infra_host`. The scaffolder's schema header, jobs and `.env.example` name exactly these two variables. Seam test: `tests/test_scaffold_audit_log.py::test_env_example_names_both_dsns` (T05, consumer).

## Behavior Contract

- **Given** a spec with `shape.database_url_app_role: true` and `needs_database: false`, **When** it is loaded, **Then** validation fails naming `database_url_app_role requires needs_database: true` (src/fabrik/spec_loader.py:380; spec-fed: `spec § 2`)
- **Given** a spec with no `database_url_app_role` key, **When** it is loaded, **Then** the field is `False` — an existing spec is never switched by an upgrade (src/fabrik/spec_loader.py:333)
- **Given** `generate_spec` for a type whose defaults set `needs_database`, or any type with `use_database=True`, **When** the spec is emitted, **Then** `shape.database_url_app_role` is `true`; a spec without a database carries `false` (src/fabrik/spec_generator.py:381)
- **Given** `ensure_app_role` against a fake `_run_sql` on a role that does not exist, **When** it runs, **Then** the SQL batch mints `"<db>_app" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS` with a 32-character `[a-zA-Z0-9]` password, grants `CONNECT` and `USAGE ON SCHEMA public` and never `CREATE`, grants DML on all tables and `USAGE, SELECT` on all sequences, and sets `ALTER DEFAULT PRIVILEGES FOR ROLE "<owner>"` for both; it returns `status="created"` with the password (src/fabrik/drivers/postgres.py:829; spec-fed: `spec § 1`)
- **Given** the role already exists, **When** `ensure_app_role` runs again with `reset_password=False`, **Then** no `CREATE ROLE` and no `PASSWORD` appear in the batch, the grants are re-applied, and it returns `status="exists"` with `password=None`; with `reset_password=True` it issues `ALTER ROLE ... PASSWORD` and returns `status="reset"` with the new password (src/fabrik/drivers/postgres.py:561)
- **Given** any `ensure_app_role` batch, **When** it is inspected, **Then** it carries a `to_regclass('public.audit_log')`-guarded DO block that re-asserts `ALTER TABLE audit_log OWNER TO "<owner>"` when the owner differs, revokes `UPDATE, DELETE, TRUNCATE` from `"<db>_app"`, from `"<db>_wd_rw"` when that role exists and from each of `anon`/`authenticated`/`service_role` that exists, grants `INSERT, SELECT` to `"<db>_app"`, and grants each existing group role the owner is a member of to `"<db>_app"` `WITH INHERIT FALSE, SET TRUE` (src/fabrik/drivers/postgres.py:803)
- **Given** a scratch PostgreSQL 16 container with an owner, the audit table created by the owner and the watchdog roles minted, **When** `ensure_app_role` runs and a session `SET ROLE "<db>_app"` tries each statement, **Then** `INSERT`/`SELECT` on `audit_log` succeed and `UPDATE`, `DELETE`, `TRUNCATE` fail with a permission error, the same three fail as `"<db>_wd_rw"`, and the test goes red when the revoke line is removed (src/fabrik/drivers/postgres.py:612; spec-fed: `spec § Validation`)
- **Given** `drop_database` for a database whose app role exists, or an orphan app role whose database is gone, **When** it runs, **Then** `DROP ROLE IF EXISTS "<db>_app"` is in the batch after the database drop (src/fabrik/drivers/postgres.py:1080)
- **Given** a fake `_run_sql` whose ownership query returns one table owned by `<db>_app` and whose privilege query reports `UPDATE` on `audit_log` for `authenticated`, **When** `probe_app_role` runs, **Then** it returns two failures naming the table and the role, and an all-clear fake returns `[]` (src/fabrik/drivers/postgres.py:572)
- **Given** a scratch repo holding `app/db.py` with `CREATE TABLE`, an `alembic.ini`, a compose `migrate` service running `alembic upgrade head`, and an entrypoint running `psql "$DATABASE_URL"`, **When** `scan_repo` runs, **Then** it returns one finding per file with path, line and pattern, and ignores the same text under `tests/`, `.venv/`, `node_modules/` and `libs/` (src/fabrik/app_role_check.py:1; spec-fed: `spec § Derivations D1`)
- **Given** the same repo after every DDL and migration site reads `DATABASE_URL_OWNER` (the finding line or its compose service names `DATABASE_URL_OWNER`), **When** `scan_repo` runs, **Then** it returns `[]` (src/fabrik/app_role_check.py:1)
- **Given** `run_check` with a passing probe but a repo dir that does not exist, **When** it runs, **Then** `ok` is `False` and the failures name the missing repo; with a failing probe and a clean repo, the probe's failures are carried verbatim (tests/test_app_role_check.py:1)
- **Given** `fabrik app-role-check --spec specs/services/<id>.yaml` with the check monkeypatched to fail, **When** the CLI runs, **Then** it prints one `✗` line per failure and exits 1; a passing check prints `✓` and exits 0 (src/fabrik/cli.py:1370)
- **Given** a fresh create with `database_url_app_role: true`, **When** `_provision_postgres` runs with fakes, **Then** `inject_env` receives `DATABASE_URL` whose user is `<db>_app` and `DATABASE_URL_OWNER` whose user is the owner, in one call (src/fabrik/orchestrator/infrastructure.py:633; spec-fed: `spec § 2`)
- **Given** a fresh create with the flag `false`, **When** the step runs, **Then** both `DATABASE_URL` and `DATABASE_URL_OWNER` carry the owner DSN, and the app role is still minted (src/fabrik/orchestrator/infrastructure.py:638)
- **Given** an existing database, the flag `true`, and a remote `.env` whose `DATABASE_URL` user is the owner, **When** the step runs with a passing check, **Then** `ensure_app_role(reset_password=True)` is called and `inject_env` receives `DATABASE_URL`=app DSN and `DATABASE_URL_OWNER`=the old `DATABASE_URL` value; with a failing check nothing is injected and `ctx.registrar_failures` gains one `app-role:` entry naming each failure (src/fabrik/orchestrator/infrastructure.py:426)
- **Given** an existing database, the flag `false`, and a remote `.env` whose `DATABASE_URL` user is `<db>_app`, **When** the step runs, **Then** `inject_env` receives `DATABASE_URL`=the `DATABASE_URL_OWNER` value; when `DATABASE_URL_OWNER` is absent it injects nothing and records a registrar failure (src/fabrik/orchestrator/infrastructure.py:701)
- **Given** a re-apply where the flag matches the current `DATABASE_URL` user, **When** the step runs, **Then** no password is reset and `inject_env` is not called — only the grants are re-applied (src/fabrik/drivers/postgres.py:340)
- **Given** `ensure_app_role` raising, **When** the step runs, **Then** the failure lands on `ctx.registrar_failures` via `_nonfatal` and the CLI exits 2 (src/fabrik/cli.py:531)
- **Given** `SSHDeployer.read_env(ctx)` against a fake `_ssh` returning a `.env` body, **When** it runs, **Then** it returns the parsed dict, returns `{}` when the file is absent, and `inject_env` still merges exactly as before (src/fabrik/orchestrator/deployer_ssh.py:258)
- **Given** each Python-backed scaffold type (saas-skeleton, python-api, python-api-gpu, and the `server/` of office-extension, chrome-extension, mobile-app and static-site) emitted into a scratch dir with a database, **When** the tree is inspected, **Then** every Python backend has `libs/audit_log/` (or `server/libs/audit_log/`) vendored, its schema file carries the `audit_log` table and the guarded revokes naming `<db>_app`, `<db>_wd_rw` and the group roles, its header says `psql "$DATABASE_URL_OWNER"`, the stdout `_LogAuditLogger` is gone, retention and weekly verify are scheduled, and `.env.example` names `DATABASE_URL` and `DATABASE_URL_OWNER` (src/fabrik/scaffold.py:2111; spec-fed: `spec § 3`)
- **Given** node-api and file-api with a database, **When** emitted, **Then** the schema carries the table and revokes and no Python module; desktop-app and docusaurus emit neither; file-worker without a database emits neither (src/fabrik/scaffold.py:1484)
- **Given** a scaffolded python-api `--db` project, **When** its compose is read, **Then** a `jobs` companion service shares the app image, overrides `command`, `container_name` and `deploy.resources.limits.memory`, and sets `DATABASE_URL=${DATABASE_URL_OWNER}` in its own `environment` (src/fabrik/scaffold.py:902)
- **Given** the emitted schema applied to a scratch PostgreSQL 16 as the owner in one transaction, with the app role minted, **When** the app role tries `UPDATE` on `audit_log` immediately after, **Then** it is refused — no default-privilege window (src/fabrik/scaffold.py:2111; spec-fed: `spec § 1 No window`)

## Global Constraints

- **Shared tree with three hub sessions:**
  - Every commit is a pathspec or private-index commit of explicitly named paths; never `git add -A`, `--amend` or stash.
  - Fetch and fast-forward before push; never `--force`.
  - `CHANGELOG.md`, `INDEX.md`, `docs/DECISIONS.md` and `docs/STRATEGIC_BACKLOG.md` go only through the private-index recipe, with the step-4 assertion gating and the step-7 carry.
- **Never print a secret.** Tests assert on the SHAPE of a DSN (user, host, scheme), never a real password. Log lines name the role, never the DSN. A password in SQL is passed only inside `_run_sql`'s stdin, as the payments role does.
- **No new dependency in the hub.** Stdlib plus what `src/fabrik` already imports. The scaffolded projects' `requirements.txt` gains `psycopg[binary]`, which is scaffold output, not the hub's deps file.
- **Idempotent on every apply.** Every role and `audit_log` statement is guarded: role existence via `pg_roles`, table existence via `to_regclass`. A second apply changes no password unless a cutover or rollback is in progress.
- **Fail closed.** A missing repo, missing `DATABASE_URL_OWNER` or failing probe refuses the switch and records a registrar failure; it never silently skips.
- **Third-party images are never switched.** The check's missing-repo failure enforces this; nothing special-cases them by name.
- **Datetimes:** `datetime.now(UTC)`, never `utcnow()` (core/10-python.md:219).
- **Tests:** every test is watched RED first. The real-PG tests are proven red-on-revert, the mutation made in a throwaway worktree, never the shared checkout.
- Never-Route: src/fabrik/drivers/postgres.py
- Never-Route: src/fabrik/orchestrator/infrastructure.py
- **12-Factor non-negotiables (binding on every ticket):**
  - Logs go unbuffered to stdout only, never a logfile (XI).
  - Migrations run as a one-off process against the deployed release, never from `lifespan`/startup (XII). The jobs companion runs retention and verify on a schedule; it never applies schema.
  - The same backing services in dev, test and prod.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/app-audit-log.md` | the five-point "properly" list (:22-45); the per-type rules (:50-55); one writer under `pg_advisory_xact_lock`, no table privilege needed (:200-213); the async recipe (:215-222) | § Constraints digest |
| `.windsurf/rules/core/25-data-postgres.md` (FLOOR) | the `DATABASE_URL_DIRECT` naming precedent (:254); Settings, never a raw getenv (:331) | § Constraints digest |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | DSNs have no fallback (:273); 32-char `[a-zA-Z0-9]` passwords (:321); Pattern A group roles (:91) | § Constraints digest |
| `.windsurf/rules/core/30-ops.md` (FLOOR) | a companion shares the app env and overrides only command/name/memory (:161); registrar fix-ups, never manual edits (:420); the migrate service reads the same env (:444-445) | § Constraints digest |
| `.windsurf/rules/core/10-python.md` | apps read a complete `DATABASE_URL` (:133); `datetime.now(UTC)` (:219); `uv`, no new dependency (:21) | § Constraints digest |
| `.windsurf/rules/core/45-testing-strategy.md` | one test per user-observable behaviour, red-first | every Behavior Contract |
| fabrik-lib | VENDOR `app-audit-log` as-is: `record_event` (audit_log.py:116), `verify_chain` (:264), `schema.sql`, `data_retention.sql`. The async writer and retention end dates are fabrik-lib's (01M37RT50). BUILD the role, grants, DSN and cutover in the hub, since no module provisions roles | /opt/fabrik-lib/app-audit-log/README.md |
| `agents-fabrik.md` invariants | `postgres-main:5432`, never localhost; `deploy.resources.limits.memory` on every compose service, the jobs companion included | § Global Constraints |
| `specs/services/*.yaml` `shape:` | the new `database_url_app_role` field (T01). No existing spec is edited by this plan; the waves flip them one at a time | spec § Shape and infra implications |
| `docs/data-contract.md` / `docs/ui-design.md` | absent in the hub. Each project re-freezes its own during its wave (spec § Contract deltas) | — |
| `src/fabrik/drivers/postgres.py` | `_generate_password` (:106); `_run_sql` (:111); `create_database` (:289), early return (:340-342), role (:393-400), owner (:409); `_role_exists` (:561); `_db_owner` (:572); `create_watchdog_roles` (:612), rw default grants (:710-730); `_payments_ingest_policy_block` (:803); `create_payments_ingest_role` (:829); `drop_database` (:1018), orphan drops (:1080-1086), main drops (:1103-1106) | read this run |
| `src/fabrik/orchestrator/infrastructure.py` | `resolve_applicability` (:196); `_nonfatal` (:426-436); `provision` (:447); `_provision_postgres` (:561), db name (:574-580), `DATABASE_URL` injection (:633-644), payments step (:695-733) | read this run |
| `src/fabrik/orchestrator/deployer_ssh.py` | `inject_env` reads the remote `.env` inline (:258-296); `_parse_env` (:720); `_format_env` (:745) | read this run |
| `src/fabrik/spec_loader.py` / `spec_generator.py` | `Shape` (:205); `needs_payments_ingest` (:333-345); its validator (:380-389); the `use_database` overlay (:381-382) | read this run |
| `src/fabrik/cli.py` | the `registrar_failures` exit 2 (:531-545); `audit-registrars` as the sibling command shape (:1370) | read this run |
| `src/fabrik/scaffold.py` | `_write_canonical_compose` (:902); placeholder `db/schema.sql` (:1484); python-api `--db` `.env.example` no-op replace (:1971-1977); `_SAAS_SCHEMA_SQL` (:2111), header (:2113); `_LogAuditLogger` (:2476) used at (:2498); `_SAAS_WORKER_PY` beat loop (:2589, :2773-2804); `_write_saas_compose` (:3070); `_vendor_fastapi_user_auth` (:3290) — 280 KB, over the per-ticket budget → Integration hatch | read this run |
| `src/fabrik/drivers/watchdog.py` | `_PROJECTS_ROOT = Path("/opt")` (:247), the repo-root precedent for T03 | read this run |

## Constraints digest

| Pack | Row (verbatim) | Applies to |
|---|---|---|
| .windsurf/rules/core/app-audit-log.md:40 | "4. **Retention scheduled** — `data_retention.sql` from the project's scheduler, as the owner role" | T05 retention runs on `DATABASE_URL_OWNER` |
| .windsurf/rules/core/app-audit-log.md:203 | "takes `pg_advisory_xact_lock(AUDIT_CHAIN_LOCK_KEY)` in the SAME transaction as the write — every writer," | T05 writer; T02 grants no `UPDATE` to the app |
| .windsurf/rules/core/10-python.md:133 | "**Config convention:** apps read a complete `DATABASE_URL`" | T04 keeps the app on `DATABASE_URL` |
| .windsurf/rules/core/25-data-postgres.md:254 | "must connect directly to `postgres-main:5432` via a separate `DATABASE_URL_DIRECT` env var" | T04 names `DATABASE_URL_OWNER` on this precedent |
| .windsurf/rules/core/30-ops.md:161 | "the scaffolder emits a 2nd compose service that shares the app's build/image + env + `DATABASE_URL`/`REDIS_URL`, overriding only `command` + `container_name` + `memory`." | T05 jobs companion overrides `DATABASE_URL` too, and says why |
| .windsurf/rules/core/30-ops.md:420 | "\| Manual VPS edits / registrar fix-ups \| `fabrik apply` / `reconcile-all` (spec-driven) \|" | T04 — the revokes and the cutover are registrar work |
| .windsurf/rules/core/35-security-auth.md:273 | "# DSNs and secrets get NO fallback — a missing value fails LOUDLY at boot" | T05 — neither DSN has a default in emitted code |
| .windsurf/rules/core/35-security-auth.md:321 | "- **32 characters**, charset `[a-zA-Z0-9]` only (no symbols — survives `.env` round-trip + shell quoting)." | T02 app-role password |
| .windsurf/rules/core/10-python.md:219 | "**`datetime.now(UTC)`, never `datetime.utcnow()`**" | T05 jobs cursor timestamps |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor.** Every ticket, on the coder's return, runs `/fabrik-review` on its changed surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green. T02 and T04 touch auth, schema and the registrar (heavy surfaces), so their review carries an Opus authoritative seat.
- **Dispatch policy.**
  - Native Claude seats for every fan-out, because the pool is OFF (D-181).
  - T01 is `simple` and gets a native Sonnet coder.
  - T02 and T04 are `never-route` (their Touches are in `## Global Constraints` Never-Route) and get `claude -p opus`: auth, schema and concurrency-shaped SQL.
  - T03 is `complex` and gets a native Sonnet coder.
  - T05 is `native` (Integration, owns `scaffold.py`) and gets Opus.
  - The Opus seat does the decide/merge in every review.
- **Parallelism + merge.**
  - T01 and T02 fan out concurrently in Phase 1: their Touches are disjoint.
  - T03 follows T02 (it consumes `probe_app_role`).
  - T04 follows T01, T02 and T03.
  - T05 runs last.
  - Results merge in the main checkout by the merge owner (this fleet session) in Merge Order: one `--no-ff` merge per ticket after its review, with the tests of the merged result run before the next dispatch.

## File Scope (owned paths)

- src/fabrik/spec_loader.py
- src/fabrik/spec_generator.py
- tests/test_spec_loader.py
- tests/test_spec_generator.py
- src/fabrik/drivers/postgres.py
- tests/test_app_role_driver.py
- tests/test_app_role_real_pg.py
- src/fabrik/app_role_check.py
- tests/test_app_role_check.py
- src/fabrik/cli.py
- src/fabrik/orchestrator/infrastructure.py
- src/fabrik/orchestrator/deployer_ssh.py
- tests/test_app_role_provision.py
- tests/orchestrator/test_deployer_ssh.py
- docs/operations/fabrik-lifecycle.md
- docs/CONFIGURATION.md
- docs/reference/modules/drivers.md
- docs/QUICKSTART.md
- src/fabrik/scaffold.py
- templates/scaffold/docs/CONFIGURATION_TEMPLATE.md
- templates/scaffold/docs/OPERATIONS_TEMPLATE.md
- templates/scaffold/docs/RESILIENCE_TEMPLATE.md
- templates/saas-skeleton/.env.example
- templates/mobile-app/.env.example
- templates/node-api/.env.example
- tests/test_scaffold_audit_log.py
- tests/test_scaffold_saas_backend.py
- docs/development/reviews/2026-09-24-plan-1-audit-log-everywhere-review.md

## Evidence

- `src/fabrik/spec_loader.py:333-345` — `needs_payments_ingest: bool = Field(default=False, …)` and the `_payments_ingest_needs_database` validator (:380-389), the exact shape T01 copies.
- `src/fabrik/drivers/postgres.py:340-342` — `create_database` returns before any role SQL once the database exists, so T04's step is its own call. `:409` `ALTER DATABASE "{db_name}" OWNER TO "{db_user}"` makes the app the owner today. `:710-730` gives the watchdog rw role DML plus default privileges `FOR ROLE <owner>`. `:803-826` is the `to_regclass`-guarded DO-block idiom T02 reuses.
- `src/fabrik/app_role_check.py` — new (T03). Its patterns come from spec § Derivations D1 (`CREATE TABLE|ALTER TABLE|CREATE EXTENSION|CREATE INDEX` outside migrations, tests and vendored dirs), widened by spec § 2 to `alembic`, `prisma migrate`, `psql`, and compose `migrate` services or entrypoints.
- `src/fabrik/orchestrator/infrastructure.py:633-644` — `DATABASE_URL` is injected only when `create_database` returns a password. `:426-436` shows `_nonfatal` appends to `ctx.registrar_failures`, which `src/fabrik/cli.py:531-545` turns into exit 2.
- `src/fabrik/orchestrator/deployer_ssh.py:280-289` — the remote `.env` read is inline in `inject_env`. T04 extracts it as `read_env` with no behaviour change to the merge.
- `src/fabrik/scaffold.py:2113` — `-- Apply once after the DB is provisioned:  psql "$DATABASE_URL" -f db/schema.sql`. `:2476` `class _LogAuditLogger` is the stdout stub T05 replaces. `:1975-1977` is the python-api `.env.example` replace whose search string does not occur, so it is a no-op.
- The live fleet has 22 database specs: 17 with a repo on this box and 5 without. Of the 17, 8 carry DDL in app code (spec § Derivations D0 and D1, re-derived in the spec's review). No existing spec carries the new flag, so this plan switches nothing live.

```text
$ wc -c src/fabrik/drivers/postgres.py src/fabrik/orchestrator/infrastructure.py src/fabrik/scaffold.py src/fabrik/spec_loader.py src/fabrik/cli.py src/fabrik/orchestrator/deployer_ssh.py
 72045 src/fabrik/drivers/postgres.py
 53495 src/fabrik/orchestrator/infrastructure.py
280715 src/fabrik/scaffold.py
 42399 src/fabrik/spec_loader.py
140312 src/fabrik/cli.py
 44930 src/fabrik/orchestrator/deployer_ssh.py
$ timeout 10 docker images postgres --format '{{.Repository}}:{{.Tag}}'
postgres:14
postgres:18
postgres:15-alpine
$ command grep -c 'database_url_app_role' specs/services/*.yaml | command grep -vc ':0$'
0
```

## Self-audit

- **Grounding passes.** Every `path:line` above was opened this run or re-derived by the grounding seats. The cross-checks include `create_database`'s early return, `_nonfatal`, the CLI exit 2, `inject_env`'s inline read, the payments validator, the `use_database` overlay, the scaffold stub and header, the `.env.example` no-op and `_PROJECTS_ROOT`.
- **(a) Coverage:**
  - role, grants and revokes → T02;
  - its own step and failure-denies-success → T04;
  - DSN contract, new vs existing, and rollback → T01 + T04;
  - measured check → T03;
  - scaffolder → T05;
  - the two scaffold bugs → T05;
  - docs → T04 (drivers.md, lifecycle) + T05 (CONFIGURATION.md, templates);
  - the security limit of a shared `.env` → T04 Docs + backlog.
- **(b) Cross-ticket signatures:**
  - `ensure_app_role` / `probe_app_role` are produced by T02 and consumed by T03 and T04. The signatures are identical in `## Interfaces`, the T02 Behavior Contract and the T03/T04 Context Files.
  - `run_check` is produced by T03 and consumed by T04.
  - `database_url_app_role` is produced by T01 and consumed by T04 and T05.
  - The two-variable env contract is produced by T04 and consumed by T05.
- **Sizing:** the emit gate's summary line is recorded in § Residual unknowns. `scaffold.py` (280 KB) sits in the Integration ticket by the READ-budget hatch.
- **Fixed point:** pending — `/fabrik-plan-review` converges it.

## Coverage Checklist

Rubric over the touched surfaces (`python scripts/review_rubric.py --changed src/fabrik/drivers/postgres.py src/fabrik/orchestrator/infrastructure.py src/fabrik/scaffold.py src/fabrik/app_role_check.py`) — run at each ticket's review; the classes below are the standing ones.

| Class | Status |
|---|---|
| core/25-data-postgres.md + core/35-security-auth.md (FLOOR) — roles, grants, DSNs, passwords | OPEN — T02/T04 Behavior Contracts; the real-PG test is the proof |
| core/30-ops.md (FLOOR) — companion memory limit, registrar-only fix-ups | OPEN — T05 compose row; T04 |
| core/app-audit-log.md — five points per type | OPEN — T05 per-type rows |
| Recurrence: bounded-count claims without denominators | OPEN — the 22/17/5 and 8-of-17 counts cite spec § Derivations |
| Recurrence: proxy-as-evidence (a SQL string grep standing in for a privilege test) | OPEN — T02 and T05 each carry a real-PG row, red-on-revert |
| Recurrence: fleet blast radius | OPEN — no existing spec switches; the flag defaults false |
| Recurrence: idempotency claimed, not asserted | OPEN — T02/T04 second-run rows |

## Residual unknowns

- **Resolved (emit gate):** `python -m scripts.enforcement.check_plan_tickets --plan-dir docs/development/plans/2026-09-24-plan-1-audit-log-everywhere` → `graded 5 ticket(s), 28 Touches path(s), 35 Context-Files entry(ies); READ budget measured against /opt/fabrik; 0 finding(s)`. The first run found T04 at 276,215 B against 262,144, so `docs/CONFIGURATION.md` (57,582 B) moved to T05.
- **Open (self-service, T05): the jobs companion's memory limit.** Measure the peak RSS of `python -m <pkg>.audit_jobs` running one retention and one verify pass over 10k rows in a scratch container. Set the limit to 2× peak, floor 128M, and record the measurement in the receipt.
- **Open (self-service, T02/T05): the scratch PostgreSQL for the real-PG rows.** `postgres-main` runs 16. `postgres:16` is not in the local image list (`postgres:14`, `postgres:18`, `postgres:15-alpine`), so the fixture pulls `postgres:16` and skips with its reason when docker is unavailable. A skip is never counted as the red-on-revert proof.
- **Follow-up plan, not this one: the migration waves.** After T05 merges, a waves plan pilots one low-risk database project, then mails one repo at a time. It inventories fabrik-smoke-test, test-saas-log and translator (no repo on this box, no third-party image) first, and measures each project's Pattern A group-role membership.
- **Routed at Finish (T05 receipt):**
  - infra is mailed that the pack's owner-role caveats (`core/app-audit-log.md:26-36`, `:40-41`) are stale once T04 ships;
  - fabrik-lib already holds 01M37RT50.
- **Stated limit (T04 docs + backlog):** `DATABASE_URL_OWNER` lives in the same project `.env` the app reads. Append-only therefore holds against the app's code paths and SQL injection, not against code execution in the container. A migrate-only env file is the backlog row.
