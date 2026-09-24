# The audit log in every Fabrik project — non-owner app role, DSN contract, pre-cutover check, scaffolder

Status: CONVERGED (/fabrik-plan-review 2026-09-24 — 4 passes, confirmed 48 → 9 → 1 → 0; scope-growth stop at pass 3, remainder round quiet)
**Owner:** fleet
Spec: docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md (CONVERGED 799b1434a, D-387; approved D-389; design D-385 as corrected by D-386; mandate D-368)

## Goal

Every `needs_database` project gets a non-owning `<db>_app` login role from the registrar, against which `audit_log` is append-only (no `UPDATE`/`DELETE`/`TRUNCATE` for the app, the watchdog rw role or the Pattern A group roles). New projects are born connecting as that role, with the owner DSN in `DATABASE_URL_OWNER` and the module, table, revokes and jobs emitted by the scaffolder. Existing projects switch one at a time behind a spec flag, and only after a measured pre-cutover check passes. This plan builds the hub side. The per-project migration waves are a follow-up plan (§ Residual unknowns).

## What we already agreed (from the spec + this conversation)

- A second, non-owning app role per project; the owner is kept for schema changes and retention (mail 01M37SPA; spec § 1 → T02, T04).
- `USAGE` on the owner's schemas, never `CREATE`; `audit_log` ownership is re-asserted by the registrar, which runs as the superuser; the audit revokes go to the app role, `<db>_wd_rw`, PUBLIC and every Pattern A group role; group memberships are the three Pattern A roles only, `WITH INHERIT FALSE, SET TRUE` (D-386 → T02). This review added PUBLIC's `CREATE` on `public` to the revokes, and real-owner resolution through `_db_owner`.
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

Serialized: src/fabrik/spec_generator.py — T01, T05

## Interfaces

- **T02 → T03, T04 (`src/fabrik/drivers/postgres.py`):**
  - `POSTGRES_CONTAINER` — the existing container-name constant every driver function defaults to; import it, never restate it.
  - `class AppRoleError(RuntimeError)` — raised when the database's owner (`_db_owner`) is `None` or `postgres`, before any SQL.
  - `app_role_name(db_name: str) -> str` returns `f"{db_name}_app"`, validated by `_validate_identifier`, with the payments role's 63-character guard.
  - `ensure_app_role(db_name: str, container: str = POSTGRES_CONTAINER, dry_run: bool = False, reset_password: bool = False) -> dict` returns `{"user": str, "owner": str, "password": str | None, "status": "created" | "exists" | "reset" | "dry_run"}`. A password is returned only on `created` or `reset`. Every call re-applies the grants, default privileges, `audit_log` ownership and revokes, the PUBLIC `CREATE` revoke and the three group memberships.
  - `probe_app_role(db_name: str, container: str = POSTGRES_CONTAINER) -> list[str]` returns one failure string per violated property; empty means pass.
  - Seam tests:
    - `tests/test_app_role_check.py` (T03, consumer): `run_check` calls `probe_app_role`, carries its failures verbatim and turns `AppRoleError` into a failure.
    - `tests/test_app_role_provision.py` (T04, consumer): the step calls `ensure_app_role` on every apply, with `reset_password=True` only at a cutover, after the watchdog and payments steps.
- **T02 → T05 (test helper):** `tests/test_app_role_real_pg.py::scratch_pg()`, a context manager that starts a throwaway `postgres:16` container and yields `run_sql(sql: str) -> str` (superuser) plus `login_sql(role: str, password: str, sql: str) -> str` (a real LOGIN session). It skips with its reason when docker is unavailable. Seam test: T05's no-window row in `tests/test_scaffold_audit_log.py` imports it.
- **T03 → T04 (`src/fabrik/app_role_check.py`):**
  - `run_check(db_name: str, repo_dir: Path, container: str = POSTGRES_CONTAINER) -> CheckResult`, where `CheckResult(ok: bool, failures: list[str])`.
  - `project_repo_dir(spec: dict) -> Path` returns `Path("/opt") / (spec.get("id") or spec.get("name"))` — the orchestrator's `_load_secrets` precedence. The CLI and the registrar step use this one helper.
  - A missing repo, zero scanned files or a stale clone is a failure, never a pass.
  - Seam test: `tests/test_app_role_provision.py` (T04, consumer) — a failing `run_check` injects nothing.
- **T01 → T04:** `Shape.database_url_app_role: bool = False`, requiring `needs_database` (validator mirroring `_payments_ingest_needs_database`, `src/fabrik/spec_loader.py:380-389`). The step reads the RAW dict — `(spec.get("shape") or {}).get("database_url_app_role", False)` — because `ctx.spec` never passes through `Shape`. Seam test: `tests/test_app_role_provision.py` (T04, consumer), the missing-key row.
- **T01 → T05:** `generate_spec(..., use_database=True)` emits `shape.database_url_app_role: true` for every enabled type. Seam test: `tests/test_scaffold_audit_log.py` (T05, consumer) asserts a scaffolded database project's spec carries it.
- **T04 → T05 (the env contract):** every database project's `.env` carries `DATABASE_URL` and `DATABASE_URL_OWNER`. On a fresh create both are the owner DSN (scheme `postgresql://`, host `postgres-main:5432`, rewritten for spokes by `_rewrite_shared_infra_host`) until the declarative step cuts `DATABASE_URL` over to `<db>_app` by swapping only user and password. The scaffolder's schema header, jobs and `.env.example` name exactly these two variables. Seam test: `tests/test_scaffold_audit_log.py` (T05, consumer), the `.env.example` assertion in the per-type row.

## Behavior Contract

