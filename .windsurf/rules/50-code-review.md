---
activation: always_on
description: Mandatory execution protocol with code review enforcement
trigger: always_on
---

# Execution Protocol (MANDATORY)

## The Flow: PLAN → APPROVE → IMPLEMENT → REVIEW → FIX → VALIDATE → NEXT

**This applies to ALL tasks in /opt/* projects.**

| Step | Action | Gate |
|------|--------|------|
| **1** | **Traycer Plan** | Plan exists with spec, edge cases, env vars, DB changes |
| **2** | **Coder Implements** | Code only what phase requires, follow spec strictly |
| **3** | **Final Gate (Pre-Kilo)** | `python /opt/fabrik/scripts/final_gate.py` → all PASS |
| **4** | **Kilo Review Loop** | Fix ALL issues until verdict=PASS (diff-scoped) |
| **5** | **Final Gate (Post-Kilo)** | `python /opt/fabrik/scripts/final_gate.py` → all PASS |
| **6** | **Traycer Verification** | Traycer verifier passes |
| **7** | **Sync Only** | `python /opt/fabrik/scripts/final_gate.py --sync` → sync extensions/backup |
| **8** | **Traycer Commit** | Pre-commit runs 4 blockers only |
| **9** | **Next Phase** | Move to next Traycer phase |

> **Note:** When Traycer is not available, fall back to manual plan creation and AI code review.

## Gates Contract (Current Workflow)

### Final Gate (Steps 3 + 5)
Runs deterministic checks and must PASS:
- AUTO-FIX: trailing whitespace, EOF, ruff-format, ruff --fix
- STATIC: ruff, mypy, bandit, semgrep (best-effort), yaml, json, sqlfluff, vulture
- CONSISTENCY: structure, conventions, rule size, models, changelog, kilo health

Semgrep policy:
- If semgrep is missing → skip (PASS)
- If semgrep is not authenticated (HTTP 401 / requires login) → skip (PASS with instruction)
- Otherwise semgrep failures are enforced

### Sync Only (Step 7)
`python /opt/fabrik/scripts/final_gate.py --sync` runs ONLY sync side-effects (extensions + backup). No quality checks.

### Pre-commit (Step 8)
Pre-commit enforces ONLY 4 absolute blockers:
- check-added-large-files
- check-merge-conflict
- detect-private-key
- forbid-secrets

---

## Code Review (After EVERY Code Change)

**Immediately after writing/editing code, I MUST:**

### Traycer-Managed Tasks (Primary)

Use Traycer's built-in verifier as the review surface.

### Non-Traycer Tasks: Kilo Code Review (Fallback)

**Two-phase workflow (Kilo review + Final Gate):**

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

**Phase 1: Kilo AI Review**
- Reviews for: SPEC, SECURITY, CONFIG, EDGE, DOCS
- Returns JSON with `verdict` and `issues`

**Then I MUST:**
1. Read JSON output - check `verdict` and `issues`
2. Fix ALL issues myself (BLOCKER, MAJOR, MINOR) - I fix, not Kilo
3. Get another review with `--session continue`
4. Repeat 2-3 until `verdict=PASS` (max 5 iterations)
5. Report to user what was done

**Phase 2: Final Gate (MANDATORY before commit)**

```bash
# Step 3 - Before Kilo review (catches deterministic failures, saves tokens)
python /opt/fabrik/scripts/final_gate.py

# Step 5 - After Kilo review (ensures Kilo fixes didn't break rules)
python /opt/fabrik/scripts/final_gate.py

# Step 7 - Sync only (no duplicate checks)
python /opt/fabrik/scripts/final_gate.py --sync
```

This runs quality and consistency checks at Steps 3/5, then sync-only at Step 7.

Final Gate coverage (Steps 3 and 5):
- Auto-fix formatting: trailing whitespace, EOF newline, ruff-format, ruff --fix
- Static analysis: ruff, mypy, bandit, semgrep, check yaml, check json, sqlfluff, vulture
- Repo consistency: structure, conventions, rule size, model names sync, changelog, kilo health

Sync-only coverage (Step 7 / --sync):
- Sync Windsurf Extensions
- Sync Cascade Backup

**Key points:**
- **Pass the task/plan on initial review** - Kilo needs it for SPEC verification
- Save task to `.droid/review-context/task.md` (not in `docs/development/plans/`)
- I fix Kilo issues, not Kilo auto-fix (cheaper: review ~$0.03-0.40 vs auto-fix ~$1-2)
- Fix ALL severities, not just BLOCKER/MAJOR
- Use `--session continue` for subsequent reviews (maintains context)
- Max 5 iterations before stopping
- If still failing after 5 iterations, escalate model or request plan clarification

**Output format after each step:**
```
STEP <N> STATUS: PASS / FAIL
Changed files:
- <path>
Traycer verifier findings:
<findings or "No issues">
Gate output:
<command result>
Next: Proceed to Step <N+1> / STOP (issues remain)
```

---

## Plan Template (For Every Non-Trivial Task)

Every plan MUST include review checkpoints:

```markdown
## Step N: <description>

**DO:** <what to implement>

**REVIEW:**
- Traycer-managed: Run Traycer verification for this step
- Fallback: Run `python /opt/fabrik/scripts/kilo_code_review.py review <files> --output json`
- Fix all issues myself (I fix, not Kilo)
- Re-review until verdict=PASS

**GATE:** <validation command>

**EVIDENCE:** <expected output>
```

---

## Violations

**I am FORBIDDEN from:**
- Skipping REVIEW phase (Traycer verification or fallback review)
- Proceeding to next step with unfixed errors
- Marking task complete without final review
- Assuming approval — must wait for explicit "go"
- Reordering, expanding, or modifying Traycer plan steps without requesting a plan update from Traycer

**If user catches me skipping review:**
- I must acknowledge the violation
- Run the skipped review immediately
- Fix issues before continuing

---

## Scope

This protocol applies to:
- All projects under `/opt/`
- All Cascade agents working in this workspace
- All file modifications (edit, multi_edit, write_to_file, Create)

Symlinked via `.windsurfrules` to all project roots.
