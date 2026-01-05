# Fabrik Hooks and Skills Guide

> Complete reference for all Factory hooks and skills used in Fabrik automation.

Last updated: 2025-01-03

---

## Overview

**Hooks** run automatically at specific points in droid execution.
**Skills** are invoked automatically when keywords are detected in prompts.

Together, they enable Cascade to drive droid exec with high automation success.

---

## Part 1: Hooks

All hooks are located at `~/.factory/hooks/`

### Hook Execution Points

| Hook Type | When It Runs | Can Block? |
|-----------|--------------|------------|
| `PreToolUse` | Before tool execution | ✅ Yes (exit 2) |
| `PostToolUse` | After tool execution | ✅ Yes (exit 2) |
| `SessionStart` | When session begins | ❌ No |
| `Notification` | When droid sends notification | ❌ No |

---

### Hook 1: `secret-scanner.py`

**Type:** PostToolUse
**File:** `~/.factory/hooks/secret-scanner.py`
**Lines:** 150

#### Purpose
Prevents hardcoded secrets from being written to code. Scans every file write/edit for credential patterns and blocks if found.

#### Patterns Detected

| Pattern | Regex | Example |
|---------|-------|---------|
| AWS Access Key | `AKIA[0-9A-Z]{16}` | `AKIAIOSFODNN7EXAMPLE` |
| AWS Secret | `aws_secret_access_key\s*=\s*[\'"][A-Za-z0-9/+=]{40}[\'"]` | |
| Google API Key | `AIza[0-9A-Za-z\-_]{35}` | `AIzaSyA...` |
| OpenAI Key | `sk-[a-zA-Z0-9]{32,}` | `sk-abc123...` |
| Anthropic Key | `sk-ant-[a-zA-Z0-9\-]{32,}` | `sk-ant-...` |
| GitHub PAT | `ghp_[a-zA-Z0-9]{36}` | `ghp_abc123...` |
| GitHub OAuth | `gho_[a-zA-Z0-9]{36}` | |
| GitHub Fine-grained | `github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}` | |
| GitLab Token | `glpat-[a-zA-Z0-9\-]{20}` | |
| Stripe Live | `sk_live_[a-zA-Z0-9]{24,}` | |
| Stripe Restricted | `rk_live_[a-zA-Z0-9]{24,}` | |
| Database URL | `postgresql://[^:]+:[^@]+@` | `postgresql://user:pass@host` |
| MySQL URL | `mysql://[^:]+:[^@]+@` | |
| MongoDB URL | `mongodb://[^:]+:[^@]+@` | |
| Generic Credential | `(?:password\|passwd\|pwd\|secret\|token\|api_key)\s*[:=]\s*[\'"][^\'"]{8,}[\'"]` | `password = "abc123"` |

#### Skip Patterns
- `.env.example`, `.env.sample`
- Test files (`test*.py`, `*_test.py`, `*.test.ts`)
- Fixtures and mocks directories
- Binary files (.jpg, .png, .pdf, .zip, etc.)

#### How Cascade Uses This
When I write code that accidentally contains a credential, this hook blocks me and tells me to use environment variables instead. This prevents security incidents before they happen.

#### Exit Codes
- `0` — Pass (no secrets found)
- `2` — Block with feedback (secrets detected)

---

### Hook 2: `fabrik-conventions.py`

**Type:** PostToolUse
**File:** `~/.factory/hooks/fabrik-conventions.py`
**Lines:** 149

#### Purpose
Enforces Fabrik coding standards automatically. Catches common mistakes that would break deployment.

#### Violations Detected

| Violation | Severity | File Types | What It Catches |
|-----------|----------|------------|-----------------|
| `hardcoded_localhost` | Error | .py | `host = 'localhost'` without getenv |
| `alpine_image` | Error | Dockerfile | `FROM python:3.12-alpine` |
| `class_config` | Warning | .py | Class-level `os.getenv()` calls |
| `fake_health` | Warning | .py | Health returning ok without testing |
| `hardcoded_password` | Error | .py, .yaml, .json | `password = "abc123"` |
| `system_tmp` | Warning | .py, .sh | Using `/tmp/` instead of `.tmp/` |

