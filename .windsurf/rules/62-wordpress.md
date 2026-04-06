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
- **Redis Object Cache** via a dedicated Redis container handles database query caching for dynamic/logged-in requests.
- PHP-based caching plugins (WP Rocket, W3 Total Cache, WP Super Cache) are **banned** — they waste CPU invoking PHP just to serve cached pages.

## Security Hardening

### wp-config.php (enforced via `wp-config-extra.php` template)

- `define('DISALLOW_FILE_EDIT', true);` — prevents remote code execution if an admin account is compromised.
- `define('FORCE_SSL_ADMIN', true);` — forces HTTPS for wp-admin.
- `define('WP_POST_REVISIONS', 5);` — prevents `wp_posts` table bloat.
- `define('DISABLE_WP_CRON', true);` — use system cron instead of PHP-triggered cron.
- Inject all secrets (DB credentials, cryptographic salts) via Coolify environment variables. **Never** hardcode secrets in `wp-config.php` or version-controlled files.

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
- Wordfence firewall mode should be set to "Extended Protection" after initial setup.

### Post-Deploy Security Checklist

Every new WordPress site must complete these steps **before going live**:

1. [ ] Admin username is NOT `admin` — use a unique, non-guessable name
2. [ ] Admin password is 32-char CSPRNG
3. [ ] `xmlrpc.php` is blocked (verify: `curl -sI https://domain.com/xmlrpc.php` returns 403/404/444)
4. [ ] Wordfence installed, activated, and firewall in Extended Protection mode
5. [ ] `DISALLOW_FILE_EDIT` is `true` in wp-config
6. [ ] `wp-login.php` rate-limited via Traefik middleware
7. [ ] No default/sample content remains (Hello World post, Sample Page)
8. [ ] WordPress auto-updates enabled for minor/security releases
9. [ ] Cloudflare WAF rules active (if using Cloudflare proxy)

## Plugin & Theme Discipline

- Use **Gutenberg Block Themes** (Full Site Editing) or lightweight frameworks (GeneratePress). Heavy page builders (Elementor, Divi, WPBakery) are banned — excessive DOM bloat, slow JS, proprietary shortcode lock-in.
- Always use a **Child Theme** for custom PHP/CSS. Never modify parent theme files directly.
- Profile every new plugin with Query Monitor in dev. Prefer single-purpose plugins over "all-in-one" suites.
- **SEO**: RankMath configured strictly for sitemaps and structured data. Disable unused modules.

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
  - `make scaffold` — `wp rewrite flush --hard`, install/activate Redis Object Cache
  - `make backup` — trigger server-level backup script
  - `make harden` — install Wordfence, rename admin user, verify xmlrpc blocked, run security checklist
  - `make security-check` — verify xmlrpc blocked, Wordfence active, admin user not `admin`

## Backups

- Execute backups at the **server level** via bash scripts: `mysqldump` for the database, `tar` for `wp-content`, sync to S3-compatible storage (Backblaze B2 / MinIO).
- PHP-based backup plugins (UpdraftPlus, BackWPup) are banned — they're constrained by PHP timeouts/memory limits and are vulnerable if the server is compromised.

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

---

## Done When

- [ ] Docker Compose uses `wordpress:php8.x-fpm-bookworm` + `nginx:mainline-bookworm-slim` + `mariadb:10.6+` + `redis:7-bookworm`.
- [ ] Only `wp-content` is mounted as a named volume — not the full web root.
- [ ] `wp-content` owned by `www-data:www-data` (UID 33).
- [ ] Nginx config includes FastCGI cache directives and blocks `xmlrpc.php`.
- [ ] All secrets injected via environment variables — nothing hardcoded.
- [ ] `DISALLOW_FILE_EDIT` and `WP_POST_REVISIONS` set in `wp-config.php`.
- [ ] Makefile exists with `update`, `cache-flush`, `scaffold`, `backup` targets.
- [ ] Server-level backup script syncs DB dump + wp-content to S3.
- [ ] No PHP caching plugins, no heavy page builders, no WPML/TranslatePress installed.
- [ ] Admin username is not `admin` — unique, non-guessable name used.
- [ ] Admin password is 32-char CSPRNG.
- [ ] Wordfence installed, activated, firewall in Extended Protection mode.
- [ ] `xmlrpc.php` returns 403/404/444 when tested externally.
- [ ] `wp-login.php` rate-limited via Traefik middleware.
- [ ] Post-deploy security checklist completed before site goes live.