- **Given** a spec with `shape.database_url_app_role: true` and `needs_database: false`, **When** it is loaded, **Then** validation fails naming `database_url_app_role requires needs_database: true` (src/fabrik/spec_loader.py:380; spec-fed: `spec § 2`)
- **Given** a spec with no `database_url_app_role` key, **When** it is loaded, **Then** the field is `False` — an existing spec is never switched by an upgrade (src/fabrik/spec_loader.py:333)
- **Given** `generate_spec` for a type whose defaults set `needs_database`, or any type with `use_database=True`, **When** the spec is emitted, **Then** `shape.database_url_app_role` is `true`; a spec without a database carries `false` (src/fabrik/spec_generator.py:381)
- **Given** every type in `SPEC_ENABLED_TYPES`, **When** `generate_spec(type, use_database=True)` runs, **Then** the emitted shape is not `None` and carries `database_url_app_role: true` — a type whose `templates/<type>/defaults.yaml` has no `shape:` block fails this test instead of silently shipping an owner DSN (src/fabrik/spec_generator.py:381)
- **Given** a fake `_run_sql` where `_db_owner` returns `<db>` and the app role does not exist, **When** `ensure_app_role` runs, **Then** `CREATE ROLE "<db>_app" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS` with a 32-character `[a-zA-Z0-9]` password runs in its own `_run_sql` call; the grants batch that follows opens with `\c <db>`; it grants `CONNECT` and `USAGE` (never `CREATE`) on each owner schema, DML on its tables, `USAGE, SELECT` on its sequences, and `ALTER DEFAULT PRIVILEGES FOR ROLE "<db>"` for both; it returns `status="created"` with the password and the owner (src/fabrik/drivers/postgres.py:829; spec-fed: `spec § 1`)
- **Given** the role already exists, **When** `ensure_app_role` runs with `reset_password=False`, **Then** no `CREATE ROLE` and no `PASSWORD` appear, the grants batch is re-applied, and it returns `status="exists"` with `password=None`; with `reset_password=True` it issues `ALTER ROLE ... PASSWORD` in its own call and returns `status="reset"` with the new password (src/fabrik/drivers/postgres.py:561)
- **Given** `_db_owner` returns `None` or `postgres`, **When** `ensure_app_role` or `probe_app_role` runs, **Then** it raises `AppRoleError` naming the database and owner, and no SQL was sent (src/fabrik/drivers/postgres.py:572)
- **Given** any `ensure_app_role` grants batch, **When** it is inspected, **Then** it carries `GRANT CREATE ON SCHEMA public TO "<owner>"` before `REVOKE CREATE ON SCHEMA public FROM PUBLIC`; the `to_regclass('public.audit_log')`-guarded block re-asserts ownership, revokes `UPDATE, DELETE, TRUNCATE` from `PUBLIC`, `"<db>_app"`, an existing `"<db>_wd_rw"` and each existing `anon`/`authenticated`/`service_role`, and grants `INSERT, SELECT` to `"<db>_app"`; memberships are granted `WITH INHERIT FALSE, SET TRUE` for those three names only, and no other role name appears in a `GRANT … TO "<db>_app"` (src/fabrik/drivers/postgres.py:803)
- **Given** a scratch PostgreSQL 16 container holding an owner that is a member of `authenticated`, an `audit_log` created by the owner, the watchdog roles minted, and a legacy `GRANT ALL ON audit_log TO PUBLIC`, **When** `ensure_app_role` runs and a real LOGIN session as `"<db>_app"` tries each statement, **Then** `INSERT`/`SELECT` on `audit_log` succeed; `UPDATE`, `DELETE`, `TRUNCATE` are refused directly and after `SET ROLE authenticated`; `CREATE TABLE` in `public` and `SET ROLE "<owner>"` are refused; the same three are refused to `"<db>_wd_rw"`; and the test goes red when the revoke line is removed (src/fabrik/drivers/postgres.py:612; spec-fed: `spec § Validation`)
- **Given** `drop_database` for a database whose app role exists, or an orphan app role whose database is gone, **When** it runs, **Then** `DROP ROLE IF EXISTS "<db>_app"` is in the batch after the database drop (src/fabrik/drivers/postgres.py:1080)
- **Given** a fake `_run_sql` whose `probe|` rows report one table owned by `<db>_app`, `UPDATE` on `audit_log` for `authenticated`, and `CREATE` on `public` for PUBLIC, **When** `probe_app_role` runs, **Then** it returns three failures naming the table, the role and PUBLIC; the batch opens with `\set ON_ERROR_STOP on` and `\c <db>`; a psql connection line in the output is ignored; an all-clear fake ending in the `probe|done` sentinel returns `[]`; and output lacking that sentinel returns a `probe incomplete` failure, never `[]` (src/fabrik/drivers/postgres.py:133)
- **Given** the scratch PostgreSQL 16 database before `ensure_app_role` (the legacy PUBLIC grants in place), **When** `probe_app_role` runs, **Then** it reports the PUBLIC `UPDATE` on `audit_log` and the PUBLIC `CREATE` on `public`; after `ensure_app_role` it returns `[]` (tests/test_app_role_real_pg.py:1)
- **Given** a scratch repo holding `app/db.py` with `await conn.run_sync(metadata.create_all)`, `app/models.py` with a lowercase `create unique index`, an `alembic/env.py` reading `DATABASE_URL`, a compose `migrate` service running `alembic upgrade head`, an `entrypoint.sh` running `psql "$DATABASE_URL" -f db/schema.sql`, a compose service with `DATABASE_URL` under `environment:`, and a `db/schema.sql` full of `CREATE TABLE`, **When** `scan_repo` runs, **Then** it returns one finding per site with path, line and pattern, none for `db/schema.sql`, and none for the same text under `tests/`, `.venv/`, `node_modules/` and `libs/` (src/fabrik/app_role_check.py:1; spec-fed: `spec § Derivations D1`)
- **Given** the same repo after every one of those sites takes `DATABASE_URL_OWNER` as its connection source, **When** `scan_repo` runs, **Then** it returns no findings; a line naming `DATABASE_URL_OWNER` only after a `#`, `--` or `//` comment marker is still a finding (src/fabrik/app_role_check.py:1)
- **Given** `run_check` with a passing probe, **When** the repo dir does not exist, or holds no walkable file, or its `HEAD` differs from its upstream after fetch, **Then** `ok` is `False` and the failure names which; with a failing probe or a probe raising `AppRoleError` and a clean current repo, the probe's failures are carried verbatim (tests/test_app_role_check.py:1)
- **Given** a spec whose `id` and `name` differ, **When** `project_repo_dir(spec)` runs, **Then** it returns `/opt/<id>` — the orchestrator's `_load_secrets` precedence (src/fabrik/orchestrator/__init__.py:384)
- **Given** `fabrik app-role-check --spec specs/services/<id>.yaml` with the check monkeypatched to fail, **When** the CLI runs, **Then** it prints one `✗` line per failure and exits 1; a passing check prints `✓` and exits 0 (src/fabrik/cli.py:1370)
- **Given** a fresh create, **When** `_provision_postgres` runs with a call recorder, **Then** the first `inject_env` carries `DATABASE_URL` and `DATABASE_URL_OWNER`, both with the owner as user and the host rewritten by `_rewrite_shared_infra_host`, and it happens BEFORE `ensure_app_role` is called; with `ensure_app_role` raising a `RuntimeError` (a `_run_sql` failure — not `AppRoleError`, whose flag-false case is the skipped row below), that owner injection has still happened and `ctx.registrar_failures` gains one `app-role:` entry (src/fabrik/orchestrator/infrastructure.py:633; spec-fed: `spec § 2`)
- **Given** a raw spec dict with no `database_url_app_role` key, **When** the step runs, **Then** the flag reads `False` with no `KeyError`, the app role is still minted, and no check runs; when `ensure_app_role` raises `AppRoleError` there (a legacy database owned by `postgres`), resource `app-role` is recorded `skipped` naming the owner and no registrar failure is added (src/fabrik/orchestrator/infrastructure.py:232)
- **Given** the flag `true` and a `.env` whose `DATABASE_URL` is `postgresql+asyncpg://<owner>:pw@10.99.0.1:5432/<db>?ssl=require` and has no `DATABASE_URL_OWNER`, **When** the step runs with a passing check, **Then** `ensure_app_role(reset_password=True)` is called and ONE `inject_env` carries `DATABASE_URL` = the same scheme, host, port, database and query with user `<db>_app` and the new password, and `DATABASE_URL_OWNER` = the old value; with a failing check nothing is injected and `ctx.registrar_failures` gains one `app-role:` entry listing each failure (src/fabrik/orchestrator/infrastructure.py:426)
- **Given** the flag `false` and a `.env` whose `DATABASE_URL` user is `<db>_app`, **When** the step runs, **Then** `inject_env` receives `DATABASE_URL` = the `DATABASE_URL_OWNER` value; when `DATABASE_URL_OWNER` is absent it injects nothing and records a registrar failure (src/fabrik/orchestrator/infrastructure.py:652)
- **Given** the flag `true` and a `.env` with no `DATABASE_URL`, or one whose user is `postgres`, or a second spec in the specs dir resolving to the same `db_name`, **When** the step runs, **Then** nothing is injected, no password is reset, and one registrar failure names the user found or the sibling specs — never the DSN (src/fabrik/orchestrator/infrastructure.py:574)
- **Given** a re-apply where the flag matches the current `DATABASE_URL` user, **When** the step runs, **Then** `ensure_app_role` is called once with `reset_password=False`, after the watchdog-role and payments steps; `inject_env` is not called while `DATABASE_URL_OWNER` is present; when it is absent and the user is the owner one `inject_env` backfills it from `DATABASE_URL`, and when it is absent and the user is `<db>_app` a registrar failure names the missing rollback DSN (src/fabrik/orchestrator/infrastructure.py:652)
- **Given** `SSHDeployer.read_env(ctx)` against a fake `_ssh`, **When** it runs, **Then** it returns the parsed dict for a present file, `{}` when `test -f` reports absence, raises `DeployError` when the ssh call fails, and runs inside `_target_vps_env(ctx)`; `inject_env` still merges exactly as before (src/fabrik/orchestrator/deployer_ssh.py:258)
- **Given** a dry-run apply, **When** the step runs, **Then** no ssh, no SQL and no check is invoked and resource `app-role` is recorded with status `dry_run` (src/fabrik/drivers/postgres.py:133)
- **Given** each Python-backed scaffold type (saas-skeleton, python-api, python-api-gpu, file-worker, and the `server/` of office-extension, chrome-extension, mobile-app and static-site) emitted into a scratch dir with a database, **When** the tree is inspected, **Then** `libs/audit_log/` (or `server/libs/audit_log/`) is vendored with no cache directory and no `test_*.py`, the schema file carries the `audit_log` table and, after it, the guarded revokes naming `current_database() || '_app'`, `current_database() || '_wd_rw'` and the three group roles, its header says `psql -1 -v ON_ERROR_STOP=1 "$DATABASE_URL_OWNER"` and the file carries no top-level `BEGIN`/`COMMIT` of its own, `_LogAuditLogger` is gone, and `.env.example` names `DATABASE_URL` and `DATABASE_URL_OWNER` (src/fabrik/scaffold.py:2111; spec-fed: `spec § 3`)
- **Given** node-api and file-api with a database, **When** emitted, **Then** the schema carries the table and revokes and no Python module; desktop-app and docusaurus emit neither; file-worker without a database emits neither (src/fabrik/scaffold.py:1484)
- **Given** a scaffolded saas-skeleton, **When** its worker is read, **Then** the beat loop schedules retention and the weekly verify (src/fabrik/scaffold.py:2773)
- **Given** a scaffolded python-api `--db`, **When** its generated spec and rendered compose are read, **Then** `companion_services` carries `<name>-audit-jobs` with a `memory` and no `env_overrides`, and the compose service renders from the partial with the app's env unchanged (src/fabrik/spec_generator.py:381)
- **Given** the emitted `audit_jobs` with `DATABASE_URL_OWNER` unset, **When** it starts, **Then** it logs `audit_jobs: not_configured` and keeps running instead of exiting non-zero (src/fabrik/scaffold.py:3081)
- **Given** the emitted schema applied to a scratch PostgreSQL 16 exactly as its header says (`psql -1 -v ON_ERROR_STOP=1 … -f`) as the owner, with the app role minted by T02, **When** a LOGIN session as the app role tries `UPDATE` on `audit_log` immediately after, **Then** it is refused; and a copy of the file with a failing statement appended after the audit block exits non-zero and leaves no `audit_log` table at all (src/fabrik/scaffold.py:2113; spec-fed: `spec § 1 No window`)
- **Given** the emitted writer adapter against that scratch database, **When** two writes run concurrently, **Then** `verify_chain(strict=True)` over the table returns no break (src/fabrik/scaffold.py:2476)

