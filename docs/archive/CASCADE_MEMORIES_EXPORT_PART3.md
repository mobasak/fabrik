# Cascade Memories Export - Part 3 of 3

**Exported:** 2026-01-13

---

# MEMORY: Execution Protocol (MANDATORY)

## The Flow: PLAN → APPROVE → IMPLEMENT → REVIEW → FIX → VALIDATE → NEXT

**This applies to ALL tasks in /opt/* projects.**

| Phase | Action | Gate |
|-------|--------|------|
| **1. PLAN** | Create/show execution plan | Plan exists |
| **2. APPROVE** | Wait for explicit "go" from human | Human says "go" |
| **3. IMPLEMENT** | Execute ONE step | Code written |
| **4. REVIEW** | Run code review (see below) | Review output shown |
| **5. FIX** | Address ALL issues found | Zero errors |
| **6. VALIDATE** | Run gate command | Gate passes |
| **7. NEXT** | Only proceed after gate passes | Ready for next step |

---

## Code Review (After EVERY Code Change)

**Immediately after writing/editing code, I MUST:**

```bash
# 1. Check no droid instances running (prevents resource contention)
pgrep -f "droid exec" || echo "Ready"

# 2. Get recommended model for code review
python3 scripts/droid_models.py recommend code_review 2>/dev/null || echo "gemini-3-flash-preview"

# 3. Run review (read-only, NO changes)
droid exec -m <model_from_step_2> "Review these files for Fabrik conventions and bugs. DO NOT make changes, only report issues as JSON: {issues: [{file, line, severity, message}], summary: string}

Files: <changed_files>"
```

**Then I MUST:**
1. Show the review output to user
2. Fix ALL errors (severity: error)
3. Fix warnings if reasonable
4. Re-run review until: `"issues": []` or only minor warnings remain

**Output format after each step:**
```
STEP <N> STATUS: PASS / FAIL
Changed files:
- <path>
Review output:
<issues or "No issues">
Gate output:
<command result>
Next: Proceed to Step <N+1> / STOP (issues remain)
```

---

## Violations

**I am FORBIDDEN from:**
- Skipping REVIEW phase
- Proceeding to next step with unfixed errors
- Marking task complete without final review
- Assuming approval — must wait for explicit "go"

**If user catches me skipping review:**
- I must acknowledge the violation
- Run the skipped review immediately
- Fix issues before continuing

---

# MEMORY: Environment Variables (CRITICAL)

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

# MEMORY: Target Environments

Code MUST work in ALL environments without modification:

| Environment | Database | Config Source |
|-------------|----------|---------------|
| WSL (dev) | PostgreSQL localhost | `.env` file |
| VPS Docker | postgres-main container | compose.yaml |
| Supabase | Supabase PostgreSQL | env vars |

---

# MEMORY: Health Checks (MUST Test Dependencies)

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

# MEMORY: Container Base Images (CRITICAL)

**Use Debian/Ubuntu, NOT Alpine:**

| Use Case | Base Image |
|----------|------------|
| Python apps | `python:3.12-slim-bookworm` |
| Node.js apps | `node:22-bookworm-slim` |
| General | `debian:bookworm-slim` |

**Why not Alpine:** glibc compatibility, ARM64 support, pre-built wheels.

---

# MEMORY: Forbidden Actions

| Action | Use Instead |
|--------|-------------|
| `/tmp/` directory | Project `.tmp/` |
| Hardcoded localhost | `os.getenv()` |
| Alpine base images | `python:3.12-slim-bookworm` |
| Class-level config | Function-level loading |

---

# MEMORY: Cascade Behavior Rules (STRICT)

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

# MEMORY: Port Management

| Range | Purpose |
|-------|---------|
| 8000-8099 | Python services |
| 3000-3099 | Frontend apps |

**Before using a port:** Check PORTS.md, register new ports.

---

# MEMORY: Security Gates

### Credentials Storage (TWO PLACES)
1. Project `.env` - local use
2. `/opt/fabrik/.env` - master backup

### Password Policy (CSPRNG)
- Length: 32 characters
- Characters: `[a-zA-Z0-9]`
- Generator: `secrets.choice()`
- **FORBIDDEN:** `postgres`, `admin`, `password123`

---

# MEMORY: SaaS Projects (MANDATORY)

**When starting ANY SaaS, web app, or dashboard project, ALWAYS use the SaaS skeleton:**

```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/<project-name>
cd /opt/<project-name>
npm install
cp .env.example .env
npm run dev
```

**Template includes:**
- Next.js 14 + TypeScript + Tailwind CSS
- Marketing pages (landing, pricing, FAQ, terms, privacy)
- App pages (dashboard, settings, job workflow)
- SSE streaming + ChatUI for droid exec integration
- Supabase-ready auth patterns

**Customize:** `lib/config/site.ts` for branding, `app/(marketing)/` for content.

---

# MEMORY: Documentation Rules

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

---

# End of Memories Export

**To import on new machine:**
1. Open each part in Windsurf
2. Tell Cascade: "Memorize all rules from this document"
3. Or selectively: "Remember that [specific rule]"
