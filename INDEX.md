# Project File Index

**Last Updated:** 2026-03-01

> **Purpose:** Single source of truth for all file purposes in this project.
> **For AI Agents:** Read this FIRST before making changes. Every file's purpose and update trigger is documented here.

---

## Root Files

| File | Purpose | Update When | Enforced |
|------|---------|-------------|----------|
| **INDEX.md** | This file - master index of all files | Add/remove files from project | Step 3 (ERROR) |
| **README.md** | Primary entry point - features, quick start, architecture, tech stack | New features, tech changes, setup changes | Step 3 (ERROR) |
| **CHANGELOG.md** | Change history - what/why/when | Every code change | Step 3 (ERROR) |
| **AGENTS.md** | AI agent briefing - authoritative source for AI coding agents | Never edit (managed by Fabrik) | N/A |
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
| **INDEX.md** | Master file index - auto-generated structure tree in Documentation Structure Map section | Auto-updated by docs_updater.py | Step 7 (auto) |
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
│   ├── QUICKSTART.md       # Getting started guide
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
├── apps/                            # Deployable application containers
│   ├── example-api/                 # Example FastAPI service (Dockerfile, compose.yaml)
│   └── postgres-main/               # Shared PostgreSQL instance (compose.yaml)
├── config/                          # Runtime configuration files
│   └── platform.yaml.example        # Platform config template
├── configs/                         # Runtime service configs (deployed services)
│   ├── loki/                        # Loki log aggregation config
│   ├── promtail/                    # Promtail log scraper config
│   ├── prometheus/                  # Prometheus metrics config
│   └── n8n/workflows/               # n8n workflow JSON templates
├── docs/                            # Documentation (see Structure Map below)
│   └── operations/n8n-webhooks.md   # n8n webhook URLs, payloads, curl tests
├── infrastructure/                  # VPS-level system files
│   ├── coolify-ssh-permissions.sh
│   ├── coolify-ssh-permissions.service
│   └── coolify-ssh-permissions.timer
├── scripts/                         # Automation and tooling scripts
│   ├── final_gate.py                # Mandatory pre-commit quality gate
│   ├── docs_updater.py              # Auto-update docs structure
│   ├── kilo_code_review.py          # Kilo-based code review runner
│   ├── enforcement/                 # Convention check scripts (check_*.py)
│   └── utils/                       # Shared script utilities
├── specs/                           # YAML specs and planning documents
│   └── infrastructure/              # Infrastructure service YAML specs (Phase 9)
├── sql/                             # Database DDL scripts
├── src/fabrik/                      # Core Fabrik Python package
│   ├── cli.py                       # CLI entry point
│   ├── scaffold.py                  # Project scaffolding
│   ├── ai/                          # AI module: LLMClient, UsageTracker
│   ├── api/                         # API layer
│   ├── drivers/                     # External service drivers
│   ├── models/                      # Data models
│   ├── orchestrator/                # Deployment orchestrator
│   └── wordpress/                   # WordPress automation
│       ├── handoff.py               # Handoff report generator
│       ├── stages/
│       │   └── verify.py            # Verification stage (post-deploy)
├── templates/                       # Project and document templates
│   ├── saas-skeleton/               # Next.js 14 + Tailwind SaaS starter
│   ├── scaffold/                    # Fabrik scaffold config
│   ├── prompts/                     # Prompt templates for AI commands
│   └── docs/                        # Document templates
├── tests/                           # Test suite
├── .github/                         # GitHub Actions CI/CD
│   └── workflows/                   # ci.yml, docs-check.yml
└── .windsurf/                       # Windsurf IDE config
    ├── hooks.json
    ├── rules/                       # 00-critical, 10-python, etc.
    └── workflows/                   # code-review, bug-fix, deploy, etc.
