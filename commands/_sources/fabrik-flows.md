---
description: Freeze the project's JOURNEY contract — docs/flows.md, every persona walked entry → actions → feedback → exit (decision points, edge/error paths, per-call resilience, one [PRIMARY PATH] per flow) BEFORE any field or screen freezes. EVERY scaffold type — user journeys (UI), consumer journeys (headless), reader journeys (docusaurus). After /fabrik-spec-review approval, before /fabrik-data-contract: journeys are the evidence that forces contract bumps instead of scope cuts. Self-converges to FROZEN. TRIGGER — EN: "map the journeys/flows"; TR: "akışları çıkar" — fires at design time, never a rendered UI (→ /design-review) or the contract's own review (→ /fabrik-flows-review). Stage: 2-contract.
argument-hint: "[spec path — omit to use the CONVERGED spec of the CURRENT project (the command always operates on cwd)]"
---

Produce (or backfill) the **journey contract** `docs/flows.md`: every persona's complete journey (entry → actions → feedback → exit), decision points, edge/error paths, what the user sees when an external call is slow or down, and exactly one `[PRIMARY PATH]` per flow. An epic's journeys are frozen here too, from the spec `/fabrik-spec <epic file>` produced.

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
This command owns the AUTHOR'S self-convergence; the separate `/fabrik-flows-review` runs the INDEPENDENT author-blind pass.

## Phase 0 — Establish scope, journey kind, and mode

Operate on the **current project** (cwd); `$ARGUMENTS`, if given, is the spec path. State:

- **Journey kind from `project.yaml::type`** (registry: `scaffold.py::SCAFFOLD_TYPES`):
  - **User journeys** — `saas-skeleton`, `chrome-extension`, `office-extension`, `mobile-app`, `desktop-app`, `static-site`: personas moving through screens and states.
  - **Consumer journeys** — `python-api`, `python-api-gpu`, `node-api`, `file-api`, `file-worker`: the CALLER is the persona onboard/obtain credentials → authenticate → happy path → error path → rate-limit/quota path → deprecation/versioning path. This is the denominator `/fabrik-service-test` certifies against.
  - **Reader journeys** — `docusaurus`: find the answer from the landing page, search, land mid-site from a search engine, follow a cross-reference — the denominator `/fabrik-user-test` certifies for doc sites.
  - **Two-faced types** (`chrome-extension`, `office-extension`, `mobile-app`, `desktop-app`) (hosted taskpane + fleet backend, D-039) map BOTH the client-side journeys AND any backend-served ones (popup + dashboard; screens + API-driven notifications).
  - `wordpress` runs no fabrik command (out of fabrik, archived 2026-08-07) — not a skip, an absence.
