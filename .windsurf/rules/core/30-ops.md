---
activation: glob
globs: ["**/Dockerfile", "**/compose.yaml", "**/compose.yml", "**/docker-compose.yaml", "**/docker-compose.yml"]
description: Docker standards, deployment, infrastructure
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (deploy-plan step)
     GOAL: Docker, compose.yaml, Docker Compose via `fabrik apply` — base images, DNS, Traefik, resource limits, security
     TRAYCER USAGE: Referenced during deploy-plan and ticket-breakdown for infrastructure tickets. Injects as Context File.
     AGENT USAGE: Follow verbatim when writing Dockerfiles, compose files, or deployment config. -->

# Operations & Deployment Rules

**Activation:** Glob `**/Dockerfile`, `**/compose.yaml`, `**/compose.yml`
**Purpose:** Docker standards, deployment, infrastructure

> **Deploy = SSH + Docker Compose via `fabrik apply`. The Docker network is `fabrik`** (renamed from `coolify` 2026-05-31; `fabrik apply` REJECTS a compose that declares the old `coolify` network). No Coolify UI/API is in the loop — `fabrik` SSHes to the VPS and runs `docker compose`.

---

## Container Base Images (CRITICAL)

**Use Debian/Ubuntu, NOT Alpine:**

| Use Case | Base Image |
|----------|------------|
| Python apps | `python:<!--v:python_stable-->3.14<!--/v-->-slim-<!--v:debian_codename-->trixie<!--/v-->` |
| Node.js apps | `node:<!--v:node_lts-->24<!--/v-->-<!--v:debian_codename-->trixie<!--/v-->-slim` |
| General | `debian:<!--v:debian_codename-->trixie<!--/v-->-slim` |

The literals above are machine-owned (D-062 marker spans; source: `.windsurf/rules/versions.yaml`,
refreshed weekly). The Debian variant is a DELIBERATE fleet pin — it flips as one class commit when
the pinned release leaves full security support, never per-pack.

**Why not Alpine:** glibc compatibility, pre-built wheels, consistent behavior across dev/prod.

---

## Docker DNS — No `localhost` in Connection Strings (CRITICAL)

Inside a container, `localhost` resolves to the container itself, NOT the host or the shared DB. Use Docker network DNS names on the `fabrik` network:

| Variable | Wrong | Correct |
|---|---|---|
| `DATABASE_URL` | `...@localhost:5432/...` | `...@postgres-main:5432/...` |
| `REDIS_URL` | `redis://localhost:6379` | `redis://redis-main:6379` |

`localhost` is always wrong inside a container. The `*-main` Docker-DNS names in the "Correct" column are the **hub (vps1)** form; for a **spoke** target (`--target-vps vps2/vps3`) the registrar injects vps1's **mesh IP** (`10.99.0.1:5432` / `:6379`) instead — WireGuard carries no DNS, so `postgres-main`/`redis-main` SERVFAIL on a spoke. The app writes neither by hand; the registrar picks the right host from `target_vps` (see § Multi-host targeting).

**Verify before deploy:**

```bash
grep -E '^(DATABASE_URL|REDIS_URL)=' .env | grep localhost
# Must return nothing.
```

---

## Dockerfile Template (Python)

Multi-stage build with `uv` (mandated package manager). No `requirements.txt`, no raw `pip`.

```dockerfile
FROM python:<!--v:python_stable-->3.14<!--/v-->-slim-<!--v:debian_codename-->trixie<!--/v--> AS builder
WORKDIR /app
# gcc ONLY if a dependency without a wheel must compile; asyncpg ships wheels.
# NO libpq-dev — that's psycopg2, which 25-data-postgres.md bans.
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:<!--v:uv_version-->0.12.8<!--/v--> /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

FROM python:<!--v:python_stable-->3.14<!--/v-->-slim-<!--v:debian_codename-->trixie<!--/v-->
WORKDIR /app
# curl for HEALTHCHECK only. NO libpq5 (psycopg2).
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY . .

# Port fixed at build (Traefik routes by label). CMD + HEALTHCHECK use the SAME literal.
# Target /healthz — the DEP-FREE liveness probe (10-python § health split): a DB blip must
# degrade /health (readiness), never restart the container. Services scaffolded before the
# split serve only /health — keep that target until the endpoint exists.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

EXPOSE 8000
CMD ["uvicorn", "<package>.main:app", "--host", "0.0.0.0", "--port", "8000"]
# <package> = your package name — the scaffold emits src/<package>/main.py with
# pythonpath=["src"]; a flat `src.main:app` imports NOTHING on scaffolded projects.
```

