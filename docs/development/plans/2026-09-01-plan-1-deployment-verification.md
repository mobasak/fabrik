# Plan 1 — Deployment Verification Contract (hub build)

Status: DRAFT
Date: 2026-09-01
Spec: `docs/superpowers/specs/2026-09-01-deployment-verification-contract-design.md` (CONVERGED, `3a853851`)
Scope: **`/opt/fabrik` only** — 4 file groups. Routed feature-scale (spec defect 15: the epic verdict was wrong).

## Why this plan exists

I certified tryton-crm `DEPLOY CONFIRMED LIVE` with every check green while production held **0 of its
760 companies**. Liveness checks cannot fail on a missing product, because nothing declared what the
product should contain.

## File Scope (exhaustive — nothing outside this list)

| # | path | change |
|---|---|---|
| 1 | `commands/_sources/fabrik-deploy-checklist.md` | **NEW** — the project-side authoring command |
| 2 | `commands/_sources/fabrik-deploy-verify.md` | rewrite (216 lines today) |
| 3 | `src/fabrik/scaffold.py` + `templates/scaffold/**` | seeding, on the `:285` precedent |
| 4 | `tests/**` | regression guards for 1–3 |

⚠️ **FLEET-SYNCED SURFACE.** Every `commands/_sources/` edit distributes to 43 repos on commit. **Merge-time
render only** — never bare-render `assemble_commands.py` from a worktree (it PRUNES installed commands
absent from the current tree). `--check` is always safe.

## OUT OF SCOPE — named, not silently dropped

- **fabrik-lib `health-probe` enhancement** — filed `01M1ESR5KJW5Z1EE2YE55MBTE8`; **they** spec and
  implement. This plan builds against the **FALLBACK** (vendor `health-probe` as-is, diff in the parity
  runner) so **nothing blocks on their reply**. If they land the core change, the runner swaps to it.
- **Per-project onboarding (27 deployable repos)** — self-serve; each project's own agent runs the new
  command in its own repo. Cross-repo commits are a HARD STOP, so this is not mine to execute.

## Phase A — `/fabrik-deploy-verify` rewrite (the runner)

**Steps**
1. Add **Layer 1 Identity** as a new phase: deployed SHA vs tested SHA · `alembic current` vs `heads` ·
   image digest · lockfile hash. *(Measured absent today: `rev-parse` 0, `alembic` 0, `digest` 0.)*
2. Rewrite **Layer 3** so registrar rows are **generated from `infrastructure.py::_REGISTRAR_ORDER`**,
   not hand-listed — the 10 are postgres · redis · gatus · backrest · glitchtip · grafana · authelia ·
   **meilisearch** · prometheus · watchdog. Meilisearch has **no row at all** today.
3. Make **Phase 6 blocking and contract-driven** — remove the "first 3 rows" cap; consume the project's
   parity contract; `UNVERIFIABLE (<why>)` rows counted in the verdict.
4. Implement the **verdict algebra**: `UP` / `COMPLETE` / `RUNNING` separately-failable; `CONFIRMED`
   requires all three; **`UNVERIFIED`** when no contract exists; `not obligated` distinct from `not checked`.

**Gate:** `python scripts/final_gate.py --json` → success · `python commands/assemble_commands.py --check`
(temp-dir render, safe) · `grep -c _REGISTRAR_ORDER commands/_sources/fabrik-deploy-verify.md` ≥ 1.

**Evidence owed:** the 10 registrar names re-derived from `infrastructure.py` in-run; a `--check` render
showing no pruning.

## Phase B — the new authoring command

**Steps**
1. Author `commands/_sources/fabrik-deploy-checklist.md` — project-side. It walks the corpus and emits
   **the runnable command + expected result per row**, never prose.
2. Encode the **derived-denominator rules**: routes from the router's introspection · jobs from the live
   scheduler · env keys from `grep os.getenv` · services from **compose ∪ registrar-injected sidecars**
   (tryton-crm: compose declares 4, 5 run) · schema from `alembic heads`.
3. **Features cross-check** — features are prose and underivable, so: every derived route maps to a
   *Shipped* row and every *Shipped* row to a route; **either direction unmatched is a FINDING**.
4. Output `scripts/verify_prod_parity.py` + refresh `DEPLOYMENT.md`/`OPERATIONS.md` (D-065).
   ⚠️ **Derive from CODE + SPEC + DEV, never from PROD** — generating docs from deployed state launders
   drift into the declaration and destroys the only signal.
5. Add the NEXT-map entry so the command chains.

**Gate:** `final_gate --json` success · `assemble_commands.py --check` · the new command appears in the
NEXT map · a dry authoring run against tryton-crm produces a non-empty row set with its denominator stated.

## Phase C — scaffolder seeding (born compliant)

**Steps**
1. Seed on the **`scaffold.py:285` precedent** (`docs/data-contract-template.md` → `docs/data-contract.md`):
   `scripts/verify_prod_parity.py` stub that **EXITS NON-ZERO** (an unfilled contract fails closed),
   `specs/services/<id>.yaml` generated from `project.yaml` + `shape:`, and the `DEPLOYMENT.md` /
   `OPERATIONS.md` fleet-AI sections.
2. ⚠️ **Carry the `scaffold.py:293` docusaurus leak caveat** — seeding into `docs/` **publishes** it there.
   The parity contract names internal hosts, table names and row counts: seed outside `docs/` (`scripts/`
   already is) or add to the content-docs exclude.
3. Behavior test: scaffold each type in a temp dir; assert the stub exists, exits non-zero, and that a
   `docusaurus` scaffold does **not** publish it.

**Gate:** `final_gate --json` success · `pytest tests/test_scaffold*.py` green · the non-zero-exit and
docusaurus-exclusion assertions proven **red-on-revert**.

## Phase D — convergence

`/fabrik-review` over the full diff to a raised-zero round; `docs_updater.py --check`; CHANGELOG entry;
`docs/DECISIONS.md` row (this is an architecture choice: verification ownership moves to the project).

## Self-audit

- **Every phase has a runnable gate** — no phase exits on inspection.
- **The riskiest step is Phase C's docusaurus caveat**: it is the one place this plan can leak internal
  infrastructure detail to a public site, and it is guarded by a test, not a comment.
- **Nothing here depends on fabrik-lib.** The fallback is the plan of record; their enhancement is an
  upgrade, not a prerequisite.
- **Residual risk, named:** the store/static per-type packs are the least-grounded content in the spec
  (no such deploy was exercised). Phase B ships their rows as `UNVERIFIABLE` **by default** rather than
  guessing, so a wrong check never silently passes.

## Next

`/fabrik-plan-review` — this is a fleet-synced corpus change and earns an adversarial pass before execution.
