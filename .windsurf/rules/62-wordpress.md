---
activation: glob
globs: ["**/wp-content/**", "**/wp-config*"]
description: WordPress discipline — security hardening, plugin discipline, WooCommerce, caching, WP-CLI, Docker patterns
trigger: glob
---

# WordPress Rules

Apply when working on WordPress sites — Docker config, theme/plugin work, WooCommerce, or headless CMS integration. Skip for Next.js apps, FastAPI services, or Docusaurus sites.

## When WordPress Does NOT Make Sense

Do not use WordPress when:
- **Custom application logic** is needed (SaaS dashboards, complex state management, data visualisations) — use Next.js + FastAPI + PostgreSQL.
- **Relational data models**, vector embeddings, or JSONB operations are central — use PostgreSQL 16 directly.
- **API-first microservices** for mobile apps — use FastAPI.

WordPress is appropriate for: editorial content sites, WooCommerce e-commerce, or headless CMS feeding a Next.js frontend via WPGraphQL.

## Database

- **MariaDB 10.6+** is the sole authorised database for WordPress. PostgreSQL via translation plugins (pg4wp) is banned — it breaks during core updates and plugin installations.
- MariaDB runs in its own container with a named Coolify volume for `/var/lib/mysql`.

## Docker Images & Architecture

- Use `wordpress:php8.x-fpm-bookworm` — the `php-fpm` variant behind a dedicated Nginx container. The default `wordpress:latest` (Apache) image is banned.
- Lock PHP version in the image tag. The `:latest` tag is banned — it breaks container immutability with unpredictable upstream changes.
- Nginx handles static file serving, FastCGI proxying, caching, and security blocking — all before PHP is invoked.

## Volume Persistence

- Mount **only** `/var/www/html/wp-content` to a named Coolify Docker volume. Never bind-mount the entire `/var/www/html` root — it defeats containerised core updates and causes permission conflicts.
- The `wp-content` volume must be owned by `www-data:www-data` (UID 33). Set ownership via entrypoint script or init container command.
- MariaDB data and Redis data each get their own named volumes.

## Caching

- **Nginx FastCGI Cache** is mandatory for full-page HTML caching. It serves cached responses directly from disk/RAM, bypassing PHP-FPM entirely for anonymous traffic (~40ms TTFB).
- **Cloudflare cache purge before warm:** after bulk content injection or migrations, fire a Cloudflare zone cache purge via API (`DELETE /client/v4/zones/{zone_id}/purge_cache` with `{"purge_everything": true}`) **before** running `make warm-cache`. Failing to purge first means the edge may continue serving stale pre-injection content regardless of the origin warm.
- **Redis Object Cache** via a dedicated Redis container handles database query caching for dynamic/logged-in requests.
- **Redis isolation:** every site must set `define('WP_REDIS_PREFIX', 'sitename:')` and `define('WP_REDIS_DATABASE', 0)` — prevents object cache key collisions when multiple sites share a Redis instance.
- PHP-based caching plugins (WP Rocket, W3 Total Cache, WP Super Cache) are **banned** — they waste CPU invoking PHP just to serve cached pages.
- **WooCommerce cache bypass:** FastCGI cache must be bypassed for `/cart/`, `/checkout/`, `/my-account/`, `?add-to-cart=` URLs, and for requests carrying `woocommerce_items_in_cart` or `wordpress_logged_in` cookies. Failure to do this serves cached cart/checkout pages to wrong users. Implemented in `nginx/default.conf.j2` via `map` directives.
- **GDPR / consent cache poisoning:** if the site uses a cookie consent banner, Nginx must bypass FastCGI cache for visitors who have not yet set a `cookie_consent` cookie — otherwise a page cached without the banner is served to users who haven't consented. Implemented in `nginx/default.conf.j2` via `$skip_cache_consent` map.

## Security Hardening

### wp-config.php (enforced via `wp-config-extra.php` template)

