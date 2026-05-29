<!-- WordPress Domain Module — paste into Traycer workflow GUI.
     Part 1: paste with mega-epic-breakdown (00 + 02)
     Part 2: paste when starting my-workflow for a WordPress epic
     Auto-select when scaffold signal includes wordpress.
     Consumer: Traycer planning LLM (NOT coding agents).
     No dedicated WordPress rule pack exists — coding agents use
     general rule packs (core/30-ops, core/35-security-auth, core/85-payments-billing)
     plus decisions made in this module. -->

# WordPress Domain Module (18 dimensions, any type)

## Operating Lens (solo + AI fleet)

- **Build cost is cheap** — agents + WP do the heavy lifting. Your edge is content + niche depth, not code.
- **Your time is the scarce resource** — every default optimizes **set-and-forget ops**, never quality.
- **Pro-grade is non-negotiable** — green Core Web Vitals, hardened, auto-updated from launch.

## WordPress is not SaaS/mobile — the 4 forks

1. **"WordPress" = 5 products** — affiliate / content+ads / business-leadgen / landing-funnel / ecommerce. Dimension 1 is the type fork; **everything downstream branches on it.** Don't proceed without it.
2. **WP is not 12-Factor** — local media uploads + plugin state. To run safely on the VPS (SSH + Docker Compose): **media offload to Backblaze B2, dedicated per-site Redis object-cache container, dedicated MariaDB container**, persistent volume only as fallback. State this in the summary.
3. **Plugins/security = the maintenance bomb** — WP is the most-attacked CMS; plugin sprawl is the antithesis of low-maintenance. Set-and-forget demands ruthless minimalism + auto-update + Cloudflare WAF.
4. **Google-algorithm dependency is existential** for affiliate/content — the Apple-deplatform analogue. Diversify into an owned audience or one update can zero you.

## Completeness Test (apply per dimension)

A dimension belongs at intake **only if** wrong = **irreversible** or **kills before build**. Else it's downstream. Resolve each or log as Open Question. **No "TBD" survives confirmation.**

---

## Part 1 — Mega-Epic (paste with 00 + 02)

### 1A. Vision Intake Dimensions

#### 1. Site Type & Goal (the fork)

**Force:** affiliate / content+ads / business-leadgen / landing-funnel / ecommerce — and the single success metric (revenue/visitor, RPM, leads, conversion, AOV).

**Default:** pick ONE; hybrids dilute. Your edge favors **affiliate/content** (AI content + scraping + domain depth) or **ecommerce** (Rebul anchor).

**Why now:** type decides monetization, stack, channel, and metric — wrong type = wrong everything.

#### 2. Market & Niche Positioning

**Force:** named niche/ICP, search intent targeted, 3-5 named competitor sites, the angle that wins.

**Default:** narrow niche with topical authority potential; moat = depth + owned audience, not breadth.

**Why now:** for content/affiliate the niche *is* the business; for ecommerce it's the catalog focus.

#### 3. Geographic Market & Language

**Force:** TR vs international vs both; single vs multilingual (Polylang + AutoPoly/DeepL).

**Default:** one market/language first; en for affiliate-scale, tr for Rebul/local ecommerce.

**Why now:** multilingual + hreflang + DeepL config retrofits are painful; pick before content/URLs exist.

#### 4. WordPress Architecture & Hosting (Fabrik-fit irreversibles)

- **Hosting:** 4-container per-site stack on VPS via SSH + Docker Compose — **nginx + php-fpm (WordPress) + dedicated MariaDB + dedicated Redis** (object cache); **media offload to Backblaze B2**; backups via central Backrest; Cloudflare CDN+WAF in front.
- **Domains:** via Cloudflare Registrar + site-provisioner for DNS.
- **Backups:** Backrest to B2 (DB + uploads), staging clone for major changes.

**Why now:** media-offload + object-cache + DB choices are foundational; bolting them on after content exists risks data/URL churn.

#### 5. Theme, Builder & Brand Assets

**Force:** block theme (FSE) vs page builder; brand asset set.

**Default:** **lightweight block theme** (GeneratePress / Kadence / native FSE). Avoid Elementor/Divi — bloat, lock-in, CWV + maintenance cost.

