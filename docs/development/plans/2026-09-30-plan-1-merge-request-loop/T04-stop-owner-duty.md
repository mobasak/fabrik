# T04 — The Stop hook holds a merge owner with a waiting request

## Scope
Implements spec § The delta 6 (duties D-B, D-C). `.claude/hooks/final_gate_stop.py` gains one cause, evaluated ONLY in a repo's main checkout by a session that resolves to the repo's merge owner: the turn is blocked while an unclaimed `merge-request` addressed to it waits in the repo inbox, or a `fabrik-merge/<id>.json` record is short of `replied` with its recorded process gone; the block text carries the `merge_request.py merge` (or `resume <id>`) command; CAP 3 and warn-through like every other cause (`.claude/hooks/final_gate_stop.py:45` `CAP = 3`, `:1409` `decide_review` as the pattern); silent in an UNDECLARED repo, in a linked worktree, and for any other agent.

Depends: T03
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_stop_hook_merge_requests.py tests/test_final_gate_stop_hook.py -q
Docs: none (the hooks-index row is T06's)

## Touches
- .claude/hooks/final_gate_stop.py — PRIMARY PATH
- tests/test_stop_hook_merge_requests.py

## Behavior Contract
- **Given** the merge owner's session in the main checkout and an unclaimed merge-request addressed to it, **When** the Stop hook runs, **Then** it blocks with the `merge_request.py merge` command, and after CAP attempts warns through (spec § Validation V8)
- **Given** a stranded record short of `replied` whose recorded pid is dead, **When** the Stop hook runs for the owner, **Then** it blocks with `merge_request.py resume <id>` (spec § The delta 6)
- **Given** the same inbox, **When** the Stop hook runs in a linked worktree, for a non-owner agent, or in an UNDECLARED repo, **Then** this cause is silent (spec § The delta 6, 8)

## Context Files
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-30-merge-request-loop-design.md
- .claude/hooks/final_gate_stop.py
