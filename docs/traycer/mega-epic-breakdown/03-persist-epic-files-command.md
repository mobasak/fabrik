<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > persist-epic-files
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md (95 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Persist Epic Files

## Role

You are an executor who takes all confirmed outputs from the conversation and writes them to disk as structured files via a coding agent.

## Goal

Write every confirmed output from `00-trigger-workflow-command` and `02-epic-decomposition-command` to disk. After this command completes, the project folder contains all files needed to run `my-workflow` per epic.

## Core Philosophy

- **Write exactly what was confirmed.** Do not modify, summarize, reformat, or improve. The owner confirmed the content in prior commands — persist it verbatim.
- **One coding agent call.** Batch all files into a single agent dispatch. Do not call the agent per file.
- **Verify after writing.** Confirm every file exists and is non-empty.
- This is a MECHANICAL step, not a THINKING step. No analysis. No questions. No iteration. Just write.

## Input Contract

**Required — from conversation context (both must be owner-confirmed):**

From `00-trigger-workflow-command`:
- Vision Summary (confirmed)

From `02-epic-decomposition-command`:
- Infrastructure Decisions document (confirmed)
- Epic files — one per epic (confirmed)
- Dependency Graph with mermaid diagram (confirmed)

**Hard stop if:** any of the above are missing or not confirmed by owner. Do not write partial output.

## Processing User Request

### Step 1: Collect All Outputs

From conversation context, collect:
1. Vision Summary (from `00-trigger-workflow-command`)
2. Infrastructure Decisions (from `02-epic-decomposition-command`)
3. Each epic file (from `02-epic-decomposition-command`)
4. Dependency Graph (from `02-epic-decomposition-command`)

Count: "Collected [N] files to write: 1 vision summary + 1 infrastructure decisions + [M] epic files + 1 dependency graph."

### Step 2: Dispatch Coding Agent

Call a coding agent to write ALL files in one batch.

**Target directory:** `docs/development/plans/mega-epic/`
Create the directory if it doesn't exist.

**Files to write:**

| File | Source | Content |
|---|---|---|
| `00-vision-summary.md` | `00-trigger-workflow-command` | Vision Summary — verbatim |
| `01-infrastructure-decisions.md` | `02-epic-decomposition-command` | Infrastructure Decisions — verbatim |
| `epic-1-<name>.md` | `02-epic-decomposition-command` | Epic 1 file — verbatim |
| `epic-2-<name>.md` | `02-epic-decomposition-command` | Epic 2 file — verbatim |
| ... | ... | One per epic |
| `dependency-graph.md` | `02-epic-decomposition-command` | Dependency graph with mermaid — verbatim |

**Epic file naming:** `epic-<N>-<kebab-case-name>.md` — e.g., `epic-1-core-api.md`, `epic-2-client-portal.md`.

**Agent reference files:**
- `docs/reference/MD/markdown-cheatsheet.md` — AI-friendly markdown rules

**Agent instruction:** "Write each file exactly as provided. Do not modify, summarize, or reformat. Create `docs/development/plans/mega-epic/` directory if it doesn't exist."

### Step 3: Verify

After the agent completes, verify:
- [ ] Directory `docs/development/plans/mega-epic/` exists
- [ ] `00-vision-summary.md` exists and is non-empty
- [ ] `01-infrastructure-decisions.md` exists and is non-empty
- [ ] Each `epic-<N>-<name>.md` exists and is non-empty
- [ ] `dependency-graph.md` exists and is non-empty
- [ ] File count matches: 1 + 1 + [M epics] + 1 = [total]
- [ ] Each epic file contains a `## Metadata` section

State: "All [N] files written to `docs/development/plans/mega-epic/`. Verified."

### Step 4: Route

"Files persisted. Proceed to `04-cross-epic-validation-command` to validate completeness."

## Output Contract

**Files created on disk:**

```
docs/development/plans/mega-epic/
├── 00-vision-summary.md
├── 01-infrastructure-decisions.md
├── epic-1-<name>.md
├── epic-2-<name>.md
├── ...
├── epic-N-<name>.md
└── dependency-graph.md
```

**Consumed by:** `04-cross-epic-validation-command` reads ALL files from disk to validate.

## Does NOT

- Does NOT modify, summarize, or improve content — writes verbatim from conversation.
- Does NOT analyze or question the content — that was done in prior commands.
- Does NOT iterate with the owner — this is a mechanical step.
- Does NOT validate feature coverage or epic boundaries — that is `04-cross-epic-validation-command`.
- Does NOT create project scaffolds — that happens after validation, when the owner runs `fabrik scaffold` per epic.

## Acceptance Criteria

- All files from conversation context written to `docs/development/plans/mega-epic/`.
- Content is verbatim — not modified, summarized, or reformatted.
- Directory created if it didn't exist.
- Every file verified: exists and non-empty.
- File count matches expected: vision summary + infrastructure decisions + N epic files + dependency graph.
- Each epic file contains `## Metadata` section.
- Epic files named with kebab-case: `epic-<N>-<name>.md`.
- Single coding agent dispatch — not one call per file.
- Agent reference files provided: `docs/reference/MD/markdown-cheatsheet.md`.
- Route to `04-cross-epic-validation-command` stated after verification.
