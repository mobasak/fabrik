# What's Next for Fabrik

**Date:** 2025-12-23  
**Current Status:** Phase 1 (81%) + Phase 1b (100%)

---

## Recommended Next Steps

### Option A: Production-Ready File Service (1-2 days)

Deploy the file infrastructure we just built to production.

```
Day 1:
├── Deploy file-api to VPS via Coolify
├── Add DNS: files-api.vps1.ocoron.com
├── Deploy file-worker for processing
└── Test E2E with real files

Day 2:
├── Build simple upload UI component
├── Integrate with existing apps (translator, youtube-pipeline)
└── Document API for team use
```

**Why this first?** The infrastructure is ready. Small step to production value.

---

### Option B: Complete Phase 1 (1 day)

Finish the remaining 19% of Phase 1.

| Task | Status | Effort |
|------|--------|--------|
| WordPress template | Deferred | 2-3 hours |
| `fabrik destroy` command | Not started | 1 hour |
| `fabrik logs` command | Not started | 1 hour |

**Why this?** Clean completion before moving to new features.

---

### Option C: Start Phase 2 - Multi-Project Support (3-5 days)

Enable Fabrik to manage multiple projects from a single interface.

```
Phase 2 Goals:
├── Project grouping (translator, youtube, calendar as separate projects)
├── Environment management (dev, staging, prod)
├── Shared secrets management
├── Deployment pipelines (git push → auto deploy)
└── Web dashboard for Fabrik
```

---

## Detailed Roadmap

### Immediate (This Week)

| Priority | Task | Time |
|----------|------|------|
| 1 | Deploy file-api to VPS | 30 min |
| 2 | Deploy file-worker to VPS | 30 min |
| 3 | Test with real PDF/audio upload | 1 hour |
| 4 | Integrate Soniox for transcription | 2 hours |

### Short Term (Next Week)

| Priority | Task | Time |
|----------|------|------|
| 1 | Upload UI component (React) | 4 hours |
| 2 | Job status webhooks | 2 hours |
| 3 | Admin view for jobs/files | 4 hours |

### Medium Term (Next Month)

| Priority | Task | Time |
|----------|------|------|
| 1 | Fabrik web dashboard | 2 days |
| 2 | GitHub Actions integration | 1 day |
| 3 | Cloudflare DNS driver | 4 hours |
| 4 | Auto-scaling workers | 1 day |

---

## Your Existing Projects That Can Use This

### 1. YouTube Pipeline
- **Use case:** Store downloaded audio in R2
- **Benefit:** Free up VPS disk, faster downloads
- **Integration:** Replace local storage with R2Client

### 2. Translator Service
- **Use case:** Document translation with file upload
- **Benefit:** Handle large documents without memory issues
- **Integration:** Presigned upload → process → presigned download

### 3. Calendar Engine
- **Use case:** Store calendar exports/imports
- **Benefit:** Persistent storage for ICS files
- **Integration:** Simple R2 storage

### 4. LLM Batch Processor
- **Use case:** Store prompts and responses
- **Benefit:** Audit trail, replay capability
- **Integration:** File metadata in Supabase

---

## Decision Point

**What would you like to focus on?**

1. **🚀 Deploy to Production** — File API + Worker on VPS (fastest path to value)

2. **🔧 Complete Phase 1** — WordPress template, remaining CLI commands

3. **📊 Build Dashboard** — Web UI to manage Fabrik deployments

4. **🔗 Integrate Existing App** — Add file uploads to translator/youtube-pipeline

5. **📝 Something Else** — Your priorities may differ

---

## Quick Start Commands

### Deploy File API to VPS

```bash
# 1. Push to GitHub
cd /opt/apps/file-api
git init && git add . && git commit -m "File API service"
gh repo create file-api --private --push

# 2. In Coolify:
#    - New Application → GitHub repo
#    - Set env vars from /opt/apps/file-api/.env
#    - Domain: files-api.vps1.ocoron.com
#    - Deploy

# 3. Add DNS
# A record: files-api → 172.93.160.197

# 4. Test
curl https://files-api.vps1.ocoron.com/health
```

### Test File Upload Flow

```bash
# Get token
TOKEN=$(curl -s -X POST 'https://xjmsceegyztgtcpywhry.supabase.co/auth/v1/token?grant_type=password' \
  -H 'apikey: YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@fabrik.dev","password":"FabrikTest2025!"}' | jq -r '.access_token')

# Request upload URL
curl -X POST https://files-api.vps1.ocoron.com/api/files/upload-url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename":"test.pdf","contentType":"application/pdf","size":1024}'
```
