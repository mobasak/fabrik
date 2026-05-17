# Execution Order — What to Build When

## Dependency Chain

```
[0] Decisions (WPML vs Polylang, plugin tiering)
 ↓
[1] Foundation (EXEC_MODE=local, ocoron.com live, content cron)
 ↓
[2] Golden Base (Docker image + first-boot + preview/promote + fabrik wp create)
 ↓
[3] API Bridge (fabrik-api on VPS + MCP server)
 ↓
[4] GUI (creation wizard + operations dashboard)
 ↓
[5] Watchdog AI (Tier 1 cron → Tier 2 LLM → Tier 3 strategy)
 ↓
[6] Scaling & SaaS (multi-VPS + billing, when VPS1 outgrown)
```

---

## Phase 0 — Decisions (BLOCKERS, must resolve before any code)

| # | Decision | Status | Resolution |
|---|---|---|---|
| 0.1 | **WPML vs Polylang** | ✅ RESOLVED | **Polylang Pro + AutoPoly Pro + SearchWP Polylang + Polylang for WooCommerce.** AutoPoly calls DeepL directly (API key). AMP not used. WPML removed from all profiles. |
| 0.2 | **Plugin tiering** | PENDING | All plugins active at launch (heavier) vs Launch/Growth/Scale tiers (lighter, add as site matures). Affects golden base + deployer + watchdog. | Before Phase 2 |

---

## Phase 1 — Foundation (make existing pipeline work from VPS)

| # | What | Effort | Depends on |
|---|---|---|---|
| 1.0 | Create project-specific `CLAUDE.md` + `KILO_CLI_RULES.md` for WordPress Factory development (rules for AI agents building this infrastructure) | 2h | Nothing |
| 1.1 | Implement `FABRIK_EXEC_MODE=local` in `src/fabrik/drivers/wordpress.py` — 1-line gate on `_exec()` and `ContainerResolver.resolve()` | 1h | 1.0 |
| 1.2 | Fix ocoron.com spec: WPML→Polylang Pro, fill remaining DRAFT fields, add Translator API config, change status DRAFT→READY | 2h | 0.1 ✅ resolved |
| 1.3 | Fix `docs/reference/wordpress/deployment-workflow.md` — Apache→FPM references (outdated, contradicts 62-wordpress.md) | 30min | Nothing |
| 1.4 | Deploy ocoron.com via pipeline: `fabrik wp plan ocoron-com && fabrik wp apply ocoron-com` | 1h | 1.1 + 1.2 |
| 1.5 | Set up VPS cron: `0 3 * * * fabrik content publish ocoron.com --limit 2` | 30min | 1.4 |
| 1.6 | Register ocoron.com in SEO service + create first keyword jobs: `fabrik seo site-register` + `fabrik seo job-create` | 1h | 1.4 |

**Result:** ocoron.com live via pipeline, content publishing daily. First real validation of the entire 30-step workflow.

**Effort:** ~8 hours / 1 day

---

## Phase 2 — Golden Base (make new sites instant)

