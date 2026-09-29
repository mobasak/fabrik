# T03b — A hub worktree is the hub to the gate

## Scope
Implements spec § The delta D4 (H4) and V8. Hub identity becomes "`scripts/fabrik_synced_manifest.py` is present in the tree AND the git common dir's parent is `/opt/fabrik`", replacing `cwd == /opt/fabrik` in `scripts/enforcement/check_vendored_drift.py:127-129` and in `scripts/final_gate.py:2445-2448, :2725-2755`. In a hub worktree `check_vendored_drift.py` grades the worktree's own governance set, not `_governance_set(HUB)` (`scripts/enforcement/check_vendored_drift.py:40, :131`). The hub path is one module constant in each file (`HUB`, and `fabrik_master` at `scripts/final_gate.py:2445`), which the tests monkeypatch to a scratch repo's path, so no test adds a worktree to the real `/opt/fabrik`. DO-NOT: touch `session_orient.py` (T04a owns its hub test) or any other gate check.

Depends: —
Parallel: ⚡
Complexity: never-route
Gate: python -m pytest tests/test_hub_identity_worktree.py -q
Docs: none

## Touches
- scripts/final_gate.py — PRIMARY PATH
- scripts/enforcement/check_vendored_drift.py
- tests/test_hub_identity_worktree.py

## Behavior Contract
- **Given** a throwaway linked worktree of the hub, **When** `check_vendored_drift.py` runs there, **Then** it grades instead of returning 0 at its hub test (spec § Validation V8)
- **Given** the same worktree, **When** `final_gate.py`'s self-exemption and `_synced_paths` resolve, **Then** they treat it as the hub, exactly as the main checkout; a project repo is still a project (spec § The delta D4)

## Context Files
- .windsurf/rules/core/10-python.md
- .windsurf/rules/core/45-testing-strategy.md
- docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md
- scripts/enforcement/check_vendored_drift.py
- scripts/final_gate.py
