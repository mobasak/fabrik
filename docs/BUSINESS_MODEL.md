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
- **Internal tools** (Email gateway, DNS manager)

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
| Uptime | >99% | Uptime Kuma |
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
<!-- Last synced: 2026-03-26 00:08:37 -->
<!-- Total projects: 38 -->

### Production Services (5 projects)

| Project | Purpose | Stack | Status | URL | Scaffold |
|---------|---------|-------|--------|-----|----------|
| **captcha** | A REST API service for solving captchas. Other applications can call this service to solve reCA... | Python | ✅ Production | https://captcha.vps1.ocoron.com | ✅ Current |
| **dns-manager** | Python SDK, CLI, and REST API for managing Namecheap domains, DNS, SSL, and more. | Python | ✅ Production | https://dns.vps1.ocoron.com | ✅ Current |
| **file-api** | Presigned URL service for Cloudflare R2 file uploads/downloads. | Express | ✅ Production | https://files-api.vps1.ocoron.com | ✅ Current |
| **translator** | A unified translation service wrapper that uses **DeepL** as the primary provider and **Azure T... | Python | ✅ Production | https://translator.vps1.ocoron.com | ✅ Current |
| **youtube** | **Status:** Production Ready - Multi-Tenant SaaS ✅ | Python | ✅ Production | Multi-tenant SaaS | ✅ Current |

### Active Development (14 projects)

| Project | Purpose | Stack | Status | URL | Scaffold |
|---------|---------|-------|--------|-----|----------|
| **calendar-orchestration-engine** | Automated calendar scheduling system with conflict resolution and multi-provider integration. | Python | 🔨 Development | - | ✅ Current |
| **candle** | A new project | FastAPI | 🔨 Development | - | ✅ Current |
| **emailgateway** | A provider-agnostic email gateway service with built-in routing, retry logic, rate limiting, id... | Fastify | 🔨 Development | - | ✅ Current |
| **image-broker** | Unified API for stock image providers with **smart routing, deterministic scoring, and Option C... | Python | 🔨 Development | - | ✅ Current |
| **job-agent** | AI agent orchestration and job processing system | FastAPI | 🔨 Development | - | ✅ Current |
| **proposal-creator** | A professional B2B proposal generation system based on best practices from McKinsey, Shipley, a... | FastAPI | 🔨 Development | - | ✅ Current |
| **seo** | SEO keyword research and long-tail keyword generation for AI content creation | FastAPI | 🔨 Development | - | ✅ Current |
| **test-coolify** | Coolify deployment readiness test | FastAPI | 🔨 Development | - | ✅ Current |
| **test-final** | **Last Updated:** 2026-03-23 | FastAPI | 🔨 Development | - | ✅ Current |
| **test-session-check** | Session poisoning audit - verify no Fabrik references | FastAPI | 🔨 Development | - | ✅ Current |
| **test-zero-refs** | Complete workspace isolation verification - expect ZERO /opt/fabrik references | FastAPI | 🔨 Development | - | ✅ Current |
| **trade-intelligence** | **Last Updated:** 2026-03-10 | FastAPI | 🔨 Development | - | ✅ Current |
| **trading-core** | Crash-safe Python FX trading service with Pepperstone/cTrader integration and risk gates. | FastAPI | 🔨 Development | - | ✅ Current |
| **triggered-content-orchestration** | Multi-platform content orchestration pipeline for automated content creation and distribution. | FastAPI | 🔨 Development | - | ✅ Current |

### Planning/Research (19 projects)

| Project | Purpose | Stack | Status | URL | Scaffold |
|---------|---------|-------|--------|-----|----------|
| **ComplianceOps** | Async compliance service platform for HealthTech startups. | Unknown | 🔨 Development | - | ✅ Current |
| **Reference_Creator** | Reference_Creator project | Unknown | 🔨 Development | - | ✅ Current |
| **apidoccreator** | Automated API documentation reference creator from URLs using web crawling. | Unknown | 🔨 Development | - | ✅ Current |
| **apps** | apps project | Unknown | 🔨 Development | - | ✅ Current |
| **brand-identiy-creator** | AI-powered tool for creating comprehensive brand identities from customer inputs and existing m... | Unknown | 🔨 Development | - | ✅ Current |
| **email-reader** | A Python service to read Gmail and Microsoft 365 emails, extracting verification codes or login... | Python | 🔨 Development | - | ✅ Current |
| **exam-coach** | exam-coach project | Unknown | 🔨 Development | - | ✅ Current |
| **file-worker** | file-worker project | Python | 🔨 Development | - | ✅ Current |
| **gmailaccountcreator** | gmailaccountcreator project | Unknown | 🔨 Development | - | ✅ Current |
| **image-generation** | Complete product photography system with platform-specific requirements and DIY setup guidance. | Unknown | 🔨 Development | - | ✅ Current |
| **iterative_image_editor** | AI-powered product photography tool for automated background removal and scene placement. | Python | 🔨 Development | - | ✅ Current |
| **llm_batch_processor** | A self-hosted automation tool for processing documents through Claude and ChatGPT web interface... | Python | 🔨 Development | - | ✅ Current |
| **marketing-argumant-generator** | marketing-argumant-generator project | Unknown | 🔨 Development | - | ✅ Current |
| **namecheap** | namecheap project | Unknown | 🔨 Development | - | ✅ Current |
| **proxy** | **Status:** Production Ready | Python | 🔨 Development | - | ✅ Current |
| **supplement-tracker-advisor** | supplement-tracker-advisor project | Unknown | 🔨 Development | - | ✅ Current |
| **transcriber** | Internal audio transcription API provider for project-wide transcription needs. | Unknown | 🔨 Development | - | ✅ Current |
| **ugc** | User-generated content data scraping system for social media platforms. | Unknown | 🔨 Development | - | ✅ Current |
| **web-scraper** | Scrapy + Playwright web scraper extracting content for AI training pipelines. | Flask | 🔨 Development | - | ✅ Current |

<!-- AUTO-GENERATED:PROJECTS:END -->
