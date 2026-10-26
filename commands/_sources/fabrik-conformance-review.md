---
description: Reopen EVERY spec + plan in a project and verify each was actually IMPLEMENTED — inventory → one grounded verifier per spec↔plan pair → five-value verdict → adjudicated ledger. Catches what code review and staleness checks cannot: a CONVERGED-but-stale plan, an implemented-but-INERT surface, a live-SLA broken while code conforms, and spec-refreeze debt. TRIGGER — EN: "was everything we specced actually built", "audit every spec and plan against the code"; TR: "spec'lediklerimiz gerçekten yapıldı mı". SKIP: code defects (→ /fabrik-review, /fabrik-repo-review) · doc/plan STALENESS (→ /fabrik-catchup). Stage: gate.
argument-hint: "[spec/plan subset or era to scope — omit for the whole portfolio]"
---

# /fabrik-conformance-review — did we actually BUILD what we specced?

This gate reopens each finished spec and checks it against the live tree. ONE epic (the argument names its spec) is this same sweep scoped to that epic's spec↔plan pair, with `/fabrik-review` on the diffs it finds wanting — the corpus has no separate per-epic validator. Methodology origin: run by hand in trade-intelligence 2026-08-22 over 28 artifacts (commit `e3b779cc`, ledger `docs/development/reviews/2026-08-22-spec-plan-conformance-review.md`): 13 CONFORMS · 9 PARTIAL · 2 NOT-IMPLEMENTED · 1 drain-list · 1 superseded-in-part · 2 doc-stale-only (the ledger's own six-way summary line, verbatim — a re-bucketed restatement here went stale), ~1,050 plan tests re-run as evidence.

{{include:run-record}}
{{include:orient}}
{{include:term-coverage}}
{{include:grounding-artifact}}

## PHASE 0 — DISCOVER THIS PROJECT'S ARTIFACTS (you, first — assume NOTHING)

Do not hardcode the layout: glob first, then pair. Specs sit at `docs/superpowers/specs/**`; plans at `docs/development/plans/**` in two shapes — flat `YYYY-MM-DD-plan-N-<slug>.md` and dated plan-SET directories (a same-stem spine + `T##<slug>.md` tickets, ONE artifact, not N); archived plans under `docs/archive/**`; `PLANS.md` exists in only 1 of 5, so pairing must never depend on it; archived plans under `docs/archive/**` exist in some projects and not others; and only 9 of 22 specs carried a parseable `Status:` line. Record what you found, including "this project has no specs" — that is a finding, not an error.

