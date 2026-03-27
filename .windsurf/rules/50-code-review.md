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

**PLAN → IMPLEMENT (per ticket) → SELF_REVIEW → [END OF PHASE: GATES] → VERIFY → COMMIT**

---

## Per-Ticket Steps (Cascade)

### Implement
Code changes for current ticket only.

### Self-Review (MANDATORY)
- [ ] No hardcoded localhost/secrets?
- [ ] Imports correct?
- [ ] Env vars use `os.getenv()`?
- [ ] DB changes in `db/schema.sql`?

---

## End-of-Phase Gates (User/Traycer decides when)

Gates run at **end of phase**, not every ticket:

```bash
# Kilo Review
git add -A && python scripts/kilo_code_review.py staged --plan "..."

# Documentator
python scripts/kilo_docs_enforcer.py --auto-generate

# Final Gate
python scripts/final_gate.py
```

**Cascade fixes all findings itself** — no separate FIXER role.

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
