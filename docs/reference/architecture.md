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

```text
/opt/fabrik/
├── src/fabrik/
│   ├── cli.py                        # 22-command CLI (2048 lines)
│   ├── spec_loader.py                # Pydantic Spec + Shape models
│   ├── template_renderer.py          # Jinja2 + ComposeLinter hook
│   ├── scaffold.py                   # fabrik scaffold logic
│   ├── deploy_router.py              # project-type dispatch
│   ├── deploy_validator.py           # scaffold-level readiness
│   ├── compose_linter.py             # Coolify-compat checks
│   ├── registry.py                   # project registry
│   ├── provisioner.py                # brand-new-site saga
│   ├── verify.py                     # postcondition framework
│   ├── orchestrator/                 # 11 modules — deployment state machine
│   └── drivers/                      # 22 modules — external API clients
├── templates/                        # 12 deploy templates (11 also scaffold-exposed)
├── specs/
│   ├── services/                     # per-app specs (~52 services)
│   ├── infrastructure/               # platform-wide specs
│   ├── sites/                        # WordPress site specs
│   └── verification/                 # declarative postconditions
├── configs/                          # local mirrors of VPS configs
├── scripts/
│   ├── enforcement/                  # pre-deploy invariant checks
│   ├── probes/                       # live API contract tests
│   └── final_gate.py                 # tier-1/2/3 quality gate
├── tests/
│   ├── orchestrator/                 # 144 tests
│   └── drivers/                      # 331 tests across 12 modules
└── docs/
    ├── DEPLOYMENT.md                 # canonical deploy reference (790 lines)
    ├── LESSONS_LEARNT.md             # every live-incident invariant
    └── reference/                    # this directory
```

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
