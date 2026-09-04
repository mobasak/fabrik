# T05a — epic containment in check_plan_tickets, and the lock dir moves with the locks

## Scope
Two enforcement edits, each with a watched-red test. (1) `scripts/enforcement/check_plan_tickets.py`: when the spine carries an `Epic:` header line (T04b's interface), load that epic's frontmatter `owned_paths` — COPY the ~20-line parser from `scripts/epic_order.py:29`, never import it: this check is synced to every project and must stay dependency-free — and enforce **both** links the spec commits to (§ Chain consolidation (e): *"every ticket's Scope ⊆ the spine's File Scope ⊆ the epic's `owned_paths`"*): ERROR any ticket Touches path the epic's paths do not cover, AND ERROR any spine File Scope entry outside them — the first draft implemented only the ticket link, which let a spine widen past its epic and still pass. Both sit beside the existing File-Scope containment (`:1067`). A spine with no `Epic:` line behaves exactly as today. (2) `scripts/enforcement/check_plan_lock_release.py:396` `lockdir = root / ".fabrik" / "plan-locks"` → the relocated dir (`~/.claude/state/plan-locks/<repo-basename>/`, with a `FABRIK_PLAN_LOCK_DIR` env override for tests), or the check reports PASS on an empty directory forever — the leaked-lock class its own docstring says it caught twice. SPLIT NOTE: this was T05 until the emit gate measured 267,161 bytes against the 262144 budget (`final_gate.py` alone is 123 KB); the gate registration is T05b. DO-NOT: touch `scripts/final_gate.py` (T05b), `scripts/epic_order.py` (T03) or `commands/_sources/` (T04a/T04b).

Depends: T04b
Parallel: ⛓️
Complexity: never-route
Gate: python -m pytest tests/enforcement/test_plan_tickets_epic_scope.py tests/enforcement/test_plan_lock_release_dir.py -q
Docs: CHANGELOG.md · INDEX.md (new tests) — orchestrator-applied

## Touches
- scripts/enforcement/check_plan_tickets.py — PRIMARY PATH
- scripts/enforcement/check_plan_lock_release.py
- tests/enforcement/test_plan_tickets_epic_scope.py
- tests/enforcement/test_plan_lock_release_dir.py

## Behavior Contract
- **Given** a fixture spine with `Epic: docs/development/epics/1-x.md` whose `owned_paths` is `["src/a/**"]` and a ticket touching `src/b/x.py`, **When** `check_plan_tickets --plan-dir` runs, **Then** it ERRORs naming the ticket, the path and the epic (scripts/enforcement/check_plan_tickets.py:1067)
- **Given** the same spine with the ticket touching `src/a/x.py`, **When** the check runs, **Then** no epic-containment finding is raised (scripts/enforcement/check_plan_tickets.py:1067)
- **Given** a spine whose File Scope names `src/c/**` while its epic owns only `src/a/**`, **When** the check runs, **Then** it ERRORs on the spine entry, not merely on the tickets (scripts/enforcement/check_plan_tickets.py:1067)
- **Given** a spine with no `Epic:` line, **When** the check runs, **Then** its output is byte-identical to today's (scripts/enforcement/check_plan_tickets.py:1067)
- **Given** `FABRIK_PLAN_LOCK_DIR` pointing at a temp dir holding a stale `active` lock, **When** `check_plan_lock_release.py` runs, **Then** it reports the leaked lock; with the dir empty it reports PASS (scripts/enforcement/check_plan_lock_release.py:396)

## Context Files
- .windsurf/rules/core/10-python.md
- scripts/epic_order.py
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
