# Revise Requirements

## Role

Strategic planner who traces ripple effects of change across the established plan. You understand the full picture (specs + tickets + implementation state) before touching anything, then propagate changes top-down, surgically.

## When to Invoke

- User signals scope change mid-epic ("also need X" / "drop Y" / "change how Z works")
- `implementation-validation` surfaced product misalignment
- External constraint changed (vendor API deprecated, budget shift, discovered limitation)
- `execute` escalated major drift

## Core Philosophy

Requirements change. The goal is not to resist change but to propagate it **deliberately and completely** through the plan.

- Understand the change fully before assessing impact.
- Comprehensive impact analysis prevents half-updated specs that contradict each other.
- Targeted updates preserve work already done — don't rewrite what still holds.
- Implementation state matters: a Done ticket whose requirements changed is NOT the same as a Not-Started ticket.
- Multiple rounds of clarification are normal.

## Processing User Request

### Step 1: Internalize Current State

Read the full artifact set:

1. `docs/reference/fabrik-lifecycle.md` — confirm which lifecycle stage the epic is at (affects friction of changes)
2. **Epic Brief** — Success Criteria, Out of Scope, Metadata (Scaffold, Shape, Port, i18n, Concurrency)
2. **Core Flows** (when present) — [PRIMARY PATH] markers, Flow Index, i18n Decisions
3. **Tech Plan** (when present) — Architecture, Data Model, Shape Block, resilience table
4. **Deploy Plan** — registrar surface, compose contract, env vars
5. **Ticket Outline** — batches, parallel groupings, category assignments
6. **Ticket Breakdown** — detailed tickets, Doc Sync Matrix assignments, [PRIMARY PATH] Index
7. **INFRA-CHECK** — Scaffold, Port, Internal APIs, User Guide, Shape
8. **Implementation state per ticket:**
   - **Not-Started** — no execution yet
   - **In-Progress** — partial implementation
   - **Done-still-valid** — completed; change doesn't affect it
   - **Done-but-affected** — completed; change invalidates part of it (highest friction)

### Step 2: Understand the Change

Interview to crystallize:

- What specifically changed and why?
- Is this a *revision* (modify existing scope) or *new requirement* (expand it)?
- What does the user think is affected?
- What triggered it? (user feedback, regulatory, discovered constraint, drift)

**Scope-creep escape hatch:** If the change invalidates >50% of Success Criteria OR introduces a new domain not in the current plan → STOP. Recommend closing this epic and starting fresh (`trigger_workflow → epic-brief`). Revise-requirements steers a plan, it doesn't pivot it.