#### How Cascade Uses This
When I write code that violates Fabrik conventions, this hook warns me (for warnings) or blocks me (for errors). This ensures code works across WSL, Docker, and Supabase without modification.

#### Exit Codes
- `0` — Pass (or warnings only)
- `2` — Block (errors detected)

---

### Hook 3: `protect-files.sh`

**Type:** PreToolUse
**File:** `~/.factory/hooks/protect-files.sh`
**Lines:** 52

#### Purpose
Prevents AI from modifying sensitive files that should be edited manually.

#### Protected Patterns
```
.env, .env.local, .env.production, .env.development
.git/
node_modules/, __pycache__/
.pem, .key, .p12, .crt (certificates)
credentials.json, secrets.json
.ssh/, id_rsa
.gnupg/
```

#### How Cascade Uses This
If I accidentally try to edit your `.env` file or SSH keys, this hook blocks me. You must edit sensitive files manually, which is the correct security practice.

#### Exit Codes
- `0` — Pass (file not protected)
- `2` — Block (protected file)

---

### Hook 4: `format-python.sh`

**Type:** PostToolUse
**File:** `~/.factory/hooks/format-python.sh`
**Lines:** 45

#### Purpose
Auto-formats Python code after every edit using ruff (fast) or black (fallback).

#### What It Does
1. Checks if file is `.py`
2. Skips fixtures, generated files, `__pycache__`
3. Runs `ruff format` (preferred)
4. Runs `ruff check --fix` (auto-fix lints)
5. Falls back to `black` if ruff unavailable

#### How Cascade Uses This
After I write Python code, this hook automatically formats it. I don't need to worry about formatting — it happens automatically. This keeps code style consistent.

#### Exit Codes
- `0` — Always (non-blocking)

---

### Hook 5: `log-commands.sh`

**Type:** PreToolUse
**File:** `~/.factory/hooks/log-commands.sh`
**Lines:** 26

#### Purpose
Creates audit trail of all bash commands executed by droid.

#### Log Location
`~/.factory/logs/droid-commands-YYYY-MM-DD.log`

#### Log Format
```
[2025-01-03 01:55:00] session=abc123 command="git status"
[2025-01-03 01:55:05] session=abc123 command="docker compose up"
```

#### How Cascade Uses This
Every command I run is logged. You can review what happened, debug issues, or audit for compliance. This is especially useful when something goes wrong.

#### Exit Codes
- `0` — Always (non-blocking)

---

### Hook 6: `notify.sh`

**Type:** Notification
**File:** `~/.factory/hooks/notify.sh`
**Lines:** 33

#### Purpose
Sends desktop notification when droid needs attention.

#### Notification Methods
1. **Linux:** `notify-send`
2. **WSL:** PowerShell toast notification
3. **Fallback:** Echo to terminal

#### How Cascade Uses This
When droid completes a long task or needs your input, this hook sends a desktop notification so you don't have to watch the terminal.

#### Exit Codes
- `0` — Always (non-blocking)

---

### Hook 7: `session-context.py`

**Type:** SessionStart
**File:** `~/.factory/hooks/session-context.py`
**Lines:** 147

#### Purpose
Loads project context when a droid session starts, giving droid relevant information about the project.

#### What It Detects
- Is this a Fabrik project? (AGENTS.md, .windsurfrules)
- Project type (Python, Node, Go, Rust)
- Has Dockerfile? Has compose.yaml?
- Has .env.example?
- Has tests directory?
- Recently modified files (for resume sessions)

#### Context Output
```
This is a Fabrik project. Follow Fabrik conventions:
- Use os.getenv() for all config, never hardcode localhost
- Base images: python:3.12-slim-bookworm (not Alpine)
- Health endpoints must test actual dependencies
- See AGENTS.md for full standards

Project type: python
⚠️ Missing Dockerfile - needed for Coolify deployment
```

#### How Cascade Uses This
When I start a droid session, this hook tells droid about the project context. This helps droid follow the right conventions from the start.

