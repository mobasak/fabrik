---
activation: always_on
description: Critical Fabrik rules - ALWAYS enforced (Windsurf Cascade only)
trigger: always_on
---

# Critical Rules (ALWAYS ACTIVE)

**Scope:** These rules apply to **Windsurf Cascade** agents working on any project under `/opt/`. Not for Kilo CLI agents.

---

## Orientation — Do This First (MANDATORY)

**Scan before you act.** Read the full project structure from root. Locate and read any present:
- `README.md`, `AGENTS.md`
- `docker-compose.yml`, `Dockerfile`
- `.env.example`, `pyproject.toml`, `package.json`, `requirements.txt`

**Do not generate anything until this scan is complete.**

**Do not** recreate `.venv` or replace existing Docker configuration unless explicitly instructed.

---

## Environment Context

**Runtime is WSL (Ubuntu).** Linux paths and commands only. Never assume Windows tooling.

**Follow the project scaffold structure verbatim.** Do not reorganize, flatten, or add directories.

**All architectural decisions, base images, and tool choices are resolved before you start** — execute the plan as given. Do not expand scope silently.

**Target deployment:** Linux VPS + container orchestration, optionally Supabase. ARM-compatible builds by default.

**If anything in the task contradicts what exists in the project, stop and report.** Do not silently overwrite.

## ⚠️ MANDATORY WORKFLOW (March 2026)

**PLAN → IMPLEMENT → SELF_REVIEW → FINAL_GATE → KILO_REVIEW → FIX → TRAYCER_VERIFY → COMMIT**

| Step | Who | Action | Gate |
|------|-----|--------|------|
| 1 | **Traycer** | Creates plan | Spec exists with requirements |
| 2 | **Cascade** | Implements code | Code only what phase requires |
| 2.5 | **Cascade** | Self-review | Reviews own work (MANDATORY) |
| 3 | **Cascade** | Final Gate | `python /opt/fabrik/scripts/final_gate.py` → all PASS |
| 4 | **Cascade** | Kilo Review | `python scripts/kilo_code_review.py staged --plan "..."` → report issues |
| 5 | **Cascade** | Fixes issues | Fix reported issues, re-run review until PASS |
| 6 | **Traycer** | Verifies | Traycer verifier confirms SPEC compliance |
| 7 | **Traycer** | Commits | Pre-commit runs 4 blockers only |

**Kilo Review (report-only by default):**
```bash
# Auto-selects model based on risk level (no manual selection needed)
python /opt/fabrik/scripts/kilo_code_review.py staged --plan "task description" --output json

# Risk → Model routing (automatic):
# - low (docs only) → Free tier (minimax, glm-4.7-free)
# - medium (normal code) → Economy tier (gemini-flash-lite)
# - high (src/, scripts/, >400 lines) → Balanced tier (glm-4.7)
# - critical (auth/, security/, secrets) → Strong tier (glm-5, claude-sonnet)
```

**Key Changes (March 2026):**
- `kilo_code_review.py` replaces `reviewer_selector.py` (archived)
- Default is **report-only** - Cascade fixes issues, not Kilo
- Model selection is **automatic** based on file paths and diff size
- Session isolation is **automatic** (no manual `--tracked-review-id` needed)
- Use `--fix` flag only if you want Kilo to auto-fix (costs more)

**Notes:**
- Final Gate runs deterministic checks (lint, type check, security scan)
- Kilo Review runs AI review (SPEC compliance, edge cases, security)
- **Traycer commits, not Cascade** — Cascade only implements and fixes
- Pre-commit runs ONLY 4 blockers: large-files, merge-conflict, private-key, secrets

**If I skip these steps, the user should call me out.**
---

## Sensitive Data Protection (CRITICAL)

**Before modifying ANY file containing credentials/secrets:**
- `.env`, `.env.*` (except `.env.example`)
- `*.key`, `*.pem`, `*.p12`, `*.pfx`
- Files in `secrets/`, `credentials/`, `.ssh/`

**MUST create timestamped backup first:**
```bash
cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
```

**Then verify backup exists before proceeding.**

**Violations:**
- Modifying `.env` without backup = STOP immediately
- Running destructive scripts on production data without dry-run test = FORBIDDEN
- Applying changes to credentials without showing full diff first = FORBIDDEN

**Enforcement:** Pre-commit hook + manual AI review discipline.

---
## Before Creating New Scripts (MANDATORY)

