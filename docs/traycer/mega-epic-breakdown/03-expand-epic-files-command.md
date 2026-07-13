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

Additionally read: `docs/operations/fabrik-lifecycle.md` — ⚠️ it covers **only lifecycle stages 3–4** (deploy/runtime behaviour + data safety); it carries **no** stage model. The 4-stage model (scaffold → implement → `fabrik apply` → `fabrik verify`) is asserted by the command chain itself: a **delta-feature** epic ticket must pass all four. ⚠️ **Retrofit exception:** a Retrofit on an already-deployed service creates **no new deploy unit** — it has no Stage-1/Stage-3 of its own; its Stage-3 equivalent is the gate + the compliance-row flip in Success Criteria #1.

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
[5-8 measurable outcomes for delta-feature epics; 3-5 for Retrofit epics — ⚠️ criteria #3 and #4 are N/A **only** for a retrofit touching **neither** external-call sites (#3) **nor** mutation surfaces (#4) — a `Retrofit: Resilience …` epic **MUST keep #3** (`04-cross-epic-validation` § Step 3 fails it otherwise). When both are genuinely N/A, #1 and #2 alone yield 2, so the epic **MUST add at least one area-specific criterion** to reach the floor of 3 — `04` fails 'below per-flavour minimum' with no justification escape. MUST include AT LEAST ONE deploy/gate-level criterion AND ONE feature/compliance-level criterion. Pick whichever variant of each fits the epic:]
1. Deploy/gate-level — delta-feature epic: `fabrik apply` succeeds; health endpoint returns 200. — Retrofit epic on existing service (no new deploy unit): `python scripts/final_gate.py --json` returns `"status":"success"` (the **FULL Tier-2** gate — mypy + bandit + semgrep; ⚠️ `--lean` is Tier-1, for iteration only, **never** an acceptance gate per `CLAUDE.md` § Completion Contract) for the modified scope, AND the rule pack's compliance check moves from Partial/Violates → Compliant (per the gap row in the Vision Summary's Compliance Report).
2. Feature/compliance-level — delta-feature: [**the `Delivers:` value from 02's compact entry**, restated as an end-to-end user flow that proves the epic works. ⚠️ `Delivers` is the owner-visible outcome negotiated at 02's checkpoint — never drop it] — Retrofit: [the specific behaviour the rule pack mandates is now observable — e.g., `tr` locale renders for an i18n retrofit; rate-limit middleware blocks the test request for an abuse-detection retrofit].
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
- **Consumes from prior epics:** [specific artifacts: DB tables, API endpoints, env vars, middleware — **carried verbatim from 02's `Consumes:` field**; expand into concrete names, never re-derive] or [`none — root epic`]
- **Produces for later epics:** [specific artifacts this epic creates that others need — **carried verbatim from 02's `Produces:` field**. `Delivers:` is owner-visible value; this is the machine contract downstream epics consume]
- **Depends on:** [Epic X (hard), Epic Y (soft)] or [none — root epic]
- **Parallel with:** [Epic X] or [none]

### Metadata
- Scaffold: [one of the 11 scaffoldable types per `00-trigger-workflow-command` § Shape model — carried verbatim from 02's `Scaffold:`]
- Port: [value]
- target_vps: [`vps1` (hub, default) / `vps2` / `vps3` — carried verbatim from 02's `Target host:`. Drives the spec's `target_vps:` field, and epic-to-ticket re-checks it as overlay constraint #31. ⚠️ A spoke-targeted service reaches shared infra over the mesh (`10.99.0.1`), NOT by Docker DNS]
- Shape: [`kind` + the 8 canonical flags: is_public, is_admin_dashboard, has_bearer_api, has_persistent_data, needs_database, has_search_feature, needs_cache, exposes_metrics — plus `watchdog.enabled`. Carried verbatim from 02's `Shape:`. ⚠️ `has_bearer_api` fires **no** registrar of its own]
- Concurrency: [mechanism]
- i18n: [mechanism or N/A]
- Responsive: [carry from compact entry verbatim — per `00-trigger-workflow-command` § Architectural Mandates (always-read; it points to the Rule-area applicability matrix at Step E3.B), GUI mandates trigger on the *GUI surface*, NOT the scaffold type; mandatory for saas-skeleton / docusaurus front / mobile-app / desktop-app AND for python-api/node-api/file-api when `shape.is_admin_dashboard: true` OR `shape.is_public: true` with HTML output; N/A only when no HTML/native UI exists (pure JSON API, file-worker queue consumer). Chrome-extension popup is fixed 400px (carve-out per `00-trigger-workflow-command` § Architectural Mandates → Responsive).]
- Dark+Light: [carry from compact entry verbatim — same feature-based trigger as Responsive above]
- Rule Packs: [IDs]
- HAS_USER_GUIDE: [true/false]
- Registrars: [which of the **10** fire for this epic's deploy unit(s) — 7 flag-driven + grafana (always) + glitchtip (`shape.kind`) + watchdog (opt-OUT: fires unless `watchdog: {enabled: false}`). ⚠️ **gatus, authelia and prometheus ALSO require `spec.domain`** — the flag alone fires nothing (`infrastructure.py:214,255,293`). ⚠️ **Any** registrar — grafana included — can additionally be force-disabled by `infra: { <name>: false }` (`infrastructure.py::_enabled`)]
- Universal categories: [comma-separated numbers from 1–14 this epic owns; copied verbatim from the per-epic compact entry produced by `02-epic-decomposition-command` sub-step 2h]
- Abuse Detection: [required — SaaS scaffold with a free-tier signup surface (per `saas/87-abuse-detection.md`) / N/A — not a free-tier signup surface]
- Email: [transactional / marketing / two-stream (both, separate subdomains per `core/86-email-templates.md`) / none — epic does not send email / N/A]
- FINANCIALS: [required — SaaS scaffold pre-launch (per `saas/88-saas-launch-checklist.md` + `core/40-documentation.md`) / N/A — non-SaaS or this epic does not affect launch gate]

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
- Title: `Epic N — [Name]` (delta-feature) or `Epic N — Retrofit: [area]` (Retrofit)
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
- Each ticket title follows the format: `Epic N — [Name]` (delta-feature) **or** `Epic N — Retrofit: [area]` (Retrofit). ⚠️ The `Retrofit:` prefix is the **sole carrier** of the epic flavour downstream — `epic-to-ticket/00` string-parses the Title. A title like `Epic 4 — i18n Retrofit` silently classifies as Delta-feature.
- Each ticket description is self-sufficient: a coding agent can run `epic-to-ticket-workflow/01-epic-brief-command` using only the ticket + Infrastructure Decisions spec.
- Ticket length is **structure-bounded by the template** (no numeric token cap — per `EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS` item 93). A ticket that will not fit the template means the epic is **over-scoped** → route back to `02-epic-decomposition-command`.
- Each ticket has ALL required sections: Summary, Scope (In/Out), Success Criteria (**5-8** measurable for delta-feature; **3-5** for Retrofit), Out of Scope, Dependencies (with specific artifacts), Metadata (**all 15 fields**: Scaffold, Port, target_vps, Shape, Concurrency, i18n, Responsive, Dark+Light, Rule Packs, HAS_USER_GUIDE, Registrars, Universal categories, Abuse Detection, Email, FINANCIALS), Infrastructure reference, Execution Order, Entry Point.
- Success Criteria are testable — "user can do X", not "system supports X."
- Dependencies name specific artifacts (tables, functions, endpoints, env vars), not vague references.
- Scope boundaries unchanged from 02's confirmed proposal — no feature migration without routing back to 02.
- Ticket count matches epic count from the compact proposal.
- Route to `04-cross-epic-validation-command` stated after confirmation.
