# Project File Index

**Last Updated:** 2026-05-03

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
| **KILO_CLI_RULES.md** | Kilo CLI spec-contract awareness — full shape/registrar snippet loaded by Kilo via `opencode.json` `instructions:` array. Same content also appears in CLAUDE.md / .windsurfrules / AFCL.md; AGENTS-compact.md carries only a one-line cross-reference (T3-02, 2026-05-16). Propagated to all projects via `scripts/sync_enforcement_to_projects.py` GOVERNANCE_FILES. | Never edit (managed by Fabrik) | Step 3 (ERROR) |
| **opencode.json** | Kilo CLI bootstrap config (schema: `https://opencode.ai/config.json`). `instructions:` array tells Kilo which markdown files to load on context init: `["AGENTS-compact.md", "KILO_CLI_RULES.md"]`. | New rule file added to Kilo's bootstrap | N/A |
| **.windsurf/workflows/registrar-audit.md** | Cascade slash-command `/registrar-audit` — wraps `fabrik audit-registrars` with MISSING/DRIFT handling (T3-02 G-C2, 2026-05-16). | New registrar workflow surfaces | Manual |

---

## docs/ Files

| File | Purpose | Update When | Enforced |
|------|---------|-------------|----------|
| **INDEX.md** | Master file index - auto-generated structure tree in Documentation Structure Map section | Auto-updated by docs_updater.py | Step 7 (auto) |
| **docs/QUICKSTART.md** | Getting started guide - installation, first run, verification | Setup steps change | Step 5 (WARN) |
| **docs/CONFIGURATION.md** | Configuration GUIDE - how to get credentials, architecture context, troubleshooting (NOT variable tables - see .env.example) | New services, config patterns, troubleshooting cases | Step 5 (WARN) |
| **docs/TROUBLESHOOTING.md** | Developer troubleshooting - dependency issues, deployment errors | New complex dependencies | Step 5 (WARN) |
| **docs/BUSINESS_MODEL.md** | Go-to-market + monetization strategy + AUTO-GENERATED project catalog | Manual updates for strategy; AUTO-GENERATED:PROJECTS block syncs via `python scripts/sync_projects.py` or `fabrik scaffold` completion | Step 7 (auto-sync catalog only) |
| **docs/STRATEGIC_BACKLOG.md** | Strategic backlog — Now / Later / Context for deferred work; one row per item with explicit "ready when" trigger | When an item gets deferred from a session OR when a deferred item gains a triggering incident | Manual |

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
├── infrastructure/                  # VPS-level system files (Coolify-era systemd units
│                                    # removed 2026-05-30; directory may be empty)
├── scripts/                         # Automation and tooling scripts
│   ├── final_gate.py                # Mandatory pre-commit quality gate
│   ├── docs_updater.py              # Auto-update docs structure
│   ├── kilo_code_review.py          # Kilo-based code review runner
│   ├── create_pg_dev_db.sh          # PostgreSQL dev database creation helper
│   ├── enforcement/                 # Convention check scripts (check_*.py)
│   └── utils/                       # Shared script utilities
├── specs/                           # YAML specs and planning documents
│   ├── infrastructure/              # Infrastructure service YAML specs
│   │   ├── apprise.yaml             # Apprise notification service — Docker Compose + Traefik config
│   │   ├── glitchtip.yaml           # GlitchTip error tracking (errors.vps1) — declares the existing deployment
│   │   └── n8n.yaml                 # n8n workflow automation — Docker Compose + Traefik config
│   └── n8n-workflows/               # Importable n8n workflow JSON files
│       ├── 01-deploy-notify.json    # Webhook → Code → Apprise on deploy.success / deploy.failure
│       ├── 02-content-notify.json   # Webhook → Code → Apprise on content.published
│       ├── 03-health-alert.json     # Uptime Kuma DOWN/UP → Code → Apprise
│       └── 04-content-trigger.json  # Schedule every 6h → HTTP (Fabrik API) → Apprise
├── sql/                             # Database DDL scripts
├── src/fabrik/                      # Core Fabrik Python package
│   ├── cli.py                       # CLI entry point — includes `fabrik deploy`, `fabrik content publish` (batch brief-drain), `fabrik wp`, `fabrik seo`, `fabrik ai`, `fabrik domain`
│   ├── deploy_router.py             # [reusable] Unified deploy routing — resolve_project_dir(), get_project_type(), route_deploy()
│   ├── notifications.py             # [reusable] Fire-and-forget webhook helpers — notify_deploy(), notify_content() → N8N_WEBHOOK_DEPLOY / N8N_WEBHOOK_CONTENT
│   ├── deploy_validator.py          # [reusable] Deployment readiness validator — 5 checks, validate(), format_warnings()
│   ├── scaffold.py                  # Project scaffolding
│   ├── ai/                          # AI usage/cost tracking: UsageTracker (LLM + GPU rows)
│   ├── api/                         # API layer
│   ├── drivers/                     # External service drivers
│   │   ├── dns.py                   # DNS Manager service client
│   │   ├── coolify.py               # Coolify deployment API client (legacy — pre SSH+Compose migration)
│   │   ├── seo.py                   # SEO service client (keyword research, briefs)
│   │   ├── tco.py                   # TCO client (AI content generation)
│   │   ├── image_broker.py          # Image Broker client (stock images)
│   │   ├── r2.py                    # Cloudflare R2 object storage client
│   │   ├── supabase.py              # Supabase client
│   │   └── uptime_kuma.py           # Uptime Kuma monitoring client
│   ├── models/                      # Data models
│   ├── orchestrator/                # Deployment orchestrator
│   │   ├── __init__.py              # DeploymentOrchestrator
│   │   ├── context.py               # DeploymentContext
│   │   ├── deployer.py              # ServiceDeployer
│   │   ├── exceptions.py            # Custom exceptions
│   │   ├── infrastructure.py        # InfrastructureProvisioner — shape-driven registrar dispatch (postgres, gatus, backrest, glitchtip, grafana, authelia, meilisearch)
│   │   ├── rollback.py              # RollbackManager
│   │   ├── secrets.py               # SecretsManager
│   │   ├── states.py                # DeploymentState
│   │   ├── validator.py             # SpecValidator
│   │   ├── verifier.py              # DeploymentVerifier
│   │   └── sysadmin_tokens.py       # PR3 — per-host Telegram bot-token pool (DR-store) for spoke sysadmin auto-provision; claim/release, no double-assign
│   ├── content/                     # Content publishing package
│   │   ├── __init__.py              # Package marker
│   │   └── orchestrator.py          # Canonical module — re-exports ContentPublisher, PublishResult, PublishSummary, PublishContext
│   └── wordpress/                   # WordPress automation
│       ├── spec_loader.py           # SpecLoader + resolve_spec_path() + load_spec_from_path()
│       ├── resolved_spec.py         # ResolvedSpec + load_spec() (supports site_path override)
│       ├── deployer.py              # SiteDeployer (accepts project_path for folder-based resolution)
│       ├── planner.py               # Planner (accepts project_path for folder-based resolution)
│       ├── handoff.py               # Handoff report generator
│       ├── stages/
│       │   └── verify.py            # Verification stage (post-deploy)
├── templates/                       # Project and document templates
│   ├── modal/                       # Modal serverless Jinja2 App templates (Phase 3.5)
│   │   ├── echo-handler.py.j2       # Minimum-cost smoke template — debian_slim + fastapi[standard]; rendered by ModalClient.create_endpoint()
│   │   └── vllm-openai.py.j2        # vLLM-OpenAI serving template (@app.cls + @modal.fastapi_endpoint, sync mode); takes {model} HF id
│   ├── file-worker/                 # File worker scaffold template
│   │   └── worker/
│   │       └── main.py              # Job processor (uses worker.logger)
│   ├── wordpress/
│   │   ├── CLAUDE.md                   # Claude Code tactical bootstrap for WordPress Factory infrastructure work (cross-refs wordpress rules)
│   │   ├── KILO_CLI_RULES.md           # Kilo CLI tactical bootstrap for WordPress Factory infrastructure work (cross-refs wordpress rules)
│   │   ├── base/
│   │   │   ├── site.yaml.j2            # Jinja2 template for WordPress site-layer spec, rendered at scaffold time
│   │   │   ├── compose.dev.yaml.j2     # Jinja2 template for local dev Docker Compose stack (WSL); uses wp_html shared volume for full WordPress core + nginx access
│   │   │   └── nginx-dev.conf.j2       # Minimal nginx dev config for PHP-FPM passthrough (static, no Jinja vars)
│   ├── saas-skeleton/               # Next.js 14 + Tailwind SaaS starter
│   ├── scaffold/                    # Fabrik scaffold config
│   ├── prompts/                     # Prompt templates for AI commands
│   └── docs/                        # Document templates
├── tests/                           # Test suite
│   ├── test_deploy_validator.py     # deploy_validator.py tests (7 classes, 21 tests)
│   ├── test_watchdog_db_roles.py    # create_watchdog_roles RO/RW provisioning + registrar wiring (28 tests)
│   ├── test_watchdog_governance_mount.py # _push_governance ship + /governance:ro mount + WATCHDOG_GOVERNANCE_MOUNT gate, fail-soft (12 tests)
│   ├── test_kilo_review_validation.py # Kilo review validation tests (validate_review_schema, validate_evidence, validate_plan_coverage)
│   ├── content/                     # Content pipeline tests
│   │   ├── test_seo_client.py       # SEOClient driver tests
│   │   ├── test_tco_client.py       # TCOClient driver tests
│   │   ├── test_image_broker_client.py # ImageBrokerClient driver tests
│   │   ├── test_orchestrator.py     # ContentPublisher orchestrator tests (imports from fabrik.content.orchestrator)
│   │   └── test_cli_content.py      # CLI content command tests (imports from fabrik.content.orchestrator)
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
<!-- AUTO-GENERATED:STRUCTURE v1 | 2026-05-03T21:25 -->
```text
docs/
├── BUSINESS_MODEL.md               # Monetization strategy
├── CONFIGURATION.md                # Environment variables and settings
├── DEPLOYMENT.md                   # How to deploy services to VPS
├── EXTERNAL_SYSTEMS.md             # External service dependencies
├── FAQ.md                          # Frequently asked questions
├── FEATURES.md                     # Feature list
├── LESSONS_LEARNT.md
├── QUICKSTART.md                   # Get Fabrik running in 5 minutes
├── SERVICES.md                     # External services Fabrik depends on
├── TROUBLESHOOTING.md              # Common issues & solutions
├── architecture
│   └── WORDPRESS-MODULE-INTEGRATION.md # WordPress module integration
├── archive                         # Archived and completed documentation
├── development                     # Active development plans and specs
│   ├── PLANS.md                    # Development plans index
│   ├── backlog                     # Deferred residuals (low-severity, fix-on-prompt)
│   │   └── 2026-06-30-kilo-scraper-residuals.md  # post-adversarial-review LOW findings + upstream-fabrik-lib PR (M5)
│   ├── plans                       # Plan documents (YYYY-MM-DD-plan-*.md)
│   │   ├── 2026-04-13-fabrik-control-plane.md
│   │   ├── 2026-04-18-zero-touch-deployment.md
│   │   ├── archived
│   │   ├── issues
│   │   └── previously-planned-fabrik-phases
│   └── wordpress-files-index.md
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
│   ├── WSL2-DNS-FIX.md             # WSL2 DNS resolution fix
│   ├── archive                     # Archived and completed documentation
│   │   ├── coolify-api-reference.md  # Coolify v4 API (historical — Coolify removed 2026-05)
│   │   ├── coolify-migration.md      # Coolify migration procedures (historical)
│   │   └── coolify-stable-aliases.md # UUID-alias watcher (historical)
│   ├── grafana-dashboards-setup.md
│   ├── glitchtip-sdk-integration-setup.md
│   ├── grafana-provisioning-setup.md
│   ├── prometheus-app-metrics-setup.md
│   ├── promtail-noise-filter-setup.md
│   ├── vps-ai-sysadmin.md           # AI sysadmin reference (host process)
│   ├── vps-bootstrap-plan.md        # Bootstrap automation (pointer to scripts/bootstrap/)
│   ├── vps-residue-policy.md        # Residue / hygiene policy
│   ├── vps-status.md                # Current VPS fleet state
│   ├── vps-urls.md                  # All deployed service URLs
│   ├── audit-prompts/               # 8 self-contained AI audit prompts
│   └── vps-complete-inventory.md
├── operations                      # Operational runbooks and VPS state
│   ├── disaster-recovery.md        # Backup and recovery procedures
│   ├── n8n-webhooks.md             # n8n webhook configuration
│   ├── wsl-environment.md          # WSL-side ops: crontab + bashrc chain + project-cron lifecycle + recovery (2026-06-30)
├── owner_ozgur_basak.md            # Owner profile & AI instructions
├── reference                       # Technical reference and module documentation
│   ├── # (Moved — AI taxonomy is now .windsurf/rules/ai/)
│   ├── # (Archived — CRITICAL_RULES.md → docs/archive/2026-06-25-critical-rules-legacy.md)
│   ├── # (Deleted — see .windsurf/rules/core/25-data-postgres.md)
│   ├── DOCUMENTATION_STANDARD.md   # Documentation standards and conventions
│   ├── LOCAL_LLM_INFRASTRUCTURE.md
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
│   ├── fixtures
│   │   └── glitchtip-webhook.json  # Live-captured GlitchTip new-issue webhook envelope (watchdog parser pin)
│   ├── glitchtip-api.md
│   ├── global-gates.md             # Global gate definitions
│   ├── gpu
│   │   ├── Architectural Paradigms in Specialized GPU Infrastructure A Comparative Technical Analysis of TensorDock, RunPod, and Vast.ai for Q2 2026.md
│   │   ├── Choosing ML Framework Templates.md
│   │   ├── The 2026 DePIN GPU Landscape A Technical Audit of Akash, Spheron, and Salad Cloud for Solo PaaS Infrastructure.md
│   │   └── The 2026 Zero-Maintenance AI Inference Landscape A Strategic Analysis for Solo Developers.md
│   ├── health-monitoring.md        # Health monitoring patterns
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
│   ├── provisioner.md
│   ├── research-files                # Gemini deep-research outputs (sources for rule packs)
│   │   ├── AI for Autonomous System Administration.md
│   │   ├── Electron Desktop App Best Practices.md
│   │   ├── Modern GUI Approaches for Chrome Extensions.md
│   │   ├── Modern GUI Approaches for a Lean, Fast, Effective, Low-Confusion SaaS Web App.md
│   │   ├── Modern Mobile GUI Approaches for Android and iOS.md
│   │   ├── Node API File Storage Rules.md
│   │   ├── Node Backend Practices Research 2026.md
│   │   └── cookie-consent-gdpr-2026-research.md
│   ├── research-prompt-preamble-for-agent-rules.md
│   ├── scaffold-type-decision-guide.md
│   ├── scripts.md
│   ├── service-contracts
│   │   └── site-provisioner.md
│   ├── stack.md                    # Technology stack & tools inventory
│   ├── technology-stack-decision-guide.md # Tech decision flowchart
│   ├── template_renderer.md
│   ├── templates.md                # Available deployment templates
│   ├── trueforge-images.md         # Trueforge image catalog
│   ├── windsurf                    # Windsurf IDE optimization
│   │   ├── actively-used-windsurf-extensions.md
│   │   ├── cascade-guide.md
│   │   ├── cascade-models.md
│   │   ├── csharp-cpp-setup.md
│   │   ├── features.md
│   │   ├── overview.md
│   │   └── recommended-extensions.md
│   ├── wordpress                   # WordPress technical docs
│   │   ├── 01 WordPress Production SOP Enhancement.md
│   │   ├── 02 Techinical Implementation Addendum.md
│   │   ├── A perfect systems architect operating a Zero-Ops pipeline.md
│   │   ├── architecture.md         # System architecture overview
│   │   ├── deployment-workflow.md  # WordPress deployment workflow
│   │   ├── fixes.md                # Critical fixes
│   │   ├── pages-idempotency.md    # Page creation idempotency
│   │   ├── plugin-evaluation.md    # WordPress plugin evaluation criteria
│   │   ├── plugin-stack.md         # Curated WordPress plugin stack
│   │   └── site-specification.md   # Site spec YAML format
│   └── wordpress.md                # WordPress module overview
├── traycer
│   ├── AGENT-TIMEOUT-POLICY.md     # Agent timeout policy
│   ├── PLAN_OUTPUT_LOCATION.md     # Plan output location
│   ├── QUICKSTART-MCP-KILO.md      # MCP Kilo quickstart
│   ├── README.md                   # Documentation index (Legacy)
│   ├── TEMPLATE_MAPPING.md         # Template mapping
│   ├── TRAYCER-KILO-AGENTS-GUIDE.md # Traycer Kilo agents guide
│   ├── TRAYCER-KILO-DIRECT-CLI.md  # Traycer Kilo direct CLI
│   ├── epic-kilo-integration.md    # Epic Kilo integration
│   ├── fabrik-workflow.md
│   ├── kilo_selected_agents.md     # Kilo selected agents
│   ├── mcp-kilo-setup-guide.md     # MCP Kilo setup guide
│   ├── templates
│   │   ├── plan_template.md
│   │   ├── task_execution_template.md
│   │   └── verification_template.md
│   ├── traycer-agile-workflow.md   # 8-command Traycer Agile Workflow reference
│   ├── traycer-evaluation.md       # Traycer integration evaluation
│   ├── traycer-managed-development-workflow
│   │   ├── 1-trigger-workflow.md
│   │   ├── 2-epic-brief.md
│   │   ├── 3-core-flows.md
│   │   ├── 4-tech-plan.md
│   │   ├── 5-ticket-breakdown.md
│   │   ├── 6-execute.md
│   │   ├── 7-implementation-validation.md
│   │   ├── 8-revise-requirements.md
│   │   └── 9-cross-artifact-validation.md
│   ├── traycer-refactoring-workflow.md # 4-command Traycer Refactoring Workflow reference
│   └── traycer-yolo-workflow.md
└── workflows                       # Workflow documentation
    ├── DATA_SYNC_WORKFLOW.md
    ├── DEV_TRACKER_WORKFLOW.md     # Development tracker workflow
    ├── DOCUMENTATOR_WORKFLOW.md    # Documentator workflow
    ├── FABRIK_SCAFFOLD_WORKFLOW.md # Fabrik scaffold workflow
    ├── FINAL_GATE_WORKFLOW.md      # Final gate workflow
    ├── HEALTH_CHECKER_WORKFLOW.md  # Health checker workflow
    ├── HEALTH_SUMMARY_WORKFLOW.md
    ├── KILO_AGENT_MANAGEMENT.md    # Kilo agent management
    ├── KILO_CLI_OUTPUT_WORKFLOW.md
    ├── KILO_CONSULT_WORKFLOW.md
    ├── KILO_DISPATCH_WORKFLOW.md
    ├── KILO_REVIEW_WORKFLOW.md     # Kilo review workflow
    ├── SCAFFOLD_STRUCTURE.md
    ├── SYNC_ENFORCEMENT_WORKFLOW.md # Sync enforcement workflow
    ├── SYNC_PROJECTS_WORKFLOW.md   # Sync projects workflow
    └── windsurf-triggered-workflows.md
```
<!-- AUTO-GENERATED:STRUCTURE:END -->

