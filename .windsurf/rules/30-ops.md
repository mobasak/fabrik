---
activation: glob
globs: ["**/Dockerfile", "**/compose.yaml", "**/compose.yml", "**/docker-compose.yaml", "**/docker-compose.yml"]
description: Docker standards, deployment, infrastructure
---

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

## Dockerfile Template

```dockerfile
FROM python:<current-stable>-slim-bookworm AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache -r requirements.txt

FROM python:<current-stable>-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.x/site-packages /usr/local/lib/python3.x/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

# HEALTHCHECK is REQUIRED
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

ENV PORT=8000
EXPOSE ${PORT}
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
```

---

## compose.yaml Template

```yaml
services:
  api:
    build: .
    platform: linux/amd64  # MANDATORY for check_docker.py compliance (VPS is x86_64)
    ports:
      - "${PORT:-8000}:${PORT:-8000}"
    environment:
      - DB_HOST=postgres-main
      - DB_PORT=5432
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
    depends_on:
      postgres-main:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    networks:
      - coolify

networks:
  coolify:
    external: true
```

---

## Deployment Checklist

Before deploying to Coolify:

- [ ] Dockerfile uses bookworm-slim (not Alpine)
- [ ] HEALTHCHECK instruction present
- [ ] Health endpoint tests actual dependencies
- [ ] All env vars documented in .env.example
- [ ] Credentials in project .env
- [ ] Port registered in PORTS.md
- [ ] compose.yaml uses coolify network
- [ ] Service added to docs/SERVICES.md
- [ ] Watchdog script created
- [ ] `.dockerignore` present (excludes `.env`, `.git`, `.venv`, `node_modules`)

---

## Watchdog Requirement

Every service MUST have a watchdog script.

**Scope:** Runs on VPS host, not inside container. Uses systemd or cron on host.

```bash
#!/bin/bash
# scripts/watchdog.sh
SERVICE_NAME="myservice"
HEALTH_URL="http://localhost:8000/health"
MAX_FAILURES=3

failures=0
while true; do
    if ! curl -sf "$HEALTH_URL" > /dev/null; then
        ((failures++))
        if [ $failures -ge $MAX_FAILURES ]; then
            systemctl restart "$SERVICE_NAME"
            failures=0
        fi
    else
        failures=0
    fi
    sleep 30
done
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

**Note:** Child projects don't have this script - use Docker Hub/registry docs to verify amd64 support.

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
3. Restart Authelia: `docker compose -f /opt/authelia/compose.yaml restart`

**Health endpoints (`/health`, `/healthz`, `/metrics`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring.

---

## Traefik Entrypoint Names

Coolify's Traefik uses these entrypoint names:

| Entrypoint | Port | Usage |
|------------|------|-------|
| `web` | 80 | HTTP → redirect to HTTPS |
| `websecure` | 443 | HTTPS with Let's Encrypt |

**CRITICAL:** When deploying Docker Image apps via Coolify API, the auto-generated labels use `http`/`https` entrypoints which **do not exist**. You MUST patch `custom_labels` to use `web`/`websecure` after creating the app. See Coolify API reference for the PATCH workflow.
