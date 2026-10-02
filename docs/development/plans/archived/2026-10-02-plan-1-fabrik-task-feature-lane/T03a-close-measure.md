# T03a — task_lane.py close: the per-commit measurement and its refusals

## Scope
Implements spec § The delta D1 (close column), D3, D4 (`over_appetite`) and § Lifecycle (unstamped records). Adds `measure_close` and `LaneRecord` per the spine § Interfaces `task_lane` API. Measurement is per commit in the given order with rename carry-over (today's single-commit rule is `scripts/command_run.py:3519-3541`; the caller passes name-status rows produced as at `:3363`, `--name-status -M -C`). The contract path test runs over EVERY committed path BEFORE the `excluded` predicate the caller passes (today's exclusion set is `:3216-3297`); new-source and contract use T02's `is_new_source` and `contract_hit`, never a second implementation. An unstamped record (no `gate: 2`) keeps today's behaviour: undeclared paths recorded as `oversized_mini` (`:3571-3572`), last commit only.

DO NOT import or edit `scripts/command_run.py` (T08), and DO NOT write the receipt checks (T03b).

Depends: T02
Parallel: ⛓️
Complexity: native
Appetite: 150
Gate: python -m pytest tests/test_task_lane_close.py -q
Docs: none

## Touches
- scripts/task_lane.py — PRIMARY PATH
- tests/test_task_lane_close.py

## Behavior Contract
- **Given** a stamped record whose commits add 3 new non-test, non-`.md` source files, one of them a copy (`C`), **When** `measure_close` runs, **Then** `upgrade` includes `new-source` and `needs_full_review` is true, and `classify_commit` on the same rows returns `chain: new-source` (spec § Validation V2)
- **Given** a stamped record declared `consumers=internal` whose commit touches `specs/services/x.yaml` that the `excluded` predicate would hide, **When** `measure_close` runs, **Then** `upgrade` includes `contract` and `needs_full_review` is true, and `classify_commit` on the same rows returns `chain: contract` (spec § Validation V3)
- **Given** a stamped record and a committed path named in neither the design nor an amendment, **When** `measure_close` runs for `done`, **Then** it refuses naming the path; after `--design-amend` names it, it passes with `design_amends: 1` and that path in `amended_paths`; for `blocked` or `handoff` the same path is recorded, never refused; the run's own receipt path is exempt (spec § Validation V4; § The delta D3.3)
- **Given** a design with 8 Behaviours, **When** `measure_close` runs, **Then** `upgrade` includes `behaviours`; with 7 it does not (spec § Validation V5)
- **Given** two commits where the first renames a declared file and the second edits the new name, **When** `measure_close` runs, **Then** the edit counts as declared; **Given** a record whose `sync_hits` is non-empty, **Then** more than one commit is refused, since a sync-path run commits once (spec § The delta D3.2, D7)
- **Given** a stamped record with appetite 60, **When** `measure_close` runs at 121 minutes, **Then** it records `over_appetite: true` and returns the UPGRADE line; at exactly 120 minutes it does not (spec § Validation V6)
- **Given** commits adding 801 lines, **When** `measure_close` runs, **Then** it records `loc_added: 801` and returns a `change:` finding, never a refusal; 800 returns no finding (spec § The delta D3.4)
- **Given** an UNSTAMPED record, **When** `measure_close` runs with two commits and an undeclared path, **Then** it measures the last commit only and lists the path in `oversized_mini`, never refused (spec § Lifecycle)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- docs/development/plans/archived/2026-10-02-plan-1-fabrik-task-feature-lane/2026-10-02-plan-1-fabrik-task-feature-lane.md
