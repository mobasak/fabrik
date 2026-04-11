# Frequently Asked Questions

**Last Updated:** 2026-02-26

---

## General

### What is Fabrik?

Fabrik is an **enterprise-grade deployment orchestration platform** that automates the entire lifecycle of deploying services to production infrastructure. It's spec-driven infrastructure-as-code designed for teams who need repeatable deployments without vendor lock-in.

**Core capabilities:**
- Automated domain registration and DNS configuration
- Container deployment via Coolify (Docker Compose)
- SSL certificate automation (Let's Encrypt)
- Health monitoring and status pages
- Encrypted backups to cloud storage
- WordPress site automation (themes, plugins, content)
- Multi-service orchestration with shared infrastructure

### What makes Fabrik different from Kubernetes?

| Aspect | Fabrik | Kubernetes |
|--------|--------|------------|
| **Complexity** | 1 YAML file per service | 100+ YAML files |
| **Cost** | $10/month VPS, unlimited services | $50-200/month managed cluster |
| **Learning Curve** | 5 minutes to first deployment | Weeks to understand basics |
| **Target** | Small-medium teams, 5-50 services | Large orgs, 100+ services |
| **Features** | End-to-end (DNS, SSL, monitoring, backups) | Container orchestration only |

**Use Fabrik when:** You need production infrastructure without K8s complexity

**Use Kubernetes when:** You need auto-scaling 100+ containers, multi-region failover

### What makes Fabrik different from Platform-as-a-Service (Heroku, Vercel, Railway)?

| Aspect | Fabrik | PaaS |
|--------|--------|------|
| **Cost** | $10/month total (unlimited services) | $20-100/month per service |
| **Control** | Full VPS access, customize everything | Limited, managed platform |
| **Vendor Lock-in** | None (self-hosted) | Locked to platform |
| **Customization** | Full Docker control | Platform constraints |

**Use Fabrik when:** You want PaaS simplicity at self-hosted prices

**Use PaaS when:** You don't want to manage infrastructure at all

### Where do I find credentials?

**Two locations (by design):**

1. **Project `.env`** - Project-specific credentials
2. **`/opt/fabrik/.env`** - Master credentials file (backup + shared vars)

**Why both?**
- Each project can override shared credentials
- Master file survives project deletion
- Consolidation via `python scripts/consolidate_envs.py` merges them

**Security:**
- Both files are git-ignored
- Mandatory timestamped backups (`.env.backup.YYYYMMDD-HHMMSS`)
- Never commit credentials to version control

### What environments does Fabrik code run in?

| Environment | Database | Config Source | Purpose |
|-------------|----------|---------------|---------|
| **WSL** | PostgreSQL localhost | `.env` file | Local development |
| **VPS Docker** | postgres-main container | `compose.yaml` env vars | Production |
| **Supabase** | Supabase PostgreSQL | env vars | Cloud database option |

**Critical:** All Fabrik code must work in all three without modification. Use `os.getenv()`, never hardcode `localhost`.

---

## Installation & Setup

### How do I install Fabrik?

```bash
# 1. Clone or navigate to Fabrik
cd /opt/fabrik

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install with uv (fast) or pip
uv pip install -e .
# OR: pip install -e .

# 4. Configure credentials
cp .env.example .env
nano .env  # Fill in your VPS, Coolify, DNS credentials

# 5. Verify installation
fabrik --version
fabrik templates
```

### What credentials do I need to get started?

**Minimum (for basic deployment):**
```bash
# VPS Access
VPS_HOST=172.93.160.197
VPS_USER=ozgur

# Coolify API (get from Coolify UI → Settings → API)
COOLIFY_API_URL=https://coolify.vps1.ocoron.com
COOLIFY_API_TOKEN=your-token-here

# DNS Provider (choose one)
DNS_MANAGER_URL=https://dns.vps1.ocoron.com  # Service-based
# OR
CLOUDFLARE_API_TOKEN=your-token
CLOUDFLARE_ZONE_ID=your-zone-id

# Backups
B2_KEY_ID=your-key-id
B2_APPLICATION_KEY=your-app-key
B2_BUCKET_NAME=fabrik-backups
```

**Optional (for advanced features):**
- Supabase (multi-tenant database)
- Cloudflare R2 (file storage)
- AI services (Anthropic, OpenAI, Factory.ai)
- Monitoring (Uptime Kuma credentials)

### How do I get Coolify API credentials?

1. Open Coolify UI: `http://YOUR_VPS_IP:8000`
2. Settings → API Tokens
3. Create New Token → Copy token
4. Add to `.env`:
   ```bash
   COOLIFY_API_URL=http://YOUR_VPS_IP:8000
   COOLIFY_API_TOKEN=paste-token-here
   ```

### How do I set up DNS automation?

**Option 1: dns-manager service (recommended)**

Fabrik includes a dns-manager microservice that handles both Namecheap and Cloudflare:

```bash
DNS_MANAGER_URL=https://dns.vps1.ocoron.com
```

**Option 2: Direct Cloudflare API**

```bash
CLOUDFLARE_API_TOKEN=your-api-token
CLOUDFLARE_ZONE_ID=your-zone-id
```

**Getting Cloudflare token:**
1. Cloudflare Dashboard → My Profile → API Tokens
2. Create Token → Edit zone DNS template
3. Permissions: Zone.DNS (Edit)
4. Include: Specific zone → select your domain

---

## Development

### How do I start a new project?

**For generic projects:**
```bash
cd /opt/fabrik
source .venv/bin/activate
fabrik scaffold my-project
```

**For SaaS applications:**
```bash
cp -r templates/saas-skeleton /opt/my-saas-app
cd /opt/my-saas-app
# Edit package.json, update branding, deploy
```

**For microservices:**
```bash
fabrik new my-api --template python-api --domain api.example.com
# Edit specs/my-api.yaml
fabrik apply specs/my-api.yaml
```

### Why can't I use `/tmp/` for temporary files?

**Problems with `/tmp/`:**
- Shared across all projects (name collisions)
- Deleted on WSL restart (data loss)
- Cleared by system processes
- Not gitignored (security risk if paths leak)

**Use project-local `.tmp/` instead:**
```python
from pathlib import Path

TEMP_DIR = Path(__file__).parent.parent / ".tmp"
TEMP_DIR.mkdir(exist_ok=True)

# Now safe, isolated, gitignored
temp_file = TEMP_DIR / "processing.json"
```

### How do I add a new environment variable?

**Process:**
1. Add to project `.env` (actual value)
2. Add to `/opt/fabrik/.env` (master backup)
3. Add to `.env.example` with inline comment explaining purpose
4. Document usage context in `docs/CONFIGURATION.md` (guide only, not variable tables)

**Example:**
```bash
# In .env.example
TRANSLATOR_API_KEY=  # DeepL API key from https://www.deepl.com/pro-api
```

### Why isn't my env var working in Docker?

**Problem:** `.env` files are for local dev. Docker containers get env vars from `compose.yaml`.

**Wrong approach:**
```yaml
# compose.yaml - this won't work
services:
  api:
    # Missing environment section!
```

**Correct approach:**
```yaml
# compose.yaml
services:
  api:
    environment:
      - DB_HOST=postgres-main  # Use container name, not localhost
      - DB_PORT=5432
      - API_KEY=${API_KEY}  # Reference from .env
```

**Environment-specific values:**
```python
# CORRECT - works everywhere
DB_HOST = os.getenv('DB_HOST', 'localhost')

# WRONG - breaks in Docker
DB_HOST = 'localhost'
```

---

## Deployment

### How do I deploy to production?

**Full workflow:**
```bash
# 1. Scaffold project (spec auto-generated with secrets)
fabrik scaffold my-api --type python-api

# 2. Set secrets in project .env file
# /opt/my-api/.env
API_KEY=your_actual_key
DATABASE_PASSWORD=your_actual_password

# 3. Deploy - secrets auto-loaded from .env file
fabrik apply /opt/fabrik/specs/services/my-api.yaml

# 4. Verify
curl https://api.example.com/health

# 5. Check status
fabrik status specs/my-api.yaml
```

**No manual environment variable setting needed.** Fabrik automatically reads secrets from the project's `.env` file.

### How do I manage secrets for deployment?

**Fabrik automatically loads secrets from project `.env` files during deployment.**

**Secret Loading Precedence:**
1. Command-line `-s` flags (highest)
2. Project `.env` file at `/opt/{project}/.env`
3. Environment variables (lowest)

**How It Works:**
1. **Scaffold auto-detection:** `fabrik scaffold` reads `.env.example` and auto-detects secret env vars (matching patterns like `_KEY`, `_SECRET`, `_PASSWORD`, `_TOKEN`, `_CREDENTIALS`). These are added to the spec's `from_env` field.

2. **Project .env file:** During development, set your actual secrets in the project's `.env` file at `/opt/{project}/.env`.

3. **Automatic loading:** When you run `fabrik apply`, it automatically reads from the project's `.env` file before checking system environment variables.

**Example:**
```bash
# /opt/my-api/.env
API_KEY=your_actual_key
DATABASE_PASSWORD=your_actual_password
SECRET_TOKEN=your_secret_token

# Deploy - secrets auto-loaded
fabrik apply /opt/fabrik/specs/services/my-api.yaml
```

**Benefits:**
- No manual environment variable setting needed
- Secrets are isolated per project
- Works seamlessly across WSL dev and VPS Docker environments
- Easy to override with `-s` flags when needed

### What ports should my services use?

**Port allocation strategy:**

| Range | Purpose | Examples |
|-------|---------|----------|
| 3000-3099 | Frontend (Node.js) | Next.js, React dev servers |
| 8000-8099 | Python APIs | FastAPI, Django |
| 8100-8199 | Workers | Background processors |
| 8200-8299 | Databases | PostgreSQL, Redis (internal only) |

**Before using a port:**
1. Check `PORTS.md` for current allocations
2. Add your service to `PORTS.md`
3. Use port in `compose.yaml`

**Example:**
```yaml
# compose.yaml
services:
  api:
    ports:
      - "8042:8042"  # Registered in PORTS.md
    environment:
      - PORT=8042
```

### Why isn't my service accessible externally?

**Checklist:**

1. **Traefik labels missing?**
   ```yaml
   # compose.yaml needs these labels
   services:
     api:
       labels:
         - "traefik.enable=true"
         - "traefik.http.routers.myapi.rule=Host(`api.example.com`)"
         - "traefik.http.routers.myapi.entrypoints=websecure"
         - "traefik.http.routers.myapi.tls.certresolver=letsencrypt"
   ```

2. **DNS record exists?**
   ```bash
   dig api.example.com  # Should return VPS IP
   ```

3. **Service healthy?**
   ```bash
   curl https://api.example.com/health
   # OR
   docker logs <container-name>
   ```

4. **Firewall open?**
   ```bash
   sudo ufw status
   # Ports 80, 443 must be open
   ```

### How do I check if a deployment succeeded?

**Three verification methods:**

1. **Fabrik status command:**
   ```bash
   fabrik status specs/my-api.yaml
   # Shows: state, URL, container status, health
   ```

2. **Direct health check:**
   ```bash
   curl https://api.example.com/health
   # Should return: {"status": "ok"}
   ```

3. **Uptime Kuma dashboard:**
   ```
   https://status.vps1.ocoron.com
   # Visual status of all services
   ```

---

## WordPress

### How do I deploy a WordPress site?

```bash
# 1. Create site spec
nano specs/sites/my-site.yaml

# 2. Add spec content
schema_version: 1
preset: company
site:
  domain: example.com
  name: my-site
brand:
  name: "My Company"
  colors:
    primary: "#1e3a5f"

# 3. Deploy
fabrik wp deploy specs/sites/my-site.yaml
```

**What gets automated:**
- WordPress installation
- Theme customization (colors, fonts, logo)
- Page generation from spec
- Menu structure
- Contact forms
- SEO configuration
- Analytics (GA4)
- Multilingual support

### How do I add custom WordPress plugins?

**Two methods:**

1. **Add to preset** (for reusable plugin sets):
   ```yaml
   # templates/wordpress/presets/my-preset.yaml
   plugins:
     - wordpress-seo  # Yoast SEO
     - contact-form-7
     - my-custom-plugin
   ```

2. **Add to site spec** (for site-specific plugins):
   ```yaml
   # specs/sites/my-site.yaml
   plugins:
     - woocommerce  # Only for this site
   ```

**Plugin must exist in:**
- `templates/wordpress/plugins/<plugin-name>/`
- OR WordPress plugin directory (auto-downloaded)

---

## Troubleshooting

### "Connection refused" errors

**Checklist:**

1. **Is service running?**
   ```bash
   docker ps | grep my-service
   ```

2. **Correct port?**
   ```bash
   docker logs <container-name> | grep -i port
   # Should show: "Uvicorn running on 0.0.0.0:8042"
   ```

3. **Firewall blocking?**
   ```bash
   sudo ufw status
   # Allow 80/tcp ALLOW Anywhere
   # Allow 443/tcp ALLOW Anywhere
   ```

4. **Container networking?**
   ```bash
   docker network ls
   docker network inspect coolify
   # Service should be in coolify network
   ```

### "Module not found" errors

```bash
# Reinstall dependencies
cd /opt/fabrik
source .venv/bin/activate
pip install -e .

# OR with uv (faster)
uv pip install -e .
```

### Health check failing

**Common causes:**

1. **Healthcheck doesn't test dependencies**
   ```python
   # BAD - lies about health
   @app.get("/health")
   async def health():
       return {"status": "ok"}

   # GOOD - actually tests DB connection
   @app.get("/health")
   async def health():
       await db.execute("SELECT 1")  # Will fail if DB down
       return {"status": "ok", "db": "connected"}
   ```

2. **Wrong health check path**
   ```yaml
   # compose.yaml - path must match your endpoint
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:8042/health"]
     # NOT /healthz or /ping - must be actual path
   ```

3. **Healthcheck too strict**
   ```yaml
   healthcheck:
     interval: 30s
     timeout: 10s
     retries: 3
     start_period: 40s  # Give service time to start up!
   ```

### Deployment stuck in DEPLOYING state

**Causes:**

1. **Coolify waiting for health check**
   - Check container logs: `docker logs <container>`
   - Verify health endpoint works: `curl http://localhost:PORT/health`

2. **Build failing**
   - Check Coolify UI for build logs
   - Verify Dockerfile builds locally: `docker build .`

3. **Resource constraints**
   - Check VPS resources: `htop` or `docker stats`
   - Reduce resource limits in spec if needed

**Recovery:**
```bash
# Check orchestrator state
cat /opt/fabrik/.tmp/deployment-<id>.json

# Manual rollback if needed
fabrik rollback specs/my-api.yaml
```

### How do I roll back a deployment?

**Automatic rollback:**
- Fabrik automatically rolls back failed deployments
- Deletes created DNS records
- Stops deployed containers
- Cleans up resources

**Manual rollback:**
```bash
# If deployment succeeded but you want to revert
fabrik rollback specs/my-api.yaml
# OR
docker stop <container-name>
docker rm <container-name>
# Then redeploy previous version
```

---

## Configuration

### How do I change the default AI model for Kilo CLI?

Kilo CLI uses automatic model routing based on task type. To override:

```bash
# Set preferred model in environment
export KILO_MODEL="claude-sonnet-4-5-20250929"

# Or use --model flag
kilo run --model claude-sonnet-4-5-20250929 "your task"
```

**Available models:** Run `kilo models` to see current list

### Where do I find service URLs?

See `docs/SERVICES.md` for complete catalog, or check running services:

```bash
# All services
curl https://status.vps1.ocoron.com/api/status

# Specific service health
curl https://translator.vps1.ocoron.com/health
```

---

## Advanced

### How do I use Fabrik with Supabase?

**Setup:**
```bash
# .env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-key
```

**Usage in services:**
```python
from fabrik.drivers.supabase import SupabaseClient

client = SupabaseClient()
result = await client.query("users").select("*").execute()
```

**Features:**
- Multi-tenant row-level security
- Real-time subscriptions
- Built-in auth
- PostgreSQL with 500MB free tier

### How do I set up file uploads with R2?

**Architecture:**
```
Browser → Request Upload URL → API → R2 Presigned URL
Browser → Upload Direct to R2 (no server bandwidth)
Browser → Confirm Upload → API → Create job in queue
Worker → Process file → Upload result → R2
```

**See:** `templates/file-api/` and `templates/file-worker/` for full implementation

### How do I run background jobs?

**Use file-worker template:**
```bash
fabrik new my-worker --template file-worker --domain worker.example.com
```

**Customize processor:**
```python
# src/processors/my_task.py
async def process_job(job: ProcessingJob) -> dict:
    # 1. Download file from R2
    # 2. Process (OCR, transcribe, etc.)
    # 3. Upload result to R2
    # 4. Return metadata
    return {"status": "completed", "output_url": "..."}
```

---

## Related Documentation

- **[Quick Start](QUICKSTART.md)** - Get Fabrik running in 5 minutes
- **[Configuration Guide](CONFIGURATION.md)** - All settings explained
- **[Troubleshooting](TROUBLESHOOTING.md)** - Debug guides
- **[Services](SERVICES.md)** - Service catalog with URLs
- **[INDEX.md](../INDEX.md)** - Complete documentation map
