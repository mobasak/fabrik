# WordPress Deployment Workflow

**Last Updated:** 2026-05-18
**Canonical lifecycle reference:** [`docs/reference/fabrik-lifecycle.md`](../fabrik-lifecycle.md) — all 4 stages apply to WordPress.
**Canonical rules:** [`.windsurf/rules/62-wordpress.md`](../../.windsurf/rules/62-wordpress.md) — architecture contract.
**VPS:** `172.93.160.197` / `vps1.ocoron.com` — AMD EPYC-Genoa, 6 vCPU, 12 GB RAM.

---

## The WordPress Deploy Path

```
fabrik scaffold <name> --type wordpress --preset <preset>
    ↓
Edit site.yaml (brand, pages, services, plugins, languages)
    ↓
fabrik wp plan <site>
    ↓
fabrik wp apply specs/sites/<domain>.yaml
    ↓
Site LIVE with 13 stages completed + 5 registrars fired
```

That's it. Everything below is detail on what happens inside each step.

---

## Architecture

```
WSL (Control Plane)                    VPS (Execution Plane)
─────────────────────                  ─────────────────────
/opt/fabrik/                           Docker containers:
├── specs/sites/<domain>.yaml          ├── <domain>-wordpress-1 (php8.3-fpm-bookworm + Nginx)
├── src/fabrik/wordpress/ (engine)     ├── <domain>-db-1 (MariaDB 10.11)
├── templates/wordpress/ (presets)     └── redis-main (shared, Object Cache Pro)
└── fabrik CLI                         
                                       Shared services:
Communication:                         ├── Traefik (reverse proxy + LetsEncrypt)
├── SSH (FABRIK_EXEC_MODE=ssh)         ├── Gatus (uptime monitoring)
├── OR docker exec (=local, on VPS)    ├── GlitchTip (error tracking)
├── Coolify API (app creation)         ├── Backrest → Backblaze B2 (backups)
└── WordPress REST API (content)       └── Grafana + Prometheus (metrics)
```

**`FABRIK_EXEC_MODE` (T1.1):**
- `ssh` (default) — WSL wraps `docker exec` in `ssh vps ...` — use when running from WSL
- `local` — calls `docker exec` directly — use when running ON the VPS (cron, watchdog, Phase 5)

---

## Prerequisites

1. **VPS running:** Coolify, Traefik, redis-main, Gatus, GlitchTip, Backrest all operational
2. **DNS provisioned:** `fabrik domain provision <domain>` already run (Cloudflare zone, A record, CDN, WAF, GSC, Bing)
3. **Env vars set in `/opt/fabrik/.env`:**
   - `FABRIK_EXEC_MODE=ssh` (or `local` on VPS)
   - `WP_ADMIN_USER`, `WP_ADMIN_PASSWORD` (32-char CSPRNG, no "admin" username)
   - `DEEPL_API_KEY` (for AutoPoly auto-translation)
   - `COOLIFY_API_TOKEN`
   - `SERVICE_INTERNAL_SECRET_KEY` (M2M auth for internal APIs)

---

## Step 1: Scaffold

```bash
fabrik scaffold ocoron-com --type wordpress --preset company
```

Creates project folder with:
- `site.yaml` (from company preset, you customize)
- `compose.yaml` (image: `wordpress:php8.3-fpm-bookworm` + MariaDB 10.11 + Nginx)
- `Makefile` (ops targets: update, cache-flush, backup, harden, db-clean, warm-cache)
- AI governance files (CLAUDE.md, KILO_CLI_RULES.md, AGENTS.md, etc.)

---

## Step 2: Plan

```bash
fabrik wp plan ocoron-com
```

Resolves spec via 3-layer merge: `defaults.yaml` → `presets/company.yaml` → `site.yaml`

Outputs to `build/sites/ocoron-com/`:
- `plan.json` — per-stage input hashes (skip unchanged stages on re-run)
- `blueprint.resolved.yaml` — fully merged spec (read-only reference)
- `manifests/{plugins,pages,menus,checks}.json` — what each stage will create

---

## Step 3: Apply (13 stages)

```bash
fabrik wp apply specs/sites/ocoron.com.yaml
```

Runs sequentially. Each stage is idempotent (re-run safe). Blocking stages halt on failure.

