# Project File Index — [Project Name]

**Last Updated:** YYYY-MM-DD

> **Purpose:** Single source of truth for all file purposes in this project.
> **For AI Agents:** Read this FIRST before making changes. Every file's purpose is documented here.

---

## Root Files

| File | Purpose | Update When |
|------|---------|-------------|
| **INDEX.md** | This file — master index of all files and their purposes | Add/remove/rename any file |
| **README.md** | Primary entry point — overview, tech stack, requirements, link to INDEX.md | Tech changes, setup changes |
| **CHANGELOG.md** | Change history — what changed, why, when (Keep-a-Changelog format) | Every code change |
| **AGENTS.md** | AI agent identity, tech stack, infra context | Read-only (synced from Fabrik) |
| **AGENTS-compact.md** | Compressed agent contract (small-context agents) | Read-only (synced from Fabrik) |
| **PORTS.md** | Port allocations for this project's services | New services or port changes |
| **project.yaml** | Project metadata — type, status, ports, dependencies, tags | Status changes, new dependencies, port changes |
| **.env.example** | Environment variable template (no secrets) | New env vars added |
| **.env** | Actual secrets — **NEVER COMMIT** | When credentials change |
| **.gitignore** | Git exclusion patterns | New file patterns to ignore |
| **.pre-commit-config.yaml** | Git hooks — commit-time quality checks | Read-only (synced from Fabrik) |
| **.windsurfrules** | Legacy Windsurf agent contract (kept for editor compatibility) | Read-only (synced from Fabrik) |
| **opencode.json** | Legacy OpenCode configuration (retired stack; kept while synced) | Read-only (synced from Fabrik) |

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

## docs/ Structure

See [docs/README.md](docs/README.md) for documentation index with purposes.

---

## docs/ — Subdirectories

| Directory | Purpose | Contents |
|-----------|---------|----------|
| **docs/reference/** | Technical reference docs | API reference, SDK docs, DNS patterns, stack decisions |
| **docs/guides/** | How-to guides | Step-by-step instructions for specific tasks |
| **docs/operations/** | Runbooks | Operational procedures, incident response |
| **docs/development/** | Plans and specs | Development plans, research docs |
| **docs/development/plans/** | Plan documents | `YYYY-MM-DD-plan-<n>.md` files or `YYYY-MM-DD-plan-<n>-<slug>/` spine+ticket sets |
| **docs/superpowers/** | Spec/plan pipeline artifacts | `specs/` (design specs) + `plans/` (skill-authored plans) |
| **docs/archive/** | Archived docs | Completed or obsolete documentation |

---

## Source & Infrastructure

| Directory | Purpose |
|-----------|---------|
| **src/** | Source code (main package) |
| **tests/** | Test suite |
| **scripts/** | Automation scripts — `final_gate.py`, `enforcement/` gate checks |
| **scripts/enforcement/** | Individual quality gate checks |
| **config/** | Configuration files |
| **db/** | Database schema (`schema.sql` is source of truth) |
| **.droid/** | Agent runtime artifacts — Traycer reports (mostly gitignored) |
| **.windsurf/** | Rule packs (glob-activated coding rules read by every planning/coding agent via select_rules.py) (synced from Fabrik) |

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
│   │   └── plans/              # Plan documents (files or spine+ticket dirs)
│   ├── superpowers/            # Spec/plan pipeline artifacts (specs/ + plans/)
│   └── archive/                # Archived docs
├── .droid/                     # Agent runtime (gitignored)
│   └── traycer-reports/        # Traycer reports
├── .windsurf/                  # Rule packs (synced, glob-activated)
│   ├── rules/                  # Coding rules read via select_rules.py
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

ONE gate, three tiers — `scripts/final_gate.py` (see the project's CLAUDE.md Completion Contract):

| Invocation | Tier | When |
|---|---|---|
| `python scripts/final_gate.py --json` | **Tier 2 FULL** — mypy + bandit + semgrep + doc-sync + structure + all convention checks | the completion gate for every task |
| `python scripts/final_gate.py --lean --json` | Tier 1 subset | fast self-review DURING iteration only |
| `python scripts/final_gate.py --systemic --json` | Tier 3 repo health (docker/ports/docs-sprawl/deps) | periodic hygiene, never a completion gate |
| add `--check` to any | READ-ONLY (never mutates the tree) | verifying before you claim |

A bare run auto-fixes + auto-stages only the files your change touched. Doc-sync failures
(CHANGELOG / INDEX / CONFIGURATION / .env.example…) are driven by the Doc Sync Matrix — the gate
tells you exactly which doc a change obligates.

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
