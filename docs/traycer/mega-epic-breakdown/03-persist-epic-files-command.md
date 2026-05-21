<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > 03-persist-epic-files
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md (95 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# TODO: Draft this command — call coding agent to write all confirmed outputs to disk

## Purpose

Takes the confirmed outputs from 01-vision-intake (Vision Summary) and 02-epic-decomposition (infrastructure decisions, epic files, dependency graph) and writes them as structured files to disk via a coding agent.

This is the ONLY command that creates files. 01 and 02 produce output in conversation. This command persists it.

## Input Contract

**From conversation context (produced by prior commands):**
- Vision Summary (from 01-vision-intake, confirmed by owner)
- Infrastructure Decisions (from 02-epic-decomposition, confirmed by owner)
- Epic files (from 02-epic-decomposition, one per epic, confirmed by owner)
- Dependency Graph (from 02-epic-decomposition, confirmed by owner)

## Output Contract

**Files to create** (via coding agent):

```
docs/development/plans/mega-epic/
├── 00-vision-summary.md              ← from 01-vision-intake output
├── 01-infrastructure-decisions.md    ← from 02-epic-decomposition output
├── epic-1-<name>.md                  ← one per epic from 02 output
├── epic-2-<name>.md
├── ...
└── dependency-graph.md               ← from 02-epic-decomposition output
```

**Agent reference files:**
- `docs/reference/MD/markdown-cheatsheet.md` — AI-friendly markdown formatting
- `docs/reference/MD/ai-prompt-templates.md` — structured document formatting

**Each epic file must contain a `## Metadata` section** matching what `my-workflow/01-epic-brief-command` expects (scaffold type, shape flags, concurrency, i18n, port, rule packs).

## After Persist

State: "All files written to `docs/development/plans/mega-epic/`. Proceed to `04-cross-epic-validation-command` to validate."
