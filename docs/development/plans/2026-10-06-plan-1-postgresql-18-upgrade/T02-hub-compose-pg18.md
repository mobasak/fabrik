# T02 — The repo's hub compose files describe the PG18 cluster and exporter

Depends: —
Parallel: ⚡
Complexity: simple
Appetite: 30
Gate: python -m pytest tests/test_infra_vps1_postgres_compose.py -q
Docs: none

## Scope
Implements spec § The delta › D1 step 4 (the compose half) and § Compatibility checks (the exporter). `infra/vps1/postgres/compose.yaml:3` becomes `postgres:18.6-alpine`, its mount `:8` becomes `postgres18-data:/var/lib/postgresql` and its volume block `:24-26` names `postgres18-data` (external); the memory limit `:14`, the healthcheck and the mesh port `:22` are unchanged. `infra/vps1/monitoring/compose.yaml:178` becomes `prometheuscommunity/postgres-exporter:v0.20.1` with `command: ["--collector.stat_checkpointer"]`. These files are the repo mirror of the hand-edit the operator makes on the hub in the window (spec D1 step 4: nothing syncs them to the hub); the branch merges after the hub window. DO-NOT: touch any live host, the old `postgres-data` volume, or the glitchtip compose.

## Touches
- infra/vps1/postgres/compose.yaml — PRIMARY PATH
- infra/vps1/monitoring/compose.yaml
- tests/test_infra_vps1_postgres_compose.py

## Behavior Contract
- **Given** `infra/vps1/postgres/compose.yaml`, **When** it is parsed, **Then** postgres-main runs `postgres:18.6-alpine`, mounts the external volume `postgres18-data` at `/var/lib/postgresql`, keeps `deploy.resources.limits.memory`, `container_name` and the `fabrik` network, and no service mounts anything at `/var/lib/postgresql/data` (infra/vps1/postgres/compose.yaml:3; spec § The delta › D1)
- **Given** `infra/vps1/monitoring/compose.yaml`, **When** it is parsed, **Then** postgres-exporter runs `prometheuscommunity/postgres-exporter:v0.20.1` with `--collector.stat_checkpointer` and keeps its memory limit (infra/vps1/monitoring/compose.yaml:178; spec § Compatibility checks)

## Context Files
- .windsurf/rules/core/30-ops.md
- .windsurf/rules/core/55-observability.md
- docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
- infra/vps1/postgres/compose.yaml
- infra/vps1/monitoring/compose.yaml
