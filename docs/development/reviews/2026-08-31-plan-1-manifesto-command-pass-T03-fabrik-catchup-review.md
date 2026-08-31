# T03 — /fabrik-catchup: 63b manifesto conformance

Status: CONVERGED — 1 source fix (two clauses) after verification; closing round new: 0

Surface: commands/_sources/fabrik-catchup.md (124 lines pre-fix, 131 post-fix, read in full) + rendered ~/.claude/commands/fabrik-catchup.md (288 lines; composition = source + run-record + grounding-artifact + repo-identity + close-feedback, all swept by T01's fragment ledger).
Outcome: 1 FIX — the initial 6/6-CONFORM stamp was falsified on three axes by the scoped verifier (citation-surface mismatch; (b) same-change atomicity gap; (f) undecidable-reconcile stall path).

Citation convention (verifier-corrected): the `:NN` anchors below are SOURCE-relative (commands/_sources/fabrik-catchup.md); rendered-file equivalents, re-derived by the verifier's greps: termination :48-56 · reconcile 'state which' :167 · worst-first :157-158 · evidence-per-item :158-159 · probe-6 epistemics :149-153 · output block :186-188 · the OLD Phase-2 paragraph (pre-fix render) :171-180; the close-out decision line at :201-206 is the generic fragment, distinct from the Phase-2 clause (closing verifier corrected this mapping).

## 63b Verdict Table

| intersection | verdict |
|---|---|
| (a) checkable gates | CONFORMS — termination = a zero-new-item RE-MEASURE (fresh Phase-0 probe re-run) AND `final_gate.py --check --json` success IN THIS RUN (:15-20); the executed pass is never the last MEASURE (:20-22) — the fix-never-last law in catchup form |
| (b) ledger routing + one-way field block | FIXED — the verifier proved the generic close-out decision line cannot satisfy SAME-change atomicity for a decision-shaped reconcile committed mid-run (one-commit-per-item means the row would land in a different commit); Phase 2 now mandates the ledger row IN the reconcile's own commit, truth-restoring corrections exempt (source :105-113) |
| (c) rigor scales with irreversibility | CONFORMS-via-delegation (cell re-adjudicated per the verifier: ORDERING is not SCALING) — catchup is a router; depth scaling lives in the routed commands' own convergence loops, which is the correct shape for a measurement/routing utility; worst-first ordering (:88-89 source) additionally sequences by consequence |
| (d) labeled verified/assumption evidence | CONFORMS — every queue item names its evidence (path:line or the raising command, :90); grounding-artifact fragment included (:30); probe 6's epistemics (:75-84) explicitly refuse BOTH "the row says live" AND a project-side probe as proof — verified-vs-assumption at its sharpest |
| (e) captured disorder | CONFORMS — the mandatory CATCHUP/RE-MEASURE/GATE output block (:116-120) + report-only findings + close-feedback MACHINERY routing |
| (f) most-reversible default under ambiguity | FIXED — probe 6's report-only default was already exemplary, but the verifier found a SECOND ambiguity surface with no disposition: a spine-vs-lock / spec-vs-code reconcile whose true side is undecidable. Phase 2 now downgrades that case to report-only naming both candidate truths — Invariant 3 applied (source :105-113) |

6/6 adjudicated after verification: 4 CONFORMS · 2 FIXED. The initial all-CONFORM stamp was falsified — third ticket running where the verification floor caught what the author-pass stamped clean.

## Scoped verification review

| pass | finders | found | new | fixed | verdict |
|---|---|---|---|---|---|
| Pass 1 | 1 native author-blind verifier: all 9 citations re-derived by grep against the DECLARED surface + intersection over-credit hunt | 5 | 5 | 4 | citation-surface mismatch CONFIRMED (all 9 anchors were source-relative vs a rendered Surface line); (b)+(f) source gaps FIXED (one Phase-2 clause pair); (c) cell re-adjudicated; #5 self-grading edge noted-no-exploit |
| Pass 2 | fresh finder over the source fix + corrected artifact; all 7 rendered anchors spot-checked; ledger-duty cross-check vs BOTH contracts | 5 | 5 | 4 | re-measure loop-forever on the new class FIXED (carve-out extended) · route-table signals FIXED · anchor mis-map FIXED · stale line count FIXED · W5 = hub-vs-template ledger-bullet drift, routed to the orchestrator (out of ticket scope) |
| Pass 3 (closing, method: gate) | mechanical: coherence grep (both report-only classes in the carve-out, both route rows signal the downgrade), diff hygiene | 0 | 0 | 0 | → EXIT |

## Per-finding disposition ledger

| # | finding | state |
|---|---|---|
| V1 | every table citation resolved against the source while Surface declared the rendered file | FIXED — citation convention stated + rendered equivalents added from the verifier's own greps |
| V2 | decision-shaped reconcile commits violate SAME-change ledger atomicity | FIXED — Phase-2 clause: the row rides the reconcile's own commit |
| V3 | (c) credited ordering as scaling | FIXED — cell re-adjudicated as CONFORMS-via-delegation with the distinction stated |
| V4 | undecidable reconcile ambiguity had no sanctioned disposition | FIXED — Phase-2 clause: downgrade to report-only naming both candidate truths (Invariant 3) |
| V5 | RE-MEASURE self-grading edge | NOTED — structural to self-terminating loops, tightly scoped by the (now two-class) carve-out; no concrete exploit demonstrated; no edit |
| W1 | the new report-only class escaped the termination carve-out — Probe 1 would re-flag it forever (loop or coerced guess) | FIXED — carve-out now names BOTH report-only classes |
| W2 | artifact's rendered-anchor footer mapped the Phase-2 clause to the generic decision-line fragment | FIXED — mapping corrected to :171-180 (pre-fix render) |
| W3 | route-table rows gave no signal the two reconcile classes may terminate report-only | FIXED — both rows now point at the Phase-2 downgrade |
| W4 | Surface line-count stale post-fix | FIXED |
| W5 | hub CLAUDE.md's ledger bullet lacks the template's "NOT a decision" carve-out (governance drift, found via the truth-restoring-correction cross-check) | ROUTED — orchestrator commit follows this ticket (out of ticket Touches; hub governance is not plan surface) |
