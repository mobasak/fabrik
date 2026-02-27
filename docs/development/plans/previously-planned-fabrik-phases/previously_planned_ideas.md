# Previously Planned Ideas & Future Enhancements

**Last Updated:** 2026-02-27

> This document consolidates future feature ideas, deferred enhancements, and low-priority improvements from various planning sessions. Items here are NOT currently scheduled but may be implemented when resources allow.

---

## Traycer MCP Integration (Future Work)

**Status:** 📋 Planned | **Priority:** Medium | **Value:** High automation leverage | **Cost:** ~$50/month

### Overview

Integrate Model Context Protocol (MCP) into Traycer workflows to enable live external data access during Epic Mode planning and YOLO execution. Focus on high-value integrations that reduce manual coordination.

### Phase 1: GitHub Issues Integration (Week 1)

**Goal:** Epic Mode automatically pulls and updates GitHub issues

**Implementation:**
1. Add Composio GitHub MCP server (10 min)
   - Authentication: GitHub OAuth
   - Tools: `list_issues`, `get_issue`, `update_issue`, `create_comment`
   - Account: Organization

2. Update custom templates (20 min)
   - `~/.traycer/prompt-templates/Kilo Plan - Fabrik 9-Step.md`
   - Add: "Before planning, use GitHub MCP to check related issues"
   - Add: "After commit, update GitHub issue status"

3. Test workflow (30 min)
   - Create test Epic: "Fix scaffold compliance"
   - Verify: Traycer pulls issues during `/epic-brief`
   - Verify: Tickets reference actual issue numbers
   - Verify: YOLO updates issue status automatically

**Value:** Single source of truth for 759+ compliance issues across 6 modules. No manual status updates.

**Done When:**
- [ ] Epic planning fetches GitHub issues labeled "compliance"
- [ ] Generated tickets include GitHub issue numbers
- [ ] YOLO execution updates issue status (in-progress → closed)
- [ ] Commit messages link to closed issues

---

### Phase 2: Notion Architecture Repository (Week 2)

**Goal:** Enforce consistent patterns across all `/opt/*` projects

**Implementation:**
1. Create Notion workspace (1 hour)
   - Page: "Fabrik Service Patterns" (health checks, env vars, CHANGELOG)
   - Page: "Active Services" (all projects + ports + URLs)
   - Page: "Architecture Decisions" (rationale for patterns)

2. Add Composio Notion MCP server (10 min)
   - Authentication: Notion OAuth
   - Tools: `search_pages`, `read_page`, `update_page`
   - Account: Organization

3. Update templates (30 min)
   - Epic planning: "Query Notion for relevant patterns"
   - Verification: "Check against Notion documented patterns"

**Value:** Every new microservice follows exact same conventions. Zero architecture drift.

**Done When:**
- [ ] Traycer can query "microservice health check pattern"
- [ ] Returns exact code snippet from Notion
- [ ] New service scaffolds match documented patterns
- [ ] Deployed services automatically update "Active Services" page

---

### Phase 3: Slack Critical Alerts (Week 3)

**Goal:** Monitor unattended YOLO execution

**Implementation:**
1. Create Slack channels (5 min)
   - `#fabrik-alerts` — Only BLOCKER/MAJOR verification failures
   - `#fabrik-deploys` — Epic completion summaries

2. Add Composio Slack MCP server (10 min)
   - Authentication: Slack OAuth
   - Tools: `post_message`
   - Account: Organization

3. Update verification template (20 min)
   - Add: "If BLOCKER issues, post to #fabrik-alerts"
   - Include: Phase name, issue summary, file paths
   - Do NOT spam for MINOR issues

**Value:** Stay informed without watching YOLO. Critical failures surface immediately.

**Done When:**
- [ ] BLOCKER verification failure → Slack message in #fabrik-alerts
- [ ] Message includes: Phase, files, issues
- [ ] Epic completion → Summary in #fabrik-deploys
- [ ] MINOR issues do NOT trigger alerts

---

### Cost & ROI

| Item | Cost | Notes |
|------|------|-------|
| Composio Team Plan | ~$20-50/month | 250+ integrations |
| Traycer Pro+ | $384/year | Already paid (sunk cost) |
| **Time Saved** | 2-4 hours/week | No manual issue updates, pattern lookups |
| **ROI** | Positive after Month 1 | 8-16 hours saved vs $50 cost |

---

### Example End-to-End Workflow (After All 3 Phases)

