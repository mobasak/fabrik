> **Phase Navigation:** [← Phase 1](Phase1.md) | **Phase 2** | [Phase 3 →](Phase3.md) | [All Phases](roadmap.md)

**Status:** ✅ COMPLETE (historical implementation)
## Phase 2: WordPress Automation — Complete Narrative

**Status: ✅ Core Complete**

---

### Progress Tracker

| Step | Task | Status |
|------|------|--------|
| 1 | Create WordPress template (compose + env + hardening) | ✅ Done |
| 2 | Add backup sidecar to template | ✅ Done |
| 3 | Deploy WordPress test site | ✅ Done (wp-test.vps1.ocoron.com) |
| 4 | WP-CLI wrapper | ✅ Done (WordPressClient driver) |
| 5 | WordPress REST API client | ✅ Done (WordPressAPIClient driver) |
| 6 | Theme management | ✅ Done (via WP-CLI wrapper) |
| 7 | Plugin management | ✅ Done (via WP-CLI wrapper) |
| 8 | Content operations | ✅ Done (via REST API client) |
| 9 | Configure WAF rules (from Phase 1c/4) | ⏸️ Deferred (needs Cloudflare permissions) |
| 10 | Build preset loader | ❌ Pending |
| 11 | Create themes (flavor-starter, flavor-corporate) | ❌ Pending |
| 12 | Deploy ocoron.com | ❌ Pending |

**Completion: 8/12 tasks (67%)**

---

### Template Configuration (Decided)

| Setting | Value | Rationale |
|---------|-------|-----------|
| **Database** | MariaDB per site (isolated) | WordPress standard, easier migration, full isolation |
| **PHP** | 8.2 (configurable) | 2025 default, best performance |
| **Traefik** | HTTPS via Let's Encrypt | Matches existing stack |
| **Language** | en_US (default) | English default, multilingual via plugin |
| **Admin Email** | web@ocoron.com | Generic email for all WP notifications |

### Language Support

| Language | Code | Notes |
|----------|------|-------|
| English | `en_US` | Default for all sites |
| Turkish | `tr_TR` | Sites like ocoron.com |
| Others | As needed | Multilingual via WPML or Polylang |

**Architecture:** Each site starts with single language. Multilingual support added via plugin (WPML for premium, Polylang for free) when needed.

### Default Plugins

| Purpose | Plugin | Why |
|---------|--------|-----|
| Security | WP Fail2Ban or Limit Login Attempts | Lightweight, server-friendly |
| SEO | Rank Math Pro | User has license, better than Yoast |
| Multilingual | WPML or Polylang | When multiple languages needed |

### wp-config Hardening

```php
// Disable file editor
define('DISALLOW_FILE_EDIT', true);
// Disable XML-RPC
define('XMLRPC_DISABLED', true);
// Force SSL admin
define('FORCE_SSL_ADMIN', true);
// Limit revisions
define('WP_POST_REVISIONS', 5);
// Memory limits
define('WP_MEMORY_LIMIT', '256M');
```

### Backups (Non-Optional)

Every WordPress site includes:
- Daily database dump
- Weekly full backup
- Stored to R2 (using existing credentials)

---

## Site Types & Template Architecture

### Template Structure

```
templates/wordpress/
├── base/                    # Immutable infrastructure
│   ├── compose.yaml.j2      # WordPress + MariaDB + Backup
│   ├── .env.j2              # Generated secrets
│   ├── wp-config-extra.php  # Security hardening
│   └── backup/backup.sh     # R2 backup script
├── presets/                 # Data-driven overlays
│   ├── saas.yaml            # SaaS companion preset
│   ├── company.yaml         # Company site preset
│   ├── content.yaml         # Authority/SEO preset
│   ├── landing.yaml         # Single-page preset
│   └── ecommerce.yaml       # Future: WooCommerce
└── README.md
```

**Design principles:**
- `base/` is **immutable** — no product-specific logic, only infra + security
- Presets are **data-driven** YAML overlays that toggle features
- Upgrades to base/ apply to all sites automatically

---

### Site Type 1: SaaS Companion

**Purpose:** Marketing site for SaaS products (awareness → trust → signup)

**SaaS Product Architecture:**
```
product.com       → WordPress (saas preset) - marketing, pricing, signup
docs.product.com  → Docusaurus - guides + API reference
app.product.com   → Application (separate deployment)
```

| Page | Required | Purpose |
|------|----------|---------|
| Homepage | ✅ | Value proposition + primary CTA |
| Product/Features | ✅ | What it does, screenshots, use cases |
| Pricing | ✅ | Tiers, what's included |
| Signup/Login | ✅ | Links to app (external) |
| About | ✅ | Who's behind it, credibility |
| Contact | ✅ | Email/form, demo booking |
| Blog | ⚡ Light | 5-10 posts max (SEO + credibility) |
| Legal | ✅ | Privacy Policy, Terms of Service |

**Documentation (Docusaurus at docs.product.com):**

| Section | Source | Purpose |
|---------|--------|---------|
| Guides/Tutorials | Native MDX | Getting started, how-tos |
| API Reference | OpenAPI → MDX | Generated from spec |

Stack: `docusaurus-plugin-openapi-docs` + `docusaurus-theme-openapi-docs`

**Preset config:**
```yaml
type: saas
features:
  blog: true
  blog_categories: minimal  # 2-3 max
  docs: basic
  pricing_page: true
  signup_cta: true
plugins:
  - limit-login-attempts-reloaded
  - rank-math-pro
theme: flavor-starter  # or flavor-starter
```

---

### Site Type 2: Company Site

**Purpose:** Corporate anchor site (who you are, what you build, credibility)

| Page | Required | Purpose |
|------|----------|---------|
| Homepage | ✅ | What Ocoron does, links to products |
| Products/Platforms | ✅ | One page per product |
| Services/Capabilities | ✅ | High-level, outcome-focused |
| About | ✅ | Mission, positioning, credibility |
| Contact | ✅ | Business contact path |
| Insights/Articles | ⚡ Light | SEO, thought leadership |
| Updates/News | ⚡ Light | Product launches, milestones |
| Legal | ✅ | Privacy Policy, Terms of Service |

**Preset config:**
```yaml
type: company
features:
  blog: true
  blog_categories: focused  # products, insights, news
  multi_product: true
  team_page: optional
plugins:
  - limit-login-attempts-reloaded
  - rank-math-pro
  - polylang  # for multilingual (ocoron.com)
languages:
  - en_US
  - tr_TR
theme: flavor-corporate
```

---

### Site Type 3: Content/Authority Site

**Purpose:** SEO, GEO, brand expansion, AI content systems

| Page | Required | Purpose |
|------|----------|---------|
| Homepage | ✅ | Category index, featured content |
| Articles | ✅ | Primary content (AI-generated) |
| Categories/Tags | ✅ | Taxonomy for internal linking |
| Author/About | ✅ | Credibility signal |
| Contact | ✅ | Minimal |

**Preset config:**
```yaml
type: content
features:
  blog: true
  blog_categories: extensive  # Topic clusters
  internal_linking: optimized
  author_pages: true
  publishing_velocity: high
plugins:
  - limit-login-attempts-reloaded
  - rank-math-pro
  - flavor-ai-publisher  # Phase 3 custom plugin
theme: flavor-content  # Minimal, fast, SEO-optimized
```

**Note:** Optimized for Phase 3 AI integration — publishing velocity + internal linking over design.

---

### Site Type 4: Landing Page

**Purpose:** Experiments, ads, waitlists, GEO pages

| Page | Required | Purpose |
|------|----------|---------|
| Single page | ✅ | One message, one CTA |
| Email capture | ⚡ Optional | Waitlist signup |

**Preset config:**
```yaml
type: landing
features:
  blog: false
  minimal: true
  single_page: true
  email_capture: optional
plugins:
  - limit-login-attempts-reloaded
  # No SEO plugin needed for landing pages
theme: flavor-landing  # Ultra-minimal
```

**Key traits:**
- Ultra-fast to deploy
- Cheap to discard
- WordPress (not raw HTML) for Fabrik consistency: DNS, TLS, monitoring, analytics

---

### Site Type 5: E-commerce (Future)

**Purpose:** Product sales, digital goods

**Deferred until needed.** Will include:
- WooCommerce
- Payment integration
- Inventory management
- Order processing

