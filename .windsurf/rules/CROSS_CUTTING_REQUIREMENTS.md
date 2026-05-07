---
activation: always
description: Cross-cutting requirements — doc currency, observability, user guide, reusability
trigger: always_on
---
# Cross-Cutting Requirements (Auto-enforced)

## 1. Documentation Currency

Update matched docs in the SAME staged change. Skipping = task failure.

| Change | Update |
|---|---|
| New env var added | `.env.example` (with comment block: Why / How to get / Default) |
| User provided real secret value | `.env` (write actual value; never staged — gitignored) |
| External service credential setup changed | `docs/CONFIGURATION.md` (How to get credentials section) |
| Code, Docker, deps changed | `CHANGELOG.md` (gate-enforced Tier 1) |
| Any file added / removed / renamed | `INDEX.md` |
| Tech stack or setup steps changed | `README.md` |
| API endpoint / SDK / CLI / Docker wiring / integration surface changed | `docs/QUICKSTART.md` |
| New port allocated | `PORTS.md` |
| Symptom encountered that future-you will hit again | `docs/TROUBLESHOOTING.md` (Symptom / Cause / Fix) |
| Feature shipped / deprecated / removed | `docs/FEATURES.md` (Status table; Removed table for deprecations) |
| New plan started | `docs/development/plans/YYYY-MM-DD-plan-<name>.md` |
| Schema migration | Alembic file + `db/schema.sql` |
| Future feature/refactor idea surfaces during work | `docs/STRATEGIC_BACKLOG.md` (Now / Later / Context) |
| Agent struggled then solved (with or without user help) — the "Aha!" moment | `docs/LESSONS_LEARNT.md` (full template entry; name target rule pack to update) |
| Agent hit a "silicon ceiling" — context drift, model limit, repeated mistake pattern | `AFCL.md` (Constraint table + Guardrail Recommendation) |
| Monetization / pricing / target customer / GTM decision | `docs/BUSINESS_MODEL.md` |

**Skip:** refactor-only / docs-only / test-only → `CHANGELOG.md` only.

## 2. Observability (ref: .windsurf/rules/55-observability.md)

Every service MUST implement:

- Structured logging (JSON format, correlation IDs)
- Health endpoint (`/health` or equivalent)
- Error classification (transient vs permanent)
- Log levels: DEBUG for dev, INFO for prod, ERROR for failures
- No print() — use logger exclusively
- Pre-scaffolded logger exists at `src/{package}/logger.py` (Python) or `src/logger.js` (Node)
- DO NOT create custom logging modules — import the existing one
- DO NOT use `print()` or `console.log()` — use the scaffolded logger

## 3. Docusaurus User Guide

