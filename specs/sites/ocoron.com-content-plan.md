# Ocoron.com Content Plan

> **Status:** Planning
> **Approach:** Option B - AI-generated content, user reviews

---

## Stock Images Strategy

### Attribution Requirements (CRITICAL)

| Source | Attribution Required | Format |
|--------|---------------------|--------|
| **Unsplash** | YES | Photographer name + link with UTM params |
| **Pexels** | YES (Terms) | Follow Pexels Terms of Service |
| **Pixabay** | YES (search UI) | "Powered by Pixabay" when showing search results |

> **Key insight:** Attribution compliance must be a first-class requirement, not optional.

### Architecture: Image Broker Microservice (Future)

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   WordPress     │────▶│   Image Broker   │────▶│  Stock APIs     │
│   (WP Plugin)   │◀────│   (Container)    │◀────│  Unsplash/Pexels│
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Local Cache     │
                        │  + Attribution   │
                        │  Metadata        │
                        └──────────────────┘
```

**Image Broker Responsibilities:**
- Normalize providers (Unsplash/Pexels/Pixabay) into one response schema
- Enforce attribution rules in schema (frontend can't "forget")
- Cache responses + downloaded assets
- Rate limit per WP site
- Allowlist keywords/categories

**Normalized Response Schema:**
```json
{
  "asset_url": "https://cache.fabrik.io/images/abc123.jpg",
  "source": "unsplash",
  "attribution_text": "Photo by John Doe on Unsplash",
  "attribution_links": [
    "https://unsplash.com/@johndoe?utm_source=ocoron&utm_medium=referral"
  ],
  "photographer": "John Doe",
  "license_notes": "Unsplash License - free for commercial use"
}
```

### Tier Strategy

| Tier | Source | Cost | Use Case |
|------|--------|------|----------|
| **Primary** | Curated library (cached) | Free | Default for all sites |
| **Secondary** | Stock APIs (Unsplash/Pexels/Pixabay) | Free | New/custom requests |
| **Tertiary** | AI generation (OpenAI gpt-image-1) | Paid | Brand-specific, unique scenes |

### Implementation Phases

**Phase 1: Manual Curation (NOW - ocoron.com)**
- Download ~10-30 images per service category
- Store with attribution metadata in JSON
- Use directly in WordPress

**Phase 2: Image Broker Container (FUTURE)**
- Build microservice alongside WordPress containers
- WP plugin calls broker, writes to Media Library
- Attribution stored in attachment meta

**Phase 3: AI Fallback (FUTURE - paid tier)**
- OpenAI gpt-image-1 API integration
- Only for "custom branded visuals" tier
- Not part of default free imagery stack

### Image Folder Structure

```
ocoron.com-media/
├── heroes/                    # Full-width hero images (1920x1080)
├── services/
│   ├── incentives/           # Government, Turkish flag, business meetings
│   ├── trade/                # Shipping, customs, global maps, ports
│   ├── ai/                   # Tech, data visualization, automation
│   ├── manufacturing/        # Factories, machinery, workers, R&D labs
│   ├── logistics/            # Warehouses, trucks, supply chain
│   ├── b2b/                  # Marketing, digital, analytics dashboards
│   ├── medical/              # Medical devices, hospitals, procurement
│   └── quality/              # Certifications, audits, ISO badges
├── about/                    # Team, office, Turkey landmarks
├── icons/                    # Service icons (SVG, consistent style)
└── logos/                    # Client logos (if available)
```

### Image Search Keywords

| Service | Keywords |
|---------|----------|
| Investment Incentives | government support, KOSGEB, Turkish ministry, business funding, grant application |
| Foreign Trade | export, import, customs, shipping container, global trade, port |
| AI Consultancy | artificial intelligence, machine learning, data analytics, digital transformation |
| Manufacturing | factory, production line, machinery, R&D, industrial |
| Logistics | warehouse, supply chain, trucks, inventory, distribution |
| B2B Marketing | digital marketing, email campaign, SEO, analytics dashboard |
| Medical Procurement | medical devices, hospital equipment, healthcare procurement |
| Quality Management | ISO certification, audit, quality control, compliance |

---

## Page Content Plan

### 1. Home Page (/)

**Sections:**
1. **Hero** - Full-width with tagline
   - Headline: "Strategic Consulting for Growing Businesses"
   - Subheadline: "Government incentives, international expansion, digital transformation"
   - CTA: "Explore Services" / "Contact Us"

2. **Features** (4 cards)
   - Government Incentives
   - Global Trade
   - AI & Digital
   - Manufacturing

3. **Services Overview** - Grid of 8 service icons with titles

4. **Why Ocoron** - Trust signals
   - Experience
   - Results
   - Multilingual

5. **CTA Section** - "Ready to grow?"

---

### 2. Services Index (/services)

**Sections:**
1. Hero with services headline
2. Grid of 8 service cards (icon + title + short description + link)
3. CTA

---

### 3. Service Pages (8 pages)

Each service page follows this template:

```
1. Hero Section
   - Service title
   - Short description (1-2 sentences)
   - Background image

