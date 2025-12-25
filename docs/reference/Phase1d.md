# Phase 1d: WordPress Site Builder Automation

**Status: 🚧 IN PROGRESS**
**Last Updated:** 2025-12-25

---

## Overview

Phase 1d completes the WordPress automation by implementing the missing components needed to deploy a fully configured WordPress site from a YAML specification.

**Goal:** Deploy `ocoron.com` (and future sites) with a single `fabrik wp:deploy site-id` command.

**Prerequisite Phases:**
- Phase 1: VPS + Coolify + Core CLI ✅
- Phase 1b: Supabase + R2 ✅
- Phase 1c: Cloudflare DNS ✅
- Phase 2: WordPress template + WP-CLI wrapper ✅

---

## Progress Tracker

| # | Component | Status | Priority | Effort |
|---|-----------|--------|----------|--------|
| 1 | Settings applicator | ❌ Pending | HIGH | Low |
| 2 | Page creator | ❌ Pending | HIGH | Medium |
| 3 | Menu creator | ❌ Pending | HIGH | Low |
| 4 | Content generator (AI) | ❌ Pending | HIGH | Medium |
| 5 | Media uploader | ❌ Pending | MEDIUM | Low |
| 6 | Theme customizer | ❌ Pending | MEDIUM | Medium |
| 7 | Form creator | ❌ Pending | MEDIUM | Medium |
| 8 | SEO applicator | ❌ Pending | MEDIUM | Medium |
| 9 | Analytics injector | ❌ Pending | MEDIUM | Low |
| 10 | Legal content generator | ❌ Pending | MEDIUM | Low |
| 11 | Default content cleanup | ❌ Pending | LOW | Low |
| 12 | Editor account creation | ❌ Pending | LOW | Low |
| 13 | Post-deploy cache clear | ❌ Pending | LOW | Low |

**Completion: 0/13 tasks (0%)**

---

## What We Have

### Existing Infrastructure
- **VPS:** Hardened server with Coolify, Traefik, PostgreSQL, Redis
- **DNS:** Cloudflare driver with automatic A record creation
- **WordPress Template:** Docker Compose with WP + MariaDB + backup sidecar
- **WP-CLI Wrapper:** Execute commands inside WordPress containers
- **REST API Client:** CRUD operations for posts, pages, media
- **Plugin Stack:** Full premium plugin collection defined and placed
- **Presets:** company, saas, content, landing, ecommerce YAMLs
- **Site Spec:** `ocoron.com.yaml` fully defined with pages, menus, branding

### What's Missing (This Phase)
The "last mile" automation to:
1. Apply WordPress settings from spec
2. Create pages and menus from spec
3. Generate content for pages
4. Upload brand assets (logo, favicon)
5. Configure theme with brand colors/fonts
6. Create forms from spec
7. Configure SEO settings
8. Inject analytics codes

---

## Component Details

### 1. Settings Applicator

**Purpose:** Apply WordPress settings from spec YAML via WP-CLI.

**Input (from spec):**
```yaml
settings:
  blogname: "{{ site_name }}"
  blogdescription: "{{ site_tagline }}"
  permalink_structure: "/%postname%/"
  timezone_string: "Europe/Istanbul"
  date_format: "Y-m-d"
  show_on_front: page
  page_on_front: Home
  page_for_posts: Insights
```

**Implementation:**
```python
# compiler/wordpress/settings.py
def apply_settings(site_id: str, settings: dict):
    """Apply WordPress settings via WP-CLI."""
    wp = WPCLIExecutor(site_id)
    
    for key, value in settings.items():
        if key in ['page_on_front', 'page_for_posts']:
            # These need page ID lookup
            page_id = wp.get_page_id_by_title(value)
            wp.execute(f"option update {key} {page_id}")
        else:
            wp.execute(f"option update {key} '{value}'")
```

**WP-CLI Commands:**
```bash
wp option update blogname "Ocoron"
wp option update blogdescription "Professional Services"
wp option update permalink_structure "/%postname%/"
wp option update timezone_string "Europe/Istanbul"
wp option update date_format "Y-m-d"
wp option update show_on_front page
wp option update page_on_front <page_id>
wp option update page_for_posts <page_id>
wp option update blog_public 1  # Enable indexing
```

