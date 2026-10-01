# T06 — The feedback report reads the lane's new fields

## Scope
Implements spec § Validation (the 30-day measures and the kill-rule joins) and § The delta D9 (shares). `scripts/command_feedback_report.py` (`queue` `scripts/command_feedback_report.py:1374`, row loader `:82`) gains a `--lane` view reading the feedback field names fixed in the spine § Interfaces and the refusal ledger: per agent, the refused and downgraded shares; the task median, the UPGRADE share (rows with a non-empty `upgrade`, as today) and the downgrade-then-upgrade share (a task row carrying a `from_downgrade` id and a non-empty `upgrade`), with the per-token split read from `upgrades`; the in-lane full-review median (rows whose `parent` is `fabrik-task`); small specs sent back to spec-review (a spec row with `size: small` followed by a `fabrik-spec-review` row whose `surface` contains that spec path); per-repo `lane.json` pins; and the over-appetite share from `over_appetite_phases` over `phase_marks` (never the declared `phases` count; W-25318990). Downgraded `/fabrik-spec` runs are excluded from the task-to-spec ratio.

DO NOT reuse the declared `phases` field for appetite data.

Depends: T03b
Parallel: ⛓️
Complexity: native
Appetite: 90
Gate: python -m pytest tests/test_command_feedback_report_lane.py tests/test_command_feedback_report.py -q
Docs: none

## Touches
- scripts/command_feedback_report.py — PRIMARY PATH
- tests/test_command_feedback_report_lane.py

## Behavior Contract
- **Given** fixture rows and a refusal ledger, **When** `command_feedback_report.py --lane` runs, **Then** it prints per agent the refused and downgraded shares, and the task-to-spec ratio excludes downgraded spec runs (spec § The delta D9)
- **Given** task rows with durations, `upgrade` values and `from_downgrade` ids, **When** the report runs, **Then** it prints the task median, the UPGRADE share and the share of downgraded tasks that later upgraded (spec § Validation 30-day; kill rules)
- **Given** review rows with and without `parent: fabrik-task`, **When** the report runs, **Then** the in-lane full-review median uses only the former (spec § Validation 30-day)
- **Given** a spec row with `size: small`, a later `fabrik-spec-review` row whose `surface` contains that spec path, and a `fabrik-plan-review` row that does too, **When** the report runs, **Then** only the first counts as sent back to spec-review (spec § Validation kill rules; W-25318990)
- **Given** execute-plan rows carrying `over_appetite_phases` and `phase_marks`, **When** the report runs, **Then** it prints the over-appetite share without reading `phases`, and counts `lane.json` pins per repo (W-25318990)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- docs/development/plans/2026-10-02-plan-1-fabrik-task-feature-lane/2026-10-02-plan-1-fabrik-task-feature-lane.md
- scripts/command_feedback_report.py
