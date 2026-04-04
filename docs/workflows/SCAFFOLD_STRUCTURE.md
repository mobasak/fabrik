# Fabrik Scaffold Structure

**Last Updated:** 2026-04-03

> Complete reference for the folder and file structure created by `fabrik scaffold`.

---

## Overview

When you run `fabrik scaffold <project-name> --type python-api`, the following structure is created in `/opt/<project-name>/`:

---

## Complete Scaffold Tree

```
/opt/<project-name>/
├── .windsurf/
│   ├── rules/
│   │   ├── 10-python.md
│   │   ├── 15-api-contracts.md
│   │   ├── 20-typescript.md
│   │   ├── 25-data-postgres.md
│   │   ├── 30-ops.md
│   │   ├── 35-security-auth.md
│   │   ├── 40-documentation.md
│   │   ├── 42-docusaurus.md
│   │   ├── 45-testing-strategy.md
│   │   ├── 50-code-review.md
│   │   ├── 55-observability.md
│   │   ├── 60-saas-ui.md
│   │   ├── 62-wordpress.md
│   │   ├── 65-rag-search.md
│   │   ├── 70-chrome-ext.md
│   │   ├── 75-workers-jobs.md
│   │   ├── 80-mobile.md
│   │   ├── 85-payments-billing.md
│   │   ├── 90-automation.md
│   │   ├── 95-multi-tenant-saas.md
│   │   ├── CROSS_CUTTING_REQUIREMENTS.md
│   │   └── ocoron-design-system.md
│   └── workflows/
│       ├── bug-fix.md
│       ├── deploy.md
│       ├── kilo.md
│       ├── kilo-review.md
│       ├── local-coder.md
│       ├── local-docs.md
│       ├── local-fixer.md
│       ├── local-review.md
│       ├── new-feature.md
│       └── review.md
├── .droid/
│   ├── .gitignore
│   ├── review-context/
│   │   └── .gitkeep
│   └── traycer-reports/
│       └── .gitignore
├── db/
│   └── schema.sql
├── docs/
│   ├── archive/
│   │   └── README.md
│   ├── development/
│   │   ├── plans/
│   │   └── PLANS.md
│   ├── reference/
│   │   └── windsurf/
│   │       └── cascade-models.md
│   ├── BUSINESS_MODEL.md
│   ├── CONFIGURATION.md
│   ├── FEATURES.md
│   ├── QUICKSTART.md
│   ├── README.md
│   └── TROUBLESHOOTING.md
├── scripts/
│   ├── enforcement/              # Entire dir copied from Fabrik (~30 scripts)
│   ├── docs_updater.py
│   ├── final_gate.py
│   ├── health_checker.py
│   ├── kilo_code_review.py
│   ├── kilo_docs_enforcer.py
│   ├── update_agents_toc.py
│   ├── runc
│   ├── rund
│   ├── rundsh
│   ├── runk
│   ├── sync_cascade_backup.sh
│   └── sync_extensions.sh
├── src/
│   └── <project_name>/
│       ├── __init__.py
│       └── main.py
├── tests/
│   ├── __init__.py
│   └── test_health.py
├── .dockerignore
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── AGENTS-compact.md
├── AGENTS.md
├── CHANGELOG.md
├── compose.dev.yaml
├── compose.yaml
├── Dockerfile
├── INDEX.md
├── Makefile
├── opencode.json
├── PORTS.md
├── project.yaml
├── pyproject.toml
├── requirements.txt
├── .windsurfrules
└── README.md
```

---

## Document Generation

### From Templates (`templates/scaffold/docs/`)

| Template | Generated File | Purpose |
|----------|----------------|---------|
| `PROJECT_INDEX_TEMPLATE.md` | `INDEX.md` | Master file index |
| `PROJECT_README_TEMPLATE.md` | `README.md` | Project overview |
| `CHANGELOG_TEMPLATE.md` | `CHANGELOG.md` | Change history |
| `DOCS_INDEX_TEMPLATE.md` | `docs/README.md` | Documentation index |
| `QUICKSTART_TEMPLATE.md` | `docs/QUICKSTART.md` | Quick start guide |
| `CONFIGURATION_TEMPLATE.md` | `docs/CONFIGURATION.md` | Configuration guide |
| `TROUBLESHOOTING_TEMPLATE.md` | `docs/TROUBLESHOOTING.md` | Troubleshooting guide |
| `BUSINESS_MODEL_TEMPLATE.md` | `docs/BUSINESS_MODEL.md` | Business model doc |
| `FEATURES_TEMPLATE.md` | `docs/FEATURES.md` | Features overview |

### Inline Generated (No Templates)

| File | Purpose |
|------|---------|
| `PORTS.md` | Port allocation tracking |
| `docs/development/PLANS.md` | Development plans index |
| `docs/archive/README.md` | Archive directory index |

### Copied from Fabrik

