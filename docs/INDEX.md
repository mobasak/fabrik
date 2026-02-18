# Fabrik Documentation

**Last Updated:** 2026-01-08

---

## Structure Map

<!-- AUTO-GENERATED:STRUCTURE:START -->
<!-- AUTO-GENERATED:STRUCTURE v1 | 2026-01-07T10:20Z -->
```text
docs/
├── README.md                       # This file - documentation index
├── QUICKSTART.md                   # Get Fabrik running in 5 minutes
├── CONFIGURATION.md                # Environment variables and settings (updated 2026-01-06)
├── DEPLOYMENT.md                   # How to deploy services to VPS
├── SERVICES.md                     # External services Fabrik depends on
├── TROUBLESHOOTING.md              # Common issues & solutions
├── TESTING.md                      # How to run and write tests
├── FAQ.md                          # Frequently asked questions
├── ENVIRONMENT_VARIABLES.md        # Complete env var reference (updated 2026-01-06)
├── FABRIK_OVERVIEW.md              # What Fabrik is and what it does
├── ROADMAP_ACTIVE.md               # Current priorities, backlog, future plans
├── BUSINESS_MODEL.md               # Monetization strategy
├── owner_ozgur_basak.md            # Owner profile & AI instructions
├── guides/
│   ├── PROJECT_WORKFLOW.md         # Start here - new/existing project workflow
│   ├── FABRIK_INTEGRATION.md       # Build Fabrik-compatible microservices
│   ├── domain-hosting-automation.md # Domain + hosting automation
│   └── DEPLOYMENT_READY_CHECKLIST.md # Make projects deployment-ready
├── reference/
│   ├── CRITICAL_RULES.md           # Non-negotiable execution rules
│   ├── DOCUMENTATION_STANDARD.md   # Documentation standards and conventions
│   ├── PROCESS_MONITORING_QUICKSTART.md # Process monitor setup
│   ├── SaaS-GUI.md                 # SaaS skeleton GUI guide
│   ├── architecture.md             # System architecture overview
│   ├── auto-review.md              # Automatic code review system
│   ├── docs-updater.md             # Automatic documentation updater
│   ├── fabrik-cli-reference.md     # Fabrik CLI command reference
│   ├── droid-exec-usage.md         # Core droid exec usage (updated 2026-01-07)
│   ├── enforcement-system.md       # Convention enforcement (check scripts, rules)
│   ├── hooks-and-skills-guide.md   # Hook and skill usage guide
│   ├── drivers.md                  # Fabrik driver API (Coolify, DNS, etc.)
│   ├── orchestrator.md             # Deployment orchestrator module (Phase 10)
│   ├── file-api-deployment.md      # File API deployment guide
│   ├── AI_TAXONOMY.md              # AI categories & tool selection (15 categories)
│   ├── DATABASE_STRATEGY.md        # Database selection (PostgreSQL/Supabase/pgvector)
│   ├── PLANNING_REFERENCES.md      # **INDEX for AI planning phases** (NEW 2026-01-08)
│   ├── prebuilt-app-containers.md  # Prebuilt container catalog
│   ├── project-registry.md         # Master inventory of all /opt projects
│   ├── roadmap.md                  # Complete 8-phase roadmap summary
│   ├── stack.md                    # Technology stack & tools inventory
│   ├── technology-stack-decision-guide.md  # Tech decision flowchart
│   ├── templates.md                # Available deployment templates
│   ├── spec-pipeline.md            # Spec pipeline (idea → scope → spec)
│   ├── trueforge-images.md         # Trueforge image catalog
│   ├── uptime-kuma.md              # Uptime Kuma runbook
│   ├── verification-framework.md   # 3-lane verification system
│   ├── windsurf/                   # Windsurf IDE optimization
│   │   ├── overview.md             # Windsurf optimization overview
│   │   ├── recommended-extensions.md # Curated extensions list
│   │   ├── cascade-models.md       # Cascade models and credits (source of truth)
│   │   ├── cascade-guide.md        # Cascade modes, checkpoints, tools
│   │   ├── features.md             # Command, Editor, Terminal features
│   │   └── csharp-cpp-setup.md     # C#/.NET/C++ setup (not used by Fabrik)
│   └── wordpress/                  # WordPress technical docs
│       ├── architecture.md         # WordPress v2 spec system
│       ├── fixes.md                # Critical fixes
│       ├── pages-idempotency.md    # Page creation idempotency
│       ├── plugin-stack.md         # Curated plugin stack
│       └── site-specification.md   # Site spec YAML format
├── operations/
│   ├── vps-status.md               # Current VPS state and configuration
│   ├── vps-urls.md                 # All deployed service URLs
│   ├── disaster-recovery.md        # Backup and recovery procedures
│   ├── duplicati-setup.md          # Duplicati backup configuration
│   ├── backup-strategy.md          # VPS backup strategy
│   └── coolify-migration.md        # Coolify migration procedures
│   └── backup-strategy.md          # VPS backup strategy
├── development/
│   ├── PLANS.md                    # Development plans index
│   └── plans/                      # Plan documents (YYYY-MM-DD-plan-*.md)
```
<!-- AUTO-GENERATED:STRUCTURE:END -->

---

## Quick Start

