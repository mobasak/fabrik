# AGENTS.md — Fabrik Identity & Knowledge (Traycer Only)

**Last Updated:** 2026-04-17
**Read by:** Traycer only (auto-loaded every interaction)
**Coding agents:** Read `AGENTS-compact.md` via `opencode.json`

> For all development work, use the **Fabrik Development Workflow**.
> Owner drops pre-research at `docs/development/plans/00-research.md` after external research with ChatGPT/Claude/Gemini.

---

## Owner & Working Style

- **Solo developer** — Özgür Başak, 45, Turkish electronics engineer & entrepreneur
- **Capacity:** ~50 focused hours/week
- **Budget:** Limited — prefer free/cheap but good, fast tools, maximize ROI
- **Philosophy:** Fast but good. Ship fast, iterate, automate. No over-engineering.
- **Full profile:** `docs/owner_ozgur_basak.md`

## Development Environment

- **Dev machine:** WSL (Ubuntu 24.04) on Windows
- **IDE:** Windsurf (Cascade AI agents for interactive work)
- **Coding agents:** Windsurf Cascade (manual/interactive) · Kilo CLI (YOLO) · Local LLM agents
- **VPS:** x86_64 (amd64) Ubuntu at 172.93.160.197 — AMD EPYC-Genoa, 6 vCPU, 12 GB RAM
- **Deployment:** Coolify on VPS (Docker Compose) — `fabrik apply` automates DNS + Coolify + monitoring
- **Database:** PostgreSQL on VPS (default) · Supabase (when managed auth/realtime/pgvector needed)
- **Reverse proxy:** Traefik (managed by Coolify) — HTTPS/SSL via Let's Encrypt
- **Domains:** `*.vps1.ocoron.com` — managed by site-provisioner (supports Namecheap, Cloudflare, auto-purchase) and others
- **Monitoring:** Gatus · Netdata · Grafana · Prometheus · Alertmanager · Loki (all active, deployed 2026-04-13)

### Local LLM Agents

| Agent | Hardware | Memory Usage | Speed | Stability |
|-------|----------|--------------|-------|-----------|
| fabrik-coder | hybrid-cpu | ~19GB (8GB VRAM + 11GB RAM) | Moderate (~15-25 tok/s) | Stable |
| fabrik-reviewer | cpu | ~42GB RAM | Slow (~8-12 tok/s) | High memory pressure ⚠️ |
| fabrik-fixer | hybrid-gpu | ~9GB (8GB VRAM + 1GB RAM) | Fast (~40-60 tok/s) | Stable |
| fabrik-docs | gpu | ~5GB VRAM | Instant (~80-100 tok/s) | Rock solid |

## File & Folder Naming

All files and folders use **kebab-case** unless listed as an exception.

✅ `user-profile.ts`, `auth-service.py`, `api-client.md`, `docs/setup-guide.md`
❌ `UserProfile.ts`, `auth_service.py`, `ApiClient.md`

