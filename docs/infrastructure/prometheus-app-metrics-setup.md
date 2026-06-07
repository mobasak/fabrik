# Prometheus app-level metrics — runbook

**Last Updated:** 2026-06-07 (aro-wake SLI scrape job covers full fleet of vps1+vps2+vps3 via the same `aro-wake` job; cross-mesh container→host NAT path documented below as a worked example. **Two updates 2026-06-07**: `aro_wake_requests_total` counter now has `status="rate_limited"` value alongside `success` + `failure`; `AroWakeLowSuccessRate` alert rule denominator updated from `aro_wake_requests_total` to `aro_wake_requests_total{status!="rate_limited"}` so refused-at-the-gate drops don't unfairly lower the LLM success-rate SLI. The stale `netdata` scrape job is REMOVED from `prometheus.yml` — caused a 24× Telegram flood overnight before removal via the Phase 4 wire's `repeat_interval: 30m`.)
**Status:** ✅ Live (originally 2026-05-08)
**Prometheus container:** `prometheus` (stable name)
**Scrape config:** `/opt/monitoring/configs/prometheus/prometheus.yml`

This runbook covers Prometheus scrape configuration for application-level metrics from infrastructure services. It complements `cadvisor` (container-level) and `node-exporter` (host-level), which were already in place.

## What's scraped

### vps1-local app metrics

| Job | Endpoint | Auth | Why this job |
| :--- | :--- | :--- | :--- |
| `grafana` | `http://grafana:3000/metrics` | none (anonymous) | dashboard query rates, datasource health |
| `authelia` | `http://authelia:9959/metrics` | none (telemetry port) | auth success/fail rates, session counts, request latency |
| `meilisearch` | `http://meilisearch:7700/metrics` | Bearer token (master key) | search latency, index size, HTTP request counters |
| `pushgateway` | `http://pushgateway:9091/metrics` | none | short-lived metric pushes (used by `audit_all_registrars.py` cron) |
| ~~glitchtip~~ | — | — | **NOT SCRAPED.** GlitchTip ships without `django-prometheus`. cAdvisor + Gatus cover it. |

### vps1-local platform metrics (already present pre-2026-05-08)

| Job | Endpoint | Notes |
| :--- | :--- | :--- |
| `prometheus` | `http://localhost:9090/metrics` | Prometheus self-monitoring |
| `node` | `http://node-exporter:9100/metrics` | vps1 host metrics |
| `cadvisor` | `http://cadvisor:8080/metrics` | vps1 container metrics |
| `loki` | `http://loki:3100/metrics` | Loki ingest stats |
| `alertmanager` | `http://alertmanager:9093/metrics` | Alert dispatch counters |
| `gatus` | `http://gatus:8080/metrics` | Synthetic check results |
| `postgres` | `http://postgres-exporter:9187/metrics` | Connections, slow queries, replication |
| `redis` | `http://redis-exporter:9121/metrics` | Hit ratio, memory, ops/sec |

### Spoke metrics (added 2026-05-31)

| Job | Targets | Per-target label |
| :--- | :--- | :--- |
| `node-spokes` | `10.99.0.2:9100`, `10.99.0.3:9100` | `host: vps2` / `host: vps3` |
| `cadvisor-spokes` | `10.99.0.2:8080`, `10.99.0.3:8080` | `host: vps2` / `host: vps3` |
| `promtail-spokes` | `10.99.0.2:9080`, `10.99.0.3:9080` | `host: vps2` / `host: vps3` |

Every scrape target now carries a `host` label so dashboards + alerts can filter per-host. vps1-local jobs get `host: vps1`; spoke jobs split per-target. See § Multi-host below for the pattern.

### aro-wake SLI metrics (added 2026-06-06 — full fleet)

| Job | Targets | Per-target labels | Path |
| :--- | :--- | :--- | :--- |
| `aro-wake` | `10.0.1.1:8201` (vps1, docker-bridge), `10.99.0.2:8201` (vps2, wg0), `10.99.0.3:8201` (vps3, wg0) | `host: vps1`+`role: hub`, `host: vps2`+`role: spoke`, `host: vps3`+`role: spoke` | `/metrics` |

Eight metric families exposed by the FastAPI app (`scripts/aro-wake/main.py`) via `prometheus-client==0.21.1`: 6 counters (`aro_wake_requests_total{source,status}`, `aro_wake_cost_usd_total{source}`, `aro_wake_dedup_drops_total`, `aro_wake_hop_limit_exceeded_total`, `aro_wake_forward_suppressed_total{target_host,reason}`, `aro_wake_storm_breaker_trips_total{target_host}`) + 2 gauges (`aro_wake_pending_queue_size`, `aro_wake_active_sessions`).

**Hub-side scrape path** for vps1 uses the same `10.0.1.1:8201` docker-bridge gateway that Alertmanager already uses to reach `/wake`. Scrape latency ~1.4ms.

