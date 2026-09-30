# T06 — Integration: landing docs, distribution, fabrik-lib, the live run, receipt

## Scope
Implements spec § Documentation landing sites, § The delta 9 and § Validation V9, and owns the whole-plan receipt. The orchestrator, in the main checkout, after T01-T05 are merged: rewrites `docs/reference/multi-agent-operating-model.md` § Merge protocol (`:141-158`) to name the request and the script; adds the kind, its body fields and `who` to `docs/reference/fabrik-mail.md`; adds the D-B cause row to `docs/workstation/hooks-index.md`; adds `merge_request.py` to `RUN_SCRIPTS` in `scripts/fabrik_synced_manifest.py` beside `mail.py` (`:51`) so every project receives it; mails `fabrik-lib-sentinel` the adoption request (the template text and the two scripts to vendor); then runs V9 live — the next fleet or intel request in the hub goes end to end through `request`, the doorbell and `merge` with no hand-rolled step — and writes the whole-plan receipt.

Depends: T03, T04, T05b
Parallel: ⛓️
Complexity: native
Integration: true
Gate: python scripts/final_gate.py --check --json
Docs: docs/reference/multi-agent-operating-model.md, docs/reference/fabrik-mail.md, docs/workstation/hooks-index.md

## Touches
- docs/reference/multi-agent-operating-model.md
- docs/reference/fabrik-mail.md
- docs/workstation/hooks-index.md
- scripts/fabrik_synced_manifest.py
- tests/test_synced_manifest.py
- docs/development/reviews/2026-09-30-plan-1-merge-request-loop-review.md

## Behavior Contract
- **Given** the synced manifest, **When** `RUN_SCRIPTS` is read, **Then** it lists `merge_request.py` (spec § Lifecycle adoption)
- **Given** every ticket merged, **When** the next fleet or intel merge request runs in the hub, **Then** it goes end to end through `request`, the doorbell and `merge` with no hand-rolled step, and the requester's reply names the merge commit (spec § Validation V9)
- **Given** the model doc, **When** § Merge protocol is read, **Then** it names `merge_request.py request` for the finishing agent and `merge_request.py merge` for the owner (spec § Documentation landing sites)

## Context Files
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- docs/reference/multi-agent-operating-model.md
- docs/reference/fabrik-mail.md
- scripts/fabrik_synced_manifest.py