Before writing ANY new script, I MUST:
1. `grep_search` for similar functionality in scripts/
2. Check if existing scripts in scripts/ or scripts/enforcement/ handle it
3. If existing code can be extended → extend it, don't create new

**Violation:** Creating duplicate functionality.
---

## Environment Variables (CRITICAL)

**NEVER hardcode these values:**
- `localhost`, `127.0.0.1`
- Database connection strings
- API keys, tokens, passwords

**ALWAYS use:**
```python
# CORRECT
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))

# WRONG - breaks in Docker/VPS
DB_HOST = 'localhost'
```

---

## Target Environments

Code MUST work in ALL environments without modification:

| Environment | Database | Config Source |
|-------------|----------|---------------|
| WSL (dev) | PostgreSQL localhost | `.env` file |
| VPS Docker | postgres-main container | compose.yaml |
| Supabase | Supabase PostgreSQL | env vars |

---

## Health Checks (MUST Test Dependencies)

```python
# CORRECT - tests actual DB
@app.get("/health")
async def health():
    await db.execute("SELECT 1")
    return {"status": "ok", "db": "connected"}

# WRONG - hides failures
@app.get("/health")
async def health():
    return {"status": "ok"}  # Lies!
```

---

## Security Gates

### Credentials Storage (TWO PLACES)
1. Project `.env` - local use
2. `/opt/fabrik/.env` - master backup

### Password Policy (CSPRNG)
- Length: 32 characters
- Characters: `[a-zA-Z0-9]`
- Generator: `secrets.choice()`
- **FORBIDDEN:** `postgres`, `admin`, `password123`

---

## Forbidden Actions

| Action | Use Instead |
|--------|-------------|
| `/tmp/` directory | Project `.tmp/` |
| Hardcoded localhost | `os.getenv()` |
| Alpine base images | `python:3.12-slim-bookworm` |
| Class-level config | Function-level loading |
| Bare `pip install` | `/opt/fabrik/.venv/bin/pip install` |

### PEP 668: WSL/Debian Venv Requirement (CRITICAL)

WSL and modern Debian block system-wide pip installs. **NEVER** run bare `pip install`.

```bash
# WRONG - will fail with "externally-managed-environment"
pip install textual

# CORRECT - use Fabrik master venv
/opt/fabrik/.venv/bin/pip install textual

# CORRECT - project-specific venv
/opt/<project>/.venv/bin/pip install textual
```

The Fabrik master venv (`/opt/fabrik/.venv/`) hosts cross-project tools like `kilo_terminal_runner.py`.
---

## Cascade Behavior Rules (STRICT)

| Rule | Description |
|------|-------------|
| **Check before create** | ALWAYS verify file exists (`ls`, `find`, `read_file`) before `write_to_file` |
| **Present before execute** | Present solution/plan first, wait for user approval, then execute |
| **No unsolicited advice** | Never suggest breaks, lifestyle tips, or non-task commentary |

**Violations:**
- Attempting to create a file that already exists = STOP, acknowledge error
- Executing commands without presenting plan first = violation
- Suggesting breaks or personal advice = violation

---

## Port Management

| Range | Purpose |
|-------|---------|
| 8000-8099 | Python services |
| 3000-3099 | Frontend apps |

**Before using a port:** Check PORTS.md, register new ports.

---

## Self-Check Before Responding

Before I finish ANY coding task, I MUST verify:
- [ ] No hardcoded localhost/secrets
- [ ] Documentation updated if code changed
- [ ] Enforcement check passed
- [ ] Review triggered or manually done

---

## Terminal Selection (CRITICAL)

**NEVER use "legacy terminal" in Windsurf IDE** - it hangs on certain commands.

When running commands, always use the standard terminal. If Windsurf shows "Using legacy terminal", the command may hang indefinitely. This is an IDE issue, not a code issue.

**If a command appears stuck:** Cancel and re-run in a proper terminal.

---

## Fast Context (Windsurf RAG)

**Force quick codebase search:** `Cmd+Enter` (Mac) / `Ctrl+Enter` (Win/Linux)

Uses SWE-grep models for parallel code retrieval (up to 8 tool calls/turn).

**Optimize indexing with `.codeiumignore`:**
- Project-level: `/opt/fabrik/.codeiumignore`
- Global: `~/.codeium/.codeiumignore`

Excluded from index: `.venv/`, `node_modules/`, `.droid/` queues, build artifacts.
