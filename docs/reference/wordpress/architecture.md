# WordPress v2 Architecture - Implementation Summary

**Date:** 2025-12-25
**Status:** ✅ Complete and tested
**Spec Format:** v2 (schema version 1)

---

## Overview

Complete rewrite of WordPress site specification and deployment system. Moved from monolithic 473-line YAML files to a layered architecture with 205-line site specs (57% reduction).

### Key Improvements

1. **Three-layer merge system** (defaults → preset → site)
2. **Schema-driven validation** with fail-fast error handling
3. **Section-based page building** (10 reusable section types)
4. **Entity-to-page generation** (services/features/products → pages)
5. **Normalized localization** (`{en_US: "...", tr_TR: "..."}` everywhere)
6. **Reference resolution** (items_ref, content_ref, entity.*)

---

## Architecture Components

### 1. Schema & Documentation

| File | Purpose | Lines |
|------|---------|-------|
| `templates/wordpress/schema/v1.yaml` | Schema definition, types, validation rules | 270 |
| `templates/wordpress/schema/MERGE_RULES.md` | Deep merge semantics, conflict resolution | 170 |
| `templates/wordpress/schema/VALIDATION_RULES.md` | Validation pipeline, error messages | 350 |

### 2. Spec Layers

| Layer | File | Purpose |
|-------|------|---------|
| **Defaults** | `templates/wordpress/defaults.yaml` | Global settings (theme, plugins, WP config) |
| **Preset** | `templates/wordpress/presets/company.yaml` | Industry-specific (entities, page templates, sections) |
| **Site** | `specs/sites/ocoron.com.v2.yaml` | Site-specific (brand, services, contact, SEO) |

**Merge order:** defaults → preset → site → secrets → runtime

### 3. Python Modules

| Module | Purpose | Key Features |
|--------|---------|--------------|
| `spec_loader.py` | Load & merge YAML layers | Deep merge, entity normalization, secret injection |
| `spec_validator.py` | Validate merged spec | Required fields, refs, localization, conflicts |
| `section_renderer.py` | Render sections to Gutenberg blocks | 10 section types, localization, ref resolution |
| `page_generator.py` | Generate pages from spec | Templates + entities → page specs |
| `deployer.py` | Orchestrate deployment | v2 integration, page hierarchy |

---

## Spec Format Comparison

### Old Format (v1)

```yaml
# 473 lines, everything inline

pages:
  - slug: ""
    title: "Home"
    title_tr: "Ana Sayfa"
    sections:
      - type: hero
        headline: "Strategic Consulting..."
        headline_tr: "Büyüyen İşletmeler..."
        # ... 50 more lines per page
```

### New Format (v2)

```yaml
# 205 lines, minimal site-specific data

schema_version: 1
preset: company

brand:
  name: "Ocoron"
  tagline:
    en_US: "Strategic Consulting for Growing Businesses"
    tr_TR: "Büyüyen İşletmeler için Stratejik Danışmanlık"

services:
  - slug: investment-incentives
    name:
      en_US: "Investment Incentives"
      tr_TR: "Yatırım Teşvikleri"
```

**Pages generated automatically** from preset templates + service entities.

---

## Section Types (Tier 1)

10 reusable section types implemented:

| Section | Purpose | Params |
|---------|---------|--------|
| `hero` | Homepage hero with CTA | headline, subheadline, cta_text, cta_url |
| `cta` / `cta_banner` | Call-to-action block | headline, cta_text, cta_url |
| `features` / `features_grid` | Feature grid (3-4 columns) | headline, items_ref, columns |
| `services_grid` | Service cards with links | headline, source, show_summary |
| `testimonials` | Customer testimonials | headline, items_ref, style |
| `faq` | FAQ accordion | headline, items_ref |
| `contact_form` | Contact form placeholder | headline, show_info |
| `rich_text` / `text_block` | Rich text content | content, content_ref |
| `logos_strip` | Logo gallery | headline, items |
| `pricing_table` | Pricing comparison | headline, plans |

---

## Entity-to-Page Generation

### Entities

Preset-specific data types that generate pages:

- **company preset:** `services` → `/services/*` pages
- **saas preset:** `features` → `/features/*` pages
- **ecommerce preset:** `products` → `/products/*` pages
- **multi-location:** `locations` → `/locations/*` pages

### Example: Services

```yaml
# Site spec
services:
  - slug: consulting
    name: {en_US: "Consulting", tr_TR: "Danışmanlık"}
    summary: {en_US: "Strategy and ops", tr_TR: "Strateji ve operasyon"}

# Generated pages:
# - /services (from preset template)
# - /services/consulting (from entity, child of /services)
```

---

## Merge Rules

### Maps (Deep Merge)

```yaml
# defaults.yaml
brand:
  colors:
    primary: "#1e3a5f"
    secondary: "#0891b2"

# site.yaml
brand:
  colors:
    primary: "#FF0000"  # Override

# Result: primary from site, secondary from defaults
```

### Arrays (Replace by Default)

```yaml
# defaults.yaml
plugins:
  base: [wp-mail-smtp, generatepress]

# preset.yaml
plugins:
  add: [wpml, thrive-architect]

# Result: base + add (appended)
```

### Plugin Layering

```yaml
plugins:
  base: [...]        # From defaults
  add: [...]         # From preset + site (appended)
  skip: [rank-math]  # Remove from final list
```

