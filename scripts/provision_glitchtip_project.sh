#!/bin/bash
# provision_glitchtip_project.sh — Idempotently provision a GlitchTip project + DSN.
#
# Sentry-compatible API. Creates project under the team if missing, fetches the
# project's first DSN, rewrites the host part to the VPS-internal stable alias
# (so coolify-network containers can ingest events without going through Authelia),
# and prints the final DSN as the LAST line of stdout (other output to stderr).
#
# Designed to run ON THE VPS — accesses the GlitchTip container via the coolify
# Docker network. Required env vars:
#   GLITCHTIP_AUTH_TOKEN  — Bearer token (must have project:write scope)
#   GLITCHTIP_ORG_SLUG    — e.g. "ocoron"
#   GLITCHTIP_TEAM_SLUG   — e.g. "vps1"
#
# Optional env vars:
#   GLITCHTIP_PLATFORM    — default "python"; set to "javascript-node" for node-api
#   GLITCHTIP_INTERNAL_HOST — DSN host rewrite target; default "glitchtip-web:8000"
#                              (the stable Docker DNS alias on coolify network)
#   COOLIFY_API_URL, COOLIFY_API_TOKEN — set together with --coolify-uuid to push
#                                        the DSN into a Coolify service's env.
#
# Usage on VPS:
#   GLITCHTIP_AUTH_TOKEN=... GLITCHTIP_ORG_SLUG=ocoron GLITCHTIP_TEAM_SLUG=vps1 \
#     bash provision_glitchtip_project.sh <project-name> [--platform python|javascript-node]
#
# Usage from WSL (recommended — auto-extracts creds from /opt/fabrik/.env):
#   bash scripts/provision_glitchtip_project.sh <project-name>
#
# Exit codes:
#   0 — DSN printed (project created, or already existed and DSN fetched)
#   1 — missing creds, API error, project creation failed
#
# Idempotent: re-running for an existing project just refetches the DSN.

set -euo pipefail

# ----- arg parsing ---------------------------------------------------------
PROJECT_NAME=""
COOLIFY_UUID=""
PLATFORM="${GLITCHTIP_PLATFORM:-python}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --platform)      PLATFORM="$2"; shift 2 ;;
    --coolify-uuid)  COOLIFY_UUID="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
      exit 0 ;;
    -*)
      echo "ERROR: unknown flag: $1" >&2; exit 1 ;;
    *)
      [[ -z "$PROJECT_NAME" ]] && PROJECT_NAME="$1" || { echo "ERROR: too many positional args" >&2; exit 1; }
      shift ;;
  esac
done

if [[ -z "$PROJECT_NAME" ]]; then
  echo "Usage: $0 <project-name> [--platform python|javascript-node] [--coolify-uuid UUID]" >&2
  exit 1
fi

# ----- WSL passthrough: if creds not set & we have a local .env, re-exec on VPS ---
WSL_PASSTHROUGH() {
  local env_file="/opt/fabrik/.env"
  [[ ! -f "$env_file" ]] && return 1
  command -v ssh >/dev/null || return 1

  local extract
  extract() { grep -E "^${1}=" "$env_file" | head -1 | cut -d= -f2- | sed 's/^["'\'']//;s/["'\'']$//'; }

  local tok org team coolify_url coolify_tok
  tok=$(extract GLITCHTIP_AUTH_TOKEN)
  org=$(extract GLITCHTIP_ORG_SLUG)
  team=$(extract GLITCHTIP_TEAM_SLUG)
  [[ -z "$tok" || -z "$org" || -z "$team" ]] && return 1

  coolify_url=$(extract COOLIFY_API_URL || true)
  coolify_tok=$(extract COOLIFY_API_TOKEN || true)

  echo "[wsl] re-running on vps via ssh..." >&2
  # shellcheck disable=SC2029   # intentional client-side expansion
  exec ssh vps "GLITCHTIP_AUTH_TOKEN='$tok' GLITCHTIP_ORG_SLUG='$org' GLITCHTIP_TEAM_SLUG='$team' \
                GLITCHTIP_PLATFORM='$PLATFORM' \
                COOLIFY_API_URL='$coolify_url' COOLIFY_API_TOKEN='$coolify_tok' \
                bash -s -- '$PROJECT_NAME' ${COOLIFY_UUID:+--coolify-uuid $COOLIFY_UUID}" < "$0"
}

# Detect WSL & creds-missing situation
if grep -qi microsoft /proc/version 2>/dev/null && [[ -z "${GLITCHTIP_AUTH_TOKEN:-}" ]]; then
  WSL_PASSTHROUGH || { echo "ERROR: GLITCHTIP_AUTH_TOKEN not set and WSL passthrough failed" >&2; exit 1; }
fi

# ----- creds check (we're now on VPS, or invoked directly with env set) ---------
: "${GLITCHTIP_AUTH_TOKEN:?must be set}"
: "${GLITCHTIP_ORG_SLUG:?must be set}"
: "${GLITCHTIP_TEAM_SLUG:?must be set}"

INTERNAL_HOST="${GLITCHTIP_INTERNAL_HOST:-glitchtip-web:8000}"
GT_HOST_API="glitchtip-web:8000"   # API endpoint inside coolify network

CURL() { sudo docker run --rm --network coolify curlimages/curl:latest "$@"; }

AUTH="Authorization: Bearer ${GLITCHTIP_AUTH_TOKEN}"
BASE="http://${GT_HOST_API}/api/0"

