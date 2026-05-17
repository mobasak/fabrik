# WordPress Factory — Vision

## What We're Building

A website factory. You have an idea → answer 5-10 questions → a fully secured, monitored, SEO-optimized, bilingual (en+tr), content-producing WordPress site is live in seconds. An AI agent manages it forever — plans content, adjusts SEO, fixes issues, reports results. You manage a portfolio of 10+ sites with the same effort as zero.

## The End-to-End Flow

```
IDEA (you)
  ↓
GUI WIZARD (5-10 questions: preset, domain, brand, services)
  ↓
GOLDEN BASE clones + customizes (< 60 seconds)
  ↓
SITE IS LIVE with:
  • 10-layer security (WAF, hardening, 2FA, rate limiting, footprint removal)
  • 4-layer caching (Cloudflare + Nginx + Redis + WP transients)
  • Full analytics (GA4, GTM, GSC, Bing, IndexNow, Schema markup, OG)
  • Monitoring (Gatus uptime, GlitchTip errors, Grafana, Backrest→B2 backup)
  • Search engine registration (Google, Bing, Yandex, Seznam, Naver)
  • Bilingual content (en + tr, Polylang, locale-aware dates/numbers)
  • Professional pages (from preset: services, pricing, contact, legal, blog)
  • SEO optimized (RankMath, sitemap, breadcrumbs, robots.txt, JSON-LD)
  ↓
CONTENT PIPELINE (runs daily, forever):
  SEO service researches keywords → generates briefs
  TCO service writes articles (AI)
  Image Broker selects hero images
  WordPress publishes (REST API)
  Sitemap resubmits to all engines
  Telegram notifies you
  ↓
WATCHDOG AI (runs daily/weekly/monthly):
  Monitors GSC rankings → adjusts strategy
  Plans next week's content → triggers pipeline
  Fixes issues (broken links, 404s, slow pages)
  Updates plugins (test in staging first)
  Monthly: competitor analysis, full audit
  Reports via Telegram
  Escalates to you ONLY for decisions
```

## The Three Pillars

### 1. Golden Base (build once, deploy many)

One baked Docker image. Everything that's IDENTICAL across all sites is pre-installed, pre-configured, pre-tested:

**WordPress core:** `php8.3-fpm-bookworm` + Nginx (hardened) + MariaDB 10.11

**Security (10 layers, all baked in):**
- wp-config: DISALLOW_FILE_EDIT/MODS, FORCE_SSL, WP_HTTP_BLOCK_EXTERNAL, custom table prefix, DISABLE_WP_CRON
- Cloudflare WAF: 5 rules (bot skip, login challenge, xmlrpc block, wp-admin challenge, VPN ASN challenge)
- Nginx: security headers, xmlrpc blocked, /uploads/ PHP blocked, FastCGI cache
- REST API: /users enumeration blocked, anon non-GET blocked
- Rate limiting: 10 req/min/IP on wp-login.php
- Wordfence: brute-force (5 attempts), 2FA mandatory, file integrity, malware scan
- MU-plugins: footprint removal (generator, RSD, emoji, version strings)
- Admin: no "admin" username, 32-char CSPRNG password
- Upload: PHP execution blocked in /uploads/
- Outbound: WP_HTTP_BLOCK_EXTERNAL (only api.wordpress.org allowed)

**Plugins (25+ pre-installed):** GeneratePress Premium, RankMath Pro, FlyingPress, WP Mail SMTP Pro, WP Staging Pro, Redis Object Cache, Wordfence, Complianz Pro, AutomatorWP + integrations, Cloudflare Turnstile

**Caching (4-layer, pre-configured):** Cloudflare edge + Nginx FastCGI + Redis Object + WP transients. WooCommerce bypass rules. GDPR consent awareness.

**SEO base:** RankMath modules (sitemap, instant-indexing, rich-snippet, image-seo, redirections). Sitemap 200 links/page. AI crawler allow rules in robots.txt.

**New site = golden base + per-site variables:**
- Domain, SSL, Traefik labels
- Brand (name, colors, logo, fonts, tagline)
- Pages + content (from preset entities)
- Contact info, forms
- GA4/GTM IDs
- Language locales
- Per-preset plugin additions (WooCommerce for ecommerce, FluentCRM for company)

### 2. GUI Wizard + Dashboard