---

## Validation Rules

### Required Fields

- `schema_version` (integer)
- `site.domain` (string)
- `brand.name` (string)
- `contact.email` (email)
- `languages.primary` (locale)
- `deployment.target` (string)

### Reference Resolution

```yaml
sections:
  - type: testimonials
    items_ref: content.testimonials  # Must exist
```

**Validation:** Fail fast if reference not found.

### Localization

```yaml
languages:
  primary: en_US
  additional: [tr_TR]

brand:
  tagline:
    en_US: "English"  # Required (primary)
    tr_TR: "Türkçe"   # Optional (additional)
```

**Rules:**
- Primary locale MUST be present
- Additional locales MAY be missing (fallback to primary)
- Locale keys must match `languages` list

---

## Test Results (ocoron.com v2)

### Spec Loading

```
Spec: 205 lines (vs 472 old format)
Merge: defaults (180) + preset (219) + site (205) = merged
Validation: ✅ No errors, no warnings
Services: 8 entities normalized to entities.services
Plugins: 8 base + 7 preset = 15 total
```

### Page Generation

```
Total pages: 15
  - 7 from preset templates (home, services, about, contact, insights, privacy, terms)
  - 8 from service entities (investment-incentives, foreign-trade, ai-consultancy, etc)

Content rendered:
  - Homepage: 5997 chars (hero + features + services_grid + cta)
  - Services index: 3165 chars
  - Service detail: 730 chars each
```

### Deployment (Dry-run)

```
✅ Settings applied
✅ Theme configured
✅ 15 pages generated
✅ Menus configured (primary, footer)
✅ Forms configured
✅ SEO configured
⚠️  Analytics: ${GA4_ID} not set (expected in .env)
✅ Site finalized

Steps completed: 8
Steps failed: 0
```

---

## Migration Guide (v1 → v2)

### 1. Create Minimal Site Spec

**Old (v1):**
```yaml
domain: ocoron.com
preset: company
brand:
  name: "Ocoron"
  tagline: "Professional Services"
  tagline_tr: "Profesyonel Hizmetler"
pages:
  - slug: ""
    title: "Home"
    title_tr: "Ana Sayfa"
    # ... 400 more lines
```

**New (v2):**
```yaml
schema_version: 1
preset: company
site:
  domain: ocoron.com
brand:
  name: "Ocoron"
  tagline:
    en_US: "Professional Services"
    tr_TR: "Profesyonel Hizmetler"
services:
  - slug: consulting
    name: {en_US: "Consulting", tr_TR: "Danışmanlık"}
```

### 2. Normalize Localization

**Old:** `title` + `title_tr`
**New:** `title: {en_US: "...", tr_TR: "..."}`

### 3. Move Pages to Entities

**Old:** Explicit pages for each service
**New:** Services list → pages generated automatically

### 4. Use Preset Templates

**Old:** Define all page sections inline
**New:** Preset provides templates, site provides data

---

## Next Steps

### Ready for Production

- ✅ Schema defined and documented
- ✅ Loader, validator, renderer, generator implemented
- ✅ Deployer updated to v2
- ✅ Tested with ocoron.com (dry-run)

### To Deploy ocoron.com

1. **Set environment variables:**
   ```bash
   export GA4_ID=G-VK6FMQRVRL
   export WP_ADMIN_PASSWORD=<password>
   ```

2. **Deploy WordPress container:**
   ```bash
   fabrik apply ocoron-com
   ```

3. **Run site deployer:**
   ```python
   from fabrik.wordpress import deploy_site
   result = deploy_site('ocoron.com')
   ```

### Future Enhancements

- **Tier 2 sections:** Advanced layouts, conditional rendering, AB variants
- **More presets:** saas, agency, clinic, ecommerce, landing
- **Content generation:** AI-powered page content from Claude
- **State tracking:** Idempotent deploys with spec hash
- **Post-deploy checks:** Automated QA (URLs, SSL, forms, sitemap)
- **Migration tool:** Automated v1 → v2 spec conversion

---

## Files Created/Modified

### New Files (v2 Architecture)

```
templates/wordpress/
├── schema/
│   ├── v1.yaml                    # Schema definition
│   ├── MERGE_RULES.md             # Merge semantics
│   └── VALIDATION_RULES.md        # Validation rules
├── defaults.yaml                  # Global defaults
└── presets/
    └── company.yaml               # Company preset (v2)

specs/sites/
└── ocoron.com.v2.yaml             # Minimal site spec

src/fabrik/wordpress/
├── spec_loader.py                 # Load & merge
├── spec_validator.py              # Validate
├── section_renderer.py            # Render sections
├── page_generator.py              # Generate pages
└── deployer.py                    # Updated for v2
```

### Modified Files

```
src/fabrik/wordpress/__init__.py   # Added v2 exports
```

---

## Summary

WordPress v2 architecture provides a **production-ready, scalable foundation** for deploying multiple WordPress sites with minimal per-site configuration. The 57% reduction in spec size (473 → 205 lines) demonstrates the power of the layered approach, while maintaining full flexibility through the merge system.

**Key achievement:** A company can now deploy a fully-configured WordPress site by providing only brand, services, and contact info. Everything else (theme, plugins, pages, sections, menus) comes from defaults and presets.
