# T03 — task_lane.py close: re-checks, the refusal, multi-commit, the review receipt

## Scope
Implements spec § The delta D1 (close column), D3 (Behaviours cap, multi-commit, undeclared-path refusal with `--design-amend`, `loc_added`), D4 (`over_appetite`), and the receipt checks (a)–(d). `task_lane.measure_close(record, commits, repo) -> CloseVerdict`: per-commit `--name-status -M -C` measurement in the given order with rename carry-over (today's single-commit rule is `scripts/command_run.py:3519-3541`); contract path test over EVERY committed path before exclusions (today's exclusion set `:3216-3297`); new-source counts `A` and `C` (today's diff flags `:3363`); undeclared paths REFUSE for a v2 record unless named in the design or an amendment, and the receipt path itself is exempt; `upgrade: contract|new-source|behaviours` recorded by the close; `check_review_receipt(path, commits)` enforces (a) under `docs/development/reviews/`, (b) `check_review_coverage.py` passes, (c) `**Command:**` is exactly `/fabrik-review`, (d) a `range tip` equal to the last listed commit. `scripts/review_receipt.py` gains `--command` (W-0a89f069: `:138` hard-codes `/fabrik-review`) and `--lane` (writes `**Lane:** fabrik-task`). A v1 record keeps today's behaviour (`oversized_mini` recorded, `:3571-3572`).

DO NOT edit `scripts/command_run.py` (T08) or change the v1 close behaviour.

Depends: T02
Parallel: ⛓️
Complexity: native
Appetite: 180
Gate: python -m pytest tests/test_task_lane_close.py tests/test_review_receipt*.py -q
Docs: none

## Touches
- scripts/task_lane.py — PRIMARY PATH
- scripts/review_receipt.py
- tests/test_task_lane_close.py

## Behavior Contract
- **Given** a v2 record whose commits add 3 new non-test source files, one of them a copy (`C`), **When** `measure_close` runs, **Then** it records `upgrade: new-source` and requires a full-review receipt (spec § Validation V2)
- **Given** a v2 record declared `consumers=internal` whose commit touches `specs/services/x.yaml` that a Doc Sync exclusion would hide, **When** `measure_close` runs, **Then** the hit is found and `done` needs a full-review receipt (spec § Validation V3)
- **Given** a committed path named in neither the design nor an amendment, **When** `measure_close` runs for a v2 record, **Then** it refuses; after `--design-amend` naming it, it passes and records `design_amends: 1` with the path; for a v1 record the same path is recorded as `oversized_mini`, never refused (spec § Validation V4; § The delta D3.3; § Lifecycle)
- **Given** a design with 8 Behaviours, **When** `measure_close` runs, **Then** it records `upgrade: behaviours` (spec § Validation V5)
- **Given** two commits where the first renames a declared file and the second edits the new name, **When** `measure_close` runs, **Then** the edit counts as declared and no other session's commit is read (spec § The delta D3.2)
- **Given** a receipt outside `docs/development/reviews/`, failing coverage, carrying `/fabrik-review-scoped`, or without the last commit as its range tip, **When** `check_review_receipt` runs, **Then** each is refused; a valid one passes, and the receipt's own commit is not in the `--commit` list (spec § The delta D1 checks (a)–(d); W-0a89f069)
- **Given** `review_receipt.py --command /fabrik-review-scoped --lane`, **When** the receipt is written, **Then** its `**Command:**` line carries the real command and a `**Lane:** fabrik-task` line is present (W-0a89f069)
- **Given** a v2 record with appetite 60 closing after 130 minutes, **When** `measure_close` runs, **Then** it records `over_appetite: true` and returns the UPGRADE line to print (spec § Validation V6)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- scripts/review_receipt.py
