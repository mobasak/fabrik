# Configuration Guide

**Last Updated:** 2026-02-26

**Purpose:** This guide explains HOW to configure Fabrik and WHY certain configurations exist. For WHAT variables are needed, see `.env.example` which is self-documenting.

---

## Quick Setup

```bash
# 1. Copy template
cp .env.example .env

# 2. Edit with your values
nano .env

# 3. Verify
python -m fabrik.config --verify
```

**All variables are documented in `.env.example` with inline comments.**

---

## Getting Credentials

### VPS Access

**Why needed:** Deploy applications to your VPS via Coolify.

**How to get:**
1. Provision VPS (DigitalOcean, Linode, etc.)
2. Note public IP (`VPS_IP`, `VPS_HOST`)
3. Create deploy user:
   ```bash
   ssh root@your-vps
   adduser deploy
   usermod -aG sudo deploy
   ```
4. Set up SSH key (optional but recommended):
   ```bash
   ssh-copy-id deploy@your-vps
   ```

### Coolify API Token

**Why needed:** Automate deployments, manage services.

**How to get:**
1. Install Coolify: https://coolify.io/docs/installation
2. Login to dashboard: `https://your-vps:8000`
3. Settings → API Keys → Create New
4. Copy token (shown once)
5. Server/Project UUIDs auto-detected on first run

### DNS - Namecheap Service

**Why this approach:** Fabrik uses a deployed microservice instead of direct API calls.

**Architecture:**
- `namecheap` service runs at `https://namecheap.vps1.ocoron.com`
- Handles DNS record creation/updates
- No need for individual API keys per project

**Local development only:**
If running namecheap service locally, you need direct Namecheap API credentials (see `.env.example`).

### Backblaze B2

**Why needed:** Encrypted backups of all project data.

**How to get:**
1. Create account: https://www.backblaze.com/b2/sign-up.html
2. Buckets → Create Bucket → Note name
3. App Keys → Add New → Copy ID and Key
4. Generate strong passphrase for encryption:
   ```bash
   python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32)))"
   ```

### Docker Hub

**Why needed:** Private container images for proprietary services.

**How to get:**
1. Create account: https://hub.docker.com
2. Account Settings → Security → New Access Token
3. Select "Read, Write, Delete" permissions
4. Copy token (shown once)

---

## Architecture Context

### Database Strategy

**Single shared PostgreSQL instance:**
- `postgres-main` container serves all projects
- Each project gets its own database
- Connection string format: `postgresql://user:pass@postgres-main:5432/dbname`

**Why:** Resource efficiency, easier backups, consistent version.

### DNS Provider Choice

**Development:** Use namecheap service (no local credentials needed)

**Production options:**
1. **Namecheap service** (current) - Centralized, simple
2. **Cloudflare** (Phase 4+) - Better API, faster propagation, free tier

**Migration path:** Set `CLOUDFLARE_*` vars, Fabrik auto-switches.

### Logging Architecture

**Two modes:**
- `LOG_FORMAT=json` → Structured logs for log aggregation (Loki, CloudWatch)
- `LOG_FORMAT=text` → Human-readable for development

**Log levels:**
- `DEBUG` → Development only (verbose, includes SQL queries)
- `INFO` → Production default (business events)
- `WARNING` → Potential issues
- `ERROR` → Failures requiring attention

---

## Environment-Specific Setups

### Development (WSL)

```bash
# .env
VPS_HOST=localhost
DATABASE_URL=postgresql://fabrik:dev@localhost:5432/fabrik_dev
LOG_LEVEL=DEBUG
LOG_FORMAT=text
```

**Why:** Local services, verbose logging, human-readable output.

### Production (VPS)

```bash
# .env
VPS_HOST=172.93.160.197
VPS_IP=172.93.160.197
DATABASE_URL=postgresql://fabrik:${SECURE_PASSWORD}@postgres-main:5432/fabrik
LOG_LEVEL=INFO
LOG_FORMAT=json
DUPLICATI_PASSPHRASE=${SECURE_PASSPHRASE}
```

**Why:** Real IPs, secure passwords, structured logs, encrypted backups.

---

## Configuration Files

### `.env` vs `.env.example`

| File | Purpose | Git |
|------|---------|-----|
| `.env.example` | Self-documenting template with all vars, defaults, and inline help | ✅ Committed |
| `.env` | Your actual credentials and config | ❌ Gitignored |

**Pattern:** `.env.example` has comprehensive comments. Copy and fill in values.

### `config/platform.yaml`

**Purpose:** Non-secret platform configuration.

**When to use:**
- Cross-environment settings (backup schedule)
- Feature flags
- Service discovery rules

**When NOT to use:**
- Secrets → Always in `.env`
- Per-deployment config → `specs/*.yaml`

---

## Troubleshooting

### "Permission denied" on VPS

**Cause:** SSH key not set up or wrong user.

**Fix:**
```bash
ssh-copy-id deploy@your-vps
# Or use password temporarily:
VPS_SSH_KEY=  # Remove from .env
```

### Coolify API 401 Unauthorized

**Causes:**
1. Token expired → Regenerate in Coolify dashboard
2. Wrong token → Check for copy/paste errors
3. Coolify not running → `systemctl status coolify`

### Database connection refused

**Check:**
```bash
# Is postgres running?
docker ps | grep postgres-main

# Can you connect manually?
psql $DATABASE_URL

# Check from app container:
docker exec -it myapp psql $DATABASE_URL
```

### Namecheap service 404

**Cause:** Service not deployed or wrong URL.

**Fix:**
```bash
# Check service health
curl https://namecheap.vps1.ocoron.com/health

# Fallback: Use direct API
NAMECHEAP_API_USER=youruser
NAMECHEAP_API_KEY=yourkey
NAMECHEAP_CLIENT_IP=your-ip
```

---

## Security Best Practices

### Password Generation

**DO:**
```bash
# 32+ characters, random
python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32)))"
```

**DON'T:**
- `password123`
- Dictionary words
- Reuse across services

### Credential Storage

1. **Development:** `.env` file (gitignored)
2. **Production:** Environment variables set by Coolify
3. **Backup:** `/opt/fabrik/.env` (master copy)

### Rotation Schedule

- API tokens: Every 90 days
- Database passwords: Every 180 days
- Encryption passphrases: Never (backups become unrecoverable)

---

## Migration Guides

### Adding a New Service

1. Add env vars to `.env.example` with comments
2. Document credential acquisition in this guide
3. Update config verification in `fabrik.config`

### Changing DNS Provider

**Namecheap → Cloudflare:**
```bash
# 1. Get Cloudflare credentials
# 2. Add to .env:
CLOUDFLARE_API_TOKEN=xxx
CLOUDFLARE_ZONE_ID=xxx

# 3. Fabrik auto-detects and switches
```

**Rollback:** Remove `CLOUDFLARE_*` vars, falls back to Namecheap.

---

## Configuration Checklist

Before deploying:

- [ ] `.env` created from `.env.example`
- [ ] All required credentials obtained (VPS, Coolify, B2)
- [ ] SSH access verified: `ssh deploy@$VPS_HOST`
- [ ] Database accessible: `psql $DATABASE_URL`
- [ ] Backups configured: `DUPLICATI_PASSPHRASE` set
- [ ] Verification passed: `python -m fabrik.config --verify`
- [ ] Master backup exists: `/opt/fabrik/.env` synced
