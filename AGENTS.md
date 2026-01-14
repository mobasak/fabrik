# Fabrik Project Agent Briefing

**Last Updated:** 2026-01-14

> Standard instructions for AI coding agents (droid exec, Cursor, Aider, etc.)

## Authority Model

- You write content.
- Tools enforce structure.
- CI is final authority.

## Execution Protocol (ALL TASKS)

**Before ANY implementation:**

| Phase | Action | Gate |
|-------|--------|------|
| **1. PLAN** | Create/show execution plan document | Plan exists in `docs/development/plans/` |
| **2. APPROVE** | Wait for explicit "go" from human | Human says "go" |
| **3. IMPLEMENT** | Execute one step at a time | Step code complete |
| **4. REVIEW** | Request AI code review | Review received |
| **5. FIX** | Address issues before proceeding | Issues resolved |
| **6. VALIDATE** | Run gate command, show evidence | Gate passes |
| **7. NEXT** | Only proceed after gate passes | Approval for next step |

**Step Output Format (MANDATORY after each step):**
```
STEP <N> STATUS: PASS / FAIL
Changed files:
- <path>
Gate output:
<output>
Next: Proceed to Step <N+1> / STOP
```

**Violations:**
- Do NOT implement without showing plan first
- Do NOT proceed to next step without gate passing
- Do NOT skip code review on significant changes
- Do NOT assume approval — wait for explicit "go"

---

## Planning (Required for Non-Trivial Work)

**Before implementing any feature or fix, create a plan document.**

### Plan Location & Naming
- Location: `docs/development/plans/`
- Filename: `YYYY-MM-DD-plan-<name>.md` (e.g., `2026-01-14-plan-feature-auth.md`)

### Plan Lifecycle
1. **Create** plan in `docs/development/plans/`
2. **Add** to `docs/development/PLANS.md` index
3. **Update** `**Status:**` as work progresses
4. **Check boxes** as items complete
5. **Archive** when COMPLETE → move to `docs/archive/`

### Required Plan Sections
- `**Status:**` line (NOT_STARTED, IN_PROGRESS, PARTIAL, COMPLETE, NOT_DONE)
- `## Goal` - One-line description
- `## DONE WHEN` - Checkboxes for completion criteria
- `## Out of Scope` - What's excluded
- `## Steps` - Implementation steps

---

## Documentation Rules

1) **VERIFY before creating:** Check `docs/INDEX.md` and existing folders before creating new files.
2) Do NOT create markdown files in repo root (except README.md, CHANGELOG.md, AGENTS.md, tasks.md).
3) Feature/Execution plans: See **Planning** section above.
4) Every new plan MUST be added to `docs/development/PLANS.md`.
5) Do NOT create new folders under `docs/` except via existing structure.
6) If you add a module under `src/`, ensure a reference doc exists:
   - `docs/reference/<module>.md`
   - If missing, run `docs_updater.py --sync`.
7) NEVER edit inside `<!-- AUTO-GENERATED:* -->` blocks.
   - Run `docs_updater.py --sync` instead.
8) All changes MUST keep `make docs-check` passing.

**Existing docs structure:**
- `docs/guides/` - How-to guides
- `docs/reference/` - Technical reference
- `docs/operations/` - Ops runbooks
- `docs/development/plans/` - Plan documents
- `docs/archive/` - Archived/completed docs

Violations will fail CI and must be fixed before merge.

---

## ⚠️ MANDATORY WORKFLOW (ALL AI AGENTS)

**Before finishing ANY coding task, you MUST:**

```bash
# 1. Run enforcement check
python3 -m scripts.enforcement.validate_conventions --strict <changed_files>

# 2. Trigger code review (if significant changes)
# Get model dynamically: python3 scripts/droid_models.py recommend code_review
./scripts/droid-review.sh <files...>

# 3. Update documentation
# If you changed code in src/, scripts/, update relevant docs/
# Manual update: ./scripts/droid-review.sh --update-docs <files...>
```

