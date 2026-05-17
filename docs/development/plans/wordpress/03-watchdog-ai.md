# Watchdog AI — Autonomous Site Admin

## What

A tiered automation system that manages WordPress sites after deployment. Tier 1 is cron scripts (no LLM, free). Tier 2 adds bounded LLM calls for specific decisions. Tier 3 is a strategic AI agent for monthly planning. Build in order — each tier works independently.

## Why

A WordPress site that stops getting content dies in Google rankings within weeks. Plugins without updates become security holes. Broken links accumulate. Without automation: you manually manage 10+ sites. With tiered watchdog: sites manage themselves, at the cost appropriate to their maturity.

## Three Tiers

### Tier 1 — Cron Automation (no LLM, $0/month)

Pure logic scripts. Already 80% built in existing codebase. Runs via VPS cron.

| Task | Frequency | What it does | Existing code |
|---|---|---|---|
| Health check | Every 5 min | Query Gatus API → site up? SSL valid? CWV within threshold? | Gatus already monitors; this reads the API |
| Content publish | Daily 03:00 | Drain ready briefs → publish 2 articles | `src/fabrik/orchestrator/content_publisher.py` ✅ |
| Social distribution | After each publish | Auto-post to social channels via n8n webhook | `src/fabrik/notifications.py` + n8n workflow |
| Sitemap resubmit | After each publish | Notify Google/Bing/IndexNow | `src/fabrik/drivers/dns.py` → `update_sitemap()` ✅ |
| Broken link scan | Daily 04:00 | Crawl all internal + affiliate links, log 404s | NEW: curl loop over sitemap URLs |
| 404 → redirect | After scan | Known slug changes → auto-create 301 via RankMath | NEW: WP-CLI `wp redirection add` |
| DB maintenance | Weekly Sun 02:00 | Prune transients, spam, revisions, optimize | `make db-clean` (Makefile target) ✅ |
| Plugin update check | Daily 05:00 | `wp plugin list --update=available` → log + auto-apply minor with snapshot | `src/fabrik/drivers/wordpress.py` WP-CLI ✅ |
| Cache warm | After publish | Purge CF + hit new URLs | `src/fabrik/wordpress/cache.py` → `flush_all()` ✅ |
| Email capture check | Weekly | Verify FluentCRM forms exist on homepage + key pages, alert if missing | NEW: curl + grep for form shortcode |
| Daily report | 08:00 | Template: published N, health OK/FAIL, N 404s fixed, social posted | `src/fabrik/notifications.py` → Telegram ✅ |

**Cron schedule:**
```
*/5 * * * *   fabrik watchdog health --all
0 3 * * *     fabrik watchdog publish --all --limit 2
0 4 * * *     fabrik watchdog scan-links --all
0 5 * * *     fabrik watchdog check-updates --all
0 2 * * 0     fabrik watchdog db-clean --all
0 8 * * *     fabrik watchdog report --daily --all
```

**Cost:** $0. No LLM. Pure automation.
**Build time:** ~6 hours (mostly wiring existing code into a unified `fabrik watchdog` CLI command).

### Tier 2 — Bounded LLM Decisions (~$1-3/site/month)

LLM makes specific, scoped decisions. One call per decision. Hard token cap. Uses Claude Haiku (cheapest).

| Decision | Trigger | Input to LLM | Output | Frequency |
|---|---|---|---|---|
| "Which keywords next?" | Brief queue < 3 ready | GSC top 20 keywords + positions + existing briefs | 5 keyword suggestions in cluster structure (pillar or supporting) | Weekly |
| "Which article to refresh?" | Weekly cycle | GSC data: articles with declining impressions | 1 article slug + what to add/update | Weekly |
| "Safe to update plugin?" | Minor update available | Plugin changelog (scraped from WP.org) | Yes/No + reason | Per update |
| "Content plan for next week" | Monday | Last week's performance + **upcoming events from calendar-orchestration-engine** | 5 topic suggestions (keyword + timing + event hook + cluster position) | Weekly |
| "Fix this 404 pattern?" | >5 404s to same pattern | URL list + referrer data | Redirect rule suggestion | When triggered |
| "Internal link opportunities" | Weekly | New articles published this week + existing pillar pages | Link suggestions: "Add link from [article] to [pillar] with anchor [text]" → auto-apply via WP REST API | Weekly |
| "Newsletter content" | Weekly (if email list exists) | Last 7 days published articles | Summary draft → FluentCRM campaign (auto-send or human-approve per config) | Weekly |
| "Topical authority gaps" | Bi-weekly | Full content inventory + keyword clusters | Missing supporting articles in each cluster. Creates SEO jobs to fill gaps. | Bi-weekly |

