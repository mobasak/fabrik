# You run this yourself in WSL — takes seconds
fabrik apply specs/services/myapp.yaml      # provision infra + deploy
fabrik redeploy fabrik-myapp                # redeploy
fabrik destroy specs/services/myapp.yaml    # teardown
fabrik vps-sync --verify                    # confirm clean

# Deployment — Canonical Reference

**Purpose:** this file is the **single entry point** any AI coder or human operator reads to understand how Fabrik deploys services to the VPS. Every file involved in a deploy is cataloged below with its function and cross-references. If you are about to touch deployment behavior, **read this file end-to-end first**.

**Last Updated:** 2026-05-07 (§11.x added — 2026-05-06/07 lessons; §7.4 prometheus retention; §8.4 M2M auth; §10.4 canonical env vars).10 added — template-defaults registrar matrix, derived from live defaults.yaml HEAD).
Previous: 2026-05-06 (§9.9 G4/G5 marked closed — Redis `needs_cache` and Prometheus `exposes_metrics` registrars are live with drivers, applicability resolution, and provisioner methods. Template-defaults audit: chrome-extension/desktop-app/mobile-app `defaults.yaml` flipped from `kind: static` to `kind: service` so their scaffolded backends get GlitchTip; `next-tailwind/defaults.yaml` gained an explicit shape block (`is_public: true`) so Gatus auto-registers. Regression tests: `@/opt/fabrik/tests/orchestrator/test_template_defaults.py` (14 tests covering all 12 scaffold templates). Previous: 2026-05-05 — §2.1, §9.2, §9.3, §9.4 resynced with `cli.py` after G1/G2/G3/G7 closures. 2026-05-04 — initial §9.2 per-command factual pipeline tables + §9.9 infra-coverage matrix. 2026-04-28 — live-deploy proof for all 7 deployable scaffold types — see `@/opt/fabrik/PROOF.md`. 2026-04-22 — maximal-shape e2e on `python-api`, ~63s wall time, all 7 registrars green — see `_REGISTRAR_ORDER` in `src/fabrik/orchestrator/infrastructure.py`.)
**Backup of prior version:** `docs/archive/2026-04-28-DEPLOYMENT.md.backup.20260419-144040` (pre-rewrite)

## Table of Contents

