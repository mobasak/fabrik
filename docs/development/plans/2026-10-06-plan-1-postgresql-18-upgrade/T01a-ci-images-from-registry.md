# T01a — The CI scaffold derives its Postgres images from the version registry

Depends: —
Parallel: ⚡
Complexity: complex
Appetite: 75
Gate: python -m pytest tests/test_ci_scaffold.py tests/test_scaffold_test_db_guard.py -q
Docs: none (CHANGELOG is the orchestrator's)

## Scope
Implements spec § The delta › D3 (the `ci_scaffold.py` bullet). `CiConfig.pg_image()` (`src/fabrik/ci_scaffold.py:47-48`) stops returning the two literals at `src/fabrik/ci_scaffold.py:33-34` and derives `postgres:<postgres_major>` and `pgvector/pgvector:<pgvector_version>-pg<postgres_major>` from `.windsurf/rules/versions.yaml` at CALL time, through `fabrik.version_registry` (`src/fabrik/version_registry.py:22,33`) without adding either key to `REQUIRED_KEYS` (`src/fabrik/version_registry.py:26` — the spec leaves it alone), so `scripts/backfill_ci.py:31` and `src/fabrik/scaffold.py:1142` still import the module when the registry is broken; a missing or blank key raises `VersionRegistryError` naming the key — never a silent default. DO-NOT: edit `.windsurf/rules/versions.yaml` (a governance-sync path — infra adds the key, see the precondition gate), or `scripts/sysadmin/rules_render_versions.py` (T01b's).

## Touches
- src/fabrik/ci_scaffold.py — PRIMARY PATH
- tests/test_ci_scaffold.py

## Behavior Contract
- **Given** `fabrik.version_registry.VERSIONS_FILE` monkeypatched to a registry with `postgres_major: "16"` and `pgvector_version: "0.8.6"`, **When** `ci_files` renders a config with and without `db_extensions=("pgvector",)`, **Then** the workflow and the local script both name `pgvector/pgvector:0.8.6-pg16` and `postgres:16` respectively (src/fabrik/ci_scaffold.py:47; spec § The delta › D3)
- **Given** `VERSIONS_FILE` monkeypatched to a registry with `postgres_major: "18"`, **When** the same configs render, **Then** they name `pgvector/pgvector:0.8.6-pg18` and `postgres:18` (spec § The delta › D3)
- **Given** `VERSIONS_FILE` monkeypatched to a registry lacking `pgvector_version`, **When** `fabrik.ci_scaffold` is reloaded with `importlib.reload`, **Then** the reload succeeds, and **When** `pg_image()` runs for a pgvector config, **Then** it raises `VersionRegistryError` naming `pgvector_version` (src/fabrik/version_registry.py:22)
- **Given** the live `.windsurf/rules/versions.yaml`, **When** it is loaded, **Then** it carries non-empty `postgres_major` and `pgvector_version` (the only test bound to the live registry, so infra's later flip to 18 never reds the others) (spec § The delta › D3)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
- src/fabrik/version_registry.py
- src/fabrik/ci_scaffold.py
- tests/test_ci_scaffold.py
- scripts/backfill_ci.py
