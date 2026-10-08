#!/bin/bash
# Observability pipeline audit data collection — runs ON the VPS via SSH.
# Usage: ssh vps 'bash -s' < scripts/audit/05-observability.sh
set -uo pipefail

# Helper: run curl from inside the fabrik network (renamed from coolify 2026-05-31)
fabrik_curl() {
  sudo docker run --rm --network fabrik curlimages/curl:latest -sS "$@" 2>/dev/null
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
fabrik_curl -o /dev/null -w "%{http_code}" "http://prometheus:9090/-/ready"
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
fabrik_curl "http://loki:3100/ready"
echo "--- labels ---"
fabrik_curl "http://loki:3100/loki/api/v1/labels"
echo ""
echo "--- container_name label values ---"
fabrik_curl "http://loki:3100/loki/api/v1/label/container_name/values" | python3 -c "
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
echo "========== ALLOY =========="
# Metric names measured locally (grafana/alloy:v1.20.1 run against a throwaway
# grafana/loki:3.4.2, see tests/test_alloy_consumers.py docstring for the exact
# commands): loki.source.file + loki.write expose loki_source_file_* from the
# first tail and loki_write_* only after the first successful push to Loki —
# there is no Alloy equivalent of promtail_targets_active_total (the nearest
# is loki_source_file_files_active_total, the files actively tailed).
#
# Fail-closed (O1): an unreachable Alloy / missing container prints nothing from
# a bare curl|grep, and a cold start (no push yet) silently drops the loki_write_*
# line out of the grep -E output — both read as a clean audit unless said aloud.
#
# Here-strings, not pipes (O12): under `set -uo pipefail`, `echo "$x" | grep -q ...`
# has grep exit at the first match while echo is still writing — on a body over
# ~64 KiB (a pipe buffer) echo gets SIGPIPE, pipefail reports 141, and `! ...`
# reads that as "grep found nothing", printing a false WARNING on a healthy Alloy.
# A here-string feeds grep directly with no pipe to break.
_alloy_metrics=$(fabrik_curl "http://alloy:12345/metrics")
if [ -z "$_alloy_metrics" ]; then
  echo "FAILED: alloy metrics unreachable on alloy:12345"
else
  grep -E "loki_write_sent_entries_total|loki_write_dropped_entries_total|loki_source_file_files_active_total" <<<"$_alloy_metrics"
  if ! grep -q "^loki_write_sent_entries_total" <<<"$_alloy_metrics"; then
    echo "WARNING: alloy has not pushed to Loki yet (no loki_write_* series)"
  fi
fi

echo ""
echo "========== GRAFANA =========="
TOKEN=$(grep '^GRAFANA_SERVICE_ACCOUNT_TOKEN=' /opt/fabrik/.env 2>/dev/null | cut -d= -f2-)
if [ -n "$TOKEN" ]; then
  echo "--- datasources ---"
  fabrik_curl -H "Authorization: Bearer $TOKEN" "http://grafana:3000/api/datasources" | python3 -c "
import json,sys
try:
    for d in json.load(sys.stdin):
        print(f\"{d['name']:15s} {d['type']:12s} {d['url']}\")
except: print('FAILED')
  "
  echo "--- dashboard count ---"
  fabrik_curl -H "Authorization: Bearer $TOKEN" "http://grafana:3000/api/search?type=dash-db" | python3 -c "
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
fabrik_curl -o /dev/null -w "HTTP %{http_code}" "http://glitchtip-web:8000/api/0/"
echo ""
GT_TOKEN=$(grep '^GLITCHTIP_AUTH_TOKEN=' /opt/fabrik/.env 2>/dev/null | cut -d= -f2-)
GT_ORG=$(grep '^GLITCHTIP_ORG_SLUG=' /opt/fabrik/.env 2>/dev/null | cut -d= -f2-)
if [ -n "$GT_TOKEN" ] && [ -n "$GT_ORG" ]; then
  echo "--- projects ---"
  fabrik_curl -H "Authorization: Bearer $GT_TOKEN" "http://glitchtip-web:8000/api/0/organizations/$GT_ORG/projects/" | python3 -c "
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
fabrik_curl "http://gatus:8080/api/v1/endpoints/statuses" 2>/dev/null | python3 -c "
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
fabrik_curl "http://pushgateway:9091/metrics" 2>/dev/null | grep "fabrik_audit" | head -5 || echo "no fabrik_audit metrics"

echo ""
echo "========== STACK CONTAINER HEALTH =========="
for name in prometheus grafana loki alloy gatus alertmanager glitchtip-web glitchtip-worker netdata cadvisor node-exporter pushgateway redis-exporter postgres-exporter; do
  match=$(docker ps --format "{{.Names}} {{.Status}}" | grep "$name" | head -1)
  echo "${match:-MISSING: $name}"
done

echo ""
echo "========== END =========="
