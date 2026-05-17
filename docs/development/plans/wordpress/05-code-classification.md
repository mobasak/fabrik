# Code Classification — Use, Modify, or Archive

**Principle:** Existing code serves the vision or gets archived. Nothing is sacred. 9,700 LoC and hundreds of hours of work only matter if they make the factory faster, leaner, or more autonomous.

---

## Classification Key

- **✅ USE** — fits the vision as-is
- **🔧 MODIFY** — concept right, needs changes for golden base / GUI / watchdog
- **🆕 CREATE** — new file needed
- **📦 ARCHIVE** — doesn't serve the vision, keep in git history
- **❓ TBD** — validate during Phase 1 (deploy ocoron.com)

---

## WordPress Engine (`src/fabrik/wordpress/`)

| File | Class | Phase | What changes |
|---|---|---|---|
| `__init__.py` | ✅ USE | — | — |
| `spec_loader.py` | 🔧 MODIFY | 2 | Remove v2 file preference (specs consolidated). Support golden base context. |
| `spec_validator.py` | ✅ USE | — | — |
| `preset_loader.py` | ✅ USE | — | Preset merge is core to factory |
| `resolved_spec.py` | ✅ USE | — | — |
| `planner.py` | 🔧 MODIFY | 2.6 | Golden base detection → stages 3-4 skip logic in hash computation |
| `deployer.py` | 🔧 MODIFY | 2.6, 3.3 | (1) Golden base detection → run first-boot if not initialized, skip theme install. (2) SSE event emission for GUI streaming (Phase 3). |
| `handoff.py` | ❓ TBD | 1.4 | Useful for client handoff? Or watchdog replaces it? Validate on ocoron.com deploy. |
| `domain_setup.py` | 🔧 MODIFY | 2 | Pre-deploy DNS (Phase 1 provision) vs stage-1 DNS sync (verification only). May need splitting. |
| `settings.py` | ✅ USE | — | Per-site always (blogname, email, timezone) |
| `theme.py` | 🔧 MODIFY | 2.8 | Remove install logic. Keep Customizer brand application only (colors, fonts from site.yaml). |
| `pages.py` | ✅ USE | — | REST API page creation always per-site |
| `page_generator.py` | ✅ USE | — | Entity → page generation is core factory |
| `section_renderer.py` | 🔧 MODIFY | ongoing | 10 section types work. Add new types as needed. Keep extensible. |
| `menus.py` | ✅ USE | — | Per-site menus |
| `forms.py` | ✅ USE | — | Per-site forms |
| `seo.py` | 🔧 MODIFY | 2.9 | Split: base RankMath config (baked into golden) vs per-site (verification codes, homepage meta, schema type) |
| `analytics.py` | ✅ USE | — | GA4/GTM IDs always per-site |
| `legal.py` | ✅ USE | — | Privacy/terms per jurisdiction — valuable |
| `media.py` | ✅ USE | — | Brand asset upload per-site |
| `content.py` | ❓ TBD | 1.4 | Uses Claude API directly. Overlaps with TCO service. Test: do presets provide enough template content without AI generation at deploy time? |
| `cache.py` | ✅ USE | — | 4-layer flush needed for every site |

## Stages (`src/fabrik/wordpress/stages/`)

| File | Class | Phase | What changes |
|---|---|---|---|
| `__init__.py` | ✅ USE | — | Registry + StageResult + time_stage |
| `dns.py` | 🔧 MODIFY | 2 | With golden base: DNS already provisioned. Stage becomes VERIFICATION (confirm records exist), not creation. |
| `settings.py` | ✅ USE | — | Always per-site |
| `theme.py` | 🔧 MODIFY | 2.8 | Theme pre-installed in golden base. Stage: apply brand customizations ONLY. Skip if no brand changes. |
| `plugins.py` | 🔧 MODIFY | 2.7 | Golden base has BASE plugins. Stage: install LAUNCH tier ADDITIONS only from local zips. Skip if no additions. |
| `languages.py` | ✅ USE | — | Per-site locale config (depends on 0.1 WPML/Polylang decision) |
| `pages.py` | ✅ USE | — | Always per-site |
| `menus.py` | ✅ USE | — | Always per-site |
| `forms.py` | ✅ USE | — | Always per-site |
| `seo.py` | 🔧 MODIFY | 2.9 | Base RankMath in golden. Stage: per-site verification codes, homepage meta, schema type only. |
| `post_deploy.py` | ✅ USE | — | Sitemap resubmit + GA4 retrieval always needed |
| `analytics.py` | ✅ USE | — | Per-site GA4/GTM injection |
| `monitoring.py` | ✅ USE | — | Per-site Gatus + GlitchTip registration |
| `verify.py` | ✅ USE | — | 10 health checks always needed |