## Global Constraints

- **Shared tree with three hub sessions:**
  - Every commit is a pathspec or private-index commit of explicitly named paths; never `git add -A`, `--amend` or stash.
  - Fetch and fast-forward before push; never `--force`.
  - `CHANGELOG.md`, `INDEX.md`, `docs/DECISIONS.md` and `docs/STRATEGIC_BACKLOG.md` go only through the private-index recipe, with the step-4 assertion gating and the step-7 carry.
- **Never print a secret.** Tests assert on the SHAPE of a DSN (user, host, scheme), never a real password. Log lines name the role, never the DSN. A password in SQL is passed only inside `_run_sql`'s stdin, as the payments role does.
- **No new dependency in the hub.** Stdlib plus what `src/fabrik` already imports. The scaffolded projects' `requirements.txt` gains `psycopg[binary]`, which is scaffold output, not the hub's deps file.
- **Idempotent on every apply.** Every role and `audit_log` statement is guarded: role existence via `pg_roles`, table existence via `to_regclass`. A second apply changes no password unless a cutover or rollback is in progress.
- **Fail closed.** Every one of these refuses the switch and records a registrar failure; none is ever silently skipped:
  - a missing repo, zero scanned files, a stale clone or a failing probe;
  - a missing `DATABASE_URL_OWNER` at rollback;
  - an unreadable `.env`;
  - a `DATABASE_URL` that is absent or names neither the owner nor the app role while the flag is true;
  - a shared database.
