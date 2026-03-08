# WordPress Deployment Workflow

**Last Updated:** 2026-03-07

Complete guide to deploying WordPress sites with Fabrik, from spec creation to live site.

---

## Overview

Fabrik's WordPress deployment has two distinct phases:

```
Phase 1: Container Creation (Infrastructure)
    ↓
Phase 2: WordPress Configuration (Content & Settings)
```

**Key Principle:** Fabrik does NOT create Docker containers. It configures existing WordPress installations via WP-CLI and REST API.

---

## Architecture: WSL + VPS Model

```
┌─────────────────────────────────────────────────────────────┐
│  WSL (Development Machine)                                   │
│                                                              │
│  /opt/fabrik/                                                │
│  ├── specs/sites/ocoron.com.yaml  ← YAML spec               │
│  └── src/fabrik/wordpress/        ← Automation code         │
│                                                              │
│  Actions:                                                    │
│  - Edit spec files                                           │
│  - Run: fabrik apply ocoron.com                              │
│  - Fabrik CLI orchestrates via APIs (does not run containers)│
└────────────────────┬─────────────────────────────────────────┘
                     │
                     │ SSH + Coolify API + WP-CLI (via SSH)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  VPS (45.61.127.38 / vps1.ocoron.com)                        │
│                                                              │
│  Docker Containers:                                          │
│  ├── ocoron-com-wordpress-1  ← WordPress + Apache + WP-CLI  │
│  ├── ocoron-com-db-1         ← MariaDB                       │
│  ├── wp-test-wordpress       ← Another site                  │
│  └── wp-test-db              ← Another DB                    │
│                                                              │
│  All containers run here, managed by Coolify                 │
└─────────────────────────────────────────────────────────────┘
```

**WSL:** Control plane (CLI, specs, orchestration)
**VPS:** Execution plane (containers, databases, WordPress files)

---

## Prerequisites

### 1. VPS Infrastructure

```bash
# Required services running on VPS:
- Coolify (container orchestration)
- Traefik (reverse proxy + SSL)
- postgres-main (shared database, optional)
- Docker + docker-compose
```

### 2. WSL Environment

```bash
# Required in WSL:
cd /opt/fabrik
source .venv/bin/activate

# Verify Fabrik installation
python -c "from fabrik.wordpress import SiteDeployer; print('OK')"

# Verify SSH access to VPS
ssh vps "echo 'SSH OK'"

# Verify Coolify API access
python -c "from fabrik.drivers.coolify import CoolifyClient; c=CoolifyClient(); print(c.health())"
```

### 3. DNS & Domain

```bash
# Domain must point to VPS IP
# Either:
- Cloudflare zone created (via dns.vps1.ocoron.com)
- OR manual DNS A record: ocoron.com → 45.61.127.38
```

---

## Deployment Methods

### Method 1: Via Coolify API (Recommended)

**Pros:**
- Coolify tracks deployment status
- Auto-restart on failure
- Health checks integrated
- Manageable via Coolify UI

**Cons:**
- More complex (requires Coolify project/server UUIDs)
- API may have limitations (422 errors observed)

**Implementation:**
```python
from fabrik.drivers.coolify import CoolifyClient

coolify = CoolifyClient()
compose_yaml = """
services:
  wordpress:
    image: wordpress:php8.2-apache
    ...
"""

result = coolify.create_dockercompose_application(
    project_uuid="zkco0cc40040kkw0gc4k0848",
    server_uuid="jk4wskkcks8csg4gcokwgw8s",
    docker_compose_raw=compose_yaml,
    name='ocoron-com',
    instant_deploy=True
)
```

### Method 2: Direct docker-compose on VPS (Fallback)

**Pros:**
- Simple, direct control
- No Coolify API dependencies
- Works when Coolify API fails

**Cons:**
- Not tracked by Coolify
- Manual health checks
- No auto-restart

**Implementation:**
```bash
# 1. Generate compose file (in WSL)
python scripts/generate_wp_compose.py ocoron.com > /tmp/ocoron-compose.yaml

# 2. Deploy on VPS
scp /tmp/ocoron-compose.yaml vps:/tmp/
ssh vps "cd /tmp && sudo docker compose -f ocoron-compose.yaml -p ocoron-com up -d"
```

