# Deployment-Ready Checklist

> **How to make any /opt project ready for VPS deployment via Coolify**

---

## The Development → Deployment Flow

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WSL (Development Factory)                         │
│                                                                             │
│  1. Write/modify code                                                       │
│  2. Test locally (venv, npm run dev, etc.)                                  │
│  3. Add deployment files (Dockerfile, compose.yaml)                         │
│  4. Commit to Git                                                           │
│  5. Push to GitHub                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GitHub Repository                                 │
│                                                                             │
│  - Source code                                                              │
│  - Dockerfile                                                               │
│  - compose.yaml                                                             │
│  - .env.example (never .env!)                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Coolify (VPS Control Plane)                       │
│                                                                             │
│  1. Connects to GitHub repo                                                 │
│  2. Pulls code on deploy                                                    │
│  3. Builds Docker image from Dockerfile                                     │
│  4. Runs containers per compose.yaml                                        │
│  5. Manages HTTPS certificates                                              │
│  6. Handles environment variables (set in Coolify UI)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           VPS (Production)                                  │
│                                                                             │
│  - Running containers                                                       │
│  - PostgreSQL database                                                      │
│  - Persistent volumes                                                       │
│  - HTTPS endpoints                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment-Ready Checklist

For each project, you need these files. Check off as you add them:

### Required Files

| File | Purpose | Template |
|------|---------|----------|
| `Dockerfile` | Build instructions for container | See below |
| `compose.yaml` | Service definition for Coolify | See below |
| `.env.example` | Document all required env vars | Already exists in most projects |
| `.dockerignore` | Exclude unnecessary files from build | See below |
| `README.md` | Include deployment section | Add if missing |

### Required Code Changes

| Requirement | Why | How |
|-------------|-----|-----|
| Health check endpoint | Coolify monitors container health | Add `GET /health` returning `{"status": "ok"}` |
| Listen on `0.0.0.0` | Container networking requirement | Set `host="0.0.0.0"` in uvicorn/express |
| Port from env var | Flexibility | Use `PORT` or `API_PORT` env var |
| Graceful shutdown | Clean container stops | Handle SIGTERM signal |

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

### compose.yaml (Coolify-compatible)

```yaml
# compose.yaml - Coolify deployment configuration
# Required env vars use ${VAR:?} syntax (fails if not set)

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "${PORT:-8000}:${PORT:-8000}"
    environment:
      - PORT=${PORT:-8000}
      - DATABASE_URL=${DATABASE_URL:?Database URL is required}
      - API_KEY=${API_KEY:?API key is required}
      # Add all your required env vars here
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
    # For services that need persistent storage:
    # volumes:
    #   - app_data:/app/data

# Uncomment if using volumes
# volumes:
#   app_data:
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

## Next Steps

1. **Start with captcha** - simplest service, good test case
2. **Then emailgateway** - many services need it
3. **Then translator** - youtube needs it
4. **Then calendar-orchestration-engine** - you said "deploy soon"
5. **Infrastructure services first, then products**

Would you like me to create the actual Dockerfile and compose.yaml for a specific project now?