### Calendar-Driven Content Planning (calendar-orchestration-engine integration)

The `calendar-orchestration-engine` project contains **15,000+ enriched global events** (holidays, industry dates, sector events, cultural observances) scraped from multiple sources and enriched with LLM descriptions. It covers all countries and sectors.

**How the watchdog uses it:**

| Use case | Example | How |
|---|---|---|
| **Topical content timing** | "International Quality Day is Nov 9" → publish quality consulting article 2 weeks before | Query calendar API for upcoming events matching site keywords |
| **Seasonal content** | Ecommerce site: "Black Friday Nov 28" → prepare deals content 3 weeks ahead | Event type: `commercial` + site preset: `ecommerce` |
| **Industry events** | "Canton Fair April 15" → trade-intelligence article for company sites | Event sector matches site's service categories |
| **Holiday publishing schedule** | Don't publish during Bayram (low readership). Ramp up before. | Event type: `public_holiday` + country: `TR` → pause content |
| **Bilingual content hooks** | "Cumhuriyet Bayramı Oct 29" → Turkish-language article auto-planned | Event country + site language config |

**Integration point:** Tier 2 weekly content plan query includes:
```
Input to LLM:
  - GSC performance data (what's working)
  - Upcoming events next 2-4 weeks (from calendar-orchestration-engine API)
  - Site preset + service categories (what's relevant)
  - Existing content (avoid duplication)

Output: 5 content topics with timing + event hook
```

This transforms content planning from reactive ("what keyword is declining?") to **proactive** ("what's COMING that we should write about NOW").

**How it works:**
```python
# Example: keyword decision
prompt = f"""
Site: {domain}
Current top keywords (from GSC): {top_20_keywords_with_positions}
Existing briefs in queue: {pending_briefs}
Site preset: {preset} (focus: {preset_description})

Suggest 5 new long-tail keywords to target. 
Rules: no cannibalization with existing content, 
search volume > 100/month, difficulty < 40.
Return JSON: [{{"keyword": "...", "intent": "...", "target_page_type": "..."}}]
"""
response = kilo_client.chat(model="claude-haiku", prompt=prompt, max_tokens=500)
```

**Budget enforcement:**
- Max 10 LLM calls/site/week (hard cap in code)
- If cap reached → skip LLM decisions this cycle, use last week's plan
- Monthly cost alert if > $5/site → Telegram warning

**GSC Integration (the missing piece):**

| What | How | Status |
|---|---|---|
| GSC OAuth setup | One-time per site via site-provisioner | Site-provisioner registers site ✅ |
| GSC data pull | Google Search Console API → query analytics | NEW: `src/fabrik/watchdog/gsc_client.py` |
| Data storage | Per-site JSON snapshots in `data/watchdog/<site>/gsc/` | NEW |
| Trend detection | Compare this week vs last week vs 4-week average | NEW: `src/fabrik/watchdog/analyzer.py` |

**Build time:** ~12 hours (GSC integration is the bulk — 8 hours. LLM decision wrappers — 4 hours).

### Tier 3 — Strategic Agent (monthly, ~$3-5/site/month)

Full LLM reasoning for complex, infrequent decisions. Uses Claude Sonnet (better reasoning). Runs monthly or on-trigger only.

