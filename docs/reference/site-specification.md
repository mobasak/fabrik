# Site Specification Guide

**Last Updated:** 2025-12-24

---

## Overview

A **Site Specification** is a complete definition of a WordPress site before deployment. It captures everything needed to build the site:

- Brand identity (logo, colors, fonts)
- Site structure (pages, menus)
- Content strategy
- Plugin configuration
- SEO settings
- Deployment details

## Directory Structure

```
/opt/fabrik/
├── specs/
│   └── sites/
│       ├── ocoron.com.yaml      # Site spec
│       └── assets/
│           └── ocoron/          # Site assets
│               ├── logo.svg
│               ├── logo-light.svg
│               └── favicon.png
└── templates/wordpress/
    └── site-spec-schema.yaml    # Schema reference
```

## Workflow

```
1. CREATE SITE SPEC
   └── Copy schema, fill in details
   
2. GATHER ASSETS
   └── Logo, favicon, brand assets
   
3. DEFINE CONTENT
   └── Page structure, sections, copy
   
4. REVIEW & APPROVE
   └── Stakeholder sign-off
   
5. DEPLOY
   └── fabrik apply specs/sites/example.com.yaml
```

---

## Schema Sections

### Basic Information

```yaml
id: ocoron-com              # Unique ID (used in Coolify, DNS-safe)
domain: ocoron.com          # Primary domain
preset: company             # company | saas | content | landing | ecommerce
environment: production     # production | staging
```

**Preset determines:**
- Default plugins
- Page templates
- Feature set
- Blog configuration

### Brand Identity

```yaml
brand:
  name: "Ocoron"
  tagline: "Building intelligent systems"
  
  logo:
    primary: "assets/ocoron/logo.svg"
    light: "assets/ocoron/logo-light.svg"
    icon: "assets/ocoron/icon.svg"
    favicon: "assets/ocoron/favicon.png"
  
  colors:
    primary: "#1a365d"      # Navy blue
    secondary: "#2b6cb0"    # Lighter blue
    accent: "#ed8936"       # Orange (CTAs)
    background: "#ffffff"
    text: "#1a1a1a"
    text_light: "#6b7280"
  
  fonts:
    heading: "Inter"
    body: "Inter"
    source: google
```

**Color guidelines:**
- Primary: Main brand color (headers, links)
- Secondary: Supporting color (sections, hover states)
- Accent: Call-to-action buttons, highlights
- Keep contrast ratio accessible (WCAG AA minimum)

### Languages

```yaml
languages:
  primary: en_US
  additional: [tr_TR]
  plugin: wpml              # wpml | polylang | none

timezone: "Europe/Istanbul"
```

**Plugin choice:**
- **WPML**: Premium, better for complex sites, you have license
- **Polylang**: Free, simpler sites

### Pages

```yaml
pages:
  - slug: ""                # Homepage
    title: "Home"
    template: full-width
    show_in_menu: false     # Usually linked via logo
    sections:
      - type: hero
        headline: "Build systems that scale"
        subheadline: "We create automation, AI, and software solutions"
        cta_text: "View Products"
        cta_url: "/products"
        background: gradient
      
      - type: features
        headline: "What We Build"
        columns: 3
        items:
          - icon: code
            title: "Automation"
            description: "..."
          - icon: brain
            title: "AI Systems"
            description: "..."
          - icon: shield
            title: "Compliance"
            description: "..."
      
      - type: cta_banner
        headline: "Ready to start?"
        cta_text: "Contact Us"
        cta_url: "/contact"

  - slug: products
    title: "Products"
    show_in_menu: true
    menu_order: 1
    children:
      - slug: fabrik
        title: "Fabrik"
        sections:
          - type: product_hero
          - type: features
          - type: pricing
          - type: cta
      
      - slug: compliance-os
        title: "ComplianceOS"
```

**Section Types:**

| Type | Purpose |
|------|---------|
| `hero` | Full-width banner with headline, CTA |
| `features` | Grid of feature cards (2-4 columns) |
| `testimonials` | Customer quotes carousel |
| `cta_banner` | Call-to-action strip |
| `contact_form` | Contact form with fields |
| `product_hero` | Product-specific hero |
| `pricing` | Pricing table |
| `team` | Team member grid |
| `faq` | Accordion FAQ |
| `text_block` | Rich text content |
| `gallery` | Image gallery/grid |

### Navigation

