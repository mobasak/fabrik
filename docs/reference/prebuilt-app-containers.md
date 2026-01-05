# Prebuilt Container Strategy

How Fabrik selects and uses prebuilt container images for self-hosted services.

## Architecture Notice

> **⚠️ VPS1 is ARM64 (aarch64)** — All container images MUST support `linux/arm64`.
> Most LinuxServer.io images support multi-arch. Always verify before deploying.

---

## Fabrik Docker Hub Tool

Use the `container_images.py` script to search, evaluate, and select container images.

### Quick Start

```bash
cd /opt/fabrik && source .venv/bin/activate

# Search for images
python scripts/container_images.py search nginx

# Check arm64 support (critical for VPS1)
python scripts/container_images.py check-arch nginx:alpine

# Get image recommendations by category
python scripts/container_images.py recommend database
python scripts/container_images.py recommend monitoring

# List available tags
python scripts/container_images.py tags postgres

# Get detailed image info
python scripts/container_images.py info nginx:alpine

# Pull image to WSL for local testing
python scripts/container_images.py pull nginx:alpine
```

### Workflow: Adding a New Service

1. **Search** for the image: `container_images.py search <name>`
2. **Check arm64** support: `container_images.py check-arch <image:tag>`
3. **Review tags** for production version: `container_images.py tags <image>`
4. **Pull to WSL** for local testing: `container_images.py pull <image:tag>`
5. **Deploy via Coolify** with pinned version tag

### Available Categories

- `database` — PostgreSQL, MariaDB, Redis
- `webserver` — Nginx, Traefik, Caddy
- `monitoring` — Netdata, Uptime Kuma, Prometheus, Grafana
- `backup` — Duplicati, Restic
- `development` — Code Server, Gitea
- `media` — Jellyfin, Plex

---

## Current State

### Infrastructure Services (Prebuilt)

| Service | Source | Image | Purpose |
|---------|--------|-------|---------|
| Duplicati | LinuxServer | `lscr.io/linuxserver/duplicati` | Backup to B2 |
| Netdata | Official | `netdata/netdata` | System monitoring |
| Uptime Kuma | Official | `louislam/uptime-kuma` | Uptime monitoring |
| Coolify | Official | Self-managed | Deployment control plane |
| PostgreSQL | Official | `postgres:16` | Shared database |
| Redis | Official | `redis:7-alpine` | Caching |
| Traefik | Official | `traefik:v3` | Reverse proxy (via Coolify) |

### External Services

| Service | Provider | Purpose |
|---------|----------|---------|
| Backblaze B2 | Backblaze | Object storage for backups |
| Supabase | Supabase | Managed PostgreSQL + pgvector (some projects) |

### Fabrik Custom Services (Built In-House)

| Service | Path | Stack | Port | Purpose |
|---------|------|-------|------|---------|
| fabrik-proxy | `/opt/proxy` | Python/FastAPI | 8000 | Proxy management (Webshare.io) |
| fabrik-captcha | `/opt/captcha` | Python/FastAPI | 8000 | Captcha solving (Anti-Captcha) |
| fabrik-translator | `/opt/translator` | Python/FastAPI | 8000 | Translation (DeepL, Azure) |
| fabrik-dns-manager | `/opt/namecheap` | Python/FastAPI | 8001 | DNS management (Namecheap API) |
| fabrik-emailgateway | `/opt/emailgateway` | Node.js/Fastify | 3000 | Email sending (Resend, SES) |
| fabrik-file-api | `/opt/file-api` | Python/FastAPI | 8000 | File operations API |
| fabrik-file-worker | `/opt/file-worker` | Python | - | Background file processing |
| fabrik-image-broker | `/opt/image-generation` | Python/FastAPI | 8000 | AI image generation (FLUX) |

## Image Source Hierarchy

When deploying a new service, follow this priority:

### 1. LinuxServer.io (Default for ops tools)

**URL:** https://docs.linuxserver.io

