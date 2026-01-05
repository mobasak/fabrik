# Deployment-Ready Checklist

> **Container-first development: fast local dev + production parity**

---

## Core Principle

**Container-first but not container-only.**

- Write code with normal local tooling (venv/npm) for speed
- Keep a **working Dockerfile + compose** from day 1
- Use Docker as the **truth for production parity**

This avoids two common failures:

| Failure Mode | Solution |
|--------------|----------|
| "Works locally but not in container" | Docker-ready from day 1, `docker build` as gate |
| "Container works but dev is slow" | Local venv/npm for speed, Docker only for parity |

---

## The Development → Deployment Flow

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WSL (Development Factory)                         │
│                                                                             │
│  LOCAL DEV (fast):                                                          │
│    - Python: uv venv + uvicorn --reload                                     │
│    - Node: npm run dev                                                      │
│    - Shared Postgres container for all projects                             │
│                                                                             │
│  DOCKER PARITY (gate):                                                      │
│    - make docker-smoke (build + run + health check)                         │
│    - Run before every push to main                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GitHub Repository                                 │
│                                                                             │
│  - Source code                                                              │
│  - Dockerfile + .dockerignore                                               │
│  - compose.yaml (prod-like) + compose.dev.yaml (optional)                   │
│  - .env.example (never .env!)                                               │
│  - CI: docker build + health check on every PR                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Coolify (VPS Control Plane)                       │
│                                                                             │
│  1. Webhook from GitHub on push                                             │
│  2. Pulls code, builds Docker image                                         │
│  3. Runs migrations (pre-deploy command)                                    │
│  4. Starts container, routes traffic                                        │
│  5. Manages HTTPS certificates                                              │
│  6. Env vars set in Coolify UI (not in repo)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VPS (Production)                                  │
│                                                                             │
│  - ONE shared PostgreSQL (Coolify managed or dedicated container)           │
│  - Per-project databases: project1_db, project2_db, etc.                    │
│  - App containers connect via DATABASE_URL                                  │
│  - Persistent volumes for data                                              │
│  - HTTPS endpoints via Coolify reverse proxy                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment-Ready Checklist

For each project, you need these files. Check off as you add them:

### Required Files

| File | Purpose | Template |
|------|---------|----------|
| `Dockerfile` | Build instructions for container | See below |
| `compose.yaml` | Production-like (no bind mounts, no dev tools) | See below |
| `compose.dev.yaml` | Dev overrides (bind mounts, hot reload) | Optional but recommended |
| `.env.example` | Document all required env vars | Already exists in most projects |
| `.dockerignore` | Exclude unnecessary files from build | See below |
| `Makefile` | Standard commands: `make dev`, `make docker-smoke`, `make test` | See below |
| `README.md` | Include deployment section | Add if missing |

### Required Code Changes

| Requirement | Why | How |
|-------------|-----|-----|
| Health check endpoint | Coolify monitors container health | Add `GET /health` returning `{"status": "ok"}` |
| Listen on `0.0.0.0` | Container networking requirement | Set `host="0.0.0.0"` in uvicorn/express |
| Port from env var | Flexibility | Use `PORT` or `API_PORT` env var |
| Graceful shutdown | Clean container stops | Handle SIGTERM signal |
| Migrations strategy | Repeatable DB setup | Alembic/Prisma with pre-deploy command |

---

## File Templates

### Python FastAPI Dockerfile

```dockerfile
# Dockerfile for Python FastAPI projects
# Build: docker build -t myproject .
# Run: docker run -p 8000:8000 --env-file .env myproject

FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Create non-root user (optional but recommended)
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Default port
ENV PORT=8000
EXPOSE ${PORT}

# Run the application
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

### Node.js Fastify/Express Dockerfile

```dockerfile
# Dockerfile for Node.js projects
# Build: docker build -t myproject .
# Run: docker run -p 3000:3000 --env-file .env myproject

FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy source
COPY . .

