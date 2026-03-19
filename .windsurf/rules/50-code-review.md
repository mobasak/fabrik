---
activation: always_on
description: Mandatory execution protocol with code review enforcement
trigger: always_on
---

# Execution Protocol (MANDATORY)

## The Flow: PLAN → IMPLEMENT → SELF_REVIEW → FINAL_GATE → CHEAP_REVIEW → VERIFY → COMMIT

**This applies to ALL tasks in /opt/* projects.**

| Step | Action | Gate |
|------|--------|------|
| **1** | **Traycer Plan** | Plan exists with spec, edge cases, env vars, DB changes |
| **2** | **Coder Implements** | Code only what phase requires, follow spec strictly |
| **2.5** | **Self-Review (MANDATORY)** | Review own code: ✓ spec ✓ edge cases ✓ env vars ✓ DB ⚠ issues |
| **3** | **Final Gate** | `python /opt/fabrik/scripts/final_gate.py` → all PASS |
| **4** | **Cheap Review** | Context-aware reviewer (optional, see below) |
| **5** | **Traycer Verify** | Traycer verifier passes |
| **6** | **Commit** | Pre-commit runs 4 blockers only |

> **Note:** When Traycer is not available, fall back to manual plan creation and cheap review.

## Gates Contract (Simplified March 2026)

### Final Gate (Step 3 - Single Pass)
Runs deterministic checks once (no pre/post split):
- AUTO-FIX: trailing whitespace, EOF, ruff-format, ruff --fix
- STATIC: ruff, mypy, bandit, semgrep (best-effort), yaml, json, sqlfluff, vulture
- CONSISTENCY: structure, conventions, rule size, models, changelog, kilo health

Semgrep policy:
- If semgrep is missing → skip (PASS)
- If semgrep is not authenticated → skip (PASS with instruction)

### Pre-commit (Step 6)
Enforces ONLY 4 absolute blockers:
- check-added-large-files
- check-merge-conflict
- detect-private-key
- forbid-secrets

---

## Code Review (After EVERY Code Change)

**Immediately after writing/editing code, I MUST:**

### Traycer-Managed Tasks (Primary)

Use Traycer's built-in verifier as the review surface.

### Non-Traycer Tasks: Cheap Review (Fallback)

**Staged-first workflow with scoped sessions (2026-03-17):**

```bash
# Set stable review ID once per cycle
export REVIEW_ID="feat-$(date +%Y%m%d)-<feature-slug>"

# Stage intended files before initial review
git add <intended_files>

# Initial pass: staged commit candidate
python /opt/fabrik/scripts/kilo_code_review.py staged \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --plan "Brief task description" \
  --review-agent ask \
  --output json

# Intermediate passes: verify command (lighter)
python /opt/fabrik/scripts/kilo_code_review.py verify <changed_files> \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --fixes "What was fixed" \
  --review-agent ask \
  --output json
```

**Session Scoping:**
- Sessions scoped by: `project_root + git_branch + tracked_review_id`
- Prevents cross-repo/branch session pollution
- Issue state: `.droid/reviews/<tracked_review_id>_issues.json`
- Open issues reused across iterations
- Auto-close is conservative: only for staged, single-batch, non-verify, auto-fix runs

**Review Mode Selection:**
- **staged**: Initial pass, final risky-branch check
- **verify** (command): Intermediate fix loops (cheaper, focused - use after manual fixes)
- **review <files>**: Manual WIP review, deliberate partial review only
- **--mode full**: Full file review (default for review command)

**Recommendation:** Stage intended files semantically before calling reviewer.

**See:** `.windsurf/rules/90-automation.md` for complete reviewer selection guide

**Key points:**
- **Stage intended files first** - review commit candidate, not arbitrary file sets
- **Staged for initial pass** - full SPEC verification
- **verify command for intermediate loops** - cheaper, focused on fixes only
- **Pass the task/plan on initial review** - Kilo needs it for SPEC verification
- Use inline plan text (`--plan "description"`) - simpler, no file management
- **Set REVIEW_ID once** - keep same ID across all fix iterations
- **Only open issues matter** - do not assume unseen issues are fixed unless full-scope
- I fix Kilo issues, not Kilo auto-fix (cheaper: review ~$0.03-0.40 vs auto-fix ~$1-2)
- Fix ALL severities, not just BLOCKER/MAJOR
- Max 5 verify iterations before stopping
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

**Violations:**
- Do NOT implement without plan approval
- Do NOT skip Step 2.5 self-review
- Do NOT proceed to Step 3 without self-review report
- Do NOT skip final_gate before Kilo review
- Do NOT proceed with BLOCKER/MAJOR issues
- Do NOT skip post-Kilo final_gate
- Do NOT commit without Step 7 passing

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
