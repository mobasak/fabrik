# Fabrik WordPress Development — Complete File Index

**Generated:** 2026-04-29 (rescan v2) | **Updated:** 2026-05-17 (added content automation pipeline §1.5-1.6, consolidated ocoron specs, archived legacy plans + SOP docs)
**Working directory:** `/opt/fabrik`
**Scope:** Every file in this repository that participates in the WordPress site lifecycle (spec → scaffold → deploy → content → verify → ongoing ops).

> Use this as the working ledger for the WordPress workstream. We will tick / annotate / refactor against this list.

---

## 1. Production Source Code

### 1.1 `src/fabrik/wordpress/` — WordPress engine package (22 modules, 6,921 LoC)

Core orchestration layer that turns a `site.yaml` + preset into a deployed, idempotent WordPress site.

| File | LoC | Role |
|------|----:|------|
| `@/opt/fabrik/src/fabrik/wordpress/__init__.py` | 145 | Public surface: `Planner`, `Deployer`, `ResolvedSpec`, stage registry exports |
| `@/opt/fabrik/src/fabrik/wordpress/spec_loader.py` | 362 | Parses `site.yaml`, applies inheritance / overrides, resolves preset chain |
| `@/opt/fabrik/src/fabrik/wordpress/spec_validator.py` | 257 | Schema validation against `templates/wordpress/schema/v1.yaml` + business rules |
| `@/opt/fabrik/src/fabrik/wordpress/preset_loader.py` | 325 | Loads `templates/wordpress/presets/{saas,company,content,landing,ecommerce}.yaml` and merges with user spec |
| `@/opt/fabrik/src/fabrik/wordpress/resolved_spec.py` | 122 | Frozen dataclass — final merged spec passed to deployer |
| `@/opt/fabrik/src/fabrik/wordpress/planner.py` | 234 | Builds an ordered stage plan from a `ResolvedSpec` (DAG of stages) |
| `@/opt/fabrik/src/fabrik/wordpress/deployer.py` | 465 | Executes the stage plan. Idempotent runner with rollback hooks |
| `@/opt/fabrik/src/fabrik/wordpress/handoff.py` | 147 | Transfers state from infrastructure-deploy phase (Fabrik core) to WP-specific stages |
| `@/opt/fabrik/src/fabrik/wordpress/domain_setup.py` | 484 | DNS + Cloudflare + Traefik labels for the WP site (calls `dns-manager` service) |
| `@/opt/fabrik/src/fabrik/wordpress/cache.py` | 172 | Object-cache (Redis) wiring + Cloudflare cache rules + .htaccess hardening |
| `@/opt/fabrik/src/fabrik/wordpress/content.py` | 256 | Content-import primitives (used by `pages.py`, `seo.py`) |
| `@/opt/fabrik/src/fabrik/wordpress/pages.py` | 620 | Pages/posts/CPT creation, slug resolution, parent linking |
| `@/opt/fabrik/src/fabrik/wordpress/page_generator.py` | 328 | Generates page bodies from preset blueprints + Gutenberg blocks |
| `@/opt/fabrik/src/fabrik/wordpress/section_renderer.py` | 508 | Renders Gutenberg block sections (hero, features, pricing, FAQ, CTA, etc.) |
| `@/opt/fabrik/src/fabrik/wordpress/menus.py` | 328 | Nav menus, locations, item ordering |
| `@/opt/fabrik/src/fabrik/wordpress/forms.py` | 353 | Fluent Forms / WPForms / Contact Form 7 provisioning |
| `@/opt/fabrik/src/fabrik/wordpress/seo.py` | 469 | Rank Math / Yoast settings, schema markup, sitemaps, redirects |
| `@/opt/fabrik/src/fabrik/wordpress/analytics.py` | 242 | GA4, GSC, GTM, Matomo wiring |
| `@/opt/fabrik/src/fabrik/wordpress/legal.py` | 337 | Privacy / Terms / Cookie / Impressum auto-generation per jurisdiction |
| `@/opt/fabrik/src/fabrik/wordpress/media.py` | 221 | Image-broker integration, thumbnail generation, alt-text |
| `@/opt/fabrik/src/fabrik/wordpress/settings.py` | 281 | `wp_options` writes (site identity, reading, discussion, permalinks, etc.) |
| `@/opt/fabrik/src/fabrik/wordpress/theme.py` | 265 | Theme install/activate, customizer settings, child-theme bootstrap |

