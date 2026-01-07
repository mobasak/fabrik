---
activation: glob
globs: ["**/Dockerfile", "**/compose.yaml", "**/compose.yml", "**/docker-compose.yaml", "**/docker-compose.yml"]
description: Docker standards, deployment, infrastructure
trigger: always_on
---

# Operations & Deployment Rules

**Activation:** Glob `**/Dockerfile`, `**/compose.yaml`, `**/compose.yml`
**Purpose:** Docker standards, deployment, infrastructure

---

## Container Base Images (CRITICAL)

**Use Debian/Ubuntu, NOT Alpine:**

| Use Case | Base Image |
|----------|------------|
| Python apps | `python:3.12-slim-bookworm` |
| Node.js apps | `node:22-bookworm-slim` |
| General | `debian:bookworm-slim` |

**Why not Alpine:** glibc compatibility, ARM64 support, pre-built wheels.

---

## Dockerfile Template

```dockerfile
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
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
    ports:
      - "${PORT:-8000}:${PORT:-8000}"
    environment:
      - DB_HOST=postgres-main
      - DB_PORT=5432
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
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
- [ ] Credentials in project .env AND /opt/fabrik/.env
- [ ] Port registered in PORTS.md
- [ ] compose.yaml uses coolify network
- [ ] Service added to /opt/fabrik/docs/SERVICES.md
- [ ] Watchdog script created

---

## Watchdog Requirement

Every service MUST have a watchdog script:

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

## ARM64 Requirement

VPS1 uses ARM64 (aarch64). Verify image support:
```bash
python scripts/container_images.py check-arch <image:tag>
```
