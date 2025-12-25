# Fabrik: What We've Built

**Date:** 2025-12-23  
**Status:** Phase 1 (81%) + Phase 1b (100%) Complete

---

## The Big Picture

Fabrik is a **spec-driven deployment automation system** that transforms simple YAML files into fully deployed, monitored, and backed-up services on your VPS.

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOUR WORKFLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. Write a spec.yaml     →    2. Run `fabrik apply`          │
│                                                                 │
│   ┌──────────────────┐          ┌──────────────────────────┐   │
│   │ id: my-api       │          │ • DNS records created    │   │
│   │ template: python │    →     │ • Docker image built     │   │
│   │ domain: api.com  │          │ • Container deployed     │   │
│   └──────────────────┘          │ • SSL certificate issued │   │
│                                 │ • Health checks active   │   │
│                                 └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## What We Built in Phase 1

### Core Infrastructure

| Component | Purpose | Status |
|-----------|---------|--------|
| **VPS** | Hetzner server in LA (172.93.160.197) | ✅ Running |
| **Coolify** | Container orchestration + SSL | ✅ Running |
| **PostgreSQL** | Shared database (postgres-main) | ✅ Running |
| **Redis** | Shared cache (redis-main) | ✅ Running |
| **Traefik** | Reverse proxy + HTTPS | ✅ Running |
| **Uptime Kuma** | Status monitoring | ✅ Running |
| **Duplicati** | Backups to Backblaze B2 | ✅ Running |

### Fabrik CLI

```bash
fabrik new <template> <name> --domain=<domain>   # Create spec from template
fabrik plan <name>                                # Preview changes
fabrik apply <name>                               # Deploy
fabrik status <name>                              # Check status
fabrik templates                                  # List templates
```

### Templates Available

| Template | Stack | Use Case |
|----------|-------|----------|
| `python-api` | FastAPI + Uvicorn | REST APIs, microservices |
| `node-api` | Express.js | Node.js APIs |
| `next-tailwind` | Next.js + Tailwind | Full-stack web apps |
| `file-api` | Node.js + R2 | File upload services |
| `file-worker` | Python | Background job processing |

### Drivers (Integrations)

| Driver | What It Does |
|--------|--------------|
| `DNSClient` | Manages DNS records via Namecheap service |
| `CoolifyClient` | Deploys apps, manages containers |
| `UptimeKumaClient` | Creates health monitors |
| `SupabaseClient` | Auth, database, file metadata |
| `R2Client` | Object storage with presigned URLs |

---

## What We Built in Phase 1b (Cloud Infrastructure)

### The Problem We Solved

Your VPS has **110GB disk**. User uploads (audio files, PDFs) would quickly fill it. We needed:
- Unlimited storage that doesn't consume VPS disk
- Secure file access (public, private, internal)
- Background processing pipeline (transcription, OCR)

### The Solution

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│  File API   │────▶│  Supabase   │
│             │     │  (Node.js)  │     │  (Postgres) │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       │ Direct upload     │ Metadata          │ Job queue
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Cloudflare  │     │ File Worker │────▶│  Processed  │
│     R2      │◀────│  (Python)   │     │   Output    │
│ (Storage)   │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Components Deployed

| Component | Location | Purpose |
|-----------|----------|---------|
| **Supabase** | `xjmsceegyztgtcpywhry.supabase.co` | Auth + Postgres + Realtime |
| **Cloudflare R2** | `fabrik-files` bucket | 10GB free storage, S3-compatible |
| **File API** | Local test (port 3333) | Presigned URL generation |
| **File Worker** | Template ready | OCR, transcription, text extraction |

### Database Schema

```sql
tenants           -- Multi-tenant support (isolate data per customer)
tenant_members    -- User-tenant relationships with roles
files             -- File metadata (actual bytes in R2)
file_derivatives  -- Processed outputs (transcripts, OCR text)
processing_jobs   -- Async job queue with atomic claiming
```

---

## How You'll Use It

### Scenario 1: Deploy a New API

```bash
# Create spec
fabrik new python-api translator-api --domain=translator.vps1.ocoron.com

# Edit spec (add env vars, dependencies)
nano specs/translator-api/spec.yaml

# Preview what will happen
fabrik plan translator-api

# Deploy
fabrik apply translator-api
```

**Result:** API live at `https://translator.vps1.ocoron.com` with SSL, health checks, and monitoring.

### Scenario 2: Add File Uploads to an App

