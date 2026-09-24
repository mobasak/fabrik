# T03 — Pre-cutover check: ownership + privilege probe + repo scan, and `fabrik app-role-check`

## Scope
New module `src/fabrik/app_role_check.py`. Implements spec § 2 "pre-cutover check", with the patterns settled in D-390.

`scan_repo(repo_dir: Path) -> list[Finding]`:
- `Finding(path: str, line: int, pattern: str)`.
- It walks `*.py *.ts *.js *.sh *.sql`, compose files (`compose.yaml`, `compose.*.yaml`, `docker-compose*.yml`), `Dockerfile*`, `entrypoint*` and `package.json`.
- It skips `tests/ test/ .venv/ venv/ node_modules/ libs/ dist/ build/ .claude/ .git/` (spec § Derivations D1's exclusions).
- Patterns:
  - `CREATE TABLE|ALTER TABLE|CREATE EXTENSION|CREATE INDEX`, but not under `alembic/` or `migrations/` (those are caught as a migration tool below);
  - `alembic (upgrade|downgrade)`, an `alembic.ini` present;
  - `prisma migrate`, `prisma db push`;
  - `psql` invocations;
  - a compose service named `migrate`.
- A finding is suppressed when its line, or its compose service's `environment`/`command`, names `DATABASE_URL_OWNER`.

`run_check(db_name, owner, repo_dir, container=POSTGRES_CONTAINER) -> CheckResult(ok, failures)`:
- It calls T02's `probe_app_role` and carries each failure verbatim.
- It adds one failure per scan finding (`<path>:<line> <pattern> reaches DATABASE_URL`).
- A missing `repo_dir` is a failure, never a pass. This is the cobra counter: a scan that finds nothing because it looked at nothing must not pass. Write that sentence into the module docstring.

New CLI command `fabrik app-role-check --spec <path>`, registered like `audit-registrars` (`src/fabrik/cli.py:1370`):
- It derives `db_name` with the registrar's rule: `depends.postgres`, else the spec id with `-` → `_`, as at `src/fabrik/orchestrator/infrastructure.py:574-580`.
- It derives the owner as `db_name` (:614) and `repo_dir` as `Path("/opt") / <spec id>` (the `_PROJECTS_ROOT` precedent, `src/fabrik/drivers/watchdog.py:247`).
- It prints `✓` or one `✗` line per failure, and exits 0 or 1.

DO-NOT: switch any DSN or write any `.env` (T04); edit `postgres.py`.

Depends: T02
Parallel: ⛓️
Complexity: complex
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_app_role_check.py -q
Docs: CHANGELOG (Deltas) · docs/QUICKSTART.md (Touches — the new CLI command, API/SDK/CLI row of the Doc Sync Matrix)

## Touches
- src/fabrik/app_role_check.py — PRIMARY PATH
- src/fabrik/cli.py
- tests/test_app_role_check.py
- docs/QUICKSTART.md

## Behavior Contract
- **Given** a scratch repo holding `app/db.py` with `CREATE TABLE`, an `alembic.ini`, a compose `migrate` service running `alembic upgrade head`, and an entrypoint running `psql "$DATABASE_URL"`, **When** `scan_repo` runs, **Then** it returns one finding per file with path, line and pattern, and ignores the same text under `tests/`, `.venv/`, `node_modules/` and `libs/` (src/fabrik/app_role_check.py:1; spec-fed: `spec § Derivations D1`)
- **Given** the same repo after every DDL and migration site reads `DATABASE_URL_OWNER` (the finding line or its compose service names `DATABASE_URL_OWNER`), **When** `scan_repo` runs, **Then** it returns `[]` (src/fabrik/app_role_check.py:1)
- **Given** `run_check` with a passing probe but a repo dir that does not exist, **When** it runs, **Then** `ok` is `False` and the failures name the missing repo; with a failing probe and a clean repo, the probe's failures are carried verbatim (tests/test_app_role_check.py:1)
- **Given** `fabrik app-role-check --spec specs/services/<id>.yaml` with the check monkeypatched to fail, **When** the CLI runs, **Then** it prints one `✗` line per failure and exits 1; a passing check prints `✓` and exits 0 (src/fabrik/cli.py:1370)

## Context Files
- .windsurf/rules/core/10-python.md
- src/fabrik/cli.py
- src/fabrik/drivers/watchdog.py
- docs/QUICKSTART.md
- tests/test_app_role_driver.py
- docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md
