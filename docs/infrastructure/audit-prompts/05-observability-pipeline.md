# 05 — Observability Pipeline (fleet-wide, hub-rooted)

**Last Updated:** 2026-06-07 (aro-wake SLI scrape coverage on the full-fleet `aro-wake` job at `10.0.1.1:8201` (hub via docker-bridge) + `10.99.0.{2,3}:8201` (spokes via wg0); audit must confirm all 3 targets `up` and the 2 alert rules `AroWakeLowSuccessRate`+`AroWakeCostBurnHigh` are loaded in the `aro_wake` rule group. **Two updates 2026-06-07**: `AroWakeLowSuccessRate` denominator now excludes `status="rate_limited"`; the stale `netdata` scrape job has been REMOVED from `prometheus.yml` after it caused a 24× Telegram flood overnight via the Phase 4 wire's `repeat_interval: 30m`. Audit must verify no `up == 0` for the `netdata` job (job no longer exists).)
**Run mode:** **fleet-wide, hub-rooted.** Most probes from vps1 (Prometheus / Grafana / Loki / Alertmanager queries). Spoke-side checks confirm agents are pushing.
**Scope:** end-to-end check that metrics are scraped, logs shipped, alerts fire, errors captured, status probes green.
**Time budget:** ~15 min probes + ~15 min analysis.

---

## Stack context

```text
- Hub (vps1) centralizes the observability stack:
  - Prometheus (13 jobs configured in `prometheus.yml`, 12 active with targets,
    14 active scrape targets total — verified 2026-06-07T20:20Z; `fabrik-services`
    is a placeholder job with no targets yet; `node-spokes`/`cadvisor-spokes`/
    `promtail-spokes` jobs were removed/never-shipped; spokes are scraped only
    via the `aro-wake` job which has 3 targets covering hub+vps2+vps3)
  - Grafana (5 Fabrik-folder dashboards with $host template variable; aro-wake
    dashboard deliberately deferred — PromQL + alert rules suffice today)
  - Loki (mesh-bound at 10.99.0.1:3100 for spoke push)
  - Alertmanager → Apprise → Telegram (with aro-wake routed receiver since
    2026-06-05 Phase 4; severity=~"critical|warning" routes to aro-wake FIRST,
    `continue: true` keeps telegram fallback)
  - Gatus (synthetic uptime probes)
  - GlitchTip (error tracking; UI + worker + clickhouse)
  - cadvisor, node-exporter, promtail, postgres-exporter, redis-exporter,
    pushgateway (vps1's own agents)
- Spokes (vps2/vps3) run agents AND aro-wake:
  - node-exporter (host metrics → Prometheus over mesh)
  - cadvisor (container metrics → Prometheus over mesh)
  - promtail (container logs → Loki over mesh)
  - aro-wake (since 2026-06-06; FastAPI on 0.0.0.0:8201 exposing
    `POST /wake` + `GET /health` + `GET /metrics`)
- Spoke observability was broken 2026-05-31 evening → 2026-06-01 evening
  because UFW default-deny didn't have a mesh-allow rule (W8 finding).
  Fixed with `ufw allow from 10.99.0.0/24` on each spoke.
- 'host' label is propagated to every metric and log stream (W11 work).
  Filter dashboards/alerts with $host or {host=...}.
- Alert rule groups (verified live 2026-06-07T20:20Z): `aro_wake` (2 rules:
  AroWakeLowSuccessRate, AroWakeCostBurnHigh — both per-host); `container_health`
  (6 rules: ContainerDown, ContainerHighCPU, ContainerHighMemory,
  ContainerMemoryHighOfHost, ContainerOOMKilled, ContainerRestarting);
  `host_health` (3 rules: HostHighCPU, HostHighMemory, HostDiskFull);
  `service_health` (1 rule: ServiceUnhealthy — note: the `netdata` instance
  this used to fire for was removed 2026-06-07 after a 24× Telegram flood);
  `fabrik-registrar-drift` (1 rule). TOTAL: 13 rules across 5 groups.
  **No** `spoke_health` group exists today (earlier docs referenced
  SpokeDown/SpokeHighCPU/SpokeHighRAM which never landed or were removed).
```

---

## Data collection — HUB (vps1)

```bash
ssh vps bash <<'EOF'
echo "=== PROMETHEUS TARGETS (expect 14/14 up across 12 jobs as of 2026-06-07 (spoke-side scrape jobs are NOT in current prometheus.yml — aro-wake covers all 3 hosts in a single job)) ==="
sudo docker exec prometheus wget -qO- http://localhost:9090/api/v1/targets 2>&1 | python3 -c "
import json, sys
d = json.load(sys.stdin)
targets = d['data']['activeTargets']
up = [t for t in targets if t['health']=='up']
down = [t for t in targets if t['health']!='up']
jobs = sorted({t['labels'].get('job') for t in targets})
print(f'  Targets total: {len(targets)} (up: {len(up)}, down: {len(down)})')
print(f'  Jobs ({len(jobs)}): {jobs}')
for t in down:
    print(f'  DOWN: {t[\"labels\"].get(\"job\")} {t.get(\"scrapeUrl\")} — {t.get(\"lastError\")[:80]}')
"
echo
echo "=== PROMETHEUS RECENT SCRAPE ERRORS ==="
sudo docker logs prometheus --since 1h 2>&1 | grep -iE "error|warn" | tail -15
echo
echo "=== ALERTMANAGER ==="
sudo docker exec alertmanager wget -qO- http://localhost:9093/api/v2/status 2>&1 | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('  Cluster: ', d.get('cluster',{}).get('status'))
print('  Uptime:  ', d.get('uptime'))
"
sudo docker exec alertmanager wget -qO- http://localhost:9093/api/v2/alerts 2>&1 | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'  Active alerts: {len(d)}')
for a in d[:10]:
    print(f'    [{a.get(\"status\",{}).get(\"state\")}] {a[\"labels\"].get(\"alertname\")} on {a[\"labels\"].get(\"host\",\"?\")}')
"
echo
echo "=== ALERTING SILENCES ==="
sudo docker exec alertmanager wget -qO- http://localhost:9093/api/v2/silences 2>&1 | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'  Silences: {len(d)} (any current ones during this audit?)')
for s in d[:5]:
    print(f'    [{s.get(\"status\",{}).get(\"state\")}] {s.get(\"comment\",\"-\")[:60]} (ends {s.get(\"endsAt\",\"?\")})')
"
echo
echo "=== LOKI INGEST + HOST LABEL VALUES ==="
# Probe via a throwaway alpine on the `fabrik` network — `docker exec prometheus`
# does NOT work: prometheus is on a separate compose network and can't resolve
# `loki:3100` ("bad address"). The fabrik-network probe is the canonical path.
sudo docker run --rm --network fabrik alpine sh -c 'wget -qO- http://loki:3100/loki/api/v1/label/host/values' 2>&1 | python3 -m json.tool 2>&1 | head -10
echo "(expect [\"vps1\",\"vps2\",\"vps3\"] — if vps1 is missing, hub promtail isn't tagging its own stream; fix by adding a static label_config in /opt/monitoring/configs/promtail/promtail-config.yaml)"
echo
echo "=== GATUS ENDPOINT COUNT ==="
sudo find /opt/monitoring/configs/gatus -name "*.yaml" | xargs grep -h "^  - name:" 2>/dev/null | wc -l | xargs echo "Gatus endpoint count:"
sudo find /opt/monitoring/configs/gatus -name "*.yaml" | wc -l | xargs echo "Gatus config files:"
echo
echo "=== GRAFANA LIVENESS ==="
# Grafana /api/datasources REQUIRES auth and `Bearer admin` is not a real token.
# Datasources are stored in /var/lib/grafana/grafana.db (no host-side provisioning
# files in this deployment) and the grafana image lacks sqlite3, so listing them
# from the shell is awkward. /api/health is anonymous and confirms both grafana
# liveness AND DB reachability — that's the right probe for an audit. To inspect
# datasources, use the UI at https://grafana.vps1.ocoron.com/datasources.
sudo docker exec grafana wget -qO- http://localhost:3000/api/health 2>&1 | head -c 200

echo
echo "=== GLITCHTIP HEALTH ==="
# glitchtip-web is python-only (no wget/curl). Use the in-container python3.
sudo docker exec glitchtip-web python3 -c "
import urllib.request
r = urllib.request.urlopen('http://localhost:8000/_health/')
print(f'  status: {r.status}  body[:80]: {r.read()[:80]!r}')
" 2>&1 | head -3
echo
echo "=== AGENTS LOCAL ON HUB ==="
sudo docker ps --filter "name=cadvisor" --filter "name=node-exporter" --filter "name=promtail" --filter "name=postgres-exporter" --filter "name=redis-exporter" --filter "name=pushgateway" --format "{{.Names}} {{.Status}}"
EOF
```

## Data collection — SPOKES (vps2, vps3) — confirm agents push to hub

```bash
ssh vps2 bash <<'EOF'    # repeat for vps3
echo "=== AGENT CONTAINERS ==="
sudo docker ps --filter "name=node-exporter" --filter "name=cadvisor" --filter "name=promtail" --format "table {{.Names}}\t{{.Status}}"
echo
echo "=== AGENT BIND ADDRESSES (mesh-only) ==="
sudo ss -tlnp | grep -E ':9100|:8080|:9080'
echo
echo "=== OUTBOUND PUSH CONNS TO HUB ==="
sudo ss -tnp 2>&1 | grep -E "10\\.99\\.0\\.1:(3100|9090|9091)" | head -10
echo
echo "=== UFW MESH-ALLOW (must exist; W8 fix) ==="
sudo ufw status verbose | grep -E "10\\.99\\.0\\.0/24"
echo
echo "=== PROMTAIL CONFIG (target Loki at 10.99.0.1:3100) ==="
sudo grep -A2 "url:" /opt/monitoring-agent/promtail.yaml 2>/dev/null | head -10
echo
echo "=== AGENT LOGS (last 5 min, any errors?) ==="
sudo docker logs --since 5m node-exporter 2>&1 | tail -5
sudo docker logs --since 5m cadvisor 2>&1 | tail -5
sudo docker logs --since 5m promtail 2>&1 | tail -5
EOF
```

---

## Analysis checklist

### Metrics pipeline (Prometheus → Grafana)

- 14 / 14 targets `up` (11 vps1-local jobs + aro-wake job covering all 3 hosts = 3). The earlier spoke-side jobs (node-spokes, cadvisor-spokes, promtail-spokes) are NOT in the current `prometheus.yml`.
- `host` label present on every active series.
- Scrape errors in last hour: ideally zero.
- Grafana dashboards load + render historical 7d range.
- `$host` template variable on all 5 Fabrik dashboards works (regex `/^vps/`).
- **aro-wake job (since 2026-06-06)**: 3 targets up (vps1 at `10.0.1.1:8201`, vps2 at `10.99.0.2:8201`, vps3 at `10.99.0.3:8201`); 8 metric families present (`aro_wake_requests_total`, `aro_wake_cost_usd_total`, `aro_wake_dedup_drops_total`, `aro_wake_hop_limit_exceeded_total`, `aro_wake_forward_suppressed_total`, `aro_wake_storm_breaker_trips_total`, `aro_wake_pending_queue_size`, `aro_wake_active_sessions`); cross-mesh scrape latency on spokes ~270ms is normal (vs ~1.4ms hub).

### Log pipeline (Docker → Promtail → Loki)

- Hub: `promtail` container running; Loki ingests local + spoke logs.
- Spokes: outbound TCP conns to `10.99.0.1:3100` visible in `ss -tn`.
- Loki returns `host` label with values `["vps1", "vps2", "vps3"]`.
- Spoke `promtail.yaml` `clients[].url` points at `http://10.99.0.1:3100/loki/api/v1/push`.
- **aro-wake logs are host-local** (not shipped via Promtail's docker-socket discovery): operators read `/var/log/aro-wake.log` directly via SSH; not in Loki.

### Alert pipeline (Prometheus → Alertmanager → Apprise → Telegram)

- Alertmanager cluster status `ready` / `active`.
- ~~`spoke_health` rule group loaded (`SpokeDown`, `SpokeHighCPU`, `SpokeHighRAM`).~~ — **NOT PRESENT** as of 2026-06-07T20:20Z. The current rule groups are listed above in § Stack context. If a future drill confirms spoke_health is wanted, add via `configs/prometheus/rules/alerts.yml`; otherwise drop this expectation from audits.
- **`aro_wake` rule group loaded (since 2026-06-06): `AroWakeLowSuccessRate` + `AroWakeCostBurnHigh`, both per-host via `by (host)`; both `inactive` is the healthy state.**
- Active alerts: only expected ones (or none). Investigate firing.
- Active silences: only legitimate planned-downtime silences; expired ones cleaned.
- Apprise reachable from vps1 cluster on `http://apprise:8000/notify/alerts`.
- **Alertmanager → aro-wake wire (since 2026-06-05 Phase 4): `aro-wake-routed` receiver exists, `severity=~"critical|warning"` route matches it with `continue: true` so the telegram fallback stays.**

### Error pipeline (App → Sentry SDK → GlitchTip)

- `glitchtip-web` `/_health/` returns 200.
- DSN injection verified for any app shape with `exposes_metrics`: see W14 — `docker inspect <main> | grep SENTRY_DSN` (Lesson 31).
- GlitchTip not blocked by Authelia for the SDK ingest path (`/api/<id>/store/`).

### Uptime monitoring (Gatus → Apprise → Telegram)

- 18 Gatus config files, 36 endpoint definitions across 7 groups (verified live 2026-06-07T20:20Z: `apps:8`, `core:5`, `data:3`, `external:5`, `observability:7`, `services:5`, `trio-aro-wake:3`). Endpoint count is the stable signal; file count drifts as endpoints are split.
- No persistently-failing endpoints (would indicate a real outage OR a stale endpoint).
- Authelia bypass on `*.vps1.ocoron.com → /health` working.

### Spoke observability health

- Each spoke's 3 agents (node-exporter, cadvisor, promtail) running.
- UFW mesh-allow rule present (W8 fix).
- No agent log errors in last 5 min.
- ~~Hub Prometheus shows `node-spokes` / `cadvisor-spokes` / `promtail-spokes` jobs each with 2 targets up~~ — **NOT in `prometheus.yml` as of 2026-06-07T20:20Z**. Live spoke-side scrape is the `aro-wake` job (3 targets: vps1, vps2, vps3 over mesh). Spoke node/container exporters are running on each spoke but not currently scraped from vps1 — to restore, add the static_configs blocks back to `prometheus.yml` and SIGHUP. Mesh + UFW are already permissive.

### W14 / W15 spoke-deploy verification path

- vps2 + vps3 Traefik exposed publicly with W15 `gzip@docker` middleware (per `docker inspect traefik`).
- vps2 `/opt/traefik/acme.json` populated (first cert issued 2026-06-02 W14/W15 verify).
- Verifier path `https://<spec>.vps2.ocoron.com/health` returns 200 for deployed services.

---

## Output format

```markdown
## Observability Audit — Fleet — <UTC date>

**Verdict:** GREEN / YELLOW / RED
**Per-pipeline status:**
| Pipeline | State | Notes |
| :--- | :--- | :--- |
| Metrics (Prometheus → Grafana)        | GREEN/YELLOW/RED | <one-line> |
| Logs (Promtail → Loki)                | ... | <one-line> |
| Alerts (Alertmanager → Apprise)       | ... | <one-line> |
| Errors (GlitchTip)                    | ... | <one-line> |
| Uptime (Gatus)                        | ... | <one-line> |

### Per-host agent status
| Host | node-exporter | cadvisor | promtail | mesh push |
| :--- | :--- | :--- | :--- | :--- |
| vps1 | running | running | running | local |
| vps2 | ... | ... | ... | ✓/✗ |
| vps3 | ... | ... | ... | ✓/✗ |

### Findings
1. [severity] <pipeline> — <issue>
   - Evidence
   - Fix
```