**Notes:**
- `uv sync --frozen` uses `uv.lock` — deterministic, no resolution at build time. uv itself arrives via the pinned `COPY --from` (Astral's documented pattern) — an unpinned `pip install uv` would re-resolve a build tool every build and break the same determinism the lockfile buys.
- `.venv` is copied as a whole directory — no fragile `site-packages` path matching. **Both `FROM` lines must stay identical** — the venv is ABI-bound to the base (the shared marker spans keep them locked; keep them locked through hand-edits too).
- CMD is exec form — SIGTERM reaches uvicorn directly. If you need PORT-env flexibility: `CMD ["sh", "-c", "exec uvicorn <package>.main:app --host 0.0.0.0 --port ${PORT:-8000}"]` — the `exec` replaces the shell so SIGTERM is still signal-safe.
- HEALTHCHECK uses `localhost` correctly here — it runs inside the same container as the app.
- **No libpq-dev / libpq5** — asyncpg speaks the PG wire protocol directly and ships prebuilt wheels. `libpq` is for psycopg2, which `25-data-postgres.md` bans.

---

## compose.yaml Template

All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.

```yaml
services:
  api:
    build: .
    platform: linux/amd64
    environment:
      - DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres-main:5432/${DB_NAME}
      - REDIS_URL=redis://redis-main:6379/${REDIS_DB:-0}
      - SERVICE_INTERNAL_SECRET_KEY=${SERVICE_INTERNAL_SECRET_KEY}
    healthcheck:
      # Overrides the image HEALTHCHECK — if you declare it, keep target + port
      # identical to the Dockerfile's (the PORT-mismatch ban covers both pairs).
      test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'
    labels:
      - traefik.enable=true
      - traefik.http.routers.api.rule=Host(`api.${DOMAIN}`)
      - traefik.http.routers.api.entrypoints=websecure
      - traefik.http.routers.api.tls.certresolver=letsencrypt
      - traefik.http.services.api.loadbalancer.server.port=${PORT:-8000}
      - traefik.http.routers.api.middlewares=gzip@docker
    networks:
      - fabrik

networks:
  fabrik:
    external: true
```

**CRITICAL rules:**
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`deploy.resources.limits.memory` is mandatory.** A Fabrik invariant enforced by `deployer_ssh._validate_compose()` — `fabrik apply` refuses any compose service without a memory limit (prevents OOM on the shared VPS). The compose must carry the declaration explicitly.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- **`platform: linux/amd64` is mandatory.** VPS is x86_64.
- **No `depends_on: postgres-main`.** The shared database is a separate long-lived container on the `fabrik` network, not a service in your compose file. Docker DNS resolves `postgres-main` at runtime.
- **Traefik labels** set routing, TLS, and middleware. The scaffolder emits the correct labels; middleware per service category: admin UI = `authelia-forward@docker,gzip@docker`; API = `gzip@docker`; public = none.

---

## Multi-Service Compose — companion vs standalone worker

A service often needs a background companion (scheduler, queue worker). Pick the pattern by one test: **"does it ship from the same `git push` as the app?"**

- **Companion service** (same image, different command) — *yes, same codebase.* Declare it in the spec; the scaffolder emits a 2nd compose service that shares the app's build/image + env + `DATABASE_URL`/`REDIS_URL`, overriding only `command` + `container_name` + `memory`. **No Traefik labels** — companions are workers, not HTTP-routed.
  ```yaml
  companion_services:
    - id: <app>-scheduler
      command: ["node", "dist/scheduler.js"]   # same image, different entrypoint
      memory: 256M                              # REQUIRED — no default
      env_overrides: { ROLE: scheduler }        # optional, merged on top
  ```
  `memory` is mandatory (the per-service memory-limit invariant covers companions). Rendered by `node-api`/`python-api` via `templates/_partials/_companion_service.yaml.j2`.
- **Standalone `kind: worker`** (its own image/repo) — *no, separate codebase.* Give it its own spec + the `file-worker` scaffold; it deploys independently.

`source.type: git` projects (compose committed in the repo) hand-roll the companion as a 2nd service in their own `compose.yaml` — `companion_services` drives the *scaffold-emitted* path, not git-sourced composes. Either way, every service (parent + companion) carries its own memory limit and joins the `fabrik` network.

---

## Deployment Checklist

Before running `fabrik apply`:

- [ ] Dockerfile uses the pinned Debian `-slim` variant per § Container Base Images (not Alpine)
- [ ] HEALTHCHECK instruction present, targeting the dep-free `/healthz` (services predating the health split keep `/health` until `/healthz` exists)
- [ ] Readiness endpoint `/health` tests actual dependencies (`SELECT 1`, Redis `PING`, etc.) — Gatus/Traefik consume it
- [ ] All env vars documented in `.env.example`
- [ ] Credentials in project `.env`
- [ ] Port registered in `PORTS.md`
- [ ] compose.yaml uses `fabrik` network (external)
- [ ] compose.yaml has `deploy.resources.limits.memory` + `cpus`
- [ ] compose.yaml has `container_name: <name>` per service (mandatory; `_validate_compose()` refuses missing)
- [ ] compose.yaml has `platform: linux/amd64`
- [ ] compose.yaml has Traefik labels with `websecure` entrypoint
- [ ] No `ports:` section in compose.yaml (Traefik routes all traffic)
- [ ] Service added to `docs/SERVICES.md`
- [ ] **`docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are CURRENT and fleet-AI-consumable (D-065)** — the hub's deploy agent learns from THESE FILES what and how to deploy and which VPS services to set up (workers, systemd units, cron/Beat jobs, companions); projects cannot self-deploy, so this is the only channel that knowledge travels. A compose/worker/job change that isn't reflected there ships a silent misdeploy
- [ ] `.dockerignore` present (excludes `.env`, `.git`, `.venv`, `node_modules`)
- [ ] Traefik middleware set per service category — admin UI: `authelia-forward@docker,gzip@docker`; API: `gzip@docker`; public: none
- [ ] Compose env vars set: `SERVICE_INTERNAL_SECRET_KEY`, `DATABASE_URL` (using `postgres-main`), `REDIS_URL` (using `redis-main`)
- [ ] `/health` returns 200 against real deps; Gatus polls it for external availability

---

## Deployment Completeness — settle these at SPEC time, not at deploy time (CRITICAL)

The checklist above verifies **form**: every item is a property of a file you can read without deploying
anything. None of it asks the question that actually decides a deploy — *will this work when it comes up,
and is the infrastructure it claims actually attached?* Each class below is a real failure measured on this
fleet, and each was discovered at DEPLOY time when it was knowable at SPEC time. **A `shape:` flag is a
claim about RUNTIME, not a config value** — the registrar believes it and wires accordingly.

- [ ] **A watchdog is not optional.** `watchdog.enabled` defaults `true` for every kind and every project
      gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }`
      opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default
      to flip.
- [ ] **`exposes_metrics: true` ⇒ the metrics path actually SERVES.** The prometheus registrar scrapes
      `monitoring.metrics_path` (default `/metrics`); a wrong or unenabled path produces a job that
      404s forever while `fabrik apply` reports success — `_provision_prometheus` swallows failures as
      non-fatal and `add_scrape_target` only means "job appended to file". *Measured: zitadel declared
      `exposes_metrics: true` with `metrics_path: /debug/metrics`, served neither, and its target sat DOWN
      with `ServiceUnhealthy` firing for 2.5 days before anyone asked.* Verify the built image serves the
      path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a
      bare `curl` of a path you assumed.
- [ ] **`has_persistent_data: true` ⇒ name WHERE the data actually lives.** The backrest registrar
      hardcodes `paths = [/opt/<name>/data]` regardless of reality, so a service persisting to a NAMED
      VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and
      archives nothing. *Measured: `/opt/zitadel/data` is absent while the `zitadel-data` plan points at
      it.* If the data is a volume, say so in the spec comment and rely on the global `docker-volumes`
      plan; never let a service-named plan be mistaken for the protection.
- [ ] **Cold start: does the datastore initialise ITSELF?** Read the base image's entrypoint, the compose
      `command:`, and any baked init script — do not assume. If nothing initialises the schema, a
      health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to
      timeout. *Measured: trytond bakes an init script but sets no `command:`, and its base entrypoint is
      a bare `exec "$@"`.* An init the deploy cannot perform itself is a runbook step the plan MUST own.
- [ ] **A credential GENERATED during init goes stale the instant it is generated.** If a bootstrap script
      mints and prints a password, the value already in `.env` no longer matches — the service authenticates
      against nothing. Name the propagation step, or make the script consume the existing value.
- [ ] **Check the shared `fabrik` network for NAME and ALIAS collisions before naming a service.** The net
      is flat and shared fleet-wide; a name another stack already owns silently resolves to THEIR container.
      *Measured: a standalone `gotenberg` owns both the name and the alias, so a stack's own renamed
      `crm-gotenberg` still had to be pointed at explicitly — the code default would have hit the
      basic-auth'd neighbour and 401'd.*
- [ ] **First-boot DSN ordering.** The registrar injects `DATABASE_URL` POST-deploy, so a container that
      needs a real DSN at first boot crashes before it arrives. Either set `deploy.db_before_boot: true`
      (which pre-provisions via `create_database`, and therefore also registers the per-DB backup plan and
      the tracked-DBs entry) or document the two-pass explicitly in the runbook.
- [ ] **A step whose FAILURE is the designed path must say so, and carry `--keep-on-failure`.** Otherwise
      the rollback deletes resources the next step depends on — a failed `fabrik apply` rolls back the DNS
      record it just created. A step whose verify criterion cannot be met is a defect in the plan, not in
      the deploy.

---

## Redeploying Git-Sourced Apps

`fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.

**Correct sequence:**

```bash
git commit -m "..."
git push
fabrik redeploy <app>
```

---

## 12‑Factor V (Build, release, run) (CRITICAL)

**12‑Factor quotes:**
- "a release cannot be mutated once it is created. Any change must create a new release"
- each release has "a unique release ID"
- "it is impossible to make changes to the code at runtime, since there is no way to propagate those changes back to the build stage"

**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.

**❌ Forbidden:**
- `docker exec -it <container> vim /app/file.py`
- Editing source code directly on the VPS under `/opt/<app>`
- Changing environment variables with `docker exec <container> export VAR=value`
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)

**✅ Correct:**
- `git commit -m "..."`
- `git push`
- `fabrik redeploy <app>`
- Deploy‑time migrations as a one-shot `migrate` compose service (see § Release & Admin Processes)

---

## Multi-host targeting (`--target-vps`)

The fleet is a **vps1 hub + vps2/vps3 spokes**. `fabrik apply` / `plan` / `redeploy` / `destroy` all take `--target-vps <vpsN>` to choose where a service deploys.

**Resolution order** (highest wins): `--target-vps` CLI flag > state file `.fabrik/state/<id>.json::target_vps` > spec `target_vps:` field > **vps1** default.

Spokes are full deploy targets, not standby boxes — a spoke-targeted service runs its container on the spoke but **wires back to the shared vps1 data plane** over the WireGuard mesh. Those shared backing services always live on vps1 regardless of `target_vps`; only the app container moves. **The connection host differs by target — WireGuard routes IP packets but carries NO DNS, so the `*-main` Docker-DNS names SERVFAIL on a spoke:** a vps1 app reaches them by name (`postgres-main:5432`, `redis-main:6379`, `glitchtip-web:8000`) over the local `fabrik` bridge; a spoke app reaches them at vps1's **mesh IP** (`10.99.0.1:5432` / `:6379` / `:8000`, published mesh-only, same ports). The infra registrar picks the right host automatically from `target_vps` and injects it into `DATABASE_URL` / `REDIS_URL` / `SENTRY_DSN` — the app needs no special config. Source of truth: `docs/infrastructure/vps-urls.md` § Mesh URLs.

---

## Microservice URLs

| Environment | Pattern |
|-------------|---------|
| WSL | `http://localhost:PORT` |
| VPS Internal | `http://service-name:PORT` |
| VPS External | `https://service.vps1.ocoron.com` |

---

## 12‑Factor X (Dev/prod parity)

**12‑Factor quote:**
- "The twelve‑factor developer resists the urge to use different backing services between development and production" — use the same type AND version.

**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.

**❌ Forbidden:**
- SQLite in WSL → PostgreSQL on VPS
- Python `dict` or `cachetools` in WSL → Redis on VPS
- Different PostgreSQL major versions (14 in dev, 15 in prod)
- Mock/stub backends in dev that don't exist in prod

**✅ Correct:**
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
- Parity is about MAJOR VERSION + engine, not the distro layer of an upstream image (native WSL PostgreSQL at the same major satisfies it — see `25-data-postgres.md` § Local Development)
- Connection strings identical (`postgres-main:5432`, `redis-main:6379`)

---

## Architecture Requirement

VPS1 uses x86_64 (amd64). Verify image support:

**Before building images:**

```bash
python scripts/container_images.py check-arch <image:tag>  # Fabrik project only
```

Ensures base images support amd64 (required for VPS deployment).

**Note:** Child projects don't have this script — use Docker Hub/registry docs to verify amd64 support.

**If script missing:** Check `prebuilt-app-containers.md` manually or skip and flag.

---

## Docker Port Security (CRITICAL)

Docker bypasses UFW by inserting NAT rules in `PREROUTING`/`FORWARD` chains. The `DOCKER-USER` iptables chain is the **only** place to filter forwarded traffic before it reaches containers.

**Rules (enforced via `/etc/systemd/system/iptables-docker-user.service` on VPS):**

| Rule | Effect |
|------|--------|
| Allow established/related | Don't break existing sessions |
| Allow Docker internal nets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) | Container-to-container OK |
| Allow ports 80, 443 | Traefik front door |
| DROP all other external traffic | Blocks raw port access to containers |

