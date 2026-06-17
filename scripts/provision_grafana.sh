#!/bin/bash
# provision_grafana.sh — Idempotently provision Grafana datasources + dashboards.
#
# Must be run on the VPS (accesses internal container network).
# Reads GRAFANA_SERVICE_ACCOUNT_TOKEN from /opt/fabrik/.env mirror OR env var.
#
# Safe to re-run: creates on first run, no-ops on subsequent runs.
#
# Usage (from WSL):
#   scp /opt/fabrik/scripts/provision_grafana.sh vps:/tmp/
#   ssh vps "GRAFANA_SERVICE_ACCOUNT_TOKEN='<token>' bash /tmp/provision_grafana.sh"

set -euo pipefail

TOKEN="${GRAFANA_SERVICE_ACCOUNT_TOKEN:-}"
if [ -z "$TOKEN" ]; then
  echo "ERROR: GRAFANA_SERVICE_ACCOUNT_TOKEN not set" >&2
  exit 1
fi

# Resolve grafana container IP on the fabrik network (survives redeploys)
GRAFANA_IP=$(sudo docker inspect \
  "$(sudo docker ps --format '{{.Names}}' | grep '^grafana-')" \
  --format '{{(index .NetworkSettings.Networks "fabrik").IPAddress}}')
BASE="http://${GRAFANA_IP}:3000/api"
AUTH="Authorization: Bearer ${TOKEN}"

# curl runner — use a throwaway curl container on the fabrik network
CURL() {
  sudo docker run --rm --network fabrik curlimages/curl:latest "$@"
}

echo "=== Grafana base: $BASE ==="

# --- Datasources ---
create_ds() {
  local name="$1"
  local type="$2"
  local url="$3"
  if CURL -sf -H "$AUTH" "${BASE}/datasources/name/${name}" >/dev/null 2>&1; then
    echo "[skip] datasource '${name}' already exists"
    return
  fi
  echo "[create] datasource '${name}' -> ${url}"
  CURL -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
    "${BASE}/datasources" \
    -d "{\"name\":\"${name}\",\"type\":\"${type}\",\"url\":\"${url}\",\"access\":\"proxy\",\"isDefault\":$([[ "$name" = "Prometheus" ]] && echo true || echo false)}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('  ->', d.get('message','created'), 'id=', d.get('datasource',{}).get('id'))"
}

create_ds "Prometheus" "prometheus" "http://prometheus:9090"
create_ds "Loki"       "loki"       "http://loki:3100"

# --- Dashboards ---
# Pull by grafana.com ID, set datasource overrides, import.
import_dashboard() {
  local gcom_id="$1"
  local ds_type_override="$2"   # e.g. "prometheus" or "loki"
  local ds_name_override="$3"   # e.g. "Prometheus"

  # Check if already imported (by gcom ID tag)
  EXISTING=$(CURL -sf -H "$AUTH" "${BASE}/search?type=dash-db&query=gcom-${gcom_id}" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d))")
  if [ "$EXISTING" -gt 0 ]; then
    echo "[skip] dashboard gcom-${gcom_id} already imported"
    return
  fi

  # Fetch dashboard JSON from grafana.com (to temp file; large payload)
  local tmpfile
  tmpfile=$(mktemp /tmp/dash-${gcom_id}.XXXXXX.json)
  if ! CURL -sf "https://grafana.com/api/dashboards/${gcom_id}/revisions/latest/download" -o - > "$tmpfile"; then
    echo "[err]  failed to download dashboard ${gcom_id} from grafana.com" >&2
    rm -f "$tmpfile"
    return 1
  fi

  echo "[import] dashboard gcom-${gcom_id}"
  # Wrap in Grafana import body, tag with gcom id for future detection
  local body_file
  body_file=$(mktemp /tmp/import-${gcom_id}.XXXXXX.json)
  python3 - "$tmpfile" "$body_file" "$gcom_id" "$ds_type_override" "$ds_name_override" <<'PY'
import json, sys
src, dst, gcom, ds_type, ds_name = sys.argv[1:6]
with open(src) as f:
    dash = json.load(f)
dash.setdefault('tags', []).append(f'gcom-{gcom}')
body = {
    'dashboard': dash,
    'overwrite': False,
    'inputs': [{'name': 'DS_PROMETHEUS', 'type': 'datasource',
                'pluginId': ds_type, 'value': ds_name}],
    'folderId': 0,
}
with open(dst, 'w') as f:
    json.dump(body, f)
PY
  # Stream body via stdin (curl container doesn't share host /tmp)
  sudo cat "$body_file" | sudo docker run --rm -i --network fabrik curlimages/curl:latest \
    -sf -X POST -H "$AUTH" -H "Content-Type: application/json" \
    "${BASE}/dashboards/import" --data-binary @- \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('  ->', d.get('slug','?'), d.get('status','?'))" \
    || echo "  (import response unreadable)"
  rm -f "$tmpfile" "$body_file"
}

# Node Exporter Full (host metrics from node-exporter)
import_dashboard 1860 "prometheus" "Prometheus"
# Docker containers (cAdvisor)
import_dashboard 193 "prometheus" "Prometheus"
# Prometheus stats
import_dashboard 2 "prometheus" "Prometheus"

echo ""
echo "=== final state ==="
echo "datasources:"
CURL -sf -H "$AUTH" "${BASE}/datasources" \
  | python3 -c "import json,sys; [print(f'  - {x[\"name\"]:15s} {x[\"type\"]:12s} {x[\"url\"]}') for x in json.load(sys.stdin)]"
echo "dashboards:"
CURL -sf -H "$AUTH" "${BASE}/search?type=dash-db" \
  | python3 -c "import json,sys; [print(f'  - {x[\"uid\"]:20s} {x[\"title\"]}') for x in json.load(sys.stdin)]"