### 1.2 `src/fabrik/wordpress/stages/` — Idempotent stage executors (14 modules, 1,654 LoC)

One file per pipeline stage. Each stage has `run(ctx)` + `verify(ctx)` + idempotency keys.

| File | LoC | Stage |
|------|----:|-------|
| `@/opt/fabrik/src/fabrik/wordpress/stages/__init__.py` | 38 | Stage registry / dispatch table |
| `@/opt/fabrik/src/fabrik/wordpress/stages/dns.py` | 91 | DNS records + Traefik labels |
| `@/opt/fabrik/src/fabrik/wordpress/stages/theme.py` | 54 | Theme install + activate |
| `@/opt/fabrik/src/fabrik/wordpress/stages/plugins.py` | 141 | Plugin install + activate (uses `manifests/plugins.py` + `templates/wordpress/plugins/`) |
| `@/opt/fabrik/src/fabrik/wordpress/stages/settings.py` | 195 | `wp_options` writes |
| `@/opt/fabrik/src/fabrik/wordpress/stages/languages.py` | 106 | WPML / Polylang configuration |
| `@/opt/fabrik/src/fabrik/wordpress/stages/menus.py` | 51 | Nav menus |
| `@/opt/fabrik/src/fabrik/wordpress/stages/pages.py` | 183 | Page creation |
| `@/opt/fabrik/src/fabrik/wordpress/stages/forms.py` | 71 | Forms |
| `@/opt/fabrik/src/fabrik/wordpress/stages/seo.py` | 79 | SEO plugin config |
| `@/opt/fabrik/src/fabrik/wordpress/stages/analytics.py` | 68 | Analytics wiring |
| `@/opt/fabrik/src/fabrik/wordpress/stages/monitoring.py` | 95 | Gatus endpoint registration + GlitchTip DSN injection |
| `@/opt/fabrik/src/fabrik/wordpress/stages/post_deploy.py` | 89 | Cache prime, sitemap submit, search-engine ping |
| `@/opt/fabrik/src/fabrik/wordpress/stages/verify.py` | 393 | End-to-end smoke tests (homepage 200, admin reachable, DB writable, plugins active) |

### 1.3 `src/fabrik/wordpress/manifests/` — Declarative manifests (5 modules, 382 LoC)

Static catalogs of "what plugins/menus/pages should exist" — consumed by stages.

| File | LoC | Role |
|------|----:|------|
| `@/opt/fabrik/src/fabrik/wordpress/manifests/__init__.py` | 40 | Manifest registry |
| `@/opt/fabrik/src/fabrik/wordpress/manifests/checks.py` | 69 | Validates a manifest against the resolved spec |
| `@/opt/fabrik/src/fabrik/wordpress/manifests/plugins.py` | 168 | Plugin manifest (slug → version → source → activation order) |
| `@/opt/fabrik/src/fabrik/wordpress/manifests/menus.py` | 52 | Default menu structures per preset |
| `@/opt/fabrik/src/fabrik/wordpress/manifests/pages.py` | 53 | Default page structures per preset |

### 1.4 `src/fabrik/drivers/` — WordPress driver layer (2 files, 717 LoC)

| File | LoC | Role |
|------|----:|------|
| `@/opt/fabrik/src/fabrik/drivers/wordpress.py` | 346 | High-level driver: container exec, WP-CLI wrapper, file mgmt |
| `@/opt/fabrik/src/fabrik/drivers/wordpress_api.py` | 371 | REST API client (auth via app passwords, retry, pagination) |

### 1.5 Content Automation Pipeline (Post-Deploy)

The continuous content loop that feeds WordPress sites after deployment:

| File | LoC | Role |
|------|----:|------|
| `@/opt/fabrik/src/fabrik/orchestrator/content_publisher.py` | ~800 | Orchestrator: SEO brief → TCO generation → Image Broker → WP REST API publish. Two modes: `publish()` (batch drain) + `publish_page()` (single job) |
| `@/opt/fabrik/src/fabrik/drivers/seo.py` | ~400 | SEO service client: site registration, keyword research jobs, brief lifecycle (claim/release/submit) |
| `@/opt/fabrik/src/fabrik/drivers/tco.py` | ~130 | TCO (Triggered Content Orchestration) client: sends brief to AI content generation pipeline (port 8025), returns page_package with sections + JSON-LD + metadata |
| `@/opt/fabrik/src/fabrik/drivers/image_broker.py` | ~180 | Image Broker client (port 18016): stock photo search/download with provider routing (Pexels/Pixabay), scoring, attribution |
| `@/opt/fabrik/src/fabrik/notifications.py` | ~100 | n8n webhook notifications: fires on deploy success/failure + content publish events → Telegram |

