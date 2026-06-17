# Previously Planned Ideas & Future Enhancements

**Last Updated:** 2026-03-07

> This document consolidates future feature ideas, deferred enhancements, and low-priority improvements from various planning sessions. Items here are NOT currently scheduled but may be implemented when resources allow.

---

## Phase 1 Deferred Items

### 1. Cloudflare WAF Rules (Phase 1c)

**Status:** 📋 Deferred | **Priority:** Low | **Source:** Phase1c.md

**Description:** Configure Cloudflare Web Application Firewall rules for WordPress protection.

**Why Deferred:** Not blocking - manual Cloudflare configuration can be done when WordPress goes to production.

**Implementation:** Manual Cloudflare dashboard configuration when needed:
- WordPress-specific attack patterns
- Comment spam prevention
- XML-RPC protection
- Login page rate limiting

**Done When:**
- [ ] WAF rules configured in Cloudflare dashboard
- [ ] Rules tested against WordPress sites
- [ ] Documentation added to SERVICES.md

---

### 2. WPML Translation Integration (Phase 1d)

**Status:** 📋 Deferred | **Priority:** Low | **Source:** Phase1d.md

**Description:** Multi-language WordPress site support via WPML plugin integration.

**Why Deferred:** Not needed for single-language sites. All current sites are English-only.

**Implementation:** Would require:
- WPML plugin installation in WordPress automation
- Language configuration in site spec
- Translation workflow integration
- Multi-language menu generation

**Done When:**
- [ ] WPML plugin auto-installed for multi-lang sites
- [ ] Spec supports `languages: [en, tr, de]` syntax
- [ ] Menus generated for each language
- [ ] Translation strings managed via spec

---

## Phase 2 Missing Items

### 1. Custom Flavor Themes (Design Changed)

**Status:** ✅ RESOLVED (Design Changed) | **Priority:** N/A | **Source:** Phase2.md

**Original Plan:** Create custom child themes (flavor-starter, flavor-corporate) for GeneratePress.

**Current Implementation:** Using GeneratePress + GP Premium plugin directly from wordpress.org.

**Why Changed:** Preset system achieves same goal without maintaining custom child themes. More maintainable approach.

**No Action Required** - Current design is superior.

---

### 2. Deploy ocoron.com

**Status:** 📋 Pending Deployment | **Priority:** Medium | **Source:** Phase2.md

**Description:** Deploy ocoron.com WordPress site using existing spec.

**What Exists:**
- ✅ Spec: `specs/sites/ocoron.com.yaml` (20KB)
- ✅ Content plan: `specs/sites/ocoron.com-content-plan.md`
- ✅ Media assets: `specs/sites/ocoron.com-media/`

**Done When:**
- [ ] Execute `fabrik apply specs/sites/ocoron.com.yaml`
- [ ] Verify site loads at ocoron.com
- [ ] Verify all pages rendered
- [ ] Verify SSL/HTTPS working

---

## Phase 3 Missing Items

### 1. Unified LLM Client Wrapper

**Status:** 📋 Not Implemented | **Priority:** High | **Source:** Phase3.md

**Description:** Provider-agnostic LLM client with Claude + OpenAI support, fallback, rate limiting, cost tracking.

**Current State:** Direct `anthropic.Anthropic()` usage in `content.py` and `legal.py`.

**Implementation Required:**
- Create `src/fabrik/ai/llm_client.py`
- Support Claude (primary) and OpenAI (fallback)
- Add rate limiting and retry logic
- Add cost tracking to SQLite
- Add streaming support

**Effort:** ~2 hours

**Done When:**
- [ ] `src/fabrik/ai/llm_client.py` created
- [ ] `LLMClient` class with `generate()` method
- [ ] Claude + OpenAI providers
- [ ] Cost tracking to SQLite
- [ ] `content.py` and `legal.py` migrated to use wrapper

---

### 2. Content Revision System

**Status:** 📋 Not Implemented | **Priority:** Medium | **Source:** Phase3.md