## Manifests (`src/fabrik/wordpress/manifests/`)

| File | Class | Phase | What changes |
|---|---|---|---|
| `__init__.py` | ✅ USE | — | — |
| `checks.py` | ✅ USE | — | — |
| `plugins.py` | 🔧 MODIFY | 2.7 | Split into: BASE (golden, skip at deploy), LAUNCH (install from local zips), GROWTH (activate later by watchdog), SCALE (activate by watchdog when traffic justifies). Depends on 0.2 tiering decision. |
| `menus.py` | ✅ USE | — | Per-preset menu definitions |
| `pages.py` | ✅ USE | — | Per-preset page definitions |

## Drivers (`src/fabrik/drivers/`)

| File | Class | Phase | What changes |
|---|---|---|---|
| `wordpress.py` | 🔧 MODIFY | 1.1 | Add `FABRIK_EXEC_MODE=local` gate (1-line in `_exec()` + `ContainerResolver.resolve()`). |
| `wordpress_api.py` | ✅ USE | — | REST API client always needed |
| `dns.py` | ✅ USE | — | Site-provisioner client (domain/GSC/Bing/IndexNow) |
| `seo.py` | ✅ USE | — | SEO service client (keyword jobs, briefs) |
| `tco.py` | ✅ USE | — | TCO client (AI content generation) |
| `image_broker.py` | ✅ USE | — | Image sourcing (Pexels/Pixabay) |
| `glitchtip.py` | ✅ USE | — | DSN injection per-site (wp-config-extra.php) |

## Orchestrators & Core (`src/fabrik/`)

| File | Class | Phase | What changes |
|---|---|---|---|
| `orchestrator/content_publisher.py` | ✅ USE | — | Content loop: SEO→TCO→Image→WP→publish. Used by watchdog Tier 1. |
| `orchestrator/deployer.py` | ✅ USE | — | Coolify deployment |
| `orchestrator/verifier.py` | ✅ USE | — | WP health checks |
| `orchestrator/infrastructure.py` | ✅ USE | — | Registrar dispatch for WP services |
| `content/orchestrator.py` | ✅ USE | — | Re-export of content_publisher |
| `deploy_router.py` | 🔧 MODIFY | 2.6 | Golden base awareness in routing (detect image tag, run first-boot) |
| `deploy_validator.py` | ✅ USE | — | Pre-deploy checks |
| `provisioner.py` | 🔧 MODIFY | 2.5 | WP container uses golden image but MariaDB is per-site compose. Update compose generation. |
| `notifications.py` | ✅ USE | — | Telegram via n8n (used by watchdog reporter) |
| `cli.py` | 🔧 MODIFY | 2.10, 5.1 | Add: `fabrik wp create` (Phase 2), `fabrik wp preview/promote` (Phase 2), `fabrik watchdog run` (Phase 5) |
| `preplan.py` | ❓ TBD | 4 | GUI wizard may replace preplan flow. Or preplan feeds wizard. Validate in Phase 4. |
| `scaffold.py` | 🔧 MODIFY | 2.5 | WordPress scaffold generates compose with golden base image instead of bare WP image |
| `spec_generator.py` | ✅ USE | — | Generates specs/services with shape block at scaffold time |
| `__init__.py` | ✅ USE | — | Re-exports |

## Templates (`templates/wordpress/`)

