# Cascade Rules Export - WORKSPACE RULES (Part 5 of 5)

**Exported:** 2026-01-13
**Type:** WORKSPACE RULES
**Location:** `/opt/fabrik/AGENTS.md` (Second Half - Lines 300-654)

---

# FILE: AGENTS.md (Continued)

```markdown
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

**Code Review (Dual-Model):** Always use BOTH models from config:
```bash
python3 scripts/droid_models.py recommend code_review
for model in $(python3 -c "import yaml; c=yaml.safe_load(open('config/models.yaml')); print(' '.join(c['scenarios']['code_review']['models']))"); do
  droid exec -m "$model" "Review [files]..."
done
```

**Model Management (Automated):**
```bash
./scripts/setup_model_updates.sh               # Enable daily auto-updates
python3 scripts/droid_model_updater.py         # Force update now
python3 scripts/droid_models.py stack-rank     # View current rankings
python3 scripts/droid_models.py recommend ci_cd # Get model for scenario
```

## Implementing Large Features

For projects touching 30+ files, use the phased workflow:

```bash
# 1. Create master plan with spec mode
droid exec --use-spec "Create implementation plan for [feature]."

# 2. Implement phase by phase (fresh session per phase)
droid exec --auto medium "Implement Phase 1 per IMPLEMENTATION_PLAN.md."

# 3. Commit and PR per phase
droid exec --auto medium "Commit Phase 1 changes with detailed message."

# 4. Test each phase before moving on
droid exec --auto medium "Run tests for Phase 1. Verify functionality."
```

## Auto-Run Mode (Autonomy Levels)

| Level | What Runs Automatically | Typical Examples |
|-------|------------------------|------------------|
| **Default** | Read-only only | `ls`, `git status`, `cat` |
| **`--auto low`** | File edits, creation | `Edit`, `Create`, `git diff` |
| **`--auto medium`** | + Reversible changes | `npm install`, `git commit`, builds |
| **`--auto high`** | All non-blocked commands | `docker compose up`, `git push`, migrations |

**Safety interlocks (always blocked, even in high):**
- `rm -rf /`, `dd of=/dev/*`
- Command substitution `$(...)`

**Fabrik preference:** Use `medium` for dev work, `high` for CI/CD.

## droid exec Quick Reference

### Direct CLI Usage

```bash
droid exec "Analyze the auth system and create a plan"
droid exec --auto low "Add JSDoc comments to all functions"
droid exec --auto medium "Install deps, run tests, fix issues"
droid exec --auto high "Fix bug, test, commit, and push"
droid exec --use-spec "Add user authentication feature"
droid exec -m <model> "Quick analysis"
droid exec -o json "Analyze code"
```

### Via Fabrik Task Runner

```bash
python scripts/droid_core.py idea "Voice-controlled home automation"
python scripts/droid_core.py scope "home-automation"
python scripts/droid_core.py spec "home-automation"
python scripts/droid_core.py scaffold "Create FastAPI service"
python scripts/droid_core.py health "Verify deployment"
python scripts/droid_core.py deploy "Add Redis to compose"
```

### Task Types (13 total)

| Type | Use Case |
|------|----------|
| `idea` | Capture and explore product idea |
| `scope` | Define IN/OUT boundaries |
| `analyze`, `review` | Read-only analysis |
| `code`, `refactor` | Write changes |
| `spec` | Planning with reasoning |
| `test`, `health`, `preflight` | Verification |
| `scaffold`, `deploy`, `migrate` | Infrastructure |

### Key Flags

| Flag | Purpose |
|------|---------|
| `--auto low/medium/high` | Autonomy level |
| `--use-spec` | Specification mode |
| `-m <model>` | Model selection |
| `-r <level>` | Reasoning effort |
| `-o json/stream-json` | Output format |
| `--cwd <path>` | Working directory |
| `-s <id>` | Continue session |

## Batch Refactoring Scripts

Location: `scripts/droid/`

| Script | Purpose |
|--------|---------|
| `refactor-imports.sh` | Organize Python imports |
| `improve-errors.sh` | Improve error messages |
| `fix-lint.sh` | Fix lint violations |

All scripts support `DRY_RUN=true` for preview mode.

## Fabrik Skills (Auto-Invoked)

Location: `~/.factory/skills/` (personal) or `<repo>/.factory/skills/` (workspace)

| Skill | Auto-Triggers On | Purpose |
|-------|------------------|---------|
| `fabrik-scaffold` | "new project", "create service" | Full project structure |
| `fabrik-docker` | "dockerfile", "compose", "deploy" | Docker/Compose for ARM64 |
| `fabrik-health-endpoint` | "health", "healthcheck" | Health endpoints |
| `fabrik-config` | "config", "environment" | os.getenv() patterns |
| `fabrik-preflight` | "preflight", "deploy ready" | Pre-deployment validation |
| `fabrik-api-endpoint` | "endpoint", "route", "API" | FastAPI patterns |
| `fabrik-watchdog` | "watchdog", "monitor" | Service monitoring |
| `fabrik-postgres` | "database", "postgres" | PostgreSQL + pgvector |

## Droid Hooks

Location: `/opt/fabrik/.factory/hooks/`

| Hook | Purpose |
|------|---------|
| `fabrik-conventions.py` | Validates Fabrik conventions |
| `secret-scanner.py` | Detects hardcoded secrets |
| `format-python.sh` | Auto-formats Python |
| `protect-files.sh` | Blocks edits to .env, credentials |
| `session-context.py` | Loads project context |

## Agent Readiness Checklist

### Level 1: Functional
- [ ] README.md with setup instructions
- [ ] Linter configured
- [ ] Type checker configured
- [ ] Unit tests exist

### Level 2: Documented
- [ ] AGENTS.md (symlink to `/opt/fabrik/AGENTS.md`)
- [ ] .env.example with all required vars
- [ ] Pre-commit hooks or CI validation
- [ ] compose.yaml for deployment

### Level 3: Standardized
- [ ] Integration tests
- [ ] Health check endpoint that tests dependencies
- [ ] Structured logging (JSON format)
- [ ] Secret scanning
- [ ] Verification runs in <30 seconds

### Level 4: Optimized (Target)
- [ ] CI/CD pipeline with fast feedback (<5 min)
- [ ] Automated deployment via Coolify
- [ ] Metrics/observability

## Writing Effective Prompts

**Quick patterns:**
- **Feature:** Goal + files + similar code + verification
- **Bug fix:** Error + reproduction + relevant files
- **Refactor:** What to change + what to preserve
- **Review:** Scope + focus areas

**Example:**
```
Add rate limiting to login attempts with exponential backoff.
Similar pattern in middleware/rateLimit.ts.
Run auth tests to verify.
```

---

*Symlink: `ln -s /opt/fabrik/AGENTS.md AGENTS.md`*
*Complements: `.windsurfrules` (Windsurf-specific rules)*
```