**Why:** Consistent PUID/PGID mapping, s6-overlay supervisor, regular security updates, excellent docs.

**Use for:**
- Backup tools (Duplicati, Restic, Borg)
- Media servers (Plex, Jellyfin, Emby)
- Download managers (qBittorrent, SABnzbd, NZBGet)
- Network tools (WireGuard, OpenVPN, Nginx)
- Dashboards (Heimdall, Homer, Organizr)

**Fabrik example:**
```yaml
services:
  duplicati:
    image: lscr.io/linuxserver/duplicati:latest
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=UTC
```

### 2. hotio.dev (Alternative for specific apps)

**URL:** https://hotio.dev

**Why:** Sometimes better maintained for specific apps, especially *arr stack.

**Use for:**
- Sonarr, Radarr, Lidarr, Prowlarr
- When LinuxServer version has issues

**Decision rule:** If app exists in both, check:
1. Which has more recent updates?
2. Which supports your CPU architecture?
3. Which has better docs for your use case?

### 3. Official Images (For core infrastructure)

**Why:** Direct from maintainers, most stable for databases/proxies.

**Use for:**
- PostgreSQL, MySQL, MariaDB
- Redis, Memcached
- Nginx, Traefik, Caddy
- Node.js, Python base images

### 4. TrueForge/ContainerForge (Supply-chain security)

**URL:** https://trueforge.org
**Registry:** `oci.trueforge.org/tccr/<name>`
**Source:** https://github.com/trueforge-org/containerforge

**Why:** GitHub Actions attestations, verifiable provenance, standardized bases, SBOM included.

**Use when:**
- Client requires supply-chain compliance
- Enterprise deployments with audit requirements
- You need SBOM (Software Bill of Materials)
- Security-focused deployments

**Fabrik CLI:**
```bash
cd /opt/fabrik && source .venv/bin/activate

# List all available TrueForge images (requires GITHUB_TOKEN with read:packages scope)
python scripts/container_images.py trueforge list

# Get tags for specific image
python scripts/container_images.py trueforge tags home-assistant

# Get image info with architecture check
python scripts/container_images.py trueforge info home-assistant

# Check ARM64 support
python scripts/container_images.py check-arch oci.trueforge.org/tccr/home-assistant
```

**Pull example:**
```bash
docker pull oci.trueforge.org/tccr/home-assistant:latest
```

**Use cases for Fabrik:**
- **complianceOS**: When clients require auditable container provenance
- **Enterprise projects**: Supply-chain attestations for security compliance
- **Regulated industries**: SBOM requirements for software inventory

### 5. JFrog Artifactory (Future: multi-environment promotion)

**URL:** https://jfrog.com/artifactory

**Why:** Private registry with dev → staging → prod promotion flows.

**Use when:**
- Multiple VPS servers need coordinated deployments
- You want to pin and mirror upstream images
- Team needs access control on image pushes

**Not needed yet** — overhead for single-VPS setup.

---

## Container Registry Platform Comparison

