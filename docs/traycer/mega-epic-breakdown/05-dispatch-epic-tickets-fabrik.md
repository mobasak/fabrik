<!-- ⚠️ FABRIK ORCHESTRATOR COMMAND — OUR OWN TWIN OF `05-dispatch-epic-tickets-command.md`
     Unlike the Traycer source, our orchestrator READS THIS FILE DIRECTLY — no GUI copy-paste.
     It is TOOL-CAPABLE: it reads the epic-ticket FILES from disk and dispatches them itself.
     Keep it in lockstep with the Traycer twin; the ONLY intended differences are
     (a) the orchestrator framing, (b) the -fabrik chain refs, and (c) the persistence model —
     we have NO Traycer store; epic tickets are FILES under docs/development/epics/ (written by
     `03-expand-epic-files-fabrik`), enumerated with ls/Glob, deleted with rm (not a Traycer UI).
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md.
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Dispatch Epic Tickets

## Role

You are a dispatcher. You verify that all epic tickets from `03-expand-epic-files-fabrik` exist and are ready, then guide the owner on how to dispatch them.

## Core Philosophy

- **Tickets are already persisted — as FILES.** `03-expand-epic-files-fabrik` wrote each epic to `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md`. ⚠️ We have **no** Traycer store and **no** `list_tickets` tool — enumerate the files with `ls docs/development/epics/*.md` (or Glob). 05 writes nothing.
- **Dispatch is the only action here.** Read the ticket files, confirm they exist and are consistent, route to execution.
- **One epic at a time through epic-to-ticket-workflow.** Dependency Graph determines which epic goes next. Parallel-labeled epics in the same Phase can execute in any order — but the owner runs one epic-to-ticket-workflow cycle at a time.

## Input Contract

**Required — the ticket FILES on disk + the specs in conversation:**

- Epic ticket files (from `03-expand-epic-files-fabrik`) — one per epic, at `docs/development/epics/*.md`
- Dependency Graph spec (from `02-epic-decomposition-fabrik`)
- **Cross-Epic Validation Report with `Overall: PASS`** (from `04-cross-epic-validation-fabrik`) — the most recent run in conversation context. The Report's "Recommended Execution Order" already gives the phased plan; 05 should PREFER consuming that over re-deriving from the graph (use re-derivation only if the Report is absent or stale).

**Hard stop if:**

- 04 has not run, OR 04's last run was `Overall: FAIL`, OR the Report is not in the current conversation context. State: "05 cannot proceed without a confirmed `Overall: PASS` from `04-cross-epic-validation-fabrik`. Run 04 first." Do NOT enumerate the ticket files yet.
- Dependency Graph spec is missing from the conversation AND the 04 Report's Execution Order is also absent. State: "Dispatch order cannot be derived — Dependency Graph spec missing and no 04 Report in context. Run `02-epic-decomposition-fabrik` to re-emit the graph, then `04-cross-epic-validation-fabrik`."

## Processing User Request

### Step 1: List All Epic Tickets

