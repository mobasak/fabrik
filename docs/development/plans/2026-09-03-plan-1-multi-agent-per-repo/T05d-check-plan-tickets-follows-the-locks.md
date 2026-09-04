# T05d — check_plan_tickets' lock-metadata exemption follows the locks

## Scope
The lock relocation in T04b/T05a is incomplete, and the consumer sweep is split across T05c/T05d/T05e purely by READ BUDGET (the whole set measured 623,472 B against 262,144). Resolve the directory with the SAME four-line snippet in every consumer — there is no shared helper and there cannot be one (`scripts/enforcement/` is synced dependency-free; `.claude/hooks/final_gate_stop.py` is a standalone synced hook that cannot import it). Census re-derived 2026-09-04: **55** tracked files match `\.fabrik/plan-locks`, **69** match the broader `-e plan-locks -e plan_locks` — the slash form is a bounded search that misses every componentwise consumer, which is where this ticket's two worst sites live. **This ticket owns `scripts/enforcement/check_plan_tickets.py` — all FOUR sites, two of which the obvious grep does not find.** String form: `_SPINE_METADATA_PREFIXES` (`:320`) and the own-lock exemption at `:1038`. **Component form, and both fail OPEN:** `:650` `lock = root / ".fabrik" / "plan-locks" / f"{plan_dir.name}.json"` — a miss returns `[]` at `:654` and kills the entire board-staleness ERROR class; `:1574` `locks = root / ".fabrik" / "plan-locks"` — `if locks.is_dir()` goes false and sibling plan sets are never discovered on the gate path. Both would have survived this ticket's first-draft gate, which greps only the slash form. T05a edits this same file for epic containment but never these lines, so without this ticket a plan's own lock stops being recognised as its own metadata and every plan set starts erroring on its own receipt paths. ⚠️ **Shares the file with T05a** — the Depends edge below serialises them; rebase onto T05a's merge before editing. DO-NOT: touch the hook (T05c) or the remaining consumers (T05e).

Depends: T05a, T05c
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/enforcement/test_check_plan_tickets.py -q
Gate: test -z "$(git grep -nE '\.fabrik/plan-locks|\"\.fabrik\"\s*/\s*\"plan-locks\"' -- scripts/enforcement/check_plan_tickets.py)"   # BOTH forms — the string grep alone passes with :650 and :1574 still wrong
Docs: CHANGELOG.md — orchestrator-applied

## Touches
- scripts/enforcement/check_plan_tickets.py — PRIMARY PATH
- tests/enforcement/test_check_plan_tickets.py

## Behavior Contract
- **Given** a spine whose File Scope names its own lock at the NEW path, **When** `check_plan_tickets` runs, **Then** the own-lock metadata exemption applies and no finding is raised (scripts/enforcement/check_plan_tickets.py:320)
- **Given** a plan set whose board is stale, **When** the check runs after the move, **Then** the board-staleness ERROR still fires — proving `:650` resolves the lock at the new directory rather than returning `[]` (scripts/enforcement/check_plan_tickets.py:650)
- **Given** two concurrent plan sets, **When** the check runs on the gate path, **Then** the sibling set is still discovered (scripts/enforcement/check_plan_tickets.py:1574)
- **Given** a ticket whose Touches names its own lock, **When** the check runs, **Then** the dedicated own-lock ERROR still fires at the new path (scripts/enforcement/check_plan_tickets.py:1038)

## Context Files
- .windsurf/rules/core/10-python.md
