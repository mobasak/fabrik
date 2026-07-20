<!-- ⚠️ FABRIK FACTORY WORKFLOW — CROSS-ARTIFACT VALIDATION (our own, tool-capable twin of
     10-cross-artifact-validation-fabrik). Run DIRECTLY by our orchestrator agent (Opus 4.8, via the
     driver) — never pasted into a planner GUI.
     THIS IS THE CROSS-CUTTING INTEGRATION REVIEW + 09-REVISE'S PAIRED REVIEW (north star § Command-chain
     build plan — CC5): the SPEC-vs-SPEC pass that validates the seams BETWEEN artifacts (Decisions Lock ↔ Flows ↔
     Tech Plan ↔ Deploy Plan ↔ tickets ↔ INFRA-CHECK). Distinct from 08 (code-vs-spec). Opus orchestrates
     reviewer agents (find cross-artifact drift) AND fixup agents (correct the artifacts/tickets), loops the
     artifact set to a no-op, and DOES NOT STOP until it validates clean — halting only on the 3 BLOCKED
     cases. A change that needs full top-down PROPAGATION routes to `09-revise-requirements-fabrik`.

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · the plan artifacts — Decisions Lock (`01-decisions-lock-fabrik`) · Core Flows (`02-core-flows-fabrik`) ·
         Tech Plan (`03-tech-plan-fabrik`) · Deploy Plan (`04-deploy-plan-fabrik`) · Ticket Outline
         (`05-ticket-outline-fabrik`) · Ticket Breakdown (`06-ticket-breakdown-fabrik` output, which
         carries the `[PRIMARY PATH]` Index)
       · the INFRA-CHECK — Path A (`00-trigger-fabrik` output / Decisions Lock Metadata) OR the dispatched epic
         file on disk (Path B — `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md`)
       · `docs/operations/fabrik-lifecycle.md` (the epic's stage) · `docs/LESSONS_LEARNT.md` (accumulated
         entries)
       · during fixup — each returned agent's diff + its `final_gate.py --json` output
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Cross-Artifact Validation

## Role

The **cross-artifact (spec-vs-spec) review orchestrator** — Opus 4.8, running the driver's loop `[canonical: docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md]`. It validates the **seams between artifacts** — where specs connect, where tickets derive from specs, where INFRA-CHECK fields propagate downstream — NOT the internal quality of any single artifact. It dispatches reviewer agents to find cross-artifact drift and fixup agents to correct it, and **loops the artifact set to a no-op — it does not stop and ask** except on the three BLOCKED cases. A finding that needs full top-down propagation routes to `09-revise-requirements-fabrik`.

**Where it runs** (CC5 — the cross-cutting integration review + `09`'s paired review) `[canonical: north star § Command-chain build plan — CC5, "10-cross-artifact-validation is the cross-cutting integration review (plan→execute boundary + 09-revise's review)"]`: as the **plan→execute integration gate** — canonically after `06-ticket-breakdown-fabrik` produces the tickets and before `07-execute-fabrik` (the CC5 plan→execute boundary, when all artifacts including tickets exist), and optionally earlier as a spec-only consistency check after `04-deploy-plan-fabrik` confirms shape and before `05-ticket-outline-fabrik` (when the Ticket Outline/Breakdown do not yet exist); as **`09`'s paired review** (after `09` propagates a change — did the cascade leave the artifacts consistent?); and after `07-execute-fabrik` if drift was noted.

## Core Philosophy

One question: **"Are the artifacts in a state we can confidently act on?"** — the joints, not the internals.

- **Specs are truth; tickets are derivatives; INFRA-CHECK fields are a contract.** Ground the specs first, check tickets against grounded specs, verify the INFRA-CHECK propagation chain. This is **spec-vs-spec**; the **code-vs-spec** pass is `08-implementation-validation-fabrik` — both run, on different surfaces.
- **Every finding cites the artifacts** — which spec/ticket/field says what, at `path:line`. A finding without the two conflicting sources named is not a finding.
- **Autonomous between the two human gates** `[canonical: north star § Human gates — R14]`: no per-finding human prompt; drift → a scoped fixup, re-dispatched, re-reviewed, until the artifacts validate. A **surgical** fix (a column-name drift, a missing ticket field) `10` dispatches directly; a change that **ripples through many layers** routes to `09-revise-requirements-fabrik` (propagation is `09`'s job, not `10`'s).
- **The only halt conditions are the 3 BLOCKED cases** `[canonical: CLAUDE.md § Behavior — the three BLOCKED cases]`: 3 consecutive same-test failures on one fixup · missing infra · an unresolvable spec contradiction (→ route to `09`). On any → Apprise→Telegram, pause THAT thread, continue.