**If you skip these steps, you are violating Fabrik rules.**

---

## Windsurf Cascade Users

For IDE-specific rules, see `.windsurf/rules/`:
- `00-critical.md` — Security, env vars, ports (Always On)
- `10-python.md` — FastAPI patterns (*.py glob)
- `20-typescript.md` — Next.js patterns (*.ts, *.tsx glob)
- `30-ops.md` — Docker/deployment (Always On)
- `40-documentation.md` — Plan documents, writing style (Always On)
- `50-code-review.md` — Execution protocol, PLAN→APPROVE→IMPLEMENT→REVIEW→FIX→VALIDATE→NEXT (Always On)
- `90-automation.md` — droid exec integration, skills, batch scripts (Always On)

## Build & Test

```bash
# Python projects
pip install -e .                    # Install in dev mode
pytest                              # Run tests
pytest -x --tb=short               # Stop on first failure

# Check code quality
ruff check .                        # Lint
mypy .                              # Type check

# Docker
docker compose up -d                # Start services
docker compose logs -f              # Follow logs
docker compose down                 # Stop services
```

## Run Locally

```bash
# Most projects use uvicorn
uvicorn src.main:app --reload --port 8000

# Or with watchdog scripts
./scripts/watchdog_api.sh start

# Check health
curl http://localhost:8000/health
```

## Architecture Overview

Fabrik projects follow a consistent pattern:

- **WSL (dev)** → Local PostgreSQL, local services, `.env` file
- **VPS (prod)** → Coolify-managed Docker Compose, `postgres-main` container
- **Every project ships as one Compose app** — web + worker + optional services

## SaaS Projects (MANDATORY)

**When starting ANY SaaS, web app, or dashboard project, ALWAYS use the SaaS skeleton:**

```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/<project-name>
cd /opt/<project-name>
npm install
cp .env.example .env
npm run dev
```

**Template includes:** Next.js 14 + TypeScript + Tailwind CSS, marketing pages, app pages (dashboard, settings, job workflow), SSE streaming + ChatUI for droid exec integration.

**Customize:** `lib/config/site.ts` for branding, `app/(marketing)/` for content.

## Project Layout

```
/opt/<project>/
├── src/ or <package>/     # Main source code
│   ├── main.py            # Entry point
│   ├── config.py          # Config loading (from env vars)
│   ├── models/            # Data models
│   ├── services/          # Business logic
│   └── api/               # API endpoints
├── tests/                 # Tests mirror src/
├── scripts/               # Utility & watchdog scripts
├── config/                # YAML/JSON configs
├── docs/                  # Documentation
├── compose.yaml           # Docker Compose for deployment
├── .env.example           # Env var template (never commit .env)
└── AGENTS.md              # This file (symlinked)
```

## Conventions & Patterns

### Environment Variables (CRITICAL)

```python
# CORRECT - works in WSL, Docker, Supabase
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))

# WRONG - breaks in production
DB_HOST = 'localhost'  # Hardcoded!
```

### Health Checks

```python
# CORRECT - tests actual dependencies
@app.get("/health")
async def health():
    await db.execute("SELECT 1")  # Actually test DB
    return {"status": "ok", "db": "connected"}

# WRONG - hides failures
@app.get("/health")
async def health():
    return {"status": "ok"}  # Lies!
```

### Config Loading

```python
# CORRECT - load at runtime
def get_db_url():
    return f"postgresql://{os.getenv('DB_USER')}:..."

# WRONG - class-level (env not set at import time)
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_USER')}:..."  # Fails!
```

## Security

- **Never commit `.env`** — Use `.env.example` as template
- **All credentials in TWO places:**
  1. Project `.env` (local use)
  2. `/opt/fabrik/.env` (master backup)
- **CSPRNG passwords**: 32 chars, alphanumeric only
- **No hardcoded secrets** — Always use env vars

## Deployment

Target: **Coolify on VPS via Docker Compose**

