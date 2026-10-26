---
description: Converge a FROZEN docs/flows.md to a fixed point — an author-blind adversarial review (Success-Criterion tracing, persona completeness, SECOND-ACTOR completeness, async-boundary gap states, one [PRIMARY PATH] per flow, per-call resilience, life-cycle arcs (UI types), discipline + exclusions, cross-artifact truth) → an edit-free md5-verified no-op. Distinct from /fabrik-flows (author self-convergence; this runs after it), /fabrik-ui-design-review (the screen contract), and /fabrik-workflow-review (epic-route artifacts). TRIGGER — EN: "review/harden the flows contract", "are the journeys complete", "did we walk every persona"; TR: "akış sözleşmesini gözden geçir", "yolculuklar eksiksiz mi" — fires on a FROZEN flows contract, never a rendered UI (→ /design-review) or a plan (→ /fabrik-plan-review). Stage: 2-contract.
argument-hint: "[path to docs/flows.md — omit to use the current project's frozen journey contract]"
---

Converge this journey contract to a fixed point — do not stop after one pass. **Fixed point = a full review
round that CONFIRMS zero.** The author's pass cannot see its own blind spots; this one can.
The defects a flows contract hides are **(1) a flow that SENDS
something whose RECEIVING persona was never walked** (the invite that could be sent but never accepted),
**(2) an async boundary with no gap state** (what the persona sees between checkout return and webhook
landing), and **(3) a Success Criterion no journey covers — or a journey serving no criterion.** All are
invisible until a non-author re-walks the journeys against the spec.

{{include:run-record}}
{{include:orient}}
{{include:term-edit}}

{{include:grounding-artifact}}
- Also read `docs/data-contract.md` IF it already exists — a journey implying an entity/field the contract
  lacks routes to **"contract bump needed"** (consumed by `/fabrik-data-contract`), never silently absorbed
  here and never trimmed from the journey.

## Phase 0 — Establish scope

The contract under review is `$ARGUMENTS` (if empty, the current project's `docs/flows.md` — locate it and
state which file + its `Type:` and `Journey kinds:` header values). **It MUST be `Status: FROZEN`** — still
`DRAFT` → stop and route back to `/fabrik-flows`. Scope = every persona, every flow, every decision point and
gap state, against binding sources read THIS session:
- the **CONVERGED `/fabrik-spec` design doc** (+ its Success Criteria list),
- **`project.yaml::type`** (the journey kind must match: user / consumer / reader; two-faced types carry
  BOTH client and backend journeys),
- the **surface pack** for UI-bearing types and any **domain pack** the flows touch — a pack rule a flow violates: the pack wins,
- `design-system-template.md` § States (Enriched) + the resolved brand's voice (`docs/design-system.md` § Voice;
  ocoron: `ocoron-design-system.md` § Verbal Identity) (UI types).

## Phase 1 — Adversarial grounding to a fixed point (a class ledger, re-swept per round)

Treat every flow as unproven until re-walked. Run repeated passes until one demonstrably-thorough pass finds
zero new gaps; the class ledger below persists across rounds — a round re-sweeps it, never re-scopes it.
Dispatch one INDEPENDENT native seat per axis, every round (recipe in § Subagents: `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units 8 --mechanical 2 --risky 2` — one unit per axis A–G plus E2; `--units 7` when E2 does not apply; risky units C and D take the Opus seats; axes E (marker count) and F (line count) are the grep-able ones). **Never solo, never two:** a surface with fewer than three units still dispatches **THREE seats on DIFFERENT angles** over it.
Then merge + **REFUTE** what you can disprove (quote the flow line / spec line / pack rule) before editing.

**A) Success-Criterion tracing (both directions).** Every criterion → ≥1 covering flow; every flow → ≥1
criterion. A criterion with no journey is missing product; a journey with no criterion is scope creep or a
missing criterion — resolve which.

