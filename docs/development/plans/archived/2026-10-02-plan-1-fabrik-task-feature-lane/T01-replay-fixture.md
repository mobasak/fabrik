# T01 — The replay fixture, pinned before any gate code

## Scope
Implements spec § The delta D12 step (1). Captures, once, the name-status of every commit the spec measured — the hub's last 300 non-merge commits ending `c84f0b0b7`, the four project repos' last 200 (tojlo-mail's 137), and the web-ecommerce-factory wef1 commit — into `tests/fixtures/lane_replay.json`, each commit carrying its repo kind (`hub` or `project`), its `-M -C` name-status rows, and its EXPECTED verdict string from the closed set named in the spine § Interfaces `task_lane` API (`classify_commit`). The 20 `/fabrik-task` rows (declared files and outcomes) are handed to the coder by the orchestrator as `tests/fixtures/lane_replay_tasks.json`; the coder never reads `$HOME`. The capture script `scripts/lane_replay_capture.py` is read-only git (`git -C <repo> log --no-merges -n <N> --name-status -M -C --format=...`) so the fixture can be re-derived. The governance-sync regex the expected hub verdicts assume is the `files:` scalar at `.pre-commit-config.yaml:164`, copied into the fixture's header with the commit it was read at.

DO NOT write any classifier logic or the replay test here — the test is T02's (the seam's consumer), and DO NOT read `$HOME`.

Depends: —
Parallel: ⚡
Complexity: native
Appetite: 60
Gate: python -m pytest tests/test_lane_replay_capture.py -q && python scripts/lane_replay_capture.py --check tests/fixtures/lane_replay.json
Docs: none

## Touches
- scripts/lane_replay_capture.py — PRIMARY PATH
- tests/fixtures/lane_replay.json
- tests/fixtures/lane_replay_tasks.json
- tests/test_lane_replay_capture.py

## Behavior Contract
- **Given** the capture script run against `/opt/fabrik` ending at `c84f0b0b7` and the four project repos, **When** the fixture is written, **Then** it holds exactly 300 hub commits and each project repo's last 200 commits (tojlo-mail's 137, its whole history) with `-M -C` status letters, and `--check` re-derives the same rows (spec § What exists today item 7; § The delta D12 (1))
- **Given** the fixture, **When** each commit's expected verdict is read, **Then** it is one of the closed verdict set in the spine § Interfaces, the wef1 commit is `lane`, and the two historical handoffs not caused by the file count keep the verdicts they routed to (spec § Validation V0)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- docs/development/plans/archived/2026-10-02-plan-1-fabrik-task-feature-lane/2026-10-02-plan-1-fabrik-task-feature-lane.md
- .pre-commit-config.yaml
