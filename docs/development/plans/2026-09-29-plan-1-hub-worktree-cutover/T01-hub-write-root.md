# T01 — Hub write root: tracked outputs land in the invoker's tree

## Scope
Implements spec § The delta D3 (the deploy-bookkeeping rule: every hub script that writes a tracked file resolves its root from the git toplevel of the tree its invoker runs in) and V9. `src/fabrik/config.py`'s `FABRIK_ROOT` default (`src/fabrik/config.py:25`) becomes: `$FABRIK_ROOT` if set; else, when the cwd is inside a linked worktree whose git common dir's parent is `/opt/fabrik`, that worktree's toplevel; else `/opt/fabrik`. Every caller that reads `FABRIK_ROOT` (e.g. `src/fabrik/cli.py:71-77`, `src/fabrik/scaffold.py:6838`) then follows without edits. Scripts with their own hard-coded root and tracked outputs switch to the same resolution: `scripts/sync_projects.py:35`, `scripts/vps_sync.py:28, :31-33`, `scripts/command_feedback_report.py:1709` (the `--repo` default). The search: every tracked `*.py`/`*.sh` outside `tests/`, `libs/`, `scripts/.archive/`, `scripts/archived/` containing a `/opt/fabrik` string literal prefix (`"/opt/fabrik"`, `"/opt/fabrik/…"`, `'/opt/fabrik…'`) or `FABRIK_ROOT`, AND a write call — 99 candidates at plan time (grounding, § Evidence). Each hit is either converted (the four files above) or entered in the test's allowlist with a one-line reason (writes untracked state · writes another repo · main-checkout-only by design, agent-1's act · dead script). DO-NOT: change `src/fabrik/scaffold.py` or `src/fabrik/cli.py` (they follow `FABRIK_ROOT`); touch the deploy path's `.fabrik/state` writes (gitignored, `.gitignore:110`).

Depends: —
Parallel: ⚡
Complexity: complex
Gate: python -m pytest tests/test_hub_write_root.py -q
Docs: none (the rule is documented by T06b)

## Touches
- src/fabrik/config.py — PRIMARY PATH
- scripts/sync_projects.py
- scripts/vps_sync.py
- scripts/command_feedback_report.py
- tests/test_hub_write_root.py

## Behavior Contract
- **Given** `FABRIK_ROOT` unset and the cwd inside a throwaway linked worktree of a repo whose common dir's parent is the hub path under test, **When** `fabrik.config` resolves `FABRIK_ROOT`, **Then** it is that worktree's toplevel; from the main checkout, or from outside any hub tree, it is `/opt/fabrik`; an explicit `$FABRIK_ROOT` always wins (spec § The delta D3)
- **Given** a throwaway linked worktree with the SSH/VPS layer stubbed, **When** `sync_projects.py` and `vps_sync.py` run from it, **Then** their tracked outputs (`data/projects.yaml`, `PORTS.md`, `docs/PROJECT_CATALOG.md`, `docs/infrastructure/vps-status.md` and its siblings) change in that worktree and the main checkout's `git status --porcelain` is unchanged (spec § Validation V9)
- **Given** the search described in § Scope, **When** the test runs it over the tracked tree, **Then** every hit is either one of the converted files or in the allowlist with a reason, and an unlisted new hit fails the test naming the file (spec § The delta D3)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- src/fabrik/config.py
- scripts/sync_projects.py
- scripts/vps_sync.py
