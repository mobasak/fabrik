# Cascade Memories

**Exported:** 2026-01-13
**Workspace:** fabrik

## Memory 1: Before Creating New Scripts (MANDATORY)

Before writing ANY new script, I MUST:
1. `grep_search` for similar functionality in scripts/
2. Check if droid_core.py, droid-review.sh, or existing wrappers handle it
3. If existing code can be extended → extend it, don't create new

**Violation:** Creating duplicate functionality.

**Key existing infrastructure:**
- `scripts/droid_core.py` - All droid exec task types with ProcessMonitor
- `scripts/droid-review.sh` - Code review wrapper
- `scripts/docs_updater.py` - Documentation updates
- `scripts/review_processor.py` - Background reviews

**Rule location:** `.windsurf/rules/00-critical.md`

## Memory 2: Factory CLI Settings

Factory CLI settings file: `/home/ozgur/.factory/settings.json`

Key settings for full automation:
- Model: claude-sonnet-4-5-20250929
- Reasoning: high (specModeReasoningEffort: high)
- Autonomy: auto-high
- Hooks: enabled
- Skills: enabled
- Cloud sync: enabled
- Custom droids: enabled
- Co-authored commits: enabled
- Background processes: allowed

Command allowlist includes: git ops, package managers, python/node, docker, pytest, safe rm paths (/opt/*, ~/.cache/*, etc.)
Command denylist blocks: system destruction (rm -rf /, /etc, /usr, /home), mkfs, dd, shutdown, fork bombs, chmod hazards.

## Memory 3: Before Launching droid exec

Before launching ANY droid exec command:

1. Check for running instances:
```bash
pgrep -f "droid exec" || echo "No running instances"
```

2. If instances are running, either:
   - Wait for them to complete
   - Ask user if they want to proceed
   - Use ProcessMonitor to check if stuck

3. For parallel droid calls, limit to 2-3 max to avoid resource contention

Reference: /opt/fabrik/scripts/process_monitor.py

## Memory 4: After Code Changes

After implementing any code change, I MUST:

1. Run `./scripts/droid-review.sh` on changed files
2. Implement the ONE test recommended in Section E of the review output
3. Run `pytest tests/ -v` to verify the test passes

**Sequence:**
```
Code change → droid-review.sh → Implement one-test → pytest → Commit
```

**The one-test must cover:**
- The highest-risk code path identified in review
- Given / When / Then structure
- Clear assertion of expected behavior

**Violation:** Committing code changes without the recommended test.

## Memory 5: Code Review Wrapper

When reviewing code via droid exec, ALWAYS use the wrapper script:

```bash
# Code review (uses adaptive meta-prompt automatically)
./scripts/droid-review.sh src/path/to/file.py

# Plan review
./scripts/droid-review.sh --plan docs/development/plans/my-plan.md

# Multiple files
./scripts/droid-review.sh src/file1.py src/file2.py

# Specific model
./scripts/droid-review.sh --model gpt-5.1-codex-max src/file.py
```

**DO NOT** use raw `droid exec "Review..."` without the meta-prompt.

The wrapper:
- Loads `/opt/fabrik/templates/droid/review-meta-prompt.md` automatically
- Selects recommended model from config/models.yaml
- Runs read-only (no --auto flag)
- Produces structured P0/P1 output

**Violation:** Running `droid exec "Review..."` without the adaptive meta-prompt.

## Memory 6: Droid Exec Scripts - How to Use

**Primary entry point:** `/opt/fabrik/scripts/droid_core.py`

### Quick Commands
```bash
# Discovery Pipeline (NEW)
python scripts/droid_core.py idea "Voice-controlled home automation"
python scripts/droid_core.py scope "home-automation"
python scripts/droid_core.py spec "home-automation"

# Task by type
python scripts/droid_core.py analyze "Review the auth flow"
python scripts/droid_core.py code "Add error handling" --auto medium

# From task file (for long prompts)
python scripts/droid_core.py run --task tasks/my_task.md

# Continue session
python scripts/droid_core.py code "Now refactor" --session-id <id>
```

### Other Scripts
- `./scripts/droid-review.sh <file>` - Code review
- `python scripts/docs_updater.py --file <path>` - Doc updates
- `python scripts/review_processor.py` - Background reviews

### Key Features
- Large prompts (>100KB) auto-use `--file` flag
- Retries disabled for write-heavy tasks (CODE, SCAFFOLD, etc.)
- Session resets on provider switch (OpenAI ↔ Anthropic)
- ProcessMonitor detects stuck processes

### Task Types (13 total)
- **Discovery:** idea, scope
- **Core:** analyze, code, refactor, test, review
- **Lifecycle:** spec, scaffold, deploy, migrate, health, preflight

### Complete Workflow
```
idea → scope → spec → plan → code → review → deploy
```

## Memory 7: Planning Phase References

**During idea/scope/spec phases, consult these files:**

### Technology Selection
- `docs/reference/technology-stack-decision-guide.md` - Decision flowchart for tech choices
- `docs/reference/stack.md` - Fabrik's Docker+Coolify pattern
- `docs/reference/SaaS-GUI.md` - SaaS UI/UX patterns

### Infrastructure & Containers
- `docs/reference/prebuilt-app-containers.md` - Prebuilt Docker containers (CHECK BEFORE BUILDING)
- `docs/reference/trueforge-images.md` - Supply-chain secure images
- `docs/reference/DATABASE_STRATEGY.md` - PostgreSQL/Supabase/pgvector selection
- `docs/reference/wordpress/plugin-stack.md` - WordPress plugin stack

### AI/ML Decisions
- `docs/reference/AI_TAXONOMY.md` - 15-category AI taxonomy with tool recommendations

### Code Standards
- `templates/scaffold/PYTHON_PRODUCTION_STANDARDS.md` - Python best practices
- `.windsurf/rules/10-python.md` - FastAPI patterns
- `.windsurf/rules/20-typescript.md` - Next.js/React patterns

**Full index:** `docs/reference/PLANNING_REFERENCES.md`

## Memory 8: When Developing Fabrik

When developing Fabrik, I MUST think about:

1. **Fabrik itself** - the CLI, drivers, templates
2. **ALL future projects** - that will be developed AND deployed via Fabrik

Every decision should consider:
- Will this pattern work for projects scaffolded by `fabrik new`?
- Will this convention apply to deployed WordPress sites, APIs, workers?
- Is this enforcement portable to child projects?

**Examples:**
- Type annotations → Should scaffold templates include them?
- Pre-commit hooks → Should new projects get these automatically?
- droid-review.sh → Should this be part of scaffolded projects?

**Test:** Before implementing anything in Fabrik, ask:
> "How will this affect a project created via `create_project()` and deployed via `fabrik apply`?"

## Memory 9: Before Creating .md Files

Before creating ANY .md file (plan, spec, guide, etc.), Cascade MUST:

1. Check if a template exists:
   - find_by_name in templates/docs/ for document templates
   - find_by_name in templates/scaffold/docs/ for project docs

2. If template exists → USE IT exactly
3. If no template → Ask user before freestyle

Templates location: /opt/fabrik/templates/docs/
- PLAN_TEMPLATE.md (exploration/research)
- EXECUTION_PLAN_TEMPLATE.md (locked implementation)

Violation: Creating docs without checking templates first.

## Memory 10: Long Command Monitoring (MANDATORY)

**For commands expected to take >10 seconds, use detached execution:**

### Scripts Location
- Fabrik: `/opt/fabrik/scripts/rund`, `rundsh`, `runc`, `runk`
- New projects: `scripts/rund`, `rundsh`, `runc`, `runk` (from scaffold)

### Usage
```bash
# Start detached (exec mode - safe)
./scripts/rund npm install
# Returns: JOB=.tmp/jobs/job_xxx PID=xxx SID=xxx

# Start detached (shell mode - pipes allowed)
./scripts/rundsh 'npm test && npm build'

# Check status (every 15-30s)
./scripts/runc .tmp/jobs/job_xxx

# Kill if stuck (90s no progress)
./scripts/runk .tmp/jobs/job_xxx
```

### Stuck Detection Rule
STUCK = 90 seconds where ALL are true:
- LOG bytes unchanged
- cputime unchanged
- PROCS count unchanged

Action: `runk` → retry with `--verbose`

### When to Use
| Command Type | Use rund/rundsh? |
|--------------|------------------|
| npm install, pip install | ✅ Yes |
| docker build | ✅ Yes |
| pytest (large suite) | ✅ Yes |
| git clone (large repo) | ✅ Yes |
| Quick commands (<10s) | ❌ No, use normal |

### Job files stored in
`.tmp/jobs/` (gitignored, project-local)

## Memory 11: Execution Protocol (MANDATORY)

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

## Memory 12: Environment Variables (CRITICAL)

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

## Memory 13: Target Environments

Code MUST work in ALL environments without modification:

| Environment | Database | Config Source |
|-------------|----------|---------------|
| WSL (dev) | PostgreSQL localhost | `.env` file |
| VPS Docker | postgres-main container | compose.yaml |
| Supabase | Supabase PostgreSQL | env vars |

## Memory 14: Health Checks (MUST Test Dependencies)

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

## Memory 15: Container Base Images (CRITICAL)

**Use Debian/Ubuntu, NOT Alpine:**

| Use Case | Base Image |
|----------|------------|
| Python apps | `python:3.12-slim-bookworm` |
| Node.js apps | `node:22-bookworm-slim` |
| General | `debian:bookworm-slim` |

**Why not Alpine:** glibc compatibility, ARM64 support, pre-built wheels.

## Memory 16: Forbidden Actions

| Action | Use Instead |
|--------|-------------|
| `/tmp/` directory | Project `.tmp/` |
| Hardcoded localhost | `os.getenv()` |
| Alpine base images | `python:3.12-slim-bookworm` |
| Class-level config | Function-level loading |

## Memory 17: Cascade Behavior Rules (STRICT)

| Rule | Description |
|------|-------------|
| **Check before create** | ALWAYS verify file exists (`ls`, `find`, `read_file`) before `write_to_file` |
| **Present before execute** | Present solution/plan first, wait for user approval, then execute |
| **No unsolicited advice** | Never suggest breaks, lifestyle tips, or non-task commentary |

**Violations:**
- Attempting to create a file that already exists = STOP, acknowledge error
- Executing commands without presenting plan first = violation
- Suggesting breaks or personal advice = violation

## Memory 18: Port Management

| Range | Purpose |
|-------|---------|
| 8000-8099 | Python services |
| 3000-3099 | Frontend apps |

**Before using a port:** Check PORTS.md, register new ports.

## Memory 19: Security Gates

### Credentials Storage (TWO PLACES)
1. Project `.env` - local use
2. `/opt/fabrik/.env` - master backup

### Password Policy (CSPRNG)
- Length: 32 characters
- Characters: `[a-zA-Z0-9]`
- Generator: `secrets.choice()`
- **FORBIDDEN:** `postgres`, `admin`, `password123`

## Memory 20: SaaS Projects (MANDATORY)

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

## Memory 21: Documentation Rules

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
