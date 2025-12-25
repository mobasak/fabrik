# Future Development Roadmap

**Last Updated:** 2025-12-25

---

## Web-Based Site Spec Builder (Option C)

### Overview

A web interface for creating WordPress site specifications without manually editing YAML files.

### Features

#### 1. Interactive Form Builder
- Multi-step wizard for site configuration
- Real-time validation and preview
- Auto-complete for common values
- Template selection (company, saas, ecommerce, etc.)

#### 2. Visual Brand Designer
- Color picker with palette suggestions
- Font pairing recommendations
- Logo upload and preview
- Live brand preview

#### 3. Service/Entity Manager
- Add/edit/remove services visually
- Drag-and-drop ordering
- Multilingual content editor
- Bulk import from CSV/spreadsheet

#### 4. Page Structure Builder
- Visual page tree editor
- Section drag-and-drop composer
- Template selection per page
- Content preview in WordPress style

#### 5. SEO & Analytics Setup
- Guided SEO configuration
- Analytics ID validation
- Meta preview (Google/social)
- Schema.org markup builder

#### 6. Spec Export & Deployment
- Generate YAML automatically
- Validate before save
- One-click deployment
- Deployment status tracking

### Technical Architecture

```
Frontend:
  - Next.js 14 (React)
  - TailwindCSS + shadcn/ui
  - Monaco Editor (YAML editing)
  - React Hook Form + Zod validation

Backend:
  - FastAPI (Python)
  - Endpoints:
    - POST /api/specs/validate
    - POST /api/specs/generate
    - POST /api/deploy/{domain}
    - GET /api/deploy/{domain}/status

Integration:
  - Reads: templates/wordpress/schema/v1.yaml
  - Writes: specs/sites/{domain}.v2.yaml
  - Calls: fabrik.wordpress.SpecValidator
  - Calls: fabrik.wordpress.SiteDeployer
```

### User Flow

```
1. Select Template
   ↓
2. Brand Identity (name, colors, logo)
   ↓
3. Services/Entities (add items)
   ↓
4. Contact Info (email, social, address)
   ↓
5. SEO Settings (title, description, analytics)
   ↓
6. Review & Preview (see generated pages)
   ↓
7. Deploy (one-click)
   ↓
8. Monitor (deployment progress)
```

### Benefits

- **No YAML knowledge required**
- **Visual feedback** (see what you're building)
- **Validation in real-time** (catch errors early)
- **Faster onboarding** (non-technical users)
- **Template library** (start from examples)
- **Deployment tracking** (see progress live)

### Implementation Priority

**Phase:** Post-MVP (after Step 0-18 automation complete)

**Estimated Effort:** 2-3 weeks
- Week 1: Form builder + validation
- Week 2: Visual editors + preview
- Week 3: Deployment integration + polish

### Alternative: CLI Wizard

Before building full web UI, consider interactive CLI:

```bash
fabrik init newsite.com

# Interactive prompts:
? Company name: Acme Corp
? Tagline (en_US): Innovation at Scale
? Primary color: #3498DB
? How many services? 3
? Service 1 name (en_US): Consulting
? Service 1 slug: consulting
...
✓ Created specs/sites/newsite.com.v2.yaml
✓ Validated (0 errors, 0 warnings)
? Deploy now? (y/N)
```

**Effort:** 2-3 days (much faster, good interim solution)

---

## Other Future Enhancements

### Content Generation
- AI-powered service descriptions
- Auto-generate page content from keywords
- SEO-optimized meta descriptions
- Multilingual content translation

### Advanced Customization
- Custom section types
- Custom page templates
- CSS/JS injection
- Advanced theme customization

### Multi-Site Management
- Dashboard for all sites
- Bulk updates (plugins, themes)
- Cross-site analytics
- Centralized backup management

### Marketplace
- Pre-built site templates
- Section library
- Plugin bundles
- Theme variations
