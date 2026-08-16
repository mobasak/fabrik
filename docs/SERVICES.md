# Required Services

**Last Updated:** 2026-06-02 (Coolify rows removed; all services now run as standalone Compose stacks under `/opt/<svc>/` with stable `container_name:` and are deployed via `fabrik apply` SSH+Compose). Backrest replaces Duplicati [migrated 2026-04-17]; Authelia, Gotenberg, MeiliSearch present; monitoring stack [Prometheus/Grafana/Loki/Promtail/Alertmanager/cAdvisor/node-exporter] runs as `/opt/monitoring/`.

Services Fabrik needs to function.

## About Fabrik

**Fabrik is a CLI tool, not a deployed service.** It runs from WSL and orchestrates deployments to VPS via `fabrik apply` (SSH + Docker Compose). There are no daemons, watchdogs, or health endpoints for Fabrik itself.

```bash
# Fabrik runs as a command, not a service
fabrik apply my-site    # Execute and exit
fabrik plan my-api      # Execute and exit
```

## Services This Project Runs

| Service | Port | Health Endpoint | Watchdog | Purpose |
|---------|------|-----------------|----------|---------|
| Fabrik CLI | - | - | - | Command-line tool (not a daemon) |

## External Dependencies

| Service | Required | Purpose | Fallback |
|---------|----------|---------|----------|
| **SSH access to VPS** | Yes | Container deployment via `fabrik apply` (SSH + Docker Compose) | None |
| **PostgreSQL** (`postgres-main`) | Yes | Shared database | None |
| **DNS Manager** (site-provisioner / Cloudflare) | Yes | DNS management | — |
| **Backblaze B2** | Yes | Backup storage (via Backrest + restic) | None |
| **Redis** (`redis-main`) | Optional | Caching | Works without |


## VPS Services (managed by fabrik via SSH + Docker Compose)

> **⚠️ Service-status drift warning (2026-06-02):** the table below lists services that were planned/deployed under the Coolify era. **Many are not currently live**. Authoritative inventory: [`docs/infrastructure/vps-complete-inventory.md`](infrastructure/vps-complete-inventory.md) (live state) and [`docs/infrastructure/vps-urls.md`](infrastructure/vps-urls.md) (URL reality vs. claims). Specifically: `image-broker` was retired 2026-06-02 (row kept here only for historical reference); `dns-manager`, `translator`, `captcha`, `file-api`, `netdata` have no live Traefik router or backing container today either. The infra rows (`postgres-main`, `redis-main`, `backrest`, `gatus`, `gotenberg`, `browserless`, `meilisearch`, `n8n`, `apprise`, `traefik`, `authelia`, `prometheus`, `grafana`, `loki`, `glitchtip-*`) ARE live.

