# Deployment — Canonical Reference

**Purpose:** this file is the **single entry point** any AI coder or human operator reads to understand how Fabrik deploys services to the VPS. Every file involved in a deploy is cataloged below with its function and cross-references. If you are about to touch deployment behavior, **read this file end-to-end first**.

**Last Updated:** 2026-05-29 (verified end-to-end against source; 2026-05-28 was the full rewrite: Coolify API → SSH + Docker Compose deployer)
**Previous version:** `docs/archive/2026-04-28-DEPLOYMENT.md.backup.20260419-144040`

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
11. [Key Invariants Summary](#11-key-invariants-summary)

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
│   2. SecretsManager         (os.environ incl -s flags → .env → generate) │
│   3. DNSClient              (drivers/dns.py → site-provisioner)          │
│   4. SSHDeployer            (deployer_ssh.py → SCP compose + .env        │
│                              then ssh: docker compose up -d --wait)       │
│   5. InfrastructureProvisioner (shape-driven, 9 registrars:             │
│         postgres · redis · gatus · backrest · glitchtip+DSN ·            │
│         grafana · authelia+bypass · meilisearch · prometheus)            │
│   6. DeploymentVerifier     (orchestrator/verifier.py — HTTP 200,        │
│                              DSN injected, DNS resolves, SSL valid)      │
│                                                                          │
│   on failure ⇒ RollbackManager (orchestrator/rollback.py, reverse order) │
└──────────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  VPS: Docker Compose → Traefik → Container                               │
│  Security: iptables DOCKER-USER · Authelia · X-Internal · Bearer token   │
│  Observability: Prometheus+AM → Telegram  ·  Gatus → Apprise → Telegram  │
└──────────────────────────────────────────────────────────────────────────┘
```

**Deploy method:** SSH + Docker Compose (direct to VPS — no intermediary platform). The deployer renders compose files locally, copies them to the VPS via SCP (using a scp-to-tmp-then-sudo-mv pattern for root-owned paths), and runs `docker compose up -d --wait` over SSH. All state lives on the VPS filesystem at `/opt/<name>/`.

---

## 2. Fabrik Source Code — Deployment Path

Every Python file below is **on the deployment critical path**. Files not listed here (e.g., `wordpress/`, `ai/`, `content/`) are adjacent systems that ride on top of the deployment primitives.

### 2.1 CLI entry points — `src/fabrik/cli.py`

Click-based CLI. The commands below are the only public entry points for deployment work. Each delegates to modules in this document — **do not add deploy logic here**; add it to an orchestrator stage or driver and call from the CLI.

| Command | Line | Function | Delegates to |
|---|---|---|---|
| `fabrik scaffold <name> --type <t>` | 1561 | Create `/opt/<name>/` tree; generate spec at `specs/services/<name>.yaml`; allocate port; emit `.env.example`. | `scaffold.py` |
| `fabrik apply <spec.yaml>` | 382 | **Primary deploy entry point. Orchestrator pipeline (full 9-registrar sweep).** Flags: `--dry-run`, `--skip-dns`, `--skip-deploy`, `-s KEY=VALUE`, `--legacy` (opt out, render-only path), `--keep-on-failure` (proof-run only). | `orchestrator/DeploymentOrchestrator.deploy()` (default) or `deploy.py::deploy_to_coolify()` (`--legacy`, dead code) |
| `fabrik redeploy <app>` | 1182 | Rebuild-only SSH deploy by name. With `--refresh-infra --spec PATH` re-runs the `InfrastructureProvisioner` against the existing app (no rebuild). `--force`, `--dry-run`. | `SSHDeployer` (direct SSH commands) or `DeploymentOrchestrator.refresh_infrastructure()` |
| `fabrik destroy <spec>` | 896 | Tear down **all 9 registrars** in reverse-of-provision order + compose app + DNS. `--keep-dns`, `--drop-data`, `--dry-run`, `--use-state`, `--partial`. | `orchestrator/destroyer.py::destroy_deployment()` or `destroy_from_state()` |
| `fabrik vps-sync [--dry-run]` | 1137 | Refresh VPS docs (`vps-status.md`, `vps-urls.md`, `vps-complete-inventory.md`) from live `docker ps`; rerun `sync_projects.py`. Read-only on VPS. | `scripts/vps_sync.py` |
| `fabrik validate-deploy <project>` | 1715 | Pre-flight readiness check for a scaffolded project. | `deploy_validator.validate()` |
| `fabrik domain provision <domain>` | 2153 | Register domain + DNS + CDN via site-provisioner. | `drivers/dns.py::DNSClient` |
| `fabrik domain ready <domain>` | 2240 | Poll DNS + SSL readiness before deploying. | `drivers/dns.py::DNSClient` |
| `fabrik domain buy <domain>` | 2366 | Register a new domain via Namecheap. | `drivers/dns.py::DNSClient::register_domain()` |
| `fabrik wp plan/apply/verify/flush` | — | WordPress sub-pipeline. **Moved to `/opt/wpf/`** standalone project (no longer in fabrik CLI). | `wpf/` (separate repo) |

### 2.2 Orchestrator — `src/fabrik/orchestrator/`

The deployment pipeline. **Default since 2026-05-05** for `fabrik apply` (the single deploy command).

| File | Class / function | Role in deploy |
|---|---|---|
| `orchestrator/__init__.py` | `DeploymentOrchestrator.deploy(spec_path, dry_run)` | Top-level runner (line 79). Drives the state machine; calls each stage in order; wires in `RollbackManager` on error. Constructor takes optional `deployer: SSHDeployer` (defaults to `SSHDeployer()` at line 72) and `infrastructure_provisioner: InfrastructureProvisioner` (defaults with `deployer=self.deployer` at line 75-77). |
| `orchestrator/context.py` | `DeploymentContext`, `ResourceRecord` | Shared state across stages (spec, spec_hash, `coolify_uuid` — now stores app name despite the field name, `dns_records`, list of created resources). Every resource that can be rolled back calls `ctx.add_resource(...)`. |
| `orchestrator/states.py` | `DeploymentState`, `can_transition()` | State machine enum: `PENDING → VALIDATING → PROVISIONING → DEPLOYING → VERIFYING → COMPLETE` / `FAILED → ROLLING_BACK → ROLLED_BACK`. Illegal transitions raise `InvalidStateTransitionError`. |
| `orchestrator/validator.py` | `SpecValidator.validate(spec)`, `validate_domain_security()`, `compute_spec_hash()` | Spec validation (required-field + type checks on the parsed dict) + SSRF check (no private IPs, no reserved ranges) + idempotency hash. |
| `orchestrator/secrets.py` | `SecretsManager`, `generate_secret()`, `load_dotenv()` | Load secrets precedence: `os.environ` (checked first — includes `-s KEY=VALUE` flags injected by CLI) → project `.env` → auto-generate. CSPRNG for generated secrets (`secrets.choice()`, 32 chars). |
| `orchestrator/deployer_ssh.py` | `SSHDeployer.deploy(ctx)`, `SSHDeployer.find_existing(name)` | SSH+Docker Compose deployer. Dispatches by source type (TEMPLATE, GIT, DOCKER, LOCAL). Writes compose.yaml + .env to VPS via SCP, runs `docker compose up -d --wait`. Returns app name (stored in `ctx.coolify_uuid` for backward compat). Also validates compose against rule-pack constraints before deploy. |
| `orchestrator/infrastructure.py` | `InfrastructureProvisioner.provision(ctx)`, `resolve_applicability(shape)`, `format_resolved_summary()` | Shape-driven dispatcher. Invoked between Deploy and Verify. Decides per-registrar applicability (`postgres`, `redis`, `gatus`, `backrest`, `glitchtip`, `grafana`, `authelia`, `meilisearch`, `prometheus`), then calls each driver's `create_*`/`add_*` entry in contract order. Each registrar failure is logged non-fatal **except glitchtip's `verify_dsn_injection` mismatch**, which rolls back the GlitchTip project and re-raises. |
| `orchestrator/verifier.py` | `DeploymentVerifier.verify(ctx)` | Post-conditions: HTTP 200 on `/health`; DNS resolves to VPS IP; SSL cert valid; `SENTRY_DSN` in container env (when GlitchTip provisioned) — verified via `docker inspect`, never `docker exec` (Lesson 31). |
| `orchestrator/rollback.py` | `RollbackManager.rollback(ctx)` | Reverse-order cleanup of every `ctx.created_resources[*]`. Resource type `compose` → `SSHDeployer.delete()`. Destructive actions (DB drops, MeiliSearch index deletes) are **logged for operator**, not auto-executed. Config mutations and ephemeral resources are auto-cleaned. |
| `orchestrator/destroyer.py` | `destroy_deployment()`, `destroy_from_state()` | Symmetric inverse of provisioner. Walks registrars in reverse order, calls each driver's remove/delete. Data-bearing registrars (postgres, redis, meilisearch) skipped unless `--drop-data`. |
| `orchestrator/exceptions.py` | Typed exceptions | `DeploymentError`, `ValidationError`, `ProvisioningError`, `DeployError`, `VerificationError`, `RollbackError`, `InvalidStateTransitionError`. Orchestrator catches these and routes to rollback. |

**Legacy file:** `orchestrator/deployer_coolify.py` — archived `git mv` of the old Coolify deployer. Available for reference only; not imported by any active code path.

### 2.3 Spec & template layer

| File | Role |
|---|---|
| `src/fabrik/spec_loader.py` | Parse `.yaml` spec → pydantic `Spec` model. Defines every valid field: `DNSConfig` (+ `DNSRecord`), `Source` (with `path` field for LOCAL source), `Expose`, `Resources`, `Health`, `Volume`, `Backup`, `SecretsPolicy`, `CoolifyConfig` (legacy, unused by orchestrator), `Depends`, `Infrastructure`. The `Shape` sub-model enforces `model_config = {"extra": "forbid"}`; the top-level `Spec` model does not. Entry points: `load_spec(path)`, `save_spec(spec, path)`, `create_spec(name, kind, ...)`. |
| `src/fabrik/template_renderer.py` | `TemplateRenderer(spec).render(output_dir)` → writes `compose.yaml` + `Dockerfile` + auxiliary files from `templates/<type>/*.j2`. `list_templates()` enumerates available templates. |
| `src/fabrik/scaffold.py` | The entire `fabrik scaffold` command. Generates `/opt/<name>/` tree; emits `project.yaml`, `specs/services/<name>.yaml`, `.env.example`, `README.md`, tests, CI workflow. Reads `templates/<type>/defaults.yaml` for shape flags. |
| `src/fabrik/compose_linter.py` | `ComposeLinter.lint(compose_yaml)` — validates Fabrik deployment constraints: `container_name` **required** (warning), `restart` policy required, healthcheck recommended for databases, no unresolved `${VAR}` without defaults. |
| `src/fabrik/registry.py` | `ProjectRegistry` — manages `/opt/fabrik/data/projects.yaml`. Tracks every project (path, type, spec hash, last deploy). Consulted by `scripts/sync_projects.py`. |

### 2.4 Drivers — `src/fabrik/drivers/`

**Drivers are the only place that talks to external APIs or the VPS.** Every deploy mutation goes through exactly one driver. Add `drivers/<name>.py` when integrating a new external system; do not bypass via ad-hoc HTTP/SSH calls in orchestrator or CLI code.

| File | Class / entry point | External system | Used during deploy for |
|---|---|---|---|
| `drivers/ssh.py` | `ssh(cmd, timeout, dry_run)`, `scp_to_vps(src, dst)` | SSH to VPS (host alias `vps`, configurable via `FABRIK_VPS_SSH_HOST`) | **Primary deploy driver.** All VPS mutations go through SSH. Non-zero exits raise `RuntimeError` with stderr included. |
| `drivers/locks.py` | `run_locked(resource, script, timeout)`, `git_commit_config(path)` | VPS `flock -x -w` + git | Multi-step VPS mutations that must be serialized (Authelia config edits, Backrest config edits). `git_commit_config()` whitelist: **only** `/opt/monitoring/configs/gatus` may be committed; secret-bearing configs use `.bak.{ts}`. |
| `drivers/dns.py` | `DNSClient`, `DNSRecord`, `add_dns_record()` | site-provisioner service (`dns.vps1.ocoron.com`) | Domain registration, A/CNAME/TXT record management, Cloudflare zone provisioning, SSL readiness polling. Auth via `SITE_PROVISIONER_API_KEY` + `X-API-Key` header. |
| `drivers/cloudflare.py` | `CloudflareClient` | Cloudflare API (direct) | Fallback when site-provisioner unavailable. Needs `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ZONE_ID`. |
| `drivers/supabase.py` | `SupabaseClient` | Supabase API | When `spec.infrastructure.database == supabase`: create project, user, run migrations. |
| `drivers/r2.py` | `R2Client` | Cloudflare R2 (S3-compatible) | Object storage ops when `spec.storage.type == r2`. |
| `drivers/image_broker.py` | `ImageBrokerClient` | image-broker microservice | Stock image fetching (content pipeline, **not deploy**). |
| `drivers/seo.py` | `SEOClient` | SEO microservice | Keyword research (content pipeline, **not deploy**). |
| `drivers/tco.py` | `TCOClient` | TCO AI service | Content generation (content pipeline, **not deploy**). |
| `drivers/wordpress.py` | `WordPressClient`, `WPSite`, `ContainerResolver` | WP-CLI via `docker exec` | WordPress-specific deploys (plugins, themes, settings). |
| `drivers/wordpress_api.py` | `WordPressAPIClient`, `WPCredentials`, `WPPost` | WordPress REST API | Content CRUD for WordPress sites. |

**Legacy driver (not on active deploy path):**

| File | Status | Notes |
|---|---|---|
| `drivers/coolify.py` | Legacy | Coolify v4 API client (~927 lines). On the active deploy path, only used by the rollback legacy path (`_rollback_coolify()`). (The former `_destroy_coolify_legacy()` destroy fallback has been removed.) Also still imported by broken CLI commands (`status`, `logs`, `reconcile-all`, `registry --sync`), `health_app.py`, `deploy.py`, `provisioner.py`, `portability.py`, `compose_updater.py`, and `drivers/__init__.py`. These are Phase 11-2 cleanup targets. |

**Shape-driven registrar drivers (all implemented):**

| File | Entry points | Purpose | Shape gate |
|---|---|---|---|
| `drivers/postgres.py` | `create_database()`, `drop_database()` | Creates per-service Postgres DB on `postgres-main` (SQL identifier validation upstream). Destructive drops deferred to operator. Does **not** inject `DATABASE_URL` — that comes from spec `env:` block or `ctx.secrets`. | `shape.needs_database` |
| `drivers/redis.py` | `acquire_db_index()`, `release_db_index()` | Allocates isolated Redis DB index on `redis-main`; injects `REDIS_URL` via `deployer.inject_env()`. | `shape.needs_cache` |
| `drivers/gatus.py` | `add_endpoint()`, `remove_endpoint()` | Writes per-service YAML file at `/opt/monitoring/configs/gatus/apps/<name>.yaml` (git-versioned). One file per project — safer than editing a shared config. | `shape.is_public` + `domain` set |
| `drivers/backrest.py` | `add_backup_plan()`, `remove_backup_plan()` | Restic-policy mutations via Backrest UI API. Uses `run_locked("backrest-config", ...)` with atomic `.tmp` → `json.tool` validate → `mv` pattern. | `shape.has_persistent_data` |
| `drivers/glitchtip.py` | `create_project()`, `delete_project()`, `verify_dsn_injection()` | Sentry-compatible API. **`verify_dsn_injection` reads env via `docker inspect`, never `docker exec`** (Lesson 31). Loopback DSNs auto-rewritten to public host via `_canonicalize_dsn()`. | `shape.kind in {service, worker, wordpress}` |
| `drivers/grafana.py` | `post_deployment_annotation()`, `delete_annotation()` | Global deployment annotations (`POST /api/annotations`). Non-fatal (decorative). Env var `GRAFANA_SERVICE_ACCOUNT_TOKEN`. | Always (universal) |
| `drivers/authelia.py` | `add_access_rule()`, `remove_access_rule()` | `docker exec` into Authelia to add/remove `access_control` rules. Uses `run_locked("authelia-config", ...)`. Supports `insert_before_twofactor=True` for `^/api/` bypass ordering. | `shape.is_admin_dashboard` + `domain` set (+ `^/api/` bypass when `shape.has_bearer_api`) |
| `drivers/meilisearch.py` | `create_index()`, `delete_index()` | Index creation. Container-scoped `sh -c` evaluates `$MEILI_MASTER_KEY` inside the container — no secret on SSH wire. | `shape.has_search_feature` |
| `drivers/prometheus.py` | `add_scrape_target()`, `remove_scrape_target()` | Appends scrape target for `/metrics` endpoint and reloads Prometheus. | `shape.exposes_metrics` |

### 2.5 Site-provisioner saga — `src/fabrik/provisioner.py`

Implements **Steps 0-1-2** of a brand-new site deployment (domain → DNS → initial deploy). Uses a saga pattern with persistent state (`/opt/fabrik/data/provision-jobs/`).

| Class / fn | Role |
|---|---|
| `ProvisionState` | Saga state enum. |
| `ContactInfo` | WHOIS contact for domain registration. |
| `SiteProvisionRequest` | Input contract from web GUI / CLI. |
| `ProvisionJob` | Persistent state on disk (resumable across CLI invocations). |
| `SiteProvisioner.start(request)` | Saga runner. Each step is idempotent; `resume()` replays from the last successful state on failure. |
| `provision_site(request)` | Entry point; returns a `ProvisionJob`. |
| `get_provision_status(job_id)` | Polling endpoint for web GUI. |

### 2.6 Supporting modules

| File | Role |
|---|---|
| `src/fabrik/deploy.py` | **Dead code.** `deploy_to_coolify(app_name, compose_content)` — legacy Coolify API deployment. Not wired to any active CLI command. Superseded by SSHDeployer. |
| `src/fabrik/deploy_router.py` | `route_deploy(project_dir, project_type, dry_run=False)` — dispatches to WordPress pipeline vs. service pipeline based on `project_type`. Central switch used by `fabrik apply` when resolving a spec from `project.yaml`. |
| `src/fabrik/deploy_validator.py` | `validate(project_dir)` — scaffold-level readiness (Dockerfile exists, `.env` populated, healthcheck declared, platform directive). Returns `ValidationResult` list; CLI prints them as warnings. |
| `src/fabrik/verify.py` | `PostconditionChecker`, `verify_postconditions` decorator — general postcondition framework (HTTP 200, file-exists, env-var-set, etc.). Used by both legacy pipeline and orchestrator/verifier. |
| `src/fabrik/notifications.py` | Thin wrapper over Apprise for in-Fabrik notifications (not infrastructure alerts). |
| `src/fabrik/monitor.py` | Deployment monitor helpers used by `fabrik status/logs`. |
| `src/fabrik/health_app.py` | Tiny FastAPI app exposing `/health` for Fabrik's own service health (scraped by Gatus). Note: still references `CoolifyClient` for legacy health checks — monitoring only, not on deploy path. |

---

## 3. Specs

Specs are the **input** to every deploy. Two flavors: infrastructure specs (deploy shared services once) and service specs (one per app).

### 3.1 Infrastructure specs — `specs/infrastructure/`

Deployed once when bootstrapping the VPS; not touched by normal `fabrik apply` on apps.

| File | Deploys | Current state |
|---|---|---|
| `specs/infrastructure/monitoring-stack.yaml` | Grafana, Alertmanager, Loki, Promtail, node-exporter, cAdvisor (all in monitoring stack compose) + Prometheus standalone (`/opt/prometheus/compose.yaml`). Config: `/opt/monitoring/configs/prometheus/prometheus.yml`. Reload: hot-reload via `POST /-/reload`, fallback to `sudo docker compose restart`. | ✅ deployed |
| `specs/infrastructure/authelia.yaml` | Authelia (SSO/2FA forward-auth) | ✅ deployed |
| `specs/infrastructure/apprise.yaml` | Apprise (notifications gateway) | ✅ deployed |
| `specs/infrastructure/browserless.yaml` | Browserless (headless Chrome) | ✅ deployed |
| `specs/infrastructure/gotenberg.yaml` | Gotenberg (HTML/Office → PDF) | ✅ deployed |
| `specs/infrastructure/meilisearch.yaml` | MeiliSearch | ✅ deployed |
| `specs/infrastructure/n8n.yaml` | n8n (workflow automation) | ✅ deployed |
| `specs/infrastructure/minio.yaml` | MinIO (self-hosted S3) | ⏸ not deployed (Backblaze B2 via Backrest used instead) |

### 3.2 Service specs — `specs/services/`

One file per deployable app. Auto-generated by `fabrik scaffold` into `/opt/fabrik/specs/services/<name>.yaml`. Schema defined in `src/fabrik/spec_loader.py::Spec`.

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

Scaffold uses these to generate `/opt/<project>/` trees. Every template has a `defaults.yaml` that declares its **shape flags** (`is_public`, `is_admin_dashboard`, `has_bearer_api`, `has_persistent_data`, `needs_database`, `has_search_feature`). These flags drive the infrastructure provisioner's dispatch.

### 4.1 Service templates — `templates/<type>/`

| Template | Kind | Key files |
|---|---|---|
| `templates/python-api/` | FastAPI service | `compose.yaml.j2`, `defaults.yaml` |
| `templates/node-api/` | Node.js API | `compose.yaml.j2`, `Dockerfile.j2`, `AGENTS.md.j2`, `defaults.yaml` |
| `templates/saas-skeleton/` | Next.js 14 + TypeScript + Tailwind + Shadcn | `compose.yaml.j2`, `Dockerfile`, plus the full Next.js skeleton (largest template) |
| `templates/static-site/` | Static HTML/JS (nginx) | `compose.yaml.j2`, `defaults.yaml` |
| `templates/docusaurus/` | Docusaurus doc site | `compose.yaml.j2`, `Dockerfile.j2`, `docusaurus.config.js.j2`, `sidebars.js.j2` |
| `templates/file-api/` | File-operations microservice | `compose.yaml.j2`, `Dockerfile.j2` |
| `templates/file-worker/` | Background worker variant of file-api | `compose.yaml.j2` |
| `templates/chrome-extension/` | Browser extension (backend) | `manifest.json.j2`, `compose.yaml.j2`, `defaults.yaml` |
| `templates/desktop-app/` | Electron-style desktop app (backend) | `compose.yaml.j2` |
| `templates/mobile-app/` | React Native / Expo (backend) | `compose.yaml.j2` |

All compose templates emit `container_name: {{ spec.id }}` for stable Docker naming.

### 4.2 Shared scaffold assets — `templates/scaffold/`

| File | Purpose |
|---|---|
| `templates/scaffold/complex.yaml` | Canonical complex-service spec example (5+ env vars, db, storage, auth). |
| `templates/scaffold/docker/compose.yaml.template` | Base compose template shared across service types. |
| `templates/scaffold/docker/compose.dev.yaml.template` | Developer-mode override (ports exposed on `127.0.0.1` only). |
| `templates/scaffold/docker/Dockerfile.node` | Canonical Node.js Dockerfile (`node:<LTS>-bookworm-slim`). |
| `templates/scaffold/docker/Dockerfile.python` | Canonical Python Dockerfile (`python:<stable>-slim-bookworm`). |
| `templates/scaffold/*` (full shared asset set) | Tests, CI workflows, README, .env.example, .gitignore, AGENTS.md boilerplate. |

### 4.3 Template-defaults registrar matrix (what fires on `fabrik apply` by default)

Source of truth: live `templates/*/defaults.yaml`. Derived by running `resolve_applicability()` against each template's default shape.

✅ = fires by default (when `spec.domain` set where noted) · ⚙ = opt-in via spec flag · ✗ = never applicable

| Template | kind | postgres | redis | gatus | backrest | glitchtip | grafana | authelia | meili | prometheus |
|---|---|---|---|---|---|---|---|---|---|---|
| **python-api** | service | ⚙ | ⚙ | ✅* | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ✅* |
| **node-api** | service | ⚙ | ⚙ | ✅* | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ✅* |
| **saas-skeleton** | service | ✅ | ⚙ | ✅* | ✅ | ✅ | ✅ | ⚙ | ⚙ | ⚙ |
| **static-site** | static | ⚙ | ⚙ | ✅* | ⚙ | ✗ | ✅ | ⚙ | ⚙ | ⚙ |
| **docusaurus** | static | ⚙ | ⚙ | ✅* | ⚙ | ✗ | ✅ | ⚙ | ⚙ | ⚙ |
| **file-api** | service | ⚙ | ⚙ | ✅* | ✅ | ✅ | ✅ | ⚙ | ⚙ | ⚙ |
| **file-worker** | worker | ⚙ | ⚙ | ✗ | ✅ | ✅ | ✅ | ✗ | ⚙ | ✗ |
| **chrome-extension** | service | ⚙ | ⚙ | ⚙ | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ⚙ |
| **desktop-app** | service | ⚙ | ⚙ | ⚙ | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ⚙ |
| **mobile-app** | service | ⚙ | ⚙ | ⚙ | ⚙ | ✅ | ✅ | ⚙ | ⚙ | ⚙ |

`*` requires `spec.domain` to be set.
chrome/desktop/mobile backends default `is_public: false` — Gatus is opt-in (flip `is_public: true` in spec).

---

## 5. Local Config Mirrors — `configs/`

Local copies of VPS-side config files. **Source of truth is on the VPS** (Docker Compose managed or volume-mounted); these mirrors exist so AI coders can diff/edit without shelling in.

| File | VPS path | Edit mechanism |
|---|---|---|
| `configs/alertmanager/alertmanager.yml` | `/opt/monitoring/configs/alertmanager/alertmanager.yml` | Volume-mounted from host. Edit locally → `scp` → `docker restart alertmanager`. |
| `configs/alertmanager/alertmanager.yml.example` | — | Template with `__PLACEHOLDERS__`; render into the real file with secrets from `.env`. |
| `configs/prometheus/prometheus.yml` | `/opt/monitoring/configs/prometheus/prometheus.yml` | Same pattern as Alertmanager. |
| `configs/prometheus/rules/alerts.yml` | `/opt/monitoring/configs/prometheus/rules/alerts.yml` | Contains alert rules. Edit → hot-reload via `POST /-/reload` (curled from alertmanager container), fallback to `cd /opt/prometheus && sudo docker compose restart`. |
| `configs/loki/loki-config.yaml` | Loki volume | Rarely edited. |
| `configs/promtail/promtail-config.yaml` | Promtail volume | Rarely edited. |
| `configs/n8n/workflows/*.json` | n8n UI imports | Seed workflows after n8n redeploy. |

**Important:** Every file here should appear in `.gitignore` **if it ever contains secrets**. The `alertmanager.yml` is `.gitignore`d because it embeds the Telegram bot token.

---

## 6. Probes & Enforcement Scripts

### 6.1 Probes — `scripts/probes/`

Idempotent contract tests against live services. Run before shipping driver changes; also serve as living API documentation.

| Script | Tests |
|---|---|
| `scripts/probes/glitchtip_probe.sh` | GlitchTip API (create project → fetch DSN → delete) |
| `scripts/probes/grafana_token_check.sh` | Grafana `/api/annotations` write + delete |

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
| `check_compose_services.py` | Compose services declare `networks: [coolify]` when behind Traefik. |
| `check_ports.py` | Ports used fall in allocated ranges (8000–8099 Python, 3000–3099 frontend); no duplicates. |
| `check_health.py` | Every service has a `/health` endpoint that tests real dependencies. |
| `check_watchdog.py` | Long-running services have `scripts/watchdog*.sh`. |
| `check_schema_sync.py` | DB migrations match `db/schema.sql` reference. |
| `check_structure.py` | Project directory structure follows Fabrik scaffold layout. |
| `check_print_ban.py` | No `print()` / `console.log()` — use the scaffolded logger. |
| `check_duplicates.py` | No duplicated files across projects (shared helpers should live in `src/utils/`). |
| `check_doc_sprawl.py` | No orphaned `.md` files; all docs reachable from `INDEX.md`. |
| `check_index_md.py`, `check_readme_md.py`, `check_changelog.py`, `check_configuration_md.py`, `check_docs.py`, `check_user_guide.py` | Doc currency — every deploy-affecting change updates the matching doc. |
| `check_plans.py`, `check_plan_quality.py` | Plans include Invariants, Failure Modes, Acceptance Criteria. |
| `check_test_coverage.py`, `check_test_proposal.py` | Every non-trivial change proposes at least one test (One-Test Rule). |
| `check_reusable_modules.py` | Modules in `src/utils/` / `src/lib/` have zero project-specific imports. |

### 6.3 Final gate — `scripts/final_gate.py`

Single entry point for all tier-based quality checks:

- `python scripts/final_gate.py --lean` — Tier 1 (syntax, secrets, env, schema). Fast, called during coding.
- `python scripts/final_gate.py` — Tier 2 (full: lean + static analysis + changelog/docs sync). Called at milestone close.
- `python scripts/final_gate.py --systemic` — Tier 3 (repo health: docker, ports, docs sprawl, duplicates). On-demand.

### 6.4 Other deploy-adjacent scripts

| Script | Purpose |
|---|---|
| `scripts/sync_projects.py` | Discover all projects under `/opt/`, update `PORTS.md` + `registry`. Run after every scaffold. |
| `scripts/sync_enforcement_to_projects.py` | Copy enforcement scripts and governance files to all `/opt/` projects for Fabrik compliance. |
| `scripts/sync_schema_to_projects.py` | Sync shared SQL schema fragments to projects that need them. |
| `scripts/audit_envs.py` | Audit all `/opt/*/.env` files. |
| `scripts/audit_all_projects.py` | Full-fleet compliance report (every project vs. every enforcement check). |
| `scripts/container_images.py` | Inventory of every Docker image in use on the VPS; detects outdated `:latest` tags. |
| `scripts/health_summary.py`, `scripts/health_checker.py`, `scripts/health_check_autonomous.py` | Rollup health probes across all deployed services. |
| `scripts/generate_vps_inventory.py` | Generates VPS container/service inventory. Called by `_post_deploy_sync()`. |
| `scripts/update_vps_docs.py` | Refreshes VPS status documentation. Called by `_post_deploy_sync()`. |
| `scripts/provision_grafana.sh` | One-shot Grafana setup (dashboards, datasources). |
| `scripts/docs_updater.py` + `scripts/kilo_docs_enforcer.py` | Auto-update docs (CHANGELOG, INDEX, README). |
| `scripts/watchdog.sh` | Sample watchdog that services copy into their repo. |

---

## 7. VPS-Side Files & Services

Files that live **on the VPS only**, outside the Fabrik repo. Grouped by service. **Edit mechanism** is listed for each — getting this wrong risks a deploy that silently reverts.

### 7.1 Traefik (reverse proxy)

| Path | Purpose | Edit mechanism |
|---|---|---|
| `/opt/traefik/compose.yaml` | Traefik compose. | Direct edit → `cd /opt/traefik && sudo docker compose up -d`. |
| `/opt/traefik/dynamic/*.yml` | Dynamic Traefik config (rarely used; most routing is via Docker labels). | Edit + `sudo docker restart traefik`. |
| Traefik API on 127.0.0.1:8080 | Live router/service/middleware inspection | `curl -s 127.0.0.1:8080/api/http/routers` piped into `jq` (no auth on localhost). |

### 7.2 Authelia (SSO/2FA forward-auth)

| Path | Purpose | Edit mechanism |
|---|---|---|
| Authelia's `/config/configuration.yml` (bind-mounted from host `/opt/authelia/config/configuration.yml` — editing either path touches the same file) | `access_control` rules (domain → policy, bypass/one_factor/two_factor). | Go through the authelia driver, which pulls via `sudo docker exec authelia cat /config/configuration.yml > authelia.cur.yml`, edits locally, then writes back: `sudo docker cp authelia.cur.yml authelia:/config/configuration.yml && sudo docker restart authelia`. Never SIGHUP — Authelia exits on SIGHUP, use `docker restart` only. |
| Authelia container's `/config/users_database.yml` | User definitions. | Same `docker cp` + `docker restart` pattern. |
| Authelia container's `/config/notification.txt` | 2FA login codes fallback (SMTP disabled). | `sudo docker exec authelia cat /config/notification.txt` to read. |

**Authelia posture decision matrix:**

| Service class | Authelia posture | Examples | Rationale |
|---|---|---|---|
| Native auth + TOTP | **Full bypass** — app-layer is the boundary | GlitchTip, Grafana | Forward-auth breaks SPA auth flows (django-allauth/React XHRs get 302'd to Authelia). |
| Native auth, no TOTP | **Forward-auth required** | Backrest, n8n, Apprise | App auth alone is insufficient; Authelia provides the 2FA. |
| No native auth | **Forward-auth mandatory** | Bare admin panels | Only boundary available. |
| UI + Bearer-token API | **Forward-auth on UI, `^/api/` bypass** | Grafana | UI stays 2FA; machine callers use Bearer token. Only added when `shape.has_bearer_api: true`. |

### 7.3 Monitoring stack

| Path | Purpose | Edit mechanism |
|---|---|---|
| `/opt/monitoring/compose.yaml` | Main monitoring stack (Grafana, Alertmanager, Loki, Promtail, node-exporter, cAdvisor). | `cd /opt/monitoring && sudo docker compose up -d`. |
| `/opt/prometheus/compose.yaml` | Prometheus standalone. Intentionally separated — scrape targets need the `coolify` network attachment which compose stacks don't always preserve. | `cd /opt/prometheus && sudo docker compose up -d`. |
| `/opt/monitoring/configs/prometheus/prometheus.yml` | Scrape targets + alerting config. Retention: `--storage.tsdb.retention.time=30d --storage.tsdb.retention.size=5GB`. | Edit → hot-reload via `POST /-/reload` (curled from alertmanager container), fallback to `cd /opt/prometheus && sudo docker compose restart`. |
| `/opt/monitoring/configs/prometheus/rules/alerts.yml` | Alert rules (ContainerDown, HighCPU, HighMemory, OOMKilled, etc.) | Same pattern. |
| `/opt/monitoring/configs/alertmanager/alertmanager.yml` | Routes, receivers (Telegram), inhibit rules. **Secret-bearing** (Telegram bot token). | Edit → `sudo docker restart alertmanager`. |
| `/opt/monitoring/configs/gatus/` | Gatus blackbox monitoring. Per-service files in `apps/` subdir (one YAML per project). **Git-versioned** (whitelisted in `drivers/locks.py::git_commit_config()`). `_base.yaml` for global alerting → Apprise. | Edit → Gatus auto-reloads on file change. |
| `/opt/monitoring/configs/loki/loki-config.yaml` | Loki storage config. | Edit → `sudo docker restart loki`. |
| `/opt/monitoring/configs/promtail/promtail-config.yaml` | Log shipper → Loki. Has `drop` stage filter for infrastructure container noise. | Edit → `sudo docker restart promtail`. |

### 7.4 Network, firewall, persistence

| Path | Purpose | Edit mechanism |
|---|---|---|
| `/etc/iptables/add-docker-user-rules.sh` | DOCKER-USER chain rules. Only 80/443 serve traffic; the script also RETURNs (allows) 6001/6002 as stale Coolify Realtime/Soketi leftovers — nothing listens, pending cleanup. Docker bypasses UFW; this chain is the real public-port boundary. | Edit + `sudo /etc/iptables/add-docker-user-rules.sh` + `sudo systemctl restart iptables-docker-user.service`. |
| `/etc/systemd/system/iptables-docker-user.service` | Persistence for the chain across reboots. | `sudo systemctl {daemon-reload,enable,restart}` after edit. |
| Docker networks | `coolify` (10.0.1.0/24) is the shared network Traefik lives on. Named `coolify` for historical reasons — it's a standard Docker bridge network. | Inspect: `docker network inspect coolify`. |

### 7.5 Fabrik on VPS

| Path | Purpose |
|---|---|
| `/opt/fabrik/.env` | Canonical env file. All secrets (Cloudflare, Grafana SA, GlitchTip, Backrest, etc.). Backed up to `.env.backup.{ts}` before any edit. |
| `/opt/fabrik/PORTS.md` | Port registry. Auto-updated by `sync_projects.py`. |
| `/opt/fabrik/data/projects.yaml` | Project registry (paths, types, spec hashes). |
| `/opt/fabrik/data/provision-jobs/` | Saga state for `SiteProvisioner`. |
| `/opt/fabrik/.fabrik/state/` | Deploy state files (JSON) — used by `destroy_from_state()` for state-driven teardown. |
| `/opt/fabrik/.tmp/` | Throwaway artifacts (probe outputs, intermediate backups). Git-ignored. |

---

## 8. VPS Infrastructure Invariants

These are **hard rules** for every deploy. Violating any of them puts the VPS or a service in a degraded state.

### 8.1 Platform

- **VPS arch:** x86_64 (amd64), AMD EPYC-Genoa, 6 vCPU, 12 GB RAM, Ubuntu 24.04, TZ `Europe/Istanbul` (+03).
- **Every compose service MUST declare** `platform: linux/amd64` (enforced by `check_docker.py` and `deployer_ssh._validate_compose()`).
- **Base images:** `python:<current-stable>-slim-bookworm` or `node:<current-LTS>-bookworm-slim`. **Never Alpine**.

### 8.2 Networking

- **`coolify` Docker network is the shared backbone.** Traefik lives here. Every service that must be reachable by Traefik MUST attach to this network. (The name is a historical artifact — it's a standard Docker bridge network.)
- **`traefik.docker.network=coolify` label is mandatory** for any service on more than one Docker network — without it Traefik non-deterministically picks a network IP.
- **No public `ports:` mapping** in compose. Everything goes through Traefik on 80/443. Docker bypasses UFW; iptables DOCKER-USER is the real boundary.
- **Allowed public TCP ports:** 80, 443 (the only ports serving traffic). The iptables script also still allows 6001/6002 (stale Coolify Realtime/Soketi — nothing listens; pending cleanup). Everything else is blocked at iptables.
- **DB connection strings use Docker DNS names**, never `localhost`: `postgres-main:5432`, `redis-main:6379`. Inside a container, `localhost` is the container itself, not the shared database.

### 8.3 Traefik labels (canonical compose snippet)

```yaml
services:
  my-service:
    container_name: my-service
    platform: linux/amd64
    restart: unless-stopped
    networks:
      coolify: null
    deploy:
      resources:
        limits:
          memory: 512M
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=coolify"
      - "traefik.http.routers.my-service.rule=Host(`my-service.vps1.ocoron.com`)"
      - "traefik.http.routers.my-service.entrypoints=websecure"
      - "traefik.http.routers.my-service.tls=true"
      - "traefik.http.routers.my-service.tls.certresolver=letsencrypt"
      # Add middleware depending on the Authelia posture (§7.2):
      - "traefik.http.routers.my-service.middlewares=authelia-forward@docker,gzip@docker"  # admin dashboard
      # - "traefik.http.routers.my-service.middlewares=gzip@docker"  # API service
      # (no middleware for public)
      - "traefik.http.services.my-service.loadbalancer.server.port=8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

networks:
  coolify:
    external: true
```

### 8.4 4-layer security model

| Layer | Target | Mechanism |
|---|---|---|
| **Iptables DOCKER-USER** | All Docker ports | `/etc/iptables/add-docker-user-rules.sh`. 80/443 serve traffic; 6001/6002 also still allowed (stale Coolify leftovers, pending cleanup). |
| **Authelia** | Admin dashboards without native TOTP | Forward-auth 2FA via Traefik middleware. **Not used** for services with native TOTP (see §7.2 matrix). |
| **X-Internal-Token** | Fabrik microservices (captcha, translator, pdf, browser, dns, ...) | Service validates `SERVICE_INTERNAL_SECRET_KEY` header on every request. |
| **Bearer tokens** | API endpoints on admin dashboards (Grafana, GlitchTip) | Issued by each service; stored in `/opt/fabrik/.env`. Authelia `^/api/` bypass (when `has_bearer_api: true`) allows these through. |

### 8.5 Secrets

- **All secrets in `/opt/fabrik/.env`** or project `.env` files. Never hardcoded.
- **CSPRNG-generated passwords**, 32 chars, `[a-zA-Z0-9]` alphabet (`secrets.choice()`).
- **`.env` files MUST NOT be `source`d** — values may contain shell metacharacters. Use `grep | cut` in shell; `python-dotenv` in Python.
- **Backup before edit:** `cp .env .env.backup.$(date +%Y%m%d-%H%M%S)` — mandatory.

### 8.6 Container naming

**Every compose service MUST declare `container_name: <name>`** for stable `docker exec`, `docker inspect`, and Gatus monitoring. Without it, Docker generates random suffixed names that change on every recreate.

Enforced by:
- `deployer_ssh._validate_compose()` — fatal error if missing (runs for **template** and **docker** source types only)
- `compose_linter.lint()` — warning if missing
- All compose templates emit `container_name: {{ spec.id }}`

### 8.7 Resource limits

**Every compose service MUST declare `deploy.resources.limits.memory`** to prevent OOM on the shared VPS. Enforced by `deployer_ssh._validate_compose()`.

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

### 9.2 Deploy a service — `fabrik apply`

**Orchestrator pipeline (default for `fabrik apply`):**

1. `SpecValidator.validate()` — required-field + type checks + SSRF + `compute_spec_hash()` for idempotency.
2. `SecretsManager.load()` — precedence: `os.environ` (includes `-s` flags) → `.env` → auto-generate.
3. `DNSClient.add_subdomain(base_domain, subdomain, vps_ip)` — skipped if `--skip-dns`. Falls back to `CloudflareClient.add_subdomain()` if site-provisioner is unavailable.
4. `SSHDeployer.deploy(ctx)` — dispatches by source type:
   - **Template:** `TemplateRenderer.render()` → `_validate_compose()` → SCP compose.yaml + .env to VPS → `docker compose up -d --wait`
   - **Git:** `git clone` (new) or `git pull` (existing) → write .env → `docker compose build` → `docker compose up -d --wait`
   - **Docker:** generate minimal compose from `source.image` → validate → SCP → `docker compose up -d --wait`
   - **Local:** verify compose exists at `source.path` → write .env → `docker compose up -d --wait`
5. `InfrastructureProvisioner.provision(ctx)` — shape-driven dispatch. Registrar order (`_REGISTRAR_ORDER` in `orchestrator/infrastructure.py:84`): `postgres` → `redis` → `gatus` → `backrest` → `glitchtip` (+DSN injection & verification) → `grafana` (annotation) → `authelia` (+`^/api/` bypass when `has_bearer_api`) → `meilisearch` → `prometheus`. All failures are non-fatal **except** GlitchTip DSN-injection mismatch, which triggers rollback.
6. `DeploymentVerifier.verify()` — HTTP 200 on `/health`, DNS resolves, SSL valid, `SENTRY_DSN` present (when GlitchTip applicable) via `docker inspect`.
7. `_post_deploy_sync()` — runs `scripts/sync_projects.py`, `scripts/update_vps_docs.py`, `scripts/generate_vps_inventory.py --update`.

On any exception, orchestrator transitions `ROLLING_BACK` and `RollbackManager` undoes every `ctx.created_resources[*]` in reverse order (§9.7).

```bash
# Default path — runs the orchestrator + all applicable registrars
fabrik apply /opt/fabrik/specs/services/my-api.yaml

# Dry-run (orchestrator path, plans only, no mutations)
fabrik apply /opt/fabrik/specs/services/my-api.yaml --dry-run

# Flags
fabrik apply specs/services/my-api.yaml --skip-dns           # skip DNS record
fabrik apply specs/services/my-api.yaml --skip-deploy        # render files only
fabrik apply specs/services/my-api.yaml -s API_KEY=override  # override a secret
fabrik apply specs/services/my-api.yaml --keep-on-failure    # suppress rollback (debugging)
```

### 9.3 Redeploy an existing service

Two modes — pure rebuild (default) or registrar refresh (`--refresh-infra`).

```bash
# Mode 1: rebuild only (VPS pulls latest git, rebuilds image, restarts container)
fabrik redeploy my-api
fabrik redeploy my-api --force                 # bypass build cache

# Mode 2: re-run only the InfrastructureProvisioner against the existing app
# Use when you added a shape flag (e.g. needs_database, has_search_feature)
# after the first deploy and want the new registrar to fire WITHOUT rebuilding.
fabrik redeploy --refresh-infra --spec specs/services/my-api.yaml
fabrik redeploy --refresh-infra --spec specs/services/my-api.yaml --dry-run
```

Internally (`cli.py::redeploy()` line 1182):

- **Mode 1 (no `--refresh-infra`):**
  1. `SSHDeployer.find_existing(name)` — checks `/opt/<name>/compose.yaml` on VPS.
  2. Detects source type by checking for `.git` directory on VPS.
  3. **Git-sourced**:
     - `ssh: cd /opt/<name> && sudo git rev-parse HEAD` (captures current commit as a rollback point BEFORE mutating, timeout 30s)
     - `ssh: cd /opt/<name> && sudo git pull` (pulls from GitHub remote, timeout 60s)
     - `ssh: cd /opt/<name> && sudo docker compose build` (rebuilds image, timeout 300s; `--no-cache` if `--force`)
     - `ssh: cd /opt/<name> && sudo docker compose up -d --wait` (restarts with new image, blocks until healthy, timeout 120s)
     - **On health-check failure** (`up -d --wait` exits non-zero): auto-reverts with `git reset --hard <captured-sha>` → rebuild → `up -d --wait` to restore the last-known-good container, then raises `DeployError`. New code is NOT left live. If the rollback itself fails, raises `DeployError` flagging manual intervention.
  4. **Non-git** (template/docker/local):
     - `ssh: cd /opt/<name> && sudo docker compose up -d --wait` (`--force-recreate` if `--force`)
     - **On health-check failure:** fails loudly with `DeployError` — no prior image tag to revert to, so no automatic rollback for non-git sources.
  5. `_post_deploy_sync()`.

  Pure rebuild: pulls the latest git commit (for git-sourced apps), rebuilds the image, restarts containers. Does **not** touch DNS, Authelia, GlitchTip, Gatus, Backrest, Meilisearch, Prometheus, or the database. Those were created on first `apply` and are expected to already exist.

- **Mode 2 (`--refresh-infra --spec PATH`):**
  1. Loads spec; resolves app by name (with `fabrik-` prefix fallback) via `SSHDeployer.find_existing()`.
  2. `DeploymentOrchestrator.refresh_infrastructure(spec_path, dry_run)` — runs **only** `InfrastructureProvisioner.provision(ctx)`. No deploy stage, no verifier, no DNS provisioning.
  3. `_post_deploy_sync()`.

**DB schema changes are never auto-applied.** Apps must handle migrations in their container entrypoint (see `docs/operations/fabrik-lifecycle.md`).

### 9.4 Tear down a service

`fabrik destroy` reverses the full provisioner chain. Order in `orchestrator/destroyer.py::destroy_deployment()`:

1. **prometheus** → remove scrape target (first down, last up)
2. **meilisearch** → skipped (index preserved) unless `--drop-data`
3. **authelia** → remove access rule, restart authelia (if `shape.is_admin_dashboard`)
4. **glitchtip** → delete project (if `kind in {service, worker, wordpress}`)
5. **grafana** → skipped (annotations are informational, auto-expire)
6. **backrest** → remove backup plan (if `shape.has_persistent_data`)
7. **gatus** → remove endpoint, restart gatus (if `shape.is_public` + domain)
8. **postgres** → skipped (database preserved) unless `--drop-data`
9. **redis** → release index slot (data NOT flushed unless `--drop-data`)
10. **App** → `sudo docker compose down` (`-v` only with `--drop-data`) + `sudo rm -rf /opt/<name>` + `sudo docker image prune -f`
11. **DNS** → remove A record (unless `--keep-dns`)
12. `_post_deploy_sync()`

```bash
# Default: data-preserving teardown (Postgres DB + Meilisearch index + Redis data kept)
fabrik destroy specs/services/my-api.yaml

# Throwaway test cleanup — drop DB + Meilisearch index + flush Redis too
fabrik destroy specs/services/my-api.yaml --drop-data -y

# Keep DNS records
fabrik destroy specs/services/my-api.yaml --keep-dns

# Plan only — print every action, mutate nothing
fabrik destroy specs/services/my-api.yaml --dry-run

# Partial destroy (specific registrars only)
fabrik destroy specs/services/my-api.yaml --partial gatus --partial backrest

# State-driven destroy (use state file instead of current spec shape)
fabrik destroy specs/services/my-api.yaml --use-state --drop-data -y
```

Per-step exit symbol in stdout: `✅ removed`, `ℹ️ not_found`, `⏭️ skipped`, `🧪 dry_run`, `❌ error`. Non-zero exit (`2`) if any step errored.

### 9.5 Provision a brand-new domain

```bash
# Check availability + pricing
fabrik domain check example.com

# Register (requires Namecheap credentials in .env)
fabrik domain buy example.com

# Full provision — DNS zone + CDN + SSL
fabrik domain provision example.com

# Wait until HTTPS is reachable (DNS + SSL both valid)
fabrik domain ready example.com
```

### 9.6 End-to-end validation (maximal-shape test)

The **canonical way to verify the deployment pipeline after any change** to a registrar driver, the orchestrator, or the compose template. Produces a project that exercises every code path in a single deploy.

```bash
# 1. Scaffold a throwaway project
fabrik scaffold fabrik-e2e-full-test --type python-api --db

# 2. Overwrite with a MAXIMAL-SHAPE spec (every shape.* flag true)
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
  needs_cache: true
  has_search_feature: true
  exposes_metrics: true
source: {type: docker, image: traefik/whoami:latest, image_port: 80, image_command: --port 80}
expose: {http: true, internal_only: false}
health: {disabled: true, path: /}   # whoami has no shell
backup: {enabled: true, frequency: daily, retention: 30}
EOF

# 3. Deploy and time it
time fabrik apply /opt/fabrik/specs/services/fabrik-e2e-full-test.yaml

# 4. Verify every registrar touched the right place
ssh vps 'sudo docker ps --format "{{.Names}}" | grep fabrik-e2e-full'
curl -sI https://fabrik-e2e-full-test.vps1.ocoron.com | head -3
ssh vps 'sudo docker exec authelia grep -c fabrik-e2e-full /config/configuration.yml'
ssh vps 'sudo docker exec postgres-main psql -U postgres -tAc "SELECT datname FROM pg_database WHERE datname LIKE '"'"'fabrik_e2e_full%'"'"'"'
curl -s https://status.vps1.ocoron.com/api/v1/endpoints/statuses | jq '[.[]|select(.name|contains("fabrik-e2e-full"))]'

# 5. Idempotency — re-run the same deploy; every registrar should report 'exists'
fabrik apply /opt/fabrik/specs/services/fabrik-e2e-full-test.yaml

# 6. TEAR DOWN EVERYTHING
fabrik destroy /opt/fabrik/specs/services/fabrik-e2e-full-test.yaml --drop-data -y
rm -rf /opt/fabrik-e2e-full-test /opt/fabrik/specs/services/fabrik-e2e-full-test.yaml
python scripts/sync_projects.py
```

**Why this test matters:** every shape-gated code path runs exactly once per deploy. Problems hidden by smoke tests with partial shape flags surface here.

### 9.7 Rollback (automatic)

Orchestrator catches any exception during deploy, transitions to `ROLLING_BACK`, and calls `RollbackManager.rollback(ctx)`. Reverse-order cleanup of every `ctx.created_resources[*]`:

- `compose` → `SSHDeployer.delete()` (`docker compose down -v` + `rm -rf /opt/<name>`)
- `coolify` → legacy Coolify app removal (pre-migration deployments only)
- `dns` → `CloudflareClient.delete_record_by_name()`
- `monitor` → legacy monitor resource cleanup
- `glitchtip` → `delete_project()`
- `grafana_annotation_id` → `delete_annotation()`
- `authelia` / `authelia_bypass` → `remove_access_rule()` (deduplicated per-domain)
- `gatus` → `remove_endpoint()`
- `backrest` → `remove_backup_plan()`
- `redis` → `release_db_index()`
- `prometheus` → `remove_scrape_target()`
- `postgres` → **NOT auto-dropped** — logged for operator review (deliberate data-preservation policy)
- `meilisearch` → **NOT auto-deleted** — logged for operator review

Errors during rollback are logged and accumulated — rollback never aborts, always tries every resource.
`--keep-on-failure` flag skips rollback entirely (for debugging failed deploys).

### 9.8 Infrastructure-service coverage matrix

| Infra service | Per-service registration on deploy? | Mechanism | Shape gate |
|---|---|---|---|
| **PostgreSQL** (shared `postgres-main`) | Yes — creates DB + user | `drivers/postgres.py::create_database()` | `shape.needs_database` |
| **Redis** (shared `redis-main`) | Yes — allocates isolated DB index; injects `REDIS_URL` | `drivers/redis.py::acquire_db_index()` | `shape.needs_cache` |
| **Traefik** | Implicit | Docker labels in compose → Traefik picks up automatically. No registrar needed. | auto |
| **GlitchTip** | Yes — creates Sentry project + DSN; injects + verifies via `docker inspect` | `drivers/glitchtip.py::create_project()` | `shape.kind in {service, worker, wordpress}` |
| **Grafana** | Yes — writes deployment annotation | `drivers/grafana.py::post_deployment_annotation()` | Always (non-fatal) |
| **Loki** | Auto | Promtail scrapes `/var/lib/docker/containers/*` — picks up every container automatically. | auto |
| **Promtail** | Auto | Container auto-discovery via Docker socket. Has `drop` stage filter for infrastructure noise. | auto |
| **Prometheus** | Yes — appends scrape target for `/metrics` endpoint | `drivers/prometheus.py::add_scrape_target()` | `shape.exposes_metrics` |
| **Alertmanager** | No — receivers/routes are static | Manual per-service alert routes if needed. | — |
| **cAdvisor** | Auto | Discovers all containers via Docker socket. | auto |
| **node-exporter** | Auto | Host-level only; no per-service config. | auto |
| **Authelia** | Yes — adds access rule + optional `^/api/` bypass | `drivers/authelia.py::add_access_rule()` | `shape.is_admin_dashboard` + domain (bypass: `shape.has_bearer_api`) |
| **Gatus** | Yes — writes per-service YAML in `/opt/monitoring/configs/gatus/apps/` | `drivers/gatus.py::add_endpoint()` | `shape.is_public` + domain |
| **Backrest** | Yes — adds Restic backup plan | `drivers/backrest.py::add_backup_plan()` | `shape.has_persistent_data` |
| **MeiliSearch** | Yes — creates search index | `drivers/meilisearch.py::create_index()` | `shape.has_search_feature` |

---

## 10. Secrets & `.env`

### 10.1 Precedence

```text
1. os.environ (checked first by SecretsManager.get())
   Includes, in order of who sets values:
   a. -s KEY=VALUE flags     (CLI injects into os.environ before SecretsManager runs — highest)
   b. Process env vars       (already in os.environ when CLI starts)
   c. Fabrik .env             (/opt/fabrik/.env loaded into os.environ by config.py at import time
                               via python-dotenv — does NOT overwrite existing vars)
2. Project .env file          (/opt/<project>/.env — SecretsManager.dotenv property)
3. Auto-generate              (CSPRNG 32-char secret if generate_if_missing=True — lowest)
```

### 10.2 Auto-detected from `.env.example`

`fabrik scaffold` scans `.env.example` for env vars matching `_KEY`, `_SECRET`, `_PASSWORD`, `_TOKEN`, `_CREDENTIALS` and adds them to the spec's `secrets.from_env` field. `fabrik apply` then loads them from the project `.env` at deploy time.

### 10.3 Safe handling

```bash
# ✅ Correct: extract a single value without shell-eval
TOKEN=$(grep -E '^GRAFANA_SERVICE_ACCOUNT_TOKEN=' /opt/fabrik/.env | head -1 | cut -d= -f2-)

# ❌ Wrong: sourcing .env evaluates values as shell — tokens can contain |, &, etc.
set -a; source /opt/fabrik/.env; set +a
```

Python: always `python-dotenv` or `pydantic-settings`.

### 10.4 Canonical env vars

| Variable | Used by | Source |
|---|---|---|
| `FABRIK_VPS_SSH_HOST` | `drivers/ssh.py`, `drivers/locks.py` | Defaults to `vps`; set in `~/.ssh/config` |
| `SITE_PROVISIONER_API_KEY` | `drivers/dns.py` | site-provisioner admin |
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID` | `drivers/cloudflare.py` fallback | Cloudflare dashboard |
| `GRAFANA_SERVICE_ACCOUNT_TOKEN` | `drivers/grafana.py` | Grafana → Service Accounts |
| `GRAFANA_ADMIN_PASSWORD` | Grafana login | generated by `scripts/provision_grafana.sh` |
| `GLITCHTIP_AUTH_TOKEN`, `GLITCHTIP_ORG_SLUG`, `GLITCHTIP_TEAM_SLUG` | `drivers/glitchtip.py` | GlitchTip UI |
| `TELEGRAM_FULL_BOT_TOKEN` | Alertmanager, Gatus-via-Apprise | Telegram BotFather (**joined form** `<id>:<secret>`) |
| `TELEGRAM_CHAT_ID` | Same | `getUpdates` API |
| `GITHUB_TOKEN` | scaffold's CI workflow generation | GitHub personal access token |
| `SERVICE_INTERNAL_SECRET_KEY` | All Fabrik API services | Shared M2M secret. One value, all services. |
| `DATABASE_URL` / `DB_HOST` | Python services with DB | Always `postgres-main:5432` — never `localhost`. Comes from spec `env:` block or `ctx.secrets`, NOT injected by postgres registrar. |
| `REDIS_URL` | Services using Redis | Always `redis-main:6379` — never `localhost`. Injected by redis registrar via `deployer.inject_env()`. |
| `SENTRY_DSN` / `GLITCHTIP_DSN` | Error tracking | Injected by glitchtip registrar via `deployer.inject_env()`. |
| `BACKREST_*` | `drivers/backrest.py` | Backrest API credentials |

---

## 11. Key Invariants Summary

Every invariant below has been validated against live VPS behavior. Cross-reference when adding new deploy code.

### 11.1 Deploy pipeline invariants

| # | Invariant |
|---|---|
| 1 | SSH deploy: all `docker` commands on VPS require `sudo` prefix |
| 2 | Compose files go through `_validate_compose()` before deploy — fatal on constraint violation. Only runs for **template** and **docker** source types (git and local sources manage their own compose files) |
| 3 | `container_name: <name>` required in every compose service for stable naming |
| 4 | `platform: linux/amd64` required in every compose service |
| 5 | `deploy.resources.limits.memory` required in every compose service |
| 6 | No `ports:` section — all traffic through Traefik on `coolify` network |
| 7 | `restart: unless-stopped` on every service |
| 8 | Traefik entrypoint must be `websecure` (not `http`/`https`) |
| 9 | `loadbalancer.server.port` required when `traefik.enable=true` |
| 10 | No `depends_on` referencing `postgres-main` or `redis-main` (external services) |
| 11 | No `localhost` in `DATABASE_URL` or `REDIS_URL` env vars |

### 11.2 Registrar invariants

| # | Invariant |
|---|---|
| 12 | GlitchTip DSN verification uses `docker inspect`, never `docker exec printenv` (fails on scratch/distroless) — Lesson 31 |
| 13 | Loopback DSNs auto-rewritten to public host by `_canonicalize_dsn()` |
| 14 | GlitchTip DSN-injection mismatch is the only fatal registrar failure — triggers full rollback |
| 15 | Authelia: never SIGHUP (exits) — always `docker restart authelia` after config changes |
| 16 | Authelia `^/api/` bypass is conditional on `shape.has_bearer_api: true`, not always added |
| 17 | Gatus uses per-service YAML files in `/opt/monitoring/configs/gatus/apps/`, not a single config |
| 18 | Prometheus reload: hot-reload via `POST /-/reload` lifecycle endpoint (curled from alertmanager container), fallback to `docker restart` if hot-reload fails |
| 19 | Postgres registrar creates DB only — does NOT inject `DATABASE_URL` |
| 20 | Redis registrar acquires a DB index (`acquire_db_index()`) AND injects `REDIS_URL` via `deployer.inject_env()` |
| 21 | Backrest config edits serialized via `run_locked("backrest-config", ...)` |

### 11.3 VPS / Docker invariants

| # | Invariant |
|---|---|
| 22 | Docker network `coolify` is the shared backbone — all Traefik-routed services must attach |
| 23 | `.env` files root-owned at `/opt/<name>/.env` — written via scp-to-tmp-then-sudo-mv pattern |
| 24 | `docker compose up -d` only recreates containers with changed config — volumes NEVER touched |
| 25 | `docker compose down -v` removes named volumes — used by rollback's `delete()` (unconditional) and by destroy (gated behind `--drop-data`); never during redeploy |
| 26 | VPS reboot: containers auto-recover via `restart: unless-stopped` |
| 27 | In-flight requests dropped during container restart (TCP RST, 3-15s of 502s from Traefik) |
| 28 | DB migrations must be handled by container entrypoint, not the deployer |

### 11.4 Operational resource limits (from past OOM incidents)

| Service | Memory limit | Notes |
|---|---|---|
| cAdvisor | 512M | OOM at 256m with 40 containers. Add `--docker_only=true --disable_metrics=sched,tcp,udp,percpu,advtcp,hugetlb,...` |
| Prometheus | 1G | OOM at 512m scraping 40 containers. `--storage.tsdb.retention.size=5GB` |
| Netdata | 512M cache | Set `NETDATA_DBENGINE_DISK_SPACE_MB=512` + `NETDATA_DBENGINE_RETENTION_DAYS=7` |

---

## Setup Runbooks (Reproducible Procedures)

| Runbook | Purpose | Where it runs |
|---|---|---|
| [`infrastructure/promtail-noise-filter-setup.md`](infrastructure/promtail-noise-filter-setup.md) | Promtail `drop` stage to filter infrastructure log noise | VPS |
| [`infrastructure/grafana-provisioning-setup.md`](infrastructure/grafana-provisioning-setup.md) | File-based Grafana datasource provisioning (Prometheus + Loki) via host bind mount | VPS |
| [`infrastructure/grafana-dashboards-setup.md`](infrastructure/grafana-dashboards-setup.md) | API-based dashboard import (Node Exporter Full, Docker monitoring, Prometheus Stats) | VPS |

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
| Change Authelia access rules | §7.2 above |
| Change a Prometheus alert threshold | `configs/prometheus/rules/alerts.yml` + reload Prometheus |
| Change Alertmanager routing | `configs/alertmanager/alertmanager.yml` + restart Alertmanager |
| Change Grafana dashboards | Grafana UI → export JSON → commit to `configs/grafana/` |
| Understand runtime data safety | `docs/operations/fabrik-lifecycle.md` |
| Follow operational procedures | `docs/operations/deployment.md` |

## Appendix B: Related documents

- `docs/operations/deployment.md` — operational procedures for deploy/redeploy/destroy
- `docs/operations/fabrik-lifecycle.md` — runtime behavior during each operation — data safety, downtime, .env merge
- `docs/operations/disaster-recovery.md` — backup restore procedures
- `docs/operations/disaster-recovery.md` — Backup restore procedures + Backrest/Restic strategy
- `docs/LESSONS_LEARNT.md` — every live-incident invariant
- `docs/infrastructure/vps-complete-inventory.md` — what runs on the VPS right now
- `AGENTS.md` — Fabrik identity + tech-stack defaults
- `CLAUDE.md` — bootstrap for Claude Code (always-on rules)
- `.windsurfrules` — bootstrap for Windsurf Cascade (always-on rules)
- `AGENTS-compact.md` — bootstrap for Kilo CLI (always-on rules)
- `.windsurf/rules/` — topic-relevant rule packs loaded on demand by all coding agents
