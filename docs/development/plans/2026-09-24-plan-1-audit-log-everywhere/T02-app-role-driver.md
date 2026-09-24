# T02 — `<db>_app` role driver: mint, grants, audit revokes, probe, drop

## Scope
In `src/fabrik/drivers/postgres.py`, add `AppRoleError(RuntimeError)`, `app_role_name`, `ensure_app_role` and `probe_app_role` with the exact signatures in the spine § Interfaces, following the payments-ingest shape (`create_payments_ingest_role` :829-878; the guarded DO-block idiom `_payments_ingest_policy_block` :803-826). Implements spec § 1 as corrected by D-386.

**Owner.** Every function resolves the database's real owner with `_db_owner` (:572) — never assumes `owner == db_name`. It raises `AppRoleError` naming the database and owner, before any SQL, when the owner is `None` or `postgres` (a legacy, manual or seed-restored database the app role must not be minted against).

**`ensure_app_role`:**
- `CREATE ROLE "<db>_app" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD …` runs in its OWN `_run_sql` call, only when missing (`_role_exists` :561), exactly as the watchdog and payments roles do. A later grant failure then never orphans a freshly minted password inside a half-applied batch. `reset_password=True` issues `ALTER ROLE … PASSWORD` the same way. Passwords come from `_generate_password` (:106).
- Then ONE `\set ON_ERROR_STOP on` batch that opens with `\c <db>` (`_run_sql` connects to the default `postgres` database, :133-136):
  - `GRANT CONNECT` on the database;
  - for every non-system schema the owner owns (`public` plus, for a Pattern A-compat project, `auth` — `core/35-security-auth.md:91`): `USAGE` (never `CREATE`), DML on all tables, `USAGE, SELECT` on all sequences, and `ALTER DEFAULT PRIVILEGES FOR ROLE "<owner>" IN SCHEMA <s>` for both;
  - `GRANT CREATE ON SCHEMA public TO "<owner>"`, then `REVOKE CREATE ON SCHEMA public FROM PUBLIC`. A database created before PG 15, or restored from one, still lets PUBLIC create in `public`, and the whole ownership guarantee rests on the app not creating;
  - the `to_regclass('public.audit_log')`-guarded DO block: `ALTER TABLE audit_log OWNER TO "<owner>"` when owned by anyone else; `REVOKE UPDATE, DELETE, TRUNCATE ON audit_log` FROM `PUBLIC`, `"<db>_app"`, `"<db>_wd_rw"` when it exists, and each of `anon`/`authenticated`/`service_role` that exists; then `GRANT INSERT, SELECT` to `"<db>_app"`;
  - memberships: for each of `anon`/`authenticated`/`service_role` ONLY — never any other role — that exists and that the owner is a member of, `GRANT <role> TO "<db>_app" WITH INHERIT FALSE, SET TRUE`.

**`probe_app_role`:** non-mutating reads in one batch opening `\set ON_ERROR_STOP on` and `\c <db>`, each result row prefixed `probe|` so the parser ignores psql's connection line, and ending with a `SELECT 'probe|done'` sentinel. Output without the sentinel — a query error mid-batch — is a `probe incomplete` failure, never an empty pass. One failure string per violation:
- a table in an owner schema not owned by the owner (`pg_tables.tableowner`);
- the app role lacking `SELECT`/`INSERT` on a table or `USAGE` on a sequence;
- `CREATE` on `public` held by the app role or PUBLIC (`has_schema_privilege`);
- `UPDATE`/`DELETE`/`TRUNCATE` on `audit_log` held by the app role, PUBLIC, `<db>_wd_rw` or any group role the app is a member of.

It uses `has_*_privilege`. A superuser `SET ROLE` chain is checked against the SESSION user and proves nothing about the app's membership (measured in this plan's review, § Evidence).

**`drop_database`** (:1018) drops `"<db>_app"` in both the main (:1103-1106) and orphan (:1080-1086) batches.

**Tests:**
- `tests/test_app_role_driver.py` uses a fake `_run_sql` capturing SQL.
- `tests/test_app_role_real_pg.py` holds `scratch_pg()` (spine § Interfaces T02 → T05) and the two real-PG rows. The refusal row uses a real LOGIN session as `<db>_app` (`psql -h 127.0.0.1 -U <db>_app`), never superuser `SET ROLE`.
- Prove both real-PG rows red-on-revert in a throwaway worktree.

DO-NOT: touch `create_database` or `create_watchdog_roles`; inject any env or decide any cutover (T04); change the payments role.

Depends: —
Parallel: ⚡
Complexity: never-route
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_app_role_driver.py tests/test_app_role_real_pg.py tests/test_payments_ingest_role.py tests/test_watchdog_db_roles.py -q
Docs: CHANGELOG (Deltas) · none other — T04 writes the role model into docs/reference/modules/drivers.md

