# Fabrik Templates

**Last Updated:** 2025-12-23

---

## Available Templates

| Template | Stack | Port | Use Case |
|----------|-------|------|----------|
| **`saas-skeleton`** | **Next.js 14 + Tailwind + SSE** | **3000** | **SaaS apps, dashboards, web apps** |
| `python-api` | Python 3.12 + FastAPI/Uvicorn | 8000 | REST APIs, microservices |
| `node-api` | Node.js 20 | 3000 | Express/Fastify APIs |
| `next-tailwind` | Next.js 14 + Tailwind CSS | 3000 | Full-stack web apps, SSR |

---

## saas-skeleton (RECOMMENDED)

**Use this template for ANY SaaS, web app, or dashboard project.**

**Location:** `templates/saas-skeleton/`

**Features:**
- Next.js 14 + TypeScript + Tailwind CSS
- Marketing pages (landing, pricing, FAQ, terms, privacy)
- App pages (dashboard, settings, job workflow)
- SSE streaming + ChatUI for droid exec integration
- Supabase-ready auth patterns

**Quick Start:**
```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/<project-name>
cd /opt/<project-name>
npm install
cp .env.example .env
npm run dev
```

**Customize:**
- `lib/config/site.ts` — Branding, navigation
- `app/(marketing)/` — Marketing pages
- `app/(app)/app/` — Authenticated app pages

---

## python-api

Python API with FastAPI and Uvicorn.

**Features:**
- Python 3.12 slim base image
- Non-root user for security
- Health check endpoint
- PostgreSQL/Redis integration
- Traefik labels for HTTPS

**Requirements:**
- `requirements.txt` with dependencies
- `main.py` with FastAPI app

**Example spec:**
```yaml
id: my-python-api
kind: service
template: python-api
domain: api.example.com

depends:
  postgres: main

env:
  LOG_LEVEL: INFO

resources:
  memory: 512M
  cpu: "1"

health:
  path: /health
  interval: 30s
```

---

## node-api

Node.js API server.

**Features:**
- Node.js 20 slim base image
- Non-root user for security
- Health check endpoint
- PostgreSQL/Redis integration
- Traefik labels for HTTPS

**Requirements:**
- `package.json` with dependencies
- `src/index.js` as entry point

**Example spec:**
```yaml
id: my-node-api
kind: service
template: node-api
domain: api.example.com

depends:
  postgres: main
  redis: cache

env:
  LOG_LEVEL: info

resources:
  memory: 256M
  cpu: "0.5"

health:
  path: /health
  interval: 30s
```

---

## next-tailwind

Next.js with Tailwind CSS for full-stack web applications.

**Features:**
- Next.js 14 with standalone output
- Tailwind CSS pre-configured
- Multi-stage Docker build (smaller images)
- Supabase integration ready (Phase 1b)
- SSR/SSG support

**Requirements:**
- `package.json` with Next.js and Tailwind
- `next.config.js` with `output: 'standalone'`
- Standard Next.js project structure

**Example spec:**
```yaml
id: my-web-app
kind: service
template: next-tailwind
domain: app.example.com

infrastructure:
  auth: supabase      # Phase 1b
  database: supabase  # Phase 1b

env:
  NEXT_PUBLIC_API_URL: https://api.example.com

resources:
  memory: 1G
  cpu: "2"

health:
  path: /api/health
  interval: 30s
```

**Note:** For Tailwind to work, your project must have:
- `tailwind.config.js`
- PostCSS configured
- CSS imported in `_app.tsx` or layout

---

## Creating Custom Templates

Templates live in `/opt/fabrik/templates/<name>/` with:

```
templates/
└── my-template/
    ├── compose.yaml.j2   # Required - Docker Compose template
    ├── Dockerfile.j2     # Optional - Dockerfile template
    └── defaults.yaml     # Optional - Default env vars
```

### Template Variables

Available in Jinja2 templates:

| Variable | Type | Description |
|----------|------|-------------|
| `spec` | Spec | Full spec object |
| `id` | str | Service ID |
| `domain` | str | Service domain |
| `env` | dict | Environment variables |
| `resources` | Resources | Memory/CPU limits |
| `health` | Health | Health check config |
| `volumes` | list[Volume] | Persistent volumes |
| `depends` | Depends | postgres/redis deps |
| `infrastructure` | Infrastructure | database/storage/auth |

### Example compose.yaml.j2

```jinja2
services:
  {{ spec.id }}:
    build: .
    container_name: {{ spec.id }}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{{ spec.id }}.rule=Host(`{{ domain }}`)"
    environment:
      {% for key, value in env.items() %}
      - {{ key }}={{ value }}
      {% endfor %}
    deploy:
      resources:
        limits:
          memory: {{ resources.memory }}
```

---

## CLI Usage

```bash
# List templates
fabrik templates

# Create spec from template
fabrik new my-api --template python-api --domain api.example.com

# Preview deployment
fabrik plan specs/my-api.yaml

# Deploy
fabrik apply specs/my-api.yaml
```