| Path | Class | Phase | What changes |
|---|---|---|---|
| `defaults.yaml` | 🔧 MODIFY | 2.1 | Split: base settings → golden image build config. Remaining = per-site overridable. |
| `presets/company.yaml` | ✅ USE | — | 8 profiles mapped to presets. Core factory feature. |
| `presets/saas.yaml` | ✅ USE | — | |
| `presets/content.yaml` | ✅ USE | — | |
| `presets/landing.yaml` | ✅ USE | — | |
| `presets/ecommerce.yaml` | ✅ USE | — | |
| `schema/v1.yaml` | 🔧 MODIFY | 2, 5 | New fields: golden base version, watchdog config reference, plugin tier |
| `schema/MERGE_RULES.md` | ✅ USE | — | |
| `schema/VALIDATION_RULES.md` | ✅ USE | — | |
| `base/compose.yaml.j2` | 🔧 MODIFY | 2.5 | Image: `fabrik/wp-golden:v1` instead of `wordpress:php8.3-fpm-bookworm` |
| `base/compose-coolify.yaml.j2` | 🔧 MODIFY | 2.5 | Same image change |
| `base/compose.dev.yaml.j2` | 🔧 MODIFY | 2 | Decide: golden for parity or fresh for debugging |
| `base/wp-config-extra.php` | 🔧 MODIFY | 2.2 | Moves INTO golden Dockerfile. Template becomes override for per-site additions. |
| `base/nginx/default.conf.j2` | 🔧 MODIFY | 2.2 | Base hardening baked into golden. Per-site: server_name, domain-specific cache rules. |
| `base/nginx-dev.conf.j2` | ✅ USE | — | Dev config unchanged |
| `base/php-fpm/zz-fabrik-listen.conf` | ✅ USE | — | Baked into golden image |
| `base/backup/backup.sh` | ✅ USE | — | Per-site backup script |
| `base/Makefile.j2` | ✅ USE | — | Operational tooling per-site |
| `base/site.yaml.j2` | ✅ USE | — | Scaffold template |
| `base/.env.j2` | ✅ USE | — | Per-site env template |
| `plugins/premium/*.zip` | ✅ USE | 2.2 | Bundled into golden image at build time |
| `plugins/premium/wp_plugins_activation_notes.md` | ✅ USE | 2.3 | License keys consumed by first-boot script |
| `plugins/premium/README.md` | ✅ USE | — | Licensing notes |
| `plugins_latest.json` | 🔧 MODIFY | 2.4 | Becomes golden base version manifest. Update triggers image rebuild. |
| `themes/premium/README.md` | ✅ USE | — | |
| `scaffold/docker/Makefile.wordpress` | ✅ USE | — | |
| `AGENTS.md` | ✅ USE | — | WP-specific agent contract |
| `README.md` | ✅ USE | — | |

## Specs

| Path | Class | Phase | What changes |
|---|---|---|---|
| `specs/sites/ocoron.com.yaml` | 🔧 MODIFY | 1.2 | WPML→Polylang, fill DRAFT fields, status→READY |
| `specs/sites/ocoron.com-content-plan.md` | 🔧 MODIFY | 1 | Update: Image Broker + TCO are BUILT (not "FUTURE") |
| `specs/sites/ocoron.com-media/` | ✅ USE | — | Brand assets ready |
| `specs/sites/archived-ocoron.com.v1.*` | 📦 ARCHIVE | — | Already archived |
| `specs/services/seo.yaml` | ✅ USE | — | SEO microservice spec (port 8016) |

## Documentation

| Path | Class | Phase | What changes |
|---|---|---|---|
| `docs/workflows/wordpress-site-workflow.md` | 🔧 MODIFY | 2 | Rewrite for golden base + `fabrik wp create` flow |
| `docs/reference/wordpress/architecture.md` | 🔧 MODIFY | 2 | Add golden base layer to architecture |
| `docs/reference/wordpress/deployment-workflow.md` | 🔧 MODIFY | 1.3 | Fix Apache→FPM. Update for golden base. |
| `docs/reference/wordpress/site-specification.md` | ✅ USE | — | site.yaml format stays |
| `docs/reference/wordpress/pages-idempotency.md` | ✅ USE | — | |
| `docs/reference/wordpress/plugin-stack.md` | 🔧 MODIFY | 2.1 | Add tiering columns: BASE / LAUNCH / GROWTH / SCALE per plugin |
| `docs/reference/wordpress/plugin-evaluation.md` | ✅ USE | — | Research still valid |
| `docs/reference/wordpress/fixes.md` | ✅ USE | — | Known issues reference |
| `docs/architecture/WORDPRESS-MODULE-INTEGRATION.md` | 🔧 MODIFY | 3 | Add fabrik-api + golden base |
| `.windsurf/rules/62-wordpress.md` | ✅ USE | — | Rules ARE the golden base spec |
| `docs/reference/wordpress/archived-*.md` | 📦 ARCHIVE | — | Best practices extracted into golden base + rule pack |
| `docs/development/plans/2026-05-17-wordpress-blazing-fast.md` | 📦 ARCHIVE | — | Superseded by this plan folder |
| `docs/development/wordpress-files-index.md` | 🔧 MODIFY | ongoing | Keep current as files change |

## Scripts

| Path | Class | Phase | What changes |
|---|---|---|---|
| `scripts/create_wp_container.py` | ❓ TBD | 2 | May be replaced by golden base build script |
| `scripts/audit_authelia_gates.py` | ✅ USE | — | WP admin Authelia verification |
| `scripts/audit_all_projects.py` | ✅ USE | — | Includes WP sites |
| `scripts/sync_projects.py` | ✅ USE | — | WP project registration |

## Tests

