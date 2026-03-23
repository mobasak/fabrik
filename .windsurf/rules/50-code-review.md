---
activation: always_on
description: Code review workflow pointer for Windsurf Cascade
trigger: always_on
---

# Code Review (Cascade)

**Scope:** Windsurf Cascade agents working on `/opt/*` projects.

---

## Workflow Authority

**The canonical workflow is defined in `AGENTS.md` section `[ALL AGENTS] Mandatory Workflow`.**

Both Cascade and Kilo CLI agents follow the same 8-step workflow:

**PLAN → IMPLEMENT → SELF_REVIEW → KILO_REVIEW → DOCUMENTATOR → FINAL_GATE → VERIFY → COMMIT**

**Do NOT duplicate workflow details here.** Read `AGENTS.md` for:
- Step-by-step execution protocol
- Gate requirements
- Violation rules

---

## Cascade-Specific: Quick Reference

### After Writing Code

```bash
# Step 3: Kilo Review (report-only)
git diff <intended_files>           # Review changes
git add <intended_files>            # Stage
git diff --staged                   # Verify staged matches intent
python scripts/kilo_code_review.py staged --plan "task description" --output json
# Fix any Kilo findings

# Step 4: Documentator
python scripts/kilo_docs_enforcer.py --auto-generate --verbose
git add CHANGELOG.md docs/reference/*.md
python scripts/kilo_docs_enforcer.py --enforce

# Step 5: Final Gate
python scripts/final_gate.py
```

### Key Reminders

- **Step 2.5 self-review is MANDATORY** before Kilo Review
- **I fix issues, not Kilo** (report-only by default)
- **Traycer commits, not Cascade** — I only implement and fix
- **Max 5 review iterations** before escalating

**Non-trivial = any of:** new file, >50 lines changed, new dependency, DB change.

**After 5 iterations:** STOP, report blockers to user, do not attempt further fixes.

### Output Format

After each step, report:
```
STEP <N> STATUS: PASS / FAIL
Changed files: <paths>
Gate output: <result>
Next: Proceed to Step <N+1> / STOP
```

---

## Why This File Exists

This file exists because Cascade auto-discovers `.windsurf/rules/`. It provides:
1. Quick command reference (no need to open AGENTS.md for commands)
2. Cascade-specific reminders (output format, self-review)

**The workflow itself lives in `AGENTS.md`** — single source of truth for both Cascade and Kilo CLI.
