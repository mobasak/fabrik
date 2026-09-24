# T03 — Pre-cutover check: ownership + privilege probe + repo scan, and `fabrik app-role-check`

## Scope
New module `src/fabrik/app_role_check.py`. Implements spec § 2 "pre-cutover check", with the patterns settled in D-390 and widened by this plan's review.

**`scan_repo(repo_dir: Path) -> ScanResult(files_scanned: int, findings: list[Finding])`**, where `Finding(path: str, line: int, pattern: str)`.

- **What it walks:** `*.py *.ts *.js *.mjs *.sh`, `Makefile`, compose files (`compose.yaml`, `compose.*.yaml`, `docker-compose*.yml`), `Dockerfile*`, `entrypoint*`, `package.json` and every `env.py` under an `alembic/` directory.
- **What it skips:** `tests/ test/ .venv/ venv/ node_modules/ libs/ dist/ build/ .claude/ .git/` (spec § Derivations D1's exclusions).
- **`*.sql` files are not scanned for DDL text.** They are schema data applied by someone, and `db/schema.sql` is owner-applied by design. The scan finds the INVOCATION that applies them instead.
- **Patterns** (case-insensitive):
  - runtime DDL: `\b(create|alter|drop)\s+(unique\s+)?(table|index|extension|view|function|schema|type|sequence)\b`, `\bcreate_all\b` (also when passed bare, as in `conn.run_sync(metadata.create_all)`), `op.create_table`, `.sync(`;
  - migration tools: `alembic (upgrade|downgrade)`, `prisma (migrate|db push)`, `drizzle-kit push`, `manage.py migrate`, and an alembic `env.py` whose connection source is `DATABASE_URL`;
  - `psql` invocations;
  - a compose service named `migrate`;
  - a compose service that sets `DATABASE_URL` under `environment:` — that value overrides `.env`, so a cutover of `.env` would not reach the container.
- **Suppression.** A finding is suppressed only when its line — after stripping a trailing `#`, `--` or `//` comment — or its compose service's `environment`/`command` names `DATABASE_URL_OWNER` as the connection source. A comment token is the cheapest way to satisfy the check without changing the connection, so it never suppresses; write that sentence into the module docstring.

**`run_check(db_name: str, repo_dir: Path, container: str = POSTGRES_CONTAINER) -> CheckResult(ok, failures)`:**
- It calls T02's `probe_app_role` and carries each failure verbatim; T02's `AppRoleError` becomes a failure string.
- It adds one failure per finding (`<path>:<line> <pattern> reaches DATABASE_URL`).
- Fail closed, never pass on nothing:
  - a missing `repo_dir` → `"no repo at <path> — cannot scan"`;
  - `files_scanned == 0` → `"scanned 0 files under <path>"`;
  - a clone whose `HEAD` differs from its upstream after `git -C <repo> fetch -q` → `"stale clone: HEAD <sha> != upstream <sha>"`, because deploys pull the remote (`core/30-ops.md` § redeploy) and a stale hub clone would scan old code;
  - no upstream at all → a failure too.
- These are the cobra counters: a scan that finds nothing because it looked at nothing, or at old code, must not pass.

**CLI `fabrik app-role-check --spec <path>`**, registered like `audit-registrars` (`src/fabrik/cli.py:1370`):
- `db_name` comes from the registrar's rule: `depends.postgres`, else the spec id with `-` → `_` (`src/fabrik/orchestrator/infrastructure.py:574-580`).
- `repo_dir` is `Path("/opt") / (spec.get("id") or spec.get("name"))` — the orchestrator's own `/opt` precedence (`_load_secrets`), shared with T04 through one helper `project_repo_dir(spec) -> Path` exported from this module.
- It prints `✓` or one `✗` line per failure, and exits 0 or 1.

The symbols it consumes from `src/fabrik/drivers/postgres.py` (`probe_app_role`, `AppRoleError`, `POSTGRES_CONTAINER`) are defined in the spine § Interfaces, and the db-name rule is spelled out above, so neither 72 KB driver nor the 53 KB orchestrator is in the read set.

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
- **Given** a scratch repo holding `app/db.py` with `await conn.run_sync(metadata.create_all)`, `app/models.py` with a lowercase `create unique index`, an `alembic/env.py` reading `DATABASE_URL`, a compose `migrate` service running `alembic upgrade head`, an `entrypoint.sh` running `psql "$DATABASE_URL" -f db/schema.sql`, a compose service with `DATABASE_URL` under `environment:`, and a `db/schema.sql` full of `CREATE TABLE`, **When** `scan_repo` runs, **Then** it returns one finding per site with path, line and pattern, none for `db/schema.sql`, and none for the same text under `tests/`, `.venv/`, `node_modules/` and `libs/` (src/fabrik/app_role_check.py:1; spec-fed: `spec § Derivations D1`)
- **Given** the same repo after every one of those sites takes `DATABASE_URL_OWNER` as its connection source, **When** `scan_repo` runs, **Then** it returns no findings; a line naming `DATABASE_URL_OWNER` only after a `#`, `--` or `//` comment marker is still a finding (src/fabrik/app_role_check.py:1)
- **Given** `run_check` with a passing probe, **When** the repo dir does not exist, or holds no walkable file, or its `HEAD` differs from its upstream after fetch, **Then** `ok` is `False` and the failure names which; with a failing probe or a probe raising `AppRoleError` and a clean current repo, the probe's failures are carried verbatim (tests/test_app_role_check.py:1)
- **Given** a spec whose `id` and `name` differ, **When** `project_repo_dir(spec)` runs, **Then** it returns `/opt/<id>` — the orchestrator's `_load_secrets` precedence (src/fabrik/orchestrator/__init__.py:384)
- **Given** `fabrik app-role-check --spec specs/services/<id>.yaml` with the check monkeypatched to fail, **When** the CLI runs, **Then** it prints one `✗` line per failure and exits 1; a passing check prints `✓` and exits 0 (src/fabrik/cli.py:1370)

## Context Files
- .windsurf/rules/core/10-python.md
- src/fabrik/cli.py
- docs/QUICKSTART.md
- docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md
