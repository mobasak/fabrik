# Configuration Guide

**Last Updated:** 2026-04-26

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

**Why needed:** Deploy applications to your VPS via `fabrik apply` (SSH + Docker Compose).

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

<!--
Coolify API Token section — REMOVED 2026-06-02 (coolify-residue-cleanup plan).

Coolify was fully removed from vps1 on 2026-05-30 (no containers, no binary;
only /data/coolify/ filesystem residue remains). The active deploy path is
SSH + Docker Compose (`fabrik apply`). The legacy CLI commands (`fabrik status`,
`fabrik logs`, `fabrik reconcile-all`) that historically talked to the Coolify
API are now non-functional and listed under "Known broken" in the SSH-deployer
archived plan.

New projects never needed a Coolify API token.
-->

### FABRIK_EXEC_MODE — WordPress driver execution mode (T1.1)

**Why needed:** The `fabrik.drivers.wordpress` module (`ContainerResolver` + `WordPressClient`) historically assumed it was running on a WSL workstation that reaches the VPS over SSH. Phase 1 of the WordPress Factory introduces on-VPS execution surfaces (T1.5 cron, Phase 5 watchdog) where wrapping every `docker exec` in `ssh vps …` is pointless overhead. `FABRIK_EXEC_MODE` flips the dispatch at the driver level so the same code path runs unchanged in both environments.

**Values:**

| Value | When to use | Effect |
|-------|-------------|--------|
| `ssh` (default; unset = `ssh`) | WSL development; any remote orchestration | Driver invokes `ssh ${VPS_HOST} 'sudo docker exec …'` — byte-identical to pre-T1.1 behaviour |
| `local` | `fabrik` CLI running ON the VPS itself (T1.5 systemd cron, Phase 5 self-healing watchdog) | Driver invokes `sudo docker exec …` directly as an argv list — zero outbound SSH |

**Fail-fast:** any other value (e.g. `paramiko`, `remote`, typos) raises `ValueError` at the first driver call with the malformed value echoed back. Bad config surfaces immediately rather than ~30s into the first `docker exec` timeout.

**Back-compat guarantee:** unset env + unset constructor `exec_mode=` kwarg → SSH path. Existing WSL workflows and orchestration code that already pass `ssh_host=` keep working unchanged.

**Override precedence:** constructor `exec_mode=` kwarg > `FABRIK_EXEC_MODE` env var > `ssh` default. The constructor seam exists so unit tests and future orchestrators can pin the mode without mutating process env.

### DNS (Cloudflare driver)

> **⚠️ RETIRED — not deployed.** The dns-manager microservice was retired; `dns.vps1.ocoron.com` returns NXDOMAIN. DNS is now handled directly via the Cloudflare driver (`src/fabrik/drivers/cloudflare.py`). The historical service architecture below is kept for reference.

**Why this approach:** Fabrik talks to the Cloudflare API directly via the driver — no separate DNS microservice to deploy or keep healthy.

**Architecture:**
- ~~DNS Manager service runs at `https://dns.vps1.ocoron.com`~~ (retired)
- Cloudflare driver handles DNS record creation/updates
- Requires `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ZONE_ID` (see `.env.example`)

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

### Content Creation Pipeline

**Architecture:** Three microservices orchestrate SEO-driven content generation:
1. **SEO Service** (port 8016) — Keyword research, clustering, content briefs
2. **TCO** (port 8025) — AI content generation from briefs
3. ~~**Image Broker** (port 18016) — Stock image selection (Pexels/Pixabay)~~ — **RETIRED 2026-06-02** (not deployed; `images.vps1.ocoron.com` returns NXDOMAIN)

