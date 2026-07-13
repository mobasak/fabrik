<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > dispatch-epic-tickets
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md.
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Dispatch Epic Tickets

## Role

You are a dispatcher. You verify that all epic tickets from `03-expand-epic-files-command` exist and are ready, then guide the owner on how to dispatch them.

## Core Philosophy

- **Tickets are already persisted.** `03-expand-epic-files-command` created them in Traycer's ticket store. There is nothing to write to disk.
- **Dispatch is the only action here.** Read the ticket list, confirm they exist, route to execution.
- **One epic at a time through epic-to-ticket-workflow.** Dependency Graph determines which epic goes next. Parallel-labeled epics in the same Phase can execute in any order — but the owner runs one epic-to-ticket-workflow cycle at a time.

## Input Contract

**Required — all in Traycer's store or conversation context:**

- Epic tickets (from `03-expand-epic-files-command`) — one per epic
- Dependency Graph spec (from `02-epic-decomposition-command`)
- **Cross-Epic Validation Report with `Overall: PASS`** (from `04-cross-epic-validation-command`) — the most recent run in conversation context. The Report's "Recommended Execution Order" already gives the phased plan; 05 should PREFER consuming that over re-deriving from the graph (use re-derivation only if the Report is absent or stale).

**Hard stop if:**

- 04 has not run, OR 04's last run was `Overall: FAIL`, OR the Report is not in the current conversation context. State: "05 cannot proceed without a confirmed `Overall: PASS` from `04-cross-epic-validation-command`. Run 04 first." Do NOT call `list_tickets`.
- Dependency Graph spec is missing from Traycer's store AND the 04 Report's Execution Order is also absent. State: "Dispatch order cannot be derived — Dependency Graph spec missing and no 04 Report in context. Run `02-epic-decomposition-command` to re-emit the graph, then `04-cross-epic-validation-command`."

## Processing User Request

### Step 1: List All Epic Tickets

Call `list_tickets` to retrieve all tickets created in `03-expand-epic-files-command`.

State: "Found [N] epic tickets: [list titles]."

**Ticket-set integrity checks (all must pass — first failure halts dispatch):**

1. **Count match** — `[N] == epic count from 02-epic-decomposition-command Compact Epic Proposal`. On mismatch:
   - **Deficit** (fewer tickets than epics) — name the missing epic(s) by diffing `02` proposal titles against `list_tickets` titles. State: "Missing tickets: Epic [X] — [name], Epic [Y] — [name]. Re-run `03-expand-epic-files-command` to recreate ONLY the missing tickets (do NOT discard the existing ones). Then re-run `04-cross-epic-validation-command` before returning to 05."
   - **Excess** (more tickets than epics) — name the orphan(s) by diffing the other direction. State: "Orphan tickets from a prior run: [titles]. Delete them in Traycer's UI, then re-run `04-cross-epic-validation-command`. Do NOT proceed with 05 — orphans can mask the dispatch intent."
2. **Title format match** — each ticket Title matches `Epic N — [Name]` (em-dash with single spaces; optional `Retrofit:` prefix in [Name]) per `03-expand-epic-files-command` Step 2. On any mismatch: "Ticket [actual title] does not match `Epic N — [Name]` format — 05 cannot map it to a dependency-graph node. Re-run `03-expand-epic-files-command` to fix the title."
3. **Epic-number contiguity** — extracted epic numbers form `1..N` with no gaps. On gaps: state which numbers are missing; route to 03 for recreation.

If any of the 3 checks fail, STOP. Do not proceed to Step 2.

### Step 2: Verify Dependency Order

**Source-of-truth order:** PREFER the `Recommended Execution Order` already rendered by `04-cross-epic-validation-command` Step 7 in the conversation's most recent Validation Report — it's already topologically sorted into Phases. Only re-derive from the Dependency Graph spec if 04's order is absent.

**Re-derivation path (if needed):** Read the Dependency Graph spec from `02-epic-decomposition-command` (mermaid format with `subgraph "Phase N"` blocks per `02-epic-decomposition-command` § ── CHECKPOINT: Present Epic Proposal + Infrastructure Decisions ── → 3. Dependency graph — the mermaid template with the `subgraph "Phase N"` blocks, NOT the one-line summary in § Output Contract). Topologically sort: nodes with no incoming edges = Phase 1; remove them and repeat for Phase 2; continue until all nodes placed. Epics within a Phase have no mutual dependencies — render with `⚡` separator. This is the SAME terminology as 02 + 04 (`Phase`, not `Batch`) — keep it consistent so the owner sees one vocabulary across the chain.

