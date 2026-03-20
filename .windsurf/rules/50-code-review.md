---
activation: always_on
description: Mandatory execution protocol with code review enforcement
trigger: always_on
---

# Execution Protocol (MANDATORY)

## The Flow: PLAN → IMPLEMENT → SELF_REVIEW → FINAL_GATE → KILO_REVIEW → FIX → TRAYCER_VERIFY → COMMIT

**This applies to ALL tasks in /opt/* projects.**

| Step | Who | Action | Gate |
|------|-----|--------|------|
| **1** | **Traycer** | Creates plan | Spec exists with spec, edge cases, env vars, DB changes |
| **2** | **Cascade** | Implements code | Code only what phase requires, follow spec strictly |
| **2.5** | **Cascade** | Self-review | Review own code: ✓ spec ✓ edge cases ✓ env vars ✓ DB ⚠ issues |
| **3** | **Cascade** | Final Gate | `python /opt/fabrik/scripts/final_gate.py` → all PASS |
| **4** | **Cascade** | Kilo Review | `python scripts/kilo_code_review.py staged --plan "..."` → report issues |
| **5** | **Cascade** | Fixes issues | Fix reported issues, re-run Kilo review until PASS |
| **6** | **Traycer** | Verifies | Traycer verifier confirms SPEC compliance |
| **7** | **Traycer** | Commits | Pre-commit runs 4 blockers only |

> **Note:** When Traycer is not available, fall back to manual plan creation.

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

### Kilo Review Workflow (Report-Only Default)

```bash
# Stage files, then run review (session isolation is automatic)
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

**Review Mode Selection:**
- **staged**: Review git staged files (default, most common)
- **changed**: Review all changed files (unstaged too)
- **review <files>**: Review specific files
- **verify <files> --fixes "..."**: Verify manual fixes (cheaper)

**Key points:**
- **Default is report-only** - I fix issues, not Kilo
- **Model selection is automatic** - no manual `--model` needed
- **Session isolation is automatic** - no manual `--tracked-review-id` needed
- Use `--fix` only if you want Kilo to auto-fix (costs more)
- Fix ALL severities (BLOCKER, MAJOR, MINOR)
- Max 5 iterations before escalating or stopping
- **Traycer commits, not Cascade** - I only implement and fix

**Output format after each step:**
```
STEP <N> STATUS: PASS / FAIL
Changed files:
- <path>
Kilo review findings:
<findings or "No issues">
Gate output:
<command result>
Next: Proceed to Step <N+1> / STOP (issues remain)
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