| Task | Trigger | What it does | Model |
|---|---|---|---|
| Monthly strategy review | 1st of month | Analyzes full month GSC data + content performance → strategy doc (double down / drop / new topics) | Sonnet |
| Competitor gap analysis | 1st of month | web-scraper output (competitor URLs + keywords) → gaps in your content | Sonnet |
| Content quality audit | Monthly | Reads 5 lowest-performing articles → refresh / merge / delete / redirect | Sonnet |
| **Site scorecard** | Monthly | KPIs: sessions, top-10 concentration, email list size, content velocity, CWV p75 LCP, new referring domains, RPM (if monetized) | Sonnet |
| **Decision triggers** | Monthly | Evaluate: >15% MoM growth 3 months = "double down". 12 months flat = "consider selling". Report. | Sonnet |
| **AI-Search visibility** | Monthly | Sample 10 brand queries in Claude/ChatGPT → is site cited? Track trend. | Sonnet |
| **Topical authority review** | Monthly | Full cluster map: which pillars are strong, which have gaps, which supporting articles underperform | Sonnet |
| PHP error diagnosis | GlitchTip spike | Reads error log + stack trace → suggests fix OR escalates | Sonnet |
| Traffic drop analysis | >20% week-over-week | GSC + Gatus + GlitchTip data combined → root cause hypothesis | Sonnet |

**Safety rules for Tier 3:**
- NEVER directly modifies code or plugin files on production
- PHP fix suggestions are REPORTED, not applied. Human applies.
- Plugin major updates: stages in WP Staging, reports result, human approves promotion
- Strategy changes (new keyword domain, drop a topic) always reported, never auto-applied
- Monthly budget hard cap: $10/site. If exceeded → Tier 3 pauses until next month.

**Never automate (watchdog REPORTS only, kills the asset if automated):**
- Final edit pass on flagship/money content pieces
- Author POV / personal stories (your EEAT moat)
- Pricing, positioning, sponsorship decisions
- Selling a site decision
- Legal/tax/compliance decisions
- Outreach (AI personalizes, human sends)

### Strategic Layers (built into Tier 2+3 logic)

**Topical authority architecture:**
- Every content brief is placed within a cluster (pillar + 15-30 supporting articles)
- Never write isolated articles — always fill gaps in existing clusters
- Internal links flow: supporting → pillar (watchdog enforces this weekly via Link Whisper data)
- One site = one tight territory. Don't spread until DR 40+.

**Owned audience > traffic:**
- Every site ships with FluentCRM lead magnet + 5-email welcome sequence (deployed at Stage 8)
- Watchdog verifies email capture forms exist on key pages (Tier 1 weekly check)
- Watchdog assembles weekly newsletter from published content (Tier 2)
- Push notifications via OneSignal (optional, per-site config) — 10-20% return visits

**AI-Search visibility (the new SEO):**
- Optimize for citation, not just click. Structured data, definitional intros, original data.
- Watchdog tracks brand mentions in LLM outputs monthly (sample queries)
- RankMath schema markup + FAQ blocks improve citation probability

**Build time:** ~16 hours (competitor scraper config — 4h, strategy prompt engineering — 6h, safety/reporting — 6h).

## Per-Profile Task Matrix

Not every site needs every watchdog task. The `profile` field in watchdog config determines which tasks activate:

| Task | Company | SaaS | Content | Landing | Ecommerce | Digital | Membership | Appointments |
|---|---|---|---|---|---|---|---|---|
| **Tier 1** | | | | | | | | |
| Content publish (daily) | ✅ 2/day | ✅ 2/day | ✅ 3-5/day | ❌ | ✅ 2/day | ✅ 1/day | ✅ 1/day | ✅ 1/day |
| Social distribution | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Broken link scan | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Affiliate link scan | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Plugin updates | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Email capture check | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Push notifications | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Tier 2** | | | | | | | | |
| Keyword strategy (GSC) | ✅ | ✅ | ✅ | ❌ | ✅ (product keywords) | ✅ | ❌ (gated) | ✅ (local SEO) |
| Topical authority gaps | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Internal linking | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Newsletter assembly | ✅ | ❌ | ✅ | ❌ | ✅ (promotions) | ✅ | ✅ (member updates) | ❌ |
| Calendar-driven content | ✅ | ✅ | ✅ | ❌ | ✅ (seasonal promos) | ❌ | ❌ | ✅ (seasonal services) |
| Article refresh | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Tier 3** | | | | | | | | |
| Monthly strategy | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Competitor analysis | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ (local) |
| AI-Search visibility | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| RPM/revenue tracking | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ (MRR) | ✅ (booking rev) |
| Site scorecard | ✅ | ✅ | ✅ | ✅ (conversion only) | ✅ | ✅ | ✅ | ✅ |
| Decision triggers | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Profile-specific** | | | | | | | | |
| Lead form conversion monitoring | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Cart abandonment tracking | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Booking rate / no-show tracking | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Churn / retention monitoring | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Review collection prompts | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ |
| Service page seasonal refresh | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Trial/signup funnel monitoring | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |

**Landing profile is minimal:** Only health check, broken links, plugin updates, conversion tracking. No content pipeline, no SEO, no newsletter. It's a single page — the watchdog just ensures it stays up and converts.

**Open for new profiles:** Adding a new site type (e.g., LMS, community, marketplace) requires:
1. New preset YAML in `templates/wordpress/presets/`
2. New golden image layer (`Dockerfile.<profile>`)
3. New column in this task matrix (which tasks apply)
4. New watchdog config template in `configs/watchdog/templates/`

No changes to the watchdog runner code. It reads `profile` from config → activates matching tasks. New profiles are data, not code.

### Per-Site Config Example

```yaml
# configs/watchdog/ocoron-com.yaml
site_id: ocoron-com
domain: ocoron.com
profile: company
owner_id: ozgur

tier1:
  content_limit_daily: 2
  social_distribution: true
  social_channels: [linkedin, twitter]  # n8n routes per channel
  link_scan: true
  affiliate_link_scan: false  # not monetized via affiliates
  push_notifications: false   # not a content site
  email_capture_check: true

tier2:
  enabled: true
  llm_model: claude-haiku-4-5-20251001
  max_calls_per_week: 10
  keyword_strategy: true
  topical_authority: true
  internal_linking: true
  newsletter: true
  newsletter_mode: auto  # auto-send (or "approve" for human review)
  calendar_content: true
  calendar_sectors: [quality, manufacturing, trade, consulting]
  article_refresh: true

tier3:
  enabled: true
  llm_model: claude-sonnet-4-6
  monthly_strategy: true
  competitor_domains: ["competitor1.com", "competitor2.com"]
  ai_search_visibility: true
  ai_search_queries: ["quality consulting turkey", "iso certification istanbul"]
  rpm_tracking: false  # not ad-monetized
  budget_cap_monthly_usd: 10.0

profile_specific:
  lead_form_monitoring: true
  lead_form_pages: ["/contact", "/services/quality-management"]
  service_page_refresh: quarterly
  local_seo: false  # ocoron is national/international, not local

escalation:
  telegram_chat_id: "your-chat-id"
```

```yaml
# configs/watchdog/myshop-com.yaml
site_id: myshop-com
domain: myshop.com
profile: ecommerce
owner_id: ozgur

tier1:
  content_limit_daily: 2
  social_distribution: true
  social_channels: [instagram, facebook, pinterest]
  link_scan: true
  affiliate_link_scan: true  # tracks affiliate product links
  push_notifications: true   # OneSignal: deals, new arrivals
  email_capture_check: true

tier2:
  enabled: true
  llm_model: claude-haiku-4-5-20251001
  max_calls_per_week: 10
  keyword_strategy: true  # product-focused keywords
  topical_authority: true
  internal_linking: true
  newsletter: true
  newsletter_mode: auto  # weekly promotions
  calendar_content: true
  calendar_sectors: [commercial, shopping]  # Black Friday, seasonal
  article_refresh: true

tier3:
  enabled: true
  llm_model: claude-sonnet-4-6
  monthly_strategy: true
  competitor_domains: ["competitor-shop.com"]
  ai_search_visibility: false  # product search, not informational
  rpm_tracking: true  # track revenue per visit
  budget_cap_monthly_usd: 10.0

profile_specific:
  cart_abandonment: true
  cart_recovery_tool: automatewoo  # AutomateWoo handles this
  review_collection: true  # prompt buyers for reviews after delivery
  lead_form_monitoring: false
  booking_monitoring: false

escalation:
  telegram_chat_id: "your-chat-id"
```

---

## Decision Framework (Deterministic, No "Maybe")

