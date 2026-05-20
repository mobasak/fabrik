# Observability Pipeline Audit — Metrics, Logs, Alerts, Errors

Verify the entire observability stack is functioning end-to-end: metrics are scraped, logs are shipped, alerts fire, errors are captured. A broken observability pipeline is worse than no observability — it gives false confidence.

## Stack

| Component | Container | Purpose | Internal URL |
|-----------|-----------|---------|-------------|
| Prometheus | `prometheus` | Metrics collection | `http://prometheus:9090` |
| Alertmanager | `alertmanager-*` | Alert routing → Telegram | `http://alertmanager:9093` |
| Grafana | `grafana-*` | Dashboards | `http://grafana:3000` |
| Loki | `loki-*` | Log aggregation | `http://loki:3100` |
| Promtail | `promtail-*` | Log shipping (Docker → Loki) | `http://promtail:9080` |
| Gatus | `gatus-*` | Uptime monitoring | `http://gatus:8080` |
| GlitchTip | `glitchtip-web-*` + `glitchtip-worker-*` | Error tracking (Sentry-compatible) | `http://glitchtip-web:8000` |
| Netdata | `netdata-*` | Real-time system metrics | `http://netdata:19999` |
| Pushgateway | `pushgateway` | Push-based metrics (drift alerts) | `http://pushgateway:9091` |
| cAdvisor | `cadvisor-*` | Container-level metrics | `http://cadvisor:8080` |
| Node Exporter | `node-exporter-*` | Host-level metrics | `http://node-exporter:9100` |

## Data Collection

**Automated:** `ssh vps 'sudo bash -s' < /opt/fabrik/scripts/audit/05-observability.sh`

**Or manual:**

