# Fabrik Architecture

**Last Updated:** 2026-04-22

---

## Overview

Fabrik is a **spec-driven, shape-gated deployment automation CLI**. You write a YAML spec describing what you want deployed; the orchestrator runs a state machine that provisions Coolify + Traefik + every relevant registrar (Postgres, Gatus, Backrest, GlitchTip, Grafana, Authelia, MeiliSearch) and verifies the result — all atomic, with automatic rollback on failure.

**Entry point of truth:** `docs/DEPLOYMENT.md` — single canonical reference. This file is the quick architectural map.

---

## High-Level Pipeline

```text
fabrik scaffold <name> --type <t>         →  /opt/<name>/ tree + spec
                                             +
fabrik apply <spec> | fabrik deploy       →  DeploymentOrchestrator state machine:

    PENDING → VALIDATING → PROVISIONING → DEPLOYING → VERIFYING → COMPLETE
                   ↓            ↓            ↓            ↓
                 FAILED  ←  ROLLING_BACK  ←  ROLLING_BACK  ←  ROLLING_BACK
                                              ↓
                                        ROLLED_BACK
```

Each transition invokes a specific module; each module only talks to one external system via a single driver.

---

## Layered Components

### 1. Spec layer — `src/fabrik/spec_loader.py`

Pydantic models with `model_config = {"extra": "forbid"}`.

Key classes: `Spec`, `Shape`, `Source`, `Expose`, `Resources`, `Health`, `Volume`, `Backup`, `SecretsPolicy`, `CoolifyConfig`, `Depends`, `Infrastructure`, `WordPressConfig`.

**The `Shape` model drives everything downstream.** Shape flags (`is_public`, `is_admin_dashboard`, `has_bearer_api`, `has_persistent_data`, `needs_database`, `has_search_feature`) decide which registrars run.

### 2. Template layer — `src/fabrik/template_renderer.py` + `templates/`

Jinja2-rendered `compose.yaml` + `Dockerfile` + auxiliary files per template type. **12 deploy templates** (11 also exposed as `fabrik scaffold --type` options; `next-tailwind` is deploy-only): python-api, node-api, saas-skeleton, static-site, wordpress, docusaurus, file-api, file-worker, chrome-extension, desktop-app, mobile-app, next-tailwind.

Each template has `defaults.yaml` declaring its default shape flags.

### 3. Orchestrator — `src/fabrik/orchestrator/`

11 modules, 3102 lines total (2026-04-22, includes 613-line `content_publisher.py` which is not on the deploy path). Stage-by-stage pipeline with a state machine:

| Module | Role |
|---|---|
| `__init__.py` | `DeploymentOrchestrator` — top-level runner + rollback wiring |
| `states.py` | State enum + illegal-transition guard |
| `context.py` | `DeploymentContext` — shared state, resource log for rollback |
| `validator.py` | Pydantic validation + SSRF check + idempotency hash |
| `secrets.py` | `SecretsManager` — CSPRNG generate, `-s` > project `.env` > fabrik `.env` > env |
| `deployer.py` | `ServiceDeployer` — idempotent Coolify create/update + deploy(force=True) |
| `infrastructure.py` | **`InfrastructureProvisioner`** — shape-driven registrar dispatch |
| `verifier.py` | HTTP 200, DNS, SSL, SENTRY_DSN injection (via `docker inspect`) |
| `rollback.py` | `RollbackManager` — LIFO cleanup; DB drops logged, not auto-executed |
| `exceptions.py` | Typed exceptions |
| `content_publisher.py` | **Not deploy** — SEO→TCO→Image→WordPress pipeline |

### 4. Drivers — `src/fabrik/drivers/` (22 modules)

Every external call goes through a driver. No ad-hoc HTTP or SSH allowed in CLI/orchestrator code.

| Category | Drivers |
|---|---|
| **VPS primitives** | `ssh.py`, `locks.py` |
| **Coolify + networking** | `coolify.py`, `compose_updater.py`, `preflight.py`, `dns.py`, `cloudflare.py` |
| **Shape-gated registrars** | `postgres.py`, `gatus.py`, `backrest.py`, `glitchtip.py`, `grafana.py`, `authelia.py`, `meilisearch.py` |
| **Optional infra** | `supabase.py`, `r2.py` |
| **WordPress** | `wordpress.py`, `wordpress_api.py` |
| **Content pipeline** | `image_broker.py`, `seo.py`, `tco.py` |
| **Legacy** | `uptime_kuma.py` (superseded by Gatus) |

