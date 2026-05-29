# Deployment Procedures

**Last reviewed:** 2026-05-28
**VPS:** vps1.ocoron.com (172.93.160.197)
**Deploy method:** SSH + Docker Compose (direct to VPS — no intermediary platform)
**Deploy mechanism:** `fabrik apply` runs from WSL, connects to VPS via SSH, writes compose files, runs `docker compose up -d`

---

## Golden Rules

1. **All services are git-sourced. Always `git push` before `fabrik redeploy`.** Redeploy runs `git pull` on the VPS, which pulls from the GitHub remote configured in `/opt/<name>/.git/config` — not from your local WSL filesystem.
2. **DB connection strings use Docker DNS names**, never `localhost`: `postgres-main:5432`, `redis-main:6379`. Inside a container, `localhost` is the container itself, not the shared database.
3. **Never SIGHUP Authelia** — it exits. Always `docker restart authelia` after editing `/opt/authelia/configuration.yml`.
4. **No `ports:` in compose.yaml** — binding ports bypasses UFW and exposes services directly. All traffic routes through Traefik on the `coolify` Docker network.
5. **Every service must have `container_name:`** in its compose.yaml — provides stable names for `docker exec`, `docker inspect`, and Gatus monitoring. Without it, Docker generates random suffixed names.
6. **All `docker` commands on VPS require `sudo`** — root-owned containers and directories.
7. **The `.env` file on VPS is root-owned** at `/opt/<name>/.env`. Never edit it directly — use `fabrik apply` or `fabrik redeploy --refresh-infra` to update. Direct edits get overwritten on next deploy.

---

## How It Works — The Deploy Stack

```text
WSL (your laptop)                        VPS (vps1.ocoron.com)
────────────────                         ────────────────────
fabrik CLI                               /opt/<name>/
  │                                        ├── compose.yaml    ← written by deployer
  ├── SSHDeployer                          ├── .env            ← written by deployer
  │     │                                  ├── Dockerfile      ← from git repo or template
  │     ├── ssh("mkdir -p /opt/<name>")    └── src/            ← from git repo
  │     ├── scp compose.yaml → /tmp/
  │     ├── ssh("sudo mv /tmp/... → /opt/<name>/")
  │     └── ssh("cd /opt/<name> && sudo docker compose up -d")
  │
  ├── InfrastructureProvisioner            Docker Engine
  │     ├── postgres driver (CREATE DB)      └── container: <name>
  │     ├── redis driver (allocate index)        ├── network: coolify (external)
  │     ├── gatus driver (add endpoint)          ├── Traefik labels → HTTPS routing
  │     ├── glitchtip driver (create project)    └── healthcheck: /health
  │     ├── authelia driver (access rule)
  │     ├── backrest driver (backup plan)   Traefik (reverse proxy)
  │     ├── grafana driver (annotation)      └── routes *.vps1.ocoron.com → containers
  │     ├── meilisearch driver (index)
  │     └── prometheus driver (scrape job)
  │
  └── DeploymentVerifier
        └── HTTPS probe: https://<domain>/health → 200 OK
```

**Key principle:** The deployer writes files to the VPS via SCP (using a scp-to-tmp-then-sudo-mv pattern for root-owned paths) and runs Docker Compose commands via SSH. It never runs Docker commands locally. All state lives on the VPS filesystem at `/opt/<name>/`.

---

## Source Types

Every Fabrik spec declares a `source.type` that controls how code reaches the VPS:

| Source type | How code gets to VPS | Spec example | Used by |
|---|---|---|---|
| **git** | `git clone` / `git pull` on VPS from GitHub | `source: { type: git, repository: "https://github.com/...", branch: main }` | All 8 Fabrik microservices (captcha, image-broker, translator, etc.) |
| **template** | Fabrik renders compose.yaml from `templates/<type>/*.j2`, SCPs to VPS | `source: { type: template }` | New scaffolded services |
| **docker** | Deployer generates minimal compose.yaml from `source.image`, SCPs to VPS | `source: { type: docker, image: "nginx:latest", image_port: 80 }` | Single-image services |
| **local** | Compose.yaml already exists on VPS at `source.path`; deployer only writes .env | `source: { type: local, path: "/opt/my-app" }` | 13 services (captcha, file-api, translator, image-broker, etc.) |