# Build TypeScript if needed
RUN npm run build --if-present

# Production stage
FROM node:20-alpine

WORKDIR /app

# Install curl for health checks
RUN apk add --no-cache curl

# Copy from builder
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package*.json ./

# Create non-root user
RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
USER nodejs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-3000}/health || exit 1

# Default port
ENV PORT=3000
EXPOSE ${PORT}

# Run the application
CMD ["node", "dist/index.js"]
```

### compose.yaml (Production-like)

```yaml
# compose.yaml - Production-like configuration
# Used by: Coolify deployment, docker-smoke test
# No bind mounts, no dev tools

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - PORT=${PORT:-8000}
      - DATABASE_URL=${DATABASE_URL:?Database URL is required}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
```

### compose.dev.yaml (Dev Overrides)

```yaml
# compose.dev.yaml - Development overrides
# Usage: docker compose -f compose.yaml -f compose.dev.yaml up --build

services:
  app:
    build:
      target: builder  # Use builder stage for dev deps
    volumes:
      - .:/app         # Bind mount for hot reload
      - /app/node_modules  # Exclude node_modules (Node.js)
      - /app/.venv         # Exclude venv (Python)
    environment:
      - DEBUG=1
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--reload"]
    # For Node.js:
    # command: ["npm", "run", "dev"]
```

### Makefile (Standard Commands)

```makefile
# Makefile - Standard project commands
# Usage: make dev, make docker-smoke, make test

.PHONY: dev test docker-smoke docker-build clean

# Local development (fast)
dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
	# For Node.js: npm run dev

# Run tests
test:
	pytest -v
	# For Node.js: npm test

# Docker smoke test (parity check before push)
docker-smoke: docker-build
	@echo "Starting container..."
	@docker run -d --name smoke-test -p 8000:8000 --env-file .env $(PROJECT_NAME) || true
	@sleep 3
	@echo "Health check..."
	@curl -sf http://localhost:8000/health && echo " ✓ Health OK" || echo " ✗ Health FAILED"
	@docker stop smoke-test && docker rm smoke-test

# Build Docker image
docker-build:
	docker build -t $(PROJECT_NAME) .

# Run with dev overrides
docker-dev:
	docker compose -f compose.yaml -f compose.dev.yaml up --build

# Clean up
clean:
	docker stop smoke-test 2>/dev/null || true
	docker rm smoke-test 2>/dev/null || true
	docker rmi $(PROJECT_NAME) 2>/dev/null || true

# Project name (override in each project)
PROJECT_NAME ?= myproject
```

### .dockerignore

```text
# .dockerignore - Exclude from Docker build

# Virtual environments
venv/
.venv/
env/
.env

# Node modules (will be installed in container)
node_modules/

# Git
.git/
.gitignore

# IDE
.vscode/
.idea/
*.swp
*.swo

# Python cache
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Logs
logs/
*.log

# Local data
data/
*.db
*.sqlite

# Build artifacts
dist/
build/
*.egg-info/

# Test files
tests/
test_*.py
*_test.py

# Documentation (optional - include if needed)
# docs/

# Temporary files
.tmp/
.cache/
tmp/
```

---

## Health Check Endpoint Examples

### Python FastAPI

```python
# Add to app/main.py or create app/health.py

from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "ok"}

# In main.py:
# app.include_router(router)
```

### Node.js Express

```typescript
// Add to src/routes/health.ts or directly in index.ts

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});
```

### Node.js Fastify

```typescript
// Add to src/routes/health.ts

fastify.get('/health', async (request, reply) => {
  return { status: 'ok' };
});
```

---

## Per-Project Instructions

### Step-by-Step for Each Project

For each project in `/opt`, run through this checklist:

```bash
cd /opt/<project-name>

# 1. Check if Dockerfile exists
ls -la Dockerfile

# 2. Check if compose.yaml exists
ls -la compose.yaml docker-compose*.yml

# 3. Check if .env.example exists
ls -la .env.example

