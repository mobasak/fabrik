---
activation: model_decision
description: Code review workflow, quality gate commands, and reusability discipline. Apply when running a self-review/gate, closing a milestone, deciding what tests to write, or judging whether a function should be extracted to a shared module.
---
<!-- CONSUMER: Coding agents (all) — loaded on-demand for self-review/gate tasks
     GOAL: Quality gate commands (lean/full/systemic), self-review audit, reusability discipline
     TRAYCER USAGE: Not directly injected — agents load this when running gates.
     AGENT USAGE: Lean gate WHILE iterating; the full --json gate is the per-task completion gate. -->

# Code Review

**Scope:** Any coding agent (Claude Code + dispatched subagents) running the self-review gate, closing a milestone, or judging code reusability on `/opt/*` projects.

---

## A) Self-Review Gate (Every Task)

### Internal Audit

*Perform before reporting completion. Full checklist in the agent's bootstrap file (`CLAUDE.md` / `.windsurfrules` / `AGENTS-compact.md`).*

- [ ] **Secrets:** No hardcoded keys or tokens?
- [ ] **Infrastructure:** `Dockerfile` uses the pinned Debian `-slim` variant (per `30-ops.md` § Container Base Images), has `HEALTHCHECK`, no Alpine?
- [ ] **Compose:** `platform: linux/amd64`, `deploy.resources.limits.memory`, Traefik labels with `websecure` entrypoint, `fabrik` network, no `ports:` section?
- [ ] **Networking:** Port registered in `PORTS.md`? DB host = `postgres-main`, Redis = `redis-main` (not `localhost`)?
- [ ] **Database:** Changes added to `db/schema.sql`? Alembic migration (no raw DDL)?
- [ ] **Docs:** `CHANGELOG.md` entry? `INDEX.md` reflects file changes? See `40-documentation.md` for full Documentation Sync Matrix.

### Lean Gate (Tier 1)

```bash
python scripts/final_gate.py --lean --json
```

Syntax (ruff), json/yaml validation, secrets, env vars, schema sync. Fast, no context poisoning.
**Tier 1 is for iteration only — never the completion gate**: that is the full `--json` run below.
Add `--check` for a read-only run (no fixes, no auto-stage).

**Note:** `final_gate.py` runs in the fabrik project context with its own `.venv`. In child projects, use `uv run python scripts/final_gate.py --lean --json` if the gate script is synced.

---

## B) Changelog (Every Code/Config/Infra Change)

For any non-trivial code, config, infrastructure, Docker, or compose change in:
`src/`, `scripts/`, `templates/`, `.github/`, `Dockerfile`, `compose.yaml`, `.env.example`, `pyproject.toml`, `package.json`, `uv.lock`,
you MUST ensure `CHANGELOG.md` has a real entry under `## [Unreleased]`:

```markdown
### Added/Changed/Fixed — <Title> (YYYY-MM-DD)
```

See `40-documentation.md` for the full Documentation Sync Matrix — changelog is one of its trigger-based doc updates (the registry `_doc_registry.py::PROJECT_DOCS` is the SSOT; never carry a copy of the row count).

---

## C) Completion Gate (EVERY task — and again at batch closure)

The full gate is the **per-task definition of done**, not a milestone ritual: run it before reporting completion, fix to `"status": "success"`, and re-run it in the SAME turn you claim green (a stale pass is not evidence). Run it once more when closing a batch:

```bash
python scripts/final_gate.py --json
```

Full quality: static analysis (ruff, mypy, bandit, semgrep) + consistency checks (changelog, index, readme, test proposal). Diff-aware — skips checks for unchanged files. ⚠️ A tool missing from the interpreter running the gate is **SKIPPED, not passed** — the run says which; read the skip lines before treating green as verified.

---

## D) The review family — which command, sized to the surface

The gates above are mechanical. The **review commands** are the adversarial pass, and every
code-changing chunk of work gets one:

- **`/fabrik-review-scoped`** — diff-scoped, minutes. The default for spontaneous / plain-chat
  changes. (The Stop hook BLOCKS a code-editing session that never opened a review record.)
- **`/fabrik-review`** — the full command. Escalate to it for: a new mechanism, any
  gate/hook/enforcement path, auth/schema/migrations/concurrency, >5 files, anything the owner
  asked for by name, or a scoped review still finding after 3 rounds.

Both arm their finders from `scripts/review_rubric.py --changed <paths>` (synced to every project),
converge to a round that raises **zero new** candidates, and are **fix-in-run**: findings are fixed
or refuted with the disproving line — never filed as someone else's problem. Stage specific files
by name, never `git add -A`.

---

## D2) WHY the review family is shaped this way — the properties that make it work

D) says which command; this says which properties must survive when someone "simplifies" it.

- **The maker never certifies its own work.** LLM evaluators show a measured *agreeableness bias* —
  they confirm correct feedback and fail to reject incorrect feedback — and recall drops hardest
  when a model reviews its OWN output, because a model that missed its own bug has no signal to look
  again. Hence: review runs in a SEPARATE session with no authoring context, and D-063 pins the
  second-opinion model. § A's self-review is the floor, not the review.
- **Finders over-generate; refutation is a separate ACT with a hard bar.** Finders get narrow briefs
  and no obligation to be balanced. Every candidate is then attacked — REFUTED only when provably
  impossible, factually wrong, or already guarded, each with the line quoted.
  ⚠️ **In our machinery the refuter is the ORCHESTRATOR, not a blinded verifier** (`/fabrik-review`
  Phase 2): it refutes from the code while holding the finder's output. That is a real bar but NOT
  the incentive separation the published finder/verifier pattern describes — so the discipline has
  to come from the bar, not the architecture. When a finding is high-stakes, buy the independence
  back by dispatching a fresh author-blind agent for that finding alone.
