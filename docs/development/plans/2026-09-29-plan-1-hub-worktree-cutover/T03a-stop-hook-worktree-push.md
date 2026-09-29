# T03a — The Stop hook's push law binds a worktree branch with no upstream

## Scope
Implements spec § The delta D4 (H3) and V4. `_ahead_of_upstream` (`.claude/hooks/final_gate_stop.py:682-686, :732-748`) keeps `@{upstream}` when set; when it is not and the tree is a linked worktree, it counts the session's authored commits on HEAD not on the main checkout's branch — the symbolic HEAD of the git common dir, the rule `scripts/final_gate.py::_linked_worktree_base` uses (cf4374537), re-implemented here because the hook imports nothing from `final_gate.py`. The docstring's "mid-plan worktree branches have no upstream by design" is replaced by the new rule; the count stays scoped to the session's authored paths (`:715-718`); every git error still returns None. DO-NOT: change the uncommitted check or any other Stop cause.

Depends: —
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/test_stop_hook_worktree_push.py tests/test_stop_hook_push_attribution.py -q
Docs: none (hooks-index row is T06b's)

## Touches
- .claude/hooks/final_gate_stop.py — PRIMARY PATH
- tests/test_stop_hook_worktree_push.py

## Behavior Contract
- **Given** a linked worktree branch with no upstream holding one commit the session authored and not on the main checkout's branch, **When** `_ahead_of_upstream` runs, **Then** it returns 1 and the Stop hook's push cause fires (spec § Validation V4)
- **Given** the same branch after that commit is merged into the main checkout's branch, **When** `_ahead_of_upstream` runs, **Then** it returns 0 (spec § The delta D4)
- **Given** a detached main checkout or a repo with no common-dir HEAD, **When** `_ahead_of_upstream` runs in a worktree without upstream, **Then** it returns None and never blocks (spec § The delta D4)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- .claude/hooks/final_gate_stop.py
- tests/test_stop_hook_push_attribution.py
