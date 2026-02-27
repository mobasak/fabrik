# Project File Index

**Last Updated:** 2026-02-25

> **Purpose:** Single source of truth for all file purposes in this project.
> **For AI Agents:** Read this FIRST before making changes. Every file's purpose and update trigger is documented here.

---

## Root Files

| File | Purpose | Update When | Enforced |
|------|---------|-------------|----------|
| **INDEX.md** | This file - master index of all files | Add/remove files from project | Step 3 (ERROR) |
| **README.md** | Primary entry point - features, quick start, architecture, tech stack | New features, tech changes, setup changes | Step 3 (ERROR) |
| **CHANGELOG.md** | Change history - what/why/when | Every code change | Step 3 (ERROR) |
| **AGENTS.md** | AI agent briefing (symlink to /opt/fabrik/AGENTS.md) | Never edit (managed by Fabrik) | N/A |
| **.env.example** | Self-documenting secrets template - AUTHORITATIVE variable reference with inline comments explaining each var | New secrets/credentials needed | Step 3 (ERROR) |
| **.env** | Actual secrets - NEVER COMMIT | When user provides secrets, AI writes here | N/A |
| **requirements.txt** | Python dependencies | New packages imported | Step 3 (ERROR) |
| **pyproject.toml** | Python project config - ruff, mypy, pytest settings | New tools/linting rules | Step 5 (WARN) |
| **Dockerfile** | Container build instructions | Base image, dependencies, ports change | Step 5 (WARN) |
| **compose.yaml** | Docker Compose orchestration | Service config, networks, volumes change | Step 5 (WARN) |
| **.pre-commit-config.yaml** | Git hooks config | Add new quality checks | Manual |
| **.gitignore** | Git exclusions | New file patterns to ignore | Manual |
| **.windsurfrules** | Windsurf rules (symlink to /opt/fabrik/windsurfrules) | Never edit (managed by Fabrik) | N/A |

---

## docs/ Files

| File | Purpose | Update When | Enforced |
|------|---------|-------------|----------|
| **docs/README.md** | Documentation index - auto-generated structure tree | Auto-updated by docs_updater.py | Step 7 (auto) |
| **docs/QUICKSTART.md** | Getting started guide - installation, first run, verification | Setup steps change | Step 5 (WARN) |
| **docs/CONFIGURATION.md** | Configuration GUIDE - how to get credentials, architecture context, troubleshooting (NOT variable tables - see .env.example) | New services, config patterns, troubleshooting cases | Step 5 (WARN) |
| **docs/TROUBLESHOOTING.md** | Developer troubleshooting - dependency issues, deployment errors | New complex dependencies | Step 5 (WARN) |
| **docs/BUSINESS_MODEL.md** | Go-to-market + monetization strategy + AUTO-GENERATED project catalog | Manual updates for strategy; AUTO-GENERATED:PROJECTS block syncs via `python scripts/sync_projects.py` or `fabrik scaffold` completion | Step 7 (auto-sync catalog only) |

---

## Project Structure

```
/opt/fabrik/
├── src/                    # Source code
│   └── fabrik/   # Main package
├── docs/                   # Documentation
│   ├── README.md           # Auto-generated docs index
│   ├── QUICKSTART.md       # Getting started
│   ├── CONFIGURATION.md    # Configuration guide
│   ├── TROUBLESHOOTING.md  # Dev troubleshooting
│   ├── guides/             # How-to guides
│   ├── reference/          # Technical reference
│   ├── operations/         # Runbooks
│   ├── development/        # Plans and specs
│   └── archive/            # Archived docs
├── tests/                  # Test suite
├── scripts/                # Automation scripts
├── config/                 # Configuration files
├── data/                   # Data files
├── logs/                   # Log files
├── .tmp/                   # Temporary files
└── .cache/                 # Cache files
```

---

## Enforcement Gates

