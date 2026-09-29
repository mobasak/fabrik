# T02a — The corpus render is refused from a worktree

## Scope
Implements spec § The delta D3 (a) and V3. `commands/assemble_commands.py` refuses a render (not `--check`) whose `git rev-parse --show-toplevel` is not the main checkout — the parent of `git rev-parse --path-format=absolute --git-common-dir` — failing CLOSED with a message naming the main checkout; the guard sits before any write in `__main__` (`commands/assemble_commands.py:1368-1382`), ahead of the prune (`:1262-1287`). DO-NOT: change the render or prune logic itself.

Depends: —
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/test_assemble_worktree_guard.py -q
Docs: none (hooks-index row is T06b's)

## Touches
- commands/assemble_commands.py — PRIMARY PATH
- tests/test_assemble_worktree_guard.py

## Behavior Contract
- **Given** a linked worktree of a repo carrying `commands/assemble_commands.py`, **When** the renderer runs without `--check`, **Then** it exits non-zero naming the main checkout and writes nothing under its output dirs; `--check` still runs (spec § Validation V3)
- **Given** the main checkout, **When** the renderer runs, **Then** it proceeds as today (spec § The delta D3)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- commands/assemble_commands.py