---

### Preset Overlay Schema

```yaml
# Example: presets/saas.yaml
name: SaaS Companion
description: Marketing site for SaaS products
base: wordpress/base

features:
  blog: true
  blog_limit: 10
  docs: basic
  pricing: true
  signup_cta: true

plugins:
  install:
    - limit-login-attempts-reloaded
    - rank-math-pro
  premium:
    - rank-math-pro.zip  # From plugins/ folder

theme:
  name: flavor-starter
  source: zip  # or wordpress.org

pages:
  create:
    - title: Home
      template: front-page
    - title: Features
      template: page
    - title: Pricing
      template: page
    - title: About
      template: page
    - title: Contact
      template: page

settings:
  permalink_structure: "/%postname%/"
  timezone: "Europe/Istanbul"
  date_format: "Y-m-d"
```

---

### What We're Building in Phase 2

By the end of Phase 2, you will have:

1. **WP-CLI wrapper** that executes commands inside WordPress containers
2. **WordPress REST API client** for content operations
3. **Theme management** — install from WP repo, ZIP, or Git
4. **Plugin management** — install, activate, configure, handle license flags
5. **Content operations** — create/update pages, posts, menus, media, forms
6. **Extended CLI commands** for WordPress-specific operations
7. **Full WordPress lifecycle** manageable without wp-admin login

This transforms Fabrik from "deploy WordPress" to "fully operate WordPress sites programmatically."

---

### Prerequisites

Before starting Phase 2, confirm:

```
[ ] Phase 1 complete
[ ] At least one WordPress site deployed via Fabrik
[ ] Coolify API working
[ ] Can SSH into VPS
[ ] WordPress site accessible with HTTPS
```

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  FABRIK CLI                                                     │
│                                                                 │
│  fabrik wp:theme install <site> flavor                          │
│  fabrik wp:plugin install <site> woocommerce                    │
│  fabrik wp:page create <site> --title="About"                   │
│  fabrik wp:post create <site> --title="Welcome"                 │
│  fabrik wp:menu create <site> primary                           │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  WORDPRESS DRIVER                                               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  WP-CLI Executor                                        │    │
│  │  • Runs commands inside container via Coolify API       │    │
│  │  • Theme/plugin installation                            │    │
│  │  • Configuration changes                                │    │
│  │  • User management                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  REST API Client                                        │    │
│  │  • Content CRUD (pages, posts, media)                   │    │
│  │  • Menu management                                      │    │
│  │  • Taxonomy management                                  │    │
│  │  • Uses Application Passwords for auth                  │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  WORDPRESS CONTAINER                                            │
│                                                                 │
│  • WP-CLI installed                                             │
│  • REST API enabled                                             │
│  • Application password for API access                          │
└─────────────────────────────────────────────────────────────────┘
```

---

### Step 1: Implement WP-CLI Executor

**Why:** WP-CLI is the standard tool for managing WordPress from command line. It can do almost everything the admin dashboard does — install themes, activate plugins, change settings, manage users.

**How it works:** We execute WP-CLI commands inside the WordPress container through Coolify's execute API (or via Docker exec if Coolify doesn't support it directly).

**Code:**

```python
# compiler/wordpress/wp_cli.py

import os
import json
import subprocess
from typing import Optional, Union
from dataclasses import dataclass

from compiler.coolify import CoolifyDriver

@dataclass
class WPCLIResult:
    success: bool
    output: str
    error: Optional[str] = None

