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
| **2.5** | **Self-Review (MANDATORY)** | Review own code, report: ✓ spec compliance ✓ edge cases ✓ env vars ✓ DB changes ⚠ issues |
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

# Final risky-branch check: staged again (only if needed)
python /opt/fabrik/scripts/kilo_code_review.py staged \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --output json
```

**Critical:** `--tracked-review-id` is MANDATORY with `--session continue`. Without it:
```
ValueError: --tracked-review-id is required with --session continue
```

**Session Scoping:**
- Sessions scoped by: `project_root + git_branch + tracked_review_id`
- Prevents cross-repo/branch session pollution
- Issue state: `.droid/reviews/<tracked_review_id>_issues.json`
- Open issues reused across iterations
- Auto-close is conservative: only for staged, single-batch, non-verify, auto-fix runs

**Review Mode Selection:**
- **staged** (recommended): Initial pass, final risky-branch check
- **verify** (command): Intermediate fix loops (cheaper, focused - use after manual fixes)
- **review <files>**: Manual WIP review, deliberate partial review only
- **--mode full**: Full file review (default for review command)

**Phase 1: Kilo AI Review (Strict Enforcement - 2026-03-05)**

**NEW: 6-Layer Enforcement Pipeline:**
1. **Pre-Review Gates** - Runs final_gate.py (deterministic checks), results injected into prompt
2. **Risk Assessment** - Security-sensitive paths or large diffs (>500 lines) trigger multi-pass review
3. **Plan Extraction** - Extracts requirements (REQ-#, numbered, bulleted) from plan
4. **Kilo Review** - Enhanced prompt with gate results, requirements, strict schema warnings
5. **Schema Validation** - Strict JSON schema, NO auto-fill (invalid → BLOCKER)
6. **Evidence + Coverage Validation** - BLOCKER/MAJOR need evidence, all requirements must be covered

**Enforcement Details:**
- **Schema**: Required fields: verdict, summary, issues, plan_coverage (minItems: 1)
- **Evidence**: BLOCKER/MAJOR issues MUST have structured evidence object (file_line, diff, tool_output, missing, multi_file, external)
- **Plan Coverage**: All extracted requirements must be addressed (status: satisfied/missing/partial/n/a)
- **Retry Logic**: 1 retry with JSON skeleton if schema fails, tracks ALL attempt tokens
- **Multi-Pass**: High-risk changes get 2 passes (general + security-focused), results merged
- **Doc/Verify Modes**: Skip plan coverage validation (no plan in prompt)

**Then I MUST:**
1. **Initial staged review** - check `verdict` and `issues` in JSON output
2. Fix ALL open issues myself (BLOCKER, MAJOR, MINOR) - I fix, not Kilo
3. **Verify with verify command** - lighter follow-up check on fixes
4. Repeat verify until `verdict=PASS` (max 5 iterations)
5. **Final staged review** - only if risky/cross-module changes
6. Report to user what was done

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