echo "[gt] org=${GLITCHTIP_ORG_SLUG} team=${GLITCHTIP_TEAM_SLUG} project=${PROJECT_NAME} platform=${PLATFORM}" >&2

# ----- step 1: project — create if missing -------------------------------------
EXISTS_BODY=$(CURL -s -H "$AUTH" "${BASE}/projects/${GLITCHTIP_ORG_SLUG}/${PROJECT_NAME}/" -w "\nHTTP_STATUS:%{http_code}")
EXISTS_CODE=$(echo "$EXISTS_BODY" | sed -n 's/^HTTP_STATUS://p')

if [[ "$EXISTS_CODE" == "200" ]]; then
  echo "[gt] project '${PROJECT_NAME}' exists — skipping create" >&2
elif [[ "$EXISTS_CODE" == "404" ]]; then
  echo "[gt] creating project '${PROJECT_NAME}'..." >&2
  CREATE_RESP=$(CURL -s -w "\nHTTP_STATUS:%{http_code}" -X POST -H "$AUTH" -H "Content-Type: application/json" \
    "${BASE}/teams/${GLITCHTIP_ORG_SLUG}/${GLITCHTIP_TEAM_SLUG}/projects/" \
    -d "{\"name\":\"${PROJECT_NAME}\",\"platform\":\"${PLATFORM}\"}")
  CREATE_CODE=$(echo "$CREATE_RESP" | sed -n 's/^HTTP_STATUS://p')
  CREATE_BODY=$(echo "$CREATE_RESP" | sed '/^HTTP_STATUS:/d')
  if [[ "$CREATE_CODE" != "201" && "$CREATE_CODE" != "200" ]]; then
    echo "[gt] ERROR: project create returned HTTP $CREATE_CODE: $CREATE_BODY" >&2
    exit 1
  fi
  echo "[gt] project created (HTTP $CREATE_CODE)" >&2
else
  echo "[gt] ERROR: unexpected status when probing project existence: HTTP $EXISTS_CODE" >&2
  echo "$EXISTS_BODY" | sed '/^HTTP_STATUS:/d' >&2
  exit 1
fi

# ----- step 2: fetch the project's DSN -----------------------------------------
KEYS_JSON=$(CURL -sf -H "$AUTH" "${BASE}/projects/${GLITCHTIP_ORG_SLUG}/${PROJECT_NAME}/keys/")
DSN_RAW=$(echo "$KEYS_JSON" | python3 -c "
import json, sys
keys = json.load(sys.stdin)
if not keys:
    sys.stderr.write('ERROR: no DSN keys found\n'); sys.exit(1)
# Prefer the first active key; GlitchTip auto-creates one on project create.
for k in keys:
    if k.get('isActive', True):
        print(k['dsn']['public']); sys.exit(0)
print(keys[0]['dsn']['public'])
")
if [[ -z "$DSN_RAW" ]]; then
  echo "[gt] ERROR: no DSN returned from /keys/ endpoint" >&2
  exit 1
fi

# Rewrite the host so coolify-net containers can reach it without TLS/Authelia.
# Source DSN format: http://<key>@<gt-internal-host>/<project_id>
# We replace whatever host:port GlitchTip emitted (typically localhost:8000)
# with the stable internal alias.
DSN=$(echo "$DSN_RAW" | python3 -c "
import sys, re
raw = sys.stdin.read().strip()
# Expect scheme://key@host:port/path — replace host:port wholesale.
m = re.match(r'^(https?://[^@]+@)([^/]+)(/.*)$', raw)
if not m:
    sys.stderr.write(f'ERROR: unparseable DSN: {raw!r}\n'); sys.exit(1)
print(f\"{m.group(1)}${INTERNAL_HOST}{m.group(3)}\")
")

echo "[gt] DSN ready (host rewritten -> ${INTERNAL_HOST})" >&2

# ----- step 3 (optional): push DSN to Coolify env ------------------------------
if [[ -n "$COOLIFY_UUID" ]]; then
  : "${COOLIFY_API_URL:?--coolify-uuid given but COOLIFY_API_URL not set}"
  : "${COOLIFY_API_TOKEN:?--coolify-uuid given but COOLIFY_API_TOKEN not set}"
  echo "[coolify] pushing GLITCHTIP_DSN to service ${COOLIFY_UUID}..." >&2
  PUSH_RESP=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH \
    -H "Authorization: Bearer ${COOLIFY_API_TOKEN}" -H "Content-Type: application/json" \
    "${COOLIFY_API_URL}/api/v1/services/${COOLIFY_UUID}/envs" \
    -d "{\"key\":\"GLITCHTIP_DSN\",\"value\":\"${DSN}\",\"is_preview\":false,\"is_build_time\":false}")
  PUSH_CODE=$(echo "$PUSH_RESP" | sed -n 's/^HTTP_STATUS://p')
  if [[ "$PUSH_CODE" == "200" || "$PUSH_CODE" == "201" ]]; then
    echo "[coolify] env updated (HTTP $PUSH_CODE) — service redeploy required" >&2
  else
    echo "[coolify] WARN: env push returned HTTP $PUSH_CODE (DSN still printed below)" >&2
    echo "$PUSH_RESP" | sed '/^HTTP_STATUS:/d' >&2
  fi
fi

# ----- final: DSN as the LAST stdout line --------------------------------------
echo "$DSN"
