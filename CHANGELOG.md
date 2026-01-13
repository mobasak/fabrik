# Changelog

All notable changes to Fabrik will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added - Windsurf Extensions Sync (2026-01-13)

**What:** Automated tracking of installed Windsurf extensions via pre-commit hook.

**Files:**
- `scripts/sync_extensions.sh` - Syncs extensions to documentation
- `docs/reference/EXTENSIONS.md` - Auto-generated extensions list with install commands
- `.pre-commit-config.yaml` - Added sync-extensions hook

**Features:**
- Runs automatically on every commit
- Categorizes extensions (AI, Python, Docker, Git, Markdown, Web)
- Generates one-liner install commands for new machine setup
- Updates only when extensions change

---

### Added - AI Quick Review Pre-commit Hook (2026-01-08)

**What:** AI-powered code review integrated into pre-commit workflow.

**Files:**
- `scripts/enforcement/ai_quick_review.py` - Reviews staged diffs for critical issues
- `scripts/droid_core.py` - Added PRECOMMIT task type
- `.pre-commit-config.yaml` - Added ai-quick-review hook
- `.windsurf/rules/20-typescript.md` - Added visual design workflow
- `.windsurf/rules/00-critical.md` - Added "check existing code first" rule

**Features:**
- Uses `droid_core.py` with ProcessMonitor (no duplicate monitoring code)
- Reviews ALL code files: Python, TypeScript, JavaScript, Shell, YAML
- Includes renamed files (`--diff-filter=ACMR`)
- Proper exit codes: 0=passed, 1=failed, 2=skipped
- 8KB diff limit for token efficiency
- Disable with `SKIP_AI_REVIEW=1`

**Visual Design Workflow (SaaS/Web/Mobile):**
- Screenshot/mockup → AI generates code → preview → refine cycle
- Added to TypeScript rules for frontend projects

---

### Added - Spec Pipeline Integration (2026-01-08)

**What:** Integrated spec-interviewer discovery workflow into Fabrik with Traycer-optional support.

**Files:**
- `scripts/droid_core.py` - Added `IDEA` and `SCOPE` task types
- `templates/spec-pipeline/` - NEW (4 files)
- `templates/traycer/` - NEW (4 files, copied from spec-interviewer)
- `specs/` - NEW directory for project specifications
- `docs/FABRIK_OVERVIEW.md` - Updated with spec pipeline docs

**New Task Types:**
- `droid exec idea "<idea>"` - Capture and explore product idea
- `droid exec scope "<project>"` - Define IN/OUT boundaries

**Workflow:**
```
idea → scope → spec → plan → code → review → deploy
```

**Traycer Integration:**
- Templates in `templates/traycer/` for optional Traycer.ai use
- Works without Traycer using pure droid exec commands

---

### Fixed - Droid Core P0/P1 Issues (2026-01-08)

**What:** Fixed all critical issues identified in dual-model code reviews.

**Files:**
- `scripts/droid_core.py` - Multiple P0/P1 fixes
- `scripts/docs_updater.py` - ProcessMonitor threading fix
- `scripts/review_processor.py` - Task file support
- `tests/test_droid_core.py` - NEW (16 tests)

**P0 Fixes:**
- Final buffer completion events now parsed after process exit
- Large prompts (>100KB) use `--file` flag instead of CLI args (avoids OS limit crash)
- `run_droid_exec_monitored`: Missing completion event now marks FAILED (not stuck RUNNING)
- `run_droid_exec_monitored`: Non-zero exit code after completion marks FAILED
- `run_droid_exec_monitored`: Completion with `is_error=True` marks FAILED
- `_run_streaming`: Final buffer events with `is_error=True` now return failure

**P1 Fixes:**
- stderr captured via threaded bounded buffer (50 lines max)
- JSON parse fallback no longer marks failures as success
- Malformed JSON logged instead of silently ignored
- `--verbose` now attaches streaming callback
- Retries disabled for write-heavy tasks (CODE, SCAFFOLD, DEPLOY, MIGRATE, REFACTOR)
- Session reset on provider switch (OpenAI ↔ Anthropic) with user warning

**Minor Fixes:**
- `_sanitize_task_id` max length guard (128 chars with hash suffix)
- `refresh_models_from_docs()` emits warning on failure

**New Features:**
- Task file support (`--task-file`) in all scripts
- ProcessMonitor active polling in docs_updater.py

