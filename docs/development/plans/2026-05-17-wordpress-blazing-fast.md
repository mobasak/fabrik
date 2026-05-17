# Plan: WordPress Blazing Fast — Local Create → VPS Deploy → Continuous Content

**Created:** 2026-05-17
**Status:** PLANNING
**Owner:** Özgür (solo)
**Consolidates:** `2026-04-13-fabrik-control-plane.md` (archived), legacy SOP docs, ocoron.com spec work

---

## Vision

Create WordPress sites in minutes. No manual steps after deploy. The pipeline feeds itself with AI-generated content forever.

---

## Complete Pipeline (30 Steps, 7 Phases)

### Phase 0 — Research & Decide

| Step | Action | Source File |
|---|---|---|
| 0.1 | Choose preset: `company` / `saas` / `content` / `landing` / `ecommerce` | `templates/wordpress/presets/*.yaml` |
| 0.2 | `fabrik domain check <domain>` — check availability via site-provisioner | `src/fabrik/drivers/dns.py` → `DNSClient.check_availability()` |
| 0.3 | `fabrik domain buy <domain>` — register (Namecheap, nameservers→Cloudflare, WHOIS privacy) | `src/fabrik/drivers/dns.py` → `DNSClient.register()` |

### Phase 1 — Domain Provisioning

| Step | Action | Source File |
|---|---|---|
| 1.1 | `fabrik domain provision <domain>` — single API call does ALL: Cloudflare zone + A record + DNSSEC + CDN + WAF + Bing Webmaster + IndexNow (Bing/Yandex/Seznam/Naver) + optional GSC + optional GA4 + sitemap submission | `src/fabrik/drivers/dns.py` → `DNSClient.provision()` |
| 1.2 | `fabrik domain ready <domain> --wait` — poll until zone active + DNS resolves | `src/fabrik/drivers/dns.py` → `DNSClient.check_ready()` |
| 1.3 | `fabrik domain integrations <domain>` — confirm GA4 ID, GSC status, Bing status | `src/fabrik/drivers/dns.py` → `DNSClient.get_integrations()` |

### Phase 2 — Scaffolding

| Step | Action | Source File |
|---|---|---|
| 2.1 | `fabrik scaffold <name> --type wordpress --preset company` — generates project folder | `src/fabrik/scaffold.py` → `_scaffold_wordpress_templates()` |
| 2.2 | Edit `site.yaml` — brand, pages, services, contact, SEO, plugins, languages | `templates/wordpress/base/site.yaml.j2` (template) |

### Phase 3 — Planning

| Step | Action | Source File |
|---|---|---|
| 3.1 | `fabrik wp plan <site>` — 3-layer merge (defaults→preset→site.yaml), compute hashes, write plan.json + manifests | `src/fabrik/wordpress/planner.py` → `Planner.plan()` |

**Merge chain:** `src/fabrik/wordpress/spec_loader.py` → `src/fabrik/wordpress/preset_loader.py` → `src/fabrik/wordpress/resolved_spec.py`

**Outputs:** `build/sites/<id>/plan.json`, `blueprint.resolved.yaml`, `manifests/{plugins,pages,menus,checks}.json`

### Phase 4 — Container Deployment

