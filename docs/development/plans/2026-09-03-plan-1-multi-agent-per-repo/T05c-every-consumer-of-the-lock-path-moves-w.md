# T05c — the Stop hook follows the locks (the fleet-synced one)

## Scope
The lock relocation in T04b/T05a is incomplete: `git grep -l '\.fabrik/plan-locks'` finds 50 tracked files and those two own three. The consumer sweep is split across T05c/T05d/T05e purely by READ BUDGET (the whole set measured 623,472 B against 262,144); they share one mechanism — resolve the lock directory through the single `FABRIK_PLAN_LOCK_DIR`-aware helper T05a introduces, never by re-deriving the path. **This ticket owns the one that matters most.** `.claude/hooks/final_gate_stop.py:864` — `if ".fabrik/plan-locks/" in rel and p.is_file():` — is how the Stop hook decides a plan run is in flight. The file is FLEET-SYNCED, so leaving it keyed on the old path removes a live enforcement in the hub and in ~46 projects at once, with no error raised anywhere: the hook simply stops arming. This is the defect the author-blind review caught, and the reason the lock move is not a three-file change. DO-NOT: touch the enforcement checks (T05d/T05e), `check_plan_lock_release.py` (T05a) or the command sources (T04b).

Depends: T04b, T05a
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/test_final_gate_stop_hook.py -q
Gate: test -z "$(git grep -n '\.fabrik/plan-locks' -- .claude/hooks/final_gate_stop.py)"
Docs: docs/workstation/hooks-index.md is T02's; CHANGELOG.md — orchestrator-applied

## Touches
- .claude/hooks/final_gate_stop.py — PRIMARY PATH
- tests/test_final_gate_stop_hook.py

## Behavior Contract
- **Given** a live plan lock in the NEW directory, **When** the Stop hook evaluates whether a run is in flight, **Then** it arms exactly as it does today for a lock at the old path (.claude/hooks/final_gate_stop.py:864)
- **Given** a lock at the OLD `.fabrik/plan-locks/` path only, **When** the hook runs, **Then** it does NOT arm — proving the move is complete rather than dual-homed (.claude/hooks/final_gate_stop.py:864)
- **Given** no lock anywhere, **When** the hook runs, **Then** its behaviour is unchanged from today (.claude/hooks/final_gate_stop.py:864)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