---

## Documentation Navigation

### Quick Start

| Document | Purpose |
|----------|--------|
| [QUICKSTART.md](docs/QUICKSTART.md) | Get Fabrik running in 5 minutes |
| [CONFIGURATION.md](docs/CONFIGURATION.md) | Configuration guide - credentials, architecture, troubleshooting |
| [DEPLOYMENT_ARCHITECTURE.md](docs/DEPLOYMENT_ARCHITECTURE.md) | Deploy code architecture reference |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [FAQ.md](docs/FAQ.md) | Frequently asked questions |
| [.env.example](.env.example) | Environment variable reference (AUTHORITATIVE with inline comments) |

### Core Reference

| Document | Purpose |
|----------|--------|
| [architecture.md](docs/reference/architecture.md) | System architecture, components, data flow |
| [stack.md](docs/reference/stack.md) | Technology stack, APIs, libraries |
| [roadmap.md](docs/archive/roadmap.md) | Original 8-phase build plan (archived — 7/8 phases shipped; superseded by `CHANGELOG.md` + the live docs) |
| [drivers.md](docs/reference/drivers.md) | Fabrik driver API (Coolify, DNS, etc.) |
| [templates.md](docs/reference/templates.md) | Available deployment templates |
| [SaaS-GUI.md](docs/reference/SaaS-GUI.md) | SaaS skeleton template guide |
| [gui-toolchain.md](docs/reference/gui-toolchain.md) | Standing decision — the MCP/skill/tool stack for building high-quality GUIs (Playwright MCP visual loop, shadcn MCP, frontend-design, axe/screenshot gate); verified 2026-07-06 |
| [mobile-gui-research.md](docs/reference/mobile-gui-research.md) | Full RN/Expo mobile verify-stack research (Maestro MCP, Mobile Next MCP, RN a11y, visual regression, CI reality); defers to `mobile-app/80-mobile.md`; verified 2026-07-06 |
| [chrome-ext-gui-research.md](docs/reference/chrome-ext-gui-research.md) | Full MV3 chrome-extension verify-stack research (reuse web loop + Playwright load-extension fixture, axe `bypassCSP`, `size-limit` bundle gate); defers to `chrome-ext/70-chrome-ext.md`; verified 2026-07-07 |
<!-- archived 2026-04-28: SCAFFOLD_TO_DEPLOY_INTEGRATION.md (HISTORICAL gap analysis), DEPLOY_TEMPLATE_AUDIT_2026-04-10.md (HISTORICAL audit), POSTGRESQL_LOCAL_DEV_*.md ×4 (impl shipped, see CHANGELOG line 4041); see docs/archive/2026-04-28-* and docs/DEPLOYMENT_ARCHITECTURE.md for current canonical reference -->
| [DOCUMENTATION_STANDARD.md](docs/reference/DOCUMENTATION_STANDARD.md) | Documentation standards and conventions |
| [global-gates.md](docs/reference/global-gates.md) | Global gate definitions |