(The legacy Coolify Realtime ALLOW rules for 6001/6002 were removed in the 2026-05-31 cleanup sweep — Coolify is decommissioned.)

**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.

**Exception:** Only Traefik (80/443) may bind to host ports.

---

## Authelia SSO (Forward Auth)

All admin dashboards are protected by Authelia (`auth.vps1.ocoron.com`) via Traefik forward-auth middleware.

**Service categories:**

| Category | Auth Mechanism | Examples |
|----------|---------------|----------|
| Public | None (bypass) | `ocoron.com`, `status.vps1.ocoron.com` |
| Admin dashboards | Authelia (2FA) | `auto` (n8n), `monitor` (Grafana), `backup` (Backrest), `notify` (Netdata removed 2026-05-30 → Grafana/cAdvisor) |
| API services | `X-Internal-Token` header | `site-provisioner` (the only live Fabrik microservice; `pdf`/`captcha`/`proxy`/`translator`/`files-api`/`emailgateway`/`dns`/`images` all retired) |

**Adding Authelia to a new admin service:**

```yaml
labels:
  - traefik.http.routers.<name>.middlewares=authelia-forward@docker
```

**Adding a new API service (bypass Authelia, use token):**

1. Add the domain to Authelia's `access_control.rules` bypass list in `/opt/authelia/config/configuration.yml`
2. Add `X-Internal-Token` validation middleware to the service
3. Restart Authelia: `docker restart <authelia-container>` (find name: `sudo docker ps --filter name=authelia --format '{{.Names}}'`)

