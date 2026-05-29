# Fabrik Business Model

**Last Updated:** 2026-02-26

Fabrik's monetization strategy and revenue opportunities.

## Overview

Fabrik is an **internal platform** enabling rapid deployment of revenue-generating products.

**Primary value:** Reduce deployment friction from hours → minutes, enabling more experiments and faster iteration.

## Revenue Streams

**See Project Portfolio below for complete catalog of revenue-generating projects.**

### Active Production Services
- **11 deployed services** in production (captcha, youtube, translator, etc.)
- **6 projects in active development**
- Multi-tenant SaaS, API services, B2B tools

### Revenue Models
- **SaaS subscriptions** (YouTube pipeline)
- **API usage fees** (Captcha, translation, file storage)
- **B2B services** (Proposal generation, proxy management)
- **Internal tools** (Email gateway, Site provisioner)

## Cost Structure

### Infrastructure

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| VPS | ~$20-50 | Scales with products |
| Domains | ~$10-20/year each | Per product |
| Backblaze B2 | ~$5-10 | Backup storage |
| **Total baseline** | **~$30-60/month** | |

### AI/API Costs

| Service | Usage-Based | Notes |
|---------|-------------|-------|
| Claude/OpenAI | Per token | Content generation |
| Namecheap API | Free | DNS management |
| Coolify | Free (self-hosted) | Deployment |

## Break-Even Analysis

With ~$50/month infrastructure cost:

- **1 Gumroad sale** at $50 = break-even
- **2-3 consulting hours** = profitable
- **10 blog posts** with affiliate = variable

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Deployment time | <5 min | From spec to live |
| Uptime | >99% | Gatus |
| Products deployed | 3+ | YT, Wellness, QMS |
| Monthly revenue | $30k+ | 12-month goal |

## Competitive Advantage

1. **Speed:** Minutes not hours to deploy
2. **AI-integrated:** Content generation built-in (Phase 3)
3. **Low cost:** Self-hosted, no platform fees
4. **Domain expertise:** Healthcare IT, cosmetics, B2B

## Phase-Revenue Mapping

| Phase | Revenue Unlock |
|-------|----------------|
| 1 (Foundation) | Platform ready |
| 2 (WordPress) | Client site capability |
| 3 (AI Content) | Content at scale |
| 4-8 | Efficiency/scale |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| VPS failure | Daily backups to B2 |
| Over-engineering | Phase-gated development |
| Scope creep | Project portfolio tracking |
| Revenue delay | B2B/labels as side income |

---

## Project Portfolio

<!-- AUTO-GENERATED:PROJECTS:START -->
<!-- Last synced: 2026-05-29 11:57:39 -->
<!-- Total projects: 34 -->

### Production Services (5 projects)

| Project | Purpose | Stack | Status | URL | Scaffold |
|---------|---------|-------|--------|-----|----------|
| **captcha** | A REST API service for solving captchas. Other applications can call this service to solve reCA... | Python | ✅ Production | https://captcha.vps1.ocoron.com | ✅ Current |
| **image-broker** | Unified API for stock image providers with **smart routing, deterministic scoring, and Option C... | Python | ✅ Production | https://images.vps1.ocoron.com | ✅ Current |
| **proxy** | **Status:** Production Ready - Proxy Management API ✅ | Python | ✅ Production | Multi-service proxy broker | ✅ Current |
| **site-provisioner** | Unified site provisioning API - domain registration, DNS, SSL, CDN, analytics, and webmaster to... | Python | ✅ Production | https://provision.vps1.ocoron.com | ✅ Current |
| **youtube** | **Status:** Production Ready - Multi-Tenant SaaS ✅ | Python | ✅ Production | Multi-tenant SaaS | ✅ Current |

### Active Development (13 projects)