| Service | Container | Port | URL | Protection | Purpose |
|---------|-----------|------|-----|------------|---------|
| PostgreSQL | postgres-main | 5432 | - (mesh-only via 10.99.0.1) | 🔐 Password | Shared database |
| Redis | redis-main | 6379 | - (internal) | 🔒 Internal | Caching (optional) |
| ~~Netdata~~ | ~~netdata~~ | ~~19999~~ | ~~`netdata.vps1.ocoron.com`~~ | — | **REMOVED 2026-05-30** — metrics now via node-exporter + cAdvisor → Prometheus → Grafana |
| Gatus | gatus | 3001 | `https://status.vps1.ocoron.com` | 🔐 Password | Service monitoring |
| Backrest | backrest | 9898 | `https://backup.vps1.ocoron.com` | 🔐 Authelia 2FA | Backup management (restic + Backblaze B2; replaced Duplicati 2026-04-17) |
| ~~Image Broker~~ | ~~image-broker~~ | ~~8010~~ | ~~`https://images.vps1.ocoron.com`~~ | — | **REMOVED 2026-06-02** — spec retired; row kept for history |
| ~~DNS Manager~~ | ~~dns-manager~~ | ~~8001~~ | ~~`dns.vps1.ocoron.com`~~ | — | **RETIRED** — not deployed (DNS handled directly via Cloudflare driver) |
| ~~Translator~~ | ~~translator~~ | ~~8000~~ | ~~`translator.vps1.ocoron.com`~~ | — | **RETIRED** — not deployed |
| ~~Captcha~~ | ~~captcha~~ | ~~8000~~ | ~~`captcha.vps1.ocoron.com`~~ | — | **RETIRED** — not deployed |
| ~~File API~~ | ~~file-api~~ | ~~8004~~ | ~~`files-api.vps1.ocoron.com`~~ | — | **RETIRED** — not deployed |
| Browserless | browserless | 3000 | `https://browser.vps1.ocoron.com` | 🔑 API Key | Headless Chrome for scraping/extensions |
| Gotenberg | gotenberg | 3003 | `https://pdf.vps1.ocoron.com` | ⚠️ Open | PDF generation |
| ~~MinIO~~ | ~~minio~~ | ~~9000/9001~~ | ~~`s3.vps1.ocoron.com`~~ | — | **RETIRED** — not deployed (object storage via Backblaze B2 / Cloudflare R2 directly) |
| Apprise | apprise | — (Traefik) | `https://notify.vps1.ocoron.com` | ⚠️ Open | Unified notifications (internal 8000; no host port) |
| Meilisearch | meilisearch | 7700 | `https://search.vps1.ocoron.com` | 🔑 API Key | Fast full-text search |
| Loki | loki | 3100 | internal only | 🔒 Internal | Log aggregation |
| Promtail | promtail | — | internal only | 🔒 Internal | Log shipper (Docker → Loki) |
| Prometheus | prometheus | 9090 | internal only | 🔒 Internal | Metrics collection (15d retention) |
| Node Exporter | node-exporter | 9100 | internal only | 🔒 Internal | Host system metrics |
| cAdvisor | cadvisor | 8080 | internal only | 🔒 Internal | Container metrics |
| Grafana | grafana | 3002 | `https://monitor.vps1.ocoron.com` | 🔐 Password | Dashboards & alerting |
| n8n | n8n | 5678 | `https://auto.vps1.ocoron.com` | 🔐 Password | Business automation & webhook pipelines |

All services use Traefik reverse proxy on ports 80/443. Mesh-only services (postgres-main, redis-main, loki, etc.) bind only to `10.99.0.1` (Wireguard hub interface).

**Protection Legend:**
- 🔐 **Password** — Requires login (basicauth or app login)
- 🔑 **API Key** — Requires API key header
- 🔒 **Internal** — No external access, Docker network only
- ⚠️ **Open** — Publicly accessible (needs auth added)

See [vps-urls.md](infrastructure/vps-urls.md) for complete URL reference.

## Startup Order

