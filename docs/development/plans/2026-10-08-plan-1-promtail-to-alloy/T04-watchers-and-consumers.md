# T04 — The watchers and every repo consumer move to Alloy's name, port and metrics

Depends: —
Parallel: ⚡
Complexity: simple
Appetite: 75
Gate: python -m pytest tests/test_alloy_watchers.py tests/test_prometheus_reload_path.py -q
Docs: none (T05 owns the doc sweep)

## Scope
Implements spec § The delta › D3 (the watcher change and the consumer moves). Prometheus job `promtail-spokes` in
`configs/prometheus/prometheus.yml:70-80` becomes job `alloy` with targets `alloy:12345`, `10.99.0.2:12345` and
`10.99.0.3:12345`; Gatus endpoint `promtail` in `configs/gatus/apps/observability-agents.yaml:5-14` becomes `alloy`,
checking `http://alloy:12345/-/ready` with the same interval and threshold; `configs/gatus/README.md:8` follows. The
consumers move in the same change: `scripts/audit/05-observability.sh:77-78` reads Alloy's metric names (the
`loki_write_*` and `loki_source_file_*` families, taken from a local `alloy run`'s `/metrics`, spec ledger cv-04) on
port 12345 and `:146` lists `alloy`; `scripts/audit/06-backup.sh:88` adds the Alloy config path beside the Promtail
one; `scripts/vps_sync.py:154,673` adds `alloy` to both classification sets; `scripts/generate_vps_inventory.py:67,73`
names Alloy; the comments in `scripts/sysadmin/proactive-check.sh:110,150,187,399`, `scripts/sysadmin/system-prompt.txt:124`,
`scripts/bootstrap/bootstrap-hub.sh:64,670-671` and `templates/file-worker/compose.yaml.j2:16` name the shipper as Alloy.
Promtail names stay wherever the rollback profile still needs them (the classification sets, the backup path) until
Gate S. DO-NOT: push either config to vps1 (the window's step, T06), touch `agents-fabrik.md`, `.windsurf/rules/`,
`CLAIMS.yaml` or `commands/_sources/` (infra's, mailed per T06).

## Touches
- configs/prometheus/prometheus.yml — PRIMARY PATH
- configs/gatus/apps/observability-agents.yaml
- configs/gatus/README.md
- scripts/audit/05-observability.sh
- scripts/audit/06-backup.sh
- scripts/vps_sync.py
- scripts/generate_vps_inventory.py
- scripts/sysadmin/proactive-check.sh
- scripts/sysadmin/system-prompt.txt
- scripts/bootstrap/bootstrap-hub.sh
- templates/file-worker/compose.yaml.j2
- tests/test_alloy_watchers.py

## Behavior Contract
- **Given** `configs/prometheus/prometheus.yml`, **When** it is parsed, **Then** job `alloy` scrapes exactly `alloy:12345`, `10.99.0.2:12345` and `10.99.0.3:12345` and no job is named `promtail-spokes` (configs/prometheus/prometheus.yml:70; spec § The delta › D3)
- **Given** the Gatus observability-agents config, **When** it is parsed, **Then** endpoint `alloy` checks `http://alloy:12345/-/ready` with the old interval and failure threshold and no `promtail` endpoint remains (configs/gatus/apps/observability-agents.yaml:5; spec § The delta › D3)
- **Given** the observability audit, **When** its Alloy block runs against a local `alloy run`, **Then** every metric name it greps for is present in Alloy's `/metrics` (scripts/audit/05-observability.sh:78; spec ledger cv-04)
- **Given** `vps_sync.py`'s classification sets, **When** they are read, **Then** both contain `alloy` and still contain `promtail` (scripts/vps_sync.py:154; spec § The delta › D6)
- **Given** the repo consumers named in spec § What exists today, **When** each is searched, **Then** none presents Promtail as the running shipper outside the rollback-profile references (spec § The delta › D3)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- configs/prometheus/prometheus.yml
- configs/gatus/apps/observability-agents.yaml
- scripts/audit/05-observability.sh
- scripts/vps_sync.py
- tests/test_prometheus_reload_path.py
- .windsurf/rules/core/55-observability.md
