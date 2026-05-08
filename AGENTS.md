# AGENTS.md — Fabrik Identity & Knowledge (Traycer Only)

**Last Updated:** 2026-05-03
**Read by:** Traycer only (auto-loaded every interaction)
**Coding agents:** Read `AGENTS-compact.md` via `opencode.json`

> For all development work, use the **Fabrik Development Workflow**.
> Owner drops pre-research at `docs/development/plans/00-research.md` after external research with ChatGPT/Claude/Gemini.

---

## File Ownership

Traycer's planning context lives in `AGENTS.md`. Rule enforcement, agent contracts, and workflow definitions live elsewhere and are out of Traycer's edit scope.

| File / Path | Owner | Traycer May Edit? |
|---|---|---|
| `AGENTS.md` | Traycer (planner context) | ✅ Yes |
| `AGENTS-compact.md` | Kilo CLI (via `opencode.json`) | ❌ No |
| `.windsurfrules` | Windsurf Cascade | ❌ No |
| `.windsurf/rules/**` | All agents (auto-loaded packs) | ❌ No |
| `.windsurf/workflows/**` | Cascade workflow definitions | ❌ No |
| `docs/traycer/traycer-managed-development-workflow/**` | Traycer workflow definitions | ✅ Yes |
| Per-project `CLAUDE.md`, per-project `AGENTS-compact.md`, per-project `project.yaml` | Project-scoped (out of Fabrik-monorepo scope) | ❌ No |

## Owner & Working Style

- **Solo developer** — Özgür Başak, 46, Turkish electronics engineer & entrepreneur
- **Capacity:** ~50 focused hours/week
- **Budget:** Limited — prefer free/cheap but good, fast tools, maximize ROI
- **Philosophy:** Fast but good. Ship fast, iterate, automate. No over-engineering.
- **Full profile:** `docs/owner_ozgur_basak.md`

## Development Environment

- **Dev machine:** WSL (Ubuntu 24.04) on Windows
- **IDE:** Windsurf (Cascade AI agents for interactive work)
- **Coding agents:** Windsurf Cascade (manual/interactive) · Kilo CLI (YOLO) · Local LLM agents
- **VPS:** x86_64 (amd64) Ubuntu at 172.93.160.197 — AMD EPYC-Genoa, 6 vCPU, 12 GB RAM
- **Deployment:** Coolify on VPS (Docker Compose). Two CLI entry points: `fabrik deploy` (project.yaml-driven, modern) and `fabrik apply` (spec-driven, legacy). Both route through the orchestrator pipeline. Full reference in `docs/DEPLOYMENT.md`.
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
| Notifications | Apprise (self-hosted) | Direct API for single-channel |
| Object storage | Backblaze B2 (via Backrest, deployed 2026-04-17) | MinIO for self-hosted S3-compatible when needed |

## Infrastructure Services — Running on VPS

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
| **X-Internal-Token** | API services | Machine-to-machine auth for all Fabrik API services. Header: `X-Internal-Token`. Env: `SERVICE_INTERNAL_SECRET_KEY` (shared across all services). Module: `internal_auth.py` in each service's `app/` or `src/`. |
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

Full auto-generated project list at `docs/BUSINESS_MODEL.md` § Project Portfolio. Source of truth: `data/projects.yaml` (auto-synced by `scripts/sync_projects.py`).

## 🛑 MANDATORY ORCHESTRATOR PRE-FLIGHT

Traycer MUST run these checks before generating any Plan, PRD, or Execution Spec.

1. **PORTS.md** — Assign a free port (Python 8000–8099 / Frontend 3000–3099). State it.
2. **BUSINESS_MODEL.md** — Check for duplicate/similar project. State finding.
3. **Fabrik Microservices table** — Use existing internal APIs before planning new logic. State which apply.
4. **Hardware Audit** — Confirm all Docker images support `linux/amd64`.
5. **Design System** — For any project type with a UI surface (saas-skeleton, static-site, chrome-extension, mobile-app, desktop-app, wordpress, docusaurus), read `.windsurf/rules/ocoron-design-system.md` before generating any spec or copy. Apply color tokens, typography rules, scaffold-specific adaptations, and verbal identity (forbidden language, voice, microcopy rules) to all planning output. State: "Design system read."
6. **External Knowledge Verification** — When the plan touches a third-party API/SDK/vendor product (Coolify, Paddle, Traefik, Authelia, Stripe, Supabase, Cloudflare, n8n, etc.), verify the current contract against live docs BEFORE writing the ticket spec. Order: (a) search `docs/`, `docs/reference/`, `AFCL.md`, `docs/LESSONS_LEARNT.md` for prior coverage; (b) if absent, fetch the vendor's official docs URL and cite it in the ticket's `References:` field; (c) pass cited URLs to executing agents in `Final Gate Instruction` or `Implementation Notes` so they don't re-research what you already verified. If you cannot verify within 3 search calls, mark the ticket `BLOCKED: external-research-needed` and stop. Skip for: stdlib, language syntax, internal Fabrik conventions.

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