2. Overview
   - What we offer (paragraph)
   - Key benefits (3-4 bullet points)

3. Service List
   - Detailed offerings (from Services Draft)

4. Process (optional)
   - How we work (3-4 steps)

5. CTA
   - "Get Started" / "Contact Us"
```

**Content Source:** `/opt/fabrik/specs/sites/ocoron.com-media/Ocoron Services Draft.md`

---

### 4. About Page (/about)

**Sections:**
1. Hero - "About Ocoron"
2. Company Story - Brief history/mission
3. Team (optional) - Founder/key people
4. Values - What drives us
5. CTA

**Status:** ⚠️ Needs user input for company story

---

### 5. Insights (/insights)

**Sections:**
1. Hero - "Insights & News"
2. Blog grid (empty initially)
3. Categories sidebar

**Status:** ✅ Just structure, no posts yet

---

### 6. Contact (/contact)

**Sections:**
1. Hero - "Get in Touch"
2. Contact Form (Fluent Forms)
   - Name
   - Email
   - Company
   - Service Interest (dropdown)
   - Message
3. Contact Info
   - Email: contact@ocoron.com
   - LinkedIn: linkedin.com/company/ocoron/
4. Map (optional)

---

### 7. Privacy Policy (/privacy-policy)

**Source:** Complianz auto-generated
**Status:** ✅ Auto-generated during setup

---

### 8. Terms of Service (/terms)

**Source:** Complianz or AI-generated template
**Status:** ✅ Auto-generated during setup

---

## Competitor Reference: fixdanismanlik.com

### Their Structure
- Export & Business Development
- Grants and Incentives (KOSGEB, Trade Ministry, TUBITAK)
- Corporate Development
- Energy Consultancy

### Their Messaging
- AI/data-driven approach
- CRM transparency
- "One firm per sector" exclusivity
- Multilingual team

### Ocoron Differentiation
- **Broader scope:** AI, Manufacturing, Medical, Quality Management
- **Technical depth:** ISO certifications, R&D, ERP implementation
- **Government focus:** KOSGEB, TUBITAK, Turquality, TEKNOPARK

---

## Content Generation Process

### Phase 1: AI Generation (droid exec)
1. Generate service page content from Services Draft
2. Generate homepage copy
3. Generate About page draft
4. Generate meta descriptions for SEO

### Phase 2: User Review
1. Review generated content
2. Provide About page personal content
3. Approve or request changes

### Phase 3: Image Sourcing
1. Download images per service category
2. Optimize for web (compress, resize)
3. Add to media folder

### Phase 4: WordPress Integration
1. Create pages with Thrive Architect
2. Add content and images
3. Configure SEO (Rank Math)
4. Test multilingual (WPML)

---

## Turkish Translation

All pages will have Turkish versions via WPML.

**Translation approach:**
- AI-translate content
- User review for Turkish accuracy
- Native speaker review recommended

---

## Timeline Estimate

| Phase | Duration | Notes |
|-------|----------|-------|
| Content generation | 1-2 hours | AI-assisted |
| User review | 1-2 days | Depends on feedback |
| Image sourcing | 2-3 hours | Download + organize |
| WordPress build | 4-6 hours | Pages + design |
| Testing | 1-2 hours | Responsive, links, forms |

**Total:** ~2-3 days (with user review time)

---

## Content Generation Plan

### Source Material
- `/opt/fabrik/specs/sites/ocoron.com-media/Ocoron Services Draft.md`
- 8 service categories with detailed bullet points
- Turkish and English structure ready

### Output Structure

```
/opt/fabrik/specs/sites/ocoron.com-content/
├── pages-en.md       # All English content
├── pages-tr.md       # All Turkish content
└── meta.json         # SEO titles, descriptions, slugs
```

### Pages to Generate

| Page | Content Type | Est. Words EN/TR |
|------|--------------|------------------|
| Home | Hero + 4 features + CTA | ~500 |
| Services Index | 8 service cards | ~300 |
| 8 Service Pages | Full content each | ~400 × 8 = 3200 |
| About | Company story draft | ~400 |
| Contact | Form labels + CTA | ~100 |
| Privacy/Terms | Legal templates | ~1000 |

**Total:** ~5,500 words in English + Turkish translations

### Content Style
- Professional consultancy tone
- Confident, results-focused
- Technical depth (ISO, R&D, ERP expertise)
- Differentiate from competitors on breadth of services

### Each Page Includes
- Hero headline + subheadline
- Body content (paragraphs)
- Feature/service lists
- CTAs
- SEO meta title + description
