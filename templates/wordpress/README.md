# WordPress Template

Deploys hardened WordPress sites with preset-based configuration.

## Architecture

```text
templates/wordpress/
├── base/                         # Immutable infrastructure
│   ├── compose-coolify.yaml.j2   # PRIMARY: Coolify-managed production stack
│   ├── compose.yaml.j2           # Self-hosted VPS variant (env_file-based)
│   ├── compose.dev.yaml.j2       # Local development (full root mount — NOT for VPS)
│   ├── nginx/default.conf.j2     # Nginx: FastCGI cache, xmlrpc block, security
│   ├── nginx-dev.conf.j2         # Nginx: dev-only config
│   ├── wp-config-extra.php       # Security hardening constants
│   └── backup/backup.sh          # Server-level mysqldump + tar + S3 sync
├── presets/                 # Data-driven site types
│   ├── saas.yaml            # SaaS companion site
│   ├── company.yaml         # Company website
│   ├── content.yaml         # Authority/SEO site
│   ├── landing.yaml         # Single-page campaigns
│   └── ecommerce.yaml       # Future: WooCommerce
├── plugins/                 # Premium plugin ZIPs
├── themes/                  # Premium theme ZIPs
└── README.md
```

## Site Types

| Type | Use Case | Preset |
|------|----------|--------|
| **SaaS Companion** | Marketing for SaaS products | `saas.yaml` |
| **Company Site** | Corporate presence (ocoron.com) | `company.yaml` |
| **Content/Authority** | SEO, AI content, brand expansion | `content.yaml` |
| **Landing Page** | Ads, experiments, waitlists | `landing.yaml` |
| **E-commerce** | Product sales (future) | `ecommerce.yaml` |

## Usage

```bash
# Scaffold a new WordPress project (renders site.yaml.j2 template)
fabrik scaffold my-product --type wordpress --preset saas

# Edit the generated spec
vim /opt/my-product/site.yaml

# Plan and deploy
fabrik wp plan my-product.com
fabrik wp apply my-product.com
```

## Spec Options

See `templates/wordpress/base/site.yaml.j2` for the full annotated template.
Key overridable fields:

```yaml
preset: saas  # saas, company, content, landing, ecommerce

site:
  domain: product.example.com

brand:
  name: "My Product"

plugins:
  add:
    - some-extra-plugin
  skip:
    - a-default-plugin-to-remove
```

> **Note:** `php_version` is set in the Coolify service config, not in the site spec.

## Security Hardening (base/)

All sites include:

- File editor disabled (`DISALLOW_FILE_EDIT`)
- XML-RPC blocked at Nginx (`return 444`) and Traefik middleware
- SSL forced for admin (`FORCE_SSL_ADMIN`)
- Post revisions limited to 5 (`WP_POST_REVISIONS`)
- PHP cron disabled (`DISABLE_WP_CRON`) — use Uptime Kuma ping every 5 min (preferred) or system cron
- Auto-updates enabled for minor/security releases (`WP_AUTO_UPDATE_CORE=minor`)
- `wp-content` owned by `www-data:www-data` (UID 33) at startup
- Rate-limiting on `wp-login.php` via Traefik (10 req/min, burst 20)
- Admin username is NOT `admin` — rename immediately after install
- Admin password: 32-char CSPRNG (`secrets.choice` over `[a-zA-Z0-9]`)
- Wordfence installed, activated, firewall in Extended Protection mode
- Child theme always used for custom PHP/CSS (never modify parent directly)

## Backups (base/)

All sites include:

- Daily: Database dump + wp-content tar → Backblaze B2 (preferred; Bandwidth Alliance = free egress)
- Duplicati per-site volume registration: mandatory for VPS deployments (AES-256, dedicated B2 bucket)
- Retention: 30 days (configurable via `backup.retain_days` in site spec)

## WP-CLI Access

```bash
# Run WP-CLI commands
fabrik wp my-product plugin list
fabrik wp my-product theme activate flavor-starter
# NEVER use 'admin' as username — use a unique, non-guessable name
fabrik wp my-product user create siteowner admin@example.com --role=administrator
```

## Makefile Targets

Every scaffolded site includes a `Makefile` wrapping WP-CLI via `docker exec`:

```makefile
make update          # wp core update + wp plugin update --all + wp theme update --all
make cache-flush     # wp cache flush + wp rewrite flush --hard
make scaffold        # post-install: permalinks, Redis Object Cache, cleanup defaults
make backup          # trigger server-level backup (mysqldump + tar → R2)
make harden          # install Wordfence, check admin username, verify xmlrpc blocked
make security-check  # verify xmlrpc blocked, Wordfence active, admin not 'admin'
make rename-admin NEW_USER=siteowner  # rename the admin account
make shell           # open bash shell in WordPress container
make logs            # tail WordPress container logs
```

## Premium Plugins

Place premium plugin ZIPs in `plugins/` folder:

```bash
cp ~/Downloads/rank-math-pro.zip templates/wordpress/plugins/
```

Referenced via site spec `plugins.add`:

```yaml
plugins:
  add:
    - rank-math-seo-pro  # premium slug (ZIP must be in plugins/ folder)
```