| # | What | Effort | Depends on |
|---|---|---|---|
| 2.1 | Resolve plugin tiering (per 0.2): define BASE plugins (golden image) vs LAUNCH additions vs GROWTH additions vs SCALE additions per profile | 2h | 0.2 decided |
| 2.2 | Create `templates/wordpress/golden/Dockerfile` — hybrid approach: extract plugin zips to filesystem, theme files, MU-plugins, wp-config-extra, nginx config | 4h | 2.1 |
| 2.3 | Create `templates/wordpress/golden/first-boot.sh` — one-time: wp core install, plugin activate, RankMath/FlyingPress/Complianz base config, mark initialized | 2h | 2.2 |
| 2.4 | Create `scripts/build_golden_base.sh` — build + tag + test (spin up temp, verify 10 security layers, verify plugins active) + push to local registry | 2h | 2.3 |
| 2.5 | Update `templates/wordpress/base/compose.yaml.j2` + `compose-coolify.yaml.j2` — use `fabrik/wp-golden:v1` image | 1h | 2.4 |
| 2.6 | Update `src/fabrik/wordpress/deployer.py` — detect golden base (image tag), run first-boot if not initialized, skip theme install stage | 2h | 2.5 |
| 2.7 | Update `src/fabrik/wordpress/stages/plugins.py` + `manifests/plugins.py` — split BASE (skip) vs LAUNCH additions (install from local zips) | 2h | 2.6 |
| 2.8 | Update `src/fabrik/wordpress/stages/theme.py` — remove install logic, keep brand Customizer application only | 1h | 2.6 |
| 2.9 | Update `src/fabrik/wordpress/stages/seo.py` — split base RankMath config (golden) vs per-site (verification codes, homepage meta) | 1h | 2.6 |
| 2.10 | Create `fabrik wp create <domain> --preset <p>` wrapper — chains: scaffold + plan + apply in one command | 2h | 2.6 |
| 2.11 | Test: `fabrik wp create testsite.com --preset company` → live in <90 seconds | 2h | 2.10 |
| 2.12 | Add `fabrik wp preview <site>` (temp subdomain `preview-<hash>.vps1.ocoron.com`, auto-delete 7d) + `fabrik wp promote <site>` (move to real domain, register search engines) | 4h | 2.11 |

**Result:** New sites in ~90 seconds via CLI. Preview before burning DNS resources.

**Effort:** ~25 hours / 3 days

---

## Phase 3 — API Bridge (enable GUI and remote control)

| # | What | Effort | Depends on |
|---|---|---|---|
| 3.1 | `fabrik scaffold fabrik-api --type python-api` | 30min | Phase 2 |
| 3.2 | Implement core endpoints: `GET /health`, `GET /api/v1/sites`, `POST /api/v1/sites` (JSON → site.yaml → plan → apply) | 6h | 3.1 |
| 3.3 | Implement deploy endpoints: `POST /sites/{id}/deploy`, `GET /sites/{id}/stream/{task}` (SSE progress) | 4h | 3.2 |
| 3.4 | Implement operations endpoints: `/sites/{id}/content/publish`, `/cache/flush`, `/verify`, `/status` | 3h | 3.2 |
| 3.5 | Implement brand endpoint: `POST /api/v1/brand/generate` (calls brand-identity-creator) | 2h | 3.2 |
| 3.6 | Implement domain endpoints: `/domain/check`, `/domain/buy`, `/domain/provision` (wraps dns.py) | 2h | 3.2 |
| 3.7 | Bearer token auth (`FABRIK_API_TOKEN`), bind `127.0.0.1:8050` only, crash on missing token | 1h | 3.2 |
| 3.8 | Deploy as systemd service on VPS | 1h | 3.7 |
| 3.9 | Expose as MCP server (Claude/Windsurf/Traycer call `create_site`, `publish_content`, `check_health` directly) | 2h | 3.8 |

**Result:** All fabrik operations accessible via authenticated HTTP API + MCP from anywhere.

**Effort:** ~22 hours / 3 days

---

## Phase 4 — GUI (visual management)

| # | What | Effort | Depends on |
|---|---|---|---|
| 4.1 | `fabrik scaffold fabrik-control-panel --type saas-skeleton` | 30min | Phase 3 |
| 4.2 | Creation wizard Screen 1: preset picker (5 cards: company/saas/content/landing/ecommerce with descriptions) | 3h | 4.1 |
| 4.3 | Creation wizard Screen 2: domain (availability check via fabrik-api, buy/provision flow) | 3h | 4.2 + 3.6 |
| 4.4 | Creation wizard Screen 3: brand (manual OR AI-generate via brand-identity-creator, live preview) | 4h | 4.3 + 3.5 |
| 4.5 | Creation wizard Screen 4: content (services/features/products per preset, bilingual en+tr fields) | 3h | 4.4 |
| 4.6 | Creation wizard Screen 5: integrations (GA4, GTM, email, social, GSC/Bing checkboxes) | 2h | 4.5 |
| 4.7 | Creation wizard Screen 6: review + deploy button (SSE stage progress) | 3h | 4.6 + 3.3 |
| 4.8 | Operations dashboard: all sites list with health (Gatus), content stats, SEO rankings | 8h | 4.1 + 3.4 |
| 4.9 | Per-site view: health, content pipeline status, keyword rankings (GSC), actions (publish/flush/verify/redeploy) | 6h | 4.8 |
| 4.10 | Watchdog AI status per site (when Phase 5 ready): last action, next planned, issues | 2h | 4.9 |
| 4.11 | Deploy to Coolify (Authelia-protected admin dashboard, `is_admin_dashboard: true`) | 2h | 4.10 |