- **Third-party images are never switched.** The check's missing-repo failure enforces this; nothing special-cases them by name.
- **Datetimes:** `datetime.now(UTC)`, never `utcnow()` (core/10-python.md:220).
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
| `.windsurf/rules/core/app-audit-log.md` | the five-point "properly" list (:22-45); the per-type rules (:50-55); one writer under `pg_advisory_xact_lock`, no table privilege needed (:200-213, the lock rule at :205); the async recipe (:215-222) | § Constraints digest |
| `.windsurf/rules/core/25-data-postgres.md` (FLOOR) | the `DATABASE_URL_DIRECT` naming precedent (:254); Settings, never a raw getenv (:331) | § Constraints digest |
| `.windsurf/rules/core/35-security-auth.md` (FLOOR) | DSNs have no fallback (:273); 32-char `[a-zA-Z0-9]` passwords (:322); Pattern A group roles (:91) | § Constraints digest |
| `.windsurf/rules/core/30-ops.md` (FLOOR) | a companion shares the app env and overrides only command/name/memory (:161); registrar fix-ups, never manual edits (:420); the migrate service reads the same env (:444-445) | § Constraints digest |
| `.windsurf/rules/core/10-python.md` | apps read a complete `DATABASE_URL` (:133); `datetime.now(UTC)` (:220); `uv`, no new dependency (:22) | § Constraints digest |
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
| `src/fabrik/orchestrator/__init__.py` | `_pre_provision_db_for_boot` (:274-343) seeds an owner-only `DATABASE_URL` for `db_before_boot` specs; `_load_secrets` resolves `/opt/<id or name>` | read in review pass 1 |
| `templates/_partials/_companion_service.yaml.j2` | the rendered companion (`core/30-ops.md:161`) T05 declares through `companion_services` | read in review pass 1 |

## Constraints digest

