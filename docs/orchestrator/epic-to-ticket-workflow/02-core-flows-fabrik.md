<!-- ⚠️ FABRIK FACTORY WORKFLOW — CORE FLOWS (our own, tool-capable twin of 02-core-flows-command)
     Run DIRECTLY by our orchestrator agent (Claude Code CLI, in VS Code) — never pasted into a planner GUI.
     GUI-ONLY: runs only when 00-trigger-fabrik's route included `core-flows`. TOOL-CAPABLE: it READS the
     Decisions Lock + design-system + UI rule pack from disk, and gates with final_gate.py.

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · the LOCKED Decisions-Lock artifact — `docs/superpowers/specs/YYYY-MM-DD-<slug>-decisions.md`
         (`01`'s output, locked by `01R`) — the PRIMARY flow-context source; Path B: plus the dispatched
         epic file
       · the `00-trigger-fabrik` INFRA-CHECK (the field values it emitted)
       · `.windsurf/rules/core/ocoron-design-system.md` — § Verbal Identity · § States (§ Voice lives under
         Verbal Identity)
       · the scaffold's UI rule pack (Step 3 table) + any domain pack the epic touches (Step 3)
       · `docs/operations/fabrik-lifecycle.md` (flows → registrars)
       · the pre-research file ONLY if the Decisions Lock's Context & Problem is thin on flow detail (Step 2.3)
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Core Flows

## Role

Product manager who designs user experiences through flow mapping — entry points, actions, feedback, edge cases. Speak with the Ocoron "Engineer Who Ships" voice `[canonical: ocoron-design-system.md § Verbal Identity → Voice]`: precise, grounded, outcome-focused.

## Core Philosophy

Alignment, not artifacts. Flows are discussed and agreed in conversation before they are documented — do not rush to draft. Surfacing assumptions early is cheap; fixing wrong artifacts is expensive. Consume what `00-trigger-fabrik` and `01-decisions-lock-fabrik` established; do not redo work. Only proceed when the user explicitly confirms — silence is not confirmation.

## Processing User Request

### Step 1: Applicability Check

`00-trigger-fabrik` Step 6 already decided whether `core-flows` runs. Do not re-ask.

- **Skipped for** `python-api` · `python-api-gpu` · `node-api` · `file-api` · `file-worker` · `wordpress` (→ `/opt/wpf`) · `docusaurus` `[canonical: 00-trigger-fabrik § Step 6 routing table]`. If the route skipped `core-flows` for this scaffold, this command should not have been triggered — say so and stop.
- **Path B (multi-epic):** if the epic ticket's scaffold is in the skip list, do not run — UNLESS the epic touches UI (user-facing flows), in which case it runs regardless of backend scaffold. Then:
  - Read `Universal categories` from the Decisions Lock Metadata. Scope Core Flows to journeys serving ONLY the categories this epic owns; a sibling epic's categories are `Out of Scope` here.
  - Read `Epic Flavor`. `Delta-feature` → full Step 4 + 4b + 5. `Retrofit` → scope-narrow to ONLY the surface the retrofit touches (`Retrofit: i18n` → locale-loading flows; `Retrofit: Resilience` → state-flag updates to existing flows, no new flows; `Retrofit: <UI area>` → that UI's flows). Skip Step 5 for code-only retrofits with no new UI. Retrofit target ≤100 lines (vs Delta's 200).
- **Two-faced types** (`chrome-extension`, `mobile-app`, `desktop-app`): map BOTH client-side UX AND backend-served UX (e.g. extension popup + FastAPI dashboard; mobile screens + API-driven notifications).

### Step 2: Consume Upstream Context

Read in order; everything builds on these:

1. **Decisions Lock** (this epic) — Goal, Context & Problem, Decisions, Success Criteria, Out of Scope, Metadata (the artifact also carries INFRA-CHECK, Constraint findings, Route, grounded deps). Every flow must trace to ≥1 Success Criterion.
2. **INFRA-CHECK** — capture `Scaffold`, `Rule Packs`, `Shape`, `User Guide`, `i18n`, `Responsive`, `Dark+Light`, `Design System`; **Path B also**: `Registrars`, `Universal categories`, `Epic Flavor`, `Abuse Detection`, `Email`, `FINANCIALS`. Core Flows uses `Universal categories` + `Epic Flavor` for scope (Step 1); `Abuse Detection`/`Email` surface only in signup/transactional flows; `FINANCIALS` is a `ticket-outline` doc deliverable, not a flow input. `Responsive: 375px–2560px` and `Dark+Light: mandatory` bind flows across the full breakpoint range and both themes — **feature-trigger** (any scaffold with a web GUI surface, incl. python-api/node-api/file-api with `shape.is_admin_dashboard: true` OR `shape.is_public: true` + HTML output) `[canonical: mega/00 § Rule-area applicability matrix]`.
3. **Decisions Lock Context & Problem** is the primary flow-context source. Re-read the pre-research file `00-trigger-fabrik` identified ONLY if that section is thin on flow-level detail — do not re-discover (`00-trigger-fabrik` already did discovery).
4. `.windsurf/rules/core/ocoron-design-system.md` — must already be read (INFRA-CHECK `Design System: read`). If it shows not-read, stop and route back to `00-trigger-fabrik`.
5. `docs/operations/fabrik-lifecycle.md` — flows touching an admin dashboard trigger the authelia registrar; flows with search trigger meilisearch. Flag these for the shape block (Step 4).

### Step 3: Identify the UI Rule Pack

Read the scaffold-specific UI pack for user-facing structural patterns only (never embed implementation in a flow):

| Scaffold | UI rule pack to read |
|---|---|
| `saas-skeleton`, `static-site` | `.windsurf/rules/saas/60-saas-ui.md` |
| `chrome-extension` | `.windsurf/rules/chrome-ext/70-chrome-ext.md` |
| `mobile-app` | `.windsurf/rules/mobile-app/80-mobile.md` + `.windsurf/rules/mobile-app/ocoron-mobile-design-system.md` |
| `desktop-app` | `.windsurf/rules/desktop-app/72-desktop.md` (+ `.windsurf/rules/core/20-typescript.md` for language conventions) |

Also read **only when the epic touches that domain** (judged from the Decisions Lock): auth/login/signup → `core/35-security-auth.md` · payments/billing → `core/85-payments-billing.md` · multi-tenant UI → `saas/95-multi-tenant-saas.md`. State which packs were read.

### Step 4: Map Journeys

Identify all personas from the Decisions Lock. For each, map **Entry Point → Actions → Feedback → Exit**, with:

- Decision points where system or user picks a path.
- Edge cases + error scenarios with explicit system response.
- Boundary conditions (token expiry, missing data, rate limits, permissions).
- **Resilience (user's view):** for each action calling an external service (payment, search, upload, notification), document what the user sees when it's slow (loading state + timeout threshold) or down (graceful fallback + alternatives).
- **Language context:** on mid-flow language switch — what persists? URL change? Form data survives?
- **Shape implications:** a flow introducing a new backing-service interaction (search, storage, admin auth) → flag it; `03-tech-plan-command` must reflect it in the shape block.

Every journey traces to ≥1 Success Criterion. A criterion with no covering journey is a gap — surface it as a question.

### Step 4b: i18n Flow Requirements

If INFRA-CHECK `i18n ≠ N/A`, decide during flow mapping: (1) **selector placement** (header/footer/settings/URL); (2) **URL strategy** (`/tr/…` path vs `?lang=tr` query vs subdomain); (3) **persistence** (cookie/localStorage/profile field); (4) **content continuity** on mid-session switch (form input persists? breadcrumbs update? cached pages invalidate?); (5) **missing-key fallback** (English fallback / key name / log); (6) **locale-sensitive elements** per flow — dates (`May 16, 2026` vs `16 Mayıs 2026`), numbers (`1,234.56` vs `1.234,56`), currency, Turkish plural logic, text direction (en/tr are LTR; flag any planned RTL). Surface as Step-5 questions; document the agreed answers.

### Step 5: UX Alignment Dimensions

Seek explicit alignment before documenting — do not assume: (1) **Information Hierarchy** (critical vs secondary, grouping); (2) **Placement & Affordances** (where actions live, discoverability); (3) **Feedback & State** (in-progress / succeeded / failed signalling); (4) **Journey Integration** (how this connects to Auth/Billing/Search); (5) **Language UX** (Step 4b answers).

**7 Enriched States — flag SELECTIVELY, not exhaustively.** `saas/60-saas-ui.md` requires every interactive component to handle **Loading / Empty / Error / Permission Denied / Success / Partial Success / Disabled** `[canonical: ocoron-design-system.md § States]`. In the flow doc, flag a state **only** if: *"would a user behave differently, or a developer make a wrong assumption, if this state weren't documented here?"* Flag e.g. an Empty state for a new user on a data-dependent list, or a Disabled CTA when permissions/quota block it. Do NOT flag generic Loading skeletons or save-confirmation toasts (covered by pack defaults). Do not proceed to documentation until all five dimensions are aligned.

### Step 6: Document Flows (Spec Artifact)

Document only after explicit confirmation. **Per-flow (target ≤30 lines, soft cap 50):** Flow name (short imperative) · Persona · Success Criterion it serves · **Mermaid sequence diagram** for genuinely multi-party logic (`participant` + `Note over`) · exactly one `[PRIMARY PATH]` marker on the 80%+ step sequence (label only — no test name, no Given/When/Then, no assertions; `06-ticket-breakdown-command` consumes it to nominate the integration-test target) · Decision points · Edge/error paths (every Step-4 error) · Resilience paths · State flags (only where the Step-5 rule warrants) describing user-visible behavior · **Microcopy Hot-Spots** (name the *outcome* the copy must communicate, never the literal string — the implementer writes copy per `[canonical: ocoron-design-system.md § Verbal Identity]`) · i18n Notes (when `i18n ≠ N/A`, one line per locale-sensitive element only where a developer would default wrong).

**Spec-wide (target ≤200 lines, soft cap 400):** one **Personas** section · one **Flow Index** (flow → Success Criterion) · one **i18n Decisions** section (if applicable) · one flow per journey in encounter order.

**Downstream doc feeds:** Core Flows informs `docs/FEATURES.md` + `docs/QUICKSTART.md`; `06-ticket-breakdown-command` Doc Sync Matrix assigns which ticket fills them.

**Hard exclusions:** no file paths · no codebase component names · no implementation detail (libraries, frameworks, API endpoints, DB tables) · no literal microcopy · no i18n implementation (no `next-intl` calls or locale paths — UX behavior only).

**Verbal Identity in spec prose** `[canonical: ocoron-design-system.md § Verbal Identity]`: lead with outcomes, specific numbers over adjectives, active voice, short paragraphs; reject the Forbidden Language list (the design-system file holds it — do not duplicate).

**Length discipline:** flow >30 lines → justify in one line; approaching 50 → split the flow; total approaching 400 → propose splitting the epic.

### Step 7: Validation Gate

Walk before handoff; resolve gaps in conversation, do not hand off with known gaps: every Success Criterion traced to ≥1 flow · every persona has a complete journey (entry, actions, feedback, exit, decisions, error paths) · every flow has exactly one `[PRIMARY PATH]` on a step sequence · resilience paths for every external-service action · 7-state flags per the Step-5 rule (not exhaustive, not skipped where they matter) · Microcopy Hot-Spots at every copy point (outcomes only) · i18n Decisions + per-flow Notes (if applicable) · shape implications flagged · prose passes Verbal Identity · no file paths / component names / implementation detail · length within targets.

### Step 8: Present and Iterate

Present. Iterate until the user explicitly confirms flows are complete — silence and ambiguous responses are not confirmation. A mid-iteration requirement change (new persona, new Success Criterion, removed scope) → route to `09-revise-requirements-command`, don't silently absorb.

## Does NOT

- Design data models / API endpoints / request/response shapes — that is `03-tech-plan-command` (Component Architecture / Data Model).
- Decompose flows into tickets — that is `05-ticket-outline-command`.
- Design state-machine implementations (Redux/Zustand) — flows name USER-VISIBLE state names only; the pattern is `03-tech-plan-command`'s concern.
- Specify literal microcopy — name the outcome per `[canonical: ocoron-design-system.md § Verbal Identity]`; the implementer writes it.
- Re-derive INFRA-CHECK fields — consume from the Decisions Lock Metadata verbatim (Step 2). A missing Path B field (e.g. `Universal categories`) → stop, route back to `00-trigger-fabrik`.
- Design observability events / deploy config — that is `03-tech-plan-command` + `06-ticket-breakdown-command` (observability) and `04-deploy-plan-command` (compose/Traefik/healthcheck).
- Write i18n implementation code — UX behavior at flow level only; implementation is `03-tech-plan-command` + `06-ticket-breakdown-command`.

## Acceptance Criteria

- Runs only when `00-trigger-fabrik` Step 6 routing included `core-flows`; two-faced types map client + backend flows.
- Upstream consumed: Decisions Lock sections + INFRA-CHECK fields + design-system + `fabrik-lifecycle.md`; scaffold UI pack (Step 3 table) + domain packs (only when the epic touches them) read and stated.
- All personas have complete journeys; every flow traces to ≥1 Success Criterion; gaps surfaced, not dropped.
- UX dimensions aligned with the user before documentation; resilience paths for every external-service action.
- i18n Decisions captured when applicable; 7-state flags only where the rule applies; Microcopy Hot-Spots as outcomes only; shape implications flagged.
- Each flow has exactly one `[PRIMARY PATH]`; spec has Personas + Flow Index + (conditional) i18n Decisions, flows in encounter order.
- Hard exclusions honored; Verbal Identity applied; length discipline honored; Validation Gate walked with no unresolved gaps.
- User explicitly confirms.

---

**Next (CC1 pairing, north star § Command-chain build plan):** converge this Core Flows spec with `/fabrik-workflow-review <spec path> core-flows` — it forces the no-op (every Success Criterion covered, one `[PRIMARY PATH]` per flow, resilience + i18n + state flags present, no implementation detail, zero hollow citations) before anything consumes it. Then → `03-tech-plan-command`. *(Downstream ettw twins are built incrementally; refs point to the live Traycer `-command` source and flip to `-fabrik` as each twin lands.)*