| Source | Destination | Purpose |
|--------|-------------|---------|
| `/opt/fabrik/AGENTS.md` | `AGENTS.md` | Traycer orchestrator contract |
| `/opt/fabrik/AGENTS-compact.md` | `AGENTS-compact.md` | Compact agent reference |
| `/opt/fabrik/.windsurfrules` | `.windsurfrules` | Cascade compact agent contract |
| `/opt/fabrik/.windsurf/rules/` | `.windsurf/rules/` | Windsurf IDE rules (22 files) |
| `/opt/fabrik/.windsurf/workflows/` | `.windsurf/workflows/` | Cascade slash-command workflows |
| `/opt/fabrik/opencode.json` | `opencode.json` | Kilo CLI configuration |
| `/opt/fabrik/docs/reference/windsurf/cascade-models.md` | `docs/reference/windsurf/cascade-models.md` | Cascade model reference |

### Type-Specific Documents

| Type | File | Purpose |
|------|------|---------|
| `chrome-extension` | `extension/icons/README.md` | Icon generation guide |

---

## Key Components Synced from Fabrik

These files/folders are **auto-synced** from `/opt/fabrik/` to all projects:

### 1. Cascade Compact Contract (`.windsurfrules`)
- **Source:** `/opt/fabrik/.windsurfrules`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Always-loaded Cascade agent contract (~154 lines) — orientation, behavior rules, essential invariants, decision-grade audit

### 2. Governance Rules (`.windsurf/rules/`)
- **Source:** `/opt/fabrik/.windsurf/rules/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Project-wide coding standards and conventions (22 rule files)

### 3. Cascade Workflows (`.windsurf/workflows/`)
- **Source:** `/opt/fabrik/.windsurf/workflows/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Slash command workflows for Windsurf Cascade

### 4. Enforcement Scripts (`scripts/enforcement/`)
- **Source:** `/opt/fabrik/scripts/enforcement/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Quality gate checks (docker, health, env, schema, etc.)

### 5. Cascade Wrappers (`scripts/Local_*.sh`, `scripts/Kilo_Review.sh`)
- **Source:** `/opt/fabrik/scripts/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Hardware-safe local LLM agent wrappers

### 6. Core Scripts
- `final_gate.py` - Pre-commit quality gate
- `kilo_code_review.py` - AI-powered code review
- `kilo_docs_enforcer.py` - Documentation enforcer

---

## Variable Substitution

Templates use Jinja2 syntax for variable substitution:

| Variable | Example Value | Used In |
|----------|---------------|---------|
| `{{ project_name }}` | `my-api` | All templates |
| `{{ python_version }}` | `3.12` | Dockerfile, pyproject.toml |
| `{{ port }}` | `8000` | Dockerfile, compose.yaml |
| `{{ description }}` | `API description` | README, pyproject.toml |

---

## Scaffold Types

Different scaffold types create variations:

| Type | Base Template | Additional Files |
|------|---------------|------------------|
| `python-api` | `templates/scaffold/` | FastAPI + Uvicorn setup |
| `saas-skeleton` | `templates/saas-skeleton/` | Next.js 14 + TypeScript + Tailwind |
| `static-site` | `templates/saas-skeleton/` | Same as saas-skeleton (landing pages) |
| `node-api` | `templates/node-api/` | Express + JavaScript |
| `file-api` | `templates/file-api/` | File operations API (Node.js) |
| `file-worker` | `templates/file-worker/` | Python background worker |
| `wordpress` | `templates/wordpress/` | WordPress + WP-CLI |
| `docusaurus` | `templates/docusaurus/` | Docusaurus docs site |
| `chrome-extension` | `templates/chrome-extension/` | Chrome extension (Vite + CRXJS) + Python backend |
| `mobile-app` | `templates/mobile-app/` | React Native + TypeScript |
| `desktop-app` | `templates/desktop-app/` | Electron + TypeScript |

---

## Post-Scaffold Initialization

After scaffold creation, run:

```bash
# Initialize git repository
cd /opt/<project-name>
git init
git add -A
git commit -m "chore: initial scaffold"

# Set up Python virtual environment (for Python projects)
uv venv
source .venv/bin/activate  # or: . .venv/bin/activate
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Verify setup
python scripts/final_gate.py --lean
```

---

## Sync Mechanism

Projects stay synchronized with Fabrik master via:

1. **Pre-commit hook:** Runs `sync_enforcement_to_projects.py` before each commit in Fabrik
2. **Manual sync:** Run `python /opt/fabrik/scripts/sync_enforcement_to_projects.py` anytime
3. **Scaffold refresh:** Re-scaffolding updates templates (preserves project-specific code)

---

## See Also

- [FABRIK_SCAFFOLD_WORKFLOW.md](FABRIK_SCAFFOLD_WORKFLOW.md) - Detailed scaffold workflow
- [SYNC_ENFORCEMENT_WORKFLOW.md](SYNC_ENFORCEMENT_WORKFLOW.md) - How syncing works
- [FINAL_GATE_WORKFLOW.md](FINAL_GATE_WORKFLOW.md) - Quality gates
- `templates/README.md` - Template development guide
