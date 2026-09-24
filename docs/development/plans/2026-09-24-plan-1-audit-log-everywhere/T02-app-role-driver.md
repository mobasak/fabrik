# T02 — `<db>_app` role driver: mint, grants, audit revokes, probe, drop

## Scope
In `src/fabrik/drivers/postgres.py`, add `app_role_name`, `ensure_app_role` and `probe_app_role` with the exact signatures in the spine § Interfaces, following the payments-ingest shape (`create_payments_ingest_role` :829-878; its guarded DO-block idiom `_payments_ingest_policy_block` :803-826). Implements spec § 1 as corrected by D-386.

What `ensure_app_role` does:
- Mints the role only when missing (`_role_exists` :561), with `_generate_password` (:106).
- On every call, in one `\set ON_ERROR_STOP on` batch through `_run_sql` (:111):
  - `GRANT CONNECT` on the database; `GRANT USAGE ON SCHEMA public` (never `CREATE`);
  - DML on all tables; `USAGE, SELECT` on all sequences;
  - `ALTER DEFAULT PRIVILEGES FOR ROLE "<owner>" IN SCHEMA public` for tables and sequences;
  - the `to_regclass('public.audit_log')`-guarded block: ownership re-assertion, then `REVOKE UPDATE, DELETE, TRUNCATE` from `<db>_app`, from `<db>_wd_rw` if it exists and from each existing `anon`/`authenticated`/`service_role`, then `GRANT INSERT, SELECT` to `<db>_app`;
  - `GRANT <group> TO "<db>_app" WITH INHERIT FALSE, SET TRUE` for each group role the owner is a member of.
- `reset_password=True` issues `ALTER ROLE … PASSWORD`.

What `probe_app_role` does: non-mutating reads only.
- Every `public` table's owner is the owner (`pg_tables.tableowner`).
- `has_table_privilege` / `has_sequence_privilege`: the app role holds `SELECT`/`INSERT` on all tables and `USAGE` on all sequences.
- The app role, and each group role it is a member of, holds none of `UPDATE`/`DELETE`/`TRUNCATE` on `audit_log` when the table exists.

`drop_database` (:1018) drops `"<db>_app"` in both the main (:1103-1106) and orphan (:1080-1086) batches.

Tests:
- `tests/test_app_role_driver.py` uses a fake `_run_sql` capturing SQL.
- `tests/test_app_role_real_pg.py` holds the `scratch_pg()` helper (spine § Interfaces T02 → T05) and the real-privilege row. Prove it red-on-revert in a throwaway worktree.

DO-NOT: touch `create_database` or `create_watchdog_roles` (the revoke is re-applied from `ensure_app_role`, which T04 calls after the watchdog step); inject any env (T04); change the payments role.

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
- **Given** `ensure_app_role` against a fake `_run_sql` on a role that does not exist, **When** it runs, **Then** the SQL batch mints `"<db>_app" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS` with a 32-character `[a-zA-Z0-9]` password, grants `CONNECT` and `USAGE ON SCHEMA public` and never `CREATE`, grants DML on all tables and `USAGE, SELECT` on all sequences, and sets `ALTER DEFAULT PRIVILEGES FOR ROLE "<owner>"` for both; it returns `status="created"` with the password (src/fabrik/drivers/postgres.py:829; spec-fed: `spec § 1`)
- **Given** the role already exists, **When** `ensure_app_role` runs again with `reset_password=False`, **Then** no `CREATE ROLE` and no `PASSWORD` appear in the batch, the grants are re-applied, and it returns `status="exists"` with `password=None`; with `reset_password=True` it issues `ALTER ROLE ... PASSWORD` and returns `status="reset"` with the new password (src/fabrik/drivers/postgres.py:561)
- **Given** any `ensure_app_role` batch, **When** it is inspected, **Then** it carries a `to_regclass('public.audit_log')`-guarded DO block that re-asserts `ALTER TABLE audit_log OWNER TO "<owner>"` when the owner differs, revokes `UPDATE, DELETE, TRUNCATE` from `"<db>_app"`, from `"<db>_wd_rw"` when that role exists and from each of `anon`/`authenticated`/`service_role` that exists, grants `INSERT, SELECT` to `"<db>_app"`, and grants each existing group role the owner is a member of to `"<db>_app"` `WITH INHERIT FALSE, SET TRUE` (src/fabrik/drivers/postgres.py:803)
- **Given** a scratch PostgreSQL 16 container with an owner, the audit table created by the owner and the watchdog roles minted, **When** `ensure_app_role` runs and a session `SET ROLE "<db>_app"` tries each statement, **Then** `INSERT`/`SELECT` on `audit_log` succeed and `UPDATE`, `DELETE`, `TRUNCATE` fail with a permission error, the same three fail as `"<db>_wd_rw"`, and the test goes red when the revoke line is removed (src/fabrik/drivers/postgres.py:612; spec-fed: `spec § Validation`)
- **Given** `drop_database` for a database whose app role exists, or an orphan app role whose database is gone, **When** it runs, **Then** `DROP ROLE IF EXISTS "<db>_app"` is in the batch after the database drop (src/fabrik/drivers/postgres.py:1080)
- **Given** a fake `_run_sql` whose ownership query returns one table owned by `<db>_app` and whose privilege query reports `UPDATE` on `audit_log` for `authenticated`, **When** `probe_app_role` runs, **Then** it returns two failures naming the table and the role, and an all-clear fake returns `[]` (src/fabrik/drivers/postgres.py:572)

## Context Files
- .windsurf/rules/core/25-data-postgres.md
- .windsurf/rules/core/35-security-auth.md
- .windsurf/rules/core/app-audit-log.md
- src/fabrik/drivers/postgres.py
- tests/test_payments_ingest_role.py
- tests/test_watchdog_db_roles.py
- docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md