- **Rank by whether it changes what someone does.** Runtime errors, security, data loss first;
  architecture and measured performance second; style opinions and micro-optimisations are a
  linter's job, not a review comment. Noise is not harmless — once a reviewer is ignored, its
  correct findings are ignored too.

**Loop shape — we converge where the common pattern escalates.** The published review-then-implement
loop caps automated fixing at ONE pass and hands to a human instead of iterating; that is right when
a human reviews every merge. Ours converges to a quiet round because the work is unattended and
there is no human at the merge point — the loop IS the oversight. Two obligations come with it:
1. **Dedup against everything ever SEEN, not against what was CONFIRMED.** A refuted finding never
   enters the confirmed set, so the next round rediscovers it, refutes it again, and the counter
   never reaches zero — the loop runs forever looking busy. ⚠️ One deliberate carve-out: a re-raise
   carrying evidence the refutation does not cover NEEDS adjudication and COUNTS. An independent
   finder rediscovering a weakly-refuted bug must never be silenced by the citation rule
   (`/fabrik-review` is canonical for the exact wording).
2. **A quiet round is evidence only if the search was diverse.** Zero findings because the code is
   clean and zero because every pass looked the same way are indistinguishable from inside the loop.

**Cross-REPO findings are logged, not converged on** — recorded with an owner and excluded from the
convergence check, or the loop oscillates: fixer applies a local workaround, next reviewer flags the
workaround, forever. That is what `ROUTED` is for. ⚠️ It is scoped to ANOTHER REPO only —
cross-service findings inside this repo are fix-or-refute, never routed away.

---

## E) Systemic Gate (Tier 3 — On-Demand Only)

```bash
python scripts/final_gate.py --systemic
```

Repo health: docker, ports, docs sprawl, duplicates, deps sync, health endpoints, env contract. NARROWER than the completion gate — never a substitute for it, never part of a normal fix loop.

---

## Key Reminders

- Internal audit is **MANDATORY** before reporting completion; the lean gate is the fast loop DURING iteration.
- **The full `--json` gate is the per-task completion gate** — green on it (this turn, not an earlier run) is the definition of done. **Changelog is MANDATORY for any code/config/infrastructure change.**
- The coding agent FIXES what the review finds, in the same run. A finding handed onward is not a review.
- **The agent COMMITS AND PUSHES its own work at task end** — explicit pathspecs + provenance trailers, never `git add -A`. An uncommitted task is an unfinished task; an unpushed one is off-box-unprotected. (Hub + project contracts, § EXIT — Stop-hook-enforced.)
- **Review iterates to a FIXED POINT, not to a counter** — done is a pass that raises zero new candidates. Only the three sanctioned BLOCKED cases halt early: 3 consecutive same-test failures · missing infra · an unresolvable spec contradiction. Rounds that keep finding mean the surface outgrew the scoped command — escalate to `/fabrik-review`, don't stop.
- Non-trivial = any of: new file, >50 lines changed, new dependency, DB change, or any code/config/infrastructure/Docker/compose change.

---

## Output Format

Mid-run (after an ITERATION gate) report the tier, the changed files, and whether you proceed.

**At task completion, the report format is the contract's FINAL OUTPUT block, not a local one** —
`GATE: <command run> → success|failure` (the gate emits `"status": "success"`, never `PASS`) plus
the `DOCS UPDATED` / `CHANGELOG` / `LESSONS LEARNT` / `DONE` / `NEXT` / `FEEDBACK` lines. See
`CLAUDE.md` § FINAL OUTPUT — including the bar on `NEXT: operator decision`. Never emit a
competing `GATE:`/`NEXT:` grammar.

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

- **No Speculation:** If information is missing, state the assumption explicitly and proceed — or, when it genuinely blocks, exhaust the self-service sources (rule packs, `agents-fabrik.md`, `docs/`, `AFCL.md`, codebase grep) and then raise `BLOCKED: <what> — searched: <sources> — missing: <need>`. Never guess; never stall on a question the artifacts already answer.
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

- **`CLAUDE.md` § THE FIX DIRECTIVE** — binding on every fix; its verb 6 IS this pack ("review your own fix and fix what the review finds"), verbs 1-5 are measure → fix-the-class → no-stopgaps → fix+grader → don't overengineer
- `62-using-subagents.md` — finder dispatch (pool-default vs native-added), the parallelism trap
- `40-documentation.md` — Documentation Sync Matrix, CHANGELOG, INDEX.md, LESSONS_LEARNT, DECISIONS
- `45-testing-strategy.md` — Behavior Contract, framework per scaffold, test fixtures
- `30-ops.md` — Dockerfile + compose checklist (aggregated in the internal audit above)
- `25-data-postgres.md` — Alembic migration discipline (no raw DDL)
- `55-observability.md` — structlog, `/health`, `/metrics` (referenced in audit)

---

## Why This File Exists

Coding agents (Claude Code + dispatched subagents) load this pack on demand when a code-review or completion-gate task is in flight. It provides:

1. Quality gate commands organized by tier (lean, full, systemic).
2. Self-review reminders (output format, convergence law, fixer responsibility).
3. Reusability discipline (cross-project-extractable code review).
4. Solo-Dev Creed for architectural discipline.