| Platform | How to use with Coolify | Why (in Coolify terms) | Choose it when | Default policy |
|----------|------------------------|------------------------|----------------|----------------|
| **Docker Hub** | Set `image: repo:tag` (or digest). If private, add registry credentials in Coolify. | Fastest path for common building blocks; widest availability. | You need standard infrastructure images (nginx, redis, postgres) or an app image primarily distributed on Docker Hub. | Use, but **pin versions** (`:1.2.3`) or **digest** for production; avoid floating `latest`. |
| **GHCR** | Use `image: ghcr.io/org/image:tag`. For private images, add GitHub token (PAT) in Coolify registry credentials. | Best when your code and CI are on GitHub; easiest "build in GitHub Actions → deploy from GHCR". | You build/own services or rely on OSS projects publishing releases to GHCR. | Preferred for **your own images** if repo is on GitHub; tag releases (`vX.Y.Z`) and optionally pin digests. |
| **LinuxServer.io** | Use `image: lscr.io/linuxserver/<app>:tag`; set required env/volumes (PUID/PGID/TZ etc.), map persistent volumes. | Quick deploy of off-the-shelf apps with consistent configuration patterns and good docs. | You want to add a utility/service quickly without maintaining Dockerfiles. | Use only images that match VPS architecture (**arm64**). Prefer explicit tags over `latest`. |
| **TrueForge** | Use `image: oci.trueforge.org/tccr/<app>:tag`. List images via `container_images.py trueforge list`. | Supply-chain security with attestations, SBOM, verifiable provenance. | Client requires compliance, enterprise audits, or regulated industry deployment. | Use for security-critical deployments. Verify arm64 support per image. |
| **hotio.dev** | Use `image: hotio/<app>:tag` per hotio docs; configure env/volumes. | Alternative curated publisher; sometimes better-maintained for specific apps. | The specific app works better / is maintained better in hotio than elsewhere. | Don't mix LinuxServer and hotio arbitrarily—pick per app based on maintenance + arch support. |
| **JFrog** | Add JFrog registry to Coolify (URL + credentials). Deploy using `image: <registry>/<repo>/<image>:tag`. Optionally mirror upstream images. | Governance: one controlled source, access control, promotion (dev→staging→prod), less dependency on public pulls. | You have multiple environments, multiple servers, need controlled rollout, or want to mirror upstream images. | Not needed for single VPS. Consider when introducing staging/multi-server. |

---

## Coolify Deployment Policy

> **DONE =** Every Coolify app deploys from pinned, architecture-compatible images, and you can roll back reliably.

### Policy Rules

1. **Fabrik custom services**: Build in CI → push to **GHCR** → Coolify pulls `ghcr.io/...:vX.Y.Z`
2. **3rd-party services**: Pull from Docker Hub / LinuxServer / hotio, but **pin versions** (or digest) and ensure **arm64 compatibility**
3. **When adding staging or multi-server**: Introduce a registry layer (JFrog) and optionally mirror upstream images

### Version Pinning Examples

```yaml
# ❌ BAD - floating tag
image: lscr.io/linuxserver/duplicati:latest

# ✅ GOOD - pinned version
image: lscr.io/linuxserver/duplicati:2.0.8

# ✅ BEST - pinned digest (immutable)
image: lscr.io/linuxserver/duplicati@sha256:abc123...
```

### Architecture Verification

Before deploying any new image, verify arm64 support:

```bash
# Check if image supports arm64
docker manifest inspect <image:tag> | grep -i arm64

# Or pull and check
docker pull --platform linux/arm64 <image:tag>
```

---

## Fabrik Future Project Use Cases

### Media Server Stack (for content sites)

```yaml
# All from LinuxServer
services:
  jellyfin:
    image: lscr.io/linuxserver/jellyfin:latest
  sonarr:
    image: lscr.io/linuxserver/sonarr:latest
  radarr:
    image: lscr.io/linuxserver/radarr:latest
  prowlarr:
    image: lscr.io/linuxserver/prowlarr:latest
  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent:latest
```

**Fabrik integration:** Deploy via Coolify, monitor via Netdata, backup configs via Duplicati.

### Code/Git Server (for client projects)

```yaml
services:
  gitea:
    image: gitea/gitea:latest  # Official
  # or
  gitlab:
    image: gitlab/gitlab-ce:latest  # Official
  drone:
    image: drone/drone:latest  # CI/CD
```

**Fabrik integration:** Internal Git for client codebases, CI/CD pipelines.

### Monitoring Stack (enhanced observability)

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
  grafana:
    image: grafana/grafana:latest
  loki:
    image: grafana/loki:latest
  uptime-kuma:
    image: louislam/uptime-kuma:latest
```

**Fabrik integration:** Replace/complement Netdata for multi-service dashboards.

### Document/Wiki System (for project documentation)

```yaml
services:
  bookstack:
    image: lscr.io/linuxserver/bookstack:latest
  # or
  wikijs:
    image: ghcr.io/requarks/wiki:latest
  # or
  outline:
    image: outlinewiki/outline:latest
