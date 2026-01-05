# Fabrik Project Agent Briefing

> Standard instructions for AI coding agents (droid exec, Cursor, Aider, etc.)

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

### When Making Changes

1. **Update docs/README.md structure map** if adding/moving/deleting files
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

- [ ] `docs/README.md` structure map current?
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

# Model selection
droid exec -m gemini-3-flash-preview "Quick analysis"
droid exec -m gpt-5.1-codex-max -r high "Complex refactoring"

# Output formats
droid exec -o json "Analyze code"           # Structured for scripts
droid exec -o stream-json "Complex task"    # Real-time JSONL events
```

### Via Fabrik Task Runner

```bash
# Spec mode (Design)
python scripts/droid_tasks.py spec "Plan the auth system"

# Scaffold (Build)
python scripts/droid_tasks.py scaffold "Create FastAPI service"

# Health check (Verify - autonomous)
python scripts/droid_tasks.py health "Verify deployment"

# Deploy config (Ship)
python scripts/droid_tasks.py deploy "Add Redis to compose"
```

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
- `model`: `gpt-5.1-codex-max`
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
