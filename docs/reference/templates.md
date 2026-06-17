# Fabrik Templates

**Last Updated:** 2026-04-22

Scaffold templates live in `/opt/fabrik/templates/<name>/`. Each has a `defaults.yaml` declaring default shape flags (Phase 4k) — these drive which registrars run when the scaffolded project is deployed.

Source of truth for the Shape matrix: `src/fabrik/spec_loader.py::Shape`.

---

## All 12 Deploy Templates (2026-04-22)

11 of these are also exposed via `fabrik scaffold --type <name>`. The 12th, `next-tailwind`, is **deploy-only** (used by specs that reference it directly; not creatable via `fabrik scaffold`).

| Template | Stack | Port | Typical use | Default shape |
|---|---|---|---|---|
| `python-api` | Python 3.12 + FastAPI + Uvicorn | 8000 | REST APIs, microservices | service, public, DB, persistent |
| `node-api` | Node.js 22 + Express/Fastify | 3000 | Node.js APIs | service, public, DB, persistent |
| `saas-skeleton` | Next.js 14 + TypeScript + Tailwind + Shadcn | 3000 | Full SaaS apps & dashboards | service, public, admin-dashboard, DB |
| `next-tailwind` | Next.js 14 + Tailwind (minimal) | 3000 | Marketing sites, small SSR apps | service, public |
| `static-site` | Static HTML/JS via nginx | 80 | Landing pages, doc sites | static, public |
| `wordpress` | WordPress + WP-CLI | 80 | Content sites (plus `landing`/`saas`/`content` presets) | wordpress, public, DB, persistent |
| `docusaurus` | Docusaurus 3 | 3000 | Documentation sites | static, public |
| `file-api` | Python + FastAPI (file-ops microservice) | 8000 | File upload/transform services | service, internal, DB, persistent |
| `file-worker` | Python background worker (variant of file-api) | — | Async file processing | worker, DB, persistent |
| `chrome-extension` | MV3 build pipeline | — | Browser extensions (GitHub-releases deploy) | extension (no VPS deploy) |
| `desktop-app` | Electron-style | — | Desktop apps (GitHub-releases deploy) | desktop (no VPS deploy) |
| `mobile-app` | React Native / Expo | — | Mobile apps (EAS / app-store deploy) | mobile (no VPS deploy) |

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

| Template | kind | is_public | is_admin_dashboard | has_bearer_api | has_persistent_data | needs_database | has_search_feature |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `python-api` | service | ✓ | — | — | ✓ | ✓ | — |
| `node-api` | service | ✓ | — | — | ✓ | ✓ | — |
| `saas-skeleton` | service | ✓ | ✓ | — | ✓ | ✓ | — |
| `next-tailwind` | service | ✓ | — | — | — | — | — |
| `static-site` | static | ✓ | — | — | — | — | — |
| `wordpress` | wordpress | ✓ | — | — | ✓ | ✓ | — |
| `docusaurus` | static | ✓ | — | — | — | — | — |
| `file-api` | service | — | — | ✓ | ✓ | ✓ | — |
| `file-worker` | worker | — | — | — | ✓ | ✓ | — |

(Non-deploy templates — `chrome-extension`, `desktop-app`, `mobile-app` — omit deploy-side shape flags.)

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

### wordpress with content preset

```yaml
id: my-blog
kind: service
template: wordpress
preset: content                  # templates/wordpress/presets/content.yaml
domain: blog.example.com

shape:
  kind: wordpress
  is_public: true
  has_persistent_data: true
  needs_database: true
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

## Related

- [DEPLOYMENT_ARCHITECTURE.md](../DEPLOYMENT_ARCHITECTURE.md) §4 — template catalog in the deploy reference
- [Orchestrator](orchestrator.md) — how shape flags drive the provisioner
- [Drivers](drivers.md) — shape-gated registrars
- [CLI Reference](fabrik-cli-reference.md)
- [template_renderer.md](template_renderer.md) — renderer internals
