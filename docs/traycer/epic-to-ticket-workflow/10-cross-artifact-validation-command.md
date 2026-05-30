<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (123 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Cross-Artifact Validation

## Role

Reviewer who validates consistency across artifact boundaries — the seams where specs connect with each other, where tickets derive from specs, and where INFRA-CHECK fields propagate downstream.

Focus on:
- **Cross-cutting analysis** — how artifacts relate to each other, not internal quality of individual ones.
- **The joints** between artifacts, not re-reviewing internals.
- **Grounding in specific references** — cite which spec/ticket/field says what.

This command does NOT:
- Re-review internal quality of individual specs.
- Validate code vs. spec — that's `implementation-validation`.
- Propagate requirement changes — that's `revise-requirements`.

## Core Philosophy

One question: ***"Are the artifacts in a state we can confidently act on?"***

Specs are truth — ground those first. Tickets are derivatives — check against grounded specs. INFRA-CHECK fields are a contract — verify the propagation chain. Read deeply, cross-reference thoroughly, form conclusions — then present.

## When to Invoke

- Before ticket-outline (after deploy-plan confirms shape).
- After `revise-requirements` propagated changes.
- After `execute` if any drift was noted.
- When user suspects inconsistency.

## Processing User Request

### Step 1: Internalize All Artifacts

Read in order:

1. **Epic Brief** — Success Criteria, Out of Scope, Metadata (Scaffold, Shape, Port, i18n, Concurrency)
2. **Core Flows** (when present) — [PRIMARY PATH] markers, Flow Index, i18n Decisions, Microcopy Hot-Spots
3. **Tech Plan** (when present) — Architecture, Data Model, Component Architecture, Shape Block, resilience table, Stack block
4. **Deploy Plan** — registrar surface, compose contract, env vars
5. **Ticket Outline** (when present) — batches, parallel groupings, categories, Doc Sync Matrix
6. **Ticket Breakdown** (when present) — full tickets, [PRIMARY PATH] Index, Acceptance Criteria
7. **INFRA-CHECK** — Scaffold, Port, Internal APIs, User Guide, Shape, Concurrency, i18n, Rule Packs
8. `docs/operations/fabrik-lifecycle.md` — which stage the epic is at
9. `docs/LESSONS_LEARNT.md` — accumulated entries from prior execution

For scaffolds without Core Flows or Tech Plan (per routing): derive from Success Criteria. Don't flag intentional absence.

Build the mental model: Success Criteria ↔ flows ↔ components ↔ tickets ↔ tests ↔ docs ↔ INFRA-CHECK.

**Multi-pass for large epics (>8 tickets):**

| Pass | Dimensions | Why first |
|---|---|---|
| 1 — Mechanical | 6 (INFRA-CHECK), 7 (Ticket Structure), 8 (LESSONS_LEARNT) | Objective checks, highest hit rate for missed fields |
| 2 — Tracing | 2 (Coverage), 3 (Interface), 5 (Assumptions) | Finds structural gaps between artifacts |
| 3 — Judgment | 1 (Conceptual), 4 (Specificity) | Requires reading + reasoning, lowest urgency |

Small epics (≤8 tickets): all dimensions in one pass.

### Step 2: Cross-Referential Analysis (8 Dimensions)

**Tracing procedure:** For Dimension 2 (Coverage), build an explicit mapping table:

```
| SC# | Success Criterion | Flow | Component | Ticket | Test |
|-----|-------------------|------|-----------|--------|------|
| 1   | Users can create projects | Create Project flow | ProjectService | T4 | tests/integration/test_create_project.py |
| 2   | ... | ... | ... | ... | ... |
```

Any empty cell = finding. This prevents things slipping through.

**Intentional vs accidental differences:** If a Tech Plan section says "Accepted deviation: [reason]" or a ticket's Spec References explicitly notes a departure — that's intentional. If there's no such marker and the artifacts simply disagree — that's a finding. When unsure, present as finding and ask user.

#### Dimension 1 — Conceptual Consistency

- **Terminology drift** — same concept, different names across artifacts.
- **Contradictory characterizations** — Brief says admin-only, flow shows regular user doing it.
- **Persona drift** — personas in Core Flows match Epic Brief audience.

#### Dimension 2 — Coverage Traceability (Bidirectional)

- **Forward:** every Success Criterion → flow → component → ticket with AC covering it.
- **Reverse:** every Tech Plan component → traceable to a Success Criterion. Every ticket → traceable to a component.
- **Orphans:** requirements with no flow, tech decisions solving unstated problems, tests without corresponding ticket scope.

#### Dimension 3 — Interface Alignment

- Data flows reference → exists in Data Model.
- Interactions in flows → components in Tech Plan.
- `Internal APIs` in INFRA-CHECK → referenced (not redesigned) in Component Architecture → appear in ticket Steps.
- Microcopy Hot-Spots → map to UI components and tickets.
- Resilience table entries → match actual external deps in ticket Steps.

#### Dimension 4 — Specificity

Areas where a coder would be forced to guess:
- Vague flow descriptions deferring decisions to code time.
- Tech Plan stubs ("TBD", "decide during implementation").
- Ticket Steps with unspecified files, conditional language, compound actions.
- Acceptance Criteria requiring human judgment instead of objective checks.

#### Dimension 5 — Assumption Coherence

- Brief assumes real-time but Tech Plan designs batch → finding.
- Brief Out of Scope excludes X but a ticket implements it → finding.
- Tech Plan Stack says one thing but tickets reference different → finding.
- Shape block says `needs_cache: false` but code uses Redis → finding.

#### Dimension 6 — INFRA-CHECK Propagation

Verify the contract flows correctly through the chain:

| Field | Must appear consistently in |
|---|---|
| `HAS_USER_GUIDE` | Epic Brief Metadata → ticket ACs (`docs/user-guide/`) |
| `Scaffold` | Epic Brief → Tech Plan Stack → ticket category |
| `Port` | Epic Brief → Tech Plan → compose.yaml → PORTS.md → data/projects.yaml |
| `Internal APIs` | INFRA-CHECK → Tech Plan Component Architecture → ticket Steps |
| `Shape` | Tech Plan Shape Block → Deploy Plan registrar surface → compose contract |
| `Concurrency` | INFRA-CHECK → Tech Plan § Concurrency → ticket ACs (async/non-blocking) |
| `i18n` | INFRA-CHECK → Tech Plan § i18n Architecture → ticket ACs (locale keys) |

#### Dimension 7 — Ticket Structure (per ticket-breakdown contract)

For every ticket, verify present:
- [ ] Documentation Sync Matrix ACs injected (per ticket's Scope triggers)
- [ ] Final Gate Instruction (one of three valid commands)
- [ ] `Lessons Learnt:` line in Completion Self-Check
- [ ] Agent-aware first-output line in Governance Checklist
- [ ] No-git-commands in DO NOT
- [ ] [PRIMARY PATH] test AC (if ticket touches a [PRIMARY PATH] flow)
- [ ] Epic Closure ticket (Tier 3, depends on all, full field set)
- [ ] Parallelism budget ≥3:1 (outline's total tickets ÷ longest chain)

#### Dimension 8 — LESSONS_LEARNT.md Coherence

- Entries match ticket activity (every triggered ticket has a `# Lesson <N>:` heading).
- Sequential numbering (duplicates = parallel-execution artifact).
- No contradictions with current specs (superseded entries marked, not deleted).
- Filename is `docs/LESSONS_LEARNT.md` (uppercase).

### Step 3: Present Findings

**Lead with overall assessment:** coherent story or not? Why?

**Then by significance:**
- **Blockers** — broken cross-artifact contracts, missing ticket fields, Success Criteria with no coverage.
- **Significant** — interface misalignment, assumption contradictions, specificity gaps.
- **Minor** — terminology drift, trivial wording. Batch these with proposed fixes.

For each: what's wrong + which artifacts + why it matters.
Consolidate related findings (same root cause = one finding).
Interview questions for judgment-needed items.

**Example findings:**

```
❌ BLOCKER: Coverage gap — SC#3 "Users can search projects" has no covering ticket
   Brief: Success Criterion #3 defines search as core
   Tech Plan: MeiliSearch index designed (§ B. Data Model)
   Tickets: No ticket has search in Scope or Acceptance Criteria
   Impact: Search feature will not be implemented.

⚠️ SIGNIFICANT: Interface misalignment — column name drift
   Core Flows § Create Project, step 3: "System assigns owner_id"
   Tech Plan § B Data Model: column is `created_by_user_id`
   Impact: Coder will use wrong column name or guess.

ℹ️ MINOR (batch fix): Terminology — Brief says "tenant", Tech Plan says "workspace"
   Proposed: standardize on "tenant" everywhere. Approve?
```

### Step 4: Update Artifacts

Based on user direction:
- Surgical updates. Don't rewrite what's fine.
- Re-verify against relevant dimensions after each update (no new contradictions introduced).
- INFRA-CHECK violations: propagate fix through the full chain.

### Step 5: Ticket Reconciliation (if tickets exist)

Compare tickets against updated specs:
- Tickets referencing outdated decisions, superseded architecture, stale terminology.
- Tickets for descoped work.
- Missing tickets for new scope.
- Shifted dependencies.
- Missing Documentation Sync Matrix injections (governance triggers from 06), Final Gate, Lessons Learnt, [PRIMARY PATH] test ACs.
- Documentation Assignment Matrix (from 05) entries — is each assigned doc actually filled by its ticket?

**Escape hatch:** if >50% of tickets need substantial rework → recommend `ticket-breakdown` re-run.

**Done-but-affected tickets:** present three-option matrix (amend / rollback / accept divergence). User picks.

### Step 6: Suggest Next Steps

- Tickets reconciled → `execute` or `implementation-validation`
- No tickets → `ticket-breakdown`
- Recommended re-run → `ticket-breakdown`
- Done-but-affected amended → `execute` new tickets → `implementation-validation`

## Acceptance Criteria

- All artifact surfaces internalized (Brief, Flows, Tech Plan, Deploy Plan, Outline, Tickets, INFRA-CHECK, lifecycle, LESSONS_LEARNT).
- All 8 dimensions analyzed. Findings classified by significance.
- INFRA-CHECK propagation verified for all 7 fields.
- Ticket structure verified (Doc Sync Matrix, Final Gate, Lessons Learnt, first-output, no-git, [PRIMARY PATH], Epic Closure, parallelism budget).
- LESSONS_LEARNT coherence verified (entries match, numbering sequential, no spec contradictions).
- Findings presented: overall assessment → significant → minor (batched).
- Artifacts updated surgically. No new contradictions introduced.
- Tickets reconciled against grounded specs. Escape hatch at >50% drift.
- Done-but-affected: three-option matrix presented.
- Next steps suggested based on outcome.