| # | Stage | What it does | Blocking? |
|---|---|---|---|
| 1 | DNS | Sync A record + www CNAME, verify zone active | YES |
| 2 | Settings | blogname, tagline, email, timezone, permalinks, admin user | YES |
| 3 | Theme | Install + activate GeneratePress, apply brand colors/fonts | no |
| 4 | Plugins | Install + activate all profile plugins from local zips | YES |
| 5 | Languages | Polylang Pro config: EN + TR, directory URLs, AutoPoly → DeepL | no |
| 6 | Pages | Create via REST API: home, about, services/*, contact, blog, legal | no |
| 7 | Menus | Create nav menus, assign to theme locations | no |
| 8 | Forms | Create contact forms (Fluent Forms Pro) | no |
| 9 | SEO | RankMath: title, meta, schema, breadcrumbs, OG, verification codes | no |
| 10 | Post-deploy | Resubmit sitemap to all engines, retrieve GA4 measurement ID | no |
| 11 | Analytics | Inject GA4 + GTM tracking code | no |
| 12 | Monitoring | Gatus HTTP monitor + optional WP Cron monitor | no |
| 13 | Verify | 10 health checks: DNS, SSL, HTTP 200, sitemap, robots.txt, plugins active | no |

**Expected time:** ~5-7 min first deploy (includes Coolify container creation + SSH fallback if #9161 fires). Redeploys faster (image cached, unchanged stages skipped via hash).

---

## Step 4: Registrars (fired by `fabrik apply` based on shape)

For `wordpress` shape (`is_public: true`, `has_persistent_data: true`, `needs_database: true`):

| Registrar | What it creates |
|---|---|
| redis | Assigns `WP_REDIS_DATABASE` index on redis-main |
| gatus | HTTP monitor at `status.vps1.ocoron.com` |
| backrest | Backup plan → Backblaze B2 (wp-content + DB volumes) |
| glitchtip | Error tracking project + SENTRY_DSN injected |
| grafana | Deploy annotation |

NOT fired: postgres (WP uses per-site MariaDB), authelia (not admin dashboard), meilisearch (no search feature), prometheus (no /metrics endpoint).

State written to `.fabrik/state/<domain>.json` — source of truth for `fabrik destroy --use-state`.

---

## Step 5: Verify

```bash
fabrik verify <domain> --spec registrars    # all registrars present
fabrik audit-registrars --spec specs/sites/<domain>.yaml   # detailed per-registrar status
curl -sI https://<domain>/health            # if health endpoint exists
```

---

## Step 6: Content Pipeline (post-deploy, ongoing)

```bash
# One-time setup
fabrik seo site-register <domain>
fabrik seo job-create <domain> --keywords "your seed keywords"
fabrik seo job-run <job_id> --wait

# Daily (systemd cron on VPS)
fabrik content publish <domain> --limit 2
# → SEO brief → TCO generates article → Image Broker hero → WordPress publish → AutoPoly translates → sitemap resubmit → Telegram report
```

---

## Redeploy (after spec changes)

```bash
# Edit site.yaml
vim specs/sites/ocoron.com.yaml

# Re-plan (recomputes hashes, identifies changed stages)
fabrik wp plan ocoron-com

# Re-apply (only changed stages execute — hash-based skip)
fabrik wp apply specs/sites/ocoron.com.yaml
```

---

## Rollback

```bash
# Full teardown (reversible — DNS preserved)
fabrik destroy specs/sites/<domain>.yaml --use-state --drop-data --keep-dns

# Then re-apply from clean state
fabrik wp apply specs/sites/<domain>.yaml
```

---

## Operational Makefile Targets

Every WordPress project includes a Makefile:

```bash
make update          # WP core + plugin updates via WP-CLI
make cache-flush     # 4-layer atomic: Cloudflare → Nginx FastCGI → Redis → WP transients
make backup          # Trigger Backrest backup
make harden          # Verify security settings
make security-check  # Wordfence scan (if installed)
make warm-cache      # Purge CF + hit all sitemap URLs (8 parallel workers)
make rename-admin    # Rotate admin username
make db-clean        # Prune transients, spam, revisions, orphaned postmeta, optimize
```

---

## Container Naming

Convention: `<domain-slug>-wordpress-1` (e.g., `ocoron-com-wordpress-1`)

`ContainerResolver` in `src/fabrik/drivers/wordpress.py` auto-discovers by name pattern. Override via env var `WP_CONTAINER_NAME_<SLUG>` if needed (e.g., `WP_CONTAINER_NAME_OCORON_COM=ocoron-com-wordpress-1`).

---

## Security (automated via templates + rules)

All security is baked into templates and enforced by `.windsurf/rules/62-wordpress.md`:

- wp-config: DISALLOW_FILE_EDIT/MODS, FORCE_SSL, WP_HTTP_BLOCK_EXTERNAL, custom table prefix, DISABLE_WP_CRON
- Cloudflare WAF: 5 mandatory rules
- Nginx: security headers, xmlrpc blocked, /uploads/ PHP blocked, FastCGI cache
- REST API: /users blocked, anon non-GET blocked
- Rate limiting: wp-login.php 10/min/IP
- Admin: no "admin" username, 32-char password
- MU-plugins: footprint removal, version stripping

No manual security steps required. `fabrik wp apply` handles everything.

---

## See Also

- [`docs/reference/fabrik-lifecycle.md`](../fabrik-lifecycle.md) — canonical 4-stage lifecycle
- [`.windsurf/rules/62-wordpress.md`](../../.windsurf/rules/62-wordpress.md) — WordPress architecture rules
- [`docs/development/plans/wordpress/`](../../development/plans/wordpress/) — factory plan (7 files)
- [`templates/wordpress/schema/v1.yaml`](../../../templates/wordpress/schema/v1.yaml) — site.yaml schema
