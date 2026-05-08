"""Generate Grafana v11 dashboard JSON files for the Fabrik observability stack.

Outputs to ./dashboards/ as one .json per dashboard. These get bind-mounted
into Grafana on the VPS at /var/lib/grafana/dashboards/ via the provisioning
provider in dashboards.yaml.

Run: cd configs/grafana && python3 build_dashboards.py
"""
from __future__ import annotations
import json
import os
from typing import Any

OUT_DIR = os.path.join(os.path.dirname(__file__), "dashboards")
DS = {"type": "prometheus", "uid": "prometheus"}

def panel(
    id: int, title: str, x: int, y: int, w: int, h: int, ptype: str,
    targets: list[dict], unit: str = "short",
    overrides: list[dict] | None = None, options: dict | None = None,
    legend: bool = True,
) -> dict:
    p = {
        "id": id,
        "type": ptype,
        "title": title,
        "datasource": DS,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {
            "defaults": {"unit": unit, "color": {"mode": "palette-classic"}},
            "overrides": overrides or [],
        },
        "options": options or {
            "legend": {"displayMode": "list" if legend else "hidden", "placement": "bottom"},
            "tooltip": {"mode": "multi"},
        },
        "targets": [{"datasource": DS, "expr": t["expr"], "legendFormat": t.get("legend", ""), "refId": chr(65 + i)}
                    for i, t in enumerate(targets)],
    }
    return p

def stat(id, title, x, y, w, h, expr, unit="short", legend=""):
    return panel(id, title, x, y, w, h, "stat",
                 [{"expr": expr, "legend": legend}], unit=unit, legend=False,
                 options={"reduceOptions": {"calcs": ["lastNotNull"]},
                          "graphMode": "area", "colorMode": "value"})

def gauge(id, title, x, y, w, h, expr, unit="short", legend=""):
    return panel(id, title, x, y, w, h, "gauge",
                 [{"expr": expr, "legend": legend}], unit=unit, legend=False)

def timeseries(id, title, x, y, w, h, targets, unit="short", overrides=None):
    return panel(id, title, x, y, w, h, "timeseries", targets, unit=unit, overrides=overrides or [])