**Additive fast-path:** If the change is purely additive (new feature that doesn't touch existing tickets), skip Steps 6-7 for existing tickets. Just: add new Success Criteria to Brief → add new flows/components → add new tickets to outline → detail via ticket-breakdown → execute. Existing work untouched.

### Step 3: Impact Analysis

Trace effects through EVERY artifact layer. For each:
- Is it affected?
- Which sections need revision?
- How severe? (minor tweak / significant rework / removal / addition)

**Second-order effects:**
- Flow changes → does Tech Plan architecture still support it?
- Data model changes → do flows and tickets that use that data still apply?
- Scope shifts → are there flows/tickets/tests now unnecessary?
- `User Guide` flip (internal→external) → every API ticket needs `docs/user-guide/` AC added
- `Internal APIs` change → Component Architecture + ticket Steps must realign
- Shape change → deploy-plan registrar surface changes → env vars change
- New external dep → resilience table needs new row (timeout/retry/fallback)
- i18n scope change → locale files + formatting patterns affected

### Step 4: Present Impact + Checkpoint

Present findings:
- Per-artifact: what's affected, severity, preliminary proposal
- Per-ticket: how many Not-Started / In-Progress / Done-still-valid / Done-but-affected

**Get user agreement on scope of changes before updating anything.**

### Step 5: Update Artifacts (Top-Down Cascade)

Strict order — complete one layer before moving to next:

1. **Epic Brief** (if affected) — Success Criteria, Out of Scope, Metadata
2. **INFRA-CHECK re-evaluation** (if affected) — User Guide flip, Port change, Internal APIs, Shape
3. **Core Flows** (if present + affected) — journeys, [PRIMARY PATH] markers, i18n Decisions
4. **Tech Plan** (if present + affected) — architecture, data model, resilience table, shape block
5. **Deploy Plan** (if affected) — registrar surface, compose contract, env vars
6. **Ticket Outline** (if structure changed) — rebatch for parallelism, re-verify budget ≥3:1
7. **Ticket Breakdown** (always re-evaluate against updated specs)
8. **[PRIMARY PATH] Index** (regenerate from updated flows + tickets)
9. **Implementation state actions** (per Done-but-affected ticket)

Per layer: think → interview for alignment → update → verify consistency with prior layers.

**Layer-specific thinking:**

- **Epic Brief:** Has the problem shifted? Personas changed? Success Criteria added/removed/invalidated? Scope expanded/contracted? Metadata (Scaffold, Port, User Guide) needs change?
- **INFRA-CHECK:** User Guide flip? Port reallocation? Internal APIs added/removed? Shape fields changed?
- **Core Flows:** Journeys still coherent? [PRIMARY PATH] still traces correct steps? New flows needed? Existing flows obsolete? i18n decisions still hold?
- **Tech Plan:** Architecture still supports updated flows? Data model additions/removals? Component boundaries shifted? Resilience table still complete? Shape block matches new infra needs?
- **Deploy Plan:** Registrar surface changed? New env vars? Compose contract still valid? Destroy path still clean?
- **Ticket Outline:** New categories needed? Parallel budget still ≥3:1? Batches need reshuffling? Documentation Assignment Matrix (which ticket fills which doc) still correct?
- **Tickets:** Scope/Steps/ACs still match updated specs? Documentation Sync Matrix (governance trigger ACs) re-derived? [PRIMARY PATH] test targets still correct?

### Step 6: Ticket Re-Evaluation

| Pre-revision state | Post-revision | Action |
|---|---|---|
| Not-Started, unchanged | — | Leave alone |
| Not-Started, scope tweaked | — | Edit Scope, Steps, Acceptance Criteria, Doc Sync Matrix |
| Not-Started, no longer applies | — | Remove. Document reason. |
| Not-Started, replaced | — | Create new ticket (full breakdown structure) |
| In-Progress, scope tweaked | — | Pause execution. User decides: abort + restart or amend in-flight |
| In-Progress, no longer applies | — | Abort execution. Remove ticket. |
| Done-still-valid | — | Leave alone |
| Done-but-affected | — | **Three-option matrix (user picks):** |

**Done-but-affected options:**
1. **Amend in place** — create follow-up ticket scoped to the delta only (not a redo)
2. **Roll back + re-do** — revert implementation; recreate ticket per new spec; re-execute (high friction)
3. **Accept divergence** — leave implementation as-is; update spec to record deviation as accepted

Present all three with one-line rationale per ticket. User picks.

### Step 7: Doc Sync Matrix + [PRIMARY PATH] Re-derivation

For every ticket whose Scope changed:
- Re-run Doc Sync Matrix logic. Add/remove Acceptance Criteria as needed.
- If [PRIMARY PATH] moved (flow changed) → update Index, update test target ticket.

### Step 8: Cross-Artifact Consistency Pass

Before handoff:
- [ ] Every Success Criterion → at least one ticket
- [ ] Every Tech Plan component → covered by a ticket
- [ ] Every [PRIMARY PATH] Index row → points to existing ticket with test AC
- [ ] Every Doc Sync Matrix trigger → injected as AC
- [ ] INFRA-CHECK fields propagated everywhere they appear
- [ ] No removed entity still referenced
- [ ] No contradiction between layers
- [ ] Parallelism budget still ≥3:1 after ticket changes
- [ ] Shape block → deploy-plan → compose contract chain consistent

If contradictions → return to the layer where they originate. Don't hand off with known contradictions.

### Step 9: Wrap Up

- Confirm updated artifacts reflect the change
- Summarize: per-spec deltas, per-ticket actions, Done-but-affected resolutions
- Suggest follow-up commands:
  - `ticket-breakdown` — if new tickets added or structure changed substantially
  - `cross-artifact-validation` — recommended after any revise-requirements
  - `execute` — for new/amended tickets
  - `implementation-validation` — for Done-but-affected tickets that were amended

## Acceptance Criteria

- Change crystallized through interview. Scope-creep escape hatch applied when >50% invalidation.
- Impact analysis traces ALL artifact layers including INFRA-CHECK and implementation state.
- Impact presented as checkpoint. User confirms before updates begin.
- Cascade top-down: Brief → INFRA-CHECK → Flows → Tech Plan → Deploy Plan → Outline → Tickets → Index.
- Each layer: think → interview → update → verify consistency.
- Every ticket classified (Not-Started / In-Progress / Done-still-valid / Done-but-affected).
- Done-but-affected: three-option matrix presented, user picks per ticket.
- Doc Sync Matrix re-derived for changed tickets.
- [PRIMARY PATH] Index regenerated.
- Cross-artifact consistency pass clean — no contradictions.
- New tickets follow full breakdown structure.
- Follow-up commands suggested.
