# T06 — Integration: landing docs, distribution, fabrik-lib, the live run, receipt

## Scope
Implements spec § Documentation landing sites, § The delta 9 and § Validation V9, and owns the whole-plan receipt. The orchestrator, in the main checkout, after T01-T05 are merged: rewrites `docs/reference/multi-agent-operating-model.md` § Merge protocol (`:141-158`) to name the request and the script; adds the kind, its body fields and `who` to `docs/reference/fabrik-mail.md`; adds the D-B cause row to `docs/workstation/hooks-index.md`; applies the `INDEX.md` rows for `scripts/merge_request.py` and its three test files at merge (a governance ledger the orchestrator applies — through the private-index recipe); corrects the spec's invariant (3), whose 'skipped in (e)' is stale against § The delta 5 (e): a path that changes after (a) keeps the owner's working copy, its index entry realigned to the merge, and is listed in the reply (W-8a6a5644); mails `fabrik-lib-sentinel` the adoption request (the template text and the two scripts to vendor); then runs V9 live — the next fleet or intel request in the hub goes end to end through `request`, the doorbell and `merge` with no hand-rolled step — and writes the whole-plan receipt.

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
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- docs/development/reviews/2026-09-30-plan-1-merge-request-loop-review.md

## Behavior Contract
- **Given** `INDEX.md`, **When** it is read, **Then** it carries a row for `scripts/merge_request.py` and each of its test files (spec § Documentation landing sites)
- **Given** the spec, **When** invariant (3) is read, **Then** it says a path changed after (a) keeps the owner's working copy with its index realigned to the merge and is listed in the reply, never 'skipped' (W-8a6a5644)
- **Given** every ticket merged, **When** the next fleet or intel merge request runs in the hub, **Then** it goes end to end through `request`, the doorbell and `merge` with no hand-rolled step, and the requester's reply names the merge commit (spec § Validation V9)
- **Given** the model doc, **When** § Merge protocol is read, **Then** it names `merge_request.py request` for the finishing agent and `merge_request.py merge` for the owner (spec § Documentation landing sites)

## Context Files
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- docs/reference/multi-agent-operating-model.md
- docs/reference/fabrik-mail.md
- docs/workstation/hooks-index.md
- INDEX.md