See `docs/reference/drivers.md` for shape gates and usage.

### 5. CLI — `src/fabrik/cli.py` (2048 lines)

Click-based. 22 top-level commands. See `docs/reference/fabrik-cli-reference.md`.

### 6. Supporting modules

| File | Role |
|---|---|
| `deploy_router.py` | `route_deploy(project_path)` — WordPress vs. service pipeline dispatch |
| `deploy_validator.py` | Scaffold-level readiness (Dockerfile, `.env`, healthcheck, platform) |
| `compose_linter.py` | Coolify compatibility: no public ports, amd64 platform, coolify network |
| `registry.py` | `ProjectRegistry` → `/opt/fabrik/data/projects.yaml` |
| `provisioner.py` | Saga for brand-new-site setup (domain → DNS → Coolify bootstrap) |
| `verify.py` | `PostconditionChecker` framework for declarative post-deploy checks |

---

## Data Flow Example

```text
User: fabrik deploy --project /opt/my-api

  1. deploy_router reads /opt/my-api/project.yaml → routes to service pipeline
  2. DeploymentOrchestrator.deploy(spec_path)
     a. SpecValidator.validate() + SSRF check + spec_hash
     b. deploy_validator (scaffold readiness warnings)
     c. SecretsManager.load() — project .env merged with fabrik .env
     d. DNSClient.add_record(domain, VPS_IP)              [if --skip-dns not set]
     e. TemplateRenderer.render() + ComposeLinter.lint()
     f. ServiceDeployer — Coolify PATCH+deploy or POST+deploy
     g. InfrastructureProvisioner.provision(ctx)          [SHAPE-GATED]:
          postgres.create_database()      if needs_database
          gatus.add_endpoint()            if is_public + domain
          backrest.add_backup_plan()      if has_persistent_data
          glitchtip.create_project() + verify_dsn_injection()
                                          if shape.kind in service|worker|wordpress
          grafana.post_deployment_annotation()            always
          authelia.add_access_rule()      if is_admin_dashboard + domain
          authelia.add_access_rule(^/api/ bypass, insert_before_twofactor=True)
                                          if has_bearer_api
          meilisearch.create_index()      if has_search_feature
     h. DeploymentVerifier — HTTP 200, DNS, SSL, SENTRY_DSN via docker inspect
  3. Any exception → RollbackManager.rollback(ctx) — LIFO cleanup
  4. Success → print deployed URL, exit 0
```

Expected wall time for maximal shape (all flags true, scratch image): **~63s** (measured 2026-04-22, see `docs/DEPLOYMENT.md` §9.6).

---

## Spec File Example (maximal shape)

```yaml
id: my-api
kind: service
template: python-api
domain: my-api.vps1.ocoron.com

shape:
  kind: service
  is_public: true            # → Gatus endpoint
  is_admin_dashboard: true   # → Authelia forward-auth
  has_bearer_api: true       # → Authelia ^/api/ bypass
  has_persistent_data: true  # → Backrest backup
  needs_database: true       # → Postgres DB
  has_search_feature: true   # → MeiliSearch index

source: {type: docker, image: my/image:tag, image_port: 8000}
coolify: {project: default, server: localhost}
env: {LOG_LEVEL: INFO}
resources: {memory: 512M, cpu: '1'}
health: {path: /health, disabled: false}
backup: {enabled: true, frequency: daily, retention: 30}
```

---

## Directory Structure

**Last verified:** 2026-05-19

### Source code