```
You: "Create auth service with JWT"

Traycer Epic Mode:
1. MCP → Notion: Pull "auth service pattern"
2. Generates Epic Brief with JWT library, token expiry, refresh flow
3. MCP → GitHub: Check existing "auth" issues
4. Creates tickets referencing issue #142 (JWT rotation)

YOLO Execution:
5. Implements code following Notion pattern
6. MCP → GitHub: Updates issue #142 → "in-progress"
7. Verification passes
8. MCP → GitHub: Closes issue #142, links commit
9. MCP → Slack: "#fabrik-deploys: Auth service complete, 3 tickets, 0 blockers"

You: Check Slack, review commit, done.
```

---

### What NOT to Integrate

| Tool | Reason |
|------|--------|
| Gmail | Code-first workflow, not email-driven |
| Linear | GitHub already works, migration overhead |
| Google Calendar | Doesn't integrate with code workflow |
| Generic docs search | Local `docs/` folder sufficient |

---

### References

- MCP Documentation: `docs/traycer/README.md` (MCP Integration section)
- Traycer Platform: https://traycer.ai
- Composio: https://composio.dev

---

### Complementary: GitHub Ticket Assist (Future Work)

**Status:** 📋 Planned | **Priority:** High | **Value:** Immediate automation wins | **Cost:** FREE (included in Pro+)

**Alternative/Addition to MCP GitHub integration**

#### What It Does

Ticket Assist automatically generates development plans from GitHub issues without manual Epic Mode planning.

**Workflow:**
```
GitHub Issue → Traycer Auto-Plan → YOLO Execution → Done
```

#### When to Use

**Use Ticket Assist for:**
- ✅ Standalone bug fixes ("Fix health check timeout")
- ✅ Security patches ("Update dependency X to v2.0")
- ✅ Small features ("Add retry logic to API client")
- ✅ Issues with clear, detailed descriptions

**Use MCP GitHub for:**
- ✅ Multi-issue Epics ("Fix all 759 compliance issues")
- ✅ Cross-module refactoring ("Standardize env vars across /opt/*")
- ✅ Complex features requiring architecture decisions

#### Recommended Setup for Fabrik

**Repository:** `fabrik` (main repo)

**Configuration:**
```yaml
Target Branch: main
Plan Creation: On
Trigger: On issue creation
Label Filter: "auto-plan"
```

**Label Strategy:**
- `auto-plan` → Ticket Assist generates plan automatically
- `epic` → Handle via MCP GitHub in Epic Mode (manual planning)
- `manual` → No automation (review, research, unclear scope)

**Example Issue Labels:**
```
Issue #142: JWT token rotation
Labels: security, auth, auto-plan
→ Ticket Assist creates plan

Issue #143-899: Compliance fixes (759 issues)
Labels: compliance, epic
→ Epic Mode with MCP GitHub query

Issue #900: Research alternative auth providers
Labels: research, manual
→ No automation
```

#### Implementation Steps

1. **Install Traycer GitHub App** (5 min)
   - Traycer Platform → Ticket Assist → Repositories
   - Add `fabrik` repository
   - Grant access to GitHub app

2. **Configure Settings** (5 min)
   - Target Branch: `main`
   - Trigger: On issue creation
   - Label Filter: `auto-plan`

3. **Test Workflow** (15 min)
   - Create test issue: "Fix broken health check"
   - Add label: `auto-plan`
   - Verify: Plan appears in Traycer
   - Review plan → Run YOLO or manual implementation

**Done When:**
- [ ] GitHub app installed for `fabrik` repo
- [ ] Label filter configured: `auto-plan`
- [ ] Test issue generates plan automatically
- [ ] Plan quality is good (clear steps, file references)

#### Cost

**Free** — Built into Traycer Pro+ subscription (already paid)

#### Combined Strategy (Ticket Assist + MCP GitHub)

**Best of both worlds:**

```
Small Issues (auto-plan label):
  GitHub Issue → Ticket Assist → YOLO → Done
  (Zero manual planning)

Large Epics (epic label):
  GitHub Issues → Epic Mode (MCP queries all) → Tickets → YOLO → Done
  (Organized planning for multi-issue work)

Manual Work (manual label):
  GitHub Issue → You investigate → Manual plan/implementation
  (Research, unclear scope, needs human judgment)
```

**ROI:**
- Ticket Assist: Saves 30-60 min per small issue (no manual planning)
- MCP GitHub: Saves 2-4 hours per Epic (organized multi-issue work)
- Combined: Best automation coverage

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
