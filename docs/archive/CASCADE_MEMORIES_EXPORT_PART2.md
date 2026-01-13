# Cascade Memories Export - Part 2 of 3

**Exported:** 2026-01-13

---

# MEMORY: Droid Exec Scripts - How to Use

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

---

# MEMORY: Planning Phase References

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

---

# MEMORY: When Developing Fabrik

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

---

# MEMORY: Before Creating .md Files

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

---

# MEMORY: Long Command Monitoring (MANDATORY)

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