**Cross-mesh scrape path** for vps2 + vps3 (FIRST host-service scraped via wg0 — worth documenting):

- Prometheus container is on the `coolify` Docker network.
- Outbound traffic from the container to a wg0 IP (e.g. `10.99.0.2`) leaves the host through `eth0` → kernel routing decides this is a wg0 destination → encapsulates via `wg0` interface → emerges on the spoke.
- Docker MASQUERADE on vps1 rewrites the container's source IP from its docker-bridge IP (e.g. `10.0.1.x`) to vps1's wg0 IP `10.99.0.1` when the packet leaves the host.
- The spoke's UFW rule `from 10.99.0.0/24 to any port 8201 proto tcp` accepts the rewritten source. No spoke-side firewall change needed.
- Verified via tcpdump on vps2's wg0 interface: `IP 10.99.0.1.<port> > 10.99.0.2.8201: Flags [S]` — the SNAT works as expected.
- Scrape latency ~270ms (transcontinental wg0 RTT ~133ms + connection handshake overhead).

The aro-wake-specific alert rules ship in `configs/prometheus/rules/alerts.yml` under group `aro_wake`. Both are evaluated per-host via `by (host)`:

- `AroWakeLowSuccessRate` — `sum(rate(aro_wake_requests_total{status="success"}[10m])) by (host) / sum(rate(aro_wake_requests_total[10m])) by (host) < 0.90` for 15m (warning)
- `AroWakeCostBurnHigh` — `sum(rate(aro_wake_cost_usd_total[1h])) by (host) > 5` for 10m (warning, runaway-reasoning early-warning)