**All production services are currently git-sourced or local-sourced.** Template and docker source types are used for initial scaffolding and one-off image deployments.

---

## Standard Workflows

### Redeploy an Existing Service (most common)

```bash
# 1. Edit code locally in WSL
cd /opt/<service>
# ... make changes ...

# 2. Commit + push to GitHub
git add -A && git commit -m "feat: <change>" && git push

# 3. Trigger redeploy (VPS pulls from GitHub, rebuilds, restarts)
fabrik redeploy <service-name>

# 4. Verify
curl -sS https://<service>.vps1.ocoron.com/health
```

**What `fabrik redeploy` does under the hood:**

1. `SSHDeployer.find_existing(name)` — checks `/opt/<name>/compose.yaml` exists on VPS
2. Detects source type by checking for `.git` directory on VPS
3. **Git-sourced** (all current services):
   - `ssh: cd /opt/<name> && sudo git pull` (pulls from GitHub remote, timeout 60s)
   - `ssh: cd /opt/<name> && sudo docker compose build` (rebuilds image, timeout 300s)
   - `ssh: cd /opt/<name> && sudo docker compose up -d` (restarts with new image, timeout 120s)
4. **Non-git** (template/docker/local):
   - `ssh: cd /opt/<name> && sudo docker compose up -d` (recreates only if config changed)

**Flags:**
- `--force` / `-f` — adds `--no-cache` to build (git) or `--force-recreate` to up (non-git)
- `--refresh-infra --spec PATH` — re-runs all infrastructure registrars without rebuilding the container (use when spec shape flags change)
- `--dry-run` — shows what would happen without doing it

### Deploy a New Service

```bash
# 1. Scaffold project structure
cd /opt
fabrik scaffold <name> --type python-api --description "<what it does>"
# Creates: /opt/<name>/ tree, specs/services/<name>.yaml, .env.example

# 2. Implement business logic
cd /opt/<name>
# ... write code, tests ...

# 3. Validate against Fabrik standards
fabrik validate-deploy /opt/<name>

# 4. Plan (dry-run — shows what will be created)
fabrik plan specs/services/<name>.yaml

# 5. Commit + push
git add -A && git commit -m "initial" && git push

# 6. Apply (creates everything: DNS, container, DB, monitoring, auth, backups, errors)
cd /opt/fabrik
fabrik apply specs/services/<name>.yaml
# --dry-run to simulate first
# --skip-health-check for initial deploys where /health may not be ready yet
# -s KEY=VALUE to pass secrets

# 7. Verify
curl -sS https://<name>.vps1.ocoron.com/health
```

`fabrik apply` is idempotent — re-running on an existing service updates compose.yaml, merges .env, and restarts only if config changed.

### Destroy a Service

```bash
# Dry-run first (always)
fabrik destroy specs/services/<name>.yaml --dry-run

# Real destroy (tears down everything fabrik apply created)
fabrik destroy specs/services/<name>.yaml -y

# Keep DNS records (useful if migrating, not deleting)
fabrik destroy specs/services/<name>.yaml --keep-dns -y

# Also drop the database (default: preserved for safety)
fabrik destroy specs/services/<name>.yaml --drop-data -y
```

**What `fabrik destroy` does:**

1. **Registrar teardown** (reverse order of provisioning):
   - prometheus → remove scrape job (first down, last up)
   - meilisearch → skipped (index preserved) unless `--drop-data`
   - authelia → remove access rule, restart authelia
   - glitchtip → delete project
   - grafana → skipped (annotations are informational, auto-expire)
   - backrest → remove backup plan
   - gatus → remove endpoint, restart gatus
   - **postgres → skipped** (database preserved) unless `--drop-data`
   - **redis → index slot released, data NOT flushed** unless `--drop-data`
2. **App teardown:**
   - `sudo docker compose down -v` (stops containers, removes volumes)
   - `sudo rm -rf /opt/<name>` (removes all app files)
   - `sudo docker image prune -f` (cleans dangling images)
3. **DNS teardown** (unless `--keep-dns`):
   - Removes A record from site-provisioner / Cloudflare

