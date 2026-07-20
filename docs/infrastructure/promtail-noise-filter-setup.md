# Promtail Log Noise Filter — Setup

**Last Updated:** 2026-07-20 (drop filter re-verified against the repo `configs/promtail/promtail-config.yaml`: it is now the single-entry regex `^ocoron-com-backup-1$` — the four dead `coolify-*` entries were cleaned in commit `05b93197`, 2026-06-17; vps1 container count corrected 28→31. **Prior 2026-06-06:** aro-wake on full fleet writes to host journald + `/var/log/aro-wake.log` — those aren't shipped by Promtail's docker-socket discovery, so no aro-wake noise filter is needed. Each host's Loki ingest stream for `host="vpsN"` will not include aro-wake-internal logs; operators read those locally via `sudo tail /var/log/aro-wake.log`.)
**Status:** ✅ Live on vps1. Spoke-side promtail containers are running at `/opt/monitoring-agent/` on vps2/vps3 and push logs to `loki:3100` via mesh (verified 2026-06-07T20:20Z — Loki has streams labelled `host=vps1`, `host=vps2`, `host=vps3`). The `promtail-spokes` Prometheus scrape job that previously scraped each spoke promtail's `/metrics` endpoint is **NOT in `prometheus.yml` today** — promtail log shipping continues to work (it's push-based, not scrape-based) but promtail-internal metrics aren't currently scraped.
**Container:** `promtail` (stable name)
**Config:** `/opt/monitoring/configs/promtail/promtail-config.yaml` (host bind mount)
**Spoke promtails:** `vps2`, `vps3` — rendered by `scripts/bootstrap/bootstrap-vps.sh` step 11 (different config, see § Multi-host)

---

## Goal

Promtail by default tails every Docker container log under `/var/lib/docker/containers/*/*log` and ships them all to Loki. Some containers produce only Docker-daemon noise with no actionable signal — the WordPress backup sidecar's cron loop is the classic example post-Coolify. A `drop` stage in the Promtail pipeline filters these by container name before shipping, reducing Loki ingestion volume + query noise.

The original filter set (2026-05-08) included Coolify-internal containers (`coolify-db`, `coolify-redis`, `coolify-realtime`, `coolify-sentinel`) — Coolify itself was removed on 2026-05-30, so those four containers no longer exist. Those four entries have since been removed (commit `05b93197`, 2026-06-17): the repo filter is now the single-entry regex `^ocoron-com-backup-1$`.

## Prerequisites

- **Docker daemon must emit container name in log attrs.** Requires `"tag": "{{.Name}}"` in `/etc/docker/daemon.json` under `log-opts`. Without this, Docker's default JSON log driver does NOT include `attrs.tag`, the `container_name` label is never extracted, and the drop filter silently does nothing.
- Promtail running on vps1 from `/opt/monitoring/compose.yaml`
- Config volume bind-mounted from host to container at `/etc/promtail/config.yml`
- Loki running and reachable at `http://loki:3100` from the `fabrik` network

### Docker daemon.json (required on every host)

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

On spokes (vps2/vps3), `bootstrap-vps.sh` step 03 emits `daemon.json` with the `tag: "{{.Name}}"` field since 2026-06-02 (W4 pre-step). The previously-flagged gap is closed — spoke logs now carry the `container_name` label in Loki same as vps1. The existing vps2 + vps3 had docker restarted as part of W4-pre (2026-06-02), so the new tag applies to all running spoke containers immediately, and any spoke provisioned via `bootstrap-vps.sh` going forward gets it on first bootstrap.

## Reproducible Setup (vps1)

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
          host: vps1
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

      # Drop pure noise — the WordPress backup sidecar runs a tight cron
      # loop that fills Loki with non-actionable output. Update the regex
      # when more drop candidates surface.
      - drop:
          expression: '^ocoron-com-backup-1\$'
          source: container_name

      - output:
          source: output
PROMTAIL"
```

### 2. Reload Promtail

Promtail does not hot-reload; it must be restarted:

```bash
ssh vps "sudo docker restart promtail"
```

### 3. Verify the filter is applied

Confirm zero startup errors:

```bash
ssh vps 'sudo docker logs promtail --tail 20 2>&1 | grep -iE "error|level=err"'
```

Expected: no output (silent = healthy).

Confirm the filtered container no longer appears in Loki:

```bash
ssh vps 'sudo docker exec prometheus wget -qO- "http://loki:3100/loki/api/v1/label/container_name/values"' \
  | python3 -m json.tool
