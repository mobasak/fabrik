---
description: Freeze the project's JOURNEY contract — docs/flows.md, every persona walked entry → actions → feedback → exit (decision points, edge/error paths, per-call resilience, one [PRIMARY PATH] per flow) BEFORE any field or screen freezes. EVERY scaffold type — user journeys (UI), consumer journeys (headless), reader journeys (docusaurus). After /fabrik-spec-review approval, before /fabrik-data-contract: journeys are the evidence that forces contract bumps instead of scope cuts. Self-converges to FROZEN. TRIGGER — EN: "map the journeys/flows"; TR: "akışları çıkar" — fires at design time, never a rendered UI (→ /design-review) or the contract's own review (→ /fabrik-flows-review). Stage: 2-contract.
argument-hint: "[spec path — omit to use the CONVERGED spec of the CURRENT project (the command always operates on cwd)]"
---

Produce (or backfill) this project's **journey contract** — one frozen file, `docs/flows.md`, the **single
source of truth for who moves through the product and how**: every persona's complete journey (entry →
actions → feedback → exit), the decision points, the edge/error paths, what the user sees when an external
call is slow or down, and exactly one `[PRIMARY PATH]` per flow. It is the feature-scale twin of the
epic-route Core Flows stage (`docs/orchestrator/epic-to-ticket-workflow/02-core-flows-fabrik.md` owns that
discipline at epic scale; THIS command owns it for the feature-scale pipeline) — and it sits **before the
data contract on purpose**:

```
/fabrik-spec → /fabrik-spec-review (approval) → /fabrik-flows (FREEZE, self-converge)
   → /fabrik-flows-review (independent converge → attest)
   → /fabrik-data-contract → (GUI) /fabrik-ui-design → … → planning → build
```

**Why journeys precede the contract (the ordering law):** a data contract frozen before any journey thinking
becomes a **scope ceiling** — downstream stages cut features "for want of fields" instead of bumping the
contract. Walking "a teammate receives an email and joins" *produces* the invitations entity, its status
transitions, and the token-landing surface before the contract freezes. **A journey implying an entity, field,
or state the contract will need is recorded as CONTRACT INPUT — never trimmed to fit.** The two live defect
classes this stage exists to kill: a feature whose *second actor* was never walked (an invite that could be
sent but never accepted — no token-landing surface ever designed), and an *async boundary* nobody stood in
(a paying customer shown a plan picker in the checkout→webhook gap).

**HARD GATES:**
1. **A CONVERGED spec first.** Input is the `/fabrik-spec` design doc after its `/fabrik-spec-review`
   approval. No converged spec → stop and route back.
2. **Every scaffolded type runs this — no skip list.** The *journey kind* varies by `project.yaml::type`;
   the discipline never does.
3. **No contract or UI design against a `DRAFT`.** `docs/flows.md` must reach `FROZEN` (an edit-free
   convergence round), then pass `/fabrik-flows-review`, before `/fabrik-data-contract` or
   `/fabrik-ui-design` consumes it.

{{include:run-record}}
{{include:term-edit}}
(This command owns the AUTHOR'S self-convergence; the separate `/fabrik-flows-review` runs the INDEPENDENT
author-blind pass — the split mirrors `/fabrik-spec` → `/fabrik-spec-review`.)

## Phase 0 — Establish scope, journey kind, and mode

Operate on the **current project** (cwd) — `$ARGUMENTS`, if given, is the spec path. State:

- **Journey kind from `project.yaml::type`** (the live registry is `scaffold.py::SCAFFOLD_TYPES`):
  - **User journeys** — `saas-skeleton`, `chrome-extension`, `mobile-app`, `desktop-app`, `static-site`:
    personas moving through screens and states.
  - **Consumer journeys** — `python-api`, `python-api-gpu`, `node-api`, `file-api`, `file-worker`: the
    CALLER is the persona — onboard/obtain credentials → authenticate → happy path → error path →
    rate-limit/quota path → deprecation/versioning path. This is the denominator `/fabrik-service-test`
    certifies against.
  - **Reader journeys** — `docusaurus`: find the answer from the landing page, search, land mid-site from a
    search engine, follow a cross-reference — the denominator `/fabrik-user-test` certifies for doc sites.
  - **Two-faced types** (`chrome-extension`, `mobile-app`, `desktop-app`) map BOTH the client-side journeys
    AND any backend-served ones (popup + dashboard; screens + API-driven notifications).
  - `wordpress` runs no fabrik command (out of fabrik, archived 2026-08-07) — not a skip, an absence.
- **Inputs (read them, name them):** the CONVERGED spec (goal, chosen approach, workflow) ·
  `project.yaml::type` · the scaffold's UI/surface pack when UI-bearing (`saas/60-saas-ui.md` ·
  `chrome-ext/70-chrome-ext.md` · `mobile-app/80-mobile.md` · `desktop-app/72-desktop.md`) · any domain pack
  the work touches (auth/signup → `core/35-security-auth.md`; payments → `core/85-payments-billing.md`;
  multi-tenant → `saas/95-multi-tenant-saas.md`) · `ocoron-design-system.md` § Verbal Identity + § States
  (UI types). State which packs were read.
