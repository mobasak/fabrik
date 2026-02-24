# Fabrik Development Workflow

**Last Updated:** 2026-02-23

The complete 9-step development flow for AI-assisted coding in Fabrik projects.

---

## Overview

Fabrik uses a **deterministic-first, LLM-second** approach:

1. **Deterministic gates** catch 80% of issues (free, instant)
2. **LLM review** catches reasoning/logic issues (paid, slower)
3. **Pre-commit** blocks only absolute security issues

```
PLAN → IMPLEMENT → FINAL_GATE → KILO → FINAL_GATE → VERIFY → SYNC → COMMIT → NEXT
```

Traycer can optionally orchestrate the end-to-end loop in **YOLO Mode**; in Epic Mode, **Smart YOLO** can execute selected specs and tickets end-to-end by dynamically choosing planning/verification strategies per task.

---

## The 9 Steps

### Step 1: Traycer Plan

**Who:** Traycer.ai (Windsurf Extension)

**What:** Creates a focused plan (mini-spec) via the Windsurf IDE extension running in WSL.
This follows Traycer's core planning loop:
1. **Choose Workflow:** Select `Plan` (single-PR), `Phases` (multi-step execution), or `Epic` (specs + tickets).
2. **Describe Goal:** Provide a clear description of the objective and constraints. Optional context can include specific files, folders, images (UI mockups or error screenshots), and Git diffs (uncommitted, against `main`, against a branch, or against a commit).
3. **Review Plan:** Traycer generates a detailed file-level plan with symbol references and implementation steps. Review and iterate until aligned.
4. **Execute:** Hand off the plan to Fabrik's execution environment.

- Submits spec to `/opt/fabrik/factory_submit.py`
- Monitors execution via `/opt/fabrik/factory_wait.py`
- Enforces Functional specification
- Edge cases
- Required environment variables
- Database changes
- Documentation impact

**Output:** Async job submitted to `.factory_jobs/` and executing via `droid exec`.

**Epic note:** In Epic Mode, Traycer organizes work into mini-spec artifacts (Specs) and actionable Tickets. Epic Mode is driven by **Workflows** (default: Traycer Agile Workflow), which are structured command sequences (e.g., `/trigger_workflow` → `/epic-brief` → `/core-flows` → `/prd-validation` → `/tech-plan` → `/architecture-validation` → `/ticket-breakdown` → `/implementation-validation`) that guide the elicitation process.

**How Epic Mode and Fabrik Workflow relate:**
- **Traycer Agile Workflow (8 commands)** runs INSIDE Epic Mode to create tickets (Step 1 of Fabrik workflow)
- **Fabrik 9-Step Workflow (Steps 2-9)** implements EACH ticket created by Epic Mode
- Epic's `/implementation-validation` command runs during Fabrik Step 6 (Traycer Verification)

Traycer asks pointed questions to surface constraints, edge cases, and "invisible rules," then proposes mini-specs and generates tickets. Implementation typically proceeds ticket-by-ticket (or a selected set of tickets), with each ticket following the full Fabrik 9-step flow.

Epic Mode also tracks **Executions** as an audit trail for each agent handoff (what was handed off, plan generated if any, verification comments, commit, and execution status).

**For complete Epic Mode workflow details**, see [Traycer Agile Workflow (Detailed Reference)](../reference/traycer-agile-workflow.md).

**Gate:** Plan must have required sections (enforced by `check_plan_quality.py`):
- `**Status:**` line
- `## Goal`
- `## DONE WHEN` (with checkboxes)
- `## Out of Scope`
- `## Steps`

---

### Step 2: Coder Implements

**Who:** AI Agent (Cascade, Cursor, droid exec)

**What:** Writes code following the plan spec exactly.

**Rules:**
- Only implement what the phase requires
- Follow spec strictly — no scope creep
- Use Gemini 3.1 Pro High Thinking (1x cost)
- Escalate to Sonnet 4.5 Thinking (3x cost) if stuck

**Output:** Code changes ready for review

---

### Step 3: Final Gate (Pre-Kilo)

**Who:** `python scripts/final_gate.py`

**What:** Deterministic checks before spending LLM tokens on review.

**Why:** Catches ~80% of issues for FREE. Saves Kilo review costs.

#### Phase 1: AUTO-FIX FORMATTING

| Check | Command | Function |
|-------|---------|----------|
| trim trailing whitespace | `pre-commit run trailing-whitespace` | Remove trailing spaces |
| fix end of files | `pre-commit run end-of-file-fixer` | Ensure newline at EOF |
| ruff-format | `ruff format` | Format Python code |
| ruff --fix | `ruff --fix` | Auto-fix lint issues |

#### Phase 2: STATIC ANALYSIS