**Brand assets:** logo + favicon, fonts + brand CSS via **Ocoron Design System**, shipped as a **mu-plugin** (fonts + SVG mime allow) so brand survives theme/plugin updates.

**Why now:** builder lock-in is near-irreversible; brand assets feed the provisioner's theme step.

#### 6. Information Architecture

**Force:** full **page inventory** (incl. nested children), **homepage + blog-page pointers**, **primary + footer menu** structure, URL/slug map.

**Default:** flat, shallow IA; cornerstone pages first; slugs locked early.

**Why now:** the provisioner renders pages/menus from this spec (steps 5-6); URL structure is expensive to change post-index (301 debt).

#### 7. Plugin Strategy & Security

**Force:** minimal curated plugin set (the manifest) + update policy + hardening.

**Default:** fewest plugins that ship the goal; auto-update minor, staging for major; Cloudflare WAF + reputable security plugin; zero abandoned plugins.

**Why now:** this *is* your low-maintenance constraint — sprawl turns the site into constant intervention + breach risk. The decision IS the provisioner's plugin manifest.

#### 8. Performance & Caching (pro-grade)

**Force:** page cache + object cache + CDN + image optimization + CWV target.

**Default:** full-page cache + redis object cache + Cloudflare + WebP/lazy-load, green Core Web Vitals.

**Why now:** CWV is a ranking factor and conversion driver; WP is slow by default and must be tuned at build.

#### 9. Monetization (incl. bidirectional affiliate)

**Force:** the revenue mechanism for the chosen type.

**Defaults:**

- **Affiliate — two directions, both decided here:**
  - *Publisher side (we earn):* networks (Amazon Associates + niche), managed/cloaked links, disclosure.
  - *Program side (we recruit affiliates to sell OUR products):* **AffiliateWP/SliceWP** — commission tiers, cookie window, attribution, recruitment/approval flow, payout (PayPal/bank), program terms, self-referral/fraud guards. **This is also a distribution channel, not just a cost.**
- **Content+ads** — display network (Ezoic to Mediavine at traffic thresholds) + sponsored.
- **Business** — forms to CRM (lead-gen; site is a sales asset).
- **Landing-funnel (digital)** — **Paddle** (MoR).
- **Ecommerce (WooCommerce)** — **iyzico/PayTR** for TR physical goods; tax, shipping, inventory, returns. **Ecommerce/landing types also:** paid social + retargeting (post-PMF); **marketplace presence** (Amazon, Trendyol, Google Shopping) — organic-only starves ecommerce of fast/intent buyers.
- **Conditional (plugin/theme products only):** WP.org plugin/theme repo + AI directories as distribution channels. Not applicable if the product is a site, not a plugin/theme.

**Why now:** monetization shapes the data model, plugins, and compliance — and the affiliate-program decision adds a whole channel + payout system.

#### 10. SEO Engine

**Force:** technical SEO + keyword/topic map + schema + internal-linking model.

**Default:** RankMath, clean permalinks, schema, sitemap, instant-indexing, topical clusters **+ GEO/AI-answer optimization** (mandatory; AI Overviews are eating content traffic — this is existential for affiliate/content types); content is the primary channel for all types except pure paid landing.

**Why now:** URL structure + site architecture are expensive to change once indexed (301 debt).

#### 11. Content & Editorial Engine

**Force:** production model + quality bar + cadence.

**Default:** **AI-assisted pipeline** (your edge: scraping + AI + domain depth, Longephedia pattern) with human editorial QC to clear Google's helpful-content bar. Avoid thin/spam at scale. **Video/YouTube repurposing** as a second traffic source + on-page embeds (written content to video; video embeds improve dwell time and diversify from Google-only).

**Why now:** content velocity + quality is the growth engine; an unsystematized content process caps the whole site.

#### 12. Email / Owned Audience

**Force:** ESP + capture strategy + newsletter cadence.

**Default:** build the list from day 1 — the **durable asset that insulates against Google-algo risk**; ESP with automation.

**Why now:** owned audience is the only traffic you control; retrofitting capture loses the early audience.

#### 13. Conversion & Analytics

**Force:** GA4 / GTM / FB-pixel IDs + Search Console + click/conversion tracking (+ A/B for landing/ecommerce).