**Status:** ❌ Not implemented

---

### 2. Page Creator

**Purpose:** Create WordPress pages from spec YAML via REST API.

**Input (from spec):**
```yaml
pages:
  - slug: ""
    title: "Home"
    title_tr: "Ana Sayfa"
    template: full-width
    show_in_menu: false
    status: publish
    sections:
      - type: hero
        headline: "Strategic Consulting..."
```

**Implementation:**
```python
# compiler/wordpress/pages.py
async def create_pages(site_id: str, pages: list, languages: dict):
    """Create pages from spec via REST API."""
    wp_api = WordPressAPIClient(site_id)
    
    created_pages = {}
    for page in pages:
        # Create primary language version
        response = await wp_api.create_page(
            title=page['title'],
            slug=page['slug'] or None,  # Empty for homepage
            status=page.get('status', 'draft'),
            template=page.get('template', ''),
            content=page.get('content', ''),  # Will be filled by content generator
        )
        created_pages[page['slug']] = response['id']
        
        # Create translations if multilingual
        if languages.get('additional'):
            for lang in languages['additional']:
                lang_key = lang.replace('_', '-').lower()[:2]  # tr_TR -> tr
                title_key = f"title_{lang_key}"
                if title_key in page:
                    await wp_api.create_translation(
                        original_id=response['id'],
                        language=lang,
                        title=page[title_key]
                    )
        
        # Handle child pages
        if page.get('children'):
            for child in page['children']:
                child['parent'] = response['id']
                await create_pages(site_id, [child], languages)
    
    return created_pages
```

**REST API Calls:**
```
POST /wp-json/wp/v2/pages
{
  "title": "Home",
  "slug": "",
  "status": "publish",
  "template": "full-width",
  "content": ""
}
```

**Status:** ❌ Not implemented

---

### 3. Menu Creator

**Purpose:** Create WordPress navigation menus from spec YAML.

**Input (from spec):**
```yaml
menus:
  primary:
    - title: Services
      title_tr: Hizmetler
      url: /services
      children:
        - title: Investment Incentives
          url: /services/investment-incentives
    - title: About
      url: /about
  footer:
    - title: Privacy Policy
      url: /privacy-policy
```

**Implementation:**
```python
# compiler/wordpress/menus.py
def create_menus(site_id: str, menus: dict, page_ids: dict):
    """Create navigation menus from spec."""
    wp = WPCLIExecutor(site_id)
    
    for menu_name, items in menus.items():
        # Create menu
        result = wp.execute(f"menu create '{menu_name}'")
        menu_id = extract_menu_id(result.output)
        
        # Add items
        for item in items:
            add_menu_item(wp, menu_id, item, page_ids)
        
        # Assign to location
        location = 'primary' if menu_name == 'primary' else menu_name
        wp.execute(f"menu location assign {menu_id} {location}")

def add_menu_item(wp, menu_id, item, page_ids, parent_id=None):
    """Add a menu item, handling nested children."""
    # Check if it's an internal page or external URL
    if item['url'].startswith('/'):
        page_slug = item['url'].strip('/')
        if page_slug in page_ids:
            cmd = f"menu item add-post {menu_id} {page_ids[page_slug]}"
        else:
            cmd = f"menu item add-custom {menu_id} '{item['url']}' '{item['title']}'"
    else:
        cmd = f"menu item add-custom {menu_id} '{item['url']}' '{item['title']}'"
    
    if parent_id:
        cmd += f" --parent-id={parent_id}"
    
    result = wp.execute(cmd)
    item_id = extract_item_id(result.output)
    
    # Handle children
    if item.get('children'):
        for child in item['children']:
            add_menu_item(wp, menu_id, child, page_ids, parent_id=item_id)
```

**WP-CLI Commands:**
```bash
wp menu create "primary"
wp menu item add-post primary <page_id> --title="Services"
wp menu item add-custom primary "/contact" "Contact"
wp menu location assign primary primary
```

**Status:** ❌ Not implemented

---

### 4. Content Generator (AI)

**Purpose:** Generate page content from spec sections using Claude API.

**Input (from spec):**
```yaml
pages:
  - slug: about
    title: "About"
    sections:
      - type: text_block
        content: ""  # TODO: Company story, mission, vision
```

