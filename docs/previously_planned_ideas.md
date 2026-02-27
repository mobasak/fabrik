# Previously Planned Ideas & Future Enhancements

**Last Updated:** 2026-02-26

> This document consolidates future feature ideas, deferred enhancements, and low-priority improvements from various planning sessions. Items here are NOT currently scheduled but may be implemented when resources allow.

---

## Current Priority: Phase 1d (WordPress Automation)

### Active Tasks

| Task | Status | Notes |
|------|--------|-------|
| Deploy ocoron.com | 🚧 In Progress | Company site, multilingual EN/TR |
| Build preset loader | Pending | Load presets/company.yaml |
| Create custom themes | Pending | flavor-starter, flavor-corporate |
| WAF rules | Pending | Needs Cloudflare permissions |

### Next Steps

1. **Complete ocoron.com deployment** — First production WordPress site
2. **Build preset system** — Reusable site configurations
3. **Theme development** — GeneratePress child themes

---

## What's Next for Fabrik

**Date:** 2025-12-27
**Current Status:** Phase 1 ✅ | Phase 1b ✅ | Phase 1c ✅ | Phase 1d 🚧 | Phase 2 (67%)

---

## Completed Since Last Update

- ✅ **File API deployed** — `files-api.vps1.ocoron.com`
- ✅ **File Worker deployed** — Background processing active
- ✅ **All 8 microservices migrated to Coolify** — Auto-deploy via GitHub webhooks
- ✅ **Cloudflare DNS migration complete** — All DNS via Cloudflare
- ✅ **Phase 1 complete** — Foundation fully operational
- ✅ **Phase 1b complete** — Supabase + R2 integration
- ✅ **Phase 1c complete** — DNS automation

---

## Future: Web-Based Site Builder

### Overview

A web GUI that automates **Step 0 (Domain) + Step 1 (Hosting)** - the foundation for all site types.

**Key insight:** Register domain WITH Cloudflare nameservers from the start = instant DNS, no propagation wait.

### Step 0-1 Automation Flow

**What the User Sees:**
```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 0: DOMAIN                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Domain name: [newsite.com        ] [Check Availability]        │
│  ✅ Available! Price: $10.98/year                               │
│  Registration: [1 year ▼] WhoisGuard: [✓] Enable               │
├─────────────────────────────────────────────────────────────────┤
│  STEP 1: SITE TYPE                                              │
├─────────────────────────────────────────────────────────────────┤
│  ○ Company    ○ Landing    ○ SaaS    ○ Ecommerce    ○ Content  │
│                              [Register & Deploy →]              │
└─────────────────────────────────────────────────────────────────┘
```

**Behind the Scenes:**
1. Check domain availability (Namecheap API)
2. Create Cloudflare zone (get nameservers FIRST)
3. Register domain WITH CF nameservers
4. Add DNS records (A, CNAME)
5. Deploy WordPress container

**Propagation Times:**
| Domain Type | Wait | Reason |
|-------------|------|--------|
| New domain (our flow) | 5-60 min | Only TLD registry |
| Existing domain NS change | 24-48h | NS TTL + cache |

### API Endpoints Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/domains/check` | POST | Check availability |
| `/api/domains/pricing` | GET | Get pricing |
| `/api/account/balance` | GET | Namecheap balance |
| `/api/domains/register` | POST | Register with NS |
| `/api/cloudflare/zones` | POST | Create zone (existing) |
| `/api/cloudflare/dns/{domain}` | POST | Add records (existing) |

### Step 2-5: Site Configuration

After domain + hosting:
- **Step 2: Brand** — Name, tagline, colors, logo
- **Step 3: Services** — Add/edit service entities
- **Step 4: Contact** — Email, phone, address, social
- **Step 5: Review & Deploy** — Preview and publish

### Technical Architecture

**Frontend:** Next.js 14, TailwindCSS + shadcn/ui, React Hook Form + Zod
**Backend:** VPS DNS Manager (existing Cloudflare/Namecheap APIs)
**Integration:** Fabrik domain_setup.py, deployer.py

### Implementation Priority

1. **Backend APIs (1-2 days):** Domain check, register, pricing
2. **Fabrik Integration (1 day):** `register_domain()` function
3. **Web GUI (1-2 weeks):** Next.js wizard

---

## Changelog Automation (AI Tools & Services)

### Overview

**Goal:** Automatically track updates from AI tools and services we depend on, capturing changes from newsletters, changelog pages, and release notes.

**Why:** Stay current with model updates, deprecations, credit multipliers, and new features without manual monitoring.

### Tools to Monitor

| Tool | Changelog Source | Update Frequency |
|------|------------------|------------------|
| **Windsurf** | https://windsurf.com/changelog | Weekly (React SPA) |
| **Kilo AI** | https://kilo.ai/changelog | Variable |
| **Traycer AI** | https://traycer.ai/changelog | Variable |
| **Anthropic** | https://docs.anthropic.com/en/docs/about-claude/models | Monthly |
| **OpenAI** | https://platform.openai.com/docs/changelog | Weekly |
| **Google AI Studio** | Email newsletter | Variable |
| **Factory.ai** | Email newsletter | Variable |

