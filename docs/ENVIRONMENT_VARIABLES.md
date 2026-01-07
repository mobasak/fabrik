# Environment Variables Reference

**Last Updated:** 2026-01-07

Complete reference of all environment variables used in Fabrik.

---

## Quick Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `COOLIFY_API_URL` | Yes | — | Coolify API endpoint |
| `COOLIFY_API_TOKEN` | Yes | — | Coolify API authentication token |
| `COOLIFY_SERVER_UUID` | Yes | — | Target server UUID in Coolify |
| `SUPABASE_URL` | Yes | — | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | — | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | — | Supabase service role key |
| `DNS_MANAGER_URL` | No | `https://dns.vps1.ocoron.com` | DNS Manager API URL |
| `VPS_IP` | No | `172.93.160.197` | VPS public IP address |
| `FABRIK_NOTIFY_SCRIPT` | No | `~/.factory/hooks/notify.sh` | Notification script for review processor |
| `FABRIK_ROOT` | No | `/opt/fabrik` | Root directory used by automation (applies to review queue/results paths) |
| `FABRIK_REVIEW_QUEUE` | No | `${FABRIK_ROOT}/.droid/review_queue` | Directory where review tasks are queued |
| `FABRIK_REVIEW_RESULTS` | No | `${FABRIK_ROOT}/.droid/review_results` | Directory where completed review results are stored |
| `FABRIK_MODELS_CONFIG` | No | `${FABRIK_ROOT}/config/models.yaml` | Path to model configuration used by the review processor |

---

## Infrastructure

### Coolify

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `COOLIFY_API_URL` | Yes | `http://localhost:8000` | Coolify API base URL |
| `COOLIFY_API_TOKEN` | Yes | — | API token from Coolify settings |
| `COOLIFY_SERVER_UUID` | Yes | — | Server UUID for deployments |
| `COOLIFY_PROJECT_UUID` | No | — | Default project UUID |

```bash
# Example
COOLIFY_API_URL=https://coolify.vps1.ocoron.com
COOLIFY_API_TOKEN=your-token-here
COOLIFY_SERVER_UUID=jk4wskkcks8csg4gcokwgw8s
```

### VPS

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VPS_IP` | No | `172.93.160.197` | VPS public IP address |
| `VPS_SSH_USER` | No | `deploy` | SSH username |
| `VPS_SSH_KEY` | No | `~/.ssh/id_ed25519` | SSH private key path |

---

## Cloud Services

### Supabase

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUPABASE_URL` | Yes | — | Project URL (e.g., `https://xxx.supabase.co`) |
| `SUPABASE_ANON_KEY` | Yes | — | Anonymous/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | — | Service role key (server-side only) |

```bash
# Example
SUPABASE_URL=https://abcdefg.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIs...
```

### Cloudflare R2

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `R2_ACCOUNT_ID` | Yes | — | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | Yes | — | R2 access key ID |
| `R2_SECRET_ACCESS_KEY` | Yes | — | R2 secret access key |
| `R2_BUCKET` | Yes | — | Default bucket name |
| `R2_PUBLIC_URL` | No | — | Public URL for bucket |

```bash
# Example
R2_ACCOUNT_ID=abc123
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET=fabrik-files
R2_PUBLIC_URL=https://files.example.com
```

---

## DNS Management

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DNS_MANAGER_URL` | No | `https://dns.vps1.ocoron.com` | DNS Manager API URL |
| `CLOUDFLARE_API_TOKEN` | Yes | — | Cloudflare API token |
| `CLOUDFLARE_ZONE_ID` | No | — | Default zone ID |

```bash
# Example
DNS_MANAGER_URL=https://dns.vps1.ocoron.com
CLOUDFLARE_API_TOKEN=your-cloudflare-token
```

---

## WordPress

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WP_ADMIN_USER` | No | `admin` | WordPress admin username |
| `WP_ADMIN_PASSWORD` | Yes | — | WordPress admin password |
| `WP_ADMIN_EMAIL` | Yes | — | WordPress admin email |

```bash
# Example
WP_ADMIN_USER=admin
WP_ADMIN_PASSWORD=secure-password-here
WP_ADMIN_EMAIL=admin@example.com
```

---

## AI Services

### Anthropic (Claude)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |

### OpenAI

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |

### Factory (droid exec)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FACTORY_API_KEY` | Yes | — | Factory.ai API key |
| `DROID_DATA_DIR` | No | `/opt/fabrik/.droid` | Data directory for droid runner tasks/responses |
| `DROID_EXEC_TIMEOUT` | No | `1800` | Timeout in seconds for non-streaming droid exec (30 min default) |

