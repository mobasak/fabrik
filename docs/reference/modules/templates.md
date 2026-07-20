# Fabrik Templates

**Last Updated:** 2026-04-22

Scaffold templates live in `/opt/fabrik/templates/<name>/`. Each has a `defaults.yaml` declaring default shape flags (Phase 4k) — these drive which registrars run when the scaffolded project is deployed.

Source of truth for the Shape matrix: `src/fabrik/spec_loader.py::Shape`.

---

## Deploy Templates (reconciled 2026-07-19 against `templates/*/defaults.yaml`)

All rows are exposed via `fabrik scaffold --type <name>`. (`wordpress` is a recognised deploy/shape type with NO template — scaffolding redirects to the legacy `/opt/wpf` CLI. `next-tailwind` is planned-but-unimplemented — template files exist but no scaffolder function (`spec_generator.py:53`). `modal` in `templates/` is rendered by the GPU path, not by TemplateRenderer.)

| Template | Stack | Port | Typical use | Default shape (true flags) |
|---|---|---|---|---|
| `python-api` | Python 3.12 + FastAPI + Uvicorn | 8000 | REST APIs, microservices | service, public, metrics |
| `python-api-gpu` | python-api + `gpu_handler.py` (on-demand GPU rent) | 8000 | GPU-burst APIs/workers | service, public, metrics |
| `node-api` | Node.js 22 + Express/Fastify | 3000 | Node.js APIs | service, public, metrics |
| `saas-skeleton` | Next.js 15 + React 19 + TypeScript + Tailwind | 3000 | Full SaaS apps & dashboards | service, public, bearer-api, DB, cache, persistent, metrics |
| `static-site` | No own `Dockerfile.j2` — routed through `_scaffold_saas_skeleton` (Next.js 15 + React 19 + TypeScript + Tailwind, same as `saas-skeleton`) | 3000 | Landing pages, doc sites | static, public |
| `docusaurus` | Docusaurus 3 | 3000 | Documentation sites | static, public |
| `file-api` | Node.js 22 (`file-api/Dockerfile.j2`) — presigned-URL file-ops microservice | 3000 | File upload/transform services | service, public, persistent |
| `file-worker` | Python background worker (variant of file-api) | — | Async file processing | worker, persistent |
| `chrome-extension` | MV3 (WXT + Preact) | — | Browser extensions; compose.yaml.j2 deploys a companion FastAPI backend via `fabrik apply` | service (all-false flags; backend deployable) |
| `desktop-app` | Electron-style | — | Desktop apps; template carries a compose.yaml.j2 but the scaffolder does not emit a spec today | service (all-false flags) |
| `mobile-app` | React Native / Expo | — | Mobile apps (EAS deploy); companion backend deployable | service (all-false flags) |

**Note on shape:** these are the template defaults. Any scaffolded project can override its `shape:` block in the spec to turn registrars on or off.

---

## Template structure

Every template directory contains at minimum:

```text
templates/<name>/
├── defaults.yaml          # shape: + env: + resources: defaults (required for deploy-able templates)
├── compose.yaml.j2        # Docker Compose template (required) — written to /opt/<app>/compose.yaml by SSH deployer
├── Dockerfile.j2          # Dockerfile template (if not using a published image)
└── [AGENTS.md.j2 / README.md.j2 / tests / CI workflow / .env.example / ...]
```

Shared scaffold assets under `templates/scaffold/` (canonical Dockerfiles, base compose templates, CI workflows, tests, `.env.example` boilerplate).

Archived templates under `templates/.archive/` — **do not use**.

---

## Default shape flags by template

Sourced from each `templates/<name>/defaults.yaml`:

| Template | kind | is_public | is_admin_dashboard | has_bearer_api | has_persistent_data | needs_database | needs_cache | exposes_metrics | has_search_feature |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `python-api` | service | ✓ | — | — | — | — | — | ✓ | — |
| `python-api-gpu` | service | ✓ | — | — | — | — | — | ✓ | — |
| `node-api` | service | ✓ | — | — | — | — | — | ✓ | — |
| `saas-skeleton` | service | ✓ | — | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `static-site` | static | ✓ | — | — | — | — | — | — | — |
| `docusaurus` | static | ✓ | — | — | — | — | — | — | — |
| `file-api` | service | ✓ | — | — | ✓ | — | — | — | — |
| `file-worker` | worker | — | — | — | ✓ | — | — | — | — |
| `chrome-extension` | service | — | — | — | — | — | — | — | — |
| `desktop-app` | service | — | — | — | — | — | — | — | — |
| `mobile-app` | service | — | — | — | — | — | — | — | — |

See each template's `defaults.yaml` for the authoritative values — this table is a snapshot.