- `define('DISALLOW_FILE_EDIT', true);` — prevents remote code execution if an admin account is compromised.
- `define('DISALLOW_FILE_MODS', true);` — disables plugin/theme installs from dashboard entirely. Stronger than `DISALLOW_FILE_EDIT` alone.
- `define('FORCE_SSL_ADMIN', true);` — forces HTTPS for wp-admin.
- `define('WP_POST_REVISIONS', 5);` — prevents `wp_posts` table bloat.
- `define('DISABLE_WP_CRON', true);` — use system cron instead of PHP-triggered cron.
- `define('WP_DEBUG', true);` + `define('WP_DEBUG_LOG', true);` + `define('WP_DEBUG_DISPLAY', false);` — **`WP_DEBUG` must be `true`** for `WP_DEBUG_LOG` to write anything; `WP_DEBUG_DISPLAY=false` ensures errors never reach visitors.
- `define('WP_HTTP_BLOCK_EXTERNAL', true);` + `define('WP_ACCESSIBLE_HOSTS', 'api.wordpress.org,*.wordpress.org');` — blocks all outbound HTTP requests from WordPress except WP.org (core updates). Prevents compromised plugins from phoning home to C2 servers.
- `define('WP_CACHE', true);` — required to activate object cache drop-in (Redis).
- Inject all secrets (DB credentials, cryptographic salts) via Coolify environment variables. **Never** hardcode secrets in `wp-config.php` or version-controlled files.
- **Custom table prefix:** never use the default `wp_`. Set `$table_prefix` to a unique slug (e.g. `sitename_prod_`) during initial setup. Mitigates automated SQL injection attacks targeting known table names.

### Cloudflare WAF Rules (MANDATORY when Cloudflare proxy is active)

Configure these five rules in Cloudflare WAF in priority order:

| Priority | Target | Action |
|----------|--------|--------|
| 1 | `cf.client.bot` | Skip (allow verified bots) |
| 2 | `http.request.uri.path contains "wp-login.php" and http.request.method eq "POST"` | Managed Challenge |
| 3 | `http.request.uri.path contains "/xmlrpc.php"` | Block |
| 4 | `http.request.uri.path contains "/wp-admin/" and not http.request.uri.path contains "admin-ajax.php"` | Managed Challenge |
| 5 | `ip.src.asnum in {16509 15169 8075 60068}` (VPS/VPN ASNs) | Managed Challenge |

- Exceptions: `admin-ajax.php` and `/wp-json/` must remain accessible for theme features and REST consumers.
- HTTP Security Headers (`Content-Security-Policy`, `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`) must be set via **Cloudflare Transform Rules** to cover all assets (images, CSS) that bypass WordPress entirely.

### HTTP Security Headers (enforced at Nginx origin)

