# T34 — Integration — whole-plan receipt, gates, docs convergence

## Scope
The Integration receipt: after T33 merges, run the whole-plan gates and converge the docs. Steps: `python scripts/final_gate.py --check --json` (expect status success) · `python scripts/enforcement/check_convergence.py` · `python scripts/enforcement/check_doc_sync.py` · /fabrik-docs-review over docs/reference/command-evaluation-checklist.md + docs/reference/operating-manifesto.md + INDEX rows · the receipt artifact lists all 33 ticket commits + the per-command verdict-table paths + the corpus render proof (`python commands/assemble_commands.py --check` output). Doc-drift fixes flow through the orchestrator's Deltas mechanism. DO-NOT: edit commands/_sources or _fragments here — findings at this stage are BLOCKED-escalations, not new work.

Depends: T33
Parallel: ⛓️
Complexity: native
Integration: true
Gate: python scripts/final_gate.py --check --json
Docs: CHANGELOG.md entry via the orchestrator Deltas mechanism (command contract changed); INDEX.md row for the new review artifact (orchestrator-applied)

## Touches
- docs/development/reviews/2026-08-31-plan-1-manifesto-command-pass-review.md — the whole-plan receipt

## Behavior Contract
- **Given** all 33 work tickets merged, **When** the whole-plan receipt runs `python scripts/final_gate.py --check --json` + `python scripts/enforcement/check_convergence.py` + `python scripts/enforcement/check_doc_sync.py` and /fabrik-docs-review over the corpus docs, **Then** every command's 63b verdict table exists (32/32 + fragments), the gate reports success, and the receipt records the per-ticket commit list (docs/reference/command-evaluation-checklist.md:158)

## Context Files
- docs/reference/command-evaluation-checklist.md
