<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > 02-epic-decomposition
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md (95 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# TODO: Draft this command — infra decisions + epic split + dependency graph + persist epic files

## Input Contract (already known)

**Required — from 01-vision-intake:**
- `docs/development/plans/mega-epic/00-vision-summary.md` (written by 01's persist step)
- Reference this file explicitly when dispatching — agent MUST read the confirmed vision.

**References for agent:** `docs/reference/MD/markdown-cheatsheet.md`, `docs/reference/MD/ai-prompt-templates.md`, `docs/reference/fabrik-lifecycle.md`

## Output Contract (already known)

This command persists its own output (like 01 does). Files to write:
- `docs/development/plans/mega-epic/01-infrastructure-decisions.md` (≤5,000 tokens)
- `docs/development/plans/mega-epic/epic-1-<name>.md` through `epic-N-<name>.md` (≤10,000 tokens each)
- `docs/development/plans/mega-epic/dependency-graph.md`

Each epic file must contain a `## Metadata` section matching what `my-workflow/01-epic-brief-command` expects.
