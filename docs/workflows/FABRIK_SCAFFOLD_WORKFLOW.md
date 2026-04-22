# Fabrik Scaffold Specification

**Last Updated:** 2026-04-10
**Script:** `src/fabrik/scaffold.py` (scaffold) + `src/fabrik/cli.py` (CLI)

> Complete specification for project creation, templates, deployment, and management in the Fabrik ecosystem.
>
> **Coders:** When modifying `src/fabrik/scaffold.py` or `src/fabrik/cli.py`, update this workflow doc to match.

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

```
┌─────────────────────────────────────────────────────────────────┐
│                         Fabrik Ecosystem                        │
├─────────────────────────────────────────────────────────────────┤
│  CLI (fabrik)     │  Templates        │  Drivers                │
│  ├── new          │  ├── scaffold/    │  ├── CoolifyClient      │
│  ├── plan         │  ├── saas-skeleton│  ├── DNSClient          │
│  ├── apply        │  ├── python-api/  │  └── Orchestrator       │
│  ├── scaffold     │  ├── node-api/    │                         │
│  ├── validate     │  └── docker/      │                         │
│  └── fix          │                   │                         │
├─────────────────────────────────────────────────────────────────┤
│  Deployment Target: Coolify (VPS Docker Compose)                │
│  DNS: Cloudflare via API                                        │
│  Monitoring: Gatus                                        │
└─────────────────────────────────────────────────────────────────┘
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
# Create deployment spec from template
fabrik new <name> --template <template> [--domain <domain>] [--output <dir>] [--from-project <path>]

# Create project structure
fabrik scaffold <name> [--type <type>] [--preset <preset>] [--description <text>] [--no-spec]

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

### `fabrik scaffold` Output (Complete File List)

When you run `fabrik scaffold my-project -d "My description"`, the following structure is created:

#### Actual Project Tree (184 directories, 333 files)

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
│   │   ├── CROSS_CUTTING_REQUIREMENTS.md  # Cross-cutting requirements
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
│   ├── enforcement/                 # Quality gate checks (30 scripts, entire dir copied)
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
| **Enforcement Scripts (30)** | | |
| `scripts/enforcement/*.py` | Copied from Fabrik | Individual quality gate checks |
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
| `.windsurf/rules/CROSS_CUTTING_REQUIREMENTS.md` | Copied from Fabrik | Cross-cutting requirements (docs, observability, reusability) |
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

```bash
# Preview deployment plan (dry run)
fabrik plan <spec.yaml> [-s KEY=VALUE]

# Execute deployment
fabrik apply <spec.yaml> [-s KEY=VALUE] [--yes] [--skip-dns] [--skip-deploy]

# Check deployment status
fabrik status <spec.yaml>

# View logs
fabrik logs <spec.yaml> [--lines <n>] [--follow]

# Remove deployment
fabrik destroy <spec.yaml> [--yes] [--keep-dns]
```

### Project Management

```bash
# List all projects
fabrik projects [--status <status>] [--sync]

# Scan for projects
fabrik scan [--base /opt]

# Validate project structure
fabrik validate <project_path> [--type <type>]

# Auto-fix missing files
fabrik fix <project_path> [--type <type>] [--dry-run]

# Verify deployed service
fabrik verify <domain> [--spec <type>] [--app-name <name>]
```

### Maintenance

```bash
# Sync model names across configs
fabrik sync-models
```

---

## Scaffold-to-Deploy Integration (P2/P3/P4)

### Auto-Spec Generation (P2 - Implemented 2026-04-10)

**Purpose:** Automatically generate deployment spec files when scaffolding projects, eliminating manual spec creation.

**Enabled Types (SPEC_ENABLED_TYPES):**
- `python-api`
- `saas-skeleton`
- `node-api`
- `file-api`
- `file-worker`
- `chrome-extension`
- `static-site`

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

### CLI Enhancements (P3 - Implemented 2026-04-10)

**`fabrik new --from-project` flag:**
Extracts env vars, secrets, and dependencies from an existing scaffolded project:

```bash
fabrik new my-api --template python-api --domain api.vps1.ocoron.com \
  --from-project /opt/existing-api --output specs/services
```

**What it extracts:**
- Environment variables from `compose.yaml` (non-secrets)
- Secret keys from `.env.example` (patterns: PASSWORD, SECRET, KEY, TOKEN, etc.)
- Dependencies: PostgreSQL (if `DATABASE_URL` detected), Redis (if `REDIS_URL` detected)
- Project type from `project.yaml` (for correct kind mapping)

**`fabrik new --output` default:**
Changed from `specs` to `specs/services` (correct location for service specs).

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

| Template | Language | Use Case | Files Generated |
|----------|----------|----------|-----------------|
| `python-api` | Python | FastAPI REST APIs | Dockerfile, compose.yaml, src/, tests/ |
| `node-api` | Node.js | Express/Fastify APIs | Dockerfile, compose.yaml, src/, tests/ |
| `file-api` | Node.js | File handling APIs | API + S3/local storage |
| `file-worker` | Python | Background file processors | Worker + queue consumer |
| `saas-skeleton` | TypeScript | Full SaaS applications | Next.js + Tailwind + Auth |
| `wordpress` | PHP | WordPress sites | WP Docker setup |
| `docusaurus` | TypeScript | Documentation sites | Docusaurus config |
| `chrome-extension` | TypeScript | Browser extensions + Python backend | Extension (Vite + CRXJS) + FastAPI server |
| `mobile-app` | TypeScript | React Native apps | React Native setup |
| `desktop-app` | TypeScript | Electron apps | Electron + React |
| `static-site` | TypeScript | Static websites | Next.js + Tailwind |

### Template Locations

```
/opt/fabrik/templates/
├── scaffold/           # Base project structure + docs
├── saas-skeleton/      # Full Next.js SaaS starter
├── python-api/         # Python FastAPI template
├── node-api/           # Node.js API template
├── file-api/           # File handling API
├── file-worker/        # Background worker
├── wordpress/          # WordPress setup
├── docusaurus/         # Documentation site
├── chrome-extension/   # Browser extension
├── mobile-app/         # React Native
├── desktop-app/        # Electron
├── spec-pipeline/      # Traycer Stage 0 discovery pipeline
└── traycer/            # Traycer integration
```

---

## Template Complexity Tiers

### Simple (2-8 hours)

**Use for:** Quick utilities, single-file scripts, learning projects, POCs

**Structure:**
```
project/
├── README.md
├── main.py
├── .gitignore
└── CLAUDE.md (agent instructions)
```

**Features:**
- Version control: ✅
- Testing: ❌
- CI/CD: ❌
- Documentation: Minimal
- Dependencies: Minimal

**Template:** `@/opt/fabrik/templates/scaffold/simple.yaml`

---

### Medium (20-80 hours)

**Use for:** REST APIs, CLI tools, data pipelines, internal tools, MVPs

**Structure:**
```
project/
├── src/
│   ├── __init__.py
│   └── main.py
├── tests/
│   └── test_main.py
├── docs/
│   └── ARCHITECTURE.md
├── config/
│   └── config.yaml
├── README.md
├── requirements.txt
├── .gitignore
└── CLAUDE.md
```

**Features:**
- Version control: ✅
- Testing: ✅
- CI/CD: Optional
- Documentation: Standard
- Dependencies: Managed

**Template:** `@/opt/fabrik/templates/scaffold/medium.yaml`

---

### Complex (100-500+ hours)

**Use for:** Production systems, microservices, enterprise apps, SaaS, high-traffic APIs

**Structure:**
```
project/
├── src/
│   ├── api/
│   │   └── main.py
│   ├── core/
│   ├── models/
│   ├── services/
│   └── utils/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── API.md
│   └── DEPLOYMENT.md
├── config/
│   ├── config.yaml
│   └── logging.yaml
├── scripts/
│   └── setup.sh
├── infra/
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── requirements-dev.txt
├── SECURITY.md
├── README.md
└── CLAUDE.md
```

**Features:**
- Version control: ✅
- Testing: Comprehensive (unit + integration + e2e)
- CI/CD: Required
- Documentation: Extensive
- Dependencies: Strict
- Monitoring: Required
- Security: Hardened

**Template:** `@/opt/fabrik/templates/scaffold/complex.yaml`

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

Available in `@/opt/fabrik/templates/scaffold/docs/`:

| Template | Purpose |
|----------|---------|
| `PROJECT_README_TEMPLATE.md` | Project root README |
| `QUICKSTART_TEMPLATE.md` | 5-minute getting started |
| `CONFIGURATION_TEMPLATE.md` | Settings and options |
| `DEPLOYMENT_TEMPLATE.md` | Production deployment guide |
| `TROUBLESHOOTING_TEMPLATE.md` | Common issues and fixes |
| `LAUNCH_CHECKLIST_TEMPLATE.md` | Pre-launch verification |
| `CHANGELOG_TEMPLATE.md` | Version history |
| `SERVICES_TEMPLATE.md` | Service documentation |
| `BUSINESS_MODEL_TEMPLATE.md` | Business context |
| `RESEARCH_TEMPLATE.md` | Research/exploration docs |
| `PHASE_TEMPLATE.md` | Development phase docs |
| `implementation-plan-template.md` | Implementation planning |
| `DOCS_INDEX_TEMPLATE.md` | Documentation index |
| `TASKS_TEMPLATE.md` | Task tracking |
| `PROJECT_INDEX_TEMPLATE.md` | Project file index with auto-generated structure map |

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

### Settings JSON

**Template:** `@/opt/fabrik/templates/scaffold/factory-settings.json`

```json
{
  "model": "gpt-5.1-codex-max",
  "reasoningEffort": "high",
  "autonomyLevel": "auto-high",
  "diffMode": "github",
  "specSaveEnabled": true,
  "specSaveDir": ".droid/docs",
  "enableHooks": true,
  "commandAllowlist": ["git push", "pip install", "docker compose", ...],
  "commandDenylist": ["rm -rf /", "dd of=/dev", ...]
}
```

### Pre-commit Config

**Template:** `@/opt/fabrik/templates/scaffold/pre-commit-config.yaml`

Includes:
- ruff (linting + formatting)
- mypy (type checking)
- bandit (security)
- Standard hooks (trailing whitespace, YAML, JSON)

---

## Project Lifecycle

### 1. Create

```bash
# Option A: Create spec + deploy files
fabrik new my-api --template python-api --domain api.example.com

# Option B: Create project structure only
fabrik scaffold my-tool -d "CLI utility"
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

### Core Templates
- `@/opt/fabrik/templates/scaffold/simple.yaml` - Simple project template
- `@/opt/fabrik/templates/scaffold/medium.yaml` - Medium project template
- `@/opt/fabrik/templates/scaffold/complex.yaml` - Complex project template
- `@/opt/fabrik/templates/scaffold/AGENTS.md` - Agent instructions template

### Docker Templates
- `@/opt/fabrik/templates/scaffold/docker/Dockerfile.python` - Python Dockerfile
- `@/opt/fabrik/templates/scaffold/docker/Dockerfile.node` - Node.js Dockerfile
- `@/opt/fabrik/templates/scaffold/docker/compose.yaml.template` - Compose template
- `@/opt/fabrik/templates/scaffold/docker/dockerignore.template` - Dockerignore

### SaaS Template
- `@/opt/fabrik/templates/saas-skeleton/README.md` - SaaS skeleton docs
- `@/opt/fabrik/templates/saas-skeleton/AGENTS.md` - SaaS agent instructions
- `@/opt/fabrik/templates/saas-skeleton/package.json` - Dependencies
- `@/opt/fabrik/templates/saas-skeleton/Dockerfile` - Production build

### Documentation Templates
- `@/opt/fabrik/templates/scaffold/docs/PROJECT_README_TEMPLATE.md`
- `@/opt/fabrik/templates/scaffold/docs/QUICKSTART_TEMPLATE.md`
- `@/opt/fabrik/templates/scaffold/docs/DEPLOYMENT_TEMPLATE.md`
- `@/opt/fabrik/templates/scaffold/docs/CONFIGURATION_TEMPLATE.md`
- `@/opt/fabrik/templates/scaffold/docs/TROUBLESHOOTING_TEMPLATE.md`
- `@/opt/fabrik/templates/scaffold/docs/LAUNCH_CHECKLIST_TEMPLATE.md`

### Configuration
- `@/opt/fabrik/templates/scaffold/factory-settings.json` - Factory settings
- `@/opt/fabrik/templates/scaffold/factory-hooks.json` - Factory hooks
- `@/opt/fabrik/templates/scaffold/factory-mcp.json` - MCP config
- `@/opt/fabrik/templates/scaffold/pre-commit-config.yaml` - Pre-commit

### Standards
- `@/opt/fabrik/templates/scaffold/PYTHON_PRODUCTION_STANDARDS.md` - Python standards (927 lines)

### CLI Source
- `@/opt/fabrik/src/fabrik/cli.py` - CLI implementation

### Guides
- `@/opt/fabrik/AGENTS.md` - Agent briefing and mandatory workflow
- `@/opt/fabrik/docs/reference/fabrik-cli-reference.md` - CLI reference
- `@/opt/fabrik/AGENTS.md` - Main agent briefing

---

## Fabrik CLI Reference

All CLI commands implemented in `src/fabrik/cli.py`:

### Project Creation & Management

| Command | Description |
|---------|-------------|
| `fabrik scaffold <name>` | Create new project with full structure + `project.yaml` |
| `fabrik new <name>` | Create deployment spec from template |
| `fabrik scan` | Scan `/opt/*`, update registry + BUSINESS_MODEL.md |
| `fabrik projects` | List all tracked projects |
| `fabrik validate <path>` | Validate project structure |
| `fabrik fix <path>` | Auto-fix missing files |

### Deployment

| Command | Description |
|---------|-------------|
| `fabrik apply <spec>` | Deploy to Coolify |
| `fabrik plan <spec>` | Preview deployment (dry run) |
| `fabrik status <spec>` | Check deployment status |
| `fabrik logs <spec>` | View deployment logs |
| `fabrik destroy <spec>` | Remove deployment |
| `fabrik verify <domain>` | Verify deployed service |

### Utilities

| Command | Description |
|---------|-------------|
| `fabrik templates` | List available templates |
| `fabrik sync-models` | Sync model names across configs |

---

## See Also

- [AGENTS.md](../../AGENTS.md) - Mandatory workflow reference
- [Sync Projects Workflow](SYNC_PROJECTS_WORKFLOW.md) - Project tracking & registry
- [Fabrik CLI Reference](../reference/fabrik-cli-reference.md)
- [.env.example](../../.env.example)
- [Python Production Standards](../../templates/scaffold/PYTHON_PRODUCTION_STANDARDS.md)