| Check | Command | Function |
|-------|---------|----------|
| ruff | `ruff check` | Python linting |
| mypy | `mypy src/fabrik/` | Type checking |
| bandit | `bandit -r src/` | Security scan |
| semgrep | `semgrep --config auto` | Pattern-based security (best-effort) |
| check yaml | `yaml.safe_load` | YAML syntax validation |
| check json | `json.load` | JSON syntax validation |
| sqlfluff-lint | `sqlfluff lint` | SQL linting |
| vulture | `vulture src/` | Dead code detection |

#### Phase 3: REPO CONSISTENCY

| Check | Script | Function |
|-------|--------|----------|
| Project Structure | `check_structure.py` | MD file placement |
| Fabrik Convention Validator | `validate_conventions.py` | Orchestrates all enforcement checks |
| Rule File Size Guard | `check_rule_size.py` | `.windsurf/rules` < 12KB |
| Sync Droid Model Names | `droid_models.py sync` | Model config sync |
| CHANGELOG.md Updated | `check_changelog.py` | Changelog required for code changes |
| Kilo CLI Health Check | `check_kilo_health.sh` | Verify Kilo CLI works |
| Symlink Integrity | `check_symlinks()` | Verify `.windsurfrules` symlinks |
| Documentation Drift | `docs_updater.py --check` | Broken links, missing stubs |

**Gate:** All checks must PASS before proceeding to Kilo review.

---

### Step 4: Kilo Review Loop

**Who:** `python scripts/kilo_code_review.py`

**What:** AI code review for issues deterministic checks can't catch:
- SPEC compliance (does code match plan?)
- Security reasoning (logic flaws, not pattern matches)
- Edge cases (null handling, race conditions)
- Logic bugs (incorrect algorithms)

**Workflow:**

```bash
# Initial review with task context
python scripts/kilo_code_review.py review <files> \
  --plan .droid/review-context/task.md \
  --review-agent ask \
  --output json

# Subsequent reviews (maintains context)
python scripts/kilo_code_review.py review <files> \
  --session continue \
  --output json
```

**Loop:**
1. Read JSON output — check `verdict` and `issues`
2. Fix ALL issues (BLOCKER, MAJOR, MINOR) — coder fixes, not Kilo
3. Re-review with `--session continue`
4. Repeat until `verdict=PASS` (max 5 iterations)

**Cost:** ~$0.03-0.40 per review (vs ~$1-2 for auto-fix)

---

### Step 5: Final Gate (Post-Kilo)

**Who:** `python scripts/final_gate.py`

**What:** Same checks as Step 3.

**Why:** Ensures Kilo fixes didn't break deterministic rules.

**Gate:** All checks must PASS.

---

### Step 6: Traycer Verification

**Who:** Traycer.ai (Windsurf Extension)

**What:** Traycer's built-in verifier checks the implementation against the original plan and spec to prevent drift.
- Categorizes findings by severity: **Critical, Major, Minor, Outdated**.
- Relies on context preservation so earlier decisions don't have to be re-explained.

In addition, Traycer can perform deep, agentic review to help you triage improvements:
- Categorizes review comments by category: **Bug, Performance, Security, Clarity**.
- Supports fixing comments via:
  - Fix individual comments
  - Fix selected comments
  - Fix all comments

**Fallback:** If Traycer is unavailable, use manual verification checklist:
- [ ] All DONE WHEN criteria met
- [ ] No out-of-scope changes
- [ ] Tests pass
- [ ] Docs updated

**Gate:** Traycer verifier must PASS. If Critical or Major issues are found, return to Step 3.

---

### Step 7: Sync Only

**Who:** `python scripts/final_gate.py --sync`

**What:** Runs ONLY sync side-effects (no quality checks — already done in Step 5):

| Script | Function |
|--------|----------|
| `sync_extensions.sh` | Sync Windsurf extensions to `docs/reference/EXTENSIONS.md` |
| `sync_cascade_backup.sh` | Backup Cascade rules |

**Why:** Separates sync from validation to avoid duplicate checks.

---

### Step 8: Traycer Commit

**Who:** `git commit` + `.pre-commit-config.yaml`

**What:** Pre-commit runs ONLY 4 absolute blockers:

| Hook | Function | Blocks |
|------|----------|--------|
| `check-added-large-files` | No files >500KB | YES |
| `check-merge-conflict` | No conflict markers | YES |
| `detect-private-key` | No private keys | YES |
| `forbid-secrets` | No `.env`, `.pem`, `.key` files | YES |

**Why:** Quality already enforced by Final Gate. Pre-commit only blocks security issues.

---

### Step 9: Next Phase

**Who:** Traycer.ai (Windsurf Extension)

**What:** Advance to the next phase (or next ticket in Epic Mode) with preserved context and repeat from Step 1. In Epic Mode, each handoff produces an **Execution** entry so you can review the audit trail across the epic.

---

## Enforcement Scripts Reference

All enforcement scripts live in `scripts/enforcement/` and are called by `validate_conventions.py`.

