# Fabrik Scaffold Specification

**Last Updated:** 2026-04-29 (full code-truth rewrite: every CLI command/flag, `SCAFFOLD_TYPES`, `SPEC_ENABLED_TYPES`, template inventory, and file reference links re-verified against `src/fabrik/cli.py`, `src/fabrik/scaffold.py`, `src/fabrik/spec_generator.py`, and `templates/`. Aspirational sections that referenced files that never shipped — "Template Complexity Tiers", "Factory Configuration" — have been removed. `fabrik new` deprecation banner from Phase 4k 2026-04-22 retained.)
**Scope:** This doc is **canonical for the project-creation half** (`fabrik scaffold` and the file tree it produces). For the **deployment half** (`fabrik apply` / `fabrik deploy`, orchestrator state machine, registrars, verifier, rollback), see `@/opt/fabrik/docs/DEPLOYMENT.md`.
**Source code:** `src/fabrik/scaffold.py` (scaffolders) + `src/fabrik/cli.py` (CLI) + `src/fabrik/spec_generator.py` (auto-spec)

> ⚠️ **`fabrik new` deprecated 2026-04-22 (Phase 4k):** hidden from `fabrik --help`, prints a deprecation warning to stderr on every invocation, scheduled for removal one release after next. **Use `fabrik scaffold` instead** — it scaffolds the project tree AND emits the deploy spec in one step.

> **Coders:** When modifying `src/fabrik/scaffold.py`, `src/fabrik/cli.py`, `src/fabrik/spec_generator.py`, or anything under `templates/scaffold/`, update this workflow doc to match. The doc is the audit trail; the code is the truth.

---

## Table of Contents

