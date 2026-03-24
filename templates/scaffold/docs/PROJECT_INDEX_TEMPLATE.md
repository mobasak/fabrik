# Project File Index

**Last Updated:** YYYY-MM-DD

> **Purpose:** Single source of truth for all file purposes in this project.
> **For AI Agents:** Read this FIRST before making changes. Every file's purpose and update trigger is documented here.

---

## Root Files

| File | Purpose | Update When | Enforced |
|------|---------|-------------|----------|
| **INDEX.md** | This file - master index of all files | Add/remove files from project | Step 3 (ERROR) |
| **README.md** | Primary entry point - features, quick start, architecture, tech stack | New features, tech changes, setup changes | Step 3 (ERROR) |
| **CHANGELOG.md** | Change history - what/why/when | Every code change | Step 3 (ERROR) |
| **AGENTS.md** | AI agent briefing | Read-only (copied from Fabrik scaffold) | N/A |
| **.env.example** | Secrets template - structure of required API keys, passwords, config | New secrets/credentials needed | Step 3 (ERROR) |
| **.env** | Actual secrets - NEVER COMMIT | When user provides secrets, AI writes here | N/A |
| **requirements.txt** | Python dependencies | New packages imported | Step 3 (ERROR) |
| **pyproject.toml** | Python project config - ruff, mypy, pytest settings | New tools/linting rules | Step 5 (WARN) |
| **Dockerfile** | Container build instructions | Base image, dependencies, ports change | Step 5 (WARN) |
| **compose.yaml** | Docker Compose orchestration | Service config, networks, volumes change | Step 5 (WARN) |
| **.pre-commit-config.yaml** | Git hooks config | Add new quality checks | Manual |
| **.gitignore** | Git exclusions | New file patterns to ignore | Manual |
| **.windsurfrules** | Windsurf rules shim | Read-only (copied from Fabrik scaffold) | N/A |

---

## docs/ Files

| File | Purpose | Update When | Enforced |
|------|---------|-------------|----------|
| **docs/QUICKSTART.md** | Getting started guide - installation, first run, verification | Setup steps change | Step 5 (WARN) |
| **docs/CONFIGURATION.md** | Complete config reference - all env vars, defaults, examples | New env vars added | Step 3 (ERROR) |
| **docs/TROUBLESHOOTING.md** | Developer troubleshooting - dependency issues, deployment errors | New complex dependencies | Step 5 (WARN) |
| **docs/BUSINESS_MODEL.md** | Go-to-market + monetization strategy | Strategy/pricing changes | Manual |
| **docs/development/PLANS.md** | Implementation plans index | New plans created | Manual |

---

## Project Structure

```
/opt/[project]/
├── src/                    # Source code
│   └── [project]/          # Main package
├── docs/                   # Documentation
│   ├── QUICKSTART.md       # Getting started
│   ├── CONFIGURATION.md    # Config reference
│   ├── TROUBLESHOOTING.md  # Dev troubleshooting
│   ├── guides/             # How-to guides
│   ├── reference/          # Technical reference
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
