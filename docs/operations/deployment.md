# Deployment Procedures

**Last reviewed:** 2026-06-15
**VPS:** vps1.ocoron.com (172.93.160.197)
**Deploy method:** SSH + Docker Compose (direct to VPS — no intermediary platform)
**Deploy mechanism:** `fabrik apply` runs from WSL, connects to VPS via SSH, writes compose files, runs `docker compose up -d --wait`

---

## Golden Rules

1. **Git-sourced services require `git push` before `fabrik redeploy`.** Redeploy runs `git pull` on the VPS, which pulls from the GitHub remote configured in `/opt/<name>/.git/config` — not from your local WSL filesystem. (Local-sourced services skip the git pull step.)
2. **DB connection strings use Docker DNS names**, never `localhost`: `postgres-main:5432`, `redis-main:6379`. Inside a container, `localhost` is the container itself, not the shared database.
3. **Never SIGHUP Authelia** — it exits. Always `sudo docker restart authelia` after config changes. (Config is `/config/configuration.yml` inside the container, bind-mounted from `/opt/authelia/config/configuration.yml` on the host — editing either path touches the same file. The authelia driver still writes via `docker cp` and reads via `docker exec cat`, so go through the driver rather than hand-editing.)
4. **No `ports:` in compose.yaml** — binding ports bypasses UFW and exposes services directly. All traffic routes through Traefik on the `fabrik` Docker network (renamed from `coolify` on 2026-05-31).
5. **Every service must have `container_name:`** in its compose.yaml — provides stable names for `docker exec`, `docker inspect`, and Gatus monitoring. Without it, Docker generates random suffixed names.
6. **All `docker` commands on VPS require `sudo`** — root-owned containers and directories.
7. **The `.env` file on VPS is root-owned** at `/opt/<name>/.env`. Never edit it directly — use `fabrik apply` or `fabrik redeploy --refresh-infra` to update. Direct edits get overwritten on next deploy.

---

## How It Works — The Deploy Stack

