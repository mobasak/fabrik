# AGENTS.md — Fabrik Identity & Knowledge (Traycer)

**Last Updated:** 2026-05-29
**Read by:** Traycer only — for ticket planning. Traycer must know the entire Fabrik infrastructure to plan correctly.
**Coding agents:** Claude Code reads `CLAUDE.md`; Windsurf Cascade reads `.windsurfrules`; Kilo CLI reads `AGENTS-compact.md` (via `opencode.json` `instructions:` array).
**Deployment references (canonical):** [`docs/DEPLOYMENT_ARCHITECTURE.md`](docs/DEPLOYMENT_ARCHITECTURE.md) — code-level map of every file on the deploy path · [`docs/operations/deployment.md`](docs/operations/deployment.md) — procedures (apply/redeploy/destroy) · [`docs/operations/fabrik-lifecycle.md`](docs/operations/fabrik-lifecycle.md) — runtime behavior & data safety. Supersede any narrative pasted into individual tickets.
**Deploy method:** SSH + Docker Compose, direct to VPS — **no intermediary platform** (Coolify decommissioned, see below).

---

## Platform at a Glance

| #   | Layer                 | Component                                                                                    | Purpose                                                                                                                                                                                                                |
| --- | --------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **CLI**               | `fabrik` (40+ subcommands)                                                                   | scaffold, apply (single deploy entry — `deploy` removed/folded in), redeploy, destroy, verify, audit, dev, review, logs, domain, seo, ai                                                                                |
| 2   | **Scaffolding**       | `scaffold.py`                                                                                | Creates projects with governance + infra wiring (11 types)                                                                                                                                                             |
| 3   | **Planning**          | mega-epic-breakdown (5 commands: 00-trigger, 02-05)                                          | Large vision → epics → tickets → dispatch. `00-trigger` is a single entry point serving both new and existing projects via owner-declared mode (Step 0).                                                                |
| 4   | **Planning**          | epic-to-ticket-workflow (00-11)                                                                          | Single-epic planning + execution. Also the execution engine per epic after mega-epic dispatch.                                                                                                                          |
| 5   | **Governance**        | `AGENTS.md` / `CLAUDE.md` / `.windsurfrules` / `AGENTS-compact.md` / `opencode.json`        | Agent bootstraps (5 files)                                                                                                                                                                                             |
| 6   | **Rules**             | `.windsurf/rules/**/*.md`                                                                    | 30 domain discipline packs                                                                                                                                                                                             |
| 7   | **Enforcement**       | `final_gate.py` + 34 checks in `enforcement/`                                               | Task completion + structural validation                                                                                                                                                                                |
| 8   | **Dispatch**          | `kilo_dispatch.py` + kilo pipeline (15 scripts)                                              | Agent routing, model selection, benchmarks                                                                                                                                                                             |
| 9   | **Sync**              | `sync_enforcement_to_projects.py`                                                            | Pushes governance to all projects                                                                                                                                                                                      |
| 9a  | **Sync Scripts**      | `scripts/consolidate_envs.py.deprecated` (DEPRECATED — not active)                           | Was: merge all `/opt/*` project `.env` files into `/opt/fabrik/.env` with project-scoped sections. Retired; do not plan around it                                                                                     |
| 9b  | **Sync Scripts**      | `scripts/sync_projects.py`                                                                   | `project.yaml` from every `/opt/*` project → merged into `data/projects.yaml` + updates `BUSINESS_MODEL.md`                                                                                                           |
| 10  | **Specs**             | `specs/services/<id>.yaml`                                                                   | Shape contract → registrars                                                                                                                                                                                            |
| 11  | **Orchestrator**      | `src/fabrik/orchestrator/` (9 registrars + 22 drivers)                                      | postgres/redis/gatus/backrest/glitchtip/grafana/authelia/meilisearch/prometheus                                                                                                                                        |
| 12  | **AI Sysadmin**       | `scripts/sysadmin/bot.py`                                                                    | Telegram ↔ Claude Code on VPS. Proactive checks, morning reports, security audits                                                                                                                                      |
| 13  | **VPS Infra**         | ~22 services                                                                                 | Traefik (standalone proxy on 80/443), PG (postgres-main), Redis (redis-main), Gatus, GlitchTip, Grafana, Prometheus, Loki, Alertmanager, n8n, Apprise, Authelia, MeiliSearch, Backrest, Gotenberg, Browserless, Netdata, cAdvisor, node-exporter, Pushgateway, Promtail. (Coolify decommissioned — `coolify-proxy` container remains stopped/leftover) |
| 14  | **Microservices**     | 8 custom services (ports 18011–18017 + 8007)                                                 | Captcha, Translator, Proxy, DNS/Site-Provisioner, File API, Image Broker, Email Gateway, File Worker                                                                                                                   |
| 15  | **Alerting**          | Prometheus → Alertmanager → Telegram + Gatus → Apprise → Telegram                           | Multi-path alerting chain                                                                                                                                                                                              |
| 16  | **VPS Daemons**       | sysadmin bot, iptables persistence (coolify-alias-watcher still active but inert/obsolete)   | Systemd services                                                                                                                                                                                                       |
| 17  | **Cron/Scheduled**    | Hourly drift audit, daily morning report, weekly security/maintenance, monthly backup verify | Automated ops                                                                                                                                                                                                          |
| 18  | **WSL Startup**       | `wsl_startup_hook.sh` (6-step pipeline)                                                     | Env watcher, registry sync, health summary, Kilo agent refresh                                                                                                                                                         |
| 19  | **Local LLM**         | 4 Ollama agents (coder/reviewer/fixer/docs)                                                  | Offline AI for quick tasks                                                                                                                                                                                             |
| 20  | **Background Runner** | `rund/runc/runwait/runlast/runls/runtail/runk`                                               | Non-blocking long command execution                                                                                                                                                                                    |
| 21  | **Shared Code**       | `/opt/fabrik-lib/` — 18 vendorable modules (copy, don't import)                             | Reusable modules graduated from projects; see `/opt/fabrik-lib/README.md` for full table + which-module-do-I-need matrix                                                                                               |
| 22  | **VPS Audits**        | 7 audit scripts (system/health/security/performance/observability/backup/hardening)          | Deep VPS inspection                                                                                                                                                                                                    |

---

## Workflow (mandatory)

Two entry paths depending on scope:

**Single-epic:** `docs/traycer/epic-to-ticket-workflow/` — `00-trigger` → `01-epic-brief` → `02-core-flows` → `03-tech-plan` → `04-deploy-plan` → `05-ticket-outline` → implementation (`06-07-08`) → validation (`09-11`).

**Multi-epic (large vision):** `docs/traycer/mega-epic-breakdown/` — `00-trigger` (vision intake + scale assessment) → `02-epic-decomposition` → `03-expand-epic-files` → `04-cross-epic-validation` → `05-dispatch`. Each dispatched epic then runs `epic-to-ticket-workflow` in consume mode (00-trigger reads the epic ticket's Metadata as its INFRA-CHECK input).

**Existing project continuation:** use `mega-epic-breakdown/00-trigger-workflow-command` and declare **EXISTING mode** when prompted at Step 0. The command branches into the continuation path (project snapshot + Compliance Detection with mechanical / rule-pack / owner-decision sub-steps + delta scoping). Output is a Vision Summary in the same shape as new-mode + two extra sections (`Locked Decisions`, `Compliance Report`). `02-epic-decomposition` consumes the Vision Summary identically and emits **Retrofit epics** for every `fix-now` row in the Compliance Report alongside the delta-feature epics.

**Scale decision:** `00-trigger` (mega-epic) decides single vs multi-epic based on feature count and complexity. Single-epic routes directly to `epic-to-ticket-workflow`. Multi-epic routes to `02-epic-decomposition`.

**Pre-research drop point:** `docs/development/plans/00-research.md` (the owner drops external research from ChatGPT/Claude/Gemini here before planning).

## Deploy Pipeline and Automation Boundaries

Full lifecycle from vision to running service — what is automated vs what requires human action:

**Phase 1 — Planning (Traycer, mostly automated):**
1. Owner drops research file in `docs/development/plans/` or `docs/preplans/`.
2. Traycer runs `mega-epic-breakdown` or `epic-to-ticket-workflow` to produce epic tickets.
3. Owner confirms decomposition and dispatches epic tickets. **Human gate: epic confirmation.**

**Phase 2 — Implementation (coding agents: Claude Code / Windsurf / Kilo):**
4. Each epic ticket runs `epic-to-ticket-workflow` (00-trigger consume mode → 01-epic-brief → ... → 09-11).
5. Coding agent implements, passes `scripts/final_gate.py`, stages changes.
6. Owner reviews gate output and commits + pushes. **Human gate: commit/push decision.**

**Phase 3 — Deploy (WSL → VPS, semi-automated):**
7. `fabrik apply <spec>` — runs in WSL, SSHes to VPS, writes compose.yaml + .env, runs `docker compose up -d --wait`, then provisions infra registrars. First deploy time is dominated by the image build (git source: `git clone` + `docker compose build`); redeploys reuse cached layers.
8. `fabrik verify <domain> --spec registrars` — postcondition gate; confirms registrars live. **Manual today; target: auto-triggered post-apply.**
9. `fabrik audit-registrars --spec <path>` — drift check. Hourly WSL cron pushes metrics to Prometheus. AlertManager → Telegram on drift. **Manual reconcile today; target: AI Sysadmin auto-runs `fabrik reconcile-all` on drift alert.**

**Current automation gaps (open tickets):**
- **Gap 1 — Deploy supervision:** `fabrik apply` runs unmonitored. Target: AI Sysadmin watches apply log, reports pass/fail to Telegram.
- **Gap 2 — Auto-verify post-apply:** `fabrik verify` is not triggered automatically after `fabrik apply` succeeds. Wire point: `verify.py:394`.
- **Gap 3 — Auto-reconcile on drift:** AI Sysadmin receives drift alert but does not yet run `fabrik reconcile-all` automatically.

**When writing ticket success criteria:** if the ticket touches deploy, include: (a) `fabrik apply` passes, (b) `fabrik verify` returns all-green, (c) Gatus shows healthy within 5 min. Do NOT include "AI Sysadmin auto-reconciles" until Gap 3 is closed.

## File Ownership

Traycer plans against `AGENTS.md`. Agent-execution contracts, rule packs, and workflow definitions live elsewhere and are out of Traycer's edit scope.

| File / Path | Owner | Traycer May Edit? |
|---|---|---|
| `AGENTS.md` | Traycer (this file — planner context) | ✅ Yes |
| `docs/traycer/epic-to-ticket-workflow/**` + `docs/traycer/mega-epic-breakdown/**` | Traycer (workflow definitions) | ✅ Yes |
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
- **Deploy:** SSH + Docker Compose, direct to VPS — no intermediary platform. Single entry point: `fabrik apply <spec>` (spec-driven; `fabrik deploy` removed — folded into apply). Source types: git / template / docker / local. Full reference: `docs/DEPLOYMENT_ARCHITECTURE.md` + `docs/operations/deployment.md`.
- **DB:** PostgreSQL on VPS (`postgres-main` container, default) · Supabase (managed auth / realtime / pgvector when needed). Connection strings use Docker DNS (`postgres-main:5432`, `redis-main:6379`), never `localhost`.
- **Proxy:** Traefik (standalone compose stack at `/opt/traefik/`) + Let's Encrypt.
- **Domains:** `*.vps1.ocoron.com` via site-provisioner (Namecheap + Cloudflare + auto-purchase). Implementation: `docs/reference/service-contracts/site-provisioner.md`.
- **Monitoring:** Gatus · Netdata · Grafana · Prometheus · Alertmanager · Loki (standalone compose stacks under `/opt/monitoring/` + `/opt/prometheus/`).

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
| Database | PostgreSQL 16 (VPS, `postgres-main` container) | Supabase for managed auth / realtime / pgvector |
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
| PostgreSQL | (internal — `postgres-main`) | Shared database |
| Redis | (internal — `redis-main`) | Shared cache |
| Traefik | (internal — 80/443) | Reverse proxy (standalone, `/opt/traefik/`) + Let's Encrypt |
| Gatus | status.vps1.ocoron.com | Uptime monitoring (memory storage — see status.vps1.ocoron.com for live count) |
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

### Resource limits on every service

Every compose service MUST declare `deploy.resources.limits.memory` to prevent OOM on the shared 12 GB VPS. This is enforced at deploy time by `deployer_ssh._validate_compose()` (fatal — blocks the deploy if missing) for template/docker sources, and warned by `compose_linter.lint()`. Scaffolded compose files emit it automatically; hand-written or git-sourced composes must declare it themselves.

## Observability & Alerting

All monitoring services run as standalone Docker Compose stacks under `/opt/monitoring/` (Grafana, Alertmanager, Loki, Promtail, node-exporter, cAdvisor) and `/opt/prometheus/` (Prometheus). Local source: `specs/infrastructure/monitoring-stack.yaml` + `configs/` in Fabrik repo.

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
Gatus (35 endpoints, growing — see status.vps1.ocoron.com) → Apprise (http://apprise:8000/notify/alerts) → Telegram
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
- `configs/grafana/provisioning/` — bind-mounted into the Grafana container (`/opt/monitoring/`)

**Grafana admin password:** `/opt/fabrik/.env` as `GRAFANA_ADMIN_PASSWORD`. Manage start/stop via `cd /opt/monitoring && sudo docker compose {up -d,stop} grafana`.

## VPS Security (4-Layer Model)

| Layer | Target | Mechanism |
|---|---|---|
| **iptables DOCKER-USER** | All Docker ports | Blocks external access to raw container ports. Only **80/443** serve traffic. (6001/6002 remain open at DOCKER-USER + UFW as stale Coolify Realtime/Soketi leftovers — nothing listens; pending cleanup.) |
| **Authelia** | Admin dashboards w/o native TOTP | Forward-auth 2FA for n8n, Netdata, Backrest, Apprise; + forward-auth with `^/api/` bypass for Grafana. **Note:** GlitchTip is on full-bypass — uses django-allauth app-layer TOTP (canonical Sentry pattern). Decision matrix: `docs/LESSONS_LEARNT.md §8.13`. |
| **X-Internal-Token** | API services | M2M auth via `internal_auth.py` + shared `SERVICE_INTERNAL_SECRET_KEY` in `/opt/fabrik/.env`. Same key written into every deployed service's `/opt/<name>/.env`. Validation is constant-time (`hmac.compare_digest`). Implementation pack: `.windsurf/rules/core/35-security-auth.md`. |
| **Traefik** | Public sites | Routes traffic without auth for `ocoron.com`, `status.vps1.ocoron.com`. |

### Key security files on VPS

- `/etc/iptables/add-docker-user-rules.sh` — iptables rules
- `/etc/systemd/system/iptables-docker-user.service` — persistence
- `/opt/authelia/config/configuration.yml` — Authelia access control policies
- `/opt/authelia/compose.yaml` — Authelia Docker Compose
- `/opt/fabrik/.env` — `SERVICE_INTERNAL_SECRET_KEY`, `GRAFANA_ADMIN_PASSWORD`, etc.

**Authelia config changes:** Authelia exits on SIGHUP (no hot-reload). Restart procedure (discover container name, then restart): `.windsurf/rules/core/30-ops.md` § Authelia SSO. **Never** protect `/health` — Authelia bypass `*.vps1.ocoron.com → /health` is global.

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

## Container Naming (stable by construction)

Under the SSH + Docker Compose model, **every compose service declares `container_name: <name>`** (enforced fatal by `deployer_ssh._validate_compose()` for template/docker sources; warned by `compose_linter`). Names are therefore stable across redeploys — Gatus endpoints and inter-service URLs key directly on the container name. The old Coolify single-image-Application alias workaround (timestamp-suffixed `<uuid>-<ts>` names) is **obsolete and removed**; live containers already use clean names (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.). The `coolify` Docker network name is retained as a historical artifact — it is just a standard bridge network all services join for Traefik routing.

## Active Projects

Full auto-generated project list: `docs/BUSINESS_MODEL.md` § Project Portfolio. Source of truth: `data/projects.yaml` (auto-synced by `scripts/sync_projects.py`).

---

## 🛑 MANDATORY ORCHESTRATOR PRE-FLIGHT

Traycer MUST run these checks before generating any Plan, PRD, or Execution Spec.

1. **PORTS.md** — Assign a free port (Python 8000–8099 / Frontend 3000–3099). State it.
2. **BUSINESS_MODEL.md** — Check for duplicate / similar project. State finding.
3. **Fabrik Microservices table** — Use existing internal APIs before planning new logic. State which apply.
4. **Hardware Audit** — Confirm all Docker images support `linux/amd64`.
5. **Design System** — For any project type with a UI surface (saas-skeleton, static-site, chrome-extension, mobile-app, desktop-app, wordpress, docusaurus), read `.windsurf/rules/core/ocoron-design-system.md` before generating any spec or copy. For mobile-app, also read `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md`. Apply color tokens, typography, scaffold-specific adaptations, verbal identity (forbidden language, voice, microcopy rules) to all planning output. State: "Design system read."
6. **External Knowledge Verification** — When the plan touches a third-party API/SDK/vendor (Paddle, Traefik, Authelia, Supabase, Cloudflare, n8n, etc. — note: Stripe is NOT available to Turkish entities), verify the current contract against live docs BEFORE writing the ticket spec. Order: (a) search `docs/`, `docs/reference/`, `AFCL.md`, `docs/LESSONS_LEARNT.md` for prior coverage; (b) if absent, fetch the vendor's official docs URL and cite it in the ticket's `References:` field; (c) pass cited URLs to executing agents in `Final Gate Instruction` or `Implementation Notes` so they don't re-research what you verified. If you cannot verify within 3 search calls, mark the ticket `BLOCKED: external-research-needed` and stop. Skip for: stdlib, language syntax, internal Fabrik conventions.
7. **fabrik-lib check** — Before planning any new component from scratch, read `fabrik-lib/README.md` for a vendorable module that already solves it (copy, don't import). State: "fabrik-lib checked — [module used / no match]."

## Planning Constraints

Before creating any plan, verify:

1. **Solo developer** — no team handoff; one person executes everything.
2. **x86_64 VPS** — all Docker images must support `linux/amd64`.
3. **Budget-conscious** — prefer free Kilo models, free-tier APIs, self-hosted over SaaS.
4. **Existing services** — check if a Fabrik microservice already solves the need before building.
5. **Prebuilt containers** — check `docs/reference/prebuilt-app-containers.md` before writing custom code.
6. **Port conflicts** — check `PORTS.md` before assigning ports.
7. **SSH + Docker Compose deployment** — `fabrik apply` SSHes to the VPS, writes `/opt/<name>/{compose.yaml,.env}`, and runs `docker compose up -d --wait`. No Coolify/PaaS layer. Compose must satisfy `deployer_ssh._validate_compose()` (platform `linux/amd64`, memory limit, `container_name`, no `ports:`, `coolify` network external, websecure entrypoint).
8. **No Alpine** — `-slim-bookworm` base images only.
9. **Module dependencies** — if a project needs an incomplete Fabrik module, plan module completion first. Check module status in `docs/BUSINESS_MODEL.md`.
10. **DNS** — site-provisioner handles Namecheap + Cloudflare + domain purchasing automatically; don't plan around it manually.
11. **Scaffold immutability** — `fabrik scaffold` lays down a fixed project structure. Do NOT plan tickets that reorganize, flatten, or add top-level directories. Extend within the existing structure.
12. **State conflicts** — if a ticket scope contradicts existing project state (file exists, port taken, schema diverges), surface the conflict in the ticket explicitly. Coding agents are instructed to stop on contradictions, not silently overwrite.

---

## Rule-Pack Injection (Traycer Responsibility)

Traycer injects rule-pack guidance into coding-agent execution prompts based on `project.yaml::type` + ticket scope. Coding agents do NOT self-select packs.

### Pack Registry (30 packs in `.windsurf/rules/**/*.md`)

Organized by folder:

**`core/` — shared across all scaffolds (20 packs)**

| Pack ID | File | Category |
|---|---|---|
| `PY_CORE` | `core/10-python.md` | Backend |
| `API_CONTRACTS` | `core/15-api-contracts.md` | Backend |
| `TS_CORE` | `core/20-typescript.md` | Frontend |
| `DATA_PG` | `core/25-data-postgres.md` | Backend |
| `OPS` | `core/30-ops.md` | Infrastructure |
| `SECURITY` | `core/35-security-auth.md` | Infrastructure |
| `DOCUMENTATION` | `core/40-documentation.md` | Process |
| `DOCUSAURUS` | `core/42-docusaurus.md` | Platform |
| `TESTING` | `core/45-testing-strategy.md` | Process |
| `CODE_REVIEW` | `core/50-code-review.md` | Process |
| `OBSERVABILITY` | `core/55-observability.md` | Infrastructure |
| `RESILIENCE` | `core/58-resilience.md` | Backend |
| `RAG_SEARCH` | `core/65-rag-search.md` | Domain |
| `RAG_CHUNKING` | `core/66-rag-chunking.md` | Domain |
| `WORKERS` | `core/75-workers-jobs.md` | Backend |
| `GPU_WORKERS` | `core/76-gpu-workers.md` | Domain |
| `PAYMENTS` | `core/85-payments-billing.md` | Domain |
| `EMAIL_TEMPLATES` | `core/86-email-templates.md` | Domain |
| `DESIGN_SYSTEM` | `core/ocoron-design-system.md` | Cross-cutting |
| `TOJLO_DESIGN` | `core/tojlo-design-system.md` | Cross-cutting |

**`saas/` — SaaS skeleton specific (4 packs)**

| Pack ID | File | Category |
|---|---|---|
| `SAAS_UI` | `saas/60-saas-ui.md` | Frontend |
| `ABUSE_DETECTION` | `saas/87-abuse-detection.md` | Domain |
| `SAAS_LAUNCH` | `saas/88-saas-launch-checklist.md` | Domain |
| `MULTI_TENANT` | `saas/95-multi-tenant-saas.md` | Domain |

**`mobile-app/` — React Native mobile (5 packs)**

| Pack ID | File | Category |
|---|---|---|
| `MOBILE_UI` | `mobile-app/80-mobile.md` | Frontend |
| `MOBILE_BILLING` | `mobile-app/81-mobile-billing.md` | Domain |
| `MOBILE_LAUNCH` | `mobile-app/89-mobile-launch-checklist.md` | Domain |
| `MOBILE_DESIGN` | `mobile-app/ocoron-mobile-design-system.md` | Cross-cutting |
| `TOJLO_MOBILE_DESIGN` | `mobile-app/tojlo-mobile-design-system.md` | Cross-cutting |

**`chrome-ext/` — Chrome extension (1 pack)**

| Pack ID | File | Category |
|---|---|---|
| `CHROME_MV3` | `chrome-ext/70-chrome-ext.md` | Frontend |

> `90-automation.md` removed (2026-05-18) — redundant Cascade routing table.
> `62-wordpress.md` removed — WordPress projects use scaffold defaults + `30-ops`.

### Project Type → Default Packs

| Project Type | Default Packs |
|---|---|
| `python-api` | `PY_CORE` |
| `node-api` | — |
| `saas-skeleton` | `TS_CORE`, `SAAS_UI`, `DESIGN_SYSTEM` |
| `chrome-extension` | `PY_CORE`, `TS_CORE`, `CHROME_MV3`, `DESIGN_SYSTEM` |
| `mobile-app` | `TS_CORE`, `MOBILE_UI`, `MOBILE_BILLING`, `MOBILE_DESIGN` |
| `desktop-app` | `TS_CORE`, `DESIGN_SYSTEM` |
| `file-api` | — |
| `file-worker` | `PY_CORE`, `WORKERS` |
| `wordpress` | `TS_CORE`, `DESIGN_SYSTEM`, `WORDPRESS` (planned — pack not yet created) |
| `docusaurus` | `DOCUSAURUS`, `DESIGN_SYSTEM` |
| `static-site` | `TS_CORE`, `SAAS_UI`, `DESIGN_SYSTEM` |

> `node-api` and `file-api` scaffolds are currently JavaScript-based — don't inject `TS_CORE` or `PY_CORE` unless a specific project has actually adopted them. `chrome-extension` includes `PY_CORE` because the backend companion service is Python. `docusaurus` is for dev/team-authored content; `wordpress` for client-authored marketing/e-commerce; `static-site` for owner-controlled landing pages. Decision guide: `docs/reference/scaffold-type-decision-guide.md`. All UI scaffolds get `DESIGN_SYSTEM` for visual/verbal identity.

### Feature-Based Overlay Packs

| Pack | Inject When Ticket Involves |
|---|---|
| `API_CONTRACTS` | API endpoints, routes, request/response schemas |
| `DATA_PG` | Database queries, migrations, schema changes |
| `SECURITY` | Auth, sessions, CORS, secrets, CSP, sensitive files |
| `RESILIENCE` | External service calls, circuit breakers, retry/backoff, self-healing |
| `TESTING` | Always — universal overlay, injected for every ticket |
| `OBSERVABILITY` | Health endpoints, logging, monitoring, Gatus |
| `RAG_SEARCH` | Embeddings, retrieval, vector search, LLM context |
| `RAG_CHUNKING` | Document ingestion, chunking pipelines, knowledge base indexing |
| `GPU_WORKERS` | GPU cloud provisioning, inference serving, training, model quantization |
| `PAYMENTS` | Paddle, subscriptions, billing, entitlements (SaaS web) |
| `MOBILE_BILLING` | RevenueCat, Google Play Billing, App Store IAP, Turkey GPB-mandatory |
| `MOBILE_LAUNCH` | Mobile app go-to-market — store accounts, legal, tax, review traps, staged rollout |
| `EMAIL_TEMPLATES` | Email/push/notification templates, MJML, Listmonk, SES, deliverability |
| `SAAS_LAUNCH` | SaaS product planning — legal pages, payment routing, GDPR/KVKK, onboarding, org settings, abuse prevention |
| `MULTI_TENANT` | Tenant isolation, RLS, tenant-scoped queries |

### Planning Protocol (epic-brief, decomposition, expand)

During **planning** — `epic-to-ticket-workflow/01-epic-brief`, `mega-epic-breakdown/02-epic-decomposition`, `mega-epic-breakdown/03-expand-epic-files` — Traycer must **read the full `.windsurf/rules/**/<file>.md`** for every applicable pack. Rule pack mandates are constraints on the plan. A plan that violates a rule pack mandate is wrong.

**Which packs to read during planning:**

1. **Universal (always):** `OPS`, `SECURITY`, `DOCUMENTATION`, `TESTING`, `OBSERVABILITY` — every project needs these.
2. **Scaffold-specific:** match `project.yaml::type` to the Default Packs table below.
3. **Feature-based:** match the project's features (from Vision Summary or epic scope) to the Overlay Packs table below. If the project has billing → read `PAYMENTS` + `SAAS_LAUNCH`. If it has tenant isolation → read `MULTI_TENANT`. Etc.

Read the FULL file — not just the registry entry. The mandates, banned patterns, and done-when checklists inside each pack inform epic boundaries, success criteria, and scope.

### Ticket Injection Policy (coding-agent execution)

During **ticket execution** — when dispatching work to coding agents (Claude Code, Windsurf, Kilo) — inject a condensed version:

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

- Every successful `fabrik apply` / `fabrik redeploy --refresh-infra` writes `.fabrik/state/<spec.id>.json` (8-field G-F3 manifest) — the source of truth for what got registered.
- `fabrik audit-registrars [--spec <path>] [--json]` — verify each spec's shape-resolved registrars vs live VPS state. Statuses: `present / missing / drift / n/a / override / unknown`. Exit 2 if any missing.
- `fabrik reconcile-all [--filter <substr>] [--yes]` — fleet-wide re-run of `refresh_infrastructure` per spec under per-spec file lock. **Currently broken:** `reconcile_all()` still imports `CoolifyClient` and queries Coolify (decommissioned), so it fails at startup — pending Phase 11-2 migration to the SSH path. Do not plan around it until fixed.
- `fabrik verify <domain> --spec registrars` — postcondition gate; fails on any `missing` registrar.
- `fabrik destroy <spec> --partial <reg>` (repeatable) — surgical un-registration without touching DNS, the compose app, or local files. Backed by module-level `HANDLER_ARGS` / `HANDLER_FUNCS` exports in `orchestrator/destroyer.py`. Grafana intentionally excluded (annotations are decorative).
- **Gate-time spec validation (T2-03 G-E2):** `scripts/final_gate.py` (spec-validation block ≈471–505) runs `fabrik.spec_loader.load_spec()` on staged `specs/services/*.yaml` files; catches pydantic-model violations before the gate passes. Do NOT add a parallel pre-commit hook for the same purpose (Lesson 60).
- **Weekly Authelia drift cron (T2-03 G-G4):** `0 6 * * 1` WSL cron entry runs `scripts/audit_authelia_gates.py` against the live Traefik API, verifying every admin-dashboard router has the `authelia-forward@docker` middleware attached. Log at `/var/log/fabrik-audit.log`.
- **Coolify alias-watcher (OBSOLETE — do not plan around):** the `coolify.alias` / `CoolifyConfig` opt-in and `_maybe_register_coolify_alias()` write side live only in the archived `orchestrator/deployer_coolify.py` and are NOT on the active SSH deploy path. Under SSH + Docker Compose every container has a stable `container_name`, so no alias indirection is needed. The `coolify-alias-watcher` systemd service + `/opt/coolify-alias-watcher/aliases.json` still exist on the VPS as inert leftovers (pending cleanup).
- **Deploy-aware `data/projects.yaml` (T2-04 G-J1):** `scripts/sync_projects.py` now merges `.fabrik/state/<id>.json` into each project entry under a `deploy:` block (last_apply_status / last_apply_at / last_apply_sha / coolify_uuid / coolify_app_name / spec_path / registrars_applied). The `coolify_uuid` / `coolify_app_name` field names are retained for backward compat — under SSH+Compose `coolify_uuid` now holds the app/`container_name`, not a Coolify UUID. Projects with no state file show `last_apply_status: never`.
- **Local dev loop (T3-03 G-D3 + G-I1 + G-I2):** Stage 2 of the lifecycle stays in-WSL. `fabrik dev [-d]` runs `docker compose -f compose.dev.yaml up [-d]` in the project dir (fails clean if `compose.dev.yaml` missing). `fabrik logs --local [-f] [--service <name>]` tails the dev stack via `docker compose logs` (sibling of the Loki-backed `fabrik logs <service>` remote path — `--local` is opt-in, remote path unchanged). `fabrik review [--since HEAD] [--spec <path>] [--out <file>]` bundles `git diff` + spec + `docs/preplan.md` + the resolved-registrar table into `.fabrik/review/<ts>.md` for human or Kilo-CLI reviewer dispatch. Helpers in `src/fabrik/dev_tools.py`. When planning tickets that change service behaviour, suggest `fabrik review` as the pre-PR step.
- **Postgres allocation registry (T4-01 G-J4):** `/opt/monitoring/configs/postgres/allocations.json` is the source of truth for "who owns each postgres DB on `postgres-main`" — `owner ∈ {fabrik, manual, infrastructure}`, `spec_id`, `user`, `notes`. Written atomically by `drivers/postgres.register_allocation` from `create_database` (and the symmetric `unregister_allocation` from `drop_database`). `audit_postgres` cross-references the registry against live `pg_database`, returning `status: drift` (new `AuditStatus` value) when registry and live state disagree. When planning a ticket that creates / renames / drops a postgres DB out-of-band, instruct the executor to update `allocations.json` (typically via `fabrik destroy --partial postgres` + `fabrik apply` rather than direct SQL).
- **State-driven destroy (T4-02 G-F4):** `fabrik destroy <spec> --use-state [-y] [--drop-data] [--keep-dns] [--keep-files] [--dry-run]` replays the registrar list from `.fabrik/state/<id>.json` (T2-01) instead of the current spec's shape. Three phases: (0) data-bearing guard refuses without `--drop-data` if state has any postgres/redis/meilisearch entry; (1) reverse `_REGISTRAR_ORDER` dispatch via T2-02's `HANDLER_FUNCS`+`HANDLER_ARGS` — `prometheus → meilisearch → authelia → glitchtip → backrest → gatus → redis → postgres` (grafana skipped); (2) compose app (`docker compose down` + `rm -rf /opt/<name>`) + dns (gated by `--keep-dns` + domain) + files (gated by `--keep-files`). On success, state archived to `_destroyed/<id>.json.<ts>`. **Mutually exclusive with `--partial`**. Use when planning teardown of a service whose spec has drifted between apply and destroy — the only way to guarantee no orphan registrars (e.g. meilisearch index after `has_search_feature` flipped to false). Function: `fabrik.orchestrator.destroyer.destroy_from_state`.
- **Cross-VPS portability bundle (T4-03 G-J2):** `fabrik export [-o|--out|--output <path>] [--include-data] [--skip-remote]` writes a tarball containing every resource the current VPS's `fabrik apply` ever registered — specs, `.fabrik/state/`, the per-service `/opt/<name>/{compose.yaml,.env-key-list}` (legacy builds also captured any residual Coolify Applications/Services/Projects with UUIDs recursively stripped), monitoring configs (prometheus/alertmanager/grafana dashboards/redis-assignments/postgres-allocations), Authelia + Backrest configs, redacted `.env` key list (key NAMES only — never values), and a restore README. `fabrik import <bundle> [--apply]` parses the bundle and emits a restore plan (default dry-run); `--apply` is honoured but the real-run API-write path is a documented stub — **roundtrip is deferred to vps2 stand-up**. Module: `src/fabrik/portability.py`. Security invariants (test-enforced in `tests/test_portability.py`): NO plaintext secrets, NO Coolify UUIDs, NO private-key references. When planning a portability or DR ticket, surface this command and the manual follow-ups it doesn't automate (LetsEncrypt re-issue, DNS re-bind, OAuth re-create, secrets re-populate).
- **Per-registrar drift alerting (T4-04 G-G5):** hourly WSL crontab runs `scripts/audit_all_registrars.py` → walks every spec → calls `fabrik.audit.audit_all` → emits Prom-text `fabrik_audit_drift_total{spec_id, registrar}` gauge to the VPS-local pushgateway (`prom/pushgateway:v1.9.0` at `127.0.0.1:9091` — NOT publicly exposed). Prometheus scrapes pushgateway (`honor_labels: true`); rule file `rules/fabrik-drift.yml` (alert `FabrikRegistrarDrift`, `for: 10m`, label `alert_class: registrar_drift`) → Alertmanager route under `route.routes:` matches that label → existing `telegram` receiver (NO new receiver — pack v3.2 V2-S4 rejected the proliferation). When planning tickets that touch any of the 9 registrars (postgres / redis / gatus / backrest / glitchtip / grafana / authelia / meilisearch / prometheus) drift detection auto-fires within ~1 hour. Companion `fabrik_audit_status{spec_id, registrar, status}` gauge for Grafana per-status charts.
- **SSH deploy mechanics (replaces the old Coolify v4 workarounds):** the active deployer is `orchestrator/deployer_ssh.py`. It writes `compose.yaml` + `.env` to `/opt/<name>/` via SCP (scp-to-tmp-then-`sudo mv`), then runs `sudo docker compose up -d --wait` (git sources also run `sudo docker compose build` first). Git-sourced redeploys capture the current commit and auto-revert via `git reset --hard` on health-check failure; non-git sources fail loudly with no auto-revert. No PaaS grace period — first-deploy time is just `git clone` + image build. The legacy `deployer_coolify.py` (SSH-fallback-build, `.env` pre-seed, `get_deployments` workarounds for Coolify v4.0.0-beta.459 bugs) is archived and off the active path.

| Type | Template | Stack | shape.kind | shape flags (true only) |
|---|---|---|---|---|
| python-api | `templates/scaffold/` | FastAPI + Uvicorn + Docker | service | is_public, exposes_metrics |
| saas-skeleton | `templates/saas-skeleton/` | Next.js 14 + TypeScript + Tailwind | service | is_public, has_persistent_data, needs_database |
| node-api | `templates/node-api/` | Node.js API + Docker | service | is_public, exposes_metrics |
| file-api | `templates/file-api/` | File operations API | service | is_public, has_persistent_data |
| file-worker | `templates/file-worker/` | Background file worker | worker | has_persistent_data |
| wordpress | `templates/wordpress/` | WordPress + WP-CLI | wordpress | is_public, has_persistent_data, needs_database |
| docusaurus | `templates/docusaurus/` | Documentation site | static | is_public |
| chrome-extension | `templates/chrome-extension/` | Chrome extension + Python backend | static | (none — CRX, not VPS-deployed) |
| mobile-app | `templates/mobile-app/` | React Native | static | (none — distributed via app stores) |
| desktop-app | `templates/desktop-app/` | Electron | static | (none — distributed as installer) |
| static-site | `templates/saas-skeleton/` | Next.js / static HTML | static | is_public |

> Each scaffold propagates `.windsurfrules`, `.windsurf/rules/` (with subdirectory structure: `core/`, `saas/`, `mobile-app/`, `chrome-ext/`), and `.windsurf/workflows/` to generated projects automatically.
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

- **Python / FastAPI / config / temp files** → `.windsurf/rules/core/10-python.md`
- **Docker / compose / `coolify` Docker network (legacy name, standard bridge) / Authelia restart procedure / post-deploy checklist / `fabrik redeploy` sequence** → `.windsurf/rules/core/30-ops.md`
- **M2M auth (`X-Internal-Token` / `internal_auth.py`) / sensitive data backup / password policy / JWT / CORS / CSP** → `.windsurf/rules/core/35-security-auth.md`
- **Pre-scaffolded logging / GlitchTip discipline / health endpoints / Gatus stable DNS rule** → `.windsurf/rules/core/55-observability.md`
- **Documentation rules (CHANGELOG, README features, plans, `.env.example`, new-`.md`-file allowlist, writing style)** → `.windsurf/rules/core/40-documentation.md`
- **Responsive design testing (Playwright, screenshots, fix patterns, agent directive)** → `docs/reference/mobile-responsive-testing-guide.md`

## Reference Documents

| Document | Path | Use When |
|---|---|---|
| Project Portfolio | `docs/BUSINESS_MODEL.md` | Full project list, statuses, duplicate-check |
| AI Taxonomy | `docs/reference/AI_TAXONOMY.md` | Selecting AI tools / models for a ticket |
| Local LLM Infrastructure | `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` | Ollama setup, agent → model assignments |
| Stack Decision Guide | `docs/reference/technology-stack-decision-guide.md` | Choosing tech stack for new project |
| Prebuilt Containers | `docs/reference/prebuilt-app-containers.md` | Avoid writing custom code when a container exists |
| Database & Vector Strategy | `.windsurf/rules/core/25-data-postgres.md` + `core/65-rag-search.md` | PostgreSQL host selection, migrations, pgvector, hybrid search |
| Owner Profile | `docs/owner_ozgur_basak.md` | Calibrating tone / framing for planning output |
| Port Allocations | `PORTS.md` | Assigning ports to new services |
| Scaffold Decision Guide | `docs/reference/scaffold-type-decision-guide.md` | Choosing WordPress vs Docusaurus vs static-site |
| SaaS UI Patterns | `docs/reference/Modern GUI Approaches for a Lean, Fast, Effective, Low-Confusion SaaS Web App.md` | Planning SaaS frontend |
| Chrome Extension UI | `docs/reference/Modern GUI Approaches for Chrome Extensions.md` | Planning Chrome extensions |
| Mobile UI | `docs/reference/Modern Mobile GUI Approaches for Android and iOS.md` | Planning mobile apps |
| Ocoron Design System | `.windsurf/rules/core/ocoron-design-system.md` | Visual + verbal identity for UI projects |
| Ocoron Mobile Design | `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md` | Mobile component patterns (list items, sheets, navigation, forms) |
| Mobile Responsive Testing | `docs/reference/mobile-responsive-testing-guide.md` | Single source of truth for RWD testing (Playwright, screenshots, fix patterns) |
| Cascade Models | `docs/reference/windsurf/cascade-models.md` | Selecting Windsurf Cascade model tier |
| Deployment Architecture | `docs/DEPLOYMENT_ARCHITECTURE.md` | Code-level map of every file on the SSH+Compose deploy path |
| Deployment Procedures | `docs/operations/deployment.md` | `fabrik apply` / `redeploy` / `destroy` workflows + golden rules |
| Fabrik Lifecycle | `docs/operations/fabrik-lifecycle.md` | Runtime behavior, data safety, downtime, `.env` merge |
| Kilo Agent Naming | `docs/reference/kilo/KILO_AGENT_NAMING.md` | Naming new Kilo CLI agents |
| Kilo Agent Selection | `docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md` | Model routing, quality floors, current roster |
| Kilo CLI Reference | `docs/reference/kilo/KILO_CLI_REFERENCE.md` | Kilo as AI infrastructure — serve, MCP, skills, programmatic patterns |
| Kilo Use Cases | `docs/reference/kilo/KILO_USE_CASES.md` | 11 non-coding domains (data extraction, translation, content, legal, etc.) |
| Kilo Agent Registry | `scripts/kilo_47_agents_final.json` | Authoritative agent selection list |
| AI Prompt Templates | `docs/reference/MD/ai-prompt-templates.md` | Designing system prompts, skills, AGENTS.md, review templates |
| RAG Chunking Rules | `.windsurf/rules/core/66-rag-chunking.md` | Planning search/RAG features — heading-based splitting, chunk envelopes |
| Markdown AI Rules | `docs/reference/MD/markdown-cheatsheet.md` | AI-friendly markdown writing conventions |
| AI Agent Directives | `docs/reference/ai_agent_prompt_directives.md` | Copy-paste phrases for steering agent quality |
| GPU Workers Guide | `.windsurf/rules/core/76-gpu-workers.md` | GPU cloud decisions — when to self-host vs managed API, provider selection |
| Lessons Learnt | `docs/LESSONS_LEARNT.md` | Past incidents, decisions, anti-patterns |
| epic-to-ticket-workflow | `docs/traycer/epic-to-ticket-workflow/` | Single-epic planning + execution (00-11); also the per-epic execution engine in mega-epic runs |
| mega-epic-breakdown | `docs/traycer/mega-epic-breakdown/` | Large vision → epics → tickets → dispatch (5 commands); `00-trigger` is the single entry serving both new and existing projects (owner declares mode at Step 0) |
