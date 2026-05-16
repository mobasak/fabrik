# AGENTS.md — Fabrik Identity & Knowledge (Traycer)

**Last Updated:** 2026-05-16
**Read by:** Traycer only — for ticket planning. Traycer must know the entire Fabrik infrastructure to plan correctly.
**Coding agents:** Claude Code reads `CLAUDE.md`; Windsurf Cascade reads `.windsurfrules`; Kilo CLI reads `AGENTS-compact.md` + `KILO_CLI_RULES.md` (via `opencode.json` `instructions:` array).

---

## Workflow (mandatory)

For every ticket: follow `docs/traycer/traycer-managed-development-workflow/` — `trigger` → `brief` → `plan` → `breakdown` → `execute`. The human-readable reference copy lives at `docs/traycer/fabrik-workflow.md`.

**Pre-research drop point:** `docs/development/plans/00-research.md` (the owner drops external research from ChatGPT/Claude/Gemini here before planning).

## File Ownership

Traycer plans against `AGENTS.md`. Agent-execution contracts, rule packs, and workflow definitions live elsewhere and are out of Traycer's edit scope.

| File / Path | Owner | Traycer May Edit? |
|---|---|---|
| `AGENTS.md` | Traycer (this file — planner context) | ✅ Yes |
| `docs/traycer/traycer-managed-development-workflow/**` | Traycer (workflow definitions) | ✅ Yes |
| `docs/traycer/fabrik-workflow.md` | Reference copy (do not diverge from workflow definitions) | ✅ Yes |
| `CLAUDE.md` | Claude Code bootstrap | ❌ No |
| `.windsurfrules` | Windsurf Cascade bootstrap | ❌ No |
| `AGENTS-compact.md` | Kilo CLI bootstrap (via `opencode.json`) | ❌ No |
| `.windsurf/rules/**` | Topic rule packs (shared; Cascade auto-loads via frontmatter, Claude Code and Kilo read on demand) | ❌ No |
| `.windsurf/workflows/**` | Cascade slash-command workflows | ❌ No |
| Per-project `CLAUDE.md`, `AGENTS-compact.md`, `project.yaml` | Project-scoped (out of Fabrik-monorepo scope) | ❌ No |

## Owner & Working Style

- **Solo developer** — Özgür Başak, 46, Turkish electronics engineer & entrepreneur. Full profile: `docs/owner_ozgur_basak.md`.
- **Capacity:** ~50 focused h/week.
- **Budget:** Prefer free/cheap-but-good fast tools; maximize ROI.
- **Philosophy:** Fast but pro. Ship → iterate → automate. No over-engineering.

## Development Environment

- **Dev:** WSL Ubuntu 24.04 on Windows. IDE: Windsurf (Cascade) + Kilo CLI + Claude Code + Local LLM agents.
- **VPS:** x86_64 (amd64) Ubuntu, 172.93.160.197 — AMD EPYC-Genoa, 6 vCPU, 12 GB RAM.
- **Deploy:** Coolify on VPS (Docker Compose). Entry points: `fabrik deploy` (project.yaml-driven, modern) and `fabrik apply` (spec-driven, legacy). Both route through the orchestrator pipeline. Full reference: `docs/DEPLOYMENT.md`.
- **DB:** PostgreSQL on VPS (default) · Supabase (managed auth / realtime / pgvector when needed).
- **Proxy:** Traefik (Coolify-managed) + Let's Encrypt.
- **Domains:** `*.vps1.ocoron.com` via site-provisioner (Namecheap + Cloudflare + auto-purchase). Implementation: `docs/reference/service-contracts/site-provisioner.md`.
- **Monitoring:** Gatus · Netdata · Grafana · Prometheus · Alertmanager · Loki (all Coolify-managed since 2026-04-17).

### Local LLM Agents

Ollama on localhost:11434. Full setup: `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md`.

| Agent | Hardware | Memory Usage | Speed | Stability |
|---|---|---|---|---|
| `fabrik-coder` | hybrid-cpu | ~19 GB (8 GB VRAM + 11 GB RAM) | Moderate (~15–25 tok/s) | Stable |
| `fabrik-reviewer` | cpu | ~42 GB RAM | Slow (~8–12 tok/s) | High memory pressure ⚠️ |
| `fabrik-fixer` | hybrid-gpu | ~9 GB (8 GB VRAM + 1 GB RAM) | Fast (~40–60 tok/s) | Stable |
| `fabrik-docs` | gpu | ~5 GB VRAM | Instant (~80–100 tok/s) | Rock solid |

## File & Folder Naming