**Default:** GA4 + GSC + affiliate-click/Woo-conversion events; privacy-compliant tagging.

**Why now:** untracked traffic can't be optimized; the IDs feed the provisioner's analytics step.

#### 14. Legal & Compliance

**Force:** affiliate disclosure, cookie consent (KVKK/GDPR), privacy policy; ecommerce: distance-selling terms, returns, KVKK; **affiliate-program: affiliate agreement/terms, payout tax handling, self-referral/fraud policy.**

**Default:** consent banner, disclosure on affiliate pages, generated legal pages reviewed; Woo legal flows for ecommerce; program T&Cs if running affiliates.

**Why now:** ad networks + affiliate programs + TR ecommerce law require these before they'll pay or before you can sell/recruit.

#### 15. Finance & Unit Economics

**Force:** the right metric by type — revenue/visitor & RPM (affiliate/ads), leads & close rate (business), AOV & margin & COGS (ecommerce), program ROI & blended commission (affiliate program).

**Default:** content cost is your time/AI (low cash, high leverage); know traffic-to-revenue conversion.

**Why now:** sets the traffic/sales target that defines "working."

#### 16. Risk Register

**Force:** top 5 + mitigation — **Google-algo dependency (existential, affiliate/content)**, ad-network/affiliate-program dependency, security breach, single-VPS, single-channel.

**Default:** diversify traffic (email + secondary channels); minimal attack surface; named owner-action per risk.

**Why now:** one core-update can erase a single-channel content site — design for it, not around it.

#### 17. Ops & Solo-Dev Load

**Force:** what's automated (updates, backups, security scans, caching, deploys, provisioning pipeline) vs needs you; content cadence sustainability.

**Default:** auto-update minor + Backrest backups + Cloudflare WAF + minimal plugins + golden-path provisioner = near-zero recurring ops; staging for risky changes.

**Why now:** WP without automation becomes constant maintenance — directly against your hour budget.

#### 18. Sequencing & Kill Criteria

**Force:** launch scope (cornerstone content / core catalog), traffic/revenue milestones, kill/pivot criteria **with a date** — **SEO-ramp-aware (6-12mo).**

**Default:** ship the core, publish on cadence, judge at the right horizon — not month 2.

**Why now:** premature kill wastes a compounding asset; no kill criteria feeds the Forex pattern.

#### Vision Summary Gate

Vision Summary may confirm only when **all 18 are resolved or logged as Open Questions**. Map onward:

- Decisions to `Technology Decisions` + `Value Streams`.
- Unresolved to `Open Questions` (block confirmation).
- **Fabrik-fit:** `wordpress` scaffold deployed via SSH + Docker Compose as a 4-container per-site stack (nginx + php-fpm + MariaDB + Redis); media to B2, DNS via site-provisioner, WAF/CDN via Cloudflare, backups via Backrest. State the non-12-Factor handling explicitly. Multiple sites or site + custom backend = multi-epic, route to `02-epic-decomposition-command`.
- **Manifest contract:** this module's decisions emit the **site-profile manifest** consumed by your provisioning pipeline (settings, theme, plugins, languages, pages, menus, forms, seo, analytics). Pipeline steps `post_deploy`, `verify`, `finalize` are **execution (downstream)** — intake supplies their inputs (DNS target, page list to 200-check, report scope), not the steps themselves.

### 1B. Epic Decomposition Directives

When decomposing a WordPress vision into epics, these dimensions shape boundaries:

#### Mandatory Epic Coverage

Every WordPress mega-epic MUST have dedicated coverage for:

| Dimension | Epic boundary rule |
|---|---|
| §1 Site Type | Determines all downstream epics. If type = ecommerce, WooCommerce is its own epic. |
| §4 Architecture + Hosting | Foundation epic — 4-container stack (nginx + php-fpm + MariaDB + Redis) via SSH + Docker Compose, B2 offload, Cloudflare, DNS. Everything else depends on this. |
| §5 Theme + Brand | Foundation epic or immediately after — theme choice + Ocoron mu-plugin. Content epics depend on theme. |
| §6 Information Architecture | Foundation epic — page inventory, menus, URL/slug map. Content can't start without IA. |
| §7 Plugin Manifest | Foundation epic — curated list installed + configured. Features depend on plugins being present. |
| §9 Monetization | Own epic if ecommerce (WooCommerce setup). For affiliate/ads: bundled with content epic. Affiliate program = own epic if running one. |
| §10 SEO + §11 Content | Content production epic — SEO config, topic clusters, editorial pipeline. Runs after foundation. |
| §12 Email / Owned Audience | Belongs in the epic that owns the capture mechanism (forms, popups, lead magnets). Never deferred. |
| §14 Legal | Belongs in foundation epic — legal pages, consent banner, disclosures must exist before monetization. |

#### Parallel Lane Opportunities

WordPress projects naturally split into these parallel lanes after the foundation epic:

- **Content production** (articles, pages, media) — independent after IA + SEO config exist
- **Ecommerce (WooCommerce)** — independent after theme + payment gateway exist (if applicable)
- **Affiliate program setup** — independent after product/site exists (if applicable)
- **Email / audience building** — independent after capture forms exist
- **Performance tuning + security hardening** — can run parallel to content

#### Anti-Patterns

- Do NOT create a "design epic" and "content epic" — theme + brand is foundation, not a standalone epic.
- Do NOT defer SEO config to "later" — URL structure and schema are set at build.
- Do NOT defer email capture — early audience is the most valuable.
- Do NOT merge WooCommerce into "the site epic" — ecommerce is complex enough to be its own epic.
- Do NOT treat plugins as implementation detail — the plugin manifest is a planning decision (§7).

#### Phase Mapping

- **Foundation:** container + theme + plugins + IA + legal + SEO config + analytics.
- **Content launch:** cornerstone content + initial catalog (if ecommerce) + email capture live.
- **Growth:** content cadence + link building + audience expansion + monetization tuning.
- **Scale:** additional languages, traffic-tier ad network upgrades, affiliate program launch.

---

## Part 2 — Per-Epic (paste when starting my-workflow for a WordPress epic)

These directives apply throughout all my-workflow steps when the epic belongs to a WordPress project. Traycer carries them from epic-brief through ticket-breakdown and into execution plans.

### 2A. Epic Brief (my-workflow/01)

When creating the epic brief for a WordPress epic:

- State which of the 18 dimensions this epic addresses (by number).
- State the site type (§1) — it gates all downstream decisions.
- Carry forward resolved decisions from the Vision Summary — do not re-decide.
- If this epic is the foundation epic (§4-§7), the brief must include: hosting architecture (4-container SSH + Docker Compose stack: nginx + php-fpm + MariaDB + Redis + B2 offload), theme choice, plugin manifest, page inventory, menu structure, legal pages, analytics IDs.
- If this epic touches monetization (§9), the brief must include: which revenue mechanism, which networks/platforms, disclosure requirements. For ecommerce: payment gateway, shipping, tax, returns. For affiliate program: commission model, platform, terms.
- If this epic owns content (§11), the brief must include: production model, quality bar, cadence, topic clusters.
- Success Criteria must include at least one criterion per dimension this epic addresses.

### 2B. Core Flows (my-workflow/02)

When mapping core flows for a WordPress epic, include these WP-specific flows if the epic touches them:

- **Site provisioning flow:** SSH + Docker Compose deploy (4-container stack), DNS via site-provisioner, SSL via Cloudflare, WP install, theme activate, plugins install, settings apply, pages/menus create, analytics verify.
- **Content publishing flow:** draft (AI-assisted), editorial review, SEO optimize (RankMath), schedule/publish, index (instant-indexing), social share, internal-link update.
- **Visitor conversion flow (by type):**
  - Affiliate: land on content, click affiliate link (tracked), convert on merchant site, commission attributed.
  - Content+ads: land on content, view ads (RPM), optionally subscribe to newsletter.
  - Business: land on page, fill form, lead captured in CRM.
  - Landing-funnel: land on page, enter funnel, purchase via Paddle.
  - Ecommerce: browse catalog, add to cart, checkout (iyzico/PayTR), order confirmed, fulfillment.
