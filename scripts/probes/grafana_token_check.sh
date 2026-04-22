#!/usr/bin/env bash
# Grafana service-account token verification — Phase 4-pre Task 3
#
# Purpose: verify GRAFANA_SERVICE_ACCOUNT_TOKEN in .env can actually call
# the Grafana API with Editor-or-higher privileges. The token is needed by
# the future grafana.py driver (Phase 4g) for push_dashboard and add_alert_rule.
#
# Idempotent: posts an annotation tagged 'fabrik-probe' and deletes it.
# Exit 0 on success, non-zero on failure with diagnostic output.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

# Extract only what we need (source can break on values with shell metacharacters)
GRAFANA_SERVICE_ACCOUNT_TOKEN=$(grep -E '^GRAFANA_SERVICE_ACCOUNT_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2-)
: "${GRAFANA_SERVICE_ACCOUNT_TOKEN:?set GRAFANA_SERVICE_ACCOUNT_TOKEN in .env}"

BASE="https://monitor.vps1.ocoron.com"
AUTH="Authorization: Bearer $GRAFANA_SERVICE_ACCOUNT_TOKEN"
TS_MS=$(date +%s)000
BODY="{\"time\":$TS_MS,\"tags\":[\"fabrik-probe\"],\"text\":\"token verification probe\"}"

echo "=== 1. Write: POST /api/annotations ==="
RESP=$(curl -sS -H "$AUTH" -H "Content-Type: application/json" \
    -X POST "$BASE/api/annotations" \
    -d "$BODY" \
    -w '\n__HTTP__%{http_code}' --max-time 10)
HTTP=$(echo "$RESP" | sed -n 's/.*__HTTP__\([0-9]*\).*/\1/p')
BODY_OUT=$(echo "$RESP" | sed 's/__HTTP__.*//')
echo "HTTP $HTTP"
echo "$BODY_OUT"

if [ "$HTTP" != "200" ]; then
    echo "FAIL: expected HTTP 200, got $HTTP" >&2
    exit 2
fi

ANN_ID=$(echo "$BODY_OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))")
[ -z "$ANN_ID" ] && { echo "FAIL: no annotation id in response" >&2; exit 3; }

echo
echo "=== 2. Cleanup: DELETE /api/annotations/$ANN_ID ==="
HTTP=$(curl -sS -H "$AUTH" -X DELETE "$BASE/api/annotations/$ANN_ID" \
    -o /dev/null -w '%{http_code}' --max-time 10)
echo "HTTP $HTTP"
[ "$HTTP" = "200" ] || { echo "FAIL: expected 200 on delete, got $HTTP" >&2; exit 4; }

echo
echo "=== OK — GRAFANA_SERVICE_ACCOUNT_TOKEN has write access to annotations ==="
