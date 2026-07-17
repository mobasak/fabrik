<!-- ⚠️ FABRIK FACTORY WORKFLOW — REVISE REQUIREMENTS (our own, tool-capable twin of
     09-revise-requirements-command). Run DIRECTLY by our orchestrator agent (Opus 4.8, via the driver) —
     never pasted into a planner GUI.
     THIS IS THE OPERATOR'S RE-STEERING TOOL. It is reached by an OPERATOR scope-change, an
     `08-implementation-validation-fabrik` Product Misalignment, or a BLOCKED-case-3 escalation (an
     unresolvable spec contradiction from `07`/`08`) that already went to the operator via Telegram. The
     operator owns the
     DECISIONS — the Step-2 escape-hatch close-vs-continue call (an early STOP when the change is too big),
     the Step-4 scope confirmation, and the Step-6 Done-but-affected / In-Progress picks — a requirements
     change is operator-owned, effectively re-touching the plan-in gate
     `[canonical: north star § Human gates — R14]`. But the PROPAGATION those decisions imply — the cascade
     EDITS (Steps 5/7/8) and the re-execution of the new/amended tickets (Step 9) — is AUTONOMOUS: Opus
     orchestrates coder + reviewer agents THROUGH the `07`/`08` loops and DOES NOT STOP until the revised
     tickets are Done — halting only on the 3 BLOCKED cases. `09` does not re-implement `07`/`08`; it
     INVOKES them — distinct jobs, `09` drives them rather than duplicating their loops.

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · `docs/operations/fabrik-lifecycle.md` — the epic's lifecycle stage (change friction)
       · the plan artifacts — Epic Brief (`01-epic-brief-fabrik`) · Core Flows (`02-core-flows-fabrik`) ·
         Tech Plan (`03-tech-plan-fabrik`) · Deploy Plan (`04-deploy-plan-fabrik`) · Ticket Outline
         (`05-ticket-outline-fabrik`) · Ticket Breakdown (`06-ticket-breakdown-fabrik` output) · the
         `[PRIMARY PATH]` Index
       · the INFRA-CHECK — Path A (`00-trigger-fabrik` output) OR the dispatched epic file on disk
         (Path B — `docs/development/epics/YYYY-MM-DD-epic-<n>-<slug>.md`)
       · the implementation state — `git log`/branch + ticket status per ticket (Not-Started / In-Progress
         / Done-still-valid / Done-but-affected)
       · during re-execution — each returned agent's diff + its `final_gate.py --json` output
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Revise Requirements

## Role

The strategic planner that traces the ripple of a change across the established plan — and, in the autonomous factory, the **operator's re-steering tool**. It understands the full picture (specs + tickets + implementation state) before touching anything, propagates the change top-down and surgically, then **re-executes the new/amended tickets to completion by driving the `07`/`08` loops** — it does not stop until they are Done, halting only on the 3 BLOCKED cases. It writes no code itself and does not re-implement execution; the coder agents do the code, dispatched through `07-execute-fabrik`.

## When to Invoke

- The **operator** signals a mid-epic scope change (`also need X` / `drop Y` / `change how Z works`).
- `08-implementation-validation-fabrik` surfaced a **Product Misalignment** and routed it here `[canonical: 08-implementation-validation-fabrik § Step 4 — Product Misalignment routes to 09]`.
- `07-execute-fabrik` or `08-implementation-validation-fabrik` escalated **BLOCKED case 3** (an unresolvable spec contradiction) `[canonical: 07-execute-fabrik § Step 4 + 08-implementation-validation-fabrik § Step 4 — BLOCKED case 3 routes to 09]` — the Telegram alert already reached the operator; `09` is their response.
- An external constraint changed (a vendor API deprecated, a discovered limitation).

## Core Philosophy

Requirements change. The goal is not to resist it but to propagate it **deliberately and completely** — a half-updated plan whose specs contradict each other is the single biggest failure mode this command exists to prevent.

