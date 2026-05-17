# GUI Wizard + Site Dashboard

## What

A web interface for creating and managing WordPress sites. Two modes:
1. **Creation Wizard** — step-by-step questionnaire → site.yaml generated → golden base deploys
2. **Operations Dashboard** — all sites at a glance: health, content stats, rankings, actions

## Why

CLI works for one site. A portfolio of 10+ sites needs visual management. Also: filling YAML by hand is error-prone and slow. A wizard with validation + preview is faster and safer.

## Architecture

```
Browser → fabrik-control-panel (Next.js, Coolify container, port 3004)
              ↓
         fabrik-api (FastAPI, VPS host process, port 8050, localhost only)
              ↓
         fabrik CLI (wp plan, wp apply, seo, content, domain)
              ↓
         Docker containers (WordPress sites)
```

**Key decisions (from archived control-plane plan):**
- fabrik-api runs as native VPS host process (NOT containerized) — needs direct `docker exec`
- `FABRIK_EXEC_MODE=local` — no SSH hop
- fabrik-api binds `127.0.0.1:8050` only — never internet-exposed
- Bearer token authentication (`FABRIK_API_TOKEN`)
- Next.js reaches host via `host.docker.internal:host-gateway`
- SSE streaming for live stage progress

## Creation Wizard Flow

### Screen 1: Choose Preset
- 6 cards: Company, SaaS, Content, Landing, E-commerce, Appointments
- Each shows: what entities it creates, sample pages, example sites
- E-commerce has sub-variant selector (WooCommerce / EDD / MemberPress)
- User clicks one → next screen

### Screen 2: Domain
- Input: domain name
- Auto-check availability via `fabrik domain check` (real-time)
- If available: show price, "Will register on deploy"
- If owned: "Already yours, will provision DNS"
- If taken: suggest alternatives

### Screen 3: Brand Identity
- Option A: Manual — fill name, tagline, primary/secondary/accent colors, upload logo
- Option B: AI Generate — describe your business in 2 sentences → brand-identity-creator generates colors, font pairing, tagline options → user picks/tweaks
- Live preview: a mock homepage with brand applied

### Screen 4: Content (preset-specific)
- **Company preset:** list your services (name + 1-line description each). Team members (optional). Locations (optional).
- **SaaS preset:** list features, pricing tiers, testimonials
- **Content preset:** categories, writing topics, tone
- **Landing preset:** headline, subheadline, CTA, key benefits
- **E-commerce preset:** product categories, currency, shipping zones

All bilingual: English field + Turkish field side by side.

### Screen 5: Integrations
- GA4 Measurement ID (or "Create for me" → site-provisioner creates GA4 property)
- GTM Container ID (optional)
- Contact email
- Social links
- "Register with Google Search Console?" checkbox (default: yes)
- "Register with Bing?" checkbox (default: yes)

### Screen 6: Review + Deploy
- Summary of everything
- Estimated deploy time
- **"Deploy" button** — manual sign-off (irreversible ops: domain purchase, DNS)
- After click: SSE stream shows stage progress in real-time
- Completion: link to live site + wp-admin credentials

## Operations Dashboard

### All Sites View
```
┌──────────────────────────────────────────────────────┐
│ 🏢 ocoron.com    ✅ Healthy    📝 47 articles   📈 ↑12%  │
│ 🛍️ myshop.com    ✅ Healthy    📝 23 articles   📈 ↑8%   │
│ 📝 myblog.com    ⚠️ SSL expiry 📝 156 articles  📉 ↓3%   │
│ 🎯 landing.com   ✅ Healthy    📝 1 page        📈 ↑45%  │
│                                                      │
│ [+ New Site]                                         │
└──────────────────────────────────────────────────────┘
```

### Per-Site View
- Health: Gatus status, last check, uptime %
- Content: articles published (this week/month/total), pending briefs, content schedule
- SEO: top 10 keywords + positions (from GSC), impressions, clicks
- Analytics: traffic (from GA4), top pages, bounce rate
- Actions: "Publish content now", "Run SEO job", "Flush cache", "Verify", "Redeploy"
- Watchdog AI status: last action, next planned action, issues detected

## API Endpoints (fabrik-api)

| Endpoint | Method | What |
|---|---|---|
| `/health` | GET | API health check |
| `/api/v1/sites` | GET | List all sites with health/content stats |
| `/api/v1/sites` | POST | Create new site (accepts site.yaml JSON) |
| `/api/v1/sites/{id}/deploy` | POST | Trigger deploy (plan + apply) |
| `/api/v1/sites/{id}/stream/{task}` | GET (SSE) | Live stage progress |
| `/api/v1/sites/{id}/status` | GET | Health + stats |
| `/api/v1/sites/{id}/content/publish` | POST | Trigger content publish |
| `/api/v1/sites/{id}/seo/jobs` | POST | Create SEO keyword job |
| `/api/v1/sites/{id}/cache/flush` | POST | 4-layer cache flush |
| `/api/v1/sites/{id}/verify` | POST | Run verification checks |
| `/api/v1/brand/generate` | POST | AI brand generation (brand-identity-creator) |
| `/api/v1/domain/check` | GET | Domain availability |
| `/api/v1/domain/buy` | POST | Register domain (Namecheap) |
| `/api/v1/domain/provision` | POST | DNS + Cloudflare + GSC + Bing |

## Existing Code to Reuse

| What | Exists at | Reuse how |
|---|---|---|
| Brand generation | `/opt/brand-identity-creator/` | Call via internal API from wizard Screen 3 |
| Domain check/buy/provision | `src/fabrik/drivers/dns.py` | Wrap in fabrik-api endpoint |
| Site deploy | `src/fabrik/deploy_router.py` | Spawn as background task, SSE stream |
| Content publish | `src/fabrik/orchestrator/content_publisher.py` | Wrap in endpoint |
| SEO jobs | `src/fabrik/drivers/seo.py` | Wrap in endpoint |
| Cache flush | `src/fabrik/wordpress/cache.py` | Wrap in endpoint |
| Site health | `src/fabrik/wordpress/stages/verify.py` | Wrap in endpoint |
| Spec generation | `src/fabrik/wordpress/spec_loader.py` | JSON → site.yaml writer in fabrik-api |
| Marketing copy | `/opt/marketing-argument-generator/` | Optional: auto-generate page copy |

## Files to Create

| File | What |
|---|---|
| `/opt/fabrik-api/` | New project (FastAPI, fabrik scaffold --type python-api) |
| `/opt/fabrik-control-panel/` | New project (Next.js, fabrik scaffold --type saas-skeleton) |
| `specs/services/fabrik-api.yaml` | Service spec (port 8050, localhost-only) |
| `specs/services/fabrik-control-panel.yaml` | Service spec (port 3004, Coolify) |

## Dependencies

- Golden base must be built first (Screen 6 deploys against it)
- `FABRIK_EXEC_MODE=local` must work
- brand-identity-creator must be deployed
- All existing services (site-provisioner, SEO, TCO, image-broker) running on VPS
