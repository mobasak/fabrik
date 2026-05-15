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
# 0. (Optional, recommended — T3-01) Capture intent in a preplan markdown FIRST.
# Stage 1 of the lifecycle. The preplan becomes the single source of truth
# every downstream agent reads — saves re-deriving intent at every stage.
cd /opt/fabrik
fabrik preplan new <name>
# Edit docs/preplans/<today>-<name>.md — fill in 9 sections including VPS1
# inventory reminders, then hand off to scaffold via --from-preplan.

# 1. Scaffold (creates /opt/<name>/ with full structure)
cd /opt
fabrik scaffold <name> --type python-api --description "<what it does>"
# OR: fabrik scaffold <name> --from-preplan /opt/fabrik/docs/preplans/<today>-<name>.md
# (with --from-preplan, the preplan is copied into <project>/docs/preplan.md
#  and a `Preplan:` reference is appended to all 4 AI guardrail files —
#  AGENTS.md, CLAUDE.md, AGENTS-compact.md, .windsurfrules)
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
Single-image Application lost its alias on Coolify redeploy. Run `bash /opt/fabrik/scripts/vps_apply_limits.sh apply_alias <service>` (see `.windsurf/rules/55-observability.md` § "Gatus — Stable DNS Names" + `docs/reference/coolify-stable-aliases.md`).

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

