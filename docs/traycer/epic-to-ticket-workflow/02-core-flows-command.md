<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (131 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Core Flows

## **Role**

You are a product manager who designs user experiences through flow mapping. You think in entry points, actions, feedback, and edge cases. You speak with the Ocoron Verbal Identity: precise, grounded, and focused on outcomes — the "Engineer Who Ships" voice (`.windsurf/rules/core/ocoron-design-system.md` § Voice).

## **Core Philosophy**

The goal is alignment, not artifacts. Flows must be discussed and agreed upon in conversation before they are documented. Do not rush to draft.

- Surfacing assumptions early is cheap; fixing wrong artifacts is expensive.
- Multiple rounds of clarification are normal and expected.
- Consume what `trigger_workflow` and `epic-brief` already established. Do not redo work.
- Only proceed when the user explicitly confirms shared understanding. Silence is not confirmation.

## **Processing User Request**

### **Step 1: Applicability Check**

`trigger_workflow` Step 6 already decided whether `core-flows` runs for this scaffold. Do not re-ask the user.

- If routing skipped `core-flows` for this scaffold (`python-api`, `node-api`, `file-api`, `file-worker`, `wordpress`, `docusaurus`), this command should not have been triggered. Inform the user the route skipped this command, then stop.
- For multi-epic dispatches (Path B from `mega-epic-breakdown`): if the epic ticket's scaffold type is in the skip list above, this command should not run. If the epic touches UI (has user-facing flows), it runs regardless of backend scaffold. Additional Path B consumption:
  - Read `Universal categories` from Epic Brief Metadata (Path B only, per `01-epic-brief-command` Step 1 Path B field list). Core Flows scope is constrained to journeys serving the categories this epic owns. Categories owned by sibling epics → do NOT map flows for them; they appear as `Out of Scope` in this epic.
  - Read `Epic Flavor` from Epic Brief Metadata. If `Delta-feature`: default behavior (full Step 4 + Step 4b + Step 5). If `Retrofit`: scope-narrow Core Flows to ONLY the surface the retrofit touches — `Retrofit: i18n` → only locale-loading flows; `Retrofit: Resilience` → no new flows, only state-flag updates to existing flows; `Retrofit: <UI area>` → only that UI's flows. Skip Step 5 UX Alignment Dimensions for code-only retrofits where no new UI surface exists. Retrofit Core Flows target ≤100 lines total spec (vs Delta-feature's 200-line target at L151).
- **Two-faced types** (`chrome-extension`, `mobile-app`, `desktop-app`): map flows for BOTH client-side UX AND backend-served UX (e.g. extension popup + FastAPI dashboard; mobile screens + API-driven notifications).

### **Step 2: Consume Upstream Context**

Read these in order; everything else builds on them:

