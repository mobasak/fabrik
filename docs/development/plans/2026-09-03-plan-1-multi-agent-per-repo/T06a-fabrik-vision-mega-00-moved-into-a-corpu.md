# T06a — /fabrik-vision — mega 00 moved into a corpus source, with the rivals pre-step

## Scope
Create `commands/_sources/fabrik-vision.md` from `docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md` (962 lines) — a MOVE of the canonical text into the source shape the assembler renders (the source carries NO run-record, close-feedback, NEXT or question-bar fragment: the renderer appends them — `commands/assemble_commands.py:720` `render()`, `:288` `_emit_skill`). Rewrites: (g) Path A research discovery (`00:193-199`) adds `docs/reference/rivals/<market>.md` (written by `/fabrik-rivals`, `commands/_sources/fabrik-rivals.md:2`): MATCH rows seed the Full Feature Inventory as candidates, BEAT rows seed Value Streams and problems-to-solve, wedge + white-space land in Technology Decisions or Out of Scope; a market-facing vision with no dossier STOPS and names `/fabrik-rivals <market>` as its pre-step; internal tools and Retrofit skip it. Every reference to `/fab-mega-02-decompose` becomes `/fabrik-epics`; every `epic-to-ticket-workflow` reference becomes the corpus chain (`/fabrik-spec <epic file>` → … → `/fabrik-execute-plan`). The `Reads:`-budget / hollow-citation discipline (mega checklist row 102) stays as prose. `check_traycer_chain.py`'s three detectors must find 0 [C] cross-file line anchors in the new source (it scans `*.md` in `DIRS`, `scripts/enforcement/check_traycer_chain.py:89` — T09 re-points DIRS; until then run it by hand on the new file). The old doc is NOT deleted here (T12a moves it — sizing); between this ticket and T12a the two copies coexist inside one plan, T07's render is the point where the source becomes the invokable one. DO-NOT: touch the assembler or the router (T07a/T07b); edit `00-trigger-mega-epic-fabrik.md` in place.

Depends: —
Parallel: ⚡
Complexity: native
Gate: python3 commands/assemble_commands.py --check
Gate: python3 scripts/enforcement/check_traycer_chain.py
Docs: CHANGELOG.md · INDEX.md (new source) — orchestrator-applied

## Touches
- commands/_sources/fabrik-vision.md — PRIMARY PATH

## Behavior Contract
- **Given** a market-facing intake and no `docs/reference/rivals/<market>.md`, **When** `/fabrik-vision` reaches Path A discovery, **Then** it stops and names `/fabrik-rivals <market>` as the pre-step (commands/_sources/fabrik-rivals.md:2)
- **Given** a dossier exists, **When** discovery runs, **Then** MATCH rows appear as Feature Inventory candidates and BEAT rows as Value-Stream problems, each citing the dossier row (docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md:193)
- **Given** the rendered command, **When** `check_traycer_chain.py` scans the source, **Then** it reports 0 [A]/[B]/[C] findings (scripts/enforcement/check_traycer_chain.py:89)
- **Given** the source, **When** grepped for `fab-mega-`, `epic-to-ticket-workflow`, `_traycer-skills` or `traycer_mirror`, **Then** the count is 0 (docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md:1)

## Context Files
- docs/superpowers/specs/2026-09-03-multi-agent-per-repo-design.md
- docs/orchestrator/mega-epic-breakdown/00-trigger-mega-epic-fabrik.md
- commands/_sources/fabrik-rivals.md
- commands/_sources/fabrik-spec.md