#### Exit Codes
- `0` — Always (non-blocking, output goes to droid context)

---

## Part 2: Skills

All skills are located at `~/.factory/skills/<skill-name>/SKILL.md`

Skills are markdown files that droid reads when certain keywords are detected. They provide detailed instructions for specific tasks.

---

### Skill 1: `fabrik-scaffold`

**Location:** `~/.factory/skills/fabrik-scaffold/SKILL.md`
**Lines:** 199

#### Triggers
- "new project"
- "create service"
- "scaffold"
- "bootstrap"

#### What It Creates
```
/opt/<project>/
├── src/
│   ├── __init__.py
│   ├── main.py            # FastAPI with /health
│   ├── config.py          # os.getenv() patterns
│   ├── models/
│   ├── services/
│   └── api/
├── tests/
├── scripts/watchdog_api.sh
├── docs/
├── logs/, .tmp/, data/
├── Dockerfile             # python:3.12-slim-bookworm
├── compose.yaml           # Coolify-ready
├── .env.example
├── .gitignore
├── pyproject.toml         # ruff + mypy
├── README.md, CHANGELOG.md, tasks.md
├── AGENTS.md              # Symlink
└── .windsurfrules         # Symlink
```

#### How Cascade Uses This
When you say "new project" or "create a service", droid invokes this skill and follows its detailed instructions. This ensures every project starts with the correct structure.

---

### Skill 2: `fabrik-docker`

**Location:** `~/.factory/skills/fabrik-docker/SKILL.md`
**Lines:** 181

#### Triggers
- "dockerfile"
- "compose"
- "container"
- "deploy"
- "coolify"

#### Key Rules
- **NEVER use Alpine** — Use `python:3.12-slim-bookworm`
- **ARM64 required** — VPS is ARM64 architecture
- **Healthcheck required** — Both in Dockerfile and compose.yaml
- **coolify network** — Use `networks: coolify: external: true`

#### How Cascade Uses This
When creating Docker configurations, droid follows these rules. This prevents the common mistake of using Alpine (which breaks on ARM64) and ensures deployments work on your VPS.

---

### Skill 3: `fabrik-health-endpoint`

**Location:** `~/.factory/skills/fabrik-health-endpoint/SKILL.md`
**Lines:** 194

#### Triggers
- "health"
- "healthcheck"
- "monitoring"

#### Critical Rule
**Health endpoints MUST test actual dependencies.** Returning `{"status": "ok"}` without testing DB is USELESS.

#### Proper Pattern
```python
@router.get("/health")
async def health():
    # Actually test database
    await db.execute("SELECT 1")
    # Actually test Redis
    await redis.ping()
    return {"status": "ok", "db": "connected"}
```

#### How Cascade Uses This
When creating health endpoints, droid follows this skill to ensure health checks actually test dependencies. This prevents "green" health checks that hide real failures.

---

### Skill 4: `fabrik-config`

**Location:** `~/.factory/skills/fabrik-config/SKILL.md`
**Lines:** 216

#### Triggers
- "config"
- "settings"
- "environment"

#### Critical Rules
1. **NEVER hardcode localhost**
2. **NEVER hardcode credentials**
3. **NEVER use class-level config** (env vars not set at import time)

#### Correct Pattern
```python
def get_database_url():
    host = os.getenv('DB_HOST', 'localhost')
    return f"postgresql://...@{host}:..."
```

#### How Cascade Uses This
When setting up configuration, droid uses these patterns. This ensures code works in WSL (localhost), Docker (postgres-main), and Supabase without changes.

---

### Skill 5: `fabrik-preflight`

**Location:** `~/.factory/skills/fabrik-preflight/SKILL.md`
**Lines:** 186

#### Triggers
- "deploy"
- "preflight"
- "ready"
- "production"

#### Check Categories
1. **Configuration** — No hardcoded values
2. **Docker** — Correct base image, healthcheck
3. **Health Endpoint** — Tests dependencies
4. **Code Quality** — ruff, mypy, pytest pass
5. **Documentation** — README, DEPLOYMENT.md
6. **Security** — No secrets in code