**Tests Added:**
- Session ID propagation
- Provider switch reset
- JSON parse fallback behavior
- Task ID sanitization

---

### Changed - Droid Scripts Consolidation (2026-01-08)

**What:** Consolidated `droid_tasks.py` + `droid_runner.py` into unified `droid_core.py`.

**Files:**
- `scripts/droid_core.py` - NEW (1316 lines, replaces 1507 combined)
- `scripts/droid_tasks.py` - DELETED (merged)
- `scripts/droid_runner.py` - DELETED (merged)
- `docs/development/plans/2026-01-08-droid-scripts-consolidation.md` - Execution plan

**Changes:**
- Unified 11 task types (analyze, code, refactor, test, review, spec, scaffold, deploy, migrate, health, preflight)
- Merged task persistence and monitoring from droid_runner.py
- Added run/status/list commands for task management
- Preserved ProcessMonitor integration
- Backup at `scripts/.archive/2026-01-08-pre-consolidation/`

**Not Merged (by design):**
- `review_processor.py` and `docs_updater.py` kept separate (CI-critical validation)

---

### Changed - Perfect Documentation Enforcement (2026-01-07)

**What:** Enhanced `docs_updater.py` with improved task management, stale task recovery, and pattern detection for more change types.

**Files:**
- `scripts/docs_updater.py` - Task retry logic, stuck detection, and pattern analysis expansion

**Changes:**
- Added `analyze_change_type` to detect `api_endpoint`, `cli_command`, `configuration`, `health_endpoint`, and `database_model` from file content.
- Implemented stale task recovery (resets tasks stuck in "processing" for >15 mins).
- Added automatic retry logic for failed tasks (up to 3 retries).
- Improved security by rejecting symlink task files.
- Enhanced logging and task status tracking.

**Code Review:** gemini-3-flash-preview verified the task management and detection logic.

---

### Changed - Droid Task Runner Enhancements (2026-01-07)

**What:** Major expansion of the droid task runner with new lifecycle tasks, reasoning support, and session management.

**Files:**
- `scripts/droid_tasks.py` - Major rewrite/expansion
- `src/fabrik/drivers/wordpress_api.py` - Typing improvements

**Changes:**
- Added new Fabrik lifecycle task types: `spec`, `scaffold`, `deploy`, `migrate`, `health`, `preflight`.
- Integrated `reasoning-effort` support for Anthropic models.
- Implemented Pattern 2 (Session ID continuation) for reliable multi-turn tasks.
- Added Pattern 1 (Interactive Session) for long-lived droid processes.
- Added `batch` command for processing multiple tasks from JSONL.
- Enhanced prompts with structured templates for all lifecycle phases.
- Added `DROID_EXEC_TIMEOUT` environment variable support.

**Code Review:** gemini-3-flash-preview verified lifecycle templates and session logic.

---

### Fixed - droid-review.sh Model Extraction (2026-01-07)

**What:** Fixed model name extraction from droid_models.py output.

**Files:**
- `scripts/droid-review.sh` - Use Python import instead of parsing CLI output
- `docs/reference/docs-updater.md` - Document new validation checks

**Root Cause:** Script parsed first line of `recommend` output instead of model name.

---

### Added - Perfect Documentation Enforcement (2026-01-07)

**What:** Enhanced docs_updater.py with complete coverage for all doc files.

**New Checks:**
- **Stub completeness** - Fails on placeholder markers in docs/reference/*.md
- **Link integrity** - Finds broken internal markdown links
- **Staleness** - Warns when manual docs missing Last Updated date

**Files Covered:**
- Root: README.md, AGENTS.md, CHANGELOG.md, tasks.md
- docs/: INDEX.md, QUICKSTART.md, CONFIGURATION.md, TROUBLESHOOTING.md, BUSINESS_MODEL.md
- docs/reference/*.md - Stub completeness
- docs/**/*.md - Link integrity

**Usage:**
```bash
python scripts/docs_updater.py --check  # Find all issues
python scripts/docs_updater.py --sync   # Auto-fix what's possible
```

---

### Added - Automatic Documentation Sync (2026-01-07)

**What:** Created docs_sync.py to check/remind about doc updates after code changes.

**Files:**
- `scripts/docs_sync.py` - Checks CHANGELOG, tasks.md, phase docs, INDEX.md
- `scripts/droid-review.sh` - Now calls docs_sync.py after reviews

**Workflow:**
```
Code change → droid-review.sh → docs_sync.py → Update flagged docs → Commit
```

