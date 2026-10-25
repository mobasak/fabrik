---
description: Freeze the project's JOURNEY contract — docs/flows.md, every persona walked entry → actions → feedback → exit (decision points, edge/error paths, per-call resilience, one [PRIMARY PATH] per flow) BEFORE any field or screen freezes. EVERY scaffold type — user journeys (UI), consumer journeys (headless), reader journeys (docusaurus). After /fabrik-spec-review approval, before /fabrik-data-contract: journeys are the evidence that forces contract bumps instead of scope cuts. Self-converges to FROZEN. TRIGGER — EN: "map the journeys/flows"; TR: "akışları çıkar" — fires at design time, never a rendered UI (→ /design-review) or the contract's own review (→ /fabrik-flows-review). Stage: 2-contract.
argument-hint: "[spec path — omit to use the CONVERGED spec of the CURRENT project (the command always operates on cwd)]"
---

Produce (or backfill) the **journey contract** `docs/flows.md`: every persona's journey (entry → actions → feedback → exit), decision points, edge/error paths, what the user sees when an external call is slow or down, and exactly one `[PRIMARY PATH]` per flow. An epic's journeys are frozen here too, from the spec `/fabrik-spec <epic file>` produced.

```
/fabrik-spec → /fabrik-spec-review (approval) → /fabrik-flows (FREEZE, self-converge)
   → /fabrik-flows-review (independent converge → attest)
   → /fabrik-data-contract → (GUI) /fabrik-ui-design → … → planning → build
```

**Journeys precede the contract:** a contract frozen first becomes a **scope ceiling**. **A journey implying an entity, field, or state the contract will need is recorded as CONTRACT INPUT — never trimmed to fit.**

**HARD GATES:**
1. **A CONVERGED spec first** (the `/fabrik-spec` design doc after `/fabrik-spec-review` approval). None → stop and route back.
2. **Every scaffolded type runs this — no skip list.** The *journey kind* varies by `project.yaml::type`; the discipline never does.
3. **No contract or UI design against a `DRAFT`.** `docs/flows.md` must reach `FROZEN` (the closing round of its Termination contract — `confirmed: 0`, md5 unchanged), then pass `/fabrik-flows-review`, before `/fabrik-data-contract` or `/fabrik-ui-design` consumes it.

{{include:run-record}}
{{include:orient}}

{{include:delegated-reads}}
{{include:term-edit}}

## Phase 0 — Establish scope, journey kind, and mode

Operate on the **current project** (cwd); `$ARGUMENTS`, if given, is the spec path. State:

- **Journey kind from `project.yaml::type`** (registry: `scaffold.py::SCAFFOLD_TYPES`):
  - **User journeys** — `saas-skeleton`, `chrome-extension`, `office-extension`, `mobile-app`, `desktop-app`, `static-site`: personas moving through screens and states.
  - **Consumer journeys** — `python-api`, `python-api-gpu`, `node-api`, `file-api`, `file-worker`: the CALLER is the persona (credentials → authenticate → happy path → error → rate-limit/quota → deprecation); `/fabrik-service-test` certifies against it.
  - **Reader journeys** — `docusaurus`: answer from the landing page, search, mid-site landing, cross-reference; `/fabrik-user-test` certifies against it.
  - **Two-faced types** (`chrome-extension`, `office-extension`, `mobile-app`, `desktop-app`) map client AND backend-served journeys.
  - `wordpress` runs no fabrik command: an absence, not a skip.
- **Inputs (name them):** the CONVERGED spec, `project.yaml::type`, the scaffold's UI pack (UI-bearing), the domain pack the work touches (auth `core/35-security-auth.md`, payments `core/85-payments-billing.md`, multi-tenant `saas/95-multi-tenant-saas.md`), and for UI types `design-system-template.md` § States (Enriched) plus the brand voice (`docs/design-system.md` § Voice). State which packs were read.
- **Mode:** **new** (spec-driven) · **backfill** (walk the SHIPPED product, grandfathering gaps with a `⚠` note) · **fresh** (no spec → minimal stub, say so). A shipped project without a flows contract is **not a defect**; `/fabrik-catchup` must not queue one.

