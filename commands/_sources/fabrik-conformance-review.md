---
description: Reopen EVERY spec + plan in a project and verify each was actually IMPLEMENTED — inventory → one grounded verifier per spec↔plan pair → five-value verdict → adjudicated ledger. Catches what code review and staleness checks cannot: a CONVERGED-but-stale plan, an implemented-but-INERT surface, a live-SLA broken while code conforms, and spec-refreeze debt. TRIGGER — EN: "was everything we specced actually built", "audit every spec and plan against the code"; TR: "spec'lediklerimiz gerçekten yapıldı mı". SKIP: code defects (→ /fabrik-review, /fabrik-repo-review) · doc/plan STALENESS (→ /fabrik-catchup). Stage: gate.
argument-hint: "[spec/plan subset or era to scope — omit for the whole portfolio]"
---

# /fabrik-conformance-review — did we actually BUILD what we specced?

This gate reopens each finished spec and checks it against the live tree. ONE epic (the argument names its spec) is this same sweep scoped to that epic's spec↔plan pair.

{{include:run-record}}
{{include:orient}}
{{include:term-coverage}}
{{include:grounding-artifact}}

## PHASE 0 — DISCOVER THIS PROJECT'S ARTIFACTS (you, first — assume NOTHING)

Do not hardcode the layout: glob first, then pair, and record what you found, including "this project has no specs".

1. **Enumerate** every spec and plan (active + archived + epics); a plan-set directory is ONE row.
2. **Pair** spec ↔ plan by explicit reference first, then by slug/date proximity. Use `PLANS.md` as an accelerator **when it exists**, never as the mechanism. A plan with no spec gets its OWN row.
3. **Exclude pre-supersession eras explicitly, naming the successor.**
4. **Write the ledger doc NOW, before any verification** — `docs/development/reviews/YYYY-MM-DD-spec-plan-conformance-review.md`.

   It carries FOUR things from the start (the Pass Ledger joins them with the first pass), and `check_review_coverage.py` (via `final_gate` and the Stop hook) reads it — a review that exists only in chat does not exist:
   - a **`Surface:` line** — `git rev-parse HEAD` + a hash of the enumerated inventory; the inventory IS the surface, and re-running against an unchanged one is a re-adjudication, not a fresh sweep.
   - the **Inventory table** — one row per spec↔plan pair (and per spec-less plan), verdict `PENDING`.
   - a **`## Per-phase verdicts` section** — one `### Phase <n> — <title>` heading per PHASE of this command, its outcome written under it once that phase has run; `check_convergence.py` fails a ledger whose Status or text claims a finished review and that has no heading of two or more `#` starting `Phase` or `Step`.
   - the **Coverage Checklist** — one row per FAILURE CLASS, every row starting `UNCHECKED`.

   `check_review_coverage.py` PARSES the checklist, so a checklist that invents its own class list fails the gate:
   * Run `python scripts/review_rubric.py --changed <paths>` over the enumerated artifact paths plus the implementing code paths, and record BOTH: the invocation on a prose `Rubric:` line in INLINE backticks, and the OUTPUT pasted verbatim in a fence. Without the pasted output the gate fails the review with "no pasted review_rubric.py OUTPUT"; the classes derive from the rubric, never from memory.
   * Carry the four STANDING recurrence classes as rows, on top of the rubric's; the gate checks for them by name: `fail-open/fail-closed` · `cost/quota accounting` · `boundary/sentinel/prefix` · `behavior-without-a-test`.
   * Add this command's discriminator rows: `trivially-green test` · `implemented-but-inert` · `live-SLA broken` · `spec-refreeze debt` · `plan CONVERGED but never executed` · `supersession without a named successor`.
   * A `CLEAN` row must NAME the files/paths hunted — a bare "CLEAN" is rejected.
   * Pass Ledger rows are labelled `Pass 1`, `Pass 2`, … and a minimum of TWO rounds always applies: a clean pass 1 still needs its confirming round.

## PHASE 1 — ONE GROUNDED VERIFIER PER PAIR

Dispatch a verifier per row, **batched 2–4 per dispatch**. Each gets ONE brief (every path in it a literal absolute path already substituted, never a `<scratch>` placeholder the seat expands itself) and returns a compact report:

- **Ground each success criterion and behavior contract in the live tree TODAY**: open the file, confirm the symbol / table / column / route / job exists and does what was promised; follow migration renumbering through status notes rather than declaring a renamed migration missing.
- **Spot-RUN 1–2 of the plan's own test files** against a throwaway/ephemeral target. Before the run, print the database or service target the suite's seeder, provisioner or fixtures actually resolve and stop unless it is the throwaway one, and call a run read-only only after reading its shared fixtures for writes.
- **Note supersessions**: a later plan that deliberately replaced the behavior makes it SUPERSEDED, not NOT-IMPLEMENTED, and the successor must be named.
- Report: verdict · gaps as `path:line` · supersessions · evidence including test tails · hard word cap; prose without anchors verifies nothing.

## PHASE 2 — VERIFY / REFUTE (you, the orchestrator — kill the wrong verdicts)

