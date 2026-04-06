---
activation: always_on
description: Code review workflow and quality gate commands for Windsurf Cascade
trigger: always_on
---

# Code Review (Cascade)

**Scope:** Windsurf Cascade agents working on `/opt/*` projects.

---

## A) Self-Review Gate (Every Task)

### Internal Audit

*Perform before reporting completion. Full checklist in `.windsurfrules`.*
- [ ] **Secrets:** No hardcoded keys or tokens?
- [ ] **Infrastructure:** `Dockerfile` is `-slim-bookworm` and has `HEALTHCHECK`?
- [ ] **Architecture:** `compose.yaml` has `platform: linux/amd64`?
- [ ] **Networking:** Port registered in `PORTS.md`?
- [ ] **Database:** Changes added to `db/schema.sql`?

### Lean Gate (Tier 1)

```bash
python scripts/final_gate.py --lean
```

Syntax (ruff), json/yaml validation, secrets, env vars, schema sync. Fast, no context poisoning.

---

## B) Changelog (Every Code/Config/Infra Change)

For any non-trivial code, config, infrastructure, Docker, or compose change in:
`src/`, `scripts/`, `templates/`, `.factory/`, `.github/`, `Dockerfile`, `compose.yaml`, `.env.example`, `pyproject.toml`, `package.json`, `requirements.txt`,
you MUST ensure `CHANGELOG.md` has a real entry under `## [Unreleased]`:

```markdown
### Added/Changed/Fixed — <Title> (YYYY-MM-DD)
```

---

## C) Milestone Gate (Batch Closure Only)

When closing a milestone or a batch of related tickets, run the full gate once and fix all findings before handoff:

```bash
python scripts/final_gate.py
```

Full quality: static analysis (ruff, mypy, bandit, semgrep) + consistency checks (changelog, index, readme, test proposal). Diff-aware — skips checks for unchanged files.

---

## D) Optional Tools (Manual / On-Demand Only)

These tools are available when explicitly requested by the owner or when you judge a manual extra review is warranted.

### Kilo Review (Optional)

```bash
git add -A                          # CRITICAL: stage ALL uncommitted files, not just yours
git diff --staged --name-only       # Verify staged matches intent
python scripts/kilo_code_review.py staged --plan "task description" --output json
```

Use for rare high-risk or cross-cutting changes. Never rely on it as the default completion gate.

I fix all findings (BLOCKER, MAJOR, MINOR) myself—no separate FIXER role in Cascade.

### Documentator (Optional)

```bash
python scripts/kilo_docs_enforcer.py --auto-generate --verbose
```

Use for bulk documentation work (CHANGELOG/README/doc refresh), not for every code change.

### Systemic Gate (Tier 3 — On-Demand Only)

```bash
python scripts/final_gate.py --systemic
```

Repo health: docker, ports, docs sprawl, duplicates, deps sync, health endpoints, watchdog, env contract. Never part of a normal fix loop.

---

## Key Reminders

- Internal audit + lean gate is **MANDATORY** before reporting completion.
- **Changelog is MANDATORY for any code/config/infrastructure change. Full gate runs at milestone/batch closure, not for every task.**
- I fix issues, not Kilo (report-only by default).
- Traycer commits, not Cascade — I only implement and fix.
- Max 5 review iterations before escalating.
- Non-trivial = any of: new file, >50 lines changed, new dependency, DB change, or any code/config/infrastructure/Docker/compose change.

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

