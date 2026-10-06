# T01 — The CI scaffold derives its Postgres images from the version registry

Depends: —
Parallel: ⚡
Complexity: complex
Appetite: 90
Gate: python -m pytest tests/test_ci_scaffold.py tests/sysadmin/test_rules_render_versions.py -q
Docs: none (CHANGELOG is the orchestrator's)

## Scope
Implements spec § The delta › D3 (the `ci_scaffold.py` and `_LOOSE` bullets). `CiConfig.pg_image()` (`src/fabrik/ci_scaffold.py:47-48`) stops returning the two literals at `src/fabrik/ci_scaffold.py:33-34` and derives `postgres:<postgres_major>` and `pgvector/pgvector:<pgvector_version>-pg<postgres_major>` from `.windsurf/rules/versions.yaml` at CALL time, through `fabrik.version_registry` (`src/fabrik/version_registry.py:22,33`) without adding either key to `REQUIRED_KEYS` (`src/fabrik/version_registry.py:26` — the spec leaves it alone), so `scripts/backfill_ci.py:31` and `src/fabrik/scaffold.py:1142` still import the module when the registry is broken; a missing or blank key raises `VersionRegistryError` naming the key — never a silent default. `_LOOSE` (`scripts/sysadmin/rules_render_versions.py:36-51`) gains the `postgres:N(.N)?-alpine` and `pgvector:X.Y.Z-pgN` shapes. DO-NOT: edit `.windsurf/rules/versions.yaml` (a governance-sync path — infra adds the key, see the precondition gate).

## Touches
- src/fabrik/ci_scaffold.py — PRIMARY PATH
- tests/test_ci_scaffold.py
- scripts/sysadmin/rules_render_versions.py
- tests/sysadmin/test_rules_render_versions.py

## Behavior Contract
- **Given** a registry with `postgres_major: "16"` and `pgvector_version: "0.8.6"`, **When** `ci_files` renders a config with and without `db_extensions=("pgvector",)`, **Then** the workflow and the local script both name `pgvector/pgvector:0.8.6-pg16` and `postgres:16` respectively (src/fabrik/ci_scaffold.py:47; spec § The delta › D3)
- **Given** the registry path monkeypatched to one with `postgres_major: "18"`, **When** the same configs render, **Then** they name `pgvector/pgvector:0.8.6-pg18` and `postgres:18` (spec § The delta › D3)
- **Given** a registry lacking `pgvector_version`, **When** `fabrik.ci_scaffold` is imported, **Then** the import succeeds, and **When** `pg_image()` runs for a pgvector config, **Then** it raises `VersionRegistryError` naming `pgvector_version` (src/fabrik/version_registry.py:33)
- **Given** the strings `postgres:18-alpine`, `postgres:18.6-alpine` and `pgvector/pgvector:0.8.6-pg18`, **When** `_LOOSE` searches each, **Then** each matches, and the existing `PostgreSQL 16` and `pgvector:pg16` cases still match (scripts/sysadmin/rules_render_versions.py:36)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
- src/fabrik/version_registry.py
- src/fabrik/ci_scaffold.py
- tests/test_ci_scaffold.py
- scripts/sysadmin/rules_render_versions.py
- tests/sysadmin/test_rules_render_versions.py
- scripts/backfill_ci.py
