<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (131 items).
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
4. **Deploy Plan** (when present — may be SKIPPED entirely for code-only Retrofit epics per `04-deploy-plan-command` post-`3060147`) — registrar surface, compose contract, env vars
5. **Ticket Outline** (when present) — batches, parallel groupings, categories, Doc Sync Matrix
6. **Ticket Breakdown** (when present) — full tickets, [PRIMARY PATH] Index, Acceptance Criteria
7. **INFRA-CHECK** — Path A (per `01-epic-brief-command:35`, the authority): Scaffold, Port, **target_vps**, User Guide, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs (**10 required**) + Abuse Detection, Email, FINANCIALS (**3 SaaS-conditional**) = **13 fields**. ⚠️ `Internal APIs` is **informational**, NOT propagated — do not validate it as a propagated field. Path B (multi-epic 15-field block per `ettw/00-trigger-workflow-command` § Entry Points → Multi-epic (consume mode) post-`5a48017` + `1eaf22a`): ALSO Registrars, Universal categories, Epic Flavor (Path B adds exactly 3 — per `01-epic-brief-command:37`).
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
| `HAS_USER_GUIDE` | Epic Brief Metadata → Tech Plan Component Architecture (`docs/user-guide/` surface) → ticket ACs |
| `Scaffold` | Epic Brief → Tech Plan Stack → ticket category |
| `target_vps` | Epic Brief Metadata → Tech Plan DB/cache host (`postgres-main` on vps1; `10.99.0.1` on a spoke) → Deploy Plan target host |
| `Port` | Epic Brief → Tech Plan → compose.yaml → PORTS.md → data/projects.yaml |
| `Internal APIs` *(informational — not a propagated field; check only if material)* | INFRA-CHECK → Tech Plan Component Architecture → ticket Steps |
| `Rule Packs` | Epic Brief Metadata → Tech Plan → ticket Context Files (propagation only — this command does NOT validate pack CONTENT) |
| `Shape` | Tech Plan Shape Block → Deploy Plan registrar surface → compose contract |
| `Concurrency` | INFRA-CHECK → Tech Plan § Concurrency → ticket ACs (async/non-blocking) |
| `i18n` | INFRA-CHECK → Tech Plan § i18n Architecture (Step 4d) → ticket ACs (locale keys) |
| `Responsive` | Brief Metadata → Tech Plan § UI architecture (Step 4d) → ticket ACs (375px–2560px) |
| `Dark+Light` | Brief Metadata → Tech Plan § UI architecture (OS detection + toggle + persistence) → ticket ACs |
| `Registrars` (Path B) | Brief Metadata → Deploy Plan Step 4 Registrar Surface Map → compose.yaml — verify cross-check rule from `04-deploy-plan-command` post-`3060147` |
| `Universal categories` (Path B) | Brief Metadata → Tech Plan Architecture scope (per `03-tech-plan-command` Step 1 Path B branch post-`c41bb0b`) + Ticket Outline scope constraint (per `05-ticket-outline-command` Multi-epic dispatch mode post-`ff2c427`) |
| `Epic Flavor` (Path B) | Brief Metadata → ettw/02 Core Flows scope-narrow + ettw/03 Tech Plan per-step targeting + ettw/04 Skip rule + ettw/06 Mandate scoping + ettw/07 Epic Closure dispatch + ettw/08 validation thresholds + ettw/09 30% threshold + this Dimension 7 |
| `Abuse Detection` (SaaS-conditional, both paths) | Brief Metadata → Tech Plan vendor selection (`fabrik-lib/abuse-prevention/`) → ticket ACs per `saas/87-abuse-detection.md` |
| `Email` (SaaS-conditional, both paths) | Brief Metadata → Tech Plan vendor selection (`fabrik-lib/email-templates/`) → ticket ACs (two-stream separation per `core/86-email-templates.md`) |
| `FINANCIALS` (SaaS-conditional, both paths) | Brief Metadata → `05-ticket-outline-command` Step 6b doc matrix → ticket assignment for `docs/FINANCIALS.md` per `saas/88-saas-launch-checklist.md` |

#### Dimension 7 — Ticket Structure (per ticket-breakdown contract)

