<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > 02-epic-decomposition
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md (95 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# TODO: Draft this command — infra decisions + epic split + dependency graph

## Purpose

Takes the confirmed Vision Summary from 00-trigger-workflow (in conversation context) and decomposes it into independent epics with infrastructure decisions, boundaries, and a dependency graph. Output lives in conversation — `03-persist-epic-files-command` writes it to disk.

## Input Contract

**From conversation context (produced by 00-trigger-workflow):**
- Confirmed Vision Summary (Feature Inventory, Personas, Value Streams, Constraints, Scale Assessment)

**Additionally read:**
- `docs/reference/fabrik-lifecycle.md` — each epic must pass all 4 stages
- `AGENTS.md` § Infrastructure Services — backing services available
- `AGENTS.md` § Planning Constraints

## Output Contract

**Produced in conversation (NOT written to disk — that's 03's job):**
- Infrastructure Decisions (shared across all epics, ≤5,000 tokens)
- Epic files (one per epic, ≤10,000 tokens each, with Metadata section for my-workflow/01)
- Dependency Graph (mermaid diagram + execution order)

**Consumed by:** `03-persist-epic-files-command` reads from conversation and writes to disk.

## Does NOT

- Does NOT create files — that is `03-persist-epic-files-command`.
- Does NOT redo vision analysis — consumes 01's confirmed output.
