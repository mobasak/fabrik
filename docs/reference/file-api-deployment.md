# File API Deployment Guide

**Last Updated:** 2026-06-16

> **⚠️ Pre-migration vintage.** Coolify was **decommissioned (2026-05-30)**.
> The deployment sections below were written for the Coolify-era flow; the
> current deploy path is SSH + Docker Compose via `fabrik apply`. Where this
> doc still says "Coolify", read it as the legacy path — the Docker network that
> Traefik routes on is named `fabrik` (renamed from `coolify` 2026-05-31).
> For File API today, `fabrik apply specs/services/file-api.yaml` runs
> `src/fabrik/orchestrator/deployer_ssh.py` (writes `compose.yaml` + `.env`
> to `/opt/file-api/` via SSH, runs `docker compose up -d --wait`). Add
> `--target-vps <host>` to deploy to a non-default host on the 3-host fleet
> (default: `vps1`). See
> [docs/operations/deployment.md](../operations/deployment.md) for the
> current procedure. The architecture / config / env-var sections in this
> file are still accurate.

This guide covers deploying the File API service that provides presigned URLs for R2 file uploads/downloads.

---

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  File API   │────▶│  Supabase   │
│ (Frontend)  │     │  (Node.js)  │     │  (Postgres) │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       │                   ▼
       │            ┌─────────────┐
       └───────────▶│ Cloudflare  │
        (direct     │     R2      │
         upload)    └─────────────┘