class WPCLIExecutor:
    """
    Executes WP-CLI commands inside WordPress containers.

    Two execution modes:
    1. Via Coolify API (if supported)
    2. Via SSH + docker exec (fallback)
    """

    def __init__(self, site_id: str):
        self.site_id = site_id
        self.coolify = CoolifyDriver()
        self._container_id = None
        self._app_uuid = None

    def _get_app_uuid(self) -> str:
        """Get Coolify application UUID for site."""
        if self._app_uuid:
            return self._app_uuid

        apps = self.coolify.list_applications()
        for app in apps:
            if app.get('name') == self.site_id:
                self._app_uuid = app['uuid']
                return self._app_uuid

        raise ValueError(f"Site not found in Coolify: {self.site_id}")

    def _get_container_id(self) -> str:
        """Get Docker container ID for the WordPress service."""
        if self._container_id:
            return self._container_id

        # This requires SSH access to the VPS
        vps_ip = os.environ.get('VPS_IP')
        ssh_user = os.environ.get('SSH_USER', 'deploy')

        # Find container by name pattern
        cmd = f"ssh {ssh_user}@{vps_ip} docker ps --filter 'name={self.site_id}' --format '{{{{.ID}}}}' | head -1"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode != 0 or not result.stdout.strip():
            raise RuntimeError(f"Could not find container for {self.site_id}")

        self._container_id = result.stdout.strip()
        return self._container_id

    def execute(self, command: str, json_output: bool = False) -> WPCLIResult:
        """
        Execute WP-CLI command in WordPress container.

        Args:
            command: WP-CLI command (without 'wp' prefix)
            json_output: If True, add --format=json and parse output

        Returns:
            WPCLIResult with success status. output, and error

        Example:
            execute("plugin list")
            execute("option get blogname")
            execute("post list", json_output=True)
        """

        full_command = f"wp {command}"
        if json_output:
            full_command += " --format=json"

        # Add --allow-root in case container runs as root
        full_command += " --allow-root"

        try:
            # Try Coolify API first
            result = self._execute_via_coolify(full_command)
        except Exception as e:
            # Fallback to SSH + docker exec
            result = self._execute_via_ssh(full_command)

        if json_output and result.success:
            try:
                result.output = json.loads(result.output)
            except json.JSONDecodeError:
                pass  # Return raw output if not valid JSON

        return result

    def _execute_via_coolify(self, command: str) -> WPCLIResult:
        """Execute via Coolify API (if supported)."""
        app_uuid = self._get_app_uuid()

        # Note: Coolify may or may not have an execute endpoint
        # This is implementation-dependent
        try:
            response = self.coolify._post(
                f'/api/v1/applications/{app_uuid}/execute',
                {'command': command}
            )
            return WPCLIResult(
                success=True,
                output=response.get('output', '')
            )
        except Exception as e:
            raise RuntimeError(f"Coolify execute not available: {e}")

    def _execute_via_ssh(self, command: str) -> WPCLIResult:
        """Execute via SSH + docker exec."""
        container_id = self._get_container_id()
        vps_ip = os.environ.get('VPS_IP')
        ssh_user = os.environ.get('SSH_USER', 'deploy')

        # Escape command for shell
        escaped_command = command.replace("'", "'\\''")

        ssh_cmd = f"ssh {ssh_user}@{vps_ip} docker exec {container_id} sh -c '{escaped_command}'"

        result = subprocess.run(
            ssh_cmd,
            shell=True,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return WPCLIResult(
                success=True,
                output=result.stdout.strip()
            )
        else:
            return WPCLIResult(
                success=False,
                output=result.stdout.strip(),
                error=result.stderr.strip()
            )

    # ─────────────────────────────────────────────────────────────
    # Convenience Methods
    # ─────────────────────────────────────────────────────────────

    def get_option(self, option_name: str) -> str:
        """Get WordPress option value."""
        result = self.execute(f"option get {option_name}")
        if result.success:
            return result.output
        raise RuntimeError(f"Failed to get option {option_name}: {result.error}")

    def set_option(self, option_name: str, value: Union[str, dict]) -> bool:
        """Set WordPress option value."""
        if isinstance(value, dict):
            value_str = json.dumps(value)
            result = self.execute(f"option update {option_name} '{value_str}' --format=json")
        else:
            result = self.execute(f"option update {option_name} '{value}'")
        return result.success

    def plugin_is_active(self, plugin_slug: str) -> bool:
        """Check if plugin is active."""
        result = self.execute(f"plugin is-active {plugin_slug}")
        return result.success

    def theme_is_active(self, theme_slug: str) -> bool:
        """Check if theme is active."""
        result = self.execute("theme list --status=active --field=name")
        return result.success and theme_slug in result.output
```

**Test:**

```bash
cd ~/projects/fabrik
source secrets/platform.env

python3 << 'EOF'
from compiler.wordpress.wp_cli import WPCLIExecutor

# Replace with your actual site ID
wp = WPCLIExecutor("test-wp-site")

# Test basic command
result = wp.execute("option get blogname")
print(f"Site name: {result.output}")

# Test plugin list
result = wp.execute("plugin list", json_output=True)
print(f"Plugins: {result.output}")
EOF
```

**Time:** 2 hours

---

### Step 2: Implement WordPress REST API Client

**Why:** While WP-CLI is great for configuration, the REST API is better for content operations (creating posts, uploading media). It's also more reliable for operations that need precise control.

**How it works:** WordPress exposes a REST API at `/wp-json/wp/v2/`. We authenticate using Application Passwords (built into WordPress 5.6+).

**Code:**

```python
# compiler/wordpress/rest_api.py

import os
import base64
from pathlib import Path
from typing import Optional, Union
import httpx
from dataclasses import dataclass

@dataclass
class WPPage:
    id: int
    slug: str
    title: str
    url: str
    status: str

@dataclass
class WPPost:
    id: int
    slug: str
    title: str
    url: str
    status: str

@dataclass
class WPMedia:
    id: int
    url: str
    title: str

class WordPressRESTClient:
    """
    WordPress REST API client for content operations.

    Uses Application Passwords for authentication.
    """

    def __init__(self, site_url: str, username: str, app_password: str):
        """
        Initialize client.

        Args:
            site_url: WordPress site URL (e.g., https://example.com)
            username: WordPress admin username
            app_password: Application password (from WP admin → Users → App Passwords)
        """
        self.site_url = site_url.rstrip('/')
        self.api_base = f"{self.site_url}/wp-json/wp/v2"

        # Create Basic Auth header
        credentials = f"{username}:{app_password}"
        encoded = base64.b64encode(credentials.encode()).decode()

        self.client = httpx.Client(
            headers={
                'Authorization': f'Basic {encoded}',
                'Content-Type': 'application/json'
            },
            timeout=30
        )

    def _get(self, endpoint: str, params: dict = None) -> Union[dict, list]:
        """Make GET request."""
        url = f"{self.api_base}/{endpoint}"
        resp = self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, data: dict = None) -> dict:
        """Make POST request."""
        url = f"{self.api_base}/{endpoint}"
        resp = self.client.post(url, json=data)
        resp.raise_for_status()
        return resp.json()

    def _put(self, endpoint: str, data: dict) -> dict:
        """Make PUT request."""
        url = f"{self.api_base}/{endpoint}"
        resp = self.client.put(url, json=data)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, endpoint: str) -> dict:
        """Make DELETE request."""
        url = f"{self.api_base}/{endpoint}"
        resp = self.client.delete(url)
        resp.raise_for_status()
        return resp.json()

    # ─────────────────────────────────────────────────────────────
    # Pages
    # ─────────────────────────────────────────────────────────────

    def list_pages(self, per_page: int = 100) -> list[WPPage]:
        """List all pages."""
        pages = self._get('pages', {'per_page': per_page})
        return [
            WPPage(
                id=p['id'],
                slug=p['slug'],
                title=p['title']['rendered'],
                url=p['link'],
                status=p['status']
            )
            for p in pages
        ]

    def get_page_by_slug(self, slug: str) -> Optional[WPPage]:
        """Get page by slug."""
        pages = self._get('pages', {'slug': slug})
        if not pages:
            return None
        p = pages[0]
        return WPPage(
            id=p['id'],
            slug=p['slug'],
            title=p['title']['rendered'],
            url=p['link'],
            status=p['status']
        )

    def create_page(
        self,
        title: str,
        content: str,
        slug: str = None,
        status: str = 'publish',
        template: str = None,
        parent: int = None,
        featured_media: int = None,
        meta: dict = None
    ) -> WPPage:
        """Create a new page."""

        data = {
            'title': title,
            'content': content,
            'status': status
        }

        if slug:
            data['slug'] = slug
        if template:
            data['template'] = template
        if parent:
            data['parent'] = parent
        if featured_media:
            data['featured_media'] = featured_media
        if meta:
            data['meta'] = meta

        p = self._post('pages', data)

        return WPPage(
            id=p['id'],
            slug=p['slug'],
            title=p['title']['rendered'],
            url=p['link'],
            status=p['status']
        )

    def update_page(
        self,
        page_id: int,
        title: str = None,
        content: str = None,
        status: str = None,
        featured_media: int = None,
        meta: dict = None
    ) -> WPPage:
        """Update existing page."""

        data = {}
        if title:
            data['title'] = title
        if content:
            data['content'] = content
        if status:
            data['status'] = status
        if featured_media:
            data['featured_media'] = featured_media
        if meta:
            data['meta'] = meta

        p = self._put(f'pages/{page_id}', data)

        return WPPage(
            id=p['id'],
            slug=p['slug'],
            title=p['title']['rendered'],
            url=p['link'],
            status=p['status']
        )

    def delete_page(self, page_id: int, force: bool = True) -> bool:
        """Delete a page."""
        try:
            self._delete(f'pages/{page_id}?force={str(force).lower()}')
            return True
        except:
            return False

    # ─────────────────────────────────────────────────────────────
    # Posts
    # ─────────────────────────────────────────────────────────────

    def list_posts(self, per_page: int = 100, status: str = 'any') -> list[WPPost]:
        """List posts."""
        posts = self._get('posts', {'per_page': per_page, 'status': status})
        return [
            WPPost(
                id=p['id'],
                slug=p['slug'],
                title=p['title']['rendered'],
                url=p['link'],
                status=p['status']
            )
            for p in posts
        ]

    def get_post_by_slug(self, slug: str) -> Optional[WPPost]:
        """Get post by slug."""
        posts = self._get('posts', {'slug': slug})
        if not posts:
            return None
        p = posts[0]
        return WPPost(
            id=p['id'],
            slug=p['slug'],
            title=p['title']['rendered'],
            url=p['link'],
            status=p['status']
        )

    def create_post(
        self,
        title: str,
        content: str,
        slug: str = None,
        status: str = 'publish',
        categories: list[int] = None,
        tags: list[int] = None,
        featured_media: int = None,
        excerpt: str = None,
        meta: dict = None
    ) -> WPPost:
        """Create a new post."""

        data = {
            'title': title,
            'content': content,
            'status': status
        }

        if slug:
            data['slug'] = slug
        if categories:
            data['categories'] = categories
        if tags:
            data['tags'] = tags
        if featured_media:
            data['featured_media'] = featured_media
        if excerpt:
            data['excerpt'] = excerpt
        if meta:
            data['meta'] = meta

        p = self._post('posts', data)

        return WPPost(
            id=p['id'],
            slug=p['slug'],
            title=p['title']['rendered'],
            url=p['link'],
            status=p['status']
        )

    def update_post(
        self,
        post_id: int,
        title: str = None,
        content: str = None,
        status: str = None,
        categories: list[int] = None,
        tags: list[int] = None,
        featured_media: int = None,
        excerpt: str = None,
        meta: dict = None
    ) -> WPPost:
        """Update existing post."""

        data = {}
        if title:
            data['title'] = title
        if content:
            data['content'] = content
        if status:
            data['status'] = status
        if categories:
            data['categories'] = categories
        if tags:
            data['tags'] = tags
        if featured_media:
            data['featured_media'] = featured_media
        if excerpt:
            data['excerpt'] = excerpt
        if meta:
            data['meta'] = meta

        p = self._put(f'posts/{post_id}', data)

        return WPPost(
            id=p['id'],
            slug=p['slug'],
            title=p['title']['rendered'],
            url=p['link'],
            status=p['status']
        )

    # ─────────────────────────────────────────────────────────────
    # Media
    # ─────────────────────────────────────────────────────────────

    def upload_media(
        self,
        file_path: str,
        title: str = None,
        alt_text: str = None,
        caption: str = None
    ) -> WPMedia:
        """Upload media file."""

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Determine content type
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.pdf': 'application/pdf',
            '.mp4': 'video/mp4',
        }

        ext = path.suffix.lower()
        content_type = content_types.get(ext, 'application/octet-stream')

        # Upload
        url = f"{self.api_base}/media"

        with open(path, 'rb') as f:
            resp = httpx.post(
                url,
                headers={
                    'Authorization': self.client.headers['Authorization'],
                    'Content-Disposition': f'attachment; filename="{path.name}"',
                    'Content-Type': content_type
                },
                content=f.read()
            )

        resp.raise_for_status()
        m = resp.json()

        media_id = m['id']

        # Update title/alt/caption if provided
        if title or alt_text or caption:
            update_data = {}
            if title:
                update_data['title'] = title
            if alt_text:
                update_data['alt_text'] = alt_text
            if caption:
                update_data['caption'] = caption

            self._put(f'media/{media_id}', update_data)

        return WPMedia(
            id=media_id,
            url=m['source_url'],
            title=m.get('title', {}).get('rendered', '')
        )

    # ─────────────────────────────────────────────────────────────
    # Categories & Tags
    # ─────────────────────────────────────────────────────────────

    def list_categories(self) -> list[dict]:
        """List all categories."""
        return self._get('categories', {'per_page': 100})

    def get_or_create_category(self, name: str, slug: str = None) -> int:
        """Get category ID, create if not exists."""

        # Try to find existing
        cats = self._get('categories', {'search': name})
        for cat in cats:
            if cat['name'].lower() == name.lower():
                return cat['id']

        # Create new
        data = {'name': name}
        if slug:
            data['slug'] = slug

        cat = self._post('categories', data)
        return cat['id']

    def list_tags(self) -> list[dict]:
        """List all tags."""
        return self._get('tags', {'per_page': 100})

    def get_or_create_tag(self, name: str, slug: str = None) -> int:
        """Get tag ID, create if not exists."""

        # Try to find existing
        tags = self._get('tags', {'search': name})
        for tag in tags:
            if tag['name'].lower() == name.lower():
                return tag['id']

        # Create new
        data = {'name': name}
        if slug:
            data['slug'] = slug

        tag = self._post('tags', data)
        return tag['id']