| Project | Purpose | Stack | Status | URL | Scaffold |
|---------|---------|-------|--------|-----|----------|
| **calendar-orchestration-engine** | Automated calendar scheduling system with conflict resolution and multi-provider integration. | Python | 🔨 Development | https://calendar-orchestration-engine.vps1.ocoron.com | ✅ Current |
| **candle** | FastAPI microservice project (in development). | FastAPI | 🔨 Development | - | ✅ Current |
| **fabrik-claim-validator** | Multi-tradition claim validation + substance discovery service. Sibling to fabrik-citation-veri... | FastAPI | 🔨 Development | - | ✅ Current |
| **job-agent** | AI agent orchestration and job processing system | FastAPI | 🔨 Development | https://job-agent.vps1.ocoron.com | ✅ Current |
| **longephedia-vault** | Structured ontology + RAG over Longephedia constitution (12 themes, discipline rules, protocols... | FastAPI | 🔨 Development | - | ✅ Current |
| **obsidian-agents** | Obsidian plugin: right-pane chat view that drives Claude Code and Kilo CLI agents via headless ... | Node.js | 🔨 Development | - | ✅ Current |
| **proposal-creator** | A professional B2B proposal generation system based on best practices from McKinsey, Shipley, a... | FastAPI | 🔨 Development | https://proposal-creator.vps1.ocoron.com | ✅ Current |
| **seo** | SEO keyword research and long-tail keyword generation for AI content creation | FastAPI | 🔨 Development | https://seo.vps1.ocoron.com | ✅ Current |
| **test-saas-platform** | Full-blown SaaS platform for testing mega-epic workflow | Node.js | 🔨 Development | - | ✅ Current |
| **trade-intelligence** | **Last Updated:** 2026-03-10 | FastAPI | 🔨 Development | https://trade-intelligence.vps1.ocoron.com | ✅ Current |
| **trading-core** | Crash-safe Python FX trading service with Pepperstone/cTrader integration and risk gates. | FastAPI | 🔨 Development | - | ✅ Current |
| **triggered-content-orchestration** | Multi-platform content orchestration pipeline for automated content creation and distribution. | FastAPI | 🔨 Development | https://triggered-content-orchestration.vps1.ocoron.com | ✅ Current |
| **wpf** | WordPress Factory — Python orchestrator (CLI now, FastAPI in Phase 3, Next.js wizard in Phase 4... | Python | 🔨 Development | - | ✅ Current |

### Planning/Research (15 projects)

| Project | Purpose | Stack | Status | URL | Scaffold |
|---------|---------|-------|--------|-----|----------|
| **ComplianceOps** | Async compliance service platform for HealthTech startups. | Python | 🔨 Development | https://compliance-ops.vps1.ocoron.com | ✅ Current |
| **Reference_Creator** | Automated reference document creator from source materials. | Python | 🔨 Development | https://reference-creator.vps1.ocoron.com | ✅ Current |
| **apidoccreator** | External documentation registry. Scrapes, generates, stores and serves docs for AI agent consum... | FastAPI | 🔨 Development | - | ✅ Current |
| **brand-identiy-creator** | AI-powered tool for creating comprehensive brand identities from customer inputs and existing m... | FastAPI | 🔨 Development | https://brand-identity-creator.vps1.ocoron.com | ✅ Current |
| **email-reader** | A Python service to read Gmail and Microsoft 365 emails, extracting verification codes or login... | Python | 🔨 Development | https://email-reader.vps1.ocoron.com | ✅ Current |
| **emailgateway** | No description available | Unknown | 🔨 Development | - | ⚠️ No project.yaml |
| **exam-coach** | AI-powered exam preparation and coaching assistant. | Python | 🔨 Development | https://exam-coach.vps1.ocoron.com | ✅ Current |
| **gmailaccountcreator** | Automated Gmail account creation and management tool. | Python | 🔨 Development | - | ✅ Current |
| **image-generation** | Complete product photography system with platform-specific requirements and DIY setup guidance. | Python | 🔨 Development | - | ✅ Current |
| **iterative_image_editor** | AI-powered product photography tool for automated background removal and scene placement. | Python | 🔨 Development | https://iterative-image-editor.vps1.ocoron.com | ✅ Current |
| **llm_batch_processor** | A self-hosted automation tool for processing documents through Claude and ChatGPT web interface... | Python | 🔨 Development | - | ✅ Current |
| **marketing-argumant-generator** | AI-powered marketing argument and copy generation tool. | Python | 🔨 Development | https://marketing-argument-generator.vps1.ocoron.com | ✅ Current |
| **supplement-tracker-advisor** | Health supplement tracking and personalized advisory system. | Python | 🔨 Development | - | ✅ Current |
| **ugc** | User-generated content data scraping system for social media platforms. | Python | 🔨 Development | - | ✅ Current |
| **web-scraper** | Scrapy + Playwright web scraper extracting content for AI training pipelines. | Flask | 🔨 Development | - | ✅ Current |

<!-- AUTO-GENERATED:PROJECTS:END -->