```text
src/fabrik/
├── cli.py                     # Click CLI — 22 commands (plan, apply, destroy, scaffold, verify, audit, etc.)
├── main.py                    # Entry point (fabrik.cli:main)
├── health_app.py              # FastAPI health endpoint (checks Coolify + DNS manager)
├── spec_loader.py             # Pydantic Spec + Shape models
├── spec_generator.py          # Spec emission from scaffold context
├── template_renderer.py       # Jinja2 compose/Dockerfile rendering + ComposeLinter hook
├── scaffold.py                # fabrik scaffold — 11 types, .droid/ creation, AI guardrail emission
├── deploy.py                  # deploy_to_coolify() core function
├── deploy_router.py           # project-type dispatch (WordPress raises NotImplementedError — moved to /opt/wpf/)
├── deploy_validator.py        # scaffold-level readiness checks
├── compose_linter.py          # Coolify-compat: no public ports, amd64, coolify network
├── config.py                  # FABRIK_ROOT, ensure_directories
├── registry.py                # ProjectRegistry → data/projects.yaml
├── provisioner.py             # SiteProvisioner — 15-state saga for new site bootstrap
├── state.py                   # .fabrik/state/<id>.json — 8-field deploy manifest
├── locks_local.py             # File-based lock preventing concurrent applies
├── verify.py                  # PostconditionChecker framework
├── audit.py                   # Registrar drift detection (one auditor per registrar)
├── portability.py             # fabrik export/import — UUID-stripped tarball
├── monitor.py                 # Health monitoring
├── notifications.py           # Deploy success/failure notifications
├── preplan.py                 # fabrik preplan new — 9-section intent capture
├── dev_tools.py               # fabrik dev / fabrik review / fabrik logs --local
├── orchestrator/              # 11 modules — deployment state machine
│   ├── __init__.py            #   DeploymentOrchestrator — top-level runner
│   ├── deployer.py            #   ServiceDeployer — Coolify create/update/deploy
│   ├── infrastructure.py      #   InfrastructureProvisioner — 9 shape-gated registrars
│   ├── rollback.py            #   RollbackManager — LIFO cleanup
│   ├── secrets.py             #   SecretsManager — CSPRNG + env precedence
│   ├── verifier.py            #   HTTP 200, DNS, SSL, SENTRY_DSN injection
│   ├── destroyer.py           #   Reverse-order registrar teardown + state-driven destroy
│   ├── validator.py           #   Pydantic validation + SSRF check
│   ├── context.py             #   DeploymentContext — shared state for rollback
│   ├── states.py              #   State enum + transition guard
│   ├── coolify_alias.py       #   Stable Docker network alias management
│   └── exceptions.py          #   Typed exceptions
├── drivers/                   # 22+ modules — every external call goes through a driver
│   ├── coolify.py             #   CoolifyClient — API wrapper
│   ├── postgres.py            #   CREATE DATABASE via SSH
│   ├── redis.py               #   Cache index assignment via assignments.json
│   ├── gatus.py               #   Health monitor endpoint YAML emission
│   ├── backrest.py            #   Restic backup plan registration → B2
│   ├── glitchtip.py           #   Error tracking project + DSN
│   ├── grafana.py             #   Dashboard annotation
│   ├── authelia.py            #   Forward-auth rule management
│   ├── meilisearch.py         #   Search index creation
│   ├── prometheus.py          #   Scrape target registration
│   ├── cloudflare.py          #   DNS + WAF via Cloudflare API
│   ├── dns.py                 #   DNSClient — site-provisioner wrapper
│   ├── ssh.py                 #   SSH command execution
│   ├── locks.py               #   Distributed locking
│   ├── compose_updater.py     #   Live compose patching
│   ├── preflight.py           #   Pre-deploy readiness checks
│   ├── r2.py                  #   Cloudflare R2 storage
│   ├── supabase.py            #   Supabase integration
│   ├── image_broker.py        #   Stock image API
│   ├── seo.py                 #   SEO service client
│   ├── tco.py                 #   Content orchestration client
│   └── uptime_kuma.py         #   Legacy (superseded by Gatus)
├── ai/                        # LLM client + cost tracking
│   ├── client.py              #   LLMClient (Claude/OpenAI) with pricing
│   └── tracker.py             #   UsageTracker — SQLite ai_usage.db
├── api/                       # Empty — reserved for future fabrik HTTP API
├── models/                    # Empty — reserved
├── services/                  # Empty — reserved
└── utils/                     # Empty — reserved
```

### Runtime directories (dot-folders)

