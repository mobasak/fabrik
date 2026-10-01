# T06 — The feedback report reads the lane's new fields

## Scope
Implements spec § Validation (30-day measures) and § The delta D9 (shares). `scripts/command_feedback_report.py` (`queue` `:1374`, row loader `:82`) gains a `--lane` view: per agent, the share of lane starts refused to the chain and the share downgraded (from `lane-refusals.jsonl` and `handoff` rows whose reason begins `DOWNGRADE:`); in-lane full-review medians (rows whose `parent` is `fabrik-task`); `size` on spec rows joined to later spec-review/plan-review rows by spec-path prefix of `surface`; per-repo `lane.json` pins; and `over_appetite_phases` out of `phase_marks` (a new name — `phases` is already the declared phase count, `scripts/command_run.py:4932`; W-25318990). Downgraded `/fabrik-spec` runs are excluded from the task-to-spec ratio.

DO NOT reuse the declared `phases` field for appetite data.

Depends: T03
Parallel: ⛓️
Complexity: native
Appetite: 90
Gate: python -m pytest tests/test_command_feedback_report*.py -q
Docs: none

## Touches
- scripts/command_feedback_report.py — PRIMARY PATH
- tests/test_command_feedback_report_lane.py

## Behavior Contract
- **Given** fixture rows and a refusal ledger, **When** `command_feedback_report.py --lane` runs, **Then** it prints per agent the refused and downgraded shares, and the task-to-spec ratio excludes downgraded spec runs (spec § The delta D9)
- **Given** review rows with and without `parent: fabrik-task`, **When** the report runs, **Then** the in-lane full-review median uses only the former (spec § Validation)
- **Given** a spec row with `size: small` and later review rows whose `surface` starts with that spec path, **When** the report runs, **Then** it counts the spec as sent back to spec-review only when a spec-review row follows (spec § Validation kill rules; W-25318990)
- **Given** execute-plan rows carrying `over_appetite_phases` and `phase_marks`, **When** the report runs, **Then** it prints the over-appetite share without reading the declared `phases` field (W-25318990)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- scripts/command_feedback_report.py
