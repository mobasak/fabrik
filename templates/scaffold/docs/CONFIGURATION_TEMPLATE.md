# Configuration — [Project Name]

**Last Updated:** YYYY-MM-DD

> **Purpose:** ENVIRONMENT VARIABLES AND SETTINGS.
> For the variable list itself, see `.env.example` — it's self-documenting.

---

## Quick Setup

```bash
cp .env.example .env
# Edit .env — fill required values (port is pre-assigned in .env.example)
docker compose up -d
curl http://localhost:$PORT/health
```

---

## Environment Variables

<!-- This is the authoritative reference for all variables.
     .env.example has the same list with inline comments, but this doc explains WHY and HOW.
     Port is auto-assigned by scaffold and recorded in project.yaml and .env.example — do not hardcode. -->

### Required

| Variable | Example | Description |
|----------|---------|-------------|
| `PORT` | *(see .env.example)* | Service port. Auto-assigned by scaffold, registered in `PORTS.md`. |
| `DATABASE_URL` | `postgresql://user:pass@postgres-main:5432/[project]` | PostgreSQL connection string |

<!-- Add project-specific required vars. Delete DATABASE_URL if not using a database. -->

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `REDIS_URL` | — | Redis connection. Only needed if caching enabled. |

<!-- Add project-specific optional vars. -->

---

## Getting Credentials

<!-- One subsection per external service that requires API keys or credentials.
     Delete this entire section if the project has no external dependencies.

     For every service: name the *exact* permission scope and a one-shot
     verification command. "Create API key" is not a runbook — "create a token
     with `Zone.DNS:Edit` scoped to ocoron.com" is. The verify step is what
     stops "I copy-pasted the wrong token" from costing 30 minutes later.

     Cross-link the per-vendor rate-limit / fallback / failure-signature
     details to `docs/SERVICES.md` rather than duplicating them here.
-->

### {External Service Name}

**Why needed:** {One sentence — what this credential enables.}

**How to get:**
1. Go to {provider URL}
2. Sign in / sign up · then [provider-specific path to API tokens]
3. Create {credential type — e.g. "API token"} with **exact scope**: `{provider permission name}` (not broader; least privilege)
4. Restrict to `{IP allowlist / domain}` if the provider supports it
5. Add to `.env`: `{VAR_NAME}={value}`

**Verify it works:**

```bash
# One-shot check — should return 200 + a non-empty body
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer ${VAR_NAME}" \
  {provider verify endpoint}
```

**Limits / cost:** {free tier / pricing / monthly cap — keep concise; SERVICES.md owns the rate-limit detail}

**Rotation cadence:** {every N days / on suspicion / never — and where the rotation runbook lives, usually `docs/OPERATIONS.md` §3}

<!-- Worked example — keep one in for new contributors as a model.
     Delete or replace once project-specific entries exist.

### Cloudflare (example)

**Why needed:** DNS record management for `*.vps1.ocoron.com` (Traefik certs).

**How to get:**
1. Go to https://dash.cloudflare.com/profile/api-tokens
2. Create Token → "Edit zone DNS" template
3. Permissions: `Zone.DNS:Edit`, `Zone.Zone:Read` (no account-level scopes)
4. Zone Resources: `Include` → `Specific zone` → `ocoron.com`
5. Add to `.env`: `CLOUDFLARE_API_TOKEN=...`

**Verify it works:**
```bash
curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  "https://api.cloudflare.com/client/v4/user/tokens/verify"
# → HTTP 200
```

**Limits / cost:** free for DNS; 1,200 req / 5 min per token (see SERVICES.md).

**Rotation cadence:** every 12 months OR on suspicion. See `docs/OPERATIONS.md` §3 "Recurring tasks".
-->

<!-- Repeat for each external service. -->

### Database

**Shared postgres-main (recommended for Fabrik services):**

```bash
DATABASE_URL=postgresql://[project]:password@postgres-main:5432/[project]
```

**Local PostgreSQL (dev only):**

```bash
DATABASE_URL=postgresql://localhost:5432/[project]_dev
```

---

## Environment Profiles

### Development (WSL)

```bash
PORT=<see .env.example>
LOG_LEVEL=DEBUG
DATABASE_URL=postgresql://localhost:5432/[project]_dev
```

### Production (VPS / Docker Compose)

```bash
PORT=${PORT}
LOG_LEVEL=INFO
DATABASE_URL=postgresql://[project]:${DB_PASSWORD}@postgres-main:5432/[project]
REDIS_URL=redis://redis-main:6379/0
```

**Production rules:**
- No `localhost` or `127.0.0.1` — use Docker service names (`postgres-main`, `redis-main`)
- No hardcoded credentials — use `${VARIABLE}` references
- Use `${VAR:?required}` in compose.yaml for critical vars to fail fast

---

## Port Allocation

Port is auto-assigned during scaffolding and stored in `project.yaml` and `.env.example`.

Ranges: Python APIs 8000–8099, Frontend 3000–3099, Workers 8100–8199.

Before adding new ports, check `PORTS.md` for conflicts:

```bash
cat PORTS.md
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Config validation failed | Missing required env var | Check `.env` against `.env.example` |
| Port already in use | Another service on same port | Check `PORTS.md`, pick next available |
| Database unreachable | Wrong `DATABASE_URL` or network | Verify: `psql $DATABASE_URL` |
| Service starts but unhealthy | Dependency not ready | Check `/health` response for failing deps |

```bash
# Debug commands
psql $DATABASE_URL              # Test DB connection
lsof -i :$PORT                  # Check port availability
cat .env | grep -v '^#|^$'      # Show active env vars
```

## Configuration Checklist

Before deploying:

- [ ] `.env` created from `.env.example`
- [ ] All required credentials obtained
- [ ] **Port registered in `PORTS.md`** (MANDATORY — deployment may fail otherwise)
- [ ] Database accessible (if used)
- [ ] Health endpoint returns 200 AND tests DB: `curl http://localhost:${PORT}/health`
- [ ] No hardcoded `localhost` in `compose.yaml` (use service names)
- [ ] Logs writing to expected location
- [ ] Environment-specific settings verified (dev vs prod)
- [ ] amd64 compatibility confirmed (base images use `-slim-bookworm`, not Alpine)
