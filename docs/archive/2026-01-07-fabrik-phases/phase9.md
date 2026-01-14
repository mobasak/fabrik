# Phase 9: Docker Image Acceleration

**Status:** ✅ COMPLETE (historical implementation)
Accelerate Fabrik development by leveraging battle-tested Docker images instead of building custom solutions.

## Development Workflow Rule

> **Before writing custom code, search for existing Docker solutions.**
>
> Use `python scripts/container_images.py search <need>` to find containerized solutions.
> Many common problems (notifications, PDF generation, search, browser automation) are already solved.

```bash
cd /opt/fabrik && source .venv/bin/activate

# Example: Need PDF generation?
python scripts/container_images.py search pdf
python scripts/container_images.py check-arch gotenberg/gotenberg

# Example: Need a headless CMS?
python scripts/container_images.py search "headless cms"

# Example: Need supply-chain secure images?
python scripts/container_images.py trueforge list
```

This saves weeks of development time by deploying existing solutions instead of building from scratch.

## Architecture Notice

> **⚠️ VPS1 is ARM64 (aarch64)** — All container images MUST support `linux/arm64`.
> Verify with: `python scripts/container_images.py check-arch <image:tag>`

## Legend

- ✅ = ARM64 verified, ready to deploy
- ⚠️ = Needs verification on VPS
- 🎯 = High impact for Fabrik

---

## Infrastructure Improvements

### Immediate Deploy (This Week)

| Image | ARM64 | Replaces | Accelerates |
|-------|-------|----------|-------------|
| `caronc/apprise` | ✅ | Custom notification code | **All projects** - unified notifications to email, Slack, Telegram, Discord, SMS via single API |
| `dpage/pgadmin4` | ✅ | CLI-only DB management | **Ops** - visual database management for all PostgreSQL instances |
| `minio/minio` | ✅ | B2 direct integration | **All projects** - S3-compatible local storage, reduces B2 API calls |
| `n8nio/n8n` | ✅ | Custom integration scripts | **Automation** - visual workflow builder connecting services |

### Near-Term

| Image | ARM64 | Replaces | Accelerates |
|-------|-------|----------|-------------|
| `getmeili/meilisearch` | ✅ | PostgreSQL full-text search | **youtube, trade-intelligence** - fast fuzzy search |
| `browserless/chrome` | ✅ | Local Playwright/Selenium | **youtube, llm_batch_processor** - headless browser as service |
| `gotenberg/gotenberg` | ✅ | WeasyPrint custom code | **proposal-creator** - PDF generation API (HTML/Office to PDF) |

---

## Current Project Acceleration

### youtube (Scraping, Transcription, Comments)

| Image | Purpose | Impact |
|-------|---------|--------|
| `browserless/chrome` ✅ | Headless browser pool | Replace local Selenium, scale scraping |
| `getmeili/meilisearch` ✅ | Search transcripts/comments | Fast full-text search across all content |
| `minio/minio` ✅ | Store video/audio files | S3-compatible storage for media |
| `caronc/apprise` ✅ | Job completion alerts | Notify on scrape complete/errors |

**Code you don't write:**
- Browser pool management
- Search indexing
- Object storage integration
- Multi-channel notifications

### proposal-creator (Document Generation)

| Image | Purpose | Impact |
|-------|---------|--------|
| `gotenberg/gotenberg` ✅ | PDF generation | Replace WeasyPrint with robust API |
| `lscr.io/linuxserver/libreoffice` ⚠️ | Office document conversion | Generate DOCX, PPTX, not just PDF |
| `minio/minio` ✅ | Store generated documents | Client download links |

**Code you don't write:**
- PDF rendering engine
- Office format conversion
- File storage/serving

### calendar-orchestration-engine

| Image | Purpose | Impact |
|-------|---------|--------|
| `nocodb/nocodb` ✅ | Airtable-like UI for data | Visual editing of calendar data |
| `n8nio/n8n` ✅ | Scraper orchestration | Schedule and chain scrapers visually |

### llm_batch_processor (ChatGPT/Claude Automation)

| Image | Purpose | Impact |
|-------|---------|--------|
| `browserless/chrome` ✅ | Headless browser farm | Scale Playwright automation |
| `redis:7-alpine` ✅ | Job queue | Replace DB polling with proper queue |

---

## Future Project Acceleration

### complianceOS (Compliance Management SaaS)

| Image | Purpose | Impact |
|-------|---------|--------|
| `nocodb/nocodb` ✅ | Database UI | Client-facing compliance data entry |
| `directus/directus` ✅ | Headless CMS | API-first content management |
| `gotenberg/gotenberg` ✅ | Report generation | Compliance reports as PDF |
| `lscr.io/linuxserver/bookstack` ⚠️ | Documentation wiki | Client compliance documentation |
| `minio/minio` ✅ | Document storage | Store compliance documents |