#### How Cascade Uses This
Before deployment, I run preflight checks. This catches issues before they reach production. If any check fails, deployment is blocked until fixed.

---

### Skill 6: `fabrik-api-endpoint`

**Location:** `~/.factory/skills/fabrik-api-endpoint/SKILL.md`
**Lines:** 226

#### Triggers
- "endpoint"
- "route"
- "API"
- "REST"

#### Required Patterns
- Type hints on all parameters
- Pydantic models for request/response
- Proper HTTP status codes (201 for create, 204 for delete)
- Error handling with HTTPException
- Logging at appropriate levels
- Parameterized SQL (no f-strings!)

#### How Cascade Uses This
When creating API endpoints, droid follows these patterns. This ensures consistent, type-safe, well-logged APIs.

---

### Skill 7: `fabrik-watchdog`

**Location:** `~/.factory/skills/fabrik-watchdog/SKILL.md`
**Lines:** 262

#### Triggers
- "watchdog"
- "auto-restart"
- "monitor"

#### Rule
**Any service that should stay running MUST have a watchdog.**

#### What It Creates
```bash
./scripts/watchdog_api.sh start    # Start
./scripts/watchdog_api.sh stop     # Stop
./scripts/watchdog_api.sh status   # Status
./scripts/watchdog_api.sh watch    # Start with auto-restart
```

#### How Cascade Uses This
When creating services, droid includes watchdog scripts. This ensures services auto-restart on failure.

---

### Skill 8: `fabrik-postgres`

**Location:** `~/.factory/skills/fabrik-postgres/SKILL.md`
**Lines:** 250

#### Triggers
- "database"
- "postgres"
- "migration"

#### What It Covers
- asyncpg connection pooling
- Config via os.getenv()
- Alembic migrations
- pgvector for embeddings
- Health check with DB
- Backup scripts

#### How Cascade Uses This
When setting up database connections, droid follows these patterns. This ensures proper pooling, correct host configuration per environment, and backup capability.

---

### Skill 9: `fabrik-saas-scaffold`

**Location:** `~/.factory/skills/fabrik-saas-scaffold/SKILL.md`
**Lines:** 131

#### Triggers
- "SaaS"
- "web app"
- "dashboard"
- "subscription app"

#### What It Provides
```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/<project-name>
```

Includes:
- Next.js 14 + TypeScript + Tailwind
- Marketing pages (landing, pricing, FAQ, terms, privacy)
- App pages (dashboard, settings, job workflow)
- ChatUI with SSE streaming
- Supabase-ready auth

#### How Cascade Uses This
When you ask for a SaaS or web app, droid copies this template instead of building from scratch. This saves hours of boilerplate work.

---

### Skill 10: `documentation-generator`

**Location:** `~/.factory/skills/documentation-generator/SKILL.md`
**Lines:** 12

#### Triggers
- Significant code changes
- Explicit documentation requests

#### Commands
- `generate-api-docs` — Scans source, updates API docs
- `update-readme` — Updates README with project structure

#### How Cascade Uses This
After making significant code changes, droid can auto-update documentation. This keeps docs in sync with code.

---

## Part 3: How Cascade Uses Everything Together

### Typical Workflow

```
1. You: "Create a new API service called image-broker"
   │
   ├─▶ SessionStart hook runs → session-context.py loads project info
   │
   ├─▶ Droid detects "new" + "service" → invokes fabrik-scaffold skill
   │
   ├─▶ For each file write:
   │   ├─▶ PreToolUse: protect-files.sh checks if protected
   │   ├─▶ PreToolUse: log-commands.sh logs if bash
   │   ├─▶ [WRITE HAPPENS]
   │   ├─▶ PostToolUse: secret-scanner.py scans for secrets
   │   ├─▶ PostToolUse: fabrik-conventions.py checks patterns
   │   └─▶ PostToolUse: format-python.sh formats if .py
   │
   ├─▶ When complete: notify.sh sends desktop notification
   │
   └─▶ Result: Complete project structure following all conventions
```

