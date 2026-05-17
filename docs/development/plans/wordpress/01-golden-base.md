# Golden Base — Build Once, Deploy Many

## What

A pre-configured WordPress installation (Docker image + wp-content volume) that contains everything IDENTICAL across all sites. New site = clone golden base + apply per-site variables. Seconds instead of minutes.

## Why

**Current state:** `fabrik wp apply` starts from `wordpress:php8.3-fpm-bookworm` (bare), installs 8+ base plugins + 15-25 profile plugins, configures each, applies security — 5-10 minutes per site.

**Target state:** Golden base has base plugins pre-installed + configured. Profile plugins install from local zips (fast, no download). Total: < 60 seconds to live site.

## What's IN the Golden Base

Everything from `62-wordpress.md` rules + plugin-stack.md BASE tier. These are identical across ALL sites regardless of preset/profile:

### WordPress Core
- `wordpress:php8.3-fpm-bookworm` (pinned, not `:latest`)
- Nginx hardened config (from `templates/wordpress/base/nginx/default.conf.j2`)
- MariaDB 10.11 (per-site container, clean schema — NOT shared. Each site gets own DB)

### Theme
- GeneratePress + GP Premium installed + activated
- Base typography: Inter (heading + body)
- No brand colors applied (per-site via Customizer API from site.yaml `brand:`)

### BASE Plugins (11 plugins, pre-installed + activated + configured)

| Plugin | Pre-configuration in golden base |
|---|---|
| GeneratePress + GP Premium | Activated, base blocks enabled, hooks ready |
| RankMath Pro | Modules enabled: sitemap (200/page), instant-indexing, rich-snippet, image-seo, redirections. Analytics module DISABLED (table bloat). AI crawler allow rules in robots.txt. |
| FlyingPress | Page cache ON, CSS/JS optimization ON, Cloudflare APO compatible settings |
| WP Mail SMTP Pro | Installed, NOT configured (SMTP credentials are per-site env vars) |
| WP Staging Pro | Installed, ready for staging operations |
| Object Cache Pro | Installed, configured: `WP_REDIS_HOST=redis-main`. Per-site isolation via `WP_REDIS_PREFIX` + `WP_REDIS_DATABASE` (injected at deploy time from env) |
| Complianz Pro | Installed, base GDPR banner configured (geo-targeting, cookie categories). Per-site: domain, policy URLs |
| Cloudflare Turnstile | Installed, NOT configured (site key + secret are per-site) |
| Polylang Pro | Installed + activated. EN + TR registered. URL: `/en/`, `/tr/` directories. Hreflang automatic. String translation enabled. |
| AutoPoly Pro | Installed. Calls DeepL directly via `DEEPL_API_KEY` env var. Auto-translates on publish. No middleware. |
| SearchWP Polylang Integration | Installed. Search results filtered by active language. |

**Note:** Wordfence is NOT in golden base. It's OPTIONAL (high-risk sites only per plugin-stack.md). Security is handled by the 10 layers outside WordPress.

### Security Hardening (baked into image)

| Layer | What's baked | Source file |
|---|---|---|
| wp-config-extra.php | DISALLOW_FILE_EDIT, DISALLOW_FILE_MODS, FORCE_SSL_ADMIN, WP_HTTP_BLOCK_EXTERNAL + whitelist, DISABLE_WP_CRON, WP_AUTO_UPDATE_CORE='minor', OPcache tuning | `templates/wordpress/base/wp-config-extra.php` |
| MU-plugins | anon REST block, /users enumeration block, footprint removal (generator, RSD, emoji, ver strings) | To create: `templates/wordpress/golden/mu-plugins/` |
| Nginx config | Security headers (X-Frame, X-Content-Type, Referrer-Policy, XSS-Protection), xmlrpc.php blocked (return 444), PHP execution blocked in /uploads/, FastCGI cache configured | `templates/wordpress/base/nginx/default.conf.j2` |
| PHP-FPM | Pool tuning (max_children, pm settings) | `templates/wordpress/base/php-fpm/zz-fabrik-listen.conf` |