**Partial destroy** (surgical — remove specific registrars only):
```bash
fabrik destroy specs/services/<name>.yaml --partial gatus --partial backrest --dry-run
```

**State-driven destroy** (use state file instead of current spec shape):
```bash
fabrik destroy specs/services/<name>.yaml --use-state --drop-data -y
```

### Refresh Infrastructure Only (no rebuild)

When you change spec shape flags (e.g., add `needs_cache: true`) but the code hasn't changed:

```bash
fabrik redeploy --refresh-infra --spec specs/services/<name>.yaml
```

This re-runs all infrastructure registrars (postgres, redis, gatus, etc.) against the existing running container without rebuilding it.

---

## What `fabrik apply` Does — Phase by Phase

Source of truth: `src/fabrik/orchestrator/__init__.py:DeploymentOrchestrator.deploy()`

The orchestrator runs **5 phases** with state transitions: `VALIDATING → PROVISIONING → DEPLOYING → VERIFYING → COMPLETE`. Failure at any phase triggers `ROLLING_BACK` (automatic, unless `--keep-on-failure`).

### Phase 1 — VALIDATING (local, no VPS calls)

**Module:** `src/fabrik/orchestrator/validator.py:SpecValidator`

- Loads spec YAML via `spec_loader.load_spec()`
- Validates schema: required fields, `shape.*` flags, port uniqueness (PORTS.md), business model check (BUSINESS_MODEL.md)
- Computes `spec_hash` for idempotency
- Returns `(spec, spec_hash, warnings)`

### Phase 2 — SECRETS (local, no VPS calls)

**Module:** `src/fabrik/orchestrator/secrets.py:SecretsManager`

- Resolves secrets from: environment variables → project `.env` → `-s KEY=VALUE` flags → auto-generate (CSPRNG, 32-char `[a-zA-Z0-9]`)
- Populates `ctx.secrets` dict — these are layered on top of spec env vars during deploy

### Phase 3 — DNS PROVISIONING

**Module:** `src/fabrik/orchestrator/__init__.py:_provision_dns()`

- Parses domain into subdomain + base domain
- Creates A record via site-provisioner API (`DNSClient.add_subdomain()`)
- Falls back to Cloudflare API if site-provisioner is unavailable
- Tracks as `ctx.add_resource("dns", domain, zone=base_domain)` for rollback

### Phase 4 — DEPLOY (SSH to VPS)

**Module:** `src/fabrik/orchestrator/deployer_ssh.py:SSHDeployer`

This is the phase that creates or updates the container on VPS.