Add to `nginx/default.conf.j2` server block:

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header X-XSS-Protection "1; mode=block" always;
```

- `Content-Security-Policy` and `Strict-Transport-Security` go in Cloudflare Transform Rules, not Nginx — they must cover static assets that Nginx serves directly without invoking WordPress.

### REST API Hardening (MANDATORY)

- Block `/wp-json/wp/v2/users` and `/wp-json/wp/v2/users/*` at the Nginx level (`return 403`) — prevents author name scraping for brute-force attacks.
- For headless setups, restrict all `/wp-json/` writes to authenticated requests (JWT or Application Password). See §Headless CMS.
- `robots.txt` must explicitly block: `/wp-admin/`, `/wp-includes/`, `/wp-content/plugins/` from indexing.
- **Application Password for automation:** when n8n or any external pipeline pushes content via REST API, create a dedicated Application Password (never reuse the admin password): `wp user application-password create <admin_user> "n8n_automation" --allow-root`. Capture the token and store it in the Fabrik vault or n8n credential store — never in version control.
- **Block unauthenticated REST writes via MU-plugin:** drop an MU-plugin at `/wp-content/mu-plugins/block-anon-rest.php` that returns `WP_Error` for any non-GET REST request from unauthenticated users. This hardens beyond the single users-endpoint block at Nginx level.

### Block xmlrpc.php (MANDATORY — brute-force attack vector)

- Block at the **web server level** so PHP is never invoked. Two options depending on stack:
  - **Nginx (FPM stack):** `location = /xmlrpc.php { return 444; }` — drops the connection.
  - **Traefik (Apache stack / current templates):** Add middleware labels to `compose.yaml`:

```yaml
# Block xmlrpc.php via Traefik middleware
- "traefik.http.middlewares.{{ name }}-block-xmlrpc.replacepathregex.regex=^/xmlrpc\\.php$$"
- "traefik.http.middlewares.{{ name }}-block-xmlrpc.replacepathregex.replacement=/wp-login.php?blocked=xmlrpc"
```

- Do **not** rely on a WordPress plugin for xmlrpc blocking — traffic must be dropped before it reaches PHP.

### Rate-limit wp-login.php (MANDATORY)

- Add Traefik rate-limiting middleware to `compose.yaml` for the login endpoint:

```yaml
# Rate-limit wp-login.php (10 requests/minute per IP)
- "traefik.http.middlewares.{{ name }}-rate-limit.ratelimit.average=10"
- "traefik.http.middlewares.{{ name }}-rate-limit.ratelimit.burst=20"
- "traefik.http.middlewares.{{ name }}-rate-limit.ratelimit.period=1m"
```

### Admin Account Hardening (MANDATORY post-deploy)

- **Never use `admin` as the username.** Create a unique admin username during scaffold or rename immediately after install.
- Admin password must be **32 characters, CSPRNG** (`secrets.choice()` over `[a-zA-Z0-9]`). The password policy from `.windsurfrules` applies.
- Limit admin accounts to exactly **one** per site. Additional users get Editor role maximum.

### Security Plugin (MANDATORY)

- **Wordfence** is the selected security plugin (included in `defaults.yaml` base stack and available as premium ZIP).
- Must be installed and activated on every site immediately after deploy: `wp plugin install wordfence --activate --allow-root`.
- Enable: brute-force protection, login rate limiting, file integrity monitoring, malware scan.
- Wordfence firewall mode must be set to **Extended Protection** after initial setup.
- **Brute-force lockout:** lock after **5 failed attempts**; immediately block any login attempt using username `admin`.
- **2FA:** enable two-factor authentication for all Administrator and Editor roles via Wordfence Login Security. This is mandatory post-deploy (`make harden` prints the reminder).

### Post-Deploy Security Checklist

Every new WordPress site must complete these steps **before going live**:

1. [ ] Admin username is NOT `admin` — use a unique, non-guessable name
2. [ ] Admin password is 32-char CSPRNG
3. [ ] `xmlrpc.php` is blocked (verify: `curl -sI https://domain.com/xmlrpc.php` returns 403/404/444)
4. [ ] Wordfence installed, activated, firewall in Extended Protection mode
5. [ ] Wordfence 2FA enabled for all admin/editor roles
6. [ ] Wordfence brute-force: lock after 5 failed attempts, block `admin` username
7. [ ] `DISALLOW_FILE_EDIT` and `DISALLOW_FILE_MODS` are `true` in wp-config
8. [ ] `wp-login.php` rate-limited via Traefik middleware
9. [ ] No default/sample content remains (Hello World post, Sample Page)
10. [ ] WordPress auto-updates enabled for minor/security releases
11. [ ] Cloudflare WAF 5-rule set configured and active
12. [ ] HTTP security headers verified (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`)
13. [ ] HSTS + CSP configured in Cloudflare Transform Rules
14. [ ] SPF, DKIM, DMARC DNS records configured for sending domain
15. [ ] `make warm-cache` run before DNS flip to pre-prime FastCGI cache
16. [ ] `make security-check` passes all checks
17. [ ] Browserless headless screenshot taken of homepage — confirms CSS rendering, layout, and content injection beyond HTTP 200
18. [ ] GSC domain verified via Cloudflare DNS TXT record; sitemap_index.xml submitted
19. [ ] Backrest volume backup configured for this site's named volumes
20. [ ] `make db-clean` run monthly to prevent `wp_options`, `wp_postmeta`, and `wp_posts` from becoming query-performance bottlenecks

## Plugin & Theme Discipline

- Use **Gutenberg Block Themes** (Full Site Editing) or lightweight frameworks (GeneratePress). Heavy page builders (Elementor, Divi, WPBakery) are banned — excessive DOM bloat, slow JS, proprietary shortcode lock-in.
- Always use a **Child Theme** for custom PHP/CSS. Never modify parent theme files directly.
- Profile every new plugin with Query Monitor in dev. Prefer single-purpose plugins over "all-in-one" suites.
- **SEO — RankMath module discipline:** **Enable:** ACF, Image SEO, Instant Indexing, Redirections, Schema (Structured Data), Sitemap. **Disable:** Analytics (causes `wp_rankmath_*` table bloat — use Google Search Console directly), Link Counter (continuous background DB stress), AMP (adds complexity, deprecated), bbPress/BuddyPress (unless site is a forum). Also enable: Strip Category Base, Redirect Attachments to parent post, Remove Generator Tag (obscures WP footprint), Noindex empty category/tag archives. Set sitemap page size to **200 links** (default 1000+ wastes crawl budget).
- **IndexNow:** enable RankMath's Instant Indexing module (IndexNow protocol) immediately after install. This sends new/updated URLs to Bing and Yandex automatically on publish — no waiting for crawl. Verify the API key is configured in RankMath > Instant Indexing settings.
- **GSC domain verification:** use Cloudflare DNS TXT record for Google Search Console ownership verification — never HTML file upload (breaks with caching). The site-provisioner controls Cloudflare DNS and can inject the TXT record programmatically. After verification, submit `sitemap_index.xml` directly to GSC.
- **MeiliSearch frontend search:** for content-heavy sites (>100 posts), index content to the internal **MeiliSearch** container (see `specs/infrastructure/meilisearch.yaml`) via a publish webhook or plugin. Native WP search executes full-text queries against MariaDB on every request — this does not scale.
- **Head cleanup / CMS footprint obscurity:** every site must include a `mu-plugin` or child theme `functions.php` that removes: `wp_generator` (WP version in `<head>`), RSD link, Windows Live Writer manifest, shortlinks, emoji JS/CSS, RSS feed links, and `?ver=` version strings from script/style URLs. Leaking the WP version number allows targeted exploitation of known CVEs.

## Multi-Language

- Use **Polylang** (native WordPress taxonomy-based translation). Lightweight, scales linearly.
- **Banned**: WPML (proprietary DB tables, bloat), TranslatePress (CPU-heavy DOM parsing on every load).

## WooCommerce

- Use **WooCommerce Shipping & Tax** plugin for automated tax/shipping calculations via external APIs. Manual tax table management is banned.
- Payment processing via an officially maintained, region-available WooCommerce gateway plugin. Choose based on business model and geography: iyzico for Turkey digital checkout, PayTR for Turkey physical D2C, marketplace channels (Amazon TR, Trendyol) for physical distribution. International digital sales use Paddle (MoR) per `85-payments-billing.md`. This rule covers storefront product checkout only.

## WP-CLI & Makefile

- Every WordPress project must include a **Makefile** wrapping WP-CLI commands via `docker exec`. Standard targets:
  - `make update` — `wp core update`, `wp plugin update --all`, `wp theme update --all`
  - `make cache-flush` — `wp cache flush`
  - `make scaffold` — permalinks, Redis Object Cache, delete sample content, close comments on old posts, **clear default sidebar widgets**, **delete all inactive themes**
  - `make backup` — trigger server-level backup script
  - `make harden` — install Wordfence, check admin username, verify xmlrpc blocked, print 2FA/brute-force reminders
  - `make security-check` — verify xmlrpc blocked, Wordfence active, admin user not `admin`
  - `make warm-cache` — purge Cloudflare zone cache (via API), then parse sitemap and hit all URLs with 8 parallel curl workers to pre-prime FastCGI cache
  - `make rename-admin NEW_USER=<name>` — rename the admin account
  - `make db-clean` — prune expired transients, spam comments, revisions, orphaned postmeta, optimize tables
- **DB readiness gate:** `make scaffold` and `make harden` must only be run after MariaDB is fully initialized. In `compose-coolify.yaml.j2` the `wordpress` service declares `depends_on: db: condition: service_healthy`. In scripted pipelines, poll `docker exec <db-container> mysqladmin ping -h localhost --silent` before invoking WP-CLI.

## Backups

- Execute backups at the **server level** via bash scripts: `mysqldump` for the database, `tar` for `wp-content`, sync to Backblaze B2. MinIO is not deployed — use Backblaze B2 directly.
- PHP-based backup plugins (UpdraftPlus, BackWPup) are banned — they're constrained by PHP timeouts/memory limits and are vulnerable if the server is compromised.
- Monthly: restore the backup to a staging environment and verify data integrity.
- **Backrest per-site volume registration (MANDATORY for VPS deployments):** after deploy, register the site's specific named Docker volumes (`<name>_wp_content`, `<name>_db_data`) with the Backrest container by adding them to `/opt/backrest/config/config.json` as new backup plans. Set a daily cron schedule (e.g. 03:00 AM) and target the shared Backblaze B2 repository. Restic handles deduplication and encryption automatically. This supersedes bare `mysqldump` + `tar` for production Coolify deployments.

## Media Offloading

- For sites with significant media libraries (>500 files or >2GB), offload uploads to object storage using **Advanced Media Offloader** or equivalent MU-plugin.
- **Preferred storage: Backblaze B2.** Due to the Cloudflare–Backblaze Bandwidth Alliance, egress from B2 to Cloudflare is **free**. Configure a custom delivery subdomain (`media.<domain>.com`) proxied through Cloudflare. Cloudflare fetches from B2, caches at edge, and handles on-the-fly WebP/AVIF conversion.
- **Cloudflare R2** is the alternative when the site already uses Cloudflare for DNS/WAF and B2 is not preferred — functionally equivalent, also zero egress cost via Cloudflare.
- Media URLs are rewritten at the database level to serve from R2/CDN edge — Nginx never serves media files directly.
- Local uploads directory on `wp_content` volume is kept as a temporary staging area only.
- Private buckets + signed URLs are required if media assets must be access-controlled.
- This is optional for small sites; mandatory for high-traffic or WooCommerce product image libraries.
- **R2/S3 credentials must be stored in `wp-config.php` via `define()` constants** — never saved in the plugin UI (database). Dashboard exports can expose DB-stored credentials. Use `WORDPRESS_CONFIG_EXTRA` in `compose-coolify.yaml.j2` to inject them.

## Database Maintenance

- Run `make db-clean` monthly (or after major content changes) to prevent `wp_options`, `wp_postmeta`, and `wp_posts` from becoming query-performance bottlenecks.
- `make db-clean` executes: `wp transient delete --expired`, delete spam comments, delete all post revisions, delete orphaned postmeta, `wp db optimize`.
- **System cron implementation:** `DISABLE_WP_CRON=true` is set. Two options:
  - **Preferred (VPS):** configure **Gatus** to ping `https://<domain>/wp-cron.php?doing_wp_cron` every 5 minutes. This reuses the existing monitoring infrastructure, requires no host crontab management, and provides cron execution visibility in the Gatus dashboard.
  - **Alternative (local/dev):** add to host crontab via `docker exec`:

  ```bash
  */5 * * * * docker exec <container> wp cron event run --due-now --path=/var/www/html
  ```

  Use WP-CLI over `curl`/`wget` — it bypasses the HTTP stack, avoids triggering the cache, and outputs errors to the terminal for easier debugging.

## Email Deliverability

- **Preferred (VPS deployments):** route all transactional email through the **internal Fabrik Email Gateway** (HTTP REST API, internal port 3000) via a `phpmailer_init` MU-plugin or custom MU-plugin that calls `http://emailgateway:3000/send` directly. The Email Gateway is an HTTP API — do NOT configure PHPMailer SMTP to point at it. Instead, use `wp_mail` filter or a custom MU-plugin to intercept outgoing mail and POST to the Email Gateway REST endpoint.
- **Alternative:** use `wp-mail-smtp` configured to send via **Postmark** or **Amazon SES** — never the default PHP `mail()` function.
- Before go-live, verify DNS authentication:
  - **SPF:** TXT record authorising the sending service's IP range
  - **DKIM:** provider-supplied CNAME/TXT record for cryptographic signing
  - **DMARC:** start with `p=none` for monitoring, graduate to `p=quarantine` once SPF+DKIM align