kebab-case. Exceptions: `README.md`, `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `AGENTS.md`, `AGENTS-compact.md`, `LESSONS_LEARNT.md`, `CLAUDE.md`, `Makefile`, `Dockerfile`; Python packages use snake_case per PEP 8; auto-generated files (migrations, lock files, `__pycache__/`, `__init__.py`); dotfiles and dotdirs. Documentation files follow kebab-case too.

## Tech Stack Defaults

| Layer | Default | Deviate When |
|---|---|---|
| Backend | Python + FastAPI + Uvicorn | Node.js for web-adjacent workers |
| Frontend | Next.js 14 + TypeScript + Tailwind | — always use this |
| Database | PostgreSQL 16 (VPS, Coolify-managed) | Supabase for managed auth / realtime / pgvector |
| Background jobs | PostgreSQL jobs table + worker | Redis queue for high throughput |
| AI/LLM | Kilo CLI free tiers → OpenAI / Anthropic APIs | Local Ollama for offline/free |
| Local LLM | Ollama (localhost:11434) | See `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` |
| Base images | `python:<current-stable>-slim-bookworm`, `node:<current-LTS>-bookworm-slim` | **Never** Alpine |
| PDF | Gotenberg (self-hosted) | WeasyPrint for simple cases |
| Search | MeiliSearch (self-hosted) | PostgreSQL FTS for simple cases |
| Notifications | Apprise (self-hosted) | Direct API for single-channel |
| Object storage | Backblaze B2 via Backrest (deployed 2026-04-17) | MinIO for self-hosted S3-compatible |

## Infrastructure Services — Running on VPS

| Service | URL | Purpose |
|---|---|---|
| Coolify | coolify.vps1.ocoron.com | Deployment control plane |
| PostgreSQL | (internal) | Shared database |
| Redis | (internal) | Shared cache |
| Traefik | (internal) | Reverse proxy (managed by Coolify) |
| Gatus | status.vps1.ocoron.com | Uptime monitoring (memory storage, 30 endpoints) |
| GlitchTip | errors.vps1.ocoron.com | Error tracking (web + worker, Celery concurrency=2) |
| Netdata | netdata.vps1.ocoron.com | Real-time server metrics |
| Backrest | backup.vps1.ocoron.com | Restic-based backup UI → Backblaze B2 |
| n8n | auto.vps1.ocoron.com | Workflow automation |
| Apprise | notify.vps1.ocoron.com | Multi-channel notifications (used by n8n) |
| Grafana | monitor.vps1.ocoron.com | Dashboards (Prometheus + Loki) |
| Prometheus | (internal :9090) | Metrics scraper / storage |
| Alertmanager | (internal :9093) | Alert routing → Telegram (native `telegram_configs`) |
| Loki | (internal :3100) | Log aggregation |
| Promtail | (internal) | Log shipper (Docker → Loki) |
| cAdvisor | (internal :8080) | Container CPU / RAM / network metrics |
| node-exporter | (internal :9100) | Host-level VPS metrics |
| Browserless | browser.vps1.ocoron.com | Headless Chrome for scraping / automation |
| Authelia | auth.vps1.ocoron.com | SSO / 2FA forward-auth for admin dashboards |
| Gotenberg | pdf.vps1.ocoron.com | HTML / Office → PDF conversion |
| MeiliSearch | search.vps1.ocoron.com | Full-text + vector search |

### Resource limits on Coolify-deployed services

All 27 Coolify-deployed services (8 Applications + 12 Services + 3 image-based Applications + Coolify control plane) carry explicit `deploy.resources.limits.memory` (and `cpus`) declared in their compose so Docker enforces caps across redeploys (F5 fix, 2026-05-16). Coolify v4.0.0-beta.459's `limits_memory` UI field does NOT propagate to compose for `build_pack=dockercompose` apps or for Services — both paths require the explicit `deploy:` block. New deployments inherit this from the scaffolder; backfill for existing deployments lives in `scripts/inject_deploy_resources.py` (repos) and `scripts/coolify_services_f5.py` (services).

## Observability & Alerting

All monitoring services are Coolify-managed (migrated 2026-04-17). Local source: `specs/infrastructure/monitoring-stack.yaml` + `configs/` in Fabrik repo.

### Notification chains

```
Prometheus (rules) → Alertmanager → Telegram (native telegram_configs)
```

> Alertmanager uses its native `telegram_configs` receiver (same bot as Apprise).
> ARO Brain (LLM alert triage) is planned; when it ships, it will be added as a new
> receiver routed BEFORE `telegram` with telegram as the fallback route.
> Apprise's stateless `/notify` endpoint does NOT accept Alertmanager's webhook
> schema — do not point AM at it.

```
Gatus (30 endpoints) → Apprise (http://apprise:8000/notify/alerts) → Telegram
```

```
Authelia 2FA codes → filesystem (/config/notification.txt)
```

> Authelia SMTP is disabled (SES port 465 failed). Codes are written to a file; users grab them via `docker exec`.

### Alert Rules (10 total)

Source: `configs/prometheus/rules/alerts.yml`.

| Alert | Severity | Threshold | For |
|---|---|---|---|
| ContainerDown | critical | not seen >2min | 2m |
| ContainerHighCPU | warning | >80% | 5m |
| ContainerHighMemory | warning | >85% of container's own limit | 5m |
| ContainerMemoryHighOfHost | warning | >15% of VPS total RAM (catches containers without a limit) | 10m |
| ContainerOOMKilled | critical | any OOM in 5m | 0m |
| ContainerRestarting | critical | >3 in 15m | 0m |
| HostHighCPU | warning | >85% | 10m |
| HostHighMemory | critical | >90% | 5m |
| HostDiskFull | critical | >85% | 5m |
| ServiceUnhealthy | critical | target down | 2m |

### Key config files (local mirror in Fabrik `configs/`)

- `configs/alertmanager/alertmanager.yml` — routing, receivers, inhibit rules
- `configs/prometheus/prometheus.yml` — scrape targets, alerting config
- `configs/prometheus/rules/alerts.yml` — alert rules
- `configs/grafana/dashboards/*.json` — provisioned dashboards
- `configs/grafana/provisioning/` — bind-mounted to Coolify Grafana

**Grafana admin password:** `/opt/fabrik/.env` as `GRAFANA_ADMIN_PASSWORD`. Manage start/stop via Coolify dashboard.

## VPS Security (4-Layer Model)

| Layer | Target | Mechanism |
|---|---|---|
| **iptables DOCKER-USER** | All Docker ports | Blocks external access to raw container ports. Only 80/443/6001/6002 allowed. |
| **Authelia** | Admin dashboards w/o native TOTP | Forward-auth 2FA for n8n, Netdata, Backrest, Apprise; + forward-auth with `^/api/` bypass for Coolify, Grafana. **Note:** GlitchTip is on full-bypass — uses django-allauth app-layer TOTP (canonical Sentry pattern). Decision matrix: `docs/LESSONS_LEARNT.md §8.13`. |
| **X-Internal-Token** | API services | M2M auth via `internal_auth.py` + shared `SERVICE_INTERNAL_SECRET_KEY` in `/opt/fabrik/.env`. Same key pushed to Coolify env for every deployed service. Validation is constant-time (`hmac.compare_digest`). Implementation pack: `.windsurf/rules/35-security-auth.md`. |
| **Traefik** | Public sites | Routes traffic without auth for `ocoron.com`, `status.vps1.ocoron.com`. |

### Key security files on VPS

- `/etc/iptables/add-docker-user-rules.sh` — iptables rules
- `/etc/systemd/system/iptables-docker-user.service` — persistence
- `/opt/authelia/config/configuration.yml` — Authelia access control policies
- `/opt/authelia/compose.yaml` — Authelia Docker Compose
- `/opt/fabrik/.env` — `SERVICE_INTERNAL_SECRET_KEY`, `GRAFANA_ADMIN_PASSWORD`, etc.

**Authelia config changes:** Authelia exits on SIGHUP (no hot-reload). Restart procedure (discover container name, then restart): `.windsurf/rules/30-ops.md` § Authelia SSO. **Never** protect `/health` — Authelia bypass `*.vps1.ocoron.com → /health` is global.

### Exceptions to the canonical M2M pattern

- `file-api` uses Supabase Bearer JWT (user auth, different pattern).
- `site-provisioner` uses Traefik IP allowlist (no app-level auth).

## Fabrik Microservices (Custom-Built, on VPS)

| Service | Port (VPS Host) | Purpose |
|---|---|---|
| Captcha | 18011 | Anti-Captcha solving |
| Translator | 18012 | DeepL + Azure translation |
| Proxy | 18013 | Webshare.io proxy management |
| DNS Manager (site-provisioner) | 18014 | Domain registration, DNS (Namecheap / Cloudflare), SSL, CDN, analytics (GA4 / GSC), webmaster tools |
| File API | 18015 | File operations |
| Image Broker | 18016 | Stock image API (Pexels / Pixabay) with smart routing, scoring, caching |
| Email Gateway | 18017 | Resend + SES email sending |
| File Worker | 8007 | Background file processing worker |

### DNS Manager — Key Capabilities

DNS Manager (`dns.vps1.ocoron.com`) is the single gateway for all domain / DNS / provisioning operations. Fabrik calls it via the `fabrik domain` CLI or the `DNSClient` driver.

| Workflow | CLI | Endpoint |
|---|---|---|
| Check domain availability | `fabrik domain check <domain>` | `POST /api/domains/check` |
| Get TLD pricing | — | `GET /api/domains/pricing/{tld}` |
| Register domain | `fabrik domain buy <domain>` | `POST /api/domains/register` |
| Provision website (DNS + CDN + WAF) | `fabrik domain provision <domain>` | `POST /api/cloudflare/zones/{domain}/provision` |
| Check deployment readiness | `fabrik domain ready <domain>` | `GET /api/cloudflare/zones/{domain}/ready` |
| List DNS zones | `fabrik domain zones` | `GET /api/cloudflare/zones` |

Full service contract: `docs/reference/service-contracts/site-provisioner.md`.

### Microservice URL Patterns

| Environment | Pattern |
|---|---|
| WSL dev | `http://localhost:PORT` |
| VPS internal | `http://service-name:PORT` |
| VPS external | `https://service.vps1.ocoron.com` |

## Coolify Stable DNS Aliases (Single-Image Applications)

Coolify single-image Applications use container names of the form `<app-uuid>-<timestamp>`. The timestamp changes on every redeploy — Gatus / inter-service URLs keyed on the UUID name break silently. The fix: install a stable alias on the `coolify` Docker network, persisted via compose + `scripts/vps_apply_limits.sh`. Install procedure: `.windsurf/rules/30-ops.md` § Authelia SSO + `docs/reference/coolify-stable-aliases.md`.

### Currently registered aliases (single source of truth: `docs/reference/coolify-stable-aliases.md`)

| Stable name | UUID container | Gatus URL |
|---|---|---|
| `browserless` | `vckgs8c00o40o884k48cgow8-220643454460` | `tcp://browserless:3000` |
| `gotenberg` | `e04k4sco44ow04ccc0o0k00k-151256201601` | `tcp://gotenberg:3000` |
| `meilisearch` | `bs0wo48k4gwo440gcowscoc8-150802066640` | `tcp://meilisearch:7700` |
| `glitchtip-web` | `glitchtip-web-z00kkck8c8cwo800kk440csk` | `tcp://glitchtip-web:8000` |

> Coolify **Service stacks** (multi-container, under `/data/coolify/services/<uuid>/`) use `container_name: <service>-<coolify-service-uuid>` which IS stable across redeploys — the alias workaround applies only to single-image Applications.
> **Drift discipline:** any new alias must be added to (1) the App's compose `networks.coolify.aliases`, (2) `scripts/vps_apply_limits.sh` `apply_alias` section, (3) this table, and (4) `docs/reference/coolify-stable-aliases.md`.

## Active Projects

Full auto-generated project list: `docs/BUSINESS_MODEL.md` § Project Portfolio. Source of truth: `data/projects.yaml` (auto-synced by `scripts/sync_projects.py`).

---

## 🛑 MANDATORY ORCHESTRATOR PRE-FLIGHT

Traycer MUST run these checks before generating any Plan, PRD, or Execution Spec.

1. **PORTS.md** — Assign a free port (Python 8000–8099 / Frontend 3000–3099). State it.
2. **BUSINESS_MODEL.md** — Check for duplicate / similar project. State finding.
3. **Fabrik Microservices table** — Use existing internal APIs before planning new logic. State which apply.
4. **Hardware Audit** — Confirm all Docker images support `linux/amd64`.
5. **Design System** — For any project type with a UI surface (saas-skeleton, static-site, chrome-extension, mobile-app, desktop-app, wordpress, docusaurus), read `.windsurf/rules/ocoron-design-system.md` before generating any spec or copy. Apply color tokens, typography, scaffold-specific adaptations, verbal identity (forbidden language, voice, microcopy rules) to all planning output. State: "Design system read."
6. **External Knowledge Verification** — When the plan touches a third-party API/SDK/vendor (Coolify, Paddle, Traefik, Authelia, Stripe, Supabase, Cloudflare, n8n, etc.), verify the current contract against live docs BEFORE writing the ticket spec. Order: (a) search `docs/`, `docs/reference/`, `AFCL.md`, `docs/LESSONS_LEARNT.md` for prior coverage; (b) if absent, fetch the vendor's official docs URL and cite it in the ticket's `References:` field; (c) pass cited URLs to executing agents in `Final Gate Instruction` or `Implementation Notes` so they don't re-research what you verified. If you cannot verify within 3 search calls, mark the ticket `BLOCKED: external-research-needed` and stop. Skip for: stdlib, language syntax, internal Fabrik conventions.

## Planning Constraints

Before creating any plan, verify:

1. **Solo developer** — no team handoff; one person executes everything.
2. **x86_64 VPS** — all Docker images must support `linux/amd64`.
3. **Budget-conscious** — prefer free Kilo models, free-tier APIs, self-hosted over SaaS.
4. **Existing services** — check if a Fabrik microservice already solves the need before building.
5. **Prebuilt containers** — check `docs/reference/prebuilt-app-containers.md` before writing custom code.
6. **Port conflicts** — check `PORTS.md` before assigning ports.
7. **Coolify deployment** — all services deploy as Docker Compose apps via Coolify.
8. **No Alpine** — `-slim-bookworm` base images only.
9. **Module dependencies** — if a project needs an incomplete Fabrik module, plan module completion first. Check module status in `docs/BUSINESS_MODEL.md`.
10. **DNS** — site-provisioner handles Namecheap + Cloudflare + domain purchasing automatically; don't plan around it manually.
11. **Scaffold immutability** — `fabrik scaffold` lays down a fixed project structure. Do NOT plan tickets that reorganize, flatten, or add top-level directories. Extend within the existing structure.
12. **State conflicts** — if a ticket scope contradicts existing project state (file exists, port taken, schema diverges), surface the conflict in the ticket explicitly. Coding agents are instructed to stop on contradictions, not silently overwrite.

---

## Rule-Pack Injection (Traycer Responsibility)

Traycer injects rule-pack guidance into coding-agent execution prompts based on `project.yaml::type` + ticket scope. Coding agents do NOT self-select packs.

### Pack Registry (21 packs in `.windsurf/rules/`)

| Pack ID | File | Category |
|---|---|---|
| `PY_CORE` | `10-python.md` | Core |
| `API_CONTRACTS` | `15-api-contracts.md` | Backend |
| `TS_CORE` | `20-typescript.md` | Core |
| `DATA_PG` | `25-data-postgres.md` | Backend |
| `OPS` | `30-ops.md` | Backend |
| `SECURITY` | `35-security-auth.md` | Backend |
| `DOCUMENTATION` | `40-documentation.md` | Backend |
| `DOCUSAURUS` | `42-docusaurus.md` | Platform |
| `TESTING` | `45-testing-strategy.md` | Backend |
| `CODE_REVIEW` | `50-code-review.md` | Backend |
| `OBSERVABILITY` | `55-observability.md` | Backend |
| `SAAS_UI` | `60-saas-ui.md` | Core |
| `WORDPRESS` | `62-wordpress.md` | Platform |
| `RAG_SEARCH` | `65-rag-search.md` | Domain |
| `CHROME_MV3` | `70-chrome-ext.md` | Core |
| `WORKERS` | `75-workers-jobs.md` | Backend |
| `MOBILE_UI` | `80-mobile.md` | Core |
| `PAYMENTS` | `85-payments-billing.md` | Domain |
| `AUTOMATION` | `90-automation.md` | Backend |
| `MULTI_TENANT` | `95-multi-tenant-saas.md` | Domain |
| `DESIGN_SYSTEM` | `ocoron-design-system.md` | Cross-cutting |

> The former `CROSS_CUTTING` pack was dissolved 2026-05-14; its rules now live in topic packs (30-ops, 35-security-auth, 50-code-review, 55-observability) and the three coding-agent bootstraps.

### Project Type → Default Packs

| Project Type | Default Packs |
|---|---|
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

> `node-api` and `file-api` scaffolds are currently JavaScript-based — don't inject `TS_CORE` or `PY_CORE` unless a specific project has actually adopted them. `chrome-extension` includes `PY_CORE` because the backend companion service is Python. `docusaurus` is for dev/team-authored content; `wordpress` for client-authored marketing/e-commerce; `static-site` for owner-controlled landing pages. Decision guide: `docs/reference/scaffold-type-decision-guide.md`.

### Feature-Based Overlay Packs

| Pack | Inject When Ticket Involves |
|---|---|
| `API_CONTRACTS` | API endpoints, routes, request/response schemas |
| `DATA_PG` | Database queries, migrations, schema changes |
| `SECURITY` | Auth, sessions, CORS, secrets, CSP, sensitive files |
| `TESTING` | Always — universal overlay, injected for every ticket |
| `OBSERVABILITY` | Health endpoints, logging, monitoring, Gatus |
| `RAG_SEARCH` | Embeddings, retrieval, vector search, LLM context |
| `PAYMENTS` | Paddle, subscriptions, billing, entitlements |
| `MULTI_TENANT` | Tenant isolation, RLS, tenant-scoped queries |

### Injection Policy

1. Read `project.yaml::type` → default packs → add feature overlays based on ticket scope keywords.
2. Injection format into execution prompt:
   ```
   ## Rule Packs Active
   [PACK_ID] .windsurf/rules/<file>
   - <rule line 1>
   - <rule line 2>
   (max 6 lines per pack)
   ```
3. Total injected guidance must not exceed **40 lines**. If exceeded, drop feature overlays first; keep project-type defaults.
4. Injection is performed at query-construction time. Agents do NOT self-select packs.
5. `AGENTS-compact.md` is the Kilo CLI bootstrap — self-contained, carries the always-on cross-cutting rules (Doc Sync Matrix, Cross-Cutting, Security & Data, Docker & Deploy, HARD STOPS) because Kilo's dispatcher does not auto-load packs.
6. `final_gate.py` handles objective checks only; packs are enforced via injection, not by the gate.

---

## Scaffold Types

Canonical entry point: `fabrik scaffold <name> --type <type>`. Creates the project tree AND emits `specs/services/<name>.yaml` with a populated `shape:` block per `templates/<type>/defaults.yaml`. The `shape:` block drives which infrastructure registrars run during `fabrik apply` (postgres / redis / gatus / backrest / glitchtip / grafana / authelia / meilisearch / prometheus). `fabrik new` is deprecated (hidden; scheduled removal 2026-05-31).

**Pre-scaffold intent capture (T3-01, Stage 1 of the lifecycle):**

- `fabrik preplan new <slug>` — create `docs/preplans/<YYYY-MM-DD>-<slug>.md` from `templates/preplan/preplan.md.j2`. 9 sections: Idea / Project type / Shape preview / External deps / Domain / Success criteria / Out of scope / Open questions / Notes (VPS1 inventory reminders).
- Refine the markdown with Opus / ChatGPT / Claude.
- `fabrik scaffold <name> --from-preplan docs/preplans/<file>` — ingests the preplan: pre-fills `--type`, copies the preplan into `<project>/docs/preplan.md`, and **layers a `Preplan:` reference line into all 4 AI guardrail files** (`AGENTS.md`, `CLAUDE.md`, `AGENTS-compact.md`, `.windsurfrules`) so every downstream agent reads the same intent.
- Traycer's Step 2.5 in `docs/traycer/fabrik-workflow.md` is the planning-side companion: when a fresh project is detected, look for a preplan in `docs/preplans/` BEFORE asking the user to declare anything from scratch.

**Post-deploy lifecycle commands (T2-01 + T2-02 + T2-03 + T2-04):**

- Every successful `fabrik apply` / `fabrik redeploy --refresh-infrastructure` writes `.fabrik/state/<spec.id>.json` (8-field G-F3 manifest) — the source of truth for what got registered.
- `fabrik audit-registrars [--spec <path>] [--json]` — verify each spec's shape-resolved registrars vs live VPS state. Statuses: `present / missing / n/a / unknown`. Exit 2 if any missing.
- `fabrik reconcile-all [--filter <substr>] [--yes]` — fleet-wide re-run of `refresh_infrastructure` per spec under per-spec file lock.
- `fabrik verify <domain> --spec registrars` — postcondition gate; fails on any `missing` registrar.
- `fabrik destroy <spec> --partial <reg>` (repeatable) — surgical un-registration without touching DNS, Coolify app, or local files. Backed by module-level `HANDLER_ARGS` / `HANDLER_FUNCS` exports in `orchestrator/destroyer.py`. Grafana intentionally excluded (annotations are decorative).
- **Gate-time spec validation (T2-03 G-E2):** `scripts/final_gate.py:471` runs `fabrik.spec_loader.load_spec()` on staged `specs/services/*.yaml` files; catches pydantic-model violations before the gate passes. Do NOT add a parallel pre-commit hook for the same purpose (Lesson 60).
- **Weekly Authelia drift cron (T2-03 G-G4):** `0 6 * * 1` WSL cron entry runs `scripts/audit_authelia_gates.py` against the live Traefik API, verifying every admin-dashboard router has the `authelia-forward@docker` middleware attached. Log at `/var/log/fabrik-audit.log`.
- **Coolify alias-watcher write side (T2-04 G-J3):** specs that need a stable Docker DNS alias for an Application-style container (Gatus monitors / inter-service URLs reference the alias, not the timestamp-suffixed container name) opt in via `coolify.alias: <name>` in `CoolifyConfig`. The orchestrator's `_maybe_register_coolify_alias()` writes the prefix→alias mapping to `/opt/coolify-alias-watcher/aliases.json` and restarts the watcher. WSL mirror at `ops/coolify-alias-watcher/`. Restart-not-reload — service has no `ExecReload`.
- **Deploy-aware `data/projects.yaml` (T2-04 G-J1):** `scripts/sync_projects.py` now merges `.fabrik/state/<id>.json` into each project entry under a `deploy:` block (last_apply_status / last_apply_at / last_apply_sha / coolify_uuid / coolify_app_name / spec_path / registrars_applied). Projects with no state file show `last_apply_status: never`.
- **Local dev loop (T3-03 G-D3 + G-I1 + G-I2):** Stage 2 of the lifecycle stays in-WSL. `fabrik dev [-d]` runs `docker compose -f compose.dev.yaml up [-d]` in the project dir (fails clean if `compose.dev.yaml` missing). `fabrik logs --local [-f] [--service <name>]` tails the dev stack via `docker compose logs` (sibling of the Loki-backed `fabrik logs <service>` remote path — `--local` is opt-in, remote path unchanged). `fabrik review [--since HEAD] [--spec <path>] [--out <file>]` bundles `git diff` + spec + `docs/preplan.md` + the resolved-registrar table into `.fabrik/review/<ts>.md` for human or Kilo-CLI reviewer dispatch. Helpers in `src/fabrik/dev_tools.py`. When planning tickets that change service behaviour, suggest `fabrik review` as the pre-PR step.
- **Postgres allocation registry (T4-01 G-J4):** `/opt/monitoring/configs/postgres/allocations.json` is the source of truth for "who owns each postgres DB on `postgres-main`" — `owner ∈ {fabrik, manual, infrastructure}`, `spec_id`, `user`, `notes`. Written atomically by `drivers/postgres.register_allocation` from `create_database` (and the symmetric `unregister_allocation` from `drop_database`). `audit_postgres` cross-references the registry against live `pg_database`, returning `status: drift` (new `AuditStatus` value) when registry and live state disagree. When planning a ticket that creates / renames / drops a postgres DB out-of-band, instruct the executor to update `allocations.json` (typically via `fabrik destroy --partial postgres` + `fabrik apply` rather than direct SQL).
- **State-driven destroy (T4-02 G-F4):** `fabrik destroy <spec> --use-state [-y] [--drop-data] [--keep-dns] [--keep-files] [--dry-run]` replays the registrar list from `.fabrik/state/<id>.json` (T2-01) instead of the current spec's shape. Three phases: (0) data-bearing guard refuses without `--drop-data` if state has any postgres/redis/meilisearch entry; (1) reverse `_REGISTRAR_ORDER` dispatch via T2-02's `HANDLER_FUNCS`+`HANDLER_ARGS` — `prometheus → meilisearch → authelia → glitchtip → backrest → gatus → redis → postgres` (grafana skipped); (2) coolify + dns (gated by `--keep-dns` + domain) + files (gated by `--keep-files`). On success, state archived to `_destroyed/<id>.json.<ts>`. **Mutually exclusive with `--partial`**. Use when planning teardown of a service whose spec has drifted between apply and destroy — the only way to guarantee no orphan registrars (e.g. meilisearch index after `has_search_feature` flipped to false). Function: `fabrik.orchestrator.destroyer.destroy_from_state`.
- **Cross-VPS portability bundle (T4-03 G-J2):** `fabrik export [-o|--out|--output <path>] [--include-data] [--skip-remote]` writes a tarball containing every resource the current VPS's `fabrik apply` ever registered — specs, `.fabrik/state/`, Coolify Applications + Services + Projects (UUIDs recursively stripped), monitoring configs (prometheus/alertmanager/grafana dashboards/redis-assignments/postgres-allocations), Authelia + Backrest configs, redacted `.env` key list (key NAMES only — never values), and a restore README. `fabrik import <bundle> [--apply]` parses the bundle and emits a restore plan (default dry-run); `--apply` is honoured but the real-run API-write path is a documented stub — **roundtrip is deferred to vps2 stand-up**. Module: `src/fabrik/portability.py`. Security invariants (test-enforced in `tests/test_portability.py`): NO plaintext secrets, NO Coolify UUIDs, NO private-key references. When planning a portability or DR ticket, surface this command and the manual follow-ups it doesn't automate (LetsEncrypt re-issue, DNS re-bind, OAuth re-create, secrets re-populate).
- **Per-registrar drift alerting (T4-04 G-G5):** hourly WSL crontab runs `scripts/audit_all_registrars.py` → walks every spec → calls `fabrik.audit.audit_all` → emits Prom-text `fabrik_audit_drift_total{spec_id, registrar}` gauge to the VPS-local pushgateway (`prom/pushgateway:v1.9.0` at `127.0.0.1:9091` — NOT publicly exposed). Prometheus scrapes pushgateway (`honor_labels: true`); rule file `rules/fabrik-drift.yml` (alert `FabrikRegistrarDrift`, `for: 10m`, label `alert_class: registrar_drift`) → Alertmanager route under `route.routes:` matches that label → existing `telegram` receiver (NO new receiver — pack v3.2 V2-S4 rejected the proliferation). When planning tickets that touch any of the 9 registrars (postgres / redis / gatus / backrest / glitchtip / grafana / authelia / meilisearch / prometheus) drift detection auto-fires within ~1 hour. Companion `fabrik_audit_status{spec_id, registrar, status}` gauge for Grafana per-status charts.

| Type | Template | Stack | shape.kind | shape flags (true only) |
|---|---|---|---|---|
| python-api | `templates/scaffold/` | FastAPI + Uvicorn + Docker | service | is_public |
| saas-skeleton | `templates/saas-skeleton/` | Next.js 14 + TypeScript + Tailwind | service | is_public, has_persistent_data, needs_database |
| node-api | `templates/node-api/` | Node.js API + Docker | service | is_public |
| file-api | `templates/file-api/` | File operations API | service | is_public, has_persistent_data |
| file-worker | `templates/file-worker/` | Background file worker | worker | has_persistent_data |
| wordpress | `templates/wordpress/` | WordPress + WP-CLI | wordpress | is_public, has_persistent_data, needs_database |
| docusaurus | `templates/docusaurus/` | Documentation site | static | is_public |
| chrome-extension | `templates/chrome-extension/` | Chrome extension + Python backend | static | (none — CRX, not VPS-deployed) |
| mobile-app | `templates/mobile-app/` | React Native | static | (none — distributed via app stores) |
| desktop-app | `templates/desktop-app/` | Electron | static | (none — distributed as installer) |
| static-site | `templates/saas-skeleton/` | Next.js / static HTML | static | is_public |

> Each scaffold propagates `.windsurfrules`, `.windsurf/rules/`, and `.windsurf/workflows/` to generated projects automatically.
> **Authoritative shape matrix:** `src/fabrik/spec_loader.py::Shape` docstring. Change it there, then run the full scaffold suite — divergence from `templates/<type>/defaults.yaml` is a failing test (`tests/test_spec_generator.py`).
> **Registrar applicability matrix:** `src/fabrik/orchestrator/infrastructure.py` docstring + `resolve_applicability()`. Source of truth for which of (postgres / redis / gatus / backrest / glitchtip / grafana / authelia / meilisearch / prometheus) runs for a given `shape:` block.

### What every API scaffold emits automatically (no manual ticket needed)

Traycer must NOT plan tickets to manually add any of these — `fabrik scaffold` (`python-api`, `node-api`, `file-api`) writes them on creation:

- `internal_auth.py` — M2M auth module (`X-Internal-Token` validation via `hmac.compare_digest`).
- `metrics.py` — Prometheus business metrics (`REQUEST_COUNT`, `ERROR_COUNT`, `ACTIVE_JOBS`, `PROCESSING_COUNT`).
- `/metrics` endpoint — mounted in `main.py`, Authelia-bypassed.
- `glitchtip_init.py` / `glitchtip_init.js` — Sentry SDK init pointed at GlitchTip; no-op if `GLITCHTIP_DSN` env unset. Wired in `main.py` BEFORE app construction.
- `SERVICE_INTERNAL_SECRET_KEY` line in `.env.example`.
- Structured-logging module (`logger.py` / `logger.js`) with JSON output + `SERVICE_NAME` from env.

If a ticket appears to need these, the existing scaffolded code already covers it — plan against extending, not duplicating.

---

## Quality Gates

| Gate | Script | Purpose |
|---|---|---|
| Final Gate (Tier 1 — lean) | `scripts/final_gate.py --lean` | Default during coding |
| Final Gate (Tier 2 — full) | `scripts/final_gate.py` | At milestone closure |
| Final Gate (Tier 3 — systemic) | `scripts/final_gate.py --systemic` | On-demand repo health |
| Kilo Review (optional) | `scripts/kilo_code_review.py` | High-risk manual audits |
| Documentator (optional) | `scripts/kilo_docs_enforcer.py` | Bulk documentation work |

## Implementation Detail Pointers

Traycer plans against these rules but does NOT inline them into tickets — the coding agents already load them via their bootstrap + packs:

- **Python / FastAPI / config / temp files** → `.windsurf/rules/10-python.md`
- **Docker / compose / Coolify network / Authelia restart procedure / Gatus stable-alias install / post-deploy checklist / `fabrik redeploy` sequence** → `.windsurf/rules/30-ops.md`
- **M2M auth (`X-Internal-Token` / `internal_auth.py`) / sensitive data backup / password policy / JWT / CORS / CSP** → `.windsurf/rules/35-security-auth.md`
- **Pre-scaffolded logging / GlitchTip discipline / health endpoints / Gatus stable DNS rule** → `.windsurf/rules/55-observability.md`
- **Documentation rules (CHANGELOG, README features, plans, `.env.example`, new-`.md`-file allowlist, writing style)** → `.windsurf/rules/40-documentation.md`
- **Coolify stable-alias install procedure + currently-registered pairs** → `docs/reference/coolify-stable-aliases.md`

## Reference Documents

| Document | Path | Use When |
|---|---|---|
| Project Portfolio | `docs/BUSINESS_MODEL.md` | Full project list, statuses, duplicate-check |
| AI Taxonomy | `docs/reference/AI_TAXONOMY.md` | Selecting AI tools / models for a ticket |
| Local LLM Infrastructure | `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` | Ollama setup, agent → model assignments |
| Stack Decision Guide | `docs/reference/technology-stack-decision-guide.md` | Choosing tech stack for new project |
| Prebuilt Containers | `docs/reference/prebuilt-app-containers.md` | Avoid writing custom code when a container exists |
| Database Strategy | `docs/reference/DATABASE_STRATEGY.md` | Database / migration / vector storage choices |
| Owner Profile | `docs/owner_ozgur_basak.md` | Calibrating tone / framing for planning output |
| Port Allocations | `PORTS.md` | Assigning ports to new services |
| Scaffold Decision Guide | `docs/reference/scaffold-type-decision-guide.md` | Choosing WordPress vs Docusaurus vs static-site |
| SaaS UI Patterns | `docs/reference/Modern GUI Approaches for a Lean, Fast, Effective, Low-Confusion SaaS Web App.md` | Planning SaaS frontend |
| Chrome Extension UI | `docs/reference/Modern GUI Approaches for Chrome Extensions.md` | Planning Chrome extensions |
| Mobile UI | `docs/reference/Modern Mobile GUI Approaches for Android and iOS.md` | Planning mobile apps |
| Ocoron Design System | `.windsurf/rules/ocoron-design-system.md` | Visual + verbal identity for UI projects |
| Cascade Models | `docs/reference/windsurf/cascade-models.md` | Selecting Windsurf Cascade model tier |
| Deployment Guide | `docs/DEPLOYMENT.md` | `fabrik apply` / `fabrik deploy` / observability internals |
| Kilo Agent Naming | `docs/reference/kilo/KILO_AGENT_NAMING.md` | Naming new Kilo CLI agents |
| Kilo Agent Registry | `scripts/kilo_47_agents_final.json` | Authoritative agent selection list |
| Lessons Learnt | `docs/LESSONS_LEARNT.md` | Past incidents, decisions, anti-patterns |
| Coolify Stable Aliases | `docs/reference/coolify-stable-aliases.md` | Registering new single-image App aliases |
| Traycer Workflow | `docs/traycer/traycer-managed-development-workflow/` | Trigger / brief / plan / breakdown / execute commands |