- **Email capture flow:** visitor lands, capture trigger (popup/inline/content upgrade), email submitted, welcome sequence fires, subscriber tagged.
- **Affiliate program flow (if applicable):** partner applies, approved/rejected, gets tracking link, drives traffic, conversion tracked, commission accrued, payout processed.
- **Update/maintenance flow:** auto-update minor, staging clone for major, test, push to production, Backrest backup verified.

Each flow must identify the `[PRIMARY PATH]` — the happy path.

### 2C. Tech Plan (my-workflow/03)

When creating the tech plan for a WordPress epic, enforce:

- **Hosting architecture:** 4-container per-site stack via SSH + Docker Compose — nginx + php-fpm (WordPress) + dedicated MariaDB (not postgres-main — WP requires MySQL-compat) + dedicated Redis (object cache; NOT shared redis-main — WP's cache flush is FLUSHDB-based and would wipe co-tenants), Backblaze B2 for media offload, Cloudflare CDN+WAF. Persistent Docker volume for uploads as fallback only. Backups via central Backrest.
- **Theme architecture:** lightweight block theme (GeneratePress/Kadence/FSE). No Elementor/Divi. Ocoron brand assets as mu-plugin.
- **Plugin architecture:** minimal curated set per the manifest from §7. Each plugin justified. Auto-update minor, staging for major. Zero abandoned plugins.
- **Caching architecture:** full-page cache plugin + redis object cache + Cloudflare edge cache. Cache-busting strategy for dynamic content (logged-in users, cart).
- **SEO architecture:** RankMath configuration, schema markup strategy, sitemap generation, instant-indexing API, internal-linking model.
- **Analytics architecture:** GA4 + GTM + Search Console. Privacy-compliant consent-gated tagging.
- **Multilingual architecture (if applicable):** Polylang + AutoPoly/DeepL, hreflang tags, language switcher placement, translated slugs.
- **Ecommerce architecture (if applicable):** WooCommerce, payment gateway (iyzico/PayTR for TR physical, Paddle for digital), shipping plugin, tax config, inventory model.
- **Affiliate program architecture (if applicable):** AffiliateWP/SliceWP, tracking method, commission tiers, payout schedule, fraud prevention.

### 2D. Ticket Outline (my-workflow/05)

When creating the ticket outline for a WordPress epic, verify coverage:

- If this epic owns foundation: tickets for compose-stack setup (nginx + php-fpm + MariaDB + Redis) + B2 offload + Cloudflare DNS/WAF + theme install + mu-plugin (brand) + plugin manifest install + settings apply.
- If this epic owns IA: tickets for page inventory creation + menu structure + homepage/blog-page pointers + URL/slug lock.
- If this epic owns content: tickets for editorial pipeline setup + cornerstone content batch + SEO config (RankMath + schema + sitemap + instant-indexing).
- If this epic owns monetization: tickets for affiliate network signup + link management plugin (if affiliate), ad network setup (if content+ads), WooCommerce setup + payment gateway + shipping + tax (if ecommerce), Paddle integration (if landing-funnel), AffiliateWP setup + commission config + recruitment page (if affiliate program).
- If this epic owns email: tickets for ESP integration + capture forms/popups + lead magnet + welcome sequence.
- If this epic owns legal: tickets for privacy policy + cookie consent banner + affiliate disclosure + ecommerce legal pages (if applicable) + affiliate program terms (if applicable).
- If this epic owns performance: tickets for cache config + image optimization + CWV audit + lazy-load.
- Analytics instrumentation belongs inside each feature ticket as an AC, not a separate ticket.
- Backup verification (Backrest to B2) is a ticket in the foundation epic.

### 2E. Ticket Breakdown (my-workflow/06)

When Traycer creates full ticket specs and agent execution plans for a WordPress epic:

#### Per-Ticket Injection Rules

For every ticket, check which dimensions apply and inject into Acceptance Criteria and Context Files:

| If ticket touches... | Inject |
|---|---|
| Container / hosting | SSH + Docker Compose deploy (4-container stack); dedicated MariaDB container; dedicated Redis object-cache container; B2 media offload configured; Cloudflare DNS + WAF active |
| Theme / design | Lightweight block theme (no Elementor/Divi); Ocoron mu-plugin installed; brand CSS applied; CWV green |
| Plugins | Plugin from the approved manifest only; no abandoned plugins; auto-update minor configured |
| Pages / IA | Pages match inventory; slugs match URL map; menus match spec; homepage + blog-page pointers set |
| Content / articles | AI-assisted + editorial QC; RankMath SEO score green; schema applied; internal links added; instant-indexing triggered |
| Affiliate links (publisher) | Managed/cloaked links; disclosure on page; click tracking verified; network T&Cs met |
| Affiliate program (our products) | AffiliateWP/SliceWP configured; commission tiers set; tracking verified; recruitment page live; program terms published; fraud guards active |
| Ads / display | Ad network code placed; privacy-compliant (consent-gated); RPM tracking verified |
| Ecommerce / WooCommerce | Payment gateway configured; tax + shipping rules set; order flow tested end-to-end; legal pages (distance-selling, returns) published |
| Landing / funnel | Paddle integration; conversion tracking; A/B test framework (if planned) |
| Email capture | ESP connected; capture form/popup placed; welcome sequence configured; subscriber tagged |
| SEO config | RankMath configured; sitemap generated; schema markup applied; Search Console connected; instant-indexing API configured |
| Analytics | GA4 + GTM installed; consent-gated; conversion events defined; Search Console verified |
| Legal / compliance | Cookie consent banner; privacy policy; affiliate disclosure (if applicable); ecommerce legal (if applicable); affiliate program terms (if applicable) |
| Performance / caching | Full-page cache + redis object cache + Cloudflare edge; WebP + lazy-load; CWV audit passes green |
| Backups | Backrest to B2 configured; DB + uploads included; restore tested |
| Security | Cloudflare WAF rules; security plugin configured; admin hardening (2FA, limited login); XML-RPC disabled; file permissions locked |
| Multilingual (if applicable) | Polylang configured; hreflang tags present; translated slugs; language switcher placed; DeepL connected (if auto-translate) |
| Email / newsletter template | MJML as design source; compiled HTML to Woo override or ESP; WP/Woo/ESP merge tags (not Jinja2); FluentCRM for marketing; reference `core/86-email-templates.md` § WordPress |

#### Agent Context Files

Every WordPress ticket's Context Files section must include (in addition to general rule packs):

```text
.windsurf/rules/core/30-ops.md              — Docker, compose, VPS (SSH + Docker Compose) deploy patterns
.windsurf/rules/core/35-security-auth.md    — security hardening, credential management
.windsurf/rules/core/85-payments-billing.md — payment gateway patterns (if ecommerce/funnel)
.windsurf/rules/core/86-email-templates.md  — email/notification templates (if ticket creates or edits templates)
```

No dedicated WordPress rule pack exists — the domain module decisions (theme choice, plugin manifest, hosting architecture) serve as the coding agent's WordPress-specific constraints. Agents follow the approved plugin manifest and do not add plugins outside it.

#### Plan Directives for Coding Agents

When Traycer creates the execution plan (the plan the coding agent follows), embed these constraints:

1. **Plugin manifest is law.** Do not install plugins outside the approved manifest from §7. Need a new plugin = ask the owner, not the agent's judgment.
2. **No Elementor/Divi.** Lightweight block theme only. No page builder lock-in.
3. **Media goes to B2.** No local media uploads to the container filesystem. Offload plugin configured and verified.
4. **Object cache goes to the site's dedicated Redis container.** Redis object cache plugin active and connected. Never point WP at shared `redis-main` — its FLUSHDB-based flush would wipe co-tenants.
5. **DB is MariaDB, not postgres-main.** WordPress requires MySQL-compatible. Do not route WP queries to postgres-main.
6. **Every page matches the IA spec.** Slugs match the URL map from §6. No improvised page structure.
7. **Every content page has SEO.** RankMath score green, schema applied, internal links present.
8. **Every monetization touchpoint has disclosure/compliance.** Affiliate disclosure on affiliate pages, cookie consent before tracking, ecommerce legal pages published.
9. **CWV must be green.** Test after every significant change. Cache + image optimization + minimal JS.
10. **Auto-update minor is on.** Major updates go through staging first. Zero abandoned plugins at any point.
11. **Backrest backup verified.** DB + uploads backed up to B2. Restore path tested.
