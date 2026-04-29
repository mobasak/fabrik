# Fabrik Phase Gap Analysis

**Date:** 2026-04-06
**Author:** Gap analysis based on phase verification reports (2026-02-27) with VPS state corrections (2026-04-06)
**Purpose:** Determine actual completion vs. claimed completion for all Fabrik phases, identify remaining work, flag obsolete items, and surface quick wins.

**VPS Architecture:** x86_64 (amd64) — AMD EPYC-Genoa, 6 vCPU, 12 GB RAM, Ubuntu 24.04. All Docker images must target `linux/amd64`. Base images: `python:<stable>-slim-bookworm` / `node:<LTS>-bookworm-slim`. Never Alpine.

---

## 1. Executive Summary

### Phase Completion Table

| Phase | Name | Claimed | Verified (2026-02-27) | Adjusted (2026-04-06) | Delta | Notes |
|-------|------|---------|----------------------|----------------------|-------|-------|
| 1 | Foundation Infrastructure | ~83% | ~83% | ~83% | 0 | Archived. Core infra operational. |
| 2 | WordPress Automation | 67% (8/12) | 83% (10/12) | **~85-90%** | +18-23% | Preset loader was undercounted. ocoron.com compromised (needs fresh deploy). Templates migrated to FPM+Nginx (T5). |
| 3 | AI Content Integration | 0% (0/6) | 33% (2/6) | **~50%** | +50% | T1 completed: LLMClient wrapper replaces direct Anthropic. Content + legal generators + SEO applicator exist. |
| 4 | DNS Migration + Networking | 75% (6/8) | 75% (6/8) | **~80%** | +5% | T2 completed: DNS provisioning wired into orchestrator. WAF/cache still deferred. |
| 5 | Staging + Multi-Environment | 0% (0/7) | 0% (0/7) | **0%** | 0 | Entirely unimplemented. |
| 6 | Advanced Monitoring | 13% (2/15) | 20% (3/15) | **~20%** | +7% | Uptime Kuma + verify + Coolify logs. Full stack (Loki/Prometheus/Grafana) not deployed. |
| 7 | Multi-Server Scaling | 0% (0/9) | 0% (0/9) | **0%** | 0 | Not needed until VPS1 saturated. |
| 8 | Business Automation (n8n) | 0% (0/10) | 0% (0/10) | **0%** | 0 | Entirely unimplemented. |
| 9 | Docker Image Acceleration | ~100% claimed | ~50% | **~55%** | -45% | Tooling 100%, service deployments 0%, 2 Alpine Dockerfiles remain. |
| 10 | Deployment Orchestrator | 100% | 100% | **100%** | 0 | Fully implemented. T2 filled the DNS provisioning TODO. |

### Overall Assessment

**Weighted completion across all phases: ~47%** (up from ~37% at original verification).

Key corrections since 2026-02-27:
- **T1 (2026-04-06):** Unified `LLMClient` wrapper created in `src/fabrik/ai/client.py`. WordPress `content.py` and `legal.py` migrated from direct Anthropic to `LLMClient`. Phase 3 Step 1 now complete.
- **T2 (2026-04-06):** DNS provisioning wired into `DeploymentOrchestrator._provision_dns()` with DNSClient + Cloudflare fallback. Phase 10 DNS TODO resolved.
- **T5 (2026-04-06):** WordPress templates migrated from Apache to FPM+Nginx+Redis per `62-wordpress.md`. Nginx config created. WPML replaced with Polylang.
- **Duplicati (2026-04-06):** Backup system fixed after 3 months of silent failure. Full VPS backup to Backblaze B2 now operational (16,419 files / 3.7 GiB).
- **ocoron.com (2026-04-06):** Compromised via XML-RPC brute force. Container stopped and removed. Needs fresh install with hardened templates.
- **Newly confirmed running services:** file-worker, email-reader, redis-main, wp-test (were running but not previously documented).

---

## 2. STILL NEEDED

Items organized as ticket-ready descriptions, grouped by priority.