# 4. Check if health endpoint exists
grep -r "health" --include="*.py" --include="*.ts" --include="*.js" .

# 5. Check entry point
# Python: look for main.py, app.py, or __main__.py
# Node: look for index.ts, index.js, or check package.json "main"
```

---

## Project Status Matrix

| Project | Dockerfile | compose.yaml | .env.example | Health Check | Entry Point | Ready |
|---------|------------|--------------|--------------|--------------|-------------|-------|
| captcha | ❌ | ❌ | ✅ | ❌ | `app/main.py` | ❌ |
| emailgateway | ❌ | ❌ | ✅ | ❌ | `src/index.ts` | ❌ |
| translator | ❌ | ❌ | ✅ | ❌ | `app/main.py` | ❌ |
| email-reader | ❌ | ❌ | ✅ | ❌ | TBD | ❌ |
| namecheap | ❌ | ❌ | ✅ | ❌ | `api/main.py` | ❌ |
| proxy | ❌ | ❌ | ✅ | ❌ | TBD | ❌ |
| calendar-orchestration-engine | ❌ | ⚠️ partial | ✅ | ❌ | `src/index.ts` | ❌ |
| proposal-creator | ❌ | ❌ | ✅ | N/A (CLI) | `src/main.py` | ❌ |
| youtube | ❌ | ❌ | ✅ | ❌ | TBD | ❌ |

---

## Making a Project Deploy-Ready: Exact Steps

### For Python FastAPI Projects (captcha, translator, email-reader, namecheap)

```bash
# 1. Navigate to project
cd /opt/<project>

# 2. Create Dockerfile (copy template above and adjust)
# Key changes:
#   - Verify requirements.txt path
#   - Verify entry point (app.main:app vs main:app)
#   - Add any system dependencies (libpq for postgres, etc.)

# 3. Create compose.yaml (copy template above and adjust)
# Key changes:
#   - Set correct PORT
#   - Add all required env vars from .env.example
#   - Add volumes if project stores files

# 4. Create .dockerignore (copy template above)

# 5. Add health check endpoint to code
# In app/main.py:
#   @app.get("/health")
#   async def health(): return {"status": "ok"}

# 6. Verify host binding
# In app/main.py or wherever uvicorn is configured:
#   uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

# 7. Test locally
docker build -t <project> .
docker run -p 8000:8000 --env-file .env <project>
curl http://localhost:8000/health

# 8. Commit and push
git add Dockerfile compose.yaml .dockerignore
git commit -m "feat: add Docker deployment configuration"
git push
```

### For Node.js Projects (emailgateway, calendar-orchestration-engine)

```bash
# 1. Navigate to project
cd /opt/<project>

# 2. Create Dockerfile (copy Node.js template above and adjust)
# Key changes:
#   - Verify if TypeScript build is needed
#   - Verify entry point (dist/index.js vs src/index.js)

# 3. Create compose.yaml (copy template above and adjust)

# 4. Create .dockerignore (copy template above)

# 5. Add health check endpoint to code
# In src/index.ts:
#   app.get('/health', (req, res) => res.json({ status: 'ok' }));

# 6. Verify host binding
# In src/index.ts:
#   app.listen(PORT, '0.0.0.0', () => { ... });

# 7. Test locally
docker build -t <project> .
docker run -p 3000:3000 --env-file .env <project>
curl http://localhost:3000/health

# 8. Commit and push
git add Dockerfile compose.yaml .dockerignore
git commit -m "feat: add Docker deployment configuration"
git push
```

---

## Iteration Workflow (WSL → VPS)

When you make changes after initial deployment:

```bash
# 1. Make code changes in WSL
cd /opt/<project>
# ... edit files ...

# 2. Test locally
docker build -t <project> .
docker run -p 8000:8000 --env-file .env <project>

# 3. Commit and push
git add .
git commit -m "fix: description of change"
git push