**Creation wizard** — 6 screens:
1. Pick preset (company / saas / content / landing / ecommerce)
2. Domain (check availability, buy if needed)
3. Brand (manual or AI-generated via brand-identity-creator)
4. Content (services/features/products per preset, bilingual en+tr)
5. Integrations (GA4, GTM, email, social)
6. Review + Deploy (manual sign-off → golden base clones → live)

**Operations dashboard** — all sites at a glance:
- Health (Gatus green/red per site)
- Content stats (articles published this week/month, pending briefs)
- SEO rankings (top keywords, position changes from GSC)
- Actions (publish now, flush cache, verify, redeploy)
- Watchdog AI status per site (last action, next planned, issues)

### 3. Watchdog AI (autonomous site admin)

Per-site AI agent on VPS. Three cycles:

**Daily:** Health check → publish 2 articles → fix broken links → resubmit sitemap → Telegram report

**Weekly:** Analyze GSC data → identify keyword gaps → create new SEO jobs → adjust internal linking → plan next week's content → Telegram summary

**Monthly:** Full SEO audit → competitor analysis (via web-scraper) → plugin updates (stage → test → apply) → DB maintenance → content performance review → strategy adjustment → Telegram report

**Escalates to you only when:** new keyword domain decision, budget increase needed, major traffic drop, GSC manual action, plugin major version update risk.