**Result:** Full visual control over the WordPress factory.

**Effort:** ~37 hours / 5 days

---

## Phase 5 — Watchdog AI (autonomous management, 3 tiers)

Built incrementally. Each tier validated before enabling next.

### Tier 1 — Cron Automation (no LLM, $0/month)

| # | What | Effort | Depends on |
|---|---|---|---|
| 5.1 | Create `src/fabrik/watchdog/` package + `runner.py` skeleton + per-site config format (`configs/watchdog/<site>.yaml`) | 2h | Phase 1 (sites running) |
| 5.2 | Wire existing code into `fabrik watchdog run --daily`: health check (Gatus API), content publish, sitemap resubmit, daily Telegram report | 4h | 5.1 |
| 5.3 | Link scanner: crawl sitemap URLs, detect 404s, auto-create redirects via RankMath/WP-CLI | 3h | 5.2 |
| 5.4 | Plugin update checker: `wp plugin list --update=available`, auto-apply minor updates (stage → test → apply via WP Staging Pro) | 3h | 5.2 |
| 5.5 | Reporter: daily Telegram template (articles published, health, 404s fixed, updates applied) | 2h | 5.2 |
| 5.6 | Set up VPS cron for Tier 1 (daily at 03:00, DB clean weekly Sun 02:00) | 30min | 5.5 |
| 5.7 | **Validate: 7 days hands-off Tier 1 on ocoron.com** — content publishes, reports arrive, no breakage | ongoing | 5.6 |

**Result:** Sites auto-publish content, fix broken links, update plugins, report daily. Zero LLM cost.

**Effort:** ~15 hours / 2 days + 7-day validation

### Tier 2 — Bounded LLM Decisions (~$1-3/site/month)

| # | What | Effort | Depends on |
|---|---|---|---|
| 5.8 | GSC API integration: `src/fabrik/watchdog/gsc_client.py` — OAuth setup, query analytics pull, weekly snapshots to `data/watchdog/<site>/gsc/` | 8h | 5.7 passes |
| 5.9 | Analyzer: `src/fabrik/watchdog/analyzer.py` — trend detection (this week vs last week vs 4-week avg), keyword gap identification | 4h | 5.8 |
| 5.10 | Calendar integration: query calendar-orchestration-engine API for upcoming events matching site keywords/sector | 2h | 5.9 |
| 5.11 | LLM decision wrappers: `src/fabrik/watchdog/decisions.py` — keyword suggestions, content refresh picks, plugin safety check, weekly content plan (GSC data + calendar events as input) | 4h | 5.10 |
| 5.12 | Budget enforcement: max 10 LLM calls/site/week, hard cap, cost logging | 1h | 5.11 |
| 5.13 | Weekly cycle: `fabrik watchdog run --weekly` (Monday: GSC pull → analyze → plan next week → Telegram summary) | 2h | 5.12 |
| 5.14 | **Validate: 4 weeks Tier 2 on ocoron.com** — keyword suggestions make sense, content plan aligns with events, budget respected | ongoing | 5.13 |

**Result:** Content planning driven by data (GSC rankings) + events (calendar), not guesswork.

**Effort:** ~21 hours / 3 days + 4-week validation

### Tier 3 — Strategic Agent (monthly, ~$3-5/site/month)

