# Phase 9: Deploy Infrastructure Services

## Goal
Deploy 5 pre-built Docker services to VPS1 via Coolify.

## DONE WHEN
- [ ] browserless accessible at browser.vps1.ocoron.com
- [ ] gotenberg accessible at pdf.vps1.ocoron.com/health
- [ ] minio accessible at s3.vps1.ocoron.com/minio/health/live
- [ ] apprise accessible at notify.vps1.ocoron.com
- [ ] meilisearch accessible at search.vps1.ocoron.com/health
- [ ] Specs created in /opt/fabrik/specs/infrastructure/
- [ ] Credentials in /opt/fabrik/.env
- [ ] PORTS.md updated
- [ ] SERVICES.md updated
- [ ] CHANGELOG.md updated

## Out of Scope
- n8n deployment (Phase 8 handles this)
- Monitoring stack (Phase 6 handles this)
- Custom code integration with projects

## Services

### 1. browserless/chrome
- Image: browserless/chrome:latest
- Port: 3000
- Domain: browser.vps1.ocoron.com
- Env: MAX_CONCURRENT_SESSIONS=10, CONNECTION_TIMEOUT=60000, PREBOOT_CHROME=true
- Purpose: Headless browser for Chrome Extension, youtube scraping

### 2. gotenberg/gotenberg
- Image: gotenberg/gotenberg:8
- Port: 3003 (internal 3000)
- Domain: pdf.vps1.ocoron.com
- Health: /health
- Purpose: PDF generation for proposal-creator

### 3. minio/minio
- Image: minio/minio:latest
- Ports: 9000 (API), 9001 (Console)
- Domain: s3.vps1.ocoron.com
- Command: server /data --console-address ":9001"
- Env: MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
- Volume: minio-data:/data
- Health: /minio/health/live
- Purpose: S3-compatible storage for all projects

### 4. caronc/apprise
- Image: caronc/apprise:latest
- Port: 8005 (NOTE: 8000 conflicts with Translator/Captcha)
- Domain: notify.vps1.ocoron.com
- Purpose: Unified notifications (Slack, email, SMS)

### 5. getmeili/meilisearch
- Image: getmeili/meilisearch:latest
- Port: 7700
- Domain: search.vps1.ocoron.com
- Env: MEILI_MASTER_KEY
- Volume: meilisearch-data:/meili_data
- Health: /health
- Purpose: Fast search for youtube, trade-intelligence

## Execution Steps

### Step 1: Verify ARM64 Support
```bash
cd /opt/fabrik && source .venv/bin/activate
python scripts/container_images.py check-arch browserless/chrome:latest
python scripts/container_images.py check-arch gotenberg/gotenberg:8
python scripts/container_images.py check-arch minio/minio:latest
python scripts/container_images.py check-arch caronc/apprise:latest
python scripts/container_images.py check-arch getmeili/meilisearch:latest
```

### Step 2: Create Infrastructure Directory
```bash
mkdir -p /opt/fabrik/specs/infrastructure
```

### Step 3: Create Spec Files

Create each spec file in `/opt/fabrik/specs/infrastructure/`:

**browserless.yaml:**
```yaml
name: browserless
type: docker
domain: browser.vps1.ocoron.com
image: browserless/chrome:latest
environment:
  MAX_CONCURRENT_SESSIONS: "10"
  CONNECTION_TIMEOUT: "60000"
  PREBOOT_CHROME: "true"
  ENABLE_DEBUGGER: "false"
ports:
  - "3000:3000"
networks:
  - coolify
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:3000/"]
  interval: 30s
  timeout: 10s
  retries: 3
```

**gotenberg.yaml:**
```yaml
name: gotenberg
type: docker
domain: pdf.vps1.ocoron.com
image: gotenberg/gotenberg:8
environment:
  CHROMIUM_DISABLE_JAVASCRIPT: "false"
  CHROMIUM_ALLOW_LIST: "file:///tmp/.*"
ports:
  - "3003:3000"
networks:
  - coolify
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

**minio.yaml:**
```yaml
name: minio
type: docker
domain: s3.vps1.ocoron.com
image: minio/minio:latest
command: server /data --console-address ":9001"
environment:
  MINIO_ROOT_USER: ${MINIO_ROOT_USER}
  MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
volumes:
  - minio-data:/data
ports:
  - "9000:9000"
  - "9001:9001"
networks:
  - coolify
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
  interval: 30s
  timeout: 10s
  retries: 3
```

**apprise.yaml:**
```yaml
name: apprise
type: docker
domain: notify.vps1.ocoron.com
image: caronc/apprise:latest
ports:
  - "8005:8000"
networks:
  - coolify
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/"]  # Internal port
  interval: 30s
  timeout: 10s
  retries: 3
```

**meilisearch.yaml:**
```yaml
name: meilisearch
type: docker
domain: search.vps1.ocoron.com
image: getmeili/meilisearch:latest
environment:
  MEILI_MASTER_KEY: ${MEILI_MASTER_KEY}
  MEILI_ENV: production
volumes:
  - meilisearch-data:/meili_data
ports:
  - "7700:7700"
networks:
  - coolify
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:7700/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### Step 4: Generate Credentials
```bash
# Generate secure passwords
python -c "import secrets; print(f'MINIO_ROOT_USER=admin')"
python -c "import secrets; print(f'MINIO_ROOT_PASSWORD={secrets.token_urlsafe(32)}')"
python -c "import secrets; print(f'MEILI_MASTER_KEY={secrets.token_urlsafe(32)}')"
```

### Step 5: Add to /opt/fabrik/.env
Add the generated credentials to the .env file.

### Step 6: Deploy via Coolify
Manual step - deploy each service through Coolify UI or API.

### Step 7: Verify Health Endpoints
```bash
curl -sf https://browser.vps1.ocoron.com/
curl -sf https://pdf.vps1.ocoron.com/health
curl -sf https://s3.vps1.ocoron.com/minio/health/live
curl -sf https://notify.vps1.ocoron.com/
curl -sf https://search.vps1.ocoron.com/health
```

### Step 8: Update Documentation

**PORTS.md** - Add:
| Service | Port | Domain |
|---------|------|--------|
| browserless | 3000 | browser.vps1.ocoron.com |
| gotenberg | 3003 | pdf.vps1.ocoron.com |
| minio | 9000/9001 | s3.vps1.ocoron.com |
| apprise | 8005 | notify.vps1.ocoron.com |
| meilisearch | 7700 | search.vps1.ocoron.com |

**docs/SERVICES.md** - Add service entries

**CHANGELOG.md** - Add Phase 9 completion entry

## Reference Files
- /opt/fabrik/docs/development/plans/previously-planned-fabrik-phases/phase9.md
- /opt/fabrik/docs/reference/prebuilt-app-containers.md
- /opt/fabrik/scripts/container_images.py

## Constraints
- All images MUST support linux/arm64 (VPS1 is ARM64)
- Use coolify external network
- Follow 9-step workflow: implement → final_gate → kilo → final_gate → verify → sync → commit
- Store credentials in BOTH project .env AND /opt/fabrik/.env
