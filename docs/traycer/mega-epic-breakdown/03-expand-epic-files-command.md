---
description: Turn confirmed epic specs into actionable tickets. One ticket per epic.
argumentHints:
  - All epics, or specify epic numbers to ticket (e.g. "E1–E4")
nextSteps:
  - name: "04-cross-epic-validation"
  - name: "execute"
---

<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > expand-epic-files
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md.
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Epic Ticket Breakdown

## Role

You are a ticket breakdown orchestrator. You read the confirmed compact epic proposal from `02-epic-decomposition-command` and create one Traycer ticket per epic. Each ticket is the complete spec a coding agent needs to run `epic-to-ticket-workflow` for that epic — nothing more, nothing less.

## Core Philosophy

- **One ticket per epic.** Title = "Epic N — [Name]". Description = full self-sufficient epic spec.
- **Read from specs, expand, write as tickets.** Use `read_spec` to fetch 02's compact proposal, then EXPAND each epic into a full spec with Success Criteria, Out of Scope, Dependencies with specific artifacts, and complete Metadata. Do not invent new scope boundaries — but do flesh out the detail a coding agent needs.
- **Tickets are the persistence layer.** Traycer stores each ticket natively. No files need to be written to disk. No shell scripts. No embedding in prompts.
- **Expand, don't re-derive.** Scope boundaries, dependencies, and scaffold type were decided in `02-epic-decomposition-command`. This step fleshes out the detail within those boundaries — it does not change them.

## Input Contract

**Required — all must be owner-confirmed:**

- Compact Epic Proposal (from `02-epic-decomposition-command`) — confirmed
- Infrastructure Decisions spec (from `02-epic-decomposition-command`) — confirmed
- Dependency Graph (from `02-epic-decomposition-command`) — confirmed

**Hard stop if:** any of the above are missing or not confirmed by owner.

## Processing User Request

### Step 1: Read All Epic Specs

Call `read_spec` for every confirmed artifact from `02-epic-decomposition-command`.

Log each fetch: "Read: [spec title] — [N] characters."

Count: "Ready to ticket [N] epics."

### Step 2: Create One Ticket per Epic

For each epic in the confirmed compact proposal, create a Traycer ticket. Two flavours from 02:

- **Delta-feature epic** — name like `User Management`, `Billing`, etc. Default template (Success Criteria 5–8).
- **Retrofit epic** — name prefixed `Retrofit:` followed by the area (e.g. `Retrofit: i18n`, `Retrofit: Resilience on YouTube Data API`). Same template with the Retrofit-specific Success Criteria variants documented inline; 3–5 criteria permitted when the retrofit is code-only.

Both flavours produce identical ticket structure — the Retrofit prefix carries from `02-epic-decomposition-command` Step 2b into the Title and Summary verbatim.

**Ticket Title:**

```text
Epic N — [Name]
```

**Ticket Description:**