1. **Enumerate** every spec and every plan (active + archived + epics if present). A plan-set directory counts as ONE row; its tickets are evidence within that row.
2. **Pair** spec ↔ plan by explicit reference first (a plan naming its spec, a spec naming its plan), then by slug/date proximity. Use `PLANS.md` as an accelerator **when it exists**, never as the mechanism. A plan with no spec gets its OWN row, and is not second-class.
3. **Exclude pre-supersession eras explicitly, naming the successor.**
4. **Write the ledger doc NOW, before any verification** — `docs/development/reviews/YYYY-MM-DD-spec-plan-conformance-review.md`.

   It carries FOUR things from the start (the Pass Ledger joins them with the first pass), and `check_review_coverage.py` (via `final_gate` and the Stop hook) reads it — a review that exists only in chat does not exist:
   - a **`Surface:` line** — `git rev-parse HEAD` + a hash of the enumerated inventory; this surface is not a diff, so there is no `git diff | md5sum` to take; the inventory IS the surface, and re-running against an unchanged one is a re-adjudication, not a fresh sweep.
   - the **Inventory table** — one row per spec↔plan pair (and per spec-less plan), verdict `PENDING`.
   - a **`## Per-phase verdicts` section** — one `### Phase <n> — <title>` heading per PHASE of this command, its outcome written under it once that phase has run; `check_convergence.py` fails a ledger whose Status or text claims a finished review and that has no heading of two or more `#` starting `Phase` or `Step` ("no per-phase verdict").
   - the **Coverage Checklist** — one row per FAILURE CLASS, every row starting `UNCHECKED`.

   The Inventory answers "which artifacts"; the Checklist answers "which ways they can be wrong" — you need both, because a sweep can verify every row and still never have hunted for inertness.

   `check_review_coverage.py` PARSES this file, so a checklist that invents its own class list fails the gate:
   * Run `python scripts/review_rubric.py --changed <paths>` and record BOTH: the invocation on a prose `Rubric:` line in INLINE backticks, and the OUTPUT pasted verbatim in a fence. The gate (`check_review_coverage.py`'s `RUBRIC_RUN`) reads the pasted output's generated header (its `# REVIEW RUBRIC` line, which names the script that printed it), fenced or not, and fails the review with "no pasted review_rubric.py OUTPUT" without it; the invocation line is what lets a reader re-run it. The classes derive from the rubric, never from memory. The surface is not a diff, so feed it the ENUMERATED artifact paths plus the implementing code paths the verifiers will open — the rubric globs by path, so it arms correctly either way.
   * Carry the four STANDING recurrence classes as rows, on top of the rubric's; the gate checks for them by name: `fail-open/fail-closed` · `cost/quota accounting` · `boundary/sentinel/prefix` · `behavior-without-a-test`.
   * Add this command's discriminator rows: `trivially-green test` · `implemented-but-inert` · `live-SLA broken` · `spec-refreeze debt` · `plan CONVERGED but never executed` · `supersession without a named successor`.
   * A `CLEAN` row must NAME the files/paths hunted — a bare "CLEAN" is rejected.
   * Pass Ledger rows are labelled `Pass 1`, `Pass 2`, … and a minimum of TWO rounds always applies: a clean pass 1 still needs its confirming round.

## PHASE 1 — ONE GROUNDED VERIFIER PER PAIR

Dispatch a verifier per row, **batched 2–4 per dispatch** (a portfolio has dozens of rows; one dispatch each wastes wall-clock, one dispatch for all loses per-row grounding). Each verifier gets ONE brief (every path in it — the seat's scratch dir, an archive when one is used — a literal absolute path already substituted, never a `<scratch>` placeholder the seat expands itself) and returns a compact report:

- **Read the spec's success criteria and the plan's behavior contracts — those, not prose — and ground each in the live tree TODAY**: open the file, confirm the symbol / table / column / route / job actually exists and does what was promised; follow migration renumbering through status notes rather than declaring a renamed migration missing.
- **Spot-RUN 1–2 of the plan's own test files** against a throwaway/ephemeral target. Before the run, print the database or service target the suite's seeder, provisioner or fixtures actually resolve and stop unless it is the throwaway one — a hardcoded name ignores the throwaway target and silently hits the shared one — and call a run read-only only after reading its shared fixtures for writes (a fixture that deletes rows makes every test using it a write).
- **Note supersessions**: a later plan that deliberately replaced the behavior makes it SUPERSEDED, not NOT-IMPLEMENTED, and the successor must be named.
- Report: verdict · gaps as `path:line` · supersessions · evidence including test tails · hard word cap. A verifier that returns prose instead of anchors has not verified anything.

## PHASE 2 — VERIFY / REFUTE (you, the orchestrator — kill the wrong verdicts)

A verifier's verdict is a CLAIM; yours is the record. Same position and same job as `/fabrik-review`'s refute phase — the difference is only what is being refuted: there, a claimed defect; here, a claimed CONFORMS. Refute or downgrade every claim with evidence; distrust a CONFORMS most, because it ends inspection: re-check it against the four discriminators below before accepting it. **Write each adjudicated verdict into the ledger IMMEDIATELY**, row by row, never a final batch.

### The verdict scale (five values, no sixth)

| Verdict | Means |
|---|---|
| **CONFORMS** | every success criterion grounded in the live tree today |
| **PARTIAL** | some criteria met, others provably not — gaps listed with `path:line` |
| **DEVIATES** | built differently on purpose; the deviation is real and defensible |
| **NOT-IMPLEMENTED** | the artifact converged and the behavior does not exist |
| **SUPERSEDED** | later work replaced it — **name the successor** or it is not SUPERSEDED |

### The four discriminators — first-class checks, not nice-to-haves

1. **Trivially-green test** — a test that injects a shape the real callee can never emit, so it passes while proving nothing; read what the production caller produces before trusting any green.
2. **Implemented-but-inert** — the artifact exists and has ZERO consumers: a table nothing reads, a column that is permanently NULL, a flag nothing branches on; grep for readers, not just the definition.
3. **Live-SLA broken** — the code conforms but the RUNNING state does not; check runners, ledgers, schedules and thresholds, not only source. The worked example found a refresh lane whose alarm floor equalled its current count, so it could never fire.
4. **Spec-refreeze debt** — a deliberate deviation never written back into the spec; treat this as the DANGEROUS one, because a future reader "fixing" the code back to the spec reintroduces the very bug the deviation avoided.

## PHASE 3 — PROVE & ROUTE (depth — every surviving row terminates)

`/fabrik-review` fixes what survives refutation. This command does NOT fix: a conformance gap is almost never a one-line edit, it is a plan to finish or a spec to re-freeze. So the depth phase here is prove, then hand to the owner — and an unrouted finding is an unfinished one.

- **Prove each surviving verdict**: the anchor is `path:line` plus a FRESH run, never a green from last week. A row you cannot prove today is PARTIAL, and say why.
- **Cluster** the survivors: never-executed · operational reds · inert surfaces · refreeze debt · supersessions (each successor named).
- **Route each cluster to its owning command** — `/fabrik-execute-plan` for a converged plan never run · `/fabrik-spec` to re-freeze deviation debt · `/fabrik-review` for a code defect the sweep surfaced · the deploy triad for an operational red · a SUPERSEDED row is a discovered retirement/adoption: it mints its `docs/DECISIONS.md` row staged in the commit that lands this run's conformance ledger doc, classified at mint (a discovered retirement is normally a plain row; ONE-WAY — § Binding block — if the successor is already load-bearing) (the SAME-change law; the dispatching session appends — never the verifier). A review that ends in a list nobody owns has not finished.

## PHASE 4 — CONVERGE (the loop — you are here after EVERY pass, not once)

Same termination contract as every review command, on a non-diff surface: **BOTH** a quiet round AND a fully adjudicated checklist. One pass over the inventory is a first pass, never the run.

- **Round shape is discovery-until-dry**, like the certification gauntlets — not the diff loop's wide→scoped→wide, because there is no diff to derive `--changed` from (PHASE 0 passes it the enumerated paths instead). Round 1 verifies every inventory row; later rounds re-hunt the CLASSES: an adjudication that downgraded a verifier's CONFORMS is evidence that class was under-hunted, so re-sweep it across rows that already passed — inside the inventory: an instance found outside it is recorded and routed by PHASE 3's table to its owning command (a work item or a mail), never counted toward this run's convergence. The **closing round runs non-author verifiers** on the full inventory.
- **DONE requires all of:** the Termination contract's exit above — the closing round at `confirmed: 0 · fixed: 0 · unexecuted: 0` with every candidate adjudicated, every Checklist row adjudicated, the Pass Ledger in the fragment's grammar with `method: re-derivation` on the closing row — and, host-only, **every Inventory row terminal** (no `PENDING`).
- **Every verdict evidence-anchored with FRESH runs**: a green from last week is not evidence — re-run it or mark the row PARTIAL and say why. **Supersessions name their successor. DEVIATES rows state whether the spec was re-frozen** — if not, that row IS refreeze debt and belongs in the cluster summary.
- Commit the ledger, route the cluster summary, `final_gate` green; then report.
- The Evidence bootstrap (first-run trap, reported live): the convergence gate reds a ledger that lacks an embedded `final_gate` `"status": "success"` fenced block — but the gate cannot go green until that block exists. The SEQUENCE, not a paradox: (1) finish the ledger's obligations, (2) embed the fenced gate block with the EXPECTED green shape, (3) run `python scripts/final_gate.py --check --json` — it now sees the embed and reports the real result, (4) correct the embedded numbers to the verbatim output and re-run once; the fixpoint (embed == fresh run) is the evidence-true state.
- A routed finding's terminal token is **`ROUTED(n)`**, first-class in the checklist vocabulary alongside CLEAN/FIXED/REFUTED; never write "FIXED via routing". `n` counts the work items and mails the row's findings were routed to, pre-existing ones included; an operator gate is not a route — that row reads `RECORDED — measured (operator gate: <work item or mail id>)` and is listed in OUTPUT's RESIDUAL — and an id already counted under another class is not counted again.

## OUTPUT

The ledger doc (Surface hash · Inventory table · Per-phase verdicts · Coverage Checklist · Pass Ledger), committed — that FILE is the deliverable, not this chat. In the reply: the verdict distribution across the five values; every non-CONFORMS row with its `path:line` gaps; the cluster lists, enumerated from PHASE 3's own list, never a literal restated here (counts drift) — each naming the command it was routed to; and an explicit RESIDUAL list — eras deliberately excluded with their successor named, rows that could not be proven today and why, and any spec-refreeze debt the operator must decide on rather than an agent.

Scale effort to blast radius: exhaustive on money / auth / data-integrity artifacts, proportionate on low-risk ones — and log anything you deliberately skip. When unsure whether a row conforms, surface it as PARTIAL; a wrong CONFORMS is the one verdict that ends inspection.

{{include:subagents-core}}

{{include:close-chain}}
