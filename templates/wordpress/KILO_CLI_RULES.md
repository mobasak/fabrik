# Kilo CLI — WordPress Factory Bootstrap

> Tactical bootstrap for Kilo CLI when working on the **Fabrik WordPress Factory engine** (Phases 2–5 of the build). For per-generated-site work, the site's own rules apply.

**Scope:** WordPress Factory infrastructure work in `src/fabrik/wordpress/`, `templates/wordpress/`, and `specs/sites/` — NOT inside generated WordPress sites.

## What This File Governs

Kilo CLI is reading this file when it is editing the Fabrik monorepo's WordPress factory engine: the 13-stage deployer at `src/fabrik/wordpress/`, the golden-base image work (Phase 2), the `fabrik wp` CLI wrappers (Phase 2), per-site spec files at `specs/sites/*.yaml`, and the manifests under `templates/wordpress/`. It governs the **build of the factory**, not the WordPress sites the factory produces. Site-level conventions (themes, plugins inside `wp-content/`, content schemas) are out of scope here — they belong to each generated site. If you are unsure which side of the line you are on, ask before editing.

## Canonical Sources of Truth

Read these before changing factory behavior. Do not duplicate their content — cross-reference only.

- [`../../.windsurf/rules/62-wordpress.md`](../../.windsurf/rules/62-wordpress.md) — the canonical WordPress rule pack: MariaDB 10.6+, `wordpress:php8.x-fpm-bookworm` only, custom table prefix, FastCGI cache mandatory, WPML banned in favour of Polylang Pro + AutoPoly, 10-layer security model. This rule pack is the contract; if code disagrees, code is wrong.
- [`../../docs/development/plans/wordpress/00-vision.md`](../../docs/development/plans/wordpress/00-vision.md) — end-to-end factory vision (idea → live site in < 60 s; daily content pipeline; Watchdog AI).
- [`../../docs/development/plans/wordpress/01-golden-base.md`](../../docs/development/plans/wordpress/01-golden-base.md) — the baked Docker image that is identical across every site.
- [`../../docs/development/plans/wordpress/02-gui-wizard.md`](../../docs/development/plans/wordpress/02-gui-wizard.md) — six-screen creation wizard + operations dashboard.
- [`../../docs/development/plans/wordpress/03-watchdog-ai.md`](../../docs/development/plans/wordpress/03-watchdog-ai.md) — per-site autonomous admin (daily / weekly / monthly cycles).
- [`../../docs/development/plans/wordpress/04-execution-order.md`](../../docs/development/plans/wordpress/04-execution-order.md) — the seven-phase delivery order (Phase 0 = current foundation, Phase 6 = SaaS-ready housekeeping).
- [`../../docs/development/plans/wordpress/05-code-classification.md`](../../docs/development/plans/wordpress/05-code-classification.md) — which legacy modules to use / modify / archive.
- [`../../docs/development/plans/wordpress/06-plugin-manifest.md`](../../docs/development/plans/wordpress/06-plugin-manifest.md) — the 11 BASE plugins + per-profile additions.
- [`./AGENTS.md`](./AGENTS.md) — Traycer's planner context for this template tree. **Do not modify** (Traycer-owned per the repo-root `AGENTS.md` § File Ownership table).
- [`../../AGENTS-compact.md`](../../AGENTS-compact.md) + [`../../KILO_CLI_RULES.md`](../../KILO_CLI_RULES.md) — the always-on Kilo CLI bootstraps loaded via `opencode.json` `instructions:`. They carry the cross-cutting rules (Doc Sync Matrix, Security & Data, Docker & Deploy, HARD STOPS) per `AGENTS.md § Rule-Pack Injection` because Kilo's dispatcher does not auto-load `.windsurf/rules/` packs.

If a question is not answered by the seven plans above plus `62-wordpress.md`, surface it before guessing.

## Hard Stops

These are the small, high-blast-radius rules. The full list lives in `62-wordpress.md`; the six below are the ones that break a deploy fastest if violated. Read the rule pack for the rest before acting.