- DMARC policy must be in place before go-live. Add to post-deploy checklist item 14.

## Headless CMS (Next.js Integration)

- Expose content via **WPGraphQL** — the native REST API must be restricted to authenticated traffic only.
- Implement **Next.js Draft Mode** with WPGraphQL JWT Authentication for secure preview of unpublished content.
- The Next.js frontend follows the Ocoron Design System in full — tokens, fonts, component patterns, verbal identity. It is treated identically to a `saas-skeleton` or `static-site` scaffold.
- WordPress admin UI is never themed with Ocoron tokens. Non-headless WordPress frontend themes should apply Ocoron colors and fonts via child theme CSS where technically feasible.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| PostgreSQL via pg4wp | MariaDB 10.6+ natively |
| `wordpress:latest` or Apache-based images | `wordpress:php8.x-fpm-bookworm` behind Nginx |
| Full `/var/www/html` bind mount | Named volume for `/var/www/html/wp-content` only |
| PHP caching plugins (WP Rocket, W3 Total Cache) | Nginx FastCGI Cache + Redis Object Cache |
| Hardcoded secrets in `wp-config.php` | Environment variables via Coolify |
| Active `xmlrpc.php` endpoint | Block at Nginx/Traefik level (403/444) |
| `admin` as WordPress username | Unique, non-guessable admin username |
| No security plugin installed | Wordfence (mandatory on every site) |
| Unprotected `wp-login.php` | Rate-limit via Traefik middleware |
| Heavy page builders (Elementor, Divi, WPBakery) | Gutenberg Block Themes / GeneratePress |
| WPML or TranslatePress for i18n | Polylang (native taxonomy) |
| Manual WooCommerce tax tables | WooCommerce Shipping & Tax plugin (API-based) |
| PHP backup plugins (UpdraftPlus, BackWPup) | Server-level `mysqldump` + `tar` → S3 |
| `DISALLOW_FILE_EDIT` only | Also set `DISALLOW_FILE_MODS=true` |
| `WP_DEBUG=false` with `WP_DEBUG_LOG=true` | `WP_DEBUG=true` + `WP_DEBUG_LOG=true` + `WP_DEBUG_DISPLAY=false` (DEBUG must be true for log to write) |
| No `WP_HTTP_BLOCK_EXTERNAL` | `define('WP_HTTP_BLOCK_EXTERNAL', true)` + `WP_ACCESSIBLE_HOSTS` whitelist |
| Default `wp_` table prefix | Unique site-specific prefix (e.g. `sitename_prod_`) |
| No Redis prefix | `WP_REDIS_PREFIX` + `WP_REDIS_DATABASE` per-site isolation |
| PHP execution allowed in `/uploads/` | Nginx `deny all` for `*.php` in uploads dir |
| No WooCommerce cache bypass | `$skip_cache_woo` + `$skip_cache_cookie` map in Nginx |
| Cookie consent banner + Nginx cache | `$skip_cache_consent` map prevents cache poisoning |
| Open `/wp-json/wp/v2/users` endpoint | Block at Nginx level (`return 403`) |
| No Cloudflare WAF rules | 5-rule WAF set (see §Cloudflare WAF Rules) |
| PHP `mail()` for transactional email | Fabrik Email Gateway (internal, port 3000) or `wp-mail-smtp` → Postmark/SES |
| Cold site launch (no cache warm) | `make warm-cache` before DNS flip |

