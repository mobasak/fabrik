# Convergence Prompts (direct-agent workflow)

When you drive a coding agent **directly** (Claude Code, Windsurf Cascade, Kilo CLI)
instead of planning through Traycer, paste the matching prompt below. Each one is
written so the agent emits the exact artifact its gate inspects, so the claim
cannot outrun the proof.

- **Plan / Code-review evidence** is enforced by [`scripts/enforcement/check_convergence.py`](../../scripts/enforcement/check_convergence.py)
  (registered in `final_gate.py`, runs every tier).
- **Docs** are enforced by `docs_updater.py --check` ("Documentation Drift") +
  `check_docs.py` ("Documentation Completeness") in tier 3 (`--systemic`).

> **Honest ceiling:** the gate enforces evidence *presence* + mechanical green —
> never truth. It guarantees you cannot *claim* convergence without showing proof
> and passing the existing gates; whether the proof is correct still rests with
> the reviewer. Direct edits that ship no plan/review artifact are not caught by
> `check_convergence.py` — they rely on the rest of `final_gate.py`.

---

## PLAN CONVERGENCE

```text
Produce a CONVERGED plan for <TASK> in ONE pass. Gather evidence BEFORE writing
prose: for every file/column/value a step touches, READ THE VALUES (not just the
schema). Write docs/development/plans/YYYY-MM-DD-plan-<name>.md with:
(1) a "## Evidence" section listing, per Phase, >=1 path:line AND >=1 fenced block
    showing the command + its real output;
(2) every step grounded to that evidence;
(3) a strict gate per step (named test + `python scripts/final_gate.py --lean`);
(4) a "## Self-audit" confirming every claim traces to evidence and flagging each
    runtime-only item with a fail-safe.
Do NOT set "**Status:** CONVERGED" until `python scripts/final_gate.py --check`
passes. Obey .windsurf/rules.
```

## CODE REVIEW CONVERGENCE

```text
Review the implementation against the finalized plan in ONE pass. Produce
docs/development/reviews/<plan>-review.md with:
(1) a per-Phase verdict (mirrors plan / deviation + fix);
(2) the VERBATIM `python scripts/final_gate.py --json` output showing
    "status": "success" — re-run until green;
(3) each bug/edge-case with file:line + fix.
Do NOT mark it converged until the embedded gate run shows success and
`python scripts/final_gate.py --check` passes. Obey .windsurf/rules.
```

## DOCS UPDATE CONVERGENCE

```text
Update docs to match current code/DB/schema in ONE pass, tailored per doc type
(API vs architecture vs reference). For each changed doc add a "claim -> proof"
line (file:line / query output). Run `python scripts/docs_updater.py --check` and
`python scripts/final_gate.py --systemic --json`; fix until "Documentation Drift"
and "Documentation Completeness" are green. Do NOT claim "in sync" until those
pass. Obey .windsurf/rules and the CLAUDE.md Doc Sync Matrix.
```