| Document | Purpose |
|----------|--------|
| [QUICKSTART.md](QUICKSTART.md) | Get Fabrik running in 5 minutes |
| [CONFIGURATION.md](CONFIGURATION.md) | All environment variables and settings |
| [DEPLOYMENT.md](DEPLOYMENT.md) | How to deploy services to VPS |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common issues and solutions |
| [TESTING.md](TESTING.md) | How to run and write tests |
| [FAQ.md](FAQ.md) | Frequently asked questions |
| [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) | Complete env var reference |

---

## Core Reference

| Document | Purpose |
|----------|--------|
| [architecture.md](reference/architecture.md) | System architecture, components, data flow |
| [stack.md](reference/stack.md) | Technology stack, APIs, libraries |
| [roadmap.md](reference/roadmap.md) | Complete 8-phase development roadmap |
| [drivers.md](reference/drivers.md) | Fabrik driver API (Coolify, DNS, etc.) |
| [templates.md](reference/templates.md) | Available deployment templates |
| [SaaS-GUI.md](reference/SaaS-GUI.md) | SaaS skeleton template guide |

**SaaS Template:** `templates/saas-skeleton/` — Next.js + Tailwind + SSE streaming for droid exec

---

## Phase Documentation

| Phase | Status | Document |
|-------|--------|----------|
| **Phase 1: Foundation** | ✅ Complete | [architecture.md](reference/architecture.md) |
| **Phase 1b: Cloud Infrastructure** | ✅ Complete | [deployment.md](DEPLOYMENT.md) |
| **Phase 1c: Cloudflare DNS** | ✅ Complete | [services.md](SERVICES.md) |
| **Phase 1d: WordPress Automation** | 🚧 In Progress | [wordpress.md](reference/wordpress.md) |

---

## Operations

| Document | Purpose |
|----------|--------|
| [vps-status.md](operations/vps-status.md) | Current VPS state and configuration |
| [vps-urls.md](operations/vps-urls.md) | All deployed service URLs |
| [disaster-recovery.md](operations/disaster-recovery.md) | Backup and recovery procedures |
| [duplicati-setup.md](operations/duplicati-setup.md) | Duplicati backup configuration |
| [coolify-migration.md](operations/coolify-migration.md) | Coolify migration procedures |

---

## Guides

| Document | Purpose |
|----------|--------|
| [PROJECT_WORKFLOW.md](guides/PROJECT_WORKFLOW.md) | **Start here** — New/existing project workflow |
| [FABRIK_INTEGRATION.md](guides/FABRIK_INTEGRATION.md) | Build Fabrik-compatible microservices |
| [domain-hosting-automation.md](guides/domain-hosting-automation.md) | Full domain + hosting automation |
| [DEPLOYMENT_READY_CHECKLIST.md](guides/DEPLOYMENT_READY_CHECKLIST.md) | Make any project deployment-ready |

---

## WordPress

| Document | Purpose |
|----------|--------|
| [plugin-stack.md](reference/wordpress/plugin-stack.md) | Curated WordPress plugin stack |
| [architecture.md](reference/wordpress/architecture.md) | WordPress v2 spec system |
| [fixes.md](reference/wordpress/fixes.md) | Critical fixes for v2 |
| [pages-idempotency.md](reference/wordpress/pages-idempotency.md) | Page creation idempotency |
| [site-specification.md](reference/wordpress/site-specification.md) | Site spec YAML format |

---

## Droid Automation

| Document | Purpose |
|----------|--------|
| [droid-exec-usage.md](reference/droid-exec-usage.md) | **Complete droid exec guide** — models, tasks, hooks, MCP, prompting, spec mode |
| [enforcement-system.md](reference/enforcement-system.md) | Convention enforcement — check scripts, rules, pre-commit |
| [AGENTS.md](../AGENTS.md) | Agent briefing for AI coding assistants |
| [factory-settings.json](../templates/scaffold/factory-settings.json) | Factory settings template |
| [factory-hooks.json](../templates/scaffold/factory-hooks.json) | Hooks configuration template |
| [factory-mcp.json](../templates/scaffold/factory-mcp.json) | MCP servers template |

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
**Scripts:** `scripts/droid_tasks.py` (task runner), `scripts/droid_models.py` (model registry), `scripts/docs_updater.py` (documentation updater), `scripts/container_images.py` (image discovery), `scripts/setup_duplicati_backup.py` (backup automation), `scripts/enforcement/validate_conventions.py` (convention validator)
**Batch Scripts:** `scripts/droid/` (refactor-imports, improve-errors, fix-lint)
**Workflows:** `.github/workflows/` (droid-review, update-docs, security-scanner, daily-maintenance)
**Key Flags:** `--auto`, `--use-spec`, `-m`, `-r`, `-o`, `--cwd`, `-s`
**VPS Deployment:** See §25-26 in droid-exec-usage.md for Coolify + SSE streaming patterns

---

## Project Context

| Document | Purpose |
|----------|--------|
| [FABRIK_OVERVIEW.md](FABRIK_OVERVIEW.md) | What Fabrik is and what it does |
| [ROADMAP_ACTIVE.md](ROADMAP_ACTIVE.md) | Current priorities, backlog, future plans |
| [BUSINESS_MODEL.md](BUSINESS_MODEL.md) | Monetization strategy |
| [owner_ozgur_basak.md](owner_ozgur_basak.md) | Owner profile & AI instructions |
| [project-registry.md](reference/project-registry.md) | Master inventory of all /opt projects |
