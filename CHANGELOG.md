# Changelog

All notable changes to Fabrik will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added - Droid Review Meta-Prompt and Enforcement Memories (2026-01-07)

**What:** Created adaptive review prompt template and enforcement memories for Cascade behavior.

**Files:**
- `templates/droid/review-meta-prompt.md` - Adaptive prompt for plan/code/docs reviews
- `docs/reference/droid-exec-usage.md` - Merged architecture sections from complete-guide
- `docs/reference/wordpress/plugin-stack.md` - Added plugin activation workarounds section

**Archived:**
- `docs/reference/droid-validation-report.md` → `docs/archive/2025-01-03-droid-validation/`
- `docs/reference/droid-exec-complete-guide.md` - Merged and deleted

**New Memories Created:**
- Droid Review Prompt Location (pointer to meta-prompt)
- Check templates before creating docs (enforcement)
- Verify file existence before write (enforcement)
- Present plan, wait for approval (enforcement)
- Follow Fabrik doc structure (enforcement)

---

### Added - Project Structure Enforcement (2026-01-07)

**What:** Enforce document placement in correct locations per Fabrik conventions.

**Files:**
- `scripts/enforcement/check_structure.py` - New script to validate .md file locations
- `.pre-commit-config.yaml` - Added structure-check hook
- `AGENTS.md` - Added Document Location Rules section

**Enforces:**
- Root .md files limited to: README.md, CHANGELOG.md, tasks.md, AGENTS.md, PORTS.md, LICENSE.md
- All other docs must go in docs/ subdirectories
- Warns on legacy directories (specs/, proposals/)

---

### Fixed - mypy pre-commit hook finding fabrik package (2026-01-07)

**What:** Fixed mypy import errors by setting MYPYPATH=src in pre-commit hook.

**Files:**
- `.pre-commit-config.yaml` - Added MYPYPATH and --explicit-package-bases

---

### Changed - Rename docs/README.md to docs/INDEX.md (2026-01-07)

**What:** Standardized documentation index naming to avoid confusion with root README.md.

**Files:**
- `docs/README.md` → `docs/INDEX.md` - Renamed
- Updated 17 files with 29 references to use new path

---

### Added - Documentation Automation System (2026-01-07)

**What:** Automated documentation system with mandatory CHANGELOG.md updates, pre-commit enforcement, and port validation.

**Files:**
- `scripts/docs_updater.py` - Added --check/--sync/--dry-run modes, CHANGELOG.md as mandatory step 1
- `scripts/enforcement/check_changelog.py` - Smart pre-commit hook (skips tests/small diffs, validates entry quality)
- `scripts/enforcement/check_ports.py` - Port validation (checks PORTS.md registration, validates ranges)
- `.pre-commit-config.yaml` - Added changelog-check hook
- `scripts/enforcement/check_plans.py` - Plan naming validation
- `scripts/enforcement/validate_conventions.py` - Wired plan checks
- `.windsurf/rules/50-code-review.md` - Execution protocol (PLAN→APPROVE→IMPLEMENT→REVIEW→FIX→VALIDATE→NEXT)
- `.windsurf/rules/40-documentation.md` - Added CHANGELOG.md mandatory rule
- `.github/workflows/docs-check.yml` - CI for docs validation
- `docs/development/PLANS.md` - Plans index
- `docs/development/plans/` - Plans directory structure
- `templates/docs/MODULE_REFERENCE_TEMPLATE.md` - Module stub template
- `tests/test_docs_updater.py` - Tests for docs_updater

---

### Added - Deployment Orchestrator Phase 10 (2026-01-06)

**What:** Spec-driven deployment orchestration system.

**Files:**
- `src/fabrik/orchestrator/` - Complete orchestrator module
- `docs/reference/orchestrator.md` - Orchestrator documentation
- `docs/reference/phase10.md` - Human-readable plan
- `docs/reference/phase10-execution.md` - Execution details

---

### Added - Windsurf Rules Enhancement (2026-01-05)

**What:** Enhanced Windsurf rules with dynamic model discovery.

**Files:**
- `.windsurf/rules/00-critical.md` - Security, env vars (always_on)
- `.windsurf/rules/10-python.md` - Python patterns (glob)
- `.windsurf/rules/20-typescript.md` - TypeScript patterns (glob)
- `.windsurf/rules/30-ops.md` - Docker/ops (always_on)
- `.windsurf/rules/90-automation.md` - droid exec integration (always_on)
- `AGENTS.md` - Removed hardcoded model names, use config/models.yaml

---

### Added - Multi-Model Consensus & Gap Analysis (2026-01-04)

**What:** 4-model consensus for architectural decisions.

**Files:**
- `specs/FABRIK_CONSOLIDATED_GAP_ANALYSIS.md` - Gap analysis
- `specs/FABRIK_CONDUCTOR_CONSENSUS_PLAN.md` - Consensus plan
- `docs/design/CASCADE-DROID-STRATEGY.md` - Cascade-Droid strategy