```yaml
menus:
  primary:
    - title: Products
      url: /products
      children:
        - title: Fabrik
          url: /products/fabrik
        - title: ComplianceOS
          url: /products/compliance-os
    - title: About
      url: /about
    - title: Insights
      url: /insights
    - title: Contact
      url: /contact
  
  footer:
    - title: Privacy Policy
      url: /privacy
    - title: Terms of Service
      url: /terms
```

### Blog

```yaml
blog:
  enabled: true
  index_page: insights
  categories:
    - name: Product Updates
      slug: updates
    - name: Technical
      slug: technical
    - name: Industry
      slug: industry
  posts_per_page: 10
```

### Contact

```yaml
contact:
  email: hello@ocoron.com
  phone: ""
  address: ""
  
  social:
    linkedin: "https://linkedin.com/company/ocoron"
    twitter: ""
    github: "https://github.com/ocoron"
  
  form:
    fields: [name, email, subject, message]
    recipient: hello@ocoron.com
    spam_protection: turnstile
```

### Plugins

```yaml
plugins:
  # Add plugins beyond preset defaults
  add:
    - wpml                  # Multilingual
    - automatorwp           # Automation
  
  # Skip plugins from preset
  skip:
    - polylang              # Using WPML instead
  
  # Plugin-specific config
  config:
    rank-math:
      sitemap: true
      schema: organization
```

### SEO

```yaml
seo:
  title_separator: "|"
  homepage_title: "Ocoron | Building Intelligent Systems"
  homepage_description: "We build automation, AI, and compliance solutions for modern businesses."
  
  schema:
    type: Organization
    name: Ocoron
    
  analytics:
    google_analytics: "G-XXXXXXXXXX"
    
  verification:
    google: "verification-code"
```

### Content Source

```yaml
content:
  source: ai_draft          # manual | ai_draft | import
  
  ai_config:
    model: claude
    tone: professional
    review_required: true
```

**Options:**
- `manual`: You provide all content
- `ai_draft`: AI generates drafts for review
- `import`: Migrate from existing site

---

## Creating a New Site Spec

### Step 1: Copy Schema

```bash
cp templates/wordpress/site-spec-schema.yaml specs/sites/example.com.yaml
```

### Step 2: Fill Required Fields

Minimum required:
- `id`, `domain`, `preset`
- `brand.name`, `brand.tagline`
- `brand.colors` (at least primary, secondary, accent)
- `pages` (at least homepage)
- `contact.email`

### Step 3: Gather Assets

```bash
mkdir -p specs/sites/assets/example
# Add logo.svg, favicon.png
```

### Step 4: Define Pages

Start with the sitemap, then add sections to each page.

### Step 5: Review

Check:
- [ ] All pages have content defined
- [ ] Navigation matches pages
- [ ] Colors are accessible
- [ ] Contact info correct
- [ ] SEO fields filled

### Step 6: Deploy

```bash
fabrik apply specs/sites/example.com.yaml
```

---

## Preset Defaults

Each preset includes default plugins and features. Site specs can add or skip plugins.

| Preset | Default Features |
|--------|------------------|
| `company` | Blog (light), multilingual option, contact form |
| `saas` | Pricing page, signup CTA, docs integration |
| `content` | Heavy blog, author pages, categories |
| `landing` | Single page, email capture, minimal |
| `ecommerce` | WooCommerce, cart, checkout, products |

See `@/opt/fabrik/docs/reference/full-plugin-stack.md` for complete plugin lists.

---

## Examples

### Minimal Company Site

```yaml
id: example-corp
domain: example.com
preset: company

brand:
  name: "Example Corp"
  tagline: "Making examples since 2020"
  colors:
    primary: "#2563eb"
    secondary: "#1e40af"
    accent: "#f59e0b"

languages:
  primary: en_US

pages:
  - slug: ""
    title: Home
  - slug: about
    title: About
  - slug: contact
    title: Contact

contact:
  email: hello@example.com
```

### Multilingual SaaS Site

```yaml
id: my-saas
domain: mysaas.com
preset: saas

brand:
  name: "MySaaS"
  tagline: "Simplify your workflow"
  colors:
    primary: "#7c3aed"
    secondary: "#5b21b6"
    accent: "#10b981"

languages:
  primary: en_US
  additional: [de_DE, fr_FR]
  plugin: wpml

pages:
  - slug: ""
    title: Home
  - slug: features
    title: Features
  - slug: pricing
    title: Pricing
  - slug: signup
    title: Get Started

plugins:
  add:
    - fluent-forms-pro
    - automatorwp
```
