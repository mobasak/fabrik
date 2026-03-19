---
activation: always_on
description: Critical Fabrik rules - ALWAYS enforced
trigger: always_on
---

# Critical Rules (ALWAYS ACTIVE)

## ⚠️ MANDATORY WORKFLOW (Simplified March 2026)

**PLAN → IMPLEMENT → SELF_REVIEW → FINAL_GATE → CHEAP_REVIEW → TRAYCER_VERIFY → COMMIT**

| Step | Action | Gate |
|------|--------|------|
| 1 | Traycer Plan | Spec exists with requirements |
| 2 | Coder Implements | Code only what phase requires |
| 2.5 | Self-Review | Coding AI reviews own work (MANDATORY) |
| 3 | Final Gate | `python /opt/fabrik/scripts/final_gate.py` → all PASS |
| 4 | Cheap Review | Context-aware reviewer (optional, use `reviewer_selector.py`) |
| 5 | Traycer Verify | Traycer verifier passes |
| 6 | Commit | pre-commit runs 4 blockers only |

**Reviewer Selection (context-aware):**
```bash
# Auto-select cheapest capable reviewer based on diff
python /opt/fabrik/scripts/reviewer_selector.py auto

# Tiers: quick ($0.02), standard ($0.05), complex ($0.12), security ($0.30)
```

**Notes:**
- Final Gate is the authority for deterministic checks (single pass, not pre+post).
- Cheap review is optional - Traycer verify handles spec compliance.
- Semgrep is best-effort: skipped if not installed or not authenticated.
- Pre-commit runs ONLY 4 blockers: large-files, merge-conflict, private-key, secrets.

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