**Authelia does NOT hot-reload on SIGHUP** — the process exits on signal. Always restart the container after any `configuration.yml` edit. `docker compose ... restart` works too; SIGHUP-only approaches do not.

**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.

---

## Traefik Entrypoint Names

The VPS Traefik uses these entrypoint names:

| Entrypoint | Port | Usage |
|------------|------|-------|
| `web` | 80 | HTTP, redirect to HTTPS |
| `websecure` | 443 | HTTPS with Let's Encrypt |

**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Alpine base image (OUR app images) | the pinned Debian `-slim` variant per § Container Base Images (glibc, prebuilt wheels). *Scope: images we BUILD; upstream official images (`postgres`, `redis`) ship self-contained and may be Alpine-based* |
| `libpq-dev` / `libpq5` in Dockerfile | Omit — asyncpg needs no libpq (psycopg2-only; banned per `25-data-postgres.md`) |
| `ports:` in compose / host-port binding | Traefik routing — only 80/443 bind host |
| `localhost` in container connection strings | Docker DNS `postgres-main` / `redis-main` on the hub — or vps1's mesh IP `10.99.0.1` on a spoke (registrar-injected; see § Multi-host targeting) |
| Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app | Single `DATABASE_URL` (see `10-python.md` § Config) |
| `depends_on: postgres-main` | None — DB is a separate shared container on the `fabrik` network |
| `http` / `https` Traefik entrypoints | `web` / `websecure` (those entrypoints do not exist) |
| Protecting `/health` with Authelia | `/health` always bypasses auth (Gatus/Prometheus need it) |
| Missing `deploy.resources.limits.memory` | Mandatory — `fabrik apply` rejects it (`deployer_ssh._validate_compose()`) |
| Missing `platform: linux/amd64` | Mandatory — VPS is x86_64 |
| `sh -c` CMD without `exec` (breaks SIGTERM) | Exec-form CMD, or `sh -c "exec ..."` |
| Manual VPS edits / registrar fix-ups | `fabrik apply` / `reconcile-all` (spec-driven) |
| `fabrik redeploy` without `git push` | `commit → push → redeploy` (the VPS runs `git pull` from the remote) |
| PORT mismatch between CMD and HEALTHCHECK | Both must use the same literal port value |
| Any Traefik `loadbalancer.sticky.*` label | Redis session store — processes are share-nothing; session state goes to `redis-main` with a TTL |

