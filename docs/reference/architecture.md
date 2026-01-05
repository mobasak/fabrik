# Fabrik Architecture

**Last Updated:** 2025-12-27

---

## Overview

Fabrik is a spec-driven deployment automation CLI. You write a YAML spec file describing what you want deployed, and Fabrik handles the rest.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FABRIK CLI                                     │
│                                                                          │
│   fabrik new my-api --template python-api                                │
│   fabrik plan specs/my-api.yaml                                          │
│   fabrik apply specs/my-api.yaml                                         │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         SPEC LOADER                                      │
│                                                                          │
│   • Parses YAML spec files                                               │
│   • Validates schema (required fields, types)                            │
│   • Sets defaults for optional fields                                    │
│   • Returns typed Pydantic model                                         │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       TEMPLATE RENDERER                                  │
│                                                                          │
│   • Takes validated spec + template                                      │
│   • Generates compose.yaml, Dockerfile, configs                          │
│   • Variable substitution from spec.env                                  │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          DRIVERS                                         │
│                                                                          │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│   │  DNS        │  │  Coolify    │  │  Uptime     │  │  Supabase   │    │
│   │  Client     │  │  Client     │  │  Kuma       │  │  (Phase 1b) │    │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│          │                │                │                │           │
└──────────┼────────────────┼────────────────┼────────────────┼───────────┘
           │                │                │                │
           ▼                ▼                ▼                ▼
    ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
    │ Namecheap  │   │  Coolify   │   │   Uptime   │   │  Supabase  │
    │   API      │   │    API     │   │    Kuma    │   │    API     │
    └────────────┘   └────────────┘   └────────────┘   └────────────┘
```

---

## Core Components

### 1. Spec Loader (`spec_loader.py`) ✅ Implemented

**Status:** Complete (2025-12-23)

**Purpose:** Parse and validate YAML spec files into typed Python objects.

**Why it exists:**
- **Single source of truth** for spec schema
- **Fail fast** — Invalid specs rejected before any deployment starts
- **Type safety** — All downstream code works with validated objects, not raw dicts
- **Default values** — Missing optional fields get sensible defaults

**Key Models:**

| Model | Purpose |
|-------|---------|
| `Spec` | Main deployment specification |
| `Kind` | Service type (service/worker) |
| `Source` | App source (template/git/docker) |
| `Infrastructure` | Backend options (database/storage/auth) |
| `Depends` | Service dependencies (postgres/redis) |

**Public Functions:**

```python
from fabrik import load_spec, save_spec, create_spec, Spec

# Load from YAML
spec = load_spec("specs/my-api.yaml")

# Create programmatically
spec = create_spec(id="my-api", template="python-api", domain="api.example.com")

# Save to file
save_spec(spec, "specs/my-api.yaml")
```

**Validation Examples:**
- ID must be DNS-safe (`^[a-z0-9][a-z0-9-]*[a-z0-9]$`)
- HTTP services require domain
- Git source requires repository URL
- Docker source requires image name

---

### 2. Template Renderer (`template_renderer.py`) ✅ Implemented

**Status:** Complete (2025-12-23)

**Purpose:** Generate deployment files from spec + template.

**Why it exists:**
- **DRY** — Common patterns (Python API, Node API, WordPress) defined once as templates
- **Consistency** — All services follow same structure
- **Variable substitution** — `${VAR}` replaced with spec values

**Input:** Validated `Spec` + template name
**Output:** Generated `compose.yaml`, `Dockerfile`, config files

```python
from fabrik.template_renderer import render_template

files = render_template(spec, template="python-api")
# Returns dict of filename -> content
```

---

### 3. Drivers

**Purpose:** Communicate with external services.

| Driver | Service | Operations |
|--------|---------|------------|
| `DNSClient` | Namecheap + Cloudflare APIs | Add/remove DNS records |
| `CoolifyClient` | Coolify API | Create apps, deploy, manage env vars |
| `UptimeKumaClient` | Uptime Kuma | Add/remove monitors |
| `SupabaseClient` | Supabase (Phase 1b) | Auth, database, vectors |
| `R2Client` | Cloudflare R2 (Phase 1b) | Presigned URLs, bucket management |

---

### 4. CLI Commands

| Command | Purpose |
|---------|---------|
| `fabrik new <name> --template <t>` | Create new spec from template |
| `fabrik plan <spec>` | Show what will change (dry run) |
| `fabrik apply <spec>` | Execute deployment |
| `fabrik status <spec>` | Check deployment status |
| `fabrik logs <spec>` | View service logs |

---

## Data Flow Example

```
User runs: fabrik apply specs/my-api.yaml

