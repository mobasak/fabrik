# Deployment Procedures

**Last reviewed:** 2026-05-08
**VPS:** vps1.ocoron.com (172.93.160.197)
**Coolify:** v4.0.0-beta.459 (web UI: `https://coolify.vps1.ocoron.com`)
**Deploy method:** Coolify API only — no manual `docker compose up` on VPS

---

## Golden Rules

1. **`fabrik redeploy` triggers Coolify, which pulls from GitHub.** Always `git commit && git push` BEFORE redeploying — Coolify reads the GitHub remote, not your local `/opt/`.
2. **Never `docker compose up -d` directly on the VPS.** Coolify owns lifecycle. Manual `up`/`down` strips Traefik labels and breaks routing on next redeploy.
3. **DB connection strings must use container DNS names**, never `localhost`: `postgres-main:5432`, `redis-main:6379`. Inside a container, `localhost` is the container itself.
4. **Never SIGHUP Authelia** — it exits. Always `docker restart authelia-hks48k8sg8o4co4co08co00o` after editing `/opt/authelia/configuration.yml`.
5. **No `ports:` in compose.yaml** — Docker bypasses UFW. Route everything through Traefik labels.

---

## Standard Deploy Workflow (existing service)

```bash
# 1. Edit code locally in WSL (/opt/fabrik or /opt/<service>)
# 2. Commit + push
cd /opt/<service>
git add -A
git commit -m "feat: <change>"
git push

# 3. Trigger Coolify redeploy
fabrik redeploy <service-name>

# 4. Watch logs (Loki via fabrik logs, or Coolify UI)
fabrik logs <service-name> --tail 100 --follow

# 5. Verify health
curl -sS https://<service>.vps1.ocoron.com/health
```

---

## New Service Deploy Workflow

```bash
# 1. Scaffold (creates /opt/<name>/ with full structure)
cd /opt
fabrik scaffold <name> --type python-api --description "<what it does>"
# Scaffold auto-emits: logger.py, internal_auth.py, metrics.py,
# glitchtip_init.py, /metrics endpoint, /health, structlog wiring,
# Dockerfile, compose.yaml, project.yaml, .env.example, AGENTS.md

# 2. Implement business logic in src/<package>/
cd /opt/<name>
# ... edit files ...

# 3. Validate against Fabrik standards
fabrik validate <name>

# 4. Plan (dry-run — shows what Coolify resources will be created)
fabrik plan <name>

# 5. Provision GlitchTip project + push DSN to Coolify env (optional)
bash /opt/fabrik/scripts/provision_glitchtip_project.sh <name>
# For Node services: add --platform javascript-node

# 6. Apply (creates Coolify Application/Service via API)
fabrik apply <name>

# 7. Coolify pulls from GitHub, builds, deploys. Watch:
fabrik status <name>
```

`fabrik apply` is idempotent — re-running on an existing service updates env vars and redeploys.

---

## Updating an Existing Service to Match New Scaffold Standards

When the scaffold gains new emitted files (e.g. the GlitchTip integration added 2026-05-08), bring older services up to date:

```bash
fabrik fix <service-name>
# Adds missing required files. Reference docs (4 files) always overwrite.
# AFCL.md is preserved if it exists (per-project friction log).
```

After `fabrik fix`: review the diff, commit, push, redeploy.

---

## Rollback

Coolify keeps the last known-good image. To revert:

```bash
# Option A — revert the commit, push, redeploy
cd /opt/<service>
git revert HEAD
git push
fabrik redeploy <service-name>

# Option B — Coolify UI: Application → Deployments → click previous deployment → "Redeploy"
```

`DeploymentRollback` class in `src/fabrik/deploy.py` runs reverse-order handlers automatically when `fabrik apply` fails partway through.

---

## Post-Reboot Recovery

After a VPS reboot, memory limits and Gatus DNS aliases need re-applying:

```bash
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"
```