### Steps 3 & 5: Quality Gates (`python scripts/final_gate.py`)

Both Pre-Kilo (Step 3) and Post-Kilo (Step 5) run identical checks:

**PHASE 1: AUTO-FIX FORMATTING** (Fix mode only)
- trim trailing whitespace
- fix end of files (newline)
- ruff-format
- ruff --fix

**PHASE 2: STATIC ANALYSIS** (All ERROR - blocks commit)
- ruff (Python linter)
- mypy (type checking)
- bandit (security scanner)
- **semgrep (REQUIRED - security patterns)**
- check yaml (syntax validation)
- check json (syntax validation)
- sqlfluff-lint (SQL linting, skips if no .sql files)
- **vulture (REQUIRED - dead code detection)**

**PHASE 3: REPO CONSISTENCY** (All ERROR - blocks commit)
- Project Structure
- Fabrik Convention Validator
- Rule File Size Guard
- Sync Droid Model Names
- INDEX.md (Master File Index)
- README.md (Primary Entry Point)
  - CONFIGURATION.md (Configuration Guide - credentials, architecture context, troubleshooting)
- .env Updates (WARN - secrets population)
- CHANGELOG.md Updated
- Kilo CLI Health Check
- Symlink Integrity
- Documentation Drift
- AGENTS.md TOC Current

### Step 7: Sync Only (`python scripts/final_gate.py --sync`)

**No quality checks - sync side-effects only:**
- Sync Windsurf Extensions → docs/reference/EXTENSIONS.md
- Sync Cascade Backup (freshness check)

---

## Repository Structure

```text
/opt/fabrik/                         # Fabrik monorepo root
├── README.md                        # Project overview
├── CHANGELOG.md                     # Version history
├── INDEX.md                         # THIS FILE - Master file index + docs navigation
├── AGENTS.md                        # AI agent briefing (symlinked into projects)
├── Makefile                         # Common dev/ops targets
├── compose.yaml                     # Root Docker Compose (postgres-main + services)
├── pyproject.toml                   # Python package config (ruff, mypy, pytest)
├── Dockerfile                       # Root image build
├── .env.example                     # Master env var template
├── PORTS.md                         # Port registry for all services
├── tasks.md                         # Active task tracker
├── factory_submit.py                # Traycer async job submission
├── factory_wait.py                  # Traycer async job wait/poll
├── apps/                            # Deployable application containers
│   ├── example-api/                 # Example FastAPI service (Dockerfile, compose.yaml)
│   └── postgres-main/               # Shared PostgreSQL instance (compose.yaml)
├── config/                          # Runtime configuration files
│   ├── models.yaml                  # AI model registry (auto-updated daily)
│   └── platform.yaml.example        # Platform config template
├── infrastructure/                  # VPS-level system files
│   ├── coolify-ssh-permissions.sh
│   ├── coolify-ssh-permissions.service
│   └── coolify-ssh-permissions.timer
├── scripts/                         # Automation and tooling scripts
│   ├── final_gate.py                # Mandatory pre-commit quality gate
│   ├── docs_updater.py              # Auto-update docs structure
│   ├── kilo_code_review.py          # Kilo-based code review runner
│   ├── droid_models.py              # AI model registry CLI
│   ├── enforcement/                 # Convention check scripts (check_*.py)
│   ├── droid/                       # Batch refactoring scripts
│   └── utils/                       # Shared script utilities
├── specs/                           # YAML specs and planning documents
├── sql/                             # Database DDL scripts
├── src/fabrik/                      # Core Fabrik Python package
│   ├── cli.py                       # CLI entry point
│   ├── scaffold.py                  # Project scaffolding
│   ├── api/                         # API layer
│   ├── drivers/                     # External service drivers
│   ├── models/                      # Data models
│   ├── orchestrator/                # Deployment orchestrator
│   └── wordpress/                   # WordPress automation
├── templates/                       # Project and document templates
│   ├── saas-skeleton/               # Next.js 14 + Tailwind SaaS starter
│   ├── scaffold/                    # Fabrik scaffold config
│   └── docs/                        # Document templates
├── tests/                           # Test suite
├── .factory/                        # Factory AI workspace config
│   ├── hooks/                       # Lifecycle hooks
│   └── skills/                      # Auto-invoked skills
├── .github/                         # GitHub Actions CI/CD
│   └── workflows/                   # ci.yml, droid-review.yml, etc.
└── .windsurf/                       # Windsurf IDE config
    ├── hooks.json
    ├── rules/                       # 00-critical, 10-python, etc.
    └── workflows/                   # code-review, bug-fix, deploy, etc.
```

