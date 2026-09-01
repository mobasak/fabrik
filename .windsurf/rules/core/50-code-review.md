---
activation: model_decision
description: Code review workflow, quality gate commands, and reusability discipline. Apply when running a self-review/gate, closing a milestone, deciding what tests to write, or judging whether a function should be extracted to a shared module.
---
<!-- CONSUMER: Coding agents (all) — loaded on-demand for self-review/gate tasks
     GOAL: Quality gate commands (lean/full/systemic), self-review audit, reusability discipline
     TRAYCER USAGE: Not directly injected — agents load this when running gates.
     AGENT USAGE: Run internal audit + lean gate before reporting completion. Full gate at milestone. -->

# Code Review

**Scope:** Any coding agent (Claude Code + dispatched subagents) running the self-review gate, closing a milestone, or judging code reusability on `/opt/*` projects.

---

## A) Self-Review Gate (Every Task)

### Internal Audit

*Perform before reporting completion. Full checklist in the agent's bootstrap file (`CLAUDE.md` / `.windsurfrules` / `AGENTS-compact.md`).*

- [ ] **Secrets:** No hardcoded keys or tokens?
- [ ] **Infrastructure:** `Dockerfile` is `-slim-bookworm`, has `HEALTHCHECK`, no Alpine?
- [ ] **Compose:** `platform: linux/amd64`, `deploy.resources.limits.memory`, Traefik labels with `websecure` entrypoint, `fabrik` network, no `ports:` section?
- [ ] **Networking:** Port registered in `PORTS.md`? DB host = `postgres-main`, Redis = `redis-main` (not `localhost`)?
- [ ] **Database:** Changes added to `db/schema.sql`? Alembic migration (no raw DDL)?
- [ ] **Docs:** `CHANGELOG.md` entry? `INDEX.md` reflects file changes? See `40-documentation.md` for full Documentation Sync Matrix.

### Lean Gate (Tier 1)

```bash
python scripts/final_gate.py --lean
```

Syntax (ruff), json/yaml validation, secrets, env vars, schema sync. Fast, no context poisoning.

**Note:** `final_gate.py` runs in the fabrik project context with its own `.venv`. In child projects, use `uv run python scripts/final_gate.py --lean` if the gate script is synced.

---

## B) Changelog (Every Code/Config/Infra Change)

For any non-trivial code, config, infrastructure, Docker, or compose change in:
`src/`, `scripts/`, `templates/`, `.github/`, `Dockerfile`, `compose.yaml`, `.env.example`, `pyproject.toml`, `package.json`, `uv.lock`,
you MUST ensure `CHANGELOG.md` has a real entry under `## [Unreleased]`:

```markdown
### Added/Changed/Fixed — <Title> (YYYY-MM-DD)
```

See `40-documentation.md` for the full Documentation Sync Matrix — changelog is one of 14 trigger-based doc updates.

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
git diff --staged --name-only       # Verify staged matches intent
python scripts/kilo_code_review.py staged --plan "task description" --output json
```

Use for rare high-risk or cross-cutting changes. Never rely on it as the default completion gate.

**Note:** Stage specific files by name, not `git add -A`. Staging all files risks including unrelated changes, `.env` files, or large binaries.

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

Repo health: docker, ports, docs sprawl, duplicates, deps sync, health endpoints, env contract. Never part of a normal fix loop.

---

## Key Reminders

- Internal audit + lean gate is **MANDATORY** before reporting completion.
- **Changelog is MANDATORY for any code/config/infrastructure change. Full gate runs at milestone/batch closure, not for every task.**
- The coding agent fixes issues. Kilo review (when invoked) is report-only by default.
- The user commits and pushes — coding agents only implement and fix; gate auto-stages.
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
- **Behavior Contract Enforcement:** the plan enumerates a test per distinct user-observable behavior / acceptance criterion (Given/When/Then), risk-ordered, skip trivia — not a single test. See `45-testing-strategy.md`.
- **Real-World Breakage Review:** For IO/FS/Exec changes, define:
  - **Trigger:** What action causes the failure?
  - **Symptom:** What does the user see (or what does the log show)?
  - **Root Cause:** The technical "why"
  - **Detection:** How do we catch this in `final_gate.py`?
  (Related: `40-documentation.md` § LESSONS_LEARNT uses Context/Problem/Root Cause/Solution/Integration for post-incident capture — different moment, same analytical structure.)
- **No stylistic bikeshedding:** Prefer correctness and safety over "clean code" aesthetics.
- **Minimalist Refactors:** No unsolicited refactors unless part of the approved plan.

---

## Related Rule Packs

- `40-documentation.md` — Documentation Sync Matrix (14 triggers), CHANGELOG, INDEX.md, LESSONS_LEARNT
- `45-testing-strategy.md` — Behavior Contract, framework per scaffold, test fixtures
- `30-ops.md` — Dockerfile + compose checklist (aggregated in the internal audit above)
- `25-data-postgres.md` — Alembic migration discipline (no raw DDL)
- `55-observability.md` — structlog, `/health`, `/metrics` (referenced in audit)

---

## Why This File Exists

Coding agents (Claude Code + dispatched subagents) load this pack on demand when a code-review or completion-gate task is in flight. It provides:

1. Quality gate commands organized by tier (lean, full, systemic).
2. Self-review reminders (output format, iteration limits, fixer responsibility).
3. Reusability discipline (cross-project-extractable code review).
4. Solo-Dev Creed for architectural discipline.
