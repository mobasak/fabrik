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
- **Compact Epic Proposal** (from `02-epic-decomposition-fabrik`) — in conversation; `02` writes nothing to disk. Step 1's count-match and title-diff checks intersect exactly this artifact: without it, check 1 has no grounded source and either gets skipped or is reconstructed from the ticket files themselves — which makes it tautological and lets the very deficit/orphan case it exists to catch pass silently.
- Dependency Graph spec (from `02-epic-decomposition-fabrik`)
- **Cross-Epic Validation Report with `Overall: PASS`** (from `04-cross-epic-validation-fabrik`) — the most recent run in conversation context. The Report's "Recommended Execution Order" already gives the phased plan; 05 should PREFER consuming that over re-deriving from the graph (use re-derivation only if the Report's Execution Order is absent — the Report itself being absent is a hard stop, below).

**Hard stop if:**

- 04 has not run, OR 04 routed back / paused on a BLOCKED case without reaching its `found:0, fixed:0` no-op, OR the Report is not in the current conversation context. ⚠️ `04-cross-epic-validation-fabrik` converges — it never emits `Overall: FAIL` (that is the Traycer twin's one-shot audit shape); its report exists only at the no-op.
- **Compact Epic Proposal is missing from the conversation** — Step 1 check 1 cannot run; route back to `02` to re-emit it, **then re-run `04-cross-epic-validation-fabrik` before returning here** — 02's owner checkpoint can change the epic set 04 validated.
- Dependency Graph spec is missing from the conversation AND the 04 Report's Execution Order is also absent. State: "Dispatch order cannot be derived — Dependency Graph spec missing and the 04 Report carries no Recommended Execution Order. Run `02-epic-decomposition-fabrik` to re-emit the graph, then `04-cross-epic-validation-fabrik`."

## Processing User Request

### Step 1: List All Epic Tickets

Enumerate the ticket files: `ls docs/development/epics/*.md` (or Glob `docs/development/epics/*.md`) — every file `03-expand-epic-files-fabrik` wrote. Read each. (No `list_tickets` — that is Traycer's tool.)

State: "Found [N] epic tickets: [list titles]."

**Ticket-set integrity checks (all must pass — first failure halts dispatch):**

1. **Count match** — `[N] == epic count from 02-epic-decomposition-fabrik Compact Epic Proposal`. On mismatch:
   - **Deficit** (fewer tickets than epics) — name the missing epic(s) by diffing `02`'s compact entries against the ticket-file titles on **epic number + name**. ⚠️ Never diff the literal title strings: the two formats differ by separator — 02 writes `Epic [N]: [Name]`, the tickets `Epic N — [Name]` — so a string diff mismatches on every epic and reports the whole set as both deficit and orphan. State: "Missing tickets: Epic [X] — [name], Epic [Y] — [name]. Re-run `03-expand-epic-files-fabrik` to recreate ONLY the missing tickets (do NOT discard the existing ones). Then re-run `04-cross-epic-validation-fabrik` before returning to 05."
   - **Excess** (more tickets than epics) — name the orphan(s) by diffing the other direction. ⚠️ Two files can match the SAME entry (a stale in-range copy, e.g. `{1,2,3,3,4,5}` for 5 epics) — a set-diff then names ZERO orphans while the count says excess. So classify per file: matches no entry → orphan; two files match one entry → the older date prefix is the stale copy → `rm` it. State: "Orphan ticket files from a prior run: [paths]. Delete them (`rm docs/development/epics/<file>`), then re-run `04-cross-epic-validation-fabrik`. Do NOT proceed with 05 — orphans can mask the dispatch intent."
2. **Title format match** — each ticket Title matches `Epic N — [Name]` (em-dash with single spaces; optional `Retrofit:` prefix in [Name]) per `03-expand-epic-files-fabrik` Step 2. On any mismatch: "Ticket [actual title] does not match `Epic N — [Name]` format — 05 cannot map it to a dependency-graph node. Re-run `03-expand-epic-files-fabrik` to fix the title."
3. **Epic-number contiguity** — extracted epic numbers form `1..N` with no gaps. ⚠️ Check 1 has already passed, so `N` files exist for `N` epics — but check 1 is **count-only**, so a deficit and an orphan can cancel out and reach here (a stale `epic-7` + a partial `03` that never wrote epic 5 → `{1,2,3,4,7}`, count 5, check 1 PASSES; likewise a stale in-range `epic-3` → `{1,2,3,3,4}`). A gap therefore proves a duplicate or an out-of-range number — it does NOT prove nothing is missing.

   On any gap, take **every file whose number is duplicated or outside `1..N`** and diff it against `02`'s compact entries on **epic NAME alone** — ⚠️ NOT on the number: the number is the very thing under suspicion here, so keying on it makes "mis-numbered" unmatchable by construction (a file's number is in the set by definition, so it can never match a MISSING number's entry). Not on the literal title string either — the separators differ, per check 1. Verdict per file, keyed on WHICH entry its name matches:
   - matches `02`'s entry for a number **MISSING from the set** → **mis-numbered**: route to `03-expand-epic-files-fabrik` to renumber that file (title + filename). Name the file, so `03` cannot renumber the genuine one. Never create a new one — that returns an Excess and loops.
   - matches an entry whose correctly-numbered file is **a DIFFERENT file already in the set** → **redundant copy** (the date prefix identifies the stale one; the "different file" clause stops the genuine ticket self-matching and both copies being deleted): `rm docs/development/epics/<file>`; the missing number is then a genuine deficit → re-run `03` to create ONLY it.
   - matches **no** entry in `02`'s proposal → **orphan masking a deficit**: `rm docs/development/epics/<file>`, then re-run `03` to create ONLY the missing ticket(s).
   - matches the entry its OWN number carries → **genuine ticket, no action** — its co-numbered sibling is the copy. ⚠️ Where two files share a number, the **older date prefix** is the stale one: that is what makes "the correctly-numbered file" well-defined, and what stops both copies being deleted.

   This keys on the matched entry, not on "corresponds to a real epic" — a stale file can match a real epic that is already covered, and renumbering it would ship a prior run's body under a missing epic's number.
   In every case, **re-run `04-cross-epic-validation-fabrik` before returning to 05** — the renumbered or recreated ticket has never been validated. ⚠️ `04` takes the Glob file count AS the epic count, so it cannot catch this: check 1 is the chain's only comparison against 02, and it is count-only.

If any of the 3 checks fail, STOP. Do not proceed to Step 2.

### Step 2: Verify Dependency Order

**Source-of-truth order:** PREFER the `Recommended Execution Order` already rendered by `04-cross-epic-validation-fabrik` Step 4 (Report + Hand Off) in the conversation's most recent Validation Report — it's already topologically sorted into Phases. Only re-derive from the Dependency Graph spec if 04's order is absent.

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

"To execute an epic (Delta-feature OR Retrofit — same procedure): select its ticket → run `epic-to-ticket-workflow/00-trigger-fabrik` in **consume mode** (per `epic-to-ticket-workflow/00-trigger-fabrik` § Entry Points → Multi-epic (consume mode) Path B — it reads the epic ticket's Metadata block as the INFRA-CHECK input instead of deriving it from scratch). Then continue through `01-epic-brief-fabrik` (Path B § Step 1 consumes the same Metadata via INFRA-CHECK). The ticket description IS the Epic Brief input."

"Dispatch order — execute one Phase at a time, in order; within a Phase, epics with `⚡` can be worked in any order but the owner runs one `epic-to-ticket-workflow` cycle at a time:"

- Phase 1: [Epic X, Epic Y] — dispatch in any order
- Phase 2: [Epic Z] — dispatch after Phase 1 completes
- ...

"After all epics execute, run `epic-to-ticket-workflow/08-implementation-validation-fabrik` per epic to verify implementation."

## Output Contract

Dispatch instructions presented in conversation (structure-bounded, not document-style — per `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md` item 93). Format:

1. **Phased execution order** — rendered using one of the 4 patterns in Step 2 (multi-phase / single-epic / fully-parallel / fully-sequential), inherited verbatim from `04-cross-epic-validation-fabrik` Step 4 (Report + Hand Off) Recommended Execution Order when present; re-derived from the Dependency Graph spec only when 04's order is absent.
2. **Per-epic dispatch instruction** — invokes `epic-to-ticket-workflow/00-trigger-fabrik` in **consume mode** (per `epic-to-ticket-workflow/00-trigger-fabrik` § Entry Points → Multi-epic (consume mode) Path B; reads the epic ticket's 15-field Metadata block as INFRA-CHECK). Identical procedure for delta-feature and Retrofit epics.
   ⚠️ **Carry the epic's `Owned paths:` into the dispatch** (from the ticket's `### Dependencies`). It becomes the executing agent's **`## File Scope (owned paths)`** — the files it may write, and none other. This is the last hop of the concurrency contract that `02`'s parallel gate (2/3 file-scope, 3/3 migrations) established and `04` § Step 2 lens C validated; **drop it here and the contract is decorative.** A diff touching a path outside the epic's `Owned paths:` is a scope violation, and on a concurrent run it is a collision with a sibling agent.
3. **Post-execution routing** — instructs the owner to run `epic-to-ticket-workflow/08-implementation-validation-fabrik` per epic to verify implementation after all dispatched epics complete.

**Consumed by:** Owner — executes one epic at a time per phase order; within a Phase, epics with `⚡` can be worked in any order.

**Not consumed by:** Any downstream mega-epic-breakdown command — 05 is the final step before owner-driven dispatch via `epic-to-ticket-workflow`.

## Does NOT

- Does NOT write or modify ticket files — `03-expand-epic-files-fabrik` owns `docs/development/epics/`; 05 only reads them (and may `rm` a confirmed orphan **or redundant copy, per Step 1 checks 1 and 3**). It writes no new files.
- Does NOT re-create tickets — that was `03-expand-epic-files-fabrik`.
- Does NOT validate cross-epic consistency — that was done by `04-cross-epic-validation-fabrik` before reaching this step.

## Acceptance Criteria

- `ls docs/development/epics/*.md` confirms all epic ticket files exist.
- Ticket-set integrity confirmed: count matches `02-epic-decomposition-fabrik`'s Compact Epic Proposal; every title matches `Epic N — [Name]`; epic numbers form `1..N` with no gaps.
- Dispatch order stated — inherited from `04`'s Recommended Execution Order, or re-derived from the Dependency Graph ONLY when 04's order is absent.
- Each epic's `Owned paths:` carried into its dispatch as the executing agent's file scope — drop it and the concurrency contract is decorative.
- Route to `epic-to-ticket-workflow` implementation validation stated after execution.
