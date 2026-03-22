# Configuration Guide

**Last Updated:** YYYY-MM-DD

**Purpose:** This guide explains HOW to configure this service and WHY certain configurations exist. For WHAT variables are needed, see `.env.example` which is self-documenting.

---

## Quick Setup

```bash
# 1. Copy template
cp .env.example .env

# 2. Edit with your values
nano .env

# 3. Verify configuration loads
python -m src.main --check-config
```

**All variables are documented in `.env.example` with inline comments.**

---

## Getting Credentials

### Example: External API Service

**Why needed:** [Brief explanation of why this service needs the API]

**How to get:**
1. Go to https://service-provider.com
2. Create account or login
3. Navigate to Settings → API Keys
4. Create new key with [required permissions]
5. Copy key (shown once)
6. Add to `.env`: `API_KEY=your_key_here`

**Cost/Limits:**
- Free tier: [limits]
- Paid tier: [pricing]

### Database Access

**Why needed:** [Explain what database features are enabled]

**Options:**

**Shared postgres-main (recommended):**
```bash
DATABASE_URL=postgresql://myapp:password@postgres-main:5432/myapp
```

**Local PostgreSQL:**
```bash
DATABASE_URL=postgresql://localhost:5432/myapp_dev
```

---

## Architecture Context

### Why This Service Exists

[1-2 paragraph explanation of this service's role in the broader system]

### Configuration Philosophy

- **Environment variables** → Runtime config (secrets, endpoints)
- **Config files** → Static business logic
- **Feature flags** → Gradual rollouts, A/B tests

### Port Selection

**Default:** 8000

**Conflicts?** See `PORTS.md` for project port registry. Update if needed.

---

## Environment-Specific Setups

### Development (WSL)

```bash
# .env
PORT=8000
LOG_LEVEL=DEBUG
LOG_FORMAT=text
DEBUG_MODE=true
DATABASE_URL=postgresql://localhost:5432/myapp_dev
```

**Why:** Local services, verbose logging, human-readable output, hot reload enabled.

### Production (VPS via Coolify)

```bash
# .env
PORT=${PORT}  # Coolify-managed
LOG_LEVEL=INFO
LOG_FORMAT=json
DEBUG_MODE=false
DATABASE_URL=postgresql://myapp:${DB_PASSWORD}@postgres-main:5432/myapp
```

**Why:** Container networking, structured logs for aggregation, security hardening.

---

## Troubleshooting

### "Config validation failed"

**Cause:** Missing required environment variable.

**Fix:**
1. Check error message for missing var
2. Verify `.env` has all vars from `.env.example`
3. Check for typos in variable names

### Service won't start

**Common causes:**
- **Port already in use** → Change `PORT` in `.env`
- **Database unreachable** → Verify `DATABASE_URL` and network
- **Invalid credentials** → Regenerate API keys

**Debug:**
```bash
# Test database connection
psql $DATABASE_URL

# Check port availability
lsof -i :8000

# Validate env file
cat .env | grep -v '^#' | grep -v '^$'
```

---

## Security Best Practices

### Credential Management

**DO:**
- Use strong, unique passwords (32+ chars)
- Rotate API keys every 90 days
- Store backups in secure location

**DON'T:**
- Commit `.env` to git
- Share credentials in chat/email
- Reuse passwords across services

### Secret Generation

```bash
# Generate strong password
python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32)))"
```

---

## Configuration Checklist

Before deploying:

- [ ] `.env` created from `.env.example`
- [ ] All required credentials obtained
- [ ] Port registered in `PORTS.md`
- [ ] Database accessible (if used)
- [ ] Health endpoint returns 200: `curl http://localhost:${PORT}/health`
- [ ] Logs writing to expected location
- [ ] Environment-specific settings verified (dev vs prod)
