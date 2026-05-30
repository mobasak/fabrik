<!-- Companion to 00-trigger-workflow-command.md. NOT pasted into Traycer at runtime.
     Read once to learn the expected Vision Summary shape, or paste alongside 00 when
     you want a demonstrative anchor during a session. -->

# 00 — Worked Examples

Two illustrative Vision Summaries showing the exact output shape produced by `00-trigger-workflow-command.md`. The template skeletons inside Step N4 (NEW mode) and Step E5 (EXISTING mode) of that command are authoritative — these examples just show them filled in.

## Concrete Example — NEW mode (illustrative)

**Hypothetical vision intake for a "WordPress Factory" product:**

```markdown
# Vision Summary: WordPress Factory (WPF)

## Product Vision
A platform that automates WordPress site creation, management, and scaling.
Provisions new WP sites with pre-configured themes, plugins, SSL, and
monitoring in under 5 minutes via API. For digital agencies managing
50-200 client WordPress sites.

## Personas
- **Agency Admin** — manages all client sites, creates new sites, monitors health
- **Client** — views their site status, requests changes via portal
- **Developer** — customizes themes/plugins, deploys via git push

## Value Streams
- SaaS subscription per managed site ($15-50/month per site)
- Premium theme marketplace (20% commission)
- Managed hosting margin (VPS cost vs client billing)

## Full Feature Inventory
1. Site provisioning engine — create WP site with domain, SSL, DB in <5min
2. Theme management — install, customize, version themes per site
3. Plugin marketplace — curated plugins with one-click install
4. Client portal — per-client dashboard showing site health, analytics
5. Bulk operations — update WP core/plugins across all sites simultaneously
6. Backup management — per-site backup schedules via Backrest
7. Monitoring dashboard — uptime, performance, error rates per site
8. Billing integration — Paddle subscriptions tied to site count
9. API — programmatic site management for agency automation
10. Multi-user auth — agency teams with role-based access

## Backing Services (from VPS)
- postgres-main:5432 — WPF application database (NOT individual WP site DBs)
- redis-main:6379 — session cache, job queue
- MeiliSearch — site/theme/plugin search
- Apprise — notifications (site down, backup failed, billing events)
- Backrest → B2 — WPF application backups
- Gotenberg — PDF invoice generation

## External Services
- Cloudflare — DNS automation per site (via site-provisioner, already deployed)
- Paddle — subscription billing (paid, ~3% transaction fee)
- Backblaze B2 — per-site media storage (paid, ~$5/TB/month)

## Technology Decisions
- **Auth:** Supabase Auth for agency users (managed, set-and-forget) + Authelia for admin dashboard (already deployed)
- **Database:** postgres-main for WPF application data. Individual WP sites get their own DB containers (not postgres-main).
- **Search:** MeiliSearch (already deployed) for site/theme/plugin search
- **Billing:** Paddle — subscription per managed site. Paddle handles tax/invoicing.
- **File storage:** Backblaze B2 for per-site media. WPF app assets in Docker volume.
- **Notifications:** Apprise (already deployed) for site-down, backup-failed, billing alerts
- **Consumed microservices:** site-provisioner for DNS/domain automation per client site
- **Domain structure:** api.wpf.ocoron.com (API), app.wpf.ocoron.com (client portal), admin.wpf.ocoron.com (admin)
- **Scaffold types:** python-api (backend) + saas-skeleton (client portal) — 2 scaffold types → strong multi-epic signal

## Constraints
- x86_64: all clear
- Budget: Paddle + B2 are paid dependencies (~$20/month base + per-site)
- Existing services: site-provisioner handles DNS/domain — consume, don't rebuild
- Duplicate check: all clear (no WP factory exists)
- Port conflicts: all clear (will need port 8020 — available)
- SSH + Docker Compose deployment: all clear (python-api + separate WP containers per site)
- No Alpine: all clear
- 12-Factor: all clear (stateless API, config via env)
- Solo dev capacity: LARGE project — multiple large features
- Observability: all clear (python-api scaffold emits /health + /metrics)

## Out of Scope (Vision Level)
- Custom WP plugin development (agencies bring their own)
- Email hosting (use external: Google Workspace, etc.)
- Site migration from other hosts (manual process)
- White-label branding of the portal

## Open Questions
- Will individual WP sites run as separate Docker containers or shared hosting?
- What's the target for simultaneous site count on VPS1? (resource planning)
- Should the client portal be a separate saas-skeleton project or part of the API?

## Scale Assessment
- Feature count: 10 (3 small, 4 medium, 3 large)
- Classification: multi-epic (~4 epics)
- Reasoning: 3 large features + 4 medium features + multiple scaffold types → too broad for a single epic-to-ticket-workflow run.
- Next step: Proceed to `02-epic-decomposition-command` to define epic boundaries.
```

