# T05d — check_plan_tickets' lock-metadata exemption follows the locks

## Scope
The lock relocation in T04b/T05a is incomplete: `git grep -l '\.fabrik/plan-locks'` finds 50 tracked files and those two own three. The consumer sweep is split across T05c/T05d/T05e purely by READ BUDGET (the whole set measured 623,472 B against 262,144); they share one mechanism — resolve the lock directory through the single `FABRIK_PLAN_LOCK_DIR`-aware helper T05a introduces, never by re-deriving the path. **This ticket owns `scripts/enforcement/check_plan_tickets.py`:** `_SPINE_METADATA_PREFIXES` (`:320`) lists `".fabrik/plan-locks/"`, and `:1038` branches on `p.startswith(".fabrik/plan-locks/")` for the own-lock exemption. T05a edits this same file for epic containment but never these lines, so without this ticket a plan's own lock stops being recognised as its own metadata and every plan set starts erroring on its own receipt paths. ⚠️ **Shares the file with T05a** — the Depends edge below serialises them; rebase onto T05a's merge before editing. DO-NOT: touch the hook (T05c) or the remaining consumers (T05e).

Depends: T05a, T05c
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/enforcement/test_check_plan_tickets.py -q
Gate: test -z "$(git grep -n '\.fabrik/plan-locks' -- scripts/enforcement/check_plan_tickets.py)"
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- scripts/enforcement/check_plan_tickets.py — PRIMARY PATH
- tests/enforcement/test_check_plan_tickets.py

## Behavior Contract
- **Given** a spine whose File Scope names its own lock at the NEW path, **When** `check_plan_tickets` runs, **Then** the own-lock metadata exemption applies and no finding is raised (scripts/enforcement/check_plan_tickets.py:320)
- **Given** a ticket whose Touches names its own lock, **When** the check runs, **Then** the dedicated own-lock ERROR still fires at the new path (scripts/enforcement/check_plan_tickets.py:1038)

## Context Files
- .windsurf/rules/core/10-python.md