```javascript
// Frontend: Request upload URL
const { uploadUrl, fileId } = await fetch('/api/files/upload-url', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ filename: 'audio.mp3', contentType: 'audio/mpeg', size: 5000000 })
}).then(r => r.json());

// Frontend: Upload directly to R2 (bypasses your server!)
await fetch(uploadUrl, {
  method: 'PUT',
  body: file,
  headers: { 'Content-Type': 'audio/mpeg' }
});

// Frontend: Confirm and trigger processing
await fetch(`/api/files/${fileId}/confirm`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({ createJob: 'transcribe' })
});
```

**Result:** File stored in R2, metadata in Supabase, transcription job queued.

### Scenario 3: Process Files in Background

The `file-worker` polls for jobs and processes them:

```python
# Worker automatically:
# 1. Claims pending job (atomic, no duplicates)
# 2. Downloads file from R2
# 3. Processes (OCR, transcribe, extract text)
# 4. Uploads derivative to R2
# 5. Updates job status
```

---

## How It Helps You

### 1. **Faster Deployments**

Before: Manual Docker setup, Traefik config, SSL, DNS, monitoring
After: `fabrik apply my-app` (5 minutes)

### 2. **Unlimited File Storage**

- R2 free tier: 10GB storage, 1M requests/month
- Files don't consume VPS disk
- Presigned URLs = direct browser↔R2 (no server bandwidth)

### 3. **Multi-Tenant Ready**

Built-in tenant isolation:
```sql
-- All queries automatically scoped
SELECT * FROM files WHERE tenant_id = current_tenant();
```

### 4. **Background Processing**

CPU-intensive tasks (transcription, OCR) don't block your API:
```
User uploads → API responds immediately → Worker processes async
```

### 5. **Unified Auth**

Supabase Auth works across all your apps:
- Single sign-on
- JWT verification
- Row-level security

### 6. **Cost Efficient**

| Service | Free Tier |
|---------|-----------|
| Supabase | 500MB DB, 2GB bandwidth |
| R2 | 10GB storage, free egress |
| VPS | Fixed €10/month |

---

## Current State

### Running Services

| Service | URL | Status |
|---------|-----|--------|
| Coolify | `http://172.93.160.197:8000` | ✅ |
| Status Page | `https://status.vps1.ocoron.com` | ✅ |
| Backup UI | `https://backup.vps1.ocoron.com` | ✅ |
| DNS Manager | `https://dns.vps1.ocoron.com` | ✅ |
| **File API (HTTPS)** | `https://files-api.vps1.ocoron.com` | ✅ |
| **File Worker** | VPS container | ✅ Running |

### Credentials Stored

All in `/opt/fabrik/.env`:
- VPS/SSH access
- Coolify API token
- Supabase keys
- R2 credentials
- All external APIs (DeepL, Soniox, etc.)
- Test user credentials

---

## What's Next?

### Immediate Options

1. **Deploy File API to VPS**
   - Push to GitHub
   - Deploy via Coolify
   - Add DNS record

2. **Build Upload UI**
   - React/Next.js component
   - Drag-drop with progress
   - Uses presigned URLs

3. **Deploy File Worker**
   - Enable transcription (Soniox integration)
   - Enable OCR (Tesseract)
   - Enable PDF extraction

### Phase 2 Possibilities

| Feature | Description |
|---------|-------------|
| **WordPress Template** | One-click WordPress deploys |
| **Cloudflare DNS** | Alternative to Namecheap |
| **Auto-scaling** | Multiple workers based on queue |
| **Webhooks** | Notify on job completion |
| **Admin Dashboard** | Web UI for Fabrik management |

---

## File Locations

| Path | Purpose |
|------|---------|
| `/opt/fabrik/` | Main Fabrik repo |
| `/opt/fabrik/src/fabrik/` | Core Python modules |
| `/opt/fabrik/templates/` | Deployment templates |
| `/opt/fabrik/docs/` | Documentation |
| `/opt/fabrik/sql/` | Database schemas |
| `/opt/fabrik/.env` | Master credentials |
| `/opt/apps/` | Deployed app instances |

---

## Quick Commands

```bash
# Activate Fabrik environment
cd /opt/fabrik && source .venv/bin/activate

# Run Fabrik CLI
PYTHONPATH=src python -m fabrik.main

# Test Supabase connection
PYTHONPATH=src python -c "from fabrik.drivers import SupabaseClient; print(SupabaseClient().health())"

# Test R2 connection
PYTHONPATH=src python -c "from fabrik.drivers import R2Client; r2=R2Client(); print(r2.list_objects())"

# Start file-api locally
cd /opt/apps/file-api && PORT=3333 node src/index.js
```
