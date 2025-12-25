# WordPress Template

Deploys hardened WordPress sites with preset-based configuration.

## Architecture

```
templates/wordpress/
├── base/                    # Immutable infrastructure
│   ├── compose.yaml.j2      # WordPress + MariaDB + Backup
│   ├── .env.j2              # Generated secrets
│   ├── wp-config-extra.php  # Security hardening
│   └── backup/backup.sh     # R2 backup script
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
# Create new WordPress site with preset
fabrik new my-product --template=wordpress --preset=saas

# Edit the spec file
vim sites/my-product.yaml

# Deploy
fabrik apply sites/my-product.yaml
```

## Spec Options

```yaml
name: my-product
template: wordpress
preset: saas  # saas, company, content, landing
domain: product.example.com
php_version: php8.2

# Override preset defaults
features:
  blog: true
  pricing_page: true

# Premium plugins (place ZIPs in plugins/ folder)
plugins:
  premium:
    - rank-math-pro.zip
```

## Security Hardening (base/)

All sites include:
- File editor disabled
- XML-RPC blocked  
- SSL forced for admin
- Post revisions limited to 5
- Memory limits configured

## Backups (base/)

All sites include:
- Daily: Database dump → R2
- Weekly: Full backup → R2
- Retention: 7 daily, 4 weekly

## WP-CLI Access

```bash
# Run WP-CLI commands
fabrik wp my-product plugin list
fabrik wp my-product theme activate flavor-starter
fabrik wp my-product user create admin admin@example.com --role=administrator
```

## Premium Plugins

Place premium plugin ZIPs in `plugins/` folder:

```bash
cp ~/Downloads/rank-math-pro.zip templates/wordpress/plugins/
```

Referenced in preset YAML as:
```yaml
plugins:
  premium:
    - rank-math-pro.zip
```