| Row (verbatim) | Pack | Applies to |
|---|---|---|
| "4. **Retention scheduled** — `data_retention.sql` from the project's scheduler, as the owner role" | .windsurf/rules/core/app-audit-log.md:40 | T05 retention runs on `DATABASE_URL_OWNER` |
| "takes `pg_advisory_xact_lock(AUDIT_CHAIN_LOCK_KEY)` in the SAME transaction as the write — every writer," | .windsurf/rules/core/app-audit-log.md:205 | T05 writer; T02 grants no `UPDATE` to the app |
| "**Config convention:** apps read a complete `DATABASE_URL`" | .windsurf/rules/core/10-python.md:133 | T04 keeps the app on `DATABASE_URL` |
| "must connect directly to `postgres-main:5432` via a separate `DATABASE_URL_DIRECT` env var" | .windsurf/rules/core/25-data-postgres.md:254 | T04 names `DATABASE_URL_OWNER` on this precedent |
| "the scaffolder emits a 2nd compose service that shares the app's build/image + env + `DATABASE_URL`/`REDIS_URL`, overriding only `command` + `container_name` + `memory`." | .windsurf/rules/core/30-ops.md:161 | T05 — the jobs companion shares the app's env unchanged; the jobs read `DATABASE_URL_OWNER` themselves, so no override is emitted |
| "`fabrik apply` / `reconcile-all` (spec-driven)" | .windsurf/rules/core/30-ops.md:420 | T04 — the revokes and the cutover are registrar work |
| "# DSNs and secrets get NO fallback — a missing value fails LOUDLY at boot" | .windsurf/rules/core/35-security-auth.md:273 | T05 — neither DSN has a default in emitted code |
| "- **32 characters**, charset `[a-zA-Z0-9]` only (no symbols — survives `.env` round-trip + shell quoting)." | .windsurf/rules/core/35-security-auth.md:322 | T02 app-role password |
| "**`datetime.now(UTC)`, never `datetime.utcnow()`**" | .windsurf/rules/core/10-python.md:220 | T05 jobs cursor timestamps |
| "- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance." | .windsurf/rules/core/45-testing-strategy.md:58 | T02 and T05 carry real-PG rows (scratch `postgres:16`); the fake-`_run_sql` rows grade the SQL a psql driver emits, not a mocked session |
| "a non-trivial behavior's test proves something only if it has been SEEN RED" | .windsurf/rules/core/45-testing-strategy.md:22 | every ticket; the real-PG rows red-on-revert in a throwaway worktree |
| "Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`." | .windsurf/rules/core/40-documentation.md:112 | every commit (ticket coders: `Agent-Role: subagent` + `Agent-Task`) |
| "**Operational** agents (sysadmin, watchdog, bootstrap) run via **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`." | .windsurf/rules/ai/50-agentic.md:19 | MATCHED by path only (infrastructure.py, deployer_ssh.py); no ticket dispatches an LLM, so it constrains nothing here |
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

- `src/fabrik/spec_loader.py:333-345` — `needs_payments_ingest: bool = Field(default=False, …)` and its `_payments_ingest_needs_database` validator (:380-389), the shape T01 copies. `src/fabrik/orchestrator/infrastructure.py:232` reads the RAW dict with `shape.get(...)`: `ctx.spec` never passes through `Shape`, so T04 reads the flag the same way.
- `src/fabrik/drivers/postgres.py`:
  - `:340-342` — `create_database` returns before any role SQL once the database exists.
  - `:409` — `ALTER DATABASE "{db_name}" OWNER TO "{db_user}"` makes the app the owner today.
  - `:572-584` — `_db_owner` and its docstring: a legacy or seed-restored database can be owned by `postgres`.
  - `:133-136` — `_run_sql` connects to the default database, hence `\c <db>` in every T02 batch.
  - `:803-826` — the guarded DO-block idiom.
- `src/fabrik/orchestrator/infrastructure.py`:
  - `:633-644` — the owner DSN is injected right after a fresh create, the only moment its password exists; T04 keeps that injection first.
  - `:450` — the step's `name` is `spec.get("name") or id` (name first), the OPPOSITE of `_load_secrets`'s `/opt/{id or name}` (`src/fabrik/orchestrator/__init__.py:384`), so T03's `project_repo_dir` follows `_load_secrets`, never `name`.
  - `:426-436` — `_nonfatal` feeds `ctx.registrar_failures`, which `src/fabrik/cli.py:531-545` turns into exit 2.
- `src/fabrik/orchestrator/__init__.py:274-343` — `_pre_provision_db_for_boot` seeds an owner-only `DATABASE_URL` before `_provision_postgres`. T04 treats that as "owner in use" and backfills `DATABASE_URL_OWNER`.
- `src/fabrik/orchestrator/deployer_ssh.py:281-288` — the remote `.env` read runs inside `_target_vps_env` (:281) and swallows `RuntimeError` into `''` (:287-288). T04's `read_env` keeps the wrapper and drops the swallow.
- `src/fabrik/scaffold.py`:
  - `:2113` — `-- Apply once after the DB is provisioned:  psql "$DATABASE_URL" -f db/schema.sql`, with no top-level transaction in the file.
  - `:3081-3089` — DSNs arrive ONLY via `env_file`, absent until the registrar injects them.
  - `:2476` — `class _LogAuditLogger`.
  - `:1975-1977` — the no-op replace.
- `.windsurf/rules/core/30-ops.md:161` — companions are declared in the spec's `companion_services` and share the app env.
- Four database specs share `depends.postgres: main` (the third probe below). T04 refuses a cutover of a shared database.
- No existing spec carries the new flag (0 of 72), so this plan switches nothing live.
- The PostgreSQL design, probed live in a throwaway container (second block). `postgres:18` was used for its syntax, which is the same as 16's for these statements. Roles: `p` owner, member of `authenticated`; `p_app` minted as in T02; `p_wd_rw` with default DML. The audit block was applied as the owner in one transaction.
  - Output order: the `(inherit, set)` flags of the `p_app → authenticated` membership, then `has_table_privilege` per role, then statements from a superuser session under `SET ROLE`, then statements from a real `p_app` LOGIN session.
  - The superuser `[app-set-role-owner] 1` is the proof that a `SET ROLE` chain is checked against the SESSION user and grades nothing. That is why T02's refusal row uses a LOGIN session.