---

### Added - Enforcement System (2026-01-04)

**What:** Windsurf + Fabrik enforcement integration.

**Files:**
- `scripts/enforcement/` - Convention validators
- `.factory/hooks/` - Pre/post hooks
- `docs/reference/enforcement-system.md` - Enforcement documentation

---

### Added - Code Review Feedback Loop (2026-01-03)

**What:** Automated code review with acknowledgment tracking.

**Files:**
- `scripts/acknowledge_reviews.py` - Review acknowledgment
- `docs/reference/auto-review.md` - Auto-review documentation

---

### Added - Process Monitoring (2026-01-03)

**What:** Long-running command monitoring with stuck detection.

**Files:**
- `scripts/process_monitor.py` - Process monitoring
- `docs/reference/PROCESS_MONITORING_QUICKSTART.md` - Quickstart guide

---

### Added - SaaS Skeleton Template (2026-01-02)

**Complete Next.js SaaS template with droid exec integration.**

**Template (`templates/saas-skeleton/`):**
- Marketing pages: landing, pricing, FAQ, terms, privacy
- App pages: dashboard, new job, items list, item detail, settings
- Core components: AppShell, PageHeader, SectionCard, EmptyState, StateBlocks
- Chat components: ChatUI, SSEStream for real-time droid exec streaming
- API route: `/api/chat` for SSE streaming with droid exec
- Job workflow pattern: DRAFT → QUEUED → RUNNING → SUCCEEDED/FAILED

**Droid Skill (`.factory/skills/fabrik-saas-scaffold.md`):**
- Auto-invokes when creating SaaS apps
- Documents customization steps and deployment

**Documentation:**
- Updated `docs/reference/SaaS-GUI.md` with implementation reference
- Updated `docs/INDEX.md` with template link

---

### Fixed - Droid System Review (2026-01-02)

**Comprehensive review and fixes for the Fabrik Droid automation system.**

**Scripts (`scripts/`):**
- `droid_tasks.py`: Fixed CLI to use task-specific `default_auto` and `model` from `TOOL_CONFIGS`
- `droid_tasks.py`: Removed unused `threading` import
- `droid_tasks.py`: Added missing `preflight` task type to help epilog
- `droid_tasks.py`: Added `--reasoning-effort` flag passthrough to droid exec
- `droid_models.py`: Fixed `gemini-3-flash` → `gemini-3-flash-preview` in `FABRIK_EXECUTION_MODES`
- `droid_models.py`: Added model sync functionality (`python3 scripts/droid_models.py sync`)

**Hooks (`.factory/hooks/`):**
- `fabrik-conventions.py`: Fixed `hardcoded_localhost` regex pattern (broken lookbehind)
- `fabrik-conventions.py`: Excluded `getenv/environ` from `hardcoded_password` pattern to reduce false positives
- `session-context.py`: Added git availability check before running git commands
- `format-python.sh`: Removed `set -e` to prevent silent failures on syntax errors
- `protect-files.sh`: Changed `.env.` pattern to specific files, allowing `.env.example` edits

**Documentation (`docs/reference/droid-exec-usage.md`):**
- Fixed `$FACTORY_PROJECT_DIR` → `$DROID_PROJECT_DIR` environment variable name
- Updated Mode Overview table to use full model registry names
- Updated Model pricing table to use full model registry names
- Fixed shortened model names (`claude-sonnet-4-5` → `claude-sonnet-4-5-20250929`, etc.)

**Cross-file consistency (`AGENTS.md`, `windsurfrules`):**
- Synced `fabrik-watchdog` triggers to include "monitor" keyword
- Synced `fabrik-config` triggers to include "settings" keyword
- Synced `fabrik-postgres` triggers to include "migration" keyword
- Updated Execution Modes table to match canonical model names

**Architecture improvements:**
- Established `FABRIK_TASK_MODELS` in `droid_models.py` as single source of truth for model names
- Created sync mechanism: `python3 scripts/droid_models.py sync` updates `droid_tasks.py`, `AGENTS.md`, and `droid-exec-usage.md`
- Added pre-commit hook for automatic model sync on commit
- Added `fabrik sync-models` CLI command

**Documentation additions:**
- Added §21 Automated Code Review (GitHub App) to `droid-exec-usage.md`
- Added §22 GitHub Actions Workflows documentation
- Added §23 Batch Refactoring Scripts documentation
- Added §24 Fabrik Review Prompt Template documentation

**GitHub Actions Workflows (`.github/workflows/`):**
- `droid-review.yml` - Automated PR code review with Fabrik convention checks
- `update-docs.yml` - Auto-update documentation when code merges to main
- `security-scanner.yml` - Weekly security audit (vulnerabilities, secrets, conventions)
- `daily-maintenance.yml` - Daily docs and test updates