## Processing User Request

### Step 1: Internalize All Artifacts

Read in order (the Reads budget): **Decisions Lock** (Success Criteria, Out of Scope, Metadata) · **Core Flows** (when present — `[PRIMARY PATH]`, Flow Index, i18n decisions, Microcopy Hot-Spots) · **Tech Plan** (when present — Architecture, Data Model, Component Architecture, Shape Block, resilience table, Stack) · **Deploy Plan** (when present — may be SKIPPED entirely for a code-only Retrofit `[canonical: 04-deploy-plan-fabrik § Epic Flavor: Retrofit skip rule]`) · **Ticket Outline** (when present — the plan→execute run) · **Ticket Breakdown** (when present — + `[PRIMARY PATH]` Index) · **INFRA-CHECK** · `docs/operations/fabrik-lifecycle.md` · `docs/LESSONS_LEARNT.md`.

**INFRA-CHECK field set** `[canonical: 01-decisions-lock-fabrik § Step 1 — Consume Trigger Context]`: **Path A = 13** (10 required — `Port`, `target_vps`, `Scaffold`, `User Guide`, `Shape`, `Concurrency`, `i18n`, `Responsive`, `Dark+Light`, `Rule Packs` — + 3 SaaS-conditional, `N/A` allowed — `Abuse Detection`, `Email`, `FINANCIALS`). **Path B = 16** (the 15-field Metadata block = the 13 Path-A fields + `Registrars` + `Universal categories`, **plus `Epic Flavor`**). ⚠️ `Internal APIs` is **informational, NOT a propagated field** — do not validate it as one. Consume the fields from Decisions Lock Metadata **verbatim**; never re-derive them (a missing Path-B route → `00-trigger-fabrik`).

Build the mental model: Success Criteria ↔ flows ↔ components ↔ tickets ↔ tests ↔ docs ↔ INFRA-CHECK. For scaffolds without Core Flows or Tech Plan (per routing), derive from Success Criteria — don't flag an intentional absence. **When run early** (the optional pre-`05` spec-only check, no tickets yet), the ticket-dependent checks — Dimension 2's ticket/test legs and Dimension 7 (ticket structure) — are **deferred to the plan→execute run**; validate only the spec-to-spec seams then.

**Multi-pass for large epics (>8 tickets)** — one converging run, three lenses: **1 Mechanical** (Dimensions 6 INFRA-CHECK, 7 Ticket Structure, 8 Lessons — objective, highest hit-rate) → **2 Tracing** (Dimensions 2 Coverage, 3 Interface, 5 Assumptions — structural gaps) → **3 Judgment** (Dimensions 1 Conceptual, 4 Specificity). Small epics (≤8): all dimensions in one pass. Either way the run **loops to `found:0, fixed:0`** (Step 4).

### Step 2: Dispatch the Cross-Artifact Review — reviewer agents (BOTH mechanisms)

**ARM every reviewer FIRST (spec G5/G6 — an un-armed reviewer measured ~0–22% defect recall):** run
`python scripts/review_rubric.py --changed <the artifact paths under review>` and
**inject its output into every reviewer agent's prompt** as the rubric they hunt against. The rubric
carries two layers: **(1) the mandatory-core floor** — `core/35-security-auth` +
`core/25-data-postgres` + `core/30-ops` + all twelve 12-Factor axes — always injected regardless of glob
and never skippable, so the review is never un-armed on the high-blast-radius rules; **(2)** every pack
whose glob matches a changed path (mandate lines only). (No `--workflow` here: this command reviews the
chain's runtime PRODUCTS — epics / artifacts / implemented code — not the 00-N command files themselves;
the `EVALUATION_CHECKLIST_*` authoring-QA injects only when a review's subject IS a command file, e.g.
`/fabrik-workflow-review`.) The whole rubric is computed fresh by the script; nothing is inherited from
the doer. Honesty (L1): the injection STEP is maximally enforced (the rubric is always injected); this
raises compliance probability — it does **not** make compliance guaranteed.