**Exceptions (do not rename):**
- `README.md`, `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `AGENTS.md`, `AGENTS-compact.md`, `LESSONS_LEARNT.md`, `Makefile`, `Dockerfile`
- Python packages use snake_case per PEP 8: `src/apidoccreator/`, `src/fabrik/`
- Auto-generated files (migrations, lock files, `__pycache__/`, `__init__.py`)
- Dotfiles and dotdirs (`.env`, `.windsurf/`, `.gitignore`)

**Document files follow the same rule:**
- Specs, guides, ADRs, plans → kebab-case
- Example: `seo-module-spec.md`, `deployment-guide.md`, `2026-01-refactor-adr.md`

## Tech Stack Defaults

| Layer | Default | Deviate When |
|-------|---------|-------------|
| Backend | Python + FastAPI + Uvicorn | Node.js for web-adjacent workers |
| Frontend | Next.js 14 + TypeScript + Tailwind | — always use this |
| Database | PostgreSQL 16 (VPS, Coolify-managed) | Supabase for managed auth/realtime/pgvector |
| Background jobs | PostgreSQL jobs table + worker | Redis queue for high throughput |
| AI/LLM | Kilo CLI free tiers → OpenAI/Anthropic APIs | Local Ollama for offline/free |
| Local LLM | Ollama (localhost:11434) | See `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` |
| Base images | `python:<current-stable>-slim-bookworm`, `node:<current-LTS>-bookworm-slim` | Never Alpine |
| PDF | Gotenberg (self-hosted) | WeasyPrint for simple cases |
| Search | MeiliSearch (self-hosted) | PostgreSQL FTS for simple cases |
| MeiliSearch | search.vps1.ocoron.com | `specs/infrastructure/meilisearch.yaml` | **Deployed:** 2026-04-14 |
| Notifications | Apprise (self-hosted) | Direct API for single-channel |
| Object storage | Backblaze B2 (via Backrest, deployed 2026-04-17) | MinIO for self-hosted S3-compatible when needed |
| PDF Generation | Gotenberg (self-hosted) | HTML/Office/PDF conversion API | **Deployed:** 2026-04-14 |

## Infrastructure Services — Running on VPS (Verified 2026-04-17)

| Service | URL | Purpose |
|---------|-----|--------|
| Coolify | coolify.vps1.ocoron.com | Deployment control plane |
| PostgreSQL | (internal) | Shared database |
| Redis | (internal) | Shared cache |
| Traefik | (internal) | Reverse proxy (managed by Coolify) |
| Gatus | status.vps1.ocoron.com | Uptime monitoring (memory storage, 30 endpoints) |
| GlitchTip | errors.vps1.ocoron.com | Error tracking (web + worker, Celery concurrency=2) |
| Netdata | netdata.vps1.ocoron.com | Real-time server metrics |
| Backrest | backup.vps1.ocoron.com | Restic-based backup UI → Backblaze B2 (deployed 2026-04-17) |
| n8n | auto.vps1.ocoron.com | Workflow automation |
| Apprise | notify.vps1.ocoron.com | Multi-channel notifications (used by n8n) |
| Grafana | monitor.vps1.ocoron.com | Dashboards (Prometheus + Loki) |
| Prometheus | (internal :9090) | Metrics scraper/storage |
| Alertmanager | (internal :9093) | Alert routing — fires to ARO Brain webhook, then Apprise fallback |
| Loki | (internal :3100) | Log aggregation |
| Promtail | (internal) | Log shipper (Docker containers → Loki) |
| cAdvisor | (internal :8080) | Container CPU/RAM/net metrics |
| node-exporter | (internal :9100) | Host-level VPS metrics |
| Browserless | browser.vps1.ocoron.com | Headless Chrome as a service for web scraping and automation |
| Authelia | auth.vps1.ocoron.com | SSO/2FA forward-auth for admin dashboards via Traefik |
| Gotenberg | pdf.vps1.ocoron.com | HTML/Office/PDF conversion API for document generation |
| MeiliSearch | search.vps1.ocoron.com | Search service with full-text and vector search capabilities |

## VPS Security Architecture (4-Layer Model)

| Layer | Target | Mechanism |
|-------|--------|-----------|
| **Iptables (DOCKER-USER)** | All Docker ports | Blocks external access to raw container ports. Only 80/443/6001/6002 allowed. |
| **Authelia** | Admin dashboards w/o native TOTP | Forward-auth 2FA for n8n, Netdata, Backrest, Apprise; + forward-auth with `^/api/` bypass for Coolify, Grafana. **Note:** GlitchTip is on full-bypass — uses app-layer django-allauth TOTP instead (canonical Sentry pattern). See `docs/LESSONS_LEARNT.md §8.13` for the decision matrix. |
| **X-Internal-Token** | API services | Machine-to-machine auth for Gotenberg, Browserless, MeiliSearch, etc. |
| **Traefik** | Public sites | Routes traffic without auth for ocoron.com, status page |

**Key files on VPS:**
- `/etc/iptables/add-docker-user-rules.sh` — iptables rules
- `/etc/systemd/system/iptables-docker-user.service` — persistence
- `/opt/authelia/config/configuration.yml` — Authelia access control policies
- `/opt/authelia/compose.yaml` — Authelia Docker Compose

## Observability & Alerting

**Compose file:** All monitoring services are Coolify-managed (migrated 2026-04-17). Local source: `specs/infrastructure/monitoring-stack.yaml` + `configs/` in Fabrik

**Notification chains:**

Prometheus alerts:
```
Prometheus (rules) → Alertmanager → Telegram (native telegram_configs)
```
> Alertmanager uses its native `telegram_configs` receiver (same bot as Apprise).
> ARO Brain (LLM alert triage) is planned; when it ships, it will be added as a
> new receiver routed BEFORE `telegram` with telegram as the fallback route.
> Apprise's stateless `/notify` endpoint does NOT accept Alertmanager's webhook
> schema — do not point AM at it.

Gatus monitoring:
```
Gatus (30 endpoints) → Apprise (http://apprise:8000/notify/alerts) → Telegram
```

Authelia 2FA codes:
```
Authelia → filesystem (/config/notification.txt) — SMTP disabled (SES port 465 failed)
```

**Alert rules** (9 total, in `configs/prometheus/rules/alerts.yml`):

| Alert | Severity | Threshold | For |
|-------|----------|-----------|-----|
| ContainerDown | critical | not seen >2min | 2m |
| ContainerHighCPU | warning | >80% | 5m |
| ContainerHighMemory | warning | >85% limit | 5m |
| ContainerOOMKilled | critical | any OOM in 5m | 0m |
| ContainerRestarting | critical | >3 in 15m | 0m |
| HostHighCPU | warning | >85% | 10m |
| HostHighMemory | critical | >90% | 5m |
| HostDiskFull | critical | >85% | 5m |
| ServiceUnhealthy | critical | target down | 2m |

**Key config files (local mirror in Fabrik `configs/`):**
- `configs/alertmanager/alertmanager.yml` — routing, receivers, inhibit rules
- `configs/prometheus/prometheus.yml` — scrape targets, alerting config
- `configs/prometheus/rules/alerts.yml` — alert rules

**Grafana password:** in `/opt/fabrik/.env` as `GRAFANA_ADMIN_PASSWORD`
**Start/stop:** Manage via Coolify dashboard — all monitoring services are Coolify-managed as of 2026-04-17

## Infrastructure Services — Ready to Deploy

Specs and configs complete. Deploy via Coolify when needed.

*No services currently ready to deploy - all planned services have been deployed.*

## Infrastructure Services — Deferred (explicit decision)

*No services currently deferred.*

## Fabrik Microservices (Custom-Built, on VPS)

| Service | Port (VPS Host) | Purpose |
|---------|-----------------|---------|
| Captcha | 18011 | Anti-Captcha solving |
| Translator | 18012 | DeepL + Azure translation |
| Proxy | 18013 | Webshare.io proxy management |
| DNS Manager (site-provisioner) | 18014 | Domain registration, DNS (Namecheap/Cloudflare), SSL, CDN, analytics (GA4/GSC), webmaster tools. Runs as `site-provisioner` in Coolify. See `docs/reference/service-contracts/site-provisioner.md` |
| File API | 18015 | File operations |
| Image Broker | 18016 | Stock image API (Pexels/Pixabay) with smart routing, scoring, caching |
| Email Gateway | 18017 | Resend + SES email sending |
| File Worker   | 8007  | Background file processing worker |

### DNS Manager — Key Capabilities

DNS Manager (`dns.vps1.ocoron.com`) is the **single gateway** for all domain/DNS/provisioning operations. Fabrik calls it via `fabrik domain` CLI or `DNSClient` driver.

| Workflow | CLI Command | Endpoint |
|----------|-------------|----------|
| Check domain availability | `fabrik domain check <domain>` | `POST /api/domains/check` |
| Get TLD pricing | — | `GET /api/domains/pricing/{tld}` |
| Register domain | `fabrik domain buy <domain>` | `POST /api/domains/register` |
| Provision website (DNS + CDN + WAF) | `fabrik domain provision <domain>` | `POST /api/cloudflare/zones/{domain}/provision` |
| Check deployment readiness | `fabrik domain ready <domain>` | `GET /api/cloudflare/zones/{domain}/ready` |
| List DNS zones | `fabrik domain zones` | `GET /api/cloudflare/zones` |

### Microservice URL Patterns

| Environment | Pattern |
|-------------|---------|
| WSL dev | `http://localhost:PORT` |
| VPS internal | `http://service-name:PORT` |
| VPS external | `https://service.vps1.ocoron.com` |

## Active Projects

Full auto-generated project list (35 projects) in `docs/BUSINESS_MODEL.md` under ``.

## 🛑 MANDATORY ORCHESTRATOR PRE-FLIGHT

Traycer MUST run these checks before generating any Plan, PRD, or Execution Spec.

1. **PORTS.md** — Assign a free port (Python 8000–8099 / Frontend 3000–3099). State it.
2. **BUSINESS_MODEL.md** — Check for duplicate/similar project. State finding.
3. **Fabrik Microservices table** — Use existing internal APIs before planning new logic. State which apply.
4. **Hardware Audit** — Confirm all Docker images support `linux/amd64`.
5. **Design System** — For any project type with a UI surface (saas-skeleton, static-site, chrome-extension, mobile-app, desktop-app, wordpress, docusaurus), read `.windsurf/rules/ocoron-design-system.md` before generating any spec or copy. Apply color tokens, typography rules, scaffold-specific adaptations, and verbal identity (forbidden language, voice, microcopy rules) to all planning output. State: "Design system read."

---

## Planning Constraints

Before creating any plan, verify:

1. **Solo developer** — no team handoff, one person executes everything
2. **x86_64 VPS** — all Docker images must support `linux/amd64`
3. **Budget-conscious** — prefer free Kilo models, free-tier APIs, self-hosted over SaaS
4. **Existing services** — check if a Fabrik microservice already solves the need before building
5. **Prebuilt containers** — check `prebuilt-app-containers.md` before writing custom code
6. **Port conflicts** — check `PORTS.md` before assigning ports
7. **Coolify deployment** — all services deploy as Docker Compose apps via Coolify
8. **No Alpine** — use `-slim-bookworm` base images only
9. **Module dependencies** — if a project needs an incomplete Fabrik module, plan module completion first. Check module status in `docs/BUSINESS_MODEL.md` before planning dependent work
10. **DNS** — site-provisioner handles Namecheap + Cloudflare + domain purchasing automatically

## Rule-Pack Enforcement

Traycer injects rule-pack guidance into agent execution queries based on project type and ticket scope. Agents do not self-select packs.

### Pack Registry

| Pack ID | File | Category |
|---------|------|----------|
| `PY_CORE` | `.windsurf/rules/10-python.md` | Core |
| `API_CONTRACTS` | `.windsurf/rules/15-api-contracts.md` | Backend |
| `TS_CORE` | `.windsurf/rules/20-typescript.md` | Core |
| `DATA_PG` | `.windsurf/rules/25-data-postgres.md` | Backend |
| `OPS` | `.windsurf/rules/30-ops.md` | Backend |
| `SECURITY` | `.windsurf/rules/35-security-auth.md` | Backend |
| `DOCUMENTATION` | `.windsurf/rules/40-documentation.md` | Backend |
| `DOCUSAURUS` | `.windsurf/rules/42-docusaurus.md` | Platform |
| `TESTING` | `.windsurf/rules/45-testing-strategy.md` | Backend |
| `CODE_REVIEW` | `.windsurf/rules/50-code-review.md` | Backend |
| `OBSERVABILITY` | `.windsurf/rules/55-observability.md` | Backend |
| `SAAS_UI` | `.windsurf/rules/60-saas-ui.md` | Core |
| `WORDPRESS` | `.windsurf/rules/62-wordpress.md` | Platform |
| `RAG_SEARCH` | `.windsurf/rules/65-rag-search.md` | Domain |
| `CHROME_MV3` | `.windsurf/rules/70-chrome-ext.md` | Core |
| `WORKERS` | `.windsurf/rules/75-workers-jobs.md` | Backend |
| `MOBILE_UI` | `.windsurf/rules/80-mobile.md` | Core |
| `PAYMENTS` | `.windsurf/rules/85-payments-billing.md` | Domain |
| `AUTOMATION` | `.windsurf/rules/90-automation.md` | Backend |
| `MULTI_TENANT` | `.windsurf/rules/95-multi-tenant-saas.md` | Domain |
| `CROSS_CUTTING` | `.windsurf/rules/CROSS_CUTTING_REQUIREMENTS.md` | Cross-cutting |
| `DESIGN_SYSTEM` | `.windsurf/rules/ocoron-design-system.md` | Cross-cutting |

### Project Type → Default Packs

| Project Type | Default Packs |
|--------------|---------------|
| `python-api` | `PY_CORE` |
| `node-api` | — |
| `saas-skeleton` | `TS_CORE`, `SAAS_UI` |
| `chrome-extension` | `PY_CORE`, `TS_CORE`, `CHROME_MV3` |
| `mobile-app` | `TS_CORE`, `MOBILE_UI` |
| `desktop-app` | `TS_CORE` |
| `file-api` | — |
| `file-worker` | `PY_CORE`, `WORKERS` |
| `wordpress` | `WORDPRESS` |
| `docusaurus` | `DOCUSAURUS` |
| `static-site` | `TS_CORE`, `SAAS_UI` |

> `node-api` and `file-api` scaffolds are currently JavaScript-based. Do not inject `TS_CORE` or `PY_CORE` unless a specific project has actually adopted TypeScript or Python.
> `chrome-extension` includes `PY_CORE` because the backend companion service is Python.
> `docusaurus` is for dev/team-authored content (docs, API reference, knowledge base). `wordpress` is for client/non-technical-authored content (marketing, e-commerce). `static-site` is for landing pages and one-pagers you control fully. See `docs/reference/scaffold-type-decision-guide.md`.

### Feature-Based Overlay Packs

| Pack | Inject When Ticket Involves |
|------|-----------------------------|
| `API_CONTRACTS` | API endpoints, routes, request/response schemas |
| `DATA_PG` | Database queries, migrations, schema changes |
| `SECURITY` | Auth, sessions, CORS, secrets, CSP |
| `TESTING` | Always — universal overlay, injected for every ticket |
| `OBSERVABILITY` | Health endpoints, logging, monitoring |
| `RAG_SEARCH` | Embeddings, retrieval, vector search, LLM context |
| `PAYMENTS` | Paddle, subscriptions, billing, entitlements |
| `MULTI_TENANT` | Tenant isolation, RLS, tenant-scoped queries |

### Enforcement Policy

1. Traycer reads `project.yaml` type → looks up default packs → adds overlay packs based on ticket scope keywords.
2. Injection format into execution query:
   ```
   ## Rule Packs Active
   [PACK_ID] <file path>
   - <rule line 1>
   - <rule line 2>
   (max 6 lines per pack)
   ```
3. Total injected guidance must not exceed **40 lines**. If cap exceeded, drop feature overlays first, keep project-type defaults.
4. Injection is performed by Traycer at query-construction time. Agents do not self-select packs.
5. `AGENTS-compact.md` carries the completion contract and cross-cutting rules for Kilo CLI agents. Stays under 60 lines.
6. `final_gate.py` handles objective checks only; packs are enforced via injection, not gate.

## Environment Constraints

- **Runtime:** WSL (Ubuntu). Linux paths and commands only. Never Windows tooling.
- **Scaffold:** Fixed structure — do not reorganize, flatten, or add top-level directories.
- **pip:** Never bare `pip install`. Always `/opt/<project>/.venv/bin/pip install`
- **Env vars:** Never hardcode. Always `os.getenv('KEY', 'default')`
- **Base images:** `python:<current-stable>-slim-bookworm` / `node:<current-LTS>-bookworm-slim`. Never Alpine.
- **Deployment:** Linux VPS via Coolify. amd64-compatible builds required.
- **Ports:** Python 8000–8099 / Frontend 3000–3099. Register new ports in `PORTS.md`.
- **Conflicts:** If task contradicts project state — stop and return to Traycer. Do not silently overwrite.

## Code Patterns

### Python / FastAPI
```python
# Config — always function-level, never class/module-level
def get_db_url() -> str:
    return f"postgresql://{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/db"

# Health — always test real dependencies
@app.get("/health")
async def health():
    await db.execute("SELECT 1")
    return {"status": "ok", "db": "connected"}

# Temp files — never /tmp/
TEMP_DIR = Path(__file__).parent.parent / ".tmp"
```

### Logging (Pre-Scaffolded — DO NOT Recreate)

```python
# Python — already at src/{package}/logger.py
from {package}.logger import get_logger
logger = get_logger(__name__)
logger.info("user_created", user_id=uid)
# NEVER use print() — logger is already there
```

```javascript
// Node — already at src/logger.js
const logger = require('./logger');
logger.info({ event: 'user_created', user_id: uid });
// NEVER use console.log() — logger is already there
```

### Docker

```dockerfile
FROM python:<current-stable>-slim-bookworm
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1
```

### compose.yaml

```yaml
networks:
  coolify:
    external: true
environment:
  - DB_HOST=postgres-main   # service name, never localhost
```

## Documentation Rules

- **CHANGELOG.md:** Entry required for every code change. Format: `### Added/Changed/Fixed — Title (YYYY-MM-DD)`
- **README.md features table:** Every new feature added with ✅/🚧/❌ status
- **New `.md` files:** Blocked outside allowlist. Allowed: root files, scaffold docs, `docs/development/plans/YYYY-MM-DD-plan-<n>.md`, `docs/reference/**/*.md`, `docs/archive/**`
- **`.env.example`:** Authoritative variable reference. `docs/CONFIGURATION.md` is a guide only.

## Sensitive Data Protection

Before modifying any credentials file (`.env`, `*.key`, `*.pem`, `secrets/`, `.ssh/`):

```bash
cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
```

**Forbidden without dry-run:** Destructive scripts on production data.
**Forbidden without full diff approval:** Any credentials change.

## Quality Gates

| Gate | Script | Purpose |
|------|--------|---------|
| Kilo Review | `scripts/kilo_code_review.py` | Optional: AI-powered code review for high-risk manual audits |
| Documentator | `scripts/kilo_docs_enforcer.py` | Optional: AI documentation generation for bulk doc work |
| Final Gate (Tier 1 — lean) | `scripts/final_gate.py --lean` | Default: showstoppers during coding |
| Final Gate (Tier 2 — full) | `scripts/final_gate.py` | At milestone closure: full quality checks |
| Final Gate (Tier 3 — systemic) | `scripts/final_gate.py --systemic` | On-demand: repo health |

## Scaffold Types

**Canonical entry point (Phase 4k, 2026-04-19):** `fabrik scaffold <name> --type <type>`. This creates the full project tree AND emits `specs/services/<name>.yaml` with a populated `shape:` block per `templates/<type>/defaults.yaml`. The `shape:` block is what drives which infrastructure registrars run during `fabrik apply` (postgres / gatus / backrest / glitchtip / grafana / authelia / meilisearch). `fabrik new` is deprecated (hidden from `--help`, prints a warning, scheduled for removal one release after next).

| Type | Template | Stack | shape.kind | shape flags (true only) |
|------|----------|-------|------------|------------------------|
| python-api | templates/scaffold/ | FastAPI + Uvicorn + Docker | service | is_public |
| saas-skeleton | templates/saas-skeleton/ | Next.js 14 + TypeScript + Tailwind | service | is_public, has_persistent_data, needs_database |
| node-api | templates/node-api/ | Node.js API + Docker | service | is_public |
| file-api | templates/file-api/ | File operations API | service | is_public, has_persistent_data |
| file-worker | templates/file-worker/ | Background file worker | worker | has_persistent_data |
| wordpress | templates/wordpress/ | WordPress + WP-CLI | wordpress | is_public, has_persistent_data, needs_database |
| docusaurus | templates/docusaurus/ | Documentation site (Docusaurus framework) | static | is_public |
| chrome-extension | templates/chrome-extension/ | Chrome extension + Python backend | static | (none — packaged as CRX, not VPS-deployed) |
| mobile-app | templates/mobile-app/ | React Native app | static | (none — distributed via app stores) |
| desktop-app | templates/desktop-app/ | Electron app | static | (none — distributed as installer binary) |
| static-site | templates/saas-skeleton/ | Next.js / static HTML (landing pages, portfolios) | static | is_public |

> Each scaffold type propagates `.windsurfrules`, `.windsurf/rules/`, and `.windsurf/workflows/` to generated projects automatically.
>
> **Authoritative shape matrix:** `src/fabrik/spec_loader.py::Shape` docstring. Change it there, then run the full scaffold suite — a divergence between the docstring and `templates/<type>/defaults.yaml` is a failing test (`tests/test_spec_generator.py`).

## Reference Documents

| Document | Path | Use When |
|----------|------|----------|
| Project Portfolio | docs/BUSINESS_MODEL.md | Full project list with statuses |
| AI Taxonomy | docs/reference/AI_TAXONOMY.md | Selecting AI tools/models |
| Local LLM | docs/reference/LOCAL_LLM_INFRASTRUCTURE.md | Ollama setup, model assignments |
| Stack Decision Guide | docs/reference/technology-stack-decision-guide.md | Choosing tech stack for new project |
| Prebuilt Containers | docs/reference/prebuilt-app-containers.md | Ready-made Docker solutions |
| Database Strategy | docs/reference/DATABASE_STRATEGY.md | Database, migration, vector storage |
| Owner Profile | docs/owner_ozgur_basak.md | Owner background, goals |
| Port Allocations | PORTS.md | Assigning ports to new services |
| Scaffold Decision Guide | docs/reference/scaffold-type-decision-guide.md | Choosing WordPress vs Docusaurus vs static-site |
| SaaS UI Patterns | docs/reference/Modern GUI Approaches for a Lean, Fast, Effective, Low-Confusion SaaS Web App.md | Planning SaaS frontend |
| Chrome Extension UI | docs/reference/Modern GUI Approaches for Chrome Extensions.md | Planning Chrome extensions |
| Mobile UI | docs/reference/Modern Mobile GUI Approaches for Android and iOS.md | Planning mobile apps |
| Ocoron Design System | .windsurf/rules/ocoron-design-system.md | Visual + verbal identity for all UI projects — color tokens, typography, component patterns, brand voice |
