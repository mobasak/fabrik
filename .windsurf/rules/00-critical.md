---
activation: always_on
description: Critical Fabrik rules - ALWAYS enforced (Windsurf Cascade only)
trigger: always_on
---

## ⚠️ MANDATORY FIRST OUTPUT
Before any tool use or code, output:
`RULES ACTIVE: CASCADE | [List 3 specific rules from this file you will follow today]`

# Critical Rules (ALWAYS ACTIVE)

**Scope:** These rules apply to **Windsurf Cascade** agents.

---

## Orientation — Do This First (MANDATORY)

**Scan before you act.** Read the full project structure from root. Locate and read any present:
- `README.md`
- `.windsurf/rules/*.md`
- `docs/workflows/` (workflow docs, if present)
- `docker-compose.yml`, `Dockerfile`
- `.env.example`, `pyproject.toml`, `package.json`, `requirements.txt`

**Do not generate anything until this scan is complete.**

**Do not** recreate `.venv` or replace existing Docker configuration unless explicitly instructed.

**When creating a plan in `docs/development/plans/`**, you MUST include:
- **Key Invariants & Contracts:** What must *always* be true? (e.g., "API errors return JSON body," "`.venv` path never hardcoded")
- **Failure Modes:** Concrete "what-if" scenarios where this design breaks and how the system should react
- **Acceptance Criteria:** 5–10 testable bullets defining "Done"

---

## Environment Context

**Runtime is WSL (Ubuntu).** Linux paths and commands only. Never assume Windows tooling.

**Follow the project scaffold structure verbatim.** Do not reorganize, flatten, or add top-level directories.

**All architectural decisions, base images, and tool choices are resolved before you start** — execute the plan as given. Do not expand scope silently.

**Target deployment:** Linux VPS + container orchestration, optionally Supabase. ARM-compatible builds by default.

**If anything in the task contradicts what exists in the project, stop and report.** Do not silently overwrite.

---

## Internal Audit (MANDATORY)

Before reporting task completion, you MUST confirm:

**Mechanical Checks:**
- [ ] **Zero Hardcoding:** No `localhost`, `127.0.0.1`, or raw API keys in code
- [ ] **Infrastructure:** Dockerfile uses `-slim-bookworm` and has functional `HEALTHCHECK`
- [ ] **Architecture:** `compose.yaml` includes `platform: linux/arm64` for all build services
- [ ] **Dependencies:** New packages added to `requirements.txt` or `package.json`
- [ ] **Networking:** New ports checked against and registered in `PORTS.md`

**Decision-Grade Audit (Solo-Dev Creed):**
- [ ] **Error Handling Gaps:** Have you handled silent, misleading, or brittle failures?
- [ ] **Complexity Hotspots:** What logic will be a "debugging footgun" in 6 months?
- [ ] **One-Test Rule:** Propose **exactly ONE test** providing highest risk reduction
  - **Why:** Justify why this specific test matters most
  - **Contract:** Define Given/When/Then and what is mocked vs. real
  - Document in plan file or commit message

**After audit passes, run lean gate:**
```bash
python scripts/final_gate.py --lean
```

---

## Sensitive Data Protection (CRITICAL)

**Before modifying ANY file containing credentials/secrets:**
- `.env`, `.env.*` (except `.env.example`)
- `*.key`, `*.pem`, `*.p12`, `*.pfx`
- Files in `secrets/`, `credentials/`, `.ssh/`

**You MUST create a timestamped backup first:**
```bash
cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
```

Then verify backup exists before proceeding.

To restore:
```bash
cp <file>.backup.<timestamp> <file>
```

**Violations:**
- Modifying `.env` without backup = STOP immediately
- Running destructive scripts on production data without dry-run test = FORBIDDEN
- Applying changes to credentials without showing full diff first = FORBIDDEN

Enforcement: pre-commit hook + manual AI review discipline.

---

## Before Creating New Scripts (MANDATORY)

Before writing ANY new script, you MUST:

1. `grep_search` for similar functionality in `scripts/`
2. Check if existing scripts in `scripts/` or `scripts/enforcement/` handle it
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
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