- Understand the change fully before assessing impact; comprehensive impact analysis before any edit.
- Targeted updates preserve work already done — don't rewrite what still holds.
- **Implementation state matters:** a Done ticket whose requirements changed (`Done-but-affected`) is not a Not-Started ticket.
- **The operator owns the decisions, not the propagation.** The operator decisions are the Step-2 escape-hatch close-vs-continue call (an early STOP when the change is too big to steer), the Step-4 scope confirmation, and the Step-6 Done-but-affected / In-Progress picks — a requirements change re-opens the plan, so these are the operator re-steering it, not a human step injected into autonomous execution `[canonical: north star § Human gates — R14]`. The propagation they imply — the cascade edits (Steps 5/7/8) and the re-execution (Step 9) — runs autonomously.
- **The only halt conditions are the 3 BLOCKED cases** `[canonical: CLAUDE.md § Behavior — the three BLOCKED cases]`: 3 consecutive same-test failures on one ticket · missing infra · an unresolvable spec contradiction. On any → Apprise→Telegram, pause THAT ticket, continue the rest.

## Processing User Request

### Step 1: Internalize Current State

Read the full artifact set (the Reads budget): `docs/operations/fabrik-lifecycle.md` (lifecycle stage → change friction) · **Epic Brief** (Success Criteria, Out of Scope, Metadata incl. `Epic Flavor` for Path B `[canonical: 01-epic-brief-fabrik § INFRA-CHECK — Path B carries Epic Flavor]`) · **Core Flows** (when present — `[PRIMARY PATH]` markers, Flow Index, i18n decisions) · **Tech Plan** (when present — Architecture, Data Model, Shape Block, resilience table) · **Deploy Plan** (when present — may be SKIPPED entirely for code-only Retrofit epics `[canonical: 04-deploy-plan-fabrik § Retrofit branch]`) · **Ticket Outline** · **Ticket Breakdown** · **INFRA-CHECK** (Path A = 10 required fields; Path B = the 16-field set incl. `Registrars`, `Universal categories`, `Epic Flavor` `[canonical: 01-epic-brief-fabrik § INFRA-CHECK — Path A 10 / Path B 16]`).

