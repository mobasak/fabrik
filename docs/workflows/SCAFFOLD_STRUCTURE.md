# Fabrik Scaffold Structure

**Last Updated:** 2026-03-31

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
│   │   ├── 00-critical.md
│   │   ├── 10-python.md
│   │   ├── 20-typescript.md
│   │   ├── 30-ops.md
│   │   ├── 40-documentation.md
│   │   ├── 50-code-review.md
│   │   ├── 60-saas-ui.md
│   │   └── 90-automation.md
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
├── db/
│   └── schema.sql
├── docs/
│   ├── development/
│   │   └── plans/
│   ├── API_REFERENCE.md
│   ├── BUSINESS_MODEL.md
│   ├── CHANGELOG.md
│   ├── CONFIGURATION.md
│   ├── DATABASE_SCHEMA.md
│   ├── DEPLOYMENT.md
│   ├── ENV_EXAMPLE.md
│   ├── FEATURES.md
│   ├── INDEX.md
│   ├── LAUNCH_CHECKLIST.md
│   ├── MIGRATION.md
│   ├── PROJECT_README.md
│   ├── QUICKSTART.md
│   ├── RESEARCH.md
│   ├── SERVICES.md
│   └── TROUBLESHOOTING.md
├── scripts/
│   ├── enforcement/
│   │   ├── __init__.py
│   │   ├── check_android_env.py
│   │   ├── check_changelog.py
│   │   ├── check_docker.py
│   │   ├── check_docs.py
│   │   ├── check_env_contract.py
│   │   ├── check_health.py
│   │   ├── check_ports.py
│   │   ├── check_schema_sync.py
│   │   ├── check_secrets.py
│   │   ├── check_watchdog.py
│   │   ├── core.py
│   │   └── validate_conventions.py
│   ├── Local_Coder_qwen32b.sh
│   ├── Local_Documentator_llama3.1-8b.sh
│   ├── Local_Fixer_ds16b.sh
│   ├── Local_Review_llama70b.sh
│   ├── Kilo_Review.sh
│   ├── final_gate.py
│   ├── kilo_code_review.py
│   ├── kilo_docs_enforcer.py
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
│   └── test_main.py
├── .dockerignore
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .python-version
├── AGENTS-compact.md
├── AGENTS.md
├── CHANGELOG.md
├── compose.dev.yaml
├── compose.yaml
├── Dockerfile
├── INDEX.md
├── Makefile
├── PORTS.md
├── pyproject.toml
└── README.md
```

---

## Template Sources

Templates are stored in `/opt/fabrik/templates/scaffold/`:

```
/opt/fabrik/templates/scaffold/
├── complex.yaml              # Multi-service scaffold configuration
├── db/
│   └── schema.sql            # Base database schema template
├── docker/
│   ├── compose.dev.yaml.template
│   ├── compose.yaml.template
│   ├── Dockerfile.node
│   ├── Dockerfile.python
│   ├── dockerignore.template
│   ├── Makefile.node
│   ├── Makefile.python
│   └── README.md
├── docs/
│   ├── API_REFERENCE_TEMPLATE.md
│   ├── BUSINESS_MODEL_TEMPLATE.md
│   ├── CHANGELOG_TEMPLATE.md
│   ├── CONFIGURATION_TEMPLATE.md
│   ├── DATABASE_SCHEMA_TEMPLATE.md
│   ├── DEPLOYMENT_TEMPLATE.md
│   ├── DOCS_INDEX_TEMPLATE.md
│   ├── ENV_EXAMPLE_TEMPLATE.md
│   ├── FEATURES_TEMPLATE.md
│   ├── LAUNCH_CHECKLIST_TEMPLATE.md
│   ├── MIGRATION_TEMPLATE.md
│   ├── PLAN_TEMPLATE.md
│   ├── PROJECT_INDEX_TEMPLATE.md
│   ├── PROJECT_README_TEMPLATE.md
│   ├── QUICKSTART_TEMPLATE.md
│   ├── RESEARCH_TEMPLATE.md
│   ├── SERVICES_TEMPLATE.md
│   └── TROUBLESHOOTING_TEMPLATE.md
├── python/
│   └── pyproject.toml.template
└── scripts/
    ├── runc
    ├── rund
    ├── rundsh
    ├── runk
    ├── sync_cascade_backup.sh
    └── sync_extensions.sh
```

---

## Key Components Synced from Fabrik

These files/folders are **auto-synced** from `/opt/fabrik/` to all projects:

### 1. Governance Rules (`.windsurf/rules/`)
- **Source:** `/opt/fabrik/.windsurf/rules/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Project-wide coding standards and conventions

### 2. Cascade Workflows (`.windsurf/workflows/`)
- **Source:** `/opt/fabrik/.windsurf/workflows/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Slash command workflows for Windsurf Cascade

### 3. Enforcement Scripts (`scripts/enforcement/`)
- **Source:** `/opt/fabrik/scripts/enforcement/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Quality gate checks (docker, health, env, schema, etc.)

### 4. Cascade Wrappers (`scripts/Local_*.sh`, `scripts/Kilo_Review.sh`)
- **Source:** `/opt/fabrik/scripts/`
- **Synced by:** `sync_enforcement_to_projects.py`
- **Purpose:** Hardware-safe local LLM agent wrappers

### 5. Core Scripts
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
| `node-api` | `templates/node-api/` | Express + TypeScript |
| `wordpress` | `templates/wordpress/` | WordPress + WP-CLI |
| `docusaurus` | `templates/docusaurus/` | Docusaurus docs site |
| `chrome-extension` | `templates/chrome-extension/` | Chrome extension boilerplate |

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