| Step | Action | Source File |
|---|---|---|
| 4.1 | `fabrik apply` — creates Coolify app, launches WordPress + MariaDB containers | `src/fabrik/orchestrator/deployer.py` + `src/fabrik/deploy_router.py` |
| 4.2 | Wait for container running (SSH fallback if Coolify #9161 stalls) | `src/fabrik/orchestrator/deployer.py` |

### Phase 5 — WordPress Configuration (13 Stages + Finalize)

`fabrik wp apply <site>` runs all stages sequentially. Each stage is idempotent (skips if input hash unchanged).

| Stage | What It Does | Blocking? | Source File |
|---|---|---|---|
| 1. DNS | Sync A record + www CNAME, verify zone active | YES | `src/fabrik/wordpress/stages/dns.py` |
| 2. Settings | blogname, tagline, email, timezone, permalinks, users via WP-CLI | YES | `src/fabrik/wordpress/stages/settings.py` + `src/fabrik/wordpress/settings.py` |
| 3. Theme | Install + activate theme, apply brand colors + fonts via Customizer | no | `src/fabrik/wordpress/stages/theme.py` + `src/fabrik/wordpress/theme.py` |
| 4. Plugins | Install + activate all (base + preset + add - skip; 125 premium zips bundled) | YES | `src/fabrik/wordpress/stages/plugins.py` + `src/fabrik/wordpress/manifests/plugins.py` |
| 5. Languages | Polylang config, install language packs (en + tr), set default | no | `src/fabrik/wordpress/stages/languages.py` |
| 6. Pages | Create via REST API: home, about, services/*, contact, blog, legal. Entities with `generate_pages:true` auto-generate child pages | no | `src/fabrik/wordpress/stages/pages.py` + `pages.py` + `page_generator.py` + `section_renderer.py` |
| 7. Menus | Create nav menus, assign to theme locations, resolve page IDs | no | `src/fabrik/wordpress/stages/menus.py` + `src/fabrik/wordpress/menus.py` |
| 8. Forms | Create contact forms (CF7/WPForms/Fluent Forms) | no | `src/fabrik/wordpress/stages/forms.py` + `src/fabrik/wordpress/forms.py` |
| 9. SEO | RankMath: title, meta, schema markup, breadcrumbs, OG, Twitter Cards, verification codes, robots.txt AI rules | no | `src/fabrik/wordpress/stages/seo.py` + `src/fabrik/wordpress/seo.py` |
| 10. Post-deploy | Resubmit sitemap to all engines, retrieve GA4 measurement ID | no | `src/fabrik/wordpress/stages/post_deploy.py` |
| 11. Analytics | Inject GA4 + GTM tracking code into WP head/footer | no | `src/fabrik/wordpress/stages/analytics.py` + `src/fabrik/wordpress/analytics.py` |
| 12. Monitoring | Gatus HTTP monitor + optional WP Cron health monitor | no | `src/fabrik/wordpress/stages/monitoring.py` |
| 13. Verify | 10 checks: DNS, HTTP→HTTPS, SSL, homepage 200, wp-json, sitemap, robots.txt, wp-login, plugins, custom URLs | no | `src/fabrik/wordpress/stages/verify.py` |
| Finalize | `wp rewrite flush` + `wp cache flush` + write apply-report.json | — | `src/fabrik/wordpress/deployer.py` |

### Phase 6 — Standalone Verification

| Step | Action | Source File |
|---|---|---|
| 6.1 | `fabrik wp verify <domain>` — re-runs all 10 checks + generates handoff.md | `src/fabrik/wordpress/stages/verify.py` + `src/fabrik/wordpress/handoff.py` |

### Phase 7 — Continuous Content (Automated, Runs Forever)

| Step | Action | Source File |
|---|---|---|
| 7.1 | `fabrik seo site-register <domain>` — register in SEO microservice | `src/fabrik/drivers/seo.py` → `SEOClient.register_site()` |
| 7.2 | `fabrik seo job-create <site> "seed keywords"` — keyword research job | `src/fabrik/drivers/seo.py` → `SEOClient.create_job()` |
| 7.3 | `fabrik seo job-run <job_id> --wait` — researches → clusters → generates briefs | `src/fabrik/drivers/seo.py` → `SEOClient.run_job()` |
| 7.4 | `fabrik content publish <domain> --limit 2` — for each ready brief: | `src/fabrik/orchestrator/content_publisher.py` |
| | → Claim brief (lock) | `SEOClient.claim_brief()` |
| | → TCO generate (AI: brief → sections + JSON-LD + SEO meta) | `src/fabrik/drivers/tco.py` → `TCOClient.generate_from_brief()` |
| | → Image Broker (keyword → hero image from Pexels/Pixabay) | `src/fabrik/drivers/image_broker.py` → `ImageBrokerClient.auto_download()` |
| | → WordPress publish (REST API: create post + featured image) | `src/fabrik/drivers/wordpress_api.py` → `WordPressAPIClient.create_post()` |
| | → SEO submit (mark brief published with final URL) | `SEOClient.submit_brief()` |
| | → n8n webhook → Telegram notification | `src/fabrik/notifications.py` |
| 7.5 | `fabrik domain sitemap <domain> <url>` — resubmit sitemap after publish | `src/fabrik/drivers/dns.py` → `DNSClient.update_sitemap()` |
| 7.6 | Repeat 7.4-7.5 on cron/n8n trigger (daily) | n8n workflow or VPS cron |

---

## Complete File Inventory

**Canonical source:** `docs/development/wordpress-files-index.md` — 380-line exhaustive index (updated 2026-05-17).

**Summary stats:** 44 source modules (~9,700 LoC), 14 stage executors, 5 manifests, 6 drivers, 5 presets, 125 premium plugins, 20+ test files (~3,000 LoC), 11 reference docs.

**Key entry points for code work:**

| What | Where | Read for |
|---|---|---|
| CLI commands | `src/fabrik/cli.py` | All `fabrik wp/domain/seo/content` commands |
| WordPress engine | `src/fabrik/wordpress/` (25 modules) | Core orchestration |
| 13 stages | `src/fabrik/wordpress/stages/*.py` | Per-stage logic |
| Content loop | `src/fabrik/orchestrator/content_publisher.py` | SEO→TCO→Image→WP pipeline |
| Drivers | `src/fabrik/drivers/{dns,seo,tco,image_broker,wordpress,wordpress_api}.py` | External service clients |
| Site provisioner | `src/fabrik/drivers/dns.py` | Domain buy/provision/GSC/Bing/IndexNow |
| Deploy routing | `src/fabrik/deploy_router.py` + `deployer.py` | Coolify + container launch |
| GlitchTip for WP | `src/fabrik/drivers/glitchtip.py` | DSN injection into wp-config-extra.php |
| Verifier | `src/fabrik/orchestrator/verifier.py` | WP-specific health checks |
| Provisioner | `src/fabrik/provisioner.py` | MariaDB + Redis provisioning |
| Notifications | `src/fabrik/notifications.py` | n8n webhook → Telegram |
| Presets | `templates/wordpress/presets/{company,saas,content,landing,ecommerce}.yaml` | Site category definitions |
| Schema | `templates/wordpress/schema/v1.yaml` | site.yaml validation |
| Merge rules | `templates/wordpress/schema/MERGE_RULES.md` | How layers combine |
| Rule pack | `.windsurf/rules/62-wordpress.md` | WP coding discipline |
| ocoron.com spec | `specs/sites/ocoron.com.yaml` | Flagship site (DRAFT) |
| SEO service spec | `specs/services/seo.yaml` | SEO microservice definition |
| Site workflow | `docs/workflows/wordpress-site-workflow.md` | Documented end-to-end flow |
| Architecture | `docs/reference/wordpress/architecture.md` | Module design |
| Plugin stack | `docs/reference/wordpress/plugin-stack.md` | Bundled plugins reference |
| Archived best practices | `docs/reference/wordpress/archived-01-wordpress-production-sop.md` | Production SOP (reference only) |
| Archived Zero-Ops narrative | `docs/reference/wordpress/archived-zero-ops-pipeline-narrative.md` | Pipeline philosophy (reference only) |
| Full file index | `docs/development/wordpress-files-index.md` | **Exhaustive** file listing |
| Scripts | `scripts/create_wp_container.py`, `scripts/audit_authelia_gates.py` | WP-specific utilities |
| Project registry | `data/projects.yaml` | Registered WP projects |
| Test scaffold | `/opt/fabrik-test-wordpress/` | Live scaffolded WP project (2026-04-27) |

---

## Presets (5 Site Categories)

| Preset | Use Case | Key Entities | Pages Auto-Generated |
|---|---|---|---|
| `company` | Service business, agency, consultancy | services, team, locations | Home, About, Services/*, Contact, Blog, Legal |
| `saas` | SaaS landing + auth/signup flow | features, pricing_plans, testimonials | Home, Features, Pricing, About, Contact, Blog, Legal |
| `content` | Blog, magazine, content hub | categories, authors | Home, Blog, Category/*, Author/*, About, Legal |
| `landing` | Single-page conversion landing | — (all sections on one page) | Home (full-width), Legal |
| `ecommerce` | WooCommerce / EDD shop | products, product_categories | Home, Shop, Cart, Checkout, Account, About, Legal |

---

## Codebase Status (deep analysis 2026-05-17)

**Engine health:** Zero TODOs/FIXMEs/NotImplementedErrors. Two past bugs (entity slug slashes, preset merge drop) both fixed and tested. Codebase is complete and functional.

**Real stage order** (from `deployer.py`, NOT the old docs):
```
dns → settings → theme → plugins → languages → pages → menus → forms → seo → post_deploy → analytics → monitoring → verify
```
Note: theme runs BEFORE plugins (not after). Blocking stages: dns, settings, plugins only.

**Hard dependencies for deploy:**
- `fabrik wp plan` MUST run before `fabrik wp apply` (hard gate on build dir)
- `WP_ADMIN_PASSWORD` + `security.admin_username` (or `WP_ADMIN_USER` env) — REST API stages crash without these
- `ANTHROPIC_API_KEY` — needed for content generation (bypassable with `--skip-content`)
- VPS DNS Manager must be running for domain provisioning
- Cloudflare zone activation is async — can take minutes to hours for new domains
- Redis + Nginx cache + Cloudflare all must be operational for atomic cache flush

**Known contradictions:**
- `docs/reference/wordpress/deployment-workflow.md` references Apache images. Rule pack `62-wordpress.md` BANS Apache and mandates `php8.x-fpm-bookworm` + Nginx. **The workflow doc is outdated.** Templates use FPM+Nginx (correct).
- ocoron.com spec says `plugin: wpml`. Rule pack mandates Polylang. **Polylang wins.**

**Content plan outdated:**
- `specs/sites/ocoron.com-content-plan.md` says Image Broker is "FUTURE" — it's built and working at `src/fabrik/drivers/image_broker.py`
- TCO + Content Publisher also already shipped

**Plugin activation notes:** `templates/wordpress/plugins/premium/wp_plugins_activation_notes.md` — license keys for FlyingPress, WP Staging Pro, AutomatorWP + activation workarounds for WPML, Content Egg Pro.

**Not implemented (noted in fixes.md):**
- Concurrent deploy safety (per-site locks)
- Duplicate path detection
- Unresolved placeholder validation
- Path normalization for WP auto-suffix (`-2`)

---

## What's Automated Per Site (the full value of this pipeline)

Every `fabrik wp apply` site gets ALL of this without manual work:

### Security (10 layers, automated via templates + stages)

| Layer | What | Implemented in |
|---|---|---|
| wp-config hardening | DISALLOW_FILE_EDIT/MODS, FORCE_SSL, WP_HTTP_BLOCK_EXTERNAL, custom table prefix, DISABLE_WP_CRON | `templates/wordpress/base/wp-config-extra.php` |
| Cloudflare WAF | 5 rules: bot skip, login challenge, xmlrpc block, wp-admin challenge, VPN ASN challenge | `62-wordpress.md` → site-provisioner applies |
| Origin headers | X-Frame-Options, X-Content-Type, Referrer-Policy, XSS-Protection, CSP, HSTS | `templates/wordpress/base/nginx/default.conf.j2` |
| REST API lockdown | Block /wp-json/wp/v2/users, block anon non-GET requests | MU-plugin + Nginx conf |
| xmlrpc.php | Blocked at Nginx (PHP never invoked) | Nginx conf |
| Rate limiting | wp-login.php: 10 req/min/IP, burst 20 | Traefik middleware |
| Wordfence | Brute-force lockout (5 attempts), 2FA mandatory, file integrity, malware scan | Plugin stage (auto-configured) |
| Admin hardening | No "admin" username, 32-char password, max 1 admin account | `settings.py` + spec validator |
| Footprint removal | Generator meta, RSD, emoji JS/CSS, version strings all stripped | MU-plugin |
| Upload protection | PHP execution blocked in /uploads/ | Nginx conf |

### Analytics & Search Engines (automated via stages)

| What | How | Stage |
|---|---|---|
| GA4 tracking code | gtag.js async injection | Stage 11 (analytics) |
| GTM container | Head JS loader + body noscript iframe | Stage 11 (analytics) |
| Google Search Console | DNS TXT verification via site-provisioner | Phase 1 (domain provision) |
| Bing Webmaster Tools | Automatic registration | Phase 1 (domain provision) |
| IndexNow | Ping Bing/Yandex/Seznam/Naver on publish | Phase 1 + RankMath Instant Indexing |
| Sitemap submission | All engines notified | Stage 10 (post_deploy) |
| Schema markup | Organization/LocalBusiness JSON-LD | Stage 9 (seo) |
| Open Graph + Twitter Cards | Meta tags for social sharing | Stage 9 (seo) |
| robots.txt | AI crawler allow rules (GPTBot, ClaudeBot, etc.) | Stage 9 (seo) |

### Caching (4-layer atomic, automated)

| Layer | Mechanism | Flush command |
|---|---|---|
| Cloudflare edge | CDN purge via API | `cache.flush_all()` |
| Nginx FastCGI | File-based cache at /var/cache/nginx/ | rm -rf via docker exec |
| Redis Object | wp redis flush | WP-CLI |
| WP Transients | wp cache flush + wp rewrite flush | WP-CLI |

Plus: WooCommerce bypass rules, GDPR consent cache poisoning prevention, `make warm-cache` (8 parallel workers).

### Monitoring (automated via registrars + stages)

| What | How |
|---|---|
| Uptime (Gatus) | HTTP monitor at status.vps1.ocoron.com |
| Errors (GlitchTip) | SENTRY_DSN injected into wp-config-extra.php |
| Backup (Backrest) | Daily to Backblaze B2, Restic dedup + encryption |
| WP Cron health | Optional Gatus ping monitor for wp-cron.php |
| Deploy annotations | Grafana marker on every deploy |

### Operations (via Makefile + 62-wordpress.md)

```
make update          — WP core + plugin updates
make cache-flush     — 4-layer atomic flush
make backup          — manual backup trigger
make harden          — re-apply security settings
make security-check  — Wordfence scan + file integrity
make warm-cache      — purge CF + hit all sitemap URLs (8 parallel)
make rename-admin    — rotate admin username
make db-clean        — prune transients, spam, revisions, orphaned postmeta
```

---

## What's Missing (Blockers for "Blazing Fast")

| # | Blocker | Impact | Fix |
|---|---|---|---|
| 1 | No single `fabrik wp create` command | 4 commands + manual YAML editing instead of 1 | Create wrapper: `fabrik wp create <domain> --preset --brand --interactive` |
| 2 | ocoron.com spec is DRAFT since 2025-12-24 | Flagship never deployed via pipeline | Finalize spec, decide WPML→Polylang, deploy |
| 3 | WPML vs Polylang conflict | Spec says WPML, rule pack mandates Polylang | Decision: Polylang (rule pack wins) |
| 4 | No continuous content trigger | `fabrik content publish` is manual | VPS cron: `0 3 * * * fabrik content publish <domain> --limit 2` |
| 5 | SSH-only execution | Can't run pipeline on VPS without WSL up | Implement `FABRIK_EXEC_MODE=local` (1 line change in drivers/wordpress.py) |

## Nice-to-Have (From Archived Control-Plane Plan)

| # | Feature | Value | Effort |
|---|---|---|---|
| 6 | `fabrik wp create --interactive` | AI asks questions → generates site.yaml | Medium |
| 7 | SSE progress streaming (FastAPI bridge on VPS) | See stage progress from any device | Medium |
| 8 | Approval gate for irreversible ops | Prevent accidental domain purchase / zone creation | Low |

---

## Key Invariants (Permanent Architecture Decisions)

1. **`FABRIK_EXEC_MODE=local` on VPS** — drops SSH hop, docker exec directly
2. **Manual sign-off for irreversible ops** — domain purchase, zone creation, GA4 property
3. **Traefik labels explicit** — never rely on Coolify's runtime injection (Lesson §8.7)
4. **Authelia = policy rule + middleware** — bypass `/api/` paths (Lesson §8.11)
5. **Compose source-of-truth** — git-sourced: push→deploy. Services: PATCH API (Lesson §8.10)
6. **Each WP site fully isolated** — own MariaDB, own volumes. Shared: Redis, Traefik
7. **Container naming: `<domain-slug>-wordpress-1`** — deterministic, no UUIDs
8. **Spec is truth** — site.yaml drives everything. Manual WP-admin changes are overwritten on re-apply

---

## Tickets (via Traycer workflow)

| # | Title | Priority |
|---|---|---|
| 1 | Finalize ocoron.com spec (WPML→Polylang, fill remaining fields, deploy) | HIGH |
| 2 | Implement `FABRIK_EXEC_MODE=local` in wordpress.py (1-line gate) | HIGH |
| 3 | Create VPS cron for `fabrik content publish` (daily, limit 2) | HIGH |
| 4 | Create `fabrik wp create` wrapper (scaffold + plan + apply in one command) | MEDIUM |
| 5 | Create `fabrik wp create --interactive` (AI-guided spec generation) | MEDIUM |
| 6 | Archive legacy docs: rename 3 non-kebab files (already done 2026-05-17) | DONE ✅ |