**Months saved:** 2-3 months of UI/backend development

### trade-intelligence (Bill of Lading Data)

| Image | Purpose | Impact |
|-------|---------|--------|
| `getmeili/meilisearch` ✅ | Search engine | Fast search across trade records |
| `browserless/chrome` ✅ | Web scraping | Headless scraping at scale |
| `nocodb/nocodb` ✅ | Data exploration | Visual data analysis |
| `metabase/metabase` ⚠️ | BI dashboards | Trade analytics dashboards |

### triggered-content-orchestration (Content Publishing)

| Image | Purpose | Impact |
|-------|---------|--------|
| `n8nio/n8n` ✅ | Workflow automation | Visual content pipeline builder |
| `caronc/apprise` ✅ | Multi-platform posting | Publish to social, email, webhooks |
| `ghost:5` ⚠️ | Blog platform | Self-hosted publishing |
| `strapi/strapi` ⚠️ | Headless CMS | Content management API |

### brand-identity-creator

| Image | Purpose | Impact |
|-------|---------|--------|
| `gotenberg/gotenberg` ✅ | PDF brand guides | Generate brand books |
| `minio/minio` ✅ | Asset storage | Store generated logos/assets |

### ugc (User-Generated Content Collection)

| Image | Purpose | Impact |
|-------|---------|--------|
| `browserless/chrome` ✅ | Forum scraping | Scale forum data collection |
| `getmeili/meilisearch` ✅ | Content search | Search collected content |

---

## Shared Services (Deploy Once, Use Everywhere)

These services benefit ALL Fabrik projects:

| Service | Image | Projects Using |
|---------|-------|----------------|
| **Notifications** | `caronc/apprise` | All - alerts, job status, errors |
| **Object Storage** | `minio/minio` | All - files, media, exports |
| **Search** | `getmeili/meilisearch` | youtube, trade-intelligence, ugc |
| **Browser Farm** | `browserless/chrome` | youtube, llm_batch, trade-intelligence |
| **PDF Generation** | `gotenberg/gotenberg` | proposal-creator, complianceOS |
| **Workflows** | `n8nio/n8n` | Automation, integrations |
| **DB Admin** | `dpage/pgadmin4` | All PostgreSQL projects |

---

## Deployment Priority Matrix

### Week 1: Foundation

```bash
# Deploy these immediately via Coolify
caronc/apprise          # Notifications
dpage/pgadmin4          # DB admin
minio/minio             # Object storage
```

### Week 2-3: Development Acceleration

```bash
# Deploy based on active project
browserless/chrome      # If doing scraping
gotenberg/gotenberg     # If doing PDF generation
getmeili/meilisearch    # If need search
```

### Month 2: Automation & Scale

```bash
n8nio/n8n               # Workflow automation
nocodb/nocodb           # Visual data management
directus/directus       # Headless CMS
```

---

## ROI Estimate

| Category | Images | Dev Time Saved |
|----------|--------|----------------|
| Notifications | apprise | 1-2 weeks |
| PDF Generation | gotenberg | 2-3 weeks |
| Search | meilisearch | 3-4 weeks |
| Browser Automation | browserless | 2 weeks |
| Object Storage | minio | 1 week |
| Workflow Builder | n8n | 4-6 weeks |
| Data UI | nocodb/directus | 4-8 weeks |

**Total potential savings: 3-5 months of development time**

---

## LinuxServer.io High-Value Images

These `lscr.io/linuxserver/*` images accelerate specific development needs:

### Document & Content Processing

| Image | Replaces | Accelerates |
|-------|----------|-------------|
| `libreoffice` | Custom doc conversion | **proposal-creator** - Convert to DOCX, PPTX, ODF |
| `ffmpeg` | Video processing scripts | **youtube** - Transcoding, format conversion |
| `handbrake` | Video encoding code | **youtube** - Batch video transcoding |
| `calibre-web` | eBook management | **content projects** - eBook library/conversion |

### Monitoring & Change Detection

| Image | Replaces | Accelerates |
|-------|----------|-------------|
| `healthchecks` | Custom job monitoring | **All projects** - Cron job health monitoring |
| `changedetection.io` | Custom scraper polling | **trade-intelligence, ugc** - Website change alerts |
| `speedtest-tracker` | Network monitoring scripts | **Ops** - ISP performance history |

### Development & Remote Access

| Image | Replaces | Accelerates |
|-------|----------|-------------|
| `code-server` | Local-only development | **Dev** - VS Code in browser, anywhere |
| `webtop` | - | **Dev** - Full Linux desktop for testing |
| `chromium` | Local browser installs | **llm_batch** - Containerized browser automation |
| `firefox` | Local browser installs | **Testing** - Isolated browser testing |

### Client & Team Collaboration

