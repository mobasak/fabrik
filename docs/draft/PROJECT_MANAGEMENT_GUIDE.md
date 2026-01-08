# Project Management Guide

**Last Updated:** 2025-12-16

How to start a new project or migrate an existing project to follow the project management structure.

---

## Quick Reference

| Task | Command |
|------|---------|
| **New project** | `create-project.sh my-project "Description"` |
| **Migrate existing** | `migrate-project.sh /opt/my-project` |
| **Preview migration** | `migrate-project.sh /opt/my-project --dry-run` |
| **Validate structure** | `validate-project.sh /opt/my-project` |

Scripts location: `/opt/_project_management/scripts/`

---

## Starting a New Project

### Step 1: Pre-Project Research (BEFORE creating folder)

Complete research before writing any code:

1. Create research document(s) using the template:
   ```
   /opt/_project_management/templates/docs/RESEARCH_TEMPLATE.md
   ```

2. Document:
   - Problem statement
   - Tool/API evaluation with costs
   - Implementation approaches (pros/cons)
   - Selected approach with justification

3. Store research in `/opt/_research/[project-name]/` or keep with project files

### Step 2: Create Project

```bash
/opt/_project_management/scripts/create-project.sh my-project "Brief description of the project"
```

This creates:
- Full folder structure
- All required documentation templates
- `.windsurfrules` symlink
- `.gitignore` and `.env.example`
- Git repository with initial commit

### Step 3: Register Ports

If your project uses any ports, register them in:
```
/opt/_project_management/PORTS.md
```

### Step 4: Customize Templates

Edit the created files to match your project:
- `README.md` - Project overview
- `docs/BUSINESS_MODEL.md` - Monetization strategy
- `docs/DEPLOYMENT.md` - Ports, Docker config, env vars
- `tasks.md` - Development phases and tasks

---

## Migrating an Existing Project

### Step 1: Preview Changes (Safe)

```bash
/opt/_project_management/scripts/migrate-project.sh /opt/your-project --dry-run
```

This shows what will be created without making any changes.

### Step 2: Apply Migration

```bash
/opt/_project_management/scripts/migrate-project.sh /opt/your-project
```

**Safety guarantees:**
- Never overwrites existing files
- Never modifies existing files
- Never deletes anything
- Only creates files/folders that don't exist

### Step 3: Validate

```bash
/opt/_project_management/scripts/validate-project.sh /opt/your-project
```

### Step 4: Customize

Review and update the created template files with your project's actual information.

---

## Project Structure

After running the scripts, your project will have:

```
/opt/your-project/
├── .windsurfrules          # Symlink to rules (auto-created on WSL boot)
├── .gitignore              # Standard ignores
├── .env.example            # Environment template
├── README.md               # Project overview
├── CHANGELOG.md            # Version history
├── tasks.md                # Phase-based task tracking
│
├── docs/
│   ├── README.md           # Documentation index
│   ├── QUICKSTART.md       # Getting started
│   ├── CONFIGURATION.md    # Settings reference
│   ├── TROUBLESHOOTING.md  # Common issues
│   ├── BUSINESS_MODEL.md   # Monetization strategy
│   ├── DEPLOYMENT.md       # Deployment config
│   ├── guides/             # How-to documentation
│   ├── reference/          # Technical specs
│   ├── operations/         # Operational procedures
│   ├── development/        # Contributor docs
│   └── archive/            # Obsolete docs
│
├── config/                 # Configuration files
├── scripts/                # Utility scripts
├── tests/                  # Test files
├── logs/                   # Log files (gitignored)
├── data/                   # Persistent data (gitignored)
├── .tmp/                   # Temporary files (gitignored)
├── .cache/                 # Cache files (gitignored)
└── output/                 # Generated outputs (gitignored)
```

---

## Required Documentation

Every project must have these files:

| File | Purpose |
|------|---------|
| `README.md` | Project overview, quick start |
| `CHANGELOG.md` | Version history |
| `tasks.md` | Development tracking (Phase > Task > Subtask) |
| `docs/README.md` | Documentation index |
| `docs/QUICKSTART.md` | Getting started guide |
| `docs/CONFIGURATION.md` | Environment variables, settings |
| `docs/TROUBLESHOOTING.md` | Common issues and solutions |
| `docs/BUSINESS_MODEL.md` | Monetization strategy |
| `docs/DEPLOYMENT.md` | Ports, Docker, deployment steps |
| `docs/SERVICES.md` | Service documentation (if project has services) |

---