### Priority: HIGH — Blocking business value or security

#### SN-1: Deploy ocoron.com with hardened WordPress stack
- **Phase:** 2 (Step 12)
- **What:** Fresh WordPress deployment using the new FPM+Nginx+Redis templates (T5). Must include Wordfence, xmlrpc blocking, rate limiting, strong admin credentials (32-char CSPRNG).
- **Why:** ocoron.com was compromised via XML-RPC brute force. Previous container removed. Company website is offline.
- **Effort:** 2-4 hours
- **Dependencies:** T5 (complete), `specs/sites/ocoron.com.yaml` (exists)
- **Acceptance:** `curl -I https://ocoron.com` returns 200, Wordfence active, xmlrpc returns 444 via nginx.

#### SN-2: Content revision system
- **Phase:** 3 (Step 3)
- **What:** `ContentReviser` class for AI-powered content iteration. Takes existing page HTML + revision instructions, returns updated content via `LLMClient`.
- **Effort:** 2 hours
- **Dependencies:** T1 (complete — LLMClient exists)

#### SN-3: CLI AI commands (`fabrik ai generate-page`, etc.)
- **Phase:** 3 (Step 6)
- **What:** Add `fabrik ai` command group with subcommands: `generate-page`, `generate-post`, `revise-page`, `generate-legal`. Wire to existing `ContentGenerator`, `LegalContentGenerator`, and new `ContentReviser`.
- **Effort:** 4 hours
- **Dependencies:** SN-2

#### SN-4: Bulk content generation tools
- **Phase:** 3 (Step 4)
- **What:** `BulkGenerator` that processes a site manifest (list of pages with titles, sections, brand context) and generates all pages in sequence via `LLMClient`. Outputs HTML files ready for WordPress REST API upload.
- **Effort:** 4 hours
- **Dependencies:** SN-2, SN-3

### Priority: MEDIUM — Operational improvements

#### SN-5: CLI DNS commands
- **Phase:** 4
- **What:** Add `fabrik dns` command group: `zones`, `records`, `add`, `delete`. Wire to existing `DNSClient` and `CloudflareClient` drivers.
- **Effort:** 2 hours
- **Dependencies:** None (drivers exist)

#### SN-6: WordPress template compliance — FPM+Nginx migration
- **Phase:** 2
- **Status:** ✅ **COMPLETED by T5 (2026-04-06)**. Both `compose.yaml.j2` and `compose-coolify.yaml.j2` migrated to `wordpress:php8.3-fpm-bookworm` + `nginx:mainline-bookworm-slim` + `redis:7-bookworm`. Nginx config created with FastCGI cache, xmlrpc block, gzip. WPML replaced with Polylang.

#### SN-7: Fix remaining Alpine Dockerfiles
- **Phase:** 9
- **What:** Change `templates/scaffold/docker/Dockerfile.node` and `templates/file-api/Dockerfile.j2` from `node:20-alpine` to `node:22-bookworm-slim`.
- **Effort:** 15 minutes
- **Dependencies:** None

#### SN-8: SSL expiry check enhancement
- **Phase:** 6
- **What:** Add `min_days_remaining` parameter to `PostconditionChecker.run_check_ssl_valid()`. Fail if cert expires within N days (default 14).
- **Effort:** 1 hour
- **Dependencies:** None (`src/fabrik/verify.py` exists)

#### SN-9: Coolify status integration in verifier
- **Phase:** 6
- **What:** Add `run_check_coolify_status()` to `PostconditionChecker`. Query Coolify API for deployment health status.
- **Effort:** 2 hours
- **Dependencies:** None (Coolify driver exists)

#### SN-10: Deploy Cloudflare WAF rules for WordPress
- **Phase:** 4 (Step 4), Phase 2 (Step 9)
- **What:** Configure Cloudflare WAF managed rules for WordPress. Create `CloudflareWAF` module or document manual dashboard configuration.
- **Effort:** 1-2 hours
- **Dependencies:** SN-1 (deploy ocoron.com first, then apply WAF)