**SaaS Template:** `templates/saas-skeleton/` — Next.js + Tailwind + SSE streaming for AI chat integration

### Phase Documentation

| Phase | Status | Document |
|-------|--------|----------|
| **Phase 1: Foundation** | Complete | [architecture.md](docs/reference/architecture.md) |
| **Phase 1b: Cloud Infrastructure** | Complete | [DEPLOYMENT_ARCHITECTURE.md](docs/DEPLOYMENT_ARCHITECTURE.md) |
| **Phase 1c: Cloudflare DNS** | Complete | [SERVICES.md](docs/SERVICES.md) |
| **Phase 1d: WordPress Automation** | Moved out 2026-05-30 | WordPress deployment + lifecycle moved to the standalone `/opt/wpf` project (`wpf` CLI) |

### Operations

| Document | Purpose |
|----------|--------|
| [vps-status.md](docs/infrastructure/vps-status.md) | Current VPS state and configuration |
| [vps-urls.md](docs/infrastructure/vps-urls.md) | All deployed service URLs |
| [disaster-recovery.md](docs/operations/disaster-recovery.md) | Backup and recovery procedures |
<!-- duplicati-setup.md archived 2026-04-28; Backrest is the live backup tool — see backup.vps1.ocoron.com and AGENTS.md -->
| [coolify-migration.md](docs/infrastructure/archive/coolify-migration.md) | Coolify migration procedures |

### Workflows