### Caching (pre-configured)
- Redis Object Cache → connected to `redis-main` (per-site prefix via env)
- Nginx FastCGI cache → bypass rules for: logged-in users, WooCommerce cart/checkout/my-account, GDPR consent cookie absence
- FlyingPress page cache → ON, purge hooks registered

### Multilingual — RESOLVED: Polylang Pro + AutoPoly

| Plugin | In golden base | Pre-configuration |
|---|---|---|
| Polylang Pro | YES | Installed + activated. EN + TR languages registered. URL structure: `/en/`, `/tr/` directories. Hreflang automatic. |
| AutoPoly Pro | YES | Installed. Calls DeepL directly (API key via `DEEPL_API_KEY` env var). Auto-translates on publish. No middleware/Translator service needed. |
| SearchWP Polylang | YES | Installed. Activates alongside SearchWP. |
| Polylang for WooCommerce | NO (ecommerce profile) | Installed at Stage 4 (plugins) for ecommerce sites only |

**Replaces:** ~~WPML CMS~~, ~~WPML String Translation~~, ~~SearchWP WPML~~. Remove these from all profiles.

**Per-site config (from site.yaml `languages:` section):**
- Which languages active (default: en + tr)
- Default language (default: en)
- URL structure (default: directory /en/, /tr/)
- AutoPoly: `DEEPL_API_KEY` env var (calls DeepL directly, no middleware)

## What STAYS OUT (per-site variables, applied at deploy time)

| Variable | Applied by which stage | Source |
|---|---|---|
| Domain name + Traefik labels + SSL | Stage 1 (DNS) | site.yaml `site.domain` |
| WP admin user + password | Stage 2 (Settings) | `WP_ADMIN_USER` + `WP_ADMIN_PASSWORD` env vars |
| blogname, tagline, email, timezone, permalinks | Stage 2 (Settings) | site.yaml `site.*` |
| Brand colors + fonts | Stage 3 (Theme) | site.yaml `brand.*` via Customizer API |
| Profile plugins (e.g., FluentCRM, WooCommerce, Bookly) | Stage 4 (Plugins) — ADDITIONS ONLY | Preset profile → local zips |
| Polylang locale activation (which languages active) | Stage 5 (Languages) | site.yaml `languages.*` |
| Pages + content | Stage 6 (Pages) | site.yaml `pages` + entities |
| Navigation menus | Stage 7 (Menus) | site.yaml `navigation` |
| Contact forms | Stage 8 (Forms) | site.yaml `contact` / `forms` |
| SEO: verification codes, homepage meta, schema type | Stage 9 (SEO) | site.yaml `seo.*` |
| GA4/GTM IDs | Stage 11 (Analytics) | site.yaml `seo.analytics.*` or env |
| Gatus monitor, GlitchTip DSN, Backrest plan | Stage 12 (Monitoring) | Registrar system |
| SMTP credentials (Resend/SES key) | Coolify env | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` |
| Turnstile site key + secret | Coolify env | `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET` |
| Redis DB index | Coolify env | `WP_REDIS_DATABASE` from redis-assignments |
| Custom table prefix | Coolify env / wp-config | Generated at scaffold time |
| Cloudflare WAF rules (domain-specific) | site-provisioner | `fabrik domain provision` |

## Implementation: Layered Docker Images

Pure Docker image doesn't work for activation: `wp plugin activate` needs a running database. Solution: extract plugin FILES into the image (fast), activate via first-boot script after DB is up.

**Architecture: Base layer + Profile layers (Docker FROM inheritance)**

```
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 1: fabrik/wp-golden-base:v1                                   │
│ (rebuilt monthly or on base plugin security update)                  │
│                                                                     │
│ Contains (FILES only, not activated):                               │
│ • WordPress core                                                    │
│ • wp-config-extra.php (security constants)                          │
│ • MU-plugins (REST block, footprint removal, enumeration block)     │
│ • Nginx config (hardened)                                           │
│ • PHP-FPM config (tuned)                                            │
│ • 11 BASE plugins extracted to wp-content/plugins/                  │
│ • GeneratePress theme in wp-content/themes/                         │
│ • Redis Object Cache drop-in (object-cache.php)                     │
│ • First-boot script                                                 │
│                                                                     │
│ Does NOT contain: DB, activations, wp_options, license keys         │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ FROM
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 2: fabrik/wp-golden-company:v1                                │
│ (rebuilt when Company profile plugins update)                       │
│                                                                     │
│ Inherits ALL from golden-base, ADDS:                                │
│ • 22 Company profile plugins extracted to wp-content/plugins/       │
│ • Profile-specific first-boot additions (config for Fluent,         │
│   Thrive, AutomatorWP, SearchWP, PixelYourSite, Chaty)             │
│                                                                     │
│ Total: 33 plugins pre-extracted, ready to activate                  │
└─────────────────────────────────────────────────────────────────────┘

