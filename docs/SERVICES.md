# Required Services

Services Fabrik needs to function.

## About Fabrik

**Fabrik is a CLI tool, not a deployed service.** It runs from WSL and orchestrates deployments to VPS via Coolify API. There are no daemons, watchdogs, or health endpoints for Fabrik itself.

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
| **Coolify** | Yes | Container deployment | None |
| **PostgreSQL** | Yes | Database (via Coolify) | None |
| **Namecheap API** | Yes* | DNS management | Cloudflare (Phase 4) |
| **Backblaze B2** | Yes | Backup storage | None |
| **Redis** | Optional | Caching | Works without |

*Required until Phase 4 Cloudflare migration.

## VPS Services (Managed by Coolify)

| Service | Container | Port | URL | Protection | Purpose |
|---------|-----------|------|-----|------------|---------|
| Coolify | coolify | 8000* | `https://vps1.ocoron.com:8000` | 🔐 Password | Deployment control plane |
| PostgreSQL | postgres-main | 5432 | - (internal) | 🔐 Password | Shared database |
| Redis | redis-main | 6379 | - (internal) | 🔒 Internal | Caching (optional) |
| Netdata | netdata | 19999 | `https://netdata.vps1.ocoron.com` | 🔐 Password | System monitoring |
| Uptime Kuma | uptime-kuma | 3001 | `https://status.vps1.ocoron.com` | 🔐 Password | Service monitoring |
| Duplicati | duplicati | 8200 | `https://backup.vps1.ocoron.com` | 🔐 Password | Backup management |
| Image Broker | image-broker | 8010 | `https://images.vps1.ocoron.com` | ⚠️ Open | Stock image API |
| DNS Manager | dns-manager | 8001 | `https://dns.vps1.ocoron.com` | ⚠️ Open | DNS record management |
| Translator | translator | 8000 | `https://translator.vps1.ocoron.com` | 🔑 API Key | Translation API |
| Captcha | captcha | 8000 | `https://captcha.vps1.ocoron.com` | ⚠️ Open | Captcha solver (Anti-Captcha) |
| File API | file-api | 8004 | `https://files-api.vps1.ocoron.com` | ⚠️ Open | File storage API |

*Coolify port 8000 is exposed directly on host. All other services use Traefik reverse proxy on port 443.

**Protection Legend:**
- 🔐 **Password** — Requires login (basicauth or app login)
- 🔑 **API Key** — Requires API key header
- 🔒 **Internal** — No external access, Docker network only
- ⚠️ **Open** — Publicly accessible (needs auth added)

See [vps-urls.md](operations/vps-urls.md) for complete URL reference.

## Startup Order

For VPS setup (one-time):

1. Docker (system service)
2. Coolify (self-managing)
3. postgres-main (Coolify database)
4. redis-main (Coolify database)
5. Uptime Kuma (Coolify application)

For Fabrik usage (each run):

1. Ensure VPS is accessible
2. Ensure Coolify API is reachable
3. Run `fabrik` commands

## Health Checks

### Coolify

```bash
curl -s https://coolify.yourdomain.com/api/health
```

### PostgreSQL

```bash
ssh deploy@vps "docker exec postgres-main pg_isready"
```

### Uptime Kuma

```bash
curl -s https://status.vps1.ocoron.com
```

### Image Broker

```bash
curl -s https://images.vps1.ocoron.com/api/v1/health
```

### Netdata

```bash
curl -s https://netdata.vps1.ocoron.com
```

### DNS Manager

```bash
curl -s https://dns.vps1.ocoron.com/health
```

### Captcha

```bash
curl -s https://captcha.vps1.ocoron.com/healthz
```

## Service Integration

### Standard URL Pattern

All services follow this pattern:

| Environment | URL Format | Example |
|-------------|------------|---------|
| **WSL (local)** | `http://localhost:<port>` | `http://localhost:8001` |
| **VPS (Docker)** | `http://<container>:<port>` | `http://dns-manager:8001` |
| **External** | `https://<subdomain>.vps1.ocoron.com` | `https://dns.vps1.ocoron.com` |

### Code Pattern

```python
import os
import httpx

# Defaults to localhost for local dev, override in compose.yaml for VPS
SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:<port>")
response = httpx.get(f"{SERVICE_URL}/endpoint")
```

### Environment Setup

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
| Image Broker | `image-broker` | 8010 | `IMAGE_BROKER_URL` | None |
| PostgreSQL | `postgres-main` | 5432 | `DATABASE_URL` | Password |

---

## Translator Service Integration

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

## Captcha Service Integration

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

## DNS Manager Service Integration

**Purpose:** Manage Namecheap/Cloudflare DNS records programmatically

**Database:** None (stateless)
**Auth:** ⚠️ None (TODO: add API key)

### Usage

```python
import os
import httpx

DNS_MANAGER_URL = os.getenv("DNS_MANAGER_URL", "http://localhost:8001")

# List domains
response = httpx.get(f"{DNS_MANAGER_URL}/api/namecheap/domains")
domains = response.json()

# Add subdomain (A record)
response = httpx.post(
    f"{DNS_MANAGER_URL}/api/namecheap/dns/ocoron.com/subdomain",
    json={"subdomain": "myapp", "ip": "172.93.160.197"}
)

# Get all DNS records for a domain
response = httpx.get(f"{DNS_MANAGER_URL}/api/namecheap/dns/ocoron.com")
records = response.json()
```

### Common Operations

| Operation | Method | Endpoint |
|-----------|--------|----------|
| List domains | GET | `/api/namecheap/domains` |
| Get DNS records | GET | `/api/namecheap/dns/{domain}` |
| Add subdomain | POST | `/api/namecheap/dns/{domain}/subdomain` |
| Add record | POST | `/api/namecheap/dns/{domain}/records` |

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

## Image Broker Service Integration

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

## File API Service Integration

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
ssh deploy@vps "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

Expected output:

```text
NAMES           STATUS
coolify         Up 2 days
postgres-main   Up 2 days
redis-main      Up 2 days
netdata         Up 2 days
uptime-kuma     Up 2 days
duplicati       Up 2 days
image-broker    Up 1 hour (healthy)
dns-manager     Up 2 days
translator      Up 2 days
captcha         Up 2 days
file-api        Up 2 days
```
