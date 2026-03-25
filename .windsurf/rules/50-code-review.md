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

### Step 2.5: Internal Audit (MANDATORY)
*Perform this check before running any automated tools*.
- [ ] **Secrets:** No hardcoded keys or tokens?
- [ ] **Infrastructure:** `Dockerfile` is `-slim-bookworm` and has `HEALTHCHECK`?
- [ ] **Architecture:** `compose.yaml` has `platform: linux/arm64`?
- [ ] **Networking:** Port registered in `PORTS.md`?
- [ ] **Database:** Changes added to `db/schema.sql`?

### Step 3: Kilo Review (Report-Only)
```bash
git add -A                          # CRITICAL: stage ALL uncommitted files, not just yours
git diff --staged --name-only       # Verify staged matches intent
python scripts/kilo_code_review.py staged --plan "task description" --output json
```
**⚠️ NEVER `git add` only your files** — other tools (final_gate, sync_projects, scaffold) may have modified files too. Review ALL changes or risk missing issues.
*I fix all findings (BLOCKER, MAJOR, MINOR) myself—no separate FIXER role in Cascade*.

### Step 4: Documentator
```bash
python scripts/kilo_docs_enforcer.py --auto-generate --verbose
git add CHANGELOG.md docs/reference/*.md
python scripts/kilo_docs_enforcer.py --enforce
```

### Step 5: Final Gate (Preflight)
```bash
python scripts/final_gate.py
```
*This executes the enforcement suite:*
1. `check_docker.py` (ARM64 & No-Alpine)
2. `check_secrets.py` (Zero-Hardcoding)
3. `check_env_contract.py` (.env sync)
4. 24 additional checks

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

---

## Solo-Dev Creed (Global Constraints)

These constraints prevent "agent drift" and bikeshedding:

- **No Speculation:** If information is missing, state assumptions explicitly or stop and ask. Do not guess.
- **One-Test Rule Enforcement:** Every non-trivial change must have a corresponding test justification in the plan.
- **Real-World Breakage Review:** For IO/FS/Exec changes, define:
  - **Trigger:** What action causes the failure?
  - **Symptom:** What does the user see (or what does the log show)?
  - **Root Cause:** The technical "why"
  - **Detection:** How do we catch this in `final_gate.py`?
- **No stylistic bikeshedding:** Prefer correctness and safety over "clean code" aesthetics.
- **Minimalist Refactors:** No unsolicited refactors unless part of the approved plan.

---

## Why This File Exists

This file exists because Cascade auto-discovers `.windsurf/rules/`. It provides:
1. Quick command reference (no need to open AGENTS.md for commands)
2. Cascade-specific reminders (output format, self-review)
3. Solo-Dev Creed for architectural discipline

**The workflow itself lives in `AGENTS.md`** — single source of truth for both Cascade and Kilo CLI.