See [`vps-ai-sysadmin.md` § SLI metrics](vps-ai-sysadmin.md#sli-metrics-prometheus-since-2026-06-06) for the full SLI framing.

## Sample useful queries

```promql
# Authelia auth failure rate (host-aware)
rate(authelia_request{code!~"2..", host="vps1"}[5m])

# Grafana dashboard render latency (p95)
histogram_quantile(0.95,
  sum(rate(grafana_http_request_duration_seconds_bucket{handler!~"/api/health|/api/.*/metrics"}[5m])) by (le, handler))

# Meilisearch search QPS
rate(meilisearch_http_requests_total{path="/indexes/{uid}/search"}[5m])

# Container memory across all hosts, top 10
topk(10, container_memory_usage_bytes{name!=""})

# Spoke vs hub CPU comparison
sum(rate(node_cpu_seconds_total{mode!="idle"}[5m])) by (host)

# Any container restart in the last 15 min (any host)
changes(container_start_time_seconds{name!=""}[15m]) > 0
```

## Configuration setup steps reproduced

### 1. Authelia — enable telemetry server

Authelia's metrics are disabled by default. Append to `configuration.yml`:

```yaml
telemetry:
  metrics:
    enabled: true
    address: tcp://0.0.0.0:9959
```

**Important — config drift**: on vps1, the working copy at `/opt/authelia/config/configuration.yml` is watched by `authelia-config-sync.service` (inotify-driven). On save, the file is copied into the named volume (`hks48k8sg8o4co4co08co00o_authelia-config`) where Authelia actually reads it from `/config/configuration.yml`, and the Authelia container is restarted (~2 s reaction time). Drift between the two no longer happens.

Authelia exits on SIGHUP — does NOT hot-reload. The config-sync service does the restart automatically; no manual `docker restart` needed after editing the working copy.

After restart, look for log line:

```text
"Listening for non-TLS connections on '[::]:9959' path '/metrics'","server":"metrics"
```

### 2. Grafana — already exposed

Grafana exposes `/metrics` on port 3000 anonymously by default. Just add the scrape job.

### 3. Meilisearch — needs experimental flag

Meilisearch requires `MEILI_EXPERIMENTAL_ENABLE_METRICS=true` env var AND the master key as Bearer token to expose `/metrics`.

```bash
# Set env var in the service's .env on the VPS (no Coolify API anymore):
ssh vps 'sudo bash -c "
  cd /opt/meilisearch
  cp .env .env.bak-\$(date +%Y%m%d-%H%M%S)
  grep -q ^MEILI_EXPERIMENTAL_ENABLE_METRICS= .env && \
    sed -i \"s|^MEILI_EXPERIMENTAL_ENABLE_METRICS=.*|MEILI_EXPERIMENTAL_ENABLE_METRICS=true|\" .env || \
    echo \"MEILI_EXPERIMENTAL_ENABLE_METRICS=true\" >> .env
  docker compose up -d
"'
```

The `fabrik apply` orchestrator's glitchtip / postgres / etc. registrars also do `inject_env()` via the SSH deployer for env additions — the script above is the manual one-off equivalent.

### 4. Reload Prometheus (no restart needed)

```bash
ssh vps "sudo docker kill -s HUP prometheus"
# or via the lifecycle endpoint:
ssh vps 'sudo docker exec prometheus wget -qO- --post-data="" http://localhost:9090/-/reload'
```

Either works since Prometheus is started with `--web.enable-lifecycle`.

## Verifying targets are up

```bash
ssh vps 'sudo docker exec prometheus wget -qO- "http://localhost:9090/api/v1/targets?state=any"' \
  | python3 -c "
import json, sys
for t in json.load(sys.stdin)['data']['activeTargets']:
    print(f\"{t['labels']['job']:18s} {t['labels'].get('host','?'):6s} {t['health']:6s} {t['labels'].get('instance','')}\")"
```

Or via Grafana → Explore → Prometheus datasource → run `up{job=~"authelia|grafana|meilisearch"}` — all should return 1.

For spoke target health, use `up{job=~".*-spokes"}` — expects 6 series UP (3 jobs × 2 spokes).

## Multi-host

### Adding a new spoke

When provisioning vps4 (or later), `scripts/bootstrap/bootstrap-vps.sh` step 11 deploys node-exporter / cadvisor / promtail on the new spoke, bound to its mesh IP. To make Prometheus on vps1 scrape it, append per-target blocks to the spoke jobs in `prometheus.yml`:

```yaml
- job_name: node-spokes
  static_configs:
    - targets: [10.99.0.2:9100]
      labels: {host: vps2}
    - targets: [10.99.0.3:9100]
      labels: {host: vps3}
    - targets: [10.99.0.4:9100]    # NEW
      labels: {host: vps4}          # NEW
```

Same for `cadvisor-spokes` and `promtail-spokes`. SIGHUP Prometheus and verify targets.

### Adding host label to a new vps1-local job

Every static_configs block should include a `labels: {host: vps1}` so the dashboards + alert rules filter cleanly. Example:

```yaml
- job_name: new-service
  static_configs:
    - targets: [new-service:8000]
      labels: {host: vps1}
```

Without the `host` label, dashboard panels filtering on `{host=~"$host"}` will silently exclude the series.

### App-level metrics from spoke services

Future spoke tenants that expose `/metrics`:

- Bind their `/metrics` endpoint to the mesh IP (e.g. `10.99.0.2:<port>`) so only mesh peers reach it
- Add a per-host scrape block in vps1's `prometheus.yml`:

  ```yaml
  - job_name: new-saas-on-vps2
    static_configs:
      - targets: [10.99.0.2:9123]
        labels: {host: vps2, service: new-saas}
  ```

- SIGHUP Prometheus; verify in `/targets`.

When the spec-driven `fabrik apply --target-vps` workflow lands (W-Multi M4/M5), the spec's `shape.exposes_metrics: true` will auto-emit this scrape block via the prometheus registrar.

## Alert rules — spoke health

Live as of 2026-05-31 in `/opt/monitoring/configs/prometheus/rules/alerts.yml` group `spoke_health`:

| Alert | Expr | for | Severity |
| :--- | :--- | :--- | :--- |
| `SpokeDown` | `up{job=~"node-spokes\|cadvisor-spokes\|promtail-spokes"} == 0` | 5 m | critical |
| `SpokeHighCPU` | `(1 - rate(node_cpu_seconds_total{mode="idle", host=~"vps[23]"}[5m])) > 0.85` | 10 m | warning |
| `SpokeHighRAM` | `(1 - node_memory_MemAvailable_bytes{host=~"vps[23]"}/node_memory_MemTotal_bytes{host=~"vps[23]"}) > 0.85` | 10 m | warning |

Routed via Alertmanager → Apprise → Telegram with the existing config.

## Common operations

### Add a new app-level scrape job

1. Edit `/opt/monitoring/configs/prometheus/prometheus.yml`
2. Add the new `- job_name: ...` block under `scrape_configs:` with a `labels: {host: vpsN}` line
3. SIGHUP Prometheus
4. Verify via `/api/v1/targets`

### Why we don't scrape GlitchTip

GlitchTip ships without `django-prometheus`. Adding it would mean forking the image — not worth the maintenance cost. cAdvisor covers GlitchTip container metrics; Gatus covers its HTTP health. Errors arriving INTO GlitchTip count themselves (visible in the GlitchTip UI directly).

## References

- Prometheus scrape config syntax: <https://prometheus.io/docs/prometheus/latest/configuration/configuration/#scrape_config>
- Authelia telemetry: <https://www.authelia.com/configuration/telemetry/metrics/>
- Meilisearch metrics: <https://docs.meilisearch.com/learn/experimental/metrics_endpoint.html>
- Sister docs:
  - [`grafana-dashboards-setup.md`](grafana-dashboards-setup.md) (dashboards + host filter variable)
  - [`grafana-provisioning-setup.md`](grafana-provisioning-setup.md) (datasource provisioning)
