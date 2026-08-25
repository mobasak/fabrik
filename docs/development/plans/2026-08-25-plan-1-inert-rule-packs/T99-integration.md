# T99 — integration

Depends: T01, T03, T04
Parallel: ⛓️
Complexity: native
Docs: whole-plan receipt
Integration: true
Gate: python scripts/enforcement/check_doc_sync.py

## Scope

Whole-plan receipts: doc-sync + doc-stubs over the plan range, `/fabrik-docs-review`, the whole-plan
`final_gate.py --check --json` and `check_convergence.py`, and the cross-ticket seam check that the
audit (T02), the check (T03) and the matcher (T04) agree on one pack set. DO-NOT write feature code.

## Touches

- docs/reference/rule-pack-reachability.md

## Behavior Contract

- **Given** the merged plan, **When** the whole-plan receipts run, **Then** the audit, the check and the matcher all report the same pack set for the same inputs (docs/reference/rule-pack-reachability.md:1).

## Context Files

- docs/reference/rule-pack-reachability.md
