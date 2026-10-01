# T08 — Integration: wire task_lane into command_run.py, the hub lane table, distribution, hub opt-in

## Scope
Implements spec § The delta D12 (steps 3–4), § Contract deltas and § Lifecycle adoption. The orchestrator, in the main checkout, after T01–T07: `scripts/command_run.py` calls `task_lane` from `start` (the gate at `:3019`; prints `lane: v1|v2`, accepts `consumers`, `--appetite`, `--why`, `--from-downgrade`), `step` (`--design-amend`, `--appetite`, phase starts), `line` (elapsed/appetite and the order past 2×), `done`/`handoff` (`--commit` list, `--review`), `round` (the stack-aware scope-growth advisory); feedback rows gain `parent`, `size`, `over_appetite_phases`, `phase_marks`; `task_lane.py` enters `CORE_SCRIPTS` (`scripts/fabrik_synced_manifest.py:37`) and the governance-sync regex (`.pre-commit-config.yaml:164`), while `.fabrik/lane.json` enters neither (a grader asserts it). The hub `CLAUDE.md` lane table changes per D7, D2 and the module tests (rows 1, 1b, 2, 5, 6 and the precedence paragraph); the template's rows do NOT change in this plan. `INDEX.md` rows for every new file (orchestrator-applied); commands rendered from master. The hub commits `.fabrik/lane.json` `{"version": 2}`; the day-7 evaluation and the default-flip commit are a work item with the D12 criterion, not part of this plan. Mails to fabrik-lib-sentinel and Volkan's port with the rule text. The whole-plan receipt.

DO NOT change the template's lane rows or `_LANE_DEFAULT` — the day-7 flip is a separate commit.

Depends: T04, T05a, T05b, T05c, T06, T07
Parallel: ⛓️
Complexity: native
Integration: true
Appetite: 180
Gate: python scripts/final_gate.py --check --json
Docs: INDEX.md, CLAUDE.md

## Touches
- scripts/command_run.py
- scripts/fabrik_synced_manifest.py
- .pre-commit-config.yaml
- CLAUDE.md
- .fabrik/lane.json
- tests/test_command_run_fabrik_task.py
- tests/test_lane_switch_not_synced.py
- docs/development/reviews/2026-10-02-plan-1-fabrik-task-feature-lane-review.md

## Behavior Contract
- **Given** a repo with no `.fabrik/lane.json`, **When** `command_run.py start --command fabrik-task` and `done` run, **Then** they behave exactly as before this plan and `start` prints `lane: v1` (spec § The delta D12 OFF-state grader)
- **Given** the hub with `.fabrik/lane.json` `{"version": 2}`, **When** a 6-file feature starts, **Then** it is admitted and `start` prints `lane: v2` and the commit that set the switch (spec § Validation V1; W-25318990)
- **Given** the manifest and the governance-sync regex, **When** they are read, **Then** `scripts/task_lane.py` is in both and `.fabrik/lane.json` is in neither (spec § The delta D12)
- **Given** the hub `CLAUDE.md`, **When** the lane table is read, **Then** row 5 is the module tests, rows 1 and 1b send sync and heavy work into the lane with the full review, and every UNIVERSAL anchor is still present (spec § Contract deltas)
- **Given** an execute-plan record whose phase 2 declared `--appetite 30` and ran 70 minutes, **When** the run closes, **Then** the feedback row carries `over_appetite_phases: 1` and `phase_marks`, and `line` printed the re-plan order past 60 minutes (spec § Validation V10)
- **Given** a `/fabrik-spec-review` or `/fabrik-plan-review` `start` without `--surface`, **When** it runs, **Then** it is refused naming the flag, so every review row carries the spec path the D10 kill rule joins on (W-25318990)
- **Given** a `/fabrik-task` started with `--from-downgrade <id>`, **When** it closes, **Then** its feedback row carries that refusal id, and a nested review's row carries `parent: fabrik-task` (spec § Validation kill rules; § The delta D8)
- **Given** every ticket merged, **When** the T01 replay test and the full lane test files run, **Then** all pass, and the next real hub `/fabrik-task` run closes under `lane: v2` (spec § Validation V0)

## Context Files
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- INDEX.md
