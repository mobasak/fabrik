# T02a — The corpus render is refused from a worktree

## Scope
Implements spec § The delta D3 (a) and V3. `commands/assemble_commands.py` refuses a render into the installed corpus, and an `--extract` (which writes the sources, `commands/assemble_commands.py:895-928`), when the tree it renders FROM is not the main checkout: `git -C ROOT rev-parse --show-toplevel` (ROOT is the script's own directory, `:26` — never the cwd, so `cd /tmp && python3 /opt/fabrik/commands/assemble_commands.py` still renders and a worktree's copy run from anywhere is refused) must equal the parent of `git -C ROOT rev-parse --path-format=absolute --git-common-dir`. It fails CLOSED with a message naming the main checkout; the guard sits in `__main__`'s render branch (`:1378-1382`) before any write, ahead of the prune (`:1262-1287`). `--check` is unaffected, and so is a `--dest` preview — a `--dest` whose `.resolve()` differs from `OUT.resolve()`; a `--dest` that resolves to the installed corpus is guarded like a default render. Tests that call `render()` directly are unaffected. DO-NOT: change the render or prune logic itself.

Depends: —
Parallel: ⚡
Complexity: native
Gate: python -m pytest tests/test_assemble_worktree_guard.py -q
Docs: none (hooks-index row is T06b's)

## Touches
- commands/assemble_commands.py — PRIMARY PATH
- tests/test_assemble_worktree_guard.py

## Behavior Contract
- **Given** a linked worktree of a repo carrying `commands/assemble_commands.py`, **When** the renderer runs without `--check`, **Then** it exits non-zero naming the main checkout and writes nothing under its output dirs, including when `--dest` resolves to the installed corpus; `--check` and a `--dest` elsewhere still run (spec § Validation V3)
- **Given** the main checkout, **When** the renderer runs, **Then** it proceeds as today (spec § The delta D3)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- commands/assemble_commands.py
