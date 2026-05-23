---
activation: glob
globs: ["**/Dockerfile", "**/compose.yaml", "**/compose.yml", "**/docker-compose.yaml", "**/docker-compose.yml"]
description: Docker standards, deployment, infrastructure
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (deploy-plan step)
     GOAL: Docker, compose.yaml, Coolify deployment — base images, DNS, Traefik, resource limits, security
     TRAYCER USAGE: Referenced during deploy-plan and ticket-breakdown for infrastructure tickets. Injects as Context File.
     AGENT USAGE: Follow verbatim when writing Dockerfiles, compose files, or deployment config. -->

# Operations & Deployment Rules

**Activation:** Glob `**/Dockerfile`, `**/compose.yaml`, `**/compose.yml`
**Purpose:** Docker standards, deployment, infrastructure

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

Inside a container, `localhost` resolves to the container itself, NOT the host or the shared DB. Use Docker network DNS names on the `coolify` network:

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

All services deploy via Coolify on the `coolify` network. Traefik routes external traffic — services do NOT bind host ports.

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
      - coolify

networks:
  coolify:
    external: true
```

**CRITICAL rules:**
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below.
- **`deploy.resources.limits.memory` is mandatory.** Coolify v4 ignores its `limits_memory` UI field for `build_pack=dockercompose`. The compose must carry the declaration explicitly.
- **`platform: linux/amd64` is mandatory.** VPS is x86_64.
- **No `depends_on: postgres-main`.** The database is a separate Coolify-managed container on the `coolify` network, not a service in your compose file. Docker DNS resolves `postgres-main` at runtime.
- **Traefik labels** set routing, TLS, and middleware. Middleware per service category: admin UI = `authelia-forward@docker,gzip@docker`; API = `gzip@docker`; public = none.
- **Traefik entrypoints** are `web` (80) and `websecure` (443). Coolify's auto-generated labels incorrectly use `http`/`https` — always patch to `web`/`websecure`.

---

## Deployment Checklist

Before deploying to Coolify:

- [ ] Dockerfile uses `slim-bookworm` (not Alpine)
- [ ] HEALTHCHECK instruction present
- [ ] Health endpoint tests actual dependencies (`SELECT 1`, Redis `PING`, etc.)
- [ ] All env vars documented in `.env.example`
- [ ] Credentials in project `.env`
- [ ] Port registered in `PORTS.md`
- [ ] compose.yaml uses `coolify` network (external)
- [ ] compose.yaml has `deploy.resources.limits.memory` + `cpus`
- [ ] compose.yaml has `platform: linux/amd64`
- [ ] compose.yaml has Traefik labels with `websecure` entrypoint
- [ ] No `ports:` section in compose.yaml (Traefik routes all traffic)
- [ ] Service added to `docs/SERVICES.md`
- [ ] `.dockerignore` present (excludes `.env`, `.git`, `.venv`, `node_modules`)
- [ ] Traefik middleware set per service category — admin UI: `authelia-forward@docker,gzip@docker`; API: `gzip@docker`; public: none
- [ ] Coolify env vars set: `SERVICE_INTERNAL_SECRET_KEY`, `DATABASE_URL` (using `postgres-main`), `REDIS_URL` (using `redis-main`)
- [ ] `/health` returns 200 against real deps; Coolify health interval 60s for stable services

---

## Redeploying Git-Sourced Apps

`fabrik redeploy <app>` triggers Coolify to pull from the **GitHub remote**, NOT from the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — Coolify never sees local changes.

**Correct sequence:**

```bash
git commit -m "..."
git push
fabrik redeploy <app>
```

---

## Microservice URLs

| Environment | Pattern |
|-------------|---------|
| WSL | `http://localhost:PORT` |
| VPS Internal | `http://service-name:PORT` |
| VPS External | `https://service.vps1.ocoron.com` |

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
| Allow ports 6001, 6002 | Coolify realtime WebSocket |
| DROP all other external traffic | Blocks raw port access to containers |

**Invariant:** Never use `ports_mappings` in Coolify or `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.

**Exception:** Only Traefik (80/443) and Coolify WebSocket (6001/6002) may bind to host ports.

---

## Authelia SSO (Forward Auth)

All admin dashboards are protected by Authelia (`auth.vps1.ocoron.com`) via Traefik forward-auth middleware.

**Service categories:**

| Category | Auth Mechanism | Examples |
|----------|---------------|----------|
| Public | None (bypass) | `ocoron.com`, `status.vps1.ocoron.com` |
| Admin dashboards | Authelia (2FA) | `coolify`, `auto` (n8n), `monitor` (Grafana), `netdata`, `backup`, `notify` |
| API services | `X-Internal-Token` header | `pdf`, `browser`, `search`, `images`, `captcha`, `proxy`, `translator`, `files-api`, `emailgateway`, `dns` |

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

**Health endpoints (`/health`, `/healthz`, `/metrics`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass rule `*.vps1.ocoron.com → /health` is global. Never protect `/health`.

---

## Traefik Entrypoint Names

Coolify's Traefik uses these entrypoint names:

| Entrypoint | Port | Usage |
|------------|------|-------|
| `web` | 80 | HTTP, redirect to HTTPS |
| `websecure` | 443 | HTTPS with Let's Encrypt |

**CRITICAL:** When deploying Docker Image apps via Coolify API, the auto-generated labels use `http`/`https` entrypoints which **do not exist**. You MUST patch `custom_labels` to use `web`/`websecure` after creating the app. See Coolify API reference for the PATCH workflow.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Alpine base image | `slim-bookworm` / `bookworm-slim` (glibc, prebuilt wheels) |
| `libpq-dev` / `libpq5` in Dockerfile | Omit — asyncpg needs no libpq (psycopg2-only; banned per `25-data-postgres.md`) |
| `ports:` in compose / host-port binding | Traefik routing — only 80/443/6001/6002 bind host |
| `localhost` in container connection strings | Docker DNS: `postgres-main`, `redis-main` |
| Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app | Single `DATABASE_URL` (see `10-python.md` § Config) |
| `depends_on: postgres-main` | None — DB is an external Coolify-managed container |
| `http` / `https` Traefik entrypoints | `web` / `websecure` (Coolify auto-labels are wrong) |
| Protecting `/health` with Authelia | `/health` always bypasses auth (Gatus/Prometheus need it) |
| Missing `deploy.resources.limits.memory` | Mandatory — Coolify v4 ignores the UI field for compose |
| Missing `platform: linux/amd64` | Mandatory — VPS is x86_64 |
| `sh -c` CMD without `exec` (breaks SIGTERM) | Exec-form CMD, or `sh -c "exec ..."` |
| Manual VPS edits / registrar fix-ups | `fabrik apply` / `reconcile-all` (spec-driven) |
| `fabrik redeploy` without `git push` | `commit → push → redeploy` (Coolify pulls the remote) |
| PORT mismatch between CMD and HEALTHCHECK | Both must use the same literal port value |

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