**Pipeline flow:**
```
fabrik seo site-register → register site in SEO service
fabrik seo job-create → keyword research job
fabrik seo job-run → researches → generates content briefs
fabrik content publish <domain> →
  1. Claim ready brief from SEO service
  2. Send to TCO (AI generates article: sections + SEO meta + JSON-LD)
  3. Query Image Broker for hero image (keyword-based)
  4. Publish to WordPress via REST API (page/post + featured image)
  5. Mark brief as published in SEO service
  6. Fire n8n webhook → Telegram notification
```

### 1.6 Domain & Search Engine Registration

| File | Role |
|------|------|
| `@/opt/fabrik/src/fabrik/drivers/dns.py` | Site provisioner client: domain purchase (Namecheap), DNS + CDN + WAF (Cloudflare), **Google Search Console registration**, **Bing Webmaster Tools**, **IndexNow** (Bing/Yandex/Seznam/Naver), sitemap submission |
| `@/opt/fabrik/src/fabrik/wordpress/domain_setup.py` | WordPress-specific domain wiring: DNS records + Cloudflare zone + Traefik labels |

### 1.7 Adjacent integration points (WordPress-aware code in non-WP modules)

Files that import from `src/fabrik/wordpress/` or special-case `type: wordpress`:

- `@/opt/fabrik/src/fabrik/cli.py` — `fabrik wp` command group (`plan`, `apply`, `verify`, `flush` subcommands) + `fabrik domain`, `fabrik seo`, `fabrik content` commands
- `@/opt/fabrik/src/fabrik/scaffold.py` — `wordpress` scaffold type handler, calls `_scaffold_wordpress_templates()`
- `@/opt/fabrik/src/fabrik/preplan.py` — preplan authoring/ingestion; `fabrik preplan new` creates intent capture docs that scaffold reads for WP projects
- `@/opt/fabrik/src/fabrik/spec_loader.py` — branches when `type == "wordpress"` to use `wordpress/spec_loader.py`
- `@/opt/fabrik/src/fabrik/spec_generator.py` — generates `specs/services/<id>.yaml` with shape block at scaffold time (WP gets `kind: wordpress`)
- `@/opt/fabrik/src/fabrik/deploy_router.py` — routes `type: wordpress` projects to the WordPress engine instead of the standard orchestrator
- `@/opt/fabrik/src/fabrik/deploy_validator.py` — WP-specific deploy-readiness checks
- `@/opt/fabrik/src/fabrik/provisioner.py` — provisions MariaDB + Redis for WP
- `@/opt/fabrik/src/fabrik/orchestrator/content_publisher.py` — drains SEO briefs into WP via `drivers/wordpress_api.py`
- `@/opt/fabrik/src/fabrik/orchestrator/verifier.py` — WP-specific health checks (homepage 200, admin auth)
- `@/opt/fabrik/src/fabrik/orchestrator/infrastructure.py` — dispatches registrars for WP services (gatus, glitchtip, backrest, etc.)
- `@/opt/fabrik/src/fabrik/content/orchestrator.py` — re-export of `orchestrator.content_publisher` under canonical path
- `@/opt/fabrik/src/fabrik/drivers/glitchtip.py` — injects GlitchTip DSN into `wp-config-extra.php`
- `@/opt/fabrik/src/fabrik/drivers/image_broker.py` — surfaces stock-photo lookups to `wordpress/media.py`
- `@/opt/fabrik/src/fabrik/notifications.py` — n8n webhooks for deploy + content events → Telegram
- `@/opt/fabrik/src/fabrik/__init__.py` — re-exports

---

## 2. Templates (`@/opt/fabrik/templates/wordpress/`)

### 2.0 Scaffold-shared (lives outside `templates/wordpress/`)

- `@/opt/fabrik/templates/scaffold/docker/Makefile.wordpress` — WP-specific Makefile variant copied into per-site scaffolds (`up`/`down`/`logs`/`wp-cli`/`backup` targets)