1. **Name validation** — strict regex `^[a-z0-9][a-z0-9-]{0,62}$` (shell injection prevention gate)
2. **Check existing** — `ssh: test -f /opt/<name>/compose.yaml` to detect update vs new deploy
3. **Dispatch by source type** — see [Source Types](#source-types) above
4. **For template/docker sources:**
   - Render compose.yaml (from Jinja2 templates or generated)
   - Validate against rule-pack constraints (see [Compose Validation](#compose-validation-rules))
   - Build `.env` via read-merge strategy (see [.env Handling](#env-handling))
   - SCP files to VPS using scp-to-tmp-then-sudo-mv pattern
   - `ssh: cd /opt/<name> && sudo docker compose up -d`
5. **For git sources:**
   - Clone (new) or pull (existing) from GitHub
   - Build `.env` via read-merge strategy
   - `ssh: sudo docker compose build && sudo docker compose up -d`
6. **For local sources:**
   - Verify compose.yaml exists at `source.path`
   - Build `.env` via read-merge strategy
   - `ssh: cd <path> && sudo docker compose up -d`
7. **Track resource** — `ctx.add_resource("compose", name)` for rollback (new deploys only)

### Phase 4b — INFRASTRUCTURE REGISTRARS (post-deploy, SSH to VPS)

**Module:** `src/fabrik/orchestrator/infrastructure.py:InfrastructureProvisioner`

Runs **after** the container is up. Each registrar is gated by the spec's `shape:` block:

| # | Registrar | Shape gate | What it does |
|---|---|---|---|
| 1 | **postgres** | `needs_database` | `CREATE DATABASE` + `CREATE USER` on postgres-main (does NOT inject `DATABASE_URL` — that comes from spec `env:` or `ctx.secrets`) |
| 2 | **redis** | `needs_cache` | Allocates Redis DB index; injects `REDIS_URL` via `deployer.inject_env()` |
| 3 | **gatus** | `is_public` + domain set | Adds HTTPS health endpoint as per-service YAML file in `/opt/monitoring/configs/gatus/apps/<name>.yaml`; restarts gatus |
| 4 | **backrest** | `has_persistent_data` | Creates Restic backup plan for the service's volume |
| 5 | **glitchtip** | `kind in {service, worker, wordpress}` | Creates GlitchTip project + DSN; injects `SENTRY_DSN` + `GLITCHTIP_DSN` via `deployer.inject_env()`; verifies via `docker inspect` |
| 6 | **grafana** | always (non-fatal) | Creates deployment annotation |
| 7 | **authelia** | `is_admin_dashboard` + domain set | Adds two_factor access rule; adds `^/api/` bypass only if `shape.has_bearer_api: true`; `docker restart authelia` |
| 8 | **meilisearch** | `has_search_feature` | Creates search index with configured UID and searchable attributes |
| 9 | **prometheus** | `exposes_metrics` | Adds scrape target for `/metrics` endpoint |

**`inject_env()` flow** (used by redis + glitchtip registrars): reads existing `.env` on VPS, merges new vars, writes back via SCP, runs `docker compose up -d` to restart with new env. This preserves all existing env vars — registrar injections never clobber each other.

**Override:** `infra: { <registrar>: false }` in spec disables a registrar. No `infra.foo: true` opt-in exists — shape flags control applicability.

### Phase 5 — VERIFY (HTTPS probe from WSL)

**Module:** `src/fabrik/orchestrator/verifier.py:DeploymentVerifier`

- Probes `https://<domain>/health` from WSL (goes through Cloudflare → Traefik → container)
- Retries with backoff until 200 OK or timeout
- Skipped with `--skip-health-check` or when spec has no domain (internal workers)
- Failure → triggers rollback

### Rollback (automatic on phase failure)

**Module:** `src/fabrik/orchestrator/rollback.py:RollbackManager`

- Iterates `ctx.created_resources` in **reverse order** (LIFO — most-recent first)
- Each resource type has a cleanup handler:
  - `compose` → `SSHDeployer.delete()` (`docker compose down -v` + `rm -rf /opt/<name>`)
  - `dns` → `DNSClient.delete_record_by_name()`
  - `gatus` → `remove_endpoint()`
  - `glitchtip` → `delete_project()`
  - `backrest` → `remove_backup_plan()`
  - `authelia` / `authelia_bypass` → `remove_access_rule()` (deduplicated per-domain)
  - `grafana_annotation_id` → `delete_annotation()`
  - `postgres` → **NOT dropped** (logs manual command only — deliberate policy)
  - `meilisearch` → **NOT deleted** (logs manual command only — deliberate policy)
- Errors during rollback are logged and accumulated — rollback never aborts, always tries every resource
- `--keep-on-failure` flag skips rollback entirely (for debugging failed deploys)

### Post-Deploy Hook (always runs, non-fatal)

**Module:** `src/fabrik/cli.py:_post_deploy_sync()`

1. `scripts/sync_projects.py` → updates `data/projects.yaml` registry
2. `scripts/update_vps_docs.py` → refreshes VPS status docs
3. `scripts/generate_vps_inventory.py --update` → refreshes VPS inventory

---

## .env Handling

The deployer uses a **read-merge strategy** for `.env` files:

```
Layer 1 (lowest): existing .env on VPS (preserves registrar-injected vars)
Layer 2:          spec env: block from the YAML
Layer 3 (highest): ctx.secrets (from SecretsManager — env vars, .env file, -s flags, generated)
```

**Why read-merge matters:** After initial deploy, registrars inject vars like `SENTRY_DSN`, `GLITCHTIP_DSN`, `REDIS_URL`, `DATABASE_URL` into the `.env` via `inject_env()`. A naive overwrite would lose these. The read-merge strategy reads the existing `.env` first, then layers spec env and secrets on top.

**When .env is written:**
- `fabrik apply` — always (new deploy: fresh; update: read-merge)
- `inject_env()` — called by redis + glitchtip registrars post-deploy (read-merge)
- `fabrik redeploy` — **does NOT touch .env** (only pulls code and rebuilds)

---

## Compose Validation Rules

The deployer validates every compose.yaml before deploying (module: `deployer_ssh._validate_compose()`). Rules sourced from `.windsurf/rules/core/30-ops.md`:

| Rule | Requirement | Reason |
|---|---|---|
| `platform` | `linux/amd64` on every service | VPS is AMD64 |
| `deploy.resources.limits.memory` | Required on every service | Prevents OOM on shared VPS |
| `ports` | Forbidden (no `ports:` section) | All traffic through Traefik; direct ports bypass UFW |
| `restart` | `unless-stopped` on every service | Auto-recovery after crashes |
| `container_name` | Required on every service | Stable `docker exec`/`docker inspect` targeting |
| `networks` | `coolify` declared as `external: true` | Shared network for inter-service communication + Traefik routing |
| `depends_on` | No `postgres-main` or `redis-main` | These are external services, not compose dependencies |
| Traefik labels | Must use `websecure` entrypoint (not `http`/`https`) | Coolify-era labels used wrong names |
| Traefik labels | `loadbalancer.server.port` required when `traefik.enable=true` | Traefik needs to know which port to route to |
| Environment | No `localhost` in `DATABASE_URL` or `REDIS_URL` | Would point at the container, not the shared DB |

Validation is **fatal in both real and dry-run deploys** (raises `DeployError`). There is no advisory mode — invalid compose files always block deployment.

---

## VPS Directory Layout

Every deployed service lives at `/opt/<name>/` on the VPS:

```
/opt/
├── captcha/              ← git-sourced service
│   ├── .git/
│   ├── compose.yaml
│   ├── .env              ← root-owned, written by deployer
│   ├── Dockerfile
│   └── src/
├── image-broker/         ← git-sourced service
│   └── ...
├── monitoring/           ← infrastructure stack (prometheus, grafana, etc.)
│   └── compose.yaml
├── authelia/             ← auth gateway
│   └── configuration.yml
├── gatus/                ← not directly here — config at /opt/monitoring/configs/gatus/
└── fabrik/               ← this repo (CLI + orchestrator)
    ├── specs/services/   ← spec YAML files
    ├── templates/        ← Jinja2 compose templates
    └── .fabrik/state/    ← deploy state files (JSON)
```

---

## Secrets Management

Secrets never go in git. They live in `.env` files on the VPS (root-owned) or in `/opt/fabrik/.env` (for CLI scripts).

| Secret | Where it lives | How to rotate |
|---|---|---|
| `SERVICE_INTERNAL_SECRET_KEY` (M2M auth) | `/opt/fabrik/.env` + every service's `/opt/<name>/.env` | Edit `/opt/fabrik/.env`, re-apply all specs |
| `GLITCHTIP_DSN` | per-service `.env` (injected by glitchtip registrar) | Re-run `fabrik redeploy --refresh-infra --spec <spec>` |
| `REDIS_URL` | per-service `.env` (injected by redis registrar) | Re-run `fabrik redeploy --refresh-infra --spec <spec>` |
| `DATABASE_URL` | per-service `.env` (from spec `env:` block or `ctx.secrets`, NOT injected by postgres registrar) | Update spec `env:` block, re-apply |
| Service-specific keys (API tokens, etc.) | per-service `.env` via spec `secrets:` block | Update `/opt/fabrik/.env` or env var, re-apply |

**Password policy:** 32-char `[a-zA-Z0-9]` via `secrets.choice()` (CSPRNG).

**Governance sync** (`scripts/sync_enforcement_to_projects.py`) copies enforcement scripts and governance files to all `/opt` projects for Fabrik compliance — it does not block secrets. Secret blocking is handled by `.gitignore` patterns and pre-commit hooks in individual projects.

---

## Health Checks

```bash
# Per-service health
curl -sS https://<service>.vps1.ocoron.com/health | jq .

# All Gatus monitors
curl -sS https://status.vps1.ocoron.com/api/v1/endpoints/statuses | jq '.[] | {name, status: .results[-1].success}'

# Container status from VPS
ssh vps 'sudo docker ps --format "{{.Names}}\t{{.Status}}"'

# Resource usage
ssh vps 'sudo docker stats --no-stream --format "{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"'
```

**Health endpoint contract:** `/health` must verify real deps (`SELECT 1` on DB, `PING` on Redis) — not return a static 200. `/health` is globally Authelia-bypassed — never protect it.

---

## Observability

| System | URL | What it shows | Auth |
|---|---|---|---|
| Grafana | `https://grafana.vps1.ocoron.com` | Dashboards, Loki logs, Prometheus metrics | Authelia |
| GlitchTip | `https://errors.vps1.ocoron.com` | Error tracking (Sentry-compatible) | Authelia |
| Gatus | `https://status.vps1.ocoron.com` | Public status page with health history | Public |
| Alertmanager → Telegram | (push) | Critical alerts: down, OOM, cert expiry | n/a |

---

## Troubleshooting

**Symptom: `fabrik redeploy` returns success but old code is running.**
Cause: forgot `git push`. VPS pulled the old GitHub state.
Fix: `git push && fabrik redeploy <service>`.

**Symptom: service can't reach postgres-main or redis-main.**
Cause: container on wrong Docker network, or `DATABASE_URL` uses `localhost`.
Fix: check `sudo docker inspect <container> | grep -A 5 Networks` — must be on `coolify` network. Check `.env` — must use `postgres-main:5432`, not `localhost`.

**Symptom: 401 from a service that should be public.**
Cause: Authelia caught it.
Fix: check `/opt/authelia/configuration.yml` access rules. After edits: `sudo docker restart authelia`.

**Symptom: Traefik 502 / 504.**
Cause: container crashed or `/health` timing out.
Fix: `sudo docker logs --tail 100 <container>`. Check `sudo docker ps` for restart loops.

**Symptom: redeploy didn't pick up new env vars.**
Cause: `fabrik redeploy` does NOT touch `.env` — only `fabrik apply` and `inject_env` do.
Fix: re-run `fabrik apply specs/services/<name>.yaml` to read-merge the new vars.

**Symptom: registrar not running (no Gatus endpoint, no GlitchTip project, etc.).**
Cause: spec `shape:` block missing the flag, or `infra: { registrar: false }` override.
Fix: add shape flag, run `fabrik redeploy --refresh-infra --spec <spec>`.

---

## Audit & Reconciliation

```bash
# Check which registrars are live vs expected for a spec
fabrik audit-registrars --spec specs/services/<name>.yaml

# Reconcile all specs against live VPS state
fabrik reconcile-all --yes

# Verify deploy health + registrar presence
fabrik verify <domain> --spec deploy
fabrik verify <domain> --spec registrars

# Surgical un-registration (without destroying the app)
fabrik destroy specs/services/<name>.yaml --partial gatus --partial backrest
```

---

## Post-Reboot Recovery

After a VPS reboot, containers auto-restart (`restart: unless-stopped`). Resource limits need re-applying:

```bash
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"
```

---

## Related Files

| File | Purpose |
|---|---|
| `docs/DEPLOYMENT_ARCHITECTURE.md` | Code-level architecture reference — every source file on the deploy path |
| `docs/operations/fabrik-lifecycle.md` | Runtime behavior during deploy/redeploy — data safety, downtime, .env merge |
| `docs/operations/disaster-recovery.md` | Backup restore procedures |
| `docs/operations/backup-strategy.md` | Backrest/Restic strategy |
| `src/fabrik/orchestrator/__init__.py` | Orchestrator main — `deploy()` method |
| `src/fabrik/orchestrator/deployer_ssh.py` | SSH deployer — file transfer + docker compose |
| `src/fabrik/orchestrator/infrastructure.py` | Registrar dispatch |
| `src/fabrik/orchestrator/destroyer.py` | Reverse teardown |
| `src/fabrik/orchestrator/rollback.py` | Automatic rollback on failure |

---

## Change Log

| Date | Change |
|---|---|
| 2026-05-28 | Full rewrite: Coolify API → SSH + Docker Compose deployer. All procedures updated. |
| 2026-05-08 | GlitchTip SDK integration; leaked secrets redacted; Grafana file-provisioning |
| 2026-05-07 | Promtail noise filter; Gatus stable DNS alias architecture |
