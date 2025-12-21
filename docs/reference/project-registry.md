# Project Registry

> **Master inventory of all projects under /opt with status, dependencies, and deployment roadmap.**
> **Last updated:** 2025-12-21

---

## Project Classification

### Tier 0: Platform Infrastructure (Fabrik)

| Project | Status | Purpose |
|---------|--------|---------|
| `/opt/fabrik` | 🟡 In Development | Deployment automation CLI for Coolify |

---

### Tier 1: Shared Infrastructure Services

These are **internal services** that other projects depend on. Must be deployed first.

| Project | Status | Stack | Port | Consumers | VPS Ready |
|---------|--------|-------|------|-----------|-----------|
| `/opt/proxy` | ✅ Working | Python | - | youtube, namecheap | ⚠️ Needs Dockerfile |
| `/opt/captcha` | ✅ Working | FastAPI | 8000 | youtube | ⚠️ Needs Dockerfile |
| `/opt/emailgateway` | ✅ Working | Node.js/Fastify | 3000 | all projects | ⚠️ Needs Dockerfile |
| `/opt/translator` | ✅ Working | FastAPI | 8000 | youtube | ⚠️ Needs Dockerfile |
| `/opt/email-reader` | ✅ Working | FastAPI | 5050 | llm_batch_processor | ⚠️ Needs Dockerfile |
| `/opt/namecheap` | ✅ Working | FastAPI | 8001 | fabrik (DNS) | ⚠️ Needs Dockerfile |

**Deployment Order:** proxy → captcha → translator → emailgateway → email-reader → namecheap

---

### Tier 2: Core Products (Revenue Generating)

| Project | Status | Stack | Business Model | Priority |
|---------|--------|-------|----------------|----------|
| `/opt/youtube` | 🟡 Active Dev | Python, PostgreSQL | Data mining + SaaS | **HIGH** |
| `/opt/image-generation` | 🔴 Not Complete | Python, BFL API | Internal + SaaS | **HIGH** |
| `/opt/proposal-creator` | ✅ Working | Python, Claude | Consultancy + SaaS | **MEDIUM** |
| `/opt/calendar-orchestration-engine` | ✅ Ready | Node.js, PostgreSQL | Internal service | **HIGH** (deploy soon) |

---

### Tier 3: Future Products (Planned/Early Stage)

| Project | Status | Stack | Business Model | Timeline |
|---------|--------|-------|----------------|----------|
| `/opt/brand-identity-creator` | 🔴 Needs Dev | TBD | SaaS | TBD |
| `/opt/complianceOS` | 📋 Planned | TBD | SaaS | **10 days** |
| `/opt/trade-intelligence` | 🔴 Starting | Python, billofladingdata.com | SaaS/Membership | TBD |
| `/opt/triggered-content-orchestration` | 📋 Planned | TBD | SaaS | **Major project** |
| `/opt/ugc` | 📋 Planned | Python, Scrapy | Data collection | Not started |
| `/opt/spect-interviewer` | 🟡 Early | TBD | Internal tool | TBD |

---

### Tier 4: Utilities & Support

| Project | Status | Purpose | Notes |
|---------|--------|---------|-------|
| `/opt/llm_batch_processor` | ✅ Working | Web-based ChatGPT/Claude automation | Uses email-reader |
| `/opt/web-scraper` | ✅ Working | Scrapers for calendar-orchestration-engine | Part of calendar |
| `/opt/web_scraper` | ✅ Working | Scrapers for calendar-orchestration-engine | Part of calendar |
| `/opt/iterative_image_editor` | 🟡 Dev | Image editing with FLUX | Merging into image-generation? |
| `/opt/backupsystem` | ✅ Working | Backup automation | Internal |

---

### Not Projects (Folders to Clean/Reorganize)

| Path | What It Is | Action |
|------|------------|--------|
| `/opt/google` | Browser folder? | Clarify purpose or archive |
| `/opt/gmailaccountcreator` | Just a plan | Keep as reference, use API services instead |
| `/opt/ComplianceOps` | Empty | Rename to complianceOS or delete |
| `/opt/consult` | Unknown | Review and archive |
| `/opt/apidoccreator` | Unknown | Review and archive |
| `/opt/Reference_Creator` | Empty | Delete or repurpose |
| `/opt/_previouswork` | Archive | Keep as historical reference |
| `/opt/_backups` | Backups | Keep |
| `/opt/_tools` | Utilities | Keep |
| `/opt/_orchestration` | Unknown | Review |