```text
WSL (your laptop)                        VPS (vps1.ocoron.com)
────────────────                         ────────────────────
fabrik CLI                               /opt/<name>/
  │                                        ├── compose.yaml    ← from deployer (template/docker) or git repo (git/local)
  ├── SSHDeployer                          ├── .env            ← written by deployer
  │     │                                  ├── Dockerfile      ← from git repo or template
  │     ├── ssh("mkdir -p /opt/<name>")    └── src/            ← from git repo
  │     ├── scp compose.yaml → /tmp/
  │     ├── ssh("sudo mv /tmp/... → /opt/<name>/")
  │     └── ssh("cd /opt/<name> && sudo docker compose up -d --wait")
  │
  ├── InfrastructureProvisioner            Docker Engine
  │     ├── postgres driver (CREATE DB)      └── container: <name>
  │     ├── redis driver (allocate index)        ├── network: fabrik (external)
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
| **git** | `git clone` / `git pull` on VPS from GitHub | `source: { type: git, repository: "https://github.com/...", branch: main }` | 11 services (site-provisioner, youtube, fabrik-citation-verifier, fabrik-test-* series, etc.) |
| **template** | Fabrik renders compose.yaml from `templates/<type>/*.j2`, SCPs to VPS | `source: { type: template }` | Scaffolded services (gate-*, test-*, guide-proj, etc.) |
| **docker** | Deployer generates minimal compose.yaml from `source.image`, SCPs to VPS | `source: { type: docker, image: "nginx:latest", image_port: 80 }` | Single-image services (fabrik-smoke-test) |
| **local** | Compose.yaml already exists on VPS at `source.path`; deployer only writes .env | `source: { type: local, path: "/opt/my-app" }` | 8 services (translator, job-agent, trading-core, seo, etc.) — image-broker was the 9th, retired 2026-06-02 |

**Production services are git-sourced or local-sourced.** Template and docker source types are used for scaffolding and one-off deployments.

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
3. **Git-sourced** (services with `.git` directory on VPS):
   - `ssh: cd /opt/<name> && sudo git rev-parse HEAD` (captures current commit as a rollback point BEFORE mutating, timeout 30s)
   - `ssh: cd /opt/<name> && sudo git pull` (pulls from GitHub remote, timeout 60s)
   - `ssh: cd /opt/<name> && sudo docker compose build` (rebuilds image, timeout 300s)
   - `ssh: cd /opt/<name> && sudo docker compose up -d --wait` (restarts with new image, blocks until healthy, timeout 120s)
   - **On health-check failure** (`up -d --wait` exits non-zero): auto-reverts with `git reset --hard <captured-sha>` → rebuild → `up -d --wait` to restore the last-known-good container, then raises `DeployError`. New code is NOT left live. If the rollback itself also fails, raises `DeployError` flagging that manual intervention is required.
4. **Non-git** (template/docker/local):
   - `ssh: cd /opt/<name> && sudo docker compose up -d --wait` (recreates only if config changed; `--force` appends `--force-recreate`)
   - **On health-check failure:** fails loudly with `DeployError` — there is no prior image tag to revert to, so no automatic rollback is possible for non-git sources.

**Flags:**
- `--force` / `-f` — adds `--no-cache` to build (git) or `--force-recreate` to up (non-git)
- `--refresh-infra --spec PATH` — re-runs all infrastructure registrars without rebuilding the container (use when spec shape flags change)
- `--dry-run` — shows what would happen without doing it (**`--refresh-infra` path only** — standard redeploy ignores this flag)

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
# --target-vps vps2 to land the container on a spoke instead of the hub

# 7. Verify
curl -sS https://<name>.vps1.ocoron.com/health
```

`fabrik apply` is idempotent — re-running on an existing service updates compose.yaml, merges .env, and restarts only if config changed.

#### Multi-host targeting (`--target-vps`)

The fleet is a hub (`vps1`) plus optional spokes (`vps2`, `vps3`). By default everything lands on `vps1`. To place an app **container** on a spoke, set `--target-vps`. Only the container moves — shared infrastructure (Postgres, Redis, monitoring, Authelia, DNS) stays on vps1.

```bash
fabrik apply specs/services/<name>.yaml --target-vps vps2
```

The same flag is available on `fabrik redeploy <app>` and `fabrik destroy <spec>`, so an app stays pinned to its host across its lifecycle.

**Resolution order** (highest to lowest) on `apply` / `redeploy` / `destroy`:

1. `--target-vps` CLI flag
2. State file `.fabrik/state/<id>.json::target_vps` (recorded from the last apply)
3. Spec `target_vps:` field
4. `vps1` (default)

(`fabrik plan` has no `--target-vps` flag — it reads the spec's `target_vps:` directly.) Internally a non-`vps1` target sets `FABRIK_VPS_SSH_HOST` so the SSH deployer connects to the spoke.

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

1. **Registrar teardown** (approximately reverse order of provisioning):
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
   - `sudo docker compose down` (stops + removes containers). Adds `-v` (also removes named volumes) **only with `--drop-data`**; a plain destroy preserves app-local volumes.
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

- Loads spec YAML via `SpecValidator.load_spec()` (validator's own method, not `spec_loader`)
- Validates schema: required fields (`name`, `template`), domain format + SSRF prevention, template exists, secrets format
- Computes `spec_hash` for idempotency
- Returns `(spec, spec_hash, warnings)`

### Phase 2 — SECRETS (local, no VPS calls)

**Module:** `src/fabrik/orchestrator/secrets.py:SecretsManager`

- Resolves secrets from: environment variables → project `.env` → auto-generate (CSPRNG, 32-char `[a-zA-Z0-9]`). CLI `-s KEY=VALUE` flags are parsed by the `apply` command and written into `os.environ`, so `SecretsManager` then picks them up via the environment-variable path (highest-priority source).
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
   - `ssh: cd /opt/<name> && sudo docker compose up -d --wait`
5. **For git sources:**
   - Clone (new) or pull (existing) from GitHub
   - Build `.env` via read-merge strategy
   - `ssh: cd /opt/<name> && sudo docker compose build` then `ssh: cd /opt/<name> && sudo docker compose up -d --wait`
6. **For local sources:**
   - Verify compose.yaml exists at `source.path`
   - Build `.env` via read-merge strategy
   - `ssh: cd <path> && sudo docker compose up -d --wait`
7. **Track resource** — `ctx.add_resource("compose", name, name=name)` for rollback (new deploys only)

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
| 9 | **prometheus** | `exposes_metrics` + domain set | Adds scrape target for `/metrics` endpoint |

**`inject_env()` flow** (used by redis + glitchtip registrars): reads existing `.env` on VPS, merges new vars, writes back via SCP, runs `docker compose up -d --wait` to restart with new env. This preserves all existing env vars — registrar injections never clobber each other.

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
  - `coolify` → legacy Coolify app removal (pre-migration deployments only)
  - `dns` → `CloudflareClient.delete_record_by_name()` (the rollback `dns_client` defaults to `CloudflareClient`; `DNSClient` itself only exposes `delete_record()`)
  - `monitor` → legacy monitor resource cleanup
  - `gatus` → `remove_endpoint()`
  - `glitchtip` → `delete_project()`
  - `backrest` → `remove_backup_plan()`
  - `authelia` / `authelia_bypass` → `remove_access_rule()` (deduplicated per-domain)
  - `grafana_annotation_id` → `delete_annotation()`
  - `redis` → `release_db_index()` (slot released, data NOT flushed — same policy as postgres)
  - `prometheus` → `remove_scrape_target()`
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

**Why read-merge matters:** After initial deploy, registrars inject vars like `SENTRY_DSN`, `GLITCHTIP_DSN`, `REDIS_URL` into the `.env` via `inject_env()`. A naive overwrite would lose these. The read-merge strategy reads the existing `.env` first, then layers spec env and secrets on top. (`DATABASE_URL` is NOT registrar-injected — it comes from the spec `env:` block or `ctx.secrets`.)

**When .env is written:**
- `fabrik apply` — always (new deploy: fresh; update: read-merge)
- `inject_env()` — called by redis + glitchtip registrars post-deploy (read-merge)
- `fabrik redeploy` — **does NOT touch .env** (only pulls code and rebuilds)

---

## Compose Validation Rules

The deployer validates compose.yaml for **template and docker** source types before deploying (module: `deployer_ssh._validate_compose()`). Git and local sources skip validation — their compose.yaml comes from the repo, not the deployer. Rules sourced from `.windsurf/rules/core/30-ops.md`:

| Rule | Requirement | Reason |
|---|---|---|
| `platform` | `linux/amd64` on every service | VPS is AMD64 |
| `deploy.resources.limits.memory` | Required on every service | Prevents OOM on shared VPS |
| `ports` | Forbidden (no `ports:` section) | All traffic through Traefik; direct ports bypass UFW |
| `restart` | Required (presence checked, not value) | Auto-recovery after crashes |
| `container_name` | Required on every service | Stable `docker exec`/`docker inspect` targeting |
| `networks` | `fabrik` declared as `external: true` (network was renamed from `coolify` on 2026-05-31) | Shared network for inter-service communication + Traefik routing |
| `depends_on` | No `postgres-main` or `redis-main` | These are external services, not compose dependencies |
| Traefik labels | Must use `websecure` entrypoint (not `http`/`https`) | Coolify-era labels used wrong names |
| Traefik labels | `loadbalancer.server.port` required when `traefik.enable=true` | Traefik needs to know which port to route to |
| Environment | No `localhost` in `DATABASE_URL` or `REDIS_URL` | Would point at the container, not the shared DB |

Validation is **fatal in real deploys** (raises `DeployError`). In dry-run mode, the deployer returns early before rendering or validating compose content.

---

## VPS Directory Layout

Every deployed service lives at `/opt/<name>/` on the VPS:

```
/opt/
├── site-provisioner/     ← git-sourced service
│   ├── .git/
│   ├── compose.yaml
│   ├── .env              ← root-owned, written by deployer
│   ├── Dockerfile
│   └── src/
├── monitoring/           ← infrastructure stack (prometheus, grafana, etc.)
│   └── compose.yaml
├── authelia/             ← auth gateway
│   ├── compose.yaml
│   └── config/
│       └── configuration.yml  ← bind-mounted to /config inside the container
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
| Grafana | `https://monitor.vps1.ocoron.com` | Dashboards, Loki logs, Prometheus metrics | Authelia |
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
Fix: check `sudo docker inspect <container> | grep -A 5 Networks` — must be on `fabrik` network (renamed from `coolify` 2026-05-31). Check `.env` — must use `postgres-main:5432`, not `localhost`.

**Symptom: 401 from a service that should be public.**
Cause: Authelia caught it.
Fix: check access rules via `sudo docker exec authelia cat /config/configuration.yml`. Config changes go through the authelia driver (`docker cp` into container). After any change: `sudo docker restart authelia`.

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
# NOTE: reconcile-all is currently broken (still imports CoolifyClient — Phase 11-2 migration pending)
# fabrik reconcile-all --yes

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
| `../DEPLOYMENT_ARCHITECTURE.md` | Code-level architecture reference — every source file on the deploy path |
| `docs/operations/fabrik-lifecycle.md` | Runtime behavior during deploy/redeploy — data safety, downtime, .env merge |
| `docs/operations/disaster-recovery.md` | Backup restore procedures + Backrest/Restic strategy |
| `src/fabrik/orchestrator/__init__.py` | Orchestrator main — `deploy()` method |
| `src/fabrik/orchestrator/deployer_ssh.py` | SSH deployer — file transfer + docker compose |
| `src/fabrik/orchestrator/infrastructure.py` | Registrar dispatch |
| `src/fabrik/orchestrator/destroyer.py` | Reverse teardown |
| `src/fabrik/orchestrator/rollback.py` | Automatic rollback on failure |

---

## Change Log

| Date | Change |
|---|---|
| 2026-06-15 | Documented `--target-vps` multi-host targeting + resolution order on apply/redeploy/destroy; fixed broken `DEPLOYMENT_ARCHITECTURE.md` relative link. |
| 2026-05-28 | Full rewrite: Coolify API → SSH + Docker Compose deployer. All procedures updated. |
| 2026-05-08 | GlitchTip SDK integration; leaked secrets redacted; Grafana file-provisioning |
| 2026-05-07 | Promtail noise filter; Gatus stable DNS alias architecture |