---

## Documentation Structure Map

<!-- AUTO-GENERATED:STRUCTURE:START -->
<!-- AUTO-GENERATED:STRUCTURE v1 | 2026-02-25T22:21 -->
```text
docs/
├── BUSINESS_MODEL.md               # Monetization strategy
├── CONFIGURATION.md                # Configuration guide - credentials, architecture, troubleshooting
├── DEPLOYMENT.md                   # How to deploy services to VPS
├── FAQ.md                          # Frequently asked questions
├── INDEX.md                        # Main documentation entry point
├── QUICKSTART.md                   # Get Fabrik running in 5 minutes
├── SERVICES.md                     # External services Fabrik depends on
├── TESTING.md                      # How to run and write tests
├── TROUBLESHOOTING.md              # Common issues & solutions
├── archive                         # Archived and completed documentation
│   ├── 2025-01-03-droid-validation
│   │   └── droid-validation-report.md
│   ├── 2026-02-26-doc-consolidation
│   │   ├── ENVIRONMENT_VARIABLES.md
│   │   ├── FABRIK_OVERVIEW.md
│   │   └── ROADMAP_ACTIVE.md
│   ├── 2025-12-27_FUTURE_WORK.md
│   ├── 2025-12-27_WHATS_NEXT.md
│   ├── 2025-12-27_future-development.md
│   ├── 2026-01-04-analysis-reports
│   │   ├── ARCHITECTURE_ANALYSIS.md
│   │   └── DOCUMENTATION_AUDIT.md
│   ├── 2026-01-04-monitoring-design
│   │   ├── DROID_RUNNER_MONITORING.md
│   │   └── LONG_COMMAND_MONITORING.md
│   ├── 2026-01-05-design-docs
│   │   ├── ai-review-prompt.md
│   │   ├── windsurf-fabrik-final-strategy.md
│   │   ├── windsurf-fabrik-integration-details.md
│   │   └── windsurf-fabrik-integration.md
│   ├── 2026-01-07-completed-plans
│   │   ├── 2026-01-07-docs-automation.md
│   │   ├── 2026-01-07-mypy-drivers-fix.md
│   │   └── 2026-01-08-droid-scripts-consolidation.md
│   ├── 2026-01-07-fabrik-phases
│   │   ├── Phase1.md
│   │   ├── Phase1b.md
│   │   ├── Phase1c.md
│   │   ├── Phase1d.md
│   │   ├── Phase2.md
│   │   ├── Phase3.md
│   │   ├── Phase4.md
│   │   ├── Phase5.md
│   │   ├── Phase6.md
│   │   ├── Phase7.md
│   │   ├── Phase8.md
│   │   ├── README.md               # Documentation index (Legacy)
│   │   ├── phase10-execution.md
│   │   ├── phase10-fixes-execution.md
│   │   ├── phase10.md
│   │   ├── phase1b-setup.md
│   │   ├── phase1b-test-results.md
│   │   └── phase9.md
│   ├── 2026-01-08-critical-rules-legacy.md
│   ├── 2026-01-08-documentation-standard-legacy.md
│   ├── 2026-01-08-folder-file-structure-legacy.md
│   ├── 2026-01-08-long-command-monitoring-design.md
│   ├── 2026-01-08-project-management-guide-legacy.md
│   ├── 2026-01-08-workflows-legacy.md
│   ├── 2026-02-25-pre-traycer-templates
│   │   ├── PHASE_TEMPLATE.md
│   │   ├── README.md               # Documentation index (Legacy)
│   │   ├── TASKS_TEMPLATE.md
│   │   └── implementation-plan-template.md
│   ├── CASCADE_MEMORIES_EXPORT_PART1.md
│   ├── CASCADE_MEMORIES_EXPORT_PART2.md
│   ├── CASCADE_MEMORIES_EXPORT_PART3.md
│   ├── CASCADE_RULES_EXPORT_GLOBAL.md
│   ├── CASCADE_RULES_EXPORT_WORKSPACE_PART1.md
│   ├── CASCADE_RULES_EXPORT_WORKSPACE_PART2.md
│   ├── CASCADE_RULES_EXPORT_WORKSPACE_PART3.md
│   ├── CASCADE_RULES_EXPORT_WORKSPACE_PART4.md
│   ├── CASCADE_RULES_EXPORT_WORKSPACE_PART5.md
│   ├── PM_INCORPORATION_PLAN.md
│   ├── README.md                   # Documentation index (Legacy)
│   ├── building-interactive-apps-with-droid-exec.md
│   ├── droid-cli-reference-hook-reference.md
│   ├── droid-exec-headless.md
│   ├── factory-enterprise.md
│   ├── factory-hooks.md
│   ├── factory-skills.md
│   ├── factoryai-power-user-settings.md
│   ├── previousresearchfordigitalmarketingstack.md
│   ├── trajectories
│   │   └── 2026-01-13-droid-core-improvements.md
│   └── traycer-specs
│       ├── 2025-11-14-traycer-factory-connection-test-enhancement.md
│       ├── 2025-11-14-traycer-factory-connection-test-execution.md
│       ├── 2025-11-14-traycer-factory-connection-test-re-validation-report.md
│       ├── 2025-11-14-traycer-factory-connection-test.md
│       └── 2025-11-15-traycer-factory-sanity-check-test-suite.md
├── design                          # System design and architecture proposals
│   └── CASCADE-DROID-STRATEGY.md
├── development                     # Active development plans and specs
│   ├── PLANS.md                    # Development plans index
│   └── plans                       # Plan documents (YYYY-MM-DD-plan-*.md)
│       ├── AI_OPERATING_CONSTITUTION
│       │   ├── AI_OPERATING_CONSTITUTION.md
│       │   ├── README.md           # Documentation index (Legacy)
│       │   ├── WINDSURFRULES_PATCH.md
│       │   ├── WhatsApp Image 2026-01-13 at 13.07.17.jpeg
│       │   ├── stage1_discovery_prompt.md
│       │   ├── stage2_traycer_prompt.md
│       │   └── stage3_cascade_execution.md
│       ├── Optimizing Workflows Across AI Coding Platforms for Fast, Low-Cost, Near-Flawless Code.md
│       ├── archived
│       │   ├── 2026-01-14-plan-docker-compose.md
│       │   ├── 2026-02-15-plan-workflow-optimization.md
│       │   ├── 2026-02-16-plan-gap01-duplicate-detection.md
│       │   ├── 2026-02-16-plan-gap02-windsurf-workflows.md
│       │   ├── 2026-02-16-plan-gap03-mcp-server-config.md
│       │   ├── 2026-02-16-plan-gap04-kpi-dashboard.md
│       │   ├── 2026-02-16-plan-gap06-custom-droids.md
│       │   ├── 2026-02-16-plan-gap07-traycer-integration.md
│       │   ├── 2026-02-16-plan-gap08-property-testing.md
│       │   ├── 2026-02-16-plan-gap09-pipeline-orchestrator.md
│       │   ├── 2026-02-16-spec-gap01-duplicate-detection.md
│       │   ├── 2026-02-16-spec-gap02-windsurf-workflows.md
│       │   ├── 2026-02-16-spec-gap03-mcp-server-config.md
│       │   ├── 2026-02-16-spec-gap04-kpi-dashboard.md
│       │   ├── 2026-02-16-spec-gap06-custom-droids.md
│       │   ├── 2026-02-16-spec-gap07-traycer-integration.md
│       │   ├── 2026-02-16-spec-gap08-property-testing.md
│       │   ├── 2026-02-16-spec-gap09-pipeline-orchestrator.md
│       │   └── ChatGPT-Plan Document Critique.md
│       └── fix-fabrik-compliance-issues
│           ├── 2026-01-07-scaffold-fix-plan.md
│           ├── 2026-01-07-update-docs-updater-features.md
│           ├── 2026-01-09-fabrik-codebase-improvements.md
│           ├── 2026-01-09-fixes-00-index.md
│           ├── 2026-01-09-fixes-01-core.md
│           ├── 2026-01-09-fixes-02-drivers.md
│           ├── 2026-01-09-fixes-03-orchestrator.md
│           ├── 2026-01-09-fixes-04-scripts.md
│           ├── 2026-01-09-fixes-05-enforcement.md
│           ├── 2026-01-09-fixes-06-wordpress.md
│           ├── 2026-01-09-plan-review-index.md
│           └── README.md           # Documentation index (Legacy)
├── examples                        # Example code and configuration
│   └── droid_runner_integration_example.py
├── guides                          # Step-by-step guides and tutorials
│   ├── DEPLOYMENT_READY_CHECKLIST.md # Make projects deployment-ready
│   ├── DEVELOPMENT_WORKFLOW.md     # How Traycer fits into Fabrik's 9-step workflow
│   ├── FABRIK_INTEGRATION.md       # Build Fabrik-compatible microservices
│   ├── PROJECT_WORKFLOW.md         # Start here - new/existing project workflow
│   └── domain-hosting-automation.md # Domain + hosting automation
├── operations                      # Operational runbooks and VPS state
│   ├── backup-strategy.md          # VPS backup strategy
│   ├── coolify-migration.md        # Coolify migration procedures
│   ├── disaster-recovery.md        # Backup and recovery procedures
│   ├── duplicati-setup.md          # Duplicati backup configuration
│   ├── vps-status.md               # Current VPS state and configuration
│   └── vps-urls.md                 # All deployed service URLs
├── owner_ozgur_basak.md            # Owner profile & AI instructions
├── proposals                       # Project and feature proposals
│   └── document-management-system.md
├── reference                       # Technical reference and module documentation
│   ├── AI_TAXONOMY.md              # AI categories & tool selection
│   ├── CASCADE_BACKUP_GUIDE.md
│   ├── CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md
│   ├── CRITICAL_RULES.md           # Non-negotiable execution rules
│   ├── DATABASE_STRATEGY.md        # Database selection
│   ├── DOCUMENTATION_STANDARD.md   # Documentation standards and conventions
│   ├── EXTENSIONS.md
│   ├── PLANNING_REFERENCES.md      # INDEX for AI planning phases
│   ├── PROCESS_MONITORING_QUICKSTART.md # Process monitor setup
│   ├── PROJECT_COMPLIANCE_STATUS.md
│   ├── SaaS-GUI.md                 # SaaS skeleton GUI guide
│   ├── architecture.md             # System architecture overview
│   ├── auto-review.md              # Automatic code review system
│   ├── custom-droids.md
│   ├── docs-updater.md             # Automatic documentation updater
│   ├── drivers.md                  # Fabrik driver API (Coolify, DNS, etc.)
│   ├── droid-exec-integration.md
│   ├── droid-exec-limits.md
│   ├── droid-exec-usage.md         # Core droid exec usage
│   ├── enforcement-system.md       # Convention enforcement (check scripts, rules)
│   ├── exampleconsultancysitemap.md
│   ├── fabrik-cli-reference.md     # Fabrik CLI command reference
│   ├── fabrik-scaffold-specs.md
│   ├── file-api-deployment.md      # File API deployment guide
│   ├── global-gates.md             # Global gate definitions
│   ├── hooks-and-skills-guide.md   # Hook and skill usage guide
│   ├── kilo-agents.md              # Kilo agent configuration and usage
│   ├── kilo-code-review.md         # Kilo code review workflow
│   ├── kilo-complete-reference.md  # Complete Kilo reference
│   ├── kilo-files.md               # Kilo file handling reference
│   ├── kpi-schema.md
│   ├── mcp-config.md               # MCP server configuration reference
│   ├── orchestrator.md             # Deployment orchestrator module
│   ├── prebuilt-app-containers.md  # Prebuilt container catalog
│   ├── project-registry.md         # Master inventory of all /opt projects
│   ├── property-testing.md
│   ├── provisioner.md
│   ├── roadmap.md                  # Complete 8-phase roadmap summary
│   ├── spec-pipeline.md            # Spec pipeline (idea -> scope -> spec)
│   ├── stack.md                    # Technology stack & tools inventory
│   ├── technology-stack-decision-guide.md # Tech decision flowchart
│   ├── template_renderer.md
│   ├── templates.md                # Available deployment templates
│   ├── trueforge-images.md         # Trueforge image catalog
│   ├── uptime-kuma.md              # Uptime Kuma runbook
│   ├── verification-framework.md   # 3-lane verification system
│   ├── windsurf                    # Windsurf IDE optimization
│   │   ├── cascade-guide.md
│   │   ├── cascade-models.md
│   │   ├── csharp-cpp-setup.md
│   │   ├── features.md
│   │   ├── overview.md
│   │   └── recommended-extensions.md
│   ├── wordpress                   # WordPress technical docs
│   │   ├── architecture.md         # System architecture overview
│   │   ├── fixes.md                # Critical fixes
│   │   ├── pages-idempotency.md    # Page creation idempotency
│   │   ├── plugin-evaluation.md    # WordPress plugin evaluation criteria
│   │   ├── plugin-stack.md         # Curated WordPress plugin stack
│   │   └── site-specification.md   # Site spec YAML format
│   └── wordpress.md
└── trajectories
```
<!-- AUTO-GENERATED:STRUCTURE:END -->

