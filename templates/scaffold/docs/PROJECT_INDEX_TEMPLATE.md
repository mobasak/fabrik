# Project File Index — [Project Name]

**Last Updated:** YYYY-MM-DD

> **Purpose:** Single source of truth for all file purposes in this project.
> **For AI Agents:** Read this FIRST before making changes. Every file's purpose is documented here.

---

## Root Files

| File | Purpose | Update When |
|------|---------|-------------|
| **INDEX.md** | This file — master index of all files and their purposes | Add/remove/rename any file |
| **README.md** | Primary entry point — features, architecture, tech stack, quick start | New features, tech changes, setup changes |
| **CHANGELOG.md** | Change history — what changed, why, when (Keep-a-Changelog format) | Every code change |
| **AGENTS.md** | AI agent identity, tech stack, infra context | Read-only (synced from Fabrik) |
| **AGENTS-compact.md** | Compressed agent contract for Kilo CLI | Read-only (synced from Fabrik) |
| **PORTS.md** | Port allocations for this project's services | New services or port changes |
| **project.yaml** | Project metadata — type, status, ports, dependencies, tags | Status changes, new dependencies, port changes |
| **.env.example** | Environment variable template (no secrets) | New env vars added |
| **.env** | Actual secrets — **NEVER COMMIT** | When credentials change |
| **.gitignore** | Git exclusion patterns | New file patterns to ignore |
| **.pre-commit-config.yaml** | Git hooks — commit-time quality checks | Read-only (synced from Fabrik) |
| **.windsurfrules** | Cascade agent contract | Read-only (synced from Fabrik) |
| **opencode.json** | OpenCode/Kilo configuration | Read-only (synced from Fabrik) |

<!-- Add type-specific root files below. Delete rows that don't exist in your project. -->

| File | Purpose | Update When |
|------|---------|-------------|
| **pyproject.toml** | Python project config — ruff, mypy, pytest settings | New tools, linting rules, dependencies |
| **requirements.txt** | Python dependencies | New packages imported |
| **Dockerfile** | Container build instructions | Base image, dependencies, ports change |
| **compose.yaml** | Docker Compose orchestration | Service config, networks, volumes change |
| **compose.dev.yaml** | Dev-only Docker overrides | Dev workflow changes |
| **Makefile** | Build/run shortcuts | New build targets |
| **package.json** | Node.js project config and dependencies | New packages, scripts |

---

## docs/ — Documentation

| File | Purpose | Update When |
|------|---------|-------------|
| **docs/README.md** | Documentation index — table of contents for all docs | New docs added |
| **docs/QUICKSTART.md** | Integration contract — how to use this project, all endpoints, SDK modules, Docker wiring | API changes, new endpoints, setup changes |
| **docs/CONFIGURATION.md** | Complete config reference — all env vars, defaults, examples | New env vars added |
| **docs/TROUBLESHOOTING.md** | Common issues and solutions | New complex dependencies, recurring issues |
| **docs/FEATURES.md** | Detailed feature documentation and endpoint reference | New features, endpoint changes |
| **docs/BUSINESS_MODEL.md** | Go-to-market, monetization, pricing strategy | Strategy or pricing changes |

<!-- These files are created as the project matures. Add rows when they exist. -->
<!-- | **docs/DEPLOYMENT.md** | Coolify/Docker deployment instructions | Infra changes | -->
<!-- | **docs/SERVICES.md** | Microservices architecture | New services added | -->
<!-- | **docs/MIGRATION.md** | Data migration guides | Schema or data changes | -->

---

## docs/ — Subdirectories