| # | What | Effort | Depends on |
|---|---|---|---|
| 5.15 | Strategy module: `src/fabrik/watchdog/strategy.py` — monthly review prompt (full month GSC + content performance → strategy doc) | 6h | 5.14 passes |
| 5.16 | Competitor config: per-site competitor domains in watchdog config, web-scraper integration | 4h | 5.15 |
| 5.17 | Content quality audit: reads 5 lowest-performing articles → suggest refresh/merge/delete/redirect | 3h | 5.15 |
| 5.18 | Event triggers: traffic drop >20%, GlitchTip error spike, GSC manual action → immediate analysis + Telegram escalation | 3h | 5.15 |
| 5.19 | Safety rules: never modify production code, plugin major updates staged + reported not applied, strategy changes reported not applied, $10/site/month hard cap | 2h | 5.18 |
| 5.20 | Monthly cycle: `fabrik watchdog run --monthly` (1st of month: full audit + competitor gap + strategy + Telegram report) | 2h | 5.19 |

**Result:** Each site has an autonomous strategist. Human reviews monthly reports, approves major changes.

**Effort:** ~20 hours / 3 days

---

## Phase 6 — Scaling & SaaS (when portfolio outgrows VPS1)

**Trigger:** Start when VPS1 hits 80% RAM or when you want to sell the service.

| # | What | Effort | Depends on |
|---|---|---|---|
| 6.1 | Create `data/vps-pool.yaml` registry with capacity tracking (RAM, CPU, site count per VPS) | 2h | Phase 5 running |
| 6.2 | Add `--vps` parameter to `fabrik apply` + `fabrik wp create` (site-to-VPS routing) | 4h | 6.1 |
| 6.3 | Cross-VPS Grafana dashboard (single pane for all nodes) | 4h | 6.2 |
| 6.4 | Add `owner_id` to site registry + fabrik-api endpoints (tenant-aware) | 2h | Phase 3 |
| 6.5 | Multi-user auth layer for GUI (customer login, per-user site filtering) | 8h | 6.4 + Phase 4 |
| 6.6 | Billing integration (Paddle/Stripe → site quota per customer) | 12h | 6.5 |

**Result:** Factory serves multiple VPS nodes + optionally multiple customers (SaaS mode).

**Effort:** ~32 hours / 4 days

---

## Total Estimated Effort

| Phase | Hours | Calendar | Cumulative |
|---|---|---|---|
| Phase 0 (Decisions) | 1h (meeting) | 1 hour | 1h |
| Phase 1 (Foundation) | ~8h | 1 day | 9h |
| Phase 2 (Golden Base) | ~25h | 3 days | 32h |
| Phase 3 (API Bridge) | ~22h | 3 days | 54h |
| Phase 4 (GUI) | ~37h | 5 days | 91h |
| Phase 5 (Watchdog) | ~56h | 8 days + validation | 147h |
| Phase 6 (Scaling) | ~32h | 4 days | 179h |
| **Total** | **~181 hours** | **~25 focused days** | |

Note: Phases 5-6 can start in parallel with Phase 4 (Tier 1 watchdog doesn't need GUI).

## What You Get at Each Phase

| After Phase | What works |
|---|---|
| 0 | Decisions locked. Ready to build. |
| 1 | ocoron.com live, content flowing daily, SEO briefs generating |
| 2 | New sites in <90 seconds via CLI. Preview before deploy. `fabrik wp create` one-command. |
| 3 | Remote control from any device via API + MCP. Traycer/Claude can create sites directly. |
| 4 | Visual factory — pick preset, fill form, click deploy. Dashboard for all sites. |
| 5 (Tier 1) | Sites auto-publish, fix links, update plugins, report daily. $0/month. |
| 5 (Tier 2) | Content driven by GSC data + calendar events. Smart keyword targeting. ~$1-3/site/month. |
| 5 (Tier 3) | Monthly strategy reviews, competitor analysis, autonomous management. ~$3-5/site/month. |
| 6 | Multi-VPS scaling. Optionally: SaaS (customers pay per site). |