---

## Dependency Graph

```text
                    ┌─────────────────────────────────────────────────────────────┐
                    │                      FABRIK (Tier 0)                        │
                    │              Deployment Automation for All                  │
                    └─────────────────────────────────────────────────────────────┘
                                               │
        ┌──────────────────────────────────────┼──────────────────────────────────────┐
        │                                      │                                      │
        ▼                                      ▼                                      ▼
┌───────────────┐                    ┌───────────────┐                    ┌───────────────┐
│     PROXY     │                    │  EMAILGATEWAY │                    │   NAMECHEAP   │
│  (Webshare)   │                    │ (Resend, SES) │                    │  (DNS Mgmt)   │
└───────────────┘                    └───────────────┘                    └───────────────┘
        │                                      │                                      │
        │                                      │                                      │
        ▼                                      ▼                                      │
┌───────────────┐                    ┌───────────────┐                                │
│    CAPTCHA    │                    │  EMAIL-READER │                                │
│(Anti-Captcha) │                    │ (Gmail, M365) │                                │
└───────────────┘                    └───────────────┘                                │
        │                                      │                                      │
        │                                      ▼                                      │
        │                            ┌───────────────┐                                │
        │                            │LLM_BATCH_PROC │                                │
        │                            │(Web ChatGPT)  │                                │
        │                            └───────────────┘                                │
        │                                      │                                      │
        ▼                                      ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CORE PRODUCTS                                        │
├───────────────┬───────────────┬───────────────┬───────────────┬───────────────────────┤
│    YOUTUBE    │   TRANSLATOR  │ IMAGE-GEN     │ PROPOSAL      │ CALENDAR-ORCH         │
│  (Data+SaaS)  │   (Service)   │ (Images)      │ (Consultancy) │ (Holidays)            │
└───────────────┴───────────────┴───────────────┴───────────────┴───────────────────────┘
        │                                      │
        ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                  FUTURE PRODUCTS                                        │
├───────────────┬───────────────┬───────────────┬───────────────┬───────────────────────┤
│ COMPLIANCE-OS │ TRADE-INTEL   │ TRIGGERED-    │ UGC           │ BRAND-IDENTITY        │
│ (10 days)     │ (BoL Data)    │ CONTENT-ORCH  │ (Forum Data)  │ (Design)              │
└───────────────┴───────────────┴───────────────┴───────────────┴───────────────────────┘
```

---

## Deployment Readiness Assessment

### Ready for Dockerization (Have working code, need Dockerfile + compose.yaml)

| Project | Entry Point | Has .env | Has requirements/package.json | Missing |
|---------|-------------|----------|-------------------------------|---------|
| captcha | `app/main.py` | ✅ | ✅ requirements.txt | Dockerfile, compose.yaml |
| emailgateway | `src/index.ts` | ✅ | ✅ package.json | Dockerfile, compose.yaml |
| translator | `app/main.py` | ✅ | ✅ requirements.txt | Dockerfile, compose.yaml |
| email-reader | TBD | ✅ | ✅ requirements.txt | Dockerfile, compose.yaml |
| namecheap | `api/main.py` | ✅ | ✅ requirements.txt | Dockerfile, compose.yaml |
| calendar-orchestration-engine | `src/index.ts` | ✅ | ✅ package.json | Dockerfile (has partial compose) |
| proposal-creator | `src/main.py` | ✅ | ✅ pyproject.toml | Dockerfile, compose.yaml |

### Need Development Work

| Project | What's Missing | Effort |
|---------|----------------|--------|
| image-generation | Core functionality | 2-4 weeks |
| brand-identity-creator | Everything | 2-4 weeks |
| complianceOS | Everything (but deadline in 10 days) | 10 days |
| trade-intelligence | API integration, data pipeline | 2-4 weeks |
| triggered-content-orchestration | Architecture, implementation | 4-8 weeks |
| ugc | Crawlers, normalization pipeline | 4-8 weeks |

---

## Deployment Roadmap

### Phase 1: Infrastructure Services (Week 1-2)