**Render the execution order to the owner using these patterns:**

- **Multi-phase example (4-level graph 1→2, 1→3, {2,3}→4, 4→5):**

  ```text
  Phase 1 (root — no upstream dependencies): Epic 1 — [name]
  Phase 2 (after Phase 1 completes): Epic 2 — [name] ⚡ Epic 3 — [name]
  Phase 3 (after Phase 2 completes): Epic 4 — [name]
  Phase 4 (after Phase 3 completes): Epic 5 — [name]
  ```

- **Single-epic case:**

  ```text
  Phase 1: Epic 1 — [name] (atomic — no phasing required)
  ```

- **Fully-parallel case (N epics, no edges):**

  ```text
  Phase 1: Epic 1 — [name] ⚡ Epic 2 — [name] ⚡ … ⚡ Epic N — [name] (all parallel; no inter-epic dependencies)
  ```

- **Fully-sequential case (N epics, linear chain 1→2→…→N):**

  ```text
  Phase 1: Epic 1 — [name]
  Phase 2 (after Phase 1): Epic 2 — [name]
  …
  Phase N (after Phase N-1): Epic N — [name]
  ```

### Step 3: Route to Dispatch

State dispatch instructions:

"To execute an epic (Delta-feature OR Retrofit — same procedure): select its ticket → run `epic-to-ticket-workflow/00-trigger-workflow-command` in **consume mode** (per `epic-to-ticket-workflow/00-trigger-workflow-command` § Entry Points → Multi-epic (consume mode) Path B — it reads the epic ticket's Metadata block as the INFRA-CHECK input instead of deriving it from scratch). Then continue through `01-epic-brief-command` (Path B § Step 1 consumes the same Metadata via INFRA-CHECK). The ticket description IS the Epic Brief input."

"Dispatch order — execute one Phase at a time, in order; within a Phase, epics with `⚡` can be worked in any order but the owner runs one `epic-to-ticket-workflow` cycle at a time:"

- Phase 1: [Epic X, Epic Y] — dispatch in any order
- Phase 2: [Epic Z] — dispatch after Phase 1 completes
- ...

"After all epics execute, run `epic-to-ticket-workflow/08-implementation-validation-command` per epic to verify implementation."

## Output Contract

Dispatch instructions presented in conversation (structure-bounded, not document-style — per `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` item 93). Format:

1. **Phased execution order** — rendered using one of the 4 patterns in Step 2 (multi-phase / single-epic / fully-parallel / fully-sequential), inherited verbatim from `04-cross-epic-validation-command` Step 7 Recommended Execution Order when present; re-derived from the Dependency Graph spec only when 04's order is absent.
2. **Per-epic dispatch instruction** — invokes `epic-to-ticket-workflow/00-trigger-workflow-command` in **consume mode** (per `epic-to-ticket-workflow/00-trigger-workflow-command` § Entry Points → Multi-epic (consume mode) Path B; reads the epic ticket's 15-field Metadata block as INFRA-CHECK). Identical procedure for delta-feature and Retrofit epics.
3. **Post-execution routing** — instructs the owner to run `epic-to-ticket-workflow/08-implementation-validation-command` per epic to verify implementation after all dispatched epics complete.

**Consumed by:** Owner — executes one epic at a time per phase order; within a Phase, epics with `⚡` can be worked in any order.

**Not consumed by:** Any downstream Traycer command — 05 is the final mega-epic-breakdown step before owner-driven dispatch via ettw.

## Does NOT

- Does NOT write files to disk — tickets are already in Traycer's store.
- Does NOT re-create tickets — that was `03-expand-epic-files-command`.
- Does NOT validate cross-epic consistency — that was done by `04-cross-epic-validation-command` before reaching this step.

## Acceptance Criteria

- `list_tickets` confirms all epic tickets exist.
- Ticket count matches epic count from `02-epic-decomposition-command`.
- Dispatch order stated per Dependency Graph.
- Route to `epic-to-ticket-workflow` implementation validation stated after execution.