---

## 12‑Factor XII (Release & admin processes) (CRITICAL)

**12‑Factor quotes:**
- "one-off admin processes should be run in an identical environment as the regular long-running processes of the app"
- "run against a release, using the same codebase and config"
- "admin code ships with application code"

**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).

**❌ Forbidden:**
- Running migrations from laptop: `alembic upgrade head` (against prod DB)
- `docker exec -it <live-container> alembic upgrade head`
- Auto-running migrations in app startup/`lifespan` (`asynccontextmanager`)
- Running admin tasks in the main app process

**✅ Correct:**
- `docker compose run --rm <svc> alembic upgrade head` (against deployed environment)
- A one-shot **`migrate` compose service** the app services gate on:
  `depends_on: {migrate: {condition: service_completed_successfully}}`. Same image, same env, runs to
  completion and exits. The deployer's only container step is `docker compose up -d --wait`
  (`deployer_ssh.py:239`), and `up` honours `depends_on` — so this is automatic, with no operator step
  and no mechanism the platform lacks. A single `migrate` service also cannot be multiplied by
  `deploy.replicas` on `api`, so the Alembic version-table race is **structurally impossible** rather
  than merely avoided. Non-zero exit is the deployer's rollback trigger.
- Separate admin container/image for heavy admin tasks (same codebase)