```

**Fabrik integration:** Internal documentation for clients, runbooks.

### File Sync/Storage (for client file sharing)

```yaml
services:
  nextcloud:
    image: lscr.io/linuxserver/nextcloud:latest
  # or
  seafile:
    image: seafileltd/seafile-mc:latest
  syncthing:
    image: lscr.io/linuxserver/syncthing:latest
```

**Fabrik integration:** Client file portals, cross-device sync.

### Password/Secret Management

```yaml
services:
  vaultwarden:
    image: vaultwarden/server:latest
```

**Fabrik integration:** Team password management, API key storage.

---

## Selection Checklist

Before deploying any prebuilt container:

- [ ] **Architecture:** Supports `linux/arm64` (VPS is ARM-based)
- [ ] **Maintenance:** Updated within last 3 months
- [ ] **Docs:** Clear volume/env configuration documented
- [ ] **Coolify:** Can deploy via Docker Compose
- [ ] **Backup:** Data volumes identified for Duplicati
- [ ] **Health:** Has health check endpoint or can add one

## Deployment Pattern

All prebuilt containers follow this Fabrik pattern:

```yaml
services:
  service-name:
    image: source/image:tag
    container_name: service-name
    restart: unless-stopped
    environment:
      - PUID=1000  # LinuxServer only
      - PGID=1000  # LinuxServer only
      - TZ=UTC
    volumes:
      - service-config:/config
      - service-data:/data
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.service-name.rule=Host(`service.vps1.ocoron.com`)"
      - "traefik.http.routers.service-name.tls.certresolver=letsencrypt"
    networks:
      - coolify

networks:
  coolify:
    external: true