```yaml
# compose.yaml structure
services:
  api:
    build: .
    environment:
      - DB_HOST=postgres-main
      - DB_PORT=5432
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
```

## Gotchas

1. **Never use `/tmp/`** — Use project-local `.tmp/` instead (data survives restarts)
2. **Health checks must test dependencies** — Not just return `{"status": "ok"}`
3. **Env vars not set at import time** — Load config in functions, not class-level
4. **Test in Docker before deploying** — `docker compose up` locally first

## Documentation Rules (MUST)

**Every code change requires documentation update.** No exceptions.

### Document Location Rules (ENFORCED)

**Root-level `.md` files allowed:**
- `README.md`, `CHANGELOG.md`, `tasks.md`, `AGENTS.md`, `PORTS.md`, `LICENSE.md`

**All other docs MUST go in `docs/` subdirectories:**

| Directory | Purpose |
|-----------|---------|
| `docs/guides/` | How-to guides |
| `docs/reference/` | API/CLI reference |
| `docs/operations/` | Ops runbooks |
| `docs/development/` | Plans, specs |
| `docs/development/plans/` | Execution plans |
| `docs/archive/` | Archived docs |

**Forbidden:**
- Creating `.md` files in `specs/`, `proposals/`, or other non-standard directories
- Creating `.md` files in `src/`, `scripts/`, `tests/`, `config/`

This is enforced by `scripts/enforcement/check_structure.py` and pre-commit hook.

### When Making Changes

1. **Update docs/INDEX.md structure map** if adding/moving/deleting files
2. **Update relevant docs** in same commit as code changes
3. **Add Last Updated date** to modified docs: `**Last Updated:** YYYY-MM-DD`
4. **Archive, don't delete** obsolete docs → `docs/archive/YYYY-MM-DD-topic/`

### Documentation Standards

| Rule | Example |
|------|---------|
| **Clear title** | `# Feature Name` not `# Notes` |
| **Purpose statement** | First paragraph explains what and why |
| **Runnable examples** | Code blocks with copy-paste commands |
| **Cross-references** | Link to related docs with relative paths |
| **No stale info** | Remove or archive outdated sections |

### Required for Every Feature

```markdown
## Feature Name

**Purpose:** One-line description

**Usage:**
\`\`\`bash
command --example
\`\`\`

**Configuration:** List env vars or config options

**See also:** [related-doc.md](path/to/related-doc.md)
```

### Quick Checks Before Commit

- [ ] `docs/INDEX.md` structure map current?
- [ ] Changed files have updated Last Updated date?
- [ ] New features documented?
- [ ] Removed features archived or deleted from docs?

## Execution Modes (Fabrik Lifecycle)

| Mode | Task Type | Model | Reasoning | Autonomy |
|------|-----------|-------|-----------|----------|
| Explore | `analyze` | gemini-3-flash-preview | off | low |
| Design | `spec` | claude-sonnet-4-5-20250929 | **high** | low |
| Build | `code, scaffold` | gpt-5.1-codex-max | medium | **high** |
| Verify | `test, health` | gpt-5.1-codex-max / gemini-3-flash-preview | low/off | **high** |
| Ship | `deploy` | gemini-3-flash-preview | off | **high** |

**Get current models:** `python3 scripts/droid_models.py stack-rank`

**Config:** `config/models.yaml` — Single source of truth for model names

**Mixed Models:** Use premium models with high reasoning for planning (`spec`), fast models for implementation (`code`).

**Code Review (Dual-Model):** Always use BOTH models from config, not alternatives:
```bash
# Get current model names from config/models.yaml
python3 scripts/droid_models.py recommend code_review

# Use the returned models (names may change)
for model in $(python3 -c "import yaml; c=yaml.safe_load(open('config/models.yaml')); print(' '.join(c['scenarios']['code_review']['models']))"); do
  droid exec -m "$model" "Review [files]..."
done
```

**Model Compatibility:** OpenAI only pairs with OpenAI. Anthropic with reasoning ON only pairs with Anthropic. See `droid-exec-usage.md` for details.

