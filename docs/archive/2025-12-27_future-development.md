> ⚠️ **ARCHIVED DOCUMENT** — This document is outdated and kept for historical reference only.
> See [ROADMAP_ACTIVE.md](../ROADMAP_ACTIVE.md) for current roadmap.

# Future Development Roadmap

**Last Updated:** 2025-12-25

---

## Web-Based Site Builder (Priority)

### Overview

A web GUI that automates **Step 0 (Domain) + Step 1 (Hosting)** - the foundation for all site types.

**Key insight:** Register domain WITH Cloudflare nameservers from the start = instant DNS, no propagation wait.

---

## Step 0-1 Automation Flow

### What the User Sees (Web GUI)

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 0: DOMAIN                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Domain name: [newsite.com        ] [Check Availability]        │
│                                                                 │
│  ✅ Available! Price: $10.98/year                               │
│  Account balance: $15.32                                       │
│                                                                 │
│  Registration: [1 year ▼] (1-10 years)                          │
│  WhoisGuard:   [✓] Enable free privacy protection               │
│                                                                 │
│  Contact Info (used for WHOIS):                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ First Name: [Ozgur              ] Last: [Basak        ] │   │
│  │ Email: [obasak@gmail.com                              ] │   │
│  │ Phone: [+90] [5326839524                              ] │   │
│  │ Address: [Caddebostan Mh. Op. Cemil Topuzlu Cd. 110/1 ] │   │
│  │ City: [Istanbul      ] State/Province: [34           ] │   │
│  │ Country: [Turkey (TR) ▼] Postal: [34728              ] │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [Save as default contact]                                      │
├─────────────────────────────────────────────────────────────────┤
│  STEP 1: SITE TYPE                                              │
├─────────────────────────────────────────────────────────────────┤
│  ○ Company (services, about, contact)                           │
│  ○ Landing (single page, conversion-focused)                    │
│  ○ SaaS (features, pricing, signup)                             │
│  ○ Ecommerce (WooCommerce store)                                │
│  ○ Content (blog, articles, SEO)                                │
│                                                                 │
│                              [Register & Deploy →]              │
└─────────────────────────────────────────────────────────────────┘
```

### Web GUI Form Requirements

| Field | Validation | Notes |
|-------|------------|-------|
| Domain | ASCII only, valid TLD | Auto-lowercase |
| Years | 1-10, dropdown | Default: 1 |
| WhoisGuard | Checkbox | Default: enabled |
| First/Last Name | **English characters only** | No diacritics (ş→s, ü→u, etc.) |
| Email | Valid email format | Required |
| Phone | Format: +CC.NNNNNNNNNN | Country code + number |
| Address | English characters only | Required |
| City | English characters only | Required |
| State/Province | 2-3 char code or full name | Required |
| Country | ISO 2-letter code dropdown | Required |
| Postal Code | Varies by country | Required |

**Character enforcement:** All text fields must reject non-ASCII characters. Show inline validation: "Please use English characters only (a-z, A-Z, 0-9)"

### What Happens Behind the Scenes

```
User clicks [Register & Deploy →]
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 0A: Check domain availability                              │
│   POST /api/domains/check {"domain": "newsite.com"}             │
│   → namecheap.domains.check                                     │
│   ✅ Available                                                  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 0B: Create Cloudflare zone (get nameservers FIRST)         │
│   POST /api/cloudflare/zones {"domain": "newsite.com"}          │
│   → Returns: ["kiki.ns.cloudflare.com", "lex.ns.cloudflare.com"]│
│   ✅ Zone created, nameservers obtained                         │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 0C: Register domain WITH Cloudflare nameservers            │
│   POST /api/domains/register {                                  │
│     "domain": "newsite.com",                                    │
│     "years": 1,                                                 │
│     "nameservers": ["kiki.ns.cloudflare.com", "lex..."],        │
│     "contacts": {...}                                           │
│   }                                                             │
│   → namecheap.domains.create (Nameservers param!)               │
│   ✅ Registered with CF nameservers from day 1                  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1A: Add DNS records                                        │
│   POST /api/cloudflare/dns/newsite.com                          │
│   → A record: newsite.com → 172.93.160.197                      │
│   → CNAME: www.newsite.com → newsite.com                        │
│   ✅ DNS configured                                             │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1B: Deploy WordPress container                             │
│   → Coolify API: create project, deploy compose                 │
│   ✅ WordPress running                                          │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ DONE: Site ready!                                               │
│   https://newsite.com → WordPress admin                         │
└─────────────────────────────────────────────────────────────────┘
```

### API Endpoints Required (VPS DNS Manager)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/domains/check` | POST | Check domain availability |
| `/api/domains/pricing` | GET | Get registration pricing |
| `/api/account/balance` | GET | Get Namecheap balance |
| `/api/domains/register` | POST | Register domain with nameservers |
| `/api/cloudflare/zones` | POST | Create zone (existing) |
| `/api/cloudflare/dns/{domain}` | POST | Add DNS records (existing) |