This script:
- Reapplies Docker memory limits to all infra containers (Coolify strips them on restart)
- Re-attaches stable DNS aliases on the `coolify` network for single-image Applications (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`)
- Restarts Authelia if its config drifted

---

## Secrets Management

**Never commit secrets to git.** All secrets live in Coolify env (per service) or `/opt/fabrik/.env` (for CLI scripts).

| Secret | Storage | Rotation |
|---|---|---|
| `SERVICE_INTERNAL_SECRET_KEY` (M2M auth) | `/opt/fabrik/.env` + every service's Coolify env | Manual; rotate quarterly |
| `COOLIFY_API_TOKEN` | `/opt/fabrik/.env` only | Coolify UI → Profile → API Tokens |
| `GLITCHTIP_AUTH_TOKEN` | `/opt/fabrik/.env` only | GlitchTip UI → Settings → Auth Tokens |
| `GLITCHTIP_DSN` | per-service Coolify env (provisioner pushes via API) | Re-run `provision_glitchtip_project.sh` |
| Service-specific (Webshare, Apify, Cloudflare, etc.) | per-service Coolify env | Vendor dashboards |

**Pre-commit hook** (`scripts/sync_enforcement_to_projects.py`) blocks `.env`, `*.key`, `*.pem`, `*.crt` from being committed. GitHub push protection is the second line of defense.

---

## Health Check Commands

```bash
# Per-service health
curl -sS https://<service>.vps1.ocoron.com/health | jq .

# All Gatus monitors at once
curl -sS https://status.vps1.ocoron.com/api/v1/endpoints/statuses | jq '.[] | {name, status: .results[-1].success}'

# Container status from VPS
ssh vps 'sudo docker ps --format "{{.Names}}\t{{.Status}}"'

# Resource usage
ssh vps 'sudo docker stats --no-stream --format "{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"'
```

---

## Observability Per Deploy

When a deploy happens, errors flow to two places:

| Where | What | Auth |
|---|---|---|
| Loki (via Grafana `https://grafana.vps1.ocoron.com`) | Structured logs with correlation IDs | Authelia |
| GlitchTip (`https://errors.vps1.ocoron.com`) | Stacktraces, release tags, environment | Authelia |
| Prometheus (via Grafana) | RED metrics (rate, errors, duration) per service | Authelia |
| Alertmanager → Telegram | Critical alerts (down, OOM, cert expiry) | n/a |

The release tag in GlitchTip events comes from `GIT_SHA` env var — set this in CI or via Coolify env to enable per-commit error filtering.

---

## Troubleshooting

**Symptom: `fabrik redeploy` returns success but no new code in production.**
You forgot `git push`. Coolify pulled the OLD GitHub state. Fix: `git push && fabrik redeploy <service>`.

**Symptom: service can't reach `postgres-main`.**
Container is on the wrong Docker network, or compose.yaml uses `localhost` instead of `postgres-main`. Check: `sudo docker inspect <container> | grep -A 5 Networks`.

**Symptom: 401 from a service that should be public.**
Authelia caught it. Check `/opt/authelia/configuration.yml` access rules; reload via `docker restart authelia-...` (NOT SIGHUP).

**Symptom: Traefik 502 / 504.**
`/health` endpoint timing out, or container exited. `sudo docker logs --tail 100 <container>`.

**Symptom: Gatus shows alias as `unknown` / 0.0.0.0.**
Single-image Application lost its alias on Coolify redeploy. Run `bash /opt/fabrik/scripts/vps_apply_limits.sh apply_alias <service>` (see `CROSS_CUTTING_REQUIREMENTS.md §9`).

---

## Related Runbooks

- `docs/infrastructure/glitchtip-sdk-integration-setup.md` — error reporting setup
- `docs/infrastructure/grafana-provisioning-setup.md` — Grafana datasources via file provisioning
- `docs/infrastructure/promtail-noise-filter-setup.md` — Loki ingestion filtering
- `docs/operations/coolify-migration.md` — moving services between hosts
- `docs/operations/disaster-recovery.md` — restore from backup
- `docs/operations/backup-strategy.md` — Backrest/Restic strategy

---

## Change Log

| Date | Change |
|---|---|
| 2026-05-08 | GlitchTip SDK integration baked into scaffold; provisioner script added; runbook published |
| 2026-05-08 | 5 leaked secrets redacted from HEAD (`apps/fabrik-proxy/compose.yaml`, archive doc) |
| 2026-05-07 | Grafana datasource file-provisioning live; Promtail noise filter deployed |
| 2026-05-06 | Gatus stable DNS alias architecture (single-image fix) codified across 4 governance docs |

---

## What Fabrik Provides — Installed Services Inventory

Fabrik is a PaaS layer over Coolify on a single Ubuntu VPS (`vps1.ocoron.com`). Below is what's actually deployed and running, grouped by function. Container count: **44 running** as of 2026-05-08.

### Platform Layer (lifecycle + routing)

| Service | Image | Function |
|---|---|---|
| `coolify` | ghcr.io/coollabsio/coolify | Web UI + API for application lifecycle (create, deploy, destroy). Fabrik's `apply` driver calls this API. |
| `coolify-db` | postgres:15-alpine | Coolify's own state DB (apps, deployments, users) — internal to Coolify only |
| `coolify-redis` | redis:7-alpine | Coolify's own queue/cache — internal to Coolify only |
| `coolify-realtime` | coolify-realtime | WebSocket layer for the Coolify UI |
| `coolify-sentinel` | sentinel | Coolify's per-VPS health agent |
| `coolify-proxy` | traefik:v3.6 | **Active reverse proxy** — terminates TLS, routes by hostname, applies middlewares. All HTTPS traffic enters here. |
| `traefik` | traefik:v2.11 | Legacy proxy (older deploy) — kept for reference, not in active routing |

### Auth Boundary

| Service | Image | Function |
|---|---|---|
| `authelia` | authelia/authelia:latest | Forward-auth: protects admin dashboards (Grafana, GlitchTip, Coolify, etc.). Sessions stored in `redis-main:6379` DB index 3. **Never SIGHUP — always `docker restart`** to reload config. |

### Shared Application Databases

| Service | Image | Function |
|---|---|---|
| `postgres-main` | postgres:16-alpine | Primary application DB shared by all microservices. Each service gets its own DB (e.g. `glitchtip`, `proxy_management`). **Always reach via `postgres-main:5432` — never `localhost`.** |
| `redis-main` | redis:7-alpine | Shared cache + Authelia session store. **Reach via `redis-main:6379`**. |

### Observability Stack

| Service | Image | Function |
|---|---|---|
| `prometheus` | prom/prometheus:v3.2.1 | Metrics scraper — pulls `/metrics` endpoints from cadvisor, node-exporter, Fabrik services. Standalone (NOT in Coolify — Coolify strips network attachments on redeploy). 30d / 5GB retention. |
| `grafana` | grafana/grafana:11.5.1 | Dashboards. Datasources file-provisioned via bind mount `/opt/monitoring/configs/grafana/provisioning`. |
| `loki` | grafana/loki:3.4.2 | Log aggregation. 7d retention. |
| `promtail` | grafana/promtail:3.4.2 | Log shipper to Loki. Drops noise from `coolify-db`, `coolify-redis`, `coolify-realtime`, `coolify-sentinel`, `ocoron-com-backup-1`. |
| `alertmanager` | prom/alertmanager:v0.28.1 | Routes Prometheus alerts. `group_by: [alertname, container]`, repeat `4h` default / `30m` critical. |
| `apprise` | caronc/apprise | Alertmanager → Telegram bridge. |
| `node-exporter` | prom/node-exporter:v1.9.1 | Host-level CPU/memory/disk metrics. |
| `cadvisor` | gcr.io/cadvisor/cadvisor:v0.52.1 | Per-container metrics. `--housekeeping_interval=30s --docker_only=true`. |
| `netdata` | netdata/netdata:stable | Real-time per-host UI. 512MB / 7d retention. |

### Error Reporting

| Service | Image | Function |
|---|---|---|
| `glitchtip-web` | glitchtip/glitchtip:latest | Sentry-compatible error tracking UI + ingestion. Public via `errors.vps1.ocoron.com` (Authelia). Internal alias `glitchtip-web:8000` for SDK ingestion (bypasses Authelia). |
| `glitchtip-worker` | glitchtip/glitchtip:latest | Celery worker — processes incoming events. |

### Backup

| Service | Image | Function |
|---|---|---|
| `backrest` | ghcr.io/garethgeorge/backrest | Restic-based backup orchestrator. Plans created automatically by Fabrik for services with `shape.has_persistent_data`. |

### Status / Health Monitoring

| Service | Image | Function |
|---|---|---|
| `gatus` | twinproduction/gatus:latest | Public status page at `status.vps1.ocoron.com`. Uses stable Docker DNS aliases (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`) — never raw UUID container names. |

### Workflow / Automation

| Service | Image | Function |
|---|---|---|
| `n8n` | n8nio/n8n:latest | Visual workflow automation — webhooks, scheduled jobs, integrations. Authelia-protected. |

### Shared Utility Services (used by Fabrik microservices)

| Service | Image | Function |
|---|---|---|
| `meilisearch` (UUID name) | getmeili/meilisearch:v1.13 | Search index server. Per-service indexes. Internal alias `meilisearch:7700`. |
| `gotenberg` (UUID name) | gotenberg/gotenberg:8 | HTML/Markdown → PDF converter. Internal alias `gotenberg:3000`. |
| `browserless/chromium` (UUID name) | ghcr.io/browserless/chromium | Headless browser API for scraping/screenshots. Internal alias `browserless:3000`. |

### Fabrik Microservices (8 — all M2M-authed via `X-Internal-Token`)

| Service | Function |
|---|---|
| `fabrik-proxy` | Proxy management API for Webshare/Apify residential proxies (rotation, health). |
| `captcha` | CAPTCHA solving service (third-party API wrapper). |
| `image-broker` | Image processing/optimization broker. |
| `translator` | Multi-locale translation API (LLM-backed). |
| `emailgateway` | Email send relay (multiple providers behind one API). |
| `file-api` | User-facing file upload/download API. Auth via Supabase JWT (not M2M token). |
| `file-worker` | Background file-processing worker (companion to file-api). |
| `site-provisioner` | Provisions per-tenant WordPress/static sites. IP-allowlisted (no app auth). |

### Hosted End-User Applications

| Service Group | Containers | Function |
|---|---|---|
| `ocoron-com` | wordpress + mariadb + redis + nginx + backup (5 containers) | Marketing site at ocoron.com. WordPress on PHP 8.3-FPM, MariaDB 10.11, Nginx front, dedicated Redis. Backup container runs scheduled exports. |

### Project Type Catalog (`fabrik scaffold --type <T>`)

The scaffold supports **11 project types** (canonical list in `src/fabrik/scaffold.py:SCAFFOLD_TYPES`):

| Type | Stack | Use |
|---|---|---|
| `python-api` | FastAPI + structlog + Alembic | Internal/public REST APIs |
| `node-api` | Node.js + pino | JS/TS REST APIs |
| `saas-skeleton` | Next.js + TypeScript + Tailwind | Full SaaS apps with UI |
| `file-api` | FastAPI + Supabase JWT | User-facing file upload/download |
| `file-worker` | Celery / RQ | Background file processing |
| `wordpress` | WP + MariaDB | Marketing/content sites (5 sub-presets: saas, company, content, landing, ecommerce) |
| `docusaurus` | Docusaurus 3 | Documentation sites |
| `chrome-extension` | MV3 + TypeScript | Browser extensions |
| `mobile-app` | React Native / Expo | Mobile apps |
| `desktop-app` | Tauri / Electron | Desktop apps |
| `static-site` | Vite + plain HTML/JSX | Static sites |

Plus the WordPress presets give 16 effective scaffold variants.

---

## What Happens During Deploy — Phase-by-Phase

This is the actual sequence executed by `fabrik apply <spec>` (and by `fabrik deploy` when called from a project's own `project.yaml`). Source of truth: `src/fabrik/orchestrator/__init__.py:DeploymentOrchestrator.deploy()`.

The orchestrator runs **5 phases** with `DeploymentState` transitions: `VALIDATING → PROVISIONING → DEPLOYING → VERIFYING → COMPLETE`. Failure at any phase triggers `ROLLING_BACK` (auto, unless `--keep-on-failure`).

### Phase 1 — VALIDATING (locally on WSL, no VPS calls)
**Module:** `src/fabrik/orchestrator/validator.py:SpecValidator`

- Loads the spec YAML (or `project.yaml` for `fabrik deploy`)
- Validates schema: required fields, `shape.*` flags, port uniqueness against `PORTS.md`, business model duplicate check against `BUSINESS_MODEL.md`
- Computes `spec_hash` (used for idempotency — re-runs skip if hash unchanged)
- Returns `(spec, spec_hash, warnings)` — warnings are non-fatal (e.g. missing user guide flag)

**No network calls in this phase.**

### Phase 2 — PROVISIONING (local — secret resolution)
**Module:** `src/fabrik/orchestrator/secrets.py:SecretsManager`

- Resolves secrets from `--secrets KEY=VALUE` flags AND from `/opt/fabrik/.env`
- Builds the env dict that will be pushed to Coolify
- Validates no required secrets are missing

**No network calls in this phase.**

### Phase 3 — DEPLOYING (calls Coolify API on VPS)
**Module:** `src/fabrik/orchestrator/deployer.py:ServiceDeployer`

This is the only phase that creates the Application container. Sequence:

1. **`find_existing(name)`** — GET `/api/v1/applications?name=<name>` on Coolify. Idempotency check.
2. **`_resolve_project_server_uuids()`** — looks up the Coolify project + server UUIDs from the spec.
3. **`_resolve_environment_uuid()`** — resolves the target environment (production by default).
4. **`_resolve_private_key_uuid()`** — resolves the SSH key for git clone (if git source).
5. **`_create_deployment()`** — branches:
   - **Git source** → `_create_git_deployment()`: Coolify clones the GitHub repo on the VPS, builds (Dockerfile from repo root or `dockerfile_path`), and starts the container. The build happens **on the VPS** in Coolify's build environment.
   - **Inline source** → `_create_inline_deployment()`: pushes a docker-compose snippet directly to Coolify (used for single-image services like Meilisearch, Gotenberg).
6. **`_wait_for_app_status(uuid, max_wait=600)`** — polls Coolify's status endpoint until container reports running. Timeout = 10 min.
7. **`_wait_for_container(name, max_wait=90)`** — confirms the actual Docker container exists on VPS. Timeout = 90s.

**At end of Phase 3**: a running container exists on the VPS, attached to the `coolify` Docker network, with Traefik labels applied (Coolify auto-generates these from spec's `domain` and `port`).

### Phase 4 — PROVISIONING (post-deploy registrars on VPS)
**Module:** `src/fabrik/orchestrator/infrastructure.py:InfrastructureProvisioner`

The orchestrator dispatches to **9 infrastructure registrars**, each gated by a shape flag in the spec. Source order (`_REGISTRAR_ORDER`):

| # | Registrar | Runs when | Action on VPS |
|---|---|---|---|
| 1 | **postgres** | `shape.needs_database` | Creates database in `postgres-main` (idempotent CREATE DATABASE IF NOT EXISTS); creates app-specific user with restricted grants; injects `DATABASE_URL` into Coolify env. |
| 2 | **redis** | `shape.needs_cache` | Reserves a Redis DB index in `redis-main` from a shared registry; injects `REDIS_URL` with the assigned index. |
| 3 | **gatus** | `shape.is_public` AND `spec.domain` set | Adds an HTTPS endpoint to `/opt/gatus/config.yaml`; restarts gatus container. Public services get cert-expiry alerts. |
| 4 | **backrest** | `shape.has_persistent_data` | Creates a Restic backup plan named `<name>-data` pointing at the service's volume; configures retention. |
| 5 | **glitchtip** | always (when DSN provisioning enabled) | Creates a GlitchTip project via API (Sentry-compatible); rewrites DSN host to `glitchtip-web:8000`; pushes `GLITCHTIP_DSN` to Coolify env. |
| 6 | **grafana** | always (non-fatal by contract) | Creates/updates a per-service dashboard in Grafana from a template. Failure here does NOT fail the deploy. |
| 7 | **authelia** | `shape.is_admin_dashboard` AND `spec.domain` set | Adds a `two_factor` access rule to `/opt/authelia/configuration.yml`; adds an `^/api/` bypass rule for M2M traffic; **`docker restart authelia-...`** (NEVER SIGHUP — Authelia exits on SIGHUP). |
| 8 | **meilisearch** | `shape.has_search_feature` | Creates an index with the configured `uid`; sets searchable attributes from spec. |
| 9 | **prometheus** | always | Adds the service to `prometheus.yml` scrape jobs (target = `<name>:<metrics_port>`); reloads Prometheus via SIGHUP. |

**Override rule** (`infra:` block in spec): only valid value is `<registrar>: false` to **disable** an otherwise-applicable registrar. Any other value (or absence) means "run". Typo `flase` is rejected — no silent skips.

**Each successful registration is recorded in `ctx.created_resources`** so rollback can undo it in reverse order on failure.

### Phase 5 — VERIFYING (HTTP health check from outside VPS)
**Module:** `src/fabrik/orchestrator/verifier.py:DeploymentVerifier`

- Probes `https://<domain>/health` from WSL (via Cloudflare → Traefik → container)
- Waits up to a configurable timeout for `200 OK` response
- Skipped if `--skip-health-check` flag passed
- Skipped if spec has no `domain` (internal-only services)

If health check fails → `ROLLING_BACK`.

### Phase 6 — POST-DEPLOY HOOK (always runs, non-fatal)
**Module:** `src/fabrik/cli.py:_post_deploy_sync()`

After every successful (or failed) `apply` / `deploy` / `destroy`:

1. Runs `scripts/sync_projects.py` → updates `data/projects.yaml` registry from filesystem state.
2. Runs `scripts/update_vps_docs.py` in background → refreshes the `<!-- AUTO:* -->` blocks in `docs/operations/vps-status.md`, `docs/operations/vps-urls.md`, `docs/infrastructure/vps-complete-inventory.md` from live VPS state.

Errors here are logged but never fail the command.

### Rollback (automatic on any phase failure)
**Module:** `src/fabrik/orchestrator/rollback.py:RollbackManager`

- Iterates `ctx.created_resources` in **reverse order** (most-recent first)
- Each resource type has a corresponding cleanup driver (e.g. `postgres` → DROP DATABASE; `gatus` → remove endpoint; `glitchtip` → DELETE project)
- Errors during rollback are logged and accumulated; rollback never re-raises (always tries to clean as much as possible)
- `--keep-on-failure` flag skips rollback so you can inspect the broken state — manual cleanup required

### What this means in practice

| You ran | What hit the VPS |
|---|---|
| `fabrik plan <spec>` | Nothing. Read-only — prints what would happen. |
| `fabrik apply <spec>` | Phases 1-6 above. Container created, infra wired, health-checked, registry synced. |
| `fabrik redeploy <name>` | Calls Coolify API to re-pull from GitHub and rebuild. Skips Phases 1, 2, 4 — assumes spec hasn't changed. |
| `fabrik destroy <name>` | Inverse of apply: rollback all `ctx.created_resources`, then delete the Coolify Application. |
| `fabrik deploy` (in project dir) | Reads `project.yaml` → builds spec → runs `apply`. The "user-friendly" entry point. |
| `fabrik fix <name>` | Adds missing scaffold-emitted files (logger.py, internal_auth.py, metrics.py, glitchtip_init.py) without touching deploy state. |

### Source-of-truth files for this section

- `src/fabrik/orchestrator/__init__.py` — main `deploy()` method, phase transitions
- `src/fabrik/orchestrator/validator.py` — Phase 1
- `src/fabrik/orchestrator/secrets.py` — Phase 2
- `src/fabrik/orchestrator/deployer.py` — Phase 3 (Coolify API calls)
- `src/fabrik/orchestrator/infrastructure.py` — Phase 4 (registrar dispatch)
- `src/fabrik/orchestrator/verifier.py` — Phase 5
- `src/fabrik/orchestrator/rollback.py` — auto-rollback
- `src/fabrik/cli.py:_post_deploy_sync()` — Phase 6

---

## Known Operational Gotchas

These are environmental quirks discovered through real deploys. They affect every future deploy unless explicitly worked around.

### Gotcha 1: Coolify drops Docker network aliases on every redeploy

If your service or any service it talks to lives in Coolify and uses a friendly Docker DNS alias (`meilisearch`, `glitchtip-web`, `gotenberg`, `browserless`, etc.), expect every Coolify redeploy to delete that alias.

**What you'll see:** `dial tcp: lookup <alias> on 127.0.0.11:53: no such host` from any container that previously resolved it.

**Why:** Coolify's compose template only declares the timestamped UUID alias (`<uuid>-<timestamp>`). Friendly aliases were added externally via `docker network connect --alias` and don't survive container recreation.

**Fix until permanent solution lands:** after every redeploy of an affected service:
```bash
sudo docker network disconnect coolify <new-container-name>
sudo docker network connect --alias <friendly-name> coolify <new-container-name>
```

**Permanent fix:** add `networks: { coolify: { aliases: [<friendly-name>] } }` in the Coolify Application's custom compose block. See `docs/infrastructure/vps-complete-inventory.md` Issue #1.

### Gotcha 2: Authelia config has two locations — only one is loaded

The file at `/opt/authelia/config/configuration.yml` is a working copy. The file Authelia actually loads at startup lives in a Docker volume:
```
/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml
```

If you edit only `/opt/authelia/config/`, Authelia ignores your changes. Always edit the volume file (or both, then `docker restart authelia-...`). Never `SIGHUP` — Authelia exits.

### Gotcha 3: Adding a Node dep to package.json breaks `npm ci --include=dev`

If you add a new dependency by editing `package.json` only, the next deploy fails at `RUN npm ci --include=dev` because `npm ci` requires `package-lock.json` to be in sync. Always run `npm install --package-lock-only` after editing deps and commit both files together.

### Gotcha 4: Cloudflare auto-revokes leaked API tokens

If a Cloudflare API token gets pushed to a public GitHub commit (even if you immediately rewrite history), Cloudflare's leak detector finds it within minutes and auto-revokes it. Token status in the dashboard shows **"Exposed"**. The token is dead — rolling it via "Roll" generates a new value with the same scopes (1-click). For best practice: also narrow scope (the leaked token usually had broader perms than the service needed).

### Gotcha 5: Coolify API distinguishes Applications vs Services

The endpoints are NOT interchangeable:
- `/api/v1/applications/<uuid>/envs` — for git-built Apps (everything Fabrik scaffolds)
- `/api/v1/services/<uuid>/envs` — for Coolify-managed Services (one-shot DBs, marketplace items)

Calling the wrong one returns `HTTP 404 "Service not found"` even though the UUID is valid. Fabrik microservices, GlitchTip, Meilisearch, and most things deployed via fabrik are Applications — use the `/applications/` endpoint.

### Gotcha 6: Coolify env-var POST rejects `is_build_time` field

The Coolify v4 env-var POST API rejects `is_build_time` with `HTTP 422 "This field is not allowed."` Use only `key`, `value`, `is_preview`, `is_literal`. This was a breaking change between Coolify v4 versions; older docs/scripts using `is_build_time` need updating.
### Gotcha 7: Coolify keeps separate prod + preview env rows for every key

When rotating a secret in a Coolify Application's env, expect to find **two rows** for each key — one with `is_preview=false` (production) and one with `is_preview=true` (preview). A simple `PATCH /api/v1/applications/<uuid>/envs` with `{"key": K, "value": V}` only updates the matching row and silently leaves the other one stale.

**Symptom:** Next preview deploy uses the old value even though the UI showed "updated".

**Fix:** When rotating, iterate over current envs and PATCH every row whose key matches, preserving each row's existing `is_preview` flag:

```bash
# Pseudocode
for row in /api/v1/applications/<uuid>/envs:
    if row.key == TARGET:
        PATCH with {"key": TARGET, "value": NEW, "is_preview": row.is_preview, "is_literal": true}
```

This was hit on 2026-05-08 rotating `WEBSHARE_API_KEY` on fabrik-proxy — the prod row updated cleanly, the preview row was discovered only by listing all envs first.