### 2.1 Top-level

- `@/opt/fabrik/templates/wordpress/AGENTS.md` — agent contract for WP-specific work
- `@/opt/fabrik/templates/wordpress/README.md` — template overview
- `@/opt/fabrik/templates/wordpress/defaults.yaml` — defaults applied on top of every preset
- `@/opt/fabrik/templates/wordpress/site-spec-schema.yaml` — JSON-Schema for `site.yaml` (legacy entry, see `schema/v1.yaml` for the live one)
- `@/opt/fabrik/templates/wordpress/compose.yaml.j2` — top-level compose template (used directly)
- `@/opt/fabrik/templates/wordpress/plugins_latest.json` — version manifest of bundled plugins

### 2.2 `templates/wordpress/base/` — Per-site Docker baseline

- `@/opt/fabrik/templates/wordpress/base/compose.yaml.j2` — VPS/Coolify compose
- `@/opt/fabrik/templates/wordpress/base/compose-coolify.yaml.j2` — Coolify-specific compose
- `@/opt/fabrik/templates/wordpress/base/compose.dev.yaml.j2` — local dev compose
- `@/opt/fabrik/templates/wordpress/base/.env.j2` — env template
- `@/opt/fabrik/templates/wordpress/base/Makefile.j2` — convenience Makefile (down/up/logs/wp-cli)
- `@/opt/fabrik/templates/wordpress/base/site.yaml.j2` — starter `site.yaml` written by `fabrik scaffold --type wordpress`
- `@/opt/fabrik/templates/wordpress/base/wp-config-extra.php` — extra PHP config (Redis cache, GlitchTip, security headers)
- `@/opt/fabrik/templates/wordpress/base/nginx/default.conf.j2` — production nginx
- `@/opt/fabrik/templates/wordpress/base/nginx-dev.conf.j2` — dev nginx
- `@/opt/fabrik/templates/wordpress/base/php-fpm/zz-fabrik-listen.conf` — PHP-FPM pool override
- `@/opt/fabrik/templates/wordpress/base/backup/backup.sh` — DB + uploads backup script (Backrest/B2)

### 2.3 `templates/wordpress/presets/` — 5 site presets

- `@/opt/fabrik/templates/wordpress/presets/saas.yaml` (10,369 B) — SaaS landing + auth flow
- `@/opt/fabrik/templates/wordpress/presets/company.yaml` (7,598 B) — corporate brochure site
- `@/opt/fabrik/templates/wordpress/presets/content.yaml` (9,970 B) — blog/magazine
- `@/opt/fabrik/templates/wordpress/presets/landing.yaml` (5,474 B) — single-page landing
- `@/opt/fabrik/templates/wordpress/presets/ecommerce.yaml` (9,082 B) — WooCommerce / EDD

### 2.4 `templates/wordpress/schema/`

- `@/opt/fabrik/templates/wordpress/schema/v1.yaml` (12,303 B) — **canonical** site-spec schema
- `@/opt/fabrik/templates/wordpress/schema/MERGE_RULES.md` — preset+user-spec merge semantics
- `@/opt/fabrik/templates/wordpress/schema/VALIDATION_RULES.md` — business-rule validations beyond schema

### 2.5 Plugin/theme bundles

- `@/opt/fabrik/templates/wordpress/plugins/premium/*.zip` — **125 premium plugin .zip files** (not enumerated here; see `find templates/wordpress/plugins/premium -name "*.zip"`)
- `@/opt/fabrik/templates/wordpress/plugins/premium/README.md` — plugin licensing notes
- `@/opt/fabrik/templates/wordpress/plugins/premium/wp_plugins_activation_notes.md` — activation order + dependency notes
- `@/opt/fabrik/templates/wordpress/themes/premium/README.md` — theme licensing notes

> **Plugin bundle policy** — these zips are pre-licensed assets. `manifests/plugins.py` references them by slug; `stages/plugins.py` extracts + activates.

---

## 3. Tests (`tests/`, ~3,043 LoC)

### 3.1 `tests/wordpress/` — Engine tests (20 files)