**Description:** Modify existing WordPress content based on natural language instructions.

**What's Needed:**
- Fetch existing page/post content
- Apply revision instructions via LLM
- Preserve structure, update copy
- Support partial updates (hero only, specific section)

**Implementation:**
- Create `src/fabrik/ai/content_reviser.py`
- `ContentReviser.revise_page(page_id, instructions)`
- `ContentReviser.revise_section(page_id, section_type, instructions)`

**Effort:** ~2 hours

**Done When:**
- [ ] `ContentReviser` class implemented
- [ ] Can revise existing pages via LLM
- [ ] Preserves page structure
- [ ] CLI command: `fabrik ai revise-page`

---

### 3. Bulk Generation Tools

**Status:** 📋 Not Implemented | **Priority:** Medium | **Source:** Phase3.md

**Description:** Generate multiple related content items in one operation.

**What's Needed:**
- Service pages generator (10+ services from brief)
- FAQ generator (Q&A pairs from topic)
- Blog series generator (5-10 posts on theme)
- Case study generator (customer stories)

**Implementation:**
- Create `src/fabrik/ai/bulk_generator.py`
- `BulkGenerator.generate_services(company, services_list)`
- `BulkGenerator.generate_faqs(topic, count)`
- `BulkGenerator.generate_blog_series(theme, count)`

**Effort:** ~4 hours

**Done When:**
- [ ] `BulkGenerator` class implemented
- [ ] Service pages generation working
- [ ] FAQ generation working
- [ ] Blog series generation working
- [ ] CLI commands for each generator

---

### 4. CLI AI Commands

**Status:** 📋 Not Implemented | **Priority:** High | **Source:** Phase3.md

**Description:** Command-line interface for AI content operations.

**Planned Commands:**
- `fabrik ai generate-page <site> <title>` - Generate single page
- `fabrik ai generate-post <site> <title>` - Generate blog post
- `fabrik ai revise-page <site> <page-id> "<instructions>"`
- `fabrik ai generate-services <site> <brief>`
- `fabrik ai generate-website <site-spec>` - Full site generation

**Implementation:**
- Add `src/fabrik/cli/ai.py`
- Wire up to existing `ContentGenerator` and new modules
- Add to `src/fabrik/cli.py` commands

**Effort:** ~4 hours

**Done When:**
- [ ] `fabrik ai` subcommand group created
- [ ] All 5 commands implemented
- [ ] Commands work with existing WordPress modules
- [ ] Help text and examples added

---

### 5. Windsurf Agent Integration

**Status:** 📋 Not Implemented | **Priority:** Low | **Source:** Phase3.md

**Description:** Documentation and context rules for Windsurf agents to use Fabrik autonomously.

**What's Needed:**
- Agent context document with Fabrik capabilities
- Agent rules for WordPress automation
- Example conversations
- Tool usage guidelines

**Implementation:**
- Create `docs/windsurf/agent_context.md`
- Create `.windsurf/rules/fabrik-ai-agent.md`
- Document Fabrik AI workflow
- Add example prompts

**Effort:** ~2 hours (documentation only)

**Done When:**
- [ ] Agent context documentation complete
- [ ] Rules file created
- [ ] Example conversations documented
- [ ] Windsurf agent can use Fabrik autonomously

---

## Phase 4 Missing Items

### 1. Cloudflare WAF Rules Module

**Status:** 📋 Not Implemented (Manual Config Available) | **Priority:** Low | **Source:** Phase4.md

**Description:** Programmatic WAF rule configuration for WordPress protection.

**Current State:** WAF rules must be configured manually in Cloudflare dashboard.

**What's Needed:**
- Create `src/fabrik/drivers/cloudflare_waf.py`
- WordPress-specific attack patterns
- Comment spam prevention
- XML-RPC protection
- Login page rate limiting
- Bot fight mode configuration