## Authelia Config Changes
**Never SIGHUP Authelia — it exits.** After any edit to `configuration.yml`:
```bash
ssh vps "sudo docker restart authelia-hks48k8sg8o4co4co08co00o"
```

## Gatus Monitoring — Stable DNS Rule

**Never use UUID container names in Gatus config.** Coolify single-image Applications assign `<app-uuid>-<timestamp>` as the container name — the timestamp changes on every redeploy, silently breaking monitoring.

### After deploying a new single-image Application:
1. Add stable alias to compose: `networks.coolify.aliases` in `/data/coolify/applications/<uuid>/docker-compose.yaml`
2. Apply live: `docker network disconnect coolify <uuid-name> && docker network connect --alias <stable> --alias <uuid-name> coolify <uuid-name>`
3. Register in `scripts/vps_apply_limits.sh` `apply_alias` section (reboot persistence)
4. Gatus config: use `tcp://<stable-name>:<port>` — never the UUID form

### Registered stable aliases (as of 2026-05-07)
| Stable name | Container | Gatus URL |
|---|---|---|
| `browserless` | `vckgs8c00o40o884k48cgow8-220643454460` | `tcp://browserless:3000` |
| `gotenberg` | `e04k4sco44ow04ccc0o0k00k-151256201601` | `tcp://gotenberg:3000` |
| `meilisearch` | `bs0wo48k4gwo440gcowscoc8-150802066640` | `tcp://meilisearch:7700` |
| `glitchtip-web` | `glitchtip-web-z00kkck8c8cwo800kk440csk` | `tcp://glitchtip-web:8000` |

