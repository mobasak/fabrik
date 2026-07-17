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
- **Compact Epic Proposal** (from `02-epic-decomposition-command`) — in Traycer's spec store; fetch it with `read_spec`. Step 1's count-match and title-diff checks intersect exactly this artifact; without it check 1 reconstructs the count from the tickets themselves, which makes it tautological and lets the deficit/orphan case it exists to catch pass silently.
- Dependency Graph spec (from `02-epic-decomposition-command`)
- **Cross-Epic Validation Report with `Overall: PASS`** (from `04-cross-epic-validation-command`) — the most recent run in conversation context. The Report's "Recommended Execution Order" already gives the phased plan; 05 should PREFER consuming that over re-deriving from the graph (use re-derivation only if the Report's Execution Order is absent — the Report itself being absent is a hard stop, below).

**Hard stop if:**

- 04 has not run, OR 04's last run was `Overall: FAIL`, OR the Report is not in the current conversation context. State: "05 cannot proceed without a confirmed `Overall: PASS` from `04-cross-epic-validation-command`. Run 04 first." Do NOT call `list_tickets`.
- **Compact Epic Proposal is absent from BOTH Traycer's spec store (`read_spec`) and the conversation** — Step 1 check 1 cannot run; route back to `02-epic-decomposition-command` to re-emit it, then re-run `04-cross-epic-validation-command` before returning here (02's checkpoint can change the epic set 04 validated). ⚠️ Try `read_spec` FIRST: `02` persists it (§ Output Contract), so re-running 02 — and its owner checkpoint — to regenerate a spec the store already holds is the loop this chain exists to prevent.
- Dependency Graph spec is missing from Traycer's store AND the 04 Report's Execution Order is also absent. State: "Dispatch order cannot be derived — Dependency Graph spec missing and the 04 Report carries no Recommended Execution Order. Run `02-epic-decomposition-command` to re-emit the graph, then `04-cross-epic-validation-command`."

## Processing User Request

### Step 1: List All Epic Tickets

Call `read_spec` for the Compact Epic Proposal + Dependency Graph from `02-epic-decomposition-command` (persisted in Traycer's spec store per `02` § Output Contract), then call `list_tickets` to retrieve all tickets created in `03-expand-epic-files-command`.

State: "Found [N] epic tickets: [list titles]."

**Ticket-set integrity checks (all must pass — first failure halts dispatch):**

1. **Count match** — `[N] == epic count from 02-epic-decomposition-command Compact Epic Proposal`. On mismatch:
   - **Deficit** (fewer tickets than epics) — name the missing epic(s) by diffing `02`'s compact entries against the ticket titles on **epic number + name**. ⚠️ Never diff the literal title strings: the two formats differ by separator — 02 writes `Epic [N]: [Name]`, the tickets `Epic N — [Name]` — so a string diff mismatches on every epic and reports the whole set as both deficit and orphan. State: "Missing tickets: Epic [X] — [name], Epic [Y] — [name]. Re-run `03-expand-epic-files-command` to recreate ONLY the missing tickets (do NOT discard the existing ones). Then re-run `04-cross-epic-validation-command` before returning to 05."
   - **Excess** (more tickets than epics) — name the orphan(s) by diffing the other direction. ⚠️ Two tickets can match the SAME entry (a stale in-range copy, e.g. `{1,2,3,3,4,5}` for 5 epics) — a set-diff then names ZERO orphans while the count says excess. So classify per ticket: matches no entry → orphan; two tickets match one entry → the earlier-created one is the stale copy → delete it in Traycer's store. State: "Orphan tickets from a prior run: [titles]. Delete them in Traycer's UI, then re-run `04-cross-epic-validation-command`. Do NOT proceed with 05 — orphans can mask the dispatch intent."
2. **Title format match** — each ticket Title matches `Epic N — [Name]` (em-dash with single spaces; optional `Retrofit:` prefix in [Name]) per `03-expand-epic-files-command` Step 2. On any mismatch: "Ticket [actual title] does not match `Epic N — [Name]` format — 05 cannot map it to a dependency-graph node. Re-run `03-expand-epic-files-command` to fix the title."
3. **Epic-number contiguity** — extracted epic numbers form `1..N` with no gaps. ⚠️ Check 1 has passed, so `N` tickets exist for `N` epics — a gap therefore proves a DUPLICATE or an out-of-range number — it does NOT prove nothing is missing (check 1 is count-only, so a deficit and an orphan can cancel out and reach here). Recreating the missing number blindly returns an Excess to check 1 and loops. Take every ticket whose number is duplicated or outside `1..N` and diff it against `02`'s compact entries on **epic NAME alone** — not the number (it is the thing under suspicion, so keying on it makes "mis-numbered" unmatchable), not the literal title (the separators differ, per check 1). Verdict per ticket: matches the entry for a number MISSING from the set → **mis-numbered**: route to `03-expand-epic-files-command` naming that ticket, to fix its number only — never create a new one. Matches an entry whose correctly-numbered ticket is a DIFFERENT ticket already in the set → **redundant copy**: delete it in Traycer's store; the missing number is then a genuine deficit → re-run `03` for ONLY it. Matches no entry → **orphan masking a deficit**: delete it, then re-run `03` for ONLY the missing ticket(s). Matches the entry its OWN number carries → **genuine, no action** — its co-numbered sibling is the copy. ⚠️ Where two tickets share a number, the **earlier-created** one (Traycer's ticket order/ID) is the stale copy: that is what makes "the correctly-numbered ticket" well-defined and what stops both copies being deleted. In every case re-run `04-cross-epic-validation-command` before returning to 05.

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
   ⚠️ **Carry the epic's `Owned paths:` into the dispatch** (from the ticket's `### Dependencies`). It becomes the executing agent's **`## File Scope (owned paths)`** — the files it may write, and none other. This is the last hop of the concurrency contract that `02`'s parallel gate (2/3 file-scope, 3/3 migrations) established and `04` Step 4 validated; **drop it here and the contract is decorative.** A diff touching a path outside the epic's `Owned paths:` is a scope violation, and on a concurrent run it is a collision with a sibling agent.
3. **Post-execution routing** — instructs the owner to run `epic-to-ticket-workflow/08-implementation-validation-command` per epic to verify implementation after all dispatched epics complete.

**Consumed by:** Owner — executes one epic at a time per phase order; within a Phase, epics with `⚡` can be worked in any order.

**Not consumed by:** Any downstream Traycer command — 05 is the final mega-epic-breakdown step before owner-driven dispatch via ettw.

## Does NOT

- Does NOT write files to disk — tickets are already in Traycer's store.
- Does NOT re-create tickets — that was `03-expand-epic-files-command`.
- Does NOT validate cross-epic consistency — that was done by `04-cross-epic-validation-command` before reaching this step.

## Acceptance Criteria

- `list_tickets` confirms all epic tickets exist.
- Ticket-set integrity confirmed: count matches `02-epic-decomposition-command`'s Compact Epic Proposal; every title matches `Epic N — [Name]`; epic numbers form `1..N` with no gaps.
- Dispatch order stated — inherited from `04`'s Recommended Execution Order, or re-derived from the Dependency Graph ONLY when 04's order is absent.
- Each epic's `Owned paths:` carried into its dispatch as the executing agent's file scope — drop it and the concurrency contract is decorative.
- Route to `epic-to-ticket-workflow` implementation validation stated after execution.