```

The `container_name` values list should NOT include `ocoron-com-backup-1` (the only live container the filter currently matches; the four `coolify-*` entries in the regex are dead residue and match nothing).

## How to Add or Remove Filtered Containers

Edit the regex in the `drop` stage — the pattern is a pipe-separated list of exact container names anchored with `^` and `$`:

```yaml
- drop:
    expression: '^(name1|name2|name3)$'
    source: container_name
```

After editing, restart Promtail:

```bash
ssh vps "sudo docker restart promtail"
```

## Containers Currently Kept (Not Filtered)

On vps1, that's all 31 running containers minus `ocoron-com-backup-1` (the only live container the drop filter matches; the four `coolify-*` regex entries are dead residue). Full list in `docs/infrastructure/vps-complete-inventory.md § vps1 container inventory`.

## Why `ocoron-com-backup-1` Is Filtered

The WordPress backup sidecar runs a cron-style loop that logs heartbeat lines every minute. Zero actionable signal; pure noise that takes up Loki retention budget. If backup failures need to be surfaced, route them through `apprise` or a Prometheus alert on `wp_backup_last_success` (would need to be added) rather than via log scraping.

## Multi-host

### Spoke promtails

vps2 and vps3 each run a promtail container deployed by `scripts/bootstrap/bootstrap-vps.sh` step 11. Their config lives at `/opt/monitoring-agent/promtail.yaml` on each spoke and is rendered from `scripts/bootstrap/templates/promtail.yaml.template` at bootstrap time.

Key differences from vps1's promtail:

| Aspect | vps1 promtail | Spoke promtail |
| :--- | :--- | :--- |
| Loki target | `http://loki:3100` (local Docker DNS) | `http://10.99.0.1:3100` (over mesh) |
| `host` label | `vps1` | `vps2` or `vps3` |
| `server.http_listen_address` | `0.0.0.0` (Docker network) | `10.99.0.X` (mesh-only) |
| Drop filter | yes — `^(coolify-db\|coolify-redis\|coolify-realtime\|coolify-sentinel\|ocoron-com-backup-1)$` (only `ocoron-com-backup-1` is live; `coolify-*` are dead residue) | no (spokes don't have tenants yet) |

When a spoke's first tenant ships and starts producing noisy logs, mirror the drop filter into the spoke's `promtail.yaml`. Restart that spoke's promtail: `ssh vpsN 'cd /opt/monitoring-agent && sudo docker compose restart promtail'`.

### Cross-host log queries in Grafana

The `host` label is set on every Loki stream — `vps1` / `vps2` / `vps3`. So:

```logql
{host="vps2"}                            # all logs from vps2
{host="vps2", container_name="n8n"}     # n8n logs on vps2
{host=~"vps[23]"}                        # both spokes
```

Drop filters apply per-host — vps1's drop filter does NOT remove `ocoron-com-backup-1` from spokes (it doesn't exist there). Each spoke's promtail is independently configured.

## Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Logs from filtered container still appearing in Grafana/Loki | Promtail wasn't restarted | `sudo docker restart promtail` (or spoke equivalent) |
| Promtail logs show `error parsing config` | YAML syntax error (often indentation) | `yamllint /opt/monitoring/configs/promtail/promtail-config.yaml` |
| Container missing from Loki entirely (filter too broad) | Regex matches more than intended | Test the regex with `echo 'name' \| grep -E 'pattern'` first |
| `container_name` label is empty in Loki | Docker log tag format not configured | Confirm `daemon.json` has `"tag": "{{.Name}}"` under `log-opts`; recreate containers (`docker compose up -d --force-recreate`) |
| Spoke logs missing `container_name` label | bootstrap-vps.sh's daemon.json lacks the `tag` field | Edit `daemon.json` on the spoke and recreate containers; or update the bootstrap template |
| No logs from a spoke arrive at vps1 Loki | Loki isn't bound to mesh IP, or wg0 down on spoke, or firewall blocks | Check `ssh vps "sudo ss -tlnp \| grep 10.99.0.1:3100"`; mesh ping `ssh vpsN ping 10.99.0.1` |

## References

- Promtail pipeline stages: <https://grafana.com/docs/loki/latest/send-data/promtail/stages/>
- `drop` stage: <https://grafana.com/docs/loki/latest/send-data/promtail/stages/drop/>
- Sister doc: [`grafana-dashboards-setup.md`](grafana-dashboards-setup.md) (Loki dashboards + host filter)
- Bootstrap script: [`scripts/bootstrap/bootstrap-vps.sh`](../../scripts/bootstrap/bootstrap-vps.sh) step 11 + [`templates/promtail.yaml.template`](../../scripts/bootstrap/templates/promtail.yaml.template)