**Environment variables:**
- `SEO_API_URL` — SEO service endpoint (http://localhost:8016 or https://seo.vps1.ocoron.com)
- `SEO_API_KEY` — Bearer token for SEO service authentication
- `TCO_API_URL` — TCO service endpoint (http://localhost:8025)
- `TCO_API_KEY` — Bearer token for TCO authentication
- ~~`IMAGE_BROKER_URL` — Image Broker endpoint (http://localhost:18016)~~ — **RETIRED 2026-06-02** (image-broker no longer deployed)
- `CONTENT_WORKER_ID` — Worker identifier for brief lifecycle tracking (default: fabrik-content-publisher)

**WordPress credentials:** `WP_ADMIN_USER` and `WP_ADMIN_PASSWORD` are read by `deployer.py` for the REST API client (`WordPressAPIClient`). The domain is derived from the site spec — no `WP_SITE_URL` env var is needed. To target a different site, run with a different spec/site_id.

**Development:** All services run locally via docker-compose. Use `http://localhost:PORT`.
**Production:** Services deployed on VPS at `*.vps1.ocoron.com` with internal Docker networking.

### AI Model Aggregator Keys

Used by `scripts/kilo-benchmarks/fetch_*_prices.py` to populate `agents.gateway_prices` with live per-model pricing across aggregators, so the AI Models Browser surfaces the cheapest gateway per row (same OR ↔ Kilo cheapest-rate pattern, extended to non-LLM specialists). See [docs/development/plans/2026-06-29-plan-2-aggregator-pricing.md](development/plans/2026-06-29-plan-2-aggregator-pricing.md).

- `FAL_KEY` — fal.ai key in `KEY_ID:SECRET` format. Get from [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys). Read-only catalog access is sufficient for price discovery. **Positive balance required** for the specialty bench (`microbench_specialty.py`) since it enqueues real image generations against Fal.ai's BFL Flux mirror.

### Specialty-service bench providers (kilo-benchmarks)

Used by [scripts/kilo-benchmarks/microbench_specialty.py](../scripts/kilo-benchmarks/microbench_specialty.py) to fill the AI Models Browser Speed column for non-LLM rows (`image_gen`, `tts`, `music_gen`, `stt`, `translation`). Sunday cron; $10 hard / $2.50 soft per-run cost cap. See [docs/development/plans/2026-07-03-plan-1-full-speed-coverage-close.md](development/plans/2026-07-03-plan-1-full-speed-coverage-close.md).

- `REPLICATE_API_TOKEN` — Replicate prediction API. Get from [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens). Unlocks Stability SD family + Stable Audio rows (~6 rows).
- `RECRAFT_API_KEY` — Recraft direct REST. Get from [recraft.ai/profile/api](https://www.recraft.ai/profile/api). Unlocks `recraft/v3` + `recraft/nano-banana` (~2 rows; 40 credits ≈ $0.04 per image).
- `DASHSCOPE_API_KEY` — Alibaba DashScope, `sk-ws-…` format. Get from [dashscope.console.aliyun.com](https://dashscope.console.aliyun.com/apiKey). Unlocks `qwen/qwen-mt-turbo` (translation).
- `ELEVENLABS_API_KEY` — ElevenLabs REST. Get from [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys). Unlocks TTS (`multilingual-v2`, `turbo-v2.5`, `eleven-v3-alpha`) + `sound-effects` (~4 rows). Free tier absorbs the bench cost (~2.4k of 10k chars).

### GlitchTip (error tracking)

GlitchTip (`errors.vps1.ocoron.com`, Sentry-compatible) is declared in `specs/infrastructure/glitchtip.yaml` and is the error-tracker source for the AI watchdog (`org=ocoron`, `team=vps1`). It reuses `postgres-main` (DB `glitchtip`) + `redis-main`. Env vars:

- `GLITCHTIP_SECRET_KEY` — Django secret key. **Use the existing live value** (`/opt/glitchtip/compose.yaml`); changing it invalidates all sessions.
- `GLITCHTIP_REDIS_URL` — e.g. `redis://redis-main:6379/<db>` (existing live value).
- `POSTGRES_PASSWORD` — shared `postgres-main` superuser password (already provisioned).

⚠️ Do not `fabrik apply specs/infrastructure/glitchtip.yaml` until these match the live deployment, or the live tracker + its session keys break. The spec declares the existing hand-deployed stack; `fabrik apply` is targeted, so adding it does not auto-redeploy.

### Watchdog DB access — `WATCHDOG_DB_URL_RO` / `WATCHDOG_DB_URL_RW` (auto-injected, do NOT set by hand)

For a watchdog-enabled project with `shape.needs_database`, the postgres registrar auto-provisions two per-project roles on the app DB and injects their DSNs into the project `.env` at `fabrik apply`: `WATCHDOG_DB_URL_RO` (SELECT-only, the sidecar's default diagnosis lane) and `WATCHDOG_DB_URL_RW` (DML-only — no DDL/DROP — the Tier-C approved-write lane). These are **generated + managed by the hub, never operator-set** (like `DATABASE_URL`): minted on fresh role creation, preserved on re-apply. Full contract + privilege boundary in the `WATCHDOG` rule pack (`.windsurf/rules/core/60-watchdog.md`).

### Watchdog governance mount — `WATCHDOG_GOVERNANCE_MOUNT` (auto-set, do NOT set by hand)

At `fabrik apply`, the watchdog driver ships the project's governance set — `CLAUDE.md` + `AGENTS.md` + `.windsurf/rules/**` — from the hub's project tree to a dedicated per-project host dir on the VPS (`/var/lib/watchdog-governance/<id>/`, world-readable, refreshed every apply), bind-mounts it **read-only** into the sidecar at `/governance`, and sets `WATCHDOG_GOVERNANCE_MOUNT=/governance` in the sidecar env. fabrik-lib's `_materialize_conventions` reads that path (else falls back to `/project`) to make the watchdog's Tier-D fixes convention-conforming. This exists because the `/opt/<id>:/project:ro` mount is **hollow** — VPS deploy excludes gitignored `.windsurf/rules/`. **Hub-managed, never operator-set;** fail-soft (if the governance set is absent the mount + env are skipped, and materialize falls back to `/project`). Design: `docs/superpowers/specs/2026-07-07-watchdog-governance-mount-design.md`.

### Watchdog Tier-D operator knobs — `WATCHDOG_REDEPLOY_TIMEOUT` / `WATCHDOG_TELEGRAM_OPERATOR_IDS` (operator-supplied, project `.env`)

Unlike the auto-injected vars above, these two are **operator-supplied** in the project `.env` (loaded by the sidecar via `env_file`; the hub does NOT mint them): `WATCHDOG_REDEPLOY_TIMEOUT` (seconds before a redeploy is considered timed-out) and `WATCHDOG_TELEGRAM_OPERATOR_IDS` (comma-separated Telegram chat IDs that gate the fail-closed approval channel). Fail-closed behaviors they drive (fabrik-lib `watchdog/`, commit `1226196`): the sidecar does **not** auto-deploy when the Telegram channel is unreachable, and only PROPOSE-phase incidents auto-apply on timeout. Full behavior in the `WATCHDOG` rule pack.

### Subagent flywheel — `SUBAGENT_RUNS_DSN` / `SUBAGENT_PROJECT` (hub-injected; do NOT hand-set the DSN)

The vendored `libs/subagents` pool scores every run to `fabrik_analytics.subagent_runs` via `record_agent_run`, which `pick_models(task_type)` learns from. The module autoloads both vars from `.env` (`_dotenv.py`, non-overriding — a real `export` or a deploy-injected value always wins):

- `SUBAGENT_RUNS_DSN` — an **INSERT-only** writer DSN for `fabrik_analytics.subagent_runs`. The hub mints the per-project role (`create_subagent_ins_role`) and injects the DSN at `fabrik apply` (VPS) — like `WATCHDOG_DB_URL_*`, generated + managed by the hub, never operator-set; on **WSL dev** it lives in `/opt/fabrik/.env`. **Unset ⇒ `record_agent_run` fail-opens** (no row, no crash) and the flywheel silently doesn't learn — `scripts/enforcement/check_subagent_flywheel.py` WARNs on the resulting unreceipted pool runs.
- `SUBAGENT_PROJECT` — the project tag written on each row (e.g. `fabrik-hub`), so runs are attributable per project.

The writer role is INSERT-only (no SELECT) — read the table via the `postgres` superuser, never the writer DSN.

---

## Architecture Context

### Database Strategy

**Single shared PostgreSQL instance:**
- `postgres-main` container serves all projects
- Each project gets its own database
- Connection string format: `postgresql://user:pass@postgres-main:5432/dbname` <!-- noqa: doc example, not a real cred -->

**Why:** Resource efficiency, easier backups, consistent version.

### DNS Provider Choice

**Development:** Use DNS Manager service (no local credentials needed)

**Production options:**
1. **Cloudflare driver** (current) - Direct Cloudflare API via `src/fabrik/drivers/cloudflare.py`; fast propagation, free tier
2. ~~**DNS Manager service**~~ — **RETIRED** (not deployed; `dns.vps1.ocoron.com` returns NXDOMAIN)

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
DATABASE_URL=postgresql://fabrik:dev@localhost:5432/fabrik_dev  # noqa: doc example, local dev placeholder
LOG_LEVEL=DEBUG
LOG_FORMAT=text
```

**Why:** Local services, verbose logging, human-readable output.

### Production (VPS)

```bash
# .env
VPS_HOST=172.93.160.197
VPS_IP=172.93.160.197
DATABASE_URL=postgresql://fabrik:${SECURE_PASSWORD}@postgres-main:5432/fabrik  # noqa: env-var interpolation, not a hardcoded cred
LOG_LEVEL=INFO
LOG_FORMAT=json
# Backups: Backrest manages credentials internally; no env var required (replaced Duplicati 2026-04-17)
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

### Project-Specific `.env` Files

**For deployment secrets, Fabrik uses project-specific `.env` files.**

Each project has its own `.env` file at `/opt/{project}/.env` for deployment secrets:

```bash
# /opt/my-api/.env (project-specific)
API_KEY=your_api_key
DATABASE_PASSWORD=your_password
SECRET_TOKEN=your_secret_token
```

**How Fabrik loads secrets:**

1. **Scaffold auto-detection:** `fabrik scaffold` reads `.env.example` and auto-detects secret env vars (matching patterns like `_KEY`, `_SECRET`, `_PASSWORD`, `_TOKEN`, `_CREDENTIALS`). These are added to the spec's `from_env` field.

2. **Automatic loading:** `fabrik apply` automatically reads from the project's `.env` file before checking system environment variables.

3. **Precedence:** Command-line `-s` flags (highest) → Project `.env` file → Environment variables (lowest).

**Benefits:**
- No manual environment variable setting needed
- Secrets are isolated per project
- Works seamlessly across WSL dev and VPS Docker environments
- Easy to override with `-s` flags when needed

### `config/platform.yaml`

**Purpose:** Non-secret platform configuration.

**When to use:**
- Cross-environment settings (backup schedule)
- Feature flags
- Service discovery rules

**When NOT to use:**
- Secrets → Always in `.env`
- Per-deployment config → `specs/*.yaml`

### `FABRIK_LOCK_DIR` (T2-01)

Directory where `fabrik.locks_local.file_lock()` creates lock files. Used to
serialize WSL-side Python orchestration — for example, `fabrik reconcile-all`
walking specs and `state.save()` writing `.fabrik/state/<id>.json` under
contention.

- **Default:** `/tmp/fabrik-locks`
- **When to override:** if `/tmp` is on a filesystem without flock support
  (rare on modern WSL2; possible on some containers/CI), point at a path
  on the same filesystem as `FABRIK_ROOT`.

Distinct from the registrar-side VPS lock (`fabrik.drivers.locks.run_locked`),
which operates over SSH on the VPS and lives in `/tmp/fabrik-<resource>.lock`
on the remote host. The two never interact.

### Scheduled audits — WSL cron (T2-03)

`scripts/audit_authelia_gates.py` runs every Monday 06:00 local via WSL `cron`, verifying every admin-dashboard's Traefik router still has the `authelia-forward@docker` middleware attached (the policy-vs-enforcement drift class from Lesson 32 / GlitchTip 2026-04-18 incident).

The cron entry was installed on 2026-05-15 by T2-03 G-G4:

```cron
0 6 * * 1 PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_authelia_gates.py >> /var/log/fabrik-audit.log 2>&1
```

Log file lives at `/var/log/fabrik-audit.log` (writable by `ozgur:ozgur`; `sudo touch + chown` if it disappears). Each run appends a single block ending in `SUMMARY: N OK, M GAP, K MISSING`.

**Verifying:**

```bash
crontab -l | grep audit_authelia_gates
sudo tail -20 /var/log/fabrik-audit.log
# Manual run on demand:
PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_authelia_gates.py
```

**Removing:** `crontab -e` and delete the line. The script itself stays in place for ad-hoc runs.

WSL cron quirk: ensure `systemctl is-active cron` returns `active` after a WSL restart. Some fresh WSL installs don't autostart cron; if cron is `inactive` after reboot, run `sudo service cron start` and consider enabling on boot via `sudo systemctl enable cron`.

### Preplan workflow (T3-01)

Stage 1 of the Fabrik lifecycle captures project intent in `docs/preplans/<YYYY-MM-DD>-<slug>.md` BEFORE `fabrik scaffold` runs. The 9-section template (rendered by `fabrik preplan new <slug>` from `templates/preplan/preplan.md.j2`) covers Idea / Project type / Shape preview / External deps / Domain / Success criteria / Out of scope / Open questions / Notes (VPS1 inventory reminders — embedded so agents reading the preplan stay grounded in `postgres-main:5432`, `redis-main:6379`, `X-Internal-Token`, `/health` bypass, `/metrics`, GlitchTip DSN).

`fabrik scaffold <name> --from-preplan <path>` then:

- Pre-fills `--type` and description from the preplan
- Copies the markdown into `<project>/docs/preplan.md`
- Appends a `Preplan:` reference line to ALL 4 AI guardrail files (`AGENTS.md`, `CLAUDE.md`, `AGENTS-compact.md`, `.windsurfrules`) so every downstream agent reads the same intent

No new env vars. The workflow is documented in `docs/preplans/README.md` and Traycer ingests it via Step 2.5 of `docs/traycer/fabrik-workflow.md`.

<!--
`coolify.alias` spec field section — OBSOLETE 2026-06-02.

The Coolify Application UUID-suffix container renaming this section worked
around no longer happens — Coolify was fully removed from vps1 on 2026-05-30.
All containers now have stable names via compose `container_name:` fields
(Lesson 22). The `coolify-alias-watcher.service` was decommissioned with
Coolify. Code references to `coolify.alias` / `coolify_alias.add_alias()`
remain in archived legacy modules (`src/fabrik/orchestrator/coolify_alias.py`)
but are no longer called from any active code path.
-->

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

<!--
"Coolify API 401" troubleshooting section — REMOVED 2026-06-02.

Coolify is fully removed from vps1 (2026-05-30). The legacy CLI commands
that used to call the Coolify API (`fabrik status`, `fabrik logs`,
`fabrik reconcile-all`) are non-functional and listed under "Known broken"
in the archived SSH-deployer plan. New troubleshooting starts from
`docs/operations/deployment.md` (`fabrik apply` / SSH + Docker Compose).
-->

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

### ~~DNS Manager service 404~~ (RETIRED — historical)

> **⚠️ RETIRED — not deployed.** The dns-manager service was retired; `dns.vps1.ocoron.com` now returns NXDOMAIN (not a 404). DNS is handled directly via the Cloudflare driver (`src/fabrik/drivers/cloudflare.py`) — set `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ZONE_ID`. The troubleshooting below is kept for historical reference only.

**Cause:** Service not deployed or wrong URL.

**Fix:**
```bash
# Check service health
curl https://dns.vps1.ocoron.com/health

# Fallback: Direct Namecheap API (used internally by dns-manager)
# These are configured in dns-manager's .env, not in application code
# NAMECHEAP_API_USER=youruser
# NAMECHEAP_API_KEY=yourkey
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
2. **Production:** Environment variables in `/opt/<project>/.env` on the VPS, written and merged by `fabrik apply` (SSH + Docker Compose)
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

**Switch to Cloudflare:**
```bash
# 1. Get Cloudflare credentials
# 2. Add to .env:
CLOUDFLARE_API_TOKEN=xxx
CLOUDFLARE_ZONE_ID=xxx

# 3. Fabrik auto-detects and switches
```

**Rollback:** Remove `CLOUDFLARE_*` vars, falls back to default provider.

---

## Configuration Checklist

Before deploying:

- [ ] `.env` created from `.env.example`
- [ ] All required credentials obtained (VPS, Cloudflare, B2)
- [ ] SSH access verified: `ssh deploy@$VPS_HOST`
- [ ] Database accessible: `psql $DATABASE_URL`
- [ ] Backups configured: Backrest configured at `backup.vps1.ocoron.com` (Backblaze B2 remote)
- [ ] Verification passed: `python -m fabrik.config --verify`
- [ ] Master backup exists: `/opt/fabrik/.env` synced

---

## Environment Variable Best Practices

### 1. Never Hardcode Values

```python
# ❌ WRONG - breaks in Docker/VPS
DB_HOST = "localhost"
API_KEY = "sk-abc123"  # noqa: anti-pattern doc example

# ✅ CORRECT - works everywhere
DB_HOST = os.getenv('DB_HOST', 'localhost')
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    raise ValueError("API_KEY environment variable is required")
```

### 2. Load Configuration at Runtime

```python
# ❌ WRONG - env vars not set at import time
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/db"  # noqa: env-var interpolation, doc example
    # This evaluates immediately when class is defined!

# ✅ CORRECT - load in function/property
def get_db_url() -> str:
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST', 'localhost')
    return f"postgresql://{user}:{password}@{host}/db"  # noqa: param interpolation, doc example

# OR use Pydantic Settings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    db_user: str
    db_password: str
    db_host: str = "localhost"

settings = Settings()  # Loads from env at instantiation
```

### 3. Store Credentials in Two Places

**Always maintain backups:**

1. **Project `.env`** - For local development use
2. **`/opt/fabrik/.env`** - Master backup (survives project deletion)

```bash
# After creating project .env, backup to master
cp /opt/my-project/.env /opt/fabrik/.env.my-project.backup
```

### 4. Document in .env.example

```bash
# .env.example (COMMIT THIS to git)
# Never commit actual .env file!

# Database Configuration
DB_HOST=localhost                    # Database host (localhost for dev, postgres-main for Docker)
DB_PORT=5432                         # PostgreSQL port
DB_NAME=myapp_dev                    # Database name
DB_USER=postgres                     # Database username
DB_PASSWORD=                         # SET IN .env - never commit actual password

# AI/LLM: no direct API key. Operational AI uses Claude Code OAuth; content/LLM
# calls use OpenRouter (watchdog reads WATCHDOG_OPENROUTER_KEY in its own env).
```

### 5. Environment-Specific Defaults

**WSL (Development):**
```python
DB_HOST = os.getenv('DB_HOST', 'localhost')  # Local PostgreSQL
DB_PORT = int(os.getenv('DB_PORT', '5432'))
```

**VPS Docker (Production):**
```yaml
# compose.yaml
environment:
  - DB_HOST=postgres-main  # Container name, not localhost
  - DB_PORT=5432
```

**Supabase:**
```python
# Use full connection string
DATABASE_URL = os.getenv('DATABASE_URL')  # Supabase provides this
```

### 6. Validation Patterns

```python
import os
from typing import Optional

def get_required_env(key: str) -> str:
    """Get required environment variable or raise error."""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value

def get_optional_env(key: str, default: str) -> str:
    """Get optional environment variable with default."""
    return os.getenv(key, default)

# Usage
API_KEY = get_required_env('API_KEY')  # Must be set
LOG_LEVEL = get_optional_env('LOG_LEVEL', 'INFO')  # Defaults to INFO
```

### 7. Type Conversion

```python
import os
from typing import List

# Boolean
DEBUG = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')

# Integer
PORT = int(os.getenv('PORT', '8000'))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '4'))

# Float
TIMEOUT = float(os.getenv('TIMEOUT', '30.0'))

# List (comma-separated)
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')
# ALLOWED_HOSTS=localhost,example.com → ['localhost', 'example.com']
```

---

## n8n Webhook Notifications

Fabrik fires fire-and-forget webhooks after deploy and content publish events.

**How it works:**
1. `deploy_router.py` calls `notify_deploy()` after every `fabrik apply`
2. `content_publisher.py` calls `notify_content()` after every `fabrik content publish`
3. n8n receives the POST, formats the message, POSTs to Apprise
4. Apprise fans out to configured channels (Telegram, email, etc.)

**Required env vars** (all optional — notifications silently skipped if absent):

```bash
N8N_WEBHOOK_DEPLOY=https://auto.vps1.ocoron.com/webhook/deploy-notify
N8N_WEBHOOK_CONTENT=https://auto.vps1.ocoron.com/webhook/content-notify
N8N_WEBHOOK_TIMEOUT=5   # seconds
APPRISE_STATELESS_URLS=tgram://BOTTOKEN/CHATID  # set in /opt/apprise/.env
```

**Setup sequence:**
1. Visit `https://auto.vps1.ocoron.com` → create owner account
2. Import workflows from `specs/n8n-workflows/` (Settings → Workflows → Import)
3. Activate each workflow → copy the Production webhook URL
4. Paste URL into `N8N_WEBHOOK_DEPLOY` / `N8N_WEBHOOK_CONTENT` in `.env`
5. Set `APPRISE_STATELESS_URLS` in `/opt/apprise/.env` on VPS, restart Apprise

**Apprise URL formats:**
- Telegram: `tgram://BOTTOKEN/CHATID`
- Email (Resend SMTP): `mailtos://resend:RESEND_API_KEY@smtp.resend.com?to=you@email.com`
- Multiple: comma-separated

**n8n workflows** (`specs/n8n-workflows/`):

| File | Event | Nodes |
|------|-------|-------|
| `01-deploy-notify.json` | `deploy.success` / `deploy.failure` from Fabrik | Webhook → Code → Apprise |
| `02-content-notify.json` | `content.published` from Fabrik | Webhook → Code → Apprise |
| `03-health-alert.json` | Gatus DOWN/UP | Webhook → Code → Apprise |
| `04-content-trigger.json` | Schedule every 6h | Schedule → HTTP → Apprise |

---

## See Also

- [.env.example](../.env.example) - Complete list of all environment variables
- [SERVICES.md](SERVICES.md) - External services catalog
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Common configuration issues
