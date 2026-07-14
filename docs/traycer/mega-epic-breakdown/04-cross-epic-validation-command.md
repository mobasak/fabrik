<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > cross-epic-validation
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md (101 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Cross-Epic Validation

## Role

You are a quality auditor who reads all epic tickets and specs from Traycer's store and verifies the decomposition is complete, consistent, and ready for execution.

## Goal

Confirm that the mega-epic decomposition is ready for execution — every feature covered, no gaps, no overlaps, no broken dependencies, each epic ticket self-sufficient for `epic-to-ticket-workflow`. After this command, the owner can start dispatching epic tickets via `05-dispatch-epic-tickets-command`.

## Core Philosophy

- **Read from Traycer's store, not conversation.** The specs were created by `02-epic-decomposition-command` and tickets by `03-expand-epic-files-command`. Read them fresh via `read_spec` and `read_ticket` — do not rely on conversation memory.
- **Validate, don't create.** This command finds problems. It does not fix them. If problems are found, route back to `02-epic-decomposition-command` or `03-expand-epic-files-command` to fix.
- **Every check is binary.** PASS or FAIL with specific reason. No "looks good" without evidence.

## Input Contract

**Required — all in Traycer's store:**

- Vision Summary spec (from `00-trigger-workflow-command`)
- Infrastructure Decisions spec (from `02-epic-decomposition-command`)
- Dependency Graph (from `02-epic-decomposition-command` — may be embedded in a spec or in conversation context)
- Epic tickets (from `03-expand-epic-files-command`) — one per epic

**Hard stop if:** any spec or ticket missing. State which and route back to the creating command.

**Additionally read:** `docs/operations/fabrik-lifecycle.md` — ⚠️ it covers **only lifecycle stages 3–4** (deploy/runtime behaviour + data safety); it carries **no** stage model. The 4-stage model (scaffold → implement → `fabrik apply` → `fabrik verify`) is asserted by the command chain itself. A **delta-feature** epic must be able to pass all four; a **Retrofit** epic on an already-deployed service creates **no new deploy unit**, so it has no Stage-1/Stage-3 of its own — its Stage-3 equivalent is the gate + the compliance-row flip (per `03-expand-epic-files-command` § Success Criteria). Validate each epic against the stage set its **flavour** actually owns — not a blanket four.

## Processing User Request

### Step 1: Read All Artifacts

Call `list_specs` to find Vision Summary and Infrastructure Decisions.
Call `list_tickets` to find all epic tickets.
Call `read_spec` and `read_ticket` for each.

State: "Read [N] specs and [M] tickets: Vision Summary, Infrastructure Decisions, [M] epic tickets."

### Step 2: Feature Coverage Check

Extract the Full Feature Inventory from the Vision Summary spec (numbered list).

For each feature, find which epic ticket claims it in its `### Scope > In:` section.

| Check | PASS | FAIL |
|---|---|---|
| Vision Summary has Feature Inventory | Inventory section present AND at least 1 feature found | Inventory section missing OR empty — Vision Summary corrupted; route back to `00-trigger-workflow-command` (do NOT continue 04) |
| Every feature assigned to an epic | All [N] features mapped (counts BOTH numbered delta features `1, 2, ...` AND existing-mode Retrofit features `R1, R2, ...` from Vision Summary § Full Feature Inventory) | Feature #[X] "[name]" not in any epic |
| No feature in multiple epics | Each feature in exactly one — applies to delta + Retrofit features identically | Feature #[X] claimed by Epic [A] and Epic [B] |
| No phantom features in epics | Epics only contain features from inventory (numbered or R-prefixed) | Epic [N] claims feature "[name]" not in Vision Summary |

### Step 3: Epic Ticket Check

For each epic ticket, verify:

| Check | PASS | FAIL |
|---|---|---|
| Ticket Title format | Matches `Epic N — [Name]` exactly (em-dash with single spaces around it; optional `Retrofit:` prefix in [Name] for retrofit epics emitted by `02-epic-decomposition-command` Step 2b) | Wrong format (en-dash, hyphen, missing space, wrong number) |
| Has `### Summary` | Present | Missing |
| Has `### Scope` with In + Out | Both present | Missing In or Out |
| Has `### Success Criteria` — count by epic flavour | Delta-feature epic: 5–8 items. Retrofit epic (Title `[Name]` starts `Retrofit:`): 3–5 items permitted per `03-expand-epic-files-command` § Success Criteria | Below per-flavour minimum |
| Has deploy/gate-level criterion | Delta-feature: "`fabrik apply` succeeds" or "/health returns 200" found. Retrofit on existing service (no new deploy unit): `scripts/final_gate.py` success + Compliance Report gap moves Partial/Violates → Compliant per `03-expand-epic-files-command` § Success Criteria | No deploy/gate criterion of either flavour |
| Has resilience criterion | Delta-feature: states what happens when a dependency is down. Retrofit epic: this row is N/A iff the retrofit area is NOT resilience/external-call related (Title doesn't contain `Resilience` and Universal categories doesn't list #5 External integrations) | No resilience criterion AND the epic IS resilience-related (delta-feature **OR** a retrofit whose Title contains `Resilience` **OR** a retrofit on category #5) |
| Has `### Out of Scope` | Present — names other epics, vision-level exclusions, OR explicit `- none — single-epic proposal` / `- none — no overlap with other epics` per `03-expand-epic-files-command` § Scope → Out + § Out of Scope (Epic Level) | Missing, vague, OR fabricates `handled by Epic [N]` with non-existent Epic N |
| Has `### Dependencies` | Section present AND all **5** sub-bullets present with content or an explicit `none` reason — `Consumes from prior epics`, `Produces for later epics`, `Depends on`, `Parallel with`, **`Owned paths`**. ⚠️ **`Owned paths` is NOT optional and `none` is NOT a valid value** — every epic writes something, and this field is what Step 4's disjointness + migration-owner checks intersect. A ticket without it makes those checks unrunnable and the `Parallel with:` claim unverifiable | Section missing OR any sub-bullet missing OR a sub-bullet present-but-empty (no value, no `none`) OR `Owned paths` is absent/`none` |
| Has `### Metadata` with all 15 fields | Scaffold, Port, target_vps, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs, HAS_USER_GUIDE, Registrars, Universal categories, Abuse Detection, Email, FINANCIALS (last 3 conditional — N/A allowed) | Missing field: [name] |
| Dependencies name specific artifacts | Tables, functions, endpoints, env vars named (or explicit `none` for atomic-root / terminal-output epics) | Vague references only (e.g., "Epic 1's infrastructure") |

### Step 4: Dependency Graph Check

Read the Dependency Graph (from spec or conversation context) and cross-reference with epic tickets' `### Dependencies` sections.

**Graph form (checklist item 88):** `02-epic-decomposition-command` emits the graph as a **mermaid diagram with `subgraph "Phase N"` blocks**. If it is prose instead, the owner cannot see the shape of their own decomposition — route back to `02`. **Terminology is `Phase`, never `Batch`** (consistent across 02 + 04 + 05; anti-pattern 101).

**Epic-count sanity (checklist item 51):** state the count and a one-line verdict — **3–7 is typical**; **10+** ⇒ say so and recommend re-examining the boundaries (likely split by layer, not domain); **2** ⇒ say so, the vision may not be "mega" enough to need this workflow at all. This is a **surfaced observation for the owner, not a hard FAIL** — an unusual count can be right, but it must never pass unremarked.

| Check | PASS | FAIL |
|---|---|---|
| No circular dependencies | DAG validated | Cycle: Epic [A] → Epic [B] → Epic [A] |
| Graph matches epic tickets | All dependencies in graph match `### Dependencies` sections | Epic [N] depends on Epic [M] but graph doesn't show it |
| Root epic(s) identified | Epic(s) with no upstream dependencies found | No root epic — everything depends on something |
| Parallel lanes identified | Epics with no mutual dependencies marked parallel | [Specific issue] |
| **Parallel epics have DISJOINT owned paths** | For every `Parallel with:` pair, intersect their `Owned paths:` — empty intersection | Epic [A] and Epic [B] are marked parallel but BOTH write `[glob]`. Two agents writing one file is a merge conflict by construction → re-cut the boundary or reclassify to sequential |
| **At most ONE migration owner per parallel set** | Only one epic in any parallel set owns `alembic/versions/**` / `db/schema.sql` | Epic [A] and Epic [B] are parallel and BOTH own migrations. Concurrent Alembic heads race the version table and wedge the deploy (12-Factor XII) → the non-schema epic must `depends-on` the schema epic |
| Produced artifacts consumed | Every "Produces for later epics" has a matching "Consumes from prior epics" — N/A for single-epic proposals (no later epics) and for terminal-output epics that legitimately produce end-user-visible output only (e.g., a marketing-page epic that produces a rendered site, consumed by humans not by a later epic) | Epic [A] produces [X] but no epic consumes it AND epic count > 1 AND [X] is an internal artifact (DB table, API endpoint, env var, queue) not end-user output |
| **CRITICAL PATH stated** | `02-epic-decomposition-command` sub-step **2d** emits `Critical path: Epic 1 → Epic 3 → Epic 5 (3 deep)` — the longest sequential chain. Confirm it is present **and matches the graph** you just validated | Missing, or contradicts the dependency graph. Route back to `02` sub-step 2d. ⚠️ Without it nobody knows what actually gates delivery — every other optimisation is guesswork |
| **SPLIT-CANDIDATE verdict per critical-path epic** | Every epic ON the critical path carries `SPLIT-CANDIDATE: yes (<how>) / no (<why>)` per `02` sub-step 2d | Missing on any critical-path epic. Per `02`: a critical-path epic that CAN be split into a blocking half and a non-blocking half **MUST** be split — *"that is the only way to shorten delivery."* An unstated verdict means the decomposition never asked the one question that shortens the schedule |
| **Graph is MINIMAL** (checklist item 16) | Every **sequential** pair has a *stated artifact reason* in `### Dependencies` (`Consumes:` names what Epic B takes from Epic A). If epics CAN be parallel they MUST be | Epic [B] `depends-on` Epic [A] but consumes **nothing** from it → an invented sequential edge that lengthens the critical path for free. Reclassify to parallel (then it must pass the disjointness + migration gates above) |

### Step 5: Infrastructure Decisions Check

Read the Infrastructure Decisions spec and verify against epic tickets.

| Check | PASS | FAIL |
|---|---|---|
| All shared decisions present | Per `02-epic-decomposition-command` Step 3 template: Database Strategy, Auth Strategy, Email Strategy, Background Processing, Embedding Model (if RAG features), Self-Healing Ladder (if `shape.kind ∈ {service, worker}`), Watchdog Wiring (**ON by default** — the resolver reads the raw spec dict, `infrastructure.py:314`; ⚠️ the `shape.kind` matrix in `core/60-watchdog.md` is **operator discipline, NOT code-enforced** — a `static-site` gets a watchdog despite the matrix saying `off`), Observability Defaults, Cost Guardrails (if any paid-API use), Backing Services, External Services, Domain Structure, Shared Environment Variables, Shared Shape Decisions | Missing section: [section name] |
| Epic tickets reference, not duplicate | Epics say "Inherited from Infrastructure Decisions spec" | Epic [N] re-defines [decision] differently |
| No contradictions | Infrastructure Decisions consistent across all epic tickets | Epic [N] says [X], Infrastructure Decisions says [Y] |
| **Deferred Compliance appendix present** (EXISTING mode only) | If the Vision Summary's Compliance Report has any `fix-later` or `accept-as-legacy` row, a **"Deferred Compliance" appendix** exists listing every one of them (per `02-epic-decomposition-command` Step 2b — those rows emit **no epic**, so the appendix is their *only* carrier). N/A in NEW mode, or when every row is `fix-now` | A `fix-later` / `accept-as-legacy` row exists in the Compliance Report but appears in **no** epic and **no** appendix → the owner's deliberate deferral has been silently dropped. Route back to `02-epic-decomposition-command` Step 2b |

### Step 6: Handoff Readiness Check

For each epic ticket, verify it can feed into **`epic-to-ticket-workflow/00-trigger-workflow-command` in multi-epic (consume) mode** — the real entry point, which reads this ticket's **15-field Metadata block as the INFRA-CHECK** and only then hands off to `01-epic-brief-command`.

⚠️ **The entry point is `00`, not `01`** (same as `03-expand-epic-files-command` § Entry Point and `05-dispatch-epic-tickets-command` Step 2). `01` § Path B *assumes* the INFRA-CHECK already exists — and `00` is the only command that emits it. So "handoff readiness" means **ready for `00`'s consume-mode check**, which is precisely the 15-field Metadata audit below:

| Check | PASS | FAIL |
|---|---|---|
| Metadata has `Scaffold` | Present | Missing |
| Metadata has `Port` | Present, and **not already allocated** — verify against `PORTS.md` (the allocation registry), not just "looks like a port" (checklist item 53) | Missing, OR the port is already taken in `PORTS.md`, OR two epics in this proposal claim the same port. Route back to `02-epic-decomposition-command` (it assigns ports from `PORTS.md`) |
| Metadata has `target_vps` | `vps1` / `vps2` / `vps3` | Missing — the tech plan cannot pick the DB host |
| Metadata has `Shape` | Present | Missing |
| Metadata has `Concurrency` | Present | Missing |
| Metadata has `i18n` | Present or N/A stated | Missing |
| Metadata has `Responsive` | Present AND the value matches the feature trigger — mandatory iff scaffold has a GUI surface (saas-skeleton / docusaurus front / chrome-extension popup / mobile-app / desktop-app, OR python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output) per `00-trigger-workflow-command` § Rule-area applicability matrix; N/A only when no HTML/native UI exists | Missing, OR `N/A — non-GUI scaffold` declared on an epic whose Shape has `is_admin_dashboard: true` or `is_public: true` with HTML output (rule-pack violation, not just metadata gap — c2ef2ee defect class) |
| Metadata has `Dark+Light` | Same feature-based trigger as Responsive above | Missing, OR `N/A` declared on a GUI-surface epic |
| Metadata has `Rule Packs` | Present | Missing |
| Metadata has `HAS_USER_GUIDE` | true or false | Missing |
| Metadata has `Registrars` | Listed **AND the list MATCHES the epic's `Shape`** — this is a semantic cross-check, not a presence check (anti-pattern 100). Every flag that fires a registrar must have that registrar listed: `needs_database` ⇒ postgres · `needs_cache` ⇒ redis · `has_persistent_data` ⇒ backrest · `has_search_feature` ⇒ meilisearch · `is_public` ⇒ gatus · `is_admin_dashboard` ⇒ authelia · `exposes_metrics` ⇒ prometheus. Plus **grafana** (always) and **watchdog** (opt-OUT — listed unless `watchdog: {enabled: false}`). ⚠️ gatus/authelia/prometheus **also require `spec.domain`** — a flag alone fires nothing (`infrastructure.py:214,255,293`) | Missing, **OR** the list contradicts `Shape` — e.g. `Shape: needs_database: true` but postgres absent from `Registrars`. **This is not a metadata gap; it is a silently-broken deploy**: `fabrik apply` skips the registrar and the service comes up without its database (CLAUDE.md § Spec contract awareness). Route back to `02-epic-decomposition-command` |
| Metadata has `Universal categories` | Comma-separated 1–14 list (verbatim from 02 sub-step 2h) | Missing |
| Metadata has `Abuse Detection` | `required` (SaaS w/ free tier) or `N/A` with reason | Missing |
| Metadata has `Email` | `transactional` / `marketing` / `two-stream` / `none` / `N/A` | Missing |
| Metadata has `FINANCIALS` | `required` (SaaS launch gate) or `N/A` with reason | Missing |
| Epic ticket is self-sufficient | The whole `epic-to-ticket-workflow` chain — **`00-trigger` (consume mode) → `01-epic-brief`** — runs from ONLY this ticket + the Infrastructure Decisions spec. The ticket is the **sole source** of the INFRA-CHECK `00` emits and `01` § Path B consumes; nothing else is read | Requires additional context not in the ticket — e.g. a field `00`'s consume-mode check needs that only the Vision Summary carries |

### Step 7: Present Validation Report

Present the complete report:

```markdown
# Cross-Epic Validation Report

## Feature Coverage: [PASS / FAIL]
- [N] features in Vision Summary
- [N] features assigned across [M] epics
- Orphans: [none / list]
- Duplicates: [none / list]

## Epic Tickets: [PASS / FAIL]
[Per-epic summary — PASS or FAIL with reason]
- Epic 1 "[name]": [PASS / FAIL: reason]
- Epic 2 "[name]": [PASS / FAIL: reason]

## Dependency Graph: [PASS / FAIL]
- Circular dependencies: [none / found]
- Root epic(s): [list]
- Parallel lanes: [list]
- Unconsumed artifacts: [none / list]

## Infrastructure Decisions: [PASS / FAIL]
- Contradictions: [none / list]
- Missing sections: [none / list]

## Handoff Readiness: [PASS / FAIL]
[Per-epic Metadata check]
- Epic 1: [PASS / FAIL: missing field]
- Epic 2: [PASS / FAIL: missing field]

## Overall: [PASS / FAIL]

## Recommended Execution Order
[Render as topological phases — each phase contains epics with no mutual dependencies AND no dependencies on later phases. Single-phase if the proposal is single-epic or fully parallel; multi-phase otherwise. `⚡` separates epics inside a phase running in parallel.]

Phase 1 (root — no upstream dependencies): Epic [N]: [name] ⚡ Epic [M]: [name]
Phase 2 (after Phase 1 completes): Epic [O]: [name]
Phase 3 (after Phase 2 completes): Epic [P]: [name] ⚡ Epic [Q]: [name]
...

For single-epic proposals: `Phase 1: Epic 1 — [name] (atomic — no phasing required).`
```

### Step 8: Route Based on Result

**ALL PASS:** "Validation complete. All checks passed. Proceed to `05-dispatch-epic-tickets-command` to dispatch epic tickets in this order: [execution order]."

**ANY FAIL:** "Validation found [N] issues. Fix required before proceeding." List each failure with the specific fix needed. Route:

- **Scope/boundary issues** (orphans, duplicates, phantoms, wrong epic split) → "Run `02-epic-decomposition-command` to fix boundaries, then `03-expand-epic-files-command` to recreate tickets."
- **Missing ticket sections or thin metadata** (Step 3 / Step 6 failures) → "Run `03-expand-epic-files-command` to recreate the affected ticket(s)."
- **Infrastructure Decisions missing section** (Step 5 failure) → "Run `02-epic-decomposition-command` Step 3 to add the missing § section to the Infrastructure Decisions spec — do NOT recreate tickets unless they reference the missing decision."
- **Universal Coverage gap** (Step 5 missing a section that maps to a 2h category) → "Run `02-epic-decomposition-command` sub-step 2h to re-audit the 14 universal categories AND Step 3 to add the absorbing § sub-section."
- **Vision Summary corruption** (Step 2 inventory missing/empty) → "Route back to `00-trigger-workflow-command`; the upstream Vision Summary is broken — do NOT proceed with 02/03/04 until 00 produces a confirmed Vision Summary."
- **Title format violation** (Step 3 first row) → "Run `03-expand-epic-files-command` to fix titles to the `Epic N — [Name]` format with em-dash."
- Then re-run this validation.

**CRITICAL: STOP GENERATION after presenting.** Wait for owner to confirm before proceeding.

## Output Contract

**Format:** Validation Report (markdown, structure from Step 7) — presented in conversation. **Structure-bounded, NOT token-capped** (per `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS` item 93 — a PASS/FAIL-row-per-check report is bounded by "fill this template once", so a numeric budget would only force harmful truncation of the failures the owner most needs to see). Do **not** add one.
**Result:** PASS (ready for dispatch) or FAIL (route back to 02 or 03 for fixes).
**Consumed by:** Owner — decides to dispatch tickets or fix issues.

## Does NOT

- Does NOT fix problems — only finds them. Fixes happen in `02-epic-decomposition-command` or `03-expand-epic-files-command`.
- Does NOT create or modify specs or tickets — only reads from Traycer's store.
- Does NOT re-derive the vision or epic boundaries — validates what exists.
- Does NOT dispatch tickets — the owner does that via `05-dispatch-epic-tickets-command` after validation passes.

## Acceptance Criteria

- All specs and tickets read from Traycer's store via `read_spec`/`read_ticket` — not from conversation memory.
- Feature coverage checked: every feature in exactly one epic, no orphans, no duplicates.
- Epic ticket structure checked: every ticket has all required sections with content.
- Dependency graph checked: no cycles, root epics identified, parallel lanes identified, produced artifacts consumed.
- Infrastructure decisions checked: no contradictions, no missing sections, no duplication in epic tickets.
- Handoff readiness checked: every epic ticket has the complete 15-field Metadata that **`epic-to-ticket-workflow/00-trigger-workflow-command` consume-mode** verifies and emits as the INFRA-CHECK — which `01-epic-brief-command` § Path B then consumes. `00` is the entry point, not `01`.
- Every check is binary PASS/FAIL with specific evidence — no vague "looks good."
- Validation report presented with recommended execution order.
- ALL PASS → route to `05-dispatch-epic-tickets-command` (dispatch) with execution order.
- ANY FAIL → route back to `02-epic-decomposition-command` or `03-expand-epic-files-command` with specific fixes.
- Owner confirms. Silence ≠ confirmation.
