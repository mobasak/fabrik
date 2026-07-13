<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (131 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

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

1. `docs/operations/fabrik-lifecycle.md` — confirm which lifecycle stage the epic is at (affects friction of changes)
2. **Epic Brief** — Success Criteria, Out of Scope, Metadata (Scaffold, Shape, Port, i18n, Concurrency, **Epic Flavor** for Path B per `01-epic-brief-command` post-`6f3e1b2`)
3. **Core Flows** (when present) — [PRIMARY PATH] markers, Flow Index, i18n Decisions
4. **Tech Plan** (when present) — Architecture, Data Model, Shape Block, resilience table
5. **Deploy Plan** (when present — may be SKIPPED entirely for code-only Retrofit epics per `04-deploy-plan-command` post-`3060147`) — registrar surface, compose contract, env vars
6. **Ticket Outline** — batches, parallel groupings, category assignments
7. **Ticket Breakdown** — detailed tickets, Doc Sync Matrix assignments, [PRIMARY PATH] Index
8. **INFRA-CHECK** — Path A: Scaffold, Port, Internal APIs, User Guide, Shape. Path B: ALSO Registrars, Universal categories, Epic Flavor per `00-trigger-workflow-command` post-`1eaf22a`.
9. **Implementation state per ticket:**
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

**Retrofit-epic adjustments (when `Epic Flavor: Retrofit` propagated from `01-epic-brief-command` Metadata post-`6f3e1b2`):**

- **Tighter scope-creep escape hatch:** Retrofit Briefs are 3-5 SC (per `mega-epic-breakdown/03-expand-epic-files-command` § Success Criteria). Losing even 2 SC = 40-67% invalidation. Use a **30% absolute SC-loss threshold for Retrofits** (instead of 50%) — beyond that, the retrofit is the wrong scope; close it and re-decompose via `mega-epic-breakdown/02-epic-decomposition-command`.
- **Retrofit boundary check:** if the change ADDS scope that wouldn't fit a single rule-pack area (per `mega-epic-breakdown/03-expand-epic-files-command` § Step 2 Retrofit naming convention `Retrofit: <area>`), the epic has stopped being a Retrofit. Recommend closing this epic, re-running `mega-epic-breakdown/02-epic-decomposition-command` to re-decompose as a Delta-feature epic, then `mega-epic-breakdown/03-expand-epic-files-command` to retitle (drop the `Retrofit:` Title prefix).
- **Top-down cascade skips (Step 5):** for Retrofit epics where `04-deploy-plan-command` was SKIPPED entirely per its Retrofit Skip rule (post-`3060147`), Step 5 cascade skips the Deploy Plan layer. State explicitly: "Deploy Plan: skipped per Retrofit branch; no cascade needed at this layer." Same applies to Core Flows (post-`ee8792c` scope-narrow branch may produce no flows for code-only retrofits).
- **Done-but-affected rollback warning (Step 6 option 2):** "Roll back + re-do" for Retrofit tickets carries extra risk — the prior Delta-feature Epic Closure may have validated against the OLD retrofit state. State explicitly in option 2: "WARNING: prior Delta-feature closure validated against old retrofit state; rollback requires re-running `08-implementation-validation` on the Delta-feature scope too."
- **User Guide flip immunity (L78):** Retrofit epics typically don't flip User Guide — the parent project's User Guide stays. Flag any `User Guide` change in a Retrofit epic as a scope-leak signal; route to the Retrofit boundary check above.
- **New ticket Title convention (Step 6):** new tickets emitted from a Retrofit epic keep the parent epic's Title prefix — Retrofit epics emit `T<n> — Retrofit: <area>`; Delta-feature epics emit `T<n> — <action verb>` per `mega-epic-breakdown/03-expand-epic-files-command` § Step 2.

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

## Does NOT

- Does NOT execute tickets — that is `07-execute-command`. ettw/09 pauses execution (per L126), updates specs, then suggests `execute` for new/amended tickets per Step 9.
- Does NOT run the standalone cross-artifact audit — Step 8 Cross-Artifact Consistency Pass is a HANDOFF GATE during revision; the separate post-fact audit is `10-cross-artifact-validation-command`, suggested as follow-up per L165.
- Does NOT validate implementation correctness — that is `08-implementation-validation-command`, suggested for Done-but-affected tickets per L167.
- Does NOT deploy — that is `11-deploy-command`. ettw/09 stops before deploy when scope changes; deploy resumes after the updated chain completes.
- Does NOT restart the epic from scratch — when >50% Success Criteria are invalidated (per L63 Delta-feature, or >30% per the Retrofit branch above), recommend closing the epic and starting fresh via `trigger_workflow → epic-brief`. revise-requirements steers a plan, it doesn't pivot it.
- Does NOT silently absorb mid-flight scope changes — every change goes through Step 4 Checkpoint with explicit user agreement per L90; never proceed to Step 5 cascade without confirmation.
- Does NOT change ticket Title prefixes — Delta-feature stays `T<n> — <action verb>`; Retrofit stays `T<n> — Retrofit: <area>` per `mega-epic-breakdown/03-expand-epic-files-command` § Step 2. New tickets follow the same convention as the epic's Epic Flavor.
- Does NOT propagate changes to the upstream Compliance Report — Compliance Report lives at `mega-epic-breakdown/00-trigger-workflow-command` EXISTING mode Step E3.C; mid-epic changes route there only when the gap row itself changed (rare). Otherwise, the Retrofit epic adjusts within its scope without touching upstream.
- Does NOT skip the top-down cascade order — Step 5 strict order prevents contradictions. Lower-layer updates without upper-layer confirmation introduce drift; this is the single biggest source of half-updated specs (Core Philosophy L29).
- Does NOT change the Epic Flavor (Delta-feature ↔ Retrofit) — Flavor flips require re-decomposition at `mega-epic-breakdown/02-epic-decomposition-command`. Within revise-requirements, Flavor is immutable.
- Does NOT propose `revise-requirements` recursively — Step 8 contradictions return to the originating layer; never spawn a nested revise-requirements call.

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