```

**Flow:**
1. Client requests upload URL from File API
2. File API creates record in Supabase, generates presigned URL
3. Client uploads directly to R2 using presigned URL
4. Client confirms upload complete
5. (Optional) Processing job created for transcription/OCR

---

## Option A: Local Testing (WSL)

Test the API locally before deploying to VPS.

### Step 1: Copy Template to Apps

```bash
# Copy template files
cp -r /opt/fabrik/templates/file-api/* /opt/apps/file-api/

# Verify .env exists (created earlier)
cat /opt/apps/file-api/.env
```

### Step 2: Install Dependencies

```bash
cd /opt/apps/file-api
npm install
```

### Step 3: Run Locally

```bash
cd /opt/apps/file-api
node src/index.js
```

Expected output:
```
File API running on port 3000
```

### Step 4: Test Endpoints

```bash
# Health check
curl http://localhost:3000/health

# Expected: {"status":"healthy","timestamp":"2025-12-23T..."}
```

**Note:** Other endpoints require Supabase auth token. See "Testing with Auth" below.

---

## Option B: VPS Deployment via Fabrik Orchestrator

Deploy to your VPS using Fabrik's orchestrator pipeline with automatic DNS, secrets, and health verification.

### What is Fabrik Orchestrator?

Fabrik's orchestrator automates the entire deployment pipeline:
- Validates spec YAML
- Loads secrets from project .env files
- Provisions DNS records (via site-provisioner or Cloudflare)
- Writes `compose.yaml` + `.env` to `/opt/<id>/` via SSH and runs `docker compose up -d --wait` (legacy path: deployed to Coolify)
- Verifies health endpoint with retries
- Automatic rollback on failure

### Step 1: Create Deployment Spec

Create a spec file for the File API service:

```bash
cd /opt/fabrik/specs/services
vim file-api.yaml
```

**Spec content** (current schema — `kind`, `shape`, `source`, `secrets.from_env`; see `specs/services/fabrik-test-file-api.yaml` for a live example):
```yaml
id: file-api
kind: service
template: file-api          # `file-api` is a real fabrik scaffold type
domain: files-api.vps1.ocoron.com
shape:
  kind: service
  is_public: true
  is_admin_dashboard: false
  has_bearer_api: false
  has_persistent_data: true
  needs_database: false     # File API uses Supabase, not the shared postgres-main
  has_search_feature: false
source:
  type: git                 # VPS runs `git pull` from GitHub — push before redeploy
  repository: https://github.com/<owner>/file-api.git
  branch: main
infrastructure:
  database: local
  storage: local
  auth: none
env:
  # App Config (non-secret)
  PORT: '3000'
  NODE_ENV: production
secrets:
  required: []
  generate: []
  # Loaded from the project .env at apply time (never committed):
  from_env:
    - SUPABASE_SERVICE_ROLE_KEY
    - R2_SECRET_ACCESS_KEY
resources:
  memory: 256M              # required: every service must declare a memory limit
  cpu: '0.5'
health:
  path: /api/health         # File API exposes /api/health
  interval: 30s
  timeout: 10s
  retries: 3
```

### Step 2: Set Secrets in Project .env

Fabrik automatically loads secrets from the project's `.env` file:

```bash
# /opt/file-api/.env
SUPABASE_ANON_KEY=your_actual_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_actual_service_role_key
R2_ACCOUNT_ID=066f5cf1dfe20ba18549a592809aa080
R2_ACCESS_KEY_ID=735f0af6ebb94674962a918ee19d99d8
R2_SECRET_ACCESS_KEY=2c2c01c9cdc01e27e004baa80b0e9aa5546013347f7305722fea2efce9d6d6c5
R2_BUCKET=fabrik-files
R2_ENDPOINT=https://066f5cf1dfe20ba18549a592809aa080.r2.cloudflarestorage.com
```

### Step 3: Deploy with Fabrik

```bash
cd /opt/fabrik
fabrik apply specs/services/file-api.yaml
```

**What happens automatically:**
1. **Validation** - Spec YAML is validated
2. **Secrets Loading** - Secrets loaded from `/opt/file-api/.env`
3. **DNS Provisioning** - A record created: `files-api.vps1.ocoron.com → 172.93.160.197` (vps1)
4. **SSH + Compose Deployment** - `compose.yaml` + `.env` written to `/opt/file-api/` over SSH, then `docker compose up -d --wait` (legacy path: deployed to Coolify)
5. **Health Verification** - Checks the spec's `health.path` (`/api/health`) with retries
6. **Rollback** - Automatic if any step fails

### Step 4: Verify Deployment

```bash
curl https://files-api.vps1.ocoron.com/api/health
# Expected: {"status":"healthy","timestamp":"..."}
```

### Step 5: Check Deployment Status

```bash
# Tail the deployed container logs (takes a spec path, not a bare name)
fabrik app-logs specs/services/file-api.yaml
fabrik app-logs specs/services/file-api.yaml -n 50   # last 50 lines
fabrik app-logs specs/services/file-api.yaml -f      # follow

# Or check on the VPS directly:
# ssh vps1 'cd /opt/file-api && sudo docker compose ps'
```

---

## Testing with Authentication

The File API requires Supabase auth. To test:

### 1. Create Test User in Supabase

In Supabase dashboard → **Authentication** → **Users** → **Add user**

Or via API:
```bash
curl -X POST 'https://xjmsceegyztgtcpywhry.supabase.co/auth/v1/signup' \
  -H 'apikey: YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"testpassword123"}'
```

### 2. Create Test Tenant

```sql
-- Run in Supabase SQL Editor
INSERT INTO tenants (name, slug) VALUES ('Test Tenant', 'test-tenant');

-- Get the tenant ID
SELECT id FROM tenants WHERE slug = 'test-tenant';
```

### 3. Link User to Tenant

```sql
-- Replace USER_ID and TENANT_ID with actual values
INSERT INTO tenant_members (tenant_id, user_id, role)
VALUES ('TENANT_ID', 'USER_ID', 'owner');
```

### 4. Get Auth Token

```bash
curl -X POST 'https://xjmsceegyztgtcpywhry.supabase.co/auth/v1/token?grant_type=password' \
  -H 'apikey: YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"testpassword123"}'
```

Save the `access_token` from response.

### 5. Test File Upload Flow

```bash
TOKEN="your_access_token_here"

# Request upload URL
curl -X POST http://localhost:3000/api/files/upload-url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test.pdf",
    "contentType": "application/pdf",
    "size": 12345
  }'

# Response includes uploadUrl - use it to upload file directly to R2
```

---

## File Structure

```
/opt/apps/file-api/
├── .env                 # Environment variables (gitignored)
├── package.json         # Node.js dependencies
├── Dockerfile           # Container build instructions
├── compose.yaml         # Docker Compose (local + VPS deploy)
└── src/
    └── index.js         # Main application code
```

---

## Troubleshooting

### "Missing authorization header"
- Ensure you're sending `Authorization: Bearer <token>` header

### "User has no tenant access"
- User needs to be added to `tenant_members` table

### "File too large"
- Adjust `MAX_FILE_SIZE_MB` environment variable

### R2 upload fails
- Verify R2 credentials are correct
- Check R2 bucket exists and token has write permissions

### Supabase connection fails
- Verify `SUPABASE_URL` and keys are correct
- Check if Supabase project is active (not paused)

---

## Related Files

| File | Purpose |
|------|---------|
| `/opt/fabrik/.env` | Master credentials |
| `/opt/apps/file-api/.env` | Service-specific config |
| `/opt/fabrik/templates/file-api/` | Template source |
| `/opt/fabrik/sql/phase1b_ddl.sql` | Database schema |