Similarly:
  fabrik/wp-golden-saas:v1         → FROM golden-base + 24 SaaS plugins
  fabrik/wp-golden-content:v1      → FROM golden-base + 24 Content plugins
  fabrik/wp-golden-landing:v1      → FROM golden-base + 9 Landing plugins
  fabrik/wp-golden-ecommerce:v1    → FROM golden-base + 20 Ecommerce plugins
  fabrik/wp-golden-edd:v1          → FROM golden-base + 10 EDD plugins
  fabrik/wp-golden-membership:v1   → FROM golden-base + 7 MemberPress plugins
  fabrik/wp-golden-appointments:v1 → FROM golden-base + 23 Bookly plugins
```

**Why layered:**
- Base plugin update → rebuild `golden-base` → all profile images auto-rebuild (shared layer)
- Profile plugin update → rebuild ONLY that profile image
- Storage: shared base layer cached by Docker (NOT duplicated 8x)
- Deploy: container starts with ALL plugins extracted → first-boot activates → **< 30 seconds**
- Build on demand: don't build all 8 profiles on day 1. Build as you need them.

**Start with:**
1. `fabrik/wp-golden-base:v1` (always)
2. `fabrik/wp-golden-company:v1` (ocoron.com is Company preset)
3. Others built when you create that site type for the first time

### First-Boot Script (runs once per fresh site)

```
┌─────────────────────────────────────────────────────────┐
│ templates/wordpress/golden/first-boot.sh                │
│                                                         │
│ 1. wp core install (creates tables, admin user)         │
│ 2. wp plugin activate --all (activates pre-extracted)   │
│ 3. wp option update (RankMath base config)              │
│ 4. wp option update (FlyingPress base config)           │
│ 5. wp option update (Complianz base config)             │
│ 6. wp option update (Polylang: EN + TR, directory URLs) │
│ 7. wp option update (AutoPoly: DeepL API key from env)  │
│ 8. wp rewrite structure '/%postname%/'                  │
│ 9. Mark complete: touch .golden-initialized             │
│                                                         │
│ Time: ~15 seconds (all plugins already on disk)         │
└─────────────────────────────────────────────────────────┘
```

After first-boot, the 13-stage deployer runs normally (settings, brand, pages, menus, SEO, analytics, monitoring, verify) — but Stage 3 (theme) only applies brand, Stage 4 (plugins) is SKIPPED entirely (all plugins already active from first-boot).

### Per-Site Variables (NOT in any image layer)

Applied at deploy time via env vars + site.yaml:

| Variable | Source | When |
|---|---|---|
| Domain + Traefik labels | site.yaml | Stage 1 |
| Admin user + password | `WP_ADMIN_USER` + `WP_ADMIN_PASSWORD` env | First-boot |
| DeepL API key | `DEEPL_API_KEY` env → AutoPoly settings | First-boot |
| SMTP credentials | `SMTP_*` env vars | Per-site config |
| GA4/GTM IDs | site.yaml | Stage 11 |
| Brand (colors, fonts, logo) | site.yaml | Stage 3 |
| Redis DB index | `WP_REDIS_DATABASE` env | First-boot |
| Table prefix | Generated at scaffold | wp-config |
| Turnstile keys | `TURNSTILE_*` env | Per-site config |
| Content (pages, menus, forms) | site.yaml + presets | Stages 6-8 |

### Build Process

```bash
# 1. Build the golden image
docker build -t fabrik/wp-golden:v1 -f templates/wordpress/golden/Dockerfile .

