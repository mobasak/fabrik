# Cascade Rules Export - GLOBAL RULES

**Exported:** 2026-01-13
**Type:** GLOBAL RULES (apply across ALL workspaces)
**Location:** User settings / ~/.codeium/ / ~/.factory/

---

## How to Import

1. On new machine, copy these settings to appropriate locations
2. Sign in to Windsurf with same account (syncs some settings automatically)

---

# GLOBAL: Factory CLI Settings

**Location:** `~/.factory/settings.json`

```json
{
  "model": "claude-sonnet-4-5-20250929",
  "specModeReasoningEffort": "high",
  "autonomyLevel": "auto-high",
  "hooksEnabled": true,
  "skillsEnabled": true,
  "cloudSyncEnabled": true,
  "customDroidsEnabled": true,
  "coAuthoredCommitsEnabled": true,
  "backgroundProcessesAllowed": true,
  "commandAllowlist": [
    "git *",
    "npm *",
    "pip *",
    "python *",
    "node *",
    "docker *",
    "pytest *",
    "rm -rf /opt/*",
    "rm -rf ~/.cache/*"
  ],
  "commandDenylist": [
    "rm -rf /",
    "rm -rf /etc",
    "rm -rf /usr",
    "rm -rf /home",
    "mkfs *",
    "dd of=/dev/*",
    "shutdown *",
    ":(){ :|:& };:",
    "chmod -R 777 /"
  ]
}
```

---

# GLOBAL: Codeium Ignore

**Location:** `~/.codeium/.codeiumignore`

```
# Directories to exclude from indexing
.venv/
node_modules/
.droid/
__pycache__/
.git/
*.pyc
*.pyo
.tmp/
dist/
build/
*.egg-info/
```

---

# GLOBAL: Before Launching droid exec

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

---

# GLOBAL: Long Command Monitoring

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

---

# GLOBAL: After Code Changes

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

---

# GLOBAL: Code Review Wrapper

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

---

# GLOBAL: Before Creating .md Files

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

# GLOBAL: When Developing Fabrik

When developing Fabrik, I MUST think about:

1. **Fabrik itself** - the CLI, drivers, templates
2. **ALL future projects** - that will be developed AND deployed via Fabrik

Every decision should consider:
- Will this pattern work for projects scaffolded by `fabrik new`?
- Will this convention apply to deployed WordPress sites, APIs, workers?
- Is this enforcement portable to child projects?

**Test:** Before implementing anything in Fabrik, ask:
> "How will this affect a project created via `create_project()` and deployed via `fabrik apply`?"

---

# GLOBAL: Planning Phase References

**During idea/scope/spec phases, consult these files:**

### Technology Selection
- `docs/reference/technology-stack-decision-guide.md` - Decision flowchart
- `docs/reference/stack.md` - Fabrik's Docker+Coolify pattern
- `docs/reference/SaaS-GUI.md` - SaaS UI/UX patterns

### Infrastructure & Containers
- `docs/reference/prebuilt-app-containers.md` - CHECK BEFORE BUILDING
- `docs/reference/trueforge-images.md` - Supply-chain secure images
- `docs/reference/DATABASE_STRATEGY.md` - PostgreSQL/Supabase/pgvector
- `docs/reference/wordpress/plugin-stack.md` - WordPress plugin stack

### AI/ML Decisions
- `docs/reference/AI_TAXONOMY.md` - 15-category AI taxonomy

### Code Standards
- `templates/scaffold/PYTHON_PRODUCTION_STANDARDS.md` - Python best practices
- `.windsurf/rules/10-python.md` - FastAPI patterns
- `.windsurf/rules/20-typescript.md` - Next.js/React patterns

**Full index:** `docs/reference/PLANNING_REFERENCES.md`

---

# End of Global Rules Export

**To import on new machine:**
1. Copy Factory settings to `~/.factory/settings.json`
2. Copy codeiumignore to `~/.codeium/.codeiumignore`
3. Sign in to Windsurf with same account
4. Tell Cascade: "Memorize all global rules from this document"
