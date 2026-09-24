# T04 — Registrar step: owner-first injection, declarative cutover and rollback, docs

## Scope
Implements spec § 1 "Where it runs" and § 2, with the declarative semantics of D-390 (2)(3).

**`SSHDeployer.read_env(ctx) -> dict[str, str]`** in `src/fabrik/orchestrator/deployer_ssh.py`:
- It runs inside `with _target_vps_env(ctx)` (as `inject_env` does, :281), so a spoke's `.env` is read on the spoke.
- It returns `{}` only when `test -f /opt/<name>/.env` says the file is absent.
- It RAISES `DeployError` on any ssh or read failure. The swallow at :287-288 is right for a merge, never for a decision.
- `inject_env` keeps its own read and merge exactly as today.

**The new step `_provision_app_role` in `src/fabrik/orchestrator/infrastructure.py`**, called from `_provision_postgres` (:561) AFTER the watchdog-role and payments-ingest blocks (:652-733), so its revokes land after the watchdog's `GRANT … ON ALL TABLES`:

0. **Fresh create — owner first, unchanged.** When `create_database` returns a password (:633-644), inject `DATABASE_URL` AND `DATABASE_URL_OWNER`, both the owner DSN, in the existing single `inject_env` call, BEFORE anything else can fail. The owner password exists only at that moment.
1. **Inputs:**
   - the flag, read from the RAW spec dict: `(spec.get("shape") or {}).get("database_url_app_role", False)`. `ctx.spec` is the yaml dict, never the pydantic `Shape`, so its default does not apply (`resolve_applicability` reads `shape.get(...)` the same way, :232);
   - the owner and app role, from `ensure_app_role(db_name)` (T02) — called on EVERY apply, with `reset_password=True` only in the cutover branch;
   - the current `DATABASE_URL` user, from `read_env(ctx)`, parsed with `urllib.parse.urlsplit`.
2. **Decide.** Log the role names only, never a DSN or a password.
   - **Cutover** — flag true, user == owner. This covers a fresh create, a `db_before_boot` database whose owner DSN was seeded by `_pre_provision_db_for_boot` (`src/fabrik/orchestrator/__init__.py:274-343`), and an existing project.
     - Refuse when another spec in `specs/services/` resolves to the same `db_name` (`depends.postgres: main` is shared by 4 database specs): one `<db>_app` password cannot be reset for one sibling without breaking the others. Record the siblings in the failure.
     - Otherwise run `run_check(db_name, project_repo_dir(spec))` (T03).
     - If it passes: `ensure_app_role(db_name, reset_password=True)`, then ONE `inject_env` with `DATABASE_URL` = the current DSN with ONLY its user and password swapped (scheme — `+asyncpg` included — host, port, database and query preserved) and `DATABASE_URL_OWNER` = the current DSN (backfilled when absent).
     - If it fails: nothing injected, one `app-role:` registrar failure listing each failure.
   - **Rollback** — flag false, user == `<db>_app`: inject `DATABASE_URL` = the `DATABASE_URL_OWNER` value. When that key is absent, inject nothing and record a registrar failure.
   - **Converged** — flag true and user == `<db>_app`, or flag false and user == owner: inject nothing while `DATABASE_URL_OWNER` is present; the grants were re-applied in step 1. With `DATABASE_URL_OWNER` absent: user == owner backfills it from `DATABASE_URL` in one `inject_env`; user == `<db>_app` records a registrar failure, because no rollback DSN exists and the owner password cannot be recovered.
   - **Fail closed** — flag true and `DATABASE_URL` absent, or its user neither the owner nor `<db>_app` (a superuser, a legacy role, a DSN assembled from discrete variables): inject nothing and record a registrar failure naming the user found.
3. **Failures.** Every exception, `DeployError` included, goes through `self._nonfatal(ctx, "app-role", e)` (:426-436), so the CLI exits 2 (`src/fabrik/cli.py:531-545`). The one exception is `AppRoleError` while the flag is FALSE: the database is owned by `postgres` (legacy, manual or seed-restored), the app role is not needed until a cutover, and failing every apply of such a project would break deploys that never asked for the switch. It records resource `app-role` as `skipped` naming the owner. With the flag true, `AppRoleError` is a registrar failure like any other.
4. **Dry-run.** The step sends no ssh, no SQL and no check. It records resource `app-role` with status `dry_run` and logs that the decision needs the live `.env`: a preview that claimed "converged" would be a false preview.

**Docs:**
- `docs/reference/modules/drivers.md` gets the role model: owner vs app vs wd_rw vs group roles, and what each may do on `audit_log`.
- `docs/operations/fabrik-lifecycle.md` gets:
  - the cutover and rollback runbook: set the flag, run `fabrik app-role-check`, apply; unset to roll back;
  - the shared-database refusal;
  - the limit: the owner DSN shares the project `.env`, so append-only holds against the app's code paths and SQL injection, not against code execution in the container.
