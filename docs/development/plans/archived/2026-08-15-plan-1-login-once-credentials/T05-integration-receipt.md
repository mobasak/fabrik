# T05 — Integration: whole-plan gate, docs convergence, receipt

## Scope
The set's closing ticket. Runs the whole-plan
`python scripts/enforcement/check_doc_sync.py --range <baseline_commit>..HEAD` +
`check_doc_stubs.py --range <baseline_commit>..HEAD` receipt (`<baseline_commit>` = the plan
lock's recorded baseline — the dispatcher supplies it), the full
`python scripts/final_gate.py --check --json` to `"status":"success"` +
`python scripts/enforcement/check_convergence.py`, `/fabrik-docs-review` over the plan's doc
delta, and the cross-ticket seam check (the T02a→T03 assignments/fleet-root interface exercised
by the merged test suite). Writes the review receipt. DO-NOT: no code edits — a RED run is
reported to the orchestrator as Deltas, re-run after they land; the receipt is written only
when green (the Deltas loop resolves the no-edits/green-gate tension by construction).

Depends: T04
Parallel: ⛓️
Complexity: native
Integration: true
Gate: python scripts/final_gate.py --check --json
Docs: none (receipt only)

## Touches
- docs/development/reviews/2026-08-15-plan-1-login-once-credentials-review.md

## Behavior Contract
- **Given** all work tickets merged, **When** the full Tier-2 gate and convergence check run, **Then** both are green and the receipt embeds the verbatim success JSON (docs/development/reviews/2026-08-15-plan-1-login-once-credentials-review.md:1)

## Context Files
- docs/superpowers/specs/2026-08-15-login-once-credentials-design.md
- docs/workflows/FINAL_GATE_WORKFLOW.md
