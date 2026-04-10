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
| **.windsurfrules** | Windsurf rules (local copy from /opt/fabrik/.windsurfrules) | Never edit (managed by Fabrik) | N/A |

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
- Print/Console.log Ban (Tier 1)
- Kilo CLI Health Check
- Symlink Integrity
- Documentation Drift
- AGENTS.md TOC Current
- User Guide Presence (Tier 2)
- Reusable Module Tagging (Tier 2, warning)

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
├── AGENTS.md                        # AI agent briefing (copied into projects)
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
│   │   ├── dns.py                   # DNS Manager service client
│   │   ├── coolify.py               # Coolify deployment API client
│   │   ├── seo.py                   # SEO service client (keyword research, briefs)
│   │   ├── tco.py                   # TCO client (AI content generation)
│   │   ├── image_broker.py          # Image Broker client (stock images)
│   │   ├── r2.py                    # Cloudflare R2 object storage client
│   │   ├── supabase.py              # Supabase client
│   │   └── uptime_kuma.py           # Uptime Kuma monitoring client
│   ├── models/                      # Data models
│   ├── orchestrator/                # Deployment orchestrator
│   │   ├── __init__.py              # DeploymentOrchestrator
│   │   ├── content_publisher.py     # ContentPublisher (SEO → TCO → Image → WP)
│   │   ├── context.py               # DeploymentContext
│   │   ├── deployer.py              # ServiceDeployer
│   │   ├── exceptions.py            # Custom exceptions
│   │   ├── rollback.py              # RollbackManager
│   │   ├── secrets.py               # SecretsManager
│   │   ├── states.py                # DeploymentState
│   │   ├── validator.py             # SpecValidator
│   │   └── verifier.py              # DeploymentVerifier
│   └── wordpress/                   # WordPress automation
│       ├── handoff.py               # Handoff report generator
│       ├── stages/
│       │   └── verify.py            # Verification stage (post-deploy)
├── templates/                       # Project and document templates
│   ├── file-worker/                 # File worker scaffold template
│   │   └── worker/
│   │       └── main.py              # Job processor (uses worker.logger)
│   ├── saas-skeleton/               # Next.js 14 + Tailwind SaaS starter
│   ├── scaffold/                    # Fabrik scaffold config
│   ├── prompts/                     # Prompt templates for AI commands
│   └── docs/                        # Document templates
├── tests/                           # Test suite
│   ├── content/                     # Content pipeline tests
│   │   ├── test_seo_client.py       # SEOClient driver tests
│   │   ├── test_tco_client.py       # TCOClient driver tests
│   │   ├── test_image_broker_client.py # ImageBrokerClient driver tests
│   │   ├── test_orchestrator.py     # ContentPublisher orchestrator tests
│   │   └── test_cli_content.py      # CLI content command tests
│   ├── drivers/                     # Driver tests
│   └── orchestrator/                # Deployment orchestrator tests
├── .github/                         # GitHub Actions CI/CD
│   └── workflows/                   # ci.yml, docs-check.yml
└── .windsurf/                       # Windsurf IDE config
    ├── hooks.json
    ├── rules/                       # 10-python, 20-typescript, etc.
    └── workflows/                   # code-review, bug-fix, deploy, etc.
