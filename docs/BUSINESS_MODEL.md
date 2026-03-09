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
<!-- Last synced: 2026-03-09 18:53:10 -->
<!-- Total projects: 43 -->

### Production Services (5 projects)

| Project | Purpose | Stack | Status | URL | Scaffold Status |
|---------|---------|-------|--------|-----|------------------|
| **captcha** | A REST API service for solving captchas. Other applications can call this service to solve reCAPT... | Python | ✅ Production | https://captcha.vps1.ocoron.com | ✅ Current |
| **dns-manager** | A comprehensive toolkit for automating Namecheap domain management. Provides three integration me... | Python | ✅ Production | https://dns.vps1.ocoron.com | ✅ Current |
| **file-api** | Presigned URL service for Cloudflare R2 file uploads/downloads. | Express | ✅ Production | https://files-api.vps1.ocoron.com | ✅ Current |
| **translator** | A unified translation service wrapper that uses **DeepL** as the primary provider and **Azure Tra... | Python | ✅ Production | https://translator.vps1.ocoron.com | ✅ Current |
| **youtube** | **Status:** Production Ready - Multi-Tenant SaaS ✅ | Python | ✅ Production | Multi-tenant SaaS | ✅ Current |

### Active Development (9 projects)

| Project | Purpose | Stack | Status | URL | Scaffold Status |
|---------|---------|-------|--------|-----|------------------|
| **candle** | A new project | FastAPI | 🔨 Development | - | ✅ Current |
| **emailgateway** | A provider-agnostic email gateway service with built-in routing, retry logic, rate limiting, idem... | Fastify | 🔨 Development | - | ✅ Current |
| **image-broker** | Unified API for stock image providers with **smart routing, deterministic scoring, and Option C c... | Python | 🔨 Development | - | ✅ Current |
| **job-agent** | AI agent orchestration and job processing system | FastAPI | 🔨 Development | - | ✅ Current |
| **proposal-creator** | A professional B2B proposal generation system based on best practices from McKinsey, Shipley, and... | FastAPI | 🔨 Development | - | ✅ Current |
| **test-analysis** | Test project for scaffold validation | FastAPI | 🔨 Development | - | ✅ Current |
| **test-gitignore-python** | Test Python .gitignore generation | FastAPI | 🔨 Development | - | ✅ Current |
| **trade-intelligence** | Trade Intelligence is a comprehensive platform for searching and analyzing global shipment record... | FastAPI | 🔨 Development | - | ✅ Current |
| **trading-core** | Live FX trading service connecting to Pepperstone/cTrader via cTrader Open API with crash-safe st... | FastAPI | 🔨 Development | - | ✅ Current |

### Planning/Research (18 projects)

| Project | Purpose | Stack | Status | URL | Scaffold Status |
|---------|---------|-------|--------|-----|------------------|
| **ComplianceOps** | ComplianceOps is an async compliance service platform designed for HealthTech startups. It provid... | Unknown | 🔨 Development | - | ✅ Current |
| **apidoccreator** | CLI tool that visits documentation URLs, extracts relevant content, cleans and parses it, and pro... | Unknown | 🔨 Development | - | ✅ Current |
| **brand-identiy-creator** | Brand Identity Creator is an internal web-based tool that automates brand identity creation using... | Unknown | 🔨 Development | - | ✅ Current |
| **calendar-orchestration-engine** | Orchestrates calendar events across multiple providers with automated conflict resolution, schedu... | Python | 🔨 Development | - | ✅ Current |
| **email-reader** | - **Purpose:** Extract login codes or verification URLs from emails | Python | 🔨 Development | - | ✅ Current |
| **image-generation** | Comprehensive product photography solution providing platform-specific image requirements (Instag... | Unknown | 🔨 Development | - | ✅ Current |
| **iterative_image_editor** | AI-powered product photography tool for automated background removal and scene placement. Users u... | Python | 🔨 Development | - | ✅ Current |
| **llm_batch_processor** | A self-hosted automation tool for processing documents through Claude and ChatGPT web interfaces ... | Python | 🔨 Development | - | ✅ Current |
| **proxy** | **Status:** Production Ready | Python | 🔨 Development | - | ✅ Current |
| **test-gitignore-chromeext** | Test Chrome Extension .gitignore | Node.js | 🔨 Development | - | ✅ Current |
| **test-gitignore-fileapi** | Test File API .gitignore | Express | 🔨 Development | - | ✅ Current |
| **test-gitignore-fileworker** | Test File Worker .gitignore | Python | 🔨 Development | - | ✅ Current |
| **test-gitignore-node** | Test Node .gitignore generation | Node.js | 🔨 Development | - | ✅ Current |
| **test-gitignore-wordpress** | Test WordPress .gitignore generation | Unknown | 🔨 Development | - | ✅ Current |
| **transcriber** | Internal API service providing audio transcription capabilities using Soniox and other provider b... | Unknown | 🔨 Development | - | ✅ Current |
| **triggered-content-orchestration** | Orchestrates content creation across Twitter, YouTube, Blog, Email, and LinkedIn platforms. Featu... | Unknown | 🔨 Development | - | ✅ Current |
| **ugc** | Production-grade web scraping system for extracting user-generated content from social media plat... | Unknown | 🔨 Development | - | ✅ Current |
| **web-scraper** | Python-based web scraper using Scrapy and Playwright to extract full content to JSONLines format ... | Unknown | 🔨 Development | - | ✅ Current |

### Shell Projects (11 projects)

| Project | Purpose | Stack | Status | URL | Scaffold Status |
|---------|---------|-------|--------|-----|------------------|
| **.factory** | No description available | Unknown | 🔨 Development | - | ❌ No scaffold |
| **Reference_Creator** | No description available | Unknown | 🔨 Development | - | ✅ Current |
| **apps** | No description available | Unknown | 🔨 Development | - | ✅ Current |
| **exam-coach** | No description available | Unknown | 🔨 Development | - | ✅ Current |
| **file-worker** | No description available | Python | 🔨 Development | - | ✅ Current |
| **gmailaccountcreator** | No description available | Unknown | 🔨 Development | - | ✅ Current |
| **google** | No description available | Unknown | 🔨 Development | - | ✅ Current |
| **marketing-argumant-generator** | No description available | Unknown | 🔨 Development | - | ✅ Current |
| **namecheap** | No description available | Unknown | 🔨 Development | - | ✅ Current |
| **supplement-tracker-advisor** | No description available | Unknown | 🔨 Development | - | ✅ Current |
| **web_scraper** | No description available | Unknown | 🔨 Development | - | ✅ Current |

<!-- AUTO-GENERATED:PROJECTS:END -->
