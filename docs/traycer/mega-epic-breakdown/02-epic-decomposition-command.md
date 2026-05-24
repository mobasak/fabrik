<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > epic-decomposition
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md.
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Epic Decomposition

## Role

You are an architect who takes the confirmed Vision Summary and splits it into independent epics — each with clear boundaries, dependencies, and enough context to create a Traycer ticket in `03-expand-epic-files-command`.

## Goal

By the end of this command, the owner and Traycer agree on:
- **HOW MANY** epics this vision needs
- **WHAT** each epic contains (features, scope boundaries — compact format)
- **WHAT ORDER** they execute in (dependency graph — which are sequential, which are parallel)
- **WHAT EACH EPIC PRODUCES** that later epics consume (DB tables, API contracts, env vars)
- **WHAT SHARED INFRASTRUCTURE** all epics inherit (Infrastructure Decisions document)

This command produces the compact epic proposal + Infrastructure Decisions in conversation. `03-expand-epic-files-command` expands each epic into a Traycer ticket. `04-dispatch-epic-tickets-command` dispatches tickets in dependency order.

## Core Philosophy

- **`00-trigger-workflow-command` decided WHAT.** This command decides HOW TO SPLIT IT. Do not re-derive the vision, features, or technology decisions — consume them.
- **Every epic must be independently deployable.** After an epic completes, something works end-to-end that the owner can see and use. No "foundation-only" epics that produce nothing visible.
- **Maximize parallelism between epics.** If two epics share no mutable state, they can run in parallel. Fewer sequential dependencies = faster delivery.
- **Draw boundaries by DOMAIN, not by layer.** "User management" is an epic. "Database layer" is not. Each epic delivers a vertical slice — from DB to API to UI (if applicable).
- **Plan for a solo dev + AI fleet.** One epic runs through my-workflow at a time. Epics execute sequentially (owner can only orchestrate one my-workflow cycle at a time), but WITHIN each epic, tickets are parallel.
- **Token budget matters.** This command stays lean — compact proposal, not full epic files. Full expansion happens in `03-expand-epic-files-command` in controlled batches.

## Input Contract

**Required — from `00-trigger-workflow-command` (in conversation context):**
- Confirmed Vision Summary with ALL sections:
  - Full Feature Inventory (numbered, with complexity classification)
  - Technology Decisions (resolved — not re-decided here)
  - Backing Services + External Services
  - Constraints (all `all clear` or resolved)
  - Scale Assessment (multi-epic confirmed)
  - Personas, Value Streams, Out of Scope

**Hard stop if:** Vision Summary not confirmed by owner, OR Open Questions remain unresolved. Do not proceed with ambiguity.

**Additionally read:**
- `docs/reference/fabrik-lifecycle.md` — each epic must pass all 4 stages.
- `AGENTS.md` § Infrastructure Services — backing services available.
- `AGENTS.md` § Planning Constraints — constraints still apply per epic.
- `PORTS.md` — each epic's service needs a port. Check availability.
- **Domain modules** — for EACH scaffold type identified in the Vision Summary's Technology Decisions, read the matching file from `domain-modules/`:
  - `saas-skeleton` → read `domain-modules/saas.md`
  - `mobile-app` → read `domain-modules/mobile-app.md`
  - `wordpress` → read `domain-modules/wordpress.md`
  - `chrome-extension` → read `domain-modules/chrome-ext.md`
  - Multi-scaffold vision (e.g., saas + mobile-app + chrome-extension) → read ALL matching modules. They inform epic patterns (mobile always has a "store submission" epic, SaaS always has "billing + tenant" epic, chrome-ext always has "backend API first, extension second" pattern, etc.).

## Processing User Request

This command has **one checkpoint** before the final confirmation:
1. **After Step 3** — present compact epic proposal + Infrastructure Decisions + dependency graph. Owner confirms boundaries, shared decisions, and execution order. STOP and wait.
2. **Step 4** — iterate if needed, then route to `03-expand-epic-files-command`.

### Step 1: Consume Vision Summary

Read the confirmed Vision Summary from conversation context. Extract:
- Full Feature Inventory (the complete list — every feature must land in exactly one epic)
- Technology Decisions (inherited by all epics — do NOT re-decide)
- Scaffold types identified (from Technology Decisions § Scaffold types)
- Scale Assessment (expected epic count)
- Constraints, Backing Services, External Services