| Directory | Purpose | Persistent? | Git-tracked? |
|-----------|---------|-------------|-------------|
| `.fabrik/state/` | Deploy state store — 8-field JSON manifest per `fabrik apply`. Feeds destroy, audit, export, verify. `_destroyed/` subdir archives teardown state. | Yes | No (gitignored) |
| `.fabrik/review/` | Review bundles from `fabrik review` — diff + spec + registrars | No (ephemeral) | No |
| `.droid/review-context/` | Task/plan `.md` files passed to Kilo `--plan` flag | Yes | **Yes** (git-tracked) |
| `.droid/traycer-reports/` | Traycer analysis reports after dispatched sessions | Yes | **Yes** (git-tracked) |
| `.droid/transcripts/` | Raw terminal output from each Kilo agent session | Yes | No |
| `.droid/consultations/` | Multi-model architecture consultation JSON | Yes | No |
| `.droid/responses/` | Cross-model gap analysis results | Yes | No |
| `.droid/docs_log/` + `docs_queue/` | Docs enforcer state (generated/pending) | Yes | No |
| `.droid/dev_tracker.db` | SQLite — gate results, review costs, workflow events | Yes | No |
| `.droid/kilo_usage.jsonl` | Token counts + cost per Kilo review invocation | Yes | No |
| `.droid/kilo_model_sync.log` | Daily cron model availability sync (active) | Yes | No |
| `.kilo/` | Kilo Code VSCode/Windsurf extension runtime — `@kilocode/plugin` + `node_modules` (58MB) + implementation plans in `plans/` | Yes | No (gitignored) |
| `.vscode/` | VS Code settings — disables `.env` loading in Python terminal (2 settings) | Yes | Yes |
| `.windsurf/rules/` | 21 Cascade AI behavior rule packs (10-python, 30-ops, 35-security, etc.) — the convention enforcement rules referenced in CLAUDE.md | Yes | Yes |
| `.windsurf/workflows/` | 11 Cascade workflow definitions (auto-review, bug-fix, deploy, kilo, new-feature, etc.) | Yes | Yes |
| `.windsurf/hooks.json` | Post-write hooks — runs `validate_conventions` + `check_secrets` after every Cascade code write | Yes | Yes |
| `.mypy_cache/` | mypy type-check cache (142MB) — regenerated by Final Gate Phase 2 | No (cache) | No |
| `.pytest_cache/` | pytest cache (188KB) | No (cache) | No |
| `.ruff_cache/` | ruff linter cache (412KB) | No (cache) | No |

### Other root directories

| Directory | Purpose | Status |
|-----------|---------|--------|
| `apps/` | **Legacy deploy convention** — compose files for services deployed before the spec-driven pipeline. `postgres-main/` and `fabrik-proxy/` are active running services; `example-api/` is an obsolete template | Partially active |
| `backups/` | Credential/config backups (gitignored). Target for CLAUDE.md backup rule: `cp <f> backups/<f>.backup.$(date)`. Created by scaffold for all project types | Active |
| `build/` | **Moved to `/opt/wpf/build/`** (May 2026). Was WordPress deployer output (`build/sites/<site>/plan.json`, manifests, reports) | Moved |
| `config/` | `platform.yaml.example` — config schema reference for VPS/Coolify/DNS/backup settings. Referenced by `src/fabrik/config.py` as `CONFIG_DIR` | Active (example only) |
| `configs/` | **Repo-local source of VPS monitoring configs.** Prometheus scrape config + 9 alert rules, Alertmanager routing, 5 Grafana dashboards + provisioning, Loki + Promtail configs, monitoring-compose.yaml, n8n workflows (backup notification, uptime alert). Bundled by `portability.py` in `fabrik export`. Deployed to `/opt/monitoring/configs/` on VPS | Active |
| `data/` | `projects.yaml` (project registry) + `provision-jobs/` (SiteProvisioner saga state) | Active |
| `docs/` | `DEPLOYMENT.md` (canonical deploy reference), `FEATURES.md`, `LESSONS_LEARNT.md`, `reference/` (this file + excel-file-generation.md, multilingual-plan.md), `traycer/` (workflow docs + agent test reports), `development/plans/` (archived + active plans), `guides/` (empty — scaffold creates for projects) | Active |
| `scripts/` | `final_gate.py`, `enforcement/` (19 checks), `kilo_code_review.py`, `kilo_consult.py`, `kilo_model_sync.py`, `dev_tracker.py`, `docs_updater.py`, Traycer agent scripts, `kilo-benchmarks/` (model evaluation) | Active |
| `specs/services/` | Per-app deployment specs (~52 YAML files, mix of real services + scaffold test specs) | Active |
| `specs/sites/` | WordPress site specs (ocoron.com) — consumed by wpf, not fabrik | Active (wpf) |
| `templates/` | 12 deploy templates (11 scaffold-exposed + next-tailwind deploy-only). Each has `defaults.yaml` with default shape flags | Active |
| `templates/i18n-kit/` | Multi-platform i18n template (20 files). Vanilla DOM loader, React/Next.js provider, Chrome/RN/Docusaurus adapters, 3-level Kilo validator with step_finish + _context.json, multilingual plan doc. Auto-provisioned by `_provision_i18n()` in scaffold.py for 6 GUI types | Active |
| `examples/` | **Removed** (May 2026). Had one Traycer agent review example script — pattern already documented in `docs/traycer/` and the actual script at `scripts/traycer_agent_review.py` | Removed |
| `scripts/sysadmin/` | VPS AI sysadmin (1136 lines, 7 files): `bot.py` (Telegram→Claude Opus, session management, action log, health endpoint), `proactive-check.sh` (15-min cron, 11 checks + cert expiry), `morning-report.sh` (daily briefing), `weekly-security.sh` (Monday patrol vs audit checklist), `weekly-maintenance.sh` (Sunday cleanup report), `monthly-backup-verify.sh` (backup audit), `system-prompt.txt` (232-line brain: APIs, playbooks, criticality tiers, communication protocol, shift notes). Systemd service on VPS. Cron: `/etc/cron.d/vps-sysadmin`. Reference: `docs/infrastructure/vps-ai-sysadmin.md` | Active (VPS) |
| `scripts/audit/` | 7 VPS diagnostic scripts for systematic health audits: full-system, container-health, security, performance, observability, backup, hardening-verify. Run with sudo on VPS. Paired with `docs/infrastructure/audit-prompts/` (9 analysis checklists). Used by sysadmin bot and manual audits. | Active (VPS + WSL) |
| `ops/` | VPS operational files: `vps-sysadmin-bot.service` (systemd unit for the Telegram bot). Deployed to `/etc/systemd/system/` on VPS. | Active |
| `tests/` | Orchestrator tests (144), driver tests (331), scaffold tests, enforcement tests | Active |

