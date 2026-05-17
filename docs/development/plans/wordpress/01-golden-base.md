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
| Redis Object Cache | Installed, configured: `WP_REDIS_HOST=redis-main`. Per-site isolation via `WP_REDIS_PREFIX` + `WP_REDIS_DATABASE` (injected at deploy time from env) |
| Complianz Pro | Installed, base GDPR banner configured (geo-targeting, cookie categories). Per-site: domain, policy URLs |
| Cloudflare Turnstile | Installed, NOT configured (site key + secret are per-site) |
| Polylang Pro | Installed + activated. EN + TR registered. URL: `/en/`, `/tr/` directories. Hreflang automatic. String translation enabled. |
| AutoPoly | Installed. Translation provider URL from env `TRANSLATOR_API_URL` (your Translator API, port 18012). Auto-translates on publish. |
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
| AutoPoly | YES | Installed. Connected to your Translator API (DeepL via port 18012) per-site env var `TRANSLATOR_API_URL`. Auto-translates on publish. |
| SearchWP Polylang | YES | Installed. Activates alongside SearchWP. |
| Polylang for WooCommerce | NO (ecommerce profile) | Installed at Stage 4 (plugins) for ecommerce sites only |
| Polylang for AMP | NO (optional) | Only if AMP needed |

**Replaces:** ~~WPML CMS~~, ~~WPML String Translation~~, ~~SearchWP WPML~~. Remove these from all profiles.

**Per-site config (from site.yaml `languages:` section):**
- Which languages active (default: en + tr)
- Default language (default: en)
- URL structure (default: directory /en/, /tr/)
- AutoPoly translation provider URL (default: your Translator API)

## What STAYS OUT (per-site variables, applied at deploy time)

| Variable | Applied by which stage | Source |
|---|---|---|
| Domain name + Traefik labels + SSL | Stage 1 (DNS) | site.yaml `site.domain` |
| WP admin user + password | Stage 2 (Settings) | `WP_ADMIN_USER` + `WP_ADMIN_PASSWORD` env vars |
| blogname, tagline, email, timezone, permalinks | Stage 2 (Settings) | site.yaml `site.*` |
| Brand colors + fonts | Stage 3 (Theme) | site.yaml `brand.*` via Customizer API |
| Profile plugins (e.g., FluentCRM, WooCommerce, Bookly) | Stage 4 (Plugins) — ADDITIONS ONLY | Preset profile → local zips |
| Polylang/WPML locale activation (which languages) | Stage 5 (Languages) | site.yaml `languages.*` |
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

## Implementation: Hybrid Approach (Option C)

Pure Docker image doesn't work: `wp plugin install` needs a running database. Can't RUN in Dockerfile without a DB.

**Approach: Golden image + first-boot provisioning script**

```
┌─────────────────────────────────────────────────────────┐
│ GOLDEN IMAGE (fabrik/wp-golden:v1)                      │
│                                                         │
│ Contains:                                               │
│ • WordPress core files                                  │
│ • wp-config-extra.php (security constants)              │
│ • MU-plugins (security hardening)                       │
│ • Nginx config (hardened)                               │
│ • PHP-FPM config (tuned)                                │
│ • Plugin ZIPs extracted to wp-content/plugins/          │
│   (files present but NOT activated — no DB yet)         │
│ • Theme files in wp-content/themes/                     │
│ • Redis Object Cache drop-in (object-cache.php)         │
│                                                         │
│ Does NOT contain:                                       │
│ • Database (separate container per site)                │
│ • Plugin activations (need DB)                          │
│ • wp_options settings (need DB)                         │
│ • License activations (need per-site keys)              │
└─────────────────────────────────────────────────────────┘
                         +
┌─────────────────────────────────────────────────────────┐
│ FIRST-BOOT SCRIPT (runs once on fresh site)             │
│ templates/wordpress/golden/first-boot.sh                │
│                                                         │
│ 1. wp core install (creates tables, admin user)         │
│ 2. wp plugin activate --all (activates pre-extracted)   │
│ 3. wp option update (RankMath, FlyingPress, Complianz)  │
│ 4. wp rewrite structure '/%postname%/'                  │
│ 5. Mark first-boot complete (touch .golden-initialized) │
│                                                         │
│ Time: ~15 seconds (all local, no downloads)             │
└─────────────────────────────────────────────────────────┘
                         +
┌─────────────────────────────────────────────────────────┐
│ PROFILE ADDITIONS (runs after first-boot)               │
│ Handled by deployer.py Stage 4 (modified)               │
│                                                         │
│ • Reads preset profile → identifies ADDITIONS           │
│ • Installs from local zips (mounted volume, not HTTP)   │
│ • Activates + configures per-profile plugins            │
│ • License activation using keys from activation_notes   │
│                                                         │
│ Time: ~10-30 seconds depending on profile size          │
└─────────────────────────────────────────────────────────┘
```

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

### Dockerfile (realistic)

