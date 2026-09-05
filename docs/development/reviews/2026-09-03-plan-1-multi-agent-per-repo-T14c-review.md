# Acceptance review — T14c (plan set 2026-09-03-plan-1-multi-agent-per-repo)

**Status:** IN-PROGRESS

**Surface:** the coder's worktree branch diff against the dispatch base 3a4b5e77 (master after the T09 merge) — see the round sections below (one file per ticket, rounds APPENDED).

## Round 1 — over `3a4b5e77..f00dc5b1` (src/fabrik/cli.py 11/9 — the post-scaffold hint, a bare `click.echo` inside `create`, extracted into the pure helper `_orchestrator_hint(name)` with the text naming `/fabrik-vision` → `/fabrik-epics` → `/fabrik-epics-review` → per window `/fabrik-spec <epic file>`, the source comment that carried the retired path rewritten, the call site unchanged in position; tests/test_cli_orchestrator_hint.py (new, 2 tests) watched red on the OLD text through the helper (2 failed) then green; the `-l`/`-z` grep gate 0 (the comment's copy gone too); ruff clean — cli.py format-dirty at base in two unrelated hunks, left; QUICKSTART does not document the hint; the test composes the banned literal so T16's tree-wide sweep does not trip on it)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native: the orchestrator's own execution (a one-string change + a new test; stated) — round 1.
### Orchestrator execution (in the worktree, `PYTHONPATH=src` pinned — the venv's editable install resolves `fabrik.cli` to the MAIN checkout otherwise, the quirk the coder found)
- `pytest tests/test_cli_orchestrator_hint.py -q` → 2 passed; the grep gate → 0 files; `ruff check` clean; `_orchestrator_hint` defined and called once.
- Routed (T16): the coder's finding that T16's tree-wide sweep does not exclude `tests/`, and four existing test files legitimately carry the literal as graders asserting its ABSENCE (`tests/test_epic_order.py:861`, `tests/test_review_rubric*.py` — T14d clears those two, `tests/test_assemble_orch_retired.py:37`); the allowlist grows by the absence-graders at T16, stated in the receipt.
Pool: PENDING — appended when it returns.
