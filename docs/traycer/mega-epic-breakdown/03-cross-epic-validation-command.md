<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > 03-cross-epic-validation
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md (95 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# TODO: Draft this command — verify completeness, no gaps, interfaces defined between epics

## Input Contract (already known)

**Required — from 01 and 02 (all persisted on disk):**
- `docs/development/plans/mega-epic/00-vision-summary.md` (from 01)
- `docs/development/plans/mega-epic/01-infrastructure-decisions.md` (from 02)
- `docs/development/plans/mega-epic/epic-*.md` (all epic files from 02)
- `docs/development/plans/mega-epic/dependency-graph.md` (from 02)

Agent MUST read ALL of these files. Reference them explicitly when dispatching.

## Purpose

Validates the complete decomposition:
- Every feature from Vision Summary's Feature Inventory maps to exactly one epic
- No gaps (feature in vision but in no epic)
- No overlaps (feature claimed by two epics)
- Epic boundaries are clean (shared interfaces defined)
- Dependency graph has no cycles
- Each epic file is self-sufficient for my-workflow/01-epic-brief-command
- Owner confirms → ready to run my-workflow per epic
