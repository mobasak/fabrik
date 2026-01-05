# Coolify Migration Runbook

**Created:** 2025-12-26
**Completed:** 2025-12-27
**Status:** ✅ COMPLETE

---

## Migration Results

All 8 services successfully migrated from manual docker-compose to Coolify-managed deployments.

| Service | Coolify App | UUID | Health URL | Status |
|---------|-------------|------|------------|--------|
| captcha | fabrik-captcha | j8gg4ggskkossc4gkwowk4os | https://captcha.vps1.ocoron.com/healthz | ✅ |
| dns-manager | fabrik-dns-manager | bk4woo8gkckwkccg44g0o40g | https://dns.vps1.ocoron.com/healthz | ✅ |
| translator | fabrik-translator | kgws0s4cscsosw8gg848cwgw | https://translator.vps1.ocoron.com/healthz | ✅ |
| emailgateway | fabrik-emailgateway | w4oocckkwko8kowggsw8sogc | https://emailgateway.vps1.ocoron.com/healthz | ✅ |
| image-broker | fabrik-image-broker | zo4ggs4g880skwkocwwkscgk | https://images.vps1.ocoron.com/healthz | ✅ |
| proxy | fabrik-proxy | v0cscowwsgkk88c4ckckgw0g | https://proxy.vps1.ocoron.com/healthz | ✅ |
| file-api | fabrik-file-api | bsswwg4kg480c000gksw004k | https://files-api.vps1.ocoron.com/healthz | ✅ |
| file-worker | fabrik-file-worker | nwcckwggw0o0g40gwskk8kk8 | (background worker) | ✅ |

### What Was Done
- Added `/healthz` endpoint with `git_sha` to all services
- Added `GIT_SHA` build arg and `APP_GIT_SHA` env to all Dockerfiles
- Created/updated `compose.yaml` with explicit env vars and Traefik labels
- Pushed all repos to GitHub (created `proxy` repo)
- Created Coolify applications via API with deploy key authentication
- Set environment variables via Coolify API
- Deployed all services via Coolify API
- Stopped old manual docker-compose containers
- Cleaned up old containers (227MB reclaimed)
- Set DNS for `files-api.vps1.ocoron.com` via Cloudflare
- Deleted obsolete Coolify projects (infrastructure, services)

### GitHub Repositories
All repos at `github.com/mobasak/`:
- captcha, dns-manager, translator, emailgateway, image-broker, proxy, file-api, file-worker

---

## Infrastructure UUIDs

```bash
SERVER_UUID=jk4wskkcks8csg4gcokwgw8s
PROJECT_UUID=lww8g0oc48cg4gw08oc8k40k
SSH_KEY_UUID=xc80wwcggsc0wwwsc0swko4w
```

## Authentication: GitHub App Integration (Recommended)

**Why GitHub App over Deploy Keys:**
- Deploy keys are single-repo (GitHub limitation)
- GitHub App = one integration → all repos
- Revocable centrally, no per-repo key management
- Best for 8+ services

**One-time setup:**
1. Coolify UI → Settings → Git → GitHub → Create GitHub App
2. GitHub → Install the app → Select repos (captcha, dns-manager, etc.)
3. Use `github_app_uuid` instead of `private_key_uuid` in API calls

**Reference:** https://coolify.io/docs/applications/ci-cd/github/integration
## Traefik Config

- **Provider:** Docker (labels on containers)
- **entryPoints:** web (80), websecure (443)
- **certResolver:** letsencrypt
- **Network:** coolify

## Port Allocation

| Service | Manual Port | Staging Port | Coolify Name |
|---------|-------------|--------------|--------------|
| captcha | 8011 | 18011 | fabrik-captcha |
| dns-manager | 8001 | 18001 | fabrik-dns-manager |
| translator | 8002 | 18002 | fabrik-translator |
| emailgateway | 3000 | 13000 | fabrik-emailgateway |
| image-broker | 8010 | 18010 | fabrik-image-broker |
| proxy | 8000 | 18000 | fabrik-proxy |
| file-api | 8004 | 18004 | fabrik-file-api |
| file-worker | (none) | (none) | fabrik-file-worker |

**Rule:** Staging port = Manual port + 10000

---

## Migration Order (Completed)

1. [x] captcha (stateless, lowest risk)
2. [x] dns-manager (stateless)
3. [x] translator (postgres-main)
4. [x] emailgateway (SQLite ephemeral)
5. [x] image-broker (cache volume)
6. [x] file-api (external Supabase)
7. [x] file-worker (external Supabase)
8. [x] proxy (postgres-main, highest risk - last)

---

## Environment Variables

```bash
export COOLIFY="http://172.93.160.197:8000"
export TOKEN="5|YA40VYboS1RjL4uxt8vaS1Qy4IXc3vLpiiRGjkmw8c2f33b7"
export AUTH="Authorization: Bearer $TOKEN"
```

---

## Step 1: Collect UUIDs

