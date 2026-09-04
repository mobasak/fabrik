# T05e — the remaining lock consumers: cert coverage, the manifest, the tests

## Scope
The lock relocation in T04b/T05a is incomplete: `git grep -l '\.fabrik/plan-locks'` finds 50 tracked files and those two own three. The consumer sweep is split across T05c/T05d/T05e purely by READ BUDGET (the whole set measured 623,472 B against 262,144); they share one mechanism — resolve the lock directory through the single `FABRIK_PLAN_LOCK_DIR`-aware helper T05a introduces, never by re-deriving the path. **This ticket owns the tail:** (1) `scripts/enforcement/check_certification_coverage.py:257` tells a CERT lock from a plan lock by that prefix; (2) `scripts/fabrik_synced_manifest.py:258` carries the `".fabrik/plan-locks/*-salvage-*.diff"` gitignore leg, which T04b's move of the salvage-diff path (`fabrik-execute-plan.md:532`) would otherwise strand — every project would ignore a path that no longer exists while the real one goes untracked; (3) the remaining assertions in `tests/enforcement/test_phase_tests_gate.py` (22 hits), `tests/enforcement/test_plan_lock_release.py` and `tests/enforcement/test_certification_coverage.py`; (4) `docs/reference/plan-lock-lifecycle.md`, the subsystem's own reference doc (3 hits). ⚠️ **Shares `scripts/fabrik_synced_manifest.py` with T01a** — serialised by the Depends edge. DO-NOT: touch the hook (T05c) or `check_plan_tickets.py` (T05d).

Depends: T01a, T05d
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/enforcement/test_phase_tests_gate.py tests/enforcement/test_plan_lock_release.py tests/enforcement/test_certification_coverage.py -q
Gate: test -z "$(git grep -l '\.fabrik/plan-locks' -- '*.py' '*.sh')"   # zero CODE consumers left on the old path, repo-wide
Docs: docs/reference/plan-lock-lifecycle.md · templates/governance/CLAUDE.md's lock-path sentence is T14a's · CHANGELOG.md — orchestrator-applied

## Touches
- scripts/enforcement/check_certification_coverage.py — PRIMARY PATH
- scripts/fabrik_synced_manifest.py
- tests/enforcement/test_phase_tests_gate.py
- tests/enforcement/test_plan_lock_release.py
- tests/enforcement/test_certification_coverage.py
- docs/reference/plan-lock-lifecycle.md

## Behavior Contract
- **Given** a cert lock and a plan lock in the new directory, **When** `check_certification_coverage` runs, **Then** it still tells them apart (scripts/enforcement/check_certification_coverage.py:257)
- **Given** the manifest's gitignore legs, **When** rendered, **Then** the salvage-diff pattern points at the new directory and no project ignores a path that no longer exists (scripts/fabrik_synced_manifest.py:258)
- **Given** the whole repo after this ticket, **When** `git grep -l '.fabrik/plan-locks' -- '*.py' '*.sh'` runs, **Then** it prints nothing (scripts/enforcement/check_certification_coverage.py:257)

## Context Files
- .windsurf/rules/core/10-python.md