---

## Example specs

### python-api with database + search

```yaml
id: my-api
kind: service
template: python-api
domain: my-api.vps1.ocoron.com

shape:
  kind: service
  is_public: true
  needs_database: true
  has_persistent_data: true
  has_search_feature: true       # enables MeiliSearch index

source:                          # only when using a prebuilt image instead of building
  type: template                 # template | docker | git

env:
  LOG_LEVEL: INFO

resources: {memory: 512M, cpu: '1'}
health: {path: /health, disabled: false}
backup: {enabled: true, frequency: daily, retention: 30}
```

### saas-skeleton admin dashboard with bearer-token API

```yaml
id: my-saas
kind: service
template: saas-skeleton
domain: app.example.com

shape:
  kind: service
  is_public: true
  is_admin_dashboard: true       # → Authelia two_factor rule
  has_bearer_api: true           # → Authelia ^/api/ bypass (inserted BEFORE two_factor)
  needs_database: true

env:
  NEXT_PUBLIC_API_URL: https://api.example.com

resources: {memory: 1G, cpu: '2'}
health: {path: /api/health}
```

### scratch image (edge case — disable healthcheck)

```yaml
id: my-tiny-service
kind: service
template: python-api             # any — we override the source
domain: tiny.vps1.ocoron.com

source: {type: docker, image: traefik/whoami:latest, image_port: 80, image_command: --port 80}

shape: {kind: service, is_public: true}

health: {disabled: true}         # scratch image has no shell — see Lesson 30
```

---

## Creating custom templates

```text
templates/my-template/
├── defaults.yaml          # REQUIRED — shape + env defaults
├── compose.yaml.j2        # REQUIRED — Docker Compose template (rendered + scp'd to VPS by SSH deployer)
├── Dockerfile.j2          # optional
└── (AGENTS.md.j2, README.md.j2, tests, CI, ...)
```

### Jinja2 variables available in compose/Dockerfile templates

| Variable | Type | Description |
|---|---|---|
| `spec` | `Spec` | Full validated spec |
| `id` | `str` | Service ID |
| `domain` | `str \| None` | Service domain |
| `env` | `dict[str, str]` | Environment variables |
| `resources` | `Resources` | Memory/CPU limits |
| `health` | `Health` | Healthcheck config (check `health.disabled` before emitting) |
| `volumes` | `list[Volume]` | Persistent volumes |
| `depends` | `Depends` | postgres/redis dependencies |
| `infrastructure` | `Infrastructure` | Database/storage/auth selectors |
| `companion_services` | `list[CompanionService]` | Extra compose services declared in the spec (rendered into the same stack) |
| `shape` | `Shape` | Shape flags (drives conditional emission) |

### Canonical compose snippet

See `docs/DEPLOYMENT_ARCHITECTURE.md` §8.3 for the mandatory Traefik labels, `platform: linux/amd64`, `networks: fabrik` (renamed from `coolify` 2026-05-31), and healthcheck patterns.

### Security

`TemplateRenderer.render()` and `template_exists()` validate template paths with `.resolve().relative_to()` to prevent directory traversal (`../../etc/passwd` raises `ValueError`).

---

## CLI

```bash
fabrik templates                 # list all available templates
fabrik scaffold my-api --type python-api [--db] [--from-preplan <preplan.md>]
fabrik apply /opt/fabrik/specs/services/my-api.yaml [--dry-run]
```

---

## Renderer internals (`src/fabrik/template_renderer.py`)

The `TemplateRenderer` class renders these templates from specs (merged here from the former
`template_renderer.md`, 2026-07-20):

```python
from fabrik.template_renderer import TemplateRenderer

renderer = TemplateRenderer()
files = renderer.render(spec, secrets={"DB_PASSWORD": "secret"}, dry_run=True)
```

| Method | Description |
|--------|-------------|
| `list_templates()` | Returns list of available template names |
| `template_exists(name)` | Check if a template exists |
| `render(spec, secrets, dry_run)` | Render template files for a spec |

Security — path-traversal prevention: both `render()` and `template_exists()` validate that template
paths stay within the templates directory via `.resolve().relative_to()`; `render()` raises
`ValueError` on escape, `template_exists()` returns `False` (safe default). Example blocked input:
`../../etc/passwd`.

---

## Related

- [DEPLOYMENT_ARCHITECTURE.md](../../DEPLOYMENT_ARCHITECTURE.md) §4 — template catalog in the deploy reference
- [Deployment Orchestrator](deployment-orchestrator.md) — how shape flags drive the provisioner
- [Drivers](drivers.md) — shape-gated registrars
- [CLI Reference](../fabrik-cli-reference.md)
