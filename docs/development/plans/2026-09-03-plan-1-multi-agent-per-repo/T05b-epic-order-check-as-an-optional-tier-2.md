# T05b — epic_order --check as an optional Tier-2 gate check

## Scope
`scripts/final_gate.py`: register `python3 scripts/epic_order.py --check` as an optional Tier-2 check that runs ONLY when `docs/development/epics/` exists (audit R7 — the integrity proof exists but no gate ever runs it). An absent dir is SKIPPED, never silently passed. ⚠️ **TWO blockers an author-blind pass proved by execution, both of which must be handled IN this ticket or it cannot go green.** (1) `python3 scripts/epic_order.py --check` FAILS on the hub right now — `docs/development/epics/2026-07-14-epic-1-fleet-ci-deploy-debt.md: no frontmatter` — and the hub HAS `docs/development/epics/`, so the guard fires, `run_optional_check` returns not-passed, and this ticket's own `final_gate --check` gate becomes unsatisfiable. Either bring that legacy epic up to the schema or make the check skip files without frontmatter with a NAMED note, and say which. (2) `scripts/final_gate.py` is fleet-synced but `scripts/epic_order.py` is in NO manifest list and does not exist in any project (`ls /opt/transdoc/scripts/epic_order.py` → No such file), so an unconditional row would ship to ~46 repos pointing at a missing script. Make the registration hub-conditional, or add `epic_order.py` to the synced set — and state which in the Behavior Contract, because the two have very different blast radii. ⚠️ **The existing precedent is not quite what it looks like and the ticket must not copy it blindly:** `scripts/final_gate.py:929` appends `("bandit (NOT INSTALLED — skipped)", True, _skip_note("bandit"))` — a row whose boolean is **True**, i.e. it counts as a PASS carrying a skip LABEL, while `:772` emits the honest warning text "NOT INSTALLED — skipped, not passed; this green asserts nothing about …". So label-in-the-name plus True is the shipped shape. This ticket must therefore DEFINE which it means: follow the label convention (a True row named `epic_order --check (N/A — no docs/development/epics/)`) so the gate's own skip lines stay the reader's signal, and make the Behavior Contract assert the LABEL rather than a falsy result. Do not invent a third result state. One integrity finding must fail the check. SPLIT NOTE: T05's other half is T05a (the read budget — `final_gate.py` is 123 KB). DO-NOT: touch `scripts/epic_order.py` itself (T03) or the enforcement checks (T05a/T05d/T05e).

Depends: T03a
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
- **Given** the hub's own `docs/development/epics/` as it stands today, **When** `final_gate.py --check --json` runs after this ticket, **Then** the run is green — proving the legacy no-frontmatter epic was handled rather than left to red the gate (scripts/epic_order.py:83)
- **Given** a PROJECT that has no `scripts/epic_order.py`, **When** the gate runs there, **Then** the epic_order row does not appear at all, or appears skipped — never as a failure pointing at a missing script (scripts/final_gate.py:346)
- **Given** the dir present and integrity clean, **When** the gate runs, **Then** the check passes and the run's overall status is unchanged (scripts/final_gate.py:772)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/epic_order.py