| Situation | Tier | Action | Escalate to human? |
|---|---|---|---|
| Site healthy, briefs ready | T1 | Publish 2 articles | No |
| Brief queue empty | T2 | LLM suggests 5 keywords → create SEO job | No |
| Keyword dropping 5+ positions | T2 | LLM picks article to refresh → TCO rewrites sections | No |
| Plugin minor update available | T2 | LLM reads changelog → if safe: stage → test → apply | No |
| Plugin MAJOR update available | T3 | Stage → test → REPORT result to human | **Yes** |
| 404 detected (single) | T1 | Auto-create redirect if slug pattern matches | No |
| 404 pattern (>5 same path) | T2 | LLM analyzes pattern → suggests bulk redirect rule | No |
| Broken image | T1 | Re-fetch from Image Broker | No |
| Traffic drop >20% | T3 | Full analysis → report findings | **Yes** |
| GSC manual action | T1 | Report immediately (no AI needed for this) | **Yes** |
| GlitchTip PHP fatal (known pattern) | T1 | Match against known fixes DB → auto-apply | No |
| GlitchTip PHP fatal (unknown) | T3 | LLM reads stack trace → suggests fix | **Yes** (report, don't apply) |
| New keyword domain opportunity | T3 | Monthly strategy surfaces it → report | **Yes** |
| Site down (Gatus red > 5 min) | T1 | Restart container → if still down → report | **Yes** if persists |
| Content quality issue (thin article) | T3 | Monthly audit flags it → suggest refresh/merge/delete | No for refresh, **Yes** for delete |

**Rule:** If action is reversible and low-risk → auto-apply. If irreversible or high-risk → report and wait.

## Architecture

```
VPS Cron
  ↓
fabrik watchdog run --daily/--weekly/--monthly
  ↓
┌─────────────────────────────────────────────────────────┐
│ Watchdog Runner (src/fabrik/watchdog/runner.py)          │
│                                                         │
│ For each registered site:                               │
│   1. Load site config (configs/watchdog/<site>.yaml)    │
│   2. Run Tier 1 tasks (always)                          │
│   3. Run Tier 2 tasks (if --weekly or --daily + T2 on) │
│   4. Run Tier 3 tasks (if --monthly)                    │
│   5. Compile report → send to Telegram                  │
└─────────────────────────────────────────────────────────┘
  ↓ calls
┌──────────────────────────────────────────────────────────┐
│ Existing services (no changes needed):                    │
│ • content_publisher.py → publish articles                 │
│ • drivers/seo.py → create keyword jobs, manage briefs    │
│ • drivers/tco.py → generate content                      │
│ • drivers/image_broker.py → fetch images                  │
│ • drivers/wordpress.py → WP-CLI (plugin updates, DB)     │
│ • drivers/wordpress_api.py → REST API (content updates)   │
│ • drivers/dns.py → sitemap resubmit                      │
│ • wordpress/cache.py → cache flush                        │
│ • notifications.py → Telegram                             │
└──────────────────────────────────────────────────────────┘
  + new modules
┌──────────────────────────────────────────────────────────┐
│ New code:                                                 │
│ • src/fabrik/watchdog/runner.py — orchestrator loop       │
│ • src/fabrik/watchdog/gsc_client.py — GSC API data pull   │
│ • src/fabrik/watchdog/analyzer.py — trend detection       │
│ • src/fabrik/watchdog/link_scanner.py — broken link crawl │
│ • src/fabrik/watchdog/decisions.py — T2 LLM wrappers     │
│ • src/fabrik/watchdog/strategy.py — T3 monthly review    │
│ • src/fabrik/watchdog/reporter.py — report templates      │
│ • configs/watchdog/<site>.yaml — per-site config          │
└──────────────────────────────────────────────────────────┘
```

## Per-Site Config (`configs/watchdog/<site>.yaml`)

```yaml
site_id: ocoron-com
domain: ocoron.com
preset: company
owner_id: ozgur  # for multi-tenant future

# Tier 1 (always active)
tier1:
  content_limit_daily: 2
  link_scan: true
  db_clean_weekly: true
  auto_redirect_404: true

# Tier 2 (activate after 30 days / 20+ articles)
tier2:
  enabled: true
  llm_model: claude-haiku-4-5-20251001
  max_calls_per_week: 10
  keyword_suggestions_count: 5
  auto_refresh_declining: true
  auto_update_minor_plugins: true

# Tier 3 (activate after 90 days / meaningful GSC data)
tier3:
  enabled: true
  llm_model: claude-sonnet-4-6
  monthly_strategy: true
  competitor_domains: ["competitor1.com", "competitor2.com"]
  budget_cap_monthly_usd: 10.0

# Escalation
escalation:
  telegram_chat_id: "your-chat-id"
  escalation_level: "owner"  # or "team" for SaaS
```

## Cost Model

| Sites | Tier 1/month | Tier 2/month | Tier 3/month | Total |
|---|---|---|---|---|
| 1 site | $0 | ~$1-3 | ~$3-5 | ~$4-8 |
| 5 sites | $0 | ~$5-15 | ~$15-25 | ~$20-40 |
| 10 sites | $0 | ~$10-30 | ~$30-50 | ~$40-80 |

Compare: hiring a virtual assistant for 10 sites = $500-1000/month. Watchdog = $40-80/month for BETTER coverage (24/7, no sick days, no missed checks).

## Dependencies

| Dependency | Required for | Status |
|---|---|---|
| `FABRIK_EXEC_MODE=local` | All tiers (runs on VPS) | Phase 1 ticket |
| Sites deployed via golden base | Tier 1 needs running sites | Phase 2 |
| SEO service deployed | Tier 1 content publish, Tier 2 keyword decisions | 🔨 Development |
| GSC API OAuth + data pull | Tier 2 keyword analysis, Tier 3 strategy | NEW |
| web-scraper configured per competitor | Tier 3 competitor analysis | 🔨 Development |
| calendar-orchestration-engine API | Tier 2 proactive content planning (15k+ events) | 🔨 Development |
| Kilo API access (Claude Haiku/Sonnet) | Tier 2 + 3 LLM decisions | ✅ Available |
| fabrik-api running | Optional: trigger from GUI dashboard | Phase 3 |

## Build Order (within Phase 5)

**Canonical ticket numbering lives in `04-execution-order.md`.** Summary:

| Tier | Tickets | What | Hours |
|---|---|---|---|
| Tier 1 | 5.1–5.7 | Package skeleton, daily cycle (health/publish/sitemap/report), link scanner, plugin updater, reporter, VPS cron, 7-day validation | ~15h |
| Tier 2 | 5.8–5.14 | GSC API integration, analyzer, calendar-orchestration-engine integration, LLM decision wrappers, budget enforcement, weekly cycle, 4-week validation | ~21h |
| Tier 3 | 5.15–5.20 | Strategy module, competitor config, content quality audit, event triggers, safety rules, monthly cycle | ~20h |

**Total: ~56 hours across 3 tiers, built incrementally with validation gates between each.**

## Acceptance Criteria

### Tier 1 (after ticket 5.7 — 7-day validation)
- [ ] `fabrik watchdog run --daily` publishes 2 articles without intervention for 7 consecutive days
- [ ] Daily Telegram report arrives at 08:00 with: articles published, health status, 404s fixed
- [ ] Broken links detected and redirected within 24 hours
- [ ] DB maintenance runs weekly without site disruption
- [ ] Plugin minor updates applied automatically (verified via `wp plugin list`)

### Tier 2 (after ticket 5.14 — 4-week validation)
- [ ] Weekly Telegram report includes GSC data (top keywords, position changes)
- [ ] LLM keyword suggestions create valid SEO jobs (verified: briefs generated)
- [ ] Content refresh targets declining articles (verified: GSC position recovers within 2 weeks)
- [ ] Max 10 LLM calls/week/site enforced (budget log shows cap respected)

### Tier 3 (after ticket 5.20 — monthly cycle live)
- [ ] Monthly strategy document generated with actionable recommendations
- [ ] Competitor gap analysis identifies keywords they rank for that we don't
- [ ] Traffic drop >20% triggers Telegram escalation within 1 hour
- [ ] Plugin major updates reported (not auto-applied) with test results
- [ ] Monthly cost stays under $10/site cap

## Multi-VPS Awareness

When scaling to multiple VPS nodes (Phase 6):
- Watchdog runs centrally (one VPS or a dedicated management node)
- Per-site config includes `vps_host` field
- All WP-CLI calls route through correct VPS via `FABRIK_EXEC_MODE=local` on that host
- OR: watchdog calls fabrik-api per VPS (if API is deployed on each node)