For VPS setup (one-time): run `./scripts/bootstrap/bootstrap-vps.sh root@<new-ip> vpsN` — see [`docs/infrastructure/vps-bootstrap-plan.md`](infrastructure/vps-bootstrap-plan.md). Order (per the script's 17 steps, 00-16): system → Docker + fabrik network → Wireguard mesh → DOCKER-USER chain → monitoring agents → Traefik → DNS records → AI sysadmin pack (step 14) → aro-wake (step 15) → compose-boot reboot-race safety net (step 16).

For Fabrik usage (each run):

1. Ensure VPS is accessible via SSH (`ssh vps1`)
2. Run `fabrik apply specs/services/<id>.yaml` (auto-routes to the right host via `target_vps`)

## Health Checks

### PostgreSQL

```bash
ssh deploy@vps "docker exec postgres-main pg_isready"
```

### Gatus

```bash
curl -s https://status.vps1.ocoron.com
```

### ~~Image Broker~~ (REMOVED 2026-06-02)

Historical — the spec was retired. The example below will fail (NXDOMAIN); kept for reference.

```bash
curl -s https://images.vps1.ocoron.com/api/v1/health
```

### Retired services (no health endpoint)

`netdata`, `dns-manager`, `captcha`, `translator`, `file-api`, `minio` are no
longer deployed — their `*.vps1.ocoron.com` subdomains return NXDOMAIN. See the
service table above for retirement notes.

## Service Integration

### Standard URL Pattern

All services follow this pattern:

| Environment | URL Format | Example |
|-------------|------------|---------|
| **WSL (local)** | `http://localhost:<port>` | `http://localhost:8001` |
| **VPS (Docker)** | `http://<container>:<port>` | `http://site-provisioner:8001` |
| **External** | `https://<subdomain>.vps1.ocoron.com` | `https://provision.vps1.ocoron.com` |

### Code Pattern

```python
import os
import httpx

# Defaults to localhost for local dev, override in compose.yaml for VPS
SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:<port>")
response = httpx.get(f"{SERVICE_URL}/endpoint")
```

### Environment Setup

> **⚠️ RETIRED — not deployed.** `captcha`, `dns-manager`, and `translator` were all retired; their `*.vps1.ocoron.com` subdomains return NXDOMAIN. DNS is now handled directly via the Cloudflare driver (`src/fabrik/drivers/cloudflare.py`). The env blocks below are kept for historical reference only.

```yaml
# compose.yaml (VPS deployment)
environment:
  - CAPTCHA_URL=http://captcha:8000
  - DNS_MANAGER_URL=http://dns-manager:8001
  - TRANSLATOR_URL=http://translator:8000
```

```bash
# .env (WSL local dev) - optional, localhost is default
CAPTCHA_URL=http://localhost:8000
DNS_MANAGER_URL=http://localhost:8001
```

### Service Reference

| Service | Container | Port | Env Var | Auth |
|---------|-----------|------|---------|------|
| Captcha | `captcha` | 8000 | `CAPTCHA_URL` | None |
| DNS Manager | `dns-manager` | 8001 | `DNS_MANAGER_URL` | None |
| Translator | `translator` | 8000 | `TRANSLATOR_URL` | `X-API-Key` header |
| File API | `file-api` | 8004 | `FILE_API_URL` | None |
| ~~Image Broker~~ | ~~`image-broker`~~ | ~~8010~~ | ~~`IMAGE_BROKER_URL`~~ | **REMOVED 2026-06-02** |
| PostgreSQL | `postgres-main` | 5432 | `DATABASE_URL` | Password |

---

## ~~Translator Service Integration~~ (RETIRED — not deployed)

> **⚠️ RETIRED — not deployed.** The translator microservice was retired; `translator.vps1.ocoron.com` returns NXDOMAIN. Section kept for historical reference.

**Purpose:** Multi-provider translation (DeepL primary, Azure fallback)

### Usage

```python
import os
import httpx

TRANSLATOR_URL = os.getenv("TRANSLATOR_URL", "http://localhost:8000")
TRANSLATOR_API_KEY = os.getenv("TRANSLATOR_API_KEY")

# Single text translation
response = httpx.post(
    f"{TRANSLATOR_URL}/translate",
    headers={"X-API-Key": TRANSLATOR_API_KEY},
    json={"text": "Hello world", "target_language": "DE"},
    timeout=30
)
result = response.json()
# {"success": true, "result": {"translated_text": "Hallo Welt", ...}}

# Batch translation
response = httpx.post(
    f"{TRANSLATOR_URL}/translate/batch",
    headers={"X-API-Key": TRANSLATOR_API_KEY},
    json={"texts": ["Hello", "Goodbye"], "target_language": "FR"},
    timeout=60
)
```

### Environment Setup

```yaml
# compose.yaml (VPS)
environment:
  - TRANSLATOR_URL=http://translator:8000
  - TRANSLATOR_API_KEY=${TRANSLATOR_API_KEY}
```

```bash
# .env (WSL)
TRANSLATOR_URL=http://localhost:8000
TRANSLATOR_API_KEY=your-api-key
```

### Health Check

```bash
curl https://translator.vps1.ocoron.com/health
```

See `/opt/translator/README.md` for full API documentation.

---

## ~~Captcha Service Integration~~ (RETIRED — not deployed)

> **⚠️ RETIRED — not deployed.** The captcha microservice was retired; `captcha.vps1.ocoron.com` returns NXDOMAIN. Section kept for historical reference.

**Purpose:** Solve reCAPTCHA, hCaptcha, Turnstile via Anti-Captcha API

**Database:** None (stateless)
**Auth:** ⚠️ None (TODO: add API key)

### Usage

```python
import os
import httpx

CAPTCHA_URL = os.getenv("CAPTCHA_URL", "http://localhost:8000")

# Solve reCAPTCHA v2
response = httpx.post(
    f"{CAPTCHA_URL}/api/v1/solve-sync",
    json={
        "type": "recaptcha_v2",
        "website_url": "https://target-site.com",
        "website_key": "6LcXXXXX..."
    },
    timeout=200  # Can take up to 180s
)
token = response.json()["solution"]

# Check balance
balance = httpx.get(f"{CAPTCHA_URL}/api/v1/balance").json()["balance"]
```

### Supported Types

| Type | Field |
|------|-------|
| `recaptcha_v2` | `website_url`, `website_key` |
| `recaptcha_v3` | `website_url`, `website_key`, `page_action`, `min_score` |
| `hcaptcha` | `website_url`, `website_key` |
| `turnstile` | `website_url`, `website_key` |
| `image` | `body` (base64 image) |

### Environment Setup

```yaml
# compose.yaml (VPS)
environment:
  - CAPTCHA_URL=http://captcha:8000
```

```bash
# .env (WSL)
CAPTCHA_URL=http://localhost:8000
```

### Health Check

```bash
curl https://captcha.vps1.ocoron.com/healthz
curl https://captcha.vps1.ocoron.com/api/v1/balance
```

See `/opt/captcha/README.md` for full API documentation.

---

## ~~DNS Manager Service Integration~~ (RETIRED — not deployed)

> **⚠️ RETIRED — not deployed.** The dns-manager microservice was retired; `dns.vps1.ocoron.com` returns NXDOMAIN. DNS is now handled directly via the Cloudflare driver (`src/fabrik/drivers/cloudflare.py`). Section kept for historical reference.

**Purpose:** Manage Namecheap/Cloudflare DNS records programmatically

**Database:** None (stateless)
**Auth:** ⚠️ None (TODO: add API key)

### Usage

```python
import os
import httpx

DNS_MANAGER_URL = os.getenv("DNS_MANAGER_URL", "http://localhost:8001")

# List domains
response = httpx.get(f"{DNS_MANAGER_URL}/api/dns/domains")
domains = response.json()

# Add subdomain (A record)
response = httpx.post(
    f"{DNS_MANAGER_URL}/api/dns/ocoron.com/subdomain",
    json={"subdomain": "myapp", "ip": "172.93.160.197"}
)

# Get all DNS records for a domain
response = httpx.get(f"{DNS_MANAGER_URL}/api/dns/ocoron.com")
records = response.json()
```

### Common Operations

| Operation | Method | Endpoint |
|-----------|--------|----------|
| List domains | GET | `/api/dns/domains` |
| Get DNS records | GET | `/api/dns/{domain}` |
| Add subdomain | POST | `/api/dns/{domain}/subdomain` |
| Add record | POST | `/api/dns/{domain}/records` |

### Environment Setup

```yaml
# compose.yaml (VPS)
environment:
  - DNS_MANAGER_URL=http://dns-manager:8001
```

```bash
# .env (WSL)
DNS_MANAGER_URL=http://localhost:8001
```

### Health Check

```bash
curl https://dns.vps1.ocoron.com/health
# {"status":"healthy","version":"0.1.0","sandbox":false}
```

See `/opt/dns-manager/README.md` for full API documentation.

---

## ~~Image Broker Service Integration~~ (REMOVED 2026-06-02)

> Historical section. The image-broker spec was retired and removed; the integration commands below will not work. Section retained for reference until a clean rewrite of SERVICES.md happens.

**Purpose:** Unified stock image API (Pexels, Pixabay) with smart routing and caching

**Database:** None (stateless, file cache only)
**Auth:** ⚠️ None (TODO: add API key)

### Usage

```python
import os
import httpx

IMAGE_BROKER_URL = os.getenv("IMAGE_BROKER_URL", "http://localhost:8010")

# Search images
response = httpx.get(
    f"{IMAGE_BROKER_URL}/api/v1/search",
    params={"query": "sunset beach", "per_page": 5}
)
images = response.json()["images"]

# Auto-download (search + score + download in one call)
response = httpx.post(
    f"{IMAGE_BROKER_URL}/api/v1/auto-download",
    json={
        "query": "team meeting office",
        "intent": "hero",  # hero, thumbnail, background
        "topic": "people",  # people, nature, technology, etc.
        "count": 2
    },
    timeout=60
)
result = response.json()
# {"success": true, "selected": [{"local_url": "...", "score": 0.75}]}
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/search` | GET | Search images across providers |
| `/api/v1/auto-download` | POST | Search + score + download |
| `/api/v1/download` | POST | Download specific image by ID |
| `/api/v1/health` | GET | Health + provider status |

### Environment Setup

```yaml
# compose.yaml (VPS)
environment:
  - IMAGE_BROKER_URL=http://image-broker:8000
```

```bash
# .env (WSL)
IMAGE_BROKER_URL=http://localhost:8010
```

### Health Check

```bash
curl https://images.vps1.ocoron.com/api/v1/health
```

See `/opt/image-broker/README.md` for full API documentation.

---

## ~~File API Service Integration~~ (RETIRED — not deployed)

> **⚠️ RETIRED — not deployed.** The file-api microservice was retired; `files-api.vps1.ocoron.com` returns NXDOMAIN. Section kept for historical reference.

**Purpose:** Presigned URL service for Cloudflare R2 file uploads/downloads

**Database:** Supabase (external PostgreSQL, not local postgres-main)
**Auth:** Supabase JWT required

### Usage

```python
import os
import httpx

FILE_API_URL = os.getenv("FILE_API_URL", "http://localhost:8004")
SUPABASE_TOKEN = "user-jwt-token"  # From Supabase auth

# Get presigned upload URL
response = httpx.post(
    f"{FILE_API_URL}/api/files/upload-url",
    headers={"Authorization": f"Bearer {SUPABASE_TOKEN}"},
    json={"filename": "doc.pdf", "content_type": "application/pdf", "size": 1024000}
)
upload_url = response.json()["upload_url"]

# Upload file directly to R2
httpx.put(upload_url, content=file_bytes, headers={"Content-Type": "application/pdf"})
```

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/files/upload-url` | POST | Get presigned upload URL |
| `/api/files/download-url` | POST | Get presigned download URL |
| `/api/files` | GET | List files for user |
| `/api/files/:id` | DELETE | Delete file |
| `/health` | GET | Health check |

### Environment Setup

```yaml
# compose.yaml (VPS)
environment:
  - FILE_API_URL=http://file-api:3000
```

```bash
# .env (WSL)
FILE_API_URL=http://localhost:8004
```

### Health Check

```bash
curl https://files-api.vps1.ocoron.com/health
```

See `/opt/file-api/README.md` for full API documentation.

## Quick Status Check

```bash
# From WSL
ssh vps "sudo docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

Expected output (representative — vps1 runs ~31 containers):

```text
NAMES               STATUS
postgres-main       Up 2 days (healthy)
redis-main          Up 2 days
traefik             Up 2 days
authelia            Up 2 days
gatus               Up 2 days
backrest            Up 2 days
prometheus          Up 2 days
grafana             Up 2 days
loki                Up 2 days
meilisearch         Up 2 days
apprise             Up 2 days
n8n                 Up 2 days
browserless         Up 2 days
gotenberg           Up 2 days
site-provisioner    Up 2 days (healthy)
```
