# T03b — The close's review receipt: the real command, the lane marker, checks (a)–(d)

## Scope
Implements spec § The delta D1's receipt checks (a)–(d) and W-0a89f069. Adds `check_review_receipt` per the spine § Interfaces `task_lane` API: (a) the path is under `docs/development/reviews/`; (b) `python3 scripts/enforcement/check_review_coverage.py --root <root> <receipt>` exits 0 (its CLI, `scripts/enforcement/check_review_coverage.py:3009-3040`, run as a subprocess — the 185 KB checker is never read); (c) the command token on its `**Command:**` line — the text after `**Command:** ` up to the next ` · ` — is exactly `/fabrik-review`; (d) its `range tip` resolves (`git rev-parse`) to the same full SHA as the last `--commit`. `scripts/review_receipt.py` gains `--command` (today `scripts/review_receipt.py:138` hard-codes `/fabrik-review`) restricted to `/fabrik-review` and `/fabrik-review-scoped`, and `--lane`, which writes the exact line `**Lane:** fabrik-task`.

DO NOT edit `scripts/command_run.py` (T08 wires `done`/`handoff --review`), and DO NOT change `check_review_coverage.py` (T04).

Depends: T03a
Parallel: ⛓️
Complexity: native
Appetite: 60
Gate: python -m pytest tests/test_task_lane_receipt.py tests/test_review_receipt.py -q
Docs: none

## Touches
- scripts/task_lane.py
- scripts/review_receipt.py — PRIMARY PATH
- tests/test_task_lane_receipt.py
- tests/test_review_receipt.py

## Behavior Contract
- **Given** a receipt outside `docs/development/reviews/`, one failing `check_review_coverage.py`, one whose command token is `/fabrik-review-scoped` (which starts with `/fabrik-review`), and one whose range tip is not the last commit, **When** `check_review_receipt` runs, **Then** each is refused with its own reason; a valid one passes (spec § The delta D1 checks (a)–(d))
- **Given** a range tip written as a short SHA of the last commit, **When** check (d) runs, **Then** it passes; a short SHA of an earlier commit is refused (spec § The delta D1 (d))
- **Given** `review_receipt.py --command /fabrik-review-scoped --lane`, **When** the receipt is written, **Then** its `**Command:**` line carries `/fabrik-review-scoped` and the exact line `**Lane:** fabrik-task` is present; `--command /fabrik-other` is refused; without `--command` the line stays `/fabrik-review` (W-0a89f069)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-10-02-fabrik-task-feature-lane-design.md
- docs/development/plans/archived/2026-10-02-plan-1-fabrik-task-feature-lane/2026-10-02-plan-1-fabrik-task-feature-lane.md
- scripts/review_receipt.py