# 2. Tag + store in local registry (VPS)
docker tag fabrik/wp-golden:v1 localhost:5000/fabrik/wp-golden:v1
docker push localhost:5000/fabrik/wp-golden:v1

# 3. New site compose references it
# image: localhost:5000/fabrik/wp-golden:v1
```

### Dockerfiles (layered)

**Base image** (`templates/wordpress/golden/Dockerfile.base`):

```dockerfile
FROM wordpress:php8.3-fpm-bookworm AS golden-base

# Security: wp-config-extra
COPY templates/wordpress/base/wp-config-extra.php /var/www/html/

# Security: MU-plugins
COPY templates/wordpress/golden/mu-plugins/ /var/www/html/wp-content/mu-plugins/

# Theme
COPY templates/wordpress/golden/themes/generatepress/ /var/www/html/wp-content/themes/generatepress/

# BASE plugins (11): extract to plugins/ (activate via first-boot after DB up)
COPY templates/wordpress/plugins/premium/Base/*.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/Polylang/4v9GYSuEjJbq-polylang-pro_3.8.1.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/Polylang/z8bA9Xx4R9Fr-autopoly-ai-translation-for-polylang-pro.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/Polylang/S4MAzrToWLOA-searchwp-polylang-1.5.0.zip /tmp/plugins/
RUN mkdir -p /var/www/html/wp-content/plugins && \
    cd /var/www/html/wp-content/plugins && \
    for zip in /tmp/plugins/*.zip; do unzip -qo "$zip"; done && \
    rm -rf /tmp/plugins/

# Redis Object Cache drop-in
COPY templates/wordpress/golden/object-cache.php /var/www/html/wp-content/object-cache.php

# First-boot script
COPY templates/wordpress/golden/first-boot.sh /usr/local/bin/first-boot.sh
RUN chmod +x /usr/local/bin/first-boot.sh

# PHP-FPM tuning
COPY templates/wordpress/base/php-fpm/zz-fabrik-listen.conf /usr/local/etc/php-fpm.d/

VOLUME /var/www/html/wp-content
```

**Company profile image** (`templates/wordpress/golden/Dockerfile.company`):

```dockerfile
FROM fabrik/wp-golden-base:v1

# Company profile additions (22 plugins)
COPY templates/wordpress/plugins/premium/Fluent/*.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/Thrive/*.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/AutomatorWP/0wiY9KOz3j8Z-automatorwp-5.5.5.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/AutomatorWP/pQseOoXtVNjS-automatorwp-fluentcrm.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/SearchWP/XGZNZhR1A4Xr-searchwp_4.5.1.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/SearchWP/nAGf2VwSuril-searchwp-metrics-1.5.0.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/ContentSEO/*.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/ConversionMarketing/iKtmhUoUDmc1-pixelyoursite-super-pack-6.1.1.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/ConversionMarketing/ZPKuGMyrc8mT-social-connect-pys-2.0.1.1.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/ConversionMarketing/kHLzVCbLEAij-chaty-pro-3.4.7.zip /tmp/plugins/
COPY templates/wordpress/plugins/premium/ConversionMarketing/fpLjWEJczody-novashare-1.6.3.zip /tmp/plugins/
RUN cd /var/www/html/wp-content/plugins && \
    for zip in /tmp/plugins/*.zip; do unzip -qo "$zip"; done && \
    rm -rf /tmp/plugins/
```

**Build commands:**

```bash
# Build base (once, shared by all profiles)
docker build -f templates/wordpress/golden/Dockerfile.base -t fabrik/wp-golden-base:v1 .

# Build company profile (depends on base)
docker build -f templates/wordpress/golden/Dockerfile.company -t fabrik/wp-golden-company:v1 .

# Build others on demand
docker build -f templates/wordpress/golden/Dockerfile.ecommerce -t fabrik/wp-golden-ecommerce:v1 .
```

**Per-site compose references the profile image:**

```yaml
# Generated by fabrik scaffold --type wordpress --preset company
services:
  wordpress:
    image: fabrik/wp-golden-company:v1  # <-- profile-specific
    # ... rest of compose
```

### Plugin Folder Structure (after reorganization)

```
templates/wordpress/plugins/premium/
├── Base/              (7) — golden image: RankMath, GP Premium, FlyingPress, WP Mail SMTP, WP Staging, Complianz, Object Cache Pro
├── Polylang/          (8) — Polylang Pro, AutoPoly, SearchWP Polylang, Polylang WC, Formidable Polylang, WP Sheet Editor Polylang, AMP (unused)
├── Fluent/            (2) — Forms Pro, Campaign/CRM Pro
├── Thrive/            (11) — Architect, Leads, Ovation, Ultimatum, Comments, Quiz Builder, Headline Optimizer, Clever Widgets, Automator, Apprentice, Theme
├── Bookly/            (32) — PRO + all addons (appointments profile)
├── SearchWP/          (4) — Core, Metrics, WooCommerce, Polylang integration
├── AutomatorWP/       (9) — Core + FluentCRM, WhatsApp, OpenAI, ACF, CSV, AffiliateWP, MemberPress, Thrive Apprentice
├── AffiliateWP/       (9) — Core + Multi-Tier, Portal, Lifetime, Recurring, Custom Slugs, Fraud Prevention, Dashboard Sharing, Product Rates
├── EDD/               (17) — Pro + PayPal, Content Restriction, Free Downloads, Reviews, Custom Prices, Recommended Products, Fraud Monitor, etc.
├── WooCommerce/       (8) — Subscriptions, Table Rate Shipping, Advanced Shipping, FedEx, Photo Reviews, Memberships, Abandoned Cart, WhatsApp
├── MemberPress/       (3) — Core, Corporate
├── AutomateWoo/       (3) — Core, Referrals, Birthdays
├── ContentSEO/        (6) — Link Whisper, Content Egg, Essential Grid, Table Builder, Go Pricing, Testimonial Pro
├── ConversionMarketing/ (9) — PixelYourSite, Chaty, Novashare, ConvertPro, SeedProd, Cart Lift, WhatsApp Rotator
├── Security/          (2) — Wordfence (optional, high-risk sites only)
├── WPML/              (2) — ARCHIVED: replaced by Polylang. Keep for reference only.
└── Misc/              (1) — Fields
```

Build script reads from specific subfolders, NOT `**/*.zip` recursively. This prevents accidentally baking profile-specific plugins into the golden base.

### Golden Base Update Cycle

Plugins get security patches. Image must be rebuilt periodically:

```
Trigger: plugins_latest.json updated (new versions available)
         OR monthly schedule (1st of month)
         OR critical security advisory

