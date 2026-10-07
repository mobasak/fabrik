# T01 — The Alloy configs are the converter's output, committed

Depends: —
Parallel: ⚡
Complexity: simple
Appetite: 60
Gate: python -m pytest tests/test_alloy_configs.py -q
Docs: none (the configs' docs land in T05)

## Scope
Implements spec § The delta › D1 and the local proofs V1 and V2 (spec § Validation). Commit the hub config
`configs/alloy/config.alloy` and the spoke template `scripts/bootstrap/templates/alloy.alloy.template` exactly as
`alloy convert --source-format=promtail` (`grafana/alloy:v1.20.1`) emits them from `configs/promtail/promtail-config.yaml`
and from `scripts/bootstrap/templates/promtail.yaml.template` rendered with fixed values, with the `{{…}}` placeholders
put back in the spoke file. No hand edits: D3's listen address and D4's storage path are `alloy run` flags owned by the
compose tickets. A test re-runs the converter and `alloy run` validation in containers and fails on any drift. DO-NOT:
touch the Promtail configs (they stay until Gate S), any compose file or bootstrap script.

## Touches
- configs/alloy/config.alloy — PRIMARY PATH
- scripts/bootstrap/templates/alloy.alloy.template
- tests/test_alloy_configs.py

## Behavior Contract
- **Given** the hub Promtail config, **When** `alloy convert --source-format=promtail` runs on it, **Then** its output equals `configs/alloy/config.alloy` byte for byte (spec § The delta › D1; configs/promtail/promtail-config.yaml:12)
- **Given** `promtail.yaml.template` rendered with fixed spoke values, **When** it is converted, **Then** the output equals `alloy.alloy.template` rendered with the same values (spec § Validation V1; scripts/bootstrap/templates/promtail.yaml.template)
- **Given** each committed config (the spoke one rendered), **When** `alloy run` loads it in a container with no network, **Then** it starts without a config error (spec § Validation V2)
- **Given** no docker on the machine, or the `grafana/alloy:v1.20.1` image neither cached nor pullable, **When** the test runs, **Then** it skips with the stated reason instead of passing silently (core/45-testing-strategy.md)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- configs/promtail/promtail-config.yaml
- scripts/bootstrap/templates/promtail.yaml.template
- .windsurf/rules/core/55-observability.md
- .windsurf/rules/core/45-testing-strategy.md