| Document | Purpose |
|----------|--------|
| [docs/workflows/](docs/workflows/) | Full workflow set — scaffold, deploy, data-sync, Traycer/Kilo, etc. |

### WordPress & Guides (moved out)

WordPress deployment + lifecycle, the WordPress reference docs (`docs/reference/wordpress/`),
and the old `docs/guides/` set were **removed from this repo when WordPress moved to the
standalone `/opt/wpf` project (2026-05-30)**. See `/opt/wpf/AGENTS.md`. Fabrik retains only
the `wordpress` **scaffold type** (`fabrik scaffold --type wordpress`).

### Quality Gates & Code Review

| Document | Purpose |
|----------|--------|
| [AGENTS.md](AGENTS.md) | Traycer orchestrator contract (planning constraints, rule-pack registry, stack defaults) |
| [kilo_code_review.py](scripts/kilo_code_review.py) | Kilo CLI code review runner |
| [kilo_docs_enforcer.py](scripts/kilo_docs_enforcer.py) | AI documentation enforcement |
| [final_gate.py](scripts/final_gate.py) | Pre-commit quality gate (33 enforcement scripts) |
| [proof_run.py](scripts/proof_run.py) | Live-deploy proof harness — scaffolds → pushes → `fabrik apply` → curl-verifies every type in `SCAFFOLD_TYPES` against the production VPS. Pulls Coolify build logs into `proof-logs/<type>-<ts>-build.log`. Supports `--keep-on-failure` and direct-Cloudflare DNS-cleanup fallback. Run quarterly + after any change to verifier/validator/spec_generator/scaffolder. See `PROOF.md` for the latest run output and `CHANGELOG.md [Unreleased]` B23–B46 for the 22 defects it surfaced on first execution. |
| [inject_deploy_resources.py](scripts/inject_deploy_resources.py) | F5 helper — idempotent string-precise injection of `deploy.resources.limits` into a single-service `compose.yaml`. Used to backfill the 7 Coolify Applications (git-sourced Fabrik microservices). No-op if the deploy block is already present. Usage: `python3 scripts/inject_deploy_resources.py <compose.yaml> <memory> <cpus>`. |
| [coolify_services_f5.py](scripts/coolify_services_f5.py) | F5 helper — injects `deploy.resources.limits` into the 12 Coolify Services (one-click stacks). GETs each service via `/api/v1/services/<uuid>`, edits `docker_compose_raw` with string-precise injection (no YAML round-trip), PATCHes back **base64-encoded** (API requirement). Memory values mirror `vps_apply_limits.sh`. Supports `--dry-run`, `--apply`, `--only <name>`. Idempotent. See Lesson 62. |
| [src/fabrik/dev_tools.py](src/fabrik/dev_tools.py) | T3-03 local-dev helpers used by `fabrik review` / `fabrik dev` / `fabrik logs --local`. `find_spec`, `build_review_bundle`, `save_review_bundle`, `run_dev_compose`, `run_local_logs`. Each compose runner accepts an injectable `runner` callable so tests can mock docker. Pure module — no orchestrator side effects. |
| [tests/test_dev_tools.py](tests/test_dev_tools.py) | 20 tests for T3-03 — `TestReviewBundle` (9: find_spec local/none/central-fallback, build_review_bundle with/without spec/preplan, save default + --out, CLI emits summary + writes bundle), `TestDevCompose` (3: -1 when compose missing, runner argv contract, CLI exit-1 path), `TestLocalLogs` (5: -1 when compose missing, runner with -f + service, bare -f only when follow, CLI exit-1, remote-requires-SERVICE exit-2), Smoke (3: --help exits 0 for review/dev/logs). All pass. |
| [tests/test_postgres_registry.py](tests/test_postgres_registry.py) | 12 tests for T4-01 G-J4 — `TestListAllocations` (3: payload parse, empty-file → empty-shape, missing-file → empty-shape), `TestRegisterAllocation` (2: append preserves siblings, dry-run skips tee/mv), `TestUnregisterAllocation` (2: removes entry, missing-entry no-op), `TestAuditPostgresDrift` (5: four-quadrant DB×registry classification + registry-read-failure fallback). All SSH boundary mocked. |
| [tests/test_destroy_use_state.py](tests/test_destroy_use_state.py) | 16 tests for T4-02 G-F4 `fabrik destroy --use-state` — `TestDataBearingGuard` (3: refuses without `--drop-data`, proceeds with it, proceeds when no data-bearing), `TestReverseOrderDispatch` (4: only state-registered handlers invoked, canonical reverse order verified `prometheus → meilisearch → authelia → glitchtip → backrest → gatus → redis → postgres → coolify → dns → files`, grafana skipped, handler exception non-aborting), `TestPhase2NonRegistrars` (4: coolify always, dns/files gating), `TestPrimaryPathSpecDrift` (1: SC-3 — state-A destroy after spec drift to B), `TestArchiveOnSuccess` (2: archive fires on real run only), `TestCliUseState` (2: missing-state-file clean error, `--use-state + --partial` mutually-exclusive). |
| [src/fabrik/portability.py](src/fabrik/portability.py) | T4-03 G-J2 — `export_bundle` / `import_bundle` for cross-VPS portability. Helpers: `_strip_uuids` (recursive UUID + 14 sensitive-key removal + bare 24-alphanum string blanking), `_redact_env_keys` (key names only, never reads past `=`), `_collect_*` for specs/state/coolify/monitoring/authelia/backrest. Bundle layout per pack §28. **Import is shipped untested** — `dry_run=True` default; real-run path is a documented stub (vps2 roundtrip deferred). |
| [scripts/audit_all_registrars.py](scripts/audit_all_registrars.py) | T4-04 G-G5 — hourly WSL-side cron job: walks `specs/services/*.yaml`, calls `fabrik.audit.audit_all`, emits Prom-text gauge metrics (`fabrik_audit_drift_total`, `fabrik_audit_status`) to `/tmp/fabrik-audit-metrics.txt`, pushes via SSH to the loopback-bound pushgateway (`http://localhost:9091/metrics/job/fabrik-audit`). Pairs with `/opt/monitoring/configs/prometheus/rules/fabrik-drift.yml` + Alertmanager route `alert_class=registrar_drift` → existing `telegram` receiver. Crontab pattern matches T2-03's G-G4 audit_authelia_gates.py. |
| [tests/test_portability.py](tests/test_portability.py) | 23 tests for T4-03 G-J2 — schema invariant (1 carried from T4-02), `TestUuidStripping` (4: top-level/nested/bare-string/preservation), `TestSecretsRedaction` (4: key-names-only, empty/missing/malformed handling), `TestCollectLocal` (2: specs + state with coolify_uuid stripped), `TestExportBundle` (5: tarball structure + **byte-scan no-plaintext-secrets** + **recursive no-Coolify-UUIDs** + manifest), `TestImportBundle` (3: dry-run plan, --apply stub, missing-bundle), `TestExportCli` (4: helps + end-to-end + Click path validation). |
| [check_print_ban.py](scripts/enforcement/check_print_ban.py) | Tier 1: Ban print()/console.log() in production code [reusable] |
| [check_synced_unmodified.py](scripts/enforcement/check_synced_unmodified.py) | Tier 1: Fail the gate when a Fabrik-synced file drifts from the `/opt/fabrik` source (centrally-managed files must not be edited locally). Self-exempts in fabrik; skips when fabrik absent. |
| [check_doc_sync.py](scripts/enforcement/check_doc_sync.py) | Tier 1+2: Unified Doc Sync Matrix gate — fails when a trigger file changed but its doc wasn't touched. ERROR: CHANGELOG/CONFIGURATION/schema; WARN: INDEX/QUICKSTART/FEATURES/PORTS. Consolidates check_changelog/index_md/configuration_md/openapi_sync. |
| [check_script_headers.py](scripts/enforcement/check_script_headers.py) | Tier 1 (WARN): every staged `scripts/**/*.py` declares a `# AFTER-EDIT:` coupling header (files to update, or `none`); warns on a missing header or a listed coupled file not also staged. Touch-on-change; never blocks. |
| [select_rules.py](scripts/select_rules.py) | Plan-time: lists the `.windsurf/rules` packs applicable to a project (ACTIVE = glob matches own source; AVAILABLE = read if work touches the domain), from pack frontmatter. Run before planning to select the binding ruleset. |
| [test_select_rules.py](tests/test_select_rules.py) | 4 tests for select_rules — frontmatter parse, ACTIVE/AVAILABLE split, bundled-templates excluded from matching, project type read. |
| [test_check_doc_sync.py](tests/test_check_doc_sync.py) | 7 tests for the Doc Sync Matrix gate (significant-code→CHANGELOG block, .env.example→CONFIGURATION block, file-add→INDEX warn, compose→PORTS warn, docs/tests-only pass). |
| [test_check_print_ban.py](tests/test_check_print_ban.py) | 6 tests for `is_template_generator` marker matching (directive comment matches; string-literal / prose-comment / no-marker / past-line-20 don't; missing file → False). |
| [test_check_schema_sync.py](tests/test_check_schema_sync.py) | 5 tests for the data-contract drift WARN (fires on schema change + stale contract; silent when contract staged / no schema change / no contract file; `.py` migration counts). |
| [check_convergence.py](scripts/enforcement/check_convergence.py) | All tiers: a changed `plans/`/`reviews/` markdown claiming convergence must embed its proof (Evidence + `path:line` per phase + fenced cmd-output; reviews embed a `final_gate --json` success). Inert when no such artifact changed. |
| [test_check_convergence.py](tests/test_check_convergence.py) | 6 tests for the convergence gate — compliant plan/review pass, claim-without-evidence fails, non-claim ignored, no-artifact passes. |
| [convergence-prompts.md](docs/reference/convergence-prompts.md) | The 3 canonical direct-agent prompts (PLAN / CODE REVIEW / DOCS), each emitting the artifact its gate inspects. |
| [final_gate_stop.py](.claude/hooks/final_gate_stop.py) | Claude Code `SessionStart` (`--baseline`) + `Stop` hooks — Stop blocks end-of-turn only on gate failures the session INTRODUCED (current − SessionStart baseline), so inherited project debt never traps the agent. Fail-open, loop-capped, scoped. Wired in `.claude/settings.json`. |
| [test_final_gate_stop_hook.py](tests/test_final_gate_stop_hook.py) | 10 tests: `decide()` loop-guard + baseline-diff integration (inherited→allow, new failure→block, missing-baseline→fail-open, green→allow, --baseline writes snapshot). |
| [fabrik_synced_manifest.py](scripts/fabrik_synced_manifest.py) | Single source of truth for the centrally-distributed file set — consumed by `sync_enforcement_to_projects.py`, the `scaffold.py` `.gitignore` block, and `check_synced_unmodified.py`. |
| [test_synced_manifest.py](tests/test_synced_manifest.py) | 5 tests for `fabrik_synced_manifest` — category coverage, compiled-bytecode exclusion, source mapping, PORTS.md seed-exemption, gitignore grouping. |
| [check_user_guide.py](scripts/enforcement/check_user_guide.py) | Tier 2: Verify docs/user-guide/ when has_user_guide: true [reusable] |
| [check_reusable_modules.py](scripts/enforcement/check_reusable_modules.py) | Tier 2 advisory: Check [reusable] tags in INDEX.md [reusable] |
| [test_cross_cutting_enforcement.py](tests/test_cross_cutting_enforcement.py) | 31 tests for cross-cutting enforcement scripts |
| [test_backfill_has_user_guide.py](tests/test_backfill_has_user_guide.py) | 9 tests for has_user_guide backfill in fix_project() |
| [test_seo_client.py](tests/content/test_seo_client.py) | 7 tests for SEOClient driver (domain lookup, briefs lifecycle) |
| [test_tco_client.py](tests/content/test_tco_client.py) | 2 tests for TCOClient driver (generate_from_brief, error propagation) |
| [test_image_broker_client.py](tests/content/test_image_broker_client.py) | 3 tests for ImageBrokerClient driver (auto_download success/failure) |
| [test_orchestrator.py](tests/content/test_orchestrator.py) | Tests for the content-publisher orchestrator (publish_page legacy + batch brief-drain). NOTE: the `content_publisher.py` / `content/orchestrator.py` modules were removed with the WordPress→/opt/wpf move 2026-05-30. |
| [test_cli_content.py](tests/content/test_cli_content.py) | 4 tests for `fabrik content publish` CLI command (help, unknown domain ValueError, dry-run, connection error) |
| [test_saas_logger.py](tests/test_saas_logger.py) | 5 tests for saas-skeleton pino logger scaffold generation |
| [test_scaffold_logging.py](tests/test_scaffold_logging.py) | Tests for python-api + chrome-extension scaffold logging (logger.py, middleware.py, correlation ID) |
| **src/fabrik/spec_generator.py** | [reusable] Spec generation and project context extraction — SPEC_ENABLED_TYPES, SECRET_PATTERNS, extract_project_context(), generate_spec(), generate_and_save_spec() |
| [test_spec_generator.py](tests/test_spec_generator.py) | 40 tests for spec_generator (constants, _is_secret, compose/env parsing, context extraction, spec generation, save round-trip) |
| [test_scaffold_spec_generation.py](tests/test_scaffold_spec_generation.py) | Tests for scaffold spec auto-generation hook and fabrik new --from-project flag | When scaffold.py or cli.py new/scaffold commands change | N/A |
| [test_spec_loader.py](tests/test_spec_loader.py) | 7 tests for T1-02 G-B1a template-defaults deep-merge (happy-path inheritance, spec-wins-on-conflict, nested-partial-override, proxy-pattern infra.postgres override survives merge, missing-template tolerance, `_deep_merge` unit edge cases, primary-path load_spec→resolve_applicability integration) |
| **src/fabrik/locks_local.py** | T2-01 G-F2 — project-scoped fcntl-based `file_lock()` context manager for WSL-side Python orchestration concurrency (NOT [reusable]; project-internal, imports fabrik.config) |
| **src/fabrik/state.py** | T2-01 G-F3 — per-deploy state file persistence under `.fabrik/state/<id>.json`; `save()`, `load()`, `archive_destroyed()`, `find_by_spec_id()`, `DATA_BEARING_REGISTRARS` constant. Project-scoped. |
| **src/fabrik/audit.py** | T2-02 G-G2 — per-registrar drift audit module; 9 `audit_<name>` functions mirroring each driver's transport (SSH for 7, HTTP/requests for glitchtip, n/a for grafana); `audit_all(spec)` aggregator never raises; `AuditResult` dataclass with `status ∈ {present, missing, drift, n/a, override, unknown}`. Project-scoped. |
| **specs/verification/registrars.yaml** | T2-02 G-G3 — verification spec enabling `fabrik verify <domain> --spec registrars`; uses the new `registrars_present` check type in `PostconditionChecker`. |
| [test_locks_local.py](tests/test_locks_local.py) | 7 tests for locks_local (basic acquire/release, two-thread serialization, timeout, exception releases lock, name sanitization, different names don't block) |
| [test_state.py](tests/test_state.py) | 13 tests for state.py (8-field schema, data_bearing auto-stamping, atomic-write no tmp leak, load round-trip, archive_destroyed timestamp move, apply→persist→destroy→archive lifecycle, git_sha fallback) |
| [test_audit.py](tests/test_audit.py) | 28 tests for audit.py — all 9 per-registrar audits (status mapping, shape n/a, ssh-failure unknown), audit_all aggregator robustness (never raises), AuditResult serialization, SC-1/SC-3 audit→reconcile→re-audit lifecycle roundtrip |
| [test_partial_destroy.py](tests/test_partial_destroy.py) | 10 tests for HANDLER_ARGS/HANDLER_FUNCS module-level export contract (T4-02 dependency), key-set parity, lambda-signature arity match via `inspect.signature`, authelia's domain-not-id contract, drop_data shape, CLI integration tests for `fabrik destroy --partial` (single, multiple, unknown registrar) |
| [test_final_gate_pydantic.py](tests/test_final_gate_pydantic.py) | 7 tests for T2-03 G-E2 — `scripts/final_gate.py:471` pydantic Spec validation on `specs/services/*.yaml` (valid spec passes, invalid enum fails, int env fails, missing-required fails, live-gate regression net, non-spec yaml unaffected, load_spec helper importable) |
| **src/fabrik/orchestrator/coolify_alias.py** | T2-04 G-J3 — Coolify alias-watcher write side; `add_alias(coolify_uuid, alias)` writes to `/opt/coolify-alias-watcher/aliases.json` (atomic tee → chown+chmod+mv) and restarts watcher service. Restart-not-reload (unit has no ExecReload). Project-scoped. |
| **ops/coolify-alias-watcher/aliases.json** | T2-04 G-J3 — canonical data file (4 baseline aliases: meilisearch, gotenberg, browserless, glitchtip-web). WSL mirror of `/opt/coolify-alias-watcher/aliases.json` on VPS. Keys are 24-char UUID PREFIXES (no timestamp suffix). |
| **ops/coolify-alias-watcher/watcher.sh** | T2-04 G-J3 — refactored from hardcoded `declare -A ALIASES=(...)` to jq-based load from aliases.json. WSL mirror of `/opt/coolify-alias-watcher/watcher.sh` on VPS. |
| [test_coolify_alias.py](tests/test_coolify_alias.py) | 12 tests for coolify_alias.add_alias (atomic-write contract, dry-run, no-op when already matches, ssh-failure fallback, malformed JSON, sort-keys, constants). All ssh mocked. |
| [test_sync_projects_state.py](tests/test_sync_projects_state.py) | 8 tests for T2-04 G-J1 — `scripts/sync_projects.py::_load_deploy_state` (never/applied/fabrik-prefix-fallback/malformed paths), Project dataclass deploy block round-trip, SC-2 primary path: apply→state→projects.yaml roundtrip end-to-end. |
| **src/fabrik/preplan.py** | T3-01 G-A1+A3 — preplan authoring + ingestion. `create_preplan(slug, date)` renders `templates/preplan/preplan.md.j2` to `docs/preplans/<date>-<slug>.md`; `parse_preplan(path) -> Preplan` extracts 9 sections (idea/type/shape/deps/domain/criteria/scope/questions/notes). Slug + date validators. Project-scoped. |
| **templates/preplan/preplan.md.j2** | T3-01 G-A1 — Jinja2 preplan template with 9 sections, embeds VPS1-inventory cheat-sheet (postgres-main, redis-main, X-Internal-Token, /health bypass, /metrics, GlitchTip DSN) in the Notes section so the preplan stays grounded. |
| **docs/preplans/** | T3-01 G-A2 — directory for captured project intent. `README.md` documents filename convention (`<YYYY-MM-DD>-<slug>.md`), 4-stage lifecycle (author/refine/hand-off/archive), and the full Fabrik pipeline overview. |
| [test_preplan.py](tests/test_preplan.py) | 16 tests for T3-01 — `create_preplan` (creates dated file / template substitution / refuses overwrite / slug-validation / date-validation), `parse_preplan` (fresh template / missing file / invalid type / deps table / bullet list filtering), `_layer_preplan_into_project` (copy / 4-guardrail injection / partial guardrails / idempotency / none-no-op), CLI surface check (`fabrik preplan new` works, `fabrik preplan-new` does NOT — catches @cli.command vs @cli.group BLOCKER FIX). |

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
| [BUSINESS_MODEL.md](docs/BUSINESS_MODEL.md) | Live project inventory (auto-generated by `fabrik projects` / `sync_projects.py`; the old hand-maintained `project-registry.md` is archived) |

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

- `scripts/generate_kilo_agents.py` - Generates tier-based agent scripts from the agent manifest
- `scripts/kilo_code_review.py` - Code review (Step 4 in the workflow)
- `scripts/kilo_model_sync.py` - Syncs the model catalog + pricing
- `scripts/kilo-benchmarks/` - Benchmark-driven agent-selection subsystem (`agent_selector.py`, `compute_assignments.py`, `db_models.py`, embedding assignment, OpenRouter category routing: `classify_ai_category.py`, `category_selector.py`, `category_route_mapper.py`, `category_export_markdown.py`, `update_gateway_counts.py`, `seed_direct_vendors.py` + `ai_category_configs.yaml`). Direct-vendor pricing plan also lives here: `direct_vendor_parsers/` (vendor-specific HTML parsers — assemblyai, anthropic, cartesia, deepgram, openai, soniox, speechmatics, subscription_monitor), `direct_vendor_pricing_registry.yaml`, `fetch_direct_vendor_prices.py` orchestrator, `audit_direct_vendor_freshness.py` quarterly helper.

### Data Files (AUTHORITATIVE)

- `scripts/kilo_47_agents_final.json` - Primary agent manifest (47 agents)
- `scripts/kilo_all_models.json` - Complete model catalog
- `scripts/kilo_embeddings_final.json` - Embedding-based model/role assignment data
- `scripts/kilo_openrouter_routes_final.json` - OpenRouter category route assignments per `.windsurf/rules/ai/NN-*.md` pack (mirror of embeddings_final, daily refresh)
- `scripts/kilo-benchmarks/models_browser.html` - Single-file searchable browser of every chat + embedding model in `kilo_agents.db` (484 models). Generated by `export_models_browser.py`; open in any browser, no server.
- `scripts/kilo-benchmarks/verify_openrouter_catalog.py` - Cross-checks every active DB row against `https://openrouter.ai/api/v1/models` (live) AND `kilo models --verbose`. Reports pricing/context/capability/name/description discrepancies, marks delisted-upstream rows `status='deprecated'`, ingests new rows, tags via_openrouter/via_kilo gateways. Runs daily; on-demand via `--apply --ingest-new`.
- `scripts/kilo-benchmarks/scrape_openrouter_endpoints.py` - Nightly fetch of OR's per-model `/api/v1/models/<slug>/endpoints` for every active `via_openrouter=1` row. Stores the full endpoint list + the min-price in-service provider name (DeepInfra/Groq/Together/etc.) into `cheapest_provider`/`cheapest_provider_price`/`cheapest_provider_quant`. Powers the browser's "Cheapest" column so operators know which OR provider to pin via `provider.only=[...]`. ~340 API calls @ 4/s = ~90s.
- `scripts/kilo-benchmarks/audit_ui_values.py` - Systematic 5-phase audit that cross-checks every value the browser surfaces against its live upstream (OR /api/v1/models, OR /endpoints, Kilo CLI, benchmark caches). Reports drifts by field-type + verifier-tracked vs verifier-untracked bucket. Wired into `daily_refresh.sh` so any future upstream drift trips the log immediately instead of accumulating. Now also cross-checks capability flags (`has_vision`/`has_tools`/`has_reasoning`) — omission caught 2026-07-01 when the DB had `has_reasoning=0` on models that OR reports as thinking-capable via `supported_parameters`.
- `scripts/kilo-benchmarks/check_model_live.py` - **Truth-oracle CLI for a single model ID.** Fetches live OR `/api/v1/models`, OR `/models/<slug>/endpoints`, and Kilo `kilo models --verbose` and diffs each against the DB row. Emits a machine-friendly verdict (`safe_to_recommend` + `reasoning_state`) and human-readable per-source dump. Use before quoting ANY specific model ID's price / context / capability flag — DB alone is not trustable (delisted zombies, capability-flag heuristic bugs). `--list-candidates` prints a verified shortlist of truly non-thinking models straight from live OR (no reasoning param at all). Built 2026-07-01 after the operator caught a stale `x-ai/grok-4-fast` recommendation.
- `scripts/kilo-benchmarks/blocked_writes.py` - **Direct-vendor blocked-write review queue.** `record_blocked_write(vendor, model_id, parsed, db, reason, raw_text, *, today=None) -> Path` — appends to `cache/blocked_writes/YYYY-MM-DD.md`. Idempotent per `(vendor, id, parsed, db, day)` tuple; escapes `|`/newlines/tabs so raw text can't corrupt the table. Wired into `fetch_direct_vendor_prices.py`'s `refused_diff` alert path (guarded import — defense-in-depth). Landed 2026-07-08 as plan-4 Phase D.
- `scripts/kilo-benchmarks/tools/sanitize_kilo_config.py` - **Kilo CLI opencode.json sanitizer.** Idempotently strips stale `subagent_model` + `subagent_variant_overrides` keys that Kilo v7.0.33+ rejects with `Configuration is invalid`. Backs up the config before mutating. Used by plan-4 Phase B — before the fix `kilo models --verbose` returned 0 catalog entries silently, killing the dual-routing verification chain. Landed 2026-07-08.
- `scripts/kilo-benchmarks/audit_pipeline.py` - **Model-Discovery Pipeline Audit helpers.** `_load_ingestor_findings` + `_load_findings_generic` + `_render_findings_md` + `_verify_tier_split` + `_dispatch_pool_audit` (thin wrapper over `libs.subagents.run_agents` + `record_agent_run` per result) + `_run_inline_ingestor_scan` (deterministic grep-based fallback) + `_render_consolidated_report`. Consumes the 6 phase MDs at `docs/development/audits/phase-{a,b,c,d,e}-*-findings.md` and emits the operator-facing `docs/development/audits/2026-07-08-model-pipeline-audit.md`. Landed 2026-07-08 as Phase A-F of the audit plan.
- `docs/reference/kilo/AI_VENDOR_ACCESS.md` - **Hand-authored vendor-access catalog.** Single source of truth for which vendors the operator can call today (LLM gateways, specialty vendors, direct-API-need-signup, web-only accounts). 24 rows across 4 tables; Status: ✅ accessible, ⚠️ accessible-low-balance, ❌ needs-signup / deprecated / web-only. Parsed by `seed_specialty_catalog.py` to set `agents.reachable_with_existing_keys`. Governance-synced to every project via `fabrik_synced_manifest.py:69`. Landed 2026-07-07 as Phase A of best-model-suggester.
- `scripts/kilo-benchmarks/seed_specialty_catalog.py` - **Phase A seeder for best-model-suggester.** Reads `AI_VENDOR_ACCESS.md`, migrates `agents` with two columns (`quality_elo REAL`, `reachable_with_existing_keys INTEGER NOT NULL DEFAULT 0`), seeds missing TTS/STT/translation/image_gen rows from `specialty_pricing.PRICING`, and backfills `quality_elo` for 4 image_gen rows from live Arena Elos (ArtificialAnalysis image + HF TTS Arena V2). Idempotent (PRAGMA-guarded migration, INSERT OR IGNORE seeding). Landed 2026-07-07.
- `scripts/kilo-benchmarks/suggest_model.py` - **Phase B Pareto-ranked model suggester CLI.** `--task {tts|stt|translation|image_gen|music_gen|video_gen|llm|coding_llm}`, `--volume-{chars,minutes,images}`, `--top`, `--json`. Exit 0 on candidates, 1 on empty pool (`NO DATA for task=<t> under accessible vendors`), 2 on missing volume flag. Normalizes mixed pricing_unit (image vs M-tokens) via `_normalize_cost`; ranks by (cost ↑, quality_elo ↓) Pareto frontier. Landed 2026-07-07 as Phase B of best-model-suggester.
- `scripts/kilo-benchmarks/rank_{tts,stt,translation,image_gen}.py` - **Phase B per-task rankers.** Pattern-clone of `rank_coding_subagents.py`'s atomic-write layout; each queries `agents WHERE service_type=<task> AND reachable_with_existing_keys=1` via `suggest_model._rank_service_type`, renders top-10 markdown table, atomic-writes to `docs/reference/kilo/{TTS,STT,TRANSLATION,IMAGE_GEN}_SELECTION.md`. Wired into `daily_refresh.sh` steps 8c–8f (non-fatal). Landed 2026-07-07.
- `docs/reference/kilo/{TTS,STT,TRANSLATION,IMAGE_GEN}_SELECTION.md` - **Auto-generated per-task selection docs.** `Last refresh: YYYY-MM-DD` header + Pareto-ranked table (up to 10 rows). Governance-synced to every project via `fabrik_synced_manifest.py:69`. Emitted by `rank_{tts,stt,translation,image_gen}.py` daily. Landed 2026-07-07.
- `scripts/kilo-benchmarks/seed_watchlist_and_gpu.py` - **Phase E seeder for watch-list vendors + GPU providers.** Creates `gpu_providers` table (id, provider, gpu_sku, tier, usd_per_hour, usd_per_second, cold_start_s, reachable_with_existing_keys, signup_trigger, last_verified, notes) + adds `agents.signup_trigger TEXT`. Seeds 4 watch-list LLM rows (Together/Hyperbolic/Cerebras/Novita, all reachable=0) + 7 GPU rows (Vast/RunPod/Modal reachable=1 matches gpu-rent driver set, Hyperbolic/Novita reachable=0). Idempotent. Landed 2026-07-07.
- `scripts/kilo-benchmarks/scrape_gpu_prices.py` - **Phase E GPU price refresher.** Uses vendored `libs/web_scrape` (fail-soft: any network error leaves DB prices intact). `--dry-run --json` reads current DB snapshot without touching the network — safe for CI + the E.4 plan gate. Landed 2026-07-07 (live scrape path is a stub — full HTML parsing per-vendor is a follow-up).
- `scripts/kilo-benchmarks/rank_candidate_signups.py` - **Phase E candidate-signups ranker.** Union-selects `reachable_with_existing_keys=0` rows across `agents` + `gpu_providers`, ranks by cost, emits `docs/reference/kilo/CANDIDATE_SIGNUPS.md`. Pattern-clones `rank_coding_subagents.py`'s atomic-write layout. Landed 2026-07-07.
- `docs/reference/kilo/CANDIDATE_SIGNUPS.md` - **Auto-generated candidate-signups doc.** Watch-list vendors not currently reachable, ranked by cost with `signup_trigger` note per row. Governance-synced. Emitted by `rank_candidate_signups.py` daily. Landed 2026-07-07.
- `scripts/kilo-benchmarks/libs/web_scrape/` - **Vendored from `/opt/fabrik-lib/web-scrape/`** (Phase E of best-model-suggester). Provides `WebScraper` + `extract_nextjs_data` for GPU price scraping. Local UP017 modernization (`timezone.utc` → `UTC`) applied; upstream should mirror. Landed 2026-07-07.
- `scripts/kilo-benchmarks/specialty_clients/openrouter_image_gen.py` - **Bench client for `via='openrouter'` image_gen rows** (best-model-suggester specialty_clients gap fix). Calls OpenRouter's OpenAI-compatible chat endpoint with `modalities=["image","text"]` and returns `{perf_seconds, cost_usd, error}` — used by `microbench_specialty._dispatch` for openai/gpt-*-image and google/gemini-*-image rows that don't have a direct-vendor client. Handles transport errors, HTTP 4xx/5xx, vendor errors surfaced in 200 body, and empty responses. Cost falls back to `PRICING[id][per_image]` when the response omits `usage.total_cost`. Landed 2026-07-07.
- `scripts/kilo-benchmarks/scrape_groq_speeds.py` - Daily scraper for Groq's `groq.com/pricing` HTML table (tokens/sec on their LPU per model). BeautifulSoup-parses the `<table>` row set, uses an explicit `GROQ_TO_OR_ID` map for Groq's ~8-model stable catalog (avoids fuzzy-canonicalizer false-positives from Groq's `Versatile`/`Instant`/`17Bx16E`/`128k` variant tokens), writes `speed_source="groq_lpu (pin required)"`. Authority precedence enforced in the WHERE clause: `manual_override > own_microbench* > artificialanalysis.ai* > groq_lpu* > NULL`. Landed 2026-07-02 as Phase 1 of the speed-coverage plan.
- `scripts/kilo-benchmarks/microbench_or_models.py` - Weekly (Sundays UTC) microbench of every active OR-routed LLM without prior Speed data. Streams `/api/v1/chat/completions` with a fixed 200-word prompt, measures TTFT (time to first non-empty content chunk) + TPS (`usage.completion_tokens / (t_last_content_chunk - t_first_content_chunk)`), takes the median of 3 runs, writes `speed_source="own_microbench YYYY-MM-DD"`. Cost-capped at $10/run via OR's actual `usage.cost` (returned when `usage.include=true`); realistic run cost ~$0.60 for 195 rows. Idempotent — rows benched < 30d ago are skipped. Non-fatal on missing `OPENROUTER_API_KEY`. Every run appends a JSONL summary to `cache/microbench_log.jsonl`. Landed 2026-07-02 as Phase 2 of the speed-coverage plan.
- `scripts/kilo-benchmarks/microbench_specialty.py` - Weekly (Sundays UTC) per-generation latency bench for the 53 non-LLM rows (`image_gen`/`tts`/`music_gen`/`stt`/`translation`). Dispatches by row's `id` prefix + `service_type` to one of 7 per-provider clients in `specialty_clients/`. Writes `perf_seconds` (seconds-per-generation, distinct axis from `output_tokens_per_sec`). Cost-capped at $10 hard / $2.50 soft via per-row `PRICING` lookup + running sum; honors `Retry-After` hints between retries. Post-run precedence guard fails with `[BENCH-QA-FAIL]` if any LLM row got a `*_direct` `speed_source` today. Landed 2026-07-03 as Phase B of the full-coverage plan.
- `scripts/kilo-benchmarks/specialty_pricing.py` - Provider pricing snapshot (55 entries, re-verify quarterly). Feeds `microbench_specialty.py` cost-cap arithmetic. Every active non-LLM row in `agents` must appear here — the `test_pricing_table_covers_all_active_specialty_rows` drift-guard fails otherwise.
- `scripts/kilo-benchmarks/specialty_clients/` - 7 per-provider bench clients (`bfl_via_fal`, `recraft`, `replicate`, `elevenlabs_tts`, `elevenlabs_sfx`, `openai_whisper`, `dashscope_translation`). Each exposes `bench_one(model_id, api_key) -> {perf_seconds, cost_usd, error}`. Grounded API docstrings at the top of each file (live-verified 2026-07-03).
- `scripts/kilo-benchmarks/add_perf_seconds_column.py` - Idempotent one-off inline migration for the `agents.perf_seconds REAL` column (sqlite has no `IF NOT EXISTS` for columns; script guards via `PRAGMA table_info`). Also called from `microbench_specialty.py::run_specialty()` so a fresh clone works without a manual migration step.
- `scripts/kilo-benchmarks/rank_coding_subagents.py` - Daily generator (Fri 2026-07-04 →) that queries `kilo_agents.db` for GLM/Kimi/Minimax/DeepSeek models, applies a weighted composite score (45% max(SWE, Aider) + 20% AA idx + 15% Arena + 10% speed + 10% cost-inverse), derives a Doc↔Code review letter grade per model, and writes the full ranked table to `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md`. Wired into `daily_refresh.sh` right after `derive_cheapest_gateway` so the rankings reflect fresh pricing. Hand-maintained `EXCLUDE_MODELS` / `PROVIDER_PINS` / `BODY_HINTS` dicts capture known-bad routing or reasoning-only models (e.g. `moonshotai/kimi-k2-thinking` returns 0 output tokens when reasoning is excluded → excluded). Public API: `rank_all(db_path=None) -> list[dict]`, `grade_doc_review(...)`, `fmt_body_hint(mid)`, plus `CODING_EXCLUDE_MODELS` / `CODING_PROVIDER_PINS` / `CODING_BODY_HINTS` constant aliases — used by `export_models_browser.py` to overlay coding-subagent ranking data onto the AI Models Browser payload without forking scoring state.
- `docs/reference/kilo/CODING_SUBAGENT_SELECTION.md` - Ranked table of coding-subagent candidates across GLM/Kimi/Minimax/DeepSeek families. Auto-regenerated daily by `scripts/kilo-benchmarks/rank_coding_subagents.py`. Columns: OR-reachability, cheapest OR sub-provider, benched output tok/s, prices, verified SWE / Aider / AA / Arena scores, context size, Doc↔Code review letter grade (A+/A/B+/B/B-/C+/C — measures ability to spot drift between docs and implementation), composite score.
- `scripts/kilo-benchmarks/apply_subagent_runs_ddl.sh` - One-shot DDL applier for the shared `subagent_runs` table on `fabrik_analytics`. Imports `SUBAGENT_RUNS_DDL` verbatim from `/opt/fabrik-lib/subagents/subagents/pg_ledger.py:35` (single source of truth). Uses `sudo -u postgres psql` (peer auth on WSL unix socket). Idempotent. VPS deploy is a follow-up (extend `ensure_shared_analytics_db()` at `src/fabrik/drivers/postgres.py:990`).
- `scripts/kilo-benchmarks/rank_task_subagents.py` - Daily aggregator that queries fleet-wide `subagent_runs` on `fabrik_analytics`, rolls up per `(task_type, model)` over a 90-day window with min 3 runs, emits ranked markdown. Formula: `value = success × quality / max(cost, 1e-9)` — cost-in-denominator, mirrors `select.py:126` `rank_weight / price`. Fail-soft → empty stub on DB errors. Public API: `render(rows) -> str`, `filter_min_runs(rows, min_n=3)`. Wired into `daily_refresh.sh` right after `rank_coding_subagents`. Consumers: `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` (daily regen), eventually the subagents module's `pick_models` at `/opt/fabrik-lib/subagents/subagents/select.py:76` (see `/opt/fabrik-lib/subagents/UPSTREAM_FEEDBACK.md`).
- `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` - Ranked table of models per `task_type` (spec/plan/code/review/docs/research), auto-regenerated daily by `rank_task_subagents.py`. Fleet-wide flywheel: agents write outcomes to `subagent_runs`, this doc reflects what actually worked. Empty-pool stub emitted when no `(task_type, model)` pair has ≥3 runs in the last 90 days.
- `scripts/kilo-benchmarks/daily_refresh.sh` - Cron-installed (`0 6 * * *` UTC) wrapper that runs the full daily chain: verifier → migrate columns → derive_quality_v2 → classifier → route mapper → pack markdown export → models_browser regen. Cron-safe (no PATH assumptions, no shell-activity dependency).
- `scripts/kilo-benchmarks/derive_quality_v2.py` - Multi-signal quality_tier deriver. 9 signals: arena + tbench + weighted_coding + design_arena_avg + AA index (OR-embedded) + AA scraped (own leaderboard) + SWE-bench Verified % + Aider Polyglot % + design_arena coding-only ELO + family regex + cost proxy + reasoning + context. Without it, ~85% of models default to T1.
- `scripts/kilo-benchmarks/scrape_coding_benchmarks.py` - Mines three public coding leaderboards (SWE-bench Verified swebench.com, Aider Polyglot aider.chat, OpenRouter design_arena coding categories) into agents.swe_bench_verified_pct / aider_polyglot_pct / design_arena_coding_elo. No inference cost. Permissive canonical-name matching across word-order/date-suffix/agent-prefix variants.
- `scripts/kilo_agents.db` - SQLite agent/model database

### Active Agents

- `~/.traycer/cli-agents/<TIER><NN>-<model>-<role>-<effort>-i<IN>-o<OUT>.sh`
- Tiers: P=Prime, S=Strong, B=Balanced, E=Economy
- See `docs/reference/kilo/` for complete documentation

**Archived:** 10 obsolete JSON files → `scripts/.archive/kilo-json-20260228/`
**Archived:** 5 redundant docs → `docs/archive/2026-02-28-kilo-redundant/`