def dashboard(uid: str, title: str, tags: list[str], panels: list[dict], refresh: str = "30s") -> dict:
    return {
        "annotations": {"list": []},
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "panels": panels,
        "refresh": refresh,
        "schemaVersion": 39,
        "tags": tags,
        "templating": {"list": []},
        "time": {"from": "now-3h", "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": title,
        "uid": uid,
        "version": 1,
        "weekStart": "",
    }

# ── 1. Infrastructure Overview ─────────────────────────────────────────
infra = dashboard("fabrik-infra-overview", "Fabrik · Infrastructure Overview",
    ["fabrik", "infrastructure"], [
    stat(1, "Containers Up", 0, 0, 4, 4, "count(container_last_seen{name!=''})", "short"),
    stat(2, "Targets UP", 4, 0, 4, 4, "sum(up)", "short"),
    stat(3, "Targets DOWN", 8, 0, 4, 4, "sum(up == 0) OR on() vector(0)", "short"),
    stat(4, "Host CPU %", 12, 0, 4, 4, "100 * (1 - avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])))", "percent"),
    stat(5, "Host RAM %", 16, 0, 4, 4, "100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)", "percent"),
    stat(6, "Disk used %", 20, 0, 4, 4, "100 * (1 - node_filesystem_avail_bytes{mountpoint=\"/\",fstype!=\"tmpfs\"} / node_filesystem_size_bytes{mountpoint=\"/\",fstype!=\"tmpfs\"})", "percent"),
    timeseries(10, "CPU usage by container (top 10)", 0, 4, 12, 8,
        [{"expr": "topk(10, sum by (name) (rate(container_cpu_usage_seconds_total{name!=''}[5m])) * 100)",
          "legend": "{{name}}"}], unit="percent"),
    timeseries(11, "Memory usage by container (top 10)", 12, 4, 12, 8,
        [{"expr": "topk(10, sum by (name) (container_memory_working_set_bytes{name!=''}))",
          "legend": "{{name}}"}], unit="bytes"),
    timeseries(12, "Network RX by container (top 10)", 0, 12, 12, 8,
        [{"expr": "topk(10, sum by (name) (rate(container_network_receive_bytes_total{name!=''}[5m])))",
          "legend": "{{name}}"}], unit="Bps"),
    timeseries(13, "Network TX by container (top 10)", 12, 12, 12, 8,
        [{"expr": "topk(10, sum by (name) (rate(container_network_transmit_bytes_total{name!=''}[5m])))",
          "legend": "{{name}}"}], unit="Bps"),
    timeseries(14, "Scrape duration by job (p95)", 0, 20, 24, 6,
        [{"expr": "histogram_quantile(0.95, sum by (job, le) (rate(scrape_duration_seconds_bucket[5m])))",
          "legend": "{{job}}"}], unit="s"),
])

# ── 2. Databases (postgres + redis) ────────────────────────────────────
dbs = dashboard("fabrik-databases", "Fabrik · Databases (Postgres + Redis)",
    ["fabrik", "database"], [
    # Postgres row
    stat(1, "Postgres up", 0, 0, 4, 4, "pg_up", legend=""),
    stat(2, "PG Connections", 4, 0, 4, 4, "sum(pg_stat_database_numbackends)"),
    stat(3, "PG Total Size", 8, 0, 4, 4, "sum(pg_database_size_bytes)", "bytes"),
    stat(4, "Redis up", 12, 0, 4, 4, "redis_up"),
    stat(5, "Redis Clients", 16, 0, 4, 4, "redis_connected_clients"),
    stat(6, "Redis Memory", 20, 0, 4, 4, "redis_memory_used_bytes", "bytes"),
    timeseries(10, "Postgres: tx commit rate by DB", 0, 4, 12, 8,
        [{"expr": "rate(pg_stat_database_xact_commit{datname!~\"template.*|postgres\"}[5m])",
          "legend": "{{datname}} commits"}]),
    timeseries(11, "Postgres: tx rollback rate by DB", 12, 4, 12, 8,
        [{"expr": "rate(pg_stat_database_xact_rollback{datname!~\"template.*|postgres\"}[5m])",
          "legend": "{{datname}} rollbacks"}]),
    timeseries(12, "Postgres: cache hit ratio (higher = better)", 0, 12, 12, 8,
        [{"expr": "sum by (datname) (rate(pg_stat_database_blks_hit[5m])) / (sum by (datname) (rate(pg_stat_database_blks_hit[5m])) + sum by (datname) (rate(pg_stat_database_blks_read[5m])))",
          "legend": "{{datname}}"}], unit="percentunit"),
    timeseries(13, "Postgres: DB sizes", 12, 12, 12, 8,
        [{"expr": "pg_database_size_bytes{datname!~\"template.*\"}",
          "legend": "{{datname}}"}], unit="bytes"),
    timeseries(20, "Redis: commands/sec by type", 0, 20, 12, 8,
        [{"expr": "rate(redis_commands_processed_total[5m])",
          "legend": "ops/sec"}]),
    timeseries(21, "Redis: hit/miss ratio", 12, 20, 12, 8,
        [{"expr": "rate(redis_keyspace_hits_total[5m]) / (rate(redis_keyspace_hits_total[5m]) + rate(redis_keyspace_misses_total[5m]))",
          "legend": "hit ratio"}], unit="percentunit"),
    timeseries(22, "Redis: memory used vs max", 0, 28, 12, 8,
        [{"expr": "redis_memory_used_bytes", "legend": "used"},
         {"expr": "redis_memory_max_bytes", "legend": "max"}], unit="bytes"),
    timeseries(23, "Redis: evicted keys/sec", 12, 28, 12, 8,
        [{"expr": "rate(redis_evicted_keys_total[5m])", "legend": "evictions/sec"}]),
])

# ── 3. Containers by name (generic per-service) ────────────────────────
container_templating = {
    "list": [{
        "name": "container",
        "type": "query",
        "datasource": DS,
        "label": "Container",
        "query": "label_values(container_last_seen{name!=''}, name)",
        "refresh": 2,
        "current": {"text": "All", "value": "$__all"},
        "multi": True, "includeAll": True,
    }]
}
containers = dashboard("fabrik-containers", "Fabrik · Container View (per-name)",
    ["fabrik", "container"], [
    timeseries(1, "CPU %", 0, 0, 12, 8,
        [{"expr": "rate(container_cpu_usage_seconds_total{name=~\"$container\"}[5m]) * 100",
          "legend": "{{name}}"}], unit="percent"),
    timeseries(2, "Memory (working set)", 12, 0, 12, 8,
        [{"expr": "container_memory_working_set_bytes{name=~\"$container\"}",
          "legend": "{{name}}"}], unit="bytes"),
    timeseries(3, "Network RX", 0, 8, 12, 8,
        [{"expr": "rate(container_network_receive_bytes_total{name=~\"$container\"}[5m])",
          "legend": "{{name}}"}], unit="Bps"),
    timeseries(4, "Network TX", 12, 8, 12, 8,
        [{"expr": "rate(container_network_transmit_bytes_total{name=~\"$container\"}[5m])",
          "legend": "{{name}}"}], unit="Bps"),
    timeseries(5, "Disk read", 0, 16, 12, 8,
        [{"expr": "rate(container_fs_reads_bytes_total{name=~\"$container\"}[5m])",
          "legend": "{{name}}"}], unit="Bps"),
    timeseries(6, "Disk write", 12, 16, 12, 8,
        [{"expr": "rate(container_fs_writes_bytes_total{name=~\"$container\"}[5m])",
          "legend": "{{name}}"}], unit="Bps"),
])
containers["templating"] = container_templating

# ── 4. Authelia ────────────────────────────────────────────────────────
auth = dashboard("fabrik-authelia", "Fabrik · Authelia (auth + sessions)",
    ["fabrik", "auth"], [
    stat(1, "Total auth requests (5m)", 0, 0, 6, 4, "sum(increase(authelia_request[5m]))"),
    stat(2, "Failed auth (5m)", 6, 0, 6, 4, "sum(increase(authelia_request{code!~\"2..\"}[5m]))"),
    stat(3, "Authelia up", 12, 0, 6, 4, "up{job=\"authelia\"}"),
    stat(4, "Authelia memory", 18, 0, 6, 4,
         "container_memory_working_set_bytes{name=~\"authelia.*\"}", "bytes"),
    timeseries(10, "Request rate by code", 0, 4, 12, 8,
        [{"expr": "sum by (code) (rate(authelia_request[5m]))", "legend": "code={{code}}"}]),
    timeseries(11, "Request rate by method", 12, 4, 12, 8,
        [{"expr": "sum by (method) (rate(authelia_request[5m]))", "legend": "{{method}}"}]),
    timeseries(12, "Latency p50/p95/p99", 0, 12, 24, 8, [
        {"expr": "histogram_quantile(0.50, sum by (le) (rate(authelia_request_duration_bucket[5m])))",
         "legend": "p50"},
        {"expr": "histogram_quantile(0.95, sum by (le) (rate(authelia_request_duration_bucket[5m])))",
         "legend": "p95"},
        {"expr": "histogram_quantile(0.99, sum by (le) (rate(authelia_request_duration_bucket[5m])))",
         "legend": "p99"},
    ], unit="s"),
])

# ── 5. Meilisearch ─────────────────────────────────────────────────────
meili = dashboard("fabrik-meilisearch", "Fabrik · Meilisearch",
    ["fabrik", "search"], [
    stat(1, "Up", 0, 0, 6, 4, "up{job=\"meilisearch\"}"),
    stat(2, "Index count", 6, 0, 6, 4, "count(meilisearch_index_count)"),
    stat(3, "DB size", 12, 0, 6, 4, "meilisearch_database_size_bytes", "bytes"),
    stat(4, "Used DB size", 18, 0, 6, 4, "meilisearch_used_database_size_bytes", "bytes"),
    timeseries(10, "HTTP requests/sec by code", 0, 4, 12, 8,
        [{"expr": "sum by (status) (rate(meilisearch_http_requests_total[5m]))", "legend": "status={{status}}"}]),
    timeseries(11, "HTTP requests/sec by path", 12, 4, 12, 8,
        [{"expr": "sum by (path) (rate(meilisearch_http_requests_total[5m]))", "legend": "{{path}}"}]),
    timeseries(12, "Latency p95 by path", 0, 12, 24, 8,
        [{"expr": "histogram_quantile(0.95, sum by (path, le) (rate(meilisearch_http_response_time_seconds_bucket[5m])))",
          "legend": "p95 {{path}}"}], unit="s"),
])

# Write all to /dashboards/
os.makedirs(OUT_DIR, exist_ok=True)
for name, dash in [("00-infrastructure-overview", infra), ("10-databases", dbs),
                    ("20-containers", containers), ("30-authelia", auth),
                    ("40-meilisearch", meili)]:
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(dash, f, indent=2)
    print(f"  wrote {path} ({os.path.getsize(path)} bytes)")
print(f"\nDone. {len(os.listdir(OUT_DIR))} dashboards in {OUT_DIR}")
