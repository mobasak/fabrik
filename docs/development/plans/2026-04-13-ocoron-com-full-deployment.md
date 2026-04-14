# ocoron.com — Full Deployment Plan (Fresh Start)

**Created:** 2026-04-13
**Status:** IN_PROGRESS — Phase 2 complete, Phase 4 in progress (2026-04-14)
**Purpose:** Deploy ocoron.com end-to-end as the reference run for fully automated WordPress site creation. Every gap found here becomes a code fix that benefits all future sites.

---

## Pipeline Architecture

This deployment exercises the **complete automated pipeline**:

```
site-provisioner  →  Coolify (fresh WP container)  →  fabrik wp apply (12 stages)
     ↓                                                      ↓
DNS + CDN + WAF                        dns → settings → theme → plugins → languages
GSC + Bing + IndexNow                  pages → menus → forms → seo
GA4 property                           post_deploy → analytics → monitoring
                                                    ↓
                                    SEO/TCO pipeline → content publish
                                                    ↓
                                        fabrik wp verify
```

---

## Site Template YAML (Canonical)

Every WordPress site in Fabrik starts from `templates/wordpress/base/site.yaml.j2`.
This is the **scaffold template** — `fabrik scaffold <name> --type wordpress` renders it into `specs/sites/<domain>.yaml` (or a project folder's `site.yaml`).

**File:** `@/opt/fabrik/templates/wordpress/base/site.yaml.j2`

Key sections every site spec must have for the full pipeline to run:

| Section | Purpose | Pipeline consumer |
|---|---|---|
| `site.domain` | Primary domain | all stages |
| `brand.*` | Name, tagline, colors, logo | theme, seo, pages |
| `languages.*` | Primary + additional locales | languages, pages, menus |
| `contact.*` | Email, phone, full address | forms, seo (LocalBusiness schema), footer |
| `services/features/products` | Entity list → generates pages | pages, menus, seo |
| `plugins.add/skip/config` | Additions/removals to preset stack | plugins |
| `forms.contact.*` | Contact form field definitions | forms |
| `seo.*` | Meta, archives_noindex, breadcrumbs, OG, schema, robots_txt | seo |
| `post_deploy.*` | GSC/Bing/IndexNow/GA4 registration | post_deploy stage |
| `monitoring.uptime_kuma` | Uptime monitor config | monitoring stage |
| `deployment.coolify.service_uuid` | Coolify service UUID for this site | deploy/delete commands |
| `checks.urls` | URLs verified after apply | verify stage |

**Supported presets:**

| Preset | Site type | Primary entity |
|---|---|---|
| `company` | Agency, consultancy, corporate | `services` |
| `saas` | SaaS marketing site | `features`, `pricing_tiers`, `use_cases` |
| `content` | SEO/authority blog | `authors`, `categories` |
| `landing` | Single-page campaign | none |
| `ecommerce` | WooCommerce store | `products`, `collections` |

**ocoron.com uses:** `company` preset, `services` entities (8 service pages).

---

## Pre-Flight Checklist

Run before any `fabrik wp` command or container operations:

```bash
# 1. All 5 containers running?
ssh vps "sudo docker ps | grep ocoron-com"
# Expected: nginx, wordpress, db (healthy), redis (healthy), backup

# 2. WP-CLI installed in container? (ephemeral — lost on restart)
ssh vps "sudo docker exec ocoron-com-wordpress-1 wp --info --allow-root 2>&1 | head -1"
# If missing:
# ssh vps "sudo docker exec ocoron-com-wordpress-1 sh -c 'curl -sO https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && chmod +x wp-cli.phar && mv wp-cli.phar /usr/local/bin/wp'"

# 2b. WP core installed? (fresh volume = no tables)
ssh vps "sudo docker exec ocoron-com-wordpress-1 wp core is-installed --allow-root 2>&1"
# If not: run Step 2.5 below before fabrik wp apply

# 3. Required env vars set?
grep "WP_ADMIN_PASSWORD\|GA4_ID\|GA4_ACCOUNT_ID\|SITE_PROVISIONER_API_KEY\|SITE_PROVISIONER_INTERNAL_URL\|VPS_IP" /opt/fabrik/.env

# 4. site-provisioner reachable via SSH proxy?
ssh vps "curl -s -H 'X-API-Key: $(grep SITE_PROVISIONER_API_KEY /opt/fabrik/.env | cut -d= -f2)' http://10.0.1.30:8001/health"

# 5. DNS resolving to VPS?
dig +short ocoron.com

# 6. DB volume is fresh (no stale credentials)?
ssh vps "sudo docker exec ocoron-com-db-1 mysql -u wp_user -p\$(grep OCORON_DB_PASSWORD /opt/fabrik/.env | cut -d= -f2) -e 'SELECT 1;' 2>&1"

# 7. Code gaps fixed?
grep "post_deploy\|monitoring" /opt/fabrik/src/fabrik/wordpress/deployer.py
```

---

## Current State (Updated 2026-04-14)

| Item | State | Action |
|---|---|---|
| Coolify service UUID | `acc0k8o0gk08g080wwsoggk4` | Active — project "WordPress Sites" |
| WP container | `ocoron-com-wordpress-1` php8.3-fpm, fresh volumes | Running |
| nginx container | `ocoron-com-nginx-1` nginx:stable-alpine | Running |
| db container | `ocoron-com-db-1` mariadb:10.11, healthy | Running |
| redis container | `ocoron-com-redis-1` redis:7-bookworm, healthy | Running |
| backup container | `ocoron-com-backup-1` debian:bookworm-slim | Running |
| WP-CLI | Manually installed in fpm container | Ephemeral — lost on restart |
| Active theme | Not yet set — fresh install | Will be set by settings stage |
| `WP_ADMIN_PASSWORD` in .env | **SET** | ✅ |
| `GA4_ID` in .env | **MISSING** | Set after Phase 3 |
| `GA4_ACCOUNT_ID` in .env | **MISSING** | Required for post_deploy stage |
| `SITE_PROVISIONER_INTERNAL_URL` in .env | `http://10.0.1.30:8001` | ✅ SSH-proxy for WSL DNS calls |
| DNS stage | ✅ PASSING | |
| Settings stage | Running 2026-04-14 | In progress |

---

## Code Gaps — Verified Against Source (16 Total)

All gaps verified by reading actual stage source, not assumptions. Fix before `fabrik wp apply`.

### Gap 1 — `seo.py`: 5 spec keys read nowhere in code (silent skips)

`SEOApplicator.apply_site_seo()` handles only: `title_template`, `meta_description`, `schema.type` (read only, not injected), `google_verification`.

**Not read or acted on anywhere:**

| Spec key | Required action | WP-CLI / RankMath call |
|---|---|---|
| `seo.archives_noindex` | Set tags/author/date archives to noindex | `wp option update rank_math_titles '{"noindex_archive_date":1,"noindex_archive_author":1}'` |
| `seo.breadcrumbs` | Enable RankMath breadcrumbs | `wp option update rank_math_general '{"breadcrumbs":1}'` |
| `seo.og_enabled` | Enable Open Graph | `wp option update rank_math_titles '{"social_networks":1}'` |
| `seo.twitter_card` | Set Twitter card type | `wp option update rank_math_titles '{"twitter_card_type":"summary_large_image"}'` |
| `seo.robots_txt.allow_ai_crawlers` | Append Allow rules for GPTBot etc | `wp rewrite flush` then write to robots.txt via WP option or file |

Also: `configure_sitemap()` exists in `seo.py` but is **never called** from `stages/seo.py`. Sitemap is not explicitly enabled.

Also: `add_schema_markup()` is a stub — returns `True`, does nothing. LocalBusiness JSON-LD is never injected.

**Fix:** Add 5 methods to `SEOApplicator`, call `configure_sitemap()`, call all 5 new methods from `stages/seo.py apply()`.

### Gap 2 — `stages/monitoring.py` does not exist

`deployer.py` line 198: `stages = (dns, settings, theme, plugins, languages, pages, menus, forms, seo, analytics)`. No monitoring stage.
`UptimeKumaClient` exists at `src/fabrik/drivers/uptime_kuma.py` with `add_http_monitor()` but is never called from the pipeline.
Spec key `monitoring.uptime_kuma` is never read.

**Fix:** Create `src/fabrik/wordpress/stages/monitoring.py`, register after analytics in `deployer.py`.

### Gap 3 — `stages/post_deploy.py` does not exist

No post-deploy stage in the pipeline. `DNSClient.provision()` with GSC/Bing/IndexNow/GA4 flags exists in `drivers/dns.py` but is never called automatically after WordPress is live.
Spec key `post_deploy.*` is never read.

**Fix:** Create `src/fabrik/wordpress/stages/post_deploy.py`, register before analytics in `deployer.py`.

### Gap 4 — GA4 measurement ID feedback loop

`post_deploy` stage will call `DNSClient.provision(setup_ga4=True)` and get back a `ga4_measurement_id`. That ID must be written to the build artifact and consumed by the analytics stage if `seo.ga4_id` is empty in spec.

**Current stage order in deployer.py:** `analytics` runs before `post_deploy` exists.
**Required stage order:** `dns → settings → theme → plugins → languages → pages → menus → forms → seo → post_deploy → analytics → monitoring`

**Fix:** Reorder stages in `deployer.py` after creating post_deploy and monitoring.

### Gap 5 — Forms: `forms.contact.fields` (rich spec) vs `contact.form_fields` (stage reads)

`stages/forms.py` reads `contact.form_fields` — a flat list of slug strings.
The richer `forms.contact.fields` object structure in `site.yaml.j2` is **not consumed** by any stage code.

**Workaround in spec now:** Both `ocoron.com.v2.yaml` and `site.yaml.j2` include `contact.form_fields: [name, email, phone, message]` so the current stage works. Dynamic field definitions under `forms.contact.fields` are future work.

### Gap 6 — `seo.ga4_id` key path mismatch (was silent failure — now fixed in spec)

`stages/analytics.py` reads `spec["seo"]["ga4_id"]` (flat). Previous ocoron spec had it at `seo.analytics.ga4_id`. Stage silently skipped GA4 injection.

**Fixed:** Both `ocoron.com.v2.yaml` and `site.yaml.j2` now use `seo.ga4_id` flat key. Also `seo.gtm_id` added.

### Gap 7 — `stages/dns.py` uses `domain_setup.py` (old httpx direct calls), not `DNSClient`

`stages/dns.py` → `wordpress/domain_setup.py` → raw `httpx` calls to legacy endpoint structure.
`drivers/dns.py` (`DNSClient`) with correct `X-API-Key` auth and current endpoints is **never used by the pipeline**.
All DNS work done on `DNSClient` in previous sessions bypasses the actual dns stage.

**Fix:** Update `domain_setup.py` to use `DNSClient` internally, or rewrite `stages/dns.py` to call `DNSClient.provision()` / `DNSClient.add_subdomain()` directly.

### Gap 8 — Admin username `admin` never renamed (62-wordpress.md violation)

`stages/settings.py` creates an **editor** account from `contact.email`. Does not touch the existing `admin` user.
`security.admin_username` in spec is never consumed by any stage.

**Fix:** In `stages/settings.py`, after `applicator.apply_settings(spec)`, read `spec["security"]["admin_username"]` and call `wp user update 1 --user_login=<username>` if it differs from `admin`.

### Gap 9 — No Makefile generated by WordPress scaffold

`_scaffold_wordpress()` in `scaffold.py` copies base template files but generates no Makefile.
`62-wordpress.md` mandates Makefile with targets: `update`, `cache-flush`, `scaffold`, `backup`, `harden`, `security-check`.
`Makefile.python` and `Makefile.node` exist in `templates/scaffold/docker/` but no `Makefile.wordpress`.

**Fix:** Create `templates/scaffold/docker/Makefile.wordpress` with WP-CLI targets. Add to `_scaffold_wordpress()` at step (h).

### Gap 10 — `compose-coolify.yaml.j2` mounts full web root (62-wordpress.md violation) — **FIXED 2026-04-13**

~~Current template (both `compose.yaml.j2` and `compose-coolify.yaml.j2`):~~

**Fixed:** `wordpress_root` volume removed from `compose-coolify.yaml.j2`. WordPress service now mounts only `wp_content:/var/www/html/wp-content`. Nginx also updated to mount only `wp_content:ro`. `www-data:www-data` (UID 33) ownership set via `command` entrypoint override in the compose template.

### Gap 11 — `nginx/default.conf.j2` FastCGI cache uses `/tmp/wp_cache` (banned path) — **FIXED 2026-04-13**

**Fixed:** Path changed to `/var/cache/nginx/wp_cache` in `templates/wordpress/base/nginx/default.conf.j2`. This is within the Nginx container filesystem, not shared across containers, and survives Nginx restarts.

### Gap 12 — `STAGE_KEYS` in `planner.py` and `spec_validator` don't know about new stages

`STAGE_KEYS` in `src/fabrik/wordpress/planner.py` drives hash-based stage-skip logic (idempotent re-runs). Currently:

```python
STAGE_KEYS = {
    "dns": [...], "settings": [...], ..., "analytics": [...]
    # post_deploy and monitoring are MISSING
}
```

When `post_deploy` and `monitoring` are added to `deployer.py`, `planner.py` must also get their entries:

```python
"post_deploy": ["post_deploy", "site"],
"monitoring": ["monitoring", "site"],
```

Similarly, `spec_validator` validates `schema_version`, `site.domain`, `brand.name`, `contact.email`, `languages.primary`, `deployment.target` — but never checks `security.admin_username` format or warns if `post_deploy.ga4_account_id` is missing when `setup_ga4=True`. These silent spec gaps cause runtime errors, not validation errors.

**Fix:** Add `post_deploy` and `monitoring` to `STAGE_KEYS`. Add optional warnings to `spec_validator` for `security.admin_username != "admin"` and `post_deploy.ga4_account_id` presence.

### Gap 16 — `user_login` is immutable in WordPress — **DISCOVERED 2026-04-14**

`settings.py` tried `wp user update 1 --user_login=ocoronadm` which silently fails (`User logins can't be changed`). The admin username was never actually replaced.

**Fix:** Create new admin user with desired username → reassign all content from old user (ID 1) → delete old `admin` user. Implemented in `stages/settings.py` 2026-04-14.

### Gap 15 — Wrong plugin slugs in `defaults.yaml` — **DISCOVERED 2026-04-14**

`defaults.yaml` had `generatepress` and `gp-premium` in `plugins.base` — but GeneratePress is a **theme**, not a plugin. `rank-math-seo` is also wrong — the actual wordpress.org slug is `seo-by-rank-math`.

**Fix (applied 2026-04-14):**
- Removed `generatepress` from `plugins.base` (installed by theme stage)
- Removed `gp-premium` from `plugins.base` (premium ZIP, not on wordpress.org)
- Changed `rank-math-seo` → `seo-by-rank-math`

### Gap 14 — Pipeline assumes WP core is already installed — **DISCOVERED 2026-04-14**

`stages/settings.py` runs WP-CLI against the container immediately. On a fresh volume, MariaDB starts empty — WordPress tables don't exist yet. Every WP-CLI call fails with `The site you have requested is not installed. Run wp core install`.

The pipeline has no install step. This means **`wp core install` must be run manually as Phase 2 Step 2.5** before `fabrik wp apply`. Alternatively, the `settings` stage should check `wp core is-installed` first and run `wp core install` with spec values if not.

**Spec keys needed for core install:**
- `site.url` → `--url`
- `brand.name` → `--title`
- `security.admin_username` → `--admin_user`
- `WP_ADMIN_PASSWORD` env var → `--admin_password`
- `contact.email` → `--admin_email`

**Fix (two options):**
1. Add auto-install check to top of `stages/settings.py` (preferred — fully automated)
2. Document manual step in pre-flight checklist (workaround)

### Gap 13 — Duplicate `contact:` top-level key in `site.yaml.j2` (YAML parse bug — now fixed)

`site.yaml.j2` had `contact:` at line 55 (email/phone/address) AND again at line 129 (form_fields). YAML parsers silently drop the first key when a duplicate exists — meaning `email`, `phone`, `address` would all be lost, only `form_fields` surviving.

**Fixed:** `form_fields` merged into the first `contact:` block. Second `contact:` block removed. `ocoron.com.v2.yaml` was already clean (single `contact:` block with `form_fields` inside it).

---

## Key Invariants

1. **Delete first, then recreate** — the existing container has dirty state (wrong permalinks, wrong theme). A fresh container is the only clean baseline.
2. **`WP_ADMIN_PASSWORD` must be set before apply** — REST API (`WordPressAPIClient`) is `None` when absent; pages stage silently creates 0 pages.
3. **Code gaps must be fixed before apply** — running apply with gaps means stages succeed but do nothing for the missing features.
4. **`languages` stage must run before `pages`** — Polylang must be installed and active before pages are created or they have no language assignment.
5. **`post_deploy` runs after WordPress is verified live** — site-provisioner needs real HTTP responses for GSC verification.
6. **Every workaround gets committed** — this is the reference run; shortcuts not reflected in code are not automation.

---

## Failure Modes

| Scenario | Symptom | Resolution |
|---|---|---|
| `WP_ADMIN_PASSWORD` blank | Pages stage: 0 pages, no error | Set in `.env`, `--force-stage pages` |
| Polylang not active before pages | Pages have no language, Polylang can't assign retroactively | Ensure languages stage runs first (already correct order) |
| Gap fixes not deployed | SEO stage succeeds but breadcrumbs/OG/robots.txt not configured | Fix gaps first, `--force-stage seo` |
| GA4 ID not in `.env` | Analytics stage injects empty string | Get ID from site-provisioner response, set `GA4_ID` in `.env` |
| Container name mismatch | WP-CLI stages crash on connection | Verify `docker ps` name matches `{site.name}-wordpress-1` |
| `docker ps` permission denied | ContainerResolver fails silently, `No container found` error | VPS user lacks docker group — driver uses `sudo docker ps` (fixed in drivers/wordpress.py) |
| Stale DB volume | `Error establishing a database connection` | `docker compose down -v` then `up -d` to wipe volumes and reinit with fresh credentials |
| WP-CLI missing in fpm image | `exec: "wp": executable file not found` | `wordpress:php8.3-fpm` has no WP-CLI — install manually or use `-apache` image instead |
| Coolify relative bind mount | Container exits immediately, StartService completes in 450ms but nothing runs | Use absolute paths in compose (e.g. `/opt/ocoron-com/nginx/...`) not `./nginx/...` |
| Coolify varchar(255) env limit | 500 error on service create, SQL error 22001 | Never put multiline `WORDPRESS_CONFIG_EXTRA` in compose env — apply via WP-CLI post-install |
| site-provisioner 403 from WSL | DNS stage fails, `403 Forbidden` | Traefik IP allowlist blocks WSL — set `SITE_PROVISIONER_INTERNAL_URL` and use SSH proxy in DNSClient |
| Coolify StartService queues but no containers | `status: exited` after start | Coolify /start endpoint is GET not POST; also check bind mount paths resolve on VPS host |
| Premium plugin ZIP missing | Plugins stage fails for gp-premium etc. | Check VPS paths; place ZIPs before apply |
| GSC service account not owner | post_deploy GSC verify fails | One-time manual: add service account as GSC owner |

---

## Acceptance Criteria

- [ ] Coolify: old container deleted, fresh container deployed and healthy
- [ ] `/var/www/html/wp-content` owned by `www-data:www-data` (UID 33) — verified via `docker exec stat`
- [ ] `WP_ADMIN_PASSWORD` set (32-char CSPRNG, `[a-zA-Z0-9]`) and REST API returns 200 for `/wp-json/wp/v2/users/me`
- [ ] `fabrik wp plan ocoron.com` exits 0
- [ ] `fabrik wp apply ocoron.com --dry-run` exits 0, all stages print
- [ ] `fabrik wp apply ocoron.com` exits 0, `apply-report.json` shows `overall_success: true`
- [ ] Theme: GeneratePress active with Ocoron brand colors
- [ ] Plugins: full stack installed (rank-math, flyingpress, wordfence, polylang, shortpixel, complianz, fluent-forms)
- [ ] Permalinks: `/%postname%/`
- [ ] Languages: EN + TR registered in Polylang
- [ ] Pages: all 15 pages exist (home, 8 service pages, about, contact, privacy-policy, terms, insights)
- [ ] Menus: header + footer assigned to theme locations
- [ ] Forms: contact form with 5 fields (name, email, phone, service, message)
- [ ] SEO: RankMath active, sitemap at `/sitemap.xml` returns 200
- [ ] SEO: archives (tags/author/date) set to noindex
- [ ] SEO: breadcrumbs enabled
- [ ] SEO: OG + Twitter Card meta configured
- [ ] SEO: LocalBusiness + WebSite JSON-LD injected
- [ ] SEO: robots.txt includes GPTBot/ClaudeBot/PerplexityBot Allow
- [ ] Analytics: GA4 measurement ID injected (not empty)
- [ ] Monitoring: Uptime Kuma HTTP monitor active for `https://ocoron.com`
- [ ] Post-deploy: Bing + IndexNow registered, GSC property created, sitemap submitted
- [ ] `/sitemap.xml` returns HTTP 200
- [ ] `/robots.txt` returns 200 and contains `Allow: /` for GPTBot, ClaudeBot, PerplexityBot
- [ ] Core Web Vitals: LCP < 2.5s (run `lighthouse https://ocoron.com --output json | jq '.audits["largest-contentful-paint"].numericValue'`)
- [ ] Cloudflare Analytics active (verify in CF dashboard → Analytics)
- [ ] `fabrik wp verify ocoron.com` exits 0, all URL checks pass
- [ ] `DISALLOW_FILE_EDIT=true` verified: attempt to edit theme in WP admin returns "File editing disabled"
- [ ] Wordfence firewall mode set to Extended Protection (verify in WP admin → Wordfence → Firewall)
- [ ] Admin username is NOT `admin` — confirmed via `wp user list --allow-root`
- [ ] `xmlrpc.php` returns 444: `curl -sI https://ocoron.com/xmlrpc.php | head -1` returns `444`
- [ ] Backup script configured at `templates/wordpress/base/backup/backup.sh` and VPS cron set
- [ ] Handoff report generated at `build/sites/ocoron.com/reports/handoff.md`

**Not in scope for this deployment (future gaps):**

- **Yandex Webmaster:** `DNSClient.provision()` has no `setup_yandex` flag — not implemented in site-provisioner. Register manually at [webmaster.yandex.com](https://webmaster.yandex.com) until the endpoint is added.
- **FAQ Schema:** `add_schema_markup()` is a stub (Gap 1). FAQ JSON-LD per service page requires `stages/seo.py` to iterate page SEO and inject per-page schema. Future work.

---

## Phase 0 — Fix Code Gaps

**Do this before touching the container or running any `fabrik wp` command.**

### Step 0.1 — Implement Gap 1: `seo.py` missing methods

Add to `src/fabrik/wordpress/seo.py` and wire into `stages/seo.py`.
See Gap 1 table above for exact methods.

### Step 0.2 — Implement Gap 2: `stages/monitoring.py`

```python
# src/fabrik/wordpress/stages/monitoring.py
# Reads spec["monitoring"]["uptime_kuma"]
# Calls UptimeKumaClient.add_http_monitor(url, interval)
# Uses UPTIME_KUMA_URL / UPTIME_KUMA_USERNAME / UPTIME_KUMA_PASSWORD from env
```

Register in `deployer.py` after analytics stage.

### Step 0.3 — Implement Gap 3: `stages/post_deploy.py`

```python
# src/fabrik/wordpress/stages/post_deploy.py
# Reads spec["post_deploy"]
# Calls DNSClient.provision() with setup_google/bing/indexnow/ga4 flags
# Writes returned GA4 measurement_id to build_dir artifact
# Calls DNSClient.update_sitemap(domain, sitemap_url)
```

Register in `deployer.py` as final stage after monitoring.

### Step 0.4 — Implement Gap 4: GA4 feedback loop

After `post_deploy` stage writes `ga4_measurement_id` to build artifact, `analytics` stage must read it if `seo.analytics.ga4_id` is empty. Re-order: `analytics` runs **after** `post_deploy`, or `post_deploy` calls GA4 injection directly.

**Decision:** Move `analytics` to run after `post_deploy`. New stage order:

```python
stages = (dns, settings, theme, plugins, languages, pages, menus, forms, seo, post_deploy, analytics, monitoring)
```

### Step 0.5 — Implement Gap 5: dynamic form fields from spec

`src/fabrik/wordpress/forms.py` — read `spec["forms"]["contact"]["fields"]` to build form fields array instead of hardcoded structure.

---

## Phase 1 — Set Required Env Vars

These must all be set before Phase 2.

```bash
# Edit /opt/fabrik/.env — add/update:
# Generate 32-char CSPRNG password (62-wordpress.md requirement):
WP_ADMIN_PASSWORD=$(python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))")
WP_ADMIN_EMAIL=admin@ocoron.com
GA4_ACCOUNT_ID=<your Google Analytics account ID>
SITE_PROVISIONER_API_KEY=<API_KEY value from site-provisioner .env on VPS>
```

Verify:

```bash
grep "WP_ADMIN_PASSWORD\|GA4_ACCOUNT_ID\|SITE_PROVISIONER_API_KEY" /opt/fabrik/.env
```

---

## Phase 2 — Delete Container + Fresh Deploy via Coolify

### Step 2.1 — Delete existing service via Coolify API

```bash
curl -s -X DELETE \
  -H "Authorization: Bearer $(grep COOLIFY_API_TOKEN /opt/fabrik/.env | cut -d= -f2)" \
  http://172.93.160.197:8000/api/v1/services/zwgsgwkwosws84o4sk4kwkso?delete_volumes=true
```

Verify gone:

```bash
ssh ozgur@172.93.160.197 "sudo docker ps | grep ocoron"
# Should return empty
```

### Step 2.2 — Recreate via Coolify

Use Coolify dashboard or `fabrik deploy` if a `compose.yaml` exists for ocoron.com.

```bash
# Check if ocoron-com compose exists
ls /opt/fabrik/specs/sites/ocoron.com-media/
```

The container must start with:
- `WORDPRESS_ADMIN_USER=admin`
- `WORDPRESS_ADMIN_PASSWORD=<same as WP_ADMIN_PASSWORD in .env>`
- `WORDPRESS_ADMIN_EMAIL=admin@ocoron.com`
- `WORDPRESS_DB_*` credentials

### Step 2.3 — Wait for container healthy

```bash
ssh ozgur@172.93.160.197 "sudo docker ps | grep ocoron"
# ocoron-com-wordpress-1  Up X seconds (healthy)
```

### Step 2.3b — Verify wp-content ownership

```bash
ssh ozgur@172.93.160.197 "sudo docker exec ocoron-com-wordpress-1 stat -c '%U:%G' /var/www/html/wp-content"
# Should return: www-data:www-data
```

### Step 2.4 — Verify REST API accessible

```bash
WP_PASS=$(grep WP_ADMIN_PASSWORD /opt/fabrik/.env | cut -d= -f2)
curl -s -u "admin:${WP_PASS}" https://ocoron.com/wp-json/wp/v2/users/me | python3 -m json.tool | grep '"name"'
```

Must return `"name": "admin"`. If 404: REST API not yet available, wait 30s and retry.

---

## Phase 3 — DNS & Cloudflare (site-provisioner)

Only run if ocoron.com is not already provisioned in Cloudflare.

### Step 3.1 — Verify site-provisioner live

```bash
curl -s https://dns.vps1.ocoron.com/health
fabrik domain zones | grep ocoron
```

If zone exists and DNS is correct → skip to Step 3.3.

### Step 3.2 — Provision (skip if already done)

```bash
fabrik domain provision ocoron.com \
  -s www \
  --setup-google \
  --setup-ga4 --ga4-account-id ${GA4_ACCOUNT_ID} \
  --sitemap-url https://ocoron.com/sitemap.xml
```

### Step 3.3 — Wait for DNS

```bash
fabrik domain ready ocoron.com --wait
```

### Step 3.4 — Record GA4 Measurement ID

```bash
fabrik domain integrations ocoron.com
# → shows ga4.measurement_id — copy it
```

Add to `.env`:
```bash
GA4_ID=G-XXXXXXXXXX   # from above output
```

---

## Phase 4 — Generate Plan + Apply

### Step 4.1 — Plan

```bash
cd /opt/fabrik
fabrik wp plan ocoron.com
```

Verify:
- `build/sites/ocoron.com/plan.json` has 12 stages (including post_deploy + monitoring)
- `build/sites/ocoron.com/blueprint.resolved.yaml` has 8 services, address, forms section

### Step 4.2 — Dry run

```bash
fabrik wp apply ocoron.com --dry-run
```

All 12 stages must print intent. Exit 0.

### Step 4.3 — Real apply

```bash
fabrik wp apply ocoron.com
```

Expected stage order and outcomes:

| # | Stage | Key outcome |
|---|---|---|
| 1 | dns | A record verified, VPS_IP resolves |
| 2 | settings | Permalinks `/%postname%/`, cleanup, editor user |
| 3 | theme | GeneratePress active, brand colors applied |
| 4 | plugins | ~12 plugins installed + active |
| 5 | languages | Polylang active, EN + TR registered |
| 6 | pages | 15 pages created with language assignments |
| 7 | menus | Header + footer menus assigned |
| 8 | forms | Contact form with 5 fields from spec |
| 9 | seo | RankMath configured, archives noindex, breadcrumbs, OG, schema, robots.txt |
| 10 | post_deploy | GSC + Bing + IndexNow + GA4 via site-provisioner, GA4 ID written to artifact |
| 11 | analytics | GA4 measurement ID injected (from post_deploy artifact or GA4_ID env) |
| 12 | monitoring | Uptime Kuma HTTP monitor added |

### Step 4.4 — Fix failed stages

```bash
cat build/sites/ocoron.com/reports/apply-report.json | python3 -m json.tool | grep -A5 '"success": false'

# Re-run specific stage:
fabrik wp apply ocoron.com --force-stage <name>
```

---

## Phase 5 — Verify

```bash
fabrik wp verify ocoron.com
```

Manual spot checks:

```bash
# Sitemap
curl -s -o /dev/null -w "%{http_code}" https://ocoron.com/sitemap.xml

# robots.txt — should contain GPTBot Allow
curl -s https://ocoron.com/robots.txt | grep -i "GPTBot\|ClaudeBot\|PerplexityBot"

# OG tags
curl -s https://ocoron.com/ | grep 'og:title\|og:description\|og:image'

# Schema
curl -s https://ocoron.com/ | python3 -c "import sys,re; print('\n'.join(re.findall(r'application/ld\+json.*?</script>', sys.stdin.read(), re.DOTALL)))" | head -5

# Uptime Kuma
curl -s https://status.vps1.ocoron.com/api/status-page/heartbeat/all | python3 -m json.tool | grep -i ocoron
```

---

## Phase 6 — Content Pipeline

**Prerequisite:** SEO service (`/opt/seo`) and TCO service must be deployed and reachable.

```bash
# Register site
fabrik seo site-register ocoron.com \
  --name "Ocoron" \
  --country-code tr \
  --language-code en

# Create keyword jobs per service
fabrik seo job-create <site_id> "investment incentives turkey kosgeb" --page-type service
fabrik seo job-create <site_id> "foreign trade consulting turkey" --page-type service
# ... one per service

# Run jobs
fabrik seo job-run <job_id>

# Publish briefs → WordPress
fabrik content publish ocoron.com --dry-run --limit 5
fabrik content publish ocoron.com --limit 10

# Resubmit sitemap
fabrik domain sitemap ocoron.com https://ocoron.com/sitemap.xml
```

---

## Execution Order Summary

```
Phase 0:  Fix code gaps (Gaps 1-5) → commit all changes
Phase 1:  Set WP_ADMIN_PASSWORD + GA4_ACCOUNT_ID + SITE_PROVISIONER_API_KEY in .env
Phase 2:  Delete ocoron-com Coolify service → recreate fresh container → verify REST API
Phase 3:  fabrik domain ready ocoron.com --wait
          fabrik domain provision ocoron.com ... (if zone missing)
          Record GA4_ID from integrations output → add to .env
Phase 4:  fabrik wp plan ocoron.com
          fabrik wp apply ocoron.com --dry-run
          fabrik wp apply ocoron.com
          → fix failed stages with --force-stage
Phase 5:  fabrik wp verify ocoron.com
          Manual spot checks (sitemap, robots.txt, OG, schema)
Phase 6:  (after SEO/TCO deployed) fabrik content publish ocoron.com
```

---

## One-Test Rule

**Test:** After Phase 4, verify pages stage end-to-end with language assignment.

```
Given:  WP_ADMIN_PASSWORD set, Polylang active, plan.json exists
When:   SiteDeployer("ocoron.com").deploy() runs pages stage
Then:   15 pages created, each with non-zero post_id
        AND each page has a Polylang language assignment (en or tr)
        AND /services/investment-incentives returns HTTP 200
Mocked: None — integration test against live ocoron-com-wordpress-1
Real:   WordPressAPIClient + WP-CLI inside container
Why:    Silent failure here (0 pages, no error) is the highest-probability
        failure mode and cascades to menus, forms, seo, content pipeline
```