1. [High-Level Flow](#1-high-level-flow)
2. [Fabrik Source Code — Deployment Path](#2-fabrik-source-code--deployment-path)
3. [Specs](#3-specs)
4. [Templates](#4-templates)
5. [Local Config Mirrors (`configs/`)](#5-local-config-mirrors-configs)
6. [Probes & Enforcement Scripts](#6-probes--enforcement-scripts)
7. [VPS-Side Files & Services](#7-vps-side-files--services)
8. [VPS Infrastructure Invariants](#8-vps-infrastructure-invariants)
9. [Deployment Flows (step-by-step)](#9-deployment-flows-step-by-step)
10. [Secrets & `.env`](#10-secrets--env)
11. [Key Invariants Summary (from LESSONS_LEARNT)](#11-key-invariants-summary-from-lessons_learnt)

---

## 1. High-Level Flow

```text
┌──────────────────────────────────────────────────────────────────────────┐
│  fabrik scaffold <name> --type <template>                                │
│    → creates /opt/<name>/ tree from templates/<type>/                    │
│    → emits spec at specs/services/<name>.yaml                            │
│    → allocates port in PORTS.md                                          │
└──────────────────────────────────────────────────────────────────────────┘
                         │  (user fills .env, commits, pushes to GitHub)
                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  fabrik apply specs/services/<name>.yaml  (--dry-run optional)          │
│                                                                          │
│   1. SpecValidator          (orchestrator/validator.py)                  │
│   2. deploy_validator.py    (readiness: Dockerfile, .env, healthcheck)   │
│   3. SecretsManager         (env → .env → -s flags, CSPRNG generate)     │
│   4. DNSClient              (drivers/dns.py → site-provisioner)          │
│   5. TemplateRenderer       (compose.yaml + Dockerfile from templates/)  │
│   6. ComposeLinter          (Coolify-compat, no public `ports:`, etc.)   │
│   7. CoolifyClient          (drivers/coolify.py → base64 compose PATCH   │
│                              then POST /deploy?uuid=…&force=true)        │
│   8. InfrastructureProvisioner (shape-driven, live 2026-04-22:           │
│         postgres · gatus · backrest · glitchtip+DSN · grafana ·          │
│         authelia+^/api/ bypass · meilisearch)                            │
│   9. DeploymentVerifier     (orchestrator/verifier.py — HTTP 200,        │
│                              DSN injected, DNS resolves, SSL valid)      │
│                                                                          │
│   on failure ⇒ RollbackManager (orchestrator/rollback.py, reverse order) │
└──────────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  VPS: Coolify → Traefik → Container                                      │
│  Security: iptables DOCKER-USER · Authelia · X-Internal · Bearer token   │
│  Observability: Prometheus+AM → Telegram  ·  Gatus → Apprise → Telegram  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Fabrik Source Code — Deployment Path

Every Python file below is **on the deployment critical path**. Files not listed here (e.g., `wordpress/`, `ai/`, `content/`) are adjacent systems that ride on top of the deployment primitives.

### 2.1 CLI entry points — `src/fabrik/cli.py`

Click-based CLI (~2024 lines). The commands below are the only public entry points for deployment work. Each delegates to modules in this document — **do not add deploy logic here**; add it to an orchestrator stage or driver and call from the CLI.

| Command | Line | Function | Delegates to |
|---|---|---|---|
| `fabrik new <template> <name>` | 81 | **DEPRECATED & hidden** — kept for backward compatibility; use `scaffold`. | `scaffold.py` wrapper |
| `fabrik scaffold <name> --type <t>` | 1018 | Create `/opt/<name>/` tree; generate spec at `specs/services/<name>.yaml`; allocate port; emit `.env.example`. | `scaffold.py` |
| `fabrik apply <spec.yaml>` | 309 | **Primary deploy entry point. Default = orchestrator pipeline (full 7-registrar sweep).** Flags: `--dry-run`, `--skip-dns`, `--skip-deploy`, `-s KEY=VALUE`, `--legacy` (opt out, render-only path), `--keep-on-failure` (proof-run only), `--use-orchestrator` (deprecated no-op since 2026-05-05). | `orchestrator/DeploymentOrchestrator.deploy()` (default) or `deploy.py::deploy_to_coolify()` (`--legacy`) |
| `fabrik deploy [--project P]` | 1966 | Alternate deploy entry that reads `/opt/<project>/project.yaml` and routes by project type. | `deploy_router.route_deploy()` → `DeploymentOrchestrator.deploy()` |
| `fabrik redeploy <app>` | 835 | Rebuild-only Coolify deploy by name or UUID. With `--refresh-infra --spec PATH` re-runs the `InfrastructureProvisioner` against the existing app (no rebuild). `--force`, `--dry-run`. | `CoolifyClient.deploy()` or `DeploymentOrchestrator.refresh_infrastructure()` |
| `fabrik destroy <spec>` | 690 | Tear down **all 7 registrars** (meilisearch → authelia → glitchtip → backrest → gatus → postgres → coolify → dns → files) in reverse-of-provision order. `--keep-dns`, `--keep-files`, `--drop-data`, `--dry-run`. | `orchestrator/destroyer.py::destroy_deployment()` |
| `fabrik vps-sync [--dry-run]` | 792 | Refresh VPS docs (`vps-status.md`, `vps-urls.md`, `vps-complete-inventory.md`) from live `docker ps`; rerun `sync_projects.py`. Read-only on VPS. | `scripts/vps_sync.py` |
| `fabrik validate-deploy <project>` | 1094 | Pre-flight readiness check for a scaffolded project. | `deploy_validator.validate()` |
| `fabrik domain provision <domain>` | 1503 | Register domain + DNS + CDN via site-provisioner. | `drivers/dns.py::DNSClient` |
| `fabrik domain ready <domain>` | 1601 | Poll DNS + SSL readiness before deploying. | `drivers/dns.py::DNSClient` |
| `fabrik domain buy <domain>` | 1726 | Register a new domain via Namecheap. | `drivers/dns.py::DNSClient::register_domain()` |
| `fabrik wp plan/apply/verify/flush` | 1154–1331 | WordPress-specific sub-pipeline. | `wordpress/stages/*.py` |
| `fabrik content publish` | 1831 | SEO→TCO→Image→WordPress content pipeline (not deploy). | `orchestrator/content_publisher.py` |

### 2.2 Orchestrator — `src/fabrik/orchestrator/`

The deployment pipeline. **Default since 2026-05-05** for `fabrik apply` and `fabrik deploy`. Opt out via `fabrik apply --legacy` for the render-only path (see §9.2). Phase 4 plan: `docs/development/plans/2026-04-18-zero-touch-deployment.md`.

| File | Class / function | Role in deploy |
|---|---|---|
| `orchestrator/__init__.py` | `DeploymentOrchestrator.deploy(spec_path, dry_run)` | Top-level runner. Drives the state machine; calls each stage in order; wires in `RollbackManager` on error. |
| `orchestrator/context.py` | `DeploymentContext`, `ResourceRecord` | Shared state across stages (spec, spec_hash, `coolify_uuid`, `dns_records`, list of created resources). Every resource that can be rolled back calls `ctx.add_resource(...)`. |
| `orchestrator/states.py` | `DeploymentState`, `can_transition()` | State machine enum: `PENDING → VALIDATING → PROVISIONING → DEPLOYING → VERIFYING → COMPLETE` / `FAILED → ROLLING_BACK → ROLLED_BACK`. Illegal transitions raise `InvalidStateTransitionError`. |
| `orchestrator/validator.py` | `SpecValidator.validate(spec)`, `validate_domain_security()`, `compute_spec_hash()` | Pydantic spec validation + SSRF check (no private IPs, no reserved ranges) + idempotency hash. |
| `orchestrator/secrets.py` | `SecretsManager`, `generate_secret()`, `load_dotenv()` | Load secrets precedence: env vars → project `.env` → `-s KEY=VALUE` (highest wins). CSPRNG for generated secrets (`secrets.choice()`, 32 chars). |
| `orchestrator/deployer.py` | `ServiceDeployer.deploy(ctx)`, `ServiceDeployer.find_existing(name)` | Coolify-side mutations. Idempotent: `find_existing` looks up by name in `list_applications()` — if found, PATCH + update env; else POST new `dockercompose` app + `deploy(force=True)`. Returns UUID. Also waits up to 90s for the container to come Up. |
| `orchestrator/infrastructure.py` | `InfrastructureProvisioner.provision(ctx)`, `resolve_applicability(shape)`, `format_resolved_summary()` | **Live** shape-driven dispatcher. Invoked between Deploy and Verify. Decides per-registrar applicability (`postgres`, `gatus`, `backrest`, `glitchtip`, `grafana`, `authelia`, `meilisearch`), then calls each driver's `create_*`/`add_*` entry in contract order. Each registrar failure is logged non-fatal **except glitchtip's `verify_dsn_injection` mismatch**, which rolls back the GlitchTip project and re-raises (prevents silent error-tracking outages). |
| `orchestrator/verifier.py` | `DeploymentVerifier.verify(ctx)` | Post-conditions: HTTP 200 on `/health`; DNS resolves to VPS IP; SSL cert valid; `SENTRY_DSN` in container env (when GlitchTip provisioned). |
| `orchestrator/rollback.py` | `RollbackManager.rollback(ctx)` | Reverse-order cleanup of every `ctx.resources[*]`. Destructive actions (DB drops) are **logged for operator**, not auto-executed. Config mutations and ephemeral resources (annotations, projects, DNS records) are auto-cleaned. |
| `orchestrator/exceptions.py` | Typed exceptions | `DeploymentError`, `ValidationError`, `ProvisioningError`, `DeployError`, `VerificationError`, `RollbackError`, `InvalidStateTransitionError`. Orchestrator catches these and routes to rollback. |
| `orchestrator/content_publisher.py` | `ContentPublisher` | **Not deploy** — content pipeline (SEO → TCO → Images → WordPress). Uses the same context/state pattern. |

### 2.3 Spec & template layer

| File | Role |
|---|---|
| `src/fabrik/spec_loader.py` | Parse `.yaml` spec → pydantic `Spec` model. Defines every valid field: `DNS`, `Source`, `Expose`, `Resources`, `Health`, `Volume`, `Backup`, `SecretsPolicy`, `CoolifyConfig`, `Depends`, `Infrastructure`, `WordPressConfig`. Enforces `model_config = {"extra": "forbid"}`. Entry points: `load_spec(path)`, `save_spec(spec, path)`, `create_spec(name, kind, ...)`. |
| `src/fabrik/template_renderer.py` | `TemplateRenderer(spec).render(output_dir)` → writes `compose.yaml` + `Dockerfile` + auxiliary files from `templates/<type>/*.j2`. `list_templates()` enumerates available templates. |
| `src/fabrik/scaffold.py` (~111 KB) | The entire `fabrik scaffold` command. Generates `/opt/<name>/` tree; emits `project.yaml`, `specs/services/<name>.yaml`, `.env.example`, `README.md`, tests, CI workflow. Reads `templates/<type>/defaults.yaml` for shape flags. |
| `src/fabrik/compose_linter.py` | `ComposeLinter.lint(compose_yaml)` — validates Coolify compat: no public `ports:`, `platform: linux/amd64` present, `healthcheck:` present, `networks: coolify` declared, `traefik.docker.network=coolify` label when multi-network. |
| `src/fabrik/registry.py` | `ProjectRegistry` — manages `/opt/fabrik/data/projects.yaml`. Tracks every project (path, type, spec hash, last deploy). Consulted by `scripts/sync_projects.py`. |

### 2.4 Drivers — `src/fabrik/drivers/`

**Drivers are the only place that talks to external APIs or the VPS.** Every deploy mutation goes through exactly one driver. Add `drivers/<name>.py` when integrating a new external system; do not bypass via ad-hoc HTTP/SSH calls in orchestrator or CLI code.

| File | Class / entry point | External system | Used during deploy for |
|---|---|---|---|
| `drivers/ssh.py` | `ssh(cmd, timeout, dry_run)`, `scp_to_vps(src, dst)` | SSH to VPS (host alias `vps`, configurable via `FABRIK_VPS_SSH_HOST`) | Any SSH-only op (Authelia `docker cp`, filesystem inspection). **Function-level env lookup** so tests can monkeypatch. Non-zero exits raise `RuntimeError` with stderr included. |
| `drivers/locks.py` | `run_locked(resource, script, timeout)`, `git_commit_config(path)` | VPS `flock -x -w` + git | Multi-step VPS mutations that must be serialized (Authelia config edits, Backrest config edits). **Lock held for the whole script**, not across Python-orchestrated SSH calls (this pattern was proven broken on live VPS — see module docstring). `git_commit_config()` whitelist: **only** `/opt/monitoring/configs/gatus` may be committed; secret-bearing configs use `.bak.{ts}`. |
| `drivers/coolify.py` | `CoolifyClient`, `Application`, `Service` | Coolify v4 API | Create/update/delete/deploy Docker Compose applications and one-click services. **`docker_compose_raw` MUST be base64-encoded** (Lesson 1). `PATCH /applications/{uuid}` is IGNORED if `git_repository` is set — edit the repo instead (§8.10). |
| `drivers/dns.py` | `DNSClient`, `DNSRecord`, `add_dns_record()` | site-provisioner service (`dns.vps1.ocoron.com`) | Domain registration, A/CNAME/TXT record management, Cloudflare zone provisioning, SSL readiness polling. Auth via `SITE_PROVISIONER_API_KEY` + `X-Internal-Token` header. |
| `drivers/cloudflare.py` | `CloudflareClient` | Cloudflare API (direct) | Fallback when site-provisioner unavailable. Needs `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ZONE_ID`. |
| `drivers/supabase.py` | `SupabaseClient` | Supabase API | When `spec.infrastructure.database == supabase`: create project, user, run migrations. |
| `drivers/r2.py` | `R2Client` | Cloudflare R2 (S3-compatible) | Object storage ops when `spec.storage.type == r2`. |
| `drivers/uptime_kuma.py` | `UptimeKumaClient`, `add_fabrik_service_to_monitoring()` | Uptime Kuma | Legacy monitoring hook — **superseded by Gatus**; kept for old projects only. |
| `drivers/image_broker.py` | `ImageBrokerClient` | image-broker microservice | Stock image fetching (content pipeline, **not deploy**). |
| `drivers/seo.py` | `SEOClient` | SEO microservice | Keyword research (content pipeline, **not deploy**). |
| `drivers/tco.py` | `TCOClient` | TCO AI service | Content generation (content pipeline, **not deploy**). |
| `drivers/wordpress.py` | `WordPressClient`, `WPSite`, `ContainerResolver` | WP-CLI via `docker exec` | WordPress-specific deploys (plugins, themes, settings). |
| `drivers/wordpress_api.py` | `WordPressAPIClient`, `WPCredentials`, `WPPost` | WordPress REST API | Content CRUD for WordPress sites. |

**Shape-driven registrar drivers (all implemented as of 2026-04-22):**

| File | Entry points | Purpose | Shape gate |
|---|---|---|---|
| `drivers/authelia.py` | `add_access_rule()`, `remove_access_rule()` | `docker exec` into Authelia to add/remove `access_control` rules. Uses `run_locked("authelia-config", ...)`. Supports `insert_before_twofactor=True` for `^/api/` bypass ordering. | `shape.is_admin_dashboard` + `domain` set (+ `^/api/` bypass when `shape.has_bearer_api`) |
| `drivers/gatus.py` | `add_endpoint()`, `remove_endpoint()` | Git-repo edit of `/opt/monitoring/configs/gatus/config.yaml` + commit via `git_commit_config()`. | `shape.is_public` + `domain` set |
| `drivers/backrest.py` | `add_backup_plan()`, `remove_backup_plan()` | Restic-policy mutations via Backrest UI API. Uses `run_locked("backrest-config", ...)` with atomic `.tmp` → `json.tool` validate → `mv` pattern. | `shape.has_persistent_data` |
| `drivers/glitchtip.py` | `create_project()`, `delete_project()`, `verify_dsn_injection()` | Sentry-compatible API (`POST /api/0/teams/{org}/{team}/projects/`). Contract captured in `docs/reference/glitchtip-api.md`. **`verify_dsn_injection` reads env via `docker inspect`, never `docker exec`** — see Lesson 31. | `shape.kind in {service, worker, wordpress}` |
| `drivers/grafana.py` | `post_deployment_annotation()`, `delete_annotation()` | Global deployment annotations (`POST /api/annotations`). Non-fatal (decorative). Env var `GRAFANA_SERVICE_ACCOUNT_TOKEN`. | Always (universal) |
| `drivers/meilisearch.py` | `create_index()`, `delete_index()` | Index creation when `spec.has_search_feature`. Container-scoped `sh -c` evaluates `$MEILI_MASTER_KEY` inside the container — no secret on SSH wire. | `shape.has_search_feature` |
| `drivers/postgres.py` | `create_database()`, `drop_database()` | Ensures per-service Postgres DB on `postgres-main` (SQL identifier validation upstream). Destructive drops deferred to operator. | `shape.needs_database` |

### 2.5 Site-provisioner saga — `src/fabrik/provisioner.py`

Implements **Steps 0-1-2** of a brand-new site deployment (domain → DNS → Coolify). Uses a saga pattern with persistent state (`/opt/fabrik/data/provision-jobs/`).

| Class / fn | Role |
|---|---|
| `ProvisionState` | Saga state enum. |
| `ContactInfo` | WHOIS contact for domain registration. |
| `SiteProvisionRequest` | Input contract from web GUI / CLI. |
| `ProvisionJob` | Persistent state on disk (resumable across CLI invocations). |
| `SiteProvisioner.run(job)` | Saga runner. Each step is idempotent; on failure, replays from last successful state. |
| `provision_site(request)` | Entry point; returns job ID. |
| `get_provision_status(job_id)` | Polling endpoint for web GUI. |

### 2.6 Supporting modules

| File | Role |
|---|---|
| `src/fabrik/deploy.py` | Thin helper used by `fabrik deploy` command. `deploy_to_coolify(app_name, compose_content)` — used for very simple deploys that don't need the full orchestrator (legacy, shrinking). |
| `src/fabrik/deploy_router.py` | `route_deploy(project_path)` — dispatches to WordPress pipeline vs. service pipeline based on `project.yaml[type]`. Central switch for `fabrik deploy`. |
| `src/fabrik/deploy_validator.py` | `validate(project_dir)` — scaffold-level readiness (Dockerfile exists, `.env` populated, healthcheck declared, platform directive). Returns `ValidationResult` list; CLI prints them as warnings. |
| `src/fabrik/verify.py` | `PostconditionChecker`, `verify_postconditions` decorator — general postcondition framework (HTTP 200, file-exists, env-var-set, etc.). Used by both legacy pipeline and orchestrator/verifier. |
| `src/fabrik/notifications.py` | Thin wrapper over Apprise for in-Fabrik notifications (not infrastructure alerts). |
| `src/fabrik/monitor.py` | Deployment monitor helpers used by `fabrik status/logs`. |
| `src/fabrik/health_app.py` | Tiny FastAPI app exposing `/health` for Fabrik's own service health (scraped by Gatus). |

---

## 3. Specs

Specs are the **input** to every deploy. Two flavors: infrastructure specs (deploy shared services once) and service specs (one per app).

### 3.1 Infrastructure specs — `specs/infrastructure/`

Deployed once when bootstrapping the VPS; not touched by normal `fabrik apply` on apps.

| File | Deploys | Current state |
|---|---|---|
| `specs/infrastructure/monitoring-stack.yaml` | Prometheus, Grafana, Alertmanager, Loki, Promtail, node-exporter, cAdvisor (7 services) | ✅ deployed; all 7 migrated to Coolify 2026-04-17 |
| `specs/infrastructure/authelia.yaml` + `authelia-coolify.yaml` | Authelia (SSO/2FA forward-auth) | ✅ deployed on Coolify |
| `specs/infrastructure/apprise.yaml` | Apprise (notifications gateway) | ✅ deployed |
| `specs/infrastructure/browserless.yaml` | Browserless (headless Chrome) | ✅ deployed |
| `specs/infrastructure/gotenberg.yaml` | Gotenberg (HTML/Office → PDF) | ✅ deployed |
| `specs/infrastructure/meilisearch.yaml` | MeiliSearch | ✅ deployed |
| `specs/infrastructure/n8n.yaml` | n8n (workflow automation) | ✅ deployed |
| `specs/infrastructure/minio.yaml` | MinIO (self-hosted S3) | ⏸ not deployed (Backblaze B2 via Backrest used instead) |

### 3.2 Service specs — `specs/services/`

One file per deployable app. Auto-generated by `fabrik scaffold` into `/opt/fabrik/specs/services/<name>.yaml`. Current count: ~52 services. Schema defined in `src/fabrik/spec_loader.py::Spec`.

### 3.3 Site specs — `specs/sites/`

WordPress site specs (domain, theme, plugins, brand, content preset). Consumed by the WordPress pipeline (`wordpress/stages/*.py`).

### 3.4 Verification specs — `specs/verification/`

Postcondition specs consumed by `src/fabrik/verify.py` — declarative checks that must pass after a deploy (HTTP endpoints, files, env vars). Extensible via `verify.py::PostconditionChecker`.

### 3.5 n8n workflows — `specs/n8n-workflows/`

Workflow JSON exports used to seed n8n after migration/redeploy. See also `configs/n8n/workflows/`.

### 3.6 Ecosystem compliance — `specs/ecosystem-compliance/`

Cross-project compliance checks for auditing deployed services against Fabrik standards.

---

## 4. Templates

Scaffold uses these to generate `/opt/<project>/` trees. Every template has a `defaults.yaml` that declares its **shape flags** (`is_public`, `is_admin_dashboard`, `has_bearer_api`, `has_persistent_data`, `needs_database`, `has_search_feature`). These flags drive the zero-touch provisioner's dispatch (see Phase 4 plan §Execution Order).

### 4.1 Service templates — `templates/<type>/`

| Template | Kind | Deploys to | Key files |
|---|---|---|---|
| `templates/python-api/` | FastAPI service | Coolify (Docker Compose) | `compose.yaml.j2`, `defaults.yaml` |
| `templates/node-api/` | Node.js API | Coolify | `compose.yaml.j2`, `Dockerfile.j2`, `AGENTS.md.j2`, `defaults.yaml` |
| `templates/saas-skeleton/` | Next.js 14 + TypeScript + Tailwind + Shadcn | Coolify | `compose.yaml.j2`, `Dockerfile`, 39 files incl. full skeleton |
| `templates/static-site/` | Static HTML/JS | Coolify (nginx) | `compose.yaml.j2`, `defaults.yaml` |
| `templates/wordpress/` | WordPress | Coolify (wp + db) + WP-CLI pipeline | 27 files incl. presets `landing.yaml`, `saas.yaml`, `content.yaml` |
| `templates/docusaurus/` | Docusaurus doc site | Coolify | `compose.yaml.j2`, `Dockerfile.j2`, `docusaurus.config.js.j2`, `sidebars.js.j2` |
| `templates/file-api/` | File-operations microservice | Coolify | `compose.yaml.j2`, `Dockerfile.j2` |
| `templates/file-worker/` | Background worker variant of file-api | Coolify | `compose.yaml.j2` (7 files) |
| `templates/chrome-extension/` | Browser extension | GitHub releases | `manifest.json`, build config |
| `templates/desktop-app/` | Electron-style desktop app | GitHub releases | `compose.yaml.j2` (5 files) |
| `templates/mobile-app/` | React Native / Expo | EAS / stores | `compose.yaml.j2` (14 files) |
| `templates/next-tailwind/` | Next.js + Tailwind minimal | Coolify | 14 files |

### 4.2 Shared scaffold assets — `templates/scaffold/`

| File | Purpose |
|---|---|
| `templates/scaffold/complex.yaml` | Canonical complex-service spec example (5+ env vars, db, storage, auth). |
| `templates/scaffold/docker/compose.yaml.template` | Base compose template shared across service types. |
| `templates/scaffold/docker/compose.dev.yaml.template` | Developer-mode override (ports exposed on `127.0.0.1` only). |
| `templates/scaffold/docker/Dockerfile.node` | Canonical Node.js Dockerfile (`node:<LTS>-bookworm-slim`). |
| `templates/scaffold/docker/Dockerfile.python` | Canonical Python Dockerfile (`python:<stable>-slim-bookworm`). |
| `templates/scaffold/*` (34 files total) | Tests, CI workflows, README, .env.example, .gitignore, AGENTS.md boilerplate. |

### 4.3 Archived templates — `templates/.archive/`

`simple.yaml`, `medium.yaml` — prior iterations of the complexity tiers. Kept for reference; do not use.

---

## 5. Local Config Mirrors — `configs/`

Local copies of VPS-side config files. **Source of truth is on the VPS** (Coolify-managed or volume-mounted); these mirrors exist so AI coders can diff/edit without shelling in.

| File | VPS path | Edited how |
|---|---|---|
| `configs/alertmanager/alertmanager.yml` | `/opt/monitoring/configs/alertmanager/alertmanager.yml` | Volume-mounted from host. Edit locally → `scp` → `docker restart alertmanager`. |
| `configs/alertmanager/alertmanager.yml.example` | — | Template with `__PLACEHOLDERS__`; render into the real file with secrets from `.env`. |
| `configs/prometheus/prometheus.yml` | `/opt/monitoring/configs/prometheus/prometheus.yml` | Same pattern as Alertmanager. |
| `configs/prometheus/rules/alerts.yml` | `/opt/monitoring/configs/prometheus/rules/alerts.yml` | Contains the 9 alert rules. Edit → reload with `curl -X POST http://prometheus:9090/-/reload`. |
| `configs/loki/loki-config.yaml` | Loki volume | Rarely edited. |
| `configs/promtail/promtail-config.yaml` | Promtail volume | Rarely edited. |
| `configs/n8n/workflows/*.json` | n8n UI imports | Seed workflows after n8n redeploy: `backup-notification.json`, `uptime-alert.json`, `webhook-test.json`. |

**Important:** Every file here should appear in `.gitignore` **if it ever contains secrets**. The `alertmanager.yml` is `.gitignore`d because it embeds the Telegram bot token; `alertmanager.yml.example` is tracked (Lesson 25 §8.5).

---

## 6. Probes & Enforcement Scripts

### 6.1 Probes — `scripts/probes/`

Idempotent contract tests against live services. Run before shipping driver changes; also serve as living API documentation.

| Script | Tests | Used for |
|---|---|---|
| `scripts/probes/glitchtip_probe.sh` | GlitchTip API (create project → fetch DSN → delete) | Contract test for planned `drivers/glitchtip.py`. See `docs/reference/glitchtip-api.md`. |
| `scripts/probes/grafana_token_check.sh` | Grafana `/api/annotations` write + delete | Contract test for planned `drivers/grafana.py`. Validates `GRAFANA_SERVICE_ACCOUNT_TOKEN` scope. |

### 6.2 Enforcement — `scripts/enforcement/`

Pre-deploy invariant checks. Called by `scripts/final_gate.py` as part of the quality gate. Each `check_*.py` is single-purpose; exits non-zero on violation.

| Check script | Enforces |
|---|---|
| `check_secrets.py` | No secrets in tracked files (`AKIA...`, `ghp_...`, JWT patterns, etc.). |
| `check_env_contract.py` | No hardcoded `localhost` / `127.0.0.1` / hardcoded passwords; use `os.getenv(...)`. |
| `check_env_example.py` | Every env var referenced in code appears in `.env.example`. |
| `check_env_updates.py` | When `.env.example` changes, `CHANGELOG.md` is updated. |
| `check_env_vars.py` | Env vars follow `UPPER_SNAKE_CASE`. |
| `check_docker.py` | `compose.yaml` uses `platform: linux/amd64`; base images are `-slim-bookworm`; `HEALTHCHECK` present; no public `ports:` mappings. |
| `check_compose_services.py` | Compose services declare `networks: [coolify]` when behind Traefik; `traefik.docker.network=coolify` label when multi-network. |
| `check_ports.py` | Ports used fall in allocated ranges (8000–8099 Python, 3000–3099 frontend, 18000+ production); no duplicates. |
| `check_health.py` | Every service has a `/health` endpoint that tests real dependencies. |
| `check_watchdog.py` | Long-running services have `scripts/watchdog*.sh`. |
| `check_schema_sync.py` | DB migrations match `db/schema.sql` reference. |
| `check_structure.py` | Project directory structure follows Fabrik scaffold layout. |
| `check_print_ban.py` | No `print()` / `console.log()` — use the scaffolded logger. |
| `check_duplicates.py` | No duplicated files across projects (shared helpers should live in `src/utils/`). |
| `check_doc_sprawl.py` | No orphaned `.md` files; all docs reachable from `INDEX.md`. |
| `check_index_md.py`, `check_readme_md.py`, `check_changelog.py`, `check_configuration_md.py`, `check_docs.py`, `check_user_guide.py` | Doc currency — every deploy-affecting change updates the matching doc (see `docs/CROSS_CUTTING_REQUIREMENTS.md`). |
| `check_plans.py`, `check_plan_quality.py` | Plans in `docs/development/plans/` include Invariants, Failure Modes, Acceptance Criteria. |
| `check_test_coverage.py`, `check_test_proposal.py` | Every non-trivial change proposes at least one test (One-Test Rule). |
| `check_reusable_modules.py` | Modules in `src/utils/` / `src/lib/` have zero project-specific imports (for cross-project extraction). |
| `check_opencode_json.py`, `check_android_env.py`, `check_openapi_sync.py`, `check_deps_sync.py`, `check_rule_size.py`, `validate_conventions.py` | Miscellaneous ecosystem invariants. |

### 6.3 Final gate — `scripts/final_gate.py`

Single entry point for all tier-based quality checks:

- `python scripts/final_gate.py --lean` — Tier 1 (syntax, secrets, env, schema). Fast, called during coding.
- `python scripts/final_gate.py` — Tier 2 (full: lean + static analysis + changelog/docs sync). Called at milestone close.
- `python scripts/final_gate.py --systemic` — Tier 3 (repo health: docker, ports, docs sprawl, duplicates). On-demand.

### 6.4 Other deploy-adjacent scripts

| Script | Purpose |
|---|---|
| `scripts/sync_projects.py` | Discover all projects under `/opt/`, update `PORTS.md` + `registry`. Run after every scaffold. |
| `scripts/sync_enforcement_to_projects.py` | Copy `scripts/enforcement/*` into each project (so project CI can run the same gates). |
| `scripts/sync_schema_to_projects.py` | Sync shared SQL schema fragments to projects that need them. |
| `scripts/consolidate_envs.py` | Audit all `/opt/*/env` files; propose consolidation of duplicate secrets into `/opt/fabrik/.env`. |
| `scripts/watch_env_changes.sh` | Background watcher — alerts when a tracked `.env` file is modified. |
| `scripts/audit_all_projects.py` | Full-fleet compliance report (every project vs. every enforcement check). |
| `scripts/container_images.py` | Inventory of every Docker image in use on the VPS; detects outdated `:latest` tags. |
| `scripts/health_summary.py`, `scripts/health_checker.py`, `scripts/health_check_autonomous.py` | Rollup health probes across all deployed services. |
| `scripts/migrate-authelia-to-coolify.sh` | One-shot migration script (executed 2026-04-17). Kept as a reference. |
| `scripts/provision_grafana.sh` | One-shot Grafana setup (dashboards, datasources). |
| `scripts/create_wp_container.py` | Create a new WordPress container manually (used by `fabrik wp` pipeline for new sites). |
| `scripts/docs_updater.py` + `scripts/kilo_docs_enforcer.py` | Auto-update docs (CHANGELOG, INDEX, README) — used by `/local-docs` workflow. |
| `scripts/watchdog.sh` | Sample watchdog that services copy into their repo (required per `30-ops.md`). |

---

## 7. VPS-Side Files & Services

Files that live **on the VPS only**, outside the Fabrik repo. Grouped by service. **Edit mechanism** is listed for each — getting this wrong risks a deploy that silently reverts (Lesson 25 §8.6).

### 7.1 Coolify (control plane)

| Path | Purpose | Edit mechanism |
|---|---|---|
| `/data/coolify/source/docker-compose.yml` | Coolify itself | Do not edit directly; Coolify self-manages. |
| `/data/coolify/source/docker-compose.prod.yml` | Coolify production overrides | Do not edit. |
| `/data/coolify/source/docker-compose.override.yml` | Owner-authored override for Coolify's own Traefik labels. **Required** to add `authelia-forward@docker` middleware to `coolify.vps1.ocoron.com` (§8.8 of Lesson 25). | Edit on VPS → `docker compose -f ... -f docker-compose.override.yml up -d --force-recreate coolify`. |
| `/data/coolify/services/<uuid>/docker-compose.yml` | Rendered compose for each service (generated from `docker_compose_raw` in Coolify DB). | **NEVER edit directly** — Coolify overwrites on next deploy (§8.6). Use `PATCH /services/{uuid}` with base64-encoded compose. |
| Coolify DB (`coolify-db` container, postgres) | Source of truth for `docker_compose_raw`, env vars, Traefik labels. | Only via Coolify API (`coolify.vps1.ocoron.com/api/v1`). |

**Coolify v4 env-var API (captured live 2026-04-19, Phase 4c):**

- `GET /api/v1/applications/{uuid}/envs` — returns list of `{uuid, key, value, is_preview, is_build_time, ...}`. A key can appear twice if the compose references it in both build-time and runtime scope; the non-empty one is the effective value.
- `POST /api/v1/applications/{uuid}/envs` — body `{"key":"…","value":"…"}`. HTTP 201 on success.
  - HTTP 409 `"Environment variable already exists. Use PATCH"` if the key is already present (even with empty value).
  - HTTP 422 `"is_build_time: This field is not allowed"` if you include that field. Accepted body fields are only `key`, `value`, `is_preview` (optional), `is_literal` (optional).
- `PATCH /api/v1/applications/{uuid}/envs` — same body shape, updates existing. HTTP 200 on success.
- **`services` endpoint does not serve env-var subresources** for git-sourced dockercompose apps (HTTP 404). Always use `applications/{uuid}/envs` for those.
- **No redeploy required** if the new env var isn't referenced in the current `docker_compose_raw` — it becomes live on the next deploy that references it. This is the safe pattern for pre-seeding credentials.

### 7.2 Traefik (reverse proxy, Coolify-managed)

| Path | Purpose | Edit mechanism |
|---|---|---|
| `/data/coolify/proxy/docker-compose.yml` | Traefik compose | Coolify-managed. |
| `/data/coolify/proxy/dynamic/*.yml` | Dynamic Traefik config (rarely used; most routing is via Docker labels). | Edit + `docker exec traefik kill -HUP 1`. |
| Traefik API on 127.0.0.1:8080 | Live router/service/middleware inspection | `curl -s 127.0.0.1:8080/api/http/routers` piped into `jq` (no auth on localhost). |

### 7.3 Authelia (SSO/2FA forward-auth)

| Path | Purpose | Edit mechanism |
|---|---|---|
| Authelia container's `/config/configuration.yml` | `access_control` rules (domain → policy, bypass/one_factor/two_factor). | Pull: `docker exec authelia-... cat /config/configuration.yml > authelia.cur.yml`. Edit locally. Write back: `docker cp authelia.cur.yml authelia-...:/config/configuration.yml && docker restart authelia-...`. Never re-source from disk afterwards — Coolify's compose is the runtime config (§8.6). |
| Authelia container's `/config/users_database.yml` | User definitions (owner only — Ozgur). | Same `docker cp` pattern. |
| Authelia container's `/config/notification.txt` | 2FA login codes fallback (SMTP disabled). | `sudo docker exec -it authelia-... cat /config/notification.txt` to read. |

**Authelia posture decision matrix** (from LESSONS_LEARNT §8.13 — live on 2026-04-18):

| Service class | Authelia posture | Examples | Rationale |
|---|---|---|---|
| Native auth + TOTP | **Full bypass** — app-layer is the boundary | GlitchTip, Grafana, GitLab, Nextcloud | Forward-auth breaks SPA auth flows (django-allauth/React XHRs get 302'd to Authelia → SPA renders "500"). |
| Native auth, no TOTP | **Forward-auth required** | Backrest, n8n, Apprise | App auth alone is insufficient; Authelia provides the 2FA. |
| No native auth | **Forward-auth mandatory** | Netdata, bare admin panels | Only boundary available. |
| UI + Bearer-token API | **Forward-auth on UI, `^/api/` bypass** | Coolify, Grafana | UI stays 2FA; machine callers use Bearer token (§8.11). |

### 7.4 Monitoring stack (Coolify-managed)

| Path | Purpose | Edit mechanism |
|---|---|---|
| `/opt/monitoring/configs/prometheus/prometheus.yml` | Scrape targets + alerting config (7 static jobs + `fabrik-services` job at 30s). Retention: `--storage.tsdb.retention.time=30d --storage.tsdb.retention.size=5GB`. | Edit on VPS → `cd /opt/prometheus && sudo docker compose restart` (`--web.enable-lifecycle` enabled but no curl in image). |
| `/opt/monitoring/configs/prometheus/rules/alerts.yml` | 9 alert rules (ContainerDown, HighCPU, HighMemory, OOMKilled, etc.) | Same pattern. |
| `/opt/monitoring/configs/alertmanager/alertmanager.yml` | Routes, receivers (Telegram), inhibit rules | Edit → `docker restart alertmanager-...`. **Secret-bearing** (Telegram bot token). |
| `/opt/monitoring/configs/gatus/` | Gatus blackbox monitoring — 6 subdirs, auto-reloads on file change. Never use UUID container names; use stable aliases (see §8.x). `_base.yaml` for global alerting → Apprise; group files per service type. | **Git-versioned** (whitelisted in `drivers/locks.py::git_commit_config()`). Edit → `git commit` → deploy. |
| `/opt/monitoring/configs/loki/loki-config.yaml` | Loki storage config | Edit → `docker restart loki-...`. |
| `/opt/monitoring/configs/promtail/promtail-config.yaml` | Log shipper → Loki | Edit → `docker restart promtail-...`. |

### 7.5 Network, firewall, persistence

| Path | Purpose | Edit mechanism |
|---|---|---|
| `/etc/iptables/add-docker-user-rules.sh` | DOCKER-USER chain rules — only 80/443/6001/6002 allowed publicly. Docker bypasses UFW; this chain is the real public-port boundary. | Edit + `sudo /etc/iptables/add-docker-user-rules.sh` + `sudo systemctl restart iptables-docker-user.service`. |
| `/etc/systemd/system/iptables-docker-user.service` | Persistence for the chain across reboots. | `sudo systemctl {daemon-reload,enable,restart}` after edit. |
| Docker networks | `coolify` (10.0.1.0/24) is the shared network Traefik lives on. Per-service private UUID networks are auto-created by Coolify. | Inspect: `docker network inspect coolify`. |

### 7.6 Fabrik on VPS

| Path | Purpose |
|---|---|
| `/opt/fabrik/.env` | Canonical env file. All secrets (Coolify token, Cloudflare, Grafana SA, GlitchTip, Backrest, etc.). Backed up to `.env.backup.{ts}` before any edit. |
| `/opt/fabrik/PORTS.md` | Port registry. Auto-updated by `sync_projects.py`. |
| `/opt/fabrik/data/projects.yaml` | Project registry (paths, types, spec hashes). |
| `/opt/fabrik/data/provision-jobs/` | Saga state for `SiteProvisioner`. |
| `/opt/fabrik/.tmp/` | Throwaway artifacts (probe outputs, intermediate backups). Git-ignored. |

---

## 8. VPS Infrastructure Invariants

These are **hard rules** for every deploy. Violating any of them puts the VPS or a service in a degraded state.

### 8.1 Platform

- **VPS arch:** x86_64 (amd64), AMD EPYC-Genoa, 6 vCPU, 12 GB RAM, Ubuntu 24.04, TZ `Europe/Istanbul` (+03).
- **Every compose service MUST declare** `platform: linux/amd64` (enforced by `check_docker.py`).
- **Base images:** `python:<current-stable>-slim-bookworm` or `node:<current-LTS>-bookworm-slim`. **Never Alpine**.

### 8.2 Networking

- **`coolify` Docker network is the shared backbone.** Traefik lives here. Every service that must be reachable by Traefik MUST attach to this network.
- **`traefik.docker.network=coolify` label is mandatory** for any service on more than one Docker network — without it Traefik non-deterministically picks a network IP (Lesson 25 §8.12).
- **No public `ports:` mapping** in compose. Everything goes through Traefik on 80/443. Docker bypasses UFW; iptables DOCKER-USER is the real boundary.
- **Allowed public TCP ports:** 80, 443, 6001, 6002 (Coolify real-time). Everything else is blocked at iptables.

### 8.3 Traefik labels (canonical compose snippet)

```yaml
services:
  my-service:
    platform: linux/amd64
    networks:
      coolify: null
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=coolify"                                         # mandatory, see §8.2
      - "traefik.http.routers.my-service.rule=Host(`my-service.vps1.ocoron.com`)"
      - "traefik.http.routers.my-service.entrypoints=websecure"
      - "traefik.http.routers.my-service.tls=true"
      - "traefik.http.routers.my-service.tls.certresolver=letsencrypt"
      # Add ONE of the following depending on the Authelia posture (§7.3):
      - "traefik.http.routers.my-service.middlewares=authelia-forward@docker"   # forward-auth tier
      # (no middleware for full-bypass tier with native app TOTP)
      - "traefik.http.services.my-service.loadbalancer.server.port=8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  coolify:
    external: true
```

### 8.4 4-layer security model

| Layer | Target | Mechanism |
|---|---|---|
| **Iptables DOCKER-USER** | All Docker ports | `/etc/iptables/add-docker-user-rules.sh`. Only 80/443/6001/6002 public. |
| **Authelia** | Admin dashboards without native TOTP | Forward-auth 2FA via Traefik middleware. **Not used** for services with native TOTP (see §7.3 matrix). |
| **X-Internal-Token** | Fabrik microservices (captcha, translator, pdf, browser, dns, ...) | Service validates `SERVICE_INTERNAL_SECRET_KEY` header on every request. |
| **Bearer tokens** | API endpoints on admin dashboards (Coolify, Grafana, GlitchTip) | Issued by each service; stored in `/opt/fabrik/.env`. Authelia `^/api/` bypass (§8.11) allows these through. |

### 8.5 Secrets

- **All secrets in `/opt/fabrik/.env`** or project `.env` files. Never hardcoded.
- **CSPRNG-generated passwords**, 32 chars, `[a-zA-Z0-9]` alphabet (`secrets.choice()`). Forbidden: `postgres`, `admin`, `password123`.
- **`.env` files MUST NOT be `source`d** — values may contain shell metacharacters (§8.14). Use `grep | cut` in shell; `python-dotenv` in Python.
- **Backup before edit:** `cp .env .env.backup.$(date +%Y%m%d-%H%M%S)` — mandatory per the Cascade contract.

---

## 9. Deployment Flows (step-by-step)

### 9.1 Scaffold a new service

```bash
# 1. Generate the project tree, spec, port, .env.example
fabrik scaffold my-api --type python-api

# 2. Edit the generated files:
#    /opt/fabrik/specs/services/my-api.yaml   (add domain, env vars, healthcheck)
#    /opt/my-api/.env                         (fill in real secrets)
#    /opt/my-api/src/                         (write the app)

# 3. Register the project + port
python3 scripts/sync_projects.py

# 4. Pre-flight check
fabrik validate-deploy /opt/my-api
```

### 9.2 Deploy a service — command-by-command, factual

**Two deploy entry points exist, with materially different behaviour. The table below is authoritative; source is `src/fabrik/cli.py` and `src/fabrik/deploy_router.py`.**

| Entry point | Source fn | Path through code | Triggers `InfrastructureProvisioner`? |
|---|---|---|---|
| `fabrik apply <spec>` (default, since 2026-05-05) | `cli.py::apply()` L309–372 | `DeploymentOrchestrator.deploy()` → validate → DNS → Coolify → **provisioner** → verify → `_post_deploy_sync()` | **YES** — full 7-registrar sweep. |
| `fabrik apply <spec> --legacy` | `cli.py::apply()` L374–516 | Renders → DNS → `deploy.py::deploy_to_coolify()` → `_post_deploy_sync()` | **NO** — opt-in render-only path; bypasses every registrar. Kept for backward compat with old scripts. |
| `fabrik deploy [--project P]` | `cli.py::deploy_cmd()` L1966 → `deploy_router.route_deploy()` → `DeploymentOrchestrator.deploy()` | Same orchestrator pipeline as default `apply`. | **YES.** |
| `fabrik redeploy <app>` | `cli.py::redeploy()` L835–902 | `CoolifyClient.deploy(uuid, force)` → `_post_deploy_sync()` | **NO** — intentional: rebuild-only, reuses existing registrations. Use `--refresh-infra` (next row) to re-run registrars without a rebuild. |
| `fabrik redeploy --refresh-infra --spec PATH` | `cli.py::redeploy()` L845–875 | `DeploymentOrchestrator.refresh_infrastructure(spec_path, dry_run)` — resolves Coolify UUID by spec name; runs **only** the provisioner against the existing app. No DNS, no rebuild, no verifier. → `_post_deploy_sync()` | **YES** (registrars only). Picks up newly-set shape flags (e.g. `needs_database: true` added after first deploy). |
| `fabrik destroy <spec>` | `cli.py::destroy()` L690–787 → `orchestrator/destroyer.py::destroy_deployment()` | Reverse-of-provision: meilisearch → authelia → glitchtip → backrest → gatus → postgres → coolify app → DNS → project tree → `_post_deploy_sync()`. Postgres/Meilisearch data preserved unless `--drop-data`. | **YES** — symmetric inverse of provisioner. |
| `fabrik vps-sync [--dry-run]` | `cli.py::vps_sync()` L792–815 → `scripts/vps_sync.py` | SSHes to VPS, runs `sudo docker ps`, rewrites container tables + timestamps in `vps-status.md`, `vps-urls.md`, `vps-complete-inventory.md`, then runs `sync_projects.py`. | **NO** — docs refresh only, no mutations. |

**Typical usage from WSL:**

```bash
# One-time SSH tunnel per WSL session (if hitting Coolify over the internal network)
ssh -f -N -L 8002:localhost:8000 vps
export COOLIFY_API_URL=http://localhost:8002

# Default path — runs the orchestrator + all applicable registrars
fabrik apply /opt/fabrik/specs/services/my-api.yaml
#   functionally equivalent (still orchestrator, reads project.yaml):
fabrik deploy --project /opt/my-api

# Dry-run (orchestrator path, plans only, no mutations)
fabrik apply /opt/fabrik/specs/services/my-api.yaml --dry-run

# Legacy path (NO registrars — only Coolify + DNS + files). Opt-in for backward-compat:
fabrik apply specs/services/my-api.yaml --legacy

# Flags
fabrik apply specs/services/my-api.yaml --skip-dns           # skip DNS record
fabrik apply specs/services/my-api.yaml --skip-deploy        # render files only
fabrik apply specs/services/my-api.yaml -s API_KEY=override  # override a secret
fabrik apply specs/services/my-api.yaml --keep-on-failure    # suppress rollback (proof-run only)
fabrik apply specs/services/my-api.yaml --use-orchestrator   # deprecated no-op (orchestrator is default)
```

**Orchestrator pipeline (default for `fabrik apply` and `fabrik deploy`; also forced by `--dry-run`):**

1. `SpecValidator.validate()` — pydantic + SSRF + `compute_spec_hash()` for idempotency.
2. `deploy_validator.validate()` — scaffold readiness (Dockerfile, `.env`, healthcheck).
3. `SecretsManager.load()` — precedence env → `.env` → `-s` flag.
4. `DNSClient.add_record(domain, VPS_IP)` — skipped if `--skip-dns`.
5. `TemplateRenderer.render()` + `ComposeLinter.lint()`.
6. `ServiceDeployer.deploy(ctx)` — `CoolifyClient.{find_existing, create, update}_application()` + `deploy(force=true)`; waits up to 90 s for container `Up`.
7. `InfrastructureProvisioner.provision(ctx)` — shape-driven dispatch. Registrar order (`_REGISTRAR_ORDER` in `orchestrator/infrastructure.py:84`): `postgres` → `gatus` → `backrest` → `glitchtip` (+DSN injection & verification) → `grafana` (annotation) → `authelia` (+`^/api/` bypass) → `meilisearch`. All failures are non-fatal **except** GlitchTip DSN-injection mismatch, which triggers rollback.
8. `DeploymentVerifier.verify()` — HTTP 200 on `/health`, DNS resolves, SSL valid, `SENTRY_DSN` present (when GlitchTip applicable) via `docker inspect`.
9. `_post_deploy_sync()` — runs `scripts/sync_projects.py` to refresh `data/projects.yaml` + `PORTS.md`.

On any exception, orchestrator transitions `ROLLING_BACK` and `RollbackManager` undoes every `ctx.resources[*]` in reverse order (§9.8).

**Legacy `fabrik apply` pipeline (NO orchestrator):**

1. Load spec + merge secrets (project `.env` + `-s` flags + `from_env`).
2. Prompt for confirmation (unless `--yes`).
3. `render_template(spec)` → writes `apps/<id>/compose.yaml` + `Dockerfile`.
4. `DNSClient.add_subdomain(base, sub, VPS_IP)` — skipped if `--skip-dns`.
5. `deploy.py::deploy_to_coolify(spec.id, compose_content)` — creates or reuses Coolify app.
6. `_post_deploy_sync()`.

**Steps NOT run on the legacy path:** spec hashing, health verification, DNS/SSL verification, **and every infrastructure registrar** (postgres, gatus, backrest, glitchtip+DSN, grafana, authelia, meilisearch). See §9.9 for the gap list.

### 9.3 Redeploy an existing service

Two modes — pure rebuild (default) or registrar refresh (`--refresh-infra`).

```bash
# Mode 1: rebuild only (Coolify pulls latest git, rebuilds image, restarts container)
fabrik redeploy my-api                         # by name
fabrik redeploy qokoksogwsk0c04gcs4swwgs       # by UUID
fabrik redeploy my-api --force                 # bypass build cache

# Mode 2: re-run only the InfrastructureProvisioner against the existing app
# Use when you added a shape flag (e.g. needs_database, has_search_feature, has_persistent_data)
# after the first deploy and want the new registrar to fire WITHOUT rebuilding the image.
fabrik redeploy --refresh-infra --spec specs/services/my-api.yaml
fabrik redeploy --refresh-infra --spec specs/services/my-api.yaml --dry-run
```

Internally (`cli.py::redeploy()` L835–902):

- **Mode 1 (no `--refresh-infra`):**
  1. `CoolifyClient.list_applications()` — resolve name → UUID.
  2. `CoolifyClient.deploy(uuid, force)` — POSTs `/api/v1/deploy?uuid=…&force=true` on Coolify.
  3. `_post_deploy_sync()` — refreshes project registry.

  Pure rebuild: pulls the latest git commit (for git-sourced apps), rebuilds the image, restarts containers. Does **not** touch DNS, Authelia, GlitchTip, Gatus, Backrest, Meilisearch, or the database. Those were created on first `apply` / `deploy` and are expected to already exist.

- **Mode 2 (`--refresh-infra --spec PATH`):**
  1. Loads spec; resolves Coolify UUID by spec `name` (with `fabrik-` prefix fallback).
  2. `DeploymentOrchestrator.refresh_infrastructure(spec_path, dry_run)` — runs **only** `InfrastructureProvisioner.provision(ctx)`. No deploy stage, no verifier, no DNS provisioning.
  3. `_post_deploy_sync()`.

  Picks up newly-added shape flags (e.g. you set `needs_database: true` after the first deploy → DB gets created on the next `--refresh-infra` without rebuilding the container).

**DB schema changes are never auto-applied.** If your commit contains migrations, run them manually after redeploy completes:

```bash
ssh vps 'sudo docker exec -i <app-container> alembic upgrade head'
```

### 9.4 Tear down a service

`fabrik destroy` reverses the full provisioner chain (G3 closed 2026-05-05). Order in `orchestrator/destroyer.py::destroy_deployment()`:

1. **MeiliSearch index** — only with `--drop-data` (data preservation default).
2. **Authelia access rule** — if `shape.is_admin_dashboard`.
3. **GlitchTip project** — if `kind in {service, worker, wordpress}`.
4. **Backrest backup plan** — if `shape.has_persistent_data`.
5. **Gatus uptime endpoint** — if `shape.is_public` + domain set.
6. **Postgres database** — only with `--drop-data`.
7. **Coolify application** — always.
8. **DNS A record** — unless `--keep-dns`.
9. **Project tree** at `/opt/<id>/` — unless `--keep-files`.
10. `_post_deploy_sync()`.

```bash
# Default: data-preserving teardown (Postgres DB + Meilisearch index kept)
fabrik destroy specs/services/my-api.yaml

# Throwaway test cleanup — drop DB + Meilisearch index too
fabrik destroy specs/services/my-api.yaml --drop-data -y

# Keep DNS or files
fabrik destroy specs/services/my-api.yaml --keep-dns --keep-files

# Plan only — print every action, mutate nothing
fabrik destroy specs/services/my-api.yaml --dry-run

# Skip confirmation (CI)
fabrik destroy specs/services/my-api.yaml --yes
```

Per-step exit symbol in stdout: `✅ removed`, `ℹ️ not_found`, `⏭️ skipped`, `🧪 dry_run`, `❌ error`. Non-zero exit (`2`) if any step errored.

### 9.5 Provision a brand-new domain

```bash
# Check availability + pricing
fabrik domain check example.com

# Register (requires Namecheap credentials in .env)
fabrik domain buy example.com

# Full provision — DNS zone + CDN + WAF + Coolify-ready
fabrik domain provision example.com

# Wait until HTTPS is reachable (DNS + SSL both valid)
fabrik domain ready example.com
```

### 9.6 End-to-end validation (maximal-shape test)

The **canonical way to verify the deployment pipeline after any change** to a registrar driver, the orchestrator, or the compose template. Produces a project that exercises every code path in a single deploy.

```bash
# 1. Scaffold a throwaway project with a scratch image (fast feedback, no build)
fabrik scaffold fabrik-e2e-full-test --type python-api --db

# 2. Overwrite the auto-generated spec with a MAXIMAL-SHAPE spec:
#    every shape.* flag true, whoami image, health disabled, vps1.ocoron.com subdomain.
#    See CHANGELOG.md Unreleased for the exact spec used 2026-04-22.
cat > /opt/fabrik/specs/services/fabrik-e2e-full-test.yaml <<'EOF'
id: fabrik-e2e-full-test
kind: service
template: python-api
domain: fabrik-e2e-full-test.vps1.ocoron.com
shape:
  kind: service
  is_public: true
  is_admin_dashboard: true
  has_bearer_api: true
  has_persistent_data: true
  needs_database: true
  has_search_feature: true
source: {type: docker, image: traefik/whoami:latest, image_port: 80, image_command: --port 80}
expose: {http: true, internal_only: false}
coolify: {project: default, server: localhost}
health: {disabled: true, path: /}   # whoami has no shell
backup: {enabled: true, frequency: daily, retention: 30}
EOF

# 3. Deploy and time it
time fabrik deploy --project /opt/fabrik-e2e-full-test
# Expected: ~63s wall time (measured 2026-04-22, all 7 registrars green)

# 4. Verify every registrar touched the right place
ssh vps 'sudo docker ps --format "{{.Names}}" | grep fabrik-e2e-full'            # Coolify
ssh vps 'sudo docker exec traefik wget -qO- http://localhost:8080/api/http/routers' \
    | jq '[.[]|select(.name|contains("fabrik-e2e-full"))]'                        # Traefik
curl -sI https://fabrik-e2e-full-test.vps1.ocoron.com | head -3                    # Authelia 302 + LE cert
ssh vps 'sudo docker exec authelia-... grep -c fabrik-e2e-full /config/configuration.yml'  # Authelia rules (expect 2)
ssh vps 'sudo docker exec postgres-main-... psql -U postgres -tAc "SELECT datname FROM pg_database WHERE datname LIKE '"'"'fabrik_e2e_full%'"'"'"'       # Postgres
ssh vps 'sudo cat /opt/backrest/config/config.json' | jq '.plans[]|select(.id|contains("fabrik-e2e-full"))'  # Backrest
curl -s https://status.vps1.ocoron.com/api/v1/endpoints/statuses | jq '[.[]|select(.name|contains("fabrik-e2e-full"))]'  # Gatus
python -c "from fabrik.drivers.glitchtip import create_project; print(create_project('fabrik-e2e-full-test'))"       # GlitchTip (expect status=exists, dsn=...)
python -c "from fabrik.drivers.meilisearch import _resolve_container,_index_exists; print(_index_exists(_resolve_container(),'fabrik_e2e_full_test'))"   # MeiliSearch

# 5. Idempotency — re-run the same deploy; every registrar should report 'exists'
fabrik deploy --project /opt/fabrik-e2e-full-test

# 6. TEAR DOWN EVERYTHING (important — this is a throwaway test)
fabrik destroy /opt/fabrik/specs/services/fabrik-e2e-full-test.yaml -y
python -c "
from dotenv import load_dotenv; load_dotenv('/opt/fabrik/.env')
from fabrik.drivers.authelia import remove_access_rule
from fabrik.drivers.glitchtip import delete_project
from fabrik.drivers.meilisearch import delete_index
from fabrik.drivers.gatus import remove_endpoint
from fabrik.drivers.backrest import remove_backup_plan
remove_access_rule('fabrik-e2e-full-test.vps1.ocoron.com')
delete_project('fabrik-e2e-full-test')
delete_index('fabrik_e2e_full_test')
remove_endpoint('fabrik-e2e-full-test')
remove_backup_plan('fabrik-e2e-full-test-data')
"
ssh vps 'sudo docker exec postgres-main-... psql -U postgres -c "DROP DATABASE IF EXISTS fabrik_e2e_full_test"'
rm -rf /opt/fabrik-e2e-full-test /opt/fabrik/specs/services/fabrik-e2e-full-test.yaml
python scripts/sync_projects.py   # back to baseline project count
```

**Why this test matters:** every shape-gated code path runs exactly once per deploy. Problems hidden by smoke tests with `infra.glitchtip: false` / `has_search_feature: false` surface here. Lesson 31 (`docker inspect` not `docker exec` for env-var reads) was discovered by exactly this test on 2026-04-22.

**Timing benchmark (reference, 2026-04-22 VPS, maximal shape, whoami image, Coolify auto-deploy):**

| Phase | Time |
|---|---|
| Coolify API create + initial deploy | ~15–25s |
| Container pull + start | ~5–10s |
| GlitchTip DSN injection + verify | ~10–20s |
| Remaining registrars (authelia, gatus, backrest, grafana, meilisearch, postgres) | ~10–15s |
| **Total wall time** | **~63s** |

A real app with a Dockerfile build adds 30s–3min depending on cache state. DNS propagation is excluded (domains are pre-registered under `*.vps1.ocoron.com`).

### 9.7 Emergency: delete an orphaned Coolify app via API

```bash
# From VPS (bypasses iptables)
curl -X DELETE \
  -H "Authorization: Bearer $COOLIFY_API_TOKEN" \
  "https://coolify.vps1.ocoron.com/api/v1/applications/<uuid>"
```

### 9.8 Rollback (automatic)

Orchestrator catches any exception, transitions to `ROLLING_BACK`, and calls `RollbackManager.rollback(ctx)`. Reverse-order cleanup of every `ctx.resources[*]`:

- `dns_record` → delete
- `coolify_application` → delete (in-flight deploy grace period — planned, Phase 4-pre Task 2)
- `glitchtip_project` → delete
- `grafana_annotation` → delete
- `authelia_rule` → remove_access_rule
- `gatus_endpoint` → remove + commit
- `backrest_plan` → remove_backup_plan
- `database_schema` → **NOT auto-dropped** — logged for operator review

### 9.9 Infrastructure-service coverage matrix (what gets registered, what doesn't)

The user's requested list vs. the code as of 2026-05-04. "Auto" means no per-service action needed on deploy; "Registrar" means a real call-out in `InfrastructureProvisioner`.

| Infra service | Per-service registration on deploy? | Mechanism | Status | Gap? |
|---|---|---|---|---|
| **PostgreSQL** (shared `postgres-main`) | Yes — creates DB `<snake_name>` when `shape.needs_database` | `drivers/postgres.py::create_database()` | ✅ implemented | — |
| **Redis** (shared) | **No** | No registrar. Apps get a raw `REDIS_URL` env; no DB-index or namespace isolation. | ⚠️ **missing** | Build `drivers/redis.py` if multi-tenant isolation matters. Currently fine because only 2 services use Redis. |
| **Traefik** | Implicit | Coolify writes Traefik labels from compose; Traefik picks up automatically. No registrar needed. | ✅ auto | — |
| **GlitchTip (web)** | Yes — creates Sentry project + DSN; `docker inspect` verifies `SENTRY_DSN` in container | `drivers/glitchtip.py::create_project()` + `verify_dsn_injection()` | ✅ implemented (fatal-on-fail) | — |
| **GlitchTip worker** | N/A | "Web + worker" refers to GlitchTip's own compose components, not per-app registration. Celery worker just processes events the web tier ingests. | ✅ auto | — |
| **Grafana** | Yes — writes a global deployment annotation | `drivers/grafana.py::post_deployment_annotation()` | ✅ implemented (non-fatal) | Per-service dashboards are **not** auto-generated (manual). |
| **Loki** | Auto | Promtail scrapes `/var/lib/docker/containers/*` on the VPS host — picks up every new container automatically. No per-service config. | ✅ auto | — |
| **Promtail** | Auto | Config is static in `/opt/monitoring/configs/promtail/promtail-config.yaml`; container auto-discovery via Docker socket. | ✅ auto | — |
| **Prometheus** | **No** | Scrape targets live in `configs/prometheus/prometheus.yml` and are **static**. No registrar appends a scrape_config per service. `cadvisor` + `node-exporter` cover container-level metrics automatically, but app-level `/metrics` endpoints are **not** wired. | ⚠️ **missing** | Build `drivers/prometheus.py::add_scrape_target(job, target)` when/if a service exposes `/metrics`. Not blocking today — no Fabrik service exports Prometheus metrics yet. |
| **Alertmanager** | **No** | Receivers/routes are static (`configs/alertmanager/alertmanager.yml`). Per-service alert routes (e.g., "app X owner → webhook Y") are manual. | ⚠️ **missing** | Only relevant once per-service alert policies are wanted. Defer. |
| **cAdvisor** | Auto | Discovers all containers via Docker socket. No per-service config. | ✅ auto | — |
| **node-exporter** | Auto | Host-level only; no per-service config. | ✅ auto | — |
| **Netdata** | Auto | Discovers all containers via Docker socket (`/var/run/docker.sock`). | ✅ auto | — |
| **Authelia** | Yes — `docker cp` configuration.yml patch: `access_control` rule + optional `^/api/` bypass | `drivers/authelia.py::add_access_rule()` | ✅ implemented | — |
| **Gatus** | Yes — writes `/opt/monitoring/configs/gatus/apps/<service>.yaml` (git-versioned) | `drivers/gatus.py::add_endpoint()` | ✅ implemented | — |
| **Backrest** | Yes — adds Restic backup plan when `shape.has_persistent_data` | `drivers/backrest.py::add_backup_plan()` | ✅ implemented | — |
| **Meilisearch** | Yes — creates index when `shape.has_search_feature` | `drivers/meilisearch.py::create_index()` | ✅ implemented | — |

**Gaps to build (reported for prioritisation, not auto-built):**

| # | Gap | Fix recipe | Blocking today? |
|---|---|---|---|
| G1 | ~~`fabrik apply` (default legacy path) **silently skips** the entire `InfrastructureProvisioner`.~~ | **✅ CLOSED 2026-05-05** (commit `9d9a1be`) — `cli.py::apply()` now runs the orchestrator pipeline by default; legacy path is opt-in via `--legacy`. `--use-orchestrator` kept as deprecated no-op. Verified end-to-end with live proxy redeploy: 3 applicable registrars (gatus, glitchtip, grafana) all fired. | ✅ Closed |
| G2 | ~~`fabrik redeploy` does not pick up spec-shape changes (e.g., newly added `needs_database`).~~ | **✅ CLOSED 2026-05-05** — `fabrik redeploy --refresh-infra --spec PATH` re-runs only the `InfrastructureProvisioner` against the existing Coolify app. No DNS provisioning, no code rebuild, no verifier. New method: `DeploymentOrchestrator.refresh_infrastructure(spec_path)`. Resolves UUID by spec name (with `fabrik-` prefix fallback). Tests: `@/opt/fabrik/tests/orchestrator/test_refresh_infrastructure.py`. Verified live on `proxy` spec: 3 registrars fired (gatus, glitchtip, grafana annotation). | ✅ Closed |
| G3 | ~~`fabrik destroy` does **not** unregister from GlitchTip / Gatus / Authelia / Backrest / Meilisearch — it only deletes the Coolify app + DNS record.~~ | **✅ Already implemented** — `orchestrator/destroyer.py::destroy_deployment()` reverses the full 7-registrar chain in strict reverse-of-provision order (meilisearch → authelia → glitchtip → backrest → gatus → postgres → coolify → dns → files). Verified 2026-05-05: `fabrik destroy specs/services/proxy.yaml` cleanly removed GlitchTip project, Gatus endpoint, Coolify app, DNS A record; Postgres preserved per `infra.postgres: false` override. The original gap claim was stale; this row is kept for historical accountability. | ✅ Already done |
| G4 | ~~**Redis** has no per-service registrar.~~ | **✅ CLOSED** — `shape.needs_cache` flag (`spec_loader.Shape:297`) gates `_provision_redis` (`orchestrator/infrastructure.py:534`) which calls `drivers/redis.py` to allocate an isolated logical DB. Off by default in every template; opt in per spec. | ✅ Closed |
| G5 | ~~**Prometheus scrape target** registration.~~ | **✅ CLOSED** — `shape.exposes_metrics` flag (`spec_loader.Shape:306`) gates `_provision_prometheus` (`orchestrator/infrastructure.py:577`) which calls `drivers/prometheus.py` to append a scrape target and reload Prometheus. Domain-gated (scrape over public HTTPS — same rationale as Gatus). Off by default in every template; opt in per spec. | ✅ Closed |
| G6 | `scripts/vps_sync.py` pulls container state but does **not** cross-check that every project in `data/projects.yaml` has a live container (drift detector). | Add a `--verify` flag that flags projects with no matching container + registrar (GlitchTip/Gatus) orphans. | No — nice-to-have. |
| G7 | ~~GlitchTip DSNs are created with `GLITCHTIP_URL=http://localhost:8000` as the DSN host. Proxy's live DSN reads `http://bb2d...@localhost:8000/60` — **useless from inside the container**.~~ | **✅ CLOSED 2026-05-05** — `drivers/glitchtip.py::_canonicalize_dsn()` rewrites loopback DSNs (`localhost`/`127.0.0.1`/`0.0.0.0`) to the public `https://errors.vps1.ocoron.com` host before injection. `_assert_routable_dsn()` is invoked from both `_fetch_dsn` and `verify_dsn_injection`, so any malformed-loopback value still slipping through fails loud instead of silently breaking error reporting. Verified live on `proxy`: container env now shows `SENTRY_DSN=https://a3c3ff18…@errors.vps1.ocoron.com/61` (project id 61, fresh canonical DSN). The driver-level fix is self-healing; the upstream `GLITCHTIP_DOMAIN` env on the GlitchTip Coolify app is still unset and tracked as a follow-up nice-to-have (touching it bounces every service's error stream during the GlitchTip restart). | ✅ Closed |
| G8 | ~~Coolify env-var POST returns 409 when the key already exists; every re-apply logged noisy ERRORs. The code actually retried via PATCH so values were preserved, but updates to existing keys could slip through unnoticed.~~ | **✅ CLOSED 2026-05-05** — `drivers/coolify.py::bulk_update_env_vars()` now pre-fetches the current env list, picks POST (create) or PATCH (update) per key, and only falls back to POST-then-409-retry if the pre-fetch GET fails. Regression tests at `@/opt/fabrik/tests/drivers/test_coolify.py`. Verified with a live proxy re-apply: zero 409 noise. | ✅ Closed |
| G9 | ~~`drivers/dns.py` pins a static container IP for `site-provisioner` via `SITE_PROVISIONER_INTERNAL_URL`; every Coolify rebuild of the provisioner container changed the IP and broke all subsequent DNS calls.~~ | **✅ CLOSED 2026-05-05** (commit `9d9a1be`) — driver now resolves live IP via `docker inspect` over SSH when `SITE_PROVISIONER_CONTAINER` is set. Static internal URL kept as fallback. Verified: stale `10.0.1.35` → live `10.0.1.25`, health returns `{'status': 'healthy'}`. | ✅ Closed |
| G10 | ~~`vps_sync.py --verify` only checked stale Gatus aliases; no audit for test residue across Coolify/GlitchTip/Postgres/Meili/DNS/Docker.~~ | **✅ CLOSED 2026-05-06** — `verify_residue()` added: 12-point audit (Coolify apps, GlitchTip projects, Gatus .bak files, Authelia orphan rules, Postgres DBs, Meilisearch indexes, Cloudflare DNS records, Docker dangling volumes/images, /tmp locks, /opt stale dirs, Backrest repos) with inline remediation commands, exit 1 on findings. Drift detection now covers both Gatus alias drift and full test residue cleanup. | ✅ Closed |

---

### 9.10 Template-defaults registrar matrix (what fires on `fabrik apply` by default)

Source of truth: live `templates/*/defaults.yaml` as of 2026-05-06. Derived by running
`resolve_applicability()` against each template's default shape.

✅ = fires by default (when `spec.domain` set where noted) · ⚙ = opt-in via spec flag · ✗ = never applicable

| Template | kind | postgres | redis | gatus | backrest | glitchtip | grafana | authelia | meili | prometheus | DNS | Traefik | Loki/cAdvisor/etc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **python-api** | service | ⚙ | ⚙ | ✅* | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ⚙ | ✅* | auto | auto |
| **node-api** | service | ⚙ | ⚙ | ✅* | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ⚙ | ✅* | auto | auto |
| **saas-skeleton** | service | ✅ | ⚙ | ✅* | ✅ | ✅ | ✅ | ⚙ | ⚙ | ⚙ | ✅* | auto | auto |
| **next-tailwind** | service | ⚙ | ⚙ | ✅* | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ⚙ | ✅* | auto | auto |
| **static-site** | static | ⚙ | ⚙ | ✅* | ⚙ | ✗ | ✅ | ⚙ | ⚙ | ⚙ | ✅* | auto | auto |
| **docusaurus** | static | ⚙ | ⚙ | ✅* | ⚙ | ✗ | ✅ | ⚙ | ⚙ | ⚙ | ✅* | auto | auto |
| **wordpress** | wordpress | ✅ | ⚙ | ✅* | ✅ | ✅ | ✅ | ⚙ | ⚙ | ⚙ | ✅* | auto | auto |
| **file-api** | service | ⚙ | ⚙ | ✅* | ✅ | ✅ | ✅ | ⚙ | ⚙ | ⚙ | ✅* | auto | auto |
| **file-worker** | worker | ⚙ | ⚙ | ✗ | ✅ | ✅ | ✅ | ✗ | ⚙ | ✗ | ✗ | ✗ | auto |
| **chrome-extension** _(backend)_ | service | ⚙ | ⚙ | ⚙ | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ⚙ | ⚙ | auto | auto |
| **desktop-app** _(backend)_ | service | ⚙ | ⚙ | ⚙ | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ⚙ | ⚙ | auto | auto |
| **mobile-app** _(backend)_ | service | ⚙ | ⚙ | ⚙ | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ⚙ | ⚙ | auto | auto |

`*` requires `spec.domain` to be set.
chrome/desktop/mobile backends default `is_public: false` — Gatus is opt-in (flip `is_public: true` in spec when the backend has a stable public domain).

## 10. Secrets & `.env`

### 10.1 Precedence

```text
1. Command-line -s KEY=VALUE flags (highest)
2. Project .env file        (/opt/<project>/.env)
3. Fabrik .env file         (/opt/fabrik/.env)
4. Process environment      (lowest)
```

### 10.2 Auto-detected from `.env.example`

`fabrik scaffold` scans `.env.example` for env vars matching `_KEY`, `_SECRET`, `_PASSWORD`, `_TOKEN`, `_CREDENTIALS` and adds them to the spec's `secrets.from_env` field. `fabrik apply` then loads them from the project `.env` at deploy time.

### 10.3 Safe handling

```bash
# ✅ Correct: extract a single value without shell-eval of the line
TOKEN=$(grep -E '^GRAFANA_SERVICE_ACCOUNT_TOKEN=' /opt/fabrik/.env | head -1 | cut -d= -f2-)

# ❌ Wrong: sourcing .env evaluates values as shell — Coolify tokens contain `|`
set -a; source /opt/fabrik/.env; set +a   # breaks on lines like "TOKEN=5|secret..."
```

Python: always `python-dotenv` or `pydantic-settings`.

### 10.4 Canonical env vars

| Variable | Used by | Source |
|---|---|---|
| `COOLIFY_API_TOKEN` | All Coolify API calls | Coolify UI → create API token |
| `COOLIFY_API_URL` | All Coolify API calls | `https://coolify.vps1.ocoron.com` (VPS) or `http://localhost:8002` (WSL via tunnel) |
| `FABRIK_VPS_SSH_HOST` | `drivers/ssh.py`, `drivers/locks.py` | Defaults to `vps`; set in `~/.ssh/config` |
| `SITE_PROVISIONER_API_KEY` | `drivers/dns.py` | site-provisioner admin |
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID` | `drivers/cloudflare.py` fallback | Cloudflare dashboard |
| `GRAFANA_SERVICE_ACCOUNT_TOKEN` | planned `drivers/grafana.py` | Grafana → Service Accounts |
| `GRAFANA_ADMIN_PASSWORD` | Grafana login | generated by `scripts/provision_grafana.sh` |
| `GLITCHTIP_AUTH_TOKEN`, `GLITCHTIP_ORG_SLUG`, `GLITCHTIP_TEAM_SLUG`, `GLITCHTIP_ADMIN_EMAIL`, `GLITCHTIP_ADMIN_PASSWORD` | planned `drivers/glitchtip.py` | GlitchTip UI + Django `./manage.py shell` |
| `TELEGRAM_FULL_BOT_TOKEN` | Alertmanager, Gatus-via-Apprise | Telegram BotFather (**joined form** `<id>:<secret>`) |
| `TELEGRAM_CHAT_ID` | Same | `getUpdates` API |
| `GITHUB_TOKEN` | scaffold's CI workflow generation | GitHub personal access token |

---

| `SERVICE_INTERNAL_SECRET_KEY` | All Fabrik API services | Shared M2M secret. One value, all services. Copy from `/opt/fabrik/.env`. Push to Coolify env for every deployed API service. Never rotated manually. |
| `DATABASE_URL` / `DB_HOST` | Python services with DB | Always `postgres-main:5432` — never `localhost` (inside container, localhost = the container itself). |
| `REDIS_URL` | Services using Redis | Always `redis-main:6379` — never `localhost`. |

## 11. Key Invariants Summary (from LESSONS_LEARNT)

Every invariant below has a live-incident writeup in `docs/LESSONS_LEARNT.md`. Cross-reference the lesson number when adding new deploy code.

| # | Invariant | Section |
|---|---|---|
| 1 | Base64-encode `docker_compose_raw` for every Coolify API call | Lesson 1 |
| 2 | Restart Traefik after new service deployment if routes don't appear | Lesson 2, 26 |
| 3 | Verify container network membership with `docker inspect`, not just compose | Lesson 3 |
| 4 | Parallel-test critical services before traffic cutover | Lesson 4 |
| 5 | Use `Applications` endpoint for custom Docker Compose; `Services` for one-clicks | Lesson 5 |
| 6 | Use `external: true` volumes with exact names to preserve data during migration | Lesson 6 |
| 7 | `APP_URL` in Coolify must be external host, not `localhost` | Lesson 7, 14 |
| 8 | Update Gatus config after container renames | Lesson 8 |
| 10 | Coolify real-time service needs port 6001 | Lesson 10 |
| 11 | Post-migration cleanup prevents orphaned volumes | Lesson 11 |
| 17 | Traefik router name conflicts silently fail | Lesson 17 |
| 19 | Config file migration required for Coolify volumes | Lesson 19 |
| 22 | Use dynamic container-name lookup for Coolify services | Lesson 22 |
| 25 | Monitoring-stack services need `coolify` external network (9 services fixed 2026-04-18) | Lesson 25 |
| 25 §8.1 | Never point Alertmanager → Apprise `/notify` (schema mismatch) | §8.1 |
| 25 §8.2 | Docker embedded DNS can return AAAA-only after cross-network restart | §8.2 |
| 25 §8.3 | Telegram `bot_token` is `<id>:<secret>`, not the secret alone | §8.3 |
| 25 §8.4 | sed placeholders must appear only at substitution sites | §8.4 |
| 25 §8.5 | `.gitignore` any config file that may embed a secret | §8.5 |
| 25 §8.6 | Config-on-disk ≠ config-in-use for Coolify-managed services | §8.6 |
| 25 §8.7 | Coolify does NOT auto-inject Traefik labels after compose PATCH — be explicit | §8.7 |
| 25 §8.8 | Coolify's own UI needs `docker-compose.override.yml` for label changes | §8.8 |
| 25 §8.9 | Authelia policy without Traefik middleware is NOT enforced | §8.9 |
| 25 §8.10 | Git-sourced Coolify apps ignore `PATCH docker_compose_raw` — edit the repo | §8.10 |
| 25 §8.11 | Authelia forward-auth on Coolify UI blocks the API — add `^/api/` bypass | §8.11 |
| 25 §8.12 | Multi-network containers need `traefik.docker.network=coolify` label | §8.12 |
| 25 §8.13 | Authelia forward-auth breaks SPA auth flows (django-allauth etc.); use app-layer TOTP | §8.13 |
| 25 §8.14 | Never `source` `.env` files with shell metacharacters; use `grep \| cut` | §8.14 |
| 30 | Healthchecks that reference tools absent from the container image (`wget`/`curl` on scratch) make Coolify 422 the deploy — keep `health.disabled: true` for scratch/distroless; template uses positive logic `{% if health and not health.disabled %}` | Lesson 30 |
| 31 | Verify container env vars with `docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}'`, **never** `docker exec printenv` (fails on scratch/distroless with `OCI runtime exec failed`) | Lesson 31 |

---

### 11.x New Lessons (2026-05-06/07)

| Lesson | Rule |
|---|---|
| SIGHUP to Authelia exits the process (no hot-reload) | Always `docker restart <authelia-container>` after config changes. Never SIGHUP. |
| cadvisor OOM at 256m with 40 containers | Set to 512m + add `--docker_only=true --disable_metrics=sched,tcp,udp,percpu,advtcp,hugetlb,...` to compose command |
| Prometheus OOM at 512m scraping 40 containers | Set to 1g minimum + `--storage.tsdb.retention.size=5GB` |
| Netdata cache unbounded growth (hit 2.2GB) | Set `NETDATA_DBENGINE_DISK_SPACE_MB=512` + `NETDATA_DBENGINE_RETENTION_DAYS=7` |
| Per-service `X-API-Key` with different env var names | Canonical pattern: `X-Internal-Token` header + `SERVICE_INTERNAL_SECRET_KEY`; one shared key |
| `from internal_auth import` fails when uvicorn uses `app.main:app` | Import must match module path: `from app.internal_auth import` when `uvicorn app.main:app` |
| Prometheus lifecycle reload (`curl -X POST /-/reload`) fails — no curl in image | Use `cd /opt/prometheus && sudo docker compose restart` instead |
| Business metrics: scaffold now emits `metrics.py` + `/metrics` endpoint |
| Gatus UUID container names break silently on Coolify Application redeploy | Three-layer fix: compose alias + `docker network connect --alias` + `vps_apply_limits.sh apply_alias()`. Service stacks are stable; single-image Applications need the alias treatment. See CROSS_CUTTING_REQUIREMENTS.md §9. | `prometheus-client>=0.21.0` in requirements; `fabrik-services` job in prometheus.yml (targets commented) |

## Appendix A: Quick reference — where to look

| I want to... | Look at |
|---|---|
| Add a CLI command | `src/fabrik/cli.py` — but put the logic in a driver or orchestrator stage |
| Add support for a new external API | Create `src/fabrik/drivers/<name>.py` |
| Change how secrets are loaded | `src/fabrik/orchestrator/secrets.py` |
| Change spec schema | `src/fabrik/spec_loader.py` (update `Spec` pydantic model) |
| Change default scaffold layout | `templates/<type>/` and `src/fabrik/scaffold.py` |
| Add a pre-deploy invariant check | `scripts/enforcement/check_<name>.py` + wire into `final_gate.py` |
| Add a contract test for a 3rd-party API | `scripts/probes/<service>_probe.sh` + doc in `docs/reference/` |
| Change Authelia access rules | §7.3 above |
| Change a Prometheus alert threshold | `configs/prometheus/rules/alerts.yml` + reload Prometheus |
| Change Alertmanager routing | `configs/alertmanager/alertmanager.yml` + restart Alertmanager |
| Change Grafana dashboards | Grafana UI → export JSON → commit to `configs/grafana/` (planned) |

## Appendix B: Related documents

- `docs/LESSONS_LEARNT.md` — every live-incident invariant
- `docs/infrastructure/vps-complete-inventory.md` — what runs on the VPS right now
- `docs/reference/glitchtip-api.md` — live-captured GlitchTip API contract
- `docs/development/plans/2026-04-18-zero-touch-deployment.md` — the Phase 4 plan
- `docs/CROSS_CUTTING_REQUIREMENTS.md` — doc currency, observability, Docusaurus, reusability rules
- `AGENTS.md` — Fabrik identity + tech-stack defaults (for Traycer)
- `AGENTS-compact.md` — same, condensed for coding agents
- `.windsurf/rules/` — Cascade rules (ports, Python, TS, ops, code review, saas UI)
