# Project Agent Briefing

> Instructions for AI coding agents (droid exec, Cursor, Windsurf, etc.)

## Build & Test

```bash
# Install and test
pip install -e .
pytest

# Code quality
ruff check .
mypy .

# Docker
docker compose up -d
docker compose logs -f
```

## Run Locally

```bash
uvicorn src.main:app --reload --port 8000
curl http://localhost:8000/health
```

## droid exec Quick Reference

```bash
# Read-only analysis (safe default)
droid exec "Analyze this codebase"

# File edits
droid exec --auto low "Add comments to functions"

# Development (recommended)
droid exec --auto medium "Install deps and run tests"

# Full autonomy
droid exec --auto high "Fix, test, commit, push"

# Specification mode (plan before code)
droid exec --use-spec "Add authentication"
droid exec --use-spec --auto medium "Refactor module"

# Model + reasoning
droid exec -m gemini-3-flash-preview "Quick task"
droid exec -m gpt-5.1-codex-max -r high "Complex task"

# Output formats
droid exec -o json "task"          # Structured
droid exec -o stream-json "task"   # Real-time JSONL
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

### Auto-Run Mode (Risk-Based Autonomy)

| Level | What Runs Automatically | Use Case |
|-------|------------------------|----------|
| **Default** | Read-only only | Safe exploration |
| **`--auto low`** | + File edits | Docs, formatting |
| **`--auto medium`** | + Reversible changes (installs, commits) | Dev work |
| **`--auto high`** | All non-blocked commands | CI/CD, deployments |

**Always blocked:** `rm -rf /`, `dd of=/dev/*`, command substitution `$(...)`, CLI security flags.

### Model Management (Automated)

```bash
./scripts/setup_model_updates.sh               # Enable daily auto-updates (cron)
python3 scripts/droid_model_updater.py         # Force update now
python3 scripts/droid_models.py stack-rank     # View current rankings
python3 scripts/droid_models.py recommend ci_cd # Get model for scenario
```

**Config:** `config/models.yaml` — Auto-updated from Factory docs daily

### Implementing Large Features (30+ files)

```bash
# 1. Master plan with spec mode
droid exec --use-spec "Create implementation plan for [feature]"
# Save as IMPLEMENTATION_PLAN.md

# 2. Phase by phase (fresh session each)
droid exec --auto medium "Implement Phase 1 per IMPLEMENTATION_PLAN.md"

# 3. Commit per phase
droid exec --auto medium "Commit Phase 1 with detailed message"
```

**Key:** Fresh session per phase, test after each, plan rollback.

## Conventions

### Environment Variables (CRITICAL)

```python
# CORRECT - works everywhere
DB_HOST = os.getenv('DB_HOST', 'localhost')

# WRONG - breaks in production
DB_HOST = 'localhost'  # Hardcoded!
```

### Health Checks

```python
# CORRECT - tests actual dependencies
@app.get("/health")
async def health():
    await db.execute("SELECT 1")
    return {"status": "ok", "db": "connected"}

# WRONG - hides failures
@app.get("/health")
async def health():
    return {"status": "ok"}  # Lies!
```

## Gotchas

1. **Never use `/tmp/`** — Use project-local `.tmp/` instead
2. **Health checks must test dependencies** — Not just return `{"status": "ok"}`
3. **Env vars not set at import time** — Load config in functions, not class-level
4. **Test in Docker before deploying** — `docker compose up` locally first

## Project Structure

```
├── src/
│   ├── main.py            # Entry point
│   ├── config.py          # Config (os.getenv patterns)
│   ├── models/            # Data models
│   ├── services/          # Business logic
│   └── api/               # API endpoints
├── tests/                 # Tests mirror src/
├── scripts/               # Utility scripts
├── compose.yaml           # Docker Compose
├── Dockerfile             # Production build
├── .env.example           # Env var template
└── AGENTS.md              # This file
```

## Security

- **Never commit `.env`** — Use `.env.example` as template
- **CSPRNG passwords**: 32 chars, alphanumeric only
- **No hardcoded secrets** — Always use env vars
