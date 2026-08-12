# T05 — Integration: whole-plan receipts, docs convergence and final gate

## Scope

Own the whole-plan close-out that no single work ticket can: run the cross-ticket seam checks, converge the
documentation to truth, and produce the receipt artifact that proves the set landed clean. Specifically —
run the two golden/audit tools against each other's output (the oracle must still verify green after T03's
`daily_refresh.sh` change, and the audit's classification must cover every path T01 froze and every path
T04 relocated), run `/fabrik-docs-review` over the touched docs, and run the whole-plan
`python scripts/final_gate.py --check --json` plus `check_convergence.py`.

DO-NOT: do not implement or repair work-ticket behaviour here — a defect found at integration goes back to
its owning ticket, it is not patched in the receipt.

Depends: T04
Parallel: ⛓️
Complexity: native
Integration: true
Gate: python scripts/final_gate.py --check --json
Docs: CHANGELOG.md, INDEX.md, docs/LESSONS_LEARNT.md, docs/TROUBLESHOOTING.md — orchestrator-applied via Deltas

## Touches
- docs/development/reviews/2026-08-12-plan-1-catalog-extraction-fabrik-prep-review.md

## Behavior Contract
- **Given** all four work tickets merged, **When** the oracle's `--verify` runs, **Then** it reports zero drift, proving no ticket silently changed a consumed output (scripts/catalog_contract_snapshot.py:1)
- **Given** all four work tickets merged, **When** the audit runs, **Then** every node is classified and the relocated cost JSONs appear as satisfied rule-7 nodes (scripts/catalog_contract_audit.py:1)
- **Given** the whole-plan surface, **When** `python scripts/final_gate.py --check --json` runs, **Then** it reports `"status":"success"` (scripts/final_gate.py:1)
- **Given** the docs touched by this set, **When** `/fabrik-docs-review` runs to its fixed point, **Then** it converges with no remaining doc-vs-code drift (docs/superpowers/specs/2026-07-26-catalog-extraction-design.md:1)

## Context Files
- docs/superpowers/specs/2026-07-26-catalog-extraction-design.md
- .windsurf/rules/core/40-documentation.md
- .windsurf/rules/core/50-code-review.md