```

## References

- [LinuxServer.io Fleet](https://fleet.linuxserver.io/) — Full image catalog
- [hotio.dev Containers](https://hotio.dev/containers/) — Alternative images
- [Awesome-Selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) — Discovery

---

## LinuxServer.io Complete Image Catalog

All images use format: `lscr.io/linuxserver/<name>:latest`

### Media Servers & Streaming

| Image | Use Case for Fabrik |
|-------|---------------------|
| `plex` | Premium media server for client video/audio libraries |
| `jellyfin` | Open-source Plex alternative, no license needed |
| `emby` | Media server with live TV support |
| `tautulli` | Plex analytics and monitoring dashboard |
| `synclounge` | Synchronized Plex viewing for remote teams |

### Media Management (*arr Stack)

| Image | Use Case for Fabrik |
|-------|---------------------|
| `sonarr` | TV show tracking and acquisition |
| `radarr` | Movie tracking and acquisition |
| `lidarr` | Music library management |
| `prowlarr` | Indexer manager for *arr apps |
| `bazarr` | Subtitle management for Sonarr/Radarr |
| `mylar3` | Comic book management |
| `lazylibrarian` | eBook/audiobook management |
| `kavita` | eBook/manga server with reader |
| `kometa` | Plex metadata manager (formerly Plex Meta Manager) |

### Download Clients

| Image | Use Case for Fabrik |
|-------|---------------------|
| `qbittorrent` | BitTorrent client with web UI |
| `transmission` | Lightweight torrent client |
| `deluge` | Feature-rich torrent client |
| `sabnzbd` | Usenet downloader |
| `nzbget` | High-performance Usenet downloader |
| `nzbhydra2` | Usenet meta-search |
| `pyload-ng` | General download manager |

### File Storage & Sync

| Image | Use Case for Fabrik |
|-------|---------------------|
| `nextcloud` | Full-featured file sync & collaboration platform |
| `syncthing` | Peer-to-peer file synchronization |
| `resilio-sync` | Fast file sync (BitTorrent protocol) |
| `projectsend` | File sharing portal for clients |
| `pairdrop` | Local network file sharing (AirDrop alternative) |
| `lychee` | Photo management and sharing |
| `piwigo` | Photo gallery with user management |

### Documentation & Wiki

| Image | Use Case for Fabrik |
|-------|---------------------|
| `bookstack` | Wiki/documentation platform (recommended) |
| `wikijs` | Modern wiki with Git backend |
| `dokuwiki` | Simple wiki, no database needed |
| `grav` | Flat-file CMS for docs sites |
| `raneto` | Markdown-based knowledge base |
| `hedgedoc` | Collaborative markdown editor |

### Dashboards & Organization

| Image | Use Case for Fabrik |
|-------|---------------------|
| `heimdall` | Application dashboard (simple) |
| `planka` | Trello-like project management |
| `grocy` | Inventory/task management |
| `monica` | Personal CRM for client relationships |
| `your_spotify` | Spotify listening analytics |

### Network & DNS

| Image | Use Case for Fabrik |
|-------|---------------------|
| `wireguard` | VPN server for secure access |
| `nginx` | Web server / reverse proxy |
| `swag` | Nginx + Let's Encrypt + fail2ban bundle |
| `ddclient` | Dynamic DNS updater |
| `duckdns` | DuckDNS dynamic DNS client |
| `adguardhome-sync` | AdGuard Home config sync |
| `smokeping` | Network latency monitoring |
| `speedtest-tracker` | Internet speed history tracking |

### Security & Access

| Image | Use Case for Fabrik |
|-------|---------------------|
| `fail2ban` | Intrusion prevention |
| `openssh-server` | SSH jump server |
| `ldap-auth` | LDAP authentication proxy |
| `socket-proxy` | Secure Docker socket proxy |
| `pwndrop` | Self-hosted file sharing for red team |

### Development Tools

| Image | Use Case for Fabrik |
|-------|---------------------|
| `code-server` | VS Code in browser |
| `openvscode-server` | Official VS Code server |
| `gitqlient` | Git GUI client |
| `pycharm` | JetBrains PyCharm in browser |
| `intellij-idea` | JetBrains IntelliJ in browser |
| `python` | Python base image with LSIO mods |

### Database Tools

| Image | Use Case for Fabrik |
|-------|---------------------|
| `mariadb` | MySQL-compatible database |
| `phpmyadmin` | MySQL/MariaDB web admin |
| `mysql-workbench` | MySQL GUI client |
| `sqlitebrowser` | SQLite GUI |

### Backup & Recovery

| Image | Use Case for Fabrik |
|-------|---------------------|
| `duplicati` | Backup to cloud (B2, S3, etc.) ✅ IN USE |
| `rsnapshot` | Filesystem snapshots |

### Monitoring & Analytics

| Image | Use Case for Fabrik |
|-------|---------------------|
| `healthchecks` | Cron job monitoring |
| `librespeed` | Self-hosted speed test |
| `changedetection.io` | Website change monitoring |
| `hishtory-server` | Shell history sync server |

### Communication

| Image | Use Case for Fabrik |
|-------|---------------------|
| `thelounge` | IRC web client |
| `znc` | IRC bouncer |
| `mastodon` | Fediverse social network |
| `signal` | Signal messenger desktop |
| `telegram` | Telegram desktop client |
| `webcord` | Discord web client |

### Notifications & Automation

| Image | Use Case for Fabrik |
|-------|---------------------|
| `apprise-api` | Universal notification API |
| `overseerr` | Media request management |
| `ombi` | Media request system |
| `flexget` | Media automation |

### Remote Desktop & GUI Apps

| Image | Use Case for Fabrik |
|-------|---------------------|
| `webtop` | Full Linux desktop in browser |
| `rdesktop` | Remote desktop client |
| `remmina` | Remote desktop client (RDP, VNC, SSH) |
| `firefox` | Firefox browser in container |
| `chromium` | Chromium browser in container |
| `chrome` | Chrome browser in container |
| `brave` | Brave browser in container |
| `librewolf` | Privacy-focused Firefox fork |
| `obsidian` | Note-taking app |

### Creative & Design

| Image | Use Case for Fabrik |
|-------|---------------------|
| `gimp` | Image editing |
| `inkscape` | Vector graphics |
| `blender` | 3D modeling |
| `kdenlive` | Video editing |
| `shotcut` | Video editing |
| `openshot` | Video editing |
| `darktable` | RAW photo processing |
| `rawtherapee` | RAW photo processing |
| `audacity` | Audio editing |
| `ardour` | Digital audio workstation |
| `handbrake` | Video transcoding |
| `ffmpeg` | Media conversion CLI |

### Office & Productivity

| Image | Use Case for Fabrik |
|-------|---------------------|
| `libreoffice` | Office suite |
| `onlyoffice` | Collaborative office suite |
| `calibre` | eBook management |
| `calibre-web` | eBook web interface |
| `joplin` | Note-taking with sync |
| `zotero` | Research/citation manager |

### 3D Printing & CAD

| Image | Use Case for Fabrik |
|-------|---------------------|
| `freecad` | 3D CAD modeling |
| `orcaslicer` | 3D print slicer |
| `cura` | 3D print slicer |
| `bambustudio` | Bambu Lab printer slicer |
| `kicad` | PCB design |

### Gaming & Emulation

| Image | Use Case for Fabrik |
|-------|---------------------|
| `retroarch` | Multi-system emulator |
| `steamos` | Steam gaming in container |
| `pcsx2` | PlayStation 2 emulator |
| `rpcs3` | PlayStation 3 emulator |
| `duckstation` | PlayStation 1 emulator |
| `dolphin` | GameCube/Wii emulator |
| `mame` | Arcade emulator |
| `dosbox-staging` | DOS emulator |
| `scummvm` | Point-and-click adventure games |

### Home Automation

| Image | Use Case for Fabrik |
|-------|---------------------|
| `homeassistant` | Home automation hub |
| `habridge` | Philips Hue emulation |

### Specialty Tools

| Image | Use Case for Fabrik |
|-------|---------------------|
| `babybuddy` | Baby tracking app |
| `kimai` | Time tracking |
| `netbootxyz` | Network boot server |
| `minisatip` | SAT>IP server |
| `tvheadend` | TV streaming server |
| `oscam` | Card sharing server |

---

## Fabrik Acceleration Map

Comprehensive analysis of Docker images that accelerate Fabrik development by replacing custom code with battle-tested solutions.

### Legend

- ✅ = ARM64 verified, ready to deploy
- ⚠️ = Needs verification on VPS
- 🎯 = High impact for Fabrik

---

## Infrastructure Improvements

### Immediate Deploy (This Week)

| Image | ARM64 | Replaces | Accelerates |
|-------|-------|----------|-------------|
| `caronc/apprise` ✅ | ✅ | Custom notification code | **All projects** - unified notifications to email, Slack, Telegram, Discord, SMS via single API |
| `dpage/pgadmin4` ✅ | ✅ | CLI-only DB management | **Ops** - visual database management for all PostgreSQL instances |
| `minio/minio` ✅ | ✅ | B2 direct integration | **All projects** - S3-compatible local storage, reduces B2 API calls |
| `n8nio/n8n` ✅ | ✅ | Custom integration scripts | **Automation** - visual workflow builder connecting services |

### Near-Term (This Month)

| Image | ARM64 | Replaces | Accelerates |
|-------|-------|----------|-------------|
| `getmeili/meilisearch` ✅ | ✅ | PostgreSQL full-text search | **youtube, trade-intelligence** - fast fuzzy search |
| `browserless/chrome` ✅ | ✅ | Local Playwright/Selenium | **youtube, llm_batch_processor** - headless browser as service |
| `gotenberg/gotenberg` ✅ | ✅ | WeasyPrint custom code | **proposal-creator** - PDF generation API (HTML/Office to PDF) |

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
| `lscr.io/linuxserver/libreoffice` | Office document conversion | Generate DOCX, PPTX, not just PDF |
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
# Deploy these immediately
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