Coolify Service stacks (multi-container) use `container_name: <service>-<coolify-service-uuid>` which IS stable (UUID = Coolify service ID, doesn't change on redeploy).

## Post-Deploy Checklist (Every New Service)

Run these 4 steps every time a new container is deployed via Coolify:

**A — Network:** Confirm container is on the `coolify` Docker network (Coolify default ✅). Never expose raw ports to host — let Traefik route.

**B — Traefik Labels:** Scaffold emits correct labels automatically. Verify:
- Admin UI → `authelia-forward@docker,gzip@docker` middleware
- API service → `gzip@docker` middleware (auth is app-layer X-Internal-Token)
- Public service → no auth middleware

**C — Env Vars in Coolify:** For every new API service:
1. Add `SERVICE_INTERNAL_SECRET_KEY` — copy value from `/opt/fabrik/.env`
2. Add `DATABASE_URL` using `postgres-main:5432` (never `localhost`)
3. Add `REDIS_URL` using `redis-main:6379` (never `localhost`)

**D — Health Check:** Verify `/health` endpoint returns 200. It is bypassed in Authelia automatically via `*.vps1.ocoron.com` → `/health` rule. Default healthcheck interval is 30s — set to 60s in Coolify for stable services.

## M2M Authentication — Implementation Rules

All Fabrik API services use `X-Internal-Token`. **Never** write inline auth logic.

### Python (FastAPI)
```python
# File: app/internal_auth.py or src/internal_auth.py (scaffold emits this automatically)
from app.internal_auth import require_internal_token  # if uvicorn app.main:app
# OR
from internal_auth import require_internal_token  # if uvicorn api:app (root-level)

# In router:
router = APIRouter(dependencies=[Depends(require_internal_token)])
```

### Node.js (Fastify)
```javascript
// File: src/internal_auth.js (scaffold emits this automatically)
import { requireInternalToken } from './internal_auth.js';
fastify.addHook('preHandler', requireInternalToken);
```

### Calling a service from another service
```python
import os, httpx
headers = {"X-Internal-Token": os.environ["SERVICE_INTERNAL_SECRET_KEY"]}
resp = httpx.get("https://translator.vps1.ocoron.com/api/translate", headers=headers)
```

**Scaffold emits (auto, no manual action):**
- `internal_auth.py` — M2M auth module
- `metrics.py` — Prometheus business metrics (REQUEST_COUNT, ERROR_COUNT, ACTIVE_JOBS)
- `/metrics` endpoint — mounted in `main.py`, Authelia-bypassed
- `glitchtip_init.py` / `glitchtip_init.js` — Sentry SDK init pointed at GlitchTip; no-op if `GLITCHTIP_DSN` env unset. Wired in `main.py` BEFORE app construction.

**Key facts:**
- One shared secret: `SERVICE_INTERNAL_SECRET_KEY` in `/opt/fabrik/.env`
- Same key pushed to Coolify env for every deployed service
- Validation is constant-time (`hmac.compare_digest` / `timingSafeEqual`)
- Health check `/health` is NOT protected (Authelia bypass rule covers it)
- `file-api` uses Supabase Bearer JWT instead (user auth, different pattern)
- `site-provisioner` uses Traefik IP allowlist (no app-level auth)

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

Canonical patterns live in the rule packs:

- Python / FastAPI / config / temp files → `.windsurf/rules/10-python.md`
- Pre-scaffolded logging (Python / Node / Next.js) → `.windsurf/rules/55-observability.md` § Pre-Scaffolded Logging
- Dockerfile / `compose.yaml` / Coolify network → `.windsurf/rules/30-ops.md`

## Documentation Rules

See `.windsurf/rules/40-documentation.md` (CHANGELOG, README features, plans, AUTO-GENERATED blocks, `.env.example`, new-`.md`-file allowlist, writing style).

## Sensitive Data Protection

See `.windsurf/rules/CROSS_CUTTING_REQUIREMENTS.md` § Sensitive Data Protection and § Password Policy. (Auto-loaded `always_on` — applies to every Cascade interaction including edits to `.env`, `*.key`, `*.pem`, `secrets/`, `.ssh/`.)

## Quality Gates

| Gate | Script | Purpose |
|------|--------|---------|
| Kilo Review | `scripts/kilo_code_review.py` | Optional: AI-powered code review for high-risk manual audits |
| Documentator | `scripts/kilo_docs_enforcer.py` | Optional: AI documentation generation for bulk doc work |
| Final Gate (Tier 1 — lean) | `scripts/final_gate.py --lean` | Default: showstoppers during coding |
| Final Gate (Tier 2 — full) | `scripts/final_gate.py` | At milestone closure: full quality checks |
| Final Gate (Tier 3 — systemic) | `scripts/final_gate.py --systemic` | On-demand: repo health |

## Scaffold Types

**Canonical entry point (Phase 4k, 2026-04-19):** `fabrik scaffold <name> --type <type>`. This creates the full project tree AND emits `specs/services/<name>.yaml` with a populated `shape:` block per `templates/<type>/defaults.yaml`. The `shape:` block is what drives which infrastructure registrars run during `fabrik apply` (postgres / gatus / backrest / glitchtip / grafana / authelia / meilisearch). `fabrik new` is deprecated (hidden from `--help`, prints a warning; scheduled for removal on 2026-05-31).

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
>
> **Registrar applicability matrix:** `src/fabrik/orchestrator/infrastructure.py` docstring + `resolve_applicability()`. Source of truth for which of (postgres / gatus / backrest / glitchtip / grafana / authelia / meilisearch) runs for a given `shape:` block.

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
| Cascade Models | docs/reference/windsurf/cascade-models.md | Selecting Windsurf Cascade model tier |
| Deployment Guide | docs/DEPLOYMENT.md | Full deployment / `fabrik apply` / `fabrik deploy` reference |
| Kilo Agent Naming | docs/reference/kilo/KILO_AGENT_NAMING.md | Naming new Kilo CLI agents |
| Kilo Agent Registry | scripts/kilo_47_agents_final.json | Authoritative agent selection list |
| Lessons Learnt | docs/LESSONS_LEARNT.md | Past incidents, decisions, anti-patterns |
| Traycer Workflow | docs/traycer/traycer-managed-development-workflow/ | Trigger / brief / plan / breakdown / execute commands |