## Concrete Example — EXISTING mode (illustrative)

**Hypothetical continuation: "youtube" SaaS adding a RAG-search capability.**

```markdown
# Vision Summary: youtube — Adding RAG-Search Over Comment Archive

## Product Vision
youtube is a deployed SaaS that ingests YouTube channel comments and surfaces
viewer-sentiment trends for B2C brands. We're ADDING natural-language search +
AI Q&A over the comment archive so brand managers can ask "what do viewers say
about retinol?" instead of filtering by tags.

## Personas
- **Brand Manager** — existing persona; new capability they use directly
- **Analyst** — NEW persona; uses the Q&A interface for ad-hoc deep dives

## Value Streams
- Higher seat utilization (analysts now justify additional seats)
- Pricing-tier lift (RAG-search is a Pro-tier feature)

## Full Feature Inventory
1. Embedding pipeline for comment archive — large
2. Hybrid retriever (pgvector + tsvector + RRF) — medium
3. AI Q&A endpoint — medium
4. Search UI in client portal — small
R1. Retrofit: add i18n (en + tr) to client portal — medium
R2. Retrofit: add Resilience layer to YouTube Data API calls — medium

## Backing Services (from VPS)
- postgres-main:5432 — existing comment archive + pgvector for embeddings
- redis-main:6379 — existing cache; will store retriever results

## External Services
- OpenRouter — for embedding model (Voyage embedding-3) and the Q&A LLM

## Technology Decisions

**Inherited (locked — do NOT re-decide):**
- Auth: Supabase Auth (Pattern B) — locked because tokens issued, users paying
- Database: postgres-main (multi-tenant w/ tenant_id) — locked, data exists
- Frontend: Next.js + Tailwind + Shadcn — locked, deployed
- Billing: Paddle — locked, subscriptions active

**New decisions (per current ruleset):**
- RAG pipeline: search + classification (Phase 2 per `domain-modules/rag.md`)
- Background processing: existing pg job queue for embedding batch jobs
- Domain structure: no new subdomains (search lives under existing app.youtube.vps1.ocoron.com)

## Locked Decisions
- Auth: Supabase Auth — locked because 1,800 active users
- Database: postgres-main — locked because 50M comments archived
- Shape block (current): needs_database=true, needs_cache=true, exposes_metrics=true, is_admin_dashboard=false, has_persistent_data=true
- Frontend: Next.js — locked, no React → Vue migration desired

## Compliance Report

| Gap | Source | Owner decision | Epic action |
|---|---|---|---|
| i18n missing (en only) | `core/i18n` rule pack | Fix-now | Retrofit epic R1 |
| Resilience layer absent on YouTube Data API | `core/58-resilience.md` | Fix-now | Retrofit epic R2 |
| psycopg2 used instead of asyncpg | `core/25-data-postgres.md` | Accept-as-legacy | No action |
| Shape drift: prometheus registrar inactive | `fabrik audit-registrars` | Fix-now (folded into R2) | Folded into R2 |
| FINANCIALS.md missing | `saas/88-saas-launch-checklist.md` | Fix-later | Deferred |

## Constraints
- x86_64: all clear
- Budget: OpenRouter ~$30/month estimated for 50M comments
- Port conflicts: all clear (no new ports)
- SSH + Docker Compose deployment: all clear (delta is in-place; same compose)
- 12-Factor: all clear for new code
- Vector DB ban: pgvector only — confirmed
- Email streams: N/A (no new email)

## Out of Scope
- Existing comment-ingestion pipeline — not being modified
- Existing comment-sentiment classifier — not being touched
- Tenant model — not being changed
- WordPress integration (not on roadmap)

## Open Questions
- None — owner confirmed scope, retrofits, and locked decisions.

## Scale Assessment
- New feature count: 4 (1 small, 2 medium, 1 large)
- Retrofit count: 2 (both medium)
- Classification: multi-epic (~3 epics)
- Reasoning: 1 large + 2 medium new features + 2 retrofits → too broad for a single epic-to-ticket-workflow run.
- Next step: Proceed to `02-epic-decomposition-command` to define epic boundaries. 02 will emit Retrofit epics R1 and R2 alongside the delta-feature epics.
```
