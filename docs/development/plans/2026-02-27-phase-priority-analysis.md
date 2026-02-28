# Fabrik Phase Priority Analysis

**Date:** 2026-02-27  
**Scope:** Prioritize remaining Fabrik phases for 10 active projects

---

## Table of Contents

1. [Recommended Order](#recommended-order)
2. [Project Analysis](#project-analysis)
3. [Phase Details](#phase-details)
4. [Execution Roadmap](#execution-roadmap)
5. [Detailed Project Infrastructure Analysis](#detailed-project-infrastructure-analysis)
6. [Why This Order?](#why-this-order)
7. [Phase Implementation Details](#phase-implementation-details)
8. [Risk Assessment](#risk-assessment)
9. [Success Criteria](#success-criteria)
10. [Appendix: Project Status Summary](#appendix-project-status-summary)

---

## Recommended Order

| # | Phase | Effort | Projects Unblocked |
|---|-------|--------|-------------------|
| 1 | **Phase 9** | 1-2 days | 8 projects (browserless, gotenberg, minio, apprise) |
| 2 | **Phase 6** | 3-4 days | trading-core (CRITICAL), youtube |
| 3 | **Phase 3** | 2-3 days | 6 AI-dependent projects |
| 4 | **Phase 8** | 4-5 days | triggered-content, ComplianceOps, calendar |
| 5 | **Phase 5** | DEFER | Nice-to-have for trading-core |
| 6 | **Phase 7** | DEFER | Not needed (single VPS sufficient) |

---

## Project Analysis

### BLOCKING Dependencies (Cannot Proceed Without)

| Project | Blocked By | Service Needed |
|---------|------------|----------------|
| **Chrome Extension** | Phase 9 | `browserless` - ATS form automation |
| **proposal-creator** | Phase 9 | `gotenberg` - professional PDF output |
| **trading-core** | Phase 6 | Monitoring - handles real money |
| **triggered-content** | Phase 3+8 | AI content gen + n8n workflows |
| **ComplianceOps** | Phase 8 | n8n intake workflows |

### Production Systems (Need Monitoring)

| Project | Current State | Monitoring Need |
|---------|---------------|-----------------|
| **youtube** | Production SaaS, 86 channels | Loki logs, Grafana dashboards, error alerts |
| **trading-core** | Live FX trading | **CRITICAL** - P&L tracking, risk alerts |

### AI-Dependent Projects (6 total)

| Project | AI Use Case | Current State |
|---------|-------------|---------------|
| brand-identity-creator | Generate brand guidelines, logo concepts | Direct Replicate/OpenAI |
| proposal-creator | Extract proposals from discovery notes | Direct Anthropic |
| triggered-content | Draft content for 5 platforms | Not started |
| ComplianceOps | Generate compliance documentation | Not started |
| youtube | Video summaries, content analysis (future) | Not using AI yet |
| Chrome Extension | Job matching, cover letter generation (future) | Not started |

---

## Phase Details

### Phase 9: Deploy Services (FIRST - 1-2 days)

**Services to deploy:**
- `browserless/chrome` → Chrome extension, youtube scraping
- `gotenberg/gotenberg` → proposal-creator PDFs, brand guides
- `minio/minio` → Asset storage for 5+ projects
- `caronc/apprise` → Unified notifications all projects
- `getmeili/meilisearch` → Fast search for youtube, trade-intelligence

**Fix:** 2 Dockerfiles still use Alpine → change to bookworm-slim

### Phase 6: Monitoring (SECOND - 3-4 days)

**Deploy:**
1. Loki + Promtail (log aggregation)
2. Prometheus + Node Exporter + cAdvisor (metrics)
3. Grafana (dashboards)
4. Alert rules → Apprise → Slack/email

**Critical for:** trading-core (real money), youtube (production SaaS)

### Phase 3: AI Wrapper (THIRD - 2-3 days)

**Build:**
1. `src/fabrik/ai/client.py` - Provider-agnostic (Claude + OpenAI)
2. `fabrik ai generate` CLI command
3. Token usage tracking (SQLite)
4. Prompt template library

**Benefits 6 projects** that currently duplicate AI integration code

### Phase 8: n8n Workflows (FOURTH - 4-5 days)

**Deploy n8n, create workflows for:**
- triggered-content: Trigger → Generate → Review → Publish pipeline
- ComplianceOps: Intake → Assessment → Template delivery
- calendar-orchestration: Event sync automation
- trading-core: Risk alert → Action workflows

---

## Execution Roadmap

### Week 1: Phase 9
```
Day 1: Deploy browserless, gotenberg
Day 2: Deploy minio, apprise, meilisearch
       Fix Alpine Dockerfiles
```
**Result:** Chrome extension, proposal-creator UNBLOCKED

### Week 2: Phase 6
```
Day 1-2: Deploy Loki, Promtail, Prometheus
Day 3: Deploy Grafana, create dashboards
Day 4: Configure alerting
```
**Result:** trading-core SAFE for production

### Week 3: Phase 3
```
Day 1: Build LLMClient wrapper
Day 2: Add CLI commands, token tracking
Day 3: Migrate existing code to use wrapper
```
**Result:** 6 AI projects share infrastructure

### Week 4+: Phase 8 (as needed)
```
Deploy n8n, build workflows incrementally
```

---

## Detailed Project Infrastructure Analysis

### youtube - Production SaaS

**Current Architecture:**
```
Extractor v2.3.0 (Selenium + proxy) → Downloader (RapidAPI) → Transcriber (Soniox) → Comments
                                          ↓
                              PostgreSQL (86 channels, 1,699 videos)
                                          ↓
                              Flask Dashboard (multi-tenant, subscriptions)
```

**What youtube gains from each phase:**

| Phase | Capability Added | Business Impact |
|-------|------------------|-----------------|
| Phase 9 | Browserless cluster | Scale scraping 10x, replace local Selenium |
| Phase 9 | Meilisearch | Sub-100ms transcript search (currently slow LIKE) |
| Phase 9 | Apprise | Job completion alerts to Slack/email |
| Phase 6 | Loki | Debug pipeline failures with log history |
| Phase 6 | Grafana | Visualize throughput, queue depth, errors |
| Phase 6 | Alerting | Know about failures before users report |

---

### Chrome Extension - LinkedIn/ATS Automation

**Expected Architecture:**
```
Chrome Extension (content scripts)
        ↓
Backend API (job matching, deduplication)
        ↓
Browserless (headless Chrome farm) ← BLOCKING
        ↓
ATS Form Automation
```

**Why Phase 9 is BLOCKING:**
- ATS form filling requires headless browser control
- Cannot do Playwright/Puppeteer automation at scale without browserless
- Local Chrome is single-threaded, unreliable

**Phase 9 services needed:**
- `browserless/chrome` - Headless browser farm (REQUIRED)
- `redis` - Job queue for async form submissions
- `apprise` - Application status notifications

---

### proposal-creator - B2B Proposal Generation

**Current Architecture:**
```
Discovery Notes (notes.md)
        ↓
AI Extraction (Anthropic direct) → proposal_data.yaml
        ↓
14-Point Linter
        ↓
Jinja2 Templates → Markdown
        ↓
WeasyPrint → Basic PDF ← BLOCKING (unprofessional)
```

**Why Phase 9 gotenberg is BLOCKING:**
- WeasyPrint produces basic PDFs (no headers/footers, poor styling)
- B2B proposals need professional formatting
- Gotenberg provides: HTML→PDF with full CSS, Office document support

**Upgrade path with Gotenberg:**
```
Markdown → HTML (styled) → Gotenberg API → Professional PDF
                                        → DOCX (for client edits)
                                        → PPTX (for presentations)
```

---

### trading-core - Live FX Trading

**Current Architecture:**
```
cTrader Open API ← Pepperstone connection
        ↓
Risk Gates (max daily loss, max exposure)
        ↓
Kill-Switch Protection
        ↓
SQLite State Persistence
        ↓
LEAN Research Layer
```

**Why Phase 6 is CRITICAL:**

| Without Monitoring | With Monitoring |
|--------------------|-----------------|
| Blind to position health | Real-time P&L dashboard |
| Manual kill-switch only | Automated risk alerts |
| Post-mortem debugging | Live trade logging |
| No performance tracking | Win rate, drawdown metrics |
| Miss risk events | SMS/Slack on threshold breach |

**This handles REAL MONEY. Monitoring is non-negotiable.**

---

### triggered-content-orchestration - Content Pipeline

**Expected Architecture:**
```
Trigger (schedule, webhook, manual)
        ↓
Canonical Outline (evidence validation)
        ↓
AI Draft Generation ← Phase 3 BLOCKING
        ↓
Review Workflow ← Phase 8 BLOCKING (n8n approval UI)
        ↓
Platform-Specific Repurposing
        ↓
Publish (Twitter, YouTube, Blog, Email, LinkedIn)
```

**Dual dependency:**
- **Phase 3:** Cannot generate content without AI wrapper
- **Phase 8:** Cannot orchestrate pipeline without n8n

Both phases required before meaningful development can start.

---

### ComplianceOps - HealthTech Compliance SaaS

**Expected Architecture:**
```
Client Intake Form
        ↓
n8n Intake Workflow ← Phase 8 BLOCKING
        ↓
Assessment (questionnaire)
        ↓
Template Selection
        ↓
AI Document Generation ← Phase 3 beneficial
        ↓
Client Portal Delivery
        ↓
Audit-Ready Package (10 days)
```

**Phase 8 is BLOCKING:**
- Entire product is workflow-based
- Cannot build intake without n8n
- n8n provides: form processing, notifications, status tracking

---

### brand-identity-creator - AI Brand Generation

**Current Architecture:**
```
Customer Questionnaire
        ↓
Existing Brand Materials (upload)
        ↓
droid exec + Replicate API ← needs Phase 3 wrapper
        ↓
AI Generation (logos, colors, typography)
        ↓
Brand Package Output
        ↓
PDF Brand Guide ← needs Phase 9 gotenberg
```

**Phase 3 + 9 together:**
- Phase 3: Unified LLM calls (currently direct Replicate/OpenAI)
- Phase 9 gotenberg: Professional brand guide PDFs
- Phase 9 minio: Store generated brand assets

---

### image-broker - Stock Image API Gateway

**Current Architecture:**
```
WordPress Content Gen
        ↓
Image Broker API
        ↓
├── Pexels API
├── Pixabay API
        ↓
Deterministic Scoring (keyword match, quality, composition)
        ↓
Two-Tier Cache (search 24h, images 48h)
        ↓
SEO-friendly download
```

**Infrastructure Gaps:**
| Gap | Current | Ideal | Phase |
|-----|---------|-------|-------|
| Cache storage | File-based | Minio S3 | Phase 9 |
| Session cache | In-memory | Redis | Phase 9 |

**Phase 9 benefits:**
- Minio: Persistent image cache across restarts
- Redis: Shared cache for horizontal scaling

---

### trade-intelligence - Trade Data API Gateway

**Current Architecture:**
```
External Data Providers (BOL, ImportGlobals)
        ↓
Pluggable Adapters
        ↓
Company Name Normalization
        ↓
HS Code Standardization
        ↓
Redis Cache + PostgreSQL Storage
        ↓
Trade Intelligence API
```

**Infrastructure Gaps:**
| Gap | Current | Ideal | Phase |
|-----|---------|-------|-------|
| Full-text search | PostgreSQL | Meilisearch | Phase 9 |
| Data exploration | CLI only | NocoDB/Metabase | Phase 9 |
| Analytics | None | Grafana dashboards | Phase 6 |

**Phase 9 benefits:**
- Meilisearch: Sub-100ms fuzzy search across trade records
- NocoDB: Visual data exploration for analysts

---

### calendar-orchestration-engine - Multi-Provider Calendar

**Expected Architecture:**
```
Calendar Providers (Google, Outlook, iCal)
        ↓
Event Scraping/Aggregation
        ↓
Conflict Resolution Engine
        ↓
Scheduling Intelligence
        ↓
Event Coordination API
```

**Infrastructure Gaps:**
| Gap | Current | Ideal | Phase |
|-----|---------|-------|-------|
| Workflow orchestration | None | n8n | Phase 8 |
| Data UI | None | NocoDB | Phase 9 |
| Scheduled syncs | Manual | n8n cron | Phase 8 |

**Phase 8 benefits:**
- n8n: Visual workflow for multi-provider sync
- Scheduled triggers for calendar polling
- Conflict notification workflows

---

## Why This Order?

1. **Phase 9 first:** Lowest effort (1-2 days), highest immediate impact (8 projects benefit). Deploys services that BLOCK 3 projects.

2. **Phase 6 second:** trading-core handles **real money** - cannot go live without monitoring. youtube is production SaaS needing visibility.

3. **Phase 3 third:** 6 projects need AI. Currently each implements its own - shared wrapper saves time on every project.

4. **Phase 8 fourth:** Only needed when starting triggered-content or ComplianceOps development.

5. **Phase 5 defer:** Nice for trading-core (paper trading), but not blocking.

6. **Phase 7 defer:** Single VPS handles all current projects. Only needed at scale.

---

## Phase Implementation Details

### Phase 9: Service Deployment Specifications

**browserless/chrome:**
```yaml
# specs/browserless.yaml
name: browserless
type: docker
domain: browser.vps1.ocoron.com
image: browserless/chrome:latest
environment:
  MAX_CONCURRENT_SESSIONS: 10
  CONNECTION_TIMEOUT: 60000
  PREBOOT_CHROME: true
  ENABLE_DEBUGGER: false
ports:
  - 3000:3000
healthcheck:
  path: /
```

**gotenberg:**
```yaml
# specs/gotenberg.yaml
name: gotenberg
type: docker
domain: pdf.vps1.ocoron.com
image: gotenberg/gotenberg:8
environment:
  CHROMIUM_DISABLE_JAVASCRIPT: false
  CHROMIUM_ALLOW_LIST: "file:///tmp/.*"
ports:
  - 3001:3000
healthcheck:
  path: /health
```

**minio:**
```yaml
# specs/minio.yaml
name: minio
type: docker
domain: s3.vps1.ocoron.com
image: minio/minio:latest
command: server /data --console-address ":9001"
environment:
  MINIO_ROOT_USER: ${MINIO_ROOT_USER}
  MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
volumes:
  - minio-data:/data
ports:
  - 9000:9000
  - 9001:9001
healthcheck:
  path: /minio/health/live
```

**apprise:**
```yaml
# specs/apprise.yaml
name: apprise
type: docker
domain: notify.vps1.ocoron.com
image: caronc/apprise:latest
ports:
  - 8000:8000
healthcheck:
  path: /
```

---

### Phase 6: Monitoring Stack Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Your Services (youtube, trading-core, etc.)                 │
│   └── Docker logs → Promtail → Loki                         │
│   └── /metrics endpoint → Prometheus                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Monitoring Stack                                            │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Promtail  │───▶│    Loki     │◀───│  LogQL UI   │     │
│  │ (log ship)  │    │ (log store) │    │ (Grafana)   │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │Node Exporter│───▶│ Prometheus  │───▶│  Grafana    │     │
│  │  cAdvisor   │    │  (metrics)  │    │(dashboards) │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                              │              │
│                                              ▼              │
│                                       ┌─────────────┐      │
│                                       │   Apprise   │      │
│                                       │ (alerts to  │      │
│                                       │Slack/Email) │      │
│                                       └─────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

**Grafana Dashboards to Create:**
1. **System Overview** - CPU, memory, disk, network
2. **Container Health** - Per-container resources, restarts
3. **youtube Pipeline** - Queue depth, transcription rate, errors
4. **trading-core** - P&L, positions, risk metrics

**Alert Rules:**
- Container restart > 3 in 5 minutes → Slack
- CPU > 90% for 5 minutes → Slack
- Disk > 85% → Email
- trading-core risk gate triggered → SMS + Slack

---

### Phase 3: LLM Wrapper Architecture

```python
# src/fabrik/ai/client.py

class LLMProvider(Enum):
    CLAUDE = "claude"
    OPENAI = "openai"

class LLMClient:
    """Provider-agnostic LLM client with cost tracking."""
    
    def __init__(self, provider: LLMProvider = LLMProvider.CLAUDE):
        self.provider = provider
        self.usage_tracker = UsageTracker()
    
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate content with automatic retry and cost tracking."""
        # Route to provider
        # Track tokens and cost
        # Return standardized response
    
    def generate_structured(self, prompt: str, schema: dict) -> dict:
        """Generate JSON matching schema."""
        
    def revise(self, content: str, instructions: str) -> str:
        """Revise existing content based on instructions."""
```

**CLI Commands:**
```bash
fabrik ai generate "Write a product description for..."
fabrik ai revise path/to/content.md "Make it more concise"
fabrik ai usage --month 2026-02  # Show token/cost breakdown
```

**Projects Using This:**
- brand-identity-creator: `LLMClient().generate_structured()`
- proposal-creator: `LLMClient().generate()` for extraction
- triggered-content: `LLMClient().generate()` for drafts
- ComplianceOps: `LLMClient().generate_structured()` for docs

---

### Phase 8: n8n Workflow Templates

**Workflow 1: Content Publishing Pipeline (triggered-content)**
```
Trigger (webhook/schedule)
    ↓
HTTP Request → Get topic from API
    ↓
Code Node → Generate prompt
    ↓
HTTP Request → LLM API call
    ↓
Slack → Send for review (approve/reject buttons)
    ↓
IF approved → HTTP Request → Publish to platforms
    ↓
Apprise → Notify completion
```

**Workflow 2: ComplianceOps Intake**
```
Webhook → New client form submitted
    ↓
Google Sheets → Log submission
    ↓
HTTP Request → Create project in database
    ↓
Email → Send questionnaire link
    ↓
Wait → 48 hours
    ↓
IF not completed → Email reminder
```

**Workflow 3: trading-core Risk Alert**
```
Webhook → Risk gate triggered
    ↓
Switch → Route by severity
    ↓
CRITICAL: 
  - Slack message (immediate)
  - SMS via Apprise
  - Email to backup
    ↓
WARNING:
  - Slack message only
```

---

### Phase 5: Staging Environments (DEFERRED)

**What it provides:**
```
fabrik staging:create myproject    → Create staging.myproject.vps1.ocoron.com
fabrik staging:sync myproject      → Sync production → staging
fabrik staging:promote myproject   → Deploy staging → production
```

**Components:**
- Environment field in specs (`environment: staging|production`)
- Staging subdomain convention (`staging.*.vps1.ocoron.com`)
- Database cloning with anonymization
- File sync (uploads, themes, plugins)
- URL replacement in database

**Why deferred:**
- No project currently requires isolated testing
- trading-core would benefit (paper trading), but can test locally
- youtube changes can be tested on dev instance
- Can be added when first client-facing staging is needed

**Revisit when:**
- trading-core ready for paper trading phase
- Client needs staging preview before go-live
- Multiple developers need isolated environments

---

### Phase 7: Multi-Server Scaling (DEFERRED)

**What it provides:**
```
vps1.ocoron.com ←──WireGuard VPN──→ vps2.ocoron.com
        │                                   │
        └──── Shared PostgreSQL ────────────┘
        └──── Shared Redis ─────────────────┘
        └──── Centralized Monitoring ───────┘
```

**Components:**
- Second VPS provisioning
- WireGuard VPN between servers
- Server registry (`fabrik servers list`)
- PgBouncer for shared PostgreSQL
- Redis cluster
- DNS-based load balancing
- Deployment routing (`server: vps1|vps2`)

**Why deferred:**
- Single VPS (4 vCPU, 8GB RAM) handles all current projects
- No project requires geographic distribution
- No compliance requirement for redundancy
- Cost: ~$40/month for second VPS

**Revisit when:**
- VPS1 CPU consistently >70%
- Memory pressure on single server
- Compliance requires redundancy (e.g., for trading-core)
- Need US/EU geographic presence

---

## Risk Assessment

### If You Skip Phase 9

| Project | Risk |
|---------|------|
| Chrome Extension | **CANNOT BUILD** - no headless browser |
| proposal-creator | Unprofessional PDFs lose deals |
| brand-identity | No asset storage, manual file handling |
| All projects | No unified notifications |

### If You Skip Phase 6

| Project | Risk |
|---------|------|
| trading-core | **TRADING BLIND** - no P&L visibility |
| youtube | Discover failures from user reports |
| All production | No debugging capability |

### If You Skip Phase 3

| Project | Risk |
|---------|------|
| 6 AI projects | Each duplicates AI integration code |
| Development | 2-4 hours lost per project setting up AI |
| Costs | No token tracking, surprise bills |

---

## Success Criteria

### Phase 9 Complete When:
- [ ] `curl browser.vps1.ocoron.com/` returns browserless UI
- [ ] `curl pdf.vps1.ocoron.com/health` returns healthy
- [ ] `curl s3.vps1.ocoron.com/minio/health/live` returns OK
- [ ] `curl notify.vps1.ocoron.com/` returns apprise UI
- [ ] All Dockerfiles use `bookworm-slim` (no Alpine)

### Phase 6 Complete When:
- [ ] Grafana accessible at `monitor.vps1.ocoron.com`
- [ ] All containers visible in Loki
- [ ] System dashboard shows CPU/memory/disk
- [ ] Test alert fires to Slack successfully

### Phase 3 Complete When:
- [ ] `from fabrik.ai import LLMClient` works
- [ ] `fabrik ai generate "test prompt"` returns content
- [ ] `fabrik ai usage` shows token breakdown
- [ ] One existing project migrated to use wrapper

### Phase 8 Complete When:
- [ ] n8n accessible at `auto.vps1.ocoron.com`
- [ ] One workflow deployed and tested
- [ ] Webhook triggers successfully

---

## Appendix: Project Status Summary

| Project | Status | Stack | Primary Blocking Phase |
|---------|--------|-------|------------------------|
| youtube | Production | Python/Flask/PostgreSQL | Phase 6 (monitoring) |
| Chrome Extension | Not started | Chrome/Node | **Phase 9** (browserless) |
| brand-identity-creator | Development | Python/AI | Phase 3 (AI wrapper) |
| calendar-orchestration | Scaffolded | Python/TS | Phase 8 (n8n) |
| triggered-content | Scaffolded | Python | **Phase 3+8** (both) |
| proposal-creator | Functional | Python/FastAPI | **Phase 9** (gotenberg) |
| trading-core | Scaffolded | Python/cTrader | **Phase 6** (monitoring) |
| image-broker | Functional | Python/FastAPI | Phase 9 (minio) |
| ComplianceOps | Scaffolded | Next.js/Supabase | **Phase 8** (n8n) |
| trade-intelligence | Scaffolded | Python | Phase 9 (meilisearch) |

---

## Appendix: Fabrik Phase Current State

| Phase | Name | Status | Completion |
|-------|------|--------|------------|
| Phase 1 | Core Infrastructure | ✅ Complete | 100% |
| Phase 2 | WordPress Automation | ✅ Complete | 100% |
| Phase 3 | AI Content Integration | 🟡 Partial | ~30% |
| Phase 4 | DNS + Cloudflare | ✅ Complete | ~75% |
| Phase 5 | Staging Environments | ❌ Not Started | 0% |
| Phase 6 | Advanced Monitoring | 🟡 Partial | ~13% |
| Phase 7 | Multi-Server Scaling | ❌ Not Started | 0% |
| Phase 8 | n8n Automation | ❌ Not Started | 0% |
| Phase 9 | Docker Acceleration | 🟡 Partial | ~50% |
| Phase 10 | Deployment Orchestrator | ✅ Complete | 100% |

---

## Appendix: Service Port Allocations

For Phase 9 service deployments, reference PORTS.md:

| Service | Port | Domain |
|---------|------|--------|
| browserless | 3000 | browser.vps1.ocoron.com |
| gotenberg | 3001 | pdf.vps1.ocoron.com |
| minio | 9000/9001 | s3.vps1.ocoron.com |
| apprise | 8000 | notify.vps1.ocoron.com |
| meilisearch | 7700 | search.vps1.ocoron.com |
| n8n | 5678 | auto.vps1.ocoron.com |
| grafana | 3002 | monitor.vps1.ocoron.com |
| loki | 3100 | (internal) |
| prometheus | 9090 | (internal) |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-27 | Phase 9 first | Lowest effort, unblocks 3 projects immediately |
| 2026-02-27 | Phase 7 deferred | Single VPS sufficient, no scaling pressure |
| 2026-02-27 | Phase 5 deferred | No client-facing staging needed yet |
| 2026-02-27 | Phase 6 before Phase 3 | trading-core safety is higher priority than AI convenience |