| File | LoC | Covers |
|------|----:|--------|
| `@/opt/fabrik/tests/wordpress/fixtures/__init__.py` | 0 | Fixture package marker |
| `@/opt/fabrik/tests/wordpress/fixtures/ocoron_baseline.json` | n/a | Baseline run snapshot from a real `ocoron.com` deploy (used by `test_deployer_baseline.py`) |
| `@/opt/fabrik/tests/wordpress/test_planner.py` | — | `Planner` DAG construction |
| `@/opt/fabrik/tests/wordpress/test_resolved_spec.py` | — | `ResolvedSpec` immutability + merge correctness |
| `@/opt/fabrik/tests/wordpress/test_manifests.py` | — | Plugin/menu/page manifests |
| `@/opt/fabrik/tests/wordpress/test_idempotency.py` | — | Re-run safety of full pipeline |
| `@/opt/fabrik/tests/wordpress/test_deployer_baseline.py` | — | Deployer happy path |
| `@/opt/fabrik/tests/wordpress/stages/__init__.py` | 1 | |
| `@/opt/fabrik/tests/wordpress/stages/conftest.py` | 42 | Shared stage fixtures |
| `@/opt/fabrik/tests/wordpress/stages/test_dns.py` | 58 | DNS stage |
| `@/opt/fabrik/tests/wordpress/stages/test_theme.py` | 29 | Theme stage |
| `@/opt/fabrik/tests/wordpress/stages/test_plugins.py` | 218 | Plugin stage (largest single-stage test) |
| `@/opt/fabrik/tests/wordpress/stages/test_settings.py` | 135 | Settings stage |
| `@/opt/fabrik/tests/wordpress/stages/test_languages.py` | 120 | i18n stage |
| `@/opt/fabrik/tests/wordpress/stages/test_menus.py` | 40 | Menus stage |
| `@/opt/fabrik/tests/wordpress/stages/test_pages.py` | 47 | Pages stage |
| `@/opt/fabrik/tests/wordpress/stages/test_forms.py` | 40 | Forms stage |
| `@/opt/fabrik/tests/wordpress/stages/test_seo.py` | 40 | SEO stage |
| `@/opt/fabrik/tests/wordpress/stages/test_analytics.py` | 40 | Analytics stage |
| `@/opt/fabrik/tests/wordpress/stages/test_verify.py` | 1,009 | **Verify stage** (largest WP test by far) |
| `@/opt/fabrik/tests/wordpress/stages/test_verify_homepage_429.py` | 409 | Specific Cloudflare/rate-limit edge cases |

### 3.2 Other WP-related tests under `tests/`

- `@/opt/fabrik/tests/test_wp_spec_resolution.py` (342) — spec loader / preset merger
- `@/opt/fabrik/tests/test_wordpress_pages.py` (53) — pages module unit tests
- `@/opt/fabrik/tests/test_cli_wp_verify.py` (69) — `fabrik wp verify` CLI
- `@/opt/fabrik/tests/test_scaffold_wordpress_templates.py` (351) — `fabrik scaffold --type wordpress` template rendering

### 3.3 Tests with WordPress branches but not WP-primary

These exercise WP behaviour via shared modules; touch with care when refactoring:

- `@/opt/fabrik/tests/test_scaffold.py`
- `@/opt/fabrik/tests/test_scaffold_spec_generation.py`
- `@/opt/fabrik/tests/test_spec_generator.py`
- `@/opt/fabrik/tests/test_shape_phase_4k.py`
- `@/opt/fabrik/tests/test_deploy_router.py`
- `@/opt/fabrik/tests/test_deploy_validator.py`
- `@/opt/fabrik/tests/test_handoff.py`
- `@/opt/fabrik/tests/test_check_traefik_labels.py`
- `@/opt/fabrik/tests/test_backfill_has_user_guide.py`
- `@/opt/fabrik/tests/test_kilo_dispatch.py`
- `@/opt/fabrik/tests/content/test_orchestrator.py` — content-publisher → WP integration
- `@/opt/fabrik/tests/drivers/test_glitchtip.py` — DSN injection into WP
- `@/opt/fabrik/tests/drivers/test_container_resolver.py`
- `@/opt/fabrik/tests/orchestrator/test_infrastructure.py`

---

## 4. Documentation

### 4.1 Active reference (`docs/reference/wordpress/`)