## Service Architecture (How They Connect)

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOU (Browser)                             │
│                             ↓                                   │
│              fabrik-control-panel (GUI)                          │
│                             ↓                                   │
│                   fabrik-api (VPS host)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────── CREATION FLOW ───────────────────────────────────┐
│ site-provisioner → domain buy + DNS + Cloudflare + GSC + Bing   │
│ brand-identity-creator → colors, fonts, tagline (AI)            │
│ fabrik scaffold → site.yaml from preset                         │
│ fabrik wp apply → 13 stages against golden base                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────── CONTENT FLOW (daily, automated) ─────��───────────┐
│ seo service → keyword research → content briefs                  │
│ triggered-content-orchestration → AI writes article              │
│ image-broker → Pexels/Pixabay hero image                         │
│ translator → en→tr (if bilingual)                                │
│ wordpress REST API → publish post + featured image               │
│ site-provisioner → resubmit sitemap                              │
│ notifications → Telegram (via n8n/Apprise)                       │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────── WATCHDOG FLOW (daily/weekly/monthly) ─────────────┐
│ GSC API → ranking data                                            │
│ web-scraper → competitor content                                  │
│ job-agent → AI decision engine                                    │
│ seo service → new keyword jobs based on gaps                      │
│ content flow → triggered by watchdog decisions                    │
��� wordpress REST API → content updates, internal linking            │
│ wordpress WP-CLI → plugin updates, DB maintenance                 │
│ notifications → Telegram reports                                  │
└───────────────────────────────────────────────────────────────────┘
```

## Existing Services (Production + Development)

| Service | Role in factory | Status | Port |
|---|---|---|---|
| **fabrik** | Orchestrator: scaffold, plan, apply, verify, content | ✅ Production | — |
| **site-provisioner** | Domain buy → DNS → Cloudflare → GSC → Bing → IndexNow | ✅ Production | 18014 |
| **image-broker** | Stock photo search + download (Pexels/Pixabay) | ✅ Production | 18016 |
| **translator** | DeepL + Azure translation (en↔tr) | ✅ Production | 18012 |
| **emailgateway** | Transactional email (Resend + SES) | ✅ Production | 18017 |
| **file-api** | File upload to Cloudflare R2 (media offloading) | ✅ Production | 18015 |
| **youtube** | Video transcript mining → content research source | ✅ Production | 8029 |
| **captcha** | Captcha solving for automated ops | ✅ Production | 18011 |
| **proxy** | Proxy rotation for scraping | ✅ Production | 18013 |
| **seo** | Keyword research → brief generation → ranking tracking | 🔨 Development | 8016 |
| **triggered-content-orchestration** | AI content generation from SEO briefs | 🔨 Development | 8025 |
| **brand-identity-creator** | AI brand generation (colors, fonts, tagline) | 🔨 Development | — |
| **marketing-argument-generator** | Marketing copy for page sections | 🔨 Development | — |
| **job-agent** | AI agent orchestration (watchdog execution engine) | 🔨 Development | — |
| **calendar-orchestration-engine** | 15,000+ global events/holidays database — proactive content timing | 🔨 Development | 3001 |
| **web-scraper** | Competitor content scraping for SEO gaps | 🔨 Development | — |
| **proposal-creator** | B2B proposals → service page content for company preset | 🔨 Development | — |
| **image-generation** | AI product photography (premium tier imagery) | 🔨 Development | — |

## Theme + Plugin Architecture

**Canonical source:** `docs/reference/wordpress/plugin-stack.md` (556 lines, curated from 7,079 plugins). All 125 premium zips at `templates/wordpress/plugins/premium/`. License keys + activation workarounds at `templates/wordpress/plugins/premium/wp_plugins_activation_notes.md`.

### Theme: GeneratePress + GP Premium

Every site. Lightweight, block-based, full Customizer control, hooks for code injection. No heavy page builders (Elementor/Divi/WPBakery BANNED per `62-wordpress.md`). Theme is in the golden base — per-site only applies brand colors + fonts.

### Plugin Architecture: BASE + PROFILE + OPTIONAL

**BASE (golden image, every site):**

| Plugin | Purpose | Status |
|---|---|---|
| GeneratePress + GP Premium | Theme + full customization | ✅ PLACED |
| RankMath Pro | SEO: schema, TOC, redirects, 404 monitor, instant indexing (IndexNow), sitemap | ✅ PLACED |
| FlyingPress | Performance: page cache, CSS/JS optimization (works with Cloudflare APO) | ✅ PLACED |
| WP Mail SMTP Pro | Email delivery via Resend/SES, delivery logging, failure alerts | ✅ PLACED |
| WP Staging Pro | One-click staging, backup, migration | ✅ PLACED |
| Redis Object Cache | Object caching (connected to redis-main, per-site prefix) | 🆓 FREE |
| Complianz Pro | GDPR/CCPA, cookie consent, geo-targeted banners | ✅ PLACED |
| Cloudflare Turnstile | Spam protection on forms (free, 20 widgets/account) | 🆓 FREE |

Security is OUTSIDE WordPress (10 layers — Cloudflare WAF at edge, Nginx hardening at origin, MU-plugins for REST/footprint). Wordfence is OPTIONAL (high-risk sites only, not in base).

**PROFILES (8 profiles, one per site — adds to BASE):**

| Profile | For | Plugin count | Key additions (beyond BASE) |
|---|---|---|---|
| **Company** | Service business, agency, consultancy | 23 plugins | Fluent Forms Pro, FluentCRM Pro, Thrive Leads + Architect + Ovation + Headline Optimizer + Clever Widgets, AutomatorWP + FluentCRM integration, Link Whisper Pro, SearchWP + WPML + Metrics, Essential Grid, Novashare, WP Table Builder Pro, PixelYourSite Pro + Social Connect, Chaty Pro |
| **SaaS** | Product landing, conversion-focused | 24 plugins | Same as Company + Thrive Ultimatum (scarcity/countdown), Go Pricing (pricing tables), Thrive Quiz Builder |
| **Content** | Blog, magazine, affiliate | 25 plugins | Same core CRM/forms + Thrive Comments (engagement), Content Egg Pro (affiliate content), Thrive Quiz Builder, WP Table Builder Pro (comparison tables) |
| **Landing** | Single-page conversion | 18 plugins | Thrive Architect + Ultimatum + Quiz Builder, SeedProd (maintenance/coming-soon), PixelYourSite Pro, Chaty Pro — minimal, conversion-focused |
| **Ecommerce** | WooCommerce physical products | 24+ plugins | WooCommerce core, AutomateWoo (cart recovery, follow-ups — replaces AutomatorWP for WC), WooCommerce Subscriptions, Table Rate Shipping, SearchWP WooCommerce, GTM4WP, WhatsApp Chat/Notifications, Photo Reviews |
| **Digital Products** | Easy Digital Downloads (EDD) | 20+ plugins | EDD Pro + PayPal Commerce + Multi-Currency + Content Restriction + Amazon S3 + Variable Pricing Switcher + Reviews + Free Downloads + Recommended Products + Fraud Monitor |
| **Membership** | MemberPress courses/subscriptions | 20+ plugins | MemberPress Basic + Courses + Downloads + Developer Tools (REST API) + Social Login + Order Bumps + PDF Invoice + Gifting. Course add-ons: Quizzes, Gradebook, Assignments |
| **Appointments** | Bookly scheduling/service businesses | 20+ plugins | Bookly PRO + Advanced Google Calendar + Stripe + PayPal + Customer Cabinet + Staff Cabinet + Recurring + Deposit Payments + Waiting List + Cart + Custom Fields + Invoices + Locations |

Each profile has: Essential (always install), High Value (likely need), Situational (only if needed) tiers. Full breakdown per profile in `plugin-stack.md`.

**OPTIONAL (per-site activation, not in any profile by default):**

| Plugin | When to activate |
|---|---|
| Wordfence Premium | WooCommerce, membership, login-heavy, many editors, high traffic |
| Asset CleanUp Pro | Heavy bloat sites, WITH QA time (can break things) |
| AutomatorWP + integrations (WhatsApp, OpenAI, ACF, CSV, Webhooks, Google Sheets) | Cross-plugin automation beyond Thrive ecosystem |
| FS Poster | Automated social media posting workflow |
| AffiliateWP + Multi-Tier Commissions + Portal | Full affiliate program (SaaS/ecommerce) |
| Redis Object Cache Pro | Performance upgrade for high-traffic sites |

**AutomatorWP decision rule:** Install when (1) need automation BEYOND Thrive ecosystem, OR (2) need webhooks to external systems, OR (3) have repeatable workflows across containers. If installed: keep Thrive Automator minimal (one automation owner per site).

### Multilingual

WPML CMS + String Translation bundled in ALL profiles. Every site is bilingual (en + tr) by default.

**Decision pending (BLOCKER for golden base):** Rule pack `62-wordpress.md` mandates Polylang. All profiles currently bundle WPML. Plugin stack uses WPML. Must resolve before golden base build. Impact: golden base bakes one or the other — switching later means rebuilding the image + migrating all existing sites.

## Site Presets (7 profiles mapped to 5 presets)

| Preset | Profile | Auto-generates | Key entities |
|---|---|---|---|
| `company` | Company | Home, About, Services/*, Contact, Blog, Legal | services, team, locations |
| `saas` | SaaS | Home, Features, Pricing, About, Contact, Blog, Legal | features, pricing_plans, testimonials |
| `content` | Content | Home, Blog, Category/*, Author/*, About, Legal | categories, authors |
| `landing` | Landing | Home (full-width all sections), Legal | — |
| `ecommerce` | Ecommerce OR Digital Products OR Membership | Home, Shop/Downloads, Cart, Checkout, Account, About, Legal | products, product_categories |

Each preset defines: page templates with section types, entities that auto-generate pages, profile plugins, menu structure, SEO defaults, content strategy. The `ecommerce` preset has sub-variants (WooCommerce vs EDD vs MemberPress) selected via `site.yaml` field.

## What's Built vs What's New

| Component | Status | LoC |
|---|---|---|
| WordPress engine (13-stage deploy pipeline) | ✅ Built | 9,700 |
| 5 presets + spec system (3-layer merge) | ✅ Built | — |
| 10-layer security (automated via templates) | ✅ Built | — |
| 4-layer caching (atomic flush) | ✅ Built | — |
| Monitoring (Gatus + GlitchTip + Grafana + Backrest) | ✅ Built | — |
| Content pipeline (SEO→TCO→Image→WP→publish) | ✅ Built | — |
| Domain provisioning + search engine registration | ✅ Built | — |
| Analytics injection (GA4/GTM/Schema/OG) | ✅ Built | — |
| 125 premium plugins bundled + licensed | ✅ Built | — |
| Bilingual support (Polylang, locale-aware formatting) | ✅ Built | — |
| 8 Makefile ops (update, cache-flush, backup, harden, etc.) | ✅ Built | — |
| **Golden base Docker image** | 🆕 To build | — |
| **GUI wizard + operations dashboard** | 🆕 To build | — |
| **Watchdog AI (autonomous site admin)** | 🆕 To build | — |
| **fabrik-api (HTTP bridge for GUI + remote control)** | 🆕 To build | — |
| **`FABRIK_EXEC_MODE=local` (VPS-native execution)** | 🆕 To build (1-line) | — |

## Architectural Rules (from `.windsurf/rules/62-wordpress.md`)

These rules ARE the golden base specification:
- MariaDB 10.6+ (PostgreSQL banned)
- `wordpress:php8.x-fpm-bookworm` (Apache banned, `:latest` banned)
- Only `wp-content` volume mounted (not full webroot)
- Nginx FastCGI cache mandatory (PHP caching plugins banned)
- Redis per-site isolation (`WP_REDIS_PREFIX` + `WP_REDIS_DATABASE`)
- All secrets via env vars (never wp-config hardcoded)
- Custom table prefix (never `wp_`)
- `DISALLOW_FILE_EDIT`, `DISALLOW_FILE_MODS`, `FORCE_SSL_ADMIN`, `DISABLE_WP_CRON`
- Cloudflare WAF 5-rule mandatory set
- WooCommerce: FastCGI cache bypass for cart/checkout/my-account
- GDPR: cache bypass for visitors without consent cookie
- Email: via emailgateway REST API or WP Mail SMTP Pro (PHP mail() banned)
- Backups: Backrest to B2 (PHP backup plugins banned)

## Scaling & SaaS Readiness

**Strategy:** Internal-first, SaaS-ready architecture. Build for yourself (10+ sites on your VPS), but every data model and decision supports multi-tenant SaaS later without rewriting.

### Multi-VPS (needed at ~10-15 sites per VPS)

| Component | What | When |
|---|---|---|
| VPS registry | `data/vps-pool.yaml` — capacity tracking (RAM, CPU, site count per VPS) | When VPS1 hits 80% RAM |
| Site-to-VPS routing | Deploy command picks VPS with capacity. `fabrik apply --vps vps2` | Same time |
| Cross-VPS monitoring | Single Grafana/Gatus dashboard across all VPS nodes | Same time |
| Portability | `fabrik export/import` already built — moves site between VPS | ✅ Built |

### SaaS-Ready Architecture (build internal, flip switch later)

| Principle | Implementation |
|---|---|
| Tenant-aware from day 1 | `owner_id` field on every site record (always "you" initially) |
| Per-site isolation | Already done (own MariaDB, own volumes, own compose stack) |
| Billing hooks | Paddle/Stripe subscription → site quota. Not built now, but data model supports it. |
| Customer GUI | Same dashboard you use, but with login + per-user site filtering. Authelia → customer auth layer. |
| Per-customer content pipeline | Already per-site. SEO keywords are per-domain. No shared state. |
| Per-customer watchdog | Already per-site. Notification routing (your Telegram vs customer email). |
| White-label | Remove "Fabrik" branding from dashboard. Customer sees their brand. |

### What This Means for Architecture NOW

- Site registry (`data/projects.yaml` or DB) gets `owner_id` field
- fabrik-api endpoints accept `owner` context (defaults to you)
- GUI dashboard has a user model (even if single-user initially)
- VPS is a parameter, not hardcoded (`VPS_HOST` env, not `172.93.160.197` literal)
- Compose templates don't hardcode VPS1 domain — use `site.domain` from spec

**NOT building now:** billing, multi-user auth, customer onboarding, VPS auto-provisioning. These are Phase 6+ (after the factory works for you personally).

---

## Success Criteria

| Metric | Target | How measured |
|---|---|---|
| Idea → live site | < 60 seconds (golden base exists) | Timer from "Deploy" click to homepage 200 |
| Manual WP-admin interaction | Zero. Ever. | Watchdog handles everything |
| Content output | 2+ articles/day/site automatically | Content publisher logs |
| Site portfolio | 10+ sites, same effort as 0 | Watchdog manages all |
| Uptime | >99.9% per site | Gatus |
| Security incidents | 0 (proactive, not reactive) | Wordfence + WAF + hardening |
| SEO rankings | Top 10 for primary keywords within 3 months | GSC weekly reports |
| Revenue | Site portfolio revenue > 10x infrastructure cost | Monthly accounting |
| Human time per site/month | < 30 minutes (review Telegram reports only) | Time tracking |

## Reference Files

| What | Where |
|---|---|
| WordPress rule pack (golden base spec) | `.windsurf/rules/62-wordpress.md` |
| Complete file index (80+ files) | `docs/development/wordpress-files-index.md` |
| Plugin stack documentation | `docs/reference/wordpress/plugin-stack.md` |
| Architecture | `docs/reference/wordpress/architecture.md` |
| Preset definitions | `templates/wordpress/presets/*.yaml` |
| Schema | `templates/wordpress/schema/v1.yaml` |
| Plugin activation notes + license keys | `templates/wordpress/plugins/premium/wp_plugins_activation_notes.md` |
| Code classification (use/modify/archive) | `docs/development/plans/wordpress/05-code-classification.md` |
| Execution order (5 phases) | `docs/development/plans/wordpress/04-execution-order.md` |
