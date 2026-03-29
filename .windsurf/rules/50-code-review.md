---
activation: always_on
description: Code review workflow and quality gate commands for Windsurf Cascade
trigger: always_on
---

# Code Review (Cascade)

**Scope:** Windsurf Cascade agents working on `/opt/*` projects.

---

## Self-Review Gate (Every Task)

### Internal Audit

*Perform before reporting completion. Full checklist in `00-critical.md`.*
- [ ] **Secrets:** No hardcoded keys or tokens?
- [ ] **Infrastructure:** `Dockerfile` is `-slim-bookworm` and has `HEALTHCHECK`?
- [ ] **Architecture:** `compose.yaml` has `platform: linux/arm64`?
- [ ] **Networking:** Port registered in `PORTS.md`?
- [ ] **Database:** Changes added to `db/schema.sql`?

### Lean Gate (Tier 1)

```bash
python scripts/final_gate.py --lean
```

Syntax (ruff), json/yaml validation, secrets, env vars, schema sync. Fast, no context poisoning.

---

## Phase-End Gates (Traycer Instructs or Interactive Work)

These gates run at phase boundaries. When working under Traycer, Traycer decides when to trigger them. During interactive work (no Traycer), Cascade runs them after completing non-trivial changes.

### Kilo Review

```bash
git add -A                          # CRITICAL: stage ALL uncommitted files, not just yours
git diff --staged --name-only       # Verify staged matches intent
python scripts/kilo_code_review.py staged --plan "task description" --output json
```

⚠️ NEVER `git add` only your files — other tools (final_gate, sync_projects, scaffold) may have modified files too. Review ALL changes or risk missing issues.

I fix all findings (BLOCKER, MAJOR, MINOR) myself—no separate FIXER role in Cascade.

### Documentator

```bash
python scripts/kilo_docs_enforcer.py --auto-generate --verbose
git add CHANGELOG.md docs/reference/*.md
python scripts/kilo_docs_enforcer.py --enforce
```

### Full Gate (Tier 2 — Phase Handover)

```bash
python scripts/final_gate.py
```

Full quality: static analysis (ruff, mypy, bandit, semgrep) + consistency checks (changelog, index, readme, test proposal). Diff-aware — skips checks for unchanged files.

### Systemic Gate (Tier 3 — On-Demand Only)

```bash
python scripts/final_gate.py --systemic
```

Repo health: docker, ports, docs sprawl, duplicates, deps sync, health endpoints, watchdog, env contract. Never part of a fix loop.

---

## Key Reminders

- Internal audit + lean gate is **MANDATORY** before reporting completion.
- I fix issues, not Kilo (report-only by default).
- Traycer commits, not Cascade — I only implement and fix.
- Max 5 review iterations before escalating.
- Non-trivial = any of: new file, >50 lines changed, new dependency, DB change.

After 5 iterations: STOP, report blockers to user, do not attempt further fixes.

---

## Output Format

After each gate, report:

```text
GATE: <lean|full|systemic> STATUS: PASS / FAIL
Changed files: <paths>
Gate output: <result>
Next: Proceed / STOP
```

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

1. Quality gate commands organized by tier (lean, full, systemic).
2. Cascade-specific reminders (output format, self-review, iteration limits).
3. Solo-Dev Creed for architectural discipline.

