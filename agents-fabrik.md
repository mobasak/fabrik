# AGENTS-FABRIK.md — Fabrik Identity & Knowledge (canonical agents doc)

> One canonical agents doc (spec 2026-07-18 § AGENTS.md resolution, option b). `AGENTS.md` is a stub
> pointing here; the high-frequency core is `agents-fabrik-core.md`, `@import`-ed into `CLAUDE.md`.

**Read by:** Traycer (ticket planning — Claude-Max-powered, tool-capable) **and any agent planning or
making non-trivial changes directly** (Claude Code — Max OAuth — plus the OpenRouter subagent pool; Windsurf Cascade + Kilo CLI RETIRED 2026-07-19). This is the canonical infra +
codebase map — ground every plan in it, don't guess.
**Our agents are tool-capable — orient, then act:** run `python scripts/select_rules.py` to load the ACTIVE rule packs; open every file/symbol you cite (`path:line`); ground external facts **live via MCP** (`exa` → `brave-search` → `context7`, cite URL + date, never from memory); gate with `python scripts/final_gate.py`. Enumerations here are copied from the live registry (`scaffold.py::SCAFFOLD_TYPES`, `.windsurf/rules/**`, `fabrik-lib/README.md`, `spec_loader.py::Shape`) — if a count disagrees with the registry, the registry wins.
**Coding agents:** Claude Code reads `CLAUDE.md` (which `@import`s `agents-fabrik-core.md`). ⚠️ Windsurf Cascade + Kilo CLI are **RETIRED (2026-07-19)** — their bootstrap files (`.windsurfrules`, `AGENTS-compact.md` via `opencode.json`) remain synced only until removed. Rule packs live in `.windsurf/rules/**` — canonical; at review time `scripts/review_rubric.py` injects them.

## Platform at a Glance