**Batch Refactoring Scripts (`scripts/droid/`):**
- `refactor-imports.sh` - Organize Python imports across codebase
- `improve-errors.sh` - Improve error messages for better UX
- `fix-lint.sh` - Fix lint violations with AI understanding

**Templates:**
- `templates/scaffold/droid-review-prompt.md` - Fabrik-specific PR review prompt template

**droid_tasks.py enhancements:**
- Added `--debug` flag for verbose output showing tool calls
- Useful for building web UIs with real-time feedback

**Documentation (droid-exec-usage.md):**
- Added §25 Deploy Droid Exec on VPS via Coolify
- Added §26 Building Web Apps with Droid Exec (SSE Streaming)

---

### Added - Project Management Integration (2025-12-27)

**Fabrik now owns project management.** Merged `/opt/_project_management` into Fabrik.

**New CLI commands:**
- `fabrik scaffold <name>` - Create new project with full structure
- `fabrik validate <path>` - Validate project against standards

**New modules:**
- `src/fabrik/scaffold.py` - Project scaffolding logic

**Moved from _project_management:**
- `windsurfrules` → `/opt/fabrik/windsurfrules`
- `PORTS.md` → `/opt/fabrik/data/ports.yaml` (YAML format)
- `templates/docs/*` → `/opt/fabrik/templates/scaffold/docs/`
- `templates/docker/*` → `/opt/fabrik/templates/scaffold/docker/`
- `scripts/rund,rundsh,runc,runk` → `/opt/fabrik/scripts/`
- Reference docs → `/opt/fabrik/docs/reference/`

**Updated:**
- All project `.windsurfrules` symlinks now point to fabrik
- `~/.local/bin/rund,rundsh,runc,runk` symlinks updated

### Added

- Initial project structure per .windsurfrules standard
- Documentation framework (README, docs/, reference/)
- Phase 1-8 roadmap documentation
- `.pre-commit-config.yaml` for automated code quality checks (ruff, mypy, bandit)
- `Makefile` with standard targets (install, dev, test, lint, format, clean)
- `uv.lock` for reproducible dependency installations (40 packages pinned)
- Comprehensive documentation index in `docs/INDEX.md`

### Changed

- Updated `README.md` project status to reflect Phase 1-1d completion
- Updated `tasks.md` date to 2025-12-27
- Updated `docs/SERVICES.md` to clarify Fabrik is a CLI tool
- Updated `docs/FABRIK_OVERVIEW.md` date and completion status
- Moved `step1-domain-hosting-validation.md` → `guides/domain-hosting-automation.md`

### Documentation Restructure (Option B - Full Consolidation)

**New structure:**
- Created `docs/operations/` folder for operational docs
- Created `docs/reference/wordpress/` subfolder for WordPress technical docs
- Created `docs/ROADMAP_ACTIVE.md` consolidating planning docs

**Moved to `operations/`:**
- `disaster-recovery.md`, `duplicati-setup.md`, `vps-status.md`, `vps-urls.md`
- `COOLIFY_MIGRATION_RUNBOOK.md` → `coolify-migration.md`

**Moved to `reference/wordpress/`:**
- `wordpress-v2-architecture.md` → `architecture.md`
- `wordpress-v2-fixes.md` → `fixes.md`
- `wordpress-pages-idempotency.md` → `pages-idempotency.md`
- `full-plugin-stack.md` → `plugin-stack.md`
- `plugin-stack-evaluation.md` → `plugin-evaluation.md`
- `site-specification.md`

**Moved to `guides/`:**
- `DEPLOYMENT_READY_CHECKLIST.md`

**Consolidated and archived:**
- `WHATS_NEXT.md`, `FUTURE_WORK.md`, `future-development.md` → `ROADMAP_ACTIVE.md`
- Originals archived to `docs/archive/` with date prefix

### Automated Deployment (Phase 1 Completion)

**New modules:**
- `src/fabrik/deploy.py` - Coolify deployment helper
- `src/fabrik/registry.py` - Project registry system

**New CLI commands:**
- `fabrik scan` - Scan /opt for projects, update registry
- `fabrik projects` - List tracked projects with deployment status
- `fabrik projects --sync` - Sync with Coolify before listing

**Deployment automation:**
- `fabrik apply` now fully deploys to Coolify (was placeholder)
- Auto-detects server UUID and project UUID
- Creates/redeploys docker-compose apps via Coolify API

**Project registry (`data/projects.yaml`):**
- Tracks all /opt projects (excludes `_*`, `.*`, `google`, `apps`)
- Stores deployment status, Coolify UUID, domain
- Syncs with Coolify to update deployment state

**Config additions:**
- `COOLIFY_SERVER_UUID` (optional, auto-detected)
- `COOLIFY_PROJECT_UUID` (optional, auto-detected)

### Fixed

- N/A

---

## [0.0.0] - 2025-12-21

### Added

- Project initialization
- Planning documentation (Phase 1-8)
- Stack architecture documentation