A verifier's verdict is a CLAIM; yours is the record. Refute or downgrade every claim with evidence; distrust a CONFORMS most, because it ends inspection: re-check it against the four discriminators. **Write each adjudicated verdict into the ledger IMMEDIATELY**, row by row, never a final batch.

### The verdict scale (five values, no sixth)

| Verdict | Means |
|---|---|
| **CONFORMS** | every success criterion grounded in the live tree today |
| **PARTIAL** | some criteria met, others provably not — gaps listed with `path:line` |
| **DEVIATES** | built differently on purpose; the deviation is real and defensible |
| **NOT-IMPLEMENTED** | the artifact converged and the behavior does not exist |
| **SUPERSEDED** | later work replaced it — **name the successor** or it is not SUPERSEDED |

### The four discriminators — first-class checks, not nice-to-haves

1. **Trivially-green test** — it injects a shape the real callee can never emit; read what the production caller produces before trusting a green.
2. **Implemented-but-inert** — the artifact has ZERO consumers; grep for readers, not just the definition.
3. **Live-SLA broken** — the code conforms but the RUNNING state does not; check runners, ledgers, schedules and thresholds, not only source.
4. **Spec-refreeze debt** — a deliberate deviation never written back into the spec; the DANGEROUS one, because a future reader "fixing" the code back to the spec reintroduces the very bug the deviation avoided.

## PHASE 3 — PROVE & ROUTE (depth — every surviving row terminates)

This command does NOT fix: a conformance gap is a plan to finish or a spec to re-freeze, so prove, then hand to the owner — an unrouted finding is an unfinished one.

- **Prove each surviving verdict**: the anchor is `path:line` plus a FRESH run, never a green from last week. A row you cannot prove today is PARTIAL, and say why.
- **Cluster** the survivors: never-executed · operational reds · inert surfaces · refreeze debt · supersessions (each successor named).
- **Route each cluster to its owning command** — `/fabrik-execute-plan` for a converged plan never run · `/fabrik-spec` to re-freeze deviation debt · `/fabrik-review` for a code defect · the deploy triad for an operational red. A SUPERSEDED row mints its `docs/DECISIONS.md` row staged in the commit that lands this run's ledger doc (the SAME-change law; a plain row; ONE-WAY — § Binding block — if the successor is already load-bearing); the dispatching session appends, never the verifier. A review that ends in a list nobody owns has not finished.

## PHASE 4 — CONVERGE (the loop — you are here after EVERY pass, not once)

Same termination contract as every review command: **BOTH** a quiet round AND a fully adjudicated checklist.

- **Round shape is discovery-until-dry**, not the diff loop's wide→scoped→wide. Round 1 verifies every inventory row; later rounds re-hunt the CLASSES across rows that already passed — inside the inventory: an instance found outside it is recorded and routed by PHASE 3's table to its owning command (a work item or a mail), never counted toward this run's convergence. The **closing round runs non-author verifiers** on the full inventory.
- **DONE requires all of:** the Termination contract's exit above — the closing round at `confirmed: 0 · fixed: 0 · unexecuted: 0` with every candidate and Checklist row adjudicated, the Pass Ledger in the fragment's grammar with `method: re-derivation` on the closing row — and, host-only, **every Inventory row terminal** (no `PENDING`).
- **DEVIATES rows state whether the spec was re-frozen** — if not, that row IS refreeze debt and belongs in the cluster summary.
- Commit the ledger, route the cluster summary, `final_gate` green; then report.
- **The Evidence bootstrap:** the convergence gate reds a ledger lacking an embedded `final_gate` `"status": "success"` fenced block. So: (1) finish the ledger, (2) embed the block with the EXPECTED green shape, (3) run `python scripts/final_gate.py --check --json`, (4) correct the embedded numbers to the verbatim output and re-run once; the fixpoint (embed == fresh run) is the evidence-true state.
- A routed finding's terminal token is **`ROUTED(n)`**, first-class beside CLEAN/FIXED/REFUTED; never write "FIXED via routing". `n` counts the work items and mails the row's findings were routed to, pre-existing ones included; an operator gate is not a route — that row reads `RECORDED — measured (operator gate: <work item or mail id>)` and is listed in OUTPUT's RESIDUAL — and an id already counted under another class is not counted again.

## OUTPUT

The ledger doc (Surface hash · Inventory table · Per-phase verdicts · Coverage Checklist · Pass Ledger), committed — that FILE is the deliverable, not this chat. In the reply: the verdict distribution; every non-CONFORMS row with its `path:line` gaps; the cluster lists, enumerated from PHASE 3's own list, never a literal restated here — each naming the command it was routed to; and a RESIDUAL list — eras excluded with their successor named, rows not provable today, and spec-refreeze debt the operator must decide.

Scale effort to blast radius: exhaustive on money / auth / data-integrity artifacts, proportionate on low-risk ones — and log anything you skip. When unsure, surface a row as PARTIAL; a wrong CONFORMS ends inspection.

{{include:subagents-core}}

{{include:close-chain}}