### Method 3: Coolify UI (Manual)

**Use for:** One-off deployments, testing

**Steps:**
1. Open Coolify UI: https://coolify.vps1.ocoron.com
2. Create new application → Docker Compose
3. Paste compose.yaml from `templates/wordpress/base/compose-coolify.yaml.j2`
4. Deploy

---

## Complete Deployment Flow

### Step 1: Create WordPress Spec

```bash
cd /opt/fabrik/specs/sites
cp ocoron.com.yaml mynewsite.com.yaml
vim mynewsite.com.yaml
```

**Minimal spec:**
```yaml
schema_version: 1
preset: company
site:
  domain: mynewsite.com
brand:
  name: "My Company"
  tagline:
    en_US: "Professional Services"
services:
  - slug: consulting
    name: {en_US: "Consulting"}
```

### Step 2: Deploy WordPress Container

**Option A: Via Coolify API**
```python
# Use CoolifyClient.create_dockercompose_application()
# See Method 1 above
```

**Option B: Direct docker-compose (used for ocoron.com)**
```bash
# Generate compose file
python -c "
from jinja2 import Template
import secrets, string

template = open('templates/wordpress/base/compose-coolify.yaml.j2').read()
compose = Template(template).render(
    name='mynewsite-com',
    domain='mynewsite.com',
    php_version='php8.2',
    db_password=''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)),
    db_root_password=''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32))
)
print(compose)
" > /tmp/mynewsite-compose.yaml

# Deploy
scp /tmp/mynewsite-compose.yaml vps:/tmp/
ssh vps "cd /tmp && sudo docker compose -f mynewsite-compose.yaml -p mynewsite-com up -d"
```

### Step 3: Install WP-CLI in Container

```bash
ssh vps "sudo docker exec mynewsite-com-wordpress-1 bash -c 'curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && chmod +x wp-cli.phar && mv wp-cli.phar /usr/local/bin/wp'"

# Verify
ssh vps "sudo docker exec mynewsite-com-wordpress-1 wp --version --allow-root"
```

### Step 4: Install WordPress Core

```bash
# Generate admin password
ADMIN_PASSWORD=$(python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))")

# Install WordPress
ssh vps "sudo docker exec mynewsite-com-wordpress-1 wp core install \
  --url=https://mynewsite.com \
  --title='My Company' \
  --admin_user=admin \
  --admin_password='$ADMIN_PASSWORD' \
  --admin_email=admin@mynewsite.com \
  --allow-root"

# Save credentials
echo "WP_ADMIN_USER=admin" >> /tmp/mynewsite-credentials.txt
echo "WP_ADMIN_PASSWORD=$ADMIN_PASSWORD" >> /tmp/mynewsite-credentials.txt
```

### Step 5: Configure Container Name in Fabrik

**Update `/opt/fabrik/.env`:**
```bash
# Add site-specific config
MYNEWSITE_COM_CONTAINER_NAME=mynewsite-com-wordpress-1
MYNEWSITE_COM_DB_PASSWORD=<password from step 2>
WP_ADMIN_PASSWORD=<password from step 4>
```

### Step 6: Run Fabrik SiteDeployer

```python
from fabrik.wordpress import SiteDeployer

# Deploy with spec
deployer = SiteDeployer('mynewsite.com', dry_run=False)
result = deployer.deploy()

# Check result
if result.success:
    print(f"✅ Deployment successful!")
    print(f"Pages created: {len(result.pages_created)}")
else:
    print(f"❌ Deployment failed")
    print(f"Errors: {result.errors}")
```

**What SiteDeployer does:**
1. DNS setup (if needed)
2. WordPress settings (site title, timezone, permalinks)
3. Install GeneratePress theme + GP Premium
4. Install plugins (SEO, forms, analytics)
5. Generate pages from spec (hero, services, about, contact)
6. Create menus (primary, footer)
7. Configure SEO (Rank Math)
8. Configure analytics (GA4)
9. Create forms (contact, quote)

### Step 7: Verify Deployment

