---
description: Converge a FROZEN docs/flows.md to a fixed point — an INDEPENDENT author-blind adversarial review (Success-Criterion tracing, persona completeness, SECOND-ACTOR completeness, async-boundary gap states, one [PRIMARY PATH] per flow, per-call resilience, contract-input routing) → an edit-free md5-verified no-op. Distinct from /fabrik-flows (author self-convergence; this is the INDEPENDENT pass AFTER it), /fabrik-ui-design-review (the screen contract), and /fabrik-workflow-review (epic-route artifacts). TRIGGER — EN: "review/harden the flows contract", "are the journeys complete", "did we walk every persona"; TR: "akış sözleşmesini gözden geçir", "yolculuklar eksiksiz mi" — fires on a FROZEN flows contract, never a rendered UI (→ /design-review) or a plan (→ /fabrik-plan-review). Stage: 2-contract.
argument-hint: "[path to docs/flows.md — omit to use the current project's frozen journey contract]"
---

Converge this journey contract to a fixed point — do not stop after one pass. **Fixed point = a full review
round that needs no edits.** This is to `/fabrik-flows` what `/fabrik-spec-review` is to `/fabrik-spec`: the
adversarial, INDEPENDENT hardening of an artifact its author already self-converged — the author's pass
cannot see its own blind spots; this one can (the live lesson: a journey gap survived TWO frozen,
convergence-verified artifact versions because every verifying pass was run by the artifact's own author).
The defects a flows contract hides — and the ones this pass exists to catch — are **(1) a flow that SENDS
something whose RECEIVING persona was never walked** (the invite that could be sent but never accepted),
**(2) an async boundary with no gap state** (what the persona sees between checkout return and webhook
landing), and **(3) a Success Criterion no journey covers — or a journey serving no criterion.** All are
invisible until a non-author re-walks the journeys against the spec.

{{include:run-record}}
{{include:term-edit}}
(After the no-op: the approval gate at the end.)

{{include:grounding-artifact}}
- Also read `docs/data-contract.md` IF it already exists — a journey implying an entity/field the contract
  lacks routes to **"contract bump needed"** (consumed by `/fabrik-data-contract`), never silently absorbed
  here and never trimmed from the journey.

## Phase 0 — Establish scope

The contract under review is `$ARGUMENTS` (if empty, the current project's `docs/flows.md` — locate it and
state which file + its `Type:` and `Journey kinds:` header values). **It MUST be `Status: FROZEN`** — still
`DRAFT` → stop and route back to `/fabrik-flows` (you review a frozen artifact, you don't finish its
authoring). Scope = every persona, every flow, every decision point and gap state, checked against its
binding sources, all read THIS session:
- the **CONVERGED `/fabrik-spec` design doc** (+ its Success Criteria list — the tracing spine),
- **`project.yaml::type`** (the journey kind must match: user / consumer / reader; two-faced types carry
  BOTH client and backend journeys),
- the **surface pack** for UI-bearing types and any **domain pack** the flows touch (auth · payments ·
  multi-tenant) — a pack rule a flow violates: the pack wins,
- `ocoron-design-system.md` § Verbal Identity + § States (UI types — hot-spots and state flags speak its
  language).

## Phase 1 — Adversarial grounding to a fixed point (a class ledger, re-swept per round)

Treat every flow as unproven until re-walked. Run repeated passes until one demonstrably-thorough pass finds
zero new gaps; the class ledger below persists across rounds — a round re-sweeps it, never re-scopes it.
With more than a handful of flows, `fanout` one INDEPENDENT grounder per axis (recipe in § Subagents), then
merge + **REFUTE** what you can disprove (quote the flow line / spec line / pack rule) before editing.

**A) Success-Criterion tracing (both directions).** Every criterion → ≥1 covering flow; every flow → ≥1
criterion. A criterion with no journey is missing product; a journey with no criterion is scope creep or a
missing criterion — resolve which.

**B) Persona completeness.** **The DENOMINATOR is the spec's `## Personas` section — open it and
diff:** every persona it enumerates is walked in flows.md or explicitly OUT with a reason; a
silently missing persona is a blocking gap (operator law 2026-08-29). **RE-COUNT the primary
persona's path against the spec's frozen STEP BUDGET yourself** — the author's count is a claim,
and a breach is a finding against whichever contract is wrong. Then the per-journey floor: every
persona's journey has entry → actions → feedback → exit, decision
points, and error paths. No persona exits into the void ("then they're done" with no confirmed end state).