**Model Management (Automated):**
```bash
./scripts/setup_model_updates.sh               # Enable daily auto-updates (cron)
python3 scripts/droid_model_updater.py         # Force update now
python3 scripts/droid_models.py stack-rank     # View current rankings
python3 scripts/droid_models.py recommend ci_cd # Get model for scenario
```
**Config:** `config/models.yaml` — Auto-updated from Factory docs daily

## Implementing Large Features

For projects touching 30+ files, use the phased workflow:

```bash
# 1. Create master plan with spec mode
droid exec --use-spec "Create implementation plan for [feature]. Break into
phases completable in 1-2 days with testing points."
# Save output as IMPLEMENTATION_PLAN.md

# 2. Implement phase by phase (fresh session per phase)
droid exec --auto medium "Implement Phase 1 per IMPLEMENTATION_PLAN.md.
Update doc to mark complete when done."

# 3. Commit and PR per phase
droid exec --auto medium "Commit Phase 1 changes with detailed message."
droid exec --auto medium "Create PR for Phase 1 on branch feature-phase-1."

# 4. Test each phase before moving on
droid exec --auto medium "Run tests for Phase 1. Verify functionality."
```

**Best practices:** Start read-only, maintain backward compatibility, use feature flags, plan rollback for each phase.

## Auto-Run Mode (Autonomy Levels)

Auto-Run lets droid execute work matching your risk tolerance without repeated confirmations.

| Level | What Runs Automatically | Typical Examples |
|-------|------------------------|------------------|
| **Default** | Read-only only | `ls`, `git status`, `cat` |
| **`--auto low`** | File edits, creation | `Edit`, `Create`, `git diff` |
| **`--auto medium`** | + Reversible changes | `npm install`, `git commit`, builds |
| **`--auto high`** | All non-blocked commands | `docker compose up`, `git push`, migrations |

**Risk Classification:**
- **Low risk** — Read-only, no irreversible damage
- **Medium risk** — Alters workspace, easy to undo
- **High risk** — Destructive, hard to rollback, security-sensitive

**Safety interlocks (always blocked, even in high):**
- `rm -rf /`, `dd of=/dev/*`
- Command substitution `$(...)`
- CLI security-flagged commands

**Fabrik preference:** Use `medium` for dev work, `high` for CI/CD.

## droid exec Quick Reference

### Direct CLI Usage

```bash
# Read-only analysis (default - no --auto flag)
droid exec "Analyze the auth system and create a plan"

# Safe file edits
droid exec --auto low "Add JSDoc comments to all functions"

# Development work (Fabrik default)
droid exec --auto medium "Install deps, run tests, fix issues"

# Full autonomy (CI/CD, deployments)
droid exec --auto high "Fix bug, test, commit, and push"

# Specification mode (plan before executing)
droid exec --use-spec "Add user authentication feature"
droid exec --use-spec --auto medium "Refactor auth module"

# Model selection (get current names from config/models.yaml)
# python3 scripts/droid_models.py recommend <scenario>
droid exec -m <model> "Quick analysis"
droid exec -m <model> -r high "Complex refactoring"

# Output formats
droid exec -o json "Analyze code"           # Structured for scripts
droid exec -o stream-json "Complex task"    # Real-time JSONL events
```

### Via Fabrik Task Runner

```bash
# Discovery Pipeline (NEW - idea → scope → spec)
python scripts/droid_core.py idea "Voice-controlled home automation"
python scripts/droid_core.py scope "home-automation"
python scripts/droid_core.py spec "home-automation"

# Spec mode (Design)
python scripts/droid_core.py spec "Plan the auth system"

# Scaffold (Build)
python scripts/droid_core.py scaffold "Create FastAPI service"

# Health check (Verify - autonomous)
python scripts/droid_core.py health "Verify deployment"

# Deploy config (Ship)
python scripts/droid_core.py deploy "Add Redis to compose"
```

