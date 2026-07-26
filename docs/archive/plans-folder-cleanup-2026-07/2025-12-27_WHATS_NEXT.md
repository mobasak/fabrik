> ⚠️ **ARCHIVED DOCUMENT** — This document is outdated and kept for historical reference only.
> See [ROADMAP_ACTIVE.md](../ROADMAP_ACTIVE.md) for current roadmap.

# What's Next for Fabrik

**Date:** 2025-12-27
**Current Status:** Phase 1 ✅ | Phase 1b ✅ | Phase 1c ✅ | Phase 1d 🚧 | Phase 2 (67%)

---

## Completed Since Last Update

- ✅ **File API deployed** — `files-api.vps1.ocoron.com`
- ✅ **File Worker deployed** — Background processing active
- ✅ **All 8 microservices migrated to Coolify** — Auto-deploy via GitHub webhooks
- ✅ **Cloudflare DNS migration complete** — All DNS via Cloudflare
- ✅ **Phase 1 complete** — Foundation fully operational
- ✅ **Phase 1b complete** — Supabase + R2 integration
- ✅ **Phase 1c complete** — DNS automation

---

## Current Priority: Phase 1d (WordPress Automation)

### Active Tasks

| Task | Status | Notes |
|------|--------|-------|
| Deploy ocoron.com | 🚧 In Progress | Company site, multilingual EN/TR |
| Build preset loader | Pending | Load presets/company.yaml |
| Create custom themes | Pending | flavor-starter, flavor-corporate |
| WAF rules | Pending | Needs Cloudflare permissions |

### Next Steps

1. **Complete ocoron.com deployment** — First production WordPress site
2. **Build preset system** — Reusable site configurations
3. **Theme development** — GeneratePress child themes

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