**C) SECOND-ACTOR completeness.** For every flow that sends/emits anything (email, invite, webhook,
notification, export), the receiving persona's journey exists and starts from the RECEIVER'S real context
(no session, other tenant, mail client, webhook consumer). This is the highest-yield axis — walk it first.

**D) Async-boundary gap states.** Every out-of-band round-trip names what the persona sees between the two
legs. "The webhook updates the status" is the system's view; the axis demands the PERSONA'S view of the gap.

**E) `[PRIMARY PATH]` + resilience.** Exactly ONE `[PRIMARY PATH]` per flow (zero or two is a defect — it is
the certification DEPTH input, the journey exercised deeply, never the denominator: the gauntlets resolve
that from a live registry). **Count MARKERS, not the token:** only an occurrence labelling a step sequence
inside a flow counts; the artifact's own counting rule, the freeze law, a gate line and your own ledger all
match a naive grep and are prose. Miscounting here manufactures a defect that is not there — it already has,
in a checker, mid-run, and in a review. Per-external-call resilience present (slow AND down, persona's view).

**E2) Life-cycle arc coverage (UI-bearing types).** Re-derive the `/fabrik-user-test` Phase-1b arc set
independently — *first-day · habitual · paying-customer · leaving-user · recovery* — and check each
applicable arc has BOTH legs: an entry AND a deliberate exit (paying-customer needs a VOLUNTARY
downgrade/cancel, not just involuntary payment-failure recovery; recovery needs the interrupted-journey
resume, not just abandoned checkout). This axis exists because the arc set is an AUTHORING instruction in
another command and nothing in the flows gate re-derived it: two honest md5-verified convergence loops
missed two arc holes that one operator sentence caught (transdoc, 2026-08-27).

**F) Discipline + exclusions.** Microcopy Hot-Spots are outcomes, never literal strings · i18n decisions
present when the project declares i18n · **the hard exclusions (no file paths / component names /
implementation detail) govern FLOW BODIES only** — the header, R-notes, Contract inputs and the re-freeze
close-out's Downstream impact table are lifecycle metadata whose entire job is naming entities, fields and
consumer docs, and axis G below REQUIRES exactly that; raising them under F contradicts G in the same pass ·
**per-flow length asserted against the NUMBERS, not "within targets"** — `/fabrik-flows` sets
**target ≤30 lines, HARD SPLIT at 50** (`fabrik-flows.md` § Phase 5 — the per-flow length target and its `Length discipline:` clause; grep `hard split at 50` — line anchors drift): a flow over **30** owes a
one-line justification; a flow at or over **50** is a DEFECT — split it. State the count you measured per
flow. ⚠️ **"within targets" was the whole problem**: it named no number, so a closing round that
re-derives "lengths OK" is not mechanical — the reviewer picks which reading to check against and can
defend any of them. Measured live (transdoc `01M14Y90D0`): flows at **83** and **53** lines passed
unremarked through a closing round, and 83 violates even the most lenient reading. A gate whose numbers
are re-derived per reviewer is an advisory wearing a gate's clothes · Mermaid only where genuinely
multi-party.