```

---

## Documentation Structure Map

<!-- AUTO-GENERATED:STRUCTURE:START -->
<!-- AUTO-GENERATED:STRUCTURE v1 | 2026-03-26T00:13 -->
```text
docs/
├── BUSINESS_MODEL.md               # Monetization strategy
├── CONFIGURATION.md                # Environment variables and settings
├── DEPLOYMENT.md                   # How to deploy services to VPS
├── EXTERNAL_SYSTEMS.md             # External service dependencies
├── FAQ.md                          # Frequently asked questions
├── FEATURES.md                     # Feature list
├── QUICKSTART.md                   # Get Fabrik running in 5 minutes
├── SERVICES.md                     # External services Fabrik depends on
├── TROUBLESHOOTING.md              # Common issues & solutions
├── architecture
│   └── WORDPRESS-MODULE-INTEGRATION.md # WordPress module integration
├── archive                         # Archived and completed documentation
├── design                          # System design and architecture proposals
├── development                     # Active development plans and specs
│   ├── PLANS.md                    # Development plans index
│   └── plans                       # Plan documents (YYYY-MM-DD-plan-*.md)
│       ├── archived
│       ├── issues
│       └── previously-planned-fabrik-phases
├── examples                        # Example code and configuration
│   └── health_check_usage.py
├── guides                          # Step-by-step guides and tutorials
│   ├── DEPLOYMENT_READY_CHECKLIST.md # Make projects deployment-ready
│   ├── EXCEL_FILE_GENERATION.md    # Excel file generation guide
│   ├── FABRIK_INTEGRATION.md       # Build Fabrik-compatible microservices
│   ├── domain-hosting-automation.md # Domain + hosting automation
│   ├── traycer-free-tier-agents-testing.md # Traycer free-tier agent testing
│   └── traycer-kilo-workflow-analysis.md # Traycer + Kilo workflow analysis
├── infrastructure                  # Infrastructure docs
│   └── WSL2-DNS-FIX.md             # WSL2 DNS resolution fix
├── operations                      # Operational runbooks and VPS state
│   ├── backup-strategy.md          # VPS backup strategy
│   ├── coolify-migration.md        # Coolify migration procedures
│   ├── disaster-recovery.md        # Backup and recovery procedures
│   ├── duplicati-setup.md          # Duplicati backup configuration
│   ├── n8n-webhooks.md             # n8n webhook configuration
│   ├── vps-status.md               # Current VPS state and configuration
│   └── vps-urls.md                 # All deployed service URLs
├── owner_ozgur_basak.md            # Owner profile & AI instructions
├── reference                       # Technical reference and module documentation
│   ├── AI_TAXONOMY.md              # AI categories & tool selection
│   ├── CRITICAL_RULES.md           # Non-negotiable execution rules
│   ├── DATABASE_STRATEGY.md        # Database selection
│   ├── DOCUMENTATION_STANDARD.md   # Documentation standards and conventions
│   ├── EXTENSIONS.md
│   ├── Modern GUI Approaches for Chrome Extensionst.md
│   ├── Modern GUI Approaches for a Lean, Fast, Effective, Low-Confusion SaaS Web App.md
│   ├── Modern Mobile GUI Approaches for Android and iOS.md
│   ├── PLANNING_REFERENCES.md      # INDEX for AI planning phases
│   ├── SaaS-GUI.md                 # SaaS skeleton GUI guide
│   ├── ai.md
│   ├── ai_agent_prompt_directives.html
│   ├── ai_agent_prompt_directives.md # AI agent prompt directives
│   ├── architecture.md             # System architecture overview
│   ├── drivers.md                  # Fabrik driver API (Coolify, DNS, etc.)
│   ├── exampleconsultancysitemap.md
│   ├── fabrik-cli-reference.md     # Fabrik CLI command reference
│   ├── fabrik.md
│   ├── file-api-deployment.md      # File API deployment guide
│   ├── global-gates.md             # Global gate definitions
│   ├── health-monitoring.md        # Health monitoring patterns
│   ├── image
│   │   └── AI_TAXONOMY
│   ├── kilo
│   │   ├── KILO-TOKEN-LEAN-WORKFLOW.md # Kilo token-lean workflow
│   │   ├── KILO_AGENT_NAMING.md
│   │   ├── KILO_AGENT_SELECTION_GUIDE.md
│   │   ├── KILO_CLI_REFERENCE.md
│   │   ├── KILO_MODEL_CAPABILITIES.md # Kilo model capabilities
│   │   ├── KILO_MODEL_SELECTION.md
│   │   ├── KILO_PERFORMANCE_TUNING.md
│   │   ├── KILO_PLATFORM_FEATURES.md
│   │   ├── KILO_TROUBLESHOOTING.md
│   │   ├── KILO_UPDATE_SCHEDULE.md
│   │   ├── KILO_USAGE_GUIDE.md
│   │   ├── README.md               # Documentation index (Legacy)
│   │   ├── REVIEWER_BENCHMARK_RESULTS.md # Reviewer benchmark results
│   │   ├── kilo-benchmarks-testing.md # Kilo benchmarks testing
│   │   └── kilo-complete-reference.md # Complete Kilo reference
│   ├── kpi-schema.md
│   ├── orchestrator.md             # Deployment orchestrator module
│   ├── prebuilt-app-containers.md  # Prebuilt container catalog
│   ├── project-registry.md         # Master inventory of all /opt projects
│   ├── provisioner.md
│   ├── roadmap.md                  # Complete 8-phase roadmap summary
│   ├── scripts.md
│   ├── stack.md                    # Technology stack & tools inventory
│   ├── technology-stack-decision-guide.md # Tech decision flowchart
│   ├── template_renderer.md
│   ├── templates.md                # Available deployment templates
│   ├── trueforge-images.md         # Trueforge image catalog
│   ├── uptime-kuma.md              # Uptime Kuma runbook
│   ├── windsurf                    # Windsurf IDE optimization
│   │   ├── cascade-guide.md
│   │   ├── cascade-models.md
│   │   ├── csharp-cpp-setup.md
│   │   ├── features.md
│   │   ├── overview.md
│   │   └── recommended-extensions.md
│   ├── wordpress                   # WordPress technical docs
│   │   ├── architecture.md         # System architecture overview
│   │   ├── deployment-workflow.md  # WordPress deployment workflow
│   │   ├── fixes.md                # Critical fixes
│   │   ├── pages-idempotency.md    # Page creation idempotency
│   │   ├── plugin-evaluation.md    # WordPress plugin evaluation criteria
│   │   ├── plugin-stack.md         # Curated WordPress plugin stack
│   │   └── site-specification.md   # Site spec YAML format
│   └── wordpress.md                # WordPress module overview
├── trajectories
├── traycer
│   ├── AGENT-TIMEOUT-POLICY.md     # Agent timeout policy
│   ├── PLAN_OUTPUT_LOCATION.md     # Plan output location
│   ├── QUICKSTART-MCP-KILO.md      # MCP Kilo quickstart
│   ├── README.md                   # Documentation index (Legacy)
│   ├── TEMPLATE_MAPPING.md         # Template mapping
│   ├── TRAYCER-KILO-AGENTS-GUIDE.md # Traycer Kilo agents guide
│   ├── TRAYCER-KILO-DIRECT-CLI.md  # Traycer Kilo direct CLI
│   ├── epic-kilo-integration.md    # Epic Kilo integration
│   ├── kilo_selected_agents.md     # Kilo selected agents
│   ├── mcp-kilo-setup-guide.md     # MCP Kilo setup guide
│   ├── templates
│   │   ├── plan_template.md
│   │   ├── task_execution_template.md
│   │   └── verification_template.md
│   ├── traycer-agile-workflow.md   # 8-command Traycer Agile Workflow reference
│   ├── traycer-evaluation.md       # Traycer integration evaluation
│   ├── traycer-refactoring-workflow.md # 4-command Traycer Refactoring Workflow reference
│   └── traycer-yolo-workflow.md
└── workflows                       # Workflow documentation
    ├── DEV_TRACKER_WORKFLOW.md     # Development tracker workflow
    ├── DOCUMENTATOR_WORKFLOW.md    # Documentator workflow
    ├── FABRIK_SCAFFOLD_WORKFLOW.md # Fabrik scaffold workflow
    ├── FINAL_GATE_WORKFLOW.md      # Final gate workflow
    ├── HEALTH_CHECKER_WORKFLOW.md  # Health checker workflow
    ├── HEALTH_SUMMARY_WORKFLOW.md
    ├── KILO_AGENT_MANAGEMENT.md    # Kilo agent management
    ├── KILO_DISPATCH_WORKFLOW.md
    ├── KILO_REVIEW_WORKFLOW.md     # Kilo review workflow
    ├── SYNC_ENFORCEMENT_WORKFLOW.md # Sync enforcement workflow
    └── SYNC_PROJECTS_WORKFLOW.md   # Sync projects workflow
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
| [SCAFFOLD_TO_DEPLOY_INTEGRATION.md](docs/reference/SCAFFOLD_TO_DEPLOY_INTEGRATION.md) | Scaffold → Deploy workflow gaps & AI agent guidance |
| [DEPLOY_TEMPLATE_AUDIT_2026-04-10.md](docs/reference/DEPLOY_TEMPLATE_AUDIT_2026-04-10.md) | Complete deploy template system audit & verification |
| [CRITICAL_RULES.md](docs/reference/CRITICAL_RULES.md) | Non-negotiable execution rules |
| [DOCUMENTATION_STANDARD.md](docs/reference/DOCUMENTATION_STANDARD.md) | Documentation standards and conventions |
| [global-gates.md](docs/reference/global-gates.md) | Global gate definitions |

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
| [FABRIK_INTEGRATION.md](docs/guides/FABRIK_INTEGRATION.md) | Build Fabrik-compatible microservices |
| [domain-hosting-automation.md](docs/guides/domain-hosting-automation.md) | Full domain + hosting automation |
| [DEPLOYMENT_READY_CHECKLIST.md](docs/guides/DEPLOYMENT_READY_CHECKLIST.md) | Make any project deployment-ready |
| [EXCEL_FILE_GENERATION.md](docs/guides/EXCEL_FILE_GENERATION.md) | Excel file generation guide |

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
| [AGENTS.md](AGENTS.md) | Traycer orchestrator contract (planning constraints, rule-pack registry, stack defaults) |
| [kilo_code_review.py](scripts/kilo_code_review.py) | Kilo CLI code review runner |
| [kilo_docs_enforcer.py](scripts/kilo_docs_enforcer.py) | AI documentation enforcement |
| [final_gate.py](scripts/final_gate.py) | Pre-commit quality gate (33 enforcement scripts) |
| [check_print_ban.py](scripts/enforcement/check_print_ban.py) | Tier 1: Ban print()/console.log() in production code [reusable] |
| [check_user_guide.py](scripts/enforcement/check_user_guide.py) | Tier 2: Verify docs/user-guide/ when has_user_guide: true [reusable] |
| [check_reusable_modules.py](scripts/enforcement/check_reusable_modules.py) | Tier 2 advisory: Check [reusable] tags in INDEX.md [reusable] |
| [test_cross_cutting_enforcement.py](tests/test_cross_cutting_enforcement.py) | 31 tests for cross-cutting enforcement scripts |
| [test_backfill_has_user_guide.py](tests/test_backfill_has_user_guide.py) | 9 tests for has_user_guide backfill in fix_project() |
| [test_seo_client.py](tests/content/test_seo_client.py) | 7 tests for SEOClient driver (domain lookup, briefs lifecycle) |
| [test_tco_client.py](tests/content/test_tco_client.py) | 2 tests for TCOClient driver (generate_from_brief, error propagation) |
| [test_image_broker_client.py](tests/content/test_image_broker_client.py) | 3 tests for ImageBrokerClient driver (auto_download success/failure) |
| [test_orchestrator.py](tests/content/test_orchestrator.py) | 14 tests for ContentPublisher orchestrator (pipeline, error handling, submission) |
| [test_cli_content.py](tests/content/test_cli_content.py) | 3 tests for `fabrik content publish` CLI command |
| [test_saas_logger.py](tests/test_saas_logger.py) | 5 tests for saas-skeleton pino logger scaffold generation |
| [test_scaffold_logging.py](tests/test_scaffold_logging.py) | Tests for python-api + chrome-extension scaffold logging (logger.py, middleware.py, correlation ID) |

