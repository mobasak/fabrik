# Convergence Prompts (direct-agent workflow)

When you drive a coding agent **directly** (Claude Code, Windsurf Cascade, Kilo CLI)
instead of planning through Traycer, paste the matching prompt below. Each forces the
agent to **iterate to a fixed point** — not stop after one attempt — and emits the exact
artifact its gate inspects, so the claim cannot outrun the proof.

**Each phase has a different gate** (use the right one):

- **PLAN** — there is no code yet, so the gate is the plan's *evidence*, not code checks:
  [`scripts/enforcement/check_convergence.py`](../../scripts/enforcement/check_convergence.py)
  (fails a plan that claims CONVERGED without Evidence + per-phase `path:line` + fenced
  command output + a self-audit). Do **not** run `final_gate.py` to "converge" a plan —
  there is nothing to lint or test yet.
- **CODE REVIEW** — code now exists, so gate it: `final_gate.py` **tier 2** (`--json`) +
  **tier 3** (`--systemic --json`), both `"status":"success"`.
- **DOCS** — `docs_updater.py --check` ("Documentation Drift") + `check_docs.py`
  ("Documentation Completeness"), which live in `final_gate.py` **tier 3** (`--systemic`).

> **Gate tiers (for CODE/DOCS — they do NOT nest):**
>
> - `--lean` = **tier 1, showstoppers only** (syntax, secrets, schema, CHANGELOG,
>   print-ban, Doc Sync Matrix). Too weak to claim convergence.
> - *no flag* / `--check` = **tier 2, comprehensive** (tier 1 **plus** ruff/mypy/bandit/
>   semgrep, README, CONFIGURATION, test-proposal, test-coverage, env, compose-services).
> - `--systemic` = **tier 3, repo + docs health** (Documentation Drift/Completeness,
>   doc-sprawl, deps, ports, docker). **Skips** tier-1/2 — not a superset.
>
> **Implementation convergence bar = tier 2 AND tier 3 both green.** (PLAN's bar is
> `check_convergence.py`; there is no code to gate at plan time.)
>
> **What "converged" means:** a **fixed point** — another full pass (revise → self-review
> → re-gate) changes nothing and the gate is green. One pass is never enough.
>
> **Honest ceiling:** the gate enforces evidence *presence* + mechanical green — never
> truth. Whether the proof is correct still rests with the reviewer. Direct edits that
> ship no plan/review artifact aren't caught by `check_convergence.py`.

---

## PLAN CONVERGENCE

```text
ITERATE a plan for <TASK> until it CONVERGES — do NOT stop after one pass. Loop:
  1. Gather evidence FIRST: for every file/column/value a step touches, READ THE
     ACTUAL VALUES (path:line + the command and its real output) — never assume.
  2. Write/REVISE docs/development/plans/YYYY-MM-DD-plan-<name>.md with: a "## Evidence"
     section (per Phase: >=1 path:line AND >=1 fenced command-output block); every step
     grounded to that evidence and naming the gate the IMPLEMENTER will run for it
     (named test + the comprehensive gate, NOT --lean); and a "## Self-audit".
  3. Self-audit pass: re-check EVERY claim against evidence; list each unknown, gap,
     deviation, or unhandled edge case.
  4. If step 3 found ANYTHING, fix it and GO BACK TO 1.
Converged = a full pass that surfaces ZERO new gaps AND, with the plan staged,
`python scripts/enforcement/check_convergence.py` passes (the plan carries its evidence).
Do NOT run final_gate.py here — there is no code to gate yet. Only THEN set
"**Status:** CONVERGED". Obey .windsurf/rules.
```

## CODE REVIEW CONVERGENCE

```text
ITERATE your review of the implementation against the finalized plan until it CONVERGES
— do NOT stop after one pass. Loop:
  1. Review code vs plan: per-Phase verdict (mirrors / deviation+fix) and every
     bug/edge-case with file:line.
  2. Fix what you found.
  3. Re-run `python scripts/final_gate.py --json` (tier 2) AND `python scripts/final_gate.py
     --systemic --json` (tier 3). If either isn't "status":"success", fix and repeat.
  4. RE-REVIEW the code you just changed (fixes introduce new bugs); if anything turns
     up, GO BACK TO 1.
Converged = a pass that finds ZERO new issues AND both gate runs show "status":"success".
Write docs/development/reviews/<plan>-review.md with the per-Phase verdicts, every
bug+fix (file:line), and the VERBATIM output of both green gate runs. Only THEN mark it
converged. Obey .windsurf/rules.
```

## DOCS UPDATE CONVERGENCE

```text
ITERATE doc updates until they CONVERGE with current code/DB/schema — do NOT stop after
one pass. Loop:
  1. For each doc (tailored per type — API vs architecture vs reference), reconcile to
     reality and add a "claim -> proof" line (file:line / query output).
  2. Run `python scripts/docs_updater.py --check` and `python scripts/final_gate.py
     --systemic --json` (tier 3 — where Documentation Drift + Completeness live); if code
     also changed, `python scripts/final_gate.py --check` (tier 2) too.
  3. If anything is red or any drift/discrepancy remains, fix it and GO BACK TO 1.
Converged = a pass with ZERO drift AND Documentation Drift + Completeness green. Only THEN
claim "in sync". Obey .windsurf/rules and the CLAUDE.md Doc Sync Matrix.
```