- The schema transaction (review pass 2), on `postgres:16`: a file with no top-level `BEGIN`/`COMMIT` — `CREATE TABLE audit_log`, the `current_database()`-guarded revoke `DO` block, then a failing `SELECT no_such_fn()` — run with `psql -1 -v ON_ERROR_STOP=1 -f` exits `3` and leaves `to_regclass('public.audit_log')` NULL. With an inner `COMMIT`, the table survives and psql exits 0 (the pass-2 seat's reproduction).

```text
$ timeout 20 docker images postgres --format '{{.Repository}}:{{.Tag}}' | sort
postgres:14
postgres:15-alpine
postgres:16
postgres:16-alpine
postgres:16-bookworm
postgres:17
postgres:18
$ ls specs/services/*.yaml | wc -l; command grep -l 'database_url_app_role' specs/services/*.yaml | wc -l
72
0
$ for f in $(command grep -l 'postgres: *main' specs/services/*.yaml); do command grep -q 'needs_database: *true' $f && echo $f; done
specs/services/ai-model-catalog.yaml
specs/services/compliance-ops.yaml
specs/services/exam-coach.yaml
specs/services/gmail-account-creator.yaml
```

```text
-- membership row (inherit,set):
f|t
-- schema applied as owner in ONE txn with guarded revokes:
p_app INSERT=t  p_app SELECT=t  p_app UPDATE=f  p_app DELETE=f  p_app TRUNCATE=f  
p_wd_rw INSERT=t  p_wd_rw SELECT=t  p_wd_rw UPDATE=f  p_wd_rw DELETE=f  p_wd_rw TRUNCATE=f  
authenticated INSERT=t  authenticated SELECT=t  authenticated UPDATE=f  authenticated DELETE=f  authenticated TRUNCATE=f  
[app-insert] INSERT 0 1
[app-update] ERROR:  permission denied for table audit_log
[app-delete] ERROR:  permission denied for table audit_log
[app-truncate] ERROR:  permission denied for table audit_log
[app-as-authenticated-delete] ERROR:  permission denied for table audit_log
[app-as-authenticated-update] ERROR:  permission denied for table audit_log
[app-create-in-public]                      ^
[app-set-role-owner] 1
[wd-delete] ERROR:  permission denied for table audit_log
[owner-delete] DELETE 1
[login:create] ERROR:  permission denied for schema public
[login:set-owner] ERROR:  permission denied to set role "p"
[login:as-auth-delete] psql: warning: extra command-line argument "ROLE" ignored
[login:as-auth-then-delete-direct] ERROR:  permission denied for table audit_log
```

## Self-audit

- **Grounding passes.**
  - Every `path:line` above was opened in the authoring run.
  - Review pass 1 (four slices) re-derived them, executed 51 candidates and confirmed 48. § Review — Pass Ledger names the fixes.
- **(a) Coverage:**
  - role, grants and revokes → T02;
  - owner-first injection and the declarative step → T04;
  - flag → T01;
  - measured check → T03;
  - scaffolder, jobs and templates → T05;
  - the two scaffold bugs → T05;
  - docs → T04 (drivers.md, lifecycle) + T05 (CONFIGURATION.md, templates);
  - the security limit of a shared `.env` → T04 Docs + backlog;
  - the Node writer and shared databases → deferred with named destinations.
- **(b) Cross-ticket signatures:**
  - `ensure_app_role(db_name, container, dry_run, reset_password)`, `probe_app_role(db_name, container)` and `AppRoleError` are produced by T02 and consumed by T03 and T04.
  - `run_check(db_name, repo_dir, container)` and `project_repo_dir(spec)` are produced by T03 and consumed by T04.
  - The flag is produced by T01 and consumed by T04 (read from the raw dict) and T05.
  - The two-variable env contract is produced by T04 and consumed by T05.
- **Sizing:** the emit gate's summary line is in § Review — Pass Ledger. `scaffold.py` (280 KB) sits in the Integration ticket by the READ-budget hatch. T03's read set was trimmed in pass 1: the spine's Interfaces carries the symbols it consumes.
- **Fixed point:** see § Review — Pass Ledger.
- **Breadth advisory (`check_ticket_breadth.py`, run at the flip): all 5 flagged — KEPT, reasons:**
  - T02 (score 9): one file, one invariant — the grant set that makes `audit_log` append-only. Splitting grants from revokes or from the probe would spread one privilege invariant across tickets whose real-PG tests must see all of it.
  - T04 (score 9): one state machine whose branches share one decision. A split would test half-machines.
  - T05 (score 9): the Integration ticket, which owns the indivisible 280 KB `scaffold.py` by the READ-budget hatch.
  - T03 (score 6): the scan and `run_check` share the fail-closed rule.
  - T01 (score 5): one field, its validator and its generator default.
  - This record was added after pass 4 as the gate's mandated disposition; it changes no behaviour row.

## Coverage Checklist

Rubric over the plan's File Scope (`python scripts/review_rubric.py --changed src/fabrik/spec_loader.py src/fabrik/spec_generator.py tests/test_spec_loader.py tests/test_spec_generator.py src/fabrik/drivers/postgres.py tests/test_app_role_driver.py tests/test_app_role_real_pg.py src/fabrik/app_role_check.py tests/test_app_role_check.py src/fabrik/cli.py src/fabrik/orchestrator/infrastructure.py src/fabrik/orchestrator/deployer_ssh.py tests/test_app_role_provision.py tests/orchestrator/test_deployer_ssh.py docs/operations/fabrik-lifecycle.md docs/CONFIGURATION.md docs/reference/modules/drivers.md docs/QUICKSTART.md src/fabrik/scaffold.py templates/scaffold/docs/CONFIGURATION_TEMPLATE.md templates/scaffold/docs/OPERATIONS_TEMPLATE.md templates/scaffold/docs/RESILIENCE_TEMPLATE.md templates/saas-skeleton/.env.example templates/mobile-app/.env.example templates/node-api/.env.example tests/test_scaffold_audit_log.py tests/test_scaffold_saas_backend.py docs/development/reviews/2026-09-24-plan-1-audit-log-everywhere-review.md`), verbatim:

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project and per-tenant isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and archives nothing.  If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### ai/50-agentic.md  (hit: src/fabrik/orchestrator/deployer_ssh.py, src/fabrik/orchestrator/infrastructure.py, tests/orchestrator/test_deployer_ssh.py)
- **Claude** for reasoning + tool use. **Operational** agents (sysadmin, watchdog, bootstrap) run via **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`.

### core/10-python.md  (hit: src/fabrik/app_role_check.py, src/fabrik/cli.py, src/fabrik/drivers/postgres.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: docs/CONFIGURATION.md, docs/QUICKSTART.md, docs/development/reviews/2026-09-24-plan-1-audit-log-everywhere-review.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/orchestrator/test_deployer_ssh.py, tests/test_app_role_check.py, tests/test_app_role_driver.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_* tail elided here (the MATCHED/FLOOR mandates above are verbatim; the tail restates their backtick literals)
```

| Class | Status |
|---|---|
| FLOOR core/35-security-auth.md — DSNs without fallback, 32-char passwords, no secret in logs | FIXED — pass 1: failures and logs name roles and users, never a DSN (T04 step 2, fail-closed row); the password comes from `_generate_password` (T02); the jobs' DSN has no default (T05). Hunted: T02, T04 and T05 Scope, `src/fabrik/drivers/postgres.py:106`, `src/fabrik/scaffold.py:3081` |
| FLOOR core/25-data-postgres.md — roles, grants, DSN naming, Settings reads | FIXED — pass 1: grants extended to every owner schema (O7); PUBLIC `CREATE` and PUBLIC `audit_log` grants revoked (O9, O16); memberships limited to the three Pattern A roles (O6, O8); real owner via `_db_owner` (O10); `\c <db>` in every batch (O11); jobs read `DATABASE_URL_OWNER` through Settings. Proven live: § Evidence PG probe |
| FLOOR core/30-ops.md — companion env and memory limit, registrar-only fix-ups, migrate service env | FIXED — pass 1: the companion is declared through `companion_services` with no env override (S2, S3, S4); `memory` is measured (§ Residual unknowns); a compose `environment: DATABASE_URL` and a `migrate` service are scan findings (T03). Hunted: `core/30-ops.md:150-170`, `src/fabrik/scaffold.py:3081-3089` |
| FLOOR 12-FACTOR — config in env (III), backing services (IV), admin processes (XII), logs (XI) | CLEAN — the schema runs as a one-off `psql -1` (XII), the jobs never apply schema, logs go to stdout, and both DSNs come from env. Hunted: T05 Scope, § Global Constraints |
| MATCHED core/10-python.md — complete `DATABASE_URL`, `datetime.now(UTC)`, no new dependency | FIXED — pass 1: the cutover swaps only user and password, preserving `+asyncpg`, host and query (O17, B-O9); a DSN assembled from discrete variables fails closed (O3). No hub dependency is added. Hunted: T04 step 2, `core/10-python.md:133` |
| MATCHED core/40-documentation.md — trailers, docs the change makes stale | CLEAN — every ticket names its `Docs:`; CONFIGURATION.md sits with T05; the trailer rule is in the digest. Hunted: every ticket's `Docs:` line |
| MATCHED core/45-testing-strategy.md — one test per behaviour, real PostgreSQL, seen red | FIXED — pass 1: added real-PG rows for the group-role path through a LOGIN session (B-O12), for the probe over legacy PUBLIC grants, for the schema applied exactly as the header runs it (O11), and for concurrent writer chain integrity (S7); added rows for dry-run, the spoke host and the missing flag key (O18) |
| MATCHED ai/50-agentic.md — no LLM dispatch in scope | CLEAN — no ticket dispatches a model; the pack is matched by path only. Hunted: every ticket's Scope |
| core/app-audit-log.md — the five points per type | FIXED — pass 1: file-worker with a database included (O13); the vendor ignore list matches the module's real artefacts (S5); the writer follows the async recipe in one transaction with a chain test (S7). The Node writer is deferred with a named destination (S6, § Residual unknowns) |
| Standing: fail-open vs fail-closed on every gate/guard | FIXED — pass 1: the step's catch-all became fail-closed (O3, B-O3); `read_env` raises instead of returning `{}` (O4, B-O4); a zero-file scan and a stale clone fail (C-S2, O20); a comment token never suppresses (O6); a shared database is refused (B-O5) |
| Standing: cost/quota/limit accounting edges (unknown≠0, per-call vs batch) | CLEAN — the only limits are the READ budget (the emit gate, § Review — Pass Ledger) and the companion memory (measured, never assumed). Hunted: T05, § Residual unknowns |
| Standing: boundary/sentinel/prefix collisions | FIXED — pass 1: role names in the schema come from `current_database()`, never a scaffold-time name (O12); the repo dir uses id first (O20, B-O20); `probe|` row prefixes keep psql's connection line out of the parse (B-O11) |
| Standing: behavior-without-a-test | FIXED — every T04 branch (fresh, missing key, cutover, rollback, fail-closed, converged, read_env, dry-run) has its own row, and T01 pins that every enabled type has a shape |

## Residual unknowns

- **Resolved (emit gate):** `python -m scripts.enforcement.check_plan_tickets --plan-dir docs/development/plans/2026-09-24-plan-1-audit-log-everywhere` — the summary line of the last run is quoted in § Review — Pass Ledger. The first draft had T04 at 276,215 B against 262,144, so `docs/CONFIGURATION.md` (57,582 B) moved to T05.
- **Resolved (review pass 1): the scratch PostgreSQL.** `postgres:16` is in the local image list (§ Evidence). The fixture still skips with its reason when docker is unavailable, and a skip never counts as the red-on-revert proof.
- **Open (self-service, T05): the jobs companion's memory.** Measure the peak RSS of one retention and one verify pass over 10k rows in a scratch container. Set `memory` to 2× peak, floor 128M, and record the measurement in the receipt.
- **Deferred, destination named — the Node writer.** `core/app-audit-log.md:50-52` says node-api and file-api owe a writer hashing byte-identically to `canonical_payload` until fabrik-lib's Node port lands. T05 emits the table and revokes only. The writer is the port's (fabrik-lib, already filed by infra) or the project agent's during its wave. A STRATEGIC_BACKLOG row carries it (T05 Deltas).
- **Deferred, destination named — shared databases.** A database shared by several specs (`depends.postgres: main`, 4 specs) is refused by T04's cutover, because one `<db>_app` password cannot be reset for one sibling. Cutting such a database over as one unit is the waves plan's first design question; a backlog row carries it (T04 Deltas).
- **Follow-up plan, not this one: the migration waves.** After T05 merges, a waves plan pilots one low-risk database project, then mails one repo at a time. It inventories fabrik-smoke-test, test-saas-log and translator (no repo on this box, no third-party image) first, and measures each project's Pattern A membership and non-`public` schemas.
- **Routed at Finish (T05 receipt):**
  - infra is mailed that the pack's owner-role caveats (`core/app-audit-log.md:26-36`, `:40-41`) are stale once T04 ships;
  - fabrik-lib already holds 01M37RT50.
- **Stated limit (T04 docs + backlog):** `DATABASE_URL_OWNER` lives in the same project `.env` the app reads. Append-only therefore holds against the app's code paths and SQL injection, not against code execution in the container. A migrate-only env file is the backlog row.

## Review — Pass Ledger

Hashes are the combined md5 over the set's repo-relative paths, taken at each pass's pin (start) and after its fixes (end); each end precedes the writing of its own row, so the next start differs from it by exactly that row.

Emit gate at the last edit: `graded 5 ticket(s), 29 Touches path(s), 34 Context-Files entry(ies); READ budget measured against /opt/fabrik; 0 finding(s)`.

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | plan md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×2 + sonnet×2 (slices A spine grammar, B T02+T04, C spine prose+T01+T03, D T05), one refuter per slice · all axes | found: 51, new: 51, confirmed: 48, fixed: 48, unexecuted: 0, edits: 6 | method: citation — full partitioned pass. Refuted: 3 (C-S4 range correct; B-O19 split already in T02's shape; D-S1 wrapper stated). Orchestrator probes: the PG semantics container run and the flip-gate matrix on a flipped copy. The fixes rewrote T02/T03/T04/T05 Scope and rows, the spine Interfaces, Evidence, Residual unknowns and the digest column order | eeaba4cf → e7edfa3c |
| Pass 2 | opus×2 + sonnet×2 (round-1 slice owners), one refuter per slice · delta over the pass-1 fix hunks + one hop | found: 9, new: 9, confirmed: 9, fixed: 9, unexecuted: 0, edits: 12 | method: re-derivation — 51 ledger claims re-checked: 45 now false, 6 new; all 9 confirmed defects lie inside pass-1 fix hunks (own-fix: round 1). Fixed: wrong anchors (`__init__.py:384`, `deployer_ssh.py:281`/`:287-288`, `:450`), the probe's missing `ON_ERROR_STOP` and sentinel, `AppRoleError` on flag-false legacy DBs, the stale digest row, `create_all` passed bare, `psql -1` versus an inner `COMMIT` (probed: exit 3, no table), the backfill row. mirrors: 4 read | a3c30e6c → 32b3f2cb |
| Pass 3 | opus×2 + sonnet×2 (round-1 slice owners), one refuter per slice · delta over the pass-2 fix hunks + one hop | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 2 | method: re-derivation — 9 pass-2 claims re-checked, all 9 now false. 1 confirmed inside the pass-2 hunk (own-fix: round 2): T04's fresh-create failure row did not name the exception type, contradicting the flag-false `AppRoleError` skip; fixed by naming `RuntimeError`. Scope-growth stop: rounds 2 and 3 are both 100% own-fix, so the remainder round re-verifies only this fix | 8730e1de → 7bf6edeb |
| Pass 4 | opus×1 (slice B round-1 owner, remainder round after the scope-growth stop) · the one fixed row + its spine roll-up copy | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the single changed T04 row was re-read against T04 step 3 and the missing-key row; its spine roll-up copy is byte-identical (md5 of both lines equal); the `RuntimeError` claim was checked against `_run_sql`'s docstring. Standing clean since pass 2: every other class and slice (passes 2-3 re-verified all 60 ledger claims now false) | e7c93eb3 → e7c93eb3 ✓ → CONVERGED |