# 4. In Coolify UI:
#    - Go to your application
#    - Click "Redeploy"
#    - Or enable "Auto Deploy" for automatic deploys on push

# 5. Verify deployment
curl https://<your-domain>/health
```

---

## Common Issues and Fixes

### Issue: Container exits immediately

```bash
# Check logs
docker logs <container-id>

# Common causes:
# - Missing environment variables
# - Wrong entry point path
# - Syntax error in code
```

### Issue: Health check fails

```bash
# Verify endpoint works locally
curl http://localhost:8000/health

# Common causes:
# - Endpoint not added to code
# - App listening on 127.0.0.1 instead of 0.0.0.0
# - Wrong port
```

### Issue: Cannot connect to database

```bash
# In Docker, use service names not localhost
# Wrong: DATABASE_URL=postgresql://localhost:5432/db
# Right: DATABASE_URL=postgresql://postgres:5432/db  (if postgres is service name)
# Or use Coolify's managed database URL
```

### Issue: Files not persisting

```yaml
# Add volume to compose.yaml
services:
  app:
    volumes:
      - app_data:/app/data

volumes:
  app_data:
```

---

## Database Strategy

### WSL Development

Run **one shared Postgres container** for all projects:

```bash
# Start shared dev Postgres (run once)
docker run -d --name dev-postgres \
  -e POSTGRES_PASSWORD=devpass \
  -p 5432:5432 \
  -v pgdata:/var/lib/postgresql/data \
  postgres:16

# Create per-project databases
docker exec -it dev-postgres psql -U postgres -c "CREATE DATABASE captcha_db;"
docker exec -it dev-postgres psql -U postgres -c "CREATE USER captcha_user WITH PASSWORD 'devpass';"
docker exec -it dev-postgres psql -U postgres -c "GRANT ALL ON DATABASE captcha_db TO captcha_user;"
```

Each project's `.env` (local only, not committed):

```bash
DATABASE_URL=postgresql://captcha_user:devpass@localhost:5432/captcha_db
```

### VPS Production

- **ONE shared PostgreSQL** (Coolify managed or dedicated container)
- Per-project databases: `project1_db`, `project2_db`, etc.
- Connection strings set in Coolify env vars (not in repo)

---

## Migrations Strategy

### Python (Alembic)

```bash
# In Coolify pre-deploy command:
alembic upgrade head
```

Or use init container in compose:

```yaml
services:
  migrate:
    build: .
    command: ["alembic", "upgrade", "head"]
    environment:
      - DATABASE_URL=${DATABASE_URL}
  app:
    build: .
    depends_on:
      migrate:
        condition: service_completed_successfully
```

### Node.js (Prisma)

```bash
# In Coolify pre-deploy command:
npx prisma migrate deploy
```

---

## DONE Definition

A project is **deployment-ready** when:

| Criterion | Test |
|-----------|------|
| `docker build` succeeds | `docker build -t project .` from clean checkout |
| Container starts | `docker run --env-file .env.example project` |
| Health check passes | `curl http://localhost:PORT/health` returns 200 |
| Migrations work | Can apply DB migrations repeatably |
| Coolify deploys | Push to GitHub → Coolify deploys automatically |

```bash
# Quick validation script
make docker-smoke  # or manually:
docker build -t myproject .
docker run -d --name test -p 8000:8000 --env-file .env myproject
sleep 3
curl -sf http://localhost:8000/health && echo "✓ READY" || echo "✗ NOT READY"
docker stop test && docker rm test
```

---

## Next Steps

1. **Start with captcha** - simplest service, good test case
2. **Then emailgateway** - many services need it
3. **Then translator** - youtube needs it
4. **Then calendar-orchestration-engine** - deploy soon
5. **Infrastructure services first, then products**

---

## Reference

- Project Registry: `/opt/fabrik/docs/reference/project-registry.md`
- Stack Reference: `/opt/fabrik/docs/reference/stack.md`
- Windsurfrules: `/opt/fabrik/windsurfrules` (compliance trigger)