---

## Done When

- [ ] Docker Compose uses `wordpress:php8.x-fpm-bookworm` + `nginx:mainline-bookworm-slim` + `mariadb:10.6+` + `redis:7-bookworm`.
- [ ] Only `wp-content` is mounted as a named volume — not the full web root.
- [ ] `wp-content` owned by `www-data:www-data` (UID 33).
- [ ] Nginx config includes FastCGI cache directives, blocks `xmlrpc.php`, blocks PHP in `/uploads/`, has WooCommerce + consent cache bypass maps.
- [ ] All secrets injected via environment variables — nothing hardcoded.
- [ ] `DISALLOW_FILE_EDIT`, `DISALLOW_FILE_MODS`, `WP_DEBUG=true`, `WP_DEBUG_DISPLAY=false`, `WP_HTTP_BLOCK_EXTERNAL=true` set in `wp-config.php`.
- [ ] Custom table prefix set (not `wp_`).
- [ ] `WP_REDIS_PREFIX` and `WP_REDIS_DATABASE` set.
- [ ] Makefile exists with `update`, `cache-flush`, `scaffold`, `backup`, `harden`, `security-check`, `warm-cache`, `db-clean` targets.
- [ ] Server-level backup script syncs DB dump + wp-content to S3.
- [ ] No PHP caching plugins, no heavy page builders, no WPML/TranslatePress installed.
- [ ] Admin username is not `admin` — unique, non-guessable name used.
- [ ] Admin password is 32-char CSPRNG.
- [ ] Wordfence installed, activated, firewall in Extended Protection mode, 2FA enabled for admin/editor.
- [ ] `xmlrpc.php` returns 403/404/444 when tested externally.
- [ ] `/wp-json/wp/v2/users` returns 403.
- [ ] `wp-login.php` rate-limited via Traefik middleware.
- [ ] Cloudflare WAF 5-rule set active; HSTS + CSP in Transform Rules.
- [ ] SPF, DKIM, DMARC DNS records configured.
- [ ] `make warm-cache` run before DNS flip.
- [ ] Post-deploy security checklist completed before site goes live.