For every ticket, verify present:
- [ ] Documentation Sync Matrix ACs injected (per ticket's Scope triggers)
- [ ] Final Gate Instruction — **one of TWO valid commands**: `python scripts/final_gate.py --json` (Tier-2, every normal ticket) or `--systemic --json` (Tier-3, the Epic Closure ticket). ⚠️ `--lean --json` is **NEVER** valid as a Final Gate Instruction (`CLAUDE.md` § Completion Contract)
- [ ] `Lessons Learnt:` line in Completion Self-Check
- [ ] Agent-aware first-output line in Governance Checklist
- [ ] No-git-commands in DO NOT
- [ ] [PRIMARY PATH] test AC (if ticket touches a [PRIMARY PATH] flow)
- [ ] Epic Closure ticket (Tier 3, depends on all, full field set) — **Delta-feature default; OPTIONAL for Retrofit epics** where `06-ticket-breakdown` correctly skipped per its Step 10 Retrofit branch (post-`8dcdd2b`). When absent, verify ticket-breakdown's batch presentation explicitly stated `Epic Closure: skipped (Retrofit — [reason])`. Missing closure WITHOUT a skip statement = finding.
- [ ] Parallelism budget — **Delta-feature: ≥3:1** (outline's total tickets ÷ longest chain). **Retrofit (3-5 tickets total): ≥1:1** — a linear 3-ticket chain like `Retrofit: i18n` (locale-loader → validator → tr.json) is a legitimate 1:1 ratio and should NOT fail.

**Retrofit-epic adjustments to Dimensions 1-7 (when `Epic Flavor: Retrofit` propagated from `01-epic-brief-command` Metadata post-`6f3e1b2`):**

- **Deploy Plan absence (Dimensions 5 + 6 Shape/Registrars rows):** if `04-deploy-plan-command` SKIPPED entirely per its Retrofit Skip rule (post-`3060147`), propagation chain for Registrars/Shape ends at Tech Plan. State `Deploy Plan: skipped per Retrofit branch` and skip the Deploy Plan → compose.yaml leg of those rows; do not flag as broken propagation.
- **Core Flows absence (Dimensions 1 + 2):** if `02-core-flows-command` produced no flows for a code-only retrofit (post-`ee8792c` scope-narrow branch), Dimension 1 (Brief ↔ Flow traceability) and Dimension 2 (Flow ↔ Tech Plan) become N/A; do not flag missing flows as a finding.
- **Mandate-scope expectation (Dimension 6 i18n/Responsive/Dark+Light rows):** for Retrofit tickets, mandate propagation chain applies ONLY to the target area per `06-ticket-breakdown` Step 4 Retrofit branch (`8dcdd2b`). E.g., `Retrofit: i18n` → verify i18n propagation; do NOT flag missing Responsive/Dark+Light propagation in non-i18n tickets.
- **Success Criteria count expectation (Dimension 1):** Retrofit Brief is 3-5 SC per `mega-epic-breakdown/03-expand-epic-files-command` § Success Criteria; verify all 3-5 trace to tickets but do not flag SC count <5 as Significant.
- **Compliance Report propagation (multi-epic existing mode):** for Retrofit epics emitted from `mega-epic-breakdown/02-epic-decomposition-command` Compliance Report fix-now rows, verify the gap row's authority pack appears in the Tech Plan + ticket `Rule Packs` lists. Cite the specific row (e.g., "Retrofit:i18n closes Compliance Report row for `core/86-i18n-validation`").

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

## Does NOT

- Does NOT execute tickets — that is `07-execute-command`. ettw/10 reports findings; user decides actions per Step 3 advisory pattern (matches `ettw/08-implementation-validation-command` § Role "advisory, not authoritative").
- Does NOT validate implementation correctness (impl-vs-spec) — that is `08-implementation-validation-command`. ettw/10 is spec-vs-spec; ettw/08 reads code. Both run; they validate different surfaces.
- Does NOT propagate changes through the artifact set — that is `09-revise-requirements-command`. ettw/10 FINDS contradictions; user runs revise-requirements to RESOLVE them per Step 6 follow-up.
- Does NOT deploy — that is `11-deploy-command`. ettw/10 is a pre-deploy consistency gate.
- Does NOT change ticket Title prefixes — Delta-feature stays `T<n> — <action verb>`; Retrofit stays `T<n> — Retrofit: <area>` per `mega-epic-breakdown/03-expand-epic-files-command` § Step 2.
- Does NOT flag missing Epic Closure ticket for Retrofit epics where `06-ticket-breakdown` correctly skipped it (post-`8dcdd2b` Step 10 Retrofit branch) — per Step 2 Dimension 7 Retrofit branch, Epic Closure presence is conditional on Epic Flavor + ticket-breakdown's explicit skip statement.
- Does NOT flag missing Deploy Plan when `04-deploy-plan-command` was SKIPPED entirely per its Retrofit Skip rule (post-`3060147`) — per Step 1 Retrofit branch and Step 2 Retrofit-epic adjustments, missing Deploy Plan is valid for code-only retrofits.
- Does NOT enforce parallelism budget ≥3:1 for Retrofit epics — Retrofit epics have 3-5 tickets total; a 3-ticket linear chain is a legitimate 1:1 ratio that should NOT fail.
- Does NOT trust auto-detection of "Accepted deviation" markers — when unsure whether a difference is intentional, present as finding and ask user per L83. The marker requirement is one-way: marker present → intentional; marker absent → finding.
- Does NOT propose `revise-requirements` from within findings — Step 6 suggests follow-up commands; never run `09-revise-requirements-command` recursively from inside ettw/10 itself.
- Does NOT validate rule pack content — rule pack enforcement is the producer commands' job (ettw/01-06). ettw/10 verifies the propagation chain (does the Rule Packs field propagate Brief → Tech Plan → ticket?), not the rule pack semantics themselves.
- Does NOT re-derive INFRA-CHECK fields — consume from Epic Brief Metadata verbatim per Step 1. Path B fields (Registrars, Universal categories, Epic Flavor, etc.) MUST flow through Dimension 6; missing routes back to `00-trigger-workflow-command`.

## Acceptance Criteria

- All artifact surfaces internalized (Brief, Flows, Tech Plan, Deploy Plan, Outline, Tickets, INFRA-CHECK, lifecycle, LESSONS_LEARNT).
- All 8 dimensions analyzed. Findings classified by significance.
- INFRA-CHECK propagation verified for all **13** Path A fields (10 required + 3 SaaS-conditional) OR all **15** Path B fields + Epic Flavor (Path B multi-epic dispatch per `ettw/00-trigger-workflow-command` § Entry Points → Multi-epic (consume mode) post-`5a48017`+`1eaf22a`).
- Ticket structure verified (Doc Sync Matrix, Final Gate, Lessons Learnt, first-output, no-git, [PRIMARY PATH], Epic Closure, parallelism budget).
- LESSONS_LEARNT coherence verified (entries match, numbering sequential, no spec contradictions).
- Findings presented: overall assessment → significant → minor (batched).
- Artifacts updated surgically. No new contradictions introduced.
- Tickets reconciled against grounded specs. Escape hatch at >50% drift.
- Done-but-affected: three-option matrix presented.
- Next steps suggested based on outcome.