- `@/opt/fabrik/docs/reference/wordpress.md` — top-level WP reference (entry point)
- `@/opt/fabrik/docs/reference/wordpress/architecture.md` — engine architecture
- `@/opt/fabrik/docs/reference/wordpress/site-specification.md` — `site.yaml` reference
- `@/opt/fabrik/docs/reference/wordpress/deployment-workflow.md` — end-to-end deploy flow
- `@/opt/fabrik/docs/reference/wordpress/pages-idempotency.md` — page-stage idempotency contract
- `@/opt/fabrik/docs/reference/wordpress/plugin-stack.md` — bundled plugin stack
- `@/opt/fabrik/docs/reference/wordpress/plugin-evaluation.md` — plugin selection criteria
- `@/opt/fabrik/docs/reference/wordpress/fixes.md` — known-fix recipes
- `@/opt/fabrik/docs/reference/wordpress/archived-01-wordpress-production-sop.md` — archived SOP (reference only, extracted valuable items into blazing-fast plan)
- `@/opt/fabrik/docs/reference/wordpress/archived-02-technical-implementation-addendum.md` — archived technical addendum
- `@/opt/fabrik/docs/reference/wordpress/archived-zero-ops-pipeline-narrative.md` — archived Zero-Ops narrative (pipeline design philosophy)

### 4.2 Workflows + architecture

- `@/opt/fabrik/docs/workflows/wordpress-site-workflow.md` — owner-facing end-to-end WordPress workflow
- `@/opt/fabrik/docs/architecture/WORDPRESS-MODULE-INTEGRATION.md` — how WP module integrates with Fabrik core
- `@/opt/fabrik/docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md` — generic scaffold doc, has WP sections
- `@/opt/fabrik/docs/workflows/SCAFFOLD_STRUCTURE.md` — generic structure doc, has WP sections

### 4.3 Cross-cutting docs that mention WordPress

(Not WP-primary, but contain WordPress references — touch only the relevant sections.)

- `@/opt/fabrik/docs/DEPLOYMENT.md`
- `@/opt/fabrik/docs/BUSINESS_MODEL.md`
- `@/opt/fabrik/docs/CONFIGURATION.md`
- `@/opt/fabrik/docs/FEATURES.md`
- `@/opt/fabrik/docs/FAQ.md`
- `@/opt/fabrik/docs/EXTERNAL_SYSTEMS.md`
- `@/opt/fabrik/docs/LESSONS_LEARNT.md`
- `@/opt/fabrik/docs/operations/vps-urls.md`
- `@/opt/fabrik/docs/infrastructure/vps-complete-inventory.md`
- `@/opt/fabrik/docs/guides/domain-hosting-automation.md`
- `@/opt/fabrik/docs/guides/FABRIK_INTEGRATION.md`
- `@/opt/fabrik/docs/reference/architecture.md`
- `@/opt/fabrik/docs/reference/drivers.md`
- `@/opt/fabrik/docs/reference/fabrik.md`
- `@/opt/fabrik/docs/reference/fabrik-cli-reference.md`
- `@/opt/fabrik/docs/reference/orchestrator.md`
- `@/opt/fabrik/docs/reference/provisioner.md`
- `@/opt/fabrik/docs/reference/templates.md`
- `@/opt/fabrik/docs/reference/stack.md`
- `@/opt/fabrik/docs/reference/roadmap.md`
- `@/opt/fabrik/docs/reference/scaffold-type-decision-guide.md`
- `@/opt/fabrik/docs/reference/PLANNING_REFERENCES.md`

### 4.4 Active development plans

- `@/opt/fabrik/docs/development/plans/2026-05-17-wordpress-blazing-fast.md` — **current plan**: local create → VPS deploy → continuous content automation
- `@/opt/fabrik/docs/development/plans/issues/2026-03-15-deployment-log.md` — historical deployment log

Archived (2026-05-17): `2026-04-13-fabrik-control-plane.md` (chat UI — superseded by CLI pipeline), `2026-04-18-zero-touch-deployment.md` (complete — `fabrik apply` works).

### 4.5 Archived / historical (do not edit, reference only)

- `@/opt/fabrik/docs/development/plans/archived/62-wordpress.md`
- `@/opt/fabrik/docs/development/plans/archived/new rules/62-wordpress.md`
- `@/opt/fabrik/docs/archive/2026-03-24-droid-cleanup/fix-fabrik-compliance-issues/2026-01-09-fixes-06-wordpress.md`
- Multiple under `@/opt/fabrik/docs/archive/...` and `docs/development/plans/previously-planned-fabrik-phases/...`

