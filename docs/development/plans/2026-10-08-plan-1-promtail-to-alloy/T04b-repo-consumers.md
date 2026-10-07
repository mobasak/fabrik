# T04b — Every repo consumer names Alloy's container, port and metrics

Depends: —
Parallel: ⚡
Complexity: simple
Appetite: 60
Gate: python -m pytest tests/test_alloy_consumers.py -q
Docs: none (T05 owns the doc sweep)

## Scope
Implements spec § The delta › D3 (the consumer moves). `scripts/audit/05-observability.sh:77-78` reads Alloy's metric
names on port 12345 and `:146` lists `alloy` — the names are taken from a local `alloy run`'s `/metrics`
(`docker run --rm grafana/alloy:v1.20.1` with the committed hub config, `curl localhost:12345/metrics`; spec ledger
cv-04) and the grep keeps only the `loki_write_*` and `loki_source_file_*` families that output shows;
`scripts/audit/06-backup.sh:88` adds the Alloy config path beside the Promtail one; `scripts/vps_sync.py:154,673` adds
`alloy` to both classification sets; `scripts/generate_vps_inventory.py:67,73` names Alloy; the comments in
`scripts/sysadmin/proactive-check.sh:110,150,187,399`, `scripts/sysadmin/system-prompt.txt:124`,
`scripts/bootstrap/bootstrap-hub.sh:64,670-671` and `templates/file-worker/compose.yaml.j2:16` name the shipper as
Alloy. Promtail names stay wherever the rollback profile still needs them (the classification sets, the backup path)
until Gate S. DO-NOT: touch `agents-fabrik.md`, `.windsurf/rules/`, `CLAIMS.yaml` or `commands/_sources/` (infra's,
mailed per T06), or the watcher configs (T04a).

## Touches
- scripts/audit/05-observability.sh — PRIMARY PATH
- scripts/audit/06-backup.sh
- scripts/vps_sync.py
- scripts/generate_vps_inventory.py
- scripts/sysadmin/proactive-check.sh
- scripts/sysadmin/system-prompt.txt
- scripts/bootstrap/bootstrap-hub.sh
- templates/file-worker/compose.yaml.j2
- tests/test_alloy_consumers.py

## Behavior Contract
- **Given** the observability audit, **When** its Alloy block runs against a local `alloy run`, **Then** every metric name it greps for is present in Alloy's `/metrics` (scripts/audit/05-observability.sh:78; spec ledger cv-04)
- **Given** `vps_sync.py`'s classification sets, **When** they are read, **Then** both contain `alloy` and still contain `promtail` (scripts/vps_sync.py:154; spec § The delta › D6)
- **Given** the repo consumers named in spec § What exists today, **When** each is searched, **Then** none presents Promtail as the running shipper outside the rollback-profile references (spec § The delta › D3)

## Context Files
- docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md
- scripts/audit/05-observability.sh
- scripts/vps_sync.py
- scripts/generate_vps_inventory.py
- scripts/sysadmin/proactive-check.sh
- .windsurf/rules/core/55-observability.md
