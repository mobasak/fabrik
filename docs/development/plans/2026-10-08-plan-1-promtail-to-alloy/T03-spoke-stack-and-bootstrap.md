# T03 — The spoke stack and bootstrap step 11 ship Alloy

Depends: T01
Parallel: ⚡
Complexity: simple
Appetite: 75
Gate: bash -n scripts/bootstrap/bootstrap-vps.sh && bash -n scripts/bootstrap/bootstrap-spoke-restore.sh && python -m pytest tests/test_monitoring_agent_template.py tests/test_bootstrap_scripts_sshd.py -q
Docs: docs/operations/spoke-restore-inventory.md

## Scope
Implements spec § The delta › D3 (spoke listen address on the mesh IP), D4, D5 (spoke ceiling 128M, cpus 0.25 kept),
D6 (rollback profile), D7 (`grafana/alloy:v1.20.1`, `platform: linux/amd64`, `restart: unless-stopped`) and D8 (step 11 renders and ships `alloy.alloy`, verifies `name=alloy`) for vps2 and vps3. In
`scripts/bootstrap/templates/monitoring-agent.compose.yaml.template` add the `alloy` service on `network_mode: host`
with `--server.http.listen-addr={{SPOKE_MESH_IP}}:12345` and `--storage.path` in `command:`, the read-only
`promtail-positions` mount and the new `alloy-data` volume, and move `promtail` under `profiles: [rollback]`. In
`scripts/bootstrap/bootstrap-vps.sh` step 11 (`:704-738`) render `alloy.alloy.template` with the same `sed` set, scp
and install it beside `compose.yaml` and `promtail.yaml` (still shipped: the rollback service mounts it), and change
the verify filter at `:738` to `name=alloy`; rewrite the UFW comment at `:404` that names `promtail:9080`. Mirror the
rendered result into `infra/vps2/monitoring-agent/compose.yaml` and `infra/vps3/monitoring-agent/compose.yaml`.
Classify the spoke volumes in `docs/operations/spoke-restore-inventory.md` § D: `monitoring-agent_alloy-data` beside
`monitoring-agent_promtail-positions` (D-651 condition 4). Rewrite the comment at
`scripts/bootstrap/bootstrap-spoke-restore.sh:893-896` to say alloy (not promtail) depends on vps1's Loki over the mesh. DO-NOT: run step 11 against any host, touch the hub files.

## Touches
- scripts/bootstrap/templates/monitoring-agent.compose.yaml.template — PRIMARY PATH
- scripts/bootstrap/bootstrap-vps.sh
- scripts/bootstrap/bootstrap-spoke-restore.sh
- infra/vps2/monitoring-agent/compose.yaml
- infra/vps3/monitoring-agent/compose.yaml
- docs/operations/spoke-restore-inventory.md
- tests/test_monitoring_agent_template.py

## Behavior Contract
- **Given** the spoke compose template rendered for vps2, **When** it is parsed, **Then** the `alloy` service pins `grafana/alloy:v1.20.1` with `platform: linux/amd64` and `restart: unless-stopped`, and carries a 128M memory limit, `cpus: 0.25`, `network_mode: host` and a listen address on the spoke's mesh IP port 12345 (spec § The delta › D3, D5, D7; Validation V10)
- **Given** the rendered spoke template, **When** it is parsed, **Then** `promtail` appears only under the `rollback` profile and both positions volumes are declared (spec § The delta › D6)
- **Given** bootstrap step 11, **When** its script text is read, **Then** it renders and ships `alloy.alloy` beside `compose.yaml` and `promtail.yaml` and its verify filter names `alloy`, not `promtail` (scripts/bootstrap/bootstrap-vps.sh:738; spec § The delta › D8)
- **Given** the two edited bootstrap scripts, **When** `bash -n` runs on each, **Then** both parse clean (.windsurf/rules/core/90-bootstrap-scripts.md:135)
- **Given** the infra mirrors for vps2 and vps3, **When** each is compared with the template rendered for that host, **Then** they are equal (infra/README.md; spec § The delta › D8)
- **Given** the spoke restore inventory, **When** § D is read, **Then** it classifies `monitoring-agent_alloy-data` beside `monitoring-agent_promtail-positions` (docs/operations/spoke-restore-inventory.md:68; D-651)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- scripts/bootstrap/templates/monitoring-agent.compose.yaml.template
- scripts/bootstrap/bootstrap-vps.sh
- infra/vps2/monitoring-agent/compose.yaml
- docs/operations/spoke-restore-inventory.md
- .windsurf/rules/core/90-bootstrap-scripts.md
- .windsurf/rules/core/30-ops.md
