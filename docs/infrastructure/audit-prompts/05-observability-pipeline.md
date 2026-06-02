# 05 — Observability Pipeline (fleet-wide, hub-rooted)

**Last Updated:** 2026-06-02 (rewritten — observability is centralized on vps1; spokes are agents — patched 2026-06-02 evening after live-validation: fixed 3 probe bugs — Loki probe was via `docker exec prometheus` but prometheus can't resolve `loki:3100` from its compose network, Grafana datasources probe used invalid `Bearer admin` auth, GlitchTip probe used `wget` which isn't in its python-only image)
**Run mode:** **fleet-wide, hub-rooted.** Most probes from vps1 (Prometheus / Grafana / Loki / Alertmanager queries). Spoke-side checks confirm agents are pushing.
**Scope:** end-to-end check that metrics are scraped, logs shipped, alerts fire, errors captured, status probes green.
**Time budget:** ~15 min probes + ~15 min analysis.

---

## Stack context

```text
- Hub (vps1) centralizes the observability stack:
  - Prometheus (15-job scrape target list; 18/18 active targets)
  - Grafana (5 Fabrik-folder dashboards with $host template variable)
  - Loki (mesh-bound at 10.99.0.1:3100 for spoke push)
  - Alertmanager → Apprise → Telegram
  - Gatus (synthetic uptime probes)
  - GlitchTip (error tracking; UI + worker + clickhouse)
  - cadvisor, node-exporter, promtail, postgres-exporter, redis-exporter,
    pushgateway (vps1's own agents)
- Spokes (vps2/vps3) run agents only:
  - node-exporter (host metrics → Prometheus over mesh)
  - cadvisor (container metrics → Prometheus over mesh)
  - promtail (container logs → Loki over mesh)
- Spoke observability was broken 2026-05-31 evening → 2026-06-01 evening
  because UFW default-deny didn't have a mesh-allow rule (W8 finding).
  Fixed with `ufw allow from 10.99.0.0/24` on each spoke.
- 'host' label is propagated to every metric and log stream (W11 work).
  Filter dashboards/alerts with $host or {host=...}.
- Alert rule group 'spoke_health' active (SpokeDown / SpokeHighCPU / SpokeHighRAM).
```

---

## Data collection — HUB (vps1)

```bash
ssh vps bash <<'EOF'
echo "=== PROMETHEUS TARGETS (expect 18/18 up across 15 jobs) ==="
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

- 18 / 18 targets `up` (12 vps1-local jobs + 3 spoke job-groups × 2 targets = 6).
- `host` label present on every active series.
- Scrape errors in last hour: ideally zero.
- Grafana dashboards load + render historical 7d range.
- `$host` template variable on all 5 Fabrik dashboards works (regex `/^vps/`).

### Log pipeline (Docker → Promtail → Loki)

- Hub: `promtail` container running; Loki ingests local + spoke logs.
- Spokes: outbound TCP conns to `10.99.0.1:3100` visible in `ss -tn`.
- Loki returns `host` label with values `["vps1", "vps2", "vps3"]`.
- Spoke `promtail.yaml` `clients[].url` points at `http://10.99.0.1:3100/loki/api/v1/push`.

### Alert pipeline (Prometheus → Alertmanager → Apprise → Telegram)

- Alertmanager cluster status `ready` / `active`.
- `spoke_health` rule group loaded (`SpokeDown`, `SpokeHighCPU`, `SpokeHighRAM`).
- Active alerts: only expected ones (or none). Investigate firing.
- Active silences: only legitimate planned-downtime silences; expired ones cleaned.
- Apprise reachable from vps1 cluster on `http://apprise:8000/notify/alerts`.

### Error pipeline (App → Sentry SDK → GlitchTip)

- `glitchtip-web` `/_health/` returns 200.
- DSN injection verified for any app shape with `exposes_metrics`: see W14 — `docker inspect <main> | grep SENTRY_DSN` (Lesson 31).
- GlitchTip not blocked by Authelia for the SDK ingest path (`/api/<id>/store/`).

### Uptime monitoring (Gatus → Apprise → Telegram)

- 16 Gatus config files, 21 endpoint definitions (verify against `vps-complete-inventory.md`; the file count drifts up when new endpoint files are added — endpoint count is the more stable signal).
- No persistently-failing endpoints (would indicate a real outage OR a stale endpoint).
- Authelia bypass on `*.vps1.ocoron.com → /health` working.

### Spoke observability health

- Each spoke's 3 agents (node-exporter, cadvisor, promtail) running.
- UFW mesh-allow rule present (W8 fix).
- No agent log errors in last 5 min.
- Hub Prometheus shows `node-spokes` / `cadvisor-spokes` / `promtail-spokes` jobs each with 2 targets up.

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
