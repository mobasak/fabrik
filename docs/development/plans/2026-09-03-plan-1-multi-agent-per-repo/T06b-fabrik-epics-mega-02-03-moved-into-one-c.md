# T06b — /fabrik-epics — mega 02 + 03 moved into one corpus source; epics in a phase run concurrently

## Scope
Create `commands/_sources/fabrik-epics.md` from `02-epic-decomposition-fabrik.md` (548 lines) + `03-expand-epic-files-fabrik.md` (337 lines): decompose and write the epic files in one command, 02's checkpoint kept as its Phase gate. Rewrites: `02:77` ("One epic runs through epic-to-ticket-workflow at a time. Epics execute sequentially") → epics in the same `epic_order` phase run concurrently, one per named agent; the sanity band `02:153` ("3–7 epics is typical. ≥10 → re-examine the boundaries") and `02:155` ("the band is a signal, not a cap") stay as a SIGNAL with the operator's range written beside them — E = 3–20; a 20-epic decomposition is re-examined for layer-slicing, never re-cut by reflex (D-107); the epic template emits `owner: ""` in the typed frontmatter (`EPIC-ARTIFACT-SCHEMA.md:16-21`); the `### Entry Point for epic-to-ticket-workflow` section (`03:224-227`) becomes `Entry point: /fabrik-spec <this file>`; `traycer_mirror` steps are deleted (the layer is retired — `status: 0|1|2` stays as the epic's own status). The two old docs are not deleted here (T12a/T12b). DO-NOT: touch `epic_order.py` (T03) or the assembler (T07).

Depends: —
Parallel: ⚡
Complexity: native
Gate: python3 commands/assemble_commands.py --check
Gate: python3 scripts/enforcement/check_traycer_chain.py
Docs: CHANGELOG.md · INDEX.md (new source) — orchestrator-applied

## Touches
- commands/_sources/fabrik-epics.md — PRIMARY PATH

## Behavior Contract
- **Given** a decomposition of 14 epics, **When** `/fabrik-epics` reaches its band check, **Then** it flags re-examination for layer-slicing and proceeds — it does not re-cut to ≤7 (docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md:153)
- **Given** an epic file is written, **When** its frontmatter is read, **Then** it carries `owner: ""` and the Entry point line names `/fabrik-spec <this file>` (docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md:224)
- **Given** the source, **When** grepped for `execute sequentially`, `epic-to-ticket-workflow`, `traycer_mirror` or `fab-mega-`, **Then** the count is 0 (docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md:77)
- **Given** the rendered command, **When** `check_traycer_chain.py` scans the source, **Then** it reports 0 findings (scripts/enforcement/check_traycer_chain.py:89)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- docs/orchestrator/mega-epic-breakdown/02-epic-decomposition-fabrik.md
- docs/orchestrator/mega-epic-breakdown/03-expand-epic-files-fabrik.md
- docs/orchestrator/mega-epic-breakdown/EPIC-ARTIFACT-SCHEMA.md
- scripts/epic_order.py
