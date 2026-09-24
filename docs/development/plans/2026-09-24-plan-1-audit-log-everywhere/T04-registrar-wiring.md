# T04 — Registrar step: DSN injection on create, declarative cutover and rollback, docs

## Scope
Implements spec § 1 "Where it runs" and § 2, with the declarative semantics of D-390 (2)(3).

In `src/fabrik/orchestrator/deployer_ssh.py`, extract the inline remote-`.env` read of `inject_env` (:280-289) into a public `SSHDeployer.read_env(ctx) -> dict[str, str]` (parsed by `_parse_env` :720; `{}` when absent; dry-run returns `{}`). `inject_env` calls it, and its merge behaviour is unchanged.

In `src/fabrik/orchestrator/infrastructure.py::_provision_postgres` (:561):
1. **Fresh create** (`create_database` returned a password, :633-644): build the owner DSN as today. Call `ensure_app_role(db_name, owner=db_user)`. Inject, in ONE `inject_env` call, `DATABASE_URL` (the app DSN when `spec["shape"]["database_url_app_role"]` is true, else the owner DSN) and `DATABASE_URL_OWNER` (the owner DSN). Both go through `_rewrite_shared_infra_host`.
2. **Existing database:** call `ensure_app_role` (grants re-applied every apply, AFTER the watchdog-role step so its revoke lands last). Then `read_env(ctx)` and parse the current `DATABASE_URL` user with `urllib.parse.urlsplit`.
   - **Cutover** (flag true, user == owner): `run_check(db_name, db_user, Path("/opt")/name)`. If it passes, call `ensure_app_role(reset_password=True)` and inject `DATABASE_URL`=app DSN plus `DATABASE_URL_OWNER`=the old value. If it fails, inject nothing and record one `app-role:` registrar failure listing each failure.
   - **Rollback** (flag false, user == `<db>_app`): inject `DATABASE_URL`=`DATABASE_URL_OWNER`. If that key is missing, inject nothing and record a registrar failure.
   - **Anything else** (already converged): inject nothing.
3. **Failures:** every exception in this step goes through `self._nonfatal(ctx, "app-role", e)` (:426-436), so the CLI exits 2 (`src/fabrik/cli.py:531-545`).
4. **Logging:** log lines name roles, never DSNs.

Docs:
- `docs/reference/modules/drivers.md` gets the role model: owner vs app vs wd_rw vs group roles, and what each may do on `audit_log`.
- `docs/operations/fabrik-lifecycle.md` gets the cutover and rollback runbook: set the flag, run `fabrik app-role-check`, apply; unset to roll back.
- `docs/operations/fabrik-lifecycle.md` also states the limit: the owner DSN shares the project `.env`, so append-only holds against the app's code paths and SQL injection, not against code execution in the container. (`docs/CONFIGURATION.md` is T05's, for the READ budget.)

DO-NOT: edit any `specs/services/*.yaml`; touch `create_database`'s preserve-on-re-apply rule (:340-342); special-case third-party images by name.

Depends: T01, T02, T03
Parallel: ⛓️
Complexity: never-route
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_app_role_provision.py tests/orchestrator/test_deployer_ssh.py tests/test_payments_ingest_role.py tests/test_watchdog_db_roles.py -q
Docs: docs/operations/fabrik-lifecycle.md (Touches) · docs/reference/modules/drivers.md (Touches) · CHANGELOG + STRATEGIC_BACKLOG row for the migrate-only env file (Deltas)

## Touches
- src/fabrik/orchestrator/infrastructure.py — PRIMARY PATH
- src/fabrik/orchestrator/deployer_ssh.py
- tests/test_app_role_provision.py
- tests/orchestrator/test_deployer_ssh.py
- docs/operations/fabrik-lifecycle.md
- docs/reference/modules/drivers.md

## Behavior Contract
- **Given** a fresh create with `database_url_app_role: true`, **When** `_provision_postgres` runs with fakes, **Then** `inject_env` receives `DATABASE_URL` whose user is `<db>_app` and `DATABASE_URL_OWNER` whose user is the owner, in one call (src/fabrik/orchestrator/infrastructure.py:633; spec-fed: `spec § 2`)
- **Given** a fresh create with the flag `false`, **When** the step runs, **Then** both `DATABASE_URL` and `DATABASE_URL_OWNER` carry the owner DSN, and the app role is still minted (src/fabrik/orchestrator/infrastructure.py:638)
- **Given** an existing database, the flag `true`, and a remote `.env` whose `DATABASE_URL` user is the owner, **When** the step runs with a passing check, **Then** `ensure_app_role(reset_password=True)` is called and `inject_env` receives `DATABASE_URL`=app DSN and `DATABASE_URL_OWNER`=the old `DATABASE_URL` value; with a failing check nothing is injected and `ctx.registrar_failures` gains one `app-role:` entry naming each failure (src/fabrik/orchestrator/infrastructure.py:426)
- **Given** an existing database, the flag `false`, and a remote `.env` whose `DATABASE_URL` user is `<db>_app`, **When** the step runs, **Then** `inject_env` receives `DATABASE_URL`=the `DATABASE_URL_OWNER` value; when `DATABASE_URL_OWNER` is absent it injects nothing and records a registrar failure (src/fabrik/orchestrator/infrastructure.py:701)
- **Given** a re-apply where the flag matches the current `DATABASE_URL` user, **When** the step runs, **Then** no password is reset and `inject_env` is not called — only the grants are re-applied (src/fabrik/drivers/postgres.py:340)
- **Given** `ensure_app_role` raising, **When** the step runs, **Then** the failure lands on `ctx.registrar_failures` via `_nonfatal` and the CLI exits 2 (src/fabrik/cli.py:531)
- **Given** `SSHDeployer.read_env(ctx)` against a fake `_ssh` returning a `.env` body, **When** it runs, **Then** it returns the parsed dict, returns `{}` when the file is absent, and `inject_env` still merges exactly as before (src/fabrik/orchestrator/deployer_ssh.py:258)

## Context Files
- .windsurf/rules/core/30-ops.md
- .windsurf/rules/core/35-security-auth.md
- src/fabrik/orchestrator/infrastructure.py
- src/fabrik/orchestrator/deployer_ssh.py
- tests/test_payments_ingest_role.py
- tests/test_app_role_driver.py
- tests/test_app_role_check.py
- docs/operations/fabrik-lifecycle.md
- docs/reference/modules/drivers.md
- docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md