State: "Vision Summary consumed. [N] features, [M] scaffold types, scale assessment: ~[K] epics."

### Step 2: Identify Epic Boundaries

**2a. Group features into epics by domain:**
- Features that share data models, API contracts, or user flows belong together
- Features that use different scaffold types typically become separate epics
- Each epic must produce a deployable, testable artifact

**2b. Apply boundary rules:**
- Every feature from the inventory maps to EXACTLY one epic. No feature in two epics. No feature orphaned.
- Each epic has 5-15 features. Fewer than 5 = merge with adjacent epic. More than 15 = split.
- Each epic has a clear scaffold type (from the Vision Summary's Technology Decisions § Scaffold types).
- Each epic has its own `fabrik apply` with its own shape block and registrars.

**2c. Identify dependencies:**
- Does Epic B need a database table that Epic A creates? → B depends on A.
- Does Epic B call an API endpoint that Epic A implements? → B depends on A.
- Does Epic B use an auth system that Epic A configures? → B depends on A.
- Does Epic B consume any shared service or infrastructure component (background processor, job queue, storage client, notification client, shared middleware, or any API module) that another epic scaffolds or creates? → B depends on THAT epic, regardless of where it sits in the draft execution order.
- Do two epics share NO data, NO APIs, NO services, NO auth, NO infrastructure components? → They can run in parallel.

**Parallel classification gate — run AFTER dependency detection, before finalizing any "parallel" label:**
For EVERY epic marked "parallel," produce one explicit verdict line in the proposal:

```text
[Epic N] parallel gate: PASS — consumes only [list artifacts] from [Epic X], which completes before this epic starts.
[Epic N] parallel gate: FAIL — consumes [artifact] from [Epic Y], which runs AFTER this epic → reclassified to depends-on: Epic Y.
```

FAIL = fix `depends-on`, re-run the gate for that epic, confirm PASS before finalizing.
Do NOT present the proposal until every parallel-labeled epic has a PASS verdict on record.

**2d. Order for value delivery:**
- Epic 1 should deliver something the owner can SEE and USE — not just foundation.
- If a foundation epic is unavoidable (e.g., shared DB schema + auth), make it SMALL and FAST so value-delivering epics start quickly.
- After Epic 1, maximize parallel lanes. If Epic 2 and Epic 3 are independent, say so.

**2e. Background processing check:**
- After grouping features, scan: does any feature require async/background processing (transcription, PDF generation, image processing, AI inference, data imports, batch operations, scheduled jobs, webhook-triggered pipelines)?
- If yes → these become either a dedicated `file-worker` epic OR a background-processing slice within the backend epic. Rule: never run heavy processing (>10s) inline in API handlers — it must go through the PostgreSQL job queue (per `core/75-workers-jobs.md`).
- If multiple heavy-processing features exist (e.g., transcription + image generation + report building), group them into a single "Worker Pipeline" epic rather than scattering across feature epics.

**2f. Port allocation:**
- Check `PORTS.md` for each epic's service.
- Assign ports. State them.

### Step 3: Draft Infrastructure Decisions

Produce the shared infrastructure document (≤5,000 tokens). These decisions are made ONCE here, referenced by each epic — never duplicated:

```markdown
# Infrastructure Decisions — Shared Across All Epics

[These decisions are made ONCE. Each epic inherits them.
Do NOT re-decide in my-workflow. Do NOT copy into epic files.]

## Database Strategy
- [which DB holds what, shared schemas, per-epic schemas]

## Auth Strategy
- [carried from Vision Summary Technology Decisions — not re-derived]

## Backing Services
- [carried from Vision Summary — not re-derived]

## External Services
- [carried from Vision Summary — not re-derived]

## Domain Structure
- [URL routing, subdomains, path-based routing — whichever was decided]

## Shared Environment Variables
- [env vars that multiple epics need — defined once, consumed by each]

## Shared Shape Decisions
- [which registrars each epic will activate]
```

### ── CHECKPOINT: Present Epic Proposal + Infrastructure Decisions ──

Present to the owner:

**1. Epic list** — for each epic (COMPACT format — full expansion happens in 03):
```
Epic [N]: [Name]
  Scope: [1-2 sentences]
  Features: [numbers from Feature Inventory, e.g., #1, #3, #7]
  Scaffold: [type]
  Depends on: [Epic X, Epic Y] or [none — root epic]
  Parallel with: [Epic Z] or [sequential]
  Port: [assigned]
  Delivers: [what the owner can see/use after this epic ships]
  Rule Packs: [IDs from .windsurf/rules/]
  HAS_USER_GUIDE: [true/false]
```

**2. Infrastructure Decisions** — the full document from Step 3.

**3. Dependency graph** (mermaid):
```mermaid
graph TD
  subgraph "Phase 1"
    E1[Epic 1: Name]
  end
  subgraph "Phase 2 (parallel)"
    E2[Epic 2: Name]
    E3[Epic 3: Name]
  end
  E1 --> E2
  E1 --> E3
```

**4. Coverage check:**
- "All [N] features from the Vision Summary are assigned. No orphans. No duplicates."
- Table mapping every feature to its assigned epic.

**5. Execution order:**
- Numbered list showing recommended order (respecting dependencies).
- Parallel lanes noted.

**6. Questions for owner:**
- Any boundary you disagree with?
- Any epic too big or too small?
- Execution order acceptable?
- Infrastructure Decisions complete?

**CRITICAL: STOP GENERATION HERE.** Do NOT simulate the owner's response. Wait for explicit confirmation. Silence ≠ confirmation.

### Step 4: Iterate and Confirm

Iterate until the owner explicitly confirms:
- If the owner moves features between epics → update both entries + re-check dependencies + re-validate coverage.
- If the owner adds/removes an epic → re-validate coverage (all features assigned, no orphans).
- If the owner changes execution order → update dependency graph.
- If the owner adjusts Infrastructure Decisions → update the document.

**After confirmation:** "Epic proposal and Infrastructure Decisions confirmed. Proceed to `03-expand-epic-files-command` to create one Traycer ticket per epic."

## Output Contract

**Produced as Traycer specs (persisted in Traycer's spec store, readable via `read_spec`):**

1. **Compact Epic Proposal** — one entry per epic with: scope, features, scaffold, dependencies, parallel lanes, port, delivers, rule packs, HAS_USER_GUIDE.
2. **Infrastructure Decisions** — shared across all epics. ≤5,000 tokens.
3. **Dependency Graph** — mermaid diagram + execution order.
4. **Coverage Check** — every feature mapped to exactly one epic.

**NOT produced here (deferred to 03-expand-epic-files-command):**

- Full epic tickets with detailed scope, success criteria, out-of-scope, dependencies listing specific artifacts, metadata blocks.

**Consumed by:** `03-expand-epic-files-command` reads the compact proposal + Infrastructure Decisions via `read_spec` and expands each epic into a Traycer ticket.

## Does NOT

- Does NOT re-derive the vision, features, or technology decisions — consumes `00-trigger-workflow-command`'s confirmed output.
- Does NOT produce full epic tickets — that is `03-expand-epic-files-command`. This command produces the compact proposal only.
- Does NOT produce ticket outlines or ticket breakdowns — that happens in `my-workflow/05-ticket-outline-command` per epic.
- Does NOT decide implementation details (API routes, DB schema columns, component names) — that is `my-workflow/03-tech-plan-command` per epic.
- Does NOT create tickets or write files to disk — tickets are created by `03-expand-epic-files-command`.

## Acceptance Criteria

- Vision Summary consumed from conversation — not re-derived.
- Technology Decisions inherited — not re-decided.
- Every feature from Feature Inventory assigned to exactly one epic. No orphans. No duplicates.
- Each epic entry has: scope summary, feature list, scaffold, dependencies, parallel lanes, port, delivers, rule packs, HAS_USER_GUIDE.
- Each epic is independently deployable — produces a testable artifact the owner can see.
- Epic boundaries drawn by domain, not by layer.
- Dependencies between epics are explicit. No circular dependencies.
- Dependency graph presented as mermaid diagram with execution order.
- Parallel lanes identified — epics that can run simultaneously.
- Epic 1 delivers visible value (not foundation-only unless unavoidable and small).
- Infrastructure Decisions document produced — shared across all epics, ≤5,000 tokens.
- Ports assigned per epic from `PORTS.md`.
- Compact proposal format — NOT full epic files (those come in 03).
- Owner explicitly confirms. Silence ≠ confirmation.