```bash
# 1. Prometheus — targets health
sudo docker exec prometheus wget -qO- "http://localhost:9090/api/v1/targets?state=any" 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
for t in d['data']['activeTargets']:
    print(f\"{t['labels']['job']:20s} {t['health']:8s} {t['scrapeUrl']}\")
"

# 2. Prometheus — alert rules
sudo docker exec prometheus wget -qO- "http://localhost:9090/api/v1/rules" 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
for g in d['data']['groups']:
    for r in g['rules']:
        state = r.get('state','')
        print(f\"{r['name']:40s} {state:10s} {r['type']}\")
"

# 3. Alertmanager — active alerts
sudo docker exec $(sudo docker ps --filter name=alertmanager --format "{{.Names}}") wget -qO- "http://localhost:9093/api/v2/alerts" 2>/dev/null | python3 -c "
import json,sys
alerts=json.load(sys.stdin)
if not alerts: print('No active alerts')
else:
    for a in alerts:
        print(f\"{a['labels'].get('alertname','?'):30s} {a['status']['state']:10s}\")
"

# 4. Loki — is it receiving logs?
sudo docker run --rm --network coolify curlimages/curl:latest -sS "http://loki:3100/ready"
sudo docker run --rm --network coolify curlimages/curl:latest -sS "http://loki:3100/loki/api/v1/labels"
sudo docker run --rm --network coolify curlimages/curl:latest -sS "http://loki:3100/loki/api/v1/label/container_name/values" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{len(d.get('data',[]))} container labels in Loki\")"

# 5. Promtail — shipping metrics
sudo docker run --rm --network coolify curlimages/curl:latest -sS "http://promtail:9080/metrics" | grep -E "promtail_sent_entries_total|promtail_dropped_entries_total|promtail_targets_active"

# 6. Grafana — datasources + dashboards
TOKEN=$(grep '^GRAFANA_SERVICE_ACCOUNT_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)
sudo docker run --rm --network coolify curlimages/curl:latest -sf -H "Authorization: Bearer $TOKEN" "http://grafana:3000/api/datasources" | python3 -c "import json,sys; [print(f\"{d['name']:15s} {d['type']:12s} {d['url']}\") for d in json.load(sys.stdin)]"
sudo docker run --rm --network coolify curlimages/curl:latest -sf -H "Authorization: Bearer $TOKEN" "http://grafana:3000/api/search?type=dash-db" | python3 -c "import json,sys; print(f\"{len(json.load(sys.stdin))} dashboards\")"

# 7. GlitchTip — API health + project count
sudo docker run --rm --network coolify curlimages/curl:latest -sS -o /dev/null -w "%{http_code}" "http://glitchtip-web:8000/api/0/"
GT_TOKEN=$(grep '^GLITCHTIP_AUTH_TOKEN=' /opt/fabrik/.env | cut -d= -f2-)
GT_ORG=$(grep '^GLITCHTIP_ORG_SLUG=' /opt/fabrik/.env | cut -d= -f2-)
sudo docker run --rm --network coolify curlimages/curl:latest -sS -H "Authorization: Bearer $GT_TOKEN" "http://glitchtip-web:8000/api/0/organizations/$GT_ORG/projects/" | python3 -c "import json,sys; projects=json.load(sys.stdin); print(f\"{len(projects)} GlitchTip projects\"); [print(f\"  {p['slug']:30s} firstEvent={p.get('firstEvent','none')}\") for p in projects]"

# 8. Gatus — endpoint status
sudo docker run --rm --network coolify curlimages/curl:latest -sS "http://gatus:8080/api/v1/endpoints/statuses" 2>/dev/null | python3 -c "
import json,sys
data=json.load(sys.stdin)
for ep in data:
    name = ep.get('name','?')
    group = ep.get('group','?')
    results = ep.get('results',[])
    last = results[-1] if results else {}
    status = 'UP' if last.get('success') else 'DOWN'
    print(f\"{group:20s} {name:30s} {status}\")
" 2>/dev/null | head -30

# 9. Pushgateway — has metrics?
sudo docker run --rm --network coolify curlimages/curl:latest -sS "http://pushgateway:9091/metrics" | grep "fabrik_audit" | head -5

# 10. Container health of observability stack itself
for c in prometheus grafana loki promtail gatus alertmanager glitchtip-web glitchtip-worker netdata cadvisor node-exporter pushgateway redis-exporter postgres-exporter; do
  match=$(sudo docker ps --format "{{.Names}} {{.Status}}" | grep "$c" | head -1)
  echo "${match:-$c: NOT FOUND}"
done
```

## Analysis Checklist

### Metrics Pipeline (Prometheus → Grafana)
- All scrape targets healthy? Any `down`?
- Prometheus retention adequate? (default 30d/5GB)
- Grafana datasources connected?
- Dashboard count matches expected (8 dashboards)?

### Log Pipeline (Docker → Promtail → Loki)
- Promtail `sent_entries_total` increasing? (>0 = shipping)
- Promtail `dropped_entries_total` zero? (>0 = Loki rejecting)
- Loki `container_name` label populated? (requires daemon.json tag)
- Loki has container labels for all running containers?

### Alert Pipeline (Prometheus → Alertmanager → Telegram)
- Alert rules loaded? Any in `firing` state?
- Alertmanager has active route to Telegram?
- Pushgateway has `fabrik_audit_drift_total` metrics? (hourly drift audit)

### Error Pipeline (App → Sentry SDK → GlitchTip)
- GlitchTip API reachable on internal network?
- `glitchtip-web` alias on coolify network?
- Projects have `firstEvent` populated? (null = no events ever received)

### Uptime Monitoring (Gatus → Apprise → Telegram)
- All endpoints reporting UP?
- Any endpoint showing DOWN that should be UP?

## Output Format

1. **PIPELINE STATUS** — per-pipeline: Metrics / Logs / Alerts / Errors / Uptime — each OK or BROKEN
2. **BLIND SPOTS** — what's NOT being monitored that should be
3. **DATA GAPS** — metrics/logs that exist but nobody looks at
4. **REMEDIATION** — what to fix, what to add