### Priority: LOW — Future scaling, not currently blocking

#### SN-11: Staging environment system (entire Phase 5)
- **Phase:** 5 (all 7 steps)
- **What:** `EnvironmentManager`, `DatabaseManager` (clone), `StagingManager`, CLI `staging:create/sync/promote/destroy`. WordPress URL replacement via WP-CLI.
- **Effort:** 13 hours
- **When:** When client review workflow is needed. Not blocking for current solo-dev operations.

#### SN-12: Full monitoring stack (Phase 6 remainder)
- **Phase:** 6 (Steps 2-8)
- **What:** Deploy Loki + Promtail + Prometheus + Grafana. Create dashboards. Configure alerting.
- **Effort:** 15 hours
- **When:** Config files exist in `specs/infrastructure/`. Deploy when centralized log search or metrics dashboards are needed. Current Uptime Kuma + Netdata covers basics.

#### SN-13: Multi-server scaling (entire Phase 7)
- **Phase:** 7 (all 9 steps)
- **What:** Second VPS, WireGuard VPN, server registry, `DeploymentRouter`, shared PostgreSQL via PgBouncer.
- **Effort:** 11 hours + ~$20-40/mo VPS cost
- **When:** VPS1 memory >70%, CPU >60%, or disk >80% sustained. Current 12 GB RAM is sufficient.

#### SN-14: n8n business automation (entire Phase 8)
- **Phase:** 8 (all 10 steps)
- **What:** Deploy n8n, create workflows (lead capture, uptime alerts, daily reports, client onboarding, backup notifications, AI content review). CLI `fabrik automation` commands.
- **Effort:** 14 hours
- **When:** When automation ROI justifies the setup. Currently manual workflows suffice.
- **Dependencies:** Phase 6 (for daily reports), Phase 3 (for content review)

#### SN-15: Deploy shared infrastructure services (Phase 9 remainder)
- **Phase:** 9
- **What:** Deploy Apprise (notifications), MinIO (object storage), MeiliSearch (search), Gotenberg (PDF), Browserless (headless browser). All config-ready in `specs/infrastructure/`.
- **Effort:** 4-8 hours
- **When:** Deploy individually as projects need them.

---

## 3. OBSOLETE

Items from the original phase plans that should be dropped or have been superseded.

| ID | Original Item | Phase | Reasoning |
|----|---------------|-------|-----------|
| OB-1 | Custom flavor themes (flavor-starter, flavor-corporate) | 2, Step 11 | **Superseded.** GeneratePress + GP Premium plugin workflow achieves the same goal without maintaining custom child themes. Presets handle site-type differentiation. |
| OB-2 | Windsurf agent integration (`windsurf/agent_context.md`, `windsurf/rules.yaml`) | 3, Step 6 | **Superseded.** Windsurf agent rules are now managed via `.windsurf/rules/*.md` and `.windsurfrules`. The Phase 3 plan predated the current agent rule system. |
| OB-3 | `compiler/` directory structure for DNS modules | 4 | **Superseded.** Phase 4 planned `compiler/dns_cloudflare.py`, `compiler/cloudflare_settings.py`, etc. Actual implementation uses `src/fabrik/drivers/cloudflare.py` — cleaner architecture. |
| OB-4 | SendGrid email integration | 8 | **Superseded.** Fabrik microservices include Email Gateway (Resend + SES) at port 3000. No need for separate SendGrid setup. |
| OB-5 | pgAdmin deployment | 9 | **Low value.** PostgreSQL is managed via Coolify. Direct `psql` access available via SSH. pgAdmin adds resource overhead for minimal benefit in solo-dev context. |
| OB-6 | NocoDB / Directus deployment | 9 | **No current use case.** These were listed as "Month 2" services. No Fabrik project currently needs a headless CMS or visual DB frontend. Deploy only if a specific project requires it. |
| OB-7 | ARM64 architecture checks | 9 | **Not applicable.** VPS is x86_64 (amd64). The `container_images.py` tool has ARM64 checking capability, but it's not needed for current infrastructure. Retain tooling but don't prioritize ARM64 verification. |
| OB-8 | Multi-server Slack integration for alerts | 7, 8 | **Premature.** Solo developer with single VPS. Uptime Kuma provides uptime alerts. Netdata provides server metrics. Adding Slack integration for alerts is overhead without a team to notify. |