**Implementation state per ticket** (from `git log`/branch + ticket status): **Not-Started** · **In-Progress** · **Done-still-valid** (change doesn't touch it) · **Done-but-affected** (change invalidates part of it — highest friction).

### Step 2: Understand the Change

Crystallize with the operator: what specifically changed and why · a *revision* (modify existing scope) or a *new requirement* (expand it) · what the operator thinks is affected · what triggered it.

**Scope-creep escape hatch:** if the change invalidates **>50%** of Success Criteria (Delta-feature) OR introduces a new domain not in the current plan → **STOP**. Recommend closing this epic and starting fresh (`00-trigger-fabrik → 01-epic-brief-fabrik` for a single epic). `09` steers a plan; it does not pivot it.

**Additive fast-path:** if the change is purely additive (a new feature touching no existing ticket) → after the Step-4 operator OK, run the top-down cascade (Step 5) and the Step-8 consistency gate for the **new scope only** — Brief → INFRA-CHECK → flows → Tech Plan → Deploy Plan → outline → new tickets (via `06-ticket-breakdown-fabrik`) → Index — then re-execute (Step 9). The fast-path's speed is skipping the Step-6/7 re-evaluation of existing untouched tickets — never the cascade for the new scope, the Step-8 gate, or the scope confirmation.

**Retrofit-epic adjustments** (`Epic Flavor: Retrofit`, Title prefix `Retrofit:` `[canonical: mega-epic-breakdown/03-expand-epic-files-fabrik § Step 2 — Retrofit detected from the Title prefix]`):

- **Tighter escape hatch** — Retrofit Briefs are 3–5 SC, so losing 2 = 40–67% invalidation; use a **30% absolute SC-loss threshold** (not 50%). Beyond it → **STOP and recommend** closing + re-decomposing via `mega-epic-breakdown/02-epic-decomposition-fabrik` (the operator's call, like the Delta escape hatch — `09` recommends, it does not pivot).
- **Retrofit boundary check** — if the change adds scope that won't fit a single rule-pack area, the epic has stopped being a Retrofit → **STOP and recommend** closing + re-decomposing via `mega-epic-breakdown/02-epic-decomposition-fabrik` as a Delta-feature, then retitling via `mega-epic-breakdown/03-expand-epic-files-fabrik` (drop the `Retrofit:` prefix) — operator's call.
- **Cascade skips (Step 5)** — where `04-deploy-plan-fabrik` was SKIPPED per its Retrofit branch, state `Deploy Plan: skipped per Retrofit branch; no cascade at this layer`; same for a code-only Retrofit's absent Core Flows.
- **Done-but-affected rollback warning (Step 6 option 2)** — "Roll back + re-do" for a Retrofit ticket also requires re-running `08-implementation-validation-fabrik` on the Delta-feature scope (the prior Delta-feature Epic Closure may have validated against the OLD retrofit state).
- **User Guide flip immunity** — a Retrofit epic keeps the parent project's User Guide; flag any `User Guide` change as a scope-leak signal → route to the boundary check.
- **New ticket Title convention** — Retrofit epics emit `T<n> — Retrofit: <area>`; Delta-feature epics emit `T<n> — <action verb>`.

### Step 3: Impact Analysis

Trace effects through EVERY artifact layer — is it affected? which sections? how severe (tweak / rework / removal / addition)? **Second-order effects:** flow change → does Tech Plan architecture still support it? · data-model change → do flows/tickets using that data still apply? · scope shift → flows/tickets/tests now unnecessary? · `User Guide` flip (internal→external) → every API ticket gains a `docs/user-guide/` AC · `Internal APIs` change → Component Architecture + ticket Steps realign · **Shape change → deploy-plan registrar surface changes → env vars change** `[canonical: 04-deploy-plan-fabrik — the shape→registrar→compose chain]` · new external dep → resilience table needs a new row (timeout/retry/fallback) · i18n scope change → locale files + formatting affected.

### Step 4: Present Impact + Operator Checkpoint

Present per-artifact (what's affected, severity, preliminary proposal) and per-ticket (counts of Not-Started / In-Progress / Done-still-valid / Done-but-affected) to the operator — via the Telegram digest + the VS Code diff. **Get the operator's agreement on the scope of changes before updating anything.** This scope confirmation is one of the operator decisions (alongside the Step-2 escape-hatch call and the Step-6 Done-but-affected / In-Progress picks); the cascade edits and re-execution they imply run autonomously.

### Step 5: Update Artifacts (Top-Down Cascade)

Strict order — complete one layer before the next; skipping the order is the biggest source of half-updated specs: **Epic Brief** (Success Criteria, Out of Scope, Metadata) → **INFRA-CHECK re-eval** (User Guide flip, Port, Internal APIs, Shape — but for a Retrofit epic a User Guide flip is a scope-leak signal → the Step-2 boundary check, not a normal re-eval) → **Core Flows** (journeys, `[PRIMARY PATH]`, i18n) → **Tech Plan** (architecture, data model, resilience, shape block) → **Deploy Plan** (registrar surface, compose contract, env vars) → **Ticket Outline** (rebatch for parallelism, budget ≥3:1) → **Ticket Breakdown** (always re-evaluate against updated specs) → **`[PRIMARY PATH]` Index** (regenerate) → **Implementation-state actions** (per Done-but-affected ticket). Per layer: think → update → verify consistency with prior layers. ⚠️ A DB **field/enum/model** change means the data contract must be re-frozen — route it through `/fabrik-data-contract` (`docs/data-contract.md`) before any ticket consumes the stale contract `[canonical: CLAUDE.md § Doc Sync Matrix — DB field/enum/model → re-freeze data-contract.md]`.

### Step 6: Ticket Re-Evaluation

| Pre-revision state | Action |
|---|---|
| Not-Started, unchanged | Leave alone |
| Not-Started, scope tweaked | Edit Scope / Steps / Acceptance / Doc Sync Matrix |
| Not-Started, no longer applies | Remove; document reason |
| Not-Started, replaced | New ticket (full `06`-breakdown structure) |
| In-Progress, scope tweaked | Pause execution; operator decides abort+restart or amend in-flight |
| In-Progress, no longer applies | Abort execution; remove ticket |
| Done-still-valid | Leave alone |
| Done-but-affected | **Three-option matrix — operator picks per ticket** |

**Done-but-affected options** (present all three, one-line rationale each): **1. Amend in place** (follow-up ticket scoped to the delta only) · **2. Roll back + re-do** (revert + recreate + re-execute — high friction) · **3. Accept divergence** (leave the code; update the spec to record the deviation as accepted).

### Step 7: Doc Sync Matrix + `[PRIMARY PATH]` Re-derivation

For every ticket whose Scope changed: re-run the Doc Sync Matrix logic (add/remove governance ACs); if the `[PRIMARY PATH]` moved (flow changed) → update the Index + the test-target ticket.

### Step 8: Cross-Artifact Consistency Pass (handoff gate)

Before re-execution, confirm: every Success Criterion → ≥1 ticket · every Tech Plan component → a ticket · every `[PRIMARY PATH]` Index row → an existing ticket with a test AC · every Doc Sync trigger → an AC · INFRA-CHECK fields propagated everywhere · no removed entity still referenced · no contradiction between layers · parallelism budget still ≥3:1 · shape → deploy-plan → compose chain consistent. A contradiction → return to the originating layer; never re-execute with a known contradiction. (This is `09`'s internal handoff gate; the standalone post-fact audit is `10-cross-artifact-validation-command`, `09`'s paired review per CC5.)

### Step 9: Re-Execute the Revised Tickets + Hand Off (autonomous)

Once the operator has confirmed the scope (Step 4), settled any Step-6 ticket-level decisions (none for a purely-additive change, where Step 6 is skipped), and the cascade is consistent (Step 8), **drive the new/amended tickets to Done — do not stop and ask**:

- **New / amended tickets** → dispatch them through **`07-execute-fabrik`** `[canonical: 07-execute-fabrik § Step 2 — coder dispatch by Complexity]`: each ticket to the coder tier its `Complexity` assigned `[canonical: 06-ticket-breakdown-fabrik § Step 9 — the coder tiers]` — `simple` → the cheapest OpenRouter pool `pick_models("code")` coder via `fanout` (≤$1.5/Mtok auto-tier, records the flywheel); `complex` → a mid pool coder OR **`claude -p sonnet`**; `critical` → **`claude -p opus`** in an isolated git worktree (auth/schema/migrations/concurrency/secrets) — and converge each ticket's diff to a **no-op** via `07`'s per-ticket review loop (pool `fanout("review")` recording the flywheel **AND** ≥1 native `fabrik-reviewer` on Opus), all through the **`libs/subagents` module**.
- **Done-but-affected tickets amended in place** → after the delta ticket lands, re-validate the affected slice through **`08-implementation-validation-fabrik`** (the epic-level code-vs-spec pass) so the amendment didn't regress a neighbor.
- **LOOP** dispatch → converge → re-validate until every revised ticket is Done — halting only on the 3 BLOCKED cases (each → Telegram, pause THAT ticket, continue).

Then hand off: the next step is **`10-cross-artifact-validation-command`** (`09`'s paired review — the spec-vs-spec audit across the revised artifacts), then the **deploy-out human gate** → `11-deploy-command`. `09` never runs `fabrik apply`.

## Does NOT

- **Re-implement execution or review** — `09` INVOKES `07-execute-fabrik` (coder dispatch + per-ticket converge) and `08-implementation-validation-fabrik` (epic-level code-vs-spec); it drives them, it does not duplicate their loops.
- **Write code itself** — the coder agents (pool `pick_models("code")` / `claude -p`) implement, dispatched through `07`.
- **Run the standalone cross-artifact audit** — Step 8 is `09`'s internal handoff gate; the separate post-fact audit is `10-cross-artifact-validation-command` (`09`'s paired review per CC5).
- **Deploy** — that is `11-deploy-command` (the deploy-out gate). `09` stops after the revised tickets validate.
- **Restart the epic from scratch** — >50% SC invalidation (Delta-feature, or >30% Retrofit) → recommend closing + starting fresh (`00-trigger-fabrik → 01-epic-brief-fabrik`, or `mega-epic-breakdown/02-epic-decomposition-fabrik`); `09` steers, it doesn't pivot.
- **Skip the operator scope checkpoint** — every change goes through Step 4 with explicit operator agreement; never begin the Step-5 cascade without it. (The cascade + re-execution are autonomous; the operator decisions — the Step-2 escape hatch, the Step-4 confirmation, the Step-6 picks — are not.)
- **Change the Epic Flavor** (Delta-feature ↔ Retrofit) — a Flavor flip needs re-decomposition at `mega-epic-breakdown/02-epic-decomposition-fabrik`; within `09` the Flavor is immutable.
- **Change ticket Title prefixes** — Delta-feature stays `T<n> — <action verb>`; Retrofit stays `T<n> — Retrofit: <area>`.
- **Skip the top-down cascade order** — Step 5's strict order prevents contradictions; lower-layer edits without upper-layer confirmation introduce drift.
- **Propose `09` recursively** — Step 8 contradictions return to the originating layer; never spawn a nested `09`.
- **Run `git commit` / `push`** — `scripts/final_gate.py` auto-stages on success (CLAUDE.md HARD STOPS); the coder fixups merge via `07`-style worktree→default-branch.

## Acceptance Criteria

- Change crystallized with the operator; scope-creep escape hatch applied at >50% (Delta) / >30% (Retrofit) invalidation.
- Impact analysis traces ALL artifact layers including INFRA-CHECK and implementation state.
- Impact presented at the Step-4 operator checkpoint; the operator confirms before any update.
- Cascade top-down (Brief → INFRA-CHECK → Flows → Tech Plan → Deploy Plan → Outline → Tickets → Index), each layer think → update → verify; a DB field/enum/model change re-freezes `docs/data-contract.md`.
- Every ticket classified; Done-but-affected gets the three-option matrix, operator picks per ticket.
- Doc Sync Matrix re-derived + `[PRIMARY PATH]` Index regenerated for changed tickets; new tickets follow full `06`-breakdown structure.
- Cross-artifact consistency pass clean (Step 8) before re-execution — no contradictions.
- **Re-execution autonomous** (Step 9): new/amended tickets driven through `07-execute-fabrik` (pool + `claude -p` coders via `libs/subagents`, per-ticket converge to no-op), Done-but-affected amendments re-validated through `08-implementation-validation-fabrik`, **looping until every revised ticket is Done** — halting only on the 3 BLOCKED cases.
- Handoff to `10-cross-artifact-validation-command` (`09`'s paired review), then the deploy-out gate → `11-deploy-command`. Never runs `fabrik apply`.

---

**Next (CC1 pairing, north star § Command-chain build plan):** `09`'s paired review is **`10-cross-artifact-validation-command`** `[canonical: north star § Command-chain build plan — CC5, "10 is the cross-cutting integration review + 09-revise's review"]` — the spec-vs-spec audit that forces the revised artifacts to a no-op. Then the **deploy-out human gate** → `11-deploy-command`. New/amended tickets re-enter via `07-execute-fabrik`; Done-but-affected amendments re-validate via `08-implementation-validation-fabrik`. *(Downstream ettw twins are built incrementally; refs point to the live Traycer `-command` source and flip to `-fabrik` as each twin lands.)*
