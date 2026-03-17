---
activation: always_on
description: Critical Fabrik rules - ALWAYS enforced
trigger: always_on
---

# Critical Rules (ALWAYS ACTIVE)

## ⚠️ MANDATORY WORKFLOW

**PLAN → IMPLEMENT → SELF_REVIEW → FINAL_GATE → KILO → FINAL_GATE → TRAYCER_VERIFY → SYNC → COMMIT**

1. Step 2.5 (Self-Review): Coding AI reviews own work before gates (MANDATORY)
2. Step 3 (Pre-Kilo): `python /opt/fabrik/scripts/final_gate.py` → all PASS
3. Step 4 (Kilo loop): fix until verdict=PASS (diff-scoped)
4. Step 5 (Post-Kilo): `python /opt/fabrik/scripts/final_gate.py` → all PASS
5. Step 6 (Traycer verification): must PASS
6. Step 7 (Sync only): `python /opt/fabrik/scripts/final_gate.py --sync`
7. Step 8 (Commit): pre-commit runs ONLY 4 blockers:
   - check-added-large-files
   - check-merge-conflict
   - detect-private-key
   - forbid-secrets

**Notes:**
- Final Gate is the authority for deterministic checks.
- Semgrep is best-effort: skipped if not installed or not authenticated.
- Do not rely on .gitignore as a security control (pre-commit blockers still apply).
- **When using Kilo review continuation, always provide a stable tracked review ID; never rely on a global latest session.**

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

## Fast Context (Windsurf RAG)

**Force quick codebase search:** `Cmd+Enter` (Mac) / `Ctrl+Enter` (Win/Linux)

Uses SWE-grep models for parallel code retrieval (up to 8 tool calls/turn).

**Optimize indexing with `.codeiumignore`:**
- Project-level: `/opt/fabrik/.codeiumignore`
- Global: `~/.codeium/.codeiumignore`

Excluded from index: `.venv/`, `node_modules/`, `.droid/` queues, build artifacts.