### File-Triggered Checks

| Script | Triggered By | Function | Severity |
|--------|--------------|----------|----------|
| `check_env_vars.py` | `.py`, `.ts`, `.js` | Detect hardcoded localhost/127.0.0.1 | ERROR |
| `check_secrets.py` | `.py`, `.ts`, `.js` | Detect hardcoded API keys/tokens | ERROR |
| `check_env_contract.py` | `.env.example`, `compose.yaml`, `CONFIGURATION.md` | Cross-validate env vars | ERROR/WARN |
| `check_health.py` | `.py` with `/health` | Verify health tests deps + test file exists | WARN |
| `check_docker.py` | `Dockerfile`, `compose.yaml` | Alpine base, HEALTHCHECK, port consistency | ERROR/WARN |
| `check_ports.py` | Port definitions | Port registered in PORTS.md | WARN |
| `check_watchdog.py` | `compose.yaml` | Watchdog script exists | WARN |
| `check_structure.py` | `.md` files | MD file placement | ERROR/WARN |
| `check_changelog.py` | Code changes | CHANGELOG entry exists | ERROR |
| `check_docs.py` | `__init__.py` | Module docs exist | WARN |
| `check_tasks_updated.py` | `Phase*.md` | tasks.md freshness | WARN |
| `check_plans.py` | `.md` in `plans/` | Plan naming convention | ERROR/WARN |
| `check_plan_quality.py` | `.md` in `plans/` | Required sections present | ERROR/WARN |
| `check_deps_sync.py` | `requirements.txt` | Sync with pyproject.toml | WARN |

---

## Step Output Format

After each step, report:

```
STEP <N> STATUS: PASS / FAIL
Changed files:
- <path>
Gate output:
<output>
Next: Proceed to Step <N+1> / STOP
```

---

## Violations

**Forbidden actions:**
- Skipping Final Gate before Kilo review (wastes tokens)
- Proceeding with BLOCKER/MAJOR issues
- Skipping post-Kilo Final Gate
- Committing without Step 7 (`--sync`) passing
- Reordering or modifying Traycer plan steps without approval

**If caught:**
1. Acknowledge the violation
2. Run the skipped step immediately
3. Fix issues before continuing

---

## Cost Optimization

| Action | Cost | When to Use |
|--------|------|-------------|
| Final Gate | FREE | Always (Steps 3, 5) |
| Kilo review | ~$0.03-0.40 | After Final Gate passes |
| Kilo auto-fix | ~$1-2 | Never (coder fixes instead) |

**Token savings:** Run Final Gate BEFORE Kilo to catch deterministic issues for free.

---

## Scaffold File Map

### Root Files

| File | Update By | Enforcement |
|------|-----------|-------------|
| `README.md` | AI Coder | None |
| `CHANGELOG.md` | AI Coder | `check_changelog.py` |
| `tasks.md` | Traycer + AI | `check_tasks_updated.py` |
| `AGENTS.md` | Symlink | `check_symlinks()` |
| `.windsurfrules` | Symlink | `check_symlinks()` |
| `compose.yaml` | AI Coder | `check_docker.py`, `check_env_contract.py` |
| `Dockerfile` | AI Coder | `check_docker.py` |
| `.env.example` | AI Coder | `check_env_contract.py` |
| `pyproject.toml` | AI Coder | `check_deps_sync.py` |
| `requirements.txt` | AI Coder | `check_deps_sync.py` |

### Documentation

| Path | Update By | Enforcement |
|------|-----------|-------------|
| `docs/CONFIGURATION.md` | AI Coder | `check_env_contract.py` |
| `docs/QUICKSTART.md` | AI Coder | `check_structure.py` |
| `docs/development/plans/*.md` | Traycer | `check_plans.py`, `check_plan_quality.py` |
| `docs/reference/*.md` | `docs_updater.py --sync` | `check_docs.py` |

### Symlinks (enforced by `check_symlinks()`)

| Symlink | Target |
|---------|--------|
| `.windsurfrules` | `/opt/fabrik/windsurfrules` |
| `.windsurf/rules` | `/opt/fabrik/.windsurf/rules` |
| `AGENTS.md` | `/opt/fabrik/AGENTS.md` |

---

## Quick Reference

```bash
# Step 3/5: Run Final Gate
python scripts/final_gate.py

# Step 4: Kilo review
python scripts/kilo_code_review.py review <files> --output json

# Step 7: Sync only
python scripts/final_gate.py --sync

# Step 8: Commit
git commit -m "feat: description"
```

---

## See Also

- [AGENTS.md](../../AGENTS.md) — Agent instructions
- [Kilo Reference](../reference/kilo-complete-reference.md) — Kilo CLI details
- [Fabrik Scaffold Specs](../reference/fabrik-scaffold-specs.md) — Scaffold structure
