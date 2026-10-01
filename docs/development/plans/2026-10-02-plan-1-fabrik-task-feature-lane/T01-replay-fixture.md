# T01 — The replay fixture, pinned before any gate code

## Scope
Implements spec § The delta D12 step (1). Captures, once, the name-status of every commit the spec measured — the hub's last 300 non-merge commits ending `c84f0b0b7`, the four project repos' last 200 (tojlo-mail's 137), and the web-ecommerce-factory wef1 commit — into a JSON fixture, plus the 20 `/fabrik-task` rows' declared files and outcomes (from the feedback ledger, read by the orchestrator; seats never read `$HOME`). `tests/test_lane_replay.py` loads the fixture and asserts each commit's verdict under the new rule by calling `scripts/task_lane.py`'s classifier, which does not exist yet: the test is RED by construction until T02. The capture script is kept so the fixture can be re-derived (`scripts/lane_replay_capture.py`, read-only `git log`/`show --name-status -M -C`). Grounding: the replay method is spec § What exists today item 6; the governance-sync regex it reuses is `.pre-commit-config.yaml:164`.

DO NOT write any classifier logic here, and DO NOT read `$HOME` — the 20 task rows arrive as a file from the orchestrator.

Depends: —
Parallel: ⚡
Complexity: native
Appetite: 60
Gate: python -m pytest tests/test_lane_replay.py -q (expected RED until T02 — the red run is this ticket's evidence)
Docs: none

## Touches
- scripts/lane_replay_capture.py — PRIMARY PATH
- tests/fixtures/lane_replay.json
- tests/test_lane_replay.py

## Behavior Contract
- **Given** the capture script run against `/opt/fabrik` at `c84f0b0b7` and the four project repos, **When** the fixture is written, **Then** it holds exactly 300 hub commits and 62/62/86/97 non-docs-only project commits with their status letters from `-M -C` (spec § What exists today item 7)
- **Given** the fixture, **When** `tests/test_lane_replay.py` runs before T02, **Then** it fails on the missing classifier, never on the data (spec § The delta D12 (1))
- **Given** the wef1 commit in the fixture, **When** its pinned verdict is read, **Then** it is `lane` (admitted), and the two non-file historical handoffs are pinned `chain` and `seat` as before (spec § Validation V0)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- .pre-commit-config.yaml