Dispatch the review across the artifact seams through the **`libs/subagents` module** — **BOTH** layers, never either/or `[canonical: core/62-using-subagents.md § Dispatch policy]`:

- **Pool breadth** — `fanout("review", …, mode="read_only")` `[canonical: libs/subagents/agent.py — fanout]` picks family-diverse, flywheel-ranked review models (no default price cap) (`pick_models("review")`) and **auto-records each run to the flywheel**; after you adjudicate, back-fill your 0–5 verdict with `set_quality(r.agent_id, score, project="cross-artifact", task_type="review", model=r.model)` `[canonical: libs/subagents/pg_ledger.py — set_quality]` (an unscored `fanout` row teaches the flywheel nothing; ⚠️ never hand-roll `run_agents`+`record_run` — it no-ops).
- **≥1 native `fabrik-reviewer` on Opus** — the authoritative pass (the pool never runs `anthropic/*`, so pool-only is not valid). It owns the high-risk seams (Shape → registrar → compose; `target_vps` → DB host; migrations/schema propagation).

Each reviewer commits to a dimension before seeing the others; **you (Opus) refute/merge/decide**. The 8 dimensions — the joints, not the internals:

1. **Conceptual consistency** — terminology drift (same concept, different names); contradictory characterizations (Decisions Lock says admin-only, a flow shows a regular user); persona drift.
2. **Coverage traceability (bidirectional)** — forward: every Success Criterion → flow → component → ticket with a covering AC; reverse: every component/ticket → traceable to a Success Criterion; orphans (a requirement with no flow, a tech decision solving an unstated problem, a test with no ticket scope). Build the explicit `SC# | Criterion | Flow | Component | Ticket | Test` mapping table — **any empty cell is a finding**.
3. **Interface alignment** — data flows → exist in the Data Model; flow interactions → components in the Tech Plan; resilience-table entries → the real external deps in ticket Steps; Microcopy Hot-Spots → UI components + tickets.
4. **Specificity** — where a coder is forced to guess: vague flows deferring decisions to code time, Tech Plan stubs (`TBD`), ticket Steps with unspecified files / compound actions, ACs needing human judgment.
5. **Assumption coherence** — Decisions Lock assumes real-time but Tech Plan designs batch; Out-of-Scope excludes X but a ticket implements it; Shape says `needs_cache: false` but a ticket uses Redis.
6. **INFRA-CHECK propagation** — verify the contract flows through the chain for every field (Path A 13 / Path B 16): e.g. `Shape` → Tech Plan Shape Block → Deploy Plan registrar surface → compose contract; `target_vps` → Tech Plan DB host (`postgres-main` on vps1; `10.99.0.1` mesh on a spoke) → Deploy Plan; `Port` → Tech Plan → `compose.yaml` → `PORTS.md`; the GUI mandates (`i18n`/`Responsive`/`Dark+Light`) → Tech Plan UI architecture → ticket ACs. **Propagation only — `10` does NOT validate rule-pack CONTENT** (that is the producer commands' job); it checks that `Rule Packs` flow Decisions Lock → Tech Plan → ticket Context Files.
7. **Ticket structure** (per the `06-ticket-breakdown-fabrik` contract) — every ticket has: the Doc Sync Matrix ACs injected; a **Final Gate Instruction that is `python scripts/final_gate.py --json` (Tier-2) or `--systemic --json` (the Epic Closure ticket) — never `--lean`** `[canonical: CLAUDE.md § Completion Contract]`; a `Lessons Learnt:` line; the agent-aware first-output line; no git commands in DO NOT; a `[PRIMARY PATH]` test AC where it touches a `[PRIMARY PATH]` flow. **Epic Closure** — Delta-feature default; **optional for a Retrofit** where `06` skipped it per its Step 10 branch (verify the batch presentation stated `Epic Closure: skipped (Retrofit — [reason])`; missing closure with no skip statement = finding). **Parallelism budget** — Delta-feature **≥3:1**; a Retrofit (3–5 tickets) may legitimately be **1:1** (a linear 3-ticket chain) — do NOT fail it.
8. **`LESSONS_LEARNT.md` coherence** — entries match ticket activity (each triggered ticket has a `# Lesson <N>:` heading); sequential numbering; no contradiction with current specs (superseded entries marked, not deleted); filename is `docs/LESSONS_LEARNT.md` (uppercase).

**Intentional vs accidental:** a Tech Plan "Accepted deviation: [reason]" or a ticket's Spec-References departure note is intentional — not a finding. No marker + the artifacts disagree = a finding. When unsure, raise it as a finding (the marker rule is one-way).

**Retrofit-epic adjustments** (`Epic Flavor: Retrofit` `[canonical: mega-epic-breakdown/03-expand-epic-files-fabrik § Step 2 — Retrofit detected from the Title prefix]`): if `04-deploy-plan-fabrik` was SKIPPED, the Registrars/Shape propagation chain ends at the Tech Plan — skip the Deploy-Plan→compose leg, don't flag it broken; if `02-core-flows-fabrik` produced no flows for a code-only retrofit, Dimensions 1–2 flow-traceability become N/A; mandate propagation (Dimension 6 i18n/Responsive/Dark+Light) applies ONLY to the retrofit's target area `[canonical: 06-ticket-breakdown-fabrik § Step 4 Retrofit branch]`; a Retrofit Decisions Lock's 3–5 SC is not an under-spec finding.

### Step 3: Converge to a No-Op — fixup, don't stop

Classify every surviving finding by significance — **Blocker** (broken cross-artifact contract, a Success Criterion with no coverage, a missing ticket field), **Significant** (interface misalignment, an assumption contradiction, a specificity gap), **Minor** (terminology drift — batch these) — then handle it autonomously:

- **Surgical cross-artifact fix** (a column-name drift, a missing Final-Gate/Lessons AC, a stale term) → create a **scoped fixup ticket** (one fix, naming both conflicting `path:line`s) and **dispatch it** through the **`libs/subagents` module**: an artifact/spec edit → the pool `pick_models("docs")`/`pick_models("spec")` via `fanout`; a ticket-structure or code-touching fixup → the pool `pick_models("code")` (simple), a mid pool coder or **`claude -p sonnet`** (complex), or **`claude -p opus`** in an isolated git worktree (a high-risk propagation — schema/migrations/registrar) `[canonical: 06-ticket-breakdown-fabrik § Step 9 — the coder tiers]`. Re-read the touched artifacts + re-review to confirm.
- **Needs full top-down propagation** (a change that ripples Decisions Lock → … → tickets) → **route to `09-revise-requirements-fabrik`**; `10` finds the contradiction, `09` propagates the fix. Do NOT run the propagation cascade here.
- **Ticket reconciliation** — a finding that >50% of tickets need substantial rework → recommend a `06-ticket-breakdown-fabrik` re-run for that batch rather than N fixups. A Done-but-affected ticket → the three-option matrix (amend / rollback / accept divergence) is an **operator** pick (routed via `09`).
- **BLOCKED cases** — 3 consecutive same-test failures on one fixup → case 1 (Telegram, pause that thread); missing infra → case 2; unresolvable spec contradiction → case 3 (→ `09`).

**LOOP:** every fixup dispatched → re-reviewed (Step 2) → re-classified — **until a fresh cross-artifact round finds nothing AND changes nothing (`found:0, fixed:0`)**. The pass that produced a fixup is never the last; run one more. Only that no-op validates the artifact set.

### Step 4: Present + Hand Off

When the cross-artifact review reaches the `found:0, fixed:0` no-op: post the assessment to the Telegram digest (overall — coherent story or not — then Blockers → Significant → Minor), and hand off by outcome:

- **Early spec-only run** (pre-`05`, no tickets yet) reaches a clean no-op → the next step is `05-ticket-outline-fabrik` (the spec seams are consistent; now build the tickets).
- Artifacts consistent, tickets reconciled (the plan→execute run) → the next step is `07-execute-fabrik` (or, as `09`'s paired review, back into the chain) — and `08-implementation-validation-fabrik` for any Done-but-affected amendment.
- A recommended `06`-breakdown re-run or a routed propagation → `06-ticket-breakdown-fabrik` / `09-revise-requirements-fabrik`.
- When the whole chain is clean → the **deploy-out human gate** → `11-deploy-command`. `10` is a PRE-deploy consistency gate; it never runs `fabrik apply`.

## Does NOT

- **Validate code correctness (code-vs-spec)** — that is `08-implementation-validation-fabrik` (it reads code). `10` is spec-vs-spec (it reads the artifacts against each other); both run, on different surfaces.
- **Run the full top-down propagation cascade** — that is `09-revise-requirements-fabrik`. `10` FINDS contradictions and applies **surgical** fixes; a rippling change routes to `09` (never a recursive `09` call from inside `10`).
- **Re-review the internal quality of a single artifact** — `10` checks the joints; each artifact's internals were converged by its own producer command + paired review.
- **Validate rule-pack CONTENT** — `10` verifies the `Rule Packs` field *propagates* (Decisions Lock → Tech Plan → ticket Context Files); the pack semantics are the producer commands' job.
- **Re-derive INFRA-CHECK fields** — consume from Decisions Lock Metadata verbatim; a missing Path-B route (Registrars / Universal categories / Epic Flavor) routes back to `00-trigger-fabrik`.
- **Flag intentional differences** — an "Accepted deviation: [reason]" marker or a ticket Spec-References note is not a finding (the marker rule is one-way: present → intentional; absent + disagreement → finding).
- **Flag a missing Deploy Plan / Epic Closure / a <5-SC Decisions Lock for a Retrofit** where `04`/`06` correctly skipped or the Retrofit default applies (per the Step-2 Retrofit adjustments); a Retrofit's 1:1 parallelism is not a budget failure.
- **Change ticket Title prefixes** — Delta-feature stays `T<n> — <action verb>`; Retrofit stays `T<n> — Retrofit: <area>`.
- **Deploy** — that is `11-deploy-command` (the deploy-out gate). `10` is the pre-deploy consistency gate.
- **Run `git commit` / `push`** — `scripts/final_gate.py` auto-stages on success (CLAUDE.md HARD STOPS); the fixups merge via `07`-style worktree→default-branch.

## Acceptance Criteria

- All present artifact surfaces internalized (Decisions Lock, Flows, Tech Plan, Deploy Plan, Outline, Tickets, INFRA-CHECK, lifecycle, `LESSONS_LEARNT.md`) — the Outline/Tickets only in the plan→execute run (an early spec-only run has none yet).
- All applicable dimensions analyzed (all 8 in the plan→execute run; an early spec-only run defers the ticket-dependent Dimension 2 ticket/test legs + Dimension 7); the Coverage mapping table built with no empty cell; findings classified Blocker / Significant / Minor.
- INFRA-CHECK propagation verified for all Path A 13 fields (10 required + 3 SaaS-conditional) OR all Path B 16 (the 15-field block + Epic Flavor); `Internal APIs` treated as informational, not propagated.
- Ticket structure verified (in the plan→execute run — Doc Sync Matrix, the two valid Final-Gate commands, Lessons, first-output, no-git, `[PRIMARY PATH]`, Epic Closure conditionality, parallelism budget with the Retrofit 1:1 carve-out).
- `LESSONS_LEARNT.md` coherence verified (entries match, numbering sequential, no spec contradiction).
- Review dispatched through `libs/subagents` — **pool `fanout("review")` recording the flywheel AND ≥1 native `fabrik-reviewer` on Opus** — Opus refuting/merging/deciding.
- Findings handled **autonomously**: surgical fixups dispatched (pool `pick_models("docs"/"spec"/"code")` or `claude -p`), re-reviewed, **looping until `found:0, fixed:0`**; a rippling change routes to `09`; a >50%-rework batch routes to `06`; only the 3 BLOCKED cases pause (Telegram).
- The no-op hands off by outcome (`07`/`08`/`06`/`09`), and when the chain is clean → the deploy-out gate → `11-deploy-command`. Never runs `fabrik apply`.

---

**Next (CC1 doer→review pairing; `10`'s CC5 role, north star § Command-chain build plan):** `10` IS the cross-cutting integration review + `09-revise`'s paired review `[canonical: north star § Command-chain build plan — CC5]`. When the artifacts validate to a no-op, the chain continues by outcome — `07-execute-fabrik` (or `08-implementation-validation-fabrik` for Done-but-affected amendments), a routed `06-ticket-breakdown-fabrik` re-run or `09-revise-requirements-fabrik` propagation — and, when the whole chain is clean, the **deploy-out human gate** → `11-deploy-command`. *(Downstream ettw twins are built incrementally; refs point to the live Traycer `-command` source and flip to `-fabrik` as each twin lands.)*