### Scaffold-Generated Files (Python API + Chrome Extension Backend)

| Generated File | Purpose | Update When | Tag |
|----------------|---------|-------------|-----|
| `src/{package}/logger.py` | structlog JSON logger with SERVICE_NAME binding and contextvars merge | Logging config changes | [reusable] |
| `src/{package}/middleware.py` | X-Request-ID correlation middleware (ContextVar + structlog.contextvars) | Middleware pattern changes | [reusable] |
| `src/logger.js` | pino JSON logger with SERVICE_NAME env var (node-api + file-api) | Logging config changes | [reusable] |
| `lib/logger.ts` | pino TypeScript logger with SERVICE_NAME env var (saas-skeleton) | Logging config changes | [reusable] |
| `worker/logger.py` | structlog JSON logger for file-worker with SERVICE_NAME binding | Logging config changes | [reusable] |
| [test_node_scaffold_logging.py](tests/test_node_scaffold_logging.py) | 17 tests for node-api + file-api pino logging scaffold (logger.js, X-Request-ID, SERVICE_NAME) |

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

### Workflows

| Document | Purpose |
|----------|--------|
| [FINAL_GATE_WORKFLOW.md](docs/workflows/FINAL_GATE_WORKFLOW.md) | Final gate quality checks |
| [KILO_REVIEW_WORKFLOW.md](docs/workflows/KILO_REVIEW_WORKFLOW.md) | Kilo code review workflow |
| [DOCUMENTATOR_WORKFLOW.md](docs/workflows/DOCUMENTATOR_WORKFLOW.md) | Documentator workflow |
| [FABRIK_SCAFFOLD_WORKFLOW.md](docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md) | Fabrik scaffold workflow |
| [KILO_AGENT_MANAGEMENT.md](docs/workflows/KILO_AGENT_MANAGEMENT.md) | Kilo agent management |
| [HEALTH_CHECKER_WORKFLOW.md](docs/workflows/HEALTH_CHECKER_WORKFLOW.md) | Health checker workflow |
| [SYNC_ENFORCEMENT_WORKFLOW.md](docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md) | Sync enforcement workflow |
| [SYNC_PROJECTS_WORKFLOW.md](docs/workflows/SYNC_PROJECTS_WORKFLOW.md) | Sync projects workflow |
| [DEV_TRACKER_WORKFLOW.md](docs/workflows/DEV_TRACKER_WORKFLOW.md) | Development tracker workflow |

### Project Context

| Document | Purpose |
|----------|--------|
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