---

## Documentation Navigation

### Quick Start

| Document | Purpose |
|----------|--------|
| [QUICKSTART.md](docs/QUICKSTART.md) | Get Fabrik running in 5 minutes |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | Configuration guide - credentials, architecture, troubleshooting |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | How to deploy services to VPS |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [TESTING.md](docs/TESTING.md) | How to run and write tests |
| [FAQ.md](docs/FAQ.md) | Frequently asked questions |
| [ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md) | Complete env var reference |

### Core Reference

| Document | Purpose |
|----------|--------|
| [architecture.md](docs/reference/architecture.md) | System architecture, components, data flow |
| [stack.md](docs/reference/stack.md) | Technology stack, APIs, libraries |
| [roadmap.md](docs/reference/roadmap.md) | Complete 8-phase development roadmap |
| [drivers.md](docs/reference/drivers.md) | Fabrik driver API (Coolify, DNS, etc.) |
| [templates.md](docs/reference/templates.md) | Available deployment templates |
| [SaaS-GUI.md](docs/reference/SaaS-GUI.md) | SaaS skeleton template guide |
| [CRITICAL_RULES.md](docs/reference/CRITICAL_RULES.md) | Non-negotiable execution rules |
| [DOCUMENTATION_STANDARD.md](docs/reference/DOCUMENTATION_STANDARD.md) | Documentation standards and conventions |
| [verification-framework.md](docs/reference/verification-framework.md) | 3-lane verification system |
| [global-gates.md](docs/reference/global-gates.md) | Global gate definitions |
| [enforcement-system.md](docs/reference/enforcement-system.md) | Convention enforcement scripts and rules |