---

## 5. Governance Rules

- `@/opt/fabrik/.windsurf/rules/62-wordpress.md` — **canonical WordPress rules pack** (loaded on-demand when WP work is happening)
- `@/opt/fabrik/.windsurf/rules/42-docusaurus.md` — mentions WP for cross-comparison
- `@/opt/fabrik/.windsurf/rules/55-observability.md` — WP-specific health/monitoring expectations
- `@/opt/fabrik/.windsurf/rules/85-payments-billing.md` — Paddle/billing references for WP commerce
- `@/opt/fabrik/.windsurf/rules/ocoron-design-system.md` — design tokens (applied to WP themes)

---

## 6. Scripts

- `@/opt/fabrik/scripts/create_wp_container.py` — standalone helper to spin up a one-off WP container (dev/debug)
- `@/opt/fabrik/scripts/audit_all_projects.py` — audits all projects including WP sites
- `@/opt/fabrik/scripts/audit_authelia_gates.py` — checks WP admin is behind Authelia where required
- `@/opt/fabrik/scripts/sync_projects.py` — syncs WP project registrations to `data/projects.yaml`
- `@/opt/fabrik/scripts/docs_updater.py`
- `@/opt/fabrik/scripts/final_gate.py`
- `@/opt/fabrik/scripts/enforcement/check_traefik_labels.py` — gate-checks WP Traefik labels
- `@/opt/fabrik/scripts/enforcement/check_no_host_ports.py`
- `@/opt/fabrik/scripts/kilo_code_review.py`, `kilo_dispatch.py`, `mcp_kilo_server.py` — generic, but invoked on WP code

---

## 7. Specs (`specs/`)

> **Correction 2026-04-29 (rescan):** WordPress site specs ARE tracked in-repo — not under `specs/services/` (which is for Fabrik-core services) but under a dedicated **`specs/sites/`** directory. The original section overlooked this.

### 7.1 `specs/sites/` — Live WordPress site specs

- `@/opt/fabrik/specs/sites/ocoron.com.yaml` — **canonical site spec** for `ocoron.com` (588 lines, `preset: company`, status `DRAFT - Needs user input`). Consolidated 2026-05-17 (v2 became canonical; v1 + backup archived as `archived-ocoron.com.v1.*` in same dir).
- `@/opt/fabrik/specs/sites/ocoron.com-content-plan.md` — content plan (347 lines, copy/IA/keyword strategy)
- `@/opt/fabrik/specs/sites/ocoron.com-media/` — 36 media assets (logos, favicons, photos, brand art); referenced by `ocoron.com.yaml` `brand.logo.*` paths. Includes:
  - `Favicon/` (5 files: 16x16, 32x32, 192x192, 512x512, apple-touch + favicon.ico)
  - `Ocoron-art/` (8 photographic source images)
  - Logo variants (`logo.svg`, `logo_inverted.jpg`, `logo_LinkedIn.png`, `logo_watermark_white_458x96.png`, etc.)
  - LinkedIn/social BG images
  - 1 stale `Zone.Identifier` marker (Windows download artifact, **delete candidate**)
  - `Ocoron Services Draft.md` — inline content draft

### 7.2 Related service specs

- `@/opt/fabrik/specs/services/seo.yaml` — SEO microservice (port 8016): keyword research, brief generation, feeds content pipeline
- `@/opt/fabrik/specs/services/youtube.yaml` — YouTube pipeline (port 8029): content research source for SEO briefs

### 7.3 Other spec areas — no WordPress refs

Verified empty: `specs/services/`, `specs/operations/`, `specs/infrastructure/`, `specs/verification/`, `specs/n8n-workflows/`, `specs/ecosystem-compliance/`, `specs/worker-example.yaml`, `specs/example-api.yaml`, `specs/FABRIK_CONDUCTOR_PLAN.md` — none reference WordPress.

### 7.3 Project registry

- `@/opt/fabrik/data/projects.yaml` — registers `fabrik-test-wordpress` (1 entry, `type: wordpress`, `preset: saas`, port `8020`, path `/opt/fabrik-test-wordpress`, created 2026-04-27)

---

## 8. Live scaffolded sites (outside this repo)

(Per-site working trees created by `fabrik scaffold --type wordpress`. Useful for diffing against template changes.)

