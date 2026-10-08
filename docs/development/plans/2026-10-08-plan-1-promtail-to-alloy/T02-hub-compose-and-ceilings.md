# T02 — The hub monitoring compose runs Alloy, Promtail kept under the rollback profile

Depends: T01
Parallel: ⚡
Complexity: simple
Appetite: 60
Gate: bash -n scripts/bootstrap/bootstrap-config.sh && bash -n scripts/vps_apply_limits.sh && python -m pytest tests/test_vps_apply_limits.py -q
Docs: none (T05 owns the doc sweep)

## Scope
Implements spec § The delta › D3 (hub listen address), D4 (positions hand-over), D5 (hub ceiling), D6 (rollback
profile) and D7 (image, platform, hub volume classification) for vps1. In `infra/vps1/monitoring/compose.yaml` (the
repo-of-record of the live `/opt/monitoring/compose.yaml`, spec § What exists today) add the `alloy` service —
`grafana/alloy:v1.20.1`, `platform: linux/amd64`, `restart: unless-stopped`, `fabrik` network, no host port,
`command:` carrying `run`, the config path, `--server.http.listen-addr=0.0.0.0:12345` and
`--storage.path=/var/lib/alloy/data`, mounts `configs/alloy/config.alloy`, `/var/lib/docker/containers` read-only,
`promtail-positions:/run/promtail:ro` and the new `alloy-data:/var/lib/alloy/data`, memory limit 256M — and move the
`promtail` service under `profiles: [rollback]`, keeping its volume declared. The ceiling row `alloy 256` lands first
in `docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md`, then beside `promtail 256` in
`scripts/vps_apply_limits.sh:56`, then in `tests/test_vps_apply_limits.py`. `scripts/bootstrap/bootstrap-config.sh`
gains `monitoring_alloy-data` beside `monitoring_promtail-positions` at `:218` (D-651 condition 2) and its `:120`
stack comment names alloy. DO-NOT: remove the promtail service or its volume (Gate S does), touch the spoke files.

## Touches
- infra/vps1/monitoring/compose.yaml — PRIMARY PATH
- docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md
- scripts/vps_apply_limits.sh
- tests/test_vps_apply_limits.py
- scripts/bootstrap/bootstrap-config.sh

## Behavior Contract
- **Given** the hub compose, **When** it is parsed, **Then** the `alloy` service pins `grafana/alloy:v1.20.1`, declares `platform: linux/amd64` and a 256M memory limit, and carries the listen-address and storage-path flags (spec § The delta › D3, D5, D7)
- **Given** the hub compose, **When** `docker compose config` and `docker compose config --profiles` are read, **Then** `promtail` appears only under the `rollback` profile and both `promtail-positions` and `alloy-data` are declared volumes (spec § The delta › D6)
- **Given** the memory-limits table, **When** `tests/test_vps_apply_limits.py` reads it, **Then** `alloy 256` sits beside `promtail 256` and the hub compose's alloy limit matches it (scripts/vps_apply_limits.sh:56; spec § The delta › D5; Validation V10)
- **Given** the bootstrap volume classification, **When** it is read, **Then** `monitoring_alloy-data` is listed as recomputable beside `monitoring_promtail-positions` (scripts/bootstrap/bootstrap-config.sh:220, beside :218; spec § The delta › D7)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- infra/vps1/monitoring/compose.yaml
- scripts/vps_apply_limits.sh
- tests/test_vps_apply_limits.py
- scripts/bootstrap/bootstrap-config.sh
- .windsurf/rules/core/30-ops.md
