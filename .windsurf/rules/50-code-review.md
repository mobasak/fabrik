---
activation: model_decision
description: Code review workflow, quality gate commands, and reusability discipline. Apply when running a self-review/gate, closing a milestone, deciding what tests to write, or judging whether a function should be extracted to a shared module.
---

# Code Review

**Scope:** Any coding agent (Claude Code, Cascade, Kilo CLI) running the self-review gate, closing a milestone, or judging code reusability on `/opt/*` projects.

---

## A) Self-Review Gate (Every Task)

### Internal Audit

*Perform before reporting completion. Full checklist in the agent's bootstrap file (`CLAUDE.md` / `.windsurfrules` / `AGENTS-compact.md`).*
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

Fix all findings (BLOCKER, MAJOR, MINOR) yourself — there is no separate FIXER role in any of the three coding agents.

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
- The coding agent fixes issues. Kilo review (when invoked) is report-only by default.
- Traycer / the user commits — coding agents only implement and fix; gate auto-stages.
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

## Reusability & Modularity

Cross-project-extractable code is a first-class review concern:

- **Business logic separate from framework.** A FastAPI route should call into a plain Python function — not embed the business logic inline.
- **Shared utilities live in `src/utils/` or `src/lib/`** with ZERO project-specific imports and NO hardcoded project-specific values (paths, URLs, table names, env-var names).
- Any function that could serve another Fabrik project lives in its own module with a docstring + type hints.
- **Tag reusable modules in `INDEX.md` with `[reusable]`** so the next project can grep for them.

When reviewing a diff, ask: "Could this helper, decorator, or class serve any other Fabrik service?" If yes, it belongs in a shared module — not in the route file.

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

All three coding agents (Claude Code, Cascade, Kilo CLI) load this pack on demand when a code-review or completion-gate task is in flight. It provides:

1. Quality gate commands organized by tier (lean, full, systemic).
2. Self-review reminders (output format, iteration limits, fixer responsibility).
3. Reusability discipline (cross-project-extractable code review).
4. Solo-Dev Creed for architectural discipline.