**B) Persona completeness.** **The DENOMINATOR is the spec's `## Personas` section — open it and
diff:** every persona it enumerates is walked in flows.md or explicitly OUT with a reason; a
silently missing persona is a blocking gap (operator law 2026-08-29). **RE-COUNT the primary
persona's path against the spec's frozen STEP BUDGET yourself** — the author's count is a claim,
and a breach is a finding against whichever contract is wrong. Then the per-journey floor: every
persona's journey has entry → actions → feedback → exit, decision
points, and error paths. No persona exits into the void ("then they're done").

**C) SECOND-ACTOR completeness.** For every flow that sends/emits anything, the receiving persona's journey
exists and starts from the RECEIVER'S real context. This is the highest-yield axis — walk it first.

**D) Async-boundary gap states.** Every out-of-band round-trip names what the persona sees between the two
legs. The axis demands the PERSONA'S view of the gap.

**E) `[PRIMARY PATH]` + resilience.** Exactly ONE `[PRIMARY PATH]` per flow (zero or two is a defect — it is
the certification DEPTH input, never the denominator: the gauntlets resolve
that from a live registry). **Count MARKERS, not the token:** only an occurrence labelling a step sequence
inside a flow counts; the artifact's own counting rule, the freeze law, a gate line and your own ledger are prose. Per-external-call resilience present (slow AND down, persona's view).

**E2) Life-cycle arc coverage (UI-bearing types).** Re-derive the `/fabrik-user-test` Phase-1b arc set
independently — *first-day · habitual · paying-customer · leaving-user · recovery* — and check each
applicable arc has BOTH legs: an entry AND a deliberate exit (paying-customer needs a VOLUNTARY
downgrade/cancel; recovery needs the interrupted-journey resume).

**F) Discipline + exclusions.** Microcopy Hot-Spots are outcomes, never literal strings · i18n decisions
present when the project declares i18n · **the hard exclusions (no file paths / component names /
implementation detail) govern FLOW BODIES only** — the header, R-notes, Contract inputs and the re-freeze
close-out's Downstream impact table are lifecycle metadata whose entire job is naming entities, fields and
consumer docs, and axis G below REQUIRES exactly that; raising them under F contradicts G in the same pass ·
**per-flow length asserted against the NUMBERS, not "within targets"** — `/fabrik-flows` sets
**target ≤30 lines, HARD SPLIT at 50** (`fabrik-flows.md` § Phase 5 — the per-flow length target and its `Length discipline:` clause; grep `hard split at 50` — line anchors drift): a flow over **30** owes a
one-line justification; a flow at or over **50** is a DEFECT — split it. State the count you measured per
flow. A gate whose numbers are re-derived per reviewer is an advisory wearing a gate's clothes · Mermaid only where genuinely
multi-party.

**G) Cross-artifact truth.** No flow contradicts the spec (spot-check the spec's INTENT; surface, don't silently pick a side). The **Contract inputs** section lists every
entity/field/state the journeys imply — an implied field missing from that list is a finding; an existing
`docs/data-contract.md` lacking a listed input routes to **"contract bump needed."**

After each pass, list what you re-walked (which flows, which criteria, which packs) and what you found, then
fix the contract. **The loop terminates ONLY when a full, demonstrably-thorough pass CONFIRMS zero (the Termination contract's closing round, md5 unchanged)** — that
closing round is the only proof. The pass that fixed anything is never the last; run one more. A pass finding
nothing must still enumerate its coverage.

## Phase 2 — Handoff-readiness (the downstream consumers must not invent)

Reviewed means consumable as-is:
- **`/fabrik-data-contract`** can freeze fields from the Contract inputs section without re-deriving
  journeys.
- **`/fabrik-ui-design`** (GUI types) can design screens knowing every surface a journey lands on — a
  journey step landing on an undesignable "somewhere" is not handoff-ready.
- **`/fabrik-user-test` / `/fabrik-service-test`** can read the `[PRIMARY PATH]` set as the journeys owed
  DEPTH without inventing them at gauntlet time — their coverage DENOMINATOR comes from a live registry, and
  a cert board sourced from a doc is a finding.
- **The freeze is real:** `Status: FROZEN` + `Version` + `Date` + `Type` + `Journey kinds` header set; the
  verbatim freeze law present.

## Convergence & residuals

Do not promise "100% coverage" — iterate to the fixed point, then enumerate residual unknowns/assumptions,
separating **resolved** from **still-open** (each open one with a named resolution step). **Convergence = a
full review round (all axes + merge/refute) at `confirmed: 0` — the Termination contract's closing round**, md5-verified (hash before/after the
closing round — identical hashes are the proof). Your say-so does not substitute.

