# Deployment - [Project Name]

**Last Updated:** YYYY-MM-DD
**Environment:** WSL (dev) → VPS (prod via Coolify)

---

## Overview

| Attribute | Value |
|-----------|-------|
| **Project** | [Project Name] |
| **Type** | [API / Worker / Full Stack / Static] |
| **Domain** | [subdomain.domain.com] |
| **Repository** | [GitHub URL] |

---

## Services

| Service | Port (Dev) | Port (Prod) | Health Endpoint | Purpose |
|---------|------------|-------------|-----------------|---------|
| web | 8000 | Internal | /health | Main API |
| worker | - | - | - | Background jobs |

**Note:** In production, Coolify proxy handles external routing (80/443). Internal ports are not exposed.

---

## Environment Variables

### Required (deployment will fail without these)

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql://user:pass@host:5432/db` |
| `SECRET_KEY` | JWT/session signing | `openssl rand -hex 32` |

### Optional (have defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `APP_ENV` | `prod` | Environment name |

---

## Docker Compose

```yaml
services:
  web:
    build:
      context: ./services/api
    environment:
      - DATABASE_URL=${DATABASE_URL:?}
      - SECRET_KEY=${SECRET_KEY:?}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    ports:
      - "8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  worker:
    build:
      context: ./services/worker
    environment:
      - DATABASE_URL=${DATABASE_URL:?}
    depends_on:
      - web
```

---

## Deployment Steps

### First Time (Coolify)

1. Create new application in Coolify
2. Select "Docker Compose" build pack
3. Connect GitHub repository
4. Set environment variables in Coolify UI
5. Add domain (Coolify handles SSL via Let's Encrypt)
6. Deploy

### Updates

```bash
# Push to GitHub triggers auto-deploy (if configured)
git push origin main

# Or manual deploy via Coolify UI
```

---

## Local Development (WSL)

```bash
# Start services
docker compose up -d

# Or without Docker
cd /opt/[project]
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

---

## Database

| Environment | Host | Database | Notes |
|-------------|------|----------|-------|
| Development | localhost:5432 | [project]_dev | Local PostgreSQL |
| Production | postgres-main | [project] | Coolify-managed |

### Migrations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

---

## Monitoring

| Check | URL | Expected |
|-------|-----|----------|
| Health | /health | `{"status": "ok"}` |
| Readiness | /ready | `{"status": "ready"}` |

### Uptime Kuma

- [ ] Health check configured
- [ ] Alert notifications set up

---

## Rollback

```bash
# Via Coolify UI: select previous deployment and redeploy

# Database rollback (if needed)
alembic downgrade -1
```

---

## Checklist

### Before First Deploy

- [ ] Dockerfile tested locally
- [ ] docker-compose.yaml works locally
- [ ] All required env vars documented
- [ ] Health endpoint implemented
- [ ] Database migrations ready
- [ ] Port registered in `/opt/fabrik/PORTS.md`

### After Deploy

- [ ] Health check passing
- [ ] Logs accessible in Coolify
- [ ] Domain resolving with HTTPS
- [ ] Uptime monitoring configured