1. CLI parses args
2. spec_loader.load_spec("specs/my-api.yaml")
   → Validates YAML, returns Spec object
3. template_renderer.render_template(spec, "python-api")
   → Generates compose.yaml, Dockerfile
4. dns_client.add_subdomain(spec.domain)
   → Creates DNS record
5. coolify_client.create_application(spec)
   → Creates app in Coolify
6. coolify_client.deploy()
   → Triggers deployment
7. uptime_kuma_client.add_http_monitor(spec.domain)
   → Adds monitoring
8. Print success summary
```

---

## Spec File Example

```yaml
id: my-api
kind: service
template: python-api
domain: myapi.vps1.ocoron.com

depends:
  postgres: main

env:
  LOG_LEVEL: INFO
  API_KEY: ${secrets.API_KEY}

resources:
  memory: 512M
  cpu: 1

health:
  path: /health
  interval: 30s
```

---

## Directory Structure

```
/opt/fabrik/
├── src/fabrik/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── config.py            # Environment config
│   ├── spec_loader.py       # YAML parsing + validation
│   ├── template_renderer.py # Template → files
│   └── drivers/
│       ├── __init__.py
│       ├── dns.py           # DNS operations
│       ├── coolify.py       # Coolify API
│       └── uptime_kuma.py   # Monitoring
├── templates/               # Service templates
│   ├── python-api/
│   ├── node-api/
│   └── wordpress/
├── specs/                   # Deployment specs
└── docs/reference/
    ├── Phase1.md
    ├── Phase1b.md           # Supabase + R2
    ├── Phase1c.md           # Cloudflare DNS
    └── architecture.md      # This file
```

---

## Phase Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| **1** | Foundation (CLI, drivers, templates) | ✅ Complete |
| **1b** | Cloud Infrastructure (Supabase, R2) | Pending |
| **1c** | Cloudflare DNS Migration | ✅ Complete |
| **2** | WordPress Automation | Deferred |
| **3** | AI Content Integration | Deferred |

---

## Coolify-Managed Services

The following services are deployed via Coolify with GitHub webhook auto-deploy:

| Service | Domain | GitHub Repo |
|---------|--------|-------------|
| captcha | captcha.vps1.ocoron.com | mobasak/captcha |
| dns-manager | dns.vps1.ocoron.com | mobasak/dns-manager |
| translator | translator.vps1.ocoron.com | mobasak/translator |
| emailgateway | emailgateway.vps1.ocoron.com | mobasak/emailgateway |
| image-broker | images.vps1.ocoron.com | mobasak/image-broker |
| proxy | proxy.vps1.ocoron.com | mobasak/proxy |
| file-api | files-api.vps1.ocoron.com | mobasak/file-api |
| file-worker | (background worker) | mobasak/file-worker |

**Coolify UI:** https://coolify.vps1.ocoron.com

**Auto-deploy:** Push to GitHub → Webhook → Coolify rebuilds & deploys

---

## Infrastructure Services

Core platform services running on VPS:

| Service | URL | Purpose |
|---------|-----|--------|
| Coolify | https://coolify.vps1.ocoron.com | Container orchestration, deployment management |
| Traefik | (internal) | Reverse proxy, SSL termination, routing |
| Uptime Kuma | https://status.vps1.ocoron.com | Uptime monitoring, alerts |
| Netdata | https://netdata.vps1.ocoron.com | Real-time server metrics |
| Duplicati | (internal) | Postgres backup to Backblaze B2 |
| postgres-main | (internal) | Shared PostgreSQL database |
| redis-main | (internal) | Shared Redis cache |