- **Mode:** **new** (spec-driven) · **backfill** (walk the SHIPPED product's real journeys into the
  contract, grandfathering gaps with a `⚠` note) · **fresh** (no spec yet → minimal stub, say so).
  Absence of a flows contract in an already-shipped project is **not a defect** — this stage binds work
  entering the design pipeline, and `/fabrik-catchup` must not queue it retroactively.

## Phase 1 — Success Criteria (the tracing spine — extract if the spec lacks them)

Every flow will trace to ≥1 **Success Criterion**. If the converged spec carries an explicit list, quote it. If the EARLY
`/fabrik-features` pass ran, its `(Planned)` rows JOIN the tracing spine — every planned feature is
served by ≥1 flow, or the gap is surfaced.
If it does not (feature-scale specs often bury criteria in prose), **extract the criteria from the spec and
write them back to the spec as a short `## Success Criteria` section** (5–12 one-line, testable outcomes —
this is the one sanctioned spec edit; note it in the spec's changelog line). A criterion with no covering
journey, or a journey serving no criterion, is a finding — surfaced, never dropped.

## Phase 2 — Personas, including every SECOND ACTOR

Identify all personas from the spec — and then hunt the ones specs forget: **for every flow that SENDS
something (email, invite link, webhook, notification, export, payment request), the RECEIVER is a persona
whose journey must be walked too.** The receiving persona starts in a different context (no session, a
different tenant, an email client, a webhook consumer) — that entry point is exactly where unbuilt surface
hides. Headless: distinct consumer classes (first-time integrator, production caller at rate limit,
operator debugging a 4xx) are distinct personas.

## Phase 3 — Map the journeys

For each persona, map **Entry Point → Actions → Feedback → Exit**, with:

- **Decision points** where the system or the persona picks a path.
- **Edge cases + error scenarios** with the explicit system response (never "handle errors").
- **Boundary conditions:** token/link expiry, missing data, permissions, rate limits, quota.
- **Resilience (the persona's view):** for each action calling an external service (payment, search,
  upload, notification, model API), what the persona sees when it is slow (loading state + timeout
  threshold) and when it is down (graceful fallback + alternative).
- **Async boundaries (the gap state):** every external round-trip that completes OUT OF BAND (checkout →
  webhook, send → delivery, job → callback) names what the persona sees IN THE GAP between the two legs —
  the un-walked gap state is a live defect class (a paid customer re-offered the plan picker).
- **Contract inputs:** a journey step implying an entity, field, enum, or state transition → record it in
  the contract-inputs list (Phase 5). The journey is the evidence; `/fabrik-data-contract` freezes it.
- **Shape implications:** a journey introducing a backing-service interaction (search, storage, admin
  auth) → flag it for the spec's `shape:` block.
- **i18n (when the project declares i18n):** selector placement · URL strategy · persistence · mid-flow
  switch survival (form data? breadcrumbs?) · locale-sensitive elements per flow — one line each, only
  where a developer would default wrong.

## Phase 4 — Alignment before documentation

Seek explicit alignment on the load-bearing calls before writing the artifact — surfacing assumptions is
cheap, fixing frozen artifacts is expensive: information hierarchy · placement/affordances · feedback and
state signalling · how the journeys integrate (auth ↔ billing ↔ the core loop) · the i18n answers. Flag
enriched states (loading/empty/error/permission-denied/success/partial/disabled) **selectively**: only where
a persona would behave differently — or a developer would assume wrong — if the state went undocumented.

## Phase 5 — Document (the artifact)

Write `docs/flows.md`. **Per flow (target ≤30 lines, hard split at 50):** flow name (short imperative) ·
persona · the Success Criterion it serves · exactly **one `[PRIMARY PATH]`** marker on the 80%+ step
sequence (label only — a certification DEPTH input, never the denominator: the gauntlets resolve their
denominator from a live registry and demote every doc to a cross-check) · decision points ·
edge/error paths · resilience + async-gap states · **Microcopy Hot-Spots** naming the OUTCOME the copy must
communicate, never the literal string · i18n notes where applicable. **Mermaid sequence diagrams only for
genuinely multi-party logic.**

**Spec-wide (target ≤200 lines, soft cap 400):** header (`Status:` / `Version:` / `Date:` / `Type:` /
`Journey kinds:`) · one **Personas** section · one **Flow Index** (flow → Success Criterion) · one
**Contract inputs** section (the entities/fields/states the journeys surfaced — `/fabrik-data-contract`'s
evidence list) · (conditional) **i18n Decisions** · the flows in encounter order.

**Hard exclusions — these govern FLOW BODIES (the journey narratives), not lifecycle metadata:** no file
paths · no component names · no implementation detail (libraries, endpoints, DB tables) · no literal
microcopy · no test names. The **header, R-notes, Contract inputs, and the re-freeze close-out's
Downstream impact table are lifecycle metadata and EXEMPT** — their entire job is naming entities,
fields, tables, and consumer docs (`docs/data-contract.md`, `docs/ui-design.md`), which the close-out
mandates; a reviewer reading the exclusions against those sections is misapplying the law (live case:
four false CRITICALs in one transdoc review). Length discipline: a flow over 30 lines gets a one-line
justification; near 50, split it; the file near 400, propose splitting the feature.

**`[PRIMARY PATH]` counting rule — state it verbatim in the artifact:** *a MARKER is that token labelling a
step sequence inside a flow; every occurrence outside one — this rule, the freeze law, a validation-gate
line, a review ledger — is prose ABOUT the convention and is not counted.* Say it in the artifact or every
reader re-invents it: a naive grep conflates the two and mis-reports the per-flow count, which is a defect
under the "exactly one" gate above and has already mis-fired in a checker, mid-run, and in a review.

## Phase 6 — Validation gate, then self-convergence to FROZEN

Walk the gate; resolve gaps in conversation, never hand off with known gaps: every Success Criterion traced
to ≥1 flow · every persona's journey complete (entry/actions/feedback/exit/decisions/errors) · every SENDING
flow has its RECEIVING persona's journey · every async boundary has its gap state · exactly one
`[PRIMARY PATH]` per flow · resilience per external call · contract inputs recorded (never trimmed) ·
i18n decisions when applicable · hard exclusions honored · length within targets · **life-cycle arc
coverage (UI-bearing types):** the `/fabrik-user-test` Phase-1b arc set — *first-day · habitual ·
paying-customer (incl. a VOLUNTARY downgrade/cancel exit, not just involuntary recovery) · leaving-user ·
recovery (incl. an interrupted-journey resume)* — each applicable arc has entry AND exit legs, or the gap
is surfaced. Certification re-derives these arcs later; a flows contract frozen without them fails at cert
time or, worse, ships the hole (transdoc: two md5-verified convergence loops missed a missing
paying-customer exit and a missing resume path, because nothing after the authoring phase re-checked the
arc set).

Then converge: re-walk the whole artifact; fix; repeat until a full pass makes **zero edits** (md5 the file
before/after the closing pass — identical hashes are the proof). Set `Status: FROZEN`, bump `Version`.
**Present the frozen contract + the flow index to the user** — the freeze stands unless they redirect. **`FROZEN` is not `attested`:** handing the contract to `/fabrik-data-contract`, `/fabrik-ui-design`, or a planner before `/fabrik-flows-review` has run is skipping a required gate, not saving a step (§ Next).

**Freeze law (verbatim into the artifact):** *any journey/persona/flow change = bump `Version` +
re-freeze via `/fabrik-flows` — never edit in place. Downstream consumers
(`/fabrik-data-contract`, `/fabrik-ui-design`, the certification gauntlets) read the frozen version only.*

**Do not commit** unless the user says so this turn (`git add` is fine).

{{include:questionbar}}
## Re-freeze close-out (runs ONLY when this run was a version bump N→N+1 on an already-FROZEN artifact)

The frozen 2-contract chain (`flows.md` → `data-contract.md` → `ui-design.md` [→ `design-system.md`]) has
seams nothing else owns: your bump leaves every downstream consumer frozen against a version that no longer
exists. The synced gate (`check_frozen_chain.py`) catches the stale PIN mechanically — but only THIS run
holds the diff that names what changed, so only this run can say what the re-freeze must cover (transdoc
2026-08-22: a v5 column with a GUI-field name reached no screen; the pin gate alone would have hidden it):

1. **Diff the artifact against its pre-run version** (`git diff HEAD -- <artifact>` before committing, or
   HEAD~1 after) and extract the changed entity/column/enum/section names.
2. **Grep each DOWNSTREAM frozen consumer** for those names and emit a **Downstream impact** table in the
   closing report: `changed name → consumer → citing section(s) → verdict (cites it / silent)`. Zero hits
   is a stated result, never an omitted one.
3. **The NEXT line becomes the owed re-freeze** when impact is non-empty: name the consumer's owning
   command WITH the impact list as its arguments (e.g. `NEXT: /fabrik-ui-design — re-freeze v9→v10:
   projects.domain needs a §5.3 control; §5.11 'unbuildable' passages now stale`) — never the first-run
   pipeline chain line. The gate's WARN will nag until that re-freeze lands; the impact list is the part
   only you know.

## Next — run `/fabrik-flows-review` (the independent pass, before any consumer)

Freezing here is the AUTHOR'S convergence: it cannot catch its own blind spots, and this contract is the
one every downstream freeze reads. Before `/fabrik-data-contract`, `/fabrik-ui-design`, or any planner
consumes it, run **`/fabrik-flows-review`** on it — the independent, author-blind pass that re-traces every
Success Criterion, re-derives the SECOND-ACTOR and life-cycle-arc coverage, and converges to its own
edit-free md5 no-op. The split mirrors `/fabrik-spec` → `/fabrik-spec-review`.

**Do NOT let a consumer freeze against a contract the review has not attested** — a `FROZEN` status is the
author's word; the review is what makes it independent. If the review surfaces something it cannot
reconcile, it routes back here; resolve that before the contract is consumed.

{{include:subagents-core}}
