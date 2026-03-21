# Fabrik Project Agent Briefing

**Last Updated:** 2026-03-20

> Traycer is the planning authority. Kilo CLI or Windsurf Cascade is the coding executor.

## Quick Navigation

**Coder AI:** Read sections marked `[CODER AI]` and `[ALL AGENTS]`. Skip `[TRAYCER ONLY]`, `[REVIEWER]`, `[FIXER]`.

**Reviewer:** Read sections marked `[REVIEWER]` and `[ALL AGENTS]`. Skip `[TRAYCER ONLY]`, `[CODER AI]`, `[FIXER]`.

**Fixer:** Read sections marked `[FIXER]` and `[ALL AGENTS]`. Skip `[TRAYCER ONLY]`, `[CODER AI]`, `[REVIEWER]`.

**Traycer:** Read all sections.

---

<!-- AUTO-GENERATED:TOC:START -->
<!-- This section is auto-generated. Do not edit manually. Run: python scripts/update_agents_toc.py -->
## Table of Contents
- [Quick Navigation](#quick-navigation)
- [[TRAYCER ONLY] Authority Model](#traycer-only-authority-model)
- [[ALL AGENTS] Orientation — Do This First (MANDATORY)](#all-agents-orientation-—-do-this-first-mandatory)
- [[ALL AGENTS] Environment Context](#all-agents-environment-context)
- [[ALL AGENTS] Execution Protocol (7-Step Agile Flow)](#all-agents-execution-protocol-7-step-agile-flow)
- [[TRAYCER ONLY] Traycer Mode Selection](#traycer-only-traycer-mode-selection)
- [[TRAYCER ONLY] Traycer Mode (When Task is Traycer-Managed)](#traycer-only-traycer-mode-when-task-is-traycer-managed)
- [[ALL AGENTS] Documentation Rules](#all-agents-documentation-rules)
- [[ALL AGENTS] ⚠️ MANDATORY WORKFLOW](#all-agents-⚠️-mandatory-workflow)
- [[ALL AGENTS] Sensitive Data Protection (CRITICAL)](#all-agents-sensitive-data-protection-critical)
- [[ALL AGENTS] Security Gates (MANDATORY)](#all-agents-security-gates-mandatory)
- [[ALL AGENTS] Build & Test](#all-agents-build-test)
- [[CODER AI] Run Locally](#coder-ai-run-locally)
- [[CODER AI] Architecture Overview](#coder-ai-architecture-overview)
- [[CODER AI] SaaS Projects (MANDATORY)](#coder-ai-saas-projects-mandatory)
- [[CODER AI] Project Layout](#coder-ai-project-layout)
- [[ALL AGENTS] Conventions & Patterns](#all-agents-conventions-patterns)
- [[ALL AGENTS] Security](#all-agents-security)
- [[CODER AI] Deployment](#coder-ai-deployment)
- [[ALL AGENTS] Gotchas](#all-agents-gotchas)
- [[ALL AGENTS] Documentation Rules (MUST)](#all-agents-documentation-rules-must)
- [Feature Name](#feature-name)
- [[TRAYCER ONLY] Execution Modes (Fabrik Lifecycle)](#traycer-only-execution-modes-fabrik-lifecycle)
- [[TRAYCER ONLY] Traycer CLI Agent Auto-Review Integration](#traycer-only-traycer-cli-agent-auto-review-integration)
- [[TRAYCER ONLY] Traycer Report Panel (Windsurf Extension)](#traycer-only-traycer-report-panel-windsurf-extension)
- [[TRAYCER ONLY] VPS Deployment (Coolify)](#traycer-only-vps-deployment-coolify)
- [[TRAYCER ONLY] GitHub Actions Workflows](#traycer-only-github-actions-workflows)
- [[TRAYCER ONLY] Fabrik Skills (Convention Enforcement)](#traycer-only-fabrik-skills-convention-enforcement)
- [[TRAYCER ONLY] MCP (Model Context Protocol)](#traycer-only-mcp-model-context-protocol)
- [[TRAYCER ONLY] Droid Hooks](#traycer-only-droid-hooks)
- [[CODER AI] Agent Readiness Checklist](#coder-ai-agent-readiness-checklist)
- [[CODER AI] Writing Effective Prompts](#coder-ai-writing-effective-prompts)
<!-- AUTO-GENERATED:TOC:END -->

## [TRAYCER ONLY] Authority Model

- You write content.
- Deterministic gates enforce structure.
- Final Gate is the quality authority.
- Pre-commit enforces only absolute blockers.

### Traycer Planning Authority

**Traycer is the planning authority.**
- All planning happens in Traycer
- Coding agents execute steps from the Traycer-managed plan
- Traycer's verifier confirms SPEC compliance

---

## [ALL AGENTS] Orientation — Do This First (MANDATORY)

**Scan before you act.** Read the full project structure from root before generating anything.

**Do not** recreate `.venv`, `node_modules/`, or replace existing Docker configuration unless explicitly instructed.

---

## [ALL AGENTS] Environment Context

**Runtime:** WSL (Ubuntu). Linux paths and commands only. Never assume Windows tooling.

**Structure:** Project scaffold is fixed. Work within it — do not reorganize, flatten, or add top-level directories without explicit instruction.

**Task execution:** Architectural decisions, base images, and tool choices are resolved before coding begins — they are not your concern. Follow the plan verbatim. State any assumption explicitly before acting on it.

**Deployment:** Linux VPS via container orchestration, optionally Supabase. ARM-compatible builds by default.
- Base images: `python:3.12-slim-bookworm`, `node:22-bookworm-slim`

**PEP 668:** Never run bare `pip install`. Always use the project-specific venv (e.g., `/opt/<project>/.venv/bin/pip install`).

**Conflicts:** If the task contradicts what exists in the project, stop and report to Traycer for re-planning.

---

## [ALL AGENTS] Execution Protocol (7-Step Agile Flow)

**Token-optimized workflow: deterministic checks before LLM review.**

| Step | Who | Action | Gate |
|------|-----|--------|------|
| **1** | **Traycer** | Creates plan | Spec exists with spec, edge cases, env vars, DB changes |
| **2** | **Coder AI** | Implements code | Code only what phase requires, follow spec strictly |
| **2.5** | **Coder AI** | Self-review | Reviews own work (MANDATORY) |
| **3** | **Coder AI** | Final Gate | `python scripts/final_gate.py` → all PASS |
| **4** | **Coder AI** | Kilo Review | `python scripts/kilo_code_review.py staged --plan "..."` → report issues |
| **5** | **Coder AI** | Fixes issues | Fix reported issues, re-run review until PASS |
| **6** | **Traycer** | Verifies | Traycer verifier confirms SPEC compliance |
| **7** | **Traycer** | Commits | Pre-commit runs 4 blockers only |

### Step Details

**Step 1 - Traycer Plan:** Ensure plan includes functional spec, edge cases, required env vars, DB changes, docs impact. Do NOT start if spec is vague.

**Step 2 - Coder AI Implements:** Implement only phase scope. Follow spec strictly.

**Step 2.5 - Self-Review (MANDATORY):** Before running final_gate, Coder AI MUST review its own implementation.

**Self-Review Format (Required):**
```
SELF-REVIEW COMPLETE:
✓ All spec requirements implemented: [Yes/No + brief details]
✓ Edge cases handled: [list specific cases or "N/A"]
✓ Env vars documented: [list variables or "N/A"]
✓ DB changes documented: [list changes or "N/A"]
⚠ Potential issues: [list concerns or "None identified"]
```

**Violations:** Proceeding to Step 3 without self-review = FORBIDDEN.

**Step 3 - Final Gate:** Catches deterministic failures BEFORE spending Kilo tokens.
Checks include:
- Auto-fix: trailing whitespace, EOF newline, ruff-format, ruff --fix
- Static: ruff, mypy, bandit, semgrep (best-effort), check yaml, check json, sqlfluff, vulture
- Consistency: structure, conventions, rule size, model names sync, changelog, kilo health

**Step 4 - Kilo Review (March 2026 - Report-Only Default):** Single command with automatic features:
```bash
python /opt/fabrik/scripts/kilo_code_review.py staged --plan "task description" --output json
```

**Automatic features:**
- **Risk Detection**: Scans file paths + diff size → determines risk level
- **Model Selection**: Risk level → cheapest capable model (no manual `--model` needed)
- **Variant Selection**: Risk level → appropriate thinking depth
- **Session Isolation**: Auto-generates `tracked_review_id` from project+branch+date

**Default is report-only** — Coder fixes ALL issues (BLOCKER, MAJOR, MINOR). Repeat until verdict=PASS.

**Step 5 - Coder Fixes:** Fix reported issues, re-run Kilo review until PASS (max 5 iterations).

**Step 6 - Traycer Verification:** Traycer verifier confirms SPEC compliance. If issues found, return to Step 3.

**Step 7 - Traycer Commit:** Runs only 4 blockers: check-added-large-files, check-merge-conflict, detect-private-key, forbid-secrets.

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
- Do NOT skip Step 2.5 self-review
- Do NOT proceed to Step 3 without self-review report
- Do NOT skip final_gate before Kilo review
- Do NOT proceed with BLOCKER/MAJOR issues
- Do NOT skip post-Kilo final_gate
- Do NOT commit without Step 7 passing

**If user catches you skipping review:**
- Acknowledge the violation
- Run the skipped review immediately
- Fix issues before continuing

---

## [TRAYCER ONLY] Traycer Mode Selection

**When planning work with Traycer, choose the appropriate mode based on task complexity:**

| Scenario | Mode | Description |
|----------|------|-------------|
| **Single-PR / Focused task** | **Plan** | Creates a detailed, actionable implementation plan. Best for tasks that fit in one PR. |
| **Complex / Multi-step project** | **Phases** | Manages multiple phases across a project lifecycle to prevent context loss. Each phase is a discrete unit of work. |
| **Feature with specs + tickets** | **Epic** | Driven by Workflows (default: Traycer Agile Workflow). Organizes work into mini-spec artifacts (Specs) and actionable Tickets. Supports **direct agent handoff** — assign individual tickets or batch-select multiple specs/tickets and send directly to a coding agent. Execute via Phases, Smart YOLO (`/execute`), or direct handoff. |
| **Code Audit / Verification** | **Review** | Structured workflow for code review tasks. |

**Epic Mode Execution Options:**
- **Direct Agent Handoff**: Select specs/tickets → Assign to agent with template → Agent implements directly
- **Phases Execution**: Convert tickets to phases → Execute manually or with Regular YOLO
- **Smart YOLO** (`/execute`): Orchestrator evolves Epic based on implementation learnings, dynamically adjusts agents/templates

**Workflow-Driven Modes (Epic):**
- **Traycer Agile Workflow** (default): 8-command, 3-gated-phase workflow for feature development (`/trigger_workflow` → `/epic-brief` → `/core-flows` → `/prd-validation` → `/tech-plan` → `/architecture-validation` → `/ticket-breakdown` → `/implementation-validation`)
- **Traycer Refactoring Workflow**: 4-command workflow for safe refactoring (`/trigger-workflow` → `/plan-refactor` → `/ticket-breakdown` → `/verification`)
- **Custom Workflows**: Create your own command sequences tailored to your methodology

---

## [TRAYCER ONLY] Traycer Mode (When Task is Traycer-Managed)

1. **Context Preservation** — Traycer carries forward file mappings, decisions, and rationale across phases. Rely on the provided spec.
2. **Follow steps exactly in order** — Only execute steps from the managed plan.
3. **Do NOT redesign or change scope** — If changes needed, pause and request plan update from Traycer.
4. **One step at a time** — Complete current step before moving to next.
5. **After each step:** Show Evidence + Gate result.
6. **If a Gate fails** → STOP and report to Traycer for re-planning.

---

## [ALL AGENTS] Documentation Rules

1) **VERIFY before creating:** Check `INDEX.md` (root) and existing folders before creating new files.
2) New markdown files are BLOCKED except: root allowlist (INDEX.md, README.md, CHANGELOG.md, AGENTS.md), scaffold files, plans, archives.
3) Do NOT create new folders under `docs/` except via existing structure.
6) If you add a module under `src/`, ensure documentation coverage exists in the current scaffolded/reference system. Update existing docs or run `docs_updater.py --sync`; do not create ad hoc new reference markdown files unless the anti-sprawl policy explicitly allows it.
7) NEVER edit inside `<!-- AUTO-GENERATED:* -->` blocks.
   - Run `docs_updater.py --sync` instead.
8) All changes MUST keep `make docs-check` passing.

**docs/ root files (scaffold-created only):**
- `README.md`, `QUICKSTART.md`, `CONFIGURATION.md`, `TROUBLESHOOTING.md`, `BUSINESS_MODEL.md`, `FEATURES.md`, `.doc-policy.md`, `development/PLANS.md`, `archive/README.md`

**Configuration pattern (NO DUPLICATION):**
- `.env.example` = AUTHORITATIVE variable reference (self-documenting with inline comments)
- `docs/CONFIGURATION.md` = GUIDE only (how to get credentials, architecture, troubleshooting)
- DO NOT duplicate variable tables in CONFIGURATION.md - reference .env.example instead

**AUTO-GENERATED blocks (DO NOT EDIT MANUALLY):**
- `BUSINESS_MODEL.md` → `<!-- AUTO-GENERATED:PROJECTS:* -->` (project catalog)
- Run `python /opt/fabrik/scripts/sync_projects.py` to update
- Automatically syncs on `fabrik scaffold` completion

### Documentation Anti-Sprawl Policy (STRUCTURAL DEFAULT-DENY - 2026-03-16)

**Policy:** All new .md files BLOCKED except explicit allowlists and structural patterns.

**Enforcement timing:** Step 3 (pre-kilo) and Step 5 (post-kilo) via `final_gate.py`

**ALWAYS ALLOWED:**

1. **Edits to tracked files** - Any .md file already in git (modify existing docs)
2. **Root allowlist (CLOSED):** INDEX.md, README.md, CHANGELOG.md, AGENTS.md
3. **Docs scaffold (CLOSED):** docs/README.md, docs/QUICKSTART.md, docs/CONFIGURATION.md, docs/TROUBLESHOOTING.md, docs/BUSINESS_MODEL.md, docs/FEATURES.md, docs/.doc-policy.md, docs/development/PLANS.md, docs/archive/README.md
4. **Plan documents:** `docs/development/plans/YYYY-MM-DD-plan-<name>.md` (zero-padded dates required) - New dated plan files are allowed as part of the planning workflow
5. **Archive documents:** `docs/archive/**/*.md` (any depth) - Agents may automatically archive completed plans

**BLOCKED:**
- `.droid/review-context/*.md` - Agent artifacts should not be auto-created
- `docs/traycer/*` - Update existing guides only
- `docs/infrastructure/*` - Use TROUBLESHOOTING.md
- `docs/operations/*` - Use DEPLOYMENT.md
- All other new .md files anywhere in repo

**Rationale:** No approval mechanism needed. Plans are the only new docs created manually. Archives support automatic plan lifecycle. All other documentation updates existing scaffolded files.

**Enforcement:** Runs at Step 3 & 5, blocks with specific suggestions.

---

## [ALL AGENTS] ⚠️ MANDATORY WORKFLOW

**PLAN → IMPLEMENT → SELF_REVIEW → FINAL_GATE → KILO_REVIEW → FIX → TRAYCER_VERIFY → COMMIT**

| Step | Who | Action | Gate |
|------|-----|--------|------|
| **1** | **Traycer** | Creates plan | Spec exists with spec, edge cases, env vars, DB changes |
| **2** | **Coder AI** | Implements code | Code only what phase requires, follow spec strictly |
| **2.5** | **Coder AI** | Self-review | Review own code: ✓ spec ✓ edge cases ✓ env vars ✓ DB ⚠ issues |
| **3** | **Coder AI** | Final Gate | `python scripts/final_gate.py` → all PASS |
| **4** | **Coder AI** | Kilo Review | `python scripts/kilo_code_review.py staged --plan "..."` → report issues |
| **5** | **Coder AI** | Fixes issues | Fix reported issues, re-run Kilo review until PASS |
| **6** | **Traycer** | Verifies | Traycer verifier confirms SPEC compliance |
| **7** | **Traycer** | Commits | Pre-commit runs 4 blockers only |

> **Note:** When Traycer is not available, fall back to manual plan creation.

### Kilo Review (March 2026 - Simplified)

```bash
# Stage files, then run review (all routing is automatic)
git add <intended_files>
python /opt/fabrik/scripts/kilo_code_review.py staged --plan "task description" --output json
```

**What happens automatically:**
1. **Risk Detection**: Scans file paths + diff size
   - `auth/`, `security/`, `payment`, secrets → **critical**
   - `src/`, `scripts/`, >400 lines → **high**
   - Normal code → **medium**
   - Docs only → **low**

2. **Model Selection**: Risk → Strategy → Tier → Model
   - low → free → Free tier (minimax, glm-4.7-free)
   - medium → economy → Economy tier (gemini-flash-lite)
   - high → standard → Balanced tier (glm-4.7)
   - critical → premium → Strong tier (glm-5, claude-sonnet)

3. **Variant Selection**: Risk → Thinking depth
   - low → `low` variant (~10s, cheapest)
   - medium/high → `high` variant (~20s, best value)
   - critical → `max` variant (~40s, deepest)

4. **Session Isolation**: Auto-generated `tracked_review_id`
   - Hash of `project_root + git_branch + date`
   - Same project/branch/day = same session = continuity
   - Different project/branch/day = different session = no mixing

**Review Commands:**
- **staged**: Review git staged files (most common)
- **changed**: Review all changed files
- **review <files>**: Review specific files
- **verify <files> --fixes "..."**: Verify manual fixes (cheaper)

**Key points:**
- **Default is report-only** - Coder fixes issues, not Kilo
- **Model selection is automatic** - no manual `--model` needed
- **Session isolation is automatic** - no manual `--tracked-review-id` needed
- Use `--fix` only if you want Kilo to auto-fix (costs more)
- Fix ALL severities (BLOCKER, MAJOR, MINOR)
- Max 5 iterations before escalating or stopping
- **Traycer commits, not Coder** - Coder only implements and fixes

**Sequence (Traycer-managed):**
```
Code → Self-Review → Final Gate → Kilo loop → Traycer verification → Commit
```

**Sequence (Non-Traycer):**
```
Code → Self-Review → Final Gate → Kilo loop until PASS → Commit
```

**Violation:** Committing without Traycer verification (Step 6) or Final Gate PASS.

---

## [ALL AGENTS] Sensitive Data Protection (CRITICAL)

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

## [ALL AGENTS] Security Gates (MANDATORY)

**Final Gate runs at Step 3, then again after fixes if needed:**

```bash
# Step 3 - Before Kilo review (catches deterministic failures, saves tokens)
python /opt/fabrik/scripts/final_gate.py

# After fixing Kilo issues - re-run before re-review
python /opt/fabrik/scripts/final_gate.py
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

## [ALL AGENTS] Build & Test

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

## [CODER AI] Run Locally

```bash
# Most projects use uvicorn
uvicorn src.main:app --reload --port 8000

# Or with watchdog scripts
./scripts/watchdog_api.sh start

# Check health
curl http://localhost:8000/health
```

## [CODER AI] Architecture Overview

Fabrik projects follow a consistent pattern:

- **WSL (dev)** → Local PostgreSQL, local services, `.env` file
- **VPS (prod)** → Coolify-managed Docker Compose, `postgres-main` container
- **Every project ships as one Compose app** — web + worker + optional services

## [CODER AI] SaaS Projects (MANDATORY)

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

## [CODER AI] Project Layout

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

## [ALL AGENTS] Conventions & Patterns

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

## [ALL AGENTS] Security

- **Never commit `.env`** — Use `.env.example` as template
- **All credentials in TWO places:**
  1. Project `.env` (local use)
  2. `/opt/fabrik/.env` (master backup)
- **CSPRNG passwords**: 32 chars, alphanumeric only
- **No hardcoded secrets** — Always use env vars

## [CODER AI] Deployment

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

## [ALL AGENTS] Gotchas

1. **Never use `/tmp/`** — Use project-local `.tmp/` instead (data survives restarts)
2. **Health checks must test dependencies** — Not just return `{"status": "ok"}`
3. **Env vars not set at import time** — Load config in functions, not class-level
4. **Test in Docker before deploying** — `docker compose up` locally first
5. **Never bare `pip install`** — WSL/Debian uses PEP 668. Always use project-specific venv

## [ALL AGENTS] Documentation Rules (MUST)

**Every code change requires documentation update.** No exceptions.

### Document Location Rules (ENFORCED)

**Root-level `.md` files allowed (CLOSED):**
- `INDEX.md`, `README.md`, `CHANGELOG.md`, `AGENTS.md`

**New `.md` files:** See **Documentation Anti-Sprawl Policy** section above for complete enforcement rules.

**docs/ structure (UPDATE existing files, do NOT create new):**

| Directory | Purpose | Policy |
|-----------|---------|--------|
| `docs/` (root) | Scaffold files only | UPDATE existing |
| `docs/traycer/` | Traycer integration | UPDATE existing |
| `docs/development/plans/` | Execution plans | NEW allowed (dated format) |
| `docs/archive/` | Archived docs | NEW allowed (agents archive) |

**Forbidden:**
- Creating `.md` files in `specs/`, `proposals/`, or other non-standard directories
- Creating `.md` files in `src/`, `scripts/`, `tests/`, `config/`
- Creating new `.md` in `.droid/review-context/`

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

## [TRAYCER ONLY] Execution Modes (Fabrik Lifecycle)

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

**Code Review:** See `.windsurf/rules/50-code-review.md` for complete 7-step workflow with Kilo CLI.

## [TRAYCER ONLY] Traycer CLI Agent Auto-Review Integration

**Last Updated:** 2026-03-06
**Status:** Implemented in Free (9), Economy (8), and Balanced (6) tiers = 23 total agents

**Purpose:** Enable Traycer CLI agents to automatically run the complete 7-step review workflow with mandatory self-review.

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

## [TRAYCER ONLY] Traycer Report Panel (Windsurf Extension)

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

## [TRAYCER ONLY] VPS Deployment (Coolify)

**Deployment:** Use Fabrik CLI (`fabrik apply`) for deployment automation to Coolify.

## [TRAYCER ONLY] GitHub Actions Workflows

Location: `.github/workflows/`

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `droid-review.yml` | PR opened/updated | Automated code review with Fabrik checks |
| `update-docs.yml` | Push to main | Auto-update docs when code changes |
| `security-scanner.yml` | Weekly (Monday 9AM) | Vulnerability and secrets scan |
| `daily-maintenance.yml` | Daily (3AM) | Docs and test updates |

**Setup:** Add `FACTORY_API_KEY` to repository secrets.

## [TRAYCER ONLY] Fabrik Skills (Convention Enforcement)

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

## [TRAYCER ONLY] MCP (Model Context Protocol)

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

## [TRAYCER ONLY] Droid Hooks

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

## [CODER AI] Agent Readiness Checklist

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

## [CODER AI] Writing Effective Prompts

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