### What Gets Blocked

| Scenario | Hook | Result |
|----------|------|--------|
| Writing API key in code | secret-scanner.py | ❌ Blocked |
| Using `localhost` hardcoded | fabrik-conventions.py | ❌ Blocked |
| Using Alpine in Dockerfile | fabrik-conventions.py | ❌ Blocked |
| Editing .env file | protect-files.sh | ❌ Blocked |
| Fake health endpoint | fabrik-conventions.py | ⚠️ Warning |

---

## Part 4: Gaps for 100% Automation Success

### Current Success Rate: ~85%

The hooks and skills cover most common cases, but there are gaps:

### Gap 1: No Test Generation Skill

**Problem:** When creating new code, tests should be generated automatically.

**Current state:** Tests are sometimes created, sometimes not.

**Solution needed:** `fabrik-test-generator` skill that:
- Auto-generates tests for new functions/endpoints
- Follows pytest patterns
- Includes edge cases

### Gap 2: No Rollback Hook

**Problem:** When something breaks, there's no automatic rollback.

**Current state:** Manual git revert required.

**Solution needed:** `rollback-on-failure` hook that:
- Detects test failures after code changes
- Offers automatic rollback to last working state
- Keeps backup of changes for review

### Gap 3: No Dependency Check Hook

**Problem:** Adding imports for packages not in requirements.txt.

**Current state:** Import errors discovered at runtime.

**Solution needed:** `dependency-checker` hook that:
- Scans imports after file edit
- Checks against requirements.txt/pyproject.toml
- Auto-adds missing dependencies or warns

### Gap 4: No Type Check Hook

**Problem:** Type errors not caught until mypy runs manually.

**Current state:** Type errors may slip through.

**Solution needed:** `type-checker` hook that:
- Runs mypy on edited Python files
- Warns on type errors
- Suggests fixes

### Gap 5: No Test Runner Hook

**Problem:** Tests not automatically run after code changes.

**Current state:** Tests run manually or at deployment.

**Solution needed:** `auto-test` hook that:
- Runs relevant tests after code changes
- Reports failures immediately
- Blocks if critical tests fail

### Gap 6: No Database Migration Skill

**Problem:** Schema changes not automatically handled.

**Current state:** Manual Alembic commands required.

**Solution needed:** Enhanced `fabrik-postgres` skill that:
- Detects model changes
- Auto-generates migrations
- Validates migration safety

---

## Part 5: Recommended New Hooks/Skills

### Priority 1: Create Now

| Name | Type | Purpose |
|------|------|---------|
| `dependency-checker.py` | PostToolUse | Check imports vs requirements |
| `auto-test.sh` | PostToolUse | Run tests after code changes |
| `fabrik-test-generator` | Skill | Generate tests for new code |

### Priority 2: Create Later

| Name | Type | Purpose |
|------|------|---------|
| `type-checker.py` | PostToolUse | Run mypy on changes |
| `rollback-on-failure.py` | PostToolUse | Auto-rollback on test fail |
| `fabrik-migration` | Skill | Auto-generate DB migrations |

---

## Summary

### Current Coverage

| Category | Hooks | Skills | Coverage |
|----------|-------|--------|----------|
| Security | 2 (secret-scanner, protect-files) | 0 | ✅ Good |
| Code Quality | 2 (conventions, format) | 1 (api-endpoint) | ✅ Good |
| Project Setup | 1 (session-context) | 4 (scaffold, docker, config, saas) | ✅ Good |
| Deployment | 0 | 2 (preflight, watchdog) | ✅ Good |
| Database | 0 | 2 (postgres, health) | ✅ Good |
| Testing | 0 | 0 | ❌ Gap |
| Dependencies | 0 | 0 | ❌ Gap |
| Type Safety | 0 | 0 | ⚠️ Partial |

### For 100% Success

Need to add:
1. **dependency-checker** hook — Catch missing imports
2. **auto-test** hook — Run tests after changes
3. **fabrik-test-generator** skill — Generate tests automatically