```bash
# Check HTTPS
curl -I https://mynewsite.com

# Check WordPress version
ssh vps "sudo docker exec mynewsite-com-wordpress-1 wp core version --allow-root"

# List pages
ssh vps "sudo docker exec mynewsite-com-wordpress-1 wp post list --post_type=page --allow-root"

# Check plugins
ssh vps "sudo docker exec mynewsite-com-wordpress-1 wp plugin list --allow-root"

# Check theme
ssh vps "sudo docker exec mynewsite-com-wordpress-1 wp theme list --allow-root"
```

### Step 8: Security Hardening

```bash
# Disable file editing (already done by SiteDeployer)
# Verify:
ssh vps "sudo docker exec mynewsite-com-wordpress-1 wp config get DISALLOW_FILE_EDIT --allow-root"

# Rotate credentials (recommended)
# Change:
# - WordPress admin password (via wp-admin)
# - Database password (in .env and container restart)
```

---

## Container Naming Convention

### Expected by Fabrik

```python
# Default pattern in WordPressClient:
container_name = f"{site_name}-wordpress"

# Example:
site_name = "ocoron-com"
container_name = "ocoron-com-wordpress"
```

### Created by docker-compose

```yaml
# docker-compose naming:
# Pattern: {project}_{service}_{replica}
# OR with -p flag: {project}-{service}-{replica}

# Example with -p ocoron-com:
project = "ocoron-com"
service = "wordpress"
replica = "1"
container_name = "ocoron-com-wordpress-1"  # Note the "-1" suffix
```

### Created by Coolify

```bash
# Coolify uses UUIDs or custom names
# Example:
wordpress-scoksgk4ww840okw84ksw40w  # UUID-based
ocoron-com-wordpress                 # Custom name (if specified)
```

### Solution: Override Container Name

**In spec or environment:**
```python
# Option 1: Override in WPSite
site = WPSite(
    name="ocoron-com",
    domain="ocoron.com",
    container="ocoron-com-wordpress-1"  # Explicit override
)

# Option 2: Environment variable
# .env
OCORON_COM_CONTAINER_NAME=ocoron-com-wordpress-1
```

---

## Troubleshooting

### Issue: "No such container" error

**Symptom:**
```
RuntimeError: WP-CLI failed: Error response from daemon: No such container: ocoron-com-wordpress
```

**Cause:** Container name mismatch

**Solution:**
```bash
# Find actual container name
ssh vps "sudo docker ps | grep wordpress"

# Update WPSite or .env with correct name
```

### Issue: WP-CLI not found

**Symptom:**
```
exec: "wp": executable file not found in $PATH
```

**Cause:** WP-CLI not installed in container

**Solution:**
```bash
ssh vps "sudo docker exec <container> bash -c 'curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && chmod +x wp-cli.phar && mv wp-cli.phar /usr/local/bin/wp'"
```

### Issue: Compromised WordPress installation

**Symptom:** Suspicious files like `txets.php`, `.tmb/`, random PHP files in `wp-admin/css/`

**Solution:**
```bash
# Delete and redeploy clean
ssh vps "sudo docker stop <container> <db-container>"
ssh vps "sudo docker rm <container> <db-container>"
ssh vps "sudo docker volume rm <wordpress-volume> <db-volume>"

# Then redeploy from Step 2
```

### Issue: Coolify API 422 error

**Symptom:** `HTTPStatusError: Client error '422 Unprocessable Content'`

**Cause:** Invalid compose.yaml or missing parameters

**Solution:** Use Method 2 (direct docker-compose) as fallback

---

## Site Isolation Model

Each WordPress site gets:

```
ocoron.com:
├── ocoron-com-wordpress-1  (WordPress container)
├── ocoron-com-db-1         (MariaDB container)
├── wordpress_data volume   (wp-content, uploads)
└── db_data volume          (MySQL data)

mynewsite.com:
├── mynewsite-com-wordpress-1
├── mynewsite-com-db-1
├── wordpress_data volume
└── db_data volume

Benefits:
- Full isolation (one site hack ≠ all sites compromised)
- Independent updates (update one site without affecting others)
- Different PHP versions per site (if needed)
- Separate databases (security)
- Easy backup/restore per site
```

---

## Credentials Management