- `/opt/fabrik-test-wordpress/` — Test WP project, scaffolded 2026-04-27. Top-level layout: `compose.yaml.j2`, `compose.dev.yaml`, `Makefile`, `nginx/`, `php-fpm/`, `plugins/`, `db/`, `backup/`, `config/`, `data/`, `logs/`, `output/`, `project.yaml`, `INDEX.md`, `PORTS.md`, `CHANGELOG.md`, `AGENTS.md`, `AGENTS-compact.md`, `AFCL.md`, `opencode.json`. Has its own `docs/` tree.
- *(Future: any other `/opt/<wp-site>/` projects scaffolded from `templates/wordpress/`. Each has its own `site.yaml` at root.)*

## 9. Agent review-context artifacts (informational, not code)

- `@/opt/fabrik/.droid/review-context/2026-02-27-wordpress-fixes-verification.md`
- `@/opt/fabrik/.droid/review-context/2026-03-16-wordpress-integration-docs.md`

Plus dozens of `.droid/{review_results,reviews,transcripts,traycer-reports}/*` JSON/MD files that mention WordPress incidentally during agent runs. **Not enumerated** — these are run logs, not development files.

---

## Summary stats

| Area | Files | Lines |
|------|------:|------:|
| `src/fabrik/wordpress/` core | 22 | 6,921 |
| `src/fabrik/wordpress/stages/` | 14 | 1,654 |
| `src/fabrik/wordpress/manifests/` | 5 | 382 |
| `src/fabrik/drivers/wordpress*.py` | 2 | 717 |
| WP-aware code in non-WP src | ~11 files | (partial — touched as needed) |
| `templates/wordpress/` (excluding 125 plugin .zips) | 32 | n/a |
| `templates/scaffold/docker/Makefile.wordpress` (shared variant) | 1 | n/a |
| Plugin .zip bundle | 125 | binary |
| `tests/wordpress/` | 20 | ~2,440 |
| Other WP tests under `tests/` | 4 | ~815 |
| `docs/reference/wordpress/` + workflows | 13 | n/a |
| Governance rules | 5 | n/a |
| Scripts | ~3 WP-specific + several WP-aware | n/a |
| **`specs/sites/` (live site specs + media)** | **41** | **~2,115 (text only)** |
| `data/projects.yaml` registry entries | 1 (`fabrik-test-wordpress`) | n/a |
| Live scaffold trees on disk | 1 (`/opt/fabrik-test-wordpress/`) | n/a |
| **Source-of-truth code total** | **44 modules** | **~9,674 LoC** |

---

## Working list — pick from this when planning the next iteration

The owner can now point to any line and say "let's work on X". Suggested entry points (largest first, most leverage):

1. **`stages/test_verify.py` (1,009 LoC)** — the verify stage is by far the most-tested; if behaviour shifts, this is ground zero
2. **`pages.py` (620) + `section_renderer.py` (508) + `seo.py` (469)** — content-generation core
3. **`deployer.py` (465)** — the runner; refactor target if rollback semantics change
4. **`domain_setup.py` (484)** — DNS/CF/Traefik integration; touched whenever provisioning changes
5. **Schema + presets** — `schema/v1.yaml` + `presets/*.yaml` are the user-facing API; renames here are breaking changes
6. **Three legacy doc files with non-kebab-case names** under `docs/reference/wordpress/` — easy cleanup win
7. **`templates/wordpress/site-spec-schema.yaml` vs `templates/wordpress/schema/v1.yaml`** — duplicate/legacy entry, consolidate
8. **`specs/sites/ocoron.com.yaml` is `DRAFT - Needs user input`** — the production target site has an unfinished spec; pinning down the user-input gaps may be the highest-value real-world work
9. **`specs/sites/ocoron.com.yaml.backup`** — rename or delete; violates cleanliness rule
10. **`specs/sites/ocoron.com-media/` hygiene** — 1 `Zone.Identifier` artifact + `.jfif` legacy filenames + space-in-filename (`logo 1200 x 630.jfif`) — mass-rename to kebab-case + drop dupes
11. **`ocoron.com.yaml` vs `ocoron.com.v2.yaml`** — decide which is canonical, archive the other
12. **WordPress vs unified spec model** — `specs/sites/` (WP) lives parallel to `specs/services/` (Fabrik core) with different schemas; explicit decision pending on whether to converge