- **Inputs (read them, name them):** the CONVERGED spec, `project.yaml::type`, the scaffold's UI/surface pack when UI-bearing (`saas/60-saas-ui.md` · `chrome-ext/70-chrome-ext.md` · `mobile-app/80-mobile.md` · `desktop-app/72-desktop.md`), any domain pack the work touches (auth/signup `core/35-security-auth.md`, payments `core/85-payments-billing.md`, multi-tenant `saas/95-multi-tenant-saas.md`), and for UI types `design-system-template.md` § States (Enriched) plus the resolved brand's voice (`docs/design-system.md` § Voice; ocoron: `ocoron-design-system.md` § Verbal Identity). State which packs were read.
- **Mode:** **new** (spec-driven) · **backfill** (walk the SHIPPED product's real journeys into the contract, grandfathering gaps with a `⚠` note) · **fresh** (no spec → minimal stub, say so). A shipped project without a flows contract is **not a defect**; `/fabrik-catchup` must not queue it retroactively.

## Phase 1 — Success Criteria (the tracing spine)

Every flow traces to ≥1 **Success Criterion**: quote the spec's list (the `(Planned)` rows of an EARLY `/fabrik-features` pass JOIN it — every planned feature is served by ≥1 flow, or the gap is surfaced). With none, **extract the criteria and write 5–12 one-line testable criteria back as a `## Success Criteria` section** — the one sanctioned spec edit, noted in its changelog line. A criterion with no journey, or a journey serving none, is a finding — surfaced, never dropped.

## Phase 2 — Personas, including every SECOND ACTOR

**The spec's `## Personas` section is the DENOMINATOR:** walk every persona it lists or declare it OUT with a one-line reason — a persona silently absent from flows.md is a coverage defect, not an editorial choice. **The primary flow carries the spec's frozen STEP BUDGET: count the primary path's steps as you map it; over budget is a FINDING against whichever contract is wrong.** Then hunt the personas specs forget: **for every flow that SENDS something (email, invite link, webhook, notification, export, payment request), the RECEIVER is a persona whose journey must be walked too** — it starts in a different context (no session, a different tenant, an email client, a webhook consumer), where unbuilt surface hides. Headless: distinct consumer classes (first-time integrator, production caller at rate limit, operator debugging a 4xx) are distinct personas.

## Phase 3 — Map the journeys

**Parallelism — UNCONDITIONAL, every run.** Dispatch **one native `general-purpose` seat per persona (or per journey), all in a single message**; each walks its path through the spec, code and existing flows and returns its entry → actions → feedback → exit with the gaps it hit. The persona count is the PARTITION: `dispatch_headroom.py --units <N> --mechanical 0` prints the seats, stamped BEFORE dispatch with `python3 scripts/command_run.py dispatch --seats <n>` (D-191: no Haiku seat; the Opus authoritative seat re-walks the highest-risk persona). YOU own the journey judgment, the [PRIMARY PATH] call and every edit; seats ground, they do not author.
**Never solo, never two:** a surface with fewer than three units still dispatches **THREE seats on DIFFERENT angles** over it — measured, not assumed (D-186).

Per persona map **Entry Point → Actions → Feedback → Exit**, adding:

- **Decision points** where the system or the persona picks a path, and **edge/error cases** with the explicit system response (never "handle errors"); **boundaries:** token/link expiry, missing data, permissions, rate limits, quota.
- **Resilience (the persona's view):** for each action calling an external service, what the persona sees when it is slow (loading state + timeout threshold) and down (graceful fallback + alternative).
- **Async boundaries:** every external round-trip that completes OUT OF BAND (checkout → webhook, send → delivery) names what the persona sees IN THE GAP between the two legs.
- **Contract inputs:** a step implying an entity, field, enum or state transition goes in the Phase 5 list (the journey is the evidence; `/fabrik-data-contract` freezes it); a new backing-service interaction is flagged for the spec's `shape:` block.
- **i18n (when declared):** selector placement · URL strategy · persistence · mid-flow switch survival · locale-sensitive elements per flow — one line each, only where a developer would default wrong.

## Phase 4 — Alignment before documentation

Get explicit alignment on the load-bearing calls before writing (information hierarchy · placement/affordances · feedback and state signalling, how auth ↔ billing ↔ core loop integrate, i18n). Flag enriched states (loading/empty/error/permission-denied/success/partial/disabled) selectively: only where a persona would behave differently — or a developer would assume wrong — if the state went undocumented.

## Phase 5 — Document (the artifact)

Write `docs/flows.md`. **Per flow (target ≤30 lines, hard split at 50):** short imperative name · persona · the Success Criterion served · exactly **one `[PRIMARY PATH]`** marker on the 80%+ step sequence (label only — a certification DEPTH input, never the denominator: the gauntlets resolve their denominator from a live registry and demote every doc to a cross-check) · decision points · edge/error paths · resilience + async-gap states · **Microcopy Hot-Spots** naming the OUTCOME the copy must communicate, never the literal string · i18n notes where applicable. **Mermaid sequence diagrams only for genuinely multi-party logic.**

**Spec-wide (target ≤200 lines, soft cap 400):** header (`Status:` / `Version:` / `Date:` / `Type:` / `Journey kinds:`) · one **Personas** section · one **Flow Index** (flow → Success Criterion) · one **Contract inputs** section (the entities/fields/states the journeys surfaced — `/fabrik-data-contract`'s evidence list) · (conditional) **i18n Decisions** · flows in encounter order.

**Hard exclusions govern FLOW BODIES, not lifecycle metadata:** no file paths · no component names · no implementation detail (libraries, endpoints, DB tables) · no literal microcopy · no test names. The **header, R-notes, Contract inputs, and the re-freeze close-out's Downstream impact table are EXEMPT**: their entire job is naming entities, fields, tables, and consumer docs (`docs/data-contract.md`, `docs/ui-design.md`), which the close-out mandates; a reviewer reading the exclusions against those sections is misapplying the law. A flow over 30 lines gets a one-line justification; near 50, split it; the file near 400, propose splitting the feature.

**`[PRIMARY PATH]` counting rule — state it verbatim in the artifact:** *a MARKER is that token labelling a
step sequence inside a flow; every occurrence outside one — this rule, the freeze law, a validation-gate
line, a review ledger — is prose ABOUT the convention and is not counted.*

## Phase 6 — Validation gate, then self-convergence to FROZEN

Walk the gate and resolve gaps in conversation, never hand off with known gaps: every Success Criterion traced to ≥1 flow · every persona's journey complete (entry/actions/feedback/exit/decisions/errors) · every SENDING flow has its RECEIVING persona · every async boundary has its gap state · exactly one `[PRIMARY PATH]` per flow · resilience per external call · contract inputs recorded (never trimmed) · i18n decisions when applicable · hard exclusions honored · length within targets · **life-cycle arcs (UI-bearing types):** the `/fabrik-user-test` Phase-1b set — *first-day · habitual · paying-customer (incl. a VOLUNTARY downgrade/cancel exit, not just involuntary recovery) · leaving-user · recovery (incl. an interrupted-journey resume)* — each applicable arc has entry AND exit legs, or the gap is surfaced.

Then converge: re-walk the whole artifact; fix; repeat until the Termination contract's closing round — `confirmed: 0`, file md5 identical before and after. Set `Status: FROZEN`, bump `Version`.
**The freeze is a Status flip: mint its `docs/DECISIONS.md` row in the same change** (CLAUDE.md § the decision ledger); a re-freeze bump N→N+1 is a NEW row, never an edit to the old one. Classify at mint: a flows freeze is normally reversible-by-re-freeze, so the plain row suffices unless the operator rules otherwise; stage it WITH the artifact in the commit below — same change means same COMMIT, not same run.
**Present the frozen contract + flow index to the user**; the freeze stands unless they redirect. **`FROZEN` is not `attested`:** handing it to `/fabrik-data-contract`, `/fabrik-ui-design`, or a planner before `/fabrik-flows-review` has run is skipping a required gate, not saving a step (§ Next).

**Freeze law (verbatim into the artifact):** *any journey/persona/flow change = bump `Version` +
re-freeze via `/fabrik-flows` (or `/fabrik-flows-review`'s in-review re-freeze, its sanctioned
exception) — never edit in place. Downstream consumers
(`/fabrik-data-contract`, `/fabrik-ui-design`, the certification gauntlets) read the frozen version only.*

Do not commit unless the user says so this turn (`git add` is fine); superseded where it conflicts with CLAUDE.md § EXIT. **Commit** the artifact at its first write, `DRAFT` included, with its `INDEX.md` and `docs/README.md` rows in the same commit: an untracked `docs/` file reds every full (Tier-2) gate run in that checkout, a sibling's included (`check_doc_index.py`: "live doc not in INDEX.md … (untracked — the run that creates a doc owes its INDEX row)"). Committing a `DRAFT`/`FROZEN` artifact is not approving it; its own `Status:` line carries that; the user's word is needed for the APPROVAL and anything beyond this artifact's paths.

{{include:questionbar}}
## Re-freeze close-out (runs ONLY on a version bump N→N+1 of a FROZEN artifact)

A bump leaves every downstream consumer (`flows.md` → `data-contract.md` → `ui-design.md` [→ `design-system.md`]) frozen against a dead version; `check_frozen_chain.py` catches the stale PIN, but only this run holds the diff, so only this run can say what the re-freeze must cover:

1. **Diff the artifact against its pre-run version** (`git diff HEAD -- <artifact>`, or HEAD~1 after committing) and extract the changed entity/column/enum/section names.
2. **Grep each downstream frozen consumer** for them and emit a **Downstream impact** table in the closing report: `changed name → consumer → citing section(s) → verdict (cites it / silent)`. Zero hits is a stated result, never an omitted one.
3. **The NEXT line becomes the owed re-freeze when impact is non-empty**: the consumer's owning command WITH the impact list as arguments (e.g. `NEXT: /fabrik-ui-design — re-freeze v9→v10: projects.domain needs a §5.3 control; §5.11 'unbuildable' passages now stale`), never the first-run pipeline chain line.

## Next — run `/fabrik-flows-review` (the independent pass, before any consumer)

Before `/fabrik-data-contract`, `/fabrik-ui-design`, or any planner consumes it, run **`/fabrik-flows-review`** — the independent, author-blind pass that re-traces every Success Criterion, re-derives SECOND-ACTOR and life-cycle-arc coverage, and converges to its own closing round (`confirmed: 0`, md5 unchanged). **Do NOT let a consumer freeze against a contract the review has not attested**; if the review surfaces something it cannot reconcile, it routes back here; resolve that before the contract is consumed.


{{include:subagents-core}}

{{include:close-chain}}
