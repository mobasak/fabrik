#!/bin/bash
# Observability pipeline audit data collection — runs ON the VPS via SSH.
# Usage: ssh vps 'bash -s' < scripts/audit/05-observability.sh
set -uo pipefail

# Helper: run curl from inside coolify network
coolify_curl() {
  sudo docker run --rm --network coolify curlimages/curl:latest -sS "$@" 2>/dev/null
}

echo "========== PROMETHEUS =========="
echo "--- targets ---"
sudo docker exec prometheus wget -qO- "http://localhost:9090/api/v1/targets?state=any" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    for t in d['data']['activeTargets']:
        print(f\"{t['labels']['job']:20s} {t['health']:8s} {t['scrapeUrl']}\")
except: print('FAILED to parse prometheus targets')
"
echo "--- alert rules ---"
sudo docker exec prometheus wget -qO- "http://localhost:9090/api/v1/rules" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    for g in d['data']['groups']:
        for r in g['rules']:
            print(f\"{r['name']:40s} {r.get('state',''):10s} {r['type']}\")
except: print('FAILED to parse rules')
"
echo "--- ready ---"
coolify_curl -o /dev/null -w "%{http_code}" "http://prometheus:9090/-/ready"
echo ""

echo ""
echo "========== ALERTMANAGER =========="
echo "--- active alerts ---"
AM_CONTAINER=$(docker ps --filter name=alertmanager --format "{{.Names}}" | head -1)
if [ -n "$AM_CONTAINER" ]; then
  sudo docker exec "$AM_CONTAINER" wget -qO- "http://localhost:9093/api/v2/alerts" 2>/dev/null | python3 -c "
import json,sys
try:
    alerts=json.load(sys.stdin)
    if not alerts: print('No active alerts')
    else:
        for a in alerts:
            print(f\"{a['labels'].get('alertname','?'):30s} {a['status']['state']:10s}\")
except: print('FAILED to parse alerts')
  "
else
  echo "alertmanager container not found"
fi

echo ""
echo "========== LOKI =========="
echo "--- ready ---"
coolify_curl "http://loki:3100/ready"
echo "--- labels ---"
coolify_curl "http://loki:3100/loki/api/v1/labels"
echo ""
echo "--- container_name label values ---"
coolify_curl "http://loki:3100/loki/api/v1/label/container_name/values" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    values = d.get('data',[])
    print(f'{len(values)} container labels in Loki')
    # Check if the 5 filtered containers leak through
    filtered = ['coolify-db','coolify-redis','coolify-realtime','coolify-sentinel','ocoron-com-backup-1']
    leaked = [v for v in values if v in filtered]
    if leaked: print(f'WARNING: noise filter leak: {leaked}')
    else: print('Noise filter: working (5 containers excluded)')
except: print('FAILED to parse Loki labels')
"

echo ""
echo "========== PROMTAIL =========="
coolify_curl "http://promtail:9080/metrics" | grep -E "promtail_sent_entries_total|promtail_dropped_entries_total|promtail_targets_active_total|promtail_files_active_total"

echo ""
echo "========== GRAFANA =========="
TOKEN=$(grep '^GRAFANA_SERVICE_ACCOUNT_TOKEN=' /opt/fabrik/.env 2>/dev/null | cut -d= -f2-)
if [ -n "$TOKEN" ]; then
  echo "--- datasources ---"
  coolify_curl -H "Authorization: Bearer $TOKEN" "http://grafana:3000/api/datasources" | python3 -c "
import json,sys
try:
    for d in json.load(sys.stdin):
        print(f\"{d['name']:15s} {d['type']:12s} {d['url']}\")
except: print('FAILED')
  "
  echo "--- dashboard count ---"
  coolify_curl -H "Authorization: Bearer $TOKEN" "http://grafana:3000/api/search?type=dash-db" | python3 -c "
import json,sys
try: print(f\"{len(json.load(sys.stdin))} dashboards\")
except: print('FAILED')
  "
else
  echo "GRAFANA_SERVICE_ACCOUNT_TOKEN not found in .env"
fi

echo ""
echo "========== GLITCHTIP =========="
echo "--- api health ---"
coolify_curl -o /dev/null -w "HTTP %{http_code}" "http://glitchtip-web:8000/api/0/"
echo ""
GT_TOKEN=$(grep '^GLITCHTIP_AUTH_TOKEN=' /opt/fabrik/.env 2>/dev/null | cut -d= -f2-)
GT_ORG=$(grep '^GLITCHTIP_ORG_SLUG=' /opt/fabrik/.env 2>/dev/null | cut -d= -f2-)
if [ -n "$GT_TOKEN" ] && [ -n "$GT_ORG" ]; then
  echo "--- projects ---"
  coolify_curl -H "Authorization: Bearer $GT_TOKEN" "http://glitchtip-web:8000/api/0/organizations/$GT_ORG/projects/" | python3 -c "
import json,sys
try:
    projects=json.load(sys.stdin)
    print(f'{len(projects)} GlitchTip projects')
    for p in projects:
        print(f\"  {p['slug']:30s} firstEvent={p.get('firstEvent','none')}\")
except: print('FAILED')
  "
else
  echo "GLITCHTIP tokens not found in .env"
fi

echo ""
echo "========== GATUS =========="
coolify_curl "http://gatus:8080/api/v1/endpoints/statuses" 2>/dev/null | python3 -c "
import json,sys
try:
    data=json.load(sys.stdin)
    for ep in data:
        name = ep.get('name','?')
        group = ep.get('group','?')
        results = ep.get('results',[])
        last = results[-1] if results else {}
        status = 'UP' if last.get('success') else 'DOWN'
        print(f\"{group:20s} {name:30s} {status}\")
except: print('FAILED to parse Gatus')
" | head -30

echo ""
echo "========== PUSHGATEWAY =========="
coolify_curl "http://pushgateway:9091/metrics" 2>/dev/null | grep "fabrik_audit" | head -5 || echo "no fabrik_audit metrics"

echo ""
echo "========== STACK CONTAINER HEALTH =========="
for name in prometheus grafana loki promtail gatus alertmanager glitchtip-web glitchtip-worker netdata cadvisor node-exporter pushgateway redis-exporter postgres-exporter; do
  match=$(docker ps --format "{{.Names}} {{.Status}}" | grep "$name" | head -1)
  echo "${match:-MISSING: $name}"
done

echo ""
echo "========== END =========="
