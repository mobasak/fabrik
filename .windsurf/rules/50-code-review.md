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

Use Traycer's built-in verifier as the review surface. Do NOT run droid exec review.

### Non-Traycer Tasks (Fallback)

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
- Fallback: Run `droid exec -m <model> "Review <files>..."`
- Fix all issues
- Re-review until clean

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