# WRONG - breaks in Docker/VPS
DB_HOST = "localhost"
```

---

## Target Environments

Code MUST work in ALL environments without modification:

| Environment | Database             | Config Source   |
|------------|----------------------|-----------------|
| WSL (dev)  | PostgreSQL localhost | `.env` file     |
| VPS Docker | `postgres-main`      | `compose.yaml`  |
| Supabase   | Supabase PostgreSQL  | env vars        |

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

**Credentials Storage**
- Project `.env` is primary (local use).
- Backup `.env` manually to secure location if needed.

**Password Policy (CSPRNG):**
- Length: 32 characters
- Characters: `[a-zA-Z0-9]`
- Generator: `secrets.choice()`
- **FORBIDDEN:** `postgres`, `admin`, `password123`

---

## Forbidden Actions

| Action              | Use Instead                                 |
|---------------------|---------------------------------------------|
| `/tmp/` directory   | Project `.tmp/`                             |
| Hardcoded localhost | `os.getenv()`                               |
| Alpine base images  | `python:<current-stable>-slim-bookworm`     |
| Class-level config  | Function-level loading                      |
| Bare `pip install`  | `/opt/<project>/.venv/bin/pip install`      |

---

## PEP 668: WSL/Debian Venv Requirement (CRITICAL)

WSL and modern Debian block system-wide pip installs. **NEVER** run bare `pip install`.

```bash
# WRONG - will fail with "externally-managed-environment"
pip install textual

# CORRECT - project-specific venv
/opt/<project>/.venv/bin/pip install textual
```

Each project has its own `.venv` for complete isolation.

---

## Cascade Behavior Rules (STRICT)

| Rule                   | Description                                                                 |
|------------------------|-----------------------------------------------------------------------------|
| Check before create    | ALWAYS verify file exists (`ls`, `find`, `read_file`) before `write_to_file` |
| Present before execute | Present solution/plan first, wait for user approval, then execute. Exception: read-only commands (`ls`, `cat`, `find`, `grep`, `head`, `tail`) do not require approval. |
| No unsolicited advice  | Never suggest breaks, lifestyle tips, or non-task commentary               |

**Violations:**
- Attempting to create a file that already exists = STOP, acknowledge error
- Executing commands without presenting plan first = violation
- Suggesting breaks or personal advice = violation

---

## Port Management

| Range     | Purpose        |
|----------|----------------|
| 8000–8099 | Python services |
| 3000–3099 | Frontend apps  |

Before using a port: check `PORTS.md`, register new ports.

---

## Database Schema Convention

**All database changes MUST be documented in `db/schema.sql`:**
- New tables, columns, indexes → add `CREATE` statements
- Include date comments for each change
- This file is the source of truth for DB structure

```sql
-- db/schema.sql example
-- 2026-03-20: Added users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Self-review checkpoint: confirm database changes added to `db/schema.sql`.

---

## Self-Check Before Responding

Before finishing ANY coding task, you MUST verify:
- [ ] Internal audit completed and reported (this file)
- [ ] No hardcoded localhost/secrets
- [ ] Database changes added to `db/schema.sql` (if applicable)
- [ ] CHANGELOG.md updated for code/config/infrastructure changes
- [ ] Lean gate passed: `python scripts/final_gate.py --lean`
- [ ] Changes staged (`git add -A`) — never committed

Milestone gate (`python scripts/final_gate.py`) runs only when closing a milestone or batch. Kilo Review and Documentator are optional/manual tools only. Traycer verifies work; agents run local scripts. See `.windsurf/rules/50-code-review.md` for commands.

**Cascade never commits. Traycer commits.**

---

## Terminal Selection (CRITICAL)

**NEVER use "legacy terminal" in Windsurf IDE** — it hangs on certain commands.

When running commands, always use the standard terminal. If Windsurf shows "Using legacy terminal", the command may hang indefinitely. This is an IDE issue, not a code issue.

If a command appears stuck: cancel and re-run in a proper terminal.

---

## Fast Context (Windsurf RAG)

Force quick codebase search: `Cmd+Enter` (Mac) / `Ctrl+Enter` (Win/Linux)

Uses SWE-grep models for parallel code retrieval (up to 8 tool calls/turn).

Optimize indexing with `.codeiumignore`:
- Project-level: `.codeiumignore` (project root)
- Global: `~/.codeium/.codeiumignore`

Excluded from index: `.venv/`, `node_modules/`, `.droid/` queues, build artifacts.
