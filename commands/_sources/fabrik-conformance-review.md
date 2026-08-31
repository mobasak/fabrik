---
description: Reopen EVERY spec + plan in a project and verify each was actually IMPLEMENTED — inventory → one grounded verifier per spec↔plan pair → five-value verdict → adjudicated ledger. Catches what code review and staleness checks cannot: a CONVERGED-but-stale plan, an implemented-but-INERT surface, a live-SLA broken while code conforms, and spec-refreeze debt. TRIGGER — EN: "was everything we specced actually built", "audit every spec and plan against the code"; TR: "spec'lediklerimiz gerçekten yapıldı mı". SKIP: code defects (→ /fabrik-review, /fabrik-repo-review) · doc/plan STALENESS (→ /fabrik-catchup) · ONE epic vs its decisions-lock (→ /fab-ettw-08-implementation-validation). Stage: gate.
argument-hint: "[spec/plan subset or era to scope — omit for the whole portfolio]"
---

# /fabrik-conformance-review — did we actually BUILD what we specced?

Every other gate asks whether the code is *good*. This one asks whether it is *what we said it
would be*. Nothing else in the corpus reopens a finished spec and checks it against the live tree:
`/fabrik-review` reads a diff, `/fabrik-repo-review` reads code, `/fabrik-catchup` measures
staleness, and `/fab-ettw-08-implementation-validation` validates ONE epic against its own
decisions-lock. A spec that converged in July and was 60% built is invisible to all of them.

**Methodology origin:** run by hand in trade-intelligence 2026-08-22 over 28 artifacts (commit
`e3b779cc`, ledger `docs/development/reviews/2026-08-22-spec-plan-conformance-review.md`): 13
CONFORMS / 9 PARTIAL / 2 NOT-IMPLEMENTED / 1 superseded-in-part / 1 drifted, ~1,050 plan tests
re-run as evidence. Every discriminator below earned its place by catching something real there.

{{include:run-record}}
{{include:term-coverage}}
{{include:grounding-artifact}}

## PHASE 0 — DISCOVER THIS PROJECT'S ARTIFACTS (you, first — assume NOTHING)

⚠️ **Do not hardcode the layout.** Measured across five live projects 2026-08-23: specs sit at
`docs/superpowers/specs/**` in 4 of 5 (one had none at all); plans at `docs/development/plans/**`
in all 5 but in TWO shapes — flat `YYYY-MM-DD-plan-N-<slug>.md` **and** dated plan-SET directories
(a same-stem spine + `T##<slug>.md` tickets, which are ONE artifact, not N); `PLANS.md` exists in
only **1 of 5**, so pairing must never depend on it; archived plans under `docs/archive/**` exist in
some projects and not others; and only 9 of 22 specs carried a parseable `Status:` line.

So: **glob first, then pair.** Record what you actually found, including "this project has no
specs" — that is a finding, not an error.

1. **Enumerate** every spec and every plan (active + archived + epics if present). A plan-set
   directory counts as ONE row; its tickets are evidence within that row.
2. **Pair** spec ↔ plan by explicit reference first (a plan naming its spec, a spec naming its
   plan), then by slug/date proximity. Use `PLANS.md` as an accelerator **when it exists**, never
   as the mechanism. A plan with no spec gets its OWN row — those were 5 of the 28 in the worked
   example and are not second-class.
3. **Exclude pre-supersession eras explicitly, naming the successor.** An era excluded silently is
   indistinguishable from one that was missed.
