# Fabrik Microservice Integration Guide

How to build microservices that integrate with the Fabrik ecosystem.

## Overview

Fabrik deploys and orchestrates:
- **WordPress sites** via Coolify (Docker Compose)
- **Python/Node microservices** via Coolify
- **Shared infrastructure** (PostgreSQL, Redis)

Microservices provide APIs that WordPress sites and other tools consume.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  VPS (Coolify)                                                   │
├─────────────────────────────────────────────────────────────────┤
│  Shared Services                                                 │
│  ├── postgres-main (PostgreSQL 16)                              │
│  └── redis-main                                                  │
│                                                                  │
│  Microservices                                                   │
│  ├── image-broker    → images.vps1.ocoron.com                   │
│  ├── proxy-api       → proxy.vps1.ocoron.com                    │
│  ├── translator-api  → translator.vps1.ocoron.com               │
│  └── captcha-api     → captcha.vps1.ocoron.com                  │
│                                                                  │
│  WordPress Sites                                                 │
│  ├── ocoron.com      → calls image-broker, translator           │
│  └── other-sites     → call microservices as needed             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Requirements Checklist

Every Fabrik-compatible microservice MUST have:

### Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Container build |
| `compose.yaml` | Coolify deployment |
| `.env.example` | Document all env vars |
| `docs/DEPLOYMENT.md` | Deployment instructions |

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Basic health (returns 200) |
| `GET /api/v1/health` | Detailed health with dependencies |

### Environment

| Requirement | Details |
|-------------|---------|
| Bind to `0.0.0.0` | Required for Docker networking |
| Port via env var | `PORT=8000` or similar |
| Config via env vars | No hardcoded values |

---

## URL Naming Convention

### Pattern

```
https://<service>.vps1.ocoron.com
```

### Examples

| Service | URL |
|---------|-----|
| Image Broker | `https://images.vps1.ocoron.com` |
| Proxy API | `https://proxy.vps1.ocoron.com` |
| Translator | `https://translator.vps1.ocoron.com` |
| Captcha | `https://captcha.vps1.ocoron.com` |
| Email Gateway | `https://emailgateway.vps1.ocoron.com` |

### DNS Setup

Add A record in DNS pointing to VPS IP:
```
images.vps1.ocoron.com → 172.93.160.197
```

Coolify handles SSL certificates automatically.

---

## Credentials Management

### Dual Storage (MANDATORY)

All API keys must be stored in TWO places:

1. **Project `.env`** — Local development
2. **Fabrik master `.env`** — Central repository at `/opt/fabrik/.env`

### Adding New Credentials

```bash
# 1. Add to project
echo "NEW_API_KEY=xyz123" >> /opt/myservice/.env

# 2. ALSO add to Fabrik master
echo "NEW_API_KEY=xyz123" >> /opt/fabrik/.env

# 3. Document in .env.example (without real value)
echo "NEW_API_KEY=" >> /opt/myservice/.env.example
```

### Service URL Registration

Add to `/opt/fabrik/.env`:
```bash
# Service URLs
MYSERVICE_URL=https://myservice.vps1.ocoron.com
```

---

## Health Check Requirements

### Basic Health (required)

```python
@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}
```

### Detailed Health (recommended)

```python
@app.get("/api/v1/health")
async def detailed_health():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "dependencies": {
            "database": check_db_connection(),
            "redis": check_redis_connection(),
            "external_api": check_api_status(),
        }
    }
```

### Why Both?

| Endpoint | Used By | Purpose |
|----------|---------|---------|
| `/health` | Coolify, Docker | Simple up/down check |
| `/api/v1/health` | Monitoring, debugging | Detailed status |

---

## Dockerfile Template

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

ENV PORT=8000
EXPOSE ${PORT}
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

---

## compose.yaml Template

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "${PORT:-8000}:${PORT:-8000}"
    environment:
      - PORT=${PORT:-8000}
      - PEXELS_API_KEY=${PEXELS_API_KEY}
      - PIXABAY_API_KEY=${PIXABAY_API_KEY}
    volumes:
      - app-cache:/app/cache
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  app-cache:
```

---

## WordPress Integration

### From PHP (WordPress plugin/theme)

```php
// Get service URL from environment
$image_broker_url = getenv('IMAGE_BROKER_URL') ?: 'https://images.vps1.ocoron.com';

// Search for images
$response = wp_remote_get(
    "$image_broker_url/api/v1/search?" . http_build_query([
        'query' => 'business office',
        'per_page' => 5,
    ])
);

if (!is_wp_error($response)) {
    $data = json_decode(wp_remote_retrieve_body($response), true);
    $images = $data['images'];
}
```

### Environment Variables in WordPress

Add to WordPress container environment:
```yaml
environment:
  - IMAGE_BROKER_URL=https://images.vps1.ocoron.com
  - TRANSLATOR_URL=https://translator.vps1.ocoron.com
```

---

## Deployment Process

### 1. Prepare Project

```bash
# Ensure all required files exist
ls Dockerfile compose.yaml .env.example docs/DEPLOYMENT.md

# Run tests
pytest tests/

# Build locally
docker build -t myservice .
```

### 2. Register in Fabrik

Add service URL to `/opt/fabrik/.env`:
```bash
MYSERVICE_URL=https://myservice.vps1.ocoron.com
```

### 3. Deploy via Coolify

1. Create new service in Coolify
2. Select "Docker Compose"
3. Point to project repository or upload files
4. Set environment variables
5. Configure domain
6. Deploy

### 4. Verify

```bash
# Health check
curl https://myservice.vps1.ocoron.com/health

# Detailed health
curl https://myservice.vps1.ocoron.com/api/v1/health
```

---

## Existing Microservices

| Service | Location | Purpose |
|---------|----------|---------|
| Image Broker | `/opt/image-broker` | Stock image API (Pexels, Pixabay) |
| Proxy API | `/opt/proxy-api` | Web scraping proxy |
| Translator | `/opt/translator-api` | Translation service |
| Captcha | `/opt/captcha-api` | Captcha solving |
| Email Gateway | `/opt/emailgateway` | Email sending |

---

## Troubleshooting

### Service Not Reachable

1. Check Coolify deployment status
2. Verify DNS record exists
3. Check container logs: `docker logs <container>`
4. Test health endpoint locally

### SSL Certificate Issues

Coolify auto-provisions SSL. If failing:
1. Verify domain DNS points to VPS
2. Check Coolify → Service → SSL settings
3. Force certificate renewal

### WordPress Can't Connect

1. Check `SERVICE_URL` env var in WP container
2. Verify service is running: `curl $SERVICE_URL/health`
3. Check WP error logs

---

## Quick Reference

```bash
# Service URL pattern
https://<service>.vps1.ocoron.com

# Required endpoints
GET /health              # Basic health
GET /api/v1/health       # Detailed health

# Required files
Dockerfile, compose.yaml, .env.example, docs/DEPLOYMENT.md

# Credential storage
/opt/project/.env        # Project local
/opt/fabrik/.env         # Master registry
```
