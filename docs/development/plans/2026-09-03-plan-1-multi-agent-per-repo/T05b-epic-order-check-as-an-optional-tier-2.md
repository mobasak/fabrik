# T05b — epic_order --check as an optional Tier-2 gate check

## Scope
`scripts/final_gate.py`: register `python3 scripts/epic_order.py --check` as an optional Tier-2 check that runs ONLY when `docs/development/epics/` exists (audit R7 — the integrity proof exists but no gate ever runs it). An absent dir is SKIPPED with the same `(N/A)` shape the gate already uses for a conditional check, never silently passed — the gate's own skip lines are what a reader trusts (`scripts/final_gate.py:772` emits "NOT INSTALLED — skipped, not passed; this green asserts nothing about …" and `:929` is the result row `("bandit (NOT INSTALLED — skipped)", True, …)` — the precedent). One integrity finding must fail the check. SPLIT NOTE: T05's other half is T05a (the read budget — `final_gate.py` is 123 KB). DO-NOT: touch `scripts/epic_order.py` itself (T03) or the two enforcement checks (T05a).

Depends: T03
Parallel: ⛓️
Complexity: never-route
Gate: python scripts/final_gate.py --check --json
Gate: python -m pytest tests/enforcement/test_final_gate_epic_order.py -q
Docs: docs/workflows/FINAL_GATE_WORKFLOW.md (the optional-check row) · CHANGELOG.md · INDEX.md (new test) — orchestrator-applied

## Touches
- scripts/final_gate.py — PRIMARY PATH
- tests/enforcement/test_final_gate_epic_order.py
- docs/workflows/FINAL_GATE_WORKFLOW.md

## Behavior Contract
- **Given** a project without `docs/development/epics/`, **When** `final_gate.py --check --json` runs, **Then** the epic_order check appears as skipped, never as passed (scripts/final_gate.py:772)
- **Given** a project WITH the dir and one integrity finding, **When** the gate runs, **Then** that check reports failure and the finding text reaches the JSON (scripts/final_gate.py:929)
- **Given** the dir present and integrity clean, **When** the gate runs, **Then** the check passes and the run's overall status is unchanged (scripts/final_gate.py:772)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/epic_order.py