```

---

## Documentation Structure Map

<!-- AUTO-GENERATED:STRUCTURE:START -->
<!-- AUTO-GENERATED:STRUCTURE v1 | 2026-03-01T23:42 -->
```text
docs/
├── BUSINESS_MODEL.md               # Monetization strategy
├── CONFIGURATION.md                # Environment variables and settings
├── DEPLOYMENT.md                   # How to deploy services to VPS
├── FAQ.md                          # Frequently asked questions
├── QUICKSTART.md                   # Get Fabrik running in 5 minutes
├── SERVICES.md                     # External services Fabrik depends on
├── TESTING.md                      # How to run and write tests
├── TROUBLESHOOTING.md              # Common issues & solutions
├── archive                         # Archived and completed documentation
│   ├── 2026-01-04-analysis-reports
│   │   ├── ARCHITECTURE_ANALYSIS.md
│   │   └── DOCUMENTATION_AUDIT.md
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
│   ├── 2026-02-26-INDEX.md.archived
│   ├── 2026-02-26-doc-consolidation
│   │   ├── ENVIRONMENT_VARIABLES.md # Complete env var reference
│   │   ├── FABRIK_OVERVIEW.md      # What Fabrik is and what it does
│   │   └── ROADMAP_ACTIVE.md       # Current priorities, backlog, future plans
│   ├── 2026-02-27-droid-exec-cleanup
│   │   ├── droid-exec-usage.md     # Core droid exec usage
│   │   └── spec-pipeline.md        # Spec pipeline (idea -> scope -> spec)
│   ├── 2026-02-28-kilo-redundant
│   │   ├── kilo-agents.md          # Kilo agent configuration and usage
│   │   ├── kilo-ai-documentation.md
│   │   ├── kilo-code-review.md     # Kilo code review workflow
│   │   ├── kilo-complete-reference.md # Complete Kilo reference
│   │   └── kilo-files.md           # Kilo file handling reference
│   ├── 2026-03-01-kilo-enhancement-context
│   │   ├── 2026-02-28-phase2-retry-logic.md
│   │   ├── 2026-02-28-phase3-context.md
│   │   ├── 2026-02-28-phase3-cost-report.md
│   │   ├── 2026-02-28-phase3-metrics.md
│   │   ├── 2026-02-28-phase3-prevalidation.md
│   │   ├── 2026-02-28-phase6-context.md
│   │   ├── 2026-02-28-phase8-context.md
│   │   ├── 2026-02-28-phase9-context.md
│   │   ├── 2026-03-01-fix-kilo-hang.md
│   │   ├── 2026-03-01-kilo-agent-health.md
│   │   ├── 2026-03-01-opus-fix-kilo-scope-errors.md
│   │   ├── 2026-03-01-phase3-prevalidation.md
│   │   ├── 2026-03-01-phase4-script-validation.md
│   │   ├── OPUS_FIX_GUIDE.md
│   │   └── POST_MORTEM_2026-03-01_kilo_hang.md
│   ├── CASCADE_MEMORIES_EXPORT_PART1.md
│   ├── CASCADE_MEMORIES_EXPORT_PART2.md
│   ├── CASCADE_MEMORIES_EXPORT_PART3.md
│   ├── CASCADE_RULES_EXPORT_GLOBAL.md
│   ├── CASCADE_RULES_EXPORT_WORKSPACE_PART1.md
│   ├── CASCADE_RULES_EXPORT_WORKSPACE_PART2.md
│   ├── CASCADE_RULES_EXPORT_WORKSPACE_PART3.md
│   ├── CASCADE_RULES_EXPORT_WORKSPACE_PART4.md
│   ├── CASCADE_RULES_EXPORT_WORKSPACE_PART5.md
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
│       ├── 2026-02-27-phase-priority-analysis.md
│       ├── 2026-02-28-weekend-blitz-execution.md
│       ├── 2026-03-01-plan-cost-aware-escalation.md
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
│       │   ├── 2025-01-03-droid-validation
│       │   │   └── droid-validation-report.md
│       │   ├── 2025-12-27_FUTURE_WORK.md
│       │   ├── 2025-12-27_WHATS_NEXT.md
│       │   ├── 2025-12-27_future-development.md
│       │   ├── 2026-01-04-monitoring-design
│       │   │   ├── DROID_RUNNER_MONITORING.md
│       │   │   └── LONG_COMMAND_MONITORING.md
│       │   ├── 2026-01-05-design-docs
│       │   │   ├── ai-review-prompt.md
│       │   │   ├── windsurf-fabrik-final-strategy.md
│       │   │   ├── windsurf-fabrik-integration-details.md
│       │   │   └── windsurf-fabrik-integration.md
│       │   ├── 2026-01-07-completed-plans
│       │   │   ├── 2026-01-07-docs-automation.md
│       │   │   ├── 2026-01-07-mypy-drivers-fix.md
│       │   │   └── 2026-01-08-droid-scripts-consolidation.md
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
│       │   ├── ChatGPT-Plan Document Critique.md
│       │   ├── PM_INCORPORATION_PLAN.md
│       │   └── README.md           # Documentation index (Legacy)
│       ├── fix-fabrik-compliance-issues
│       │   ├── 2026-01-07-scaffold-fix-plan.md
│       │   ├── 2026-01-07-update-docs-updater-features.md
│       │   ├── 2026-01-09-fabrik-codebase-improvements.md
│       │   ├── 2026-01-09-fixes-00-index.md
│       │   ├── 2026-01-09-fixes-01-core.md
│       │   ├── 2026-01-09-fixes-02-drivers.md
│       │   ├── 2026-01-09-fixes-03-orchestrator.md
│       │   ├── 2026-01-09-fixes-04-scripts.md
│       │   ├── 2026-01-09-fixes-05-enforcement.md
│       │   ├── 2026-01-09-fixes-06-wordpress.md
│       │   ├── 2026-01-09-plan-review-index.md
│       │   └── README.md           # Documentation index (Legacy)
│       └── previously-planned-fabrik-phases
│           ├── 2026-02-27-phase1-verification.md
│           ├── 2026-02-27-phase10-verification.md
│           ├── 2026-02-27-phase2-verification.md
│           ├── 2026-02-27-phase3-verification.md
│           ├── 2026-02-27-phase4-verification.md
│           ├── 2026-02-27-phase5-verification.md
│           ├── 2026-02-27-phase6-verification.md
│           ├── 2026-02-27-phase7-verification.md
│           ├── 2026-02-27-phase8-verification.md
│           ├── 2026-02-27-phase9-verification.md
│           ├── Phase1.md
│           ├── Phase1b.md
│           ├── Phase1c.md
│           ├── Phase1d.md
│           ├── Phase2.md
│           ├── Phase3.md
│           ├── Phase4.md
│           ├── Phase5.md
│           ├── Phase6.md
│           ├── Phase7.md
│           ├── Phase8.md
│           ├── README.md           # Documentation index (Legacy)
│           ├── phase10-execution.md
│           ├── phase10-fixes-execution.md
│           ├── phase10.md
│           ├── phase1b-setup.md
│           ├── phase1b-test-results.md
│           ├── phase9.md
│           └── previously_planned_ideas.md
├── examples                        # Example code and configuration
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
│   ├── n8n-webhooks.md
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
│   ├── ai.md
│   ├── architecture.md             # System architecture overview
│   ├── auto-review.md              # Automatic code review system
│   ├── docs-updater.md             # Automatic documentation updater
│   ├── drivers.md                  # Fabrik driver API (Coolify, DNS, etc.)
│   ├── enforcement-system.md       # Convention enforcement (check scripts, rules)
│   ├── exampleconsultancysitemap.md
│   ├── fabrik-cli-reference.md     # Fabrik CLI command reference
│   ├── fabrik-scaffold-specs.md     # MOVED → docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md
│   ├── file-api-deployment.md      # File API deployment guide
│   ├── global-gates.md             # Global gate definitions
│   ├── hooks-and-skills-guide.md   # Hook and skill usage guide
│   ├── kilo
│   │   ├── KILO_AGENT_NAMING.md
│   │   ├── KILO_AGENT_SELECTION_GUIDE.md
│   │   ├── KILO_CLI_REFERENCE.md
│   │   ├── KILO_EXTRACTION_SUMMARY.md
│   │   ├── KILO_IMPROVEMENTS_PROPOSAL.md
│   │   ├── KILO_MODEL_SELECTION.md
│   │   ├── KILO_PERFORMANCE_TUNING.md
│   │   ├── KILO_PLATFORM_FEATURES.md
│   │   ├── KILO_TROUBLESHOOTING.md
│   │   ├── KILO_UPDATE_SCHEDULE.md
│   │   ├── KILO_USAGE_GUIDE.md
│   │   └── README.md               # Documentation index (Legacy)
│   ├── kpi-schema.md
│   ├── mcp-config.md               # MCP server configuration reference
│   ├── orchestrator.md             # Deployment orchestrator module
│   ├── prebuilt-app-containers.md  # Prebuilt container catalog
│   ├── project-registry.md         # Master inventory of all /opt projects
│   ├── property-testing.md
│   ├── provisioner.md
│   ├── roadmap.md                  # Complete 8-phase roadmap summary
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
├── trajectories
└── traycer
    ├── README.md                   # Documentation index (Legacy)
    ├── templates
    │   ├── plan_template.md
    │   ├── task_execution_template.md
    │   └── verification_template.md
    ├── traycer-agile-workflow.md   # 8-command Traycer Agile Workflow reference
    ├── traycer-evaluation.md       # Traycer integration evaluation
    ├── traycer-refactoring-workflow.md # 4-command Traycer Refactoring Workflow reference
    └── traycer-yolo-workflow.md
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
| [.env.example](.env.example) | Environment variable reference (AUTHORITATIVE with inline comments) |

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

