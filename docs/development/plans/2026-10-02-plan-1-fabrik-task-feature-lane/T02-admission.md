# T02 — task_lane.py admission: the module test, the switch, the refusal ledger, the replay

## Scope
Implements spec § The delta D1 (start column), D2, D4 (the declaration), D7, D9 (`--why`, the refusal ledger) and D12 (`_LANE_DEFAULT`, `.fabrik/lane.json`). Creates `scripts/task_lane.py` with the admission half of the spine § Interfaces `task_lane` API: `lane_version`, `admit`, `classify_commit`, `record_refusal`, and the three path helpers every later rule reuses — `contract_hit`, `is_new_source`, `is_migration`. The module is PURE: it never imports `scripts/command_run.py` (277 KB, outside every ticket's READ budget but T08's) — the sync-path hits, the ledger path and the git root arrive as arguments, and T08 computes them (today's sync reader is `_sync_filter_source`, `scripts/command_run.py:2898`; the state dir is `_state_dir`, `:84`). `admit` replaces only the file-count arm (`_TASK_MAX_FILES = 3`, `scripts/command_run.py:2809`, applied at `:3178-3192`); every other arm keeps today's verdict. Writes `tests/test_lane_replay.py` FIRST (red, against T01's fixture), then the code.

DO NOT import or edit `scripts/command_run.py` (T08 wires it), and DO NOT implement any close rule (T03a).

Depends: T01
Parallel: ⛓️
Complexity: native
Appetite: 120
Gate: python -m pytest tests/test_task_lane_admission.py tests/test_lane_replay.py -q
Docs: none (docs are T07's)

## Touches
- scripts/task_lane.py — PRIMARY PATH
- tests/test_task_lane_admission.py
- tests/test_lane_replay.py

## Behavior Contract
- **Given** version 2 and a feature declaring 6 existing files and 2 new source files, no contract path, `oneway=no`, `tradeoffs=no`, appetite 120, **When** `admit` runs, **Then** the route is `lane` with review `full` (more than 5 files selects the full review); with 4 files, review `scoped` (spec § Validation V1; § The delta D2)
- **Given** a declared `--file` `specs/services/x.yaml` (repo root — the Fabrik spec location), `api/openapi.yaml`, `api/openapi-v2.json` or `web/x.schema.json`, or `consumers=external`, **When** `admit` runs, **Then** the route is `chain: contract`; the same names under `node_modules/`, `.venv/` or `vendor/` path SEGMENTS are not hits, while `myvendor/` and `node_modules_old/` are NOT exclusions (`myvendor/openapi.yaml` is a hit), and `api/openapi.yml` (the spec lists `.json`/`.yaml` only), `apps/x/specs/services/y.yaml` and `x.schema.json.bak` are not hits; the basename patterns match case-INSENSITIVELY, so `api/OpenAPI.yaml` and `web/X.Schema.JSON` are hits; and `consumers=internal` never removes a hit (spec § The delta D1)
- **Given** `tradeoffs=yes` or `oneway=yes` without `--why`, **When** `admit` runs, **Then** it refuses naming the missing reason; with `--why`, the route is `chain` and `record_refusal` appends one row with an id, the git common dir, the declared keys, `--why` and the `--file` list to the ledger path it was given (spec § The delta D9; § Validation V9)
- **Given** appetite 240 or no appetite, **When** `admit` runs, **Then** it is admitted (default 240); 241 routes `chain: appetite`; 0, a negative or a non-integer value is refused naming the flag (spec § The delta D1, D4)
- **Given** version 2 and a declared path in the `sync_hits` set, or `heavy=yes`, or a migration path segment (`migrations/`, `alembic/versions/` at any depth), **When** `admit` runs, **Then** the route is `lane` with review `full`; at version 1 a sync hit or `heavy=yes` keeps today's `right-now + /fabrik-review` disposition and `decision=no` keeps today's `right-now + /fabrik-review-scoped` at both versions (spec § The delta D2, D7)
- **Given** no `.fabrik/lane.json`, **When** `lane_version` runs, **Then** it returns `(1, None, None)` from `_LANE_DEFAULT = 1`; with `{"version": 2}` committed it returns 2 and the commit that last set it; invalid JSON, an unknown version or a string version return 1 with a warning naming the file, and an uncommitted file returns its version with commit `None` (spec § The delta D12; W-25318990)
- **Given** T01's fixture, **When** `tests/test_lane_replay.py` runs `classify_commit` over every commit and `admit` over the 20 task rows, **Then** every pinned verdict matches — written and seen RED before `classify_commit` exists (spec § Validation V0; § The delta D12 (1))

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- docs/development/plans/2026-10-02-plan-1-fabrik-task-feature-lane/2026-10-02-plan-1-fabrik-task-feature-lane.md
- tests/fixtures/lane_replay.json
- tests/fixtures/lane_replay_tasks.json