- (`docs/CONFIGURATION.md` is T05's, for the READ budget.)

DO-NOT: edit any `specs/services/*.yaml`; touch `create_database`'s preserve-on-re-apply rule (:340-342) or `_pre_provision_db_for_boot`; special-case third-party images by name (their missing repo fails the check).

Depends: T01, T02, T03
Parallel: ⛓️
Complexity: never-route
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_app_role_provision.py tests/orchestrator/test_deployer_ssh.py tests/test_payments_ingest_role.py tests/test_watchdog_db_roles.py -q
Docs: docs/operations/fabrik-lifecycle.md (Touches) · docs/reference/modules/drivers.md (Touches) · CHANGELOG + STRATEGIC_BACKLOG rows for the migrate-only env file and the shared-database cutover (Deltas)

## Touches
- src/fabrik/orchestrator/infrastructure.py — PRIMARY PATH
- src/fabrik/orchestrator/deployer_ssh.py
- tests/test_app_role_provision.py
- tests/orchestrator/test_deployer_ssh.py
- docs/operations/fabrik-lifecycle.md
- docs/reference/modules/drivers.md

## Behavior Contract
- **Given** a fresh create, **When** `_provision_postgres` runs with a call recorder, **Then** the first `inject_env` carries `DATABASE_URL` and `DATABASE_URL_OWNER`, both with the owner as user and the host rewritten by `_rewrite_shared_infra_host`, and it happens BEFORE `ensure_app_role` is called; with `ensure_app_role` raising a `RuntimeError` (a `_run_sql` failure — not `AppRoleError`, whose flag-false case is the skipped row below), that owner injection has still happened and `ctx.registrar_failures` gains one `app-role:` entry (src/fabrik/orchestrator/infrastructure.py:633; spec-fed: `spec § 2`)
- **Given** a raw spec dict with no `database_url_app_role` key, **When** the step runs, **Then** the flag reads `False` with no `KeyError`, the app role is still minted, and no check runs; when `ensure_app_role` raises `AppRoleError` there (a legacy database owned by `postgres`), resource `app-role` is recorded `skipped` naming the owner and no registrar failure is added (src/fabrik/orchestrator/infrastructure.py:232)
- **Given** the flag `true` and a `.env` whose `DATABASE_URL` is `postgresql+asyncpg://<owner>:pw@10.99.0.1:5432/<db>?ssl=require` and has no `DATABASE_URL_OWNER`, **When** the step runs with a passing check, **Then** `ensure_app_role(reset_password=True)` is called and ONE `inject_env` carries `DATABASE_URL` = the same scheme, host, port, database and query with user `<db>_app` and the new password, and `DATABASE_URL_OWNER` = the old value; with a failing check nothing is injected and `ctx.registrar_failures` gains one `app-role:` entry listing each failure (src/fabrik/orchestrator/infrastructure.py:426)
- **Given** the flag `false` and a `.env` whose `DATABASE_URL` user is `<db>_app`, **When** the step runs, **Then** `inject_env` receives `DATABASE_URL` = the `DATABASE_URL_OWNER` value; when `DATABASE_URL_OWNER` is absent it injects nothing and records a registrar failure (src/fabrik/orchestrator/infrastructure.py:652)
- **Given** the flag `true` and a `.env` with no `DATABASE_URL`, or one whose user is `postgres`, or a second spec in the specs dir resolving to the same `db_name`, **When** the step runs, **Then** nothing is injected, no password is reset, and one registrar failure names the user found or the sibling specs — never the DSN (src/fabrik/orchestrator/infrastructure.py:574)
- **Given** a re-apply where the flag matches the current `DATABASE_URL` user, **When** the step runs, **Then** `ensure_app_role` is called once with `reset_password=False`, after the watchdog-role and payments steps; `inject_env` is not called while `DATABASE_URL_OWNER` is present; when it is absent and the user is the owner one `inject_env` backfills it from `DATABASE_URL`, and when it is absent and the user is `<db>_app` a registrar failure names the missing rollback DSN (src/fabrik/orchestrator/infrastructure.py:652)
- **Given** `SSHDeployer.read_env(ctx)` against a fake `_ssh`, **When** it runs, **Then** it returns the parsed dict for a present file, `{}` when `test -f` reports absence, raises `DeployError` when the ssh call fails, and runs inside `_target_vps_env(ctx)`; `inject_env` still merges exactly as before (src/fabrik/orchestrator/deployer_ssh.py:258)
- **Given** a dry-run apply, **When** the step runs, **Then** no ssh, no SQL and no check is invoked and resource `app-role` is recorded with status `dry_run` (src/fabrik/drivers/postgres.py:133)

## Context Files
- .windsurf/rules/core/30-ops.md
- .windsurf/rules/core/35-security-auth.md
- src/fabrik/orchestrator/infrastructure.py
- src/fabrik/orchestrator/deployer_ssh.py
- src/fabrik/app_role_check.py
- tests/test_payments_ingest_role.py
- docs/operations/fabrik-lifecycle.md
- docs/reference/modules/drivers.md
- docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md
