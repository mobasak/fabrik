# T34 — Integration — whole-plan receipt, gates, docs convergence

## Scope
The Integration receipt: after T33 merges, run the whole-plan gates and converge the docs. Steps: `python scripts/final_gate.py --check --json` (expect status success) · `python scripts/enforcement/check_convergence.py` · `python scripts/enforcement/check_doc_sync.py` · /fabrik-docs-review over docs/reference/command-evaluation-checklist.md + docs/reference/operating-manifesto.md in REPORT mode for this plan's purposes — both files sit OUTSIDE the plan File Scope, so a drift finding there is recorded in the receipt and routed as a BLOCKED-escalation or a normal post-plan edit, never fixed in-ticket · the receipt artifact lists all 33 ticket commits + the per-command verdict-table paths + the corpus render proof (`python commands/assemble_commands.py --check` output). ALSO MANDATORY (the /fabrik-execute-plan § Finish contract + check_convergence's EXECUTED gate demand it): run the whole-plan /fabrik-review over the CUMULATIVE diff of T01..T33 to a coverage-adjudicated exit (new: 0 closing round); its Coverage Checklist + Pass Ledger live IN the receipt artifact, which the spine's EXECUTED stamp then cites. Governance-surface rows (CHANGELOG entry, INDEX rows for the new artifacts) flow through the orchestrator's D3 Deltas block — its fixed format covers exactly those surfaces and nothing else. DO-NOT: edit commands/_sources or _fragments here — findings at this stage are BLOCKED-escalations, not new work.

Depends: T33
Parallel: ⛓️
Complexity: native
Integration: true
Gate: python scripts/final_gate.py --check --json
Docs: CHANGELOG.md entry via the orchestrator Deltas mechanism (command contract changed); INDEX.md row for the new review artifact (orchestrator-applied)

## Touches
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-review.md — the whole-plan receipt

## Behavior Contract
- **Given** all 33 work tickets merged, **When** the whole-plan receipt runs `python scripts/final_gate.py --check --json` + `python scripts/enforcement/check_convergence.py` + `python scripts/enforcement/check_doc_sync.py` and /fabrik-docs-review over the corpus docs, **Then** every command's 63b verdict table exists (32/32 + fragments), the gate reports success, and the receipt records the per-ticket commit list (docs/reference/command-evaluation-checklist.md:161)
- **Given** the cumulative diff of T01..T33, **When** the whole-plan /fabrik-review runs over it to a coverage-adjudicated exit (its Coverage Checklist + Pass Ledger living in the receipt artifact), **Then** the receipt's Pass Ledger closes on a round carrying the literal `found: 0 · fixed: 0` — what check_convergence.py's QUIET_PASS regex (scripts/enforcement/check_convergence.py:150) actually demands before any EXECUTED flip; a standing adjudicated row that keeps found above zero is BLOCKED-escalated, never carried into the close (commands/_sources/fabrik-execute-plan.md:958)

## Context Files
- docs/reference/command-evaluation-checklist.md
- docs/development/plans/2026-08-31-plan-1-manifesto-command-pass/2026-08-31-plan-1-manifesto-command-pass.md
