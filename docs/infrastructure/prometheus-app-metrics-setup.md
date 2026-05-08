# Prometheus app-level metrics — runbook

Status: **DEPLOYED 2026-05-08**

This runbook covers Prometheus scrape configuration for application-level metrics from infrastructure services. It complements `cadvisor` (container-level) and `node-exporter` (host-level) which were already in place.

## What's scraped

| Job | Endpoint | Auth | Why this job |
|---|---|---|---|
| `grafana` | `http://grafana:3000/metrics` | none (anonymous) | dashboard query rates, datasource health |
| `authelia` | `http://authelia:9959/metrics` | none (telemetry port) | auth success/fail rates, session counts, request latency |
| `meilisearch` | `http://meilisearch:7700/metrics` | Bearer token (master key) | search latency, index size, HTTP request counters |
| ~~glitchtip~~ | — | — | **NOT SCRAPED.** GlitchTip ships without `django-prometheus`. cAdvisor + Gatus cover it. |

## Sample useful queries

```promql
# Authelia auth failure rate
rate(authelia_request{code!~"2.."}[5m])

# Grafana dashboard render latency (p95)
histogram_quantile(0.95, sum(rate(grafana_http_request_duration_seconds_bucket{handler!~"/api/health|/api/.*/metrics"}[5m])) by (le, handler))

# Meilisearch search QPS
rate(meilisearch_http_requests_total{path="/indexes/{uid}/search"}[5m])
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

**Important — config drift**: on this VPS, the file at `/opt/authelia/config/configuration.yml` is a **working copy only** — it is NOT the file Authelia loads. The container mounts a Docker volume (`hks48k8sg8o4co4co08co00o_authelia-config`) at `/config/`. The actual loaded file is at `/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml`.

Edit that file (with sudo) and `docker restart authelia-...` (NEVER SIGHUP — Authelia exits on SIGHUP). Then sync `/opt/authelia/config/` so the working copy doesn't drift.

After restart, look for log line:
```
"Listening for non-TLS connections on '[::]:9959' path '/metrics'","server":"metrics"
```

### 2. Grafana — already exposed
Grafana exposes `/metrics` on port 3000 anonymously by default. Just add the scrape job.

### 3. Meilisearch — needs experimental flag
Meilisearch requires `MEILI_EXPERIMENTAL_ENABLE_METRICS=true` env var AND the master key as Bearer token to expose `/metrics`.

```bash
# Push env var via Coolify API (Application UUID for meilisearch)
curl -X POST -H "Authorization: Bearer $COOLIFY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"key":"MEILI_EXPERIMENTAL_ENABLE_METRICS","value":"true","is_preview":false,"is_literal":true}' \
  "https://coolify.vps1.ocoron.com/api/v1/applications/<MEILI_UUID>/envs"

# Trigger redeploy
curl -X POST -H "Authorization: Bearer $COOLIFY_API_TOKEN" \
  "https://coolify.vps1.ocoron.com/api/v1/deploy?uuid=<MEILI_UUID>&force=false"
```

### 4. Coolify drops network aliases on redeploy

**Operational gotcha** — when a Coolify Application is redeployed, the new container retains only the timestamped UUID alias (`<uuid>-<timestamp>`). Friendly aliases like `meilisearch`, `glitchtip-web`, `gotenberg`, `browserless` that other services depend on are **dropped**.

Workaround applied for meilisearch:
```bash
sudo docker network disconnect coolify <new-container-name>
sudo docker network connect --alias meilisearch coolify <new-container-name>
```

This is **temporary** — survives until next redeploy, then drops again. Permanent fix requires either:
- Adding `networks: { coolify: { aliases: [meilisearch] } }` to the Coolify Application's docker-compose
- OR a watcher script that re-applies aliases when Coolify deploys these UUIDs

This affects every service that depends on these aliases: prometheus scraping, gatus monitoring, fabrik microservices reaching shared utilities. Worth a separate hardening task.

### 5. Reload Prometheus (no restart needed)

```bash
sudo docker exec prometheus wget -qO- --post-data="" http://localhost:9090/-/reload
```

## Verifying targets are up

```bash
sudo docker exec prometheus wget -qO- "http://localhost:9090/api/v1/targets?state=any" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); [print(f\"{t['labels']['job']:14s} {t['health']:6s}\") for t in d['data']['activeTargets']]"
```

Or via Grafana → Explore → Prometheus datasource → run `up{job=~\"authelia|grafana|meilisearch\"}` — all should return 1.
