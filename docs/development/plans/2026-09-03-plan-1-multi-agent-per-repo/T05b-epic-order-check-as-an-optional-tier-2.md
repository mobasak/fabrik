# T05b — epic_order --check as an optional Tier-2 gate check

## Scope
`scripts/final_gate.py`: register `python3 scripts/epic_order.py --check` as an optional Tier-2 check that runs ONLY when `docs/development/epics/` exists (audit R7 — the integrity proof exists but no gate ever runs it). An absent dir is SKIPPED, never silently passed. ⚠️ **The existing precedent is not quite what it looks like and the ticket must not copy it blindly:** `scripts/final_gate.py:929` appends `("bandit (NOT INSTALLED — skipped)", True, _skip_note("bandit"))` — a row whose boolean is **True**, i.e. it counts as a PASS carrying a skip LABEL, while `:772` emits the honest warning text "NOT INSTALLED — skipped, not passed; this green asserts nothing about …". So label-in-the-name plus True is the shipped shape. This ticket must therefore DEFINE which it means: follow the label convention (a True row named `epic_order --check (N/A — no docs/development/epics/)`) so the gate's own skip lines stay the reader's signal, and make the Behavior Contract assert the LABEL rather than a falsy result. Do not invent a third result state. One integrity finding must fail the check. SPLIT NOTE: T05's other half is T05a (the read budget — `final_gate.py` is 123 KB). DO-NOT: touch `scripts/epic_order.py` itself (T03) or the two enforcement checks (T05a).

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
- **Given** a project without `docs/development/epics/`, **When** `final_gate.py --check --json` runs, **Then** the epic_order result row carries an explicit `(N/A — no docs/development/epics/)` skip label, matching the shipped convention at `:929` rather than silently reading as an ordinary pass (scripts/final_gate.py:929)
- **Given** a project WITH the dir and one integrity finding, **When** the gate runs, **Then** that check reports failure and the finding text reaches the JSON (scripts/final_gate.py:929)
- **Given** the dir present and integrity clean, **When** the gate runs, **Then** the check passes and the run's overall status is unchanged (scripts/final_gate.py:772)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/epic_order.py