### Storage Locations

**1. Project `.env` (working credentials)**
```bash
/opt/fabrik/.env
```

**2. Master backup (read-only reference)**
```bash
/opt/fabrik/.env
```

**3. Temporary deployment credentials**
```bash
/tmp/ocoron-passwords.env
/tmp/ocoron-admin-password.txt
```

### Required Credentials per Site

```bash
# Database
OCORON_COM_DB_PASSWORD=<32-char CSPRNG>
OCORON_COM_DB_ROOT_PASSWORD=<32-char CSPRNG>

# WordPress Admin
WP_ADMIN_USER=admin
WP_ADMIN_PASSWORD=<32-char CSPRNG>
WP_ADMIN_EMAIL=admin@ocoron.com

# Coolify (if using Method 1)
OCORON_COM_COOLIFY_SERVICE_UUID=<uuid>
OCORON_COM_COOLIFY_PROJECT_UUID=<uuid>
```

---

## Quick Reference

### Start New Site (15 minutes)

```bash
# 1. Create spec
cp specs/sites/template.yaml specs/sites/newsite.com.yaml

# 2. Deploy container
ssh vps "cd /tmp && docker compose -f newsite-compose.yaml -p newsite-com up -d"

# 3. Install WP-CLI
ssh vps "docker exec newsite-com-wordpress-1 bash -c 'curl -O https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && chmod +x wp-cli.phar && mv wp-cli.phar /usr/local/bin/wp'"

# 4. Install WordPress
ssh vps "docker exec newsite-com-wordpress-1 wp core install --url=https://newsite.com --title='New Site' --admin_user=admin --admin_password='PASSWORD' --admin_email=admin@newsite.com --allow-root"

# 5. Configure site
python -c "from fabrik.wordpress import SiteDeployer; SiteDeployer('newsite.com').deploy()"

# 6. Verify
curl https://newsite.com
```

### Check Site Status

```bash
# WordPress version
ssh vps "docker exec <container> wp core version --allow-root"

# Plugins
ssh vps "docker exec <container> wp plugin list --allow-root"

# Pages
ssh vps "docker exec <container> wp post list --post_type=page --allow-root"

# Site URL
ssh vps "docker exec <container> wp option get siteurl --allow-root"
```

### Update Site Content

```bash
# Edit spec
vim specs/sites/ocoron.com.yaml

# Redeploy (idempotent)
python -c "from fabrik.wordpress import SiteDeployer; SiteDeployer('ocoron.com').deploy()"
```

---

## Best Practices

### 1. Always Use WP-CLI-Enabled Containers

Standard `wordpress:php8.2-apache` does NOT include WP-CLI. Install it manually or use custom image.

### 2. Keep Specs in Version Control

```bash
cd /opt/fabrik
git add specs/sites/ocoron.com.yaml
git commit -m "Update ocoron.com spec"
```

### 3. Backup Before Major Changes

```bash
# Backup database
ssh vps "docker exec ocoron-com-db-1 mysqldump -u root -p wordpress > /tmp/ocoron-backup.sql"

# Backup wp-content
ssh vps "docker cp ocoron-com-wordpress-1:/var/www/html/wp-content /tmp/ocoron-wp-content-backup"
```

### 4. Test Locally Before VPS

```bash
# Use wp-test container for testing
python -c "from fabrik.wordpress import SiteDeployer; SiteDeployer('wp-test', dry_run=True).deploy()"
```

---

## Next Steps

After deployment:
1. **Configure backups** (Duplicati or custom script)
2. **Set up monitoring** (Uptime Kuma for ocoron.com)
3. **Configure CDN** (Cloudflare proxy already enabled via DNS)
4. **Add security** (Cloudflare WAF rules, rate limiting)
5. **SEO verification** (Submit sitemap to Google Search Console)

---

## See Also

- [WordPress Architecture](architecture.md) - System design and components
- [WordPress Spec Schema](../../../templates/wordpress/schema/v1.yaml) - YAML spec reference
- [SERVICES.md](../../SERVICES.md) - VPS infrastructure overview
- [Deployment Checklist](../../guides/DEPLOYMENT_READY_CHECKLIST.md) - Pre-deployment verification
