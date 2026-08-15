# T05 — Integration: whole-plan gate, docs convergence, receipt

## Scope
The set's closing ticket. Runs the whole-plan
`python scripts/enforcement/check_doc_sync.py --range` + `check_doc_stubs.py --range` receipt,
the full `python scripts/final_gate.py --check --json` to `"status":"success"` +
`python scripts/enforcement/check_convergence.py`, `/fabrik-docs-review` over the plan's doc
delta, and the cross-ticket seam check (the T02→T03 assignments/fleet-root interface exercised
by the merged test suite). Writes the review receipt. DO-NOT: no code edits — doc-drift fixes
flow through the orchestrator's Deltas mechanism.

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