> **Two mechanisms were struck from this list on 2026-08-28 because they do not exist** (transdoc
> `01M14BK0JD`, verified against `/opt/fabrik` before and after filing): **`fabrik run`** — the real CLI
> answers `Error: No such command 'run'`; and **`.fabrik/hooks/post-deploy/`** — the literal string appears
> **nowhere** in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`.
> This is the expensive kind of wrong: an agent following it writes `.fabrik/hooks/post-deploy/migrate.sh`,
> sees a file that looks exactly like a migration step, and ships a deploy where migrations never run —
> the rule producing the very defect it exists to prevent. Do not re-add either without a `path:line` in
> `src/fabrik/` that executes it.

**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.

---

## 12‑Factor II (Dependencies — never assume a system tool exists) (CRITICAL)

**12‑Factor quotes:**
- "A twelve-factor app never relies on implicit existence of system-wide packages"
- "if the app shells out to a system tool, that tool should be vendored into the app"

**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

**Concrete failure this prevents:** `subprocess.Popen(["ffmpeg", …])` works in WSL (ffmpeg on the dev's PATH) and raises `FileNotFoundError` in the container.

**❌ Forbidden:**
- `subprocess.Popen(["ffmpeg", "-i", input, output])` (no Dockerfile install)
- `subprocess.Popen(["convert", …])` (ImageMagick not installed)
- `subprocess.Popen(["tesseract", …])` (OCR tool missing)
- Assuming `curl` exists for health checks (install it)

**✅ Correct:**
```dockerfile
# Install ALL required system tools — unpinned inside the PINNED base
# (the base codename+digest is the version boundary; exact =version pins rot)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*
```

```python
# Startup validation — fail fast if a required tool is missing
import shutil
REQUIRED_TOOLS = ["ffmpeg", "tesseract", "pdftotext"]
for tool in REQUIRED_TOOLS:
    if not shutil.which(tool):
        raise RuntimeError(f"{tool} not found in PATH; install it in Dockerfile")
```

**Health check:** The Dockerfile template already installs `curl` for HEALTHCHECK — this is the model. Extend it for any other shell-out dependency.

---

## Related Rule Packs

- `10-python.md` — `DATABASE_URL`/`REDIS_URL` config convention, uvicorn CMD, `/health` endpoint
- `25-data-postgres.md` — asyncpg driver (why no libpq), canonical DB session
- `55-observability.md` — `/health`, `/metrics`, structlog, GlitchTip
- `58-resilience.md` — timeout/retry/circuit-breaker for inter-service calls
- `35-security-auth.md` — Authelia forward-auth, `X-Internal-Token`

---

## Spec Contract — Operational Flow

All operational concerns flow through the spec's `shape:` block. Manual VPS edits are anti-patterns. Use `fabrik apply` / `fabrik audit-registrars` / `fabrik reconcile-all` / `fabrik destroy --partial`. If a registrar is missing post-apply, treat as a deploy bug, not a manual fix-up.