4. **Write the ledger doc NOW, before any verification** —
   `docs/development/reviews/YYYY-MM-DD-spec-plan-conformance-review.md`. This is crash-safety, not
   bookkeeping: a portfolio sweep is long enough that context loss mid-run is the expected case, and
   a ledger written at the END is a ledger you write twice.

   It carries THREE things, and the file is read by `check_review_coverage.py` (via `final_gate` and
   the Stop hook) — a review that exists only in chat does not exist:
   - a **`Surface:` line** — `git rev-parse HEAD` + a hash of the enumerated inventory. This surface
     is not a diff, so there is no `git diff | md5sum` to take; the inventory IS the surface, and
     re-running against an unchanged one is a re-adjudication, not a fresh sweep.
   - the **Inventory table** — one row per spec↔plan pair (and per spec-less plan), verdict
     `PENDING`.
   - the **Coverage Checklist** — one row per FAILURE CLASS, every row starting `UNCHECKED`. The
     Inventory answers "which artifacts"; the Checklist answers "which ways they can be wrong" — you
     need both, because a sweep can verify every row and still never have hunted for inertness.

     ⚠️ `check_review_coverage.py` PARSES this file. Its requirements are not stylistic, and a
     checklist that invents its own class list fails the gate:
     * **Run `python scripts/review_rubric.py --changed <paths>` and record the invocation on a
       prose `Rubric:` line using INLINE backticks** — not only inside a fenced block. The gate
       strips fences before it looks, so a rubric recorded only inside a ``` block is invisible to
       it and the review fails with "no review_rubric.py invocation recorded" while the command is
       sitting right there in the file. Paste the OUTPUT in a fence by all means; the invocation
       line must live outside one. The classes derive from the rubric, never from memory. The
       surface is not a diff, so feed it the ENUMERATED artifact paths plus the implementing code
       paths the verifiers will open — the rubric globs by path, so it arms correctly either way.
     * **Carry the four STANDING recurrence classes as rows**, on top of the rubric's:
       `fail-open/fail-closed` · `cost/quota accounting` · `boundary/sentinel/prefix` ·
       `behavior-without-a-test`. The gate checks for these by name.
     * **Then add this command's own discriminator rows**: `trivially-green test` ·
       `implemented-but-inert` · `live-SLA broken` · `spec-refreeze debt` ·
       `plan CONVERGED but never executed` · `supersession without a named successor`.
     * **A `CLEAN` row must NAME the files/paths hunted** — a bare "CLEAN" is rejected.
     * **Pass Ledger rows are labelled `Pass 1`, `Pass 2`, …** and a minimum of TWO rounds always
       applies: a clean pass 1 still needs its confirming round.

## PHASE 1 — ONE GROUNDED VERIFIER PER PAIR

Dispatch a verifier per row, **batched 2–4 per dispatch** (a portfolio has dozens of rows; one
dispatch each wastes wall-clock, one dispatch for all loses per-row grounding).

Each verifier gets ONE brief and returns a compact report:

- Read the spec's **success criteria** and the plan's **behavior contracts** — those, not prose.
- **Ground each one in the live tree TODAY**: open the file, confirm the symbol / table / column /
  route / job actually exists and does what was promised. Follow migration renumbering through
  status notes rather than declaring a renamed migration missing.
- **Spot-RUN 1–2 of the plan's own test files** against a throwaway/ephemeral target. A plan's
  tests are the closest thing to its executable contract, and a stale green is worth nothing.
- **Note supersessions**: a later plan may have deliberately replaced this behavior. That is
  SUPERSEDED, not NOT-IMPLEMENTED, and the successor must be named.
- Report contract: verdict · gaps as `path:line` · supersessions · evidence including test tails ·
  hard word cap. A verifier that returns prose instead of anchors has not verified anything.

## PHASE 2 — VERIFY / REFUTE (you, the orchestrator — kill the wrong verdicts)

A verifier's verdict is a CLAIM; yours is the record. Same position and same job as
`/fabrik-review`'s refute phase — the difference is only what is being refuted: there, a claimed
defect; here, a claimed CONFORMS.

- **Refute or downgrade every claim with evidence.** In the worked example one verifier's verdict
  was overturned by the coder's own verbatim earlier output.
- **A CONFORMS is the claim to distrust most**, because it is the one that ends inspection. Re-check
  it against the four discriminators below before accepting it.
- **Write each adjudicated verdict into the ledger IMMEDIATELY** — row by row, never a final batch.
  Same reason the ledger is written before Phase 1: context loss mid-sweep is the expected case.

### The verdict scale (five values, no sixth)

| Verdict | Means |
|---|---|
| **CONFORMS** | every success criterion grounded in the live tree today |
| **PARTIAL** | some criteria met, others provably not — gaps listed with `path:line` |
| **DEVIATES** | built differently on purpose; the deviation is real and defensible |
| **NOT-IMPLEMENTED** | the artifact converged and the behavior does not exist |
| **SUPERSEDED** | later work replaced it — **name the successor** or it is not SUPERSEDED |

### The four discriminators — first-class checks, not nice-to-haves

Each of these passes an ordinary review. Each was caught by the worked example.

1. **Trivially-green test** — a test that injects a shape the real callee can never emit, so it
   passes while proving nothing. Read what the production caller actually produces before trusting
   any green.
2. **Implemented-but-inert** — the artifact exists and has ZERO consumers: a table nothing reads, a
   column that is permanently NULL, a flag nothing branches on. Grep for readers, not just for the
   definition.
3. **Live-SLA broken** — the code conforms but the RUNNING state does not. Check runners, ledgers,
   schedules and thresholds, not only source. The worked example found a refresh lane whose alarm
   floor equalled its current count, so it could never fire.
4. **Spec-refreeze debt** — a deliberate deviation that was never written back into the spec. Treat
   this as the DANGEROUS one: a future reader "fixing" the code back to the spec reintroduces the
   very bug the deviation avoided. It was an 8-item backlog in the worked example.

## PHASE 3 — PROVE & ROUTE (depth — every surviving row terminates)

`/fabrik-review` fixes what survives refutation. This command does NOT fix: a conformance gap is
almost never a one-line edit, it is a plan to finish or a spec to re-freeze. So the depth phase
here is **prove, then hand to the owner** — and an unrouted finding is an unfinished one.

- **Prove each surviving verdict**: the anchor is `path:line` plus a FRESH run, never a green from
  last week. A row you cannot prove today is PARTIAL, and say why.
- **Cluster** the survivors: never-executed · operational reds · inert surfaces · refreeze debt ·
  supersessions (each successor named).
- **Route each cluster to its owning command** — `/fabrik-execute-plan` for a converged plan never
  run · `/fabrik-spec` to re-freeze deviation debt · `/fabrik-review` for a code defect the sweep
  surfaced · the deploy triad for an operational red · a SUPERSEDED row is a discovered
  retirement/adoption: it mints its `docs/DECISIONS.md` row in the ledger-commit of THIS run (the
  SAME-change law; the dispatching session appends — never the verifier). A conformance review that ends in a list
  nobody owns has not finished.

## PHASE 4 — CONVERGE (the loop — you are here after EVERY pass, not once)

Same termination contract as every other review command, on a non-diff surface: **BOTH** a quiet
round AND a fully adjudicated checklist. One pass over the inventory is a first pass, never the run.

- **Round shape is discovery-until-dry**, like the certification gauntlets — not the diff loop's
  wide→scoped→wide, because there is no diff and `review_rubric.py --changed` has nothing to read.
  Round 1 verifies every inventory row. Later rounds re-hunt the CLASSES: an adjudication that
  downgraded a verifier's CONFORMS is evidence that class was under-hunted, so re-sweep it across
  rows that already passed. The **closing round runs non-author verifiers** on the full inventory.
- **DONE requires all of:** the final round raised **`new: 0`** with every found candidate adjudicated
  (`new:` counts candidates FIRST raised that round: a round raising 3 FRESH candidates and refuting
  all 3 is `new: 3` — not quiet; a round merely RE-RAISING already-adjudicated candidates is `new: 0`
  — quiet, per the corrected exit in the termination contract above); **every Inventory row
  terminal** (no `PENDING`); **every Checklist row adjudicated** `CLEAN` / `FIXED(n)` /
  `REFUTED(n, proof)` with no `UNCHECKED`; and the **Pass Ledger** reproduced with `found:` / `new:` /
  `fixed:` per round, each row naming the verifiers dispatched for THAT round.
- **Every verdict evidence-anchored with FRESH runs.** A green from last week is not evidence —
  re-run it or mark the row PARTIAL and say why.
- **Supersessions name their successor. DEVIATES rows state whether the spec was re-frozen** — if
  not, that row IS refreeze debt and belongs in the cluster summary.
- Ledger committed. Cluster summary routed to owning commands. `final_gate` green. Then report.
- **The Evidence bootstrap (first-run trap, reported live):** the convergence gate reds a ledger
  that lacks an embedded `final_gate` `"status": "success"` fenced block — but the gate cannot go
  green until that block exists. The SEQUENCE, not a paradox: (1) finish the ledger's obligations,
  (2) embed the fenced gate block with the EXPECTED green shape, (3) run
  `python scripts/final_gate.py --check --json` — it now sees the embed and reports the real
  result, (4) correct the embedded numbers to the verbatim output and re-run once; the fixpoint
  (embed == fresh run) is the evidence-true state. A routed finding's terminal token is
  **`ROUTED(n)`** — first-class in the checklist vocabulary alongside CLEAN/FIXED/REFUTED; never
  write "FIXED via routing".

## OUTPUT

The ledger doc (Surface hash · Inventory table · Coverage Checklist · Pass Ledger), committed —
that FILE is the deliverable, not this chat. Then, in the reply: the verdict distribution across
the five values; every non-CONFORMS row with its `path:line` gaps; the four cluster lists
(never-executed · operational reds · inert surfaces · refreeze debt) each naming the command it was
routed to; and an explicit RESIDUAL list — eras deliberately excluded with their successor named,
rows that could not be proven today and why, and any spec-refreeze debt the operator must decide on
rather than an agent.

Scale effort to blast radius: exhaustive on money / auth / data-integrity artifacts, proportionate
on low-risk ones — and log anything you deliberately skip. When unsure whether a row conforms,
surface it as PARTIAL; a wrong CONFORMS is the one verdict that ends inspection.

{{include:subagents-core}}