```bash
# Example
FACTORY_API_KEY=fct_abc123...
DROID_DATA_DIR=/opt/fabrik/.droid
DROID_EXEC_TIMEOUT=1800
```

---

## Monitoring

### Uptime Kuma

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `UPTIME_KUMA_URL` | No | `https://status.vps1.ocoron.com` | Uptime Kuma URL |
| `UPTIME_KUMA_USERNAME` | Yes | — | Admin username |
| `UPTIME_KUMA_PASSWORD` | Yes | — | Admin password |

### Netdata

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NETDATA_URL` | No | `https://netdata.vps1.ocoron.com` | Netdata URL |

## Automation & Notifications

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FABRIK_NOTIFY_SCRIPT` | No | `~/.factory/hooks/notify.sh` | Path to notification script invoked by `scripts/review_processor.py` or `scripts/docs_updater.py`; script receives JSON on stdin with a `message` field |
| `FABRIK_ROOT` | No | `/opt/fabrik` | Base path for resolving review/docs queue, results, and config paths |
| `FABRIK_REVIEW_QUEUE` | No | `${FABRIK_ROOT}/.droid/review_queue` | Queue directory for pending review tasks |
| `FABRIK_REVIEW_RESULTS` | No | `${FABRIK_ROOT}/.droid/review_results` | Output directory for completed review results |
| `FABRIK_DOCS_QUEUE` | No | `${FABRIK_ROOT}/.droid/docs_queue` | Queue directory for pending documentation update tasks |
| `FABRIK_DOCS_LOG` | No | `${FABRIK_ROOT}/.droid/docs_log` | Log directory for documentation update history |
| `FABRIK_MODELS_CONFIG` | No | `${FABRIK_ROOT}/config/models.yaml` | Override path for the models configuration used by the review processor and docs updater |

---

## Database

### PostgreSQL

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_HOST` | No | `localhost` | Database host |
| `DB_PORT` | No | `5432` | Database port |
| `DB_NAME` | Yes | — | Database name |
| `DB_USER` | Yes | — | Database username |
| `DB_PASSWORD` | Yes | — | Database password |
| `DATABASE_URL` | No | — | Full connection string (alternative) |

```bash
# Individual variables
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fabrik
DB_USER=postgres
DB_PASSWORD=secure-password

# Or connection string
DATABASE_URL=postgresql-connection-string
```

---

## External APIs

### Translation (DeepL)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEEPL_API_KEY` | Yes | — | DeepL API key |
| `TRANSLATOR_URL` | No | `https://translator.vps1.ocoron.com` | Translator service URL |

### Email (Resend)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RESEND_API_KEY` | Yes | — | Resend API key |
| `EMAIL_GATEWAY_URL` | No | `https://email.vps1.ocoron.com` | Email gateway URL |

### Captcha (Anti-Captcha)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTICAPTCHA_API_KEY` | Yes | — | Anti-Captcha API key |
| `CAPTCHA_URL` | No | `https://captcha.vps1.ocoron.com` | Captcha service URL |

### Proxy (Webshare)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEBSHARE_API_KEY` | Yes | — | Webshare API key |
| `PROXY_URL` | No | `https://proxy.vps1.ocoron.com` | Proxy service URL |

---

## Environment-Specific Defaults

### WSL (Development)

```bash
DB_HOST=localhost
DB_PORT=5432
COOLIFY_API_URL=https://coolify.vps1.ocoron.com
```

### VPS (Docker)

```yaml
# In compose.yaml
environment:
  - DB_HOST=postgres-main
  - DB_PORT=5432
```

### Supabase

```bash
# Use Supabase connection string
DATABASE_URL=${SUPABASE_DATABASE_URL}
```

---

## Best Practices

### 1. Never Hardcode

```python
# ❌ Wrong
DB_HOST = "localhost"

# ✅ Correct
DB_HOST = os.getenv("DB_HOST", "localhost")
```

### 2. Load at Runtime

```python
# ❌ Wrong - env not set at import time
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_USER')}:..."

# ✅ Correct - load in function
def get_db_url():
    return f"postgresql://{os.getenv('DB_USER')}:..."
```

### 3. Store in Two Places

1. Project `.env` — For local use
2. `/opt/fabrik/.env` — Master backup

### 4. Document in .env.example

```bash
# .env.example (commit this)
DB_HOST=localhost
DB_PASSWORD=  # Set in .env
```

---

## Related Documentation

- [CONFIGURATION.md](CONFIGURATION.md) — Configuration guide
- [SERVICES.md](SERVICES.md) — Service catalog with URLs
- [DEPLOYMENT.md](DEPLOYMENT.md) — Deployment guide
