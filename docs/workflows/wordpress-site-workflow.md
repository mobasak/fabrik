# WordPress Site Workflow

**Last Updated:** 2026-04-13
**Scope:** End-to-end lifecycle for launching and maintaining a WordPress site via Fabrik —
from domain registration through content publishing.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Phase 1 — Domain](#phase-1--domain)
4. [Phase 2 — Plan](#phase-2--plan)
5. [Phase 3 — Deploy to Coolify](#phase-3--deploy-to-coolify)
6. [Phase 4 — Apply WordPress Configuration](#phase-4--apply-wordpress-configuration)
7. [Phase 5 — Verify](#phase-5--verify)
8. [Phase 6 — Publish Content](#phase-6--publish-content)
9. [Day-2 Operations](#day-2-operations)
10. [Spec File Reference](#spec-file-reference)
11. [Build Artifacts Reference](#build-artifacts-reference)
12. [Stage Reference](#stage-reference)
13. [Environment Variables](#environment-variables)
14. [Troubleshooting](#troubleshooting)

---

## Overview

```text
Domain           ──► Provision DNS + CDN + WAF via site-provisioner
                          │
Plan             ──► fabrik wp plan   → build artifacts (plan.json, manifests)
                          │
Coolify deploy   ──► fabrik apply     → WordPress container live on VPS
                          │
WP config        ──► fabrik wp apply  → settings, theme, plugins, pages, SEO, analytics
                          │
Verify           ──► fabrik wp verify → HTTP checks, handoff report
                          │
Content          ──► fabrik content publish → drain SEO briefs, publish pages
```

Each phase is idempotent and can be re-run safely.

---

## Prerequisites

### Required env vars (`.env`)

```bash
VPS_IP=172.93.160.197
SITE_PROVISIONER_URL=https://dns.vps1.ocoron.com
SITE_PROVISIONER_API_KEY=<API_KEY from site-provisioner .env>
WP_ADMIN_USER=admin
WP_ADMIN_PASSWORD=<wp admin password>
COOLIFY_API_TOKEN=<token>
COOLIFY_BASE_URL=https://coolify.vps1.ocoron.com
```

### Required tools

- `fabrik` CLI installed (`pip install -e /opt/fabrik`)
- SSH access to VPS (`ssh ozgur@172.93.160.197`)
- Site spec file (`site.yaml`) created — see [Spec File Reference](#spec-file-reference)

---

## Phase 1 — Domain

Sets up DNS, CDN, WAF, and search engine registration via `site-provisioner`.
Run once per domain. Skip if the domain is already provisioned in Cloudflare.

### 1.1 Check availability (new domains only)

```bash
fabrik domain check tojlo.com
```

Output shows availability and per-registrar pricing. If available, proceed to buy.

### 1.2 Register domain (new domains only)

```bash
fabrik domain buy tojlo.com
# With confirmation skip:
fabrik domain buy tojlo.com --yes
```

`site-provisioner` selects registrar, sets nameservers, and enables WHOIS privacy automatically.

### 1.3 Provision DNS + CDN + WAF

```bash
# Minimal — DNS A record + security
fabrik domain provision tojlo.com

# With www subdomain + sitemap submitted at provision time
fabrik domain provision tojlo.com -s www \
  --sitemap-url https://tojlo.com/sitemap.xml

# With GA4 property created
fabrik domain provision tojlo.com -s www \
  --setup-ga4 --ga4-account-id 194840782 \
  --sitemap-url https://tojlo.com/sitemap.xml
```

What this does in a single call:

| Feature | Default |
|---|---|
| Cloudflare zone + A record | ✅ always |
| DNSSEC | ✅ enabled |
| Smart Tiered Cache (CDN) | ✅ enabled |
| Page Shield (script monitoring) | ✅ enabled |
| WAF threat score rule | ✅ enabled |
| Bing Webmaster Tools | ✅ enabled |
| IndexNow ping | ✅ enabled |
| Google Search Console | opt-in (`--setup-google`) |
| GA4 property | opt-in (`--setup-ga4`) |

Available flags:

```
--ip TEXT              Override target IP (default: VPS_IP env var)
-s, --subdomain TEXT   Extra subdomains — repeatable (e.g. -s www -s api)
--no-dnssec            Skip DNSSEC
--no-cache             Skip Tiered Cache
--no-shield            Skip Page Shield
--no-waf               Skip WAF rule
--setup-google         Register with Google Search Console
--no-bing              Skip Bing Webmaster Tools
--no-indexnow          Skip IndexNow
--setup-ga4            Create GA4 property
--ga4-account-id TEXT  GA4 account ID (required with --setup-ga4)
--sitemap-url TEXT     Submit sitemap to all search engines
```

### 1.4 Wait for DNS propagation

```bash
# One-shot check
fabrik domain ready tojlo.com

# Poll every 10s until ready (max 120s)
fabrik domain ready tojlo.com --wait
```

Output includes `ready=true/false`, zone status, and DNS records.
**Do not deploy to Coolify until `ready=true`.**

### 1.5 Confirm integration metadata (optional)

```bash
fabrik domain integrations tojlo.com
```

Shows GA4 measurement ID, GSC verification status, Bing registration, IndexNow ping count.

---

## Phase 2 — Plan

Generates build artifacts that the `apply` command needs. Run before every `apply`.

```bash
# Option A: pass site_id directly (reads from specs/sites/tojlo.com.yaml)
fabrik wp plan tojlo.com

# Option B: cd into the WordPress project folder (reads ./site.yaml)
cd /opt/tojlo-com
fabrik wp plan

# Option C: explicit project path
fabrik wp plan --project /opt/tojlo-com
```

**Spec resolution priority** (highest to lowest):

1. `--project <path>/site.yaml`
2. `CWD/site.yaml` (when `CWD/project.yaml` has `type: wordpress`)
3. `specs/sites/<site_id>.yaml` (legacy fallback — prints deprecation warning)

**Output:**

```
✅ Plan generated: /opt/fabrik/build/sites/tojlo.com
📁 Build directory: /opt/fabrik/build/sites/tojlo.com
📄 Plan:      build/sites/tojlo.com/plan.json
📄 Blueprint: build/sites/tojlo.com/blueprint.resolved.yaml
📂 Manifests: build/sites/tojlo.com/manifests/
```

The plan computes per-stage input hashes. On subsequent runs, stages whose spec inputs
are unchanged will be flagged `skip_if_unchanged=true` and skipped automatically by `apply`.

---

## Phase 3 — Deploy to Coolify

Launch the WordPress Docker container. Do this before running `wp apply`.

```bash
# Generic Coolify deploy from spec file
fabrik apply specs/sites/tojlo.com.yaml
```

Or use the `fabrik deploy` shortcut if a `project.yaml` is present in the project folder:

```bash
cd /opt/tojlo-com
fabrik deploy
```

Wait for Coolify to report the app as `running` before proceeding.
Check status via Coolify dashboard or:

```bash
fabrik status specs/sites/tojlo.com.yaml
```

---

## Phase 4 — Apply WordPress Configuration

Configures the live WordPress installation: settings, theme, plugins, languages, pages,
menus, forms, SEO plugin, and analytics. Requires the container from Phase 3 to be running.

```bash
# Dry run first — shows what will happen, makes no changes
fabrik wp apply tojlo.com --dry-run

# Real apply
fabrik wp apply tojlo.com

# From project folder
cd /opt/tojlo-com && fabrik wp apply

# Re-run a specific stage that failed (bypasses skip_if_unchanged)
fabrik wp apply tojlo.com --force-stage plugins
fabrik wp apply tojlo.com --force-stage pages
```

### Stage execution order

Stages run sequentially. Each writes its result to `plan.json` so re-runs skip unchanged stages.

| # | Stage | What it does |
|---|---|---|
| 1 | **dns** | Verifies DNS is live and A record points to VPS |
| 2 | **settings** | Site title, tagline, admin email, timezone, permalink structure, user creation |
| 3 | **theme** | Installs and activates theme, applies brand colors and fonts |
| 4 | **plugins** | Installs and activates all plugins from spec (base + add, minus skip) |
| 5 | **languages** | Configures Polylang if `languages.additional` is non-empty |
| 6 | **pages** | Creates all pages from spec (home, about, services, contact, entity pages) |
| 7 | **menus** | Creates navigation menus and assigns to theme locations |
| 8 | **forms** | Creates contact forms (Contact Form 7 / WPForms) |
| 9 | **seo** | Configures RankMath: site name, social profiles, homepage SEO, schema |
| 10 | **analytics** | Injects GA4 / GTM tracking code |

> **Pending code gaps (not yet in `deployer.py`):** `post_deploy` (Gap 3 — GSC/Bing/IndexNow/GA4 via site-provisioner) and `monitoring` (Gap 2 — Uptime Kuma HTTP monitor). When implemented, they run at positions 11 and 12. After all stages, `_step_finalize()` flushes rewrite rules and object cache — this is a post-stage method, not a registered stage and cannot be targeted by `--force-stage`.

### Skip logic

After a successful stage run, its `last_success_hash` is written to `plan.json`.
On the next `apply`, if the spec inputs for that stage are unchanged, it is skipped.
Use `--force-stage <name>` to bypass this and force a re-run.

### Deployment report

After every `apply`, a report is written to:

```
build/sites/tojlo.com/reports/apply-report.json
```

Contains per-stage `success`, `skipped`, `duration_ms`, and `errors`.

---

## Phase 5 — Verify

Runs HTTP checks against the live site and generates a handoff report.

```bash
fabrik wp verify tojlo.com
```

Checks performed:

- Homepage returns HTTP 200
- Key pages return HTTP 200
- SSL certificate is valid
- Redirects are correct

Output:

```
✅ All checks passed
  ✅ https://tojlo.com → 200
  ✅ https://tojlo.com/about/ → 200
  ...
📄 Generating handoff report...
✅ Handoff generated: build/sites/tojlo.com/reports/handoff.md
```

The handoff report (`handoff.md`) summarises the site — domain, pages created, plugins,
credentials location — useful for handing off to a client or documenting the deployment.

---

## Phase 6 — Publish Content

Drains ready content briefs from the SEO service and publishes each as a WordPress page/post.
This is the ongoing content loop after the site is live.

### 6.1 Register the site in the SEO service (once)

```bash
fabrik seo site-register tojlo.com \
  --name "Tojlo" \
  --country-code tr \
  --language-code tr
```

### 6.2 Create an SEO keyword research job

```bash
fabrik seo job-create <site_id> "ai voice agents for clinics" \
  --page-type service \
  --country-code tr \
  --language-code tr
```

### 6.3 Run the job to generate briefs

```bash
fabrik seo job-run <job_id>
```

### 6.4 List ready briefs

```bash
fabrik seo briefs-list <site_id>
```

### 6.5 Publish briefs to WordPress

```bash
# Dry run — shows what would be published
fabrik content publish tojlo.com --dry-run --limit 5

# Real publish — processes up to 10 briefs
fabrik content publish tojlo.com

# Process more briefs in one run
fabrik content publish tojlo.com --limit 50
```

**What happens per brief:**

1. Brief is claimed from SEO service (prevents double-processing)
2. Content (title, body, meta description, schema) is generated via AI
3. Featured image sourced from Image Broker (Pexels/Pixabay)
4. WordPress page/post created via REST API
5. SEO plugin fields populated
6. Page published
7. n8n webhook fires → Telegram notification (`content-notify`)
8. Brief marked as published in SEO service

### 6.6 Update sitemap after publishing

```bash
fabrik domain sitemap tojlo.com https://tojlo.com/sitemap.xml
```

Resubmits to Google, Bing, and IndexNow.

---

## Day-2 Operations

### Re-deploy after spec change

```bash
# Regenerate plan (picks up spec changes, recomputes hashes)
fabrik wp plan tojlo.com

# Apply — only changed stages run
fabrik wp apply tojlo.com
```

### Force a specific stage

```bash
# Re-run plugins stage even if spec unchanged
fabrik wp apply tojlo.com --force-stage plugins

# Available stage names:
# Current (deployer.py): dns, settings, theme, plugins, languages, pages, menus, forms, seo, analytics
# Target (post gap-fix):  dns, settings, theme, plugins, languages, pages, menus, forms, seo, post_deploy, analytics, monitoring
```

### Add/update DNS records

```bash
# Add an A record
fabrik domain # (use DNSClient.add_record() in code, or via site-provisioner API directly)

# Add a subdomain
# -- currently via DNSClient.add_subdomain("tojlo.com", "api", "172.93.160.197")
```

### View Cloudflare zones

```bash
fabrik domain zones
```

### Check integration status

```bash
fabrik domain integrations tojlo.com
```

---

## Spec File Reference

A `site.yaml` is the single source of truth for a WordPress site. It is merged with
`templates/wordpress/defaults.yaml` and the chosen preset at load time.

**Spec resolution (three-priority strategy):**

```text
Priority 1: --project <path>/site.yaml       ← explicit flag
Priority 2: CWD/site.yaml                    ← auto-detect (needs CWD/project.yaml with type: wordpress)
Priority 3: specs/sites/<site_id>.yaml       ← legacy, triggers deprecation warning
```

**Minimal `site.yaml` structure:**

```yaml
preset: company          # templates/wordpress/presets/company.yaml

site:
  name: Tojlo
  domain: tojlo.com
  tagline: "AI solutions"
  admin_email: admin@tojlo.com
  timezone: Europe/Istanbul

brand:
  primary_color: "#1a1a2e"
  secondary_color: "#e94560"
  font_heading: "Space Grotesk"
  font_body: "Inter"

plugins:
  add:
    - yoast-seo
    - contact-form-7
  skip:
    - hello-dolly

pages:
  - title: Home
    slug: ""
    template: home
  - title: About
    slug: about
  - title: Contact
    slug: contact

navigation:
  primary:
    - label: Home
      page: ""
    - label: About
      page: about
    - label: Contact
      page: contact

seo:
  title_separator: "|"
  social:
    twitter: "@tojlo"

languages:
  enabled: false
```

**Spec merge rules:**

- `dict` keys: deep merge (site overrides preset, preset overrides defaults)
- `list` keys: **replace** by default; append only when `<key>_merge: append` is set
- `plugins.add`: always appends to base list
- `${VAR}` references: resolved from environment at load time

---

## Build Artifacts Reference

All artifacts live under `build/sites/<site_id>/`:

| File | Description |
|---|---|
| `plan.json` | Stage execution plan with hashes, skip flags, last run timestamps |
| `blueprint.resolved.yaml` | Fully merged spec (defaults + preset + site) — read-only reference |
| `manifests/plugins.json` | Final plugin list after layering rules |
| `manifests/pages.json` | Page manifest with slugs and parent relationships |
| `manifests/menus.json` | Menu structure |
| `manifests/checks.json` | Verification checks to run |
| `reports/apply-report.json` | Last apply result: per-stage success, duration, errors |
| `reports/verify-report.json` | Last verify result: per-URL HTTP checks |
| `reports/handoff.md` | Human-readable site handoff summary |

---

## Stage Reference

Each stage is a module at `src/fabrik/wordpress/stages/<name>.py` that exports
a single `apply(spec, wp_client, api_client, build_dir) -> StageResult` function.

### dns

- Reads `spec["site"]["domain"]` and `VPS_IP` env var
- Calls `DNSClient.add_subdomain()` if VPS_IP is set
- Skips silently in dry-run mode
- **Fails fast** if `VPS_IP` is not set and not dry-run

### settings

- Sets `blogname`, `blogdescription`, `admin_email`, `timezone`
- Sets permalink structure (`/%postname%/`)
- Creates additional admin/editor users from spec

### theme

- Installs theme from slug or URL via WP-CLI
- Activates theme
- Applies brand colors to `theme.json` / Customizer
- Applies heading and body font settings

### plugins

- Computes final plugin list: `defaults.base + spec.add − spec.skip`
- Deduplicates (last occurrence wins)
- Installs each plugin via WP-CLI
- Activates all installed plugins

### languages

- Configures Polylang if `languages.enabled: true`
- Installs language packs for each locale in `languages.locales`
- Sets default language from `languages.primary`

### pages

- Reads `spec["pages"]` and entity definitions (`services`, `features`, `products`, `locations`)
- Creates each page via WordPress REST API (`WordPressAPIClient`)
- Resolves parent page IDs for hierarchical pages
- Stores created page map in `stage_result.metadata["pages_created"]`

### menus

- Creates menus from `spec["navigation"]`
- Assigns each menu to its theme location
- Resolves page slugs to WordPress page IDs

### forms

- Creates Contact Form 7 or WPForms forms from `spec["contact"]` / `spec["forms"]`

### seo

- Configures Yoast SEO or RankMath:
  - Site name, separator, social profiles
  - Homepage SEO title and meta description
  - Schema type (Organization / LocalBusiness)
  - Breadcrumbs enabled

### analytics

- Injects GA4 measurement ID or GTM container ID
- Reads from `spec["seo"]["ga4_id"]` or `spec["seo"]["gtm_id"]`

### finalize (post-stage step)

Not a registered stage — cannot be targeted by `--force-stage`. Called automatically by `_step_finalize()` after all stages complete:

- Flushes WordPress rewrite rules (`wp rewrite flush`)
- Flushes object cache (`wp cache flush`)
- Writes final `apply-report.json` to build directory

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `VPS_IP` | ✅ | VPS public IP for DNS A records |
| `SITE_PROVISIONER_URL` | ✅ | site-provisioner base URL (`https://dns.vps1.ocoron.com`) |
| `SITE_PROVISIONER_API_KEY` | ✅ | API key for site-provisioner (`X-API-Key` header) |
| `WP_ADMIN_USER` | ✅ | WordPress admin username |
| `WP_ADMIN_PASSWORD` | ✅ | WordPress admin password (for REST API) |
| `COOLIFY_API_TOKEN` | ✅ | Coolify API token for deployments |
| `COOLIFY_BASE_URL` | ✅ | Coolify base URL |
| `SEO_API_URL` | for content | SEO service base URL |
| `TCO_API_URL` | for content | TCO (content generation) service URL |
| `IMAGE_BROKER_URL` | for content | Image Broker service URL |
| `CONTENT_WORKER_ID` | for content | Worker ID for brief claiming |
| `ANTHROPIC_API_KEY` | for AI content | Claude API key |
| `N8N_WEBHOOK_DEPLOY` | optional | n8n webhook for deploy notifications |
| `N8N_WEBHOOK_CONTENT` | optional | n8n webhook for content publish notifications |
| `FABRIK_EXEC_MODE` | VPS only | `local` on VPS (direct docker exec), `ssh` on WSL (default) |
| `UPTIME_KUMA_URL` | for monitoring stage | Uptime Kuma base URL (e.g. `https://status.vps1.ocoron.com`) |
| `UPTIME_KUMA_USERNAME` | for monitoring stage | Uptime Kuma username |
| `UPTIME_KUMA_PASSWORD` | for monitoring stage | Uptime Kuma password |

---

## Troubleshooting

### `FileNotFoundError: No site.yaml found`

`fabrik wp plan` or `fabrik wp apply` cannot find the spec.

- **Option A:** Pass the site_id: `fabrik wp plan tojlo.com` (requires `specs/sites/tojlo.com.yaml`)
- **Option B:** `cd` into the project folder and run without arguments (requires `project.yaml` with `type: wordpress` + `site.yaml`)
- **Option C:** `fabrik wp plan --project /opt/tojlo-com`

### `RuntimeError: Build directory missing`

`fabrik wp apply` ran before `fabrik wp plan`.

```bash
fabrik wp plan tojlo.com
fabrik wp apply tojlo.com
```

### Stage failed — how to retry

```bash
# Check the report
cat build/sites/tojlo.com/reports/apply-report.json | python -m json.tool

# Force re-run the failed stage
fabrik wp apply tojlo.com --force-stage <stage_name>
```

### DNS not ready after provision

```bash
# Check zone status
fabrik domain ready tojlo.com

# Check Cloudflare zones list
fabrik domain zones
```

Cloudflare propagation typically takes 1–5 minutes. If zone status is `pending`,
nameservers at the registrar may not have been updated yet.

### `SITE_PROVISIONER_API_KEY not set` warning

Add to `.env`:

```bash
SITE_PROVISIONER_API_KEY=<value of API_KEY in site-provisioner's .env on VPS>
```

### WP-CLI connection refused

WordPress container is not running. Check Coolify dashboard or:

```bash
fabrik status specs/sites/tojlo.com.yaml
```

Then wait for the container to become healthy before running `wp apply`.

### `content publish` claims briefs but publishes 0

Check:

1. `SEO_API_URL` is set and the SEO service is reachable
2. Briefs have status `ready` — check with `fabrik seo briefs-list <site_id>`
3. `WP_ADMIN_PASSWORD` is correct — test with `fabrik wp verify tojlo.com`