**Implementation:**
```python
# compiler/wordpress/content.py
import anthropic

async def generate_page_content(page: dict, brand: dict, site_context: str) -> str:
    """Generate page content using Claude."""
    client = anthropic.Anthropic()
    
    prompt = f"""Generate professional website content for a {page['title']} page.

Brand: {brand['name']}
Tagline: {brand['tagline']}
Context: {site_context}

Sections to include:
{format_sections(page.get('sections', []))}

Requirements:
- Professional tone
- SEO-friendly headings (H2, H3)
- Clear value propositions
- Call-to-action where appropriate
- Output as HTML suitable for WordPress

Do not include <html>, <head>, or <body> tags. Just the content."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text
```

**For ocoron.com specifically:**
- Homepage: Hero + features + services grid + CTA
- About: Company story, mission, vision, credibility
- Services: 8 service category pages with descriptions
- Contact: Form intro + contact methods
- Legal: Privacy Policy, Terms (template-based)

**Status:** ❌ Not implemented

---

### 5. Media Uploader

**Purpose:** Upload brand assets (logo, favicon, images) to WordPress.

**Input (from spec):**
```yaml
brand:
  logo:
    primary: "ocoron.com-media/logo.svg"
    favicon: "ocoron.com-media/Favicon/favicon.ico"
```

**Implementation:**
```python
# compiler/wordpress/media.py
async def upload_brand_assets(site_id: str, brand: dict, assets_dir: str):
    """Upload brand assets to WordPress media library."""
    wp_api = WordPressAPIClient(site_id)
    
    uploaded = {}
    
    for asset_type, path in brand.get('logo', {}).items():
        if path:
            full_path = os.path.join(assets_dir, path)
            if os.path.exists(full_path):
                response = await wp_api.upload_media(full_path)
                uploaded[asset_type] = response['id']
    
    # Set site icon (favicon)
    if 'favicon' in uploaded:
        wp = WPCLIExecutor(site_id)
        wp.execute(f"option update site_icon {uploaded['favicon']}")
    
    return uploaded
```

**REST API:**
```
POST /wp-json/wp/v2/media
Content-Type: multipart/form-data
file: <binary>
```

**Status:** ❌ Not implemented

---

### 6. Theme Customizer

**Purpose:** Apply brand colors and fonts to GeneratePress theme.

**Input (from spec):**
```yaml
brand:
  colors:
    primary: "#1e3a5f"
    secondary: "#0891b2"
    accent: "#ea580c"
  fonts:
    heading: "Inter"
    body: "Inter"
```

**Implementation:**
GeneratePress stores settings as theme mods. We apply them via WP-CLI:

```python
# compiler/wordpress/theme.py
def apply_theme_customization(site_id: str, brand: dict):
    """Apply brand colors and fonts to GeneratePress."""
    wp = WPCLIExecutor(site_id)
    
    colors = brand.get('colors', {})
    fonts = brand.get('fonts', {})
    
    # GP Premium color settings
    color_settings = {
        'generate_settings[global_colors][0][color]': colors.get('primary'),
        'generate_settings[global_colors][1][color]': colors.get('secondary'),
        'generate_settings[global_colors][2][color]': colors.get('accent'),
    }
    
    for key, value in color_settings.items():
        if value:
            wp.execute(f"option update '{key}' '{value}'")
    
    # Typography settings
    if fonts.get('body'):
        wp.execute(f"option update generate_settings[font_body] '{fonts['body']}'")
    if fonts.get('heading'):
        wp.execute(f"option update generate_settings[font_heading] '{fonts['heading']}'")
```

**Status:** ❌ Not implemented

---

### 7. Form Creator

**Purpose:** Create contact forms from spec using Fluent Forms.

**Input (from spec):**
```yaml
contact:
  form:
    fields: [name, email, company, subject, message]
    recipient: "contact@ocoron.com"
    success_message: "Thank you for your message."
    spam_protection: turnstile
```

**Implementation:**
Fluent Forms has a REST API we can use:

```python
# compiler/wordpress/forms.py
async def create_contact_form(site_id: str, form_config: dict):
    """Create a Fluent Forms contact form."""
    wp_api = WordPressAPIClient(site_id)
    
    # Build form structure
    fields = []
    for field in form_config.get('fields', []):
        fields.append(get_field_config(field))
    
    # Add spam protection
    if form_config.get('spam_protection') == 'turnstile':
        fields.append({
            'element': 'turnstile',
            'attributes': {'name': 'cf-turnstile'}
        })
    
    form_data = {
        'title': 'Contact Form',
        'fields': fields,
        'notifications': [{
            'sendTo': {'email': form_config.get('recipient')},
            'subject': 'New Contact Form Submission',
        }],
        'confirmation': {
            'message': form_config.get('success_message')
        }
    }
    
    # Create via Fluent Forms API
    response = await wp_api.post('/wp-json/fluentform/v1/forms', form_data)
    return response['id']
```

**Status:** ❌ Not implemented

---

### 8. SEO Applicator

**Purpose:** Configure Rank Math SEO settings from spec.

**Input (from spec):**
```yaml
seo:
  title_separator: "|"
  homepage_title: "Ocoron | Government Incentives & Business Consultancy"
  homepage_description: "Expert consultancy in Government Incentives..."
  schema:
    type: Organization
    name: Ocoron
  analytics:
    google_analytics: "G-VK6FMQRVRL"
```

**Implementation:**
```python
# compiler/wordpress/seo.py
def apply_seo_settings(site_id: str, seo: dict):
    """Apply SEO settings to Rank Math."""
    wp = WPCLIExecutor(site_id)
    
    # Title separator
    wp.execute(f"option update rank_math_title_separator '{seo.get('title_separator', '|')}'")
    
    # Homepage SEO
    if seo.get('homepage_title'):
        wp.execute(f"option update rank_math_homepage_title '{seo['homepage_title']}'")
    if seo.get('homepage_description'):
        wp.execute(f"option update rank_math_homepage_description '{seo['homepage_description']}'")
    
    # Schema
    schema = seo.get('schema', {})
    if schema.get('type'):
        wp.execute(f"option update rank_math_knowledgegraph_type '{schema['type'].lower()}'")
    if schema.get('name'):
        wp.execute(f"option update rank_math_knowledgegraph_name '{schema['name']}'")
    
    # Enable modules
    wp.execute("option update rank_math_modules 'sitemap,analytics,seo-analysis,instant-indexing'")
```

**Status:** ❌ Not implemented

---

### 9. Analytics Injector

**Purpose:** Add Google Analytics / GTM codes to site.

**Input (from spec):**
```yaml
seo:
  analytics:
    google_analytics: "G-VK6FMQRVRL"
    google_tag_manager: ""
```

**Implementation:**
Rank Math Pro handles analytics injection:

```python
# compiler/wordpress/analytics.py
def setup_analytics(site_id: str, analytics: dict):
    """Configure analytics via Rank Math."""
    wp = WPCLIExecutor(site_id)
    
    if analytics.get('google_analytics'):
        ga_id = analytics['google_analytics']
        wp.execute(f"option update rank_math_analytics_id '{ga_id}'")
        wp.execute("option update rank_math_analytics_enabled '1'")
```

**Alternative:** Use PixelYourSite Pro for more advanced tracking.

**Status:** ❌ Not implemented

---

### 10. Legal Content Generator

**Purpose:** Generate Privacy Policy and Terms of Service from templates.

**Implementation:**
```python
# compiler/wordpress/legal.py
def generate_privacy_policy(brand: dict, contact: dict) -> str:
    """Generate Privacy Policy content."""
    template = """
<h2>Privacy Policy</h2>
<p>Last updated: {date}</p>

<h3>Who We Are</h3>
<p>This website is operated by {company_name}. Contact us at {email}.</p>

<h3>Information We Collect</h3>
<p>We collect information you provide through our contact form, including your name, email address, and message content.</p>

<h3>How We Use Your Information</h3>
<ul>
<li>To respond to your inquiries</li>
<li>To improve our services</li>
<li>To send relevant communications (with consent)</li>
</ul>

<h3>Cookies</h3>
<p>We use cookies for analytics and functionality. You can manage cookie preferences through our consent banner.</p>

<h3>Your Rights</h3>
<p>You have the right to access, correct, or delete your personal data. Contact us at {email}.</p>

<h3>Contact</h3>
<p>For privacy inquiries: {email}</p>
"""
    return template.format(
        date=datetime.now().strftime('%Y-%m-%d'),
        company_name=brand.get('name'),
        email=contact.get('email')
    )
```

