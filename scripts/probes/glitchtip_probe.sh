#!/usr/bin/env bash
# GlitchTip API probe — Phase 4-pre Task 1
#
# Purpose: capture the exact JSON response shapes for:
#   1. POST /api/0/teams/{org}/{team}/projects/ — create project
#   2. GET  /api/0/projects/{org}/{slug}/keys/  — fetch DSN
#   3. DELETE /api/0/projects/{org}/{slug}/     — cleanup
#
# Why: future glitchtip.py driver (Phase 4f) parses these exact fields. Any
# field drift between GlitchTip versions would silently break the driver.
# This probe anchors the contract.
#
# Required env (from /opt/fabrik/.env):
#   GLITCHTIP_AUTH_TOKEN  — Bearer token with project:admin scope
#   GLITCHTIP_ORG_SLUG    — organization slug (from URL)
#   GLITCHTIP_TEAM_SLUG   — team slug (from Teams tab)
#
# Output: writes raw JSON to .tmp/phase-4-pre/glitchtip-probe-<step>.json,
# then summarizes key fields on stdout for pasting into docs/reference/glitchtip-api.md
#
# Usage:
#   bash scripts/probes/glitchtip_probe.sh [--keep]
#     --keep  skip the DELETE cleanup step (for manual inspection)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
OUT_DIR="$REPO_ROOT/.tmp/phase-4-pre"
mkdir -p "$OUT_DIR"

# Extract only what we need (source can break on values with shell metacharacters)
GLITCHTIP_AUTH_TOKEN=$(grep -E '^GLITCHTIP_AUTH_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2-)
GLITCHTIP_ORG_SLUG=$(grep -E '^GLITCHTIP_ORG_SLUG='   "$ENV_FILE" | head -1 | cut -d= -f2-)
GLITCHTIP_TEAM_SLUG=$(grep -E '^GLITCHTIP_TEAM_SLUG=' "$ENV_FILE" | head -1 | cut -d= -f2-)
: "${GLITCHTIP_AUTH_TOKEN:?set GLITCHTIP_AUTH_TOKEN in .env}"
: "${GLITCHTIP_ORG_SLUG:?set GLITCHTIP_ORG_SLUG in .env}"
: "${GLITCHTIP_TEAM_SLUG:?set GLITCHTIP_TEAM_SLUG in .env}"

BASE="https://errors.vps1.ocoron.com/api/0"
ORG="$GLITCHTIP_ORG_SLUG"
TEAM="$GLITCHTIP_TEAM_SLUG"
TS=$(date +%s)
PROBE_NAME="fabrik-probe-$TS"
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

auth_header="Authorization: Bearer $GLITCHTIP_AUTH_TOKEN"

say() { printf '\n=== %s ===\n' "$1"; }

say "1. Create project: POST /api/0/teams/$ORG/$TEAM/projects/"
CREATE_OUT="$OUT_DIR/glitchtip-probe-create.json"
HTTP=$(curl -sS -X POST "$BASE/teams/$ORG/$TEAM/projects/" \
    -H "$auth_header" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$PROBE_NAME\",\"platform\":\"python\"}" \
    -o "$CREATE_OUT" -w '%{http_code}' --max-time 15)
echo "HTTP $HTTP"
cat "$CREATE_OUT" | python3 -m json.tool
PROJECT_SLUG=$(python3 -c "import json; d=json.load(open('$CREATE_OUT')); print(d.get('slug',''))")
echo "→ project_slug=$PROJECT_SLUG"
[ -z "$PROJECT_SLUG" ] && { echo "FAIL: no slug in response"; exit 2; }

say "2. Fetch DSN: GET /api/0/projects/$ORG/$PROJECT_SLUG/keys/"
KEYS_OUT="$OUT_DIR/glitchtip-probe-keys.json"
HTTP=$(curl -sS -X GET "$BASE/projects/$ORG/$PROJECT_SLUG/keys/" \
    -H "$auth_header" \
    -o "$KEYS_OUT" -w '%{http_code}' --max-time 15)
echo "HTTP $HTTP"
cat "$KEYS_OUT" | python3 -m json.tool
DSN=$(python3 -c "import json; d=json.load(open('$KEYS_OUT')); print(d[0]['dsn']['public'] if d else '')")
echo "→ dsn.public=$DSN"

if [ "$KEEP" -eq 1 ]; then
    say "KEEP mode — skipping cleanup. Project '$PROBE_NAME' remains."
    exit 0
fi

say "3. Cleanup: DELETE /api/0/projects/$ORG/$PROJECT_SLUG/"
HTTP=$(curl -sS -X DELETE "$BASE/projects/$ORG/$PROJECT_SLUG/" \
    -H "$auth_header" \
    -o /dev/null -w '%{http_code}' --max-time 15)
echo "HTTP $HTTP"
[ "$HTTP" = "204" ] && echo "→ deleted" || echo "WARN: expected 204, got $HTTP"

say "Probe complete. Artifacts:"
ls -la "$OUT_DIR"/glitchtip-probe-*.json
