# T05 — Integration: the scaffolder emits the module, table, revokes and jobs; the whole-plan receipt

## Scope
Integration: true. Implements spec § 3 under D-390 (4).

### (1) The indivisible over-budget file, `src/fabrik/scaffold.py` (280 KB)

For every Python backend emitted WITH a database:

- **Module.** Vendor `/opt/fabrik-lib/app-audit-log` into `libs/audit_log/` beside the package (`server/libs/audit_log/` for a `server/` backend). Copy with a `_vendor_app_audit_log` helper modelled on `_vendor_fastapi_user_auth` (:3290), which excludes tests and `__pycache__` and fails loud when the module is missing.
- **Schema.** Fold the module's `schema.sql` into the backend's schema file: `_SAAS_SCHEMA_SQL` (:2111), and the placeholder `db/schema.sql` (:1484) for python-api and python-api-gpu with `--db`.
  - The header becomes `psql "$DATABASE_URL_OWNER" -f db/schema.sql` (:2113).
  - The fold ends, inside the same `BEGIN … COMMIT` as the `CREATE TABLE`, with `DO` blocks that revoke `UPDATE, DELETE, TRUNCATE ON audit_log` from `"<db>_app"`, `"<db>_wd_rw"` and each of `anon`/`authenticated`/`service_role`, each guarded by the role existing in `pg_roles`.
  - `<db>` is the registrar's rule (the project name with `-` → `_`).
- **Writer.** Replace `_LogAuditLogger` (:2476, used at :2498) with an adapter that writes through the module under `AUDIT_CHAIN_LOCK_KEY`, following the pack's async recipe (`core/app-audit-log.md:215-222`).
- **Jobs.**
  - Add an `audit_jobs` module with two entry points: retention runs the module's `data_retention.sql` on `DATABASE_URL_OWNER`; the weekly verify runs `verify_chain(strict=True)` from a cursor persisted in a one-row table, plus the `has_table_privilege` ownership and privilege check.
  - The saas beat loop (:2773-2804) schedules both.
  - Every other Python backend gets a `jobs` companion service in its compose (`_write_canonical_compose` :902), sharing the image and overriding `command`, `container_name`, `deploy.resources.limits.memory` (measured: § Residual unknowns) and `environment: DATABASE_URL: ${DATABASE_URL_OWNER}`.
- **Env and requirements.** `.env.example` names `DATABASE_URL` and `DATABASE_URL_OWNER`, with no defaults in code. This fixes the no-op replace at :1975-1977 and the saas family's missing `DATABASE_URL`. The backend's `requirements.txt` gains `psycopg[binary]`.

For the other types:
- node-api and file-api with a database get the table and revokes only.
- desktop-app, docusaurus and database-less file-worker get nothing.

`tests/test_scaffold_audit_log.py` covers each type plus the no-window real-PG row (importing T02's `scratch_pg`). Extend `tests/test_scaffold_saas_backend.py` where the stub assertion lives.

### (2) Templates and hub env docs

- `docs/CONFIGURATION.md` (hub) gets `DATABASE_URL_OWNER` and `shape.database_url_app_role` (moved here from T04 for T04's READ budget), including the shared-`.env` limit T04 writes into `docs/operations/fabrik-lifecycle.md`.
- `templates/scaffold/docs/CONFIGURATION_TEMPLATE.md` gains `DATABASE_URL_OWNER`.
- `templates/scaffold/docs/OPERATIONS_TEMPLATE.md` and `RESILIENCE_TEMPLATE.md` §7 list the two jobs.
- The three type `.env.example` templates (`templates/saas-skeleton/.env.example`, `templates/mobile-app/.env.example`, `templates/node-api/.env.example`) name both DSNs.

### (3) The receipt `docs/development/reviews/2026-09-24-plan-1-audit-log-everywhere-review.md`

It records:
- the whole-plan `check_doc_sync.py --range`, `check_doc_stubs.py --range`, `python scripts/final_gate.py --check --json` and `check_convergence.py` outputs;
- the cross-ticket seam-test run;
- the companion memory measurement;
- the mail to infra naming the stale pack caveats (`core/app-audit-log.md:26-36`, `:40-41`).

DO-NOT: vendor into the hub itself; touch `libs/subagents/` (D-137); edit any live project repo (the waves are a follow-up plan).

Depends: T04
Parallel: ⛓️
Complexity: native
Integration: true
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_scaffold_audit_log.py tests/test_scaffold_saas_backend.py tests/test_scaffold_spec_generation.py -q && python scripts/final_gate.py --check --json
Docs: docs/CONFIGURATION.md + templates (Touches — new env var) · CHANGELOG + INDEX (new test files, new module) + LESSONS_LEARNT + DECISIONS built-at row (Deltas)

## Touches
- docs/development/reviews/2026-09-24-plan-1-audit-log-everywhere-review.md
- src/fabrik/scaffold.py
- docs/CONFIGURATION.md
- templates/scaffold/docs/CONFIGURATION_TEMPLATE.md
- templates/scaffold/docs/OPERATIONS_TEMPLATE.md
- templates/scaffold/docs/RESILIENCE_TEMPLATE.md
- templates/saas-skeleton/.env.example
- templates/mobile-app/.env.example
- templates/node-api/.env.example
- tests/test_scaffold_audit_log.py
- tests/test_scaffold_saas_backend.py

## Behavior Contract
- **Given** each Python-backed scaffold type (saas-skeleton, python-api, python-api-gpu, and the `server/` of office-extension, chrome-extension, mobile-app and static-site) emitted into a scratch dir with a database, **When** the tree is inspected, **Then** every Python backend has `libs/audit_log/` (or `server/libs/audit_log/`) vendored, its schema file carries the `audit_log` table and the guarded revokes naming `<db>_app`, `<db>_wd_rw` and the group roles, its header says `psql "$DATABASE_URL_OWNER"`, the stdout `_LogAuditLogger` is gone, retention and weekly verify are scheduled, and `.env.example` names `DATABASE_URL` and `DATABASE_URL_OWNER` (src/fabrik/scaffold.py:2111; spec-fed: `spec § 3`)
- **Given** node-api and file-api with a database, **When** emitted, **Then** the schema carries the table and revokes and no Python module; desktop-app and docusaurus emit neither; file-worker without a database emits neither (src/fabrik/scaffold.py:1484)
- **Given** a scaffolded python-api `--db` project, **When** its compose is read, **Then** a `jobs` companion service shares the app image, overrides `command`, `container_name` and `deploy.resources.limits.memory`, and sets `DATABASE_URL=${DATABASE_URL_OWNER}` in its own `environment` (src/fabrik/scaffold.py:902)
- **Given** the emitted schema applied to a scratch PostgreSQL 16 as the owner in one transaction, with the app role minted, **When** the app role tries `UPDATE` on `audit_log` immediately after, **Then** it is refused — no default-privilege window (src/fabrik/scaffold.py:2111; spec-fed: `spec § 1 No window`)

## Context Files
- .windsurf/rules/core/app-audit-log.md
- .windsurf/rules/core/30-ops.md
- src/fabrik/scaffold.py
- tests/test_scaffold_saas_backend.py
- tests/test_app_role_real_pg.py
- docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md
