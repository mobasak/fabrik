# Cascade Backup: Memories & Global Rules

**Exported:** 2026-01-13 20:35
**Workspace:** fabrik
**Exported By:** Cascade in conversation (manual trigger)

---

# PART 1: MEMORIES

## Memory: Before Creating New Scripts (MANDATORY)

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

---

## Memory: Factory CLI Settings

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

---

## Memory: Before Launching droid exec

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

---

## Memory: After Code Changes

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

## Memory: Code Review Wrapper

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

## Memory: Droid Exec Scripts - How to Use

**Primary entry point:** `/opt/fabrik/scripts/droid_core.py`

### Quick Commands
```bash
# Discovery Pipeline
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

### Task Types (13 total)
- **Discovery:** idea, scope
- **Core:** analyze, code, refactor, test, review
- **Lifecycle:** spec, scaffold, deploy, migrate, health, preflight

---

## Memory: Long Command Monitoring (MANDATORY)

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

### Job files stored in
`.tmp/jobs/` (gitignored, project-local)

---

## Memory: Planning Phase References

**During idea/scope/spec phases, consult these files:**

### Technology Selection
- `docs/reference/technology-stack-decision-guide.md` - Decision flowchart
- `docs/reference/stack.md` - Fabrik's Docker+Coolify pattern
- `docs/reference/SaaS-GUI.md` - SaaS UI/UX patterns

### Infrastructure & Containers
- `docs/reference/prebuilt-app-containers.md` - CHECK BEFORE BUILDING
- `docs/reference/trueforge-images.md` - Supply-chain secure images
- `docs/reference/DATABASE_STRATEGY.md` - PostgreSQL/Supabase/pgvector

### AI/ML Decisions
- `docs/reference/AI_TAXONOMY.md` - 15-category AI taxonomy

### Code Standards
- `templates/scaffold/PYTHON_PRODUCTION_STANDARDS.md`
- `.windsurf/rules/10-python.md` - FastAPI patterns
- `.windsurf/rules/20-typescript.md` - Next.js/React patterns

---

## Memory: Before Creating .md Files

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

## Memory: Allowed .md File Locations

ROOT (only these):
- README.md, CHANGELOG.md, tasks.md, AGENTS.md, PORTS.md, LICENSE.md

DOCS SUBDIRS (all other docs):
- docs/guides/ - How-to guides
- docs/reference/ - Technical reference
- docs/operations/ - Ops runbooks
- docs/development/ - Plans, specs
- docs/development/plans/ - Execution plans
- docs/archive/ - Archived docs

FORBIDDEN:
- .md files in src/, scripts/, tests/, config/
- .md files in project root (except allowed list)

Enforcement: scripts/enforcement/check_structure.py

---

## Memory: Present Before Execute

For any non-trivial task, Cascade MUST:

1. Present the plan/solution FIRST
2. Wait for user to say "go" or approve
3. Only THEN execute

Do NOT:
- Execute immediately after presenting
- Assume silence means approval
- Bundle plan + execution in one response

Phrase to use: "Say 'go' when ready to proceed."

---

## Memory: Documentation Sync After Code Changes

After completing ANY code change, I MUST run:

```bash
python3 scripts/docs_sync.py
```

This checks and reminds about:
1. **CHANGELOG.md** - Entry for code changes
2. **tasks.md** - Phase status update if implementation work
3. **Phase docs** - Checkboxes if completing tracked tasks
4. **docs/INDEX.md** - Structure map if files added/moved

**Sequence:**
```
Code change → droid-review.sh → docs_sync.py → Update all flagged docs → Commit
```

---

## Memory: Python Type Annotations

When writing NEW Python code in /opt/fabrik, ALWAYS include type annotations:

```python
# CORRECT - annotated
def get_user(user_id: int) -> dict[str, Any]:
    ...

def process_items(items: list[str]) -> None:
    ...

# WRONG - no annotations
def get_user(user_id):
    ...
```

**Rules:**
1. All function parameters must have type hints
2. All functions must have return type (use `-> None` if no return)
3. Use `dict[str, Any]` not bare `dict`
4. Use `list[str]` not bare `list`
5. Add `from __future__ import annotations` at top of new files

---

## Memory: CSPRNG Password Policy

All passwords and secrets must use CSPRNG:
- Length: 32 characters
- Characters: [a-zA-Z0-9] (alphanumeric only)
- Generator: Python `secrets` module

```python
import secrets, string
secret = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
```

**FORBIDDEN:** `postgres`, `admin`, `password123`

---

## Memory: VPS1 ARM64 Architecture

VPS1 (vps1.ocoron.com) uses ARM64 (aarch64) architecture, NOT x86_64/amd64.

All container images deployed must support linux/arm64.

Verify architecture support:
```bash
python scripts/container_images.py check-arch <image:tag>
```

---

## Memory: Read-Only Reviews

When asking droid exec to REVIEW (not execute):

WRONG (allows edits):
```bash
droid exec --auto low "Review this plan..."
```

CORRECT (read-only):
```bash
droid exec "Review this plan. DO NOT make any changes, only provide feedback."
```

Key rules:
- No --auto flag = read-only by default
- Always add explicit "DO NOT make changes" in prompt for reviews

---

# PART 2: GLOBAL RULES

## Global Rule: Factory CLI Settings

Factory CLI settings file: `/home/ozgur/.factory/settings.json`

Configured for full automation with claude-sonnet-4-5-20250929, high reasoning, auto-high autonomy.

Command allowlist: git ops, package managers, python/node, docker, pytest
Command denylist: system destruction, mkfs, dd, shutdown, fork bombs

---

## Global Rule: Codeium Ignore

Global codeiumignore at `~/.codeium/.codeiumignore`

Excludes from indexing:
- `.venv/`, `node_modules/`, `.droid/` queues
- Build artifacts, logs, cache directories

---

## Global Rule: droid exec Pre-checks

Before launching ANY droid exec command:
1. Check for running instances: `pgrep -f "droid exec"`
2. Limit parallel calls to 2-3 max
3. Use ProcessMonitor for stuck detection

---

## Global Rule: Code Review Wrapper

Always use `./scripts/droid-review.sh` for code reviews.
Never use raw `droid exec "Review..."` without the meta-prompt.

---

## Global Rule: After Code Changes

Sequence: Code change → droid-review.sh → Implement one-test → pytest → Commit

Must run docs_sync.py after changes.

---

## Global Rule: Before Creating .md Files

Check templates/docs/ for templates before creating new markdown files.
Use PLAN_TEMPLATE.md or EXECUTION_PLAN_TEMPLATE.md as appropriate.

---

## Global Rule: When Developing Fabrik

Think about both Fabrik itself AND all future projects that will use Fabrik.
Every decision should consider: Will this pattern work for scaffolded projects?

---

## Global Rule: Present Before Execute

Present plan first, wait for explicit "go", then execute.
Do NOT assume silence means approval.

---

# RESTORE INSTRUCTIONS

## Memories
To restore memories on a new machine, ask Cascade:
```
Please create memories from each section in docs/reference/CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md under "PART 1: MEMORIES"
```

## Global Rules
To restore global rules:
1. Open Windsurf Settings > Cascade > Rules
2. Add each rule from PART 2 above

## Workspace Rules
Workspace rules are in `.windsurf/rules/` and restored automatically via git clone.

## Extensions
Extensions are in `docs/reference/EXTENSIONS.md` with install commands.
