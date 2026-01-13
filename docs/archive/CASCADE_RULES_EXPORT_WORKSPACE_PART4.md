# Cascade Rules Export - WORKSPACE RULES (Part 4 of 5)

**Exported:** 2026-01-13
**Type:** WORKSPACE RULES
**Location:** `/opt/fabrik/AGENTS.md` (First Half)

---

# FILE: AGENTS.md (Lines 1-300)

```markdown
# Fabrik Project Agent Briefing

**Last Updated:** 2026-01-08

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

## Documentation Rules

1) Do NOT create markdown files in repo root.
2) Feature/Execution plans:
   - Create ONLY under `docs/development/plans/`
   - Filename: `YYYY-MM-DD-<slug>.md`
3) Every new plan MUST be added to `docs/development/PLANS.md`.
4) Do NOT create new folders under `docs/` except via existing structure.
5) If you add a module under `src/`, ensure a reference doc exists.
6) NEVER edit inside `<!-- AUTO-GENERATED:* -->` blocks.
7) All changes MUST keep `make docs-check` passing.

---

## ⚠️ MANDATORY WORKFLOW (ALL AI AGENTS)

**Before finishing ANY coding task, you MUST:**

```bash
# 1. Run enforcement check
python3 -m scripts.enforcement.validate_conventions --strict <changed_files>

# 2. Trigger code review (if significant changes)
droid exec "Review <files> for Fabrik conventions. DO NOT make changes."

# 3. Update documentation
```

---

## Build & Test

```bash
pip install -e .                    # Install in dev mode
pytest                              # Run tests
pytest -x --tb=short               # Stop on first failure
ruff check .                        # Lint
mypy .                              # Type check
docker compose up -d                # Start services
```

## Run Locally

```bash
uvicorn src.main:app --reload --port 8000
curl http://localhost:8000/health
```

## Architecture Overview

- **WSL (dev)** → Local PostgreSQL, local services, `.env` file
- **VPS (prod)** → Coolify-managed Docker Compose, `postgres-main` container
- **Every project ships as one Compose app**

## SaaS Projects (MANDATORY)

```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/<project-name>
cd /opt/<project-name>
npm install
cp .env.example .env
npm run dev
```

## Project Layout

```
/opt/<project>/
├── src/                   # Main source code
├── tests/                 # Tests mirror src/
├── scripts/               # Utility scripts
├── config/                # YAML/JSON configs
├── docs/                  # Documentation
├── compose.yaml           # Docker Compose
├── .env.example           # Env var template
└── AGENTS.md              # This file (symlinked)
```

## Conventions & Patterns

### Environment Variables (CRITICAL)

```python
# CORRECT
DB_HOST = os.getenv('DB_HOST', 'localhost')

# WRONG
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

## Security

- **Never commit `.env`**
- **All credentials in TWO places:** Project `.env` + `/opt/fabrik/.env`
- **CSPRNG passwords**: 32 chars, alphanumeric only

## Document Location Rules (ENFORCED)

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
```

---

**Continued in Part 5...**