**SaaS Template:** `templates/saas-skeleton/` — Next.js + Tailwind + SSE streaming for AI chat integration

### Phase Documentation

| Phase | Status | Document |
|-------|--------|----------|
| **Phase 1: Foundation** | Complete | [architecture.md](docs/reference/architecture.md) |
| **Phase 1b: Cloud Infrastructure** | Complete | [DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| **Phase 1c: Cloudflare DNS** | Complete | [SERVICES.md](docs/SERVICES.md) |
| **Phase 1d: WordPress Automation** | In Progress | [wordpress.md](docs/reference/wordpress.md) |

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

### Quality Gates & Code Review

| Document | Purpose |
|----------|--------|
| [enforcement-system.md](docs/reference/enforcement-system.md) | Convention enforcement — check scripts, rules, pre-commit |
| [AGENTS.md](AGENTS.md) | Agent briefing for AI coding assistants (Kilo CLI, Traycer) |
| [auto-review.md](docs/reference/auto-review.md) | Automatic code review system |
| [kilo_code_review.py](scripts/kilo_code_review.py) | Kilo CLI code review runner |
| [kilo_docs_enforcer.py](scripts/kilo_docs_enforcer.py) | AI documentation enforcement |
| [final_gate.py](scripts/final_gate.py) | Pre-commit quality gate (27 enforcement scripts) |

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

**Archived (2026-02-27):** `droid exec` system archived. Fabrik now uses **Traycer + Kilo + Windsurf Cascade** workflow.
- `scripts/droid_models.py` → `scripts/.archive/2026-02-27-droid-exec-cleanup/`
- `docs/reference/droid-exec-usage.md` → `docs/archive/2026-02-27-droid-exec-cleanup/`
- `docs/reference/spec-pipeline.md` → `docs/archive/2026-02-27-droid-exec-cleanup/`
- `config/models.yaml` → `config/.archive/2026-02-27-droid-exec-cleanup/`

**Scripts:** `scripts/docs_updater.py`, `scripts/container_images.py`, `scripts/enforcement/validate_conventions.py`
**Workflows:** `.github/workflows/` (ci.yml, docs-check.yml)

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

**Note:** For complete architecture details, see `docs/reference/`.

---

## Kilo Agent System

**Location:** `scripts/` + `docs/reference/kilo/` + `~/.traycer/cli-agents/`
**Purpose:** AI code review and code generation via Kilo CLI

### Documentation Hub
- **`docs/reference/kilo/`** - Complete Kilo documentation (README, INDEX, guides)

### Core Scripts
- `scripts/generate_kilo_agents.py` - Generates tier-based agent scripts from pricing manifest
- `scripts/kilo_agent_updater.py` - Updates catalog and pricing (57 providers)
- `scripts/kilo_code_review.py` - Code review (Step 4 in 9-step workflow)
- `scripts/extract_pricing.py` - 2-call algebraic pricing extraction

### Data Files (AUTHORITATIVE)
- `scripts/kilo_18_agents_complete.json` - Primary pricing manifest (18 agents)
- `scripts/kilo_all_models.json` - Complete catalog (319 models)
- `scripts/manual_pricing_data.json` - Manual pricing (12 models)
- `scripts/kilo_comprehensive_db.json` - Model database with capabilities

### Active Agents (18 + 1 utility)
- `~/.traycer/cli-agents/<TIER><NN>-<model>-<role>-<effort>-i<IN>-o<OUT>.sh`
- Tiers: P=Prime, S=Strong, B=Balanced, E=Economy
- See `docs/reference/kilo/` for complete documentation

**Archived:** 10 obsolete JSON files → `scripts/.archive/kilo-json-20260228/`
**Archived:** 5 redundant docs → `docs/archive/2026-02-28-kilo-redundant/`