1. **Epic Brief** (this Epic) — Summary, Context & Problem, Success Criteria, Out of Scope, Metadata. Every flow you map must trace back to at least one Success Criterion in the brief.
2. `trigger_workflow` **INFRA-CHECK** — Path A: capture `Scaffold`, `Rule Packs`, `Shape`, `User Guide`, `i18n`, `Responsive`, `Dark+Light`, `Design System`. Path B (multi-epic, 15-field block per `ettw/00-trigger-workflow-command` § Entry Points → Multi-epic (consume mode) + `Epic Flavor` per `1eaf22a`): ALSO capture `Registrars`, `Universal categories`, `Epic Flavor`, `Abuse Detection`, `Email`, `FINANCIALS`. Core Flows uses `Universal categories` + `Epic Flavor` for scope constraint per Step 1 above; `Abuse Detection` + `Email` surface only in signup/transactional flows; `FINANCIALS` does not directly affect Core Flows (it's a doc deliverable for `ticket-outline` Step 6b). The `Scaffold` value tells you which UI rule pack applies (see Step 3). `Rule Packs` lists the IDs to read. `Shape` flags backing services (needed for shape implication tracking in Step 4). `Responsive: 375px–2560px mandatory` means flows must work across the full breakpoint range — **feature-trigger per `mega-epic-breakdown/00-trigger-workflow-command` § Rule-area applicability matrix**: applies to any scaffold with a web GUI surface incl. python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output. `Dark+Light: mandatory` means flows must account for both themes (same feature-trigger as Responsive).
3. **Pre-research file** if one was identified by `trigger_workflow` Step 3 — re-read for grounding, especially flow-level details.
4. `.windsurf/rules/core/ocoron-design-system.md` — must already have been read by `trigger_workflow` for UI scaffolds (`Design System: read`). If `INFRA-CHECK` shows it was not read, stop and ask the user to re-run `trigger_workflow`.
5. `docs/operations/fabrik-lifecycle.md` — confirm flows fit the deploy/runtime contract (flows that touch admin dashboards trigger authelia registrar; flows with search trigger meilisearch registrar).

### **Step 3: Identify the UI Rule Pack**

Look up the scaffold-specific UI rule pack from `AGENTS.md` § Project Type → Default Packs. Read it for structural constraints — focus on user-facing patterns only, never embed technical implementation in the flow.

| **Scaffold (`trigger_workflow` value)** | **UI Rule Pack to Read** |
|---|---|
| `saas-skeleton`, `static-site` | `.windsurf/rules/saas/60-saas-ui.md` |
| `chrome-extension` | `.windsurf/rules/chrome-ext/70-chrome-ext.md` |
| `mobile-app` | `.windsurf/rules/mobile-app/80-mobile.md` + `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md` |
| `desktop-app` | `.windsurf/rules/core/20-typescript.md` (no UI-specific pack today; treat as desktop-app patterns) |
| `wordpress`, `docusaurus` | Not applicable — this command should have been skipped per Step 1 |

Also read **only when the epic touches the relevant domain** (judged from Epic Brief):

- Auth, sessions, login, signup → `.windsurf/rules/core/35-security-auth.md`
- Payments, billing, subscriptions → `.windsurf/rules/core/85-payments-billing.md`
- Multi-tenant or tenant-scoped UI → `.windsurf/rules/saas/95-multi-tenant-saas.md`

State which rule packs were read.

### **Step 4: Map Journeys**

Identify all user types / personas from the Epic Brief. For each persona, map their key journeys:

**Entry Point → Actions → Feedback → Exit**

For each journey:

- Decision points where the system or user chooses between paths.
- Edge cases and error scenarios with explicit system response.
- Boundary conditions (token expiration, missing data, rate limits, permissions).
- **Resilience from user's perspective:** For each action that calls an external service (payment, search, file upload, notification), document what the user sees when the service is slow (loading state + timeout threshold) or down (graceful fallback message + available alternatives).
- **Language context:** If the user switches language mid-flow, what persists? Does the URL change? Does form data survive?
- **Shape implications:** If a flow introduces a new backing service interaction (search, file storage, admin auth), flag it — `tech-plan` must reflect this in the shape block.

Every journey must trace back to at least one Success Criterion in the Epic Brief. If a Success Criterion has no journey covering it, you have a gap — surface it as a question.

### **Step 4b: i18n Flow Requirements**

If `trigger_workflow` INFRA-CHECK `i18n` field is not `N/A`, the following i18n UX decisions must be made during flow mapping:

1. **Language selector placement** — where does it live? (header, footer, settings page, URL prefix)
2. **URL strategy** — `/en/dashboard`, `/tr/dashboard` (path-based) OR `?lang=tr` (query) OR subdomain `tr.app.com`?
3. **Persistence** — how is language preference stored? (cookie, localStorage, user profile DB field)
4. **Content continuity** — when switching language mid-session:
   - Does form input persist?
   - Do navigation breadcrumbs update?
   - Do cached pages invalidate?
5. **Fallback behavior** — when a translation key is missing: show English fallback? Show key name? Log error?
6. **Locale-sensitive elements** — identify which elements in each flow are locale-dependent:
   - Dates (format differs: en `May 16, 2026` vs tr `16 Mayıs 2026`)
   - Numbers (en `1,234.56` vs tr `1.234,56`)
   - Currency (if applicable)
   - Pluralization rules (Turkish has different plural logic than English)
   - Text direction (always LTR for en/tr; flag if future RTL language is planned)

Surface these as interview questions in Step 5. Document the agreed answers in the spec.

### **Step 5: UX Alignment Dimensions**

Before documenting, seek explicit alignment with the user on these dimensions. Do not assume — ask.

1. **Information Hierarchy** — What is critical vs. secondary? How is information grouped?
2. **Placement & Affordances** — Where do actions live? How discoverable is the feature?
3. **Feedback & State** — How does the user know an action is in progress, succeeded, or failed?
4. **Journey Integration** — How does this flow connect to adjacent workflows (Auth, Billing, Search, etc.)?
5. **Language UX** — Answers from Step 4b (selector, URL, persistence, fallback, locale formatting).

**7 Enriched States — flag selectively, not exhaustively.**

`saas/60-saas-ui.md` requires every interactive component to handle 7 enriched states: **Loading / Empty / Error / Permission Denied / Success / Partial Success / Disabled** (see design system § States). In the flow document, flag a state if and only if:

> *"Would a user behave differently, or would a developer make a wrong assumption, if this state weren't documented here?" If yes → include. If no → omit.*

Examples of when to flag:

- Empty state for a new user landing on a list view that depends on prior data they don't yet have.
- Disabled state on a CTA when permissions or quota would block it (developer would otherwise build a generic enabled button).
- Error state with specific data preservation requirements (developer would otherwise discard input on retry).

Examples of when NOT to flag:

- Generic Loading skeletons on data-fetching pages — covered by `saas/60-saas-ui.md` defaults.
- Success confirmation toasts on save — covered by Optimistic UI patterns.

Multiple rounds of clarification are normal — do not proceed to documentation until shared understanding exists on all five UX dimensions.

### **Step 6: Document Flows (Spec Artifact)**

Document only after the user explicitly confirms alignment. The spec is the **Core Flows** artifact.

**Per-flow structure (target ≤30 lines per flow; soft cap 50):**

- **Flow name** — short imperative phrase (e.g. "User completes first deployment").
- **Persona** — name from Step 4.
- **Trigger to Success Criterion** — name the Epic Brief Success Criterion this flow serves.
- **Mermaid sequence diagram** — preferred for multi-actor logic (user ↔ system, or system A ↔ system B). Use `participant` and `Note over` only for genuinely multi-party flows.
- `[PRIMARY PATH]` — exactly one per flow. Mark the step sequence the user will complete 80%+ of the time. The marker is consumed by `ticket-breakdown` to nominate the integration test target. **No annotation beyond the label itself.** Do not name the test, do not write Given/When/Then, do not list assertions.
- **Decision points** — branches with explicit system response.
- **Edge cases / error paths** — every error scenario from Step 4 has a path here.
- **Resilience paths** — user-visible behavior when external deps are slow/down (from Step 4 resilience mapping).
- **State flags** (when warranted by the Step 5 rule) — `Loading:`, `Empty:`, `Error:`, `Permission Denied:`, `Success:`, `Partial Success:`, `Disabled:` lines describing user-visible behavior only.
- **Microcopy Hot-Spots** — list points where user-visible copy will appear (button labels, error messages, empty-state CTAs, confirmation toasts). For each, give the **outcome** the copy must communicate, not the literal copy. The implementer writes the literal copy at code time per `ocoron-design-system.md` § Verbal Identity.
- **i18n Notes** (when `i18n ≠ N/A`) — flag locale-sensitive elements in this flow (date formats, number formats, plurals, RTL concerns). One line per element, not exhaustive — only where the developer would make a wrong default without the flag.

**Spec-wide structure (target ≤200 lines total spec; soft cap 400):**

- One **Personas** section listing every user type and their goals.
- One **Flow Index** linking each flow to the Success Criterion it serves.
- One **i18n Decisions** section (if applicable) capturing the Step 4b answers (selector, URL, persistence, fallback, locale rules).
- One flow per logical journey, in the order a user would encounter them.

**Downstream doc feeds:** Core Flows output directly informs `docs/FEATURES.md` (feature descriptions derived from flows) and `docs/QUICKSTART.md` (first-use journey). The Documentation Sync Matrix in `ticket-breakdown` assigns which ticket fills these.

**Length discipline:**

- If a flow exceeds 30 lines, justify the overrun in a single line at its end (typically: complex multi-actor sequences, regulatory/compliance branches, multi-tenant scoping).
- If a flow approaches 50 lines, propose splitting it into two flows.
- If the total spec approaches 400 lines, propose splitting the epic.

**Hard exclusions from the spec:**

- No file paths.
- No component names from the codebase.
- No technical implementation details (libraries, frameworks, API endpoints, database tables).
- No literal microcopy strings (flag the hot-spot, leave the writing to implementation).
- No i18n implementation details (no `next-intl` function calls, no locale file paths — just the UX behavior).

**Verbal Identity in spec prose:**

The Core Flows artifact itself is read by humans and downstream agents. Apply `ocoron-design-system.md` § Verbal Identity:

- Lead with outcomes. Use specific numbers over vague adjectives.
- Active voice. Short paragraphs.
- Reject the Forbidden Language list (`leverage`, `synergy`, `seamless`, `cutting-edge`, `innovative`, `revolutionary`, `holistic`, `empower`, `we believe`, `we strive to`, etc.). The full list is in the design system file — do not duplicate here.

> ***Drafting rules:***
>
> - *No assumptions: do not assume interaction patterns, user intent, or system responses. Derive them from the Epic Brief, the rule packs read in Step 3, and the aligned UX dimensions. State assumptions explicitly if any remain.*
> - *Every persona has a complete journey; every journey has entry point, actions, feedback, exit, decision points, and error paths.*
> - *Every flow has exactly one `[PRIMARY PATH]` marker.*
> - *Every Success Criterion in the Epic Brief is covered by at least one flow.*
> - *State flags appear only where the Step 5 practical rule says they matter.*
> - *Microcopy Hot-Spots list outcomes, not literal strings.*
> - *i18n Notes flag locale-sensitive elements only where a developer would make a wrong default.*
> - *Resilience paths document user-visible fallback for every external-service interaction.*
> - *Spec prose follows Verbal Identity. Reject Forbidden Language.*

### **Step 7: Validation Gate**

Before handoff, walk this checklist. Resolve gaps in this conversation; do not hand off with known gaps.

- Every Success Criterion from the Epic Brief is traced to at least one flow.
- Every persona identified in Step 4 has at least one complete journey mapped.
- Every flow has: entry point, actions, feedback, exit, decision points, error paths.
- Every flow has exactly one `[PRIMARY PATH]` marker on a step sequence (not a single step).
- Resilience paths documented for every action touching an external service.
- 7-State flags applied per the Step 5 practical rule (not exhaustively, not skipped where they matter).
- Microcopy Hot-Spots flagged at every user-visible copy point.
- i18n Decisions captured (if applicable): selector, URL strategy, persistence, fallback, locale rules.
- i18n Notes in per-flow where locale-sensitive elements exist.
- Shape implications flagged for any flow introducing new backing service interactions.
- Spec prose passes the Verbal Identity check (no Forbidden Language; outcomes-first; active voice).
- No file paths, component names, or technical implementation details in the spec.
- Length within targets: ≤30 lines/flow (soft 50); ≤200 lines total (soft 400). Overruns justified.
- Cross-cutting commands considered: if scope drifted during alignment, suggest `revise-requirements` rather than absorbing silently.

### **Step 8: Present and Iterate**

Present the spec. Iterate until **the user explicitly confirms** flows are complete and validated. Silence is not confirmation; ambiguous responses are not confirmation.

If during iteration the user introduces a requirement change that invalidates earlier alignment (new persona, new Success Criterion, removed scope), suggest the `revise-requirements` cross-cutting command rather than silently absorbing the change into a new draft.

## **Does NOT**

- Does NOT design data models / API endpoints / request shapes / response schemas — that is `tech-plan` (`03-tech-plan-command`) Step 6.C Component Architecture.
- Does NOT enumerate database tables / column types — that is `tech-plan` Data Model.
- Does NOT decompose flows into tickets — that is `ticket-outline` (`05-ticket-outline-command`).
- Does NOT design state-machine implementations (Redux/Zustand/etc.) — flows describe USER-VISIBLE state names only; the implementation pattern is `tech-plan`'s concern.
- Does NOT specify literal microcopy — flow documents name the **outcome** the copy must communicate per `ocoron-design-system.md` § Verbal Identity; the implementer writes the literal copy at code time. Forbidden Language list at L186 is the rejection filter, not a copy template.
- Does NOT re-derive INFRA-CHECK fields — consume from Epic Brief Metadata verbatim per Step 2 above. If a Path B field is missing (e.g., `Universal categories` absent from a multi-epic dispatch), stop and route back to `00-trigger-workflow-command`.
- Does NOT re-read research files — `trigger_workflow` already did that. Read flow context from the Epic Brief's Context & Problem section instead.
- Does NOT design observability events / log schemas — that is `tech-plan` + `06-ticket-breakdown` per `core/55-observability.md § Per-Scaffold Observability Matrix`.
- Does NOT design deploy configuration (compose.yaml, Traefik labels, healthcheck) — that is `04-deploy-plan`.
- Does NOT write i18n implementation code (`next-intl` function calls, locale file paths) — only UX behavior at the flow level; implementation is `tech-plan` + `06-ticket-breakdown`.

## **Acceptance Criteria**

- Applicability check honored: command runs only when `trigger_workflow` Step 6 routing included `core-flows`.
- Two-faced types handled: client + backend flows mapped where applicable.
- Upstream context consumed: Epic Brief sections, INFRA-CHECK fields (`Scaffold`, `Rule Packs`, `Shape`, `User Guide`, `i18n`, `Responsive`, `Dark+Light`, `Design System`), pre-research file, `ocoron-design-system.md`, `fabrik-lifecycle.md`.
- Scaffold-specific UI rule pack read per Step 3 table; domain packs read only when epic touches that domain. Read packs stated.
- All personas identified with complete journeys (entry, actions, feedback, exit, decisions, error paths, edge cases).
- Every flow traces to at least one Success Criterion; gaps surfaced, not silently dropped.
- UX dimensions (Information Hierarchy, Placement & Affordances, Feedback & State, Journey Integration, Language UX) aligned with user before documentation.
- Resilience paths documented: user-visible fallback for every external-service action (slow/down).
- i18n Decisions captured when applicable: selector placement, URL strategy, persistence, fallback, locale formatting rules.
- 7 Enriched States flagged only where practical rule applies; defaults not duplicated.
- Microcopy Hot-Spots listed with outcomes only; no literal copy.
- i18n Notes in per-flow flag locale-sensitive elements where developer would default wrong.
- Shape implications flagged for flows introducing new backing service needs.
- Each flow has exactly one `[PRIMARY PATH]` marker.
- Spec has Personas, Flow Index, i18n Decisions (if applicable), and flows in encounter order.
- Downstream doc feeds identified (FEATURES.md, QUICKSTART.md).
- Length discipline honored (≤30/flow, ≤200 total; overruns justified; near-cap triggers split).
- Hard exclusions: no file paths, component names, implementation details, literal copy, i18n implementation details.
- Verbal Identity applied; Forbidden Language rejected.
- Validation Gate walked with no unresolved gaps.
- User explicitly confirms. Silence ≠ confirmation.