**G) Cross-artifact truth.** No flow contradicts the spec (spot-check the spec's INTENT — the written spec
can itself be wrong; surface, don't silently pick a side). The **Contract inputs** section lists every
entity/field/state the journeys imply — an implied field missing from that list is a finding; an existing
`docs/data-contract.md` lacking a listed input routes to **"contract bump needed."**

After each pass, list what you re-walked (which flows, which criteria, which packs) and what you found, then
fix the contract. **The loop terminates ONLY when a full, demonstrably-thorough pass makes ZERO edits** — a
no-op round is the only proof. The pass that fixed anything is never the last; run one more. A pass finding
nothing must still enumerate its coverage.

## Phase 2 — Handoff-readiness (the downstream consumers must not invent)

Reviewed means consumable as-is:
- **`/fabrik-data-contract`** can freeze fields from the Contract inputs section without re-deriving
  journeys.
- **`/fabrik-ui-design`** (GUI types) can design screens knowing every surface a journey lands on — a
  journey step landing on an undesignable "somewhere" is not handoff-ready.
- **`/fabrik-user-test` / `/fabrik-service-test`** can read the `[PRIMARY PATH]` set as the journeys owed
  DEPTH without inventing them at gauntlet time — their coverage DENOMINATOR comes from a live registry, and
  a cert board sourced from a doc is a finding their own grader raises.
- **The freeze is real:** `Status: FROZEN` + `Version` + `Date` + `Type` + `Journey kinds` header set; the
  verbatim freeze law present.

## Convergence & residuals

Do not promise "100% coverage" — iterate to the fixed point, then enumerate residual unknowns/assumptions,
separating **resolved** from **still-open** (each open one with a named resolution step). **Convergence = a
full review round (all axes + merge/refute) that produced ZERO edits**, md5-verified (hash before/after the
closing round — identical hashes are the proof). Your say-so does not substitute.

- **Clean no-op:** the FROZEN contract stands. Add the attestation to its header —
  `Independently reviewed: v<N> — /fabrik-flows-review no-op <YYYY-MM-DD>` — and report the Pass Ledger.
- **You edited the contract:** editing a FROZEN artifact re-opens it — bump `Version`, re-freeze (the
  edit-free confirming round IS the re-freeze convergence). The bump is a Status-flip event: **mint its
  `docs/DECISIONS.md` row staged in the same commit as the artifact** (the `/fabrik-flows` freeze law;
  classify at mint — plain row normally). Only then attest.
- **A BLOCKING gap remains** (a criterion with no resolvable journey; a second actor whose journey cannot
  be designed without a product decision): stop, set `Status: DRAFT`, name the blocker, route to
  `/fabrik-flows`. The FROZEN→DRAFT flip is a Status flip — **mint its `docs/DECISIONS.md` row in the
  same commit** (it reverses a readiness claim consumers may have acted on; classify at mint). Do NOT attest. **Close the run record on this path** — `blocked --command fabrik-flows-review --reason "<the gap · what you searched · what is missing>" --feedback "<...>"`; "stop" alone leaves the record `running`, which the Stop hook blocks the turn on, and this disposition is the one that most looks like simply stopping.

⚠️ **The attestation IS graded — since 2026-08-29, by `check_frozen_chain.py`.** It compares the NEWEST
`Independently reviewed: v<N>` against the contract's current `Version:` and WARNs when the contract has
moved past its last author-blind pass (`docs/x.md: newest independent review attests v6 but the contract
is at v11 — 5 version(s) have had no author-blind pass`). A history of rounds is correct and is not drift
— only the newest entry is graded — and a contract with NO attestation is silent, since most have never
had a twin run.

**What is still NOT graded:** whether the round you attest actually happened, or was thorough. The check
proves the claim is CURRENT, not that it is TRUE. Ledger honesty is still on you.

**The measurement that nearly buried this, recorded because the error is instructive.** This section
previously said a grader would "police a population of two and fire on none", and deferred it on that
basis. The count came from a regex requiring `reviewed: v` adjacently — which silently missed
`**Independently reviewed:** v2` and `**Independently reviewed:** **v6`, the two shapes the corpus
actually writes. The real numbers: **7 contracts carry an attestation and 6 were STALE**, by 1 to 5
versions. A measurement that under-counts looks exactly like a measurement that found nothing, and it
was used to justify not building the thing that would have caught it.

**Do not commit** unless the user says so this turn (`git add` is fine). ⚠️ **Superseded where it conflicts with CLAUDE.md § EXIT:** an uncommitted artifact is an UNFINISHED task and the Stop hook BLOCKS the turn on it (causes 2 and 3), so "do not commit" and "commit your own work NOW" cannot both be obeyed. **COMMIT the artifact** — on a shared tree parked WIP is the only work that can be silently destroyed, and committing a `DRAFT`/`FROZEN` artifact is not approving it; its own `Status:` line carries that. What still needs the user's word is the APPROVAL and anything beyond this artifact's own paths (trade-intelligence, 2026-08-28).

## After the attestation — STOP and ask for the user's approval (do NOT auto-chain)

Like its siblings, this is a **design approval gate**: the frozen journeys commit every downstream stage to
serve them. Once the edit-free no-op earns the attestation, **present** the contract + the flow index + any
"contract bump needed" findings + the full Pass Ledger, and **STOP — ask the user to approve the journeys.**
Name the successor without invoking it: `/fabrik-data-contract` — freeze the fields the journeys surfaced
(the Contract inputs section is its evidence list). Only on the user's explicit approval does it run; on
requested changes, re-open the loop. Never hand off on an unattested / `DRAFT` contract.

{{include:subagents-core}}