1. [Overview](#overview)
2. [Project Types & Decision Matrix](#project-types--decision-matrix)
3. [CLI Commands Reference](#cli-commands-reference)
4. [Scaffold-to-Deploy Integration (P2/P3/P4)](#scaffold-to-deploy-integration-p2p3p4)
5. [Project Templates](#project-templates)
6. [Template Complexity Tiers](#template-complexity-tiers)
7. [SaaS Skeleton (Next.js)](#saas-skeleton-nextjs)
8. [Docker Templates](#docker-templates)
9. [Documentation Templates](#documentation-templates)
10. [Factory Configuration](#factory-configuration)
11. [Project Lifecycle](#project-lifecycle)
12. [Conventions & Standards](#conventions--standards)
13. [File Reference Links](#file-reference-links)

---

## Overview

Fabrik is a **spec-driven deployment automation** system that:

1. **Scaffolds** new projects with standardized structure
2. **Generates** deployment specs from templates
3. **Deploys** to Coolify via Docker Compose
4. **Validates** projects against Fabrik standards
5. **Manages** DNS, monitoring, and secrets

### Architecture

```text
┌── fabrik CLI (src/fabrik/cli.py) — 17 top-level commands + 5 groups ─────┐
│ Project lifecycle:  scaffold  validate  validate-deploy  fix  scan       │
│                     projects  templates                                  │
│ Deploy / ops:       plan  apply  deploy  status  app-logs  logs  destroy │
│                     redeploy  verify                                     │
│ Groups:             wp  ai  domain  content  seo                         │
│ Hidden/deprecated:  new   (Phase 4k 2026-04-22)                           │
└────────────────────────────────────────────────────────────────────────────────────┘
     │
     ├─ fabrik scaffold → src/fabrik/scaffold.py + templates/<type>/
     │   → emits /opt/<name>/ tree, runs git init, creates .venv,
     │     installs pre-commit, registers in /opt/fabrik/data/projects.yaml,
     │     auto-generates specs/services/<name>.yaml (SPEC_ENABLED_TYPES only)
     │
     └─ fabrik apply / deploy → src/fabrik/orchestrator/ (state machine)
         → see @/opt/fabrik/docs/DEPLOYMENT.md (canonical deploy reference)

Drivers used by the orchestrator (src/fabrik/drivers/):
  CoolifyClient  DNSClient (DNS Manager primary, Cloudflare fallback)
  + per-registrar drivers: postgres, gatus, backrest, glitchtip,
    grafana, authelia, meilisearch (see _REGISTRAR_ORDER in
    src/fabrik/orchestrator/infrastructure.py)

Deployment target:  Coolify on VPS (Docker Compose) behind Traefik
Observability:      Prometheus + Grafana + Loki + Alertmanager + Gatus
                    (see docs/reference/health-monitoring.md)
```

---

## Project Types & Decision Matrix

### Decision Tree

```
Does it need to run continuously (24/7)?
├── YES → Container (Dockerfile + compose.yaml + Coolify)
│   ├── Listens on port? → Service (API, web app)
│   └── Processes queue? → Worker
└── NO  → No container
    ├── Importable? → Library (pip install)
    └── Runnable? → CLI Tool / Script (rsync to VPS)
```

### Type Comparison

| Type | Runtime | Runs 24/7 | Container | Deploy Method |
|------|---------|-----------|-----------|---------------|
| `python-api` | Python | ✅ Yes | ✅ Yes | `fabrik apply` → Coolify |
| `node-api` | Node.js | ✅ Yes | ✅ Yes | `fabrik apply` → Coolify |
| `file-api` | Node.js | ✅ Yes | ✅ Yes | `fabrik apply` → Coolify |
| `file-worker` | Python | ✅ Yes | ✅ Yes | `fabrik apply` → Coolify |
| `saas-skeleton` | TypeScript | ✅ Yes | ✅ Yes | `fabrik apply` → Coolify |
| `wordpress` | PHP | ✅ Yes | ✅ Yes | `fabrik apply` → Coolify (preset: `saas`/`company`/`content`/`landing`/`ecommerce`) |
| `docusaurus` | TypeScript | ❌ No | ❌ No | Static host |
| `chrome-extension` | TypeScript | ✅ Yes | ✅ Yes | `fabrik apply` → Coolify (backend) + Chrome Web Store (extension) |
| `mobile-app` | TypeScript | ❌ No | ❌ No | App stores |
| `desktop-app` | TypeScript | ❌ No | ❌ No | Direct dist |
| `static-site` | TypeScript | ✅ Yes | ✅ Yes | `fabrik apply` → Coolify |

### Per-Type Scaffold Details

| Type | Runtime | Container | Key Dirs | Deploy |
|------|---------|-----------|----------|--------|
| `python-api` | Python | ✅ | `src/`, `tests/` | Coolify |
| `node-api` | Node.js | ✅ | `src/` | Coolify |
| `file-api` | Node.js | ✅ | `src/` | Coolify |
| `file-worker` | Python | ✅ | `worker/` | Coolify |
| `saas-skeleton` | TypeScript | ✅ | `app/`, `components/`, `lib/` | Coolify |
| `wordpress` | PHP | ✅ | `plugins/`, `themes/`, `backup/` | Coolify (preset: `saas`/`company`/`content`/`landing`/`ecommerce`) |
| `docusaurus` | TypeScript | ❌ | `docs/`, `openapi.yaml`, `src/css/` | Static host |
| `chrome-extension` | TypeScript | ✅ | `extension/`, `server/` | Coolify (backend) + Chrome Web Store (extension) |
| `mobile-app` | TypeScript | ❌ | `src/navigation/`, `src/features/` | App stores |
| `desktop-app` | TypeScript | ❌ | `electron/` | Direct dist |
| `static-site` | TypeScript | ✅ | `app/`, `components/`, `lib/` | Coolify |

#### Per-Type Directory Structures

**`python-api`** — FastAPI REST service:
```
src/<package>/main.py   tests/   Dockerfile   compose.yaml   pyproject.toml
```

**`node-api`** — Express/Fastify API:
```
src/index.js   tests/   Dockerfile   compose.yaml   package.json
```

**`file-api`** — File handling API (Node.js + storage):
```
src/index.js   tests/   Dockerfile   compose.yaml   package.json
```

**`file-worker`** — Background file processor:
```
worker/main.py   Dockerfile   compose.yaml   requirements.txt
```

**`saas-skeleton`** — Next.js full SaaS:
```
app/   components/   lib/   Dockerfile   compose.yaml   package.json   tailwind.config.ts
```

**`wordpress`** — WordPress site (preset selects theme/plugin bundle; no Dockerfile — uses official `wordpress` image via Compose):
```
plugins/   themes/   backup/   config/preset.yaml
compose.yaml.j2   compose-coolify.yaml.j2   wp-config-extra.php   .env.example
```

**`docusaurus`** — Documentation site with OpenAPI docs (no container):
```
package.json              # Docusaurus deps + OpenAPI plugin deps (from template)
docusaurus.config.js      # Site config with OpenAPI plugin/theme wiring
sidebars.js               # guideSidebar + apiSidebar (requires docs/api/sidebar.js)
openapi.yaml              # Placeholder OpenAPI spec (specPath for plugin)
docs/intro.md             # Getting-started page
docs/api/sidebar.js       # API sidebar placeholder (gen-api regenerates)
src/css/custom.css        # Custom Docusaurus theme CSS
static/img/.gitkeep       # Static assets directory
```

**`chrome-extension`** — Browser extension (Vite + CRXJS) + Python backend:
```
extension/          # Chrome extension (TypeScript + Vite + CRXJS)
  src/
    popup.html
    popup.ts
    background.ts
    content.ts
  icons/            # icon16.png, icon48.png, icon128.png + README.md
  manifest.json
  package.json
  vite.config.ts
server/             # Python backend (FastAPI)
  src/<package>/main.py
Dockerfile
compose.yaml
requirements.txt
Makefile
```

**`mobile-app`** — React Native app (no container, template-backed):
```
package.json                              # React Native deps + navigation (from template)
src/App.tsx                               # SafeAreaProvider + AppNavigator entry
src/navigation/AppNavigator.tsx           # React Navigation container
src/navigation/types.ts                   # Navigation type definitions
src/features/files/types.ts               # File feature types
src/features/files/services/fileService.ts # File API service
src/features/files/hooks/useFiles.ts      # File list hook
src/features/files/hooks/useFileUpload.ts # File upload hook
src/features/files/screens/FileListScreen.tsx
src/features/files/screens/FileUploadScreen.tsx
```

> **`static-site`** reuses the `saas-skeleton` template structure (`app/`, `components/`, `lib/`). No separate directory listing needed.

**`desktop-app`** — Electron app (no container, template-backed):
```
package.json              # Electron deps + electron-builder config (from template)
electron/main.js          # Electron main process (BrowserWindow + auto-updater)
index.html                # Renderer entry (referenced by electron/main.js)
```

---

## CLI Commands Reference

### Project Creation

```bash
# Canonical: scaffold project tree + auto-emit specs/services/<name>.yaml in one step
fabrik scaffold <name> [--type <type>] [--preset <preset>] [--description <text>] [--no-spec] [--dev-port <port>] [--db]

# DEPRECATED (hidden, removed-after-next-release): create spec from template only
# fabrik new <name> --template <template> [--domain <domain>] [--output <dir>] [--from-project <path>]

# List available templates
fabrik templates
```

#### `fabrik scaffold` Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | `python-api` | Project type (see Per-Type Scaffold Details table) |
| `--preset` | _(none)_ | Preset variant — only used with `--type wordpress` (`saas`, `company`, `content`, `landing`, `ecommerce`) |
| `--description` / `-d` | `"A new project"` | Short project description |
| `--no-spec` | `false` | Skip automatic spec file generation |
| `--db` | `false` | Enable PostgreSQL database (creates DB, adds DATABASE_URL to .env.local) |
| `--dev-port` | `8080` | Local dev port (only meaningful for `--type wordpress` on WSL) |

### `fabrik scaffold` Output (Complete File List)

When you run `fabrik scaffold my-project -d "My description"`, the following structure is created:

#### Actual Project Tree

> Tree below is illustrative for `--type python-api`. Exact directory and file counts vary by type and template version — run `find /opt/<name> -type f | wc -l` after a fresh scaffold to verify. The structure below was last cross-checked against `_scaffold_python_api()` and `_scaffold_shared()` in `src/fabrik/scaffold.py` on 2026-04-29.

```
/opt/my-project/
├── .droid/
│   ├── .gitignore                   # Blocks Kilo runtime files from git
│   ├── review-context/
│   │   └── .gitkeep                 # Tracked placeholder for Traycer plans
│   └── traycer-reports/
│       └── .gitignore               # Commits dir, gitignores *.md reports
├── .cache/                          # Cache directory (gitignored)
├── .tmp/                            # Temp files (gitignored, NOT /tmp/)
├── .windsurf/
│   ├── rules/                       # Windsurf IDE rules (22 files)
│   │   ├── 10-python.md             # Python/FastAPI patterns
│   │   ├── 15-api-contracts.md      # API contract patterns
│   │   ├── 20-typescript.md         # TypeScript patterns
│   │   ├── 25-data-postgres.md      # PostgreSQL/data patterns
│   │   ├── 30-ops.md                # Docker/Compose patterns
│   │   ├── 35-security-auth.md      # Security & auth patterns
│   │   ├── 40-documentation.md      # Documentation rules
│   │   ├── 42-docusaurus.md         # Docusaurus patterns
│   │   ├── 45-testing-strategy.md   # Testing strategy
│   │   ├── 50-code-review.md        # Workflow pointer
│   │   ├── 55-observability.md      # Observability patterns
│   │   ├── 60-saas-ui.md            # SaaS UI patterns
│   │   ├── 62-wordpress.md          # WordPress patterns
│   │   ├── 65-rag-search.md         # RAG/search patterns
│   │   ├── 70-chrome-ext.md         # Chrome extension patterns
│   │   ├── 75-workers-jobs.md       # Workers & jobs patterns
│   │   ├── 80-mobile.md             # Mobile app patterns
│   │   ├── 85-payments-billing.md   # Payments & billing patterns
│   │   ├── 90-automation.md         # YOLO modes, Fabrik skills
│   │   ├── 95-multi-tenant-saas.md  # Multi-tenant SaaS patterns
│   │   └── ocoron-design-system.md  # Ocoron Design System v2
│   └── workflows/                   # Cascade slash-command workflows (10 files)
├── config/                          # Configuration files
├── data/                            # Data files (gitignored)
├── docs/
│   ├── archive/                     # Archived documents
│   ├── development/                 # Development plans
│   ├── guides/                      # How-to guides
│   ├── operations/                  # Ops runbooks
│   ├── reference/                   # Technical reference
│   ├── BUSINESS_MODEL.md            # Business context
│   ├── CONFIGURATION.md             # Config reference (env vars)
│   ├── QUICKSTART.md                # Getting started
│   ├── README.md                    # Docs index
│   └── TROUBLESHOOTING.md           # Common issues
├── logs/                            # Log files (gitignored)
├── output/                          # Output files (gitignored)
├── scripts/
│   ├── enforcement/                 # Quality gate checks (35 files inc. __init__.py, entire dir copied)
│   │   ├── __init__.py
│   │   ├── check_android_env.py
│   │   ├── check_changelog.py       # CHANGELOG.md updated
│   │   ├── check_compose_services.py
│   │   ├── check_configuration_md.py
│   │   ├── check_deps_sync.py
│   │   ├── check_doc_sprawl.py
│   │   ├── check_docker.py
│   │   ├── check_docs.py
│   │   ├── check_duplicates.py
│   │   ├── check_env_contract.py
│   │   ├── check_env_example.py
│   │   ├── check_env_updates.py
│   │   ├── check_env_vars.py
│   │   ├── check_health.py
│   │   ├── check_index_md.py
│   │   ├── check_openapi_sync.py
│   │   ├── check_opencode_json.py
│   │   ├── check_plan_quality.py
│   │   ├── check_plans.py
│   │   ├── check_ports.py
│   │   ├── check_readme_md.py
│   │   ├── check_rule_size.py
│   │   ├── check_schema_sync.py
│   │   ├── check_secrets.py
│   │   ├── check_structure.py
│   │   ├── check_test_coverage.py
│   │   ├── check_test_proposal.py
│   │   ├── check_watchdog.py
│   │   └── validate_conventions.py
│   ├── docs_updater.py              # Documentation drift checker
│   ├── final_gate.py                # Pre-commit quality gate
│   ├── health_checker.py            # Health endpoint checker
│   ├── kilo_code_review.py          # AI code review
│   ├── kilo_docs_enforcer.py        # Documentation enforcer
│   ├── update_agents_toc.py         # AGENTS.md TOC updater
│   ├── runc                         # Check job status
│   ├── rund                         # Run detached command
│   ├── rundsh                       # Shell into container
│   ├── runk                         # Kill job
│   ├── sync_cascade_backup.sh       # Backup Cascade session
│   └── sync_extensions.sh           # Sync Windsurf extensions
├── src/
│   └── my_project/                  # Main Python package
│       ├── __init__.py
│       └── main.py                  # FastAPI entry point
├── templates/
│   ├── docs/                        # Documentation templates
│   │   ├── .doc-policy.md
│   │   ├── EXECUTION_PLAN_TEMPLATE.md
│   │   ├── FEATURES_TEMPLATE.md
│   │   ├── MODULE_REFERENCE_TEMPLATE.md
│   │   └── PLAN_TEMPLATE.md
│   ├── saas-skeleton/               # Full SaaS starter (Next.js)
│   │   ├── app/                     # Next.js app router
│   │   ├── components/              # React components
│   │   ├── lib/                     # Utilities
│   │   ├── types/                   # TypeScript types
│   │   ├── Dockerfile
│   │   ├── compose.yaml
│   │   └── package.json
│   └── spec-pipeline/               # Traycer Stage 0 discovery (4 files)
│       ├── 00-idea-prompt.md        # Idea capture prompt
│       ├── 01-scope-prompt.md       # IN/OUT boundary prompt
│       ├── 02-spec-prompt.md        # Full spec generation prompt
│       └── README.md                # Pipeline overview
├── tests/
│   ├── __init__.py
│   └── test_health.py               # Health endpoint test
├── AGENTS.md                        # Copied from /opt/fabrik/AGENTS.md
├── CHANGELOG.md                     # Version history
├── compose.yaml                     # Docker Compose config
├── compose.dev.yaml                 # Dev overlay (hot reload)
├── .dockerignore                    # Excludes venv/.git from builds
├── Dockerfile                       # Production Docker build
├── .env.example                     # Env var template
├── .gitignore                       # Git ignore patterns
├── INDEX.md                         # Master file index
├── Makefile                         # Shortcuts: make dev, test, review
├── opencode.json                    # Kilo CLI configuration
├── PORTS.md                         # Port allocation registry
├── .pre-commit-config.yaml          # Pre-commit hooks
├── project.yaml                     # Project metadata (source of truth)
├── pyproject.toml                   # Python project config
├── README.md                        # Project overview
├── requirements.txt                 # Python dependencies
└── .windsurfrules                   # Copied from /opt/fabrik/.windsurfrules
```

#### Files Created (70+)

| File | Source Template | Purpose |
|------|-----------------|---------|
| **Root Files** | | |
| `README.md` | `docs/PROJECT_README_TEMPLATE.md` | Project overview |
| `CHANGELOG.md` | `docs/CHANGELOG_TEMPLATE.md` | Version history |
| `AGENTS.md` | Copied from `/opt/fabrik/AGENTS.md` | AI agent instructions |
| `.windsurfrules` | Copied from `/opt/fabrik/.windsurfrules` | Cascade compact agent contract |
| `.gitignore` | Generated inline | Git ignore patterns |
| `.env.example` | Generated inline | Env var template |
| `requirements.txt` | Generated inline | Production Python dependencies |
| `requirements-dev.txt` | Generated inline | Development dependencies (ruff, mypy, etc.) |
| `Dockerfile` | `docker/Dockerfile.python` | Production Docker build |
| `compose.yaml` | `docker/compose.yaml.template` | Docker Compose config |
| `pyproject.toml` | `python/pyproject.toml.template` | Python project config |
| `.pre-commit-config.yaml` | `pre-commit-config.yaml` | Pre-commit hooks |
| `INDEX.md` | Generated inline | Master file index |
| `PORTS.md` | Generated inline | Port allocation registry |
| `project.yaml` | Generated inline | Project metadata — source of truth for sync |
| `opencode.json` | Copied from Fabrik | Kilo CLI configuration |
| **Documentation** | | |
| `docs/README.md` | `docs/DOCS_INDEX_TEMPLATE.md` | Docs index |
| `docs/QUICKSTART.md` | `docs/QUICKSTART_TEMPLATE.md` | Getting started |
| `docs/CONFIGURATION.md` | `docs/CONFIGURATION_TEMPLATE.md` | Config reference |
| `docs/TROUBLESHOOTING.md` | `docs/TROUBLESHOOTING_TEMPLATE.md` | Common issues |
| `docs/BUSINESS_MODEL.md` | `docs/BUSINESS_MODEL_TEMPLATE.md` | Business context |
| **Source Code** | | |
| `src/<package>/main.py` | Generated inline | FastAPI entry point |
| `src/<package>/__init__.py` | Generated inline | Package init |
| `tests/__init__.py` | Generated inline | Tests package |
| `tests/test_health.py` | Generated inline | Health endpoint test |
| **Quality Gates** | | |
| `scripts/final_gate.py` | Copied from Fabrik | Pre-commit quality gate |
| `scripts/health_checker.py` | Copied from Fabrik | Health endpoint checker |
| `scripts/kilo_code_review.py` | Copied from Fabrik | AI code review |
| `scripts/kilo_docs_enforcer.py` | Copied from Fabrik | Documentation enforcer |
| `scripts/docs_updater.py` | Copied from Fabrik | Documentation drift checker |
| `scripts/update_agents_toc.py` | Copied from Fabrik | AGENTS.md TOC updater |
| **Enforcement Scripts (35)** | | |
| `scripts/enforcement/*.py` | Copied from Fabrik | Individual quality gate checks (full dir copy from `/opt/fabrik/scripts/enforcement/`) |
| **Dev Tooling** | | |
| `Makefile` | `docker/Makefile.python` | Dev shortcuts (`make dev`, `make test`, `make review`) |
| `compose.dev.yaml` | `docker/compose.dev.yaml.template` | Dev overlay with bind-mount hot reload |
| `.dockerignore` | `docker/dockerignore.template` | Excludes `.venv`, `.git`, `__pycache__` from Docker context |
| `.droid/.gitignore` | Generated inline | Blocks Kilo runtime files; tracks `review-context/` |
| `.droid/review-context/.gitkeep` | Generated inline | Ensures `review-context/` is committed |
| `.droid/traycer-reports/.gitignore` | Generated inline | Commits dir, gitignores `*.md` reports |
| `scripts/runc` | `scripts/runc` | Check detached job status |
| `scripts/rund` | `scripts/rund` | Run command in detached mode |
| `scripts/rundsh` | `scripts/rundsh` | Shell into container |
| `scripts/runk` | `scripts/runk` | Kill detached job |
| `scripts/sync_cascade_backup.sh` | `scripts/sync_cascade_backup.sh` | Backup Cascade session |
| `scripts/sync_extensions.sh` | `scripts/sync_extensions.sh` | Sync Windsurf extensions |
| **Windsurf Rules (22)** | | |
| `.windsurf/rules/10-python.md` | Copied from Fabrik | Python/FastAPI patterns |
| `.windsurf/rules/15-api-contracts.md` | Copied from Fabrik | API contract patterns |
| `.windsurf/rules/20-typescript.md` | Copied from Fabrik | TypeScript patterns |
| `.windsurf/rules/25-data-postgres.md` | Copied from Fabrik | PostgreSQL/data patterns |
| `.windsurf/rules/30-ops.md` | Copied from Fabrik | Docker/Compose patterns |
| `.windsurf/rules/35-security-auth.md` | Copied from Fabrik | Security & auth patterns |
| `.windsurf/rules/40-documentation.md` | Copied from Fabrik | Documentation rules |
| `.windsurf/rules/42-docusaurus.md` | Copied from Fabrik | Docusaurus patterns |
| `.windsurf/rules/45-testing-strategy.md` | Copied from Fabrik | Testing strategy |
| `.windsurf/rules/50-code-review.md` | Copied from Fabrik | Workflow pointer |
| `.windsurf/rules/55-observability.md` | Copied from Fabrik | Observability patterns |
| `.windsurf/rules/60-saas-ui.md` | Copied from Fabrik | SaaS UI patterns |
| `.windsurf/rules/62-wordpress.md` | Copied from Fabrik | WordPress patterns |
| `.windsurf/rules/65-rag-search.md` | Copied from Fabrik | RAG/search patterns |
| `.windsurf/rules/70-chrome-ext.md` | Copied from Fabrik | Chrome extension patterns |
| `.windsurf/rules/75-workers-jobs.md` | Copied from Fabrik | Workers & jobs patterns |
| `.windsurf/rules/80-mobile.md` | Copied from Fabrik | Mobile app patterns |
| `.windsurf/rules/85-payments-billing.md` | Copied from Fabrik | Payments & billing patterns |
| `.windsurf/rules/90-automation.md` | Copied from Fabrik | YOLO modes, Fabrik skills |
| `.windsurf/rules/95-multi-tenant-saas.md` | Copied from Fabrik | Multi-tenant SaaS patterns |
| `.windsurf/rules/ocoron-design-system.md` | Copied from Fabrik | Ocoron Design System v2 (visual + verbal identity) |
| **Templates** | | |
| `templates/docs/*.md` | Copied from Fabrik | Documentation templates (5 files) |
| `templates/saas-skeleton/` | Copied from Fabrik | Full Next.js SaaS starter |
| `templates/spec-pipeline/` | Copied from Fabrik | Traycer Stage 0 discovery pipeline (4 files) |

#### No Symlinks — All Files Copied

**All governance files are COPIED (not symlinked) for workspace isolation:**

| File | Source | Purpose |
|------|--------|---------|
| `AGENTS.md` | `/opt/fabrik/AGENTS.md` | AI agent instructions |
| `AGENTS-compact.md` | `/opt/fabrik/AGENTS-compact.md` | Compact agent instructions |
| `.windsurfrules` | `/opt/fabrik/.windsurfrules` | Cascade agent contract |
| `.windsurf/rules/*` | `/opt/fabrik/.windsurf/rules/` | Windsurf IDE rules (22 files) |
| `.windsurf/workflows/*` | `/opt/fabrik/.windsurf/workflows/` | Cascade slash-command workflows |
| `opencode.json` | `/opt/fabrik/opencode.json` | Kilo CLI configuration |

**Why copied, not symlinked:** Prevents AI agents in child projects from discovering `/opt/fabrik` parent directory (session isolation).

#### Generated Code Examples

**`src/<package>/main.py`** (FastAPI with proper health check):
```python
"""Main entry point for my-project."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Application lifespan handler."""
    # Startup: initialize resources here
    yield
    # Shutdown: cleanup resources here


app = FastAPI(title="my-project", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check - tests actual dependencies, returns non-200 on failure."""
    db_url = os.getenv("DATABASE_URL")
    deps = {}
    all_ok = True

    # Database check (only if configured)
    if db_url:
        try:
            # TODO: Replace with actual async DB ping when DB is added
            deps["database"] = "configured"
        except Exception as e:
            deps["database"] = f"error: {str(e)}"
            all_ok = False
    else:
        deps["database"] = "not_configured"

    status_code = 200 if all_ok else 503
    return JSONResponse(
        content={
            "service": "my-project",
            "status": "ok" if all_ok else "degraded",
            "dependencies": deps,
        },
        status_code=status_code,
    )


@app.get("/")
async def root():
    return {"message": "Welcome to my-project"}
```

**`.gitignore`**:
```
.env
venv/
__pycache__/
logs/
data/
.tmp/
.cache/
output/
*.log
.venv/
.droid/kilo_usage.jsonl
.droid/reviews/
.droid/kilo_models_cache.json
.droid/.kilo_cache_last_refresh
```

**`.env.example`**:
```bash
# my-project Configuration
DATABASE_URL=postgresql://user:pass@localhost:5432/my-project_dev
LOG_LEVEL=INFO
PORT=8000
```

**`requirements.txt`**:
```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.0
python-dotenv>=1.0.0
```

#### Post-Creation Actions

After file creation, `fabrik scaffold` also:

1. **project.yaml** - Creates per-project metadata file (name, type, status, port, cost, tags, etc.)
2. **Virtual environment** - Creates `.venv` and installs development dependencies from `requirements-dev.txt`
3. **Git init** - Initializes git repository
4. **Branch creation** - Creates and switches to `mobasak/<project-name>` branch
5. **Pre-commit install** - Copies config and runs `pre-commit install`
6. **Type patching** - Updates `project.yaml` with actual project type and port
7. **Initial commit** - Stages all files and commits "Initial commit"
8. **Project sync** - Runs `sync_projects.py` to register the new project in `data/projects.yaml` and `docs/BUSINESS_MODEL.md`
9. **Auto-spec generation** - For SPEC_ENABLED_TYPES, generates deployment spec at `/opt/fabrik/specs/services/{name}.yaml` (skipped if `--no-spec`)
10. **Deployment validation** - Runs `validate-deploy` checks and prints warnings (non-blocking)

> See [Sync Projects Workflow](SYNC_PROJECTS_WORKFLOW.md) for details on `project.yaml` schema and sync mechanism.

#### Kilo Workflow Integration

`fabrik scaffold` now provisions the `.droid/` directory required by `kilo_code_review.py` automatically:

| Path | Purpose |
|------|---------|
| `.droid/review-context/` | Where agents save plan artifacts (`task-${TRAYCER_TASK_ID}.md`, unique per task) |
| `.droid/.gitignore` | Commits `review-context/` only; blocks runtime files |
| `.droid/review-context/.gitkeep` | Ensures directory is tracked by git |

**Result:** Running `kilo_code_review.py review src/` works immediately after scaffold — no manual `.droid/` setup needed.

**Developer shortcuts (all available immediately after scaffold):**

```bash
make dev          # Start dev server with hot reload
make test         # Run pytest
make review       # Run Kilo code review
./scripts/rund    # Docker hot-reload container
./scripts/runc    # Docker production container
./scripts/rundsh  # Shell into running container
```

#### Project Name Validation

- Must be lowercase
- Must start with a letter
- Only letters, numbers, hyphens allowed
- Max 50 characters
- Cannot use reserved names: `src`, `test`, `tests`, `lib`, `bin`, `opt`, `tmp`, `fabrik`, `python`, etc.

### Deployment

> The deploy half is documented canonically in `@/opt/fabrik/docs/DEPLOYMENT.md`. Below is the syntax-only summary; that file is the source of truth for state-machine, registrar, and verifier behavior.

```bash
# Preview deployment plan (dry run; legacy path)
fabrik plan <spec.yaml> [-s KEY=VALUE]

# Execute deployment (legacy path; --use-orchestrator opts into the new pipeline)
fabrik apply <spec.yaml> \
  [-s KEY=VALUE]            # multiple secrets, KEY=VALUE format
  [--yes]                   # skip confirmation prompt
  [--dry-run]               # simulate without making changes (forces orchestrator path)
  [--skip-dns]              # skip DNS record creation
  [--skip-deploy]           # render files only, skip Coolify deploy
  [--use-orchestrator]      # use new orchestrator pipeline (will become default post-Phase 4)
  [--skip-health-check]     # skip verifier HTTP probe
  [--keep-on-failure]       # B27: leave Coolify app + DNS + GlitchTip etc. on failure (proof-run / debugging)

# Project-based deploy (reads /opt/<project>/project.yaml; routes WordPress vs. service)
fabrik deploy [--project /opt/<name>] [--dry-run]

# Status
fabrik status <spec.yaml>

# Logs (NOTE: two distinct commands)
fabrik app-logs <spec.yaml> [-n <lines>] [--follow]   # Coolify container logs for the spec's app
fabrik logs <service> [-n <tail>] [--since <range>]   # Loki query by service name (1h, 24h, 7d)

# Redeploy a Coolify app by name or UUID (no spec needed)
fabrik redeploy <app> [--force]

# Remove deployment
fabrik destroy <spec.yaml> \
  [--yes]                   # skip confirmation
  [--keep-dns]              # keep DNS records
  [--keep-files]            # keep generated files (compose.yaml, Dockerfile, etc.)
  [--drop-data]             # also DROP per-service Postgres DB and DELETE MeiliSearch index (off by default)
  [--dry-run]               # plan only; mutate nothing
```

### Project Management

```bash
# List all projects (reads data/projects.yaml)
fabrik projects [--status <deployed|ready|development>] [--sync]

# Scan /opt for projects, refresh registry + BUSINESS_MODEL.md
fabrik scan [--base /opt] [--health]

# Validate scaffold structure (file presence per type)
fabrik validate <project_path> [--type <type>]

# Validate deployment readiness (5 local checks: template, .env.example,
# Dockerfile, /health endpoint, spec pre-existence)
fabrik validate-deploy <project_path> [-t <type>]

# Auto-fix missing files in a scaffolded project
fabrik fix <project_path> [--type <type>] [--dry-run]

# Verify a deployed service end-to-end (DNS + HTTP + SSL + GlitchTip DSN)
fabrik verify <domain> [-s <spec>] [-a <app-name>] [--no-rollback]

# List available scaffold templates
fabrik templates
```

### Command Groups

Five subcommand groups — each has its own `fabrik <group> --help`:

```bash
fabrik wp     plan | apply | verify | flush          # WordPress site factory
fabrik ai     generate | revise | usage              # LLM content generation (Claude / OpenAI)
fabrik domain check | provision | ready | integrations | sitemap | zones | buy   # DNS Manager
fabrik content publish ...                           # Drain SEO briefs → publish to WordPress
fabrik seo    site-register | ...                    # SEO service (keyword research, brief mgmt)
```

For full `wp` flow including `site.yaml` schema, see `@/opt/fabrik/docs/workflows/wordpress-site-workflow.md`.

---

## Scaffold-to-Deploy Integration (P2/P3/P4)

### Auto-Spec Generation (P2 - Implemented 2026-04-10)

**Purpose:** Automatically generate deployment spec files when scaffolding projects, eliminating manual spec creation.

**Enabled Types (`SPEC_ENABLED_TYPES`, source: `src/fabrik/spec_generator.py:58`):**

- `python-api`
- `saas-skeleton`
- `node-api`
- `file-api`
- `file-worker`
- `static-site`
- `docusaurus`

> **Excluded by design:** `chrome-extension`, `mobile-app`, `desktop-app` are **packaged artifacts** (Chrome Web Store / app stores / direct dist) — they don't deploy to a VPS, so emitting a `specs/services/<name>.yaml` would just create a phantom DNS record + Coolify app on every `fabrik apply`. `wordpress` uses the dedicated `fabrik wp` pipeline with its own `site.yaml` schema.

**How it works:**
1. After `fabrik scaffold` completes, `create_project()` calls `generate_and_save_spec()`
2. `extract_project_context()` reads `compose.yaml` and `.env.example` from the scaffolded project
3. `generate_spec()` builds a Spec object with type-based defaults (resources, health, kind)
4. Spec is saved to `/opt/fabrik/specs/services/{name}.yaml`

**Worker kind mapping:**
- `file-worker` → `Kind.WORKER` (no HTTP exposure)
- All other types → `Kind.SERVICE` (HTTP service)

**Skip spec generation:**
```bash
fabrik scaffold my-api --type python-api --no-spec
```

### CLI Enhancements (P3 - Implemented 2026-04-10, superseded by Phase 4k 2026-04-22)

> 📜 **HISTORICAL:** `fabrik new --from-project` and `fabrik new --output` shipped in P3 then were superseded when `fabrik new` was deprecated in Phase 4k. `fabrik scaffold` now generates the spec automatically (no `--from-project` extraction needed because the spec is emitted in lock-step with the project tree, with a `shape:` block driven by `templates/<type>/defaults.yaml`).

### Deployment Validation (P4 - Implemented 2026-04-10)

**`fabrik validate-deploy` command:**
Checks deployment readiness of a scaffolded project:

```bash
fabrik validate-deploy /opt/my-api --type python-api
```

**5 checks performed:**
1. **Deploy template exists** - Template for the project type exists in `/opt/fabrik/templates/`
2. **`.env.example` present** - Required for secret detection
3. **Dockerfile present** - Required for container builds
4. **Health endpoint detected** - Greps source files for `/health` string
5. **Spec pre-existence info** - Warns if spec already exists (informational only)

**Post-scaffold validation:**
`fabrik scaffold` automatically runs validation after project creation and prints warnings (non-blocking).

**Module:** `src/fabrik/deploy_validator.py` (reusable module with `validate()` and `format_warnings()` functions)

---

## Project Templates

### Available Templates

Members of `SCAFFOLD_TYPES` (`@/opt/fabrik/src/fabrik/scaffold.py:127`):

| Template | Language | Use Case | VPS Deploy? | Spec Auto-Generated? |
|----------|----------|----------|-------------|-----------------------|
| `python-api` | Python | FastAPI REST APIs | ✅ Coolify | ✅ |
| `node-api` | Node.js | Express/Fastify APIs | ✅ Coolify | ✅ |
| `file-api` | Node.js | File handling APIs (S3/local) | ✅ Coolify | ✅ |
| `file-worker` | Python | Background file processors (queue consumer, no HTTP) | ✅ Coolify (Kind.WORKER) | ✅ |
| `saas-skeleton` | TypeScript | Full SaaS applications (Next.js + Tailwind) | ✅ Coolify | ✅ |
| `static-site` | TypeScript | Static websites (Next.js + Tailwind) | ✅ Coolify | ✅ |
| `docusaurus` | TypeScript | Documentation sites with OpenAPI | ✅ Coolify (static host) | ✅ |
| `wordpress` | PHP | WordPress sites (preset: saas/company/content/landing/ecommerce) | ✅ Coolify via `fabrik wp` (uses `site.yaml`) | ❌ (separate `fabrik wp` pipeline) |
| `chrome-extension` | TypeScript | Browser extensions + FastAPI backend | ✅ backend only via Coolify; extension → Chrome Web Store | ❌ (artifact) |
| `mobile-app` | TypeScript | React Native apps | ❌ App stores | ❌ (artifact) |
| `desktop-app` | TypeScript | Electron apps | ❌ Direct dist | ❌ (artifact) |

### Template Locations

`@/opt/fabrik/templates/` — 16 directories, verified 2026-04-29:

```text
/opt/fabrik/templates/
├── scaffold/           # Shared scaffolding (docs/, docker/, scripts/, db/, python/) consumed by every type
├── saas-skeleton/      # Full Next.js SaaS starter (also reused by static-site)
├── next-tailwind/      # Next.js + Tailwind primitives shared by saas-skeleton / static-site
├── static-site/        # Static-site-specific overrides (small)
├── python-api/         # Python FastAPI template
├── node-api/           # Node.js API template
├── file-api/           # File handling API (Node.js)
├── file-worker/        # Background worker (Python)
├── wordpress/          # WordPress setup (preset-driven)
├── docusaurus/         # Docusaurus documentation site
├── chrome-extension/   # Browser extension (Vite + CRXJS) + FastAPI backend
├── mobile-app/         # React Native
├── desktop-app/        # Electron
├── spec-pipeline/      # Traycer Stage 0 discovery pipeline (4 prompt files + README)
├── traycer/            # Traycer integration helpers
└── prompts/            # Shared LLM prompt fragments
```

---

## Template Complexity Tiers

> 📜 **REMOVED 2026-04-29.** This section previously described "Simple / Medium / Complex" tiers backed by `templates/scaffold/{simple,medium,complex}.yaml`. **`simple.yaml` and `medium.yaml` were never shipped**; only `complex.yaml` exists (`@/opt/fabrik/templates/scaffold/complex.yaml`, 1988 bytes). The tier system also referenced `CLAUDE.md` for agent instructions, but the scaffolder writes `AGENTS.md` + `AGENTS-compact.md` (never `CLAUDE.md`).
>
> The actual project structure produced by `fabrik scaffold` is documented above in [`fabrik scaffold` Output](#fabrik-scaffold-output-complete-file-list) and varies per `--type`. There is no separate complexity-tier dimension in the current code.

---

## SaaS Skeleton (Next.js)

Full-featured SaaS starter with:

### Features
- **Marketing Site:** Landing, pricing, FAQ, terms, privacy
- **App Shell:** Sidebar navigation, dashboard, job workflow
- **Chat UI:** SSE streaming for AI chat integration
- **Supabase Ready:** Auth and database

### Structure
```
saas-skeleton/
├── app/
│   ├── (marketing)/          # Public pages
│   │   ├── page.tsx          # Landing
│   │   ├── pricing/
│   │   ├── faq/
│   │   ├── terms/
│   │   └── privacy/
│   ├── (app)/app/            # Authenticated pages
│   │   ├── page.tsx          # Dashboard
│   │   ├── new/              # Create job
│   │   ├── items/            # List jobs
│   │   ├── items/[id]/       # Job detail
│   │   └── settings/
│   ├── api/
│   │   ├── chat/             # SSE streaming endpoint
│   │   └── health/           # Health check
│   └── layout.tsx
├── components/
│   ├── shell/                # AppShell
│   ├── common/               # PageHeader, SectionCard, EmptyState
│   └── chat/                 # ChatUI, SSEStream
├── lib/
│   ├── config/               # Site config
│   └── utils.ts
├── types/
├── Dockerfile
├── compose.yaml
├── package.json
├── tailwind.config.ts
└── .env.example
```

### Quick Start
```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/my-saas
cd /opt/my-saas
npm install
cp .env.example .env
npm run dev
```

### Customization
1. **Branding:** Edit `lib/config/site.ts`
2. **Navigation:** Edit `navConfig` in `lib/config/site.ts`
3. **Colors:** Edit CSS variables in `app/globals.css`
4. **Features:** Add routes in `app/(app)/app/`

**Template:** `@/opt/fabrik/templates/saas-skeleton/`

---

## Docker Templates

### Python Dockerfile

Multi-stage build with:
- Base: `python:<current-stable>-slim-bookworm` (NOT Alpine, NOT plain slim)
- Non-root user
- Health check
- Entry point customization

**Template:** `@/opt/fabrik/templates/scaffold/docker/Dockerfile.python`

```dockerfile
FROM python:<current-stable>-slim-bookworm AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache -r requirements.txt

FROM python:<current-stable>-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.x/site-packages /usr/local/lib/python3.x/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

ENV PORT=8000
EXPOSE ${PORT}
CMD ["sh", "-c", "uvicorn <package_name>.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

### Compose Template

**Template:** `@/opt/fabrik/templates/scaffold/docker/compose.yaml.template`

```yaml
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=${DATABASE_URL:?Database URL is required}
      - PORT=${PORT:-8000}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    restart: unless-stopped
```

### Node.js Dockerfile

**Template:** `@/opt/fabrik/templates/scaffold/docker/Dockerfile.node`

---

## Documentation Templates

Available in `@/opt/fabrik/templates/scaffold/docs/` (14 files + a `workflows/` subdir, verified 2026-04-29):

| Template | Purpose |
|----------|---------|
| `PROJECT_README_TEMPLATE.md` | Project root README |
| `QUICKSTART_TEMPLATE.md` | 5-minute getting started |
| `CONFIGURATION_TEMPLATE.md` | Settings and env-var reference |
| `DEPLOYMENT_TEMPLATE.md` | Production deployment guide |
| `TROUBLESHOOTING_TEMPLATE.md` | Common issues and fixes |
| `CHANGELOG_TEMPLATE.md` | Version history |
| `BUSINESS_MODEL_TEMPLATE.md` | Business context |
| `FEATURES_TEMPLATE.md` | Feature catalogue |
| `API_REFERENCE_TEMPLATE.md` | API reference |
| `DATABASE_SCHEMA_TEMPLATE.md` | DB schema reference |
| `LESSONS_LEARNT_TEMPLATE.md` | Lessons-learnt log |
| `STRATEGIC_BACKLOG_TEMPLATE.md` | Strategic backlog |
| `DOCS_INDEX_TEMPLATE.md` | Documentation index |
| `PROJECT_INDEX_TEMPLATE.md` | Project file index with auto-generated structure map |
| `workflows/KILO_CONSULT_WORKFLOW.md` | Kilo consult workflow (only workflow currently shipped to projects) |

---

## Project INDEX.md Maintenance

Each project includes an `INDEX.md` file with two sections:

### Manual Section (File Purposes Table)

- Lists every file with its purpose and update triggers
- Must be maintained by developers
- Updated when files are added/removed/repurposed

### Automatic Section (Documentation Structure Map)

- Auto-generated file tree of `docs/` directory
- Updated with `python scripts/docs_updater.py`
- Detects new, moved, or deleted documentation files

### Updating Project INDEX.md

```bash
# In any project directory:
cd /opt/<project-name>
python scripts/docs_updater.py        # Update structure map
python scripts/docs_updater.py --check # Check for issues
python scripts/docs_updater.py --dry-run # Preview changes
```

**Note:** Only the structure map is automatic. File purposes must be updated manually.

---

## Factory Configuration

> 📜 **REMOVED 2026-04-29.** This section previously documented `factory-settings.json`, `factory-hooks.json`, `factory-mcp.json`, and `pre-commit-config.yaml` under `templates/scaffold/`. **None of those files exist** in the current codebase. Pre-commit configuration is generated inline by `_install_pre_commit()` in `@/opt/fabrik/src/fabrik/scaffold.py:327` using a config that lives in the Fabrik repo itself, not in `templates/scaffold/`. Kilo CLI configuration is copied from `/opt/fabrik/opencode.json` directly (no template indirection).

---

## Project Lifecycle

### 1. Create

```bash
# Canonical: scaffold project tree + spec in one step
fabrik scaffold my-api --type python-api -d "REST API for users"

# Project structure only (skip spec emission)
fabrik scaffold my-tool -d "CLI utility" --no-spec
```

### 2. Develop

```bash
cd /opt/my-project
uv venv && source .venv/bin/activate
uv pip install -e .

# For services: verify Docker works
docker build -t my-api . && docker run -p 8000:8000 my-api
```

### 3. Validate

```bash
fabrik validate /opt/my-project
```

### 4. Deploy

```bash
# Services → Coolify
fabrik apply specs/my-api.yaml -s API_KEY=xxx

# Libraries/Tools → Direct sync
rsync -avz --exclude='.venv' /opt/my-tool vps:/opt/
```

### 5. Monitor

```bash
fabrik status specs/my-api.yaml
fabrik logs specs/my-api.yaml --follow
```

### 6. Destroy (if needed)

```bash
fabrik destroy specs/my-api.yaml --yes
```

---

## Conventions & Standards

### Environment Variables (CRITICAL)

```python
# CORRECT - works in WSL, Docker, Supabase
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))

# WRONG - breaks in production
DB_HOST = 'localhost'  # Hardcoded!
```

### Health Checks (MANDATORY)

```python
# CORRECT - tests actual dependencies
@app.get("/health")
async def health():
    await db.execute("SELECT 1")
    return {"status": "ok", "db": "connected"}

# WRONG - hides failures
@app.get("/health")
async def health():
    return {"status": "ok"}  # Lies!
```

### Config Loading

```python
# CORRECT - load at runtime
def get_db_url():
    return f"postgresql://{os.getenv('DB_USER')}:..."

# WRONG - class-level (env not set at import time)
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_USER')}:..."  # Fails!
```

### Docker Base Images

| Use Case | Base Image |
|----------|------------|
| Python apps | `python:<current-stable>-slim-bookworm` |
| Node.js apps | `node:<current-LTS>-bookworm-slim` |
| General | `debian:bookworm-slim` |

**Never use Alpine** — glibc compatibility, pre-built wheels, consistent behavior.

### Forbidden Patterns

| Pattern | Use Instead |
|---------|-------------|
| `/tmp/` directory | Project `.tmp/` |
| Hardcoded localhost | `os.getenv()` |
| Alpine base images | `*-bookworm-slim` |
| Class-level config | Function-level loading |

---

## File Reference Links

> All paths verified to exist as of 2026-04-29.

### Top-level template directories (`@/opt/fabrik/templates/`)

- `chrome-extension/` `desktop-app/` `docusaurus/` `file-api/` `file-worker/` `mobile-app/`
- `next-tailwind/` `node-api/` `prompts/` `python-api/` `saas-skeleton/`
- `scaffold/` `spec-pipeline/` `static-site/` `traycer/` `wordpress/`

### Shared scaffold scaffolding (`templates/scaffold/`)

- `complex.yaml` — only complexity-tier file present (1988 bytes; not currently consumed by `fabrik scaffold` — see Template Complexity Tiers section above)
- `AFCL_TEMPLATE.md` — agent-facing change log template
- `db/` — DB-init helpers
- `docker/` — Dockerfile + compose templates (see below)
- `docs/` — 14 doc templates (see Documentation Templates section)
- `python/` — Python-specific scaffold helpers
- `scripts/` — `runc`, `rund`, `rundsh`, `runk`, `sync_cascade_backup.sh`, `sync_extensions.sh`

### Docker templates (`templates/scaffold/docker/`)

- `Dockerfile.python` — Python multi-stage Dockerfile (Python 3 slim-bookworm)
- `Dockerfile.node` — Node.js Dockerfile (Node LTS slim-bookworm)
- `compose.yaml.template` — production Compose template
- `compose.dev.yaml.template` — dev overlay (bind-mount hot reload)
- `dockerignore.template`
- `Makefile.python` / `Makefile.node` / `Makefile.wordpress`
- `README.md`

### SaaS Skeleton (`templates/saas-skeleton/`)

- `AGENTS.md` — SaaS-specific agent instructions
- `Dockerfile`, `compose.yaml`, `package.json`, `tailwind.config.ts`
- `app/`, `components/`, `lib/`, `types/` source trees (see SaaS Skeleton section above)

### Source Code

- `@/opt/fabrik/src/fabrik/cli.py` — all 17 top-level commands + 5 groups
- `@/opt/fabrik/src/fabrik/scaffold.py` — `create_project()`, per-type scaffolders, `SCAFFOLD_TYPES`, `SHARED_DIRS`
- `@/opt/fabrik/src/fabrik/spec_generator.py` — `SPEC_ENABLED_TYPES`, `generate_and_save_spec()`
- `@/opt/fabrik/src/fabrik/deploy_validator.py` — `validate-deploy` 5-check module
- `@/opt/fabrik/src/fabrik/orchestrator/` — deploy state machine (canonical doc: `docs/DEPLOYMENT.md`)

### Governance / agent instructions

- `@/opt/fabrik/AGENTS.md` — full agent briefing (Traycer reads)
- `@/opt/fabrik/AGENTS-compact.md` — compact contract (coding agents read; copied into every scaffolded project as `AGENTS.md`)
- `@/opt/fabrik/.windsurfrules` — Cascade contract (copied into every scaffolded project)
- `@/opt/fabrik/.windsurf/rules/` — 22 rule files (copied verbatim into every scaffolded project)
- `@/opt/fabrik/.windsurf/workflows/` — 10 Cascade slash-command workflows (copied verbatim)
- `@/opt/fabrik/opencode.json` — Kilo CLI config (copied verbatim)

### Cross-referenced docs

- `@/opt/fabrik/docs/DEPLOYMENT.md` — **canonical deploy reference** (read this for the deploy half)
- `@/opt/fabrik/docs/reference/fabrik-cli-reference.md` — full CLI flag-by-flag reference
- `@/opt/fabrik/docs/reference/orchestrator.md` — orchestrator module map
- `@/opt/fabrik/docs/reference/templates.md` — deploy-template catalogue (12 deploy templates)
- `@/opt/fabrik/docs/workflows/SCAFFOLD_STRUCTURE.md` — sister doc on file structure (kept narrow; this doc is the broader workflow ref)
- `@/opt/fabrik/docs/workflows/wordpress-site-workflow.md` — WordPress lifecycle

---

## Fabrik CLI Reference

All CLI commands implemented in `@/opt/fabrik/src/fabrik/cli.py`. Counts and signatures verified 2026-04-29.

### Project Creation & Management

| Command | Description |
|---------|-------------|
| `fabrik scaffold <name>` | Create new project tree + `project.yaml` + (for `SPEC_ENABLED_TYPES`) `specs/services/<name>.yaml`. Canonical entry point. |
| ~~`fabrik new <name>`~~ | **DEPRECATED 2026-04-22 (Phase 4k):** hidden, removed-after-next-release. Use `fabrik scaffold`. |
| `fabrik scan` | Scan `/opt/*`, update registry + BUSINESS_MODEL.md (`--health` runs health summary; `--base` overrides scan root) |
| `fabrik projects` | List all tracked projects (`--status`, `--sync`) |
| `fabrik validate <path>` | Validate project file structure against scaffold expectations |
| `fabrik validate-deploy <path>` | 5 deploy-readiness checks (template, .env.example, Dockerfile, /health, spec) |
| `fabrik fix <path>` | Auto-fix missing files (`--type`, `--dry-run`) |
| `fabrik templates` | List available scaffold templates |

### Deployment

| Command | Description |
|---------|-------------|
| `fabrik apply <spec>` | Deploy from a spec (legacy path; `--use-orchestrator` opts into the new pipeline; `--keep-on-failure` for proof-runs) |
| `fabrik deploy [--project <path>]` | Deploy from `project.yaml` (auto-routes WordPress vs. service pipeline) |
| `fabrik plan <spec>` | Preview deployment (dry run, legacy path) |
| `fabrik status <spec>` | Check deployment status (Coolify + DNS + cert) |
| `fabrik app-logs <spec>` | Coolify container logs for the spec's app (`-n`, `--follow`) |
| `fabrik logs <service>` | Loki query by service name (`-n`, `--since 1h\|24h\|7d`) |
| `fabrik redeploy <app>` | Trigger Coolify redeploy by app name or UUID (`--force`) |
| `fabrik destroy <spec>` | Remove deployment (`--keep-dns`, `--keep-files`, `--drop-data`, `--dry-run`) |
| `fabrik verify <domain>` | Verify deployed service end-to-end (`-s`, `-a`, `--no-rollback`) |

### Command Groups

| Group | Subcommands | Purpose |
|-------|-------------|---------|
| `fabrik wp` | `plan`, `apply`, `verify`, `flush` | WordPress site factory (uses `site.yaml`, not `specs/services/*.yaml`) |
| `fabrik ai` | `generate`, `revise`, `usage` | LLM content generation (Claude / OpenAI) with monthly usage tracking |
| `fabrik domain` | `check`, `provision`, `ready`, `integrations`, `sitemap`, `zones`, `buy` | DNS Manager gateway (Namecheap + Cloudflare) |
| `fabrik content` | `publish` | Drain SEO briefs → publish to WordPress |
| `fabrik seo` | `site-register`, ... | SEO service (keyword research, brief management) |

---

## See Also

- [AGENTS.md](../../AGENTS.md) — Mandatory workflow reference (Traycer reads)
- [AGENTS-compact.md](../../AGENTS-compact.md) — Compact agent contract (coding agents read)
- [DEPLOYMENT.md](../DEPLOYMENT.md) — **Canonical deploy reference** (orchestrator, registrars, verifier, rollback)
- [Fabrik CLI Reference](../reference/fabrik-cli-reference.md) — Full CLI flag-by-flag reference
- [Sync Projects Workflow](SYNC_PROJECTS_WORKFLOW.md) — Project tracking & registry
- [SCAFFOLD_STRUCTURE.md](SCAFFOLD_STRUCTURE.md) — Sister doc on the file structure produced by `fabrik scaffold`
- [WordPress Site Workflow](wordpress-site-workflow.md) — End-to-end WordPress lifecycle
- [.env.example](../../.env.example)