---

## 4. Quick Wins

Items that can be completed in under 2 hours each, deliver immediate value, and have no dependencies.

| # | Item | Effort | Value | Reference |
|---|------|--------|-------|-----------|
| QW-1 | Fix 2 Alpine Dockerfiles → bookworm-slim | 15 min | Compliance with base image rules, eliminates musl edge cases | SN-7 |
| QW-2 | Add SSL expiry check to `fabrik verify` | 1 hour | Catch expiring certs before outage | SN-8 |
| QW-3 | Add `fabrik dns` CLI commands | 2 hours | DNS operations without writing Python. Drivers already exist. | SN-5 |
| QW-4 | Add `WP_REDIS_HOST` to existing deployed WordPress sites | 30 min | Enable Redis object cache on any running WP site (if Redis sidecar added) | Already in templates via T5 |
| QW-5 | Deploy Apprise for unified notifications | 1 hour | Config exists in `specs/infrastructure/apprise.yaml`. Single `docker compose up`. All projects can send alerts to Slack/Email/Telegram via one API. | SN-15 (partial) |
| QW-6 | Coolify status check in verifier | 2 hours | `fabrik verify` can confirm Coolify deployment health, not just HTTP response | SN-9 |

### Recommended Quick Win Order

1. **QW-1** (15 min) — Pure compliance fix, zero risk
2. **QW-2** (1 hour) — Prevents cert-related outages
3. **QW-3** (2 hours) — Developer productivity
4. **QW-5** (1 hour) — Foundation for all future alerting
5. **QW-6** (2 hours) — Deployment verification improvement
6. **QW-4** (30 min) — Performance improvement for WordPress sites

**Total quick win effort: ~7 hours for all 6 items.**

---

## Appendix: VPS State Corrections (2026-04-06)

These corrections were discovered during live VPS verification on 2026-04-06 and are incorporated into the adjusted completion percentages above.

### Duplicati Backup — FIXED
- **Was:** Broken since 2026-01-04 (3 months of silent failure)
- **Root causes:** PUID mismatch, missing bind mount, encryption key mismatch
- **Fix:** PUID=0, added `/data/coolify` mount, fixed encryption key, fresh job DB
- **Now:** 16,419 files / 3.7 GiB → 1.72 GiB compressed to Backblaze B2 in 1m50s
- **Schedule:** Daily at 08:00 local (pre-backup script runs pg_dumpall at 07:45)

### ocoron.com — COMPROMISED, NEEDS FRESH DEPLOY
- **Was:** WordPress site running with default admin, no xmlrpc protection
- **Attack:** XML-RPC brute force on `admin` username
- **Action taken:** Container stopped and removed
- **Next:** SN-1 — fresh deploy with hardened FPM+Nginx templates, Wordfence, strong credentials

### Newly Confirmed Running Services
Previously undocumented but verified running on VPS:
- **file-worker** — Background file processing
- **email-reader** — Email ingestion service
- **redis-main** — Shared Redis instance (redis:7-alpine)
- **wp-test** — WordPress test site (wp-test.vps1.ocoron.com)

### WordPress Template Compliance (SN-6)
- **Was:** Apache-based 2-container pattern (WP-Apache + MariaDB)
- **Now:** FPM+Nginx 4-container pattern (WP-FPM + Nginx + MariaDB + Redis)
- **Changed by:** T5 (2026-04-06)
- **Files:** `compose.yaml.j2`, `compose-coolify.yaml.j2`, `nginx/default.conf.j2` (new), `wp-config-extra.php`, `defaults.yaml`