### Why This Is Better

| Old Flow | New Flow |
|----------|----------|
| Register domain | Create CF zone first |
| Default Namecheap NS | Get CF nameservers |
| Change NS to Cloudflare | Register WITH CF NS |
| **Wait 24-48h propagation** | **5-60 min (TLD registry only)** |

### Propagation Times

| Domain Type | Expected Wait | Reason |
|-------------|---------------|--------|
| **New domain (our flow)** | 5-60 minutes | Only TLD registry propagation |
| **Existing domain NS change** | 24-48 hours | NS TTL + global cache expiry |

**Note:** The 5-60 min is for the TLD registry (`.shop`, `.com`, etc.) to publish the NS records. Once Cloudflare zone shows `status: active`, DNS is live globally.

---

## Step 2-18: Site Configuration

After Step 0-1, the web GUI continues to Step 2+ (site content):

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: BRAND                                                  │
├─────────────────────────────────────────────────────────────────┤
│  Company name: [Acme Corp                        ]              │
│  Tagline (en): [Innovation at Scale              ]              │
│  Tagline (tr): [Ölçekte İnovasyon                ]              │
│                                                                 │
│  Primary color: [#3498DB] ████                                  │
│  Logo: [Upload] or [Generate with AI]                           │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: SERVICES/ENTITIES                                      │
├─────────────────────────────────────────────────────────────────┤
│  + Add Service                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 1. Consulting    [Edit] [Delete]                        │   │
│  │ 2. Development   [Edit] [Delete]                        │   │
│  │ 3. Support       [Edit] [Delete]                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: CONTACT                                                │
├─────────────────────────────────────────────────────────────────┤
│  Email: [info@acme.com           ]                              │
│  Phone: [+90 212 XXX XX XX       ]                              │
│  Address: [Istanbul, Turkey      ]                              │
│  Social: [LinkedIn] [Twitter] [Instagram]                       │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: REVIEW & DEPLOY                                        │
├─────────────────────────────────────────────────────────────────┤
│  Preview: [Home] [Services] [About] [Contact]                   │
│                                                                 │
│  ✅ Domain: newsite.com (registered)                            │
│  ✅ DNS: Configured                                             │
│  ✅ WordPress: Running                                          │
│  ⏳ Content: Ready to deploy                                    │
│                                                                 │
│                              [Deploy Content →]                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technical Architecture

### Frontend (Web GUI)

```
Tech Stack:
  - Next.js 14 (App Router)
  - TailwindCSS + shadcn/ui
  - React Hook Form + Zod
  - Real-time status updates (SSE)

Pages:
  /new                    # Step 0-1 wizard
  /sites                  # List all sites
  /sites/[domain]         # Site dashboard
  /sites/[domain]/edit    # Edit content (Step 2+)
```

### Backend (VPS DNS Manager)

```
Existing:
  - Cloudflare zone creation
  - Cloudflare DNS records
  - Namecheap nameserver updates

New (to implement):
  - Namecheap domain availability check
  - Namecheap domain registration (with NS param)
  - Namecheap pricing/balance
```

### Integration (Fabrik)

```
fabrik.wordpress.domain_setup.py:
  - provision_domain()     # Existing (zone + NS + records)
  - register_domain()      # NEW (full registration)

fabrik.wordpress.deployer.py:
  - SiteDeployer._step_dns()  # Existing
```

---

## Implementation Priority

### Phase 1: Backend APIs (1-2 days)
- [ ] Add `/api/domains/check` to VPS DNS Manager
- [ ] Add `/api/domains/register` with nameservers param
- [ ] Add `/api/domains/pricing` endpoint
- [ ] Test full registration flow

### Phase 2: Fabrik Integration (1 day)
- [ ] Add `register_domain()` to domain_setup.py
- [ ] Update `provision_domain()` to use registration if needed

### Phase 3: Web GUI (1-2 weeks)
- [ ] Next.js project setup
- [ ] Step 0-1 wizard
- [ ] Step 2-5 content editor
- [ ] Deploy to VPS

---

## Alternative: CLI Wizard (Interim)

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