### Task Types (13 total)

| Type | Use Case |
|------|----------|
| `idea` | Capture and explore product idea (NEW) |
| `scope` | Define IN/OUT boundaries (NEW) |
| `analyze`, `review` | Read-only analysis |
| `code`, `refactor` | Write changes |
| `spec` | Planning with reasoning |
| `test`, `health`, `preflight` | Verification |
| `scaffold`, `deploy`, `migrate` | Infrastructure |

### Key Flags

| Flag | Purpose |
|------|---------|
| `--auto low/medium/high` | Autonomy level |
| `--use-spec` | Specification mode (plan before code) |
| `-m <model>` | Model selection |
| `-r <level>` | Reasoning effort |
| `-o json/stream-json` | Output format |
| `--cwd <path>` | Working directory |
| `-s <id>` | Continue session |

## Batch Refactoring Scripts

Location: `scripts/droid/`

| Script | Purpose | Usage |
|--------|---------|-------|
| `refactor-imports.sh` | Organize Python imports | `./scripts/droid/refactor-imports.sh src` |
| `improve-errors.sh` | Improve error messages | `./scripts/droid/improve-errors.sh src` |
| `fix-lint.sh` | Fix lint violations | `./scripts/droid/fix-lint.sh src` |

All scripts support `DRY_RUN=true` for preview mode.

## Output Formats

| Flag | Format | Use Case |
|------|--------|----------|
| `--stream` | Real-time text | CLI feedback |
| `--debug` | Verbose tool calls | Web UI development, debugging |

```bash
# Verbose output showing tool calls
python scripts/droid_tasks.py analyze "Find auth code" --debug

# Streaming output
python scripts/droid_tasks.py analyze "Find auth code" --stream
```

## VPS Deployment (Coolify)

Install droid CLI on VPS host, apps call via subprocess:

```bash
# On VPS
curl -fsSL https://app.factory.ai/cli | sh
droid  # One-time browser auth
```

**For SaaS web apps:** Use `--output-format debug` for SSE streaming.
See `droid-exec-usage.md` §25-26 for full patterns.

## GitHub Actions Workflows

Location: `.github/workflows/`

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `droid-review.yml` | PR opened/updated | Automated code review with Fabrik checks |
| `update-docs.yml` | Push to main | Auto-update docs when code changes |
| `security-scanner.yml` | Weekly (Monday 9AM) | Vulnerability and secrets scan |
| `daily-maintenance.yml` | Daily (3AM) | Docs and test updates |

**Setup:** Add `FACTORY_API_KEY` to repository secrets.

## Fabrik Skills (Auto-Invoked)

Location: `~/.factory/skills/` (personal) or `<repo>/.factory/skills/` (workspace)

Skills are **model-invoked** — droids automatically apply them based on task context.

| Skill | Auto-Triggers On | Purpose |
|-------|------------------|---------|
| `fabrik-scaffold` | "new project", "create service" | Full project structure with all conventions |
| `fabrik-docker` | "dockerfile", "compose", "deploy" | Docker/Compose for ARM64 Coolify VPS |
| `fabrik-health-endpoint` | "health", "healthcheck" | Health endpoints that test dependencies |
| `fabrik-config` | "config", "environment", "settings" | os.getenv() patterns, .env.example |
| `fabrik-preflight` | "preflight", "deploy ready" | Pre-deployment validation checklist |
| `fabrik-api-endpoint` | "endpoint", "route", "API" | FastAPI patterns with Pydantic |
| `fabrik-watchdog` | "watchdog", "monitor", "auto-restart" | Service monitoring scripts |
| `fabrik-postgres` | "database", "postgres", "migration" | PostgreSQL + pgvector setup |

**How it works:** When you run `python scripts/droid_tasks.py scaffold "Create user-api"`, droid detects keywords and automatically invokes `fabrik-scaffold`, `fabrik-config`, `fabrik-docker`, ensuring ALL Fabrik conventions are followed.