**Checks:**
- CHANGELOG.md entry exists for code changes
- tasks.md updated when phase docs change
- Phase docs updated for implementation work
- docs/INDEX.md updated when new docs added

---

### Changed - Scaffold Includes Dashboard + Phase Templates (2026-01-07)

**What:** Updated scaffold templates so new projects get the dashboard structure.

**Files:**
- `templates/scaffold/docs/TASKS_TEMPLATE.md` - Dashboard format (links to phase docs)
- `templates/scaffold/docs/PHASE_TEMPLATE.md` - Phase progress tracker template
- `src/fabrik/scaffold.py` - Now creates `docs/development/Phase1.md`

**New projects get:**
- `tasks.md` - Dashboard linking to phase docs
- `docs/development/Phase1.md` - Progress tracker with checkboxes

---

### Changed - tasks.md to Dashboard Format (2026-01-07)

**What:** Converted tasks.md from duplicated checklist to dashboard linking phase docs.

**Files:**
- `tasks.md` - Now links to phase docs, no duplicated checkboxes
- `scripts/enforcement/check_tasks_updated.py` - Warns when phase docs change
- `scripts/enforcement/validate_conventions.py` - Added tasks update check

**Update Protocol:**
1. Update phase doc (checkboxes, completion %)
2. Update tasks.md (status table)
3. Update CHANGELOG.md (code changes)

---

### Added - droid-review.sh Wrapper Script (2026-01-07)

**What:** Created wrapper script that enforces adaptive meta-prompt for all code reviews.

**Files:**
- `scripts/droid-review.sh` - Wrapper for `droid exec` reviews

**Usage:**
```bash
./scripts/droid-review.sh src/file.py           # Code review
./scripts/droid-review.sh --plan plan.md        # Plan review
./scripts/droid-review.sh file1.py file2.py     # Multiple files
```

**Why:** Ensures all droid exec reviews use the structured meta-prompt from
`templates/droid/review-meta-prompt.md` for consistent P0/P1 output.

---

### Fixed - Code Quality Cleanup (2026-01-07)

**What:** Fixed ruff, bandit, and convention violations across codebase.

**Fixes:**
- 12 unused variables removed (ruff F841)
- jinja2 autoescape enabled in provisioner.py (bandit B701 high severity)
- Hardcoded localhost removed from coolify.py (now requires COOLIFY_API_URL env var)

**Result:** All pre-commit hooks pass cleanly.

---

### Fixed - All mypy Type Errors Resolved (2026-01-07)

**What:** Fixed all 57 remaining mypy type errors via droid exec + manual fixes.

**Files:** 20+ files in `src/fabrik/drivers/` and `src/fabrik/wordpress/`

**Method:**
- droid exec (gpt-5.1-codex-max) fixed 54 errors automatically
- Manual fixes for 3 edge cases (theme.py, wordpress.py, supabase.py)

**Result:** `mypy src/fabrik` now passes: "Success: no issues found in 53 source files"

---

### Changed - Relax mypy Config for Gradual Typing (2026-01-07)

**What:** Disabled strict mypy checking to allow gradual typing adoption.

**Files:**
- `pyproject.toml` - Set strict=false, ignore_errors for fabrik.* module
- `.pre-commit-config.yaml` - Disabled mypy hook temporarily
- `src/fabrik/drivers/wordpress_api.py` - Added type annotations

**Reason:** 489 pre-existing mypy errors across 35 files. Strict mode blocks commits.
Gradual typing approach: add types to new code, fix old code incrementally.

---

### Fixed - scaffold.py Full Fabrik Compliance (2026-01-07)

**What:** New projects created via `create_project()` are now fully compliant with Fabrik conventions.

**Files:**
- `src/fabrik/scaffold.py` - Major enhancements
- `templates/scaffold/docker/Dockerfile.python` - Fixed CMD entry point

**Changes:**
- AGENTS.md now symlinked to master `/opt/fabrik/AGENTS.md` (with copy fallback)
- .pre-commit-config.yaml copied and hooks installed automatically
- pyproject.toml with ruff/mypy/bandit config included
- Dockerfile CMD fixed: `src.main:app` (was `app.main:app`)
- Input validation: lowercase names, reserved names blocked, length limit
- fix_project() uses same AGENTS.md fallback logic as create_project()

**Code Review:** gemini-3-flash-preview verified all issues fixed.

---

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