| Image | Replaces | Accelerates |
|-------|----------|-------------|
| `projectsend` | Custom file sharing | **Client work** - Branded file portal |
| `bookstack` | Notion/Confluence | **Docs** - Self-hosted wiki/documentation |
| `planka` | Trello subscription | **PM** - Self-hosted Kanban boards |
| `monica` | Spreadsheet CRM | **Sales** - Personal CRM for clients |
| `hedgedoc` | Google Docs | **Collab** - Real-time markdown editing |

### File & Media Management

| Image | Replaces | Accelerates |
|-------|----------|-------------|
| `syncthing` | Manual file sync | **Dev** - P2P file sync between WSL/VPS |
| `nextcloud` | Google Drive | **Client work** - Full collaboration suite |
| `lychee` | Custom photo galleries | **Content** - Photo management API |

---

## Quick Reference Commands

```bash
cd /opt/fabrik && source .venv/bin/activate

# Search for new images (Docker Hub)
python scripts/container_images.py search <query>

# Verify ARM64 before deploying (any registry)
python scripts/container_images.py check-arch <image:tag>

# Get recommendations by category
python scripts/container_images.py recommend database
python scripts/container_images.py recommend monitoring

# List available tags (Docker Hub)
python scripts/container_images.py tags <image>

# TrueForge supply-chain secure images
python scripts/container_images.py trueforge list
python scripts/container_images.py trueforge tags <name>
python scripts/container_images.py trueforge info <name>

# LinuxServer.io images
python scripts/container_images.py check-arch lscr.io/linuxserver/<name>:latest
```

---

## TrueForge Supply-Chain Secure Alternatives

When enterprise clients require compliance, attestations, or SBOM, use TrueForge images instead of standard Docker Hub:

| Standard Image | TrueForge Alternative | Use Case |
|----------------|----------------------|----------|
| `caronc/apprise` | `oci.trueforge.org/tccr/apprise-api` ✅ | Notifications with provenance |
| `postgres:16` | `oci.trueforge.org/tccr/postgresql` ✅ | Auditable database |
| `nginx:alpine` | `oci.trueforge.org/tccr/nginx` ✅ | Secure web server |
| `caddy:2` | `oci.trueforge.org/tccr/caddy` ✅ | Auto-HTTPS with attestations |
| Custom whisper | `oci.trueforge.org/tccr/faster-whisper` ✅ | Speech-to-text (youtube project) |
| - | `oci.trueforge.org/tccr/it-tools` ✅ | Developer utilities dashboard |
| Custom webhook | `oci.trueforge.org/tccr/webhook` ✅ | Webhook receiver for automation |
| Dependabot | `oci.trueforge.org/tccr/renovate` ✅ | Dependency update automation |
| Manual DNS | `oci.trueforge.org/tccr/cloudflareddns` ✅ | Dynamic DNS for Cloudflare |
| containrrr/watchtower | `oci.trueforge.org/tccr/watchtower` ✅ | Container update monitoring |

**All TrueForge images include:**
- GitHub Actions attestations
- SBOM (Software Bill of Materials)
- Verifiable provenance
- ARM64 support (99/100 images)

See `/opt/fabrik/docs/reference/trueforge-images.md` for full catalog.

---

## Container Base Image Standard

**Fabrik uses Ubuntu/Debian as the standard base for all custom containers.**

### Base Image Selection

| Use Case | Base Image | Why |
|----------|------------|-----|
| **Production services** | `ubuntu:24.04` | Stable, LTS, familiar tooling |
| **Minimal services** | `debian:bookworm-slim` | Smaller than Ubuntu, same ecosystem |
| **Python apps** | `python:3.12-slim-bookworm` | Debian-based, minimal |
| **Node.js apps** | `node:22-bookworm-slim` | Debian-based, minimal |
| **Supply-chain secure** | `oci.trueforge.org/tccr/ubuntu` ✅ | SBOM + attestations |

### Why Ubuntu/Debian (Not Alpine)

| Factor | Ubuntu/Debian | Alpine |
|--------|---------------|--------|
| **glibc vs musl** | glibc (standard) | musl (compatibility issues) |
| **Python wheels** | Pre-built available | Often need compilation |
| **Debug tools** | Standard tooling | Missing many tools |
| **ARM64 support** | Excellent | Good but some issues |
| **Fabrik team familiarity** | High | Low |

### Dockerfile Template

```dockerfile
# Standard Fabrik Python service
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system deps (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Next Steps

1. [ ] Deploy Week 1 foundation services (apprise, pgadmin4, minio)
2. [ ] Configure apprise notification channels
3. [ ] Set up minio buckets for project storage
4. [ ] Integrate services with existing Fabrik projects
5. [ ] Deploy project-specific services as needed
6. [ ] Evaluate TrueForge for enterprise client deployments
7. [ ] Standardize existing Dockerfiles to Ubuntu/Debian base