## Custom Slash Commands (TUI)

Location: `~/.factory/commands/` (personal) or `<repo>/.factory/commands/` (workspace)

| Command | Type | Description |
|---------|------|-------------|
| `/health-check` | Executable | Check service health endpoints |

Usage in droid TUI: `/health-check 8000`

## Factory Settings

Settings file: `~/.factory/settings.json`

Key Fabrik settings:
- `autonomyLevel`: `auto-high` (full auto coding)
- `model`: See `config/models.yaml` for current recommendations
- `reasoningEffort`: `high`
- `specSaveEnabled`: `true`

Template: `/opt/fabrik/templates/scaffold/factory-settings.json`

## MCP (Model Context Protocol)

MCP servers extend droid with external tools. Config: `~/.factory/mcp.json`

| Server | Purpose | Priority |
|--------|---------|----------|
| `playwright` | E2E browser testing | High |
| `sentry` | Error tracking | High |
| `supabase` | Database management | High |
| `stripe` | Payments | Medium |
| `linear` | Issue tracking | Medium |
| `notion` | Documentation | Medium |

Template: `/opt/fabrik/templates/scaffold/factory-mcp.json`

Full documentation: `docs/reference/droid-exec-usage.md` §18

## Droid Hooks

Hooks execute at various points in droid's lifecycle. Location: `/opt/fabrik/.factory/hooks/`

| Hook | Purpose |
|------|---------|
| `fabrik-conventions.py` | Validates Fabrik conventions (no hardcoded localhost, proper images) |
| `secret-scanner.py` | Detects hardcoded secrets |
| `format-python.sh` | Auto-formats Python with ruff/black |
| `protect-files.sh` | Blocks edits to .env, credentials |
| `session-context.py` | Loads project context on session start |

Template: `/opt/fabrik/templates/scaffold/factory-hooks.json`

Full documentation: `docs/reference/droid-exec-usage.md` §19

## Agent Readiness Checklist

Fabrik projects target **Level 3+ (Standardized)** readiness.

**Why this matters:** Fast verification tools let Droid self-correct. Slow tools slow everything.

### Level 1: Functional
- [ ] README.md with setup instructions
- [ ] Linter configured (`ruff check .` / `npm run lint`)
- [ ] Type checker configured (`mypy .` / `npx tsc --noEmit`)
- [ ] Unit tests exist (`pytest` / `npm test`)

### Level 2: Documented
- [ ] AGENTS.md (symlink to `/opt/fabrik/AGENTS.md`)
- [ ] .env.example with all required vars
- [ ] Pre-commit hooks or CI validation
- [ ] compose.yaml for deployment

### Level 3: Standardized
- [ ] Integration tests
- [ ] Health check endpoint that tests dependencies
- [ ] Structured logging (JSON format)
- [ ] Secret scanning (no hardcoded credentials)
- [ ] Verification runs in <30 seconds

### Level 4: Optimized (Target)
- [ ] CI/CD pipeline with fast feedback (<5 min)
- [ ] Automated deployment via Coolify
- [ ] Metrics/observability

**Critical:** Keep verification fast. Tests >30s kill iteration speed.

**Evaluate readiness:** Run `/readiness-report` in droid TUI (not `droid exec`) to evaluate a repo. Requires `enableReadinessReport: true` in settings.

---

## Writing Effective Prompts

**Full guide:** `docs/reference/droid-exec-usage.md` §27-31

**Quick patterns:**
- **Feature:** Goal + files + similar code + verification
- **Bug fix:** Error + reproduction + relevant files
- **Refactor:** What to change + what to preserve
- **Review:** Scope + focus areas (security, performance)

**Example:**
```
Add rate limiting to login attempts with exponential backoff.
Similar pattern in middleware/rateLimit.ts.
Run auth tests to verify.
```

---

*Symlink: `ln -s /opt/fabrik/AGENTS.md AGENTS.md`*
*Complements: `.windsurfrules` (Windsurf-specific rules)*