### 1.1 Get Server UUID
```bash
curl -sS "$COOLIFY/api/v1/servers" -H "$AUTH"
```
**Result:** `SERVER_UUID = jk4wskkcks8csg4gcokwgw8s`

### 1.2 Get Deploy Key UUID
```bash
curl -sS "$COOLIFY/api/v1/security/keys" -H "$AUTH"
```
**Result:** `KEY_UUID = xc80wwcggsc0wwwsc0swko4w`

---

## Step 2: Get Current State

### 2.1 Traefik Config
```bash
ssh vps "cat /opt/traefik/compose.yaml"
```
**Dynamic config path:** `___________`

### 2.2 Running Containers
```bash
ssh vps "docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}'"
```

### 2.3 Service Compose (per service)
```bash
ssh vps "docker compose -f /opt/SERVICE/compose.yaml config"
```

---

## Step 3: Prepare GitHub Repo (Per Service)

### 3.1 Update compose.yaml
```yaml
services:
  app:
    build: .
    ports:
      - "${HOST_PORT:-18003}:8000"
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-info}
      - REQUIRED_VAR=${REQUIRED_VAR:?}
```

### 3.2 Add /healthz Endpoint
```python
import os

@app.get("/healthz")
def healthz():
    return {"status": "ok", "git_sha": os.getenv("APP_GIT_SHA", "unknown")}
```

### 3.3 Add GIT_SHA to Dockerfile
```dockerfile
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.revision=$GIT_SHA
ENV APP_GIT_SHA=$GIT_SHA
```

### 3.4 Push to GitHub
```bash
git add -A
git commit -m "Prepare SERVICE for Coolify migration"
git push origin main
```

---

## Step 4: Create Coolify Project (Once)

```bash
curl -sS -X POST "$COOLIFY/api/v1/projects" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"fabrik-services","description":"Migrated from manual compose"}'
```
**Result:** `PROJECT_UUID = lww8g0oc48cg4gw08oc8k40k`

---

## Step 5: Create Coolify Application (Per Service)

### Option A: Using GitHub App (recommended)
```bash
curl -sS -X POST "$COOLIFY/api/v1/applications" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "project_uuid":"$PROJECT_UUID",
    "server_uuid":"$SERVER_UUID",
    "environment_name":"production",
    "github_app_uuid":"$GITHUB_APP_UUID",
    "git_repository":"mobasak/SERVICE",
    "git_branch":"main",
    "build_pack":"dockercompose",
    "docker_compose_location":"compose.yaml",
    "ports_exposes":"8000",
    "name":"fabrik-SERVICE",
    "instant_deploy":false
  }'
```

### Option B: Using Deploy Key (single repo only)
```bash
curl -sS -X POST "$COOLIFY/api/v1/applications/private-deploy-key" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d "{
    \"project_uuid\":\"$PROJECT_UUID\",
    \"server_uuid\":\"$SERVER_UUID\",
    \"private_key_uuid\":\"$KEY_UUID\",
    \"git_repository\":\"git@github.com:mobasak/SERVICE.git\",
    \"git_branch\":\"main\",
    \"build_pack\":\"docker-compose\",
    \"docker_compose_location\":\"compose.yaml\",
    \"name\":\"fabrik-SERVICE\",
    \"description\":\"SERVICE (migrated)\",
    \"instant_deploy\":false
  }"
```
**Result:** `APP_UUID = ___________`

---

## Step 6: Set Environment Variables

```bash
curl -sS -X PATCH "$COOLIFY/api/v1/applications/$APP_UUID/envs/bulk" \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{
    "data": [
      {"key":"HOST_PORT","value":"18003","is_preview":false,"is_literal":true,"is_multiline":false,"is_shown_once":false},
      {"key":"LOG_LEVEL","value":"info","is_preview":false,"is_literal":true,"is_multiline":false,"is_shown_once":false}
    ]
  }'
```

---

## Step 7: Deploy

```bash
curl -sS "$COOLIFY/api/v1/deploy?uuid=$APP_UUID&force=true" -H "$AUTH"
```

**Verify in Coolify UI:**
- [ ] Clone succeeds
- [ ] Container runs
- [ ] Logs show binding to 0.0.0.0:8000

---

## Step 8: Verify Host-Port

```bash
ssh vps "curl -fsS http://127.0.0.1:STAGING_PORT/healthz"
```
**Expected:** `{"status":"ok","git_sha":"..."}`

---

## Step 9: Add Traefik Staging Route

Create file in Traefik dynamic config directory:

```yaml
http:
  routers:
    SERVICE-staging:
      rule: "Host(`SERVICE-staging.vps1.ocoron.com`)"
      entryPoints: ["websecure"]
      tls:
        certResolver: letsencrypt
      service: SERVICE-staging

  services:
    SERVICE-staging:
      loadBalancer:
        servers:
          - url: "http://127.0.0.1:STAGING_PORT"
```

**Verify:**
```bash
curl -fsS https://SERVICE-staging.vps1.ocoron.com/healthz
```

---