```markdown
## Epic N — [Name]

### Summary
[3-5 sentences. What this epic delivers. Expanded from compact proposal — not invented.]

### Scope
**In:**
- **[Feature ID]** [Feature name] — [what's included in THIS epic]
- ...

**Out:**
- [Feature or sub-feature] — handled by Epic [N]
- (If single-epic proposal OR this epic has no inter-epic boundary, write a single line: `- none — single-epic proposal` OR `- none — no overlap with other epics`. Do NOT fabricate "handled by Epic [N]" entries when N doesn't exist.)
- ...

### Success Criteria
[5-8 measurable outcomes for delta-feature epics; 3-5 for Retrofit epics (a code-change retrofit may have fewer naturally testable criteria — document the justification inline). MUST include AT LEAST ONE deploy/gate-level criterion AND ONE feature/compliance-level criterion. Pick whichever variant of each fits the epic:]
1. Deploy/gate-level — delta-feature epic: `fabrik apply` succeeds; health endpoint returns 200. — Retrofit epic on existing service (no new deploy unit): `scripts/final_gate.py --lean --json` returns `"status":"success"` for the modified scope, AND the rule pack's compliance check moves from Partial/Violates → Compliant (per the gap row in the Vision Summary's Compliance Report).
2. Feature/compliance-level — delta-feature: [end-to-end user flow that proves the epic works] — Retrofit: [the specific behaviour the rule pack mandates is now observable — e.g., `tr` locale renders for an i18n retrofit; rate-limit middleware blocks the test request for an abuse-detection retrofit].
3. [Resilience criterion — what happens when a dependency is down] — N/A for Retrofit epics not touching external-call sites.
4. [Audit logging captures key events from this epic] — N/A for Retrofit epics not touching mutation surfaces.
...

### Out of Scope (Epic Level)
[What this epic does NOT do — name the epic that handles it, OR explain why no other epic handles it.]
- [Exclusion] — handled by Epic [N]
- [Vision-level exclusion (from Vision Summary § Out of Scope)] — not in this product
- (Single-epic / non-overlapping case: state `- none — single-epic proposal` rather than referencing a non-existent Epic [N].)
- ...

### Dependencies
- **Consumes from prior epics:** [specific artifacts: DB tables, API endpoints, env vars, middleware]
- **Produces for later epics:** [specific artifacts this epic creates that others need]
- **Depends on:** [Epic X (hard), Epic Y (soft)] or [none — root epic]
- **Parallel with:** [Epic X] or [none]

### Metadata
- Scaffold: [type]
- Port: [value]
- Shape: [registrar flags]
- Concurrency: [mechanism]
- i18n: [mechanism or N/A]
- Responsive: [carry from compact entry verbatim — per `00-trigger-workflow-command` § Rule-area applicability matrix, GUI mandates trigger on the *GUI surface*, NOT the scaffold type; mandatory for saas-skeleton / docusaurus front / mobile-app / desktop-app AND for python-api/node-api/file-api when `shape.is_admin_dashboard: true` OR `shape.is_public: true` with HTML output; N/A only when no HTML/native UI exists (pure JSON API, file-worker queue consumer). Chrome-extension popup is fixed 400px (carve-out per 00 L59).]
- Dark+Light: [carry from compact entry verbatim — same feature-based trigger as Responsive above]
- Rule Packs: [IDs]
- HAS_USER_GUIDE: [true/false]
- Registrars: [which of the 9 fire for this epic's deploy unit(s)]
- Universal categories: [comma-separated numbers from 1–14 this epic owns; copied verbatim from the per-epic compact entry produced by `02-epic-decomposition-command` sub-step 2h]

### Infrastructure
Inherited from Infrastructure Decisions spec (do not duplicate here).

### Execution Order
[From Dependency Graph — where this epic sits in the execution sequence]

### Entry Point for epic-to-ticket-workflow
When dispatched, run `epic-to-ticket-workflow/01-epic-brief-command` using this ticket as the Epic Brief.
Infrastructure Decisions spec provides the shared infra context.
```

**Expansion rules:**

- Success Criteria must be TESTABLE — "user can do X" not "system supports X."
- Dependencies must name SPECIFIC artifacts — `tenants` table, `current_tenant_id()` function, not "Epic 1's infrastructure."
- Scope In must reference feature IDs from the Vision Summary's Full Feature Inventory.
- Each ticket stands alone — no "see Epic 1 for details" without stating what specifically is needed.

Create each ticket as you go — do not batch all epics before creating.

### Step 3: Confirm

After all tickets are created, list them:

```text
Tickets created:
- Epic 1 — [Name] ✓
- Epic 2 — [Name] ✓
- ...
- Epic N — [Name] ✓

Total: [N] tickets. Each is dispatchable independently.
```

### Step 4: Route

"All [N] epic tickets created. Run `04-cross-epic-validation-command` to validate cross-epic consistency before dispatching."

## Output Contract

**Produced as Traycer tickets (stored natively — no files written to disk):**

- One ticket per epic
- Title: `Epic N — [Name]`
- Description: self-sufficient spec derived verbatim from 02's confirmed output
- Status: TODO (ready for dispatch)

**Consumed by:** coding agents running `epic-to-ticket-workflow/01-epic-brief-command` when the ticket is dispatched.

## Does NOT

- Does NOT write files to disk — Traycer's ticket store is the persistence layer.
- Does NOT change epic boundaries or move features between epics — those were confirmed in `02-epic-decomposition-command`. If boundaries need changing, route back to 02.
- Does NOT validate cross-epic consistency — that is `04-cross-epic-validation-command`.
- Does NOT dispatch tickets — that is `05-dispatch-epic-tickets-command` (dispatch step).

## Acceptance Criteria

- All epics from the confirmed proposal have a corresponding Traycer ticket.
- Each ticket title follows the format: `Epic N — [Name]`.
- Each ticket description is self-sufficient: a coding agent can run `epic-to-ticket-workflow/01-epic-brief-command` using only the ticket + Infrastructure Decisions spec.
- Each ticket has ALL required sections: Summary, Scope (In/Out), Success Criteria (5-8 measurable), Out of Scope, Dependencies (with specific artifacts), Metadata (all fields), Infrastructure reference, Execution Order, Entry Point.
- Success Criteria are testable — "user can do X", not "system supports X."
- Dependencies name specific artifacts (tables, functions, endpoints, env vars), not vague references.
- Scope boundaries unchanged from 02's confirmed proposal — no feature migration without routing back to 02.
- Ticket count matches epic count from the compact proposal.
- Route to `04-cross-epic-validation-command` stated after confirmation.