Process:
1. scripts/build_golden_base.sh runs
2. Downloads latest plugin zips (or uses bundled)
3. docker build → new tag (fabrik/wp-golden:v1.1)
4. Test: spin up temp site, run verify stage
5. If pass → push to local registry
6. Existing sites: next redeploy picks up new image automatically
7. Watchdog AI can trigger redeploy per-site (staging → test → promote)
```

**Who triggers:** Watchdog AI (monthly cycle) or manual `fabrik golden rebuild`.

## What Changes in the Pipeline

| Stage | Current behavior | With layered golden base |
|---|---|---|
| 1. DNS | Creates/syncs records | SAME (per-site) |
| 2. Settings | blogname, admin user, timezone, permalinks | SAME + runs first-boot if `.golden-initialized` missing |
| 3. Theme | Install + activate + brand | **BRAND ONLY:** theme pre-installed. Just Customizer API calls. |
| 4. Plugins | Install ALL from scratch | **SKIPPED ENTIRELY:** all plugins already extracted + activated by first-boot |
| 5-13 | Per-site content, SEO, analytics, monitoring | SAME (always per-site) |

**Net timing:**

| Phase | Current | With layered golden base |
|---|---|---|
| Container start | ~30s | ~5s (image layers cached locally) |
| First-boot (activate all pre-extracted plugins + base config) | — | ~15s (one-time per fresh site) |
| Stage 3 (theme) | ~60s (download + install) | ~3s (Customizer API: colors + fonts) |
| Stage 4 (plugins) | ~120s (download 20+ plugins) | **0s (SKIPPED — all active from first-boot)** |
| Stages 5-13 | ~120s | ~120s (unchanged — REST API calls) |
| **Total** | **~330s (5.5 min)** | **~143s (~2.5 min) first deploy** |

Second+ site with same profile: image already pulled → even faster (~130s).

## Preview/Promote Integration

Golden base supports the preview flow (ticket 2.7):

```
fabrik wp preview <site>
  → docker compose up with golden image on temp subdomain (preview-<hash>.vps1.ocoron.com)
  → first-boot runs
  → stages 2-13 run against preview domain
  → preview link shared

