# Fabrik Active Roadmap

**Date:** 2025-12-27
**Status:** Phase 1 ✅ | Phase 1b ✅ | Phase 1c ✅ | Phase 1d 🚧 | Phase 2 (67%)

> Consolidates current priorities and future plans. For 8-phase technical roadmap, see `reference/roadmap.md`.

---

## Completed

- ✅ Phase 1 — Foundation operational
- ✅ Phase 1b — Supabase + R2 integration
- ✅ Phase 1c — DNS automation (Cloudflare)
- ✅ File API + Worker deployed
- ✅ 8 microservices migrated to Coolify
- ✅ WordPress Phase 1d started

---

## Current: Phase 1d (WordPress)

| Task | Status |
|------|--------|
| Deploy ocoron.com | 🚧 In Progress |
| Build preset loader | Pending |
| Create custom themes | Pending |
| WAF rules | Pending |

---

## Backlog Priorities

### P1: Integrate Existing Apps (2-4h)

**YouTube Pipeline:**
```python
from fabrik.drivers import R2Client
r2 = R2Client()
r2.put_object(f"youtube/{video_id}/audio.mp3", audio_data, "audio/mpeg")
```

**Translator Service:** Document upload, store original + translated, presigned URLs

**Steps:** Replace `open(file, 'wb')` → `r2.put_object()`, update API for presigned URLs

### P2: Upload UI Component (4h)

React/Next.js drag-drop with progress, validation, retry. Direct upload to R2.

```tsx
export function FileUpload({ onUpload, allowedTypes, maxSize }) {
  // 1. Get presigned URL  2. Upload to R2  3. Confirm  4. Callback
}
```

### P3: Enable Transcription (2h)

Soniox API integration in file-worker.

```python
# worker/processors/transcribe.py
def transcribe_audio(audio_path: str) -> str:
    response = requests.post('https://api.soniox.com/v1/transcribe',
        headers={'Authorization': f'Bearer {SONIOX_API_KEY}'}, files={'audio': f})
    return response.json()['text']
```

**Job Flow:** Upload → pending → worker claims → download from R2 → Soniox API → upload transcript → completed

### P4: Admin Dashboard (2 days)

**Tech:** Next.js 14, TailwindCSS + shadcn/ui, Supabase Auth + Realtime

**Pages:**
```
/dashboard
├── /apps          # List deployed apps
├── /templates     # Available templates
├── /files         # Storage browser
├── /jobs          # Processing queue
└── /settings      # API keys, config
```

### Lower Priority

- **Auto-scaling Workers:** Monitor queue, spin up/down
- **Deployment Webhooks:** Slack/Discord/email notifications
- **GitHub Actions:** Auto-deploy on push, preview PRs, rollback

---

## Future: Web-Based Site Builder

### Overview

A web GUI that automates **Step 0 (Domain) + Step 1 (Hosting)** - the foundation for all site types.

**Key insight:** Register domain WITH Cloudflare nameservers from the start = instant DNS, no propagation wait.

### Step 0-1 Automation Flow

**What the User Sees:**
```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 0: DOMAIN                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Domain name: [newsite.com        ] [Check Availability]        │
│  ✅ Available! Price: $10.98/year                               │
│  Registration: [1 year ▼] WhoisGuard: [✓] Enable               │
├─────────────────────────────────────────────────────────────────┤
│  STEP 1: SITE TYPE                                              │
├─────────────────────────────────────────────────────────────────┤
│  ○ Company    ○ Landing    ○ SaaS    ○ Ecommerce    ○ Content  │
│                              [Register & Deploy →]              │
└─────────────────────────────────────────────────────────────────┘
```

**Behind the Scenes:**
1. Check domain availability (Namecheap API)
2. Create Cloudflare zone (get nameservers FIRST)
3. Register domain WITH CF nameservers
4. Add DNS records (A, CNAME)
5. Deploy WordPress container

**Propagation Times:**
| Domain Type | Wait | Reason |
|-------------|------|--------|
| New domain (our flow) | 5-60 min | Only TLD registry |
| Existing domain NS change | 24-48h | NS TTL + cache |

### API Endpoints Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/domains/check` | POST | Check availability |
| `/api/domains/pricing` | GET | Get pricing |
| `/api/account/balance` | GET | Namecheap balance |
| `/api/domains/register` | POST | Register with NS |
| `/api/cloudflare/zones` | POST | Create zone (existing) |
| `/api/cloudflare/dns/{domain}` | POST | Add records (existing) |

### Step 2-5: Site Configuration

After domain + hosting:
- **Step 2: Brand** — Name, tagline, colors, logo
- **Step 3: Services** — Add/edit service entities
- **Step 4: Contact** — Email, phone, address, social
- **Step 5: Review & Deploy** — Preview and publish

### Technical Architecture

**Frontend:** Next.js 14, TailwindCSS + shadcn/ui, React Hook Form + Zod
**Backend:** VPS DNS Manager (existing Cloudflare/Namecheap APIs)
**Integration:** Fabrik domain_setup.py, deployer.py

### Implementation Priority

1. **Backend APIs (1-2 days):** Domain check, register, pricing
2. **Fabrik Integration (1 day):** `register_domain()` function
3. **Web GUI (1-2 weeks):** Next.js wizard

---

## Integration Ideas

| Project | Use Case |
|---------|----------|
| YouTube Pipeline | Store audio in R2 |
| Translator | Document upload/download |
| Calendar Engine | ICS file storage |
| LLM Batch | Prompt/response audit trail |

---

## Future Enhancements

- AI content generation
- Custom section types
- Multi-site management dashboard
- Pre-built site templates marketplace

---

## Quick Commands

```bash
# Deploy File API
cd /opt/apps/file-api && gh repo create file-api --private --push

# Test upload
TOKEN=$(curl -s -X POST 'https://xjmsceegyztgtcpywhry.supabase.co/auth/v1/token?grant_type=password' \
  -H 'apikey: YOUR_ANON_KEY' -d '{"email":"test@fabrik.dev","password":"FabrikTest2025!"}' | jq -r '.access_token')
```

---

## Notes

- All credentials in `/opt/fabrik/.env`
- Test user: `test@fabrik.dev` / `FabrikTest2025!`
- Test tenant: `test-tenant`
