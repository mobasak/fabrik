---
activation: always_on
description: Mandatory execution protocol with code review enforcement
trigger: always_on
---

# Execution Protocol (MANDATORY)

## The Flow: PLAN → APPROVE → IMPLEMENT → REVIEW → FIX → VALIDATE → NEXT

**This applies to ALL tasks in /opt/* projects.**

| Phase | Action | Gate |
|-------|--------|------|
| **1. PLAN** | Traycer-managed plan exists | Plan exists in Traycer AND saved to `docs/development/plans/` |
| **2. APPROVE** | Wait for explicit "go" from human | Human says "go" |
| **3. IMPLEMENT** | Execute one step at a time (from Traycer plan only) | Step code complete |
| **4. REVIEW** | Run Traycer verification/review for completed step | Traycer verifier findings received |
| **5. FIX** | Address Traycer findings before proceeding | All findings resolved |
| **6. VALIDATE** | Traycer verifier passes + repo gate commands | Traycer pass + gate evidence |
| **7. NEXT** | Only proceed after Traycer + gates pass | Approval for next step |

> **Note:** When Traycer is not available, fall back to manual plan creation and AI code review.

---

## Code Review (After EVERY Code Change)

**Immediately after writing/editing code, I MUST:**

### Traycer-Managed Tasks (Primary)

Use Traycer's built-in verifier as the review surface.

### Non-Traycer Tasks: Kilo Code Review (Fallback)

**Two-phase workflow (pre-commit + AI review):**

```bash
# Single command runs both phases:
python scripts/kilo_code_review.py review <changed_files> --output json
```

**Phase 1: Pre-commit (automatic, FREE)**
- Runs `pre-commit run --files` on changed files
- Auto-fixes: ruff, formatting, whitespace
- Retries up to 5 times until clean
- If fails after max iterations → aborts (saves Kilo tokens)

**Phase 2: Kilo AI Review (only if Phase 1 passes)**
- Reviews for: SPEC, SECURITY, CONFIG, EDGE, DOCS
- Returns JSON with `verdict` and `issues`

**Then I MUST:**
1. Read JSON output - check `verdict` and `issues`
2. Fix ALL issues myself (BLOCKER, MAJOR, MINOR) - I fix, not Kilo
3. Get another review (same session for context continuity)
4. Repeat 2-3 until `verdict=PASS` (max 5 iterations)
5. Report to user what was done

**Key points:**
- Pre-commit runs first (catches ~80% of MINOR issues for FREE)
- I fix Kilo issues, not Kilo auto-fix (cheaper)
- Use `--skip-precommit` only if pre-commit already passed

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
- Fallback: Run `python scripts/kilo_code_review.py review <files> --output json`
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