- **Closing round at `confirmed: 0`:** the FROZEN contract stands. Add the attestation to its header —
  `Independently reviewed: v<N> — /fabrik-flows-review confirmed: 0 <YYYY-MM-DD>` — and report the Pass Ledger.
- **You edited the contract:** editing a FROZEN artifact re-opens it — the run's first edit bumps `Version`, every later edit
  stays under that version, and the closing round re-freezes it:
  one bump and one row per review run, a run closed `blocked` and resumed included, never a bump per round. The bump is a Status-flip event: **mint its
  `docs/DECISIONS.md` row staged in the same commit as the artifact** (the `/fabrik-flows` freeze law; classify at mint — plain row normally).
  Only then attest.
- **A BLOCKING gap remains** (a criterion with no resolvable journey; a second actor whose journey cannot
  be designed without a product decision): stop, set `Status: DRAFT`, name the blocker, route to
  `/fabrik-flows`. The FROZEN→DRAFT flip is a Status flip — **mint its `docs/DECISIONS.md` row in the
  same commit** (it reverses a readiness claim consumers may have acted on; classify at mint). Do NOT attest. **Close the run record on this path** — `blocked --command fabrik-flows-review --reason "<the gap · what you searched · what is missing>" --feedback "<...>"`; "stop" alone leaves the record `running`, which the Stop hook blocks the turn on.

`check_frozen_chain.py` grades the attestation (since 2026-08-29): it compares the newest `Independently reviewed: v<N>` against the contract's current `Version:` and WARNs when it is older (`docs/x.md: newest independent review attests v6 but the contract is at v11 — 5 version(s) have had no author-blind pass`). A history of rounds is correct and is not drift
— only the newest entry is graded — and a contract with NO attestation is silent, since most have never
had a twin run. It proves the claim is CURRENT, not that it is TRUE — ledger honesty is still on you.

**Do not commit** unless the user says so this turn (`git add` is fine). ⚠️ **Superseded where it conflicts with CLAUDE.md § EXIT:** an uncommitted artifact is an UNFINISHED task and the Stop hook BLOCKS the turn on it (causes 2 and 3), so **COMMIT the artifact** — on a shared tree parked WIP is the only work that can be silently destroyed, and committing a `DRAFT`/`FROZEN` artifact is not approving it; its own `Status:` line carries that. What still needs the user's word is the APPROVAL and anything beyond this artifact's own paths (2026-08-28).

## After the attestation — the panel answers the journey-freeze gate

Like its siblings, this is a **design approval gate**: the frozen journeys commit every downstream stage to serve them. Once the closing round (`confirmed: 0`) earns the attestation, the panel answers it; its brief
carries the contract, the flow index and any "contract bump needed" findings.

{{include:design-critique}}

{{include:design-gate-panel}}

On a split, end the turn with this block, written as plain lines, not inside a code fence:

```
DECISION NEEDED (ground: gate)
- Question: Do you approve these frozen journeys?
- Why it is yours: journey-freeze approval of <docs/flows.md path> — the design approval gate every downstream stage builds on; the panel split.
- Options: A — approve as frozen, and `/fabrik-data-contract` freezes the fields the journeys surfaced · B — take the disputed changes, and the loop re-opens on them.
- Recommendation: <A or B>, with the one disputed concern that decides it.
- Panel: opus="<its VERDICT line>" fable="<its VERDICT line>" → split
```

The next command is `/fabrik-data-contract` — freeze the fields the journeys surfaced (the Contract inputs
section is its evidence list). On a split, the operator's answer decides; on requested changes, re-open the
loop. Never hand off on an unattested / `DRAFT` contract.


{{include:subagents-core}}

{{include:close-chain}}