fabrik wp promote <site>
  → DNS switches to real domain
  → Traefik labels update
  → Search engine registration fires
  → Content pipeline starts
  → Preview container destroyed
```

## Dependencies

| Dependency | Status | Blocker? |
|---|---|---|
| `FABRIK_EXEC_MODE=local` | Not implemented | YES — first-boot script runs on VPS |
| Polylang Pro + AutoPoly zips in premium/ | ✅ DONE — added to `Polylang/` subfolder | — |
| `WP_ADMIN_PASSWORD` env var | Must be set per-site (32-char CSPRNG) | First-boot + REST API stages crash without it |
| `DEEPL_API_KEY` env var | Must be set | AutoPoly needs it for auto-translation |
| VPS DNS Manager running | ✅ Production | Domain provisioning requires it |
| Redis-main running | ✅ Production | Object cache requires it |
| Cloudflare zone activation (async) | N/A for golden base build | Only matters at deploy time (can take minutes for new domains) |

### AI Agents for Development (NOT in WordPress sites — for building the factory)

The golden base and factory infrastructure is BUILT using AI coding agents:

| Agent | Auth | Rules file | Role |
|---|---|---|---|
| **Claude Code** | Owner authenticates via OAuth chain (one-time) | `CLAUDE.md` | Primary coding agent. Complex/critical tickets. |
| **Kilo CLI** | Owner provides `KILO_API_KEY` | `KILO_CLI_RULES.md` (loaded via `opencode.json` `instructions:` array) | Simple/medium tickets. Free tier preferred. |

No `ANTHROPIC_API_KEY` needed in WordPress sites. Translation is handled by AutoPoly (DeepL). Content generation is handled by the SEO→TCO pipeline (separate services, not embedded in WP). The AI agents work on the FABRIK CODEBASE, not inside WordPress.
| Redis-main running on VPS | ✅ Running | No |
| Traefik running on VPS | ✅ Running | No |
| Local Docker registry on VPS | Not set up | Mild — can use local image without registry |
| Plugin activation notes | ✅ Available | No |
| `62-wordpress.md` rules reviewed | ✅ Done | No |

## Files to Create / Modify

| Action | File | What |
|---|---|---|
| CREATE | `templates/wordpress/golden/Dockerfile` | Golden base image recipe |
| CREATE | `templates/wordpress/golden/first-boot.sh` | One-time activation + configuration |
| CREATE | `templates/wordpress/golden/mu-plugins/` | Security MU-plugins (hardcoded, no per-site config) |
| CREATE | `templates/wordpress/golden/object-cache.php` | Redis drop-in configured for env-based host/prefix |
| CREATE | `scripts/build_golden_base.sh` | Build + tag + test + push the golden image |
| MODIFY | `templates/wordpress/base/compose.yaml.j2` | Image: `fabrik/wp-golden:v1` instead of `wordpress:php8.3-fpm-bookworm` |
| MODIFY | `templates/wordpress/base/compose-coolify.yaml.j2` | Same image change |
| MODIFY | `src/fabrik/wordpress/deployer.py` | Run first-boot if not initialized. Skip theme install. Reduce plugin stage to additions only. |
| MODIFY | `src/fabrik/wordpress/stages/theme.py` | Remove install logic, keep Customizer brand application |
| MODIFY | `src/fabrik/wordpress/stages/plugins.py` | Only install ADDITIONS beyond base. Use local zips (mounted volume). |
| MODIFY | `src/fabrik/wordpress/manifests/plugins.py` | Split: BASE (skip) vs ADDITIONS (install) |
| MODIFY | `templates/wordpress/plugins_latest.json` | Becomes golden base version manifest (triggers rebuild) |

## Acceptance Criteria

### Base image (`fabrik/wp-golden-base:v1`)
- [ ] `docker build -f Dockerfile.base` succeeds
- [ ] 11 BASE plugin folders exist in `wp-content/plugins/` (verify: `ls` in container)
- [ ] MU-plugins present (REST block, footprint removal, enumeration block)
- [ ] wp-config-extra.php present with all security constants
- [ ] GeneratePress theme in `wp-content/themes/`

### Profile image (e.g., `fabrik/wp-golden-company:v1`)
- [ ] `docker build -f Dockerfile.company` succeeds (inherits from base)
- [ ] 33 total plugin folders in `wp-content/plugins/` (11 base + 22 company)
- [ ] Image size < 1.5GB

### First-boot (fresh site from profile image)
- [ ] Container start + first-boot reaches wp-login.php in < 30 seconds
- [ ] `wp plugin list --status=active` shows ALL 33 plugins active (company example)
- [ ] Polylang: EN + TR languages active, `/en/` + `/tr/` URLs work
- [ ] AutoPoly: connected to DeepL (verify via settings page or API test)
- [ ] RankMath modules: sitemap, instant-indexing, rich-snippet, image-seo, redirections ON; analytics OFF
- [ ] FlyingPress: page cache active
- [ ] Redis: `wp redis status` → Connected

### Security (every fresh container)
- [ ] DISALLOW_FILE_EDIT active (`wp config get`)
- [ ] xmlrpc.php returns 444 (`curl`)
- [ ] /uploads/ PHP blocked (`curl test.php` → 403)
- [ ] Security headers present (`curl -I`)
- [ ] REST /users returns 403 for anon
- [ ] wp_generator meta removed (view source)
- [ ] Custom table prefix (not `wp_`)
- [ ] Admin user has 32-char password

### Full deploy
- [ ] `fabrik wp apply` with golden base: Stage 4 (plugins) SKIPPED, all 13 stages pass in < 150 seconds
- [ ] Preview mode: temp subdomain accessible, promote switches to real domain
- [ ] Rebuild: `scripts/build_golden_base.sh` builds base + profile, old sites unaffected until redeploy
