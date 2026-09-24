# T01 — `shape.database_url_app_role`: the cutover flag and its generator default

## Scope
Add `database_url_app_role: bool = Field(default=False, …)` to `Shape` beside `needs_payments_ingest` (`src/fabrik/spec_loader.py:333-345`). Its description says: true means the project's `DATABASE_URL` is the non-owner `<db>_app` role and the owner DSN is `DATABASE_URL_OWNER`; each `fabrik apply` converges `.env` to it; setting it on an existing project is a cutover, guarded by the pre-cutover check; unsetting it is the rollback. Add a model validator that refuses it without `needs_database`, mirroring `_payments_ingest_needs_database` (:380-389). In `generate_spec`, whenever the emitted shape has `needs_database` true — type defaults or the `use_database` overlay (`src/fabrik/spec_generator.py:381-382`) — also set `database_url_app_role: true`, so every new database project is born on the app role. `_build_shape_for_type` can return `None` (`src/fabrik/spec_generator.py:187-201`) while `use_database` still emits `depends.postgres`; the last Behavior row pins that no enabled type does. Implements spec § 2 and D-390 (1)(2). DO-NOT: touch any existing `specs/services/*.yaml`; touch the registrar or scaffolder.

Depends: —
Parallel: ⚡
Complexity: simple
Gate: /opt/fabrik/.venv/bin/python -m pytest tests/test_spec_loader.py tests/test_spec_generator.py -q
Docs: CHANGELOG (Deltas) · none other — T04 documents the field in docs/CONFIGURATION.md with the step that reads it

## Touches
- src/fabrik/spec_loader.py — PRIMARY PATH
- src/fabrik/spec_generator.py
- tests/test_spec_loader.py
- tests/test_spec_generator.py

## Behavior Contract
- **Given** a spec with `shape.database_url_app_role: true` and `needs_database: false`, **When** it is loaded, **Then** validation fails naming `database_url_app_role requires needs_database: true` (src/fabrik/spec_loader.py:380; spec-fed: `spec § 2`)
- **Given** a spec with no `database_url_app_role` key, **When** it is loaded, **Then** the field is `False` — an existing spec is never switched by an upgrade (src/fabrik/spec_loader.py:333)
- **Given** `generate_spec` for a type whose defaults set `needs_database`, or any type with `use_database=True`, **When** the spec is emitted, **Then** `shape.database_url_app_role` is `true`; a spec without a database carries `false` (src/fabrik/spec_generator.py:381)
- **Given** every type in `SPEC_ENABLED_TYPES`, **When** `generate_spec(type, use_database=True)` runs, **Then** the emitted shape is not `None` and carries `database_url_app_role: true` — a type whose `templates/<type>/defaults.yaml` has no `shape:` block fails this test instead of silently shipping an owner DSN (src/fabrik/spec_generator.py:381)

## Context Files
- .windsurf/rules/core/10-python.md
- src/fabrik/spec_loader.py
- src/fabrik/spec_generator.py
- tests/test_spec_loader.py
- tests/test_spec_generator.py
- docs/superpowers/specs/2026-09-24-audit-log-everywhere-design.md