Projects with user-facing features (APIs, UIs, CLIs) MUST include:
- `docs/user-guide/` directory with Docusaurus-compatible .md files
- Sidebar config (`sidebars.js` fragment or `_category_.json`)
- At minimum: Getting Started, Core Concepts, API Reference
- Guide pages written for END USERS, not developers
- Decision: Traycer determines in trigger_workflow whether
  this project needs a user guide (set `HAS_USER_GUIDE: true/false`
  in the project's epic brief)

## 4. Reusability & Modularity
Code MUST be structured for cross-project extraction:
- Business logic separated from framework/transport layer
- Shared utilities go in `src/utils/` or `src/lib/` with zero
  project-specific imports
- Any function that could serve another Fabrik project MUST
  be in its own module with its own docstring and type hints
- No hardcoded project-specific values in utility modules
- Tag reusable modules in INDEX.md with `[reusable]` marker

## 5. Sensitive Data Protection

Before modifying any credentials file (`.env`, `*.key`, `*.pem`, files under `secrets/`, files under `.ssh/`):

```bash
cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
```

**Forbidden without dry-run:** Destructive scripts on production data.
**Forbidden without full diff approval:** Any credentials change.

## 6. Password Policy

Generated passwords for service accounts, DB users, and internal tokens:

- **Length:** 32 characters
- **Charset:** `[a-zA-Z0-9]` only (no symbols — survives `.env` round-trips and shell quoting)
- **Generator:** Python `secrets.choice()` over `string.ascii_letters + string.digits`
- **Banned values:** `postgres`, `admin`, `password`, `password123`, default vendor credentials

```python
import secrets, string
alphabet = string.ascii_letters + string.digits
password = ''.join(secrets.choice(alphabet) for _ in range(32))
```

Applies wherever a password/secret is generated programmatically (Authelia bootstrap, `fabrik scaffold` credential generation, manual ops scripts).

## 7. Database & Cache Connection Strings (Docker environment)

**CRITICAL — applies to every service deployed via Coolify/Fabrik:**

| Variable | ❌ Wrong (local dev) | ✅ Correct (Docker/VPS) |
|---|---|---|
| `DB_HOST` | `localhost` | `postgres-main` |
| `DATABASE_URL` | `...@localhost:5432/...` | `...@postgres-main:5432/...` |
| `REDIS_URL` | `redis://localhost:6379` | `redis://redis-main:6379` |

**Why:** Inside a Docker container, `localhost` is the container itself — not the host, not `postgres-main`. Every service on this VPS connects to shared databases via Docker network DNS names.

**Rule:** Never use `localhost` in any `DATABASE_URL`, `DB_HOST`, `REDIS_URL`, or equivalent env var in production `.env` files or Coolify env var settings. Scaffold templates already emit the correct values — do not override them with localhost.

**Verify before deploy:**
```bash
grep -E "^(DB_HOST|DATABASE_URL|REDIS_URL)=" .env | grep localhost
# Should return nothing. If it returns anything, fix it first.
```

## 8. M2M Service-to-Service Authentication

Every Fabrik service that exposes HTTP endpoints must use the canonical internal auth pattern:

| Variable | Value |
|---|---|
| Header | `X-Internal-Token` |
| Env var | `SERVICE_INTERNAL_SECRET_KEY` |
| Module | `internal_auth.py` (copy into `app/` or `src/`) |
| Import | `from internal_auth import require_internal_token` |
| Validation | `hmac.compare_digest` / `timingSafeEqual` (constant-time) |

**Never** write inline `APIKeyHeader`/`require_api_key` logic. Never use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`).

### Authelia config changes
- Authelia does **NOT** support SIGHUP hot-reload — it exits.
- After any edit to `configuration.yml`: `docker restart <authelia-container-name>`
- Get container name: `ssh vps "sudo docker ps --filter name=authelia --format '{{.Names}}'"`

### Post-deploy checklist (every new service)

**A — Network:** All containers must be on `coolify` Docker network. Never bind ports to host. Let Traefik route via labels.

**B — Traefik labels:** Scaffold emits these automatically. Verify pattern:
- Admin dashboard → `authelia-forward@docker,gzip@docker`
- API service (X-Internal-Token auth) → `gzip@docker`
- Public service → no auth middleware

**C — Environment variables in Coolify:**
- `SERVICE_INTERNAL_SECRET_KEY` — same value as `/opt/fabrik/.env`
- `DATABASE_URL` → `postgresql://...@postgres-main:5432/<db>` (never localhost)
- `REDIS_URL` → `redis://redis-main:6379/0` (never localhost)

**D — Health check:** `/health` endpoint must exist and return 200. Authelia bypass rule `*.vps1.ocoron.com → /health` covers it automatically. Set healthcheck interval to 60s in Coolify for stable services.

### Calling a service (agent pattern)
```python
import os, httpx
headers = {"X-Internal-Token": os.environ["SERVICE_INTERNAL_SECRET_KEY"]}
resp = httpx.get("https://<service>.vps1.ocoron.com/api/endpoint", headers=headers)
```

## 9. Gatus Monitoring — Stable DNS Names (Mandatory)

**Rule:** Never use a UUID container name in Gatus config or any inter-service URL.

Coolify generates two types of containers:
- **Service stacks** (`/data/coolify/services/<uuid>/`): have a `container_name: <service>-<uuid>` that is stable because the UUID is the Coolify service ID (doesn't change on redeploy).
- **Single-image Applications** (`/data/coolify/applications/<uuid>/`): container name is `<app-uuid>-<timestamp>` — the **timestamp** changes on every redeploy. DNS breaks silently.

### For every new single-image Application deployed via Coolify:

```bash
# 1. Add stable alias to compose (persists through Coolify-managed redeploys)
sudo python3 -c "
import yaml
path = '/data/coolify/applications/<app-uuid>/docker-compose.yaml'
cfg = yaml.safe_load(open(path).read())
svc = cfg['services']['<uuid-name>']
svc['networks']['coolify']['aliases'].append('<stable-name>')
open(path, 'w').write(yaml.dump(cfg, default_flow_style=False))
"

# 2. Apply alias to live container (zero-downtime)
sudo docker network disconnect coolify <uuid-name>
sudo docker network connect --alias <stable-name> --alias <uuid-name> coolify <uuid-name>

# 3. Add to vps_apply_limits.sh (persists through VPS reboots)
# Add: apply_alias <uuid-name> <stable-name>

# 4. Use stable name in Gatus config
# url: "tcp://<stable-name>:<port>"
```

### Currently registered stable aliases
| Stable name | Container | Service |
|---|---|---|
| `browserless` | `vckgs8c00o40o884k48cgow8-220643454460` | Chromium headless |
| `gotenberg` | `e04k4sco44ow04ccc0o0k00k-151256201601` | PDF (Gotenberg) |
| `meilisearch` | `bs0wo48k4gwo440gcowscoc8-150802066640` | MeiliSearch |
| `glitchtip-web` | `glitchtip-web-z00kkck8c8cwo800kk440csk` | GlitchTip web |
