# T09 — Retire the Traycer layer — wrapper tree, traycer_mirror.py, the wiring doc, the Traycer workflow docs; re-point check_traycer_chain

## Scope
Delete `docs/orchestrator/_traycer-skills/` (17 tracked wrappers, 67 KB — generated artifacts, tombstoned by nothing: the assembler that made them is gone at T07) and `scripts/traycer_mirror.py` (a no-op without `TRAYCER_EPIC_ID`, `scripts/traycer_mirror.py:86`; callers: the mega docs only, which T06b already dropped). Move `docs/orchestrator/traycer-command-wiring.md` and the two Traycer workflow docs `docs/traycer/traycer-agile-workflow.md`, `docs/traycer/traycer-refactoring-workflow.md` to `docs/orchestrator/_retired/traycer/<name>.RETIRED.md` — the tombstone pattern mega 05 set (`docs/orchestrator/mega-epic-breakdown/_retired/05-dispatch-epic-tickets-fabrik.RETIRED.md`; that file MOVES to the new single `docs/orchestrator/_retired/` root in T12b so every tombstone lives in one place). KEEP `docs/traycer/README.md`, `kilo_selected_agents.md` (8 live references from rules packs), `fabrik-workflow.md` (6) and `PLAN_OUTPUT_LOCATION.md` — referenced by the rules packs, not Traycer-specific. `scripts/enforcement/check_traycer_chain.py`: `DIRS` (`:28-33`) → the three sources (`commands/_sources/fabrik-vision.md`, `fabrik-epics.md`, `fabrik-epics-review.md`) as explicit files — its glob at `:89` becomes a file list — so the [A]/[B]/[C] detectors keep running over the moved text; the `docs/traycer/*` twin roots (non-existent since 2026-07-17) are dropped. The `~/.claude/skills/fab-*` symlinks (17) disappear with T07a's render (the prune) — verify here, never a Touches entry. DO-NOT: touch the mega or ettw docs (T10–T12).

Depends: T07a, T07b, T08a, T08b
Parallel: ⛓️
Complexity: never-route
Gate: python3 scripts/enforcement/check_traycer_chain.py
Gate: test "$(ls ~/.claude/skills | grep -c '^fab-')" = 0 && test ! -e docs/orchestrator/_traycer-skills
Docs: INDEX.md (removed files + `_retired/` rows) · docs/README.md · CHANGELOG.md — orchestrator-applied

## Touches
- docs/orchestrator/_traycer-skills/ — PRIMARY PATH
- scripts/traycer_mirror.py
- docs/orchestrator/traycer-command-wiring.md
- docs/traycer/traycer-agile-workflow.md
- docs/traycer/traycer-refactoring-workflow.md
- docs/orchestrator/_retired/traycer/traycer-command-wiring.RETIRED.md
- docs/orchestrator/_retired/traycer/traycer-agile-workflow.RETIRED.md
- docs/orchestrator/_retired/traycer/traycer-refactoring-workflow.RETIRED.md
- scripts/enforcement/check_traycer_chain.py

## Behavior Contract
- **Given** the retirement commit, **When** `git ls-files docs/orchestrator/_traycer-skills scripts/traycer_mirror.py` runs, **Then** it prints nothing (scripts/traycer_mirror.py:86)
- **Given** the re-pointed `DIRS`, **When** `check_traycer_chain.py` runs, **Then** it scans exactly the three sources and exits 0 (scripts/enforcement/check_traycer_chain.py:89)
- **Given** the rules packs, **When** `git grep -l 'docs/traycer/kilo_selected_agents.md'` runs, **Then** every referenced file still exists at its path (docs/orchestrator/traycer-command-wiring.md:1)
- **Given** the render from T07a has run in the main checkout, **When** `ls ~/.claude/skills | grep -c '^fab-'` runs, **Then** it prints 0 (commands/assemble_commands.py:809)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- .windsurf/rules/core/10-python.md