## Phase 1 — Success Criteria (the tracing spine)

Every flow traces to ≥1 **Success Criterion**: quote the spec's list (the `(Planned)` rows of an EARLY `/fabrik-features` pass JOIN it). With none, **write 5–12 one-line testable criteria back as a `## Success Criteria` section** — the one sanctioned spec edit, noted in its changelog line. A criterion with no journey, or a journey serving none, is a finding — surfaced, never dropped.

## Phase 2 — Personas, including every SECOND ACTOR

**The spec's `## Personas` section is the DENOMINATOR:** walk every persona it lists or declare it OUT with a one-line reason. **The primary flow carries the spec's frozen STEP BUDGET: count the primary path's steps as you map it; over budget is a FINDING against whichever contract is wrong.** **For every flow that SENDS something (email, invite, webhook, notification, export, payment request), the RECEIVER is a persona whose journey must be walked too** — it enters without a session, where unbuilt surface hides. Headless: distinct consumer classes (first-time integrator, caller at rate limit, operator debugging a 4xx) are distinct personas.

## Phase 3 — Map the journeys

**Parallelism — UNCONDITIONAL, every run.** Dispatch **one native `general-purpose` seat per persona (or per journey), all in a single message**; each walks its path through the spec, code and existing flows and returns the journey plus the gaps it hit. The persona count is the PARTITION: `dispatch_headroom.py --units <N> --mechanical 0` prints the seats, stamped BEFORE dispatch with `python3 scripts/command_run.py dispatch --seats <n>` (no Haiku seat; the Opus seat re-walks the highest-risk persona). YOU own the journey judgment, the [PRIMARY PATH] call and every edit; seats ground, they do not author.
**Never solo, never two:** under three units, still dispatch **THREE seats on DIFFERENT angles**.

Per persona map **Entry Point → Actions → Feedback → Exit**, adding:

- **Decision points** and **edge/error cases** with the explicit system response (never "handle errors"); **boundaries:** expiry, missing data, permissions, rate limits, quota.
- **Resilience:** per external call, what shows when it is slow (loading state + timeout threshold) and down (fallback + alternative).
- **Async boundaries:** every out-of-band round-trip (checkout → webhook, send → delivery) names what the persona sees IN THE GAP.
- **Contract inputs:** a step implying an entity, field, enum or state transition goes in the Phase 5 list; a new backing-service interaction is flagged for the spec's `shape:` block.
- **i18n (when declared):** selector placement · URL strategy · persistence · mid-flow switch survival — one line each, only where a developer would default wrong.

## Phase 4 — Alignment before documentation

Get explicit alignment on the load-bearing calls before writing (information hierarchy, feedback and state signalling, how auth ↔ billing ↔ core loop integrate, i18n). Flag enriched states (loading/empty/error/permission-denied/success/partial/disabled) only where a persona would behave differently if undocumented.

## Phase 5 — Document (the artifact)

Write `docs/flows.md`. **Per flow (target ≤30 lines, hard split at 50):** short imperative name · persona · the Success Criterion served · exactly **one `[PRIMARY PATH]`** marker on the 80%+ step sequence (a certification DEPTH label, never the denominator) · decision points · edge/error paths · resilience + async-gap states · **Microcopy Hot-Spots** naming the OUTCOME the copy must communicate, never the literal string · i18n notes. **Mermaid sequence diagrams only for genuinely multi-party logic.**

**Spec-wide (target ≤200 lines, soft cap 400):** header (`Status:` / `Version:` / `Date:` / `Type:` / `Journey kinds:`) · **Personas** · **Flow Index** (flow → Success Criterion) · **Contract inputs** (entities/fields/states surfaced) · (conditional) **i18n Decisions** · flows in encounter order.

**Hard exclusions govern FLOW BODIES, not lifecycle metadata:** no file paths · no component names · no implementation detail (libraries, endpoints, DB tables) · no literal microcopy · no test names. The **header, R-notes, Contract inputs, and the re-freeze close-out's Downstream impact table are EXEMPT**. A flow over 30 lines gets a one-line justification; near 50, split it; the file near 400, propose splitting the feature.

