# Fabrik: What We've Built

**Last Updated:** 2026-01-08
**Status:** Phase 1 ✅ + Phase 1b ✅ + Phase 1c ✅ + Phase 1d ✅ + Phase 2 (80%)

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

## AI Agent Automation (2026-01-08)

### Droid Scripts

Unified AI agent execution system for code tasks:

| Script | Purpose |
|--------|--------|
| `scripts/droid_core.py` | **Main entry** - 13 task types, ProcessMonitor, stuck detection |
| `scripts/review_processor.py` | Dual-model code review queue |
| `scripts/docs_updater.py` | Automatic documentation updates |
| `scripts/droid_models.py` | Model selection and auto-updates |

### Spec Pipeline (idea → scope → spec)

Complete workflow for going from idea to implementation-ready specification:

```bash
# 1. Capture and explore idea
droid exec idea "Voice-controlled home automation for elderly"

# 2. Define IN/OUT scope boundaries
droid exec scope "home-automation"

# 3. Generate full specification
droid exec spec "home-automation"

# Output structure:
# specs/home-automation/00-idea.md
# specs/home-automation/01-scope.md
# specs/home-automation/02-spec.md
```

### Task Types

```bash
python scripts/droid_core.py analyze "Review auth flow"
python scripts/droid_core.py code "Add error handling" --auto medium
python scripts/droid_core.py spec "Plan new feature"
python scripts/droid_core.py run --task tasks/my_task.md
```

| Type | Use Case |
|------|----------|
| `idea`, `scope` | Discovery pipeline (new) |
| `analyze`, `review` | Read-only analysis |
| `code`, `refactor` | Write changes (retries disabled) |
| `spec` | Planning with reasoning |
| `test`, `health`, `preflight` | Verification |
| `scaffold`, `deploy`, `migrate` | Infrastructure |

### Key Features

- **ProcessMonitor** - Detects stuck processes, auto-retry for safe tasks
- **Session continuity** - `--session-id` for multi-turn context
- **Large prompt support** - >100KB prompts use `--file` flag
- **Provider switch handling** - Session reset on OpenAI ↔ Anthropic

---

## Enforcement & Quality Gates (2026-01-07)

### Windsurf Rules

Modular rules in `.windsurf/rules/`:

| Rule | Activation | Purpose |
|------|------------|--------|
| `00-critical.md` | Always On | Security, env vars, /tmp/ ban |
| `10-python.md` | `*.py` | FastAPI patterns |
| `20-typescript.md` | `*.ts` | Next.js patterns |
| `30-ops.md` | Dockerfile | Container standards |
| `40-documentation.md` | `*.md` | Doc standards |
| `50-code-review.md` | Always On | PLAN→APPROVE→IMPLEMENT→REVIEW |

### Enforcement Scripts

```bash
python3 -m scripts.enforcement.validate_conventions --strict <files>
python3 scripts/enforcement/check_structure.py
python3 scripts/enforcement/check_docs.py
```

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

### Completed Since Last Update

- ✅ File API deployed to VPS
- ✅ File Worker deployed
- ✅ Cloudflare DNS driver (Phase 1c)
- ✅ WordPress automation (Phase 1d)
- ✅ AI agent automation (droid scripts)
- ✅ Enforcement system (Windsurf rules)

### Current Priorities

| Feature | Status | Description |
|---------|--------|-------------|
| **SaaS Skeleton** | ✅ Done | Next.js template with auth, dashboard |
| **WordPress Sites** | 🚧 80% | Theme/plugin automation |
| **Admin Dashboard** | 📋 Planned | Web UI for Fabrik management |
| **Auto-scaling Workers** | 📋 Planned | Queue-based worker scaling |

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