| Path | Class | Phase | What changes |
|---|---|---|---|
| `tests/wordpress/` (20 files) | 🔧 MODIFY | 2 | Tests for "install from scratch" → "additions only". Golden base skip tests needed. |
| `tests/wordpress/stages/test_plugins.py` | 🔧 MODIFY | 2.7 | Largest stage test. Must verify: BASE skipped, LAUNCH additions installed. |
| `tests/wordpress/stages/test_verify.py` | ✅ USE | — | 1,009 LoC — verification unchanged |
| `tests/test_scaffold_wordpress_templates.py` | 🔧 MODIFY | 2.5 | Scaffold generates golden-base compose. Tests must verify image tag. |
| `tests/test_wp_spec_resolution.py` | ✅ USE | — | Spec resolution unchanged |
| `tests/test_wordpress_pages.py` | ✅ USE | — | Pages unchanged |
| `tests/test_cli_wp_verify.py` | ✅ USE | — | CLI verify unchanged |
| `tests/content/test_orchestrator.py` | ✅ USE | — | Content publisher unchanged |

## Data & Config

| Path | Class | Phase | What changes |
|---|---|---|---|
| `data/projects.yaml` | 🔧 MODIFY | 6.4 | Add `owner_id` field for SaaS readiness |

## External Projects (integration points)

| Project | Class | Phase | Role in factory |
|---|---|---|---|
| `/opt/calendar-orchestration-engine/` | ✅ USE | 5.10 | 15k+ events database → proactive content planning for watchdog Tier 2 |
| `/opt/brand-identity-creator/` (when deployed) | ✅ USE | 3.5 | AI brand generation → GUI wizard Screen 3 |
| `/opt/marketing-argument-generator/` (when deployed) | ✅ USE | future | Marketing copy → page section content |
| `/opt/job-agent/` (when deployed) | ❓ TBD | 5 | Possible watchdog execution engine. Or watchdog is standalone. Validate. |
| `/opt/web-scraper/` (when deployed) | ✅ USE | 5.16 | Competitor scraping → watchdog Tier 3 gap analysis |

---

## Files to CREATE (new)

| Path | Phase | Purpose |
|---|---|---|
| `templates/wordpress/golden/Dockerfile` | 2.2 | Golden base image recipe |
| `templates/wordpress/golden/first-boot.sh` | 2.3 | One-time plugin activation + base config |
| `templates/wordpress/golden/mu-plugins/` | 2.2 | Security MU-plugins (REST block, footprint removal, enumeration block) |
| `templates/wordpress/golden/object-cache.php` | 2.2 | Redis drop-in with env-based host/prefix |
| `scripts/build_golden_base.sh` | 2.4 | Build + tag + test + push golden image |
| `src/fabrik/watchdog/__init__.py` | 5.1 | Watchdog package |
| `src/fabrik/watchdog/runner.py` | 5.1 | Main loop: schedule → decide → act → report |
| `src/fabrik/watchdog/gsc_client.py` | 5.8 | GSC API data pull + weekly snapshots |
| `src/fabrik/watchdog/analyzer.py` | 5.9 | Trend detection from GSC data |
| `src/fabrik/watchdog/link_scanner.py` | 5.3 | Broken link crawl + auto-redirect |
| `src/fabrik/watchdog/decisions.py` | 5.11 | Tier 2 LLM wrappers (keywords, refresh, plugin safety) |
| `src/fabrik/watchdog/strategy.py` | 5.15 | Tier 3 monthly strategy review |
| `src/fabrik/watchdog/reporter.py` | 5.5 | Telegram report templates (daily/weekly/monthly) |
| `configs/watchdog/<site>.yaml` | 5.1 | Per-site watchdog config (tiers, keywords, competitors, budget) |
| `/opt/fabrik-api/` | 3.1 | FastAPI bridge (new project, scaffold python-api) |
| `/opt/fabrik-control-panel/` | 4.1 | Next.js GUI (new project, scaffold saas-skeleton) |

---

## Summary

### Existing code

| Classification | Count | % |
|---|---|---|
| ✅ USE as-is | ~48 | 57% |
| 🔧 MODIFY | ~30 | 36% |
| 📦 ARCHIVE | 3 | 3.5% |
| ❓ TBD | 3 | 3.5% |

### New code to create

| Area | Files |
|---|---|
| Golden base (Phase 2) | 5 (Dockerfile, first-boot, mu-plugins, object-cache, build script) |
| Watchdog (Phase 5) | 8 (runner, gsc_client, analyzer, link_scanner, decisions, strategy, reporter, per-site config) |
| API + GUI (Phase 3-4) | 2 projects (fabrik-api, fabrik-control-panel — each scaffolded as full project) |
| **Total new** | **~16 files + 2 new projects** |

**93% of existing work preserved** (USE + MODIFY). Modifications are surgical — mostly "skip when golden base" or "split base vs per-site." 16 new files implement the three pillars (golden base, API/GUI, watchdog). Only 3 files archived (already done or superseded).

Every MODIFY and CREATE entry maps to a specific ticket in `04-execution-order.md`.