Enumerate the ticket files: `ls docs/development/epics/*.md` (or Glob `docs/development/epics/*.md`) — every file `03-expand-epic-files-fabrik` wrote. Read each. (No `list_tickets` — that is Traycer's tool.)

State: "Found [N] epic tickets: [list titles]."

**Ticket-set integrity checks (all must pass — first failure halts dispatch):**

1. **Count match** — `[N] == epic count from 02-epic-decomposition-fabrik Compact Epic Proposal`. On mismatch:
   - **Deficit** (fewer tickets than epics) — name the missing epic(s) by diffing `02` proposal titles against the ticket-file titles on disk. State: "Missing tickets: Epic [X] — [name], Epic [Y] — [name]. Re-run `03-expand-epic-files-fabrik` to recreate ONLY the missing tickets (do NOT discard the existing ones). Then re-run `04-cross-epic-validation-fabrik` before returning to 05."
   - **Excess** (more tickets than epics) — name the orphan(s) by diffing the other direction. State: "Orphan ticket files from a prior run: [paths]. Delete them (`rm docs/development/epics/<file>`), then re-run `04-cross-epic-validation-fabrik`. Do NOT proceed with 05 — orphans can mask the dispatch intent."
2. **Title format match** — each ticket Title matches `Epic N — [Name]` (em-dash with single spaces; optional `Retrofit:` prefix in [Name]) per `03-expand-epic-files-fabrik` Step 2. On any mismatch: "Ticket [actual title] does not match `Epic N — [Name]` format — 05 cannot map it to a dependency-graph node. Re-run `03-expand-epic-files-fabrik` to fix the title."
3. **Epic-number contiguity** — extracted epic numbers form `1..N` with no gaps. On gaps: state which numbers are missing; route to 03 for recreation.

If any of the 3 checks fail, STOP. Do not proceed to Step 2.

### Step 2: Verify Dependency Order

**Source-of-truth order:** PREFER the `Recommended Execution Order` already rendered by `04-cross-epic-validation-fabrik` Step 7 in the conversation's most recent Validation Report — it's already topologically sorted into Phases. Only re-derive from the Dependency Graph spec if 04's order is absent.

**Re-derivation path (if needed):** Read the Dependency Graph spec from `02-epic-decomposition-fabrik` (mermaid format with `subgraph "Phase N"` blocks per `02-epic-decomposition-fabrik` § ── CHECKPOINT: Present Epic Proposal + Infrastructure Decisions ── → 3. Dependency graph — the mermaid template with the `subgraph "Phase N"` blocks, NOT the one-line summary in § Output Contract). Topologically sort: nodes with no incoming edges = Phase 1; remove them and repeat for Phase 2; continue until all nodes placed. Epics within a Phase have no mutual dependencies — render with `⚡` separator. This is the SAME terminology as 02 + 04 (`Phase`, not `Batch`) — keep it consistent so the owner sees one vocabulary across the chain.

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

1. **Phased execution order** — rendered using one of the 4 patterns in Step 2 (multi-phase / single-epic / fully-parallel / fully-sequential), inherited verbatim from `04-cross-epic-validation-fabrik` Step 7 Recommended Execution Order when present; re-derived from the Dependency Graph spec only when 04's order is absent.
2. **Per-epic dispatch instruction** — invokes `epic-to-ticket-workflow/00-trigger-workflow-command` in **consume mode** (per `epic-to-ticket-workflow/00-trigger-workflow-command` § Entry Points → Multi-epic (consume mode) Path B; reads the epic ticket's 15-field Metadata block as INFRA-CHECK). Identical procedure for delta-feature and Retrofit epics.
   ⚠️ **Carry the epic's `Owned paths:` into the dispatch** (from the ticket's `### Dependencies`). It becomes the executing agent's **`## File Scope (owned paths)`** — the files it may write, and none other. This is the last hop of the concurrency contract that `02`'s parallel gate (2/3 file-scope, 3/3 migrations) established and `04` Step 4 validated; **drop it here and the contract is decorative.** A diff touching a path outside the epic's `Owned paths:` is a scope violation, and on a concurrent run it is a collision with a sibling agent.
3. **Post-execution routing** — instructs the owner to run `epic-to-ticket-workflow/08-implementation-validation-command` per epic to verify implementation after all dispatched epics complete.

**Consumed by:** Owner — executes one epic at a time per phase order; within a Phase, epics with `⚡` can be worked in any order.

**Not consumed by:** Any downstream mega-epic-breakdown command — 05 is the final step before owner-driven dispatch via `epic-to-ticket-workflow`.

## Does NOT

- Does NOT write or modify ticket files — `03-expand-epic-files-fabrik` owns `docs/development/epics/`; 05 only reads them (and may `rm` a confirmed orphan). It writes no new files.
- Does NOT re-create tickets — that was `03-expand-epic-files-fabrik`.
- Does NOT validate cross-epic consistency — that was done by `04-cross-epic-validation-fabrik` before reaching this step.

## Acceptance Criteria

- `ls docs/development/epics/*.md` confirms all epic ticket files exist.
- Ticket count matches epic count from `02-epic-decomposition-fabrik`.
- Dispatch order stated per Dependency Graph.
- Route to `epic-to-ticket-workflow` implementation validation stated after execution.
