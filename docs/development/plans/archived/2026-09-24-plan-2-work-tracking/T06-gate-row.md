# T06 — the completion gate's advisory `work.py sync --check` row

## Scope

Implements "It joins the completion gate as an ADVISORY row first" (spec § Spec and plan state is
derived, never copied, the paragraph under the class list). One `run_optional_check` call in
`scripts/final_gate.py`'s Tier-2 block (`if tier == 2:` at `scripts/final_gate.py:1948`):
`run_optional_check("scripts/work.py", "Work items (sync)", "sync", "--check", advisory=True)`.

`advisory=True`, NOT `warn_only=True`: `warn_only` declares a check with no failing exit path, and a
`warn_only` check that exits non-zero still fails the gate as a broken contract
(`scripts/final_gate.py:436-440`). `sync --check` has a real failing path once a repo is blocking
(T02), so `advisory=True` — stdout kept on exit 0, a real red once blocking — is the honest flag.
A project without `scripts/work.py` gets the existing `⚠ check not present, skipping` row
(`scripts/final_gate.py:451-458`); one without `.fabrik/work/` gets `sync --check`'s one-line exit 0.

The tier-composition declaration `<!-- GATE-COUNTS: tier1=36 tier2=55 tier3=22 every-tier=14 -->`
(`docs/workflows/FINAL_GATE_WORKFLOW.md:144`) moves to `tier2=56`, and the doc's Tier-2 check list gains
the row, in the same change: `tests/test_final_gate_tier_counts.py` compares instrumented execution
against that line.

DO-NOT: any other gate row; `scripts/work.py` (T02 owns `sync --check`).

Depends: T02
Parallel: ⚡
Complexity: never-route
Gate: .venv/bin/python -m pytest tests/test_final_gate_work_row.py tests/test_final_gate_tier_counts.py -q
Docs: docs/workflows/FINAL_GATE_WORKFLOW.md (the GATE-COUNTS line and the Tier-2 list)

## Touches
- scripts/final_gate.py — PRIMARY PATH
- docs/workflows/FINAL_GATE_WORKFLOW.md
- tests/test_final_gate_work_row.py (new)

## Behavior Contract
- **Given** a repo with an initialised store and class-3 drift, not yet blocking, **When** the Tier-2 gate runs, **Then** the `Work items (sync)` row passes and its output names the drift (spec § Spec and plan state is derived, never copied)
- **Given** a blocking repo with class-3 drift, **When** the Tier-2 gate runs, **Then** the row fails and the gate status is not success (spec § Lifecycle)
- **Given** a repo with no `.fabrik/work/`, **When** the Tier-2 gate runs, **Then** the row passes with the one-line no-store message (spec § The CLI)
- **Given** the merged gate, **When** `tests/test_final_gate_tier_counts.py` runs, **Then** the instrumented Tier-2 count equals the declared `tier2` (docs/workflows/FINAL_GATE_WORKFLOW.md:144)

## Context Files
- tests/test_final_gate_tier_counts.py — how rows are counted (instrumented `run_consistency_checks`)
- docs/development/plans/2026-09-24-plan-2-work-tracking/T02-status-and-drift.md — the producer's `sync --check` exit contract
