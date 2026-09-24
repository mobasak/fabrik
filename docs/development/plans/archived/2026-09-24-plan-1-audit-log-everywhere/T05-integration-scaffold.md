# T05 — Integration: the scaffolder emits the module, table, revokes and jobs; the whole-plan receipt

## Scope
Integration: true. Implements spec § 3 under D-390 (4): a Python backend WITH a database — saas-skeleton, python-api, python-api-gpu, file-worker, and the `server/` of office-extension, chrome-extension, mobile-app and static-site — gets all of (1). Which of those types emit a database, and which emit the saas worker's beat loop, is read from `scaffold.py` per type during the ticket, never assumed.

### (1) The indivisible over-budget file, `src/fabrik/scaffold.py` (280 KB)

- **Module.** Vendor `/opt/fabrik-lib/app-audit-log` into `libs/audit_log/` beside the package (`server/libs/audit_log/` for a `server/` backend). Use a `_vendor_app_audit_log` helper shaped like `_vendor_fastapi_user_auth` (:3290): fail loud when the module is missing; copy with `ignore_patterns("__pycache__", "*.pyc", ".mypy_cache", ".pytest_cache", ".ruff_cache", "test_*.py", "UPSTREAM_FEEDBACK.md")`. The module's own dev artefacts are those caches plus `test_audit_log.py`, not the `conftest.py`/`pytest.ini` the auth helper excludes.
- **Schema.** Fold the module's `schema.sql` into the backend's schema file: `_SAAS_SCHEMA_SQL` (:2111), and the placeholder `db/schema.sql` (:1484) for the other types with a database.
  - The fold adds `CREATE TABLE audit_log`, its indexes and view, then `DO` blocks that revoke `UPDATE, DELETE, TRUNCATE ON audit_log` from `current_database() || '_app'`, `current_database() || '_wd_rw'` and each of `anon`/`authenticated`/`service_role`, each guarded by the role existing in `pg_roles`. `current_database()` is by construction the registrar's database name, `depends.postgres` override included (`src/fabrik/orchestrator/infrastructure.py:574-580`); a name baked at scaffold time is not.
  - The header becomes `psql -1 -v ON_ERROR_STOP=1 "$DATABASE_URL_OWNER" -f db/schema.sql` (:2113): the WHOLE file is one transaction and any error aborts it. `psql -f` otherwise autocommits per statement; the file therefore carries no top-level `BEGIN`/`COMMIT` of its own, since an inner `COMMIT` would commit `-1`'s outer transaction early (measured in review pass 2).