## Touches
- src/fabrik/drivers/postgres.py — PRIMARY PATH
- tests/test_app_role_driver.py
- tests/test_app_role_real_pg.py

## Behavior Contract
- **Given** a fake `_run_sql` where `_db_owner` returns `<db>` and the app role does not exist, **When** `ensure_app_role` runs, **Then** `CREATE ROLE "<db>_app" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS` with a 32-character `[a-zA-Z0-9]` password runs in its own `_run_sql` call; the grants batch that follows opens with `\c <db>`; it grants `CONNECT` and `USAGE` (never `CREATE`) on each owner schema, DML on its tables, `USAGE, SELECT` on its sequences, and `ALTER DEFAULT PRIVILEGES FOR ROLE "<db>"` for both; it returns `status="created"` with the password and the owner (src/fabrik/drivers/postgres.py:829; spec-fed: `spec § 1`)
- **Given** the role already exists, **When** `ensure_app_role` runs with `reset_password=False`, **Then** no `CREATE ROLE` and no `PASSWORD` appear, the grants batch is re-applied, and it returns `status="exists"` with `password=None`; with `reset_password=True` it issues `ALTER ROLE ... PASSWORD` in its own call and returns `status="reset"` with the new password (src/fabrik/drivers/postgres.py:561)
- **Given** `_db_owner` returns `None` or `postgres`, **When** `ensure_app_role` or `probe_app_role` runs, **Then** it raises `AppRoleError` naming the database and owner, and no SQL was sent (src/fabrik/drivers/postgres.py:572)
- **Given** any `ensure_app_role` grants batch, **When** it is inspected, **Then** it carries `GRANT CREATE ON SCHEMA public TO "<owner>"` before `REVOKE CREATE ON SCHEMA public FROM PUBLIC`; the `to_regclass('public.audit_log')`-guarded block re-asserts ownership, revokes `UPDATE, DELETE, TRUNCATE` from `PUBLIC`, `"<db>_app"`, an existing `"<db>_wd_rw"` and each existing `anon`/`authenticated`/`service_role`, and grants `INSERT, SELECT` to `"<db>_app"`; memberships are granted `WITH INHERIT FALSE, SET TRUE` for those three names only, and no other role name appears in a `GRANT … TO "<db>_app"` (src/fabrik/drivers/postgres.py:803)
- **Given** a scratch PostgreSQL 16 container holding an owner that is a member of `authenticated`, an `audit_log` created by the owner, the watchdog roles minted, and a legacy `GRANT ALL ON audit_log TO PUBLIC`, **When** `ensure_app_role` runs and a real LOGIN session as `"<db>_app"` tries each statement, **Then** `INSERT`/`SELECT` on `audit_log` succeed; `UPDATE`, `DELETE`, `TRUNCATE` are refused directly and after `SET ROLE authenticated`; `CREATE TABLE` in `public` and `SET ROLE "<owner>"` are refused; the same three are refused to `"<db>_wd_rw"`; and the test goes red when the revoke line is removed (src/fabrik/drivers/postgres.py:612; spec-fed: `spec § Validation`)
- **Given** `drop_database` for a database whose app role exists, or an orphan app role whose database is gone, **When** it runs, **Then** `DROP ROLE IF EXISTS "<db>_app"` is in the batch after the database drop (src/fabrik/drivers/postgres.py:1080)
- **Given** a fake `_run_sql` whose `probe|` rows report one table owned by `<db>_app`, `UPDATE` on `audit_log` for `authenticated`, and `CREATE` on `public` for PUBLIC, **When** `probe_app_role` runs, **Then** it returns three failures naming the table, the role and PUBLIC; the batch opens with `\set ON_ERROR_STOP on` and `\c <db>`; a psql connection line in the output is ignored; an all-clear fake ending in the `probe|done` sentinel returns `[]`; and output lacking that sentinel returns a `probe incomplete` failure, never `[]` (src/fabrik/drivers/postgres.py:133)
- **Given** the scratch PostgreSQL 16 database before `ensure_app_role` (the legacy PUBLIC grants in place), **When** `probe_app_role` runs, **Then** it reports the PUBLIC `UPDATE` on `audit_log` and the PUBLIC `CREATE` on `public`; after `ensure_app_role` it returns `[]` (tests/test_app_role_real_pg.py:1)

## Context Files
- .windsurf/rules/core/25-data-postgres.md
- .windsurf/rules/core/35-security-auth.md
- .windsurf/rules/core/app-audit-log.md
- src/fabrik/drivers/postgres.py
- tests/test_payments_ingest_role.py
- tests/test_watchdog_db_roles.py
- docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md
