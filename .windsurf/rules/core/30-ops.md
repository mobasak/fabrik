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
| Python apps | `python:<current-stable>-slim-bookworm` |
| Node.js apps | `node:<current-LTS>-bookworm-slim` |
| General | `debian:bookworm-slim` |

**Why not Alpine:** glibc compatibility, pre-built wheels, consistent behavior across dev/prod.

---

## Docker DNS — No `localhost` in Connection Strings (CRITICAL)

Inside a container, `localhost` resolves to the container itself, NOT the host or the shared DB. Use Docker network DNS names on the `fabrik` network:

| Variable | Wrong | Correct |
|---|---|---|
| `DATABASE_URL` | `...@localhost:5432/...` | `...@postgres-main:5432/...` |
| `REDIS_URL` | `redis://localhost:6379` | `redis://redis-main:6379` |

**Verify before deploy:**

```bash
grep -E '^(DATABASE_URL|REDIS_URL)=' .env | grep localhost
# Must return nothing.
```

---

## Dockerfile Template (Python)

Multi-stage build with `uv` (mandated package manager). No `requirements.txt`, no raw `pip`.

```dockerfile
FROM python:3.13-slim-bookworm AS builder    # track <current-stable>, don't pin stale
WORKDIR /app
# gcc ONLY if a dependency without a wheel must compile; asyncpg ships wheels.
# NO libpq-dev — that's psycopg2, which 25-data-postgres.md bans.
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim-bookworm
WORKDIR /app
# curl for HEALTHCHECK only. NO libpq5 (psycopg2).
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY . .

# Port fixed at build (Traefik routes by label). CMD + HEALTHCHECK use the SAME literal.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Notes:**
- `uv sync --frozen` uses `uv.lock` — deterministic, no resolution at build time.
- `.venv` is copied as a whole directory — no fragile `site-packages` path matching.
- CMD is exec form — SIGTERM reaches uvicorn directly. If you need PORT-env flexibility: `CMD ["sh", "-c", "exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]` — the `exec` replaces the shell so SIGTERM is still signal-safe.
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
      test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/health"]
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

- [ ] Dockerfile uses `slim-bookworm` (not Alpine)
- [ ] HEALTHCHECK instruction present
- [ ] Health endpoint tests actual dependencies (`SELECT 1`, Redis `PING`, etc.)
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
- [ ] `.dockerignore` present (excludes `.env`, `.git`, `.venv`, `node_modules`)
- [ ] Traefik middleware set per service category — admin UI: `authelia-forward@docker,gzip@docker`; API: `gzip@docker`; public: none
- [ ] Compose env vars set: `SERVICE_INTERNAL_SECRET_KEY`, `DATABASE_URL` (using `postgres-main`), `REDIS_URL` (using `redis-main`)
- [ ] `/health` returns 200 against real deps; Gatus polls it for external availability

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
- Deploy‑time migration scripts in `.fabrik/hooks/post‑deploy/`

---

## Multi-host targeting (`--target-vps`)

The fleet is a **vps1 hub + vps2/vps3 spokes**. `fabrik apply` / `plan` / `redeploy` / `destroy` all take `--target-vps <vpsN>` to choose where a service deploys.

**Resolution order** (highest wins): `--target-vps` CLI flag > state file `.fabrik/state/<id>.json::target_vps` > spec `target_vps:` field > **vps1** default.

Spokes are full deploy targets, not standby boxes — a spoke-targeted service runs its container on the spoke but **wires back to the shared vps1 data plane** (`postgres-main:5432`, `redis-main:6379`) over the WireGuard mesh. Those shared backing services always live on vps1 regardless of `target_vps`; only the app container moves. Compose connection strings stay identical (`postgres-main` / `redis-main` Docker DNS) — the mesh resolves them.

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
- WSL runs PostgreSQL via `docker run postgres:16‑bookworm` (same tag as VPS)
- WSL runs Redis via `docker run redis:7‑bookworm` (same tag as VPS)
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
| Alpine base image | `slim-bookworm` / `bookworm-slim` (glibc, prebuilt wheels) |
| `libpq-dev` / `libpq5` in Dockerfile | Omit — asyncpg needs no libpq (psycopg2-only; banned per `25-data-postgres.md`) |
| `ports:` in compose / host-port binding | Traefik routing — only 80/443 bind host |
| `localhost` in container connection strings | Docker DNS: `postgres-main`, `redis-main` |
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
- `fabrik run <app> --command "alembic upgrade head"` (Fabrik wrapper for the above)
- Deploy-time hooks in `.fabrik/hooks/post‑deploy/` for idempotent migrations
- Separate admin container/image for heavy admin tasks (same codebase)

**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.

---

## 12‑Factor II (Dependencies — never assume a system tool exists) (CRITICAL)

**12‑Factor quotes:**
- "A twelve-factor app never relies on implicit existence of system-wide packages"
- "if the app shells out to a system tool, that tool should be vendored into the app"

**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed AND version-pinned in the Dockerfile, with a `shutil.which()` startup probe that fails fast. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

**Concrete failure this prevents:** `subprocess.Popen(["ffmpeg", …])` works in WSL (ffmpeg on the dev's PATH) and raises `FileNotFoundError` in the container.

**❌ Forbidden:**
- `subprocess.Popen(["ffmpeg", "-i", input, output])` (no Dockerfile install)
- `subprocess.Popen(["convert", …])` (ImageMagick not installed)
- `subprocess.Popen(["tesseract", …])` (OCR tool missing)
- Assuming `curl` exists for health checks (install it)

**✅ Correct:**
```dockerfile
# Install ALL required system tools, version-pinned
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg=7:6.1.1-3 \
    tesseract-ocr=5.3.3-1 \
    poppler-utils=23.11.0-1 \
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
