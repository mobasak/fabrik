# T08 — Integration: wire task_lane into command_run.py, the hub lane table, distribution, hub opt-in

## Scope
Implements spec § The delta D12 (steps 3–4), § Contract deltas and § Lifecycle adoption. The orchestrator, in the main checkout, after T01–T07: `scripts/command_run.py` imports `task_lane` and maps its own facts into the API (sync hits from `_sync_filter_source`, `:2898`; the ledger at `_state_dir().parent / "lane-refusals.jsonl"`, `:84`; the exclusion set `:3216-3297`; the stack `:3752-3759`). `start` (the gate `_task_size_gate`, `:3019`): `consumers`, `--appetite`, `--why`, `--from-downgrade`, the `gate: 2` stamp (v2 only) and the `lane: v1|v2` line with the switch's commit; `step --design-amend` and `step --appetite`; `line` (elapsed/appetite and the order past 2×); `done --commit <sha>…` and `done`/`handoff --review <receipt>`; `round` (the stack-aware advisory, `scope_growth_warning` `:473`); a `--surface` refusal on `fabrik-spec-review`/`fabrik-plan-review` starts, at v2 only; feedback rows gain `parent`, `size`, `from_downgrade`, `design_amends`, `loc_added`, `over_appetite`, `upgrades`, `over_appetite_phases`, `phase_marks`, and `upgrade` keeps its single-token string (spine § Interfaces). When `done` or `handoff` carries `--review`, T08 calls `check_review_receipt` with the `--commit` SHAs; `measure_close` receives the receipt path only to exempt it. `task_lane.py` enters `CORE_SCRIPTS` (`scripts/fabrik_synced_manifest.py:37`) and the governance-sync regex (`.pre-commit-config.yaml:164`); `.fabrik/lane.json` enters neither. The hub `CLAUDE.md` lane table changes per D7, D2 and the module tests; the template's rows do NOT. `INDEX.md` rows (orchestrator-applied); commands rendered from master (render → `--check` → commit). The hub commits `.fabrik/lane.json` `{"version": 2}` alone; the day-7 evaluation and the flip are a work item with the D12 criterion. The whole-plan receipt.

DO NOT change the template's lane rows or `_LANE_DEFAULT` — the day-7 flip is a separate commit.

Depends: T04, T05a, T05b, T05c, T06, T07
Parallel: ⛓️
Complexity: native
Integration: true
Appetite: 180
Gate: python -m pytest tests/test_command_run_fabrik_task.py tests/test_command_run_lane_v2.py tests/test_lane_switch_not_synced.py -q && python scripts/final_gate.py --check --json
Docs: INDEX.md, CLAUDE.md

## Touches
- scripts/command_run.py
- scripts/fabrik_synced_manifest.py
- .pre-commit-config.yaml
- CLAUDE.md
- .fabrik/lane.json
- tests/test_command_run_fabrik_task.py
- tests/test_command_run_lane_v2.py
- tests/test_lane_switch_not_synced.py
- docs/development/reviews/2026-10-02-plan-1-fabrik-task-feature-lane-review.md

## Behavior Contract
- **Given** a repo with no `.fabrik/lane.json`, **When** `start`, `done`, `round` and a `fabrik-plan-review` `start` without `--surface` run, **Then** each behaves as before this plan, no `gate: 2` is stamped and `start` prints `lane: v1` (spec § The delta D12 OFF state)
- **Given** the hub with `.fabrik/lane.json` `{"version": 2}`, **When** a 6-file feature starts, **Then** it is admitted, stamped `gate: 2`, and `start` prints `lane: v2` and the commit that set the switch; `--why` with `tradeoffs=yes` writes a ledger row under the state dir's parent (spec § Validation V1, V9; W-25318990)
- **Given** a v2 record, **When** `done --commit A B` runs with an undeclared path, **Then** it is refused; after `step --phase 2 --design-amend <path>` it closes; a contract hit at close refuses `done` and `handoff` until `--review <receipt>` names a valid full-review receipt, and `blocked` closes without one (spec § Validation V2–V4; § The delta D1; W-0a89f069)
- **Given** a `/fabrik-review` record nested under a running `/fabrik-task`, **When** `round` records an own-fix-only round 2, **Then** the advisory prints the stop; the same rounds without the `fabrik-task` parent print nothing (spec § Validation V8)
- **Given** a `fabrik-task` started `--appetite 60` and an execute-plan phase started `step --appetite 30`, **When** `line` runs at 121 and 61 minutes, **Then** each prints elapsed/appetite and the re-plan order; the closes record `over_appetite` and `over_appetite_phases: 1` with `phase_marks` (spec § Validation V6, V10)
- **Given** a v2 repo, **When** `fabrik-spec-review` or `fabrik-plan-review` starts without `--surface`, **Then** it is refused naming the flag; a `fabrik-task` started `--from-downgrade <id>` closes with `from_downgrade: <id>`, its feedback row also carries `design_amends`, `loc_added`, the single-token `upgrade` and the space-joined `upgrades` from the close, and an evidence `UPGRADE: sync` still writes `upgrade: sync`, a `/fabrik-spec` close on a spec carrying `Size: small` writes `size: small`, and a nested review's row carries `parent: fabrik-task` (W-25318990; spec § Validation kill rules)
- **Given** the manifest, the governance-sync regex and the hub enable commit, **When** they are read, **Then** `scripts/task_lane.py` is in both, `.fabrik/lane.json` is in neither, and the enable commit's only path is `.fabrik/lane.json`, so it distributes nothing (spec § The delta D12)
- **Given** the hub `CLAUDE.md`, **When** the lane table is read, **Then** row 5 is the module tests, rows 1 and 1b send sync and heavy work into the lane with the full review, and every UNIVERSAL anchor is still present; **Given** every ticket merged, **Then** the lane test files pass and the next real hub `/fabrik-task` closes under `lane: v2` (spec § Contract deltas; § Validation V0)

## Context Files
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- docs/development/plans/archived/2026-10-02-plan-1-fabrik-task-feature-lane/2026-10-02-plan-1-fabrik-task-feature-lane.md
- scripts/task_lane.py
- INDEX.md
