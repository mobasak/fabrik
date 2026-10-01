# T02 — task_lane.py admission: the module test, the switch, the refusal ledger

## Scope
Implements spec § The delta D1 (start column), D4 (appetite declaration), D7 (sync admitted in the hub lane), D9 (`--why`, refusal ledger, `--from-downgrade`) and D12 (`_LANE_DEFAULT`, `.fabrik/lane.json`, `lane: v1|v2`). A NEW module `scripts/task_lane.py` — `command_run.py` is 277 KB, above a ticket's READ budget, so the lane logic lives beside it and only T08 wires it in. It replaces the file-count rule of `scripts/command_run.py:2809` (`_TASK_MAX_FILES = 3`, applied at `:3178-3192`) with `admit(declared, files, repo) -> Verdict`: the contract path test (`specs/services/`, `openapi*.json|yaml`, `*.schema.json` at any depth, outside `node_modules/`, `.venv/`, `vendor/`), `oneway`/`tradeoffs` requiring `--why`, appetite > 240 → chain, sync paths → lane + full review in a v2 repo (D7) and today's row-1 disposition in a v1 repo, heavy → lane + full review (D2). `lane_version(repo)` reads `.fabrik/lane.json` else `_LANE_DEFAULT = 1`. `record_refusal(...)` appends to `_state_dir().parent / "lane-refusals.jsonl"` keyed by the git common dir (`scripts/command_run.py:84` for `_state_dir`). Residual W-25318990: `lane_version` also returns the commit that last set `lane.json` so `start` can echo it.

DO NOT edit `scripts/command_run.py` (T08 wires it) or the close rules (T03).

Depends: T01
Parallel: ⛓️
Complexity: native
Appetite: 120
Gate: python -m pytest tests/test_task_lane_admission.py -q
Docs: none (docs are T07's)

## Touches
- scripts/task_lane.py — PRIMARY PATH
- tests/test_task_lane_admission.py

## Behavior Contract
- **Given** a v2 repo and a feature declaring 6 existing files and 2 new source files, no contract path, `oneway=no`, `tradeoffs=no`, appetite 120, **When** `admit` runs, **Then** the verdict is `lane` (spec § Validation V1)
- **Given** a declared file `specs/services/x.yaml`, or `api/openapi.yaml`, or `web/x.schema.json`, **When** `admit` runs, **Then** the verdict is `chain: contract`; the same names under `node_modules/` are ignored (spec § The delta D1)
- **Given** `tradeoffs=yes` or `oneway=yes` without `--why`, **When** `admit` runs, **Then** it refuses naming the missing reason; with `--why`, the verdict is `chain` and a refusal row with an id, the git common dir, the declared keys, `--why` and the `--file` list is appended to the ledger (spec § The delta D9; § Validation V9)
- **Given** appetite 300, **When** `admit` runs, **Then** the verdict is `chain: appetite` (spec § The delta D1)
- **Given** a hub-v2 repo and a declared governance-sync path, **When** `admit` runs, **Then** the verdict is `lane: full-review`; in a v1 repo the verdict is today's `right-now + /fabrik-review` (spec § The delta D7)
- **Given** no `.fabrik/lane.json`, **When** `lane_version` runs, **Then** it returns 1 (`_LANE_DEFAULT`); with `{"version": 2}` it returns 2 and the commit that set it (spec § The delta D12; W-25318990)
- **Given** the T01 fixture, **When** `tests/test_lane_replay.py` runs, **Then** every pinned verdict matches (spec § Validation V0)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- tests/fixtures/lane_replay.json