### WordPress — extracted to /opt/wpf/

The WordPress automation engine (~9,700 LoC: 13-stage deployer, planner, preset loader, WP-CLI driver, REST API client, theme/page/SEO/analytics/forms modules) was built as fabrik Phase 2 and extracted to `/opt/wpf/` in May 2026. `deploy_router.py` raises `NotImplementedError` for WordPress deploys. WordPress scaffold type still exists for project structure generation. Site specs at `specs/sites/` have `kind: wordpress` and are consumed by `wpf wp apply`, not `fabrik apply`. wpf calls the same VPS drivers (Coolify, Backrest, Gatus, site-provisioner) but manages WordPress site lifecycle independently.

---

## External surface (VPS)

| Layer | Service |
|---|---|
| **Control plane** | Coolify (`coolify.vps1.ocoron.com`) |
| **Reverse proxy** | Traefik (managed by Coolify) — 80/443 only |
| **Auth** | Authelia forward-auth (`auth.vps1.ocoron.com`) for admin dashboards without native TOTP |
| **Data** | `postgres-main` (shared), `redis-main` (shared), Backblaze B2 (via Backrest) |
| **Observability** | Prometheus + Grafana + Alertmanager + Loki + Promtail; GlitchTip (errors); Gatus (uptime); Apprise (notifications) |
| **Search / PDF / Browser** | MeiliSearch, Gotenberg, Browserless (all internal APIs) |
| **DNS** | site-provisioner service (`dns.vps1.ocoron.com`) → Namecheap + Cloudflare |

Full inventory in `docs/infrastructure/vps-complete-inventory.md` and `AGENTS.md`.

---

## Security model (4-layer)

| Layer | Target |
|---|---|
| **iptables DOCKER-USER** | Only 80/443/6001/6002 public; Docker bypasses UFW |
| **Authelia** | 2FA forward-auth for admin dashboards w/o native TOTP |
| **X-Internal-Token** | Machine-to-machine auth for internal microservices |
| **Bearer tokens** | API endpoints on admin dashboards (Coolify, Grafana, GlitchTip) |

Details: `docs/DEPLOYMENT.md` §8.4.

---

## Related

- [DEPLOYMENT.md](../DEPLOYMENT.md) — the canonical deploy reference (§1–11)
- [Orchestrator](orchestrator.md)
- [Drivers](drivers.md)
- [CLI Reference](fabrik-cli-reference.md)
- [Templates](templates.md)
- [LESSONS_LEARNT.md](../LESSONS_LEARNT.md) — every live-incident invariant
- [AGENTS.md](../../AGENTS.md) — Fabrik identity + tech stack + VPS inventory
