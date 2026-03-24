# Fabrik Scaffold Specification

**Last Updated:** 2026-03-24

> Complete specification for project creation, templates, deployment, and management in the Fabrik ecosystem.

---

## Table of Contents

1. [Overview](#overview)
2. [Project Types & Decision Matrix](#project-types--decision-matrix)
3. [CLI Commands Reference](#cli-commands-reference)
4. [Project Templates](#project-templates)
5. [Template Complexity Tiers](#template-complexity-tiers)
6. [SaaS Skeleton (Next.js)](#saas-skeleton-nextjs)
7. [Docker Templates](#docker-templates)
8. [Documentation Templates](#documentation-templates)
9. [Factory Configuration](#factory-configuration)
10. [Project Lifecycle](#project-lifecycle)
11. [Conventions & Standards](#conventions--standards)
12. [File Reference Links](#file-reference-links)

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
│  Monitoring: Uptime Kuma                                        │
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
| `chrome-extension` | TypeScript | ❌ No | ❌ No | Chrome Web Store |
| `mobile-app` | TypeScript | ❌ No | ❌ No | App stores |
| `desktop-app` | TypeScript | ❌ No | ❌ No | Direct dist |

### Per-Type Scaffold Details

| Type | Runtime | Container | Key Dirs | Deploy |
|------|---------|-----------|----------|--------|
| `python-api` | Python | ✅ | `src/`, `tests/` | Coolify |
| `node-api` | Node.js | ✅ | `src/` | Coolify |
| `file-api` | Node.js | ✅ | `src/` | Coolify |
| `file-worker` | Python | ✅ | `worker/` | Coolify |
| `saas-skeleton` | TypeScript | ✅ | `app/`, `components/`, `lib/` | Coolify |
| `wordpress` | PHP | ✅ | `plugins/`, `themes/`, `backup/` | Coolify (preset: `saas`/`company`/`content`/`landing`/`ecommerce`) |
| `docusaurus` | TypeScript | ❌ | `docs/` | Static host |
| `chrome-extension` | TypeScript | ❌ | `src/` | Chrome Web Store |
| `mobile-app` | TypeScript | ❌ | `src/` | App stores |
| `desktop-app` | TypeScript | ❌ | `src/` | Direct dist |

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

**`docusaurus`** — Documentation site (no container):
```
docs/   docusaurus.config.js   package.json   sidebars.js
```

**`chrome-extension`** — Browser extension (no container):
```
src/   manifest.json   package.json   tsconfig.json
```

**`mobile-app`** — React Native (Expo) app (no container):
```
src/   app.json   package.json   tsconfig.json
```

**`desktop-app`** — Electron + React (no container):
```
src/   electron/   package.json   tsconfig.json
```

---

## CLI Commands Reference

### Project Creation

```bash
# Create deployment spec from template
fabrik new <name> --template <template> [--domain <domain>] [--output <dir>]

# Create project structure
fabrik scaffold <name> [--type <type>] [--preset <preset>] [--description <text>]

# List available templates
fabrik templates
```

#### `fabrik scaffold` Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | `python-api` | Project type (see Per-Type Scaffold Details table) |
| `--preset` | _(none)_ | Preset variant — only used with `--type wordpress` (`saas`, `company`, `content`, `landing`, `ecommerce`) |
| `--description` / `-d` | `"A new project"` | Short project description |

### `fabrik scaffold` Output (Complete File List)

When you run `fabrik scaffold my-project -d "My description"`, the following structure is created:

#### Actual Project Tree (184 directories, 333 files)

```
/opt/my-project/
├── .droid/
│   ├── .gitignore                   # Blocks Kilo runtime files from git
│   └── review-context/
│       └── .gitkeep                 # Tracked placeholder for Traycer plans
├── .cache/                          # Cache directory (gitignored)
├── .tmp/                            # Temp files (gitignored, NOT /tmp/)
├── .windsurf/
│   └── rules/                       # Windsurf IDE rules (10 files)
│       ├── 00-critical.md           # IDE behavior, forbidden actions
│       ├── 10-python.md             # Python/FastAPI patterns
│       ├── 20-typescript.md         # TypeScript/Next.js patterns
│       ├── 30-ops.md                # Docker/Compose patterns
│       ├── 40-documentation.md      # Documentation rules
│       ├── 50-code-review.md        # Workflow pointer
│       ├── 60-saas-ui.md            # SaaS UI patterns
│       ├── 70-chrome-ext.md         # Chrome extension patterns
│       ├── 80-mobile.md             # Mobile app patterns
│       └── 90-automation.md         # YOLO modes, Fabrik skills
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
│   ├── enforcement/                 # Quality gate checks (27 scripts)
│   │   ├── check_changelog.py       # CHANGELOG.md updated
│   │   ├── check_compose_services.py
│   │   ├── check_configuration_md.py
│   │   ├── check_deps_sync.py
│   │   ├── check_doc_sprawl.py
│   │   ├── check_docker.py
│   │   ├── check_docs.py
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
│   │   ├── check_watchdog.py
│   │   └── validate_conventions.py
│   ├── docs_updater.py              # Documentation drift checker
│   ├── final_gate.py                # Pre-commit quality gate (928 lines)
│   ├── kilo_code_review.py          # AI code review (5528 lines)
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
├── pyproject.toml                   # Python project config
├── README.md                        # Project overview
├── requirements.txt                 # Python dependencies
└── .windsurfrules                   # Copied from /opt/fabrik/windsurfrules
```

#### Files Created (70+)

| File | Source Template | Purpose |
|------|-----------------|---------|
| **Root Files** | | |
| `README.md` | `docs/PROJECT_README_TEMPLATE.md` | Project overview |
| `CHANGELOG.md` | `docs/CHANGELOG_TEMPLATE.md` | Version history |
| `AGENTS.md` | Copied from `/opt/fabrik/AGENTS.md` | AI agent instructions |
| `.windsurfrules` | Copied from `/opt/fabrik/windsurfrules` | Legacy rules shim |
| `.gitignore` | Generated inline | Git ignore patterns |
| `.env.example` | Generated inline | Env var template |
| `requirements.txt` | Generated inline | Python dependencies |
| `Dockerfile` | `docker/Dockerfile.python` | Production Docker build |
| `compose.yaml` | `docker/compose.yaml.template` | Docker Compose config |
| `pyproject.toml` | `python/pyproject.toml.template` | Python project config |
| `.pre-commit-config.yaml` | `pre-commit-config.yaml` | Pre-commit hooks |
| `INDEX.md` | Generated inline | Master file index |
| `PORTS.md` | Generated inline | Port allocation registry |
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
| `scripts/final_gate.py` | Copied from Fabrik | Pre-commit quality checks (928 lines) |
| `scripts/kilo_code_review.py` | Copied from Fabrik | AI code review (5528 lines) |
| `scripts/docs_updater.py` | Copied from Fabrik | Documentation drift checker |
| `scripts/update_agents_toc.py` | Copied from Fabrik | AGENTS.md TOC updater |
| **Enforcement Scripts (27)** | | |
| `scripts/enforcement/*.py` | Copied from Fabrik | Individual quality gate checks |
| **Dev Tooling** | | |
| `Makefile` | `docker/Makefile.python` | Dev shortcuts (`make dev`, `make test`, `make review`) |
| `compose.dev.yaml` | `docker/compose.dev.yaml.template` | Dev overlay with bind-mount hot reload |
| `.dockerignore` | `docker/dockerignore.template` | Excludes `.venv`, `.git`, `__pycache__` from Docker context |
| `.droid/.gitignore` | Generated inline | Blocks Kilo runtime files; tracks `review-context/` |
| `.droid/review-context/.gitkeep` | Generated inline | Ensures `review-context/` is committed |
| `scripts/runc` | `scripts/runc` | Check detached job status |
| `scripts/rund` | `scripts/rund` | Run command in detached mode |
| `scripts/rundsh` | `scripts/rundsh` | Shell into container |
| `scripts/runk` | `scripts/runk` | Kill detached job |
| `scripts/sync_cascade_backup.sh` | `scripts/sync_cascade_backup.sh` | Backup Cascade session |
| `scripts/sync_extensions.sh` | `scripts/sync_extensions.sh` | Sync Windsurf extensions |
| **Windsurf Rules (10)** | | |
| `.windsurf/rules/00-critical.md` | Copied from Fabrik | IDE behavior, forbidden actions |
| `.windsurf/rules/10-python.md` | Copied from Fabrik | Python/FastAPI patterns |
| `.windsurf/rules/20-typescript.md` | Copied from Fabrik | TypeScript/Next.js patterns |
| `.windsurf/rules/30-ops.md` | Copied from Fabrik | Docker/Compose patterns |
| `.windsurf/rules/40-documentation.md` | Copied from Fabrik | Documentation rules |
| `.windsurf/rules/50-code-review.md` | Copied from Fabrik | Workflow pointer |
| `.windsurf/rules/60-saas-ui.md` | Copied from Fabrik | SaaS UI patterns |
| `.windsurf/rules/70-chrome-ext.md` | Copied from Fabrik | Chrome extension patterns |
| `.windsurf/rules/80-mobile.md` | Copied from Fabrik | Mobile app patterns |
| `.windsurf/rules/90-automation.md` | Copied from Fabrik | YOLO modes, Fabrik skills |
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
| `.windsurfrules` | `/opt/fabrik/windsurfrules` | Legacy rules shim |
| `.windsurf/rules/*` | `/opt/fabrik/.windsurf/rules/` | Windsurf IDE rules (10 files) |
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

1. **Git init** - Initializes git repository
2. **Branch creation** - Creates and switches to `mobasak/<project-name>` branch
3. **Pre-commit install** - Copies config and runs `pre-commit install`
4. **Initial commit** - Stages all files and commits "Initial commit"

#### Kilo Workflow Integration

`fabrik scaffold` now provisions the `.droid/` directory required by `kilo_code_review.py` automatically:

| Path | Purpose |
|------|---------|
| `.droid/review-context/` | Where Traycer saves plan artifacts (`task.md`) |
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

## Project Templates

### Available Templates

| Template | Language | Use Case | Files Generated |
|----------|----------|----------|-----------------|
| `python-api` | Python | FastAPI REST APIs | Dockerfile, compose.yaml, src/, tests/ |
| `node-api` | Node.js | Express/Fastify APIs | Dockerfile, compose.yaml, src/, tests/ |
| `file-api` | Python | File handling APIs | API + S3/local storage |
| `file-worker` | Python | Background file processors | Worker + queue consumer |
| `saas-skeleton` | TypeScript | Full SaaS applications | Next.js + Tailwind + Auth |
| `wordpress` | PHP | WordPress sites | WP Docker setup |
| `docusaurus` | TypeScript | Documentation sites | Docusaurus config |
| `chrome-extension` | TypeScript | Browser extensions | Manifest + popup |
| `mobile-app` | TypeScript | React Native apps | Expo setup |
| `desktop-app` | TypeScript | Electron apps | Electron + React |

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
- Base: `python:3.12-slim` (NOT Alpine)
- Non-root user
- Health check
- Entry point customization

**Template:** `@/opt/fabrik/templates/scaffold/docker/Dockerfile.python`

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
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
  "specSaveDir": ".factory/docs",
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
| Python apps | `python:3.12-slim-bookworm` |
| Node.js apps | `node:22-bookworm-slim` |
| General | `debian:bookworm-slim` |

**Never use Alpine** — glibc compatibility, ARM64 support, pre-built wheels.

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

## See Also

- [AGENTS.md](../../AGENTS.md) - Mandatory workflow reference
- [Fabrik CLI Reference](../reference/fabrik-cli-reference.md)
- [.env.example](../../.env.example)
- [Python Production Standards](../../templates/scaffold/PYTHON_PRODUCTION_STANDARDS.md)