| #   | Layer                 | Component                                                                                    | Purpose                                                                                                                                                                                                                |
| --- | --------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **CLI**               | `fabrik` (50+ subcommands)                                                                   | scaffold, apply (single deploy entry — `deploy` removed/folded in), redeploy, destroy, verify, audit, dev, review, logs, domain, seo, ai                                                                                |
| 2   | **Scaffolding**       | `scaffold.py`                                                                                | Creates projects with governance + infra wiring (12 types)                                                                                                                                                             |
| 3   | **Planning**          | mega-epic-breakdown (4 active commands: 00-trigger, 02, 03, 04 — 05 retired; dispatch is code + GUI)                                          | Large vision → epics → tickets → dispatch. `00-trigger` is a single entry point serving both new and existing projects via owner-declared mode (Step 0).                                                                |
| 4   | **Planning**          | epic-to-ticket-workflow (00-11)                                                                          | Single-epic planning + execution. Also the execution engine per epic after mega-epic dispatch.                                                                                                                          |
| 5   | **Governance**        | `AGENTS.md` / `CLAUDE.md` / `.windsurfrules` / `AGENTS-compact.md` / `opencode.json`        | Agent bootstraps (5 files)                                                                                                                                                                                             |
| 6   | **Rules**             | `.windsurf/rules/**/*.md`                                                                    | 55 packs (28 `core/` · 5 `saas/` · 6 `mobile-app/` · 3 `chrome-ext/` · 2 `desktop-app/` · 11 `ai/`)                                                                                                              |
| 7   | **Enforcement**       | `final_gate.py` + 46 checks in `enforcement/`                                               | Task completion + structural validation                                                                                                                                                                                |
| 8   | **Dispatch**          | `kilo_dispatch.py` + kilo pipeline (15 scripts)                                              | Agent routing, model selection, benchmarks                                                                                                                                                                             |
| 9   | **Sync**              | `sync_enforcement_to_projects.py`                                                            | Pushes governance to all projects. These files are **centrally managed** (canonical list: `/opt/fabrik/scripts/fabrik_synced_manifest.py`) — never plan tickets that edit a synced copy in a project; it's overwritten on the next sync (gate-enforced by `scripts/enforcement/check_synced_unmodified.py`). Changes go upstream in `/opt/fabrik`, and ONLY if correct for ALL projects.                                                                                                                                                                                      |
| 9a  | **Sync Scripts**      | `scripts/consolidate_envs.py.deprecated` (DEPRECATED — not active)                           | Was: merge all `/opt/*` project `.env` files into `/opt/fabrik/.env` with project-scoped sections. Retired; do not plan around it                                                                                     |
| 9b  | **Sync Scripts**      | `scripts/sync_projects.py`                                                                   | `project.yaml` from every `/opt/*` project → merged into `data/projects.yaml` + updates `BUSINESS_MODEL.md`                                                                                                           |
| 10  | **Specs**             | `specs/services/<id>.yaml`                                                                   | Shape contract → registrars                                                                                                                                                                                            |
| 11  | **Orchestrator**      | `src/fabrik/orchestrator/` (10 registrars incl. `watchdog` — **opt-OUT: it fires for every spec unless disabled with `watchdog: { enabled: false }`** — + 27 drivers)                                      | postgres/redis/gatus/backrest/glitchtip/grafana/authelia/meilisearch/prometheus/watchdog. Active deployer: `deployer_ssh.py`; archived: `deployer_coolify.py` + `coolify_alias.py` (off the active path, kept for reference) |
| 12  | **AI Sysadmin**       | `scripts/sysadmin/` — `bot.py` (Telegram FastAPI), `proactive-check.sh` (every 15 min via cron), `daily-digest.sh` (09:XX UTC hash-slotted), `morning-report.sh`, `weekly-security.sh`, `weekly-maintenance.sh`, `monthly-backup-verify.sh`, `detect_reversals.py` (`*/5 min`), `send-telegram.sh`, `system-prompt.txt` | **Deployed on ALL 3 hosts** (vps1 hub + vps2 + vps3 spokes). Telegram ↔ Claude Code on each host; on-host `aro-wake.service` (FastAPI :8201 with `/metrics`). Proactive checks now include Authelia + GlitchTip + GlitchTip-worker probes (2026-06-17). System prompt instructs LESSONS_LEARNT.md consultation (75+ incidents, ~250KB) before deciding fixes. Peer protocol `consult` verb LIVE since 2026-06-06 (loop-prevention guards: trace_id dedup, hop cap, forward intersection, storm breaker). Stage 2 hourly rate-limited. |
| 13  | **VPS Infra**         | Hub (vps1): ~31 containers incl. infra — count drifts; canonical: `docs/infrastructure/vps-complete-inventory.md` (registry wins) · Spokes (vps2, vps3): 5 each                                       | **Hub (vps1)** — Traefik (standalone proxy on 80/443), PG (postgres-main), Redis (redis-main), Gatus, GlitchTip (web + worker), Grafana, Prometheus, Loki, Alertmanager, n8n, Apprise, Authelia, MeiliSearch, Backrest, Gotenberg, Browserless, cAdvisor, node-exporter, postgres-exporter, redis-exporter, Pushgateway, Promtail, watchdog-test + sidecar, aro-wake, vps-sysadmin-bot, plus shared infra exposed on `10.99.0.1:<port>` for mesh access. **Spokes (vps2, vps3)** — Traefik (public TLS for `*.vpsN.ocoron.com`), node-exporter, cadvisor, promtail, aro-wake. (Coolify fully decommissioned 2026-05-30; Docker network renamed `coolify` → `fabrik` on 2026-05-31. `fabrik apply` now rejects any compose still declaring the `coolify` network.) |
| 14  | **Microservices**     | site-provisioner (live); others retired/not-deployed                                         | **Live:** site-provisioner (`provision.vps1.ocoron.com`). **Retired / not deployed (no container, no router):** Captcha, Translator, Proxy, File API, Image Broker, Email Gateway, File Worker — code may exist but none are running on the fleet                                                                                            |
| 15  | **Alerting**          | Prometheus → Alertmanager → Telegram (native `telegram_configs`) + Gatus → Apprise → Telegram | Multi-path alerting chain. Pushgateway-fed `fabrik_audit_drift_total{spec_id,registrar}` gauge has its own alert + Telegram route                                                                                       |
| 16  | **VPS Daemons**       | `vps-sysadmin-bot.service` + `aro-wake.service` (per host), iptables-docker-user persistence | Systemd services. **Removed 2026-06-18:** `coolify-alias-watcher.service` + `/opt/coolify-alias-watcher/` — obsolete under stable `container_name:` from compose; the watcher is no longer loaded and the directory is gone. |
| 17  | **Cron/Scheduled**    | Hourly drift audit, daily morning report, weekly security/maintenance, monthly backup verify | Automated ops                                                                                                                                                                                                          |
| 18  | **WSL Startup**       | `wsl_startup_hook.sh` (8-step pipeline)                                                     | Env watcher, registry sync, health summary, daily selection-doc refresh (pipeline still live; Kilo CLI itself RETIRED 2026-07-19)                                                                                                                                                         |
| 19  | **Local LLM**         | 4 Ollama agents (coder/reviewer/fixer/docs)                                                  | Offline AI for quick tasks                                                                                                                                                                                             |
| 20  | **Background Runner** | `rund/runc/runwait/runlast/runls/runtail/runk`                                               | Non-blocking long command execution                                                                                                                                                                                    |
| 21  | **Shared Code**       | `/opt/fabrik-lib/` — vendorable modules (copy, don't import)                                | Reusable modules graduated from projects. **Resolve modules from the INDEX: `/opt/fabrik-lib/README.md` § Modules (+ the which-module-do-I-need matrix). Never hard-code a fabrik-lib module name or count in a doc, rule pack, or command — the library grows continuously, so every enumeration rots.**                                                                                              |
| 22  | **VPS Audits**        | 7 audit scripts (system/health/security/performance/observability/backup/hardening)          | Deep VPS inspection                                                                                                                                                                                                    |

---

## Workflow (mandatory) — three tiers by scale

**Front door — the distinguishing test, once:** *does it need tickets and dispatched agents, or is it one
plan an operator session can carry?* Routing is symmetric (`/fabrik-spec` up-routes; ettw-00 mirrors) — no
entry point is "wrong."

**Feature-scale** (one operator-carried plan): `/fabrik-spec` → `/fabrik-data-contract` → *(GUI)*
`/fabrik-ui-design` → `/fabrik-plan-after-chat` → `/fabrik-execute-plan` — completes at execute.

**Single-epic:** `docs/orchestrator/epic-to-ticket-workflow/` (the `-fabrik` files — the ONE runnable chain;
the tool-less twins were archived 2026-07-18, north-star D2) — `00-trigger` → `01-epic-brief` →
`02-core-flows` → `03-tech-plan` → `04-deploy-plan` → `05-ticket-outline` → implementation (`06-07-08`) →
validation (`09-11`).

**Multi-epic (large vision):** `docs/orchestrator/mega-epic-breakdown/` (the `-fabrik` files) —
`00-trigger` (spec-grade vision intake + scale assessment) → `02-epic-decomposition` →
`03-expand-epic-files` → `04-cross-epic-validation`; dispatch is code + GUI (`05` retired). Each dispatched
epic then runs `epic-to-ticket-workflow` in consume mode (00-trigger reads the epic ticket's Metadata as
its INFRA-CHECK input).

**Existing project continuation:** enter at `docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md`
and declare **EXISTING mode** at Step 0 (project snapshot + Compliance Detection + delta scoping; output =
Vision Summary + `Locked Decisions` + `Compliance Report`; `02` emits **Retrofit epics** for `fix-now` rows).

**Scale decision:** mega-`00`'s Scale Assessment routes single-epic → `epic-to-ticket-workflow/00-trigger-fabrik`
directly; multi-epic → `02-epic-decomposition`.

**Pre-research drop point:** `docs/development/plans/00-research.md` (the owner drops external research from ChatGPT/Claude/Gemini here before planning).

## Deploy Pipeline and Automation Boundaries

**Control-plane boundary (the deploy model — why projects don't self-deploy).** `/opt/fabrik` is the single deploy **control plane**: it alone holds the fleet credentials (VPS SSH, DNS, shared-DB passwords on `postgres-main`) and coordinates the shared resources (DB/Redis-index/port/Traefik/GlitchTip/Authelia/Gatus allocation, deploy state, the spec→registrar invariants). A project (and its in-repo AI) **cannot and should not** run its own deploy — it lacks those credentials by design, and decentralized deploys would race on shared infra + bypass invariant enforcement. The division of labor is fixed: **projects own deploy-READINESS** (a compliant `compose.yaml`/`Dockerfile` + a correct, self-describing `specs/services/<id>.yaml`); **the hub owns deploy EXECUTION** (`fabrik apply`). To go live a project must (a) have a hub spec and (b) be triggered through the hub — **trigger, don't execute**: GitOps (`fabrik redeploy` git-pulls on push) or the watchdog Tier-D deploy adapter (`ssh fabrik redeploy`) are the self-service paths; neither hands the project fleet credentials. fabrik-lib deliberately has **no "deploy-yourself" module** — its rule is "self-contained *builds*" (a project's Docker build needs only its own repo), not self-contained deploys. New project not deploying? First check it has a `specs/services/<id>.yaml` (e.g. `trade-intelligence` has compose+Dockerfile but no spec → can't be applied).

Full lifecycle from vision to running service — what is automated vs what requires human action:

**Phase 1 — Planning (our agents, mostly automated):**
1. Owner drops research file in `docs/development/plans/` or `docs/preplans/`.
2. Our agents run `mega-epic-breakdown` or `epic-to-ticket-workflow` to produce epic tickets.
3. Owner confirms decomposition and dispatches epic tickets. **Human gate: epic confirmation.**

**Phase 2 — Implementation (coding agents: Claude Code + the OpenRouter subagent pool):**
4. Each epic ticket runs `epic-to-ticket-workflow` (00-trigger consume mode → 01-epic-brief → ... → 09-11).
5. Coding agent implements, passes `scripts/final_gate.py`, stages changes.
6. Owner reviews gate output and commits + pushes. **Human gate: commit/push decision.**

**Phase 3 — Deploy (WSL → VPS, semi-automated):**
7. `fabrik apply <spec>` — runs in WSL, SSHes to VPS, writes compose.yaml + .env, runs `docker compose up -d --wait`, then provisions infra registrars. First deploy time is dominated by the image build (git source: `git clone` + `docker compose build`); redeploys reuse cached layers.
8. `fabrik verify <domain> --spec registrars` — postcondition gate; confirms registrars live. **Manual today; target: auto-triggered post-apply.**
9. `fabrik audit-registrars --spec <path>` — drift check. Hourly WSL cron pushes metrics to Prometheus. AlertManager → Telegram on drift. **Manual reconcile today; target: AI Sysadmin auto-runs `fabrik reconcile-all` on drift alert.**

**Current automation gaps (open tickets):**
- **Gap 1 — Deploy supervision:** `fabrik apply` runs unmonitored. Target: AI Sysadmin watches apply log, reports pass/fail to Telegram.
- **Gap 2 — Auto-verify post-apply:** `fabrik verify` is not triggered automatically after `fabrik apply` succeeds.
- **Gap 3 — Auto-reconcile on drift:** AI Sysadmin receives drift alert but does not yet run `fabrik reconcile-all` automatically.

**When writing ticket success criteria:** if the ticket touches deploy, include: (a) `fabrik apply` passes, (b) `fabrik verify` returns all-green, (c) Gatus shows healthy within 5 min. Do NOT include "AI Sysadmin auto-reconciles" until Gap 3 is closed.

## File Ownership

Our planning agents ground against this file. Agent-execution contracts, rule packs, and workflow definitions live elsewhere.

| File / Path | Owner | Planner May Edit? |
|---|---|---|
| `agents-fabrik.md` | the planning agent (this file — planner context) | ✅ Yes |
| `docs/orchestrator/epic-to-ticket-workflow/**` + `docs/orchestrator/mega-epic-breakdown/**` | the runnable `-fabrik` chain (workflow definitions) | ✅ Yes |
| `docs/traycer/{epic-to-ticket-workflow,mega-epic-breakdown}/**` | ARCHIVED tool-less twins (north-star D2) — reference only, NOT kept in lockstep | ❌ No |
| `docs/traycer/fabrik-workflow.md` | Reference copy (do not diverge from workflow definitions) | ✅ Yes |
| `CLAUDE.md` | Claude Code bootstrap | ❌ No |
| `.windsurfrules` | Windsurf Cascade bootstrap | ❌ No |
| `AGENTS-compact.md` | Kilo CLI bootstrap (via `opencode.json`) | ❌ No |
| `.windsurf/rules/**` | Topic rule packs (shared; Cascade auto-loads via frontmatter, Claude Code and Kilo read on demand) | ❌ No |
| `.windsurf/workflows/**` | Cascade slash-command workflows | ❌ No |
| Per-project `CLAUDE.md`, `AGENTS-compact.md`, `project.yaml` | Project-scoped (out of Fabrik-monorepo scope) | ❌ No |

## Owner & Working Style

- **Solo developer** — Özgür Başak, 45, Turkish electronics engineer & entrepreneur. Full profile: `docs/owner_ozgur_basak.md`.
- **Capacity:** ~50 focused h/week.
- **Budget:** Prefer free/cheap-but-good fast tools; maximize ROI.
- **Philosophy:** Fast but pro. Ship → iterate → automate. No over-engineering.

## Development Environment

- **Dev:** WSL Ubuntu 24.04 on Windows. IDE: VS Code + Claude Code + Local LLM agents (Windsurf Cascade + Kilo CLI RETIRED 2026-07-19).
- **VPS Fleet (3 hosts):**
  - **vps1 (hub, LA)** — `172.93.160.197` (Hivelocity) · x86_64 Ubuntu · AMD EPYC-Genoa, 6 vCPU, 11.6 GB RAM. Runs ~31 containers incl. infra.
  - **vps2 (spoke, Coventry UK)** — `96.9.214.128` · 5 containers (Traefik + monitoring agents only).
  - **vps3 (spoke, Coventry UK)** — `104.128.190.151` · 5 containers (same as vps2).
  - **Mesh:** WireGuard `10.99.0.0/24` (UDP 51820, MTU 1420, hub-and-spoke). Cross-Atlantic RTT 133–134 ms, 0% loss. Shared infra (postgres-main, redis-main, glitchtip, authelia, loki) is bound on the hub at `10.99.0.1:<port>` so spokes can reach it.
  - **Per-host DNS:** `*.vps1.ocoron.com → 172.93.160.197` · `vps2.ocoron.com` + `*.vps2.ocoron.com → 96.9.214.128` · `vps3.ocoron.com` + `*.vps3.ocoron.com → 104.128.190.151`. Wildcards cover all tenants/subdomains per host. Source of truth: [`docs/infrastructure/vps-complete-inventory.md`](docs/infrastructure/vps-complete-inventory.md).
- **Deploy:** SSH + Docker Compose, direct to VPS — no intermediary platform. Single entry point: `fabrik apply <spec>` (spec-driven; `fabrik deploy` removed — folded into apply). Source types: git / template / docker / local. Tenant routing: spec declares target host (default: hub). Full reference: `docs/DEPLOYMENT_ARCHITECTURE.md` + `docs/operations/deployment.md`.
- **DB:** PostgreSQL on hub (`postgres-main` container, default). Self-host by default; Supabase only as a deliberate ADR-recorded exception (see § Supabase). Connection strings use Docker DNS on the hub (`postgres-main:5432`, `redis-main:6379`), never `localhost`. From spokes: use the mesh IP `10.99.0.1:5432` / `10.99.0.1:6379` (verified cross-host reachable).
- **Proxy:** Traefik runs on every host (standalone compose stacks). Hub at `/opt/traefik/` routes `*.vps1.ocoron.com` + `ocoron.com`. Spokes each run their own Traefik for `*.vpsN.ocoron.com` with `authelia-vps1@file` middleware (forward-auth → `http://10.99.0.1:9091/api/verify`) for tenant admin routes. Let's Encrypt on all 3.
- **Domains:** Domain registration + DNS + Cloudflare zone provisioning automated through site-provisioner (`provision.vps1.ocoron.com`). Implementation: `docs/reference/service-contracts/site-provisioner.md`. The `fabrik domain` CLI is the single entry point.
- **Monitoring:** Gatus · Grafana · Prometheus · Alertmanager · Loki (+ node-exporter / cAdvisor / promtail / aro-wake) — hub stack under `/opt/monitoring/`. Spokes run agents only (node-exporter on `:9100`, cadvisor on `:8080`, promtail on `:9080`, aro-wake on `:8201`) — bound to `10.99.0.x` (wg0 only, NOT publicly exposed). Hub Prometheus federates spoke jobs via wg0 (`node-spokes`, `cadvisor-spokes`, `promtail-spokes` — 6 spoke targets total, all `up`). Hub-Grafana queries the federated time-series with `host` + `role` labels. (Netdata removed 2026-05-30.)

### Local LLM Agents

Ollama on localhost:11434. Full setup: `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md`.

| Agent | Hardware | Memory Usage | Speed | Stability |
|---|---|---|---|---|
| `fabrik-coder` | hybrid-cpu | ~19 GB (8 GB VRAM + 11 GB RAM) | Moderate (~15–25 tok/s) | Stable |
| `fabrik-reviewer` | cpu | ~42 GB RAM | Slow (~8–12 tok/s) | High memory pressure ⚠️ |
| `fabrik-fixer` | hybrid-gpu | ~9 GB (8 GB VRAM + 1 GB RAM) | Fast (~40–60 tok/s) | Stable |
| `fabrik-docs` | gpu | ~5 GB VRAM | Instant (~80–100 tok/s) | Rock solid |

> ⚠️ **These are LOCAL OLLAMA models** (offline, hub-only). **The name `fabrik-reviewer` is overloaded** — the row above is the Ollama model; the **Claude Code `fabrik-reviewer` subagent-type** (and its siblings `fabrik-researcher` / `fabrik-gui`) are a *different thing* — layered **on top of** the pool-default for GUI work + the authoritative/high-risk review pass + the decide/merge phase (not the default worker).
>
> **Subagent dispatch for gradeable fan-out** (review finders, research/`path:line` grounders, doc reconcilers, rules auditors, code implementers) is governed by [`.windsurf/rules/core/62-using-subagents.md`](.windsurf/rules/core/62-using-subagents.md) **§ Dispatch policy + § Parallelism** — **pool-default** (the OpenRouter pool, `run_agents` / `pick_models`, ≤$1.5/Mtok, records to the `subagent_runs` flywheel) with native Claude Code subagents added on top for GUI / the authoritative-high-risk pass / the decide-merge. **The two-shape parallelism rule (or a fan-out SILENTLY serializes):** read-only → `tools_enabled=False` (each its own group → parallel); tools-enabled → `tools_enabled=True` + **disjoint `owned_paths`** (empty/overlapping → one serial group). The planning agents *plan*; the `/fabrik-*` execution + review commands are what dispatch the pool.

## File & Folder Naming

Kebab-case everywhere, with the canonical exception list `[canonical: CLAUDE.md § Pointers — Naming]`.

## Tech Stack Defaults

| Layer | Default | Deviate When |
|---|---|---|
| Backend | Python + FastAPI + Uvicorn | Node.js for web-adjacent workers |
| Frontend | Next.js 15 + React 19 + TypeScript + Tailwind | — always use this (saas-skeleton bumped 2026-06-18) |
| Database | PostgreSQL 16 (VPS, `postgres-main` container) | Self-host by default (see § Supabase below); Supabase only as a deliberate ADR-recorded exception |
| Background jobs | PostgreSQL jobs table + worker | Redis queue for high throughput |
| AI/LLM | Claude Max OAuth + OpenRouter subagent pool (Kilo CLI RETIRED 2026-07-19; direct API only for models not on OpenRouter) | Local Ollama for offline/free |
| Local LLM | Ollama (localhost:11434) | See `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` |
| Base images | `python:<current-stable>-slim-bookworm`, `node:<current-LTS>-bookworm-slim` | **Never** Alpine |
| PDF | Gotenberg (self-hosted) | WeasyPrint for simple cases |
| Search | MeiliSearch (self-hosted) | PostgreSQL FTS for simple cases |
| Notifications | Apprise (self-hosted) | Direct API for single-channel |
| Object storage | Backblaze B2 via Backrest (deployed 2026-04-17) | MinIO for self-hosted S3-compatible |

### Supabase — self-hosted by default (you don't need it)

Every Supabase capability has a first-party self-hosted equivalent; the one thing you don't self-host (realtime) is used **nowhere** on the fleet (zero hand-written usage as of 2026-07-03), and the lone runtime user (`trade-intelligence`) is migrating off it. Use Supabase **only as a deliberate, ADR-recorded exception** — never a silent default. New SaaS uses `fabrik-lib/fastapi-user-auth`, not Supabase auth.

| Supabase capability | Your self-hosted equivalent | Verdict |
|---|---|---|
| Postgres DB | `postgres-main` (PG16, shared, on the mesh) | ✅ fully replaced |
| End-user auth (JWT/email/social) | `fabrik-lib/fastapi-user-auth` — app issues its own JWTs: Argon2, refresh-token rotation, `jti` denylist, tenant-isolation RLS (56 tests; the default end-user auth for new SaaS) | ✅ replaced (Pattern A) |
| pgvector / vector search | `pgvector/pgvector:pg16` + `fabrik-lib/rag` (pgvector+tsvector+pg_trgm+RRF hybrid) | ✅ fully self-hosted |
| Object storage | `fabrik-lib/storage` (B2 backend, URI-routed) + Backblaze B2 via Backrest | ✅ replaced |
| Edge functions | container deploys via `fabrik apply` | ✅ different model, covered |
| Realtime subscriptions | `redis-main` pubsub — no drop-in "postgres-changes → websocket" product | ⚠️ not used anywhere on the fleet; build on Redis pubsub + WS/SSE only if a product ever needs it |

## Infrastructure Services — Running on VPS

| Service | URL | Purpose |
|---|---|---|
| PostgreSQL | (internal — `postgres-main`) | Shared database |
| Redis | (internal — `redis-main`) | Shared cache |
| Traefik | (internal — 80/443) | Reverse proxy (standalone, `/opt/traefik/`) + Let's Encrypt |
| Gatus | status.vps1.ocoron.com | Uptime monitoring (memory storage — see status.vps1.ocoron.com for live count) |
| GlitchTip | errors.vps1.ocoron.com | Error tracking (web + worker, Celery concurrency=2) |
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

Every compose service MUST declare `deploy.resources.limits.memory` to prevent OOM on the shared 12 GB VPS. This is enforced at deploy time by `deployer_ssh._validate_compose()` (fatal — blocks the deploy if missing) for template/docker sources. (`compose_linter.lint()` warns on missing `container_name` / `restart` / DB-without-healthcheck — the memory-limit check lives only in `_validate_compose()`.) Scaffolded compose files emit it automatically; hand-written or git-sourced composes must declare it themselves.

## Observability & Alerting

All monitoring services run as standalone Docker Compose stacks under `/opt/monitoring/` (Prometheus, Grafana, Alertmanager, Loki, Promtail, node-exporter, cAdvisor, Pushgateway). `/opt/prometheus/` was removed — the whole stack now lives under `/opt/monitoring/`. Local source: `specs/infrastructure/monitoring-stack.yaml` + `configs/` in Fabrik repo.

### Notification chains

```
Prometheus (rules) → Alertmanager → Telegram (native telegram_configs)
```

> Alertmanager uses its native `telegram_configs` receiver (same bot as Apprise).
> ARO Brain (LLM alert triage) is LIVE (fleet-wide since 2026-06-06): the `aro-wake-routed`
> receiver is routed BEFORE `telegram` (`continue: true`), with telegram as the fallback route.
> Apprise's stateless `/notify` endpoint does NOT accept Alertmanager's webhook
> schema — do not point AM at it.

```
Gatus (35 endpoints, growing — see status.vps1.ocoron.com) → Apprise (http://apprise:8000/notify/alerts) → Telegram
```

```
Authelia 2FA codes → filesystem (/config/notification.txt)
```

> Authelia SMTP is disabled (SES port 465 failed). Codes are written to a file; users grab them via `docker exec`.

### Alert Rules (13 total, across 2 rule files)

Source: `configs/prometheus/rules/alerts.yml` (12 rules) + `configs/prometheus/rules/fabrik-drift.yml` (1 rule).

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
| AroWakeLowSuccessRate | warning | aro-wake fix success rate low | 15m |
| AroWakeCostBurnHigh | warning | aro-wake LLM cost burn high | 10m |
| FabrikRegistrarDrift | warning | any registrar drift (`fabrik_audit_drift_total > 0`; in `fabrik-drift.yml`) | 10m |

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
| **iptables DOCKER-USER** | All Docker ports | Blocks external access to raw container ports. Only **80/443** serve traffic. (6001/6002 still have `RETURN` rules in the DOCKER-USER chain as stale Coolify Realtime/Soketi leftovers — UFW already clean, nothing listens on the host; iptables-side cleanup pending.) |
| **Authelia** | Admin dashboards w/o native TOTP | Forward-auth 2FA for n8n, Backrest, Apprise; + forward-auth with `^/api/` bypass for Grafana. **Note:** GlitchTip is on full-bypass — uses django-allauth app-layer TOTP (canonical Sentry pattern). Decision matrix: `docs/LESSONS_LEARNT.md §8.13`. |
| **X-Internal-Token** | API services | M2M auth via `internal_auth.py` + shared `SERVICE_INTERNAL_SECRET_KEY` in `/opt/fabrik/.env`, injected into each M2M **API** service's `/opt/<name>/.env` at deploy. Validation is constant-time (`hmac.compare_digest`). (Scaffold-emitted pattern — **no currently-deployed hub service uses it**: live-verified 2026-07-12, 0 of 11 `/opt/*/.env` carry the key; the live API surface is site-provisioner (IP-allowlist) + infra.) Implementation pack: `.windsurf/rules/core/35-security-auth.md`. |
| **Traefik** | Public sites | Routes traffic without auth for `ocoron.com`, `status.vps1.ocoron.com`. |

### Key security files on VPS

- `/etc/iptables/add-docker-user-rules.sh` — iptables rules
- `/etc/systemd/system/iptables-docker-user.service` — persistence
- `/opt/authelia/config/configuration.yml` — Authelia access control policies
- `/opt/authelia/compose.yaml` — Authelia Docker Compose
- `/opt/fabrik/.env` — `SERVICE_INTERNAL_SECRET_KEY`, `GRAFANA_ADMIN_PASSWORD`, etc.

**Authelia config changes:** Authelia exits on SIGHUP (no hot-reload). Restart procedure (discover container name, then restart): `.windsurf/rules/core/30-ops.md` § Authelia SSO. **Never** protect `/health` — the Authelia bypass is **resource-based, not domain-bound**: `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`).

### Exceptions to the canonical M2M pattern

- `file-api` (retired / not deployed — see § Fabrik Microservices) uses Supabase Bearer JWT (user auth, different pattern) in its template; no live service on the fleet uses this exception.
- `site-provisioner` uses Traefik IP allowlist (no app-level auth).

## Fabrik Microservices (Custom-Built)

**Live on VPS today:** only **site-provisioner**. The rest below are **retired / not deployed** (no container, no Traefik router on the fleet as of 2026-06-16) — port numbers are historical reservations, not running services. Do NOT plan against them as available internal APIs; if a project genuinely needs one, plan to (re)build + deploy it.

| Service | Port (reserved) | Status | Purpose |
|---|---|---|---|
| DNS Manager (site-provisioner) | 18014 | **LIVE** (`provision.vps1.ocoron.com`) | Domain registration, DNS (Namecheap / Cloudflare), SSL, CDN, analytics (GA4 / GSC), webmaster tools |
| Captcha | 18011 | retired / not deployed | Anti-Captcha solving |
| Translator | 18012 | retired / not deployed | DeepL + Azure translation |
| Proxy | 18013 | retired / not deployed | Webshare.io proxy management |
| File API | 18015 | retired / not deployed | File operations |
| Image Broker | 18016 | retired / not deployed | Stock image API (Pexels / Pixabay) with smart routing, scoring, caching |
| Email Gateway | 18017 | retired / not deployed | Resend + SES email sending |
| File Worker | 8007 | retired / not deployed | Background file processing worker |

### DNS Manager — Key Capabilities

DNS Manager (`provision.vps1.ocoron.com`) is the single gateway for all domain / DNS / provisioning operations. Fabrik calls it via the `fabrik domain` CLI or the `DNSClient` driver.

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

Under the SSH + Docker Compose model, **every compose service declares `container_name: <name>`** (enforced fatal by `deployer_ssh._validate_compose()` for template/docker sources; warned by `compose_linter`). Names are therefore stable across redeploys — Gatus endpoints and inter-service URLs key directly on the container name. The old Coolify single-image-Application alias workaround (timestamp-suffixed `<uuid>-<ts>` names) is **obsolete and removed**; live containers already use clean names (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.). **Docker network: `fabrik` (external bridge).** Every service joins it for Traefik routing. The network was renamed from `coolify` → `fabrik` on 2026-05-31; `fabrik apply` now rejects any compose still declaring the old `coolify` network.

## Active Projects

Full auto-generated project list: `docs/BUSINESS_MODEL.md` § Project Portfolio. Source of truth: `data/projects.yaml` (auto-synced by `scripts/sync_projects.py`).

---

## 🛑 MANDATORY ORCHESTRATOR PRE-FLIGHT

Run these checks before generating any plan, PRD, or execution spec.

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
7. **SSH + Docker Compose deployment** — `fabrik apply` SSHes to the target VPS (hub by default; spokes via spec field), writes `/opt/<name>/{compose.yaml,.env}`, and runs `docker compose up -d --wait`. No Coolify/PaaS layer. Compose must satisfy `deployer_ssh._validate_compose()` (platform `linux/amd64`, memory limit, `container_name`, no `ports:`, `fabrik` network external, websecure entrypoint). The deployer rejects composes still declaring the legacy `coolify` network.
8. **No Alpine** — `-slim-bookworm` base images only.
9. **Module dependencies** — if a project needs an incomplete Fabrik module, plan module completion first. Check module status in `docs/BUSINESS_MODEL.md`.
10. **DNS** — site-provisioner handles Namecheap + Cloudflare + domain purchasing automatically; don't plan around it manually.
11. **Scaffold immutability** — `fabrik scaffold` lays down a fixed project structure. Do NOT plan tickets that reorganize, flatten, or add top-level directories. Extend within the existing structure.
12. **State conflicts** — if a ticket scope contradicts existing project state (file exists, port taken, schema diverges), surface the conflict in the ticket explicitly. Coding agents are instructed to stop on contradictions, not silently overwrite.

---

## Rule Packs (canonical discipline — never restated here)

The 55 packs under `.windsurf/rules/**` ARE the discipline base `[canonical: the packs themselves]`.
Delivery is never "read this doc": **plan-time** — `python scripts/select_rules.py` prints the ACTIVE set
(glob-matched) + AVAILABLE; **review-time** — `python scripts/review_rubric.py --changed <paths>` injects
the matched mandates + the mandatory-core floor (`35-security-auth` + `25-data-postgres` + `30-ops` + the
twelve 12-Factor axes — not a pack; `review_rubric.py` emits them directly) into every finder (north-star § Enforcement Model). A pack fact quoted anywhere else is a copy —
the pack wins.

## Scaffold Types

Canonical entry point: `fabrik scaffold <name> --type <type>`. Creates the project tree AND emits `specs/services/<name>.yaml` with a populated `shape:` block per `templates/<type>/defaults.yaml`. The `shape:` block drives which infrastructure registrars run during `fabrik apply` (postgres / redis / gatus / backrest / glitchtip / grafana / authelia / meilisearch / prometheus). `fabrik new` is **deprecated** (hidden command; prints a deprecation warning at invocation; slated for removal in "the release after next"). Always plan against `fabrik scaffold`.

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
- **Coolify alias-watcher (REMOVED — do not plan around):** the `coolify.alias` / `CoolifyConfig` opt-in and `_maybe_register_coolify_alias()` write side live only in the archived `orchestrator/deployer_coolify.py` and are NOT on the active SSH deploy path. Under SSH + Docker Compose every container has a stable `container_name`, so no alias indirection is needed. The `coolify-alias-watcher.service` systemd unit + `/opt/coolify-alias-watcher/` directory are gone from all 3 hosts (verified 2026-06-18: no unit files, no service files, no directory).
- **Deploy-aware `data/projects.yaml` (T2-04 G-J1):** `scripts/sync_projects.py` now merges `.fabrik/state/<id>.json` into each project entry under a `deploy:` block (last_apply_status / last_apply_at / last_apply_sha / coolify_uuid / coolify_app_name / spec_path / registrars_applied). The `coolify_uuid` / `coolify_app_name` field names are retained for backward compat — under SSH+Compose `coolify_uuid` now holds the app/`container_name`, not a Coolify UUID. Projects with no state file show `last_apply_status: never`.
- **Local dev loop (T3-03 G-D3 + G-I1 + G-I2):** Stage 2 of the lifecycle stays in-WSL. `fabrik dev [-d]` runs `docker compose -f compose.dev.yaml up [-d]` in the project dir (fails clean if `compose.dev.yaml` missing). `fabrik logs --local [-f] [--service <name>]` tails the dev stack via `docker compose logs` (sibling of the Loki-backed `fabrik logs <service>` remote path — `--local` is opt-in, remote path unchanged). `fabrik review [--since HEAD] [--spec <path>] [--out <file>]` bundles `git diff` + spec + the project's `docs/preplan.md` + the resolved-registrar table into `.fabrik/review/<ts>.md` for human or Kilo-CLI reviewer dispatch. Helpers in `src/fabrik/dev_tools.py`. When planning tickets that change service behaviour, suggest `fabrik review` as the pre-PR step.
- **Postgres allocation registry (T4-01 G-J4):** `/opt/monitoring/configs/postgres/allocations.json` is the source of truth for "who owns each postgres DB on `postgres-main`" — `owner ∈ {fabrik, manual, infrastructure}`, `spec_id`, `user`, `notes`. Written atomically by `drivers/postgres.register_allocation` from `create_database` (and the symmetric `unregister_allocation` from `drop_database`). `audit_postgres` cross-references the registry against live `pg_database`, returning `status: drift` (new `AuditStatus` value) when registry and live state disagree. When planning a ticket that creates / renames / drops a postgres DB out-of-band, instruct the executor to update `allocations.json` (typically via `fabrik destroy --partial postgres` + `fabrik apply` rather than direct SQL).
- **State-driven destroy (T4-02 G-F4):** `fabrik destroy <spec> --use-state [-y] [--drop-data] [--keep-dns] [--keep-files] [--dry-run]` replays the registrar list from `.fabrik/state/<id>.json` (T2-01) instead of the current spec's shape. Three phases: (0) data-bearing guard refuses without `--drop-data` if state has any postgres/redis/meilisearch entry; (1) reverse `_REGISTRAR_ORDER` dispatch via T2-02's `HANDLER_FUNCS`+`HANDLER_ARGS` — `prometheus → meilisearch → authelia → glitchtip → backrest → gatus → redis → postgres` (grafana skipped); (2) compose app (`docker compose down` + `rm -rf /opt/<name>`) + dns (gated by `--keep-dns` + domain) + files (gated by `--keep-files`). On success, state archived to `_destroyed/<id>.json.<ts>`. **Mutually exclusive with `--partial`**. Use when planning teardown of a service whose spec has drifted between apply and destroy — the only way to guarantee no orphan registrars (e.g. meilisearch index after `has_search_feature` flipped to false). Function: `fabrik.orchestrator.destroyer.destroy_from_state`.
- **Cross-VPS portability bundle (T4-03 G-J2):** `fabrik export [-o|--out|--output <path>] [--include-data] [--skip-remote]` writes a tarball containing every resource the current VPS's `fabrik apply` ever registered — specs, `.fabrik/state/`, the per-service `/opt/<name>/{compose.yaml,.env-key-list}` (legacy builds also captured any residual Coolify Applications/Services/Projects with UUIDs recursively stripped), monitoring configs (prometheus/alertmanager/grafana dashboards/redis-assignments/postgres-allocations), Authelia + Backrest configs, redacted `.env` key list (key NAMES only — never values), and a restore README. `fabrik import <bundle> [--apply]` parses the bundle and emits a restore plan (default dry-run); `--apply` is honoured but the real-run API-write path is a documented stub — roundtrip was deferred at the time of write and is now superseded by the bootstrap-restore path (`bootstrap-spoke-restore.sh` + `bootstrap-hub.sh`, validated live across hub + spoke + spoke-restore drills 2026-06-15/16; see `docs/infrastructure/vps-complete-inventory.md`). Module: `src/fabrik/portability.py`. Security invariants (test-enforced in `tests/test_portability.py`): NO plaintext secrets, NO Coolify UUIDs, NO private-key references. When planning a portability or DR ticket, surface this command and the manual follow-ups it doesn't automate (LetsEncrypt re-issue, DNS re-bind, OAuth re-create, secrets re-populate).
- **Per-registrar drift alerting (T4-04 G-G5):** hourly WSL crontab runs `scripts/audit_all_registrars.py` → walks every spec → calls `fabrik.audit.audit_all` → emits Prom-text `fabrik_audit_drift_total{spec_id, registrar}` gauge to the VPS-local pushgateway (`prom/pushgateway:v1.9.0` at `127.0.0.1:9091` — NOT publicly exposed). Prometheus scrapes pushgateway (`honor_labels: true`); rule file `rules/fabrik-drift.yml` (alert `FabrikRegistrarDrift`, `for: 10m`, label `alert_class: registrar_drift`) → Alertmanager route under `route.routes:` matches that label → existing `telegram` receiver (NO new receiver — pack v3.2 V2-S4 rejected the proliferation). When planning tickets that touch any of the 9 drift-audited registrars (postgres / redis / gatus / backrest / glitchtip / grafana / authelia / meilisearch / prometheus — all of the 10 except `watchdog`, which carries no registrar state to drift) drift detection auto-fires within ~1 hour. Companion `fabrik_audit_status{spec_id, registrar, status}` gauge for Grafana per-status charts.
- **SSH deploy mechanics (replaces the old Coolify v4 workarounds):** the active deployer is `orchestrator/deployer_ssh.py`. It writes `compose.yaml` + `.env` to `/opt/<name>/` via SCP (scp-to-tmp-then-`sudo mv`), then runs `sudo docker compose up -d --wait` (git sources also run `sudo docker compose build` first). Git-sourced redeploys capture the current commit and auto-revert via `git reset --hard` on health-check failure; non-git sources fail loudly with no auto-revert. No PaaS grace period — first-deploy time is just `git clone` + image build. The legacy `deployer_coolify.py` (SSH-fallback-build, `.env` pre-seed, `get_deployments` workarounds for Coolify v4.0.0-beta.459 bugs) is archived and off the active path.

| Type | Template | Stack | shape.kind | shape flags (true only) |
|---|---|---|---|---|
| python-api | `templates/scaffold/` | FastAPI + Uvicorn + Docker | service | is_public, exposes_metrics |
| python-api-gpu | `templates/python-api-gpu/` | FastAPI + Uvicorn + on-demand GPU rental (`gpu_rent`) | service | is_public, exposes_metrics |
| saas-skeleton | `templates/saas-skeleton/` | Next.js 15 + React 19 + TypeScript + Tailwind | service | is_public, has_bearer_api, has_persistent_data, needs_database, needs_cache, exposes_metrics |
| node-api | `templates/node-api/` | Node.js API + Docker | service | is_public, exposes_metrics |
| file-api | `templates/file-api/` | File operations API | service | is_public, has_persistent_data |
| file-worker | `templates/file-worker/` | Background file worker | worker | has_persistent_data |
| wordpress | **scaffold path retired 2026-06-17** (commit `ef27a2c`) — `fabrik scaffold --type wordpress` now redirects to the standalone `/opt/wpf` project (use `wpf new <name>` instead). `wordpress` remains a recognised deploy/shape **type** (`Kind.WORDPRESS`, rule-pack mapping, registrar applicability) — only the Fabrik-side template/scaffolder is gone. | WordPress + WP-CLI (via `wpf`) | wordpress | is_public, has_persistent_data, needs_database |
| docusaurus | `templates/docusaurus/` | Documentation site | static | is_public |
| chrome-extension | `templates/chrome-extension/` | Chrome extension + Python backend | service | (none true; Python backend deploys, CRX ships separately) |
| mobile-app | `templates/mobile-app/` | React Native | service | (none true; companion backend deploys, app ships via stores) |
| desktop-app | `templates/desktop-app/` | Electron | service | (none true; companion backend deploys, installer ships separately) |
| static-site | `templates/static-site/` | Next.js / static HTML | static | is_public |

> Each scaffold propagates `.windsurfrules`, `.windsurf/rules/` (with subdirectory structure: `core/`, `saas/`, `mobile-app/`, `chrome-ext/`, `desktop-app/`, `ai/` (all six registry subdirs)), and `.windsurf/workflows/` to generated projects automatically.
> **Authoritative shape matrix:** `src/fabrik/spec_loader.py::Shape` docstring. Change it there, then run the full scaffold suite — divergence from `templates/<type>/defaults.yaml` is a failing test (`tests/test_spec_generator.py`).
> **Registrar applicability matrix:** `src/fabrik/orchestrator/infrastructure.py` docstring + `resolve_applicability()`. Source of truth for which of (postgres / redis / gatus / backrest / glitchtip / grafana / authelia / meilisearch / prometheus) runs for a given `shape:` block.

### What every API scaffold emits automatically (no manual ticket needed)

Do NOT plan tickets to manually add any of these — `fabrik scaffold` (`python-api`, `node-api`) writes them on creation (the JS `file-api` scaffold differs — Supabase Bearer JWT instead of `internal_auth`, and no `/metrics`):

- `internal_auth.py` — M2M auth module (`X-Internal-Token` validation via `hmac.compare_digest`).
- `metrics.py` — Prometheus business metrics (`REQUEST_COUNT`, `ERROR_COUNT`, `ACTIVE_JOBS`, `PROCESSING_COUNT`).
- `/metrics` endpoint — mounted in `main.py`, Authelia-bypassed.
- `glitchtip_init.py` / `glitchtip_init.js` — Sentry SDK init pointed at GlitchTip; no-op if `GLITCHTIP_DSN` env unset. Wired in `main.py` BEFORE app construction.
- `SERVICE_INTERNAL_SECRET_KEY` line in `.env.example`.
- Structured-logging module (`logger.py` / `logger.js`) with JSON output + `SERVICE_NAME` from env.

If a ticket appears to need these, the existing scaffolded code already covers it — plan against extending, not duplicating.

---

## Quality Gates

`python scripts/final_gate.py --json` (Tier-2 FULL) is the completion gate; `--lean` is iteration-only `[canonical: CLAUDE.md § Completion Contract · docs/workflows/FINAL_GATE_WORKFLOW.md]`.

## Implementation Detail Pointers

Our agents plan against these rules but do NOT inline them into tickets — the coding agents already load them via their bootstrap + packs:

- **Python / FastAPI / config / temp files** → `.windsurf/rules/core/10-python.md`
- **Docker / compose / `fabrik` Docker network (external bridge; renamed from `coolify` on 2026-05-31) / Authelia restart procedure / post-deploy checklist / `fabrik redeploy` sequence** → `.windsurf/rules/core/30-ops.md`
- **M2M auth (`X-Internal-Token` / `internal_auth.py`) / sensitive data backup / password policy / JWT / CORS / CSP** → `.windsurf/rules/core/35-security-auth.md`
- **Pre-scaffolded logging / GlitchTip discipline / health endpoints / Gatus stable DNS rule** → `.windsurf/rules/core/55-observability.md`
- **Documentation rules (CHANGELOG, README features, plans, `.env.example`, new-`.md`-file allowlist, writing style)** → `.windsurf/rules/core/40-documentation.md`
- **Responsive design testing (Playwright, screenshots, fix patterns, agent directive)** → `docs/reference/mobile-responsive-testing-guide.md`

## Reference Documents

| Document | Path | Use When |
|---|---|---|
| Project Portfolio | `docs/BUSINESS_MODEL.md` | Full project list, statuses, duplicate-check |
| AI Capability Packs | `.windsurf/rules/ai/` (11 packs) | Selecting AI tools / models for a ticket |
| Local LLM Infrastructure | `docs/reference/LOCAL_LLM_INFRASTRUCTURE.md` | Ollama setup, agent → model assignments |
| Stack Decision Guide | `docs/reference/technology-stack-decision-guide.md` | Choosing tech stack for new project |
| Prebuilt Containers | `docs/reference/prebuilt-app-containers.md` | Avoid writing custom code when a container exists |
| Database & Vector Strategy | `.windsurf/rules/core/25-data-postgres.md` + `core/65-rag-search.md` | PostgreSQL host selection, migrations, pgvector, hybrid search |
| Owner Profile | `docs/owner_ozgur_basak.md` | Calibrating tone / framing for planning output |
| Port Allocations | `PORTS.md` | Assigning ports to new services |
| SaaS UI Patterns | `docs/reference/research/Modern GUI Approaches for a Lean, Fast, Effective, Low-Confusion SaaS Web App.md` | Planning SaaS frontend |
| Chrome Extension UI | `docs/reference/research/Modern GUI Approaches for Chrome Extensions.md` | Planning Chrome extensions |
| Mobile UI | `docs/reference/research/Modern Mobile GUI Approaches for Android and iOS.md` | Planning mobile apps |
| Ocoron Design System | `.windsurf/rules/core/ocoron-design-system.md` | Visual + verbal identity for UI projects |
| Ocoron Mobile Design | `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md` | Mobile component patterns (list items, sheets, navigation, forms) |
| Mobile Responsive Testing | `docs/reference/mobile-responsive-testing-guide.md` | Single source of truth for RWD testing (Playwright, screenshots, fix patterns) |
| Deployment Architecture | `docs/DEPLOYMENT_ARCHITECTURE.md` | Code-level map of every file on the SSH+Compose deploy path |
| Deployment Procedures | `docs/operations/deployment.md` | `fabrik apply` / `redeploy` / `destroy` workflows + golden rules |
| Fabrik Lifecycle | `docs/operations/fabrik-lifecycle.md` | Runtime behavior, data safety, downtime, `.env` merge |
| Subagent Selection (pool) | `docs/reference/kilo/KILO_AGENT_SELECTION_GUIDE.md` | Model routing, quality floors, current roster (auto-generated daily) |
| Kilo Agent Registry | `scripts/kilo_47_agents_final.json` | Authoritative agent selection list |
| AI Prompt Templates | `docs/reference/MD/ai-prompt-templates.md` | Designing system prompts, skills, AGENTS.md, review templates |
| RAG Chunking Rules | `.windsurf/rules/core/66-rag-chunking.md` | Planning search/RAG features — heading-based splitting, chunk envelopes |
| Markdown AI Rules | `docs/reference/MD/markdown-cheatsheet.md` | AI-friendly markdown writing conventions |
| GPU Workers Guide | `.windsurf/rules/core/76-gpu-workers.md` | GPU cloud decisions — when to self-host vs managed API, provider selection |
| Lessons Learnt | `docs/LESSONS_LEARNT.md` | Past incidents, decisions, anti-patterns |
| epic-to-ticket-workflow | `docs/orchestrator/epic-to-ticket-workflow/` (`-fabrik` files; `docs/traycer/` twins are ARCHIVED reference) | Single-epic planning + execution (00-11); also the per-epic execution engine in mega-epic runs |
| mega-epic-breakdown | `docs/orchestrator/mega-epic-breakdown/` (`-fabrik` files; `docs/traycer/` twins are ARCHIVED reference) | Large vision → epics → tickets → dispatch (4 active commands — 05 retired); `00-trigger` is the single entry serving both new and existing projects (owner declares mode at Step 0) |