**Status:** ❌ Not implemented

---

### 11. Default Content Cleanup

**Purpose:** Remove WordPress default content (sample post, page, comments).

**Implementation:**
```python
def cleanup_defaults(site_id: str):
    """Remove default WordPress content."""
    wp = WPCLIExecutor(site_id)
    
    # Delete default post
    wp.execute("post delete 1 --force")
    
    # Delete sample page
    wp.execute("post delete 2 --force")
    
    # Delete default comment
    wp.execute("comment delete 1 --force")
    
    # Remove default plugins
    wp.execute("plugin delete hello")
    wp.execute("plugin delete akismet")
```

**Status:** ❌ Not implemented

---

### 12. Editor Account Creation

**Purpose:** Create a non-admin user for daily content editing.

**Implementation:**
```python
def create_editor_account(site_id: str, email: str):
    """Create an Editor role user."""
    wp = WPCLIExecutor(site_id)
    
    username = email.split('@')[0]
    password = generate_secure_password()
    
    wp.execute(f"user create {username} {email} --role=editor --user_pass={password}")
    
    return {'username': username, 'password': password}
```

**Status:** ❌ Not implemented

---

### 13. Post-Deploy Cache Clear

**Purpose:** Clear all caches after deployment.

**Implementation:**
```python
def clear_caches(site_id: str):
    """Clear all caches after deployment."""
    wp = WPCLIExecutor(site_id)
    
    # WordPress cache
    wp.execute("cache flush")
    
    # FlyingPress cache (if installed)
    wp.execute("flyingpress purge --all")
    
    # Rewrite rules
    wp.execute("rewrite flush")
```

**Status:** ❌ Not implemented

---

## Deployment Flow

Once all components are implemented, the deployment flow will be:

```
fabrik wp:deploy ocoron-com
    │
    ├── 1. Create DNS record (Cloudflare)
    ├── 2. Deploy WordPress container (Coolify)
    ├── 3. Wait for WordPress ready
    ├── 4. Cleanup default content
    ├── 5. Apply settings
    ├── 6. Install plugins (from preset + spec)
    ├── 7. Upload media assets
    ├── 8. Apply theme customization
    ├── 9. Create pages
    ├── 10. Generate content (AI or template)
    ├── 11. Create menus
    ├── 12. Create forms
    ├── 13. Apply SEO settings
    ├── 14. Setup analytics
    ├── 15. Create editor account
    ├── 16. Clear caches
    └── 17. Verify deployment
```

---

## Implementation Schedule

| Week | Components | Deliverable |
|------|------------|-------------|
| 1 | #1 Settings, #2 Pages, #3 Menus | Core page structure |
| 1 | #4 Content generator | AI-generated content |
| 2 | #5 Media, #6 Theme | Brand assets applied |
| 2 | #7 Forms, #8 SEO | Lead capture + SEO |
| 2 | #9-13 Remaining | Full automation |

**Target:** Deploy ocoron.com by end of implementation.

---

## Files to Create

```
/opt/fabrik/compiler/wordpress/
├── __init__.py
├── settings.py      # #1 Settings applicator
├── pages.py         # #2 Page creator
├── menus.py         # #3 Menu creator
├── content.py       # #4 Content generator
├── media.py         # #5 Media uploader
├── theme.py         # #6 Theme customizer
├── forms.py         # #7 Form creator
├── seo.py           # #8 SEO applicator
├── analytics.py     # #9 Analytics injector
├── legal.py         # #10 Legal content
├── cleanup.py       # #11 Default cleanup
├── users.py         # #12 User management
├── cache.py         # #13 Cache management
└── deploy.py        # Orchestrator
```

---

## Next Steps

1. **Start with Component #1: Settings Applicator** — Quick win, foundation for others
2. Implement incrementally, test against wp-test.vps1.ocoron.com
3. Once #1-4 work, deploy ocoron.com

Ready to begin?