- **Writer.** Replace `_LogAuditLogger` (:2476, used at :2498) with an adapter implementing the pack's async recipe (`core/app-audit-log.md:215-222`): in ONE transaction of the app's async session — `pg_advisory_xact_lock(AUDIT_CHAIN_LOCK_KEY)` (the module's constant), the tip read as `_select_tip` does, the `ts` clamp against the tip, `str()` coercion of `target_*`, the module's `canonical_payload`/`sha256_hex`, then the INSERT — then commit.
- **Jobs.**
  - An `audit_jobs` module with two entry points: retention runs the module's `data_retention.sql`; the weekly verify runs `verify_chain(strict=True)` from a cursor persisted in a one-row table, plus the `has_table_privilege` ownership and privilege checks.
  - Both connect through a Settings field reading `DATABASE_URL_OWNER` (`core/25-data-postgres.md:331`), with no default. When it is absent — first boot, before the registrar has injected it — the jobs log `audit_jobs: not_configured` and idle, never crash. That is the same absent-until-injected rule `_write_saas_compose` documents at :3081-3089, which is why no compose `environment:` override is emitted.
  - Scheduling: the saas beat loop (:2773-2804) schedules both. Every other Python backend declares a companion in its generated spec, the canonical mechanism (`core/30-ops.md:161`, rendered by `templates/_partials/_companion_service.yaml.j2`): `companion_services: [{id: <name>-audit-jobs, command: [...], memory: <measured>}]`, added in `src/fabrik/spec_generator.py` for those types when `use_database`. The companion shares the app's env unchanged and needs no override, because the jobs read `DATABASE_URL_OWNER` themselves.
- **Env and requirements.** `.env.example` names `DATABASE_URL` and `DATABASE_URL_OWNER` with no defaults in code. This fixes the no-op replace at :1975-1977 and the saas family's missing `DATABASE_URL`. The backend's `requirements.txt` gains `psycopg[binary]`.

For the other types:
- node-api and file-api with a database get the table and revokes only.
- desktop-app, docusaurus and database-less file-worker get nothing.
- **Deferred, not dropped:** `core/app-audit-log.md:50-52` says a Node project owes a writer hashing byte-identically to `canonical_payload` until fabrik-lib's Node port lands. The scaffolder does not author that writer here — it would fork the module's hashing in a second language inside the hub. The spine's § Residual unknowns names the destination.

`tests/test_scaffold_audit_log.py` covers each type, the no-window row and the writer row (importing T02's `scratch_pg`). Extend `tests/test_scaffold_saas_backend.py` where the stub assertion lives.

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
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_scaffold_audit_log.py tests/test_scaffold_saas_backend.py tests/test_scaffold_spec_generation.py tests/test_spec_generator.py -q && python scripts/final_gate.py --check --json
Docs: docs/CONFIGURATION.md + templates (Touches — new env var) · CHANGELOG + INDEX (new test files, new module) + LESSONS_LEARNT + DECISIONS built-at row (Deltas)

## Touches
- docs/development/reviews/2026-09-24-plan-1-audit-log-everywhere-review.md
- src/fabrik/scaffold.py
- src/fabrik/spec_generator.py
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
- **Given** each Python-backed scaffold type (saas-skeleton, python-api, python-api-gpu, file-worker, and the `server/` of office-extension, chrome-extension, mobile-app and static-site) emitted into a scratch dir with a database, **When** the tree is inspected, **Then** `libs/audit_log/` (or `server/libs/audit_log/`) is vendored with no cache directory and no `test_*.py`, the schema file carries the `audit_log` table and, after it, the guarded revokes naming `current_database() || '_app'`, `current_database() || '_wd_rw'` and the three group roles, its header says `psql -1 -v ON_ERROR_STOP=1 "$DATABASE_URL_OWNER"` and the file carries no top-level `BEGIN`/`COMMIT` of its own, `_LogAuditLogger` is gone, and `.env.example` names `DATABASE_URL` and `DATABASE_URL_OWNER` (src/fabrik/scaffold.py:2111; spec-fed: `spec § 3`)
- **Given** node-api and file-api with a database, **When** emitted, **Then** the schema carries the table and revokes and no Python module; desktop-app and docusaurus emit neither; file-worker without a database emits neither (src/fabrik/scaffold.py:1484)
- **Given** a scaffolded saas-skeleton, **When** its worker is read, **Then** the beat loop schedules retention and the weekly verify (src/fabrik/scaffold.py:2773)
- **Given** a scaffolded python-api `--db`, **When** its generated spec and rendered compose are read, **Then** `companion_services` carries `<name>-audit-jobs` with a `memory` and no `env_overrides`, and the compose service renders from the partial with the app's env unchanged (src/fabrik/spec_generator.py:381)
- **Given** the emitted `audit_jobs` with `DATABASE_URL_OWNER` unset, **When** it starts, **Then** it logs `audit_jobs: not_configured` and keeps running instead of exiting non-zero (src/fabrik/scaffold.py:3081)
- **Given** the emitted schema applied to a scratch PostgreSQL 16 exactly as its header says (`psql -1 -v ON_ERROR_STOP=1 … -f`) as the owner, with the app role minted by T02, **When** a LOGIN session as the app role tries `UPDATE` on `audit_log` immediately after, **Then** it is refused; and a copy of the file with a failing statement appended after the audit block exits non-zero and leaves no `audit_log` table at all (src/fabrik/scaffold.py:2113; spec-fed: `spec § 1 No window`)
- **Given** the emitted writer adapter against that scratch database, **When** two writes run concurrently, **Then** `verify_chain(strict=True)` over the table returns no break (src/fabrik/scaffold.py:2476)

## Context Files
- .windsurf/rules/core/app-audit-log.md
- .windsurf/rules/core/30-ops.md
- src/fabrik/scaffold.py
- src/fabrik/spec_generator.py
- templates/_partials/_companion_service.yaml.j2
- tests/test_scaffold_saas_backend.py
- tests/test_app_role_real_pg.py
- docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md