**`[PRIMARY PATH]` counting rule — state it verbatim in the artifact:** *a MARKER is that token labelling a
step sequence inside a flow; every occurrence outside one — this rule, the freeze law, a validation-gate
line, a review ledger — is prose ABOUT the convention and is not counted.*

## Phase 6 — Validation gate, then self-convergence to FROZEN

Walk the gate and resolve gaps in conversation, never hand off with known gaps: every Success Criterion traced to ≥1 flow · every persona complete (entry/actions/feedback/exit) · every SENDING flow has its RECEIVING persona · every async boundary has its gap state · exactly one `[PRIMARY PATH]` per flow · resilience per external call · contract inputs recorded · i18n decisions · hard exclusions honored · length within targets · **life-cycle arcs (UI-bearing types):** the `/fabrik-user-test` Phase-1b set — *first-day · habitual · paying-customer (incl. a VOLUNTARY downgrade/cancel exit) · leaving-user · recovery (incl. an interrupted-journey resume)* — each applicable arc has entry AND exit legs, or the gap is surfaced.

Then converge: re-walk, fix, repeat until the Termination contract's closing round — `confirmed: 0`, file md5 identical before and after. Set `Status: FROZEN`, bump `Version`.
**The freeze is a Status flip: mint its `docs/DECISIONS.md` row in the same change** (a re-freeze N→N+1 is a NEW row, never an edit), staged WITH the artifact in the commit below.
**Present the frozen contract + flow index to the user**; the freeze stands unless they redirect. **`FROZEN` is not `attested`:** handing it to `/fabrik-data-contract`, `/fabrik-ui-design`, or a planner before `/fabrik-flows-review` skips a required gate (§ Next).

**Freeze law (verbatim into the artifact):** *any journey/persona/flow change = bump `Version` +
re-freeze via `/fabrik-flows` (or `/fabrik-flows-review`'s in-review re-freeze, its sanctioned
exception) — never edit in place. Downstream consumers
(`/fabrik-data-contract`, `/fabrik-ui-design`, the certification gauntlets) read the frozen version only.*

**Commit** the artifact at its first write, `DRAFT` included, with its `INDEX.md` and `docs/README.md` rows in the same commit: CLAUDE.md § EXIT overrides any "do not commit" rule, and an untracked `docs/` file reds every full (Tier-2) gate run in that checkout, a sibling's included (`check_doc_index.py`: "live doc not in INDEX.md … (untracked — the run that creates a doc owes its INDEX row)"). Committing is not approving; the user's word is needed for the APPROVAL and anything beyond this artifact's paths.

{{include:questionbar}}
## Re-freeze close-out (runs ONLY on a version bump N→N+1 of a FROZEN artifact)

A bump leaves every downstream consumer (`flows.md` → `data-contract.md` → `ui-design.md` [→ `design-system.md`]) frozen against a dead version; `check_frozen_chain.py` catches the stale PIN, only this run holds the diff:

1. **Diff the artifact against its pre-run version** (`git diff HEAD -- <artifact>`, or HEAD~1 after committing) and extract the changed entity/column/enum/section names.
2. **Grep each downstream frozen consumer** for them and emit a **Downstream impact** table: `changed name → consumer → citing section(s) → verdict (cites it / silent)`. Zero hits is a stated result, never omitted.
3. **With impact, the NEXT line is the owed re-freeze**: the consumer's owning command WITH the impact list as arguments (e.g. `NEXT: /fabrik-ui-design — re-freeze v9→v10: projects.domain needs a §5.3 control; §5.11 'unbuildable' passages now stale`), never the first-run chain line.

## Next — run `/fabrik-flows-review` (the independent pass, before any consumer)

Run **`/fabrik-flows-review`** — the author-blind pass that re-traces every Success Criterion and re-derives SECOND-ACTOR and life-cycle-arc coverage — before any consumer reads the contract. **Do NOT let a consumer freeze against a contract the review has not attested**; a review that cannot reconcile something routes back here.


{{include:subagents-core}}

{{include:close-chain}}