**Upstream gate (T2-03 G-E2):** before `fabrik apply` ever reaches this phase, the staged spec passes through `scripts/final_gate.py` (the operator's pre-stage AI-review gate). The yaml-load block at line 471 now runs `fabrik.spec_loader.load_spec()` on any file under `specs/services/`, catching pydantic-model violations (invalid enum, wrong env type, missing required field) before the file ever lands. The orchestrator's Phase-1 validator does the same checks in-process at apply time, so the two layers are belt-and-braces.

### Phase 2 — PROVISIONING (local — secret resolution)
**Module:** `src/fabrik/orchestrator/secrets.py:SecretsManager`

- Resolves secrets from `--secrets KEY=VALUE` flags AND from `/opt/fabrik/.env`
- Builds the env dict that will be pushed to Coolify
- Validates no required secrets are missing

**No network calls in this phase.**

### Coolify v4 limits_memory gap (F5, 2026-05-16)

**Symptom:** A Fabrik microservice spec declares `resources.limits.memory: 512M` (or the pre-G1 form `resources.memory: 512M`). After `fabrik apply`, the running container has `HostConfig.Memory: 0` (unlimited) — Coolify ignores the spec value at compose-write time.

**Root cause:** Coolify v4.0.0-beta.459 stores `limits_memory` in its application config (`coolify-db.applications` table) but does NOT emit a `deploy.resources.limits` block in the `compose.yaml` it writes to `/data/coolify/applications/<uuid>/`. The compose Coolify generates for a `build_pack: dockercompose` git-source application is sourced from the project's repo `compose.yaml` — Coolify does NOT layer its own `limits_memory` on top.

**Permanent fix (per-service backfill):** add an explicit `deploy.resources.limits` block to each service's compose.yaml in its source repo:

```yaml
services:
  <service-name>:
    # ... existing config ...
    deploy:
      resources:
        limits:
          memory: 512M   # match spec.resources.limits.memory (or .memory)
          cpus: '0.5'    # match spec.resources.limits.cpus
```

Then `git add compose.yaml && git commit -m 'add memory/cpu limits' && git push && cd /opt/fabrik && fabrik redeploy fabrik-<name>`.

The python-api and node-api scaffold templates (`templates/python-api/compose.yaml.j2` and `templates/node-api/compose.yaml.j2`) already emit this block from `{{ resources.memory }}` and `{{ resources.cpu }}` — so NEW services scaffolded post-2026-04-19 carry the limit automatically. The 7 deployed Fabrik microservices (translator, image-broker, fabrik-proxy, site-provisioner, file-api, emailgateway, captcha — plus file-worker) predate that template and need manual backfill.

**Stopgap (2026-05-16):** `scripts/vps_apply_limits.sh` now applies the limits via `docker update --memory` to all 8 Fabrik microservices on every run. `docker update` is ephemeral — Coolify re-deploys drop the limit — so the script must be re-run after each Coolify redeploy until the per-service compose.yaml backfill lands. Manual rerun: `ssh vps "bash -s" < /opt/fabrik/scripts/vps_apply_limits.sh`. The script also auto-fires after VPS reboot via the `coolify-sentinel`/post-deploy pattern documented elsewhere in this file.

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

### Phase 3a — COOLIFY ALIAS REGISTRATION (T2-04 G-J3, optional)

**Module:** `src/fabrik/orchestrator/coolify_alias.py::add_alias`

Fires between Phase 3 and Phase 4 ONLY when the spec sets `coolify.alias: <friendly-name>` in its `CoolifyConfig` block. The orchestrator's `_maybe_register_coolify_alias(ctx, spec)` calls `add_alias(ctx.coolify_uuid, spec.coolify.alias)` which:

1. Reads `/opt/coolify-alias-watcher/aliases.json` via SSH+sudo cat.
2. No-ops if `aliases[coolify_uuid] == alias` already.
3. Otherwise atomically writes the merged map (`tee → /tmp/aliases.json.tmp` then `chown root:root + chmod 644 + mv`).
4. `sudo systemctl restart coolify-alias-watcher.service` (sub-second; unit has `Restart=always` and NO `ExecReload`).

The watcher's docker-events listener picks up the new prefix→alias mapping on next start. Non-fatal: alias-watcher failure logs a warning but never aborts deploy. Adds `ResourceRecord("coolify_alias", alias, ...)` to ctx so T4-01/T4-02 destroy can find it.

**Skipped for:**

- Specs without `coolify.alias` set (default `None` — covers all Service stacks and any Application whose container name doesn't need stable DNS aliasing).
- `refresh_infrastructure()` also calls this so adding `coolify.alias` to an existing spec and re-running picks it up.

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

On COMPLETE transition: `DeploymentOrchestrator._persist_state()` writes
`.fabrik/state/<spec_id>.json` (T2-01 G-F3). Captures the 8-field manifest
— `applied_at`, `coolify_app_name`, `coolify_uuid`, `domain`, `git_sha`,
`registrars_applied`, `spec_hash`, `spec_path` — that future
`fabrik audit-registrars` (T2-02) and `fabrik destroy --use-state` (T4-01)
read as the source-of-truth for what was actually applied. Failure here
is non-fatal (logged warning); the state file is best-effort metadata.
The same write happens on `refresh_infrastructure()` success. On destroy,
the file is moved to `.fabrik/state/_destroyed/<id>.json.<ts>` rather
than deleted — preserves audit trail.

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


### Gotcha 8: `/opt/monitoring/compose.yaml` is HYBRID — partly aggregated reference, partly source of truth

The 198-line file at `/opt/monitoring/compose.yaml` mixes two deployment lifecycles. **You must know which category a service belongs to before editing the file expecting changes to take effect.**

**Category A — Coolify-managed (~14 services):** grafana, loki, prometheus, promtail, alertmanager, gatus, cadvisor, netdata, node-exporter, meilisearch, gotenberg, browserless, glitchtip-web, glitchtip-worker. For these, Coolify stores its own `docker_compose_raw` per Service in its DB. **Editing the disk file changes nothing.** To extend their compose, edit via Coolify UI or API and trigger a Service redeploy.

**Category B — Host-managed sidecars (2 services):** `postgres-exporter`, `redis-exporter`. These were added via plain `docker compose up -d`. **For these, the disk file IS the source of truth** and `docker compose up -d --no-deps --force-recreate <name>` from `/opt/monitoring/` applies edits.

**Distinguishing:**
```bash
sudo docker inspect <container> \
  --format '{{ index .Config.Labels "coolify.serviceId" }} | {{ index .Config.Labels "com.docker.compose.project" }}'
```
- Empty serviceId + `project=monitoring` → Category B (host-managed, edit the file).
- Non-empty serviceId + `project=<UUID>` → Category A (find the Coolify Service compose).

**Diagnostic snippets:**
```bash
# Find a container's actual deployed mounts (works for both categories):
sudo docker inspect <name> \
  --format '{{ range .Mounts }}{{ .Type }}: {{ .Source }} -> {{ .Destination }}{{ println }}{{ end }}'

# For Category A — get Coolify's stored compose:
sudo docker exec coolify-db psql -U coolify coolify -At \
  -c "SELECT docker_compose_raw FROM services WHERE uuid = '<UUID>';"
```

**Pitfall 1 — running `docker compose up -d <svc>` for Category A:** creates **competing standalone containers** (since `container_name:` is set) without affecting the Coolify-managed ones. It also creates dangling volumes named `monitoring_*` from the file's top-level `volumes:` block via the depends_on chain.

**Pitfall 2 — bind-mount edits in the file for Category A:** silent no-op. The running container's mounts come from Coolify's stored compose, not the disk file.

**Cheaper workaround when you only need to add files under an existing bind mount:**
- Drop new files on the host inside the bind-mounted parent dir.
- They appear inside the container without any compose change.
- Example: Gap #4 Grafana dashboards used this — `/opt/monitoring/configs/grafana/provisioning` is already bind-mounted as `/etc/grafana/provisioning:ro`, so we placed `provisioning/json-dashboards/*.json` inside it. Only one Grafana restart was needed because Grafana loads provisioning **provider** yamls only at startup (the dashboard JSONs themselves auto-reload every `updateIntervalSeconds`).

**Hit during this session (2026-05-08):** A `docker compose up -d grafana` for Category A produced 1 orphan `loki` container + 3 dangling `monitoring_*` volumes that had to be cleaned up post-hoc. Later, a Category B operation (`up -d --no-deps --force-recreate redis-exporter`) worked cleanly because the `--no-deps` flag prevented the depends_on chain from triggering.
## Governance file propagation

**Last verified: 2026-05-08 — 41 projects, 0 failures.**

Committing to `/opt/fabrik` triggers the pre-commit hook `scripts/sync_enforcement_to_projects.py --force`, which copies the canonical governance files from `/opt/fabrik/.windsurfrules/`, `/opt/fabrik/AGENTS.md`, etc. into every project under `/opt/`.

**Targeted projects:** all directories under `/opt/` that are not:
- `_*` (underscore-prefixed, used for archives/internal — `_archive`, `_backups`, `_traycer`, etc.)
- `.*` (hidden)
- explicitly excluded (`.factory`, `.ssh`, `web_scraper`, `containerd`, `google`, `logs`)
- the fabrik repo itself

**41 projects synced as of 2026-05-08.** Previous sessions reported 34 because 7 projects (`gmailaccountcreator`, `image-generation`, `llm_batch_processor`, `namecheap`, `supplement-tracker-advisor`, `transcriber`, `ugc`) had not been `git init`'d and the operator had assumed git-tracking was a prerequisite. The script doesn't actually check for `.git`, so they were already being synced — but they had no commit history to detect drift against. They're now git-init'd to capture initial state.

**Expanding the exclude list:** edit `scripts/sync_enforcement_to_projects.py`, the `exclude_folders` set near `def main()`. Recently added: `containerd` (Docker runtime artifact dir, no write perm), `google` (Chrome install location), `logs` (generic logs dir, not a Fabrik project).

**Scaffold fixture relocation:** test/fixture scaffolds should live under `/opt/_archive/` (or anywhere starting with `_`) to be skipped by the propagator. The 5-month-old `/opt/_final-verify` was moved to `/opt/_archive/_final-verify` on 2026-05-08.


## Phase 4 Registrar Coverage Status (corrected 2026-05-09 — 2nd audit)

**Correction note:** A 1st-pass audit on 2026-05-09 incorrectly reported "NO driver implemented" for most registrars. That was wrong — the drivers DO exist and ARE dispatched by `DeploymentOrchestrator` during `fabrik apply`. The actual gap is different and captured below.

### Truth table (from `src/fabrik/orchestrator/infrastructure.py` + `destroyer.py` + `drivers/*.py`)

| # | Registrar | Driver size | `provision()` wired | `_destroy_*` | `_rollback_*` | Status |
|---|---|---|---|---|---|---|
| 1 | postgres | 11 KB (`drivers/postgres.py`) | ✅ `infrastructure.py:317` | ✅ `_destroy_postgres` | partial | OK |
| 2 | redis | **1 KB stub** (`drivers/redis.py`) | ✅ `:320` | ✅ `_destroy_redis` | ❌ | **driver incomplete** |
| 3 | gatus | 9 KB | ✅ `:323` | ✅ `_destroy_gatus` | ❌ | OK |
| 4 | backrest | 10 KB | ✅ `:326` | ✅ `_destroy_backrest` | ❌ | OK |
| 5 | glitchtip | 20 KB | ✅ `:329` (raises on DSN-verify failure) | ✅ `_destroy_glitchtip` | ❌ | OK |
| 6 | grafana | 10 KB | ✅ `:332` (non-fatal by contract) | ❌ **MISSING** | ❌ | **destroyer gap** |
| 7 | authelia | 19 KB | ✅ `:335` (sync hook propagates) | ✅ `_destroy_authelia` | ❌ | OK |
| 8 | meilisearch | 10 KB | ✅ `:338` | ✅ `_destroy_meilisearch` | ❌ | OK |
| 9 | prometheus | 14 KB | ✅ `:341` (SIGHUP) | ✅ `_destroy_prometheus` | ❌ | OK |

### How `fabrik apply` actually works today

Pipeline in `DeploymentOrchestrator.deploy()` (`orchestrator/__init__.py`):
1. Validate spec
2. Resolve secrets
3. Provision DNS (Cloudflare driver)
4. Deploy via Coolify API (`ServiceDeployer`)
5. **Provision infrastructure registrars** — `infrastructure_provisioner.provision(ctx)` dispatches all 9 registrars, each gated by shape attributes from the spec
6. Verify deployment health
7. Rollback on failure (currently incomplete — only DNS + Coolify rollback paths exist)

Registrar applicability is computed from `spec.shape`:

| Registrar | Runs when |
|---|---|
| postgres | `shape.needs_database` |
| redis | `shape.needs_cache` |
| gatus | `shape.is_public` AND `spec.domain` set |
| backrest | `shape.has_persistent_data` |
| glitchtip | `shape.kind in {service, worker, wordpress}` |
| grafana | always (non-fatal contract) |
| authelia | `shape.is_admin_dashboard` AND `spec.domain` set |
| meilisearch | `shape.has_search_feature` |
| prometheus | `shape.exposes_metrics` (or always, depending on driver — verify) |

`infra:` is **override-only** — `<registrar>: false` disables an otherwise-applicable registrar; there's no `infra.foo: true` opt-in. This shape-driven design means a service whose spec lacks `shape:` block triggers **zero registrars**.

### THE actual gap — pre-G1 specs lack `shape:`

The orchestrator architecture landed at G1 milestone (2026-05-05). All 8 services currently running on the VPS were deployed under **pre-G1 specs without a `shape:` block**:

| Service | Spec file | Has `shape:`? | Currently-wired registrars (manual) |
|---|---|---|---|
| captcha | `specs/services/captcha.yaml` | ❌ | gatus, glitchtip, authelia |
| image-broker | (similar) | ❌ | gatus, glitchtip, authelia |
| translator | (similar) | ❌ → ✅ post-T1-05 | postgres (`translator`, renamed from `translator_service` on 2026-05-15), gatus, glitchtip, authelia |
| emailgateway | (similar) | ❌ | gatus, glitchtip(idle), authelia |
| file-api | (similar) | ❌ | gatus, glitchtip, authelia, backrest |
| file-worker | (similar) | ❌ | glitchtip(idle), backrest |
| site-provisioner | (similar) | ❌ | postgres (site_provisioner), gatus, glitchtip, authelia |
| fabrik-proxy | (similar) | ❌ | postgres (proxy_management), gatus, authelia |

**No service has a per-service Prometheus scrape job today.** All 13 Prometheus jobs are infrastructure-level (node, cadvisor, redis-exporter, postgres-exporter, grafana, authelia, meilisearch). None scrape `<service>:8000/metrics`.

If any of the 8 services is redeployed via `fabrik apply` today, the orchestrator will:
- Re-deploy via Coolify API ✅
- Skip ALL 9 registrars ❌ (because shape-block is missing → applicability resolver returns 0 RUNS)
- The manual side-effects (postgres DBs, gatus endpoints, glitchtip projects, authelia rules) survive because nothing destroys them, but they drift from the spec over time.

### Backfill plan for the "perfect base image" goal

If the VPS is to be cloned as a base for upcoming systems, fix in this order:

1. **Backfill `shape:` blocks** for the 8 deployed services. Single-file edit per service. Without this, the registrar architecture can't act on them.
2. **Replace the redis stub** (`drivers/redis.py`) with full implementation including a central index registry (likely `data/registry/redis-allocations.json`). At scale, ad-hoc index assignment causes collisions.
3. **Add `_destroy_grafana`** to `destroyer.py` so destroyed services don't leave dashboards behind.
4. **Add `_rollback_*` handlers** for all 9 registrars in `rollback.py`. Today, a failed deploy mid-registrar leaves orphan side-effects.
5. **Add per-service Prometheus scrape jobs** — registrar code exists but has never been called for any service. After backfilling shape blocks, dry-run each spec to surface what's missing. **(Status 2026-05-15: T2-02's `audit-registrars` now surfaces this drift — `fabrik-proxy` reports `prometheus: missing` because the live setup uses an aggregated `fabrik-services` job rather than per-service jobs.)**
6. ✅ **DONE 2026-05-15 (T2-02):** `fabrik audit-registrars`, `fabrik reconcile-all`, `fabrik verify <domain> --spec registrars`, and `fabrik destroy --partial <reg>` are shipped. See `src/fabrik/audit.py` (per-registrar audit module mirroring each driver's transport) and the module-level `HANDLER_ARGS` / `HANDLER_FUNCS` exports in `orchestrator/destroyer.py`.
7. **Document central registries** (redis indexes, postgres users, GT project IDs, Backrest plan IDs) as single source of truth in `docs/infrastructure/vps-complete-inventory.md`.

### T2-01/T2-02 lifecycle commands (2026-05-15)

After every successful `fabrik apply` or `fabrik redeploy --refresh-infrastructure`, the orchestrator writes `.fabrik/state/<spec.id>.json` — an 8-field manifest of which registrars fired, what UUIDs they returned, when, against which git SHA. Built on this foundation:

| Command | Stage 3/4 of the workflow |
| --- | --- |
| `fabrik audit-registrars [--spec X] [--json]` | Verify Stage 3 auto-registration: each spec's shape-resolved registrars vs live VPS state. Exit 2 if missing. |
| `fabrik reconcile-all [--filter X] [--yes]` | Recover from drift: re-run `refresh_infrastructure` per spec under per-spec `file_lock`. |
| `fabrik verify <domain> --spec registrars` | Stage 4 postcondition gate: fails on any `missing` registrar. Pairs with the existing `--spec deploy` (HTTP `/health`). |
| `fabrik destroy <spec> --partial <reg>` (repeat) | Surgical un-registration without DNS/Coolify-app teardown. |

**Recommended full Stage 3→4 chain:**

```bash
fabrik apply <spec> \
  && fabrik verify <domain> --spec deploy \
  && fabrik verify <domain> --spec registrars
```