```

**Time:** 2 hours

---

### Step 3: Create Application Password on Deploy

**Why:** The REST API needs authentication. Application Passwords are the secure way to do this in WordPress — they're separate from the user's login password and can be revoked.

**Implementation:** Add to wp-site post-deploy hooks.

**Code:**

```python
# compiler/wordpress/hooks.py

import os
from pathlib import Path
from compiler.wordpress.wp_cli import WPCLIExecutor
from compiler.spec_loader import Spec

def generate_app_password(site_id: str, app_name: str = "fabrik") -> str:
    """
    Generate WordPress Application Password for API access.

    Returns the password (only shown once, must be saved).
    """

    wp = WPCLIExecutor(site_id)

    # Create application password for admin user
    result = wp.execute(
        f"user application-password create admin {app_name} --porcelain"
    )

    if not result.success:
        raise RuntimeError(f"Failed to create app password: {result.error}")

    return result.output.strip()

def save_wp_credentials(site_id: str, admin_user: str, app_password: str, site_url: str):
    """Save WordPress API credentials to secrets file."""

    secrets_file = Path(f"secrets/projects/{site_id}.env")

    # Load existing
    existing = {}
    if secrets_file.exists():
        with open(secrets_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    existing[k] = v

    # Add WP credentials
    existing['WP_SITE_URL'] = site_url
    existing['WP_ADMIN_USER'] = admin_user
    existing['WP_APP_PASSWORD'] = app_password

    # Save
    with open(secrets_file, 'w') as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    os.chmod(secrets_file, 0o600)

def run_wp_post_deploy_hooks(spec: Spec, site_url: str):
    """
    Run post-deployment hooks for WordPress sites.

    1. Generate application password
    2. Save credentials
    3. Apply security hardening
    4. Install/activate plugins
    5. Configure settings
    """

    site_id = spec.id
    wp = WPCLIExecutor(site_id)

    print(f"[WP] Running post-deploy hooks for {site_id}")

    # 1. Generate application password
    print(f"[WP] Generating API credentials...")
    try:
        app_password = generate_app_password(site_id)
        admin_user = spec.env.get('WP_ADMIN_USER', 'admin')
        save_wp_credentials(site_id, admin_user, app_password, site_url)
        print(f"[WP] → Credentials saved to secrets/projects/{site_id}.env")
    except Exception as e:
        print(f"[WP] → Warning: Could not generate app password: {e}")

    # 2. Security hardening
    wp_config = spec.wordpress
    if wp_config:
        print(f"[WP] Applying security settings...")

        if wp_config.disable_file_edit:
            wp.execute("config set DISALLOW_FILE_EDIT true --raw")
            print(f"[WP] → Disabled file editing")

        if wp_config.disable_xmlrpc:
            # Install plugin to disable XML-RPC
            result = wp.execute("plugin install disable-xml-rpc --activate")
            if result.success:
                print(f"[WP] → Disabled XML-RPC")

    # 3. Install plugins
    if wp_config and wp_config.plugins:
        print(f"[WP] Installing plugins...")

        for plugin in wp_config.plugins:
            if plugin.source == 'wp_repo':
                cmd = f"plugin install {plugin.slug}"
                if plugin.activate:
                    cmd += " --activate"

                result = wp.execute(cmd)
                if result.success:
                    print(f"[WP] → Installed: {plugin.slug}")
                else:
                    print(f"[WP] → Failed: {plugin.slug}: {result.error}")

            elif plugin.source == 'zip' and plugin.zip_url:
                result = wp.execute(f"plugin install {plugin.zip_url}")
                if result.success and plugin.activate:
                    wp.execute(f"plugin activate {plugin.slug}")
                    print(f"[WP] → Installed from ZIP: {plugin.slug}")

    # 4. Configure basic settings
    print(f"[WP] Configuring settings...")

    # Set permalink structure
    wp.execute("rewrite structure '/%postname%/'")
    wp.execute("rewrite flush")
    print(f"[WP] → Set permalink structure")

    # Set timezone if specified
    if 'WP_TIMEZONE' in spec.env:
        wp.set_option('timezone_string', spec.env['WP_TIMEZONE'])
        print(f"[WP] → Set timezone: {spec.env['WP_TIMEZONE']}")

    # Set site title
    if 'WP_TITLE' in spec.env:
        wp.set_option('blogname', spec.env['WP_TITLE'])
        print(f"[WP] → Set site title")

    # Disable comments by default
    wp.set_option('default_comment_status', 'closed')
    wp.set_option('default_ping_status', 'closed')
    print(f"[WP] → Disabled default comments")

    print(f"[WP] Post-deploy hooks complete")
```

**Integration with apply.py:**

```python
# In cli/apply.py, after deployment succeeds:

# 10. Post-deploy hooks
if spec.template == "wp-site":
    from compiler.wordpress.hooks import run_wp_post_deploy_hooks
    site_url = f"https://{spec.domain}"
    run_wp_post_deploy_hooks(spec, site_url)
```

**Time:** 30 minutes

---

### Step 4-6: Theme Management

**Why:** Themes control the look and feel of WordPress sites. We need to install themes from multiple sources:
- WordPress.org repository (free themes)
- ZIP files (premium themes)
- Git repositories (custom themes)

**Code:**

```python
# compiler/wordpress/themes.py

from dataclasses import dataclass
from typing import Optional
from enum import Enum

from compiler.wordpress.wp_cli import WPCLIExecutor

class ThemeSource(str, Enum):
    WP_REPO = "wp_repo"
    ZIP = "zip"
    GIT = "git"

@dataclass
class ThemeConfig:
    slug: str
    source: ThemeSource = ThemeSource.WP_REPO
    zip_url: Optional[str] = None
    git_repo: Optional[str] = None
    activate: bool = True

@dataclass
class ThemeResult:
    slug: str
    installed: bool
    active: bool
    error: Optional[str] = None

class ThemeManager:
    """Manage WordPress themes."""

    def __init__(self, site_id: str):
        self.site_id = site_id
        self.wp = WPCLIExecutor(site_id)

    def list_themes(self) -> list[dict]:
        """List all installed themes."""
        result = self.wp.execute("theme list", json_output=True)
        if result.success:
            return result.output
        return []

    def get_active_theme(self) -> Optional[str]:
        """Get currently active theme slug."""
        result = self.wp.execute("theme list --status=active --field=name")
        if result.success:
            return result.output.strip()
        return None

    def is_installed(self, slug: str) -> bool:
        """Check if theme is installed."""
        themes = self.list_themes()
        return any(t.get('name') == slug for t in themes)

    def install(self, config: ThemeConfig) -> ThemeResult:
        """Install a theme from various sources."""

        # Check if already installed
        if self.is_installed(config.slug):
            if config.activate:
                return self.activate(config.slug)
            return ThemeResult(slug=config.slug, installed=True, active=False)

        # Install based on source
        if config.source == ThemeSource.WP_REPO:
            result = self._install_from_repo(config.slug)
        elif config.source == ThemeSource.ZIP:
            if not config.zip_url:
                return ThemeResult(
                    slug=config.slug,
                    installed=False,
                    active=False,
                    error="ZIP URL required for zip source"
                )
            result = self._install_from_zip(config.zip_url)
        elif config.source == ThemeSource.GIT:
            if not config.git_repo:
                return ThemeResult(
                    slug=config.slug,
                    installed=False,
                    active=False,
                    error="Git repo required for git source"
                )
            result = self._install_from_git(config.slug, config.git_repo)
        else:
            return ThemeResult(
                slug=config.slug,
                installed=False,
                active=False,
                error=f"Unknown source: {config.source}"
            )

        if not result.installed:
            return result

        # Activate if requested
        if config.activate:
            return self.activate(config.slug)

        return result

    def _install_from_repo(self, slug: str) -> ThemeResult:
        """Install theme from WordPress.org repository."""
        result = self.wp.execute(f"theme install {slug}")

        if result.success:
            return ThemeResult(slug=slug, installed=True, active=False)

        return ThemeResult(
            slug=slug,
            installed=False,
            active=False,
            error=result.error or result.output
        )

    def _install_from_zip(self, zip_url: str) -> ThemeResult:
        """Install theme from ZIP URL."""
        result = self.wp.execute(f"theme install '{zip_url}'")

        # Extract slug from output or URL
        # WP-CLI outputs "Installing Theme from URL" ... "Theme installed successfully."
        slug = zip_url.split('/')[-1].replace('.zip', '')

        if result.success:
            return ThemeResult(slug=slug, installed=True, active=False)

        return ThemeResult(
            slug=slug,
            installed=False,
            active=False,
            error=result.error or result.output
        )

    def _install_from_git(self, slug: str, git_repo: str) -> ThemeResult:
        """Install theme from Git repository."""

        # Clone directly into themes directory
        themes_path = "/var/www/html/wp-content/themes"

        result = self.wp.execute(
            f"eval 'exec(\"cd {themes_path} && git clone {git_repo} {slug}\");'"
        )

        # Alternative: use shell command via docker exec
        # This is a bit hacky but works

        if result.success or self.is_installed(slug):
            return ThemeResult(slug=slug, installed=True, active=False)

        return ThemeResult(
            slug=slug,
            installed=False,
            active=False,
            error=result.error or "Failed to clone theme"
        )

    def activate(self, slug: str) -> ThemeResult:
        """Activate a theme."""

        if not self.is_installed(slug):
            return ThemeResult(
                slug=slug,
                installed=False,
                active=False,
                error="Theme not installed"
            )

        result = self.wp.execute(f"theme activate {slug}")

        if result.success:
            return ThemeResult(slug=slug, installed=True, active=True)

        return ThemeResult(
            slug=slug,
            installed=True,
            active=False,
            error=result.error or result.output
        )

    def delete(self, slug: str) -> bool:
        """Delete a theme."""

        # Can't delete active theme
        if self.get_active_theme() == slug:
            return False

        result = self.wp.execute(f"theme delete {slug}")
        return result.success

    def update(self, slug: str = None) -> bool:
        """Update theme(s)."""

        if slug:
            result = self.wp.execute(f"theme update {slug}")
        else:
            result = self.wp.execute("theme update --all")

        return result.success

    def set_customizer_option(self, key: str, value: str) -> bool:
        """Set theme customizer option (theme mod)."""
        result = self.wp.execute(f"theme mod set {key} '{value}'")
        return result.success

    def get_customizer_option(self, key: str) -> Optional[str]:
        """Get theme customizer option."""
        result = self.wp.execute(f"theme mod get {key}")
        if result.success:
            return result.output
        return None
```

**Time:** 3 hours total

---

### Step 7-10: Plugin Management

**Why:** Plugins extend WordPress functionality. We need to:
- Install from WordPress.org repository
- Install from ZIP files (premium plugins)
- Activate/deactivate plugins
- Configure plugin settings
- Handle plugins that require manual license activation

**Code:**

```python
# compiler/wordpress/plugins.py

from dataclasses import dataclass
from typing import Optional, Union
from enum import Enum
import json

from compiler.wordpress.wp_cli import WPCLIExecutor

class PluginSource(str, Enum):
    WP_REPO = "wp_repo"
    ZIP = "zip"

@dataclass
class PluginConfig:
    slug: str
    source: PluginSource = PluginSource.WP_REPO
    zip_url: Optional[str] = None
    activate: bool = True
    config: Optional[dict] = None  # Plugin-specific settings
    requires_license: bool = False

@dataclass
class PluginResult:
    slug: str
    installed: bool
    active: bool
    manual_action_required: Optional[str] = None
    error: Optional[str] = None

class PluginManager:
    """Manage WordPress plugins."""

    def __init__(self, site_id: str):
        self.site_id = site_id
        self.wp = WPCLIExecutor(site_id)

    def list_plugins(self, status: str = None) -> list[dict]:
        """
        List plugins.

        Args:
            status: Filter by status (active, inactive, active-network)
        """
        cmd = "plugin list"
        if status:
            cmd += f" --status={status}"

        result = self.wp.execute(cmd, json_output=True)
        if result.success:
            return result.output
        return []

    def is_installed(self, slug: str) -> bool:
        """Check if plugin is installed."""
        plugins = self.list_plugins()
        return any(p.get('name') == slug for p in plugins)

    def is_active(self, slug: str) -> bool:
        """Check if plugin is active."""
        result = self.wp.execute(f"plugin is-active {slug}")
        return result.success

    def install(self, config: PluginConfig) -> PluginResult:
        """Install a plugin."""

        # Check if already installed
        if self.is_installed(config.slug):
            if config.activate and not self.is_active(config.slug):
                return self.activate(config.slug, config.requires_license)

            return PluginResult(
                slug=config.slug,
                installed=True,
                active=self.is_active(config.slug)
            )

        # Install based on source
        if config.source == PluginSource.WP_REPO:
            result = self._install_from_repo(config.slug)
        elif config.source == PluginSource.ZIP:
            if not config.zip_url:
                return PluginResult(
                    slug=config.slug,
                    installed=False,
                    active=False,
                    error="ZIP URL required"
                )
            result = self._install_from_zip(config.zip_url, config.slug)
        else:
            return PluginResult(
                slug=config.slug,
                installed=False,
                active=False,
                error=f"Unknown source: {config.source}"
            )

        if not result.installed:
            return result

        # Apply configuration
        if config.config:
            self._apply_config(config.slug, config.config)

        # Activate if requested
        if config.activate:
            return self.activate(config.slug, config.requires_license)

        return result

    def _install_from_repo(self, slug: str) -> PluginResult:
        """Install from WordPress.org."""
        result = self.wp.execute(f"plugin install {slug}")

        if result.success:
            return PluginResult(slug=slug, installed=True, active=False)

        return PluginResult(
            slug=slug,
            installed=False,
            active=False,
            error=result.error or result.output
        )

    def _install_from_zip(self, zip_url: str, slug: str) -> PluginResult:
        """Install from ZIP URL."""
        result = self.wp.execute(f"plugin install '{zip_url}'")

        if result.success:
            return PluginResult(slug=slug, installed=True, active=False)

        return PluginResult(
            slug=slug,
            installed=False,
            active=False,
            error=result.error or result.output
        )

    def _apply_config(self, slug: str, config: dict):
        """Apply plugin-specific configuration."""

        # Plugin configurations are stored as WordPress options
        # The option name varies by plugin

        # Common patterns:
        plugin_option_patterns = {
            'wordpress-seo': 'wpseo',  # Yoast SEO
            'woocommerce': 'woocommerce',
            'contact-form-7': 'wpcf7',
            'limit-login-attempts-reloaded': 'limit_login',
        }

        prefix = plugin_option_patterns.get(slug, slug.replace('-', '_'))

        for key, value in config.items():
            option_name = f"{prefix}_{key}" if not key.startswith(prefix) else key

            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
                self.wp.execute(f"option update {option_name} '{value_str}' --format=json")
            else:
                self.wp.execute(f"option update {option_name} '{value}'")

    def activate(self, slug: str, requires_license: bool = False) -> PluginResult:
        """Activate a plugin."""

        if not self.is_installed(slug):
            return PluginResult(
                slug=slug,
                installed=False,
                active=False,
                error="Plugin not installed"
            )

        result = self.wp.execute(f"plugin activate {slug}")

        if result.success:
            manual_action = None
            if requires_license:
                manual_action = f"Plugin '{slug}' requires license activation in wp-admin"

            return PluginResult(
                slug=slug,
                installed=True,
                active=True,
                manual_action_required=manual_action
            )

        return PluginResult(
            slug=slug,
            installed=True,
            active=False,
            error=result.error or result.output
        )

    def deactivate(self, slug: str) -> PluginResult:
        """Deactivate a plugin."""
        result = self.wp.execute(f"plugin deactivate {slug}")

        return PluginResult(
            slug=slug,
            installed=True,
            active=not result.success,
            error=None if result.success else result.error
        )

    def delete(self, slug: str) -> bool:
        """Delete a plugin."""

        # Deactivate first
        if self.is_active(slug):
            self.deactivate(slug)

        result = self.wp.execute(f"plugin delete {slug}")
        return result.success

    def update(self, slug: str = None) -> bool:
        """Update plugin(s)."""

        if slug:
            result = self.wp.execute(f"plugin update {slug}")
        else:
            result = self.wp.execute("plugin update --all")

        return result.success

    # ─────────────────────────────────────────────────────────────
    # Plugin-Specific Helpers
    # ─────────────────────────────────────────────────────────────

    def configure_yoast(self, settings: dict):
        """Configure Yoast SEO plugin."""

        # Yoast uses multiple option keys
        option_mappings = {
            'title_separator': 'wpseo_titles',
            'company_name': 'wpseo',
            'website_type': 'wpseo',
        }

        for key, value in settings.items():
            if key in option_mappings:
                # Yoast stores complex options, need to merge
                current = self.wp.get_option(option_mappings[key])
                if current:
                    try:
                        current_dict = json.loads(current)
                        current_dict[key] = value
                        self.wp.set_option(option_mappings[key], current_dict)
                    except:
                        pass

    def configure_woocommerce(self, settings: dict):
        """Configure WooCommerce plugin."""

        common_settings = {
            'country': 'woocommerce_default_country',
            'currency': 'woocommerce_currency',
            'weight_unit': 'woocommerce_weight_unit',
            'dimension_unit': 'woocommerce_dimension_unit',
        }

        for key, value in settings.items():
            if key in common_settings:
                self.wp.set_option(common_settings[key], value)
```

**Time:** 5 hours total

---

### Step 11-15: Content Operations

**Why:** Creating pages, posts, menus, and media programmatically enables:
- Automated site setup with starter content
- AI-generated content publishing
- Bulk content operations
- Content migration

**Code:**

```python
# compiler/wordpress/content.py

from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import re

from compiler.wordpress.wp_cli import WPCLIExecutor
from compiler.wordpress.rest_api import WordPressRESTClient, WPPage, WPPost, WPMedia

@dataclass
class PageConfig:
    title: str
    slug: str
    content: Optional[str] = None
    content_file: Optional[str] = None
    template: Optional[str] = None
    status: str = "publish"
    parent_slug: Optional[str] = None
    featured_image: Optional[str] = None
    meta: Optional[dict] = None

@dataclass
class PostConfig:
    title: str
    slug: str
    content: Optional[str] = None
    content_file: Optional[str] = None
    status: str = "publish"
    categories: list[str] = None
    tags: list[str] = None
    featured_image: Optional[str] = None
    excerpt: Optional[str] = None
    meta: Optional[dict] = None

@dataclass
class MenuConfig:
    name: str
    location: str
    items: list[dict]

class ContentManager:
    """Manage WordPress content (pages, posts, menus, media)."""

    def __init__(self, site_id: str, site_url: str, admin_user: str, app_password: str):
        self.site_id = site_id
        self.wp_cli = WPCLIExecutor(site_id)
        self.rest_api = WordPressRESTClient(site_url, admin_user, app_password)

    # ─────────────────────────────────────────────────────────────
    # Pages
    # ─────────────────────────────────────────────────────────────

    def create_page(self, config: PageConfig) -> WPPage:
        """Create or update a page."""

        # Load content from file if specified
        content = config.content
        if config.content_file:
            content = Path(config.content_file).read_text()

        if not content:
            content = ""

        # Check if page exists
        existing = self.rest_api.get_page_by_slug(config.slug)

        # Resolve parent ID if specified
        parent_id = None
        if config.parent_slug:
            parent = self.rest_api.get_page_by_slug(config.parent_slug)
            if parent:
                parent_id = parent.id

        # Handle featured image
        featured_media_id = None
        if config.featured_image:
            media = self.rest_api.upload_media(config.featured_image)
            featured_media_id = media.id

        if existing:
            # Update
            return self.rest_api.update_page(
                page_id=existing.id,
                title=config.title,
                content=content,
                status=config.status,
                featured_media=featured_media_id,
                meta=config.meta
            )
        else:
            # Create
            return self.rest_api.create_page(
                title=config.title,
                content=content,
                slug=config.slug,
                status=config.status,
                template=config.template,
                parent=parent_id,
                featured_media=featured_media_id,
                meta=config.meta
            )

    def create_pages_from_config(self, pages: list[PageConfig]) -> list[WPPage]:
        """Create multiple pages from config list."""
        results = []
        for page_config in pages:
            page = self.create_page(page_config)
            results.append(page)
            print(f"  → Created page: {page.title} ({page.url})")
        return results

    # ─────────────────────────────────────────────────────────────
    # Posts
    # ─────────────────────────────────────────────────────────────

    def create_post(self, config: PostConfig) -> WPPost:
        """Create or update a post."""

        # Load content from file if specified
        content = config.content
        if config.content_file:
            content = Path(config.content_file).read_text()

        if not content:
            content = ""

        # Check if post exists
        existing = self.rest_api.get_post_by_slug(config.slug)

        # Resolve categories
        category_ids = []
        if config.categories:
            for cat_name in config.categories:
                cat_id = self.rest_api.get_or_create_category(cat_name)
                category_ids.append(cat_id)

        # Resolve tags
        tag_ids = []
        if config.tags:
            for tag_name in config.tags:
                tag_id = self.rest_api.get_or_create_tag(tag_name)
                tag_ids.append(tag_id)

        # Handle featured image
        featured_media_id = None
        if config.featured_image:
            media = self.rest_api.upload_media(config.featured_image)
            featured_media_id = media.id

        if existing:
            # Update
            return self.rest_api.update_post(
                post_id=existing.id,
                title=config.title,
                content=content,
                status=config.status,
                categories=category_ids if category_ids else None,
                tags=tag_ids if tag_ids else None,
                featured_media=featured_media_id,
                excerpt=config.excerpt,
                meta=config.meta
            )
        else:
            # Create
            return self.rest_api.create_post(
                title=config.title,
                content=content,
                slug=config.slug,
                status=config.status,
                categories=category_ids if category_ids else None,
                tags=tag_ids if tag_ids else None,
                featured_media=featured_media_id,
                excerpt=config.excerpt,
                meta=config.meta
            )

    # ─────────────────────────────────────────────────────────────
    # Menus
    # ─────────────────────────────────────────────────────────────

    def create_menu(self, config: MenuConfig) -> int:
        """Create a navigation menu."""

        wp = self.wp_cli

        # Delete existing menu with same name
        wp.execute(f"menu delete '{config.name}'")

        # Create menu
        result = wp.execute(f"menu create '{config.name}' --porcelain")
        if not result.success:
            raise RuntimeError(f"Failed to create menu: {result.error}")

        menu_id = result.output.strip()

        # Add items
        self._add_menu_items(menu_id, config.items)

        # Assign to location
        if config.location:
            wp.execute(f"menu location assign {menu_id} {config.location}")

        return int(menu_id)

    def _add_menu_items(self, menu_id: str, items: list[dict], parent_id: int = 0):
        """Recursively add menu items."""

        wp = self.wp_cli

        for item in items:
            item_type = item.get('type', 'custom')
            title = item.get('title', '')

            if item_type == 'page':
                # Get page ID by slug
                page = self.rest_api.get_page_by_slug(item.get('slug', ''))
                if page:
                    result = wp.execute(
                        f"menu item add-post {menu_id} {page.id} "
                        f"--title='{title}' --parent-id={parent_id} --porcelain"
                    )
                else:
                    continue

            elif item_type == 'post':
                post = self.rest_api.get_post_by_slug(item.get('slug', ''))
                if post:
                    result = wp.execute(
                        f"menu item add-post {menu_id} {post.id} "
                        f"--title='{title}' --parent-id={parent_id} --porcelain"
                    )
                else:
                    continue

            elif item_type == 'category':
                cat_id = self.rest_api.get_or_create_category(item.get('name', ''))
                result = wp.execute(
                    f"menu item add-term {menu_id} category {cat_id} "
                    f"--title='{title}' --parent-id={parent_id} --porcelain"
                )

            else:  # custom link
                url = item.get('url', '#')
                result = wp.execute(
                    f"menu item add-custom {menu_id} '{title}' '{url}' "
                    f"--parent-id={parent_id} --porcelain"
                )

            if result.success:
                item_id = int(result.output.strip())

                # Handle children
                if item.get('children'):
                    self._add_menu_items(menu_id, item['children'], parent_id=item_id)

    # ─────────────────────────────────────────────────────────────
    # Media
    # ─────────────────────────────────────────────────────────────

    def upload_media(self, file_path: str, title: str = None, alt_text: str = None) -> WPMedia:
        """Upload media file."""
        return self.rest_api.upload_media(file_path, title=title, alt_text=alt_text)

    def upload_media_batch(self, files: list[str]) -> list[WPMedia]:
        """Upload multiple media files."""
        results = []
        for file_path in files:
            media = self.upload_media(file_path)
            results.append(media)
            print(f"  → Uploaded: {Path(file_path).name} (ID: {media.id})")
        return results

    # ─────────────────────────────────────────────────────────────
    # Contact Form 7
    # ─────────────────────────────────────────────────────────────

    def create_contact_form(self, title: str, form_template: str, mail_to: str) -> int:
        """Create Contact Form 7 form."""

        wp = self.wp_cli

        # CF7 forms are custom post type 'wpcf7_contact_form'
        # WP-CLI doesn't have direct CF7 support, so we use the plugin's CLI if available

        # Try CF7 CLI extension
        result = wp.execute(
            f"cf7 create '{title}' --porcelain"
        )

        if result.success:
            form_id = result.output.strip()

            # Update form content
            wp.execute(f"cf7 update {form_id} --form='{form_template}'")

            # Update mail settings
            mail_config = {
                'to': mail_to,
                'subject': f'[{title}] New submission',
                'body': '[your-message]',
            }
            wp.execute(f"cf7 update {form_id} --mail='{str(mail_config)}'")

            return int(form_id)

        # Fallback: create via REST API or direct DB
        # This is more complex, skip for now
        raise RuntimeError("Contact Form 7 CLI not available")
```

**Time:** 5 hours total

---

### Step 16-18: CLI Extensions

**Why:** Expose WordPress operations through Fabrik CLI for easy access.

**Code:**

```python
# cli/wp.py

import click
import os
from pathlib import Path

def load_env():
    """Load environment."""
    env_file = Path("secrets/platform.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v

def load_site_credentials(site_id: str) -> dict:
    """Load site-specific credentials."""
    secrets_file = Path(f"secrets/projects/{site_id}.env")
    if not secrets_file.exists():
        raise click.ClickException(f"No credentials found for {site_id}")

    creds = {}
    with open(secrets_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                creds[k] = v

    return creds

@click.group()
def wp():
    """WordPress management commands."""
    load_env()

# ─────────────────────────────────────────────────────────────
# Theme Commands
# ─────────────────────────────────────────────────────────────

@wp.group()
def theme():
    """Theme management."""
    pass

@theme.command('list')
@click.argument('site_id')
def theme_list(site_id: str):
    """List installed themes."""
    from compiler.wordpress.themes import ThemeManager

    tm = ThemeManager(site_id)
    themes = tm.list_themes()

    click.echo(f"\nThemes for {site_id}:")
    click.echo("-" * 40)

    for t in themes:
        status = "✓ active" if t.get('status') == 'active' else ""
        click.echo(f"  {t.get('name', 'unknown'):20} {status}")

@theme.command('install')
@click.argument('site_id')
@click.argument('theme_slug')
@click.option('--activate/--no-activate', default=True)
@click.option('--source', type=click.Choice(['wp_repo', 'zip']), default='wp_repo')
@click.option('--zip-url', help='URL for zip source')
def theme_install(site_id: str, theme_slug: str, activate: bool, source: str, zip_url: str):
    """Install a theme."""
    from compiler.wordpress.themes import ThemeManager, ThemeConfig, ThemeSource

    tm = ThemeManager(site_id)

    config = ThemeConfig(
        slug=theme_slug,
        source=ThemeSource(source),
        zip_url=zip_url,
        activate=activate
    )

    click.echo(f"Installing theme: {theme_slug}")
    result = tm.install(config)

    if result.installed:
        status = "active" if result.active else "installed"
        click.echo(f"✓ Theme {theme_slug} {status}")
    else:
        click.echo(f"✗ Failed: {result.error}")

@theme.command('activate')
@click.argument('site_id')
@click.argument('theme_slug')
def theme_activate(site_id: str, theme_slug: str):
    """Activate a theme."""
    from compiler.wordpress.themes import ThemeManager

    tm = ThemeManager(site_id)
    result = tm.activate(theme_slug)

    if result.active:
        click.echo(f"✓ Theme {theme_slug} activated")
    else:
        click.echo(f"✗ Failed: {result.error}")

# ─────────────────────────────────────────────────────────────
# Plugin Commands
# ─────────────────────────────────────────────────────────────

@wp.group()
def plugin():
    """Plugin management."""
    pass

@plugin.command('list')
@click.argument('site_id')
@click.option('--status', type=click.Choice(['active', 'inactive', 'all']), default='all')
def plugin_list(site_id: str, status: str):
    """List installed plugins."""
    from compiler.wordpress.plugins import PluginManager

    pm = PluginManager(site_id)

    status_filter = None if status == 'all' else status
    plugins = pm.list_plugins(status=status_filter)

    click.echo(f"\nPlugins for {site_id}:")
    click.echo("-" * 50)

    for p in plugins:
        active = "✓" if p.get('status') == 'active' else " "
        click.echo(f"  [{active}] {p.get('name', 'unknown'):30} {p.get('version', '')}")

@plugin.command('install')
@click.argument('site_id')
@click.argument('plugin_slug')
@click.option('--activate/--no-activate', default=True)
@click.option('--source', type=click.Choice(['wp_repo', 'zip']), default='wp_repo')
@click.option('--zip-url', help='URL for zip source')
def plugin_install(site_id: str, plugin_slug: str, activate: bool, source: str, zip_url: str):
    """Install a plugin."""
    from compiler.wordpress.plugins import PluginManager, PluginConfig, PluginSource

    pm = PluginManager(site_id)

    config = PluginConfig(
        slug=plugin_slug,
        source=PluginSource(source),
        zip_url=zip_url,
        activate=activate
    )

    click.echo(f"Installing plugin: {plugin_slug}")
    result = pm.install(config)

    if result.installed:
        status = "active" if result.active else "installed"
        click.echo(f"✓ Plugin {plugin_slug} {status}")

        if result.manual_action_required:
            click.echo(f"⚠ Manual action: {result.manual_action_required}")
    else:
        click.echo(f"✗ Failed: {result.error}")

@plugin.command('activate')
@click.argument('site_id')
@click.argument('plugin_slug')
def plugin_activate(site_id: str, plugin_slug: str):
    """Activate a plugin."""
    from compiler.wordpress.plugins import PluginManager

    pm = PluginManager(site_id)
    result = pm.activate(plugin_slug)

    if result.active:
        click.echo(f"✓ Plugin {plugin_slug} activated")
    else:
        click.echo(f"✗ Failed: {result.error}")

@plugin.command('deactivate')
@click.argument('site_id')
@click.argument('plugin_slug')
def plugin_deactivate(site_id: str, plugin_slug: str):
    """Deactivate a plugin."""
    from compiler.wordpress.plugins import PluginManager

    pm = PluginManager(site_id)
    result = pm.deactivate(plugin_slug)

    if not result.active:
        click.echo(f"✓ Plugin {plugin_slug} deactivated")
    else:
        click.echo(f"✗ Failed to deactivate")

# ─────────────────────────────────────────────────────────────
# Content Commands
# ─────────────────────────────────────────────────────────────

@wp.group()
def page():
    """Page management."""
    pass

@page.command('list')
@click.argument('site_id')
def page_list(site_id: str):
    """List pages."""
    creds = load_site_credentials(site_id)

    from compiler.wordpress.rest_api import WordPressRESTClient

    client = WordPressRESTClient(
        creds['WP_SITE_URL'],
        creds['WP_ADMIN_USER'],
        creds['WP_APP_PASSWORD']
    )

    pages = client.list_pages()

    click.echo(f"\nPages for {site_id}:")
    click.echo("-" * 60)

    for p in pages:
        click.echo(f"  {p.title:30} /{p.slug}")

@page.command('create')
@click.argument('site_id')
@click.option('--title', required=True)
@click.option('--slug', required=True)
@click.option('--content', help='Page content (HTML)')
@click.option('--content-file', type=click.Path(exists=True), help='File with content')
@click.option('--status', default='publish')
@click.option('--template')
def page_create(site_id: str, title: str, slug: str, content: str, content_file: str, status: str, template: str):
    """Create a page."""
    creds = load_site_credentials(site_id)

    from compiler.wordpress.content import ContentManager, PageConfig

    cm = ContentManager(
        site_id,
        creds['WP_SITE_URL'],
        creds['WP_ADMIN_USER'],
        creds['WP_APP_PASSWORD']
    )

    config = PageConfig(
        title=title,
        slug=slug,
        content=content,
        content_file=content_file,
        status=status,
        template=template
    )

    page = cm.create_page(config)
    click.echo(f"✓ Created page: {page.title}")
    click.echo(f"  URL: {page.url}")

@wp.group()
def post():
    """Post management."""
    pass

@post.command('list')
@click.argument('site_id')
def post_list(site_id: str):
    """List posts."""
    creds = load_site_credentials(site_id)

    from compiler.wordpress.rest_api import WordPressRESTClient

    client = WordPressRESTClient(
        creds['WP_SITE_URL'],
        creds['WP_ADMIN_USER'],
        creds['WP_APP_PASSWORD']
    )

    posts = client.list_posts()

    click.echo(f"\nPosts for {site_id}:")
    click.echo("-" * 60)

    for p in posts:
        click.echo(f"  {p.title:30} /{p.slug}")

@post.command('create')
@click.argument('site_id')
@click.option('--title', required=True)
@click.option('--slug', required=True)
@click.option('--content', help='Post content (HTML)')
@click.option('--content-file', type=click.Path(exists=True), help='File with content')
@click.option('--status', default='publish')
@click.option('--categories', help='Comma-separated category names')
@click.option('--tags', help='Comma-separated tag names')
def post_create(site_id: str, title: str, slug: str, content: str, content_file: str, status: str, categories: str, tags: str):
    """Create a post."""
    creds = load_site_credentials(site_id)

    from compiler.wordpress.content import ContentManager, PostConfig

    cm = ContentManager(
        site_id,
        creds['WP_SITE_URL'],
        creds['WP_ADMIN_USER'],
        creds['WP_APP_PASSWORD']
    )

    config = PostConfig(
        title=title,
        slug=slug,
        content=content,
        content_file=content_file,
        status=status,
        categories=categories.split(',') if categories else None,
        tags=tags.split(',') if tags else None
    )

    post = cm.create_post(config)
    click.echo(f"✓ Created post: {post.title}")
    click.echo(f"  URL: {post.url}")

@wp.group()
def menu():
    """Menu management."""
    pass

@menu.command('create')
@click.argument('site_id')
@click.argument('menu_name')
@click.option('--location', help='Theme menu location')
@click.option('--items-file', type=click.Path(exists=True), help='YAML file with menu items')
def menu_create(site_id: str, menu_name: str, location: str, items_file: str):
    """Create a menu."""
    import yaml

    creds = load_site_credentials(site_id)

    from compiler.wordpress.content import ContentManager, MenuConfig

    cm = ContentManager(
        site_id,
        creds['WP_SITE_URL'],
        creds['WP_ADMIN_USER'],
        creds['WP_APP_PASSWORD']
    )

    # Load items from file
    items = []
    if items_file:
        with open(items_file) as f:
            items = yaml.safe_load(f)

    config = MenuConfig(
        name=menu_name,
        location=location,
        items=items
    )

    menu_id = cm.create_menu(config)
    click.echo(f"✓ Created menu: {menu_name} (ID: {menu_id})")

# ─────────────────────────────────────────────────────────────
# Utility Commands
# ─────────────────────────────────────────────────────────────

@wp.command('cli')
@click.argument('site_id')
@click.argument('command')
def wp_cli(site_id: str, command: str):
    """Run arbitrary WP-CLI command."""
    from compiler.wordpress.wp_cli import WPCLIExecutor

    wp = WPCLIExecutor(site_id)
    result = wp.execute(command)

    if result.success:
        click.echo(result.output)
    else:
        click.echo(f"Error: {result.error}")
        raise click.Abort()

if __name__ == '__main__':
    wp()
```

**Update main CLI to include wp commands:**

```python
# cli/main.py

import click
from cli.new import new
from cli.plan import plan
from cli.apply import apply
from cli.status import status
from cli.logs import logs
from cli.destroy import destroy
from cli.wp import wp

@click.group()
def cli():
    """Fabrik - Infrastructure deployment platform."""
    pass

# Core commands
cli.add_command(new)
cli.add_command(plan)
cli.add_command(apply)
cli.add_command(status)
cli.add_command(logs)
cli.add_command(destroy)

# WordPress commands
cli.add_command(wp)

if __name__ == '__main__':
    cli()
```

**Time:** 3 hours total

---

### Phase 2 Complete

After completing all steps, you have:

```
✓ WP-CLI wrapper executing commands in containers
✓ WordPress REST API client for content operations
✓ Application password generation on deploy
✓ Theme management (install, activate, customize)
✓ Plugin management (install, activate, configure)
✓ Page creation and updates
✓ Post creation and updates
✓ Menu creation
✓ Media uploads
✓ Contact form creation (CF7)
✓ Extended CLI commands for all operations
```

**New CLI commands available:**

```bash
# Themes
fabrik wp theme list <site>
fabrik wp theme install <site> <theme>
fabrik wp theme activate <site> <theme>

# Plugins
fabrik wp plugin list <site>
fabrik wp plugin install <site> <plugin>
fabrik wp plugin activate <site> <plugin>
fabrik wp plugin deactivate <site> <plugin>

# Content
fabrik wp page list <site>
fabrik wp page create <site> --title="About" --slug="about"
fabrik wp post list <site>
fabrik wp post create <site> --title="Hello" --slug="hello"
fabrik wp menu create <site> primary --location=primary-menu

# Raw WP-CLI
fabrik wp cli <site> "option get blogname"
```

---

### Phase 2 Summary

| Step | Task | Time |
|------|------|------|
| 1 | WP-CLI Executor | 2 hrs |
| 2 | REST API Client | 2 hrs |
| 3 | Application Password Generation | 30 min |
| 4-6 | Theme Management | 3 hrs |
| 7-10 | Plugin Management | 5 hrs |
| 11-15 | Content Operations | 5 hrs |
| 16-18 | CLI Extensions | 3 hrs |

**Total: ~20 hours (3-4 days)**

---

### What's Next (Phase 3 Preview)

Phase 3 adds AI content integration:
- LLM client wrapper
- Page/post generation from prompts
- Content revision based on instructions
- Bulk content generation
- Windsurf agent integration

With Phase 2 complete, your Windsurf agents can already:
1. Deploy WordPress sites (`fabrik apply`)
2. Install themes and plugins (`fabrik wp theme/plugin install`)
3. Create content (`fabrik wp page/post create`)

---