### Windsurf Changelog Automation (Priority)

**Challenge:** https://windsurf.com/changelog is a React SPA with no RSS feed

**Proposed Solution:**
1. Playwright-based scraper to extract model announcements
2. Parse model names (GPT-*, Claude-*, Gemini-*, SWE-*)
3. Extract credit multipliers from announcement text (e.g., "10x credits")
4. Compare against current `config/models.yaml`
5. Alert on new/changed/deprecated models
6. Run daily alongside model refresh checks

**Implementation:**
```python
# scripts/changelog_monitor.py
async def scrape_windsurf_changelog():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://windsurf.com/changelog")

        # Extract model announcements
        entries = await page.query_selector_all('.changelog-entry')
        for entry in entries:
            title = await entry.query_selector('h3').text_content()
            date = await entry.query_selector('.date').text_content()
            content = await entry.query_selector('.content').text_content()

            # Parse model names and multipliers
            models = parse_model_names(content)
            multipliers = parse_credit_multipliers(content)

            # Compare with current config
            if is_new_model(models):
                notify_model_update(models, multipliers)
```

### Extended Changelog Monitoring

**Email Newsletter Processing:**
```python
# scripts/newsletter_processor.py
def process_newsletter_email(email_content: str) -> dict:
    """
    Extract changelog items from email newsletters.

    Supports:
    - Google AI Studio updates
    - Factory.ai release notes
    - Anthropic model announcements
    """
    # Parse email HTML/text
    # Extract version numbers, model names, changes
    # Compare against known versions
    # Return structured changelog data
```

**Unified Changelog Aggregator:**
```python
# scripts/changelog_aggregator.py
class ChangelogMonitor:
    """
    Unified changelog monitoring for all AI services.

    Sources:
    - Web scraping (Playwright for SPAs, requests for static pages)
    - RSS feeds (where available)
    - Email parsing (IMAP + HTML parsing)
    - API endpoints (where available)
    """

    async def check_all_sources(self):
        windsurf = await self.check_windsurf()
        kilo = await self.check_kilo()
        traycer = await self.check_traycer()
        anthropic = await self.check_anthropic()
        openai = await self.check_openai()

        return {
            'windsurf': windsurf,
            'kilo': kilo,
            'traycer': traycer,
            'anthropic': anthropic,
            'openai': openai,
        }

    def compare_with_cache(self, changes: dict):
        """Compare against cached versions, alert on new items."""
        cache = self.load_cache()
        new_items = []

        for tool, items in changes.items():
            for item in items:
                if item not in cache.get(tool, []):
                    new_items.append((tool, item))

        return new_items
```

**Notification Integration:**
```python
# Integration with existing notify.sh
def notify_changelog_update(tool: str, update: dict):
    """Send notification about changelog update."""
    message = {
        'title': f'{tool} Update Available',
        'body': f"New {update['type']}: {update['title']}",
        'url': update['url'],
        'priority': 'medium',
    }

    subprocess.run([
        os.getenv('FABRIK_NOTIFY_SCRIPT', '~/.factory/hooks/notify.sh')
    ], input=json.dumps(message), text=True)
```

### Files to Create

- `scripts/changelog_monitor.py` — Main monitoring script
- `scripts/scrapers/windsurf.py` — Windsurf-specific scraper
- `scripts/scrapers/kilo.py` — Kilo AI scraper
- `scripts/scrapers/traycer.py` — Traycer AI scraper
- `scripts/newsletter_processor.py` — Email newsletter parser
- `config/changelog_sources.yaml` — Configuration for all sources
- `config/changelog_cache.json` — Cached versions for comparison

### Dependencies

- `playwright` — Headless browser for SPA scraping
- `beautifulsoup4` — HTML parsing
- `imapclient` — Email fetching (if monitoring inbox)
- `feedparser` — RSS feed parsing (where available)

### Scheduling

```yaml
# Add to cron or systemd timer
0 9 * * * cd /opt/fabrik && python scripts/changelog_monitor.py --check-all --notify
```

### Priority

**Low** — Manual updates work for now, but automation would:
- Catch deprecations early
- Alert on credit multiplier changes
- Track new model releases
- Reduce manual monitoring overhead

---

## Integration Ideas (Backlog)

| Project | Use Case | Status |
|---------|----------|--------|
| YouTube Pipeline | Store audio in R2 | Idea |
| Translator | Document upload/download | Idea |
| Calendar Engine | ICS file storage | Idea |
| LLM Batch | Prompt/response audit trail | Idea |

---

## Future Enhancements (Low Priority)

- AI content generation for WordPress
- Custom section types for site builder
- Multi-site management dashboard
- Pre-built site templates marketplace
- Auto-scaling workers (monitor queue, spin up/down)
- Deployment webhooks (Slack/Discord/email notifications)
- GitHub Actions auto-deploy on push, preview PRs, rollback

---

## Notes

- All ideas here are **deferred**, not scheduled
- Revisit quarterly to reassess priorities
- Move to `docs/development/plans/` when ready to implement
- Archive completed ideas to `docs/archive/`