**Goal:** Deploy all Tier 1 services to VPS via Coolify

```text
Day 1-2: Create Dockerfile + compose.yaml templates
Day 3:   Deploy proxy service
Day 4:   Deploy captcha service  
Day 5:   Deploy translator service
Day 6:   Deploy emailgateway service
Day 7:   Deploy email-reader service
Day 8:   Deploy namecheap service
Day 9:   Integration testing
Day 10:  Documentation
```

**Deliverables per service:**

- [ ] Dockerfile (multi-stage build)
- [ ] compose.yaml (Coolify-compatible)
- [ ] .env.example (all required vars)
- [ ] Health check endpoint
- [ ] README with deployment instructions

### Phase 2: Core Product Deployment (Week 3-4)

```text
Day 11-13: Deploy calendar-orchestration-engine
Day 14-16: Deploy proposal-creator
Day 17-20: Deploy youtube (complex, needs more time)
```

### Phase 3: complianceOS Sprint (10 days as specified)

```text
Day 1-2:   Requirements, architecture
Day 3-5:   Core implementation
Day 6-7:   API development
Day 8:     Testing
Day 9:     Dockerization
Day 10:    Deployment
```

### Phase 4: image-generation Development (Ongoing)

Priority development to enable:
- Product images for youtube SaaS
- Social media images for triggered-content-orchestration
- Brand assets for brand-identity-creator

---

## Service Communication Matrix

| Consumer → Provider | proxy | captcha | translator | emailgateway | email-reader | namecheap |
|---------------------|-------|---------|------------|--------------|--------------|-----------|
| youtube             | ✅    | ✅      | ✅         | ✅           | ❌           | ❌        |
| image-generation    | ❌    | ❌      | ❌         | ✅           | ❌           | ❌        |
| proposal-creator    | ❌    | ❌      | ❌         | ✅           | ❌           | ❌        |
| llm_batch_processor | ❌    | ❌      | ❌         | ❌           | ✅           | ❌        |
| trade-intelligence  | ✅    | ❌      | ✅         | ✅           | ❌           | ❌        |
| triggered-content   | ❌    | ❌      | ✅         | ✅           | ❌           | ❌        |
| fabrik              | ❌    | ❌      | ❌         | ✅           | ❌           | ✅        |

---

## Environment Variables Registry

All services should use these standardized env var patterns:

### Database

```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
# OR individual vars:
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mydb
DB_USER=myuser
DB_PASSWORD=mypass
```

### API Configuration

```bash
API_HOST=0.0.0.0
API_PORT=8000
API_KEY=secret
```

### Service Discovery (for inter-service communication)

```bash
PROXY_SERVICE_URL=http://proxy:8000
CAPTCHA_SERVICE_URL=http://captcha:8000
TRANSLATOR_SERVICE_URL=http://translator:8000
EMAILGATEWAY_SERVICE_URL=http://emailgateway:3000
EMAIL_READER_SERVICE_URL=http://email-reader:5050
NAMECHEAP_SERVICE_URL=http://namecheap:8001
```

---

## Port Allocation

| Port | Service | Protocol |
|------|---------|----------|
| 3000 | emailgateway | HTTP |
| 3001 | calendar-orchestration-engine (API) | HTTP |
| 5050 | email-reader | HTTP |
| 5173 | calendar-orchestration-engine (Admin UI) | HTTP |
| 5432 | PostgreSQL | TCP |
| 8000 | captcha, translator | HTTP |
| 8001 | namecheap | HTTP |

---

## Next Actions

### Immediate (This Week)

1. **Create Dockerfile template** for Python FastAPI services
2. **Create Dockerfile template** for Node.js services
3. **Create compose.yaml template** with Coolify conventions
4. **Deploy captcha** as first test service
5. **Deploy emailgateway** (needed by many services)

### Short-term (Next 2 Weeks)

1. Deploy all Tier 1 infrastructure services
2. Deploy calendar-orchestration-engine
3. Start complianceOS development sprint

### Medium-term (Next Month)

1. Complete image-generation development
2. Deploy youtube as SaaS
3. Start trade-intelligence development

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Working / Complete |
| 🟡 | In Development / Active Work |
| 🔴 | Not Complete / Blocked |
| 📋 | Planned / Not Started |
| ⚠️ | Needs Attention |
