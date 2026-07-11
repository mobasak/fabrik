# Fabrik Business Model

**Last Updated:** 2026-07-08

Fabrik's monetization strategy and revenue opportunities.

## Overview

Fabrik is an **internal platform** enabling rapid deployment of revenue-generating products.

**Primary value:** Reduce deployment friction from hours → minutes, enabling more experiments and faster iteration.

## Revenue Streams

**See Project Portfolio below for complete catalog of revenue-generating projects.**

### Active Production Services
- **site-provisioner** is currently the only live Fabrik microservice (`provision.vps1.ocoron.com`); earlier API services (captcha, translator, file-api, etc.) were retired
- **Projects in active development** across the portfolio (see catalog below)
- Multi-tenant SaaS, API services, B2B tools

### Revenue Models
- **SaaS subscriptions** (YouTube pipeline)
- **API usage fees** (illustrative — earlier captcha/translation/file-storage APIs are retired)
- **B2B services** (Proposal generation)
- **Internal tools** (Site provisioner)

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
| Fabrik CLI (SSH + Docker Compose) | Free (self-hosted) | Deployment |

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

The /opt project inventory moved to [`docs/PROJECT_CATALOG.md`](PROJECT_CATALOG.md) (2026-07-11) — it was mis-named here and was overwriting every project's own monetization `BUSINESS_MODEL.md` via the sync. This file is now fabrik's own monetization only.
