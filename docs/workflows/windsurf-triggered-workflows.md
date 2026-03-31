# Windsurf Cascade Triggered Workflows

**Last Updated:** 2026-03-31

This document describes all workflows available in Windsurf Cascade via the `/` slash command.

---

## Table of Contents

1. [How to Use Workflows](#how-to-use-workflows)
2. [Process Workflows](#process-workflows)
   - [/bug-fix](#bug-fix)
   - [/deploy](#deploy)
   - [/new-feature](#new-feature)
   - [/review](#review)
3. [Cloud Agent Workflows](#cloud-agent-workflows)
   - [/kilo](#kilo)
4. [Local LLM Workflows](#local-llm-workflows)
   - [/local-coder](#local-coder)
   - [/local-review](#local-review)
   - [/local-fixer](#local-fixer)
   - [/local-docs](#local-docs)
   - [/kilo-review](#kilo-review)
5. [Workflow Comparison](#workflow-comparison)

---

## How to Use Workflows

**Triggering workflows in Windsurf Cascade:**

1. Open Cascade chat window
2. Type `/` (slash key)
3. Select workflow from dropdown menu
4. Cascade executes the workflow automatically

**Note:** After adding new workflows, restart Windsurf to refresh the workflow list.

---

## Process Workflows

These workflows provide structured processes for common development tasks.

### `/bug-fix`

**Description:** Fix a reported bug with test-first approach

**Purpose:** Systematic bug fixing that prevents regressions through test-first methodology

**Workflow Steps:**

1. **Reproduce the bug**
   - Document exact reproduction steps
   - Define expected vs actual behavior
   - Capture input that triggers the bug

2. **Add failing test**
   ```bash
   pytest tests/test_<module>.py::<test_name> -v
   # Should FAIL (proves bug exists)
   ```

3. **Implement fix**
   - Make minimal change to fix root cause
   - Prefer upstream fixes over downstream workarounds
   - Address root cause, not symptoms

4. **Verify test passes** (turbo)
   ```bash
   pytest tests/test_<module>.py::<test_name> -v
   # Should PASS
   ```

5. **Run regression suite** (turbo)
   ```bash
   pytest tests/ -v --tb=short
   ```

6. **Update CHANGELOG.md**
   ```markdown
   ### Fixed - <Brief description> (YYYY-MM-DD)
   - Fixed: <what was broken>
   - Root cause: <why it was broken>
   ```

**Key Philosophy:** Test-first proves bug exists, then proves fix works.

---

### `/deploy`

**Description:** Deploy application to VPS via Coolify

**Purpose:** Production deployment with automated Coolify integration

**Prerequisites:**
- ✅ All tests passing locally
- ✅ CHANGELOG.md updated with release notes
- ✅ Clean working tree (`git status` clean)
- ✅ Feature branch merged to `main` (or ready to push)

**Workflow Steps:**

1. **Pre-flight checks** (turbo)
   ```bash
   pytest tests/ -x --tb=short
   ruff check .
   mypy .
   ```

2. **Docker build verification**
   ```bash
   docker compose build
   docker compose up -d --wait
   curl -f http://localhost:8000/health
   docker compose down
   ```

3. **Push to production**
   ```bash
   git push origin main
   ```
   Coolify watches `main` branch and auto-deploys on push.

4. **Verify health on VPS** (turbo)
   ```bash
   curl -f https://$PROJECT.vps1.ocoron.com/health
   ```

**Verification:**
- [ ] Pre-flight gates passed (tests, lint, types)
- [ ] Local Docker build succeeded
- [ ] Health endpoint responds 200 on VPS
- [ ] No error logs in Coolify dashboard

**Key Feature:** Zero-downtime deployment via Coolify auto-deploy on `main` push.

---

### `/new-feature`

**Description:** Start a new feature following Fabrik conventions

**Purpose:** Structured feature development with planning and tracking

**Prerequisites:**
- Traycer plan exists in `docs/development/plans/`
- Plan indexed in `docs/development/PLANS.md`
- Plan status: `NOT_STARTED` or `IN_PROGRESS`

**Workflow Steps:**

1. **Create feature branch**
   ```bash
   git checkout -b feature/<name>
   ```

2. **Create/update plan document**
   - Location: `docs/development/plans/`
   - Filename: `YYYY-MM-DD-plan-<name>.md`
   - Required sections: Goal, DONE WHEN, Out of Scope, Steps

3. **Implement feature**
   - Complete one step at a time per plan
   - Update plan checkboxes as you progress
   - Run review after each significant change

4. **Run pre-commit**
   ```bash
   pre-commit run --all-files
   ```

5. **Run tests** (turbo)
   ```bash
   pytest tests/ -x --tb=short
   ```

6. **Create PR**
   - Reference plan document in PR description
   - Ensure all plan checkboxes checked

**Verification:**
- [ ] Plan document exists in `docs/development/plans/`
- [ ] Plan indexed in `docs/development/PLANS.md`
- [ ] All tests pass
- [ ] Pre-commit hooks pass
- [ ] CHANGELOG.md updated with feature description

**Key Requirement:** Every feature must have a plan document before implementation.

---

### `/review`

**Description:** Review code changes for bugs, security issues, and improvements

**Purpose:** Senior engineer-level code review focusing on bug detection

**Traycer-First Rule:**
- For Traycer-managed tasks: This is supplementary (run after/within Traycer verification)
- When Traycer not available: This serves as primary review step

**Review Focus Areas:**

1. **Spec Compliance** - Behavior matches plan/spec requirements
2. **Security** - Injection risks, auth/authz flaws, sensitive data exposure
3. **Config & Secrets** - Env var hygiene, no hardcoded values
4. **Edge Cases** - Null/empty handling, error paths, concurrency
5. **Fabrik Conventions** (project-specific):
   - Container images: `-slim-bookworm` only (never Alpine)
   - Health checks: Must test actual dependencies (not just return `{"status": "ok"}`)
   - Config loading: Function-level only (never class-level `os.getenv()`)
   - Temporary files: Project-local `.tmp/` (never `/tmp/`)
   - Secrets: CSPRNG with 32+ chars (never hardcoded weak secrets)
   - Bug classes: Dead code, broken control flow, async/await mistakes, off-by-one errors, resource leaks
6. **Docs** - README/config/migration notes updated when behavior changes

**Review Guidelines:**

- ✅ Use parallel tool calls for efficiency (don't over-explore)
- ✅ Report pre-existing bugs too (maintain general code quality)
- ❌ NO speculative or low-confidence issues
- ✅ Base all conclusions on complete codebase understanding
- ⚠️  If given specific git commit, it may not be checked out (local state differs)

**Key Feature:** Deep architectural review by Cascade AI, not just surface-level linting.

---

## Cloud Agent Workflows

These workflows dispatch tasks to cloud-based Kilo CLI agents (paid).

### `/kilo`

**Description:** Delegate a task to a Kilo CLI agent (any Cascade can use this)

**Purpose:** Run cloud-based AI agents for tasks requiring specific models or capabilities

**When to Use:**
- "run kilo agent X on task Y"
- "use coding-2-gpt54 to implement Z"
- "dispatch this to code&fix-1-opus46"

**Available Agents:**

List all agents with costs and performance:
```bash
python /opt/fabrik/scripts/kilo_dispatch.py --list
```

**How to Dispatch:**

**Step 1:** Identify agent and task
- Agent name (exact script name or prefix)
- Task description (what Kilo should do)

**Step 2:** Run dispatch
```bash
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "<agent-name>" \
    --task "<task description>" \
    --project "<project-directory>" \
    --template <code|fix|plan|verify>
```

**Template Selection:**
- `code` (default) — Coding task, uses Coder-for-Plan-Mode template
- `plan` — Phased/epic task, uses Coder-for-Phased-Epic-Modes template
- `fix` — Fix review findings, uses Fix-After-Review template
- `verify` — Fix verification issues, uses Fix-After-Verification template

**Step 3:** Monitor TUI
- Kilo agent runs in terminal TUI
- Both you and user can watch progress

**Step 4:** Read report
```bash
cat <project-directory>/.droid/traycer-reports/latest.md
```

**Step 5:** Report to user
- **STATUS** — COMPLETE / PARTIAL / FAILED
- **FILES** — what was changed
- **CHECKS** — gate results (SELF_REVIEW, KILO, FG)
- **VERIFY** — verification commands to run

**Dry-Run (Preview Prompt):**
```bash
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "<agent-name>" \
    --task "<task>" \
    --dry-run
```

**Examples:**
```bash
# Best cloud agent for coding
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "code&fix-1-opus46" \
    --task "Add Stripe subscription integration" \
    --project /opt/my-saas

# Cheaper agent for simple fix
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "fixing-2-gemini31pro" \
    --task "Fix TypeScript errors in app/api/route.ts" \
    --template fix \
    --project /opt/my-saas

# Plan-based task from spec file
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "coding-3-gemini31pro" \
    --task-file specs/my-saas/02-spec.md \
    --template plan \
    --project /opt/my-saas
```

**Cost:** 💵 **PAID** — Cloud API charges apply (varies by model)

**Key Difference:** Access to powerful cloud models (GPT-5.4, Claude Opus 4.6, etc.) vs free local models.

---

## Local LLM Workflows

These workflows use hardware-safe local LLMs running on your machine (FREE).

### `/local-coder`

**Description:** Local_Coder_qwen32b - Implement features with local LLM

**Script:** `/opt/fabrik/scripts/Local_Coder_qwen32b.sh`

**Purpose:** Feature implementation using local 32B model

**When to Use:**
- Implement new features
- Write new code or create files
- Generate boilerplate or scaffolding
- Add functionality to existing code

**Hardware:**
- Model: qwen2.5-coder:32b (32B parameters)
- Hardware: hybrid-cpu (Ryzen AI 9 + RAM)
- Speed: ~15-25 tok/s

**Usage:**
```bash
# Direct invocation (turbo)
/opt/fabrik/scripts/Local_Coder_qwen32b.sh "implement user authentication with JWT"

# With stdin (Cascade context)
echo "Create a health check endpoint for FastAPI" | /opt/fabrik/scripts/Local_Coder_qwen32b.sh

# Complex task
/opt/fabrik/scripts/Local_Coder_qwen32b.sh "implement real-time WebSocket notifications with Redis pub/sub"
```

**Features:**
- ✅ Hardware Protection: Global Sequential Guard prevents GPU/RAM overload
- ✅ Reuses Traycer Agent: Calls `coding-1-fabrik-coder-qwen32b-local` CLI agent
- ✅ Stdin Support: Can pipe context from Cascade
- ✅ Zero Cost: No API charges

**When NOT to Use:**
- Simple documentation updates → use `/local-docs`
- Bug fixes → use `/local-fixer`
- Code review → use `/local-review` or `/kilo-review`

**Cost:** 🆓 **FREE** (local model)

---

### `/local-review`

**Description:** Local_Review_llama70b - Deep code review with local LLM

**Script:** `/opt/fabrik/scripts/Local_Review_llama70b.sh`

**Purpose:** Interactive architectural review and security analysis

**When to Use:**
- Deep architectural review
- Security analysis
- Bug identification in existing code
- Code quality assessment
- Identify potential issues before commit

**Hardware:**
- Model: llama3.1:70b (70B parameters)
- Hardware: CPU-only (low-context 32K to avoid RAM pressure)
- Speed: ~8-12 tok/s

**Usage:**
```bash
# Review specific implementation (turbo)
/opt/fabrik/scripts/Local_Review_llama70b.sh "review the authentication implementation in src/api/auth.py"

# With stdin (Cascade context)
echo "Check for SQL injection vulnerabilities in the database layer" | /opt/fabrik/scripts/Local_Review_llama70b.sh

# Architectural review
/opt/fabrik/scripts/Local_Review_llama70b.sh "review the microservice architecture in this project"
```

**Features:**
- ✅ Deep Analysis: 70B model provides thorough architectural review
- ✅ Hardware Protection: Global Sequential Guard prevents concurrent loading
- ✅ Temperature 0: Absolute logic, deterministic reviews
- ✅ Zero Cost: No API charges

**When NOT to Use:**
- Automated review loop → use `/kilo-review`
- Quick bug fixes → use `/local-fixer`
- Documentation → use `/local-docs`

**Note:** This is **interactive review only**. For automated review → fix → re-review workflow, use `/kilo-review`.

**Cost:** 🆓 **FREE** (local model)

---

### `/local-fixer`

**Description:** Local_Fixer_ds16b - Fast bug fixes with local LLM

**Script:** `/opt/fabrik/scripts/Local_Fixer_ds16b.sh`

**Purpose:** Quick bug fixing and debugging using specialized DeepSeek model

**When to Use:**
- Fix specific bugs or errors
- Debug issues quickly
- Apply surgical code fixes
- Resolve test failures
- Fix linting or type errors

**Hardware:**
- Model: deepseek-coder-v2:16b (16B parameters)
- Hardware: hybrid-gpu (GPU + RAM spillover)
- Speed: ~40-60 tok/s

**Usage:**
```bash
# Fix specific error (turbo)
/opt/fabrik/scripts/Local_Fixer_ds16b.sh "fix the null pointer exception in src/api/auth.py:45"

# Debug API issue
/opt/fabrik/scripts/Local_Fixer_ds16b.sh "debug why API returns 500 on POST /users"

# Fix test failure
/opt/fabrik/scripts/Local_Fixer_ds16b.sh "fix the failing test in tests/test_auth.py"

# With stdin (Cascade context)
echo "Resolve the import error in src/utils/helpers.py" | /opt/fabrik/scripts/Local_Fixer_ds16b.sh
```

**Features:**
- ✅ Fast Execution: 16B model on GPU provides quick fixes
- ✅ Surgical Precision: DeepSeek specialized in logical reasoning
- ✅ Hardware Protection: Global Sequential Guard prevents concurrent loading
- ✅ Minimal Edits: Follows existing code style, no refactoring
- ✅ Zero Cost: No API charges

**When NOT to Use:**
- Automated fix loop → use `/kilo-review auto-fix`
- New features → use `/local-coder`
- Documentation → use `/local-docs`
- Architectural review → use `/local-review`

**Cost:** 🆓 **FREE** (local model)

---

### `/local-docs`

**Description:** Local_Documentator_llama3.1-8b - Instant documentation with local LLM

**Script:** `/opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh`

**Purpose:** Fast documentation generation using GPU-optimized 8B model

**When to Use:**
- Generate or update README files
- Create CHANGELOG entries
- Write documentation
- Generate code comments
- Update API documentation

**Hardware:**
- Model: llama3.1:8b (8B parameters)
- Hardware: GPU only (fits entirely in 8GB VRAM)
- Speed: ~80-100 tok/s (instant)

**Special Feature:** **Fast-Path** - Bypasses hardware lock when 5.5GB VRAM free + GPU idle

**Usage:**
```bash
# Generate CHANGELOG (turbo)
/opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh "generate CHANGELOG entry for today's commits"

# Update README
/opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh "add installation instructions to README"

# API documentation
/opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh "document the /api/users endpoints"

# With stdin (Cascade context)
echo "Write docstrings for the auth module" | /opt/fabrik/scripts/Local_Documentator_llama3.1-8b.sh
```

**Features:**
- ✅ Blazing Fast: Runs entirely in GPU VRAM
- ✅ Fast-Path Optimization: Bypasses hardware lock when GPU idle
- ✅ Hardware Protection: Falls back to Global Sequential Guard if needed
- ✅ Zero Cost: No API charges

**When NOT to Use:**
- Code implementation → use `/local-coder`
- Bug fixes → use `/local-fixer`
- Code review → use `/local-review` or `/kilo-review`

**Performance Note:** This is the **fastest** local workflow due to:
1. Small 8B model fits entirely in 8GB VRAM
2. Fast-path bypasses lock when GPU idle
3. Instant responses for documentation tasks

**Cost:** 🆓 **FREE** (local model)

---

### `/kilo-review`

**Description:** Kilo_Review - Automated code review workflow (review → fix → re-review loop)

**Script:** `/opt/fabrik/scripts/Kilo_Review.sh`

**Purpose:** Automated quality gate with iterative review and fix cycles

**When to Use:**
- Automated code review before commit
- Review → fix → re-review workflow
- Quality gate with exit codes
- Review staged or changed files
- Multi-iteration fix loop until clean

**Uses:**
- `Local_Review_llama70b` (70B) for reviews
- `Local_Fixer_ds16b` (16B) for fixes

**Usage:**

**Review staged files:**
```bash
# (turbo)
/opt/fabrik/scripts/Kilo_Review.sh staged
```

**Review working tree changes:**
```bash
# (turbo)
/opt/fabrik/scripts/Kilo_Review.sh changed
```

**Auto-fix loop:**
```bash
/opt/fabrik/scripts/Kilo_Review.sh auto-fix src/ --max-iterations 3
```

**Review specific files:**
```bash
/opt/fabrik/scripts/Kilo_Review.sh review src/api/auth.py tests/test_auth.py
```

**Continue existing session:**
```bash
/opt/fabrik/scripts/Kilo_Review.sh auto-fix src/ --session continue
```

**Features:**
- ✅ Automated Loop: Review → Fix → Re-Review until clean or max iterations
- ✅ Exit Codes:
  - `0` - Review passed (PASS verdict)
  - `1` - Review failed (issues remaining)
  - `2` - Error (script failure)
- ✅ Hardware Protection: Both agents use Global Sequential Guard
- ✅ Session Continuity: Can continue existing review sessions
- ✅ Zero Cost: No API charges

**Important: Stage All Files First**

**RULE:** Before running `Kilo_Review.sh staged`, always stage ALL uncommitted files:

```bash
git add -A
/opt/fabrik/scripts/Kilo_Review.sh staged
```

The script warns if unstaged files exist, but it's better to stage everything first to avoid missing files in the review.

**Review Categories:**

Issues are categorized as:
- **SPEC** - Plan/spec compliance violations
- **SECURITY** - Injection, auth, secrets exposure
- **CONFIG** - Env var misuse, hardcoded values
- **EDGE** - Null handling, error paths, concurrency
- **FABRIK** - Project-specific conventions (see below)
- **DOCS** - Missing/incorrect documentation

**Fabrik-Specific Checks:**

The reviewer enforces these Fabrik conventions:
1. **Container Images:** `-slim-bookworm` only (❌ Alpine)
2. **Health Checks:** Must test dependencies (❌ just `{"status": "ok"}`)
3. **Config Loading:** Function-level only (❌ class-level `os.getenv()`)
4. **Temp Files:** Project-local `.tmp/` (❌ `/tmp/`)
5. **Secrets:** CSPRNG 32+ chars (❌ `"abc123"`)
6. **Bug Classes:** Dead code, control flow, async/await, off-by-one, resource leaks

**Workflow Details:**

1. **Review Phase:** `Local_Review_llama70b` analyzes code
2. **Fix Phase:** If issues found, `Local_Fixer_ds16b` applies fixes
3. **Re-Review Phase:** `Local_Review_llama70b` validates fixes
4. **Loop:** Repeats until clean or max iterations reached
5. **Exit:** Returns appropriate exit code for CI/CD integration

**When NOT to Use:**
- Interactive review only → use `/local-review`
- Quick bug fix → use `/local-fixer`
- Documentation → use `/local-docs`
- New features → use `/local-coder`

**Cost:** 🆓 **FREE** (local models)

---

## Workflow Comparison

### By Type

| Workflow | Type | Cost | Auto-Run | Purpose |
|----------|------|------|----------|---------|
| `/bug-fix` | Process | — | Partial | Test-first bug fixing |
| `/deploy` | Process | — | Partial | VPS deployment via Coolify |
| `/new-feature` | Process | — | Partial | Structured feature dev |
| `/review` | Cascade AI | — | No | Senior engineer review |
| `/kilo` | Cloud Agent | 💵 Paid | Partial | Any cloud Kilo agent |
| `/local-coder` | Local LLM | 🆓 Free | Yes | Implement features locally |
| `/local-review` | Local LLM | 🆓 Free | Yes | Deep review locally |
| `/local-fixer` | Local LLM | 🆓 Free | Yes | Fast bug fixes locally |
| `/local-docs` | Local LLM | 🆓 Free | Yes | Instant docs locally |
| `/kilo-review` | Local LLM | 🆓 Free | Partial | Automated review loop |

### By Use Case

| Use Case | Recommended Workflow | Alternative |
|----------|---------------------|-------------|
| Implement new feature | `/local-coder` or `/kilo` | `/new-feature` (process) |
| Fix a bug | `/local-fixer` | `/bug-fix` (test-first process) |
| Code review | `/kilo-review` (automated) | `/local-review` (interactive) |
| Update docs | `/local-docs` | Manual editing |
| Deploy to VPS | `/deploy` | Manual git push |
| Use specific cloud model | `/kilo` | N/A |

### Local vs Cloud Agents

| Feature | Local LLM Workflows | Cloud Kilo Workflow |
|---------|-------------------|-------------------|
| **Cost** | 🆓 FREE | 💵 PAID (varies by model) |
| **Speed** | 8-100 tok/s (hardware dependent) | Varies (cloud latency) |
| **Offline** | ✅ Works offline | ❌ Requires internet |
| **Models** | 4 fixed (qwen32b, llama70b, ds16b, llama8b) | 60+ cloud models |
| **Hardware Protection** | ✅ Global Sequential Guard | N/A |
| **Use Case** | Routine development tasks | Specific model requirements |

---

## Technical Details

### Hardware Protection (Local LLMs)

All local LLM workflows use **Global Sequential Guard**:

- **Lockfile:** `/opt/.fabrik_agent.lock` (shared across all projects)
- **VRAM Monitoring:** Waits for GPU idle before loading models
- **Sequential Execution:** Concurrent calls wait in queue, never overlap
- **Fast-Path Exception:** Only `Local_Documentator` (when 5.5GB+ VRAM free)

**Result:** Safe to call from Windsurf Cascade + Traycer simultaneously across different projects.

### Workflow File Locations

- **Workflow definitions:** `.windsurf/workflows/*.md`
- **Wrapper scripts:** `/opt/fabrik/scripts/Local_*.sh`, `Kilo_Review.sh`
- **CLI agents:** `~/.traycer/cli-agents/*-local-*.sh`

### Auto-Sync

All workflow files sync to every `/opt` project:
- New projects: Get workflows via `fabrik scaffold`
- Existing projects: Get workflows via pre-commit hook
- Manual sync: `python /opt/fabrik/scripts/sync_enforcement_to_projects.py --force`

---

## See Also

- **[LOCAL_LLM_INFRASTRUCTURE.md](../reference/LOCAL_LLM_INFRASTRUCTURE.md)** — Local LLM setup and hardware specs
- **[KILO_AGENT_MANAGEMENT.md](KILO_AGENT_MANAGEMENT.md)** — Kilo CLI agent management
- **[AGENTS.md](../../AGENTS.md)** — Full orchestrator documentation (Traycer only)

---

**Document Status:** Complete - covers all 10 Windsurf-triggered workflows as of 2026-03-31
