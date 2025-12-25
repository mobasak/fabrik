# File API Deployment Guide

**Last Updated:** 2025-12-23

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

## Option B: VPS Deployment via Coolify

Deploy to your VPS using Coolify's Docker Compose support.

### What is Coolify?

Coolify is the deployment platform running on your VPS (at `https://coolify.yourdomain.com`). It:
- Manages Docker containers
- Handles SSL certificates via Let's Encrypt
- Provides a web dashboard for deployments
- Supports Docker Compose files

### Step 1: Prepare Git Repository

Coolify pulls code from Git. You need to push the file-api code to a repository.

```bash
# Create a new repo on GitHub (or use existing)
cd /opt/apps/file-api

# Initialize git
git init
git add .
git commit -m "File API service"

# Add remote and push
git remote add origin https://github.com/YOUR_USERNAME/file-api.git
git branch -M main
git push -u origin main
```

**Alternative:** Use Coolify's "Docker Compose" deployment without Git by copying files directly to VPS.

### Step 2: Create Application in Coolify

1. Open Coolify dashboard: `https://coolify.vps1.ocoron.com`
2. Go to **Projects** → Select or create project (e.g., "fabrik-services")
3. Click **+ New** → **Application**
4. Choose deployment type:
   - **Public Repository** if your repo is public
   - **Private Repository (GitHub)** if private (requires GitHub app connection)
   - **Docker Compose** to paste compose.yaml directly

### Step 3: Configure Application

**If using Git repository:**
- Repository URL: `https://github.com/YOUR_USERNAME/file-api.git`
- Branch: `main`
- Build Pack: `Dockerfile`
- Dockerfile Location: `Dockerfile` (not `.j2` - you'll need to render the template first)

**If using Docker Compose:**
1. First render the Jinja2 template to plain compose.yaml
2. Paste the rendered compose.yaml in Coolify

### Step 4: Set Environment Variables

In Coolify application settings → **Environment Variables**, add:

```
# Supabase
SUPABASE_URL=https://xjmsceegyztgtcpywhry.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIs...

# R2 Storage
R2_ACCOUNT_ID=066f5cf1dfe20ba18549a592809aa080
R2_ACCESS_KEY_ID=735f0af6ebb94674962a918ee19d99d8
R2_SECRET_ACCESS_KEY=2c2c01c9cdc01e27e004baa80b0e9aa5546013347f7305722fea2efce9d6d6c5
R2_BUCKET=fabrik-files
R2_ENDPOINT=https://066f5cf1dfe20ba18549a592809aa080.r2.cloudflarestorage.com

# App Config
PORT=3000
NODE_ENV=production
```

### Step 5: Configure Domain

In Coolify application settings → **Domains**:

1. Add domain: `files-api.vps1.ocoron.com` (or your choice)
2. Enable HTTPS (Coolify auto-provisions Let's Encrypt cert)

### Step 6: Deploy

1. Click **Deploy** button in Coolify
2. Watch build logs
3. Wait for "Running" status

### Step 7: Add DNS Record

Add A record pointing your domain to VPS:

```
Type: A
Host: files-api
Value: 172.93.160.197
TTL: 1800
```

### Step 8: Verify Deployment

```bash
curl https://files-api.vps1.ocoron.com/health
# Expected: {"status":"healthy","timestamp":"..."}
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
├── compose.yaml         # Docker Compose (for local/Coolify)
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
