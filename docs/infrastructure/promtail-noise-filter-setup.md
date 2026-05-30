# Promtail Log Noise Filter — Setup

> **⚠️ Container name is pre-migration.** Was `promtail-w0000ckgsgg048w0848okk08`
> under Coolify's UUID-suffix naming. Post-migration container is named
> `promtail` (via `container_name:` in the compose stack). Filter config
> and behavior are unchanged.

**Status:** ✅ Live on VPS (2026-05-08)
**Container:** `promtail` (was `promtail-w0000ckgsgg048w0848okk08` pre-migration)
**Config:** `/opt/monitoring/configs/promtail/promtail-config.yaml` (host bind mount)

---

## Goal

Promtail by default tails every Docker container log under `/var/lib/docker/containers/*/*log` and ships them all to Loki. On a 40-container VPS this includes Coolify's internal containers (database, redis, sentinel, realtime) that produce no actionable signal — only Docker daemon noise.

A `drop` stage in the Promtail pipeline filters these by container name before shipping, reducing Loki ingestion volume and query noise.

## Prerequisites

- **Docker daemon must emit container name in log attrs.** Requires `"tag": "{{.Name}}"` in `/etc/docker/daemon.json` under `log-opts`. Without this, Docker's default JSON log driver does NOT include `attrs.tag`, the `container_name` label is never extracted, and the drop filter silently does nothing. Applied 2026-05-19 — see daemon.json setup below.
- Promtail running as a Coolify service (already deployed in monitoring stack)
- Config volume bind-mounted from host to container at `/etc/promtail/config.yml`
- Loki running and reachable at `http://loki:3100` from the `coolify` network

### Docker daemon.json (required)

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3",
    "tag": "{{.Name}}"
  }
}
```

After changing `daemon.json`: `systemctl restart docker`. **Existing containers must be recreated** (restart alone keeps the old log format) — `docker compose up -d --force-recreate` for each compose project. New containers automatically get the tag.

## Reproducible Setup

### 1. Write the Promtail config to host

```bash
ssh vps "sudo tee /opt/monitoring/configs/promtail/promtail-config.yaml > /dev/null << 'PROMTAIL'
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /run/promtail/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: containers
    static_configs:
      - targets:
          - localhost
        labels:
          job: containerlogs
          __path__: /var/lib/docker/containers/*/*log

    pipeline_stages:
      # Parse Docker JSON log format
      - json:
          expressions:
            output: log
            stream: stream
            attrs:

      # Extract container name from attrs tag
      - json:
          expressions:
            tag:
          source: attrs

      - regex:
          expression: (?P<container_name>(?:[a-zA-Z0-9][a-zA-Z0-9_.-]+))
          source: tag

      - labels:
          container_name:
          stream:

      # Drop pure Coolify infrastructure noise — these containers are
      # managed by Coolify itself and produce no actionable log signal.
      # All Fabrik services, apps, monitoring, and WordPress are kept.
      - drop:
          expression: '^(coolify-db|coolify-redis|coolify-realtime|coolify-sentinel|ocoron-com-backup-1)\$'
          source: container_name

      - output:
          source: output
PROMTAIL"
```

### 2. Reload Promtail

Promtail does not hot-reload; it must be restarted:

```bash
ssh vps "sudo docker restart promtail-w0000ckgsgg048w0848okk08"
```

### 3. Verify the filter is applied

Confirm zero startup errors:

```bash
ssh vps "sudo docker logs promtail-w0000ckgsgg048w0848okk08 --tail 20 2>&1 | grep -iE 'error|level=err'"
```

Expected: no output (silent = healthy).

Confirm filtered containers no longer appear in Loki. From any container with `wget`:

```bash
ssh vps "sudo docker exec prometheus wget -qO- 'http://loki:3100/loki/api/v1/labels' | python3 -m json.tool"
ssh vps "sudo docker exec prometheus wget -qO- 'http://loki:3100/loki/api/v1/label/container_name/values' | python3 -m json.tool"
```

The `container_name` values list should NOT include: `coolify-db`, `coolify-redis`, `coolify-realtime`, `coolify-sentinel`, `ocoron-com-backup-1`.

## How to Add or Remove Filtered Containers

Edit the regex in the `drop` stage — the pattern is a pipe-separated list of exact container names anchored with `^` and `$`:

```yaml
- drop:
    expression: '^(name1|name2|name3)$'
    source: container_name
```

After editing, restart Promtail:

```bash
ssh vps "sudo docker restart promtail-w0000ckgsgg048w0848okk08"
```

## Containers Currently Kept (Not Filtered)

- All Fabrik services (`fabrik-*`)
- Monitoring stack (`grafana`, `loki`, `prometheus`, `alertmanager`, `gatus`, `cadvisor`, `node-exporter`, `netdata`)
- Authelia, Apprise, Backrest, MeiliSearch
- WordPress containers (`ocoron-com-nginx-1`, `ocoron-com-wordpress-1`, `ocoron-com-db-1`, `ocoron-com-redis-1`)
- All Coolify single-image Applications (browserless, gotenberg, glitchtip-web, file-api, etc.)

## Why These 5 Are Filtered

| Container | Reason |
|---|---|
| `coolify-db` | Internal Postgres for Coolify itself; not ours |
| `coolify-redis` | Internal Redis for Coolify itself; not ours |
| `coolify-realtime` | Soketi WebSocket for Coolify UI live logs only |
| `coolify-sentinel` | Coolify's Redis Sentinel (HA failover for `coolify-redis`) |
| `ocoron-com-backup-1` | WordPress backup loop; cron-style noise |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Logs from filtered container still appearing in Grafana/Loki | Promtail wasn't restarted | `sudo docker restart promtail-...` |
| Promtail logs show `error parsing config` | YAML syntax error (often indentation) | `yamllint /opt/monitoring/configs/promtail/promtail-config.yaml` |
| Container missing from Loki entirely (filter too broad) | Regex matches more than intended | Test the regex with `echo 'name' \| grep -E 'pattern'` first |
| `container_name` label is empty in Loki | Docker log tag format changed | Check `attrs.tag` field in raw log: `sudo cat /var/lib/docker/containers/*/<id>-json.log \| head -1` |

## References

- Promtail pipeline stages: https://grafana.com/docs/loki/latest/clients/promtail/stages/
- `drop` stage: https://grafana.com/docs/loki/latest/clients/promtail/stages/drop/