**Implementation:**
```python
class CloudflareWAF:
    - create_waf_rule(zone_id, rule_config)
    - enable_wordpress_protection(zone_id)
    - configure_rate_limiting(zone_id, endpoints)
    - enable_bot_fight_mode(zone_id)
```

**Effort:** ~1 hour

**Done When:**
- [ ] `cloudflare_waf.py` module created
- [ ] WordPress preset applies WAF rules automatically
- [ ] Rate limiting configured for /wp-login.php
- [ ] Bot fight mode enabled

**Alternative:** Continue using Cloudflare dashboard (current approach works fine).

---

### 2. Cloudflare Cache Rules Module

**Status:** 📋 Not Implemented (Manual Config Available) | **Priority:** Low | **Source:** Phase4.md

**Description:** Programmatic cache rule and page rule configuration.

**Current State:** Cache rules must be configured manually in Cloudflare dashboard.

**What's Needed:**
- Create `src/fabrik/drivers/cloudflare_cache.py`
- Page rules for static assets
- Cache purge API
- Cache-everything rules
- Bypass rules for admin/login

**Implementation:**
```python
class CloudflareCache:
    - create_page_rule(zone_id, url_pattern, actions)
    - purge_cache(zone_id, files=None)
    - enable_cache_everything(zone_id)
    - bypass_admin_cache(zone_id)
```

**Effort:** ~1 hour

**Done When:**
- [ ] `cloudflare_cache.py` module created
- [ ] WordPress preset applies cache rules
- [ ] Admin/login pages bypass cache
- [ ] Cache purge available via CLI

**Alternative:** Continue using Cloudflare dashboard (current approach works fine).

---

### 3. CLI DNS Commands

**Status:** 📋 Not Implemented | **Priority:** Low | **Source:** Phase4.md

**Description:** Command-line interface for DNS operations.

**Current State:** DNS operations require direct Python code using drivers.

**Planned Commands:**
- `fabrik dns zones` - List Cloudflare zones
- `fabrik dns records <zone>` - List DNS records
- `fabrik dns export <zone>` - Export records to YAML
- `fabrik dns add <zone> <type> <name> <value>` - Add record
- `fabrik dns delete <zone> <record-id>` - Delete record
- `fabrik dns migrate <domain>` - Migrate Namecheap → Cloudflare
- `fabrik dns configure <zone>` - Apply settings/WAF/cache
- `fabrik dns purge-cache <zone>` - Purge Cloudflare cache

**Implementation:**
- Add `src/fabrik/cli/dns.py`
- Wire up to existing `CloudflareClient` driver
- Add to `src/fabrik/cli.py` commands

**Effort:** ~2 hours

**Done When:**
- [ ] `fabrik dns` subcommand group created
- [ ] All 8 commands implemented
- [ ] Commands work with existing Cloudflare driver
- [ ] Help text and examples added

**Alternative:** Continue using Python API directly (acceptable for infrastructure automation).

---

### 4. Cloudflare Settings Module

**Status:** 📋 Not Implemented | **Priority:** Low | **Source:** Phase4.md

**Description:** Programmatic configuration of Cloudflare zone settings.

**Current State:** Settings must be configured manually in Cloudflare dashboard.

**What's Needed:**
- SSL mode (Flexible, Full, Full Strict)
- TLS version minimums
- HTTP/3 and QUIC
- Brotli compression
- Auto minify (HTML, CSS, JS)
- Rocket Loader
- Always HTTPS redirect

**Implementation:**
```python
class CloudflareSettings:
    - configure_ssl(zone_id, mode="full_strict")
    - configure_tls(zone_id, min_version="1.2")
    - enable_http3(zone_id)
    - enable_compression(zone_id)
    - enable_minify(zone_id, html=True, css=True, js=True)
```

**Effort:** ~1 hour

**Done When:**
- [ ] `cloudflare_settings.py` module created
- [ ] WordPress preset applies optimal settings
- [ ] SSL mode set to Full Strict
- [ ] Compression and minify enabled

**Alternative:** Continue using Cloudflare dashboard defaults (current approach works).

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