| Directory | Purpose | Contents |
|-----------|---------|----------|
| **docs/reference/** | Technical reference docs | API reference, SDK docs, DNS patterns, stack decisions |
| **docs/guides/** | How-to guides | Step-by-step instructions for specific tasks |
| **docs/operations/** | Runbooks | Operational procedures, incident response |
| **docs/development/** | Plans and specs | Development plans, research docs |
| **docs/development/plans/** | Plan documents | `YYYY-MM-DD-plan-<n>.md` files |
| **docs/archive/** | Archived docs | Completed or obsolete documentation |

---

## Source & Infrastructure

| Directory | Purpose |
|-----------|---------|
| **src/** | Source code (main package) |
| **tests/** | Test suite |
| **scripts/** | Automation scripts — `final_gate.py`, `kilo_code_review.py`, enforcement checks |
| **scripts/enforcement/** | Individual quality gate checks |
| **config/** | Configuration files |
| **db/** | Database schema (`schema.sql` is source of truth) |
| **.droid/** | Kilo/Traycer runtime — review context, reports (mostly gitignored) |
| **.windsurf/** | Cascade rules and workflows (synced from Fabrik) |

---

## Temporary / Generated (gitignored)

| Directory | Purpose |
|-----------|---------|
| **logs/** | Log files |
| **data/** | Data files |
| **output/** | Output files |
| **.tmp/** | Temporary files |
| **.cache/** | Cache files |

---

## Project Structure

```text
/opt/[project]/
├── src/                        # Source code
│   └── [package]/              # Main package
├── tests/                      # Test suite
├── scripts/                    # Automation & quality gates
│   └── enforcement/            # Individual gate checks
├── config/                     # Configuration files
├── db/                         # Database schema
│   └── schema.sql              # Schema source of truth
├── docs/                       # Documentation
│   ├── README.md               # Docs index
│   ├── QUICKSTART.md           # Integration contract
│   ├── CONFIGURATION.md        # Config reference
│   ├── TROUBLESHOOTING.md      # Common issues
│   ├── FEATURES.md             # Feature docs
│   ├── BUSINESS_MODEL.md       # GTM strategy
│   ├── reference/              # Technical reference
│   ├── guides/                 # How-to guides
│   ├── operations/             # Runbooks
│   ├── development/            # Plans & specs
│   │   └── plans/              # Plan documents
│   └── archive/                # Archived docs
├── .droid/                     # Agent runtime (gitignored)
│   ├── review-context/         # Kilo review context
│   └── traycer-reports/        # Traycer reports
├── .windsurf/                  # Cascade config (synced)
│   ├── rules/                  # Agent rules
│   └── workflows/              # Agent workflows
├── INDEX.md                    # This file
├── README.md                   # Project entry point
├── CHANGELOG.md                # Change history
├── AGENTS.md                   # Agent identity (synced)
├── AGENTS-compact.md           # Compact agent contract (synced)
├── PORTS.md                    # Port allocations
├── project.yaml                # Project metadata
├── .env.example                # Env var template
└── .gitignore                  # Git exclusions
│   ├── operations/         # Runbooks
│   ├── development/        # Plans and specs
│   │   └── PLANS.md        # Plans index
│   └── archive/            # Archived docs
├── tests/                  # Test suite
├── scripts/                # Automation scripts
├── config/                 # Configuration files
├── data/                   # Data files
├── logs/                   # Log files
├── output/                 # Output files
├── .tmp/                   # Temporary files
└── .cache/                 # Cache files
```

---

## Documentation Structure Map

<!-- AUTO-GENERATED:STRUCTURE:START -->
<!-- Run `python scripts/docs_updater.py --sync` to regenerate this section -->
```text
docs/
├── QUICKSTART.md
├── CONFIGURATION.md
├── TROUBLESHOOTING.md
├── BUSINESS_MODEL.md
├── FEATURES.md
├── README.md
├── archive
├── development
│   └── PLANS.md
├── guides
├── operations
└── reference
```
<!-- AUTO-GENERATED:STRUCTURE:END -->

---

## Enforcement Gates

### Step 3: Pre-Kilo Gate (`python scripts/final_gate.py`)

**ERROR (blocks commit if missing/outdated):**
- CHANGELOG.md
- .env.example
- requirements.txt
- docs/CONFIGURATION.md
- README.md
- INDEX.md (this file)
- semgrep (installed and authenticated)
- vulture (installed)
- docs/ structure (file placement violations)

### Step 5: Post-Kilo Gate (`python scripts/final_gate.py`)

**WARN (doesn't block):**
- pyproject.toml consistency
- Dockerfile best practices
- compose.yaml standards

### Step 7: Sync (`python scripts/final_gate.py --sync`)

**Auto-syncs:**
- Windsurf Extensions (via sync_extensions.sh)
- Cascade Backup (via sync_cascade_backup.sh)

---

## Documentation Navigation

### Quick Start

| Document | Purpose |
|----------|--------|
| [QUICKSTART.md](docs/QUICKSTART.md) | Get [Project Name] running in 5 minutes |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | All environment variables and settings |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and solutions |

### Core Reference

| Document | Purpose |
|----------|--------|
| [INDEX.md](INDEX.md) | Master file index + complete documentation navigation |

### Guides

| Document | Purpose |
|----------|--------|
| Refer to docs/guides/ for project-specific guides |

---

## Update Protocol for AI Agents

**When implementing ANY feature:**

1. **Read this INDEX.md first** - Understand what each file does
2. **Update enforced files** - CHANGELOG, .env.example, requirements.txt, CONFIGURATION, README, INDEX
3. **Step 3 will catch missing updates** - Fix and re-run until PASS
4. **Step 5 will warn on best practices** - Fix warnings
5. **Commit**

**When user provides secrets:**
- Write to `.env` file (NEVER commit)
- Update `.env.example` with placeholder (safe to commit)

---

## File Creation Rules

**Before creating ANY new file:**
1. Check if it already exists
2. Verify it fits the project structure above
3. Update this INDEX.md to document the new file
4. Update README.md if it's a major component

**Never create:**
- Duplicate files
- Files outside the documented structure
- Temporary files in root (use `.tmp/`)