## Critical Rules

### NEVER Use /tmp

**FORBIDDEN:** `/tmp/`, `/var/tmp/`, `tempfile.gettempdir()`

**WHY:** Data in `/tmp` is shared across all projects and gets deleted on WSL restart.

**USE INSTEAD:**
```python
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
TEMP_DIR = PROJECT_ROOT / ".tmp"
TEMP_DIR.mkdir(exist_ok=True)
```

| Directory | Purpose | Safe to Delete |
|-----------|---------|----------------|
| `.tmp/` | Temporary/scratch files | Yes |
| `.cache/` | Cached data | Yes |
| `data/` | Persistent data | No |
| `output/` | Generated outputs | Depends |

### Register Ports

Before using any port, check `/opt/_project_management/PORTS.md` for conflicts and register your port.

### Research Before Code

Complete the research phase before creating a project folder. Use `RESEARCH_TEMPLATE.md`.

---

## Environment Context

- **Development:** WSL (Windows Subsystem for Linux)
- **Production:** VPS via Coolify (Docker Compose)
- **SSH Target:** `vps` (configured in ~/.ssh/config)

Projects should be designed to run in WSL for development and deploy to VPS via Docker Compose.

---

## Available Tools

### Factory.ai Droid (`droid exec`)

For batch research, coding tasks, and automation. See:
```
/opt/_project_management/droid-exec-usage.md
```

**Key rules:**
- Ask permission before using
- Web tools disabled by default
- Use `--auto low` for safe operations
- Separate fact discovery from writing

---

## Docker Templates (Deployment-Ready)

When making a project deployment-ready, copy Docker templates from `/opt/_project_management/templates/docker/`:

| Template | Copy To | Purpose |
|----------|---------|----------|
| `Dockerfile.python` | `Dockerfile` | Multi-stage Python FastAPI build |
| `Dockerfile.node` | `Dockerfile` | Multi-stage Node.js build |
| `compose.yaml.template` | `compose.yaml` | Production-like compose (Coolify) |
| `compose.dev.yaml.template` | `compose.dev.yaml` | Dev overrides (hot reload) |
| `dockerignore.template` | `.dockerignore` | Exclude files from build |
| `Makefile.python` | `Makefile` | Python project commands |
| `Makefile.node` | `Makefile` | Node.js project commands |

### Container-First Principle

- Write code with local tooling (venv/npm) for **speed**
- Keep a working Dockerfile + compose from **day 1**
- Use Docker as the **truth for production parity**

### Standard Makefile Commands

| Command | Purpose |
|---------|----------|
| `make dev` | Local development with hot reload |
| `make test` | Run tests |
| `make docker-smoke` | Build + run + health check (before push) |

---

## Templates Location

All templates are in `/opt/_project_management/templates/docs/`:

| Template | Creates |
|----------|---------|
| `PROJECT_README_TEMPLATE.md` | README.md |
| `CHANGELOG_TEMPLATE.md` | CHANGELOG.md |
| `TASKS_TEMPLATE.md` | tasks.md |
| `DOCS_INDEX_TEMPLATE.md` | docs/README.md |
| `QUICKSTART_TEMPLATE.md` | docs/QUICKSTART.md |
| `CONFIGURATION_TEMPLATE.md` | docs/CONFIGURATION.md |
| `TROUBLESHOOTING_TEMPLATE.md` | docs/TROUBLESHOOTING.md |
| `BUSINESS_MODEL_TEMPLATE.md` | docs/BUSINESS_MODEL.md |
| `DEPLOYMENT_TEMPLATE.md` | docs/DEPLOYMENT.md |
| `SERVICES_TEMPLATE.md` | docs/SERVICES.md |
| `RESEARCH_TEMPLATE.md` | Pre-project research |

---

## Troubleshooting

### Script doesn't create all files

The scripts were fixed on 2025-12-16. If you have old versions, pull the latest from `/opt/_project_management/scripts/`.

### .windsurfrules not appearing

The systemd service `enforce-windsurfrules.service` creates symlinks on WSL boot. Run manually:
```bash
sudo /opt/_project_management/scripts/enforce-windsurfrules.sh
```

### Validation fails

Run `migrate-project.sh` to add missing files, then validate again.

---

## See Also

- `/opt/_project_management/INDEX.md` - Full system index
- `/opt/_project_management/windsurfrules` - Development rules
- `/opt/_project_management/PORTS.md` - Port registry
- `/opt/_project_management/droid-exec-usage.md` - Droid exec guide
