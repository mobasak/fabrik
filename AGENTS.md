# Fabrik Project Agent Briefing

**Last Updated:** 2026-02-24

> Traycer is the planning authority. Kilo CLI or Windsurf Cascade is the coding executor.

<!-- AUTO-GENERATED:TOC:START -->
<!-- This section is auto-generated. Do not edit manually. Run: python scripts/update_agents_toc.py -->
## Table of Contents
- [Authority Model](#authority-model)
- [Execution Protocol (9-Step Agile Flow)](#execution-protocol-9-step-agile-flow)
- [Planning (Required for Non-Trivial Work)](#planning-required-for-non-trivial-work)
- [Traycer Mode Selection](#traycer-mode-selection)
- [Traycer Mode (When Task is Traycer-Managed)](#traycer-mode-when-task-is-traycer-managed)
- [Documentation Rules](#documentation-rules)
- [⚠️ MANDATORY WORKFLOW (ALL AI AGENTS)](#⚠️-mandatory-workflow-all-ai-agents)
- [Sensitive Data Protection (CRITICAL)](#sensitive-data-protection-critical)
- [Security Gates (MANDATORY - Runs 3 Times Per Phase)](#security-gates-mandatory-runs-3-times-per-phase)
- [Windsurf Cascade Users](#windsurf-cascade-users)
- [Build & Test](#build-test)
- [Run Locally](#run-locally)
- [Architecture Overview](#architecture-overview)
- [SaaS Projects (MANDATORY)](#saas-projects-mandatory)
- [Project Layout](#project-layout)
- [Conventions & Patterns](#conventions-patterns)
- [Security](#security)
- [Deployment](#deployment)
- [Gotchas](#gotchas)
- [Documentation Rules (MUST)](#documentation-rules-must)
- [Feature Name](#feature-name)
- [Execution Modes (Fabrik Lifecycle)](#execution-modes-fabrik-lifecycle)
- [Traycer CLI Agent Auto-Review Integration](#traycer-cli-agent-auto-review-integration)
- [Traycer Report Panel (Windsurf Extension)](#traycer-report-panel-windsurf-extension)
- [VPS Deployment (Coolify)](#vps-deployment-coolify)
- [GitHub Actions Workflows](#github-actions-workflows)
- [Fabrik Skills (Convention Enforcement)](#fabrik-skills-convention-enforcement)
- [MCP (Model Context Protocol)](#mcp-model-context-protocol)
- [Droid Hooks](#droid-hooks)
- [Agent Readiness Checklist](#agent-readiness-checklist)
- [Writing Effective Prompts](#writing-effective-prompts)
<!-- AUTO-GENERATED:TOC:END -->

## Authority Model

- You write content.
- Deterministic gates enforce structure.
- Final Gate is the quality authority.
- Pre-commit enforces only absolute blockers.

### Traycer Planning Authority

**Traycer is the planning authority.** If Traycer is used:
- No other agent may create/modify plans except by updating the Traycer-managed plan artifact
- All planning happens in Traycer (Phases)
- Traycer produces the managed plan
- Traycer's built-in verifier is the primary verification/review surface
- Coding agents only execute steps from the Traycer-managed plan
- No agent may create `PHASE_TEMPLATE.md`, `TASKS_TEMPLATE.md`, or `implementation-plan-template.md` in any project — these patterns are retired. Traycer Phases are the planning authority.

## Execution Protocol (9-Step Agile Flow)

**Token-optimized workflow: deterministic checks before LLM review.**

| Step | Action | Command / Gate |
|------|--------|----------------|
| **1** | **Traycer Plan** | Plan exists with spec, edge cases, env vars, DB changes |
| **2** | **Coder Implements** | Code only what phase requires, follow spec strictly |
| **3** | **Final Gate (Pre-Kilo)** | `python /opt/fabrik/scripts/final_gate.py` → all PASS |
| **4** | **Kilo Review Loop** | Fix ALL issues until verdict=PASS (diff-scoped) |
| **5** | **Final Gate (Post-Kilo)** | `python /opt/fabrik/scripts/final_gate.py` → all PASS |
| **6** | **Traycer Verification** | Traycer verifier passes |
| **7** | **Sync Only** | `python /opt/fabrik/scripts/final_gate.py --sync` → sync extensions/backup |
| **8** | **Traycer Commit** | Pre-commit runs 4 blockers only |
| **9** | **Next Phase** | Move to next Traycer phase |

### Step Details

**Step 1 - Traycer Plan:** Ensure plan includes functional spec, edge cases, required env vars, DB changes, docs impact. Do NOT start if spec is vague.

**Step 2 - Coder Implements:** Use Gemini 3.1 Pro High Thinking (1x). Implement only phase scope. Escalate to Sonnet 4.5 Thinking (3x) if stuck.

**Step 2.5 - Self-Review (MANDATORY - Implemented 2026-03-06):** Before running pre-kilo, coding AI MUST review its own implementation.

**For Traycer CLI Agents:** Agent performs structured self-review via separate Kilo call:
1. Agent re-reads original task/spec completely
2. Agent checks each requirement against code changes
3. Agent verifies edge cases are handled
4. Agent confirms environment variables documented
5. Agent confirms database changes documented
6. Agent generates structured self-review report

**Self-Review Format (Required):**
```
SELF-REVIEW COMPLETE:
✓ All spec requirements implemented: [Yes/No + brief details]
✓ Edge cases handled: [list specific cases or "N/A"]
✓ Env vars documented: [list variables or "N/A"]
✓ DB changes documented: [list changes or "N/A"]
⚠ Potential issues: [list concerns or "None identified"]
```

**For Manual Review (non-Traycer):**
1. Re-read the plan/spec completely
2. Check each requirement against code changes
3. Verify edge cases are handled
4. Confirm env vars/DB changes documented
5. Report findings in structured format:

```
SELF-REVIEW COMPLETE:
✓ All spec requirements implemented
✓ Edge cases handled: <list or "N/A">
✓ Env vars documented: <list or "N/A">
✓ DB changes documented: <list or "N/A">
⚠ Potential issues: <list or "None identified">

Next: Proceed to Step 3 (Final Gate Pre-Kilo)
```

**Violations:** Proceeding to Step 3 without self-review = FORBIDDEN. Self-review report missing required sections = STOP.

**Step 3 - Final Gate (Pre-Kilo):** Catches deterministic failures BEFORE spending Kilo tokens.
Checks include:
- Auto-fix: trailing whitespace, EOF newline, ruff-format, ruff --fix
- Static: ruff, mypy, bandit, semgrep (best-effort), check yaml, check json, sqlfluff, vulture
- Consistency: structure, conventions, rule size, model names sync, changelog, kilo health

**Step 4 - Kilo Review (Strict Enforcement - 2026-03-05):** 6-layer enforcement pipeline. Reviews diff with:
1. Pre-review gates (final_gate.py results injected into prompt)
2. Risk assessment (security paths + diff size → triggers multi-pass if needed)
3. Plan extraction (REQ-#, numbered, bulleted requirements)
4. Schema validation (strict JSON, NO auto-fill, invalid → BLOCKER)
5. Evidence validation (BLOCKER/MAJOR must have structured evidence: file_line, diff, tool_output, missing, multi_file, external)
6. Plan coverage validation (all requirements must be addressed, skip for doc/verify modes)

Coder fixes ALL issues (BLOCKER, MAJOR, MINOR). Repeat until verdict=PASS. Retry logic: 1 attempt with JSON skeleton if schema fails. Token accounting: sums ALL attempts. Multi-pass: 2 passes (general + security-focused) for high-risk changes.

**Step 5 - Final Gate (Post-Kilo):** Ensures Kilo fixes didn't break deterministic rules.

**Step 6 - Traycer Verification:** If issues found, return to Step 3.

**Step 7 - Sync Only:** Runs sync steps only (extensions, backup). No duplicate checks—Step 5 already verified everything.

**Step 8 - Traycer Commit:** Runs only 4 blockers: check-added-large-files, check-merge-conflict, detect-private-key, forbid-secrets.

### Why This Works

- Deterministic issues caught early (saves tokens)
- LLM tokens used only for reasoning problems
- No repeated lint/security cycles inside Kilo
- No commit friction
- No duplicated gates

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
- Do NOT implement without plan approval
- Do NOT skip final_gate before Kilo review
- Do NOT proceed with BLOCKER/MAJOR issues
- Do NOT skip post-Kilo final_gate
- Do NOT commit without Step 7 passing

---

## Planning (Required for Non-Trivial Work)

> ⚠️ **Archived templates (2026-02-25):** `PHASE_TEMPLATE.md`, `TASKS_TEMPLATE.md`, and `implementation-plan-template.md` have been archived to `docs/archive/2026-02-25-pre-traycer-templates/`. Do NOT recreate them. Use Traycer Phases for all planning.

**If Traycer is used:** Planning happens in Traycer Phases. The plan is exported to `docs/development/plans/` and indexed in `docs/development/PLANS.md`. Coding agents only execute steps from the Traycer-managed plan.

**If Traycer is NOT used:** Create a plan document before implementing any feature or fix.

### Plan Location & Naming
- Location: `docs/development/plans/`
- Filename: `YYYY-MM-DD-plan-<name>.md` (e.g., `2026-01-14-plan-feature-auth.md`)

### Plan Lifecycle
1. **Create** plan in `docs/development/plans/`
2. **Add** to `docs/development/PLANS.md` index
3. **Update** `**Status:**` as work progresses
4. **Check boxes** as items complete
5. **Archive** when COMPLETE → move to `docs/archive/`

### Required Plan Sections
- `**Status:**` line (NOT_STARTED, IN_PROGRESS, PARTIAL, COMPLETE, NOT_DONE)
- `## Goal` - One-line description
- `## DONE WHEN` - Checkboxes for completion criteria
- `## Out of Scope` - What's excluded
- `## Steps` - Implementation steps

---

## Traycer Mode Selection

**When planning work with Traycer, choose the appropriate mode based on task complexity:**

| Scenario | Mode | Description |
|----------|------|-------------|
| **Single-PR / Focused task** | **Plan** | Creates a detailed, actionable implementation plan. Best for tasks that fit in one PR. |
| **Complex / Multi-step project** | **Phases** | Manages multiple phases across a project lifecycle to prevent context loss. Each phase is a discrete unit of work. |
| **Feature with specs + tickets** | **Epic** | Driven by Workflows (default: Traycer Agile Workflow). Organizes work into mini-spec artifacts (Specs) and actionable Tickets. Ideal for features requiring requirements gathering, technical planning, and ticket breakdown. |
| **Code Audit / Verification** | **Review** | Structured workflow for code review tasks. |

**Workflow-Driven Modes (Epic):**
- **Traycer Agile Workflow** (default): 8-command, 3-gated-phase workflow for feature development (`/trigger_workflow` → `/epic-brief` → `/core-flows` → `/prd-validation` → `/tech-plan` → `/architecture-validation` → `/ticket-breakdown` → `/implementation-validation`)
- **Traycer Refactoring Workflow**: 4-command workflow for safe refactoring (`/trigger-workflow` → `/plan-refactor` → `/ticket-breakdown` → `/verification`)
- **Custom Workflows**: Create your own command sequences tailored to your methodology

**For complete workflow details**, see:
- [`docs/traycer/README.md`](docs/traycer/README.md) - Traycer integration guide
- [`docs/traycer/traycer-agile-workflow.md`](docs/traycer/traycer-agile-workflow.md) - Detailed Agile Workflow reference
- [`docs/traycer/traycer-refactoring-workflow.md`](docs/traycer/traycer-refactoring-workflow.md) - Detailed Refactoring Workflow reference
- [`docs/guides/DEVELOPMENT_WORKFLOW.md`](docs/guides/DEVELOPMENT_WORKFLOW.md) - How Traycer fits into Fabrik's 9-step workflow

---

## Traycer Mode (When Task is Traycer-Managed)

When executing a Traycer-managed plan via the **Windsurf Extension**:

1. **Traycer runs as an IDE Extension** — It connects directly to your WSL environment via CLI agents (`~/.traycer/cli-agents/`).
2. **Context Preservation** — Traycer automatically carries forward file mappings, decisions, and rationale across phases. Do not re-analyze the entire architecture if you are executing a later phase; rely on the provided spec.
3. **Async Job Submission** — Traycer submits plans using `factory_submit.py` and waits for execution using `factory_wait.py` inside `/opt/fabrik/`.
4. **Follow steps exactly in order** — Only execute steps from the managed plan.
5. **Do NOT redesign or change scope** — If changes needed, pause and request plan update from Traycer.
6. **One step at a time** — Complete current step before moving to next.
7. **After each step:** Show Evidence + Gate result (use Step Output Format above).
8. **If a Gate fails** → STOP and report to Traycer for re-planning.

**Forbidden actions in Traycer Mode:**
- Reordering steps
- Expanding scope beyond the plan
- Modifying plan steps without Traycer approval
- Creating alternative plans or workarounds
- Skipping verification steps

---

## Documentation Rules

1) **VERIFY before creating:** Check `INDEX.md` (root) and existing folders before creating new files.
2) Do NOT create markdown files in repo root (except INDEX.md, README.md, CHANGELOG.md, AGENTS.md, PORTS.md, LICENSE.md).
3) Feature/Execution plans: See **Planning** section above.
4) Every new plan MUST be added to `docs/development/PLANS.md`.
5) Do NOT create new folders under `docs/` except via existing structure.
6) If you add a module under `src/`, ensure a reference doc exists:
   - `docs/reference/<module>.md`
   - If missing, run `docs_updater.py --sync`.
7) NEVER edit inside `<!-- AUTO-GENERATED:* -->` blocks.
   - Run `docs_updater.py --sync` instead.
8) All changes MUST keep `make docs-check` passing.

**docs/ root allowlist (standard files):**
- `QUICKSTART.md`, `CONFIGURATION.md`, `TROUBLESHOOTING.md`, `BUSINESS_MODEL.md`
- `SERVICES.md`, `FABRIK_OVERVIEW.md`, `ENVIRONMENT_VARIABLES.md`

**Configuration pattern (NO DUPLICATION):**
- `.env.example` = AUTHORITATIVE variable reference (self-documenting with inline comments)
- `docs/CONFIGURATION.md` = GUIDE only (how to get credentials, architecture, troubleshooting)
- DO NOT duplicate variable tables in CONFIGURATION.md - reference .env.example instead

**AUTO-GENERATED blocks (DO NOT EDIT MANUALLY):**
- `BUSINESS_MODEL.md` → `<!-- AUTO-GENERATED:PROJECTS:* -->` (project catalog)
- Run `python /opt/fabrik/scripts/sync_projects.py` to update
- Automatically syncs on `fabrik scaffold` completion

**Existing docs structure:**
- `docs/guides/` - How-to guides
- `docs/reference/` - Technical reference
- `docs/operations/` - Ops runbooks
- `docs/development/plans/` - Plan documents
- `docs/archive/` - Archived/completed docs

Violations will fail CI and must be fixed before merge.

---

## ⚠️ MANDATORY WORKFLOW (ALL AI AGENTS)

**Before finishing ANY coding task, you MUST:**

```bash
# 1. Run enforcement check
python3 -m scripts.enforcement.validate_conventions --strict <changed_files>

# 2. Trigger code review (if significant changes)
# Traycer-managed: Run Traycer verification (primary)
# Otherwise: python /opt/fabrik/scripts/kilo_code_review.py review <files> --output json

# 3. Update documentation
# If you changed code in src/, scripts/, update relevant docs/
```

**Kilo Code Review Workflow:**

```bash
# Initial review: pass the task/plan for SPEC verification
python /opt/fabrik/scripts/kilo_code_review.py review <changed_files> \
  --plan .droid/review-context/task.md \
  --review-agent ask \
  --output json

# Subsequent reviews: use --session continue (Kilo maintains context)
python /opt/fabrik/scripts/kilo_code_review.py review <changed_files> \
  --session continue \
  --output json
```

Then:
1. Read JSON output - check `verdict` and `issues`
2. Fix ALL issues myself (BLOCKER, MAJOR, MINOR) - I fix, not Kilo
3. Get another review with `--session continue`
4. Repeat 2-3 until `verdict=PASS` (max 5 iterations)
5. Report to user what was done

**Key points:**
- **Pass the task/plan on initial review** - Kilo needs it for SPEC verification
- Save task to `.droid/review-context/task.md` (not in `docs/development/plans/`)
- I fix issues, not Kilo (cheaper: review ~$0.03-0.40 vs auto-fix ~$1-2)
- Fix ALL severities, not just BLOCKER/MAJOR
- Use `--session continue` for subsequent reviews (maintains context)
- Max 5 iterations before stopping

**Sequence (Traycer-managed):**
```
Code → Final Gate → Kilo loop → Final Gate → Traycer verification → Sync (--sync) → Commit
```

**Sequence (Non-Traycer):**
```
Code → Final Gate → Kilo loop until PASS → Final Gate → Sync (--sync) → Commit
```

**Violation:** Committing without Step 7 (`python /opt/fabrik/scripts/final_gate.py --sync`) PASS.

---

## Sensitive Data Protection (CRITICAL)

**Before modifying files with credentials/secrets:**
- `.env`, `.env.*` (not `.env.example`)
- `*.key`, `*.pem`, `*.p12`, `*.pfx`
- `secrets/`, `credentials/`, `.ssh/`

**REQUIRED: Create timestamped backup first**
```bash
cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
```

**FORBIDDEN actions:**
- Modify `.env` without backup
- Run destructive scripts on production data without dry-run test on dummy data first
- Apply changes to credentials without showing full diff for approval

---

## Security Gates (MANDATORY - Runs 3 Times Per Phase)

**Final Gate runs twice, then sync-only once:**

```bash
# Step 3 - Before Kilo review (catches deterministic failures, saves tokens)
python /opt/fabrik/scripts/final_gate.py

# Step 5 - After Kilo review (ensures Kilo fixes didn't break rules)
python /opt/fabrik/scripts/final_gate.py

# Step 7 - Sync only (no duplicate checks)
python /opt/fabrik/scripts/final_gate.py --sync
```

**What Final Gate checks:**
1. **Auto-fix formatting** - trailing whitespace, EOF, ruff-format, ruff --fix
2. **Static analysis** - ruff, mypy, bandit, semgrep, yaml, json, sqlfluff, vulture
3. **Repo consistency** - structure, conventions, rule size, model names, changelog, kilo health, symlink integrity
4. **Sync steps** (Step 7 only) - Windsurf Extensions, Cascade Backup

**Enforcement Scripts (`scripts/enforcement/`):**

| Script | Purpose | Severity |
|--------|---------|----------|
| `check_env_vars.py` | Hardcoded localhost/127.0.0.1 | ERROR |
| `check_secrets.py` | Hardcoded API keys, tokens | ERROR |
| `check_env_contract.py` | .env.example ↔ compose.yaml ↔ CONFIGURATION.md | ERROR/WARN |
| `check_health.py` | /health tests deps + test file exists | WARN |
| `check_docker.py` | Alpine base, HEALTHCHECK, port consistency | ERROR/WARN |
| `check_ports.py` | Port registered in PORTS.md | WARN |
| `check_watchdog.py` | Watchdog script exists | WARN |
| `check_structure.py` | MD file placement | ERROR/WARN |
| `check_changelog.py` | CHANGELOG entry for code changes | ERROR |
| `check_docs.py` | Module docs exist | WARN |
| `check_plans.py` | Plan naming convention | ERROR/WARN |
| `check_rule_size.py` | Rule files < 12KB | ERROR |

**Why default never syncs (Steps 3/5):**
- Avoids side-effect diffs before review is complete
- Sync only matters for final release candidate

**What remains in pre-commit hooks (4 absolute blockers):**
- `check-added-large-files` - No files >500KB
- `check-merge-conflict` - No conflict markers
- `detect-private-key` - No secrets
- `forbid-secrets` - No .env, .pem, .key files

**Workflow:**
1. Kilo review PASS (or Traycer verification PASS)
2. Run `python /opt/fabrik/scripts/final_gate.py` — fix until clean
3. Press Traycer Commit (or `git commit`)
4. Pre-commit runs only 4 blockers
5. Commit succeeds

---

## Windsurf Cascade Users

For IDE-specific rules, see `.windsurf/rules/`:
- `00-critical.md` — Security, env vars, ports (Always On)
- `10-python.md` — FastAPI patterns (*.py glob)
- `20-typescript.md` — Next.js patterns (*.ts, *.tsx glob)
- `30-ops.md` — Docker/deployment (Always On)
- `40-documentation.md` — Plan documents, writing style (Always On)
- `50-code-review.md` — Execution protocol, PLAN→APPROVE→IMPLEMENT→REVIEW→FIX→VALIDATE→NEXT (Always On)
- `90-automation.md` — Traycer YOLO automation, Fabrik skills (Always On)

## Build & Test

```bash
# Python projects
pip install -e .                    # Install in dev mode
pytest                              # Run tests
pytest -x --tb=short               # Stop on first failure

# Check code quality
ruff check .                        # Lint
mypy .                              # Type check (full); pre-commit uses src/fabrik/ only

# Docker
docker compose up -d                # Start services
docker compose logs -f              # Follow logs
docker compose down                 # Stop services
```

## Run Locally

```bash
# Most projects use uvicorn
uvicorn src.main:app --reload --port 8000

# Or with watchdog scripts
./scripts/watchdog_api.sh start

# Check health
curl http://localhost:8000/health
```

## Architecture Overview

Fabrik projects follow a consistent pattern:

- **WSL (dev)** → Local PostgreSQL, local services, `.env` file
- **VPS (prod)** → Coolify-managed Docker Compose, `postgres-main` container
- **Every project ships as one Compose app** — web + worker + optional services

## SaaS Projects (MANDATORY)

**When starting ANY SaaS, web app, or dashboard project, ALWAYS use the SaaS skeleton:**

```bash
cp -r /opt/fabrik/templates/saas-skeleton /opt/<project-name>
cd /opt/<project-name>
npm install
cp .env.example .env
npm run dev
```

**Template includes:** Next.js 14 + TypeScript + Tailwind CSS, marketing pages, app pages (dashboard, settings, job workflow), SSE streaming + ChatUI for AI chat integration.

**Customize:** `lib/config/site.ts` for branding, `app/(marketing)/` for content.

## Project Layout

```
/opt/<project>/
├── src/ or <package>/     # Main source code
│   ├── main.py            # Entry point
│   ├── config.py          # Config loading (from env vars)
│   ├── models/            # Data models
│   ├── services/          # Business logic
│   └── api/               # API endpoints
├── tests/                 # Tests mirror src/
├── scripts/               # Utility & watchdog scripts
├── config/                # YAML/JSON configs
├── docs/                  # Documentation
├── compose.yaml           # Docker Compose for deployment
├── .env.example           # Env var template (never commit .env)
└── AGENTS.md              # This file (symlinked)
```

## Conventions & Patterns

### Environment Variables (CRITICAL)

```python
# CORRECT - works in WSL, Docker, Supabase
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))

# WRONG - breaks in production
DB_HOST = 'localhost'  # Hardcoded!
```

### Health Checks

```python
# CORRECT - tests actual dependencies
@app.get("/health")
async def health():
    await db.execute("SELECT 1")  # Actually test DB
    return {"status": "ok", "db": "connected"}

# WRONG - hides failures
@app.get("/health")
async def health():
    return {"status": "ok"}  # Lies!
```

### Config Loading

```python
# CORRECT - load at runtime
def get_db_url():
    return f"postgresql://{os.getenv('DB_USER')}:..."

# WRONG - class-level (env not set at import time)
class Config:
    DB_URL = f"postgresql://{os.getenv('DB_USER')}:..."  # Fails!
```

## Security

- **Never commit `.env`** — Use `.env.example` as template
- **All credentials in TWO places:**
  1. Project `.env` (local use)
  2. `/opt/fabrik/.env` (master backup)
- **CSPRNG passwords**: 32 chars, alphanumeric only
- **No hardcoded secrets** — Always use env vars

## Deployment

Target: **Coolify on VPS via Docker Compose**

```yaml
# compose.yaml structure
services:
  api:
    build: .
    environment:
      - DB_HOST=postgres-main
      - DB_PORT=5432
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
```

## Gotchas

1. **Never use `/tmp/`** — Use project-local `.tmp/` instead (data survives restarts)
2. **Health checks must test dependencies** — Not just return `{"status": "ok"}`
3. **Env vars not set at import time** — Load config in functions, not class-level
4. **Test in Docker before deploying** — `docker compose up` locally first

## Documentation Rules (MUST)

**Every code change requires documentation update.** No exceptions.

### Document Location Rules (ENFORCED)

**Root-level `.md` files allowed:**
- `README.md`, `CHANGELOG.md`, `AGENTS.md`, `PORTS.md`, `LICENSE.md`

**All other docs (not in allowlist below) MUST go in `docs/` subdirectories:**

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

This is enforced by `scripts/enforcement/check_structure.py` and pre-commit hook.

### When Making Changes

1. **Update docs/INDEX.md structure map** if adding/moving/deleting files
2. **Update relevant docs** in same commit as code changes
3. **Add Last Updated date** to modified docs: `**Last Updated:** YYYY-MM-DD`
4. **Archive, don't delete** obsolete docs → `docs/archive/YYYY-MM-DD-topic/`

### Documentation Standards

| Rule | Example |
|------|---------|
| **Clear title** | `# Feature Name` not `# Notes` |
| **Purpose statement** | First paragraph explains what and why |
| **Runnable examples** | Code blocks with copy-paste commands |
| **Cross-references** | Link to related docs with relative paths |
| **No stale info** | Remove or archive outdated sections |

### Required for Every Feature

```markdown
## Feature Name

**Purpose:** One-line description

**Usage:**
\`\`\`bash
command --example
\`\`\`

**Configuration:** List env vars or config options

**See also:** [related-doc.md](path/to/related-doc.md)
```

### Quick Checks Before Commit

- [ ] `docs/INDEX.md` structure map current?
- [ ] Changed files have updated Last Updated date?
- [ ] New features documented?
- [ ] Removed features archived or deleted from docs?

## Execution Modes (Fabrik Lifecycle)

| Mode | Task Type | Model | Reasoning | Autonomy |
|------|-----------|-------|-----------|----------|
| Explore | `analyze` | gemini-3-flash-preview | off | low |
| Design | `spec` | claude-sonnet-4-5-20250929 | **high** | low |
| Build | `code, scaffold` | gpt-5.1-codex-max | medium | **high** |
| Verify | `test, health` | gpt-5.1-codex-max / gemini-3-flash-preview | low/off | **high** |
| Ship | `deploy` | gemini-3-flash-preview | off | **high** |

**Get current models:** `python3 scripts/droid_models.py stack-rank`

**Config:** `config/models.yaml` — Single source of truth for model names

**Mixed Models:** Use premium models with high reasoning for planning (`spec`), fast models for implementation (`code`).

**Code Review:** See `.windsurf/rules/50-code-review.md` for complete 9-step workflow with Kilo CLI.

## Traycer CLI Agent Auto-Review Integration

**Last Updated:** 2026-03-06
**Status:** Implemented in Free (9), Economy (8), and Balanced (6) tiers = 23 total agents

**Purpose:** Enable Traycer CLI agents to automatically run the complete 9-step review workflow with mandatory self-review.

**Location:**
- Fixed agents: `/opt/fabrik/scripts/traycer_agents_fixed/`
- Review script: `/opt/fabrik/scripts/traycer_agent_review.py`
- Implementation script: `/opt/fabrik/scripts/implement_self_review_workflow.py`
- Documentation: `/opt/fabrik/docs/guides/traycer-kilo-workflow-analysis.md`

### Complete Agent Workflow (Implemented 2026-03-06)

**Single Agent Execution:**
```bash
# 1. Agent codes task (Step 2)
kilo run --model ... "$PROMPT"

# 2. Agent performs Step 2.5 Self-Review (MANDATORY)
SELF_REVIEW_PROMPT="You just implemented: $PROMPT
Files changed: $CHANGED_FILES
Perform structured self-review..."

SELF_REVIEW_OUTPUT=$(kilo run --model ... "$SELF_REVIEW_PROMPT")

# 3. Agent calls review script with real self-review
python /opt/fabrik/scripts/traycer_agent_review.py \
    --task "$PROMPT" \
    --files $CHANGED_FILES \
    --self-review "$SELF_REVIEW_OUTPUT" \
    --session-id "$SESSION_ID" \
    --output json

# 4. Review script runs Steps 3-5
#    - Step 3: Pre-Kilo Gate (24 checks)
#    - Step 4: Kilo Review (separate reviewer agent)
#    - Step 5: Post-Kilo Gate (validates fixes)

# 5. Agent returns exit code
#    - 0 = PASS → Traycer verifies (Step 6)
#    - 1 = FAIL → Traycer re-invokes agent (fix loop)
```

**Two-Level Loop Architecture:**
- **Inner Loop (Agent):** Single attempt (code → self-review → review → report)
- **Outer Loop (Traycer):** Re-invokes agent on failure (~5 attempts max)

**Execution Flow:**
1. **Step 2 - Implementation:** Agent codes task
2. **Step 2.5 - Self-Review (MANDATORY):** Agent performs structured self-review via separate Kilo call
3. **Step 3 - Pre-Kilo:** Review script runs `final_gate.py` (24 deterministic checks)
4. **Step 4 - Kilo Review:** Review script spawns **separate Kilo reviewer agent** (maintains own session ID)
5. **Step 5 - Post-Kilo:** Review script runs `final_gate.py` again (ensures fixes didn't break rules)
6. **Exit:** Returns to Traycer for Step 6 verification or re-invocation

**Key Features:**
- **Real Self-Review:** Separate Kilo call generates structured report (not placeholder)
- **Validation:** Rejects placeholder/failed self-reviews with exit code 2
- **Mandatory Workflow:** Always runs on success (not optional)
- **Separate Reviewer:** Kilo reviewer runs as independent agent (unbiased review)
- **Session Isolation:** Coder and reviewer maintain separate session IDs for tracking
- **No Auto-Commit:** Workflow stops before commit - Traycer handles Step 6 verification
- **JSON Output:** Structured result for programmatic parsing
- **Cost Tracking:** Review cost tracked separately from coding cost

**Exit Codes:**
- `0` - All gates PASS, Kilo verdict PASS → Ready for Traycer verification
- `1` - Review failed (issues found or gates failed) → Traycer re-invokes agent
- `2` - Error (validation failed, self-review placeholder/failed)

**Self-Review Validation:**
- ✅ Requires structured format with all 5 sections (spec, edge cases, env vars, DB changes, issues)
- ❌ Rejects: "Agent completed implementation" (placeholder)
- ❌ Rejects: "SELF-REVIEW FAILED: Timeout or error"
- ⚠️ Warns: Missing required sections but proceeds

**Agent Tiers:**

1. **System Prompt Addition:** Add to Traycer CLI agent prompts:
   ```
   After completing implementation, run auto-review workflow:
   {% include 'fabrik-auto-review.md' %}
   ```

2. **Post-Execution Hook:** Configure in Traycer:
   ```yaml
   post_execution_hook:
     script: /opt/fabrik/scripts/traycer_agent_review.py
     args: [--task, "{{ task }}", --files, "{{ changed_files }}", ...]
   ```

3. **Manual Invocation:** Agent explicitly calls script after coding

**Cost Estimate:** ~$0.10-0.50 per agent execution (Kilo review only, gates are free)

**See:** `/opt/fabrik/templates/traycer/agent-post-execution-hook.md` for complete integration guide

---

## Traycer Report Panel (Windsurf Extension)

**Last Updated:** 2026-03-06
**Status:** Implemented and available for all Fabrik projects

**Purpose:** Windsurf extension that captures and displays Traycer CLI agent execution reports with full history browsing.

### Quick Start

1. **Install Extension** (one-time):
   ```
   Extensions → Install from VSIX → ~/traycer-report-panel/traycer-report-panel-0.2.0.vsix
   ```

2. **View Reports:**
   - Click 📄 icon in left sidebar (activity bar)
   - See two sections: **Report History** (top) + **Report Content** (bottom)
   - Click any report in history to view it

3. **Automatic Capture:**
   - Runs automatically when Traycer executes Kilo CLI agents
   - Reports saved to `.droid/traycer-reports/TIMESTAMP-slug.md`
   - Notification appears when new report arrives

### How It Works

```
Traycer Job → Agent Outputs Delimited Report → factory_wait.py Extracts
→ Writes to .droid/traycer-reports/ → Extension Detects → Notification + Display
```

**Key Components:**
- **Prompt Templates:** Force agents to wrap reports in `BEGIN_TRAYCER_REPORT_MD` / `END_TRAYCER_REPORT_MD`
- **Extraction:** `scripts/traycer_write_report.py` extracts from stdout
- **Integration:** `factory_wait.py` pipes stdout to extraction script
- **Storage:** Timestamped files in `.droid/traycer-reports/` (never overwritten)
- **Display:** Windsurf extension shows history + content

### Inheritance by Fabrik Projects

| Component | Auto-Inherited? |
|-----------|-----------------|
| Report extraction logic | ✅ Yes - shared via `/opt/fabrik/factory_wait.py` |
| Storage directory | ✅ Yes - created on first report |
| Prompt templates | ✅ Yes - global in `~/.traycer/` |
| Windsurf extension | ⚠️ Manual install (affects all workspaces) |

**All Fabrik projects automatically get report extraction.** Extension install is one-time per Windsurf instance.

### Documentation

**Complete Guide:** `/opt/fabrik/docs/guides/traycer-report-panel.md`

Covers:
- Architecture diagram
- Component details (extraction, integration, templates)
- File structure
- Security model
- Troubleshooting

---

## VPS Deployment (Coolify)

**Deployment:** Use Fabrik CLI (`fabrik apply`) for deployment automation to Coolify.

## GitHub Actions Workflows

Location: `.github/workflows/`

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `droid-review.yml` | PR opened/updated | Automated code review with Fabrik checks |
| `update-docs.yml` | Push to main | Auto-update docs when code changes |
| `security-scanner.yml` | Weekly (Monday 9AM) | Vulnerability and secrets scan |
| `daily-maintenance.yml` | Daily (3AM) | Docs and test updates |

**Setup:** Add `FACTORY_API_KEY` to repository secrets.

## Fabrik Skills (Convention Enforcement)

Location: `.factory/skills/`

Skills define Fabrik's coding conventions and project patterns.

| Skill | Triggers On | Purpose |
|-------|-------------|---------|
| `fabrik-scaffold` | "new project", "create service" | Full project structure with all conventions |
| `fabrik-docker` | "dockerfile", "compose", "deploy" | Docker/Compose for ARM64 Coolify VPS |
| `fabrik-health-endpoint` | "health", "healthcheck" | Health endpoints that test dependencies |
| `fabrik-config` | "config", "environment", "settings" | os.getenv() patterns, .env.example |
| `fabrik-preflight` | "preflight", "deploy ready" | Pre-deployment validation checklist |
| `fabrik-api-endpoint` | "endpoint", "route", "API" | FastAPI patterns with Pydantic |
| `fabrik-watchdog` | "watchdog", "monitor", "auto-restart" | Service monitoring scripts |
| `fabrik-postgres` | "database", "postgres", "migration" | PostgreSQL + pgvector setup |

## MCP (Model Context Protocol)

MCP servers extend AI capabilities with external tools. Config: `~/.factory/mcp.json`

| Server | Purpose | Priority |
|--------|---------|----------|
| `playwright` | E2E browser testing | High |
| `sentry` | Error tracking | High |
| `supabase` | Database management | High |
| `stripe` | Payments | Medium |
| `linear` | Issue tracking | Medium |
| `notion` | Documentation | Medium |

Template: `/opt/fabrik/templates/scaffold/factory-mcp.json`

Full documentation: `docs/reference/droid-exec-usage.md` §18

## Droid Hooks

Hooks execute at various points in droid's lifecycle. Location: `/opt/fabrik/.factory/hooks/`

| Hook | Purpose |
|------|---------|
| `fabrik-conventions.py` | Validates Fabrik conventions (no hardcoded localhost, proper images) |
| `secret-scanner.py` | Detects hardcoded secrets |
| `format-python.sh` | Auto-formats Python with ruff/black |
| `protect-files.sh` | Blocks edits to .env, credentials |
| `session-context.py` | Loads project context on session start |

Template: `/opt/fabrik/templates/scaffold/factory-hooks.json`

Full documentation: `docs/reference/droid-exec-usage.md` §19

## Agent Readiness Checklist

Fabrik projects target **Level 3+ (Standardized)** readiness.

**Why this matters:** Fast verification tools let Droid self-correct. Slow tools slow everything.

### Level 1: Functional
- [ ] README.md with setup instructions
- [ ] Linter configured (`ruff check .` / `npm run lint`)
- [ ] Type checker configured (`mypy .` / `npx tsc --noEmit`)
- [ ] Unit tests exist (`pytest` / `npm test`)

### Level 2: Documented
- [ ] AGENTS.md (symlink to `/opt/fabrik/AGENTS.md`)
- [ ] .env.example with all required vars
- [ ] Pre-commit hooks or CI validation
- [ ] compose.yaml for deployment

### Level 3: Standardized
- [ ] Integration tests
- [ ] Health check endpoint that tests dependencies
- [ ] Structured logging (JSON format)
- [ ] Secret scanning (no hardcoded credentials)
- [ ] Verification runs in <30 seconds

### Level 4: Optimized (Target)
- [ ] CI/CD pipeline with fast feedback (<5 min)
- [ ] Automated deployment via Coolify
- [ ] Metrics/observability

**Critical:** Keep verification fast. Tests >30s kill iteration speed.

---

## Writing Effective Prompts

**Full guide:** `docs/reference/droid-exec-usage.md` §27-31

**Quick patterns:**
- **Feature:** Goal + files + similar code + verification
- **Bug fix:** Error + reproduction + relevant files
- **Refactor:** What to change + what to preserve
- **Review:** Scope + focus areas (security, performance)

**Example:**
```
Add rate limiting to login attempts with exponential backoff.
Similar pattern in middleware/rateLimit.ts.
Run auth tests to verify.
```

---

*Symlink: `ln -s /opt/fabrik/AGENTS.md AGENTS.md`*
*Complements: `.windsurfrules` (Windsurf-specific rules)*