1. **No Alpine base images for WordPress containers.** Alpine's musl libc breaks `php-fpm` extensions WordPress depends on. Bookworm only.
2. **No `:latest` image tag — anywhere.** Lock the PHP minor (e.g. `wordpress:php8.3-fpm-bookworm`); upstream rolls break container immutability.
3. **Only `/var/www/html/wp-content` is a named volume.** Never bind-mount the whole web root — it defeats containerised core updates and breaks permissions.
4. **The five Cloudflare WAF rules are mandatory** (bot skip → `wp-login.php` POST challenge → `xmlrpc.php` block → `wp-admin` challenge → VPN ASN challenge). Sites without all five are not allowed to go live.
5. **`wp-config.php` must set `DISALLOW_FILE_EDIT`, `DISALLOW_FILE_MODS`, `FORCE_SSL_ADMIN`, and `DISABLE_WP_CRON`** — and `WP_DEBUG=true` paired with `WP_DEBUG_DISPLAY=false` (DEBUG must be true for the log to write).
6. **Secrets via environment variables only.** Never hardcode DB credentials, salts, or API keys in `wp-config.php` or any version-controlled file. Coolify env injection or `WORDPRESS_CONFIG_EXTRA` is the only path.

**Kilo-specific:** Kilo's dispatcher does **not** auto-load `.windsurf/rules/` packs the way Windsurf Cascade does. When in doubt about any WordPress-factory decision, **read [`../../.windsurf/rules/62-wordpress.md`](../../.windsurf/rules/62-wordpress.md) directly before acting** — do not infer the rule from context. The repo-root `AGENTS-compact.md` carries the always-on cross-cutting rules per `AGENTS.md § Rule-Pack Injection`; topical packs (including `62-wordpress.md`) require an explicit read.

## What's Already Built (don't recreate)

The factory engine is ~9,700 LoC of working code. Re-using it is correct; rebuilding it is not. From [`../../docs/development/plans/wordpress/00-vision.md`](../../docs/development/plans/wordpress/00-vision.md) "What's Built vs What's New":

| Component | Status |
|---|---|
| WordPress engine (13-stage deploy pipeline) | Built (~9,700 LoC) |
| 6 presets / 8 profiles + 3-layer spec merge | Built |
| 10-layer security model (automated via templates) | Built |
| 4-layer caching (Cloudflare + Nginx FastCGI + Redis Object + WP transients) | Built |
| Monitoring (Gatus + GlitchTip + Grafana + Backrest → B2) | Built |
| Content pipeline (SEO → TCO → Image Broker → WP REST → publish) | Built |
| Domain provisioning + search-engine registration | Built |
| Analytics injection (GA4 / GTM / Schema / OG) | Built |
| 125 premium plugins bundled + licensed | Built |
| Bilingual support (Polylang Pro + AutoPoly + Translator API) | Decided + wired |
| 8 Makefile ops (`update`, `cache-flush`, `backup`, `harden`, etc.) | Built |
| Golden base Docker image | **To build — Phase 2** |
| GUI wizard + operations dashboard | **To build — Phases 3 + 4** |
| Watchdog AI (autonomous site admin) | **To build — Phase 5** |
| `fabrik-api` HTTP bridge | **To build — Phase 3** |
| `FABRIK_EXEC_MODE=local` env-gate | **To build — Phase 1 (in flight)** |

Before adding any module under `src/fabrik/wordpress/`, search the tree for an existing implementation. Most "new" engine work is an extension of an existing stage, registrar, or driver.

## Phase Boundaries

The current Epic is **Phase 1 — Foundation**. Its boundary is the Out-of-Scope list of its Epic Brief — those items are explicitly deferred. Do not pull them forward.

| Phase | Owns | Out of Scope for This Phase |
|---|---|---|
| **1 — Foundation (current)** | `FABRIK_EXEC_MODE` env-gate; finalised `ocoron.com` spec (DRAFT → READY, WPML → Polylang); first end-to-end VPS deploy; agent guardrails (this file + `CLAUDE.md`) | Golden-base image, layered profile images, `fabrik wp create / preview / promote`, `fabrik-api`, GUI, Watchdog, multi-tenant fields |
| **2 — Golden Base** | Baked Docker image with the 11 BASE plugins, security baked in, MariaDB 10.11 + Nginx hardened | GUI wizard, Watchdog, content cadence beyond Phase 1's fixed cron |
| **3 — `fabrik-api`** | HTTP bridge for the GUI / remote control | Front-end UI itself |
| **4 — Control Panel** | GUI wizard + operations dashboard | Watchdog autonomy |
| **5 — Watchdog AI** | Per-site daily / weekly / monthly autonomous admin | Multi-tenant, billing |
| **6 — SaaS Readiness** | `owner_id` field, multi-VPS routing, Paddle/Stripe hooks | Customer onboarding flows |

If a ticket scope appears to require work from a later phase, **stop and flag it** before editing. Carrying scope forward silently is the most common failure mode here.

---

Keep this file under 200 lines. If a topic needs more depth, put it in the canonical rule pack or a plan doc and link from here.
