# WordPress Module Integration Architecture

**Last Updated:** 2026-03-16
**Purpose:** Integration architecture for SEO+GEO, Content Creation, and WordPress Deployment modules

---

## Table of Contents

1. [Overview](#overview)
2. [Module Responsibilities](#module-responsibilities)
3. [Orchestration Flow](#orchestration-flow)
4. [Current Fabrik WordPress Architecture](#current-fabrik-wordpress-architecture)
5. [Integration Points](#integration-points)
6. [API Contracts](#api-contracts)
7. [Data Flow](#data-flow)
8. [Implementation Roadmap](#implementation-roadmap)

---

## Overview

### Core Principle

**The Website Deployment module orchestrates. The Content Creation module generates. The SEO+GEO module plans.**

This is the cleanest and leanest system architecture.

### Orchestration Chain

```text
SEO+GEO module
  ↓ (provides briefs)
Content Creation module
  ↓ (provides page packages)
Website Creation / Deployment module
  ↓ (publishes)
WordPress / hosting / domain / CDN
```

**Critical Rule:** The deployment module calls the content creation module, not vice versa.

---

## Module Responsibilities

### 1. SEO+GEO Module (Planner)

**Status:** In development
**Location:** TBD (separate microservice or `/opt/seo-geo`)

**Owns:**
- Keyword planning and research
- Page planning and strategy
- Full SEO page records
- GEO requirements (location-based content)
- Brief queue management
- Cannibalization detection
- Content cluster organization

**Exposes:**
- `GET /briefs?status=ready` - List ready briefs
- `POST /briefs/{brief_id}/claim` - Claim brief for generation
- `POST /briefs/{brief_id}/release` - Release claimed brief
- `POST /briefs/{brief_id}/submit` - Submit generation result

**Does NOT:**
- Generate content
- Interact with WordPress directly
- Publish pages

---

### 2. Content Creation Module (Generator)

**Status:** In development
**Location:** TBD (separate microservice or `/opt/content-creation`)

**Owns:**
- Claiming briefs from SEO+GEO
- Generating page packages
- Producing visible content
- Generating metadata (SEO title, meta description, OG tags)
- Generating schema JSON-LD
- Assembling WordPress-ready payloads
- Submitting result metadata back to SEO+GEO
- Returning page package artifact to caller

**Exposes:**
- `POST /generate-from-brief` - Generate page package from brief
- `POST /validate-page-package` - Validate page package structure

**Does NOT:**
- Claim briefs automatically (deployment module provides briefs)
- Interact with WordPress directly
- Publish pages
- Make deployment decisions

**Design:** Stateless generator - receives brief, returns page package

---

### 3. Website Creation / Deployment Module (Orchestrator)

**Status:** ✅ Exists in Fabrik
**Location:** `/opt/fabrik/src/fabrik/wordpress/`

**Owns:**
- Site bootstrap and provisioning
- WordPress installation and setup
- Theme/template configuration
- Custom fields and SEO plugin mapping
- Media placement
- Page/post creation in WordPress
- Menu/navigation creation
- Breadcrumb hierarchy setup
- Publish/update workflow
- Environment deployment
- **Orchestrating brief → content → publish flow**

**Current Components:**
- `deployer.py` - Main orchestrator (SiteDeployer class)
- `planner.py` - Build directory and plan generation
- `page_generator.py` - Page spec generation
- `content.py` - AI content generation (Claude)
- `pages.py` - WordPress page creation
- Stages: dns, settings, theme, plugins, languages, pages, menus, forms, seo, analytics

**New Responsibilities (for integration):**
- Fetch ready briefs from SEO+GEO
- Send briefs to Content Creation module
- Receive page packages
- Map page packages to WordPress fields
- Submit publish results to SEO+GEO

**Exposes:**
- `fabrik wp plan <site_id>` - Generate deployment plan
- `fabrik wp apply <site_id>` - Execute deployment
- `fabrik wp verify <domain>` - Verify deployment

**Future CLI commands:**
- `fabrik wp provision <site_id>` - Create WordPress container
- `fabrik wp publish-briefs <site_id> [--filter]` - Publish from briefs
- `fabrik wp generate-drafts <site_id> [--filter]` - Generate drafts only

---

## Orchestration Flow

### High-Level Site Deployment Flow

```text
1. User: fabrik wp apply ocoron.com
2. Deployment Module:
   ├─ Provision site (if needed)
   ├─ Configure WordPress
   ├─ Configure SEO plugin defaults
   ├─ Import site structure
   ├─ Fetch ready briefs from SEO+GEO
   └─ For each brief:
      ├─ Send brief to Content Creation module
      ├─ Receive full page package
      ├─ Create/update WP page/post
      ├─ Assign metadata, schema fields, images, FAQs, CTAs
      ├─ Publish or save draft
      └─ Submit result to SEO+GEO
3. Deployment Module:
   ├─ Update menus, internal linking hubs
   ├─ Update taxonomy pages
   └─ Finalize deployment
```

### Detailed Brief-to-Publish Flow

```text
┌─────────────────┐
│   SEO+GEO       │
│   - Has briefs  │
│   - status=ready│
└────────┬────────┘
         │
         │ GET /briefs?status=ready
         ↓
┌─────────────────────────────────┐
│   Deployment Module             │
│   1. Fetch ready briefs         │
│   2. Select brief (ordering)    │
└────────┬────────────────────────┘
         │
         │ POST /briefs/{id}/claim
         ↓
┌─────────────────┐
│   SEO+GEO       │
│   - Mark claimed│
│   - Return brief│
└────────┬────────┘
         │
         │ brief object
         ↓
┌─────────────────────────────────┐
│   Deployment Module             │
│   3. Have full brief            │
└────────┬────────────────────────┘
         │
         │ POST /generate-from-brief
         │ Body: { "brief": {...}, "mode": "publish-ready" }
         ↓
┌─────────────────────────────────┐
│   Content Creation Module       │
│   1. Receive brief              │
│   2. Generate content           │
│   3. Generate metadata          │
│   4. Generate schema JSON-LD    │
│   5. Assemble page package      │
└────────┬────────────────────────┘
         │
         │ page_package object
         ↓
┌─────────────────────────────────┐
│   Deployment Module             │
│   4. Receive page package       │
│   5. Map to WordPress fields    │
│   6. Create WP page/post        │
│   7. Assign featured image      │
│   8. Set SEO plugin fields      │
│   9. Inject schema JSON-LD      │
│  10. Publish or draft           │
└────────┬────────────────────────┘
         │
         │ WP page created
         │ - post_id: 123
         │ - url: https://ocoron.com/ai-voice-agent/
         ↓
┌─────────────────────────────────┐
│   Deployment Module             │
│  11. Collect publish result     │
└────────┬────────────────────────┘
         │
         │ POST /briefs/{id}/submit
         │ Body: { "url": "...", "post_id": 123, "status": "published" }
         ↓
┌─────────────────┐
│   SEO+GEO       │
│   - Update brief│
│   - Track result│
└─────────────────┘
```

---

## Current Fabrik WordPress Architecture

### Directory Structure

```
/opt/fabrik/src/fabrik/wordpress/
├── deployer.py              # Main orchestrator (SiteDeployer)
├── planner.py               # Build directory, plan.json generation
├── spec_loader.py           # Load and merge specs
├── spec_validator.py        # Validate spec structure
├── page_generator.py        # Generate page specs
├── content.py               # AI content generation (Claude)
├── pages.py                 # WordPress page creation
├── section_renderer.py      # Render page sections
├── stages/                  # Deployment stages
│   ├── dns.py
│   ├── settings.py
│   ├── theme.py
│   ├── plugins.py
│   ├── languages.py
│   ├── pages.py
│   ├── menus.py
│   ├── forms.py
│   ├── seo.py
│   └── analytics.py
└── manifests/               # Manifest generators (build artifacts → build/sites/<site_id>/manifests/)
```

### Current Deployment Stages

| Stage | Responsibility | Integration Point |
|-------|----------------|-------------------|
| **dns** | DNS record verification | None |
| **settings** | WP core settings, users | None |
| **theme** | Theme installation | None |
| **plugins** | Plugin installation | SEO plugin setup |
| **languages** | WPML setup | None |
| **pages** | Page creation | **Content integration** |
| **menus** | Menu creation | Uses page URLs |
| **forms** | Contact forms | None |
| **seo** | SEO plugin config | **Schema integration** |
| **analytics** | Analytics tracking | None |

### Key Classes

**`SiteDeployer`** (`deployer.py`)
- Main orchestrator
- Loads spec, validates, executes stages
- Current content flow: spec → page_generator → content.py → pages.py → WordPress

**`PageGenerator`** (`page_generator.py`)
- Generates page specs from:
  - Explicit pages in spec
  - Preset page templates
  - Entity data (services, features, products)
- Current: tightly coupled to spec structure

**`ContentGenerator`** (`content.py`)
- AI content generation using Claude
- Current: Available but not used by pages stage (pages use spec-based content)
- **Future:** Will be replaced/augmented by Content Creation module

**`PageCreator`** (`pages.py`)
- Creates WordPress pages via REST API (WordPressAPIClient)
- Current: receives title, slug, content as individual arguments
- **Future:** Will receive page packages from Content Creation module

---

## Integration Points

### 1. SEO+GEO Integration Points

**Where:** `deployer.py` - new method `_fetch_briefs_from_seo_geo()`

**Implementation:**
```python
def _fetch_briefs_from_seo_geo(self, filters: dict = None) -> list[dict]:
    """
    Fetch ready briefs from SEO+GEO module.

    Args:
        filters: Optional filters (status, page_type, cluster, etc.)

    Returns:
        List of brief objects
    """
    seo_geo_url = os.getenv("SEO_GEO_API_URL")
    # GET /briefs?status=ready&...
    # Return list of briefs
```

**Configuration:**
```bash
# .env
SEO_GEO_API_URL=http://seo-geo:8010
SEO_GEO_API_KEY=<token>
```

---

### 2. Content Creation Integration Points

**Where:** `deployer.py` - new method `_generate_page_package()`

**Implementation:**
```python
def _generate_page_package(self, brief: dict, mode: str = "publish-ready") -> dict:
    """
    Generate page package from brief using Content Creation module.

    Args:
        brief: Full brief object from SEO+GEO
        mode: "draft" or "publish-ready"

    Returns:
        Page package with content, metadata, schema
    """
    content_api_url = os.getenv("CONTENT_CREATION_API_URL")
    # POST /generate-from-brief
    # Body: { "brief": brief, "mode": mode }
    # Return page_package
```

**Configuration:**
```bash
# .env
CONTENT_CREATION_API_URL=http://content-creation:8011
CONTENT_CREATION_API_KEY=<token>
```

---

### 3. WordPress Page Creation Integration Point

**Where:** `pages.py` - modify `PageCreator` class

**Current:**
```python
class PageCreator:
    def create_page(
        self,
        title: str,
        slug: str = "",
        content: str = "",
        status: str = "publish",
        template: str = "",
        parent_id: int | None = None,
    ) -> CreatedPage:
        # Creates: WP page via REST API (WordPressAPIClient)
```

**Future:**
```python
class PageCreator:
    def create_from_package(self, page_package: dict) -> CreatedPage:
        # Receives: full page package from Content Creation
        # Maps: page_payload → WP fields
        # Maps: rendered_sections → WP blocks/HTML
        # Maps: json_ld → schema fields
        # Creates: WP page via WP-CLI + REST API
```

---

### 4. Result Submission Integration Point

**Where:** `deployer.py` - new method `_submit_result_to_seo_geo()`

**Implementation:**
```python
def _submit_result_to_seo_geo(self, brief_id: str, result: dict) -> None:
    """
    Submit publish result back to SEO+GEO.

    Args:
        brief_id: Brief UUID
        result: {
            "url": "https://ocoron.com/ai-voice-agent/",
            "post_id": 123,
            "status": "published" | "draft",
            "published_at": "2026-03-16T12:00:00Z"
        }
    """
    seo_geo_url = os.getenv("SEO_GEO_API_URL")
    # POST /briefs/{brief_id}/submit
    # Body: result
```

---

## API Contracts

### SEO+GEO Module API

**Base URL:** `http://seo-geo:8010/api/v1`

#### 1. List Ready Briefs

```http
GET /briefs?status=ready&page_type=service&limit=50
Authorization: Bearer {SEO_GEO_API_KEY}
```

**Response:**
```json
{
  "briefs": [
    {
      "brief_id": "uuid",
      "page_type": "service",
      "primary_keyword": "ai voice agent for clinics",
      "cluster": "ai-automation",
      "status": "ready",
      "priority": 1,
      "created_at": "2026-03-15T10:00:00Z"
    }
  ],
  "total": 50,
  "filters_applied": {
    "status": "ready",
    "page_type": "service"
  }
}
```

#### 2. Claim Brief

```http
POST /briefs/{brief_id}/claim
Authorization: Bearer {SEO_GEO_API_KEY}
Content-Type: application/json

{
  "worker_id": "fabrik-deployer-ocoron-com",
  "expires_in": 1800
}
```

**Response:**
```json
{
  "brief_id": "uuid",
  "claimed_at": "2026-03-16T12:00:00Z",
  "expires_at": "2026-03-16T12:30:00Z",
  "brief": {
    "page_type": "service",
    "url_slug": "ai-voice-agent",
    "primary_keyword": "ai voice agent for clinics",
    "secondary_keywords": ["clinic call automation", "healthcare voice ai"],
    "search_intent": "commercial",
    "target_audience": "clinic administrators",
    "pain_points": ["high call volume", "missed calls"],
    "solutions": ["24/7 availability", "call routing"],
    "content_requirements": {
      "min_word_count": 1200,
      "include_faq": true,
      "include_cta": true,
      "tone": "professional",
      "expertise_level": "intermediate"
    },
    "seo_requirements": {
      "title_template": "{primary_keyword} | {brand}",
      "meta_description_length": [140, 160],
      "internal_links_min": 3,
      "schema_types": ["WebPage", "FAQPage"]
    },
    "geo_requirements": {
      "target_location": "US",
      "include_local_examples": false
    }
  }
}
```

#### 3. Release Brief

```http
POST /briefs/{brief_id}/release
Authorization: Bearer {SEO_GEO_API_KEY}
Content-Type: application/json

{
  "reason": "generation_failed" | "timeout" | "manual_release"
}
```

#### 4. Submit Result

```http
POST /briefs/{brief_id}/submit
Authorization: Bearer {SEO_GEO_API_KEY}
Content-Type: application/json

{
  "url": "https://ocoron.com/ai-voice-agent/",
  "post_id": 123,
  "status": "published",
  "published_at": "2026-03-16T12:30:00Z",
  "metadata": {
    "word_count": 1450,
    "internal_links_count": 5,
    "has_faq": true,
    "has_schema": true,
    "images_count": 3
  }
}
```

---

### Content Creation Module API

**Base URL:** `http://content-creation:8011/api/v1`

#### 1. Generate from Brief

```http
POST /generate-from-brief
Authorization: Bearer {CONTENT_CREATION_API_KEY}
Content-Type: application/json

{
  "brief": { /* full brief object from SEO+GEO */ },
  "mode": "publish-ready",
  "options": {
    "include_images": true,
    "include_schema": true,
    "brand_context": {
      "name": "Ocoron",
      "tagline": "AI solutions for healthcare",
      "voice": "professional, empathetic"
    }
  }
}
```

**Response:**
```json
{
  "brief_id": "uuid",
  "page_package": {
    "page_payload": {
      "page_type": "service",
      "url": "https://example.com/ai-voice-agent/",
      "slug": "ai-voice-agent",
      "seo_title": "AI Voice Agent for Clinics | Ocoron",
      "meta_description": "AI voice agents for clinics that handle calls, qualify leads, and reduce front-desk workload.",
      "canonical_url": "https://example.com/ai-voice-agent/",
      "robots": "index,follow",
      "advanced_robots": {
        "max_snippet": -1,
        "max_image_preview": "large",
        "max_video_preview": -1
      },
      "primary_keyword": "ai voice agent for clinics",
      "secondary_keywords": ["clinic call automation", "healthcare voice ai"],
      "search_intent": "commercial",
      "h1": "AI Voice Agent for Clinics",
      "breadcrumb_title": "AI Voice Agent",
      "og": {
        "title": "AI Voice Agent for Clinics | Ocoron",
        "description": "Automate inbound clinic calls with an AI voice agent.",
        "url": "https://example.com/ai-voice-agent/",
        "image": "https://example.com/uploads/ai-voice-agent-og.jpg",
        "type": "website"
      },
      "twitter": {
        "card": "summary_large_image",
        "title": "AI Voice Agent for Clinics | Ocoron",
        "description": "Automate inbound clinic calls with an AI voice agent.",
        "image": "https://example.com/uploads/ai-voice-agent-og.jpg"
      },
      "schema": {
        "primary_type": "WebPage",
        "secondary_types": ["BreadcrumbList", "FAQPage"]
      },
      "author": {
        "name": "Ocoron",
        "url": "https://example.com/about/"
      },
      "dates": {
        "published": "2026-03-16",
        "modified": "2026-03-16"
      },
      "images": {
        "featured_image": "https://example.com/uploads/ai-voice-agent-featured.jpg",
        "alt_text": "AI voice agent dashboard for clinic call handling"
      },
      "internal_links": [
        "https://example.com/ai-automation/",
        "https://example.com/clinic-chatbot/"
      ],
      "faq_items": [
        {
          "question": "What can the AI voice agent do?",
          "answer": "Our AI voice agent can answer common questions, schedule appointments, qualify leads, and route urgent calls to the right staff."
        }
      ],
      "conversion": {
        "primary_cta": "Book a Demo",
        "secondary_cta": "Get Pricing"
      }
    },
    "rendered_sections": [
      {
        "type": "hero",
        "content": {
          "heading": "AI Voice Agent for Clinics",
          "subheading": "Automate phone calls, reduce workload, never miss a patient.",
          "cta_text": "Book a Demo",
          "cta_url": "/contact/"
        }
      },
      {
        "type": "ai_summary",
        "content": {
          "text": "An AI voice agent automates inbound calls for clinics..."
        }
      },
      {
        "type": "body_section",
        "content": {
          "html": "<h2>How It Works</h2><p>...</p>"
        }
      },
      {
        "type": "faq",
        "content": {
          "items": [ /* faq_items from page_payload */ ]
        }
      },
      {
        "type": "cta",
        "content": {
          "text": "Ready to automate your clinic calls?",
          "button_text": "Book a Demo",
          "button_url": "/contact/"
        }
      }
    ],
    "json_ld": [
      {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "AI Voice Agent for Clinics",
        "description": "...",
        "url": "https://example.com/ai-voice-agent/"
      },
      {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [ /* FAQ schema */ ]
      }
    ],
    "validation": {
      "is_valid": true,
      "errors": [],
      "warnings": []
    }
  },
  "generation_metadata": {
    "model": "claude-sonnet-4-20250514",
    "tokens_used": 3500,
    "generation_time_ms": 4200,
    "word_count": 1450
  }
}
```

#### 2. Validate Page Package

```http
POST /validate-page-package
Content-Type: application/json

{
  "page_package": { /* page package object */ }
}
```

**Response:**
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": [
    "internal_links_count is below recommended minimum (3 found, 5 recommended)"
  ]
}
```

---

## Data Flow

### Current Flow (Spec-Based)

```text
YAML Spec
  ↓
spec_loader.py (load + merge presets)
  ↓
spec_validator.py (validate structure)
  ↓
page_generator.py (generate page specs with content from spec)
  ↓
pages.py (create WP pages via REST API)
  ↓
WordPress
```

**Note:** content.py (AI generation via Claude) exists but is not currently used by the pages stage. Pages are created from spec-defined content.

**Limitation:** Content from static spec, no SEO planning, no GEO requirements, no AI generation

---

### Future Flow (Brief-Based)

```text
SEO+GEO Module
  ↓ (briefs with keywords, clusters, requirements)
Deployment Module (orchestrator)
  ↓ (fetch briefs, select ordering)
Content Creation Module
  ↓ (generate page packages)
Deployment Module (map to WP fields)
  ↓ (create pages, assign metadata, inject schema)
WordPress
  ↓ (publish)
Deployment Module
  ↓ (submit results)
SEO+GEO Module (track performance)
```

**Benefits:**
- SEO-driven content planning
- GEO requirements included
- Cluster-based organization
- Cannibalization prevention
- Performance tracking
- Reusable content packages

---

## Implementation Roadmap

### Phase 1: Preparation (Current)

**Status:** ✅ In progress

- [x] Document current architecture
- [x] Define integration points
- [x] Define API contracts
- [x] Create architectural overview

---

### Phase 2: SEO+GEO Module Development

**Status:** 🚧 In development (user-owned)

**Deliverables:**
- SEO+GEO API service
- Brief queue management
- Keyword research integration
- Cluster organization
- Cannibalization detection

---

### Phase 3: Content Creation Module Development

**Status:** 🚧 In development (user-owned)

**Deliverables:**
- Content Creation API service
- Page package generation
- Schema JSON-LD generation
- Multi-section rendering
- Image placeholder generation

---

### Phase 4: Deployment Module Integration

**Status:** ⏳ Pending Phases 2 & 3

**Tasks:**
1. Add SEO+GEO client to `deployer.py`
   - `_fetch_briefs_from_seo_geo()`
   - `_claim_brief()`
   - `_release_brief()`
   - `_submit_result()`

2. Add Content Creation client to `deployer.py`
   - `_generate_page_package()`
   - `_validate_page_package()`

3. Modify `pages.py` PageCreator
   - Add `create_from_package()` method
   - Map page_package → WP fields
   - Map rendered_sections → WP blocks
   - Map json_ld → schema fields

4. Update deployment stages
   - Modify `stages/pages.py` to use brief-based flow
   - Modify `stages/seo.py` to inject JSON-LD from packages

5. Add new CLI commands
   - `fabrik wp publish-briefs <site_id> [--filter]`
   - `fabrik wp generate-drafts <site_id> [--filter]`
   - `fabrik wp list-briefs <site_id>`

6. Add environment variables
   - `SEO_GEO_API_URL`
   - `SEO_GEO_API_KEY`
   - `CONTENT_CREATION_API_URL`
   - `CONTENT_CREATION_API_KEY`

---

### Phase 5: Testing & Validation

**Status:** ⏳ Pending Phase 4

**Tasks:**
- Integration tests for SEO+GEO client
- Integration tests for Content Creation client
- End-to-end deployment tests
- Performance testing (brief → publish latency)
- Rollback/retry testing

---

### Phase 6: Documentation & Training

**Status:** ⏳ Pending Phase 5

**Tasks:**
- Update AGENTS.md with new workflow
- Update README.md with brief-based deployment
- Create deployment cookbook
- Document error handling patterns
- Create troubleshooting guide

---

## Deployment Module User Commands

### Current Commands

```bash
# Generate deployment plan
fabrik wp plan ocoron.com

# Deploy site from spec
fabrik wp apply ocoron.com

# Verify deployment
fabrik wp verify ocoron.com
```

---

### Future Commands (Post-Integration)

```bash
# List available briefs for site
fabrik wp list-briefs ocoron.com --status ready

# Generate drafts from briefs (no publish)
fabrik wp generate-drafts ocoron.com --page-type service --limit 10

# Publish specific briefs
fabrik wp publish-briefs ocoron.com --brief-ids uuid1,uuid2,uuid3

# Publish briefs by filter
fabrik wp publish-briefs ocoron.com --cluster ai-automation --limit 20

# Publish only service pages
fabrik wp publish-briefs ocoron.com --page-type service

# Publish only pages that pass cannibalization check
fabrik wp publish-briefs ocoron.com --cannibalization-status pass

# Regenerate specific page from brief
fabrik wp regenerate-page ocoron.com --brief-id uuid --force

# Full site deployment (brief-based + spec-based hybrid)
fabrik wp apply ocoron.com --use-briefs
```

---

## Summary

### Current State

Fabrik has a robust WordPress deployment system that:
- Orchestrates complete site deployments
- Generates pages from YAML specs
- Supports AI content generation via Claude
- Handles themes, plugins, menus, forms, SEO, analytics

### Integration Strategy

The deployment module will be **extended** (not replaced) to:
1. Fetch briefs from SEO+GEO module
2. Send briefs to Content Creation module
3. Receive page packages
4. Map packages to WordPress fields
5. Submit results back to SEO+GEO

### Design Principles

1. **Deployment module is the orchestrator** - it controls flow, ordering, batching
2. **Content module is stateless** - receives brief, returns package
3. **SEO+GEO module is the planner** - provides strategic briefs
4. **Clean boundaries** - each module has clear responsibilities
5. **Backward compatibility** - spec-based deployment still works

### Next Steps

1. Wait for SEO+GEO and Content Creation modules to be developed
2. Implement integration points in deployment module
3. Add new CLI commands for brief-based publishing
4. Test end-to-end flow
5. Document new workflow

---

**End of Document**