```dockerfile
FROM wordpress:php8.3-fpm-bookworm

# Security: wp-config-extra
COPY templates/wordpress/base/wp-config-extra.php /var/www/html/

# Security: MU-plugins
COPY templates/wordpress/golden/mu-plugins/ /var/www/html/wp-content/mu-plugins/

# Theme: GeneratePress (extract, don't activate — needs DB)
COPY templates/wordpress/golden/themes/generatepress/ /var/www/html/wp-content/themes/generatepress/
COPY templates/wordpress/golden/themes/flavor/ /var/www/html/wp-content/themes/flavor/

# BASE plugins: extract zips to plugins/ (don't activate — needs DB)
COPY templates/wordpress/plugins/premium/generatepress-premium-*.zip /tmp/
COPY templates/wordpress/plugins/premium/seo-by-rank-math-pro-*.zip /tmp/
COPY templates/wordpress/plugins/premium/flyingpress-*.zip /tmp/
COPY templates/wordpress/plugins/premium/wp-mail-smtp-pro-*.zip /tmp/
COPY templates/wordpress/plugins/premium/wp-staging-pro-*.zip /tmp/
COPY templates/wordpress/plugins/premium/complianz-gdpr-premium-*.zip /tmp/
RUN cd /var/www/html/wp-content/plugins && \
    for zip in /tmp/*.zip; do unzip -qo "$zip"; done && \
    rm /tmp/*.zip

# Redis Object Cache drop-in
COPY templates/wordpress/golden/object-cache.php /var/www/html/wp-content/object-cache.php

# First-boot script
COPY templates/wordpress/golden/first-boot.sh /usr/local/bin/first-boot.sh
RUN chmod +x /usr/local/bin/first-boot.sh

# Nginx config (will be mounted per-site but base is baked)
COPY templates/wordpress/base/nginx/default.conf.j2 /etc/nginx/templates/

# PHP-FPM tuning
COPY templates/wordpress/base/php-fpm/zz-fabrik-listen.conf /usr/local/etc/php-fpm.d/

# Volume: only wp-content (per 62-wordpress.md)
VOLUME /var/www/html/wp-content
```

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

| Stage | Current behavior | With golden base |
|---|---|---|
| 1. DNS | Creates/syncs records | SAME (per-site) |
| 2. Settings | blogname, admin user, timezone, permalinks | SAME (per-site) + runs first-boot if `.golden-initialized` missing |
| 3. Theme | Install + activate + brand | **REDUCED:** only apply brand colors/fonts (theme pre-installed) |
| 4. Plugins | Install ALL from scratch | **REDUCED:** only install PROFILE ADDITIONS from local zips |
| 5-13 | Per-site content, SEO, analytics, monitoring | SAME (always per-site) |

**Net timing:**

| Phase | Current | With golden base |
|---|---|---|
| Container start | ~30s | ~10s (image layers cached) |
| First-boot (activate + configure base) | — | ~15s (one-time) |
| Stage 3 (theme) | ~60s (download + install) | ~5s (just Customizer API calls) |
| Stage 4 (plugins) | ~120s (download 20+ plugins) | ~15s (install 10-15 ADDITIONS from local zips) |
| Stages 5-13 | ~120s | ~120s (unchanged — REST API calls) |
| **Total** | **~330s (5.5 min)** | **~165s (2.75 min) first site, ~90s subsequent** |

After first site on VPS: image layers cached, first-boot already has pattern — subsequent sites even faster.

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
| Polylang Pro + AutoPoly zips in premium/ | DECIDED — need to add zips | Add 5 Polylang zips to `templates/wordpress/plugins/premium/` |
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

- [ ] `docker build` succeeds for golden image
- [ ] Fresh container + first-boot reaches wp-login.php in < 30 seconds
- [ ] All 10 security layers verified on fresh golden container:
  - [ ] DISALLOW_FILE_EDIT active (`wp config get`)
  - [ ] xmlrpc.php returns 444 (`curl`)
  - [ ] /uploads/ PHP blocked (`curl test.php` → 403)
  - [ ] Security headers present (`curl -I`)
  - [ ] REST /users returns 403 for anon
  - [ ] wp_generator meta removed (view source)
  - [ ] Custom table prefix (not `wp_`)
  - [ ] Rate limiting on wp-login (ab test)
  - [ ] WP_HTTP_BLOCK_EXTERNAL blocks outbound test
  - [ ] Admin user has 32-char password
- [ ] All BASE plugins active: `wp plugin list --status=active` shows 8
- [ ] RankMath modules verified: sitemap, instant-indexing, rich-snippet, image-seo, redirections ON; analytics OFF
- [ ] FlyingPress page cache active
- [ ] Redis connected: `wp redis status` → Connected
- [ ] Profile additions install in < 30 seconds from local zips
- [ ] `fabrik wp apply` with golden base: all 13 stages pass in < 90 seconds (excluding DNS wait for new domains)
- [ ] Preview mode works: temp subdomain accessible, promote switches to real domain
- [ ] Golden base rebuild: `scripts/build_golden_base.sh` produces new tagged image, old sites unaffected until redeploy