## Step 10: Switch Production

### 10.1 Update Traefik Production Route
Point production domain to staging port.

### 10.2 Stop Old Container
```bash
ssh vps "cd /opt/SERVICE && docker compose stop"
```

### 10.3 Rollback (if needed)
```bash
# Revert Traefik config
ssh vps "cd /opt/SERVICE && docker compose up -d"
# Disable Coolify app via UI
```

---

## Service-Specific Notes

### captcha
- **DB:** None (stateless)
- **Volumes:** None
- **Env:** ANTICAPTCHA_API_KEY

### dns-manager
- **DB:** None (stateless)
- **Volumes:** None
- **Env:** NAMECHEAP_API_KEY, NAMECHEAP_API_USER

### translator
- **DB:** postgres-main
- **Volumes:** None
- **Env:** DEEPL_API_KEY, DATABASE_URL

### emailgateway
- **DB:** SQLite (ephemeral)
- **Volumes:** None
- **Env:** RESEND_API_KEY, SES credentials

### image-broker
- **DB:** None
- **Volumes:** image-broker-cache
- **Env:** PEXELS_API_KEY, PIXABAY_API_KEY

### proxy
- **DB:** postgres-main
- **Volumes:** postgres_data
- **Env:** DATABASE_URL, WEBSHARE_API_KEY

### file-api
- **DB:** Supabase (external)
- **Volumes:** None
- **Env:** SUPABASE_URL, R2 credentials

### file-worker
- **DB:** Supabase (external)
- **Volumes:** None
- **Env:** SUPABASE_URL, R2 credentials

---

## Post-Migration

### GitHub Webhooks for Auto-Deploy ✅

All webhooks configured automatically via GitHub API on 2025-12-27.

**Webhook URL:** `https://coolify.vps1.ocoron.com/webhooks/source/github/events/manual`

| Repo | Webhook ID | Secret |
|------|------------|--------|
| captcha | 588497869 | `8032a2d32b1389a1c7892d6ec4bb09a58f405822` |
| dns-manager | 588497853 | `c9f843000d45ecd4d22b9fb18e806870ca547aba` |
| translator | 588497876 | `2ae7c9a44a6c9a116b2b33f640063e5578858355` |
| emailgateway | 588497865 | `b14bba6ffaf6ce1533c400aa29154781b9e902c7` |
| image-broker | 588497879 | `fffcd82e71739abce04f7496d3a965bb879b4360` |
| proxy | 588497873 | `3e442a8a1f990df1d781fa45cc34e14aae521020` |
| file-api | 588497858 | `36208d60ccbaf9665c5338788c6c5c5434079f55` |
| file-worker | 588497861 | `46580960dbf35f2ddfa04ba32cb0720e4ba74935` |

**How it works:** Push to any repo → GitHub sends webhook → Coolify auto-deploys

### GIT_SHA Configuration

GIT_SHA env vars have been set for all applications. After each GitHub push:
1. Update GIT_SHA env var in Coolify with new commit SHA
2. Or use webhooks for automatic deployment (GIT_SHA updates on rebuild)

### VPS Cleanup Completed

Old service directories removed from VPS:
- /opt/captcha
- /opt/dns-manager
- /opt/translator
- /opt/emailgateway
- /opt/image-broker
- /opt/proxy

### verify-all.sh
```bash
#!/usr/bin/env bash
set -euo pipefail

SERVICES_JSON="scripts/services.json"

github_sha() {
  git ls-remote "git@github.com:mobasak/${1}.git" HEAD | awk '{print substr($1,1,7)}'
}

deployed_sha() {
  curl -fsS "$1" | sed -n 's/.*"git_sha":"\([^"]*\)".*/\1/p' | cut -c1-7
}

echo -e "service\tgithub\tdeployed\tstatus"
jq -r '.[] | "\(.name)\t\(.url)"' "$SERVICES_JSON" | while IFS=$'\t' read -r name url; do
  gh="$(github_sha "$name" || echo "N/A")"
  dep="$(deployed_sha "$url" || echo "N/A")"
  if [[ "$gh" != "N/A" && "$dep" != "N/A" && "$gh" == "$dep" ]]; then
    echo -e "$name\t$gh\t$dep\tOK"
  else
    echo -e "$name\t$gh\t$dep\tMISMATCH"
  fi
done
```

### services.json
```json
[
  {"name":"captcha","url":"https://captcha.vps1.ocoron.com/healthz"},
  {"name":"dns-manager","url":"https://dns.vps1.ocoron.com/healthz"},
  {"name":"translator","url":"https://translator.vps1.ocoron.com/healthz"},
  {"name":"emailgateway","url":"https://emailgateway.vps1.ocoron.com/healthz"},
  {"name":"image-broker","url":"https://images.vps1.ocoron.com/healthz"},
  {"name":"proxy","url":"https://proxy.vps1.ocoron.com/healthz"},
  {"name":"file-api","url":"https://files-api.vps1.ocoron.com/healthz"}
]
```