**SaaS Template:** `templates/saas-skeleton/` — Next.js + Tailwind + SSE streaming for droid exec

### Phase Documentation

| Phase | Status | Document |
|-------|--------|----------|
| **Phase 1: Foundation** | ✅ Complete | [architecture.md](docs/reference/architecture.md) |
| **Phase 1b: Cloud Infrastructure** | ✅ Complete | [DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| **Phase 1c: Cloudflare DNS** | ✅ Complete | [SERVICES.md](docs/SERVICES.md) |
| **Phase 1d: WordPress Automation** | 🚧 In Progress | [wordpress.md](docs/reference/wordpress.md) |

### Operations

| Document | Purpose |
|----------|--------|
| [vps-status.md](docs/operations/vps-status.md) | Current VPS state and configuration |
| [vps-urls.md](docs/operations/vps-urls.md) | All deployed service URLs |
| [disaster-recovery.md](docs/operations/disaster-recovery.md) | Backup and recovery procedures |
| [duplicati-setup.md](docs/operations/duplicati-setup.md) | Duplicati backup configuration |
| [coolify-migration.md](docs/operations/coolify-migration.md) | Coolify migration procedures |

### Guides

| Document | Purpose |
|----------|--------|
| [PROJECT_WORKFLOW.md](docs/guides/PROJECT_WORKFLOW.md) | **Start here** — New/existing project workflow |
| [FABRIK_INTEGRATION.md](docs/guides/FABRIK_INTEGRATION.md) | Build Fabrik-compatible microservices |
| [domain-hosting-automation.md](docs/guides/domain-hosting-automation.md) | Full domain + hosting automation |
| [DEPLOYMENT_READY_CHECKLIST.md](docs/guides/DEPLOYMENT_READY_CHECKLIST.md) | Make any project deployment-ready |
| [DEVELOPMENT_WORKFLOW.md](docs/guides/DEVELOPMENT_WORKFLOW.md) | How Traycer fits into Fabrik's 9-step workflow |

### WordPress

| Document | Purpose |
|----------|--------|
| [plugin-stack.md](docs/reference/wordpress/plugin-stack.md) | Curated WordPress plugin stack |
| [architecture.md](docs/reference/wordpress/architecture.md) | WordPress v2 spec system |
| [fixes.md](docs/reference/wordpress/fixes.md) | Critical fixes for v2 |
| [pages-idempotency.md](docs/reference/wordpress/pages-idempotency.md) | Page creation idempotency |
| [site-specification.md](docs/reference/wordpress/site-specification.md) | Site spec YAML format |
| [plugin-evaluation.md](docs/reference/wordpress/plugin-evaluation.md) | WordPress plugin evaluation criteria |

### Droid Automation

| Document | Purpose |
|----------|--------|
| [droid-exec-usage.md](docs/reference/droid-exec-usage.md) | **Complete droid exec guide** — models, tasks, hooks, MCP, prompting, spec mode |
| [enforcement-system.md](docs/reference/enforcement-system.md) | Convention enforcement — check scripts, rules, pre-commit |
| [AGENTS.md](AGENTS.md) | Agent briefing for AI coding assistants |
| [factory-settings.json](templates/scaffold/factory-settings.json) | Factory settings template |
| [factory-hooks.json](templates/scaffold/factory-hooks.json) | Hooks configuration template |
| [factory-mcp.json](templates/scaffold/factory-mcp.json) | MCP servers template |
| [auto-review.md](docs/reference/auto-review.md) | Automatic code review system |
| [mcp-config.md](docs/reference/mcp-config.md) | MCP server configuration reference |
| [kilo_code_review.py](scripts/kilo_code_review.py) | Kilo-based code review runner |
| [acknowledge_reviews.py](scripts/acknowledge_reviews.py) | Review acknowledgement script |
| [review_processor.py](scripts/review_processor.py) | Review result processor |

### Kilo Code Review

| Document | Purpose |
|----------|--------|
| [kilo-agents.md](docs/reference/kilo-agents.md) | Kilo agent configuration and usage |
| [kilo-code-review.md](docs/reference/kilo-code-review.md) | Kilo code review workflow |
| [kilo-complete-reference.md](docs/reference/kilo-complete-reference.md) | Complete Kilo reference |
| [kilo-files.md](docs/reference/kilo-files.md) | Kilo file handling reference |

### Traycer Documentation

| Document | Purpose |
|----------|--------|
| [README.md](docs/traycer/README.md) | Traycer integration guide - features, modes, workflows |
| [traycer-yolo-workflow.md](docs/traycer/traycer-yolo-workflow.md) | YOLO (fast-path) workflow with Kilo agents |
| [traycer-agile-workflow.md](docs/traycer/traycer-agile-workflow.md) | 8-command Agile Workflow reference |
| [traycer-refactoring-workflow.md](docs/traycer/traycer-refactoring-workflow.md) | 4-command Refactoring Workflow reference |
| [traycer-evaluation.md](docs/traycer/traycer-evaluation.md) | Integration evaluation & decision |
| [templates/](docs/traycer/templates/) | Plan, execution, verification templates |

**Archived (2026-02-25):** `PHASE_TEMPLATE.md`, `TASKS_TEMPLATE.md`, `implementation-plan-template.md` moved to `docs/archive/2026-02-25-pre-traycer-templates/`. Replaced by Traycer Phases + dynamic spec generation.

**Quick Reference:**
```bash
droid exec "analyze code"                        # Read-only
droid exec --auto medium "fix issues"            # Dev work
droid exec --use-spec "add feature"              # Plan first
droid exec -m gemini-3-flash-preview "quick task" # Model select
droid exec -o stream-json "task"                 # Real-time output
```

**Model Management (Automated):**
```bash
# Auto-update runs daily via cron - no manual intervention needed
./scripts/setup_model_updates.sh               # Enable daily auto-updates

# Manual commands (if needed)
python3 scripts/droid_model_updater.py         # Force update check now
python3 scripts/droid_models.py stack-rank     # View current rankings
python3 scripts/droid_models.py recommend ci_cd # Get model for scenario
```

**Config:** `config/models.yaml` — Auto-updated from Factory docs daily
**Scripts:** `scripts/droid_tasks.py`, `scripts/droid_models.py`, `scripts/docs_updater.py`, `scripts/container_images.py`, `scripts/enforcement/validate_conventions.py`
**Batch Scripts:** `scripts/droid/` (refactor-imports, improve-errors, fix-lint)
**Workflows:** `.github/workflows/` (droid-review, update-docs, security-scanner, daily-maintenance)
**Key Flags:** `--auto`, `--use-spec`, `-m`, `-r`, `-o`, `--cwd`, `-s`
**VPS Deployment:** See §25-26 in droid-exec-usage.md for Coolify + SSE streaming patterns

### Project Context

| Document | Purpose |
|----------|--------|
| [FABRIK_OVERVIEW.md](docs/FABRIK_OVERVIEW.md) | What Fabrik is and what it does |
| [ROADMAP_ACTIVE.md](docs/ROADMAP_ACTIVE.md) | Current priorities, backlog, future plans |
| [BUSINESS_MODEL.md](docs/BUSINESS_MODEL.md) | Monetization strategy |
| [owner_ozgur_basak.md](docs/owner_ozgur_basak.md) | Owner profile & AI instructions |
| [project-registry.md](docs/reference/project-registry.md) | Master inventory of all /opt projects |

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
