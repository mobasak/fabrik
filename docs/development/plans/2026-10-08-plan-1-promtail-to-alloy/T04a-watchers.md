# T04a — The Prometheus job and the Gatus endpoint move to Alloy

Depends: —
Parallel: ⚡
Complexity: simple
Appetite: 45
Gate: python -m pytest tests/test_alloy_watchers.py tests/test_prometheus_reload_path.py -q
Docs: none (T05 owns the doc sweep)

## Scope
Implements spec § The delta › D3 (the watcher change). Prometheus job `promtail-spokes` in
`configs/prometheus/prometheus.yml:70-82` becomes job `alloy` with targets `alloy:12345`, `10.99.0.2:12345` and
`10.99.0.3:12345` — each spoke target keeps the `host`/`role` labels its old `static_configs` entry carries, and the
hub target takes `host: vps1` with the `role` value the hub's other targets in `prometheus.yml` use; Gatus endpoint `promtail` in `configs/gatus/apps/observability-agents.yaml:5-14` becomes `alloy`,
checking `http://alloy:12345/-/ready` with the same interval and failure threshold; `configs/gatus/README.md:8`
follows. These files reach vps1 only through the window's two `--push` runs (T06). DO-NOT: push either config, touch
any script or compose file.

## Touches
- configs/prometheus/prometheus.yml — PRIMARY PATH
- configs/gatus/apps/observability-agents.yaml
- configs/gatus/README.md
- tests/test_alloy_watchers.py

## Behavior Contract
- **Given** `configs/prometheus/prometheus.yml`, **When** it is parsed, **Then** job `alloy` scrapes exactly `alloy:12345`, `10.99.0.2:12345` and `10.99.0.3:12345` and no job is named `promtail-spokes` (configs/prometheus/prometheus.yml:70; spec § The delta › D3)
- **Given** the Gatus observability-agents config, **When** it is parsed, **Then** endpoint `alloy` checks `http://alloy:12345/-/ready` with the old interval and failure threshold and no `promtail` endpoint remains (configs/gatus/apps/observability-agents.yaml:5; spec § The delta › D3)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- configs/prometheus/prometheus.yml
- configs/gatus/apps/observability-agents.yaml
- configs/gatus/README.md
- tests/test_prometheus_reload_path.py
- .windsurf/rules/core/55-observability.md
