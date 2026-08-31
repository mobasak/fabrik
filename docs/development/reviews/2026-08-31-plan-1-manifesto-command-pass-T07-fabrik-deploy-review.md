# T07 — /fabrik-deploy: 63b manifesto conformance

Status: CONVERGED — 1 source fix + honest method correction; closing round new: 0

Surface: commands/_sources/fabrik-deploy.md (333 pre-fix / 337 post-fix lines, read in full). METHOD CORRECTION (owed honestly): the initial table claimed grep-derived anchors while 6 of ~15 were carried from a stale numbering (monotonic drift signature) — the verifier re-derived all; corrected below + rendered composition (run-record + close-feedback, T01-swept).
Outcome: 1 FIX + 1 ROUTED — seventh consecutive falsified stamp: (b) rested on a NONEXISTENT 'routine operations' carve-out and a FALSE 'already-minted' premise (grep: nothing in the deploy triad mints the CONVERGED row — ROUTED to T09, whose surface owns the flip). T07's own gap: Phase 5 never minted the 'built X at Y' row — fixed in-source.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors) |
|---|---|
| (a) checkable gates | CONFORMS — exactly TWO endings, each checkable: EXECUTED = battery green + window provably closed + every ledger row committed (:26-30); Halted = the FULL halt protocol with fenced rollback proof + the ⛔ ledger row + the BLOCKED report naming the route back (:31-35); "there is no mid-runbook resume protocol" kills the mushy middle (:12-13) |
| (b) ledger routing + one-way field block | FIXED — the initial cell invented a carve-out and asserted an unminted premise (both verifier-refuted with zero-hit greps). Sound state now: Phase 5 mints the "built X at Y" row IN the flip commit (classified at mint, reversible-by-redeploy); the CONVERGED-flip row gap belongs to /fabrik-deploy-plan-review's surface → ROUTED to T09 (this pass's own ticket); the per-step deploy LEDGER remains the operational evidence record |
| (c) rigor scales with irreversibility | CONFORMS — rigor is tiered precisely by what has mutated: pre-flight failures refuse BEFORE mutating ("nothing deployed", :127-129); pre-flip stops have "nothing to unwind" (:125); post-flip the rule is TOTAL (two endings only, :130-132); the maintenance window brackets exactly the steps a healthcheck outlives (:153) |
| (d) labeled verified/assumption evidence | CONFORMS — fenced output per guard step; "Git evidence only — file mtime tells you nothing" (:74-75); the unprivileged-journalctl false-"nothing found" trap named with the bounded 5-minute rule (:186-192); after a foreground timeout, probe the remote completion state before re-running — a blind re-run is a double-apply (:147-149) |
| (e) captured disorder | CONFORMS — each ledger row committed at the step that earned it ("a migration's row living only in the working tree is not durable", :138-139); RUN-header partitioning keeps history honest (:133-134); SKIP-RUN adjudicated as an active-healer signal, never benign (:177-181) |
| (f) most-reversible default under ambiguity | CONFORMS — conservative defaults are NAMED: an unresolvable pause state → "report the raw state and proceed, the 2h self-heal bounding the residue" (:117-119); live foreign pause → bounded wait then BLOCKED, pre-flip (:122-126); a clobber race → the halt protocol REMOVING NOTHING (:166) |

6/6 adjudicated after verification: 5 CONFORMS · 1 FIXED (+1 ROUTED to T09). Armed-tripwires (manifesto :75) adjudicated as DELEGATED — the deploy-plan-review checklist class 7 ("what ACTUALLY watches the surface", fabrik-deploy-plan-review.md:137) owns the alerting question; stated here so the delegation is a verdict, not an omission. Battery-totality and wait-boundedness verified with denominators (3 exit branches; 4 wait sites).

## Scoped verification review

| pass | finders | found | new | fixed | verdict |
|---|---|---|---|---|---|
| Pass 1 | 1 native author-blind verifier: full 333-line read + the triad's plan-review read + zero-hit greps on both (b) premises + independent anchor re-derivation | 7 | 7 | 6 | A1 already-minted premise REFUTED → ROUTED to T09 · A2 invented carve-out FIXED (cell) · A3 Phase-5 row-mint FIXED (source) · A4 six stale anchors FIXED + method claim corrected · A5 tripwire delegation stated · A6/A7 clean negatives with denominators |
| Pass 2 (closing, method: gate) | mechanical: the Phase-5 clause greps clean in-source; all corrected anchors re-derived; no carve-out residue | 0 | 0 | 0 | → EXIT |

## Per-finding disposition ledger

| # | finding | state |
|---|---|---|
| A1 | "already-minted per the plan-review chain" — zero DECISIONS hits in the whole triad | REFUTED as a T07 premise · ROUTED to T09 (fabrik-deploy-plan-review owns the CONVERGED flip and will gain the row-mint there) |
| A2 | a "routine operations" carve-out that exists nowhere in the corpus | FIXED — cell rewritten without it; the real carve-out (routine fixes/refactors/doc edits) does not cover decision-shaped completions |
| A3 | Phase 5 writes EXECUTED + stamp but never mints the "built X at Y" row | FIXED — the row rides the flip commit, classified at mint |
| A4 | 6 anchors stale under a "grep-derived" method claim | FIXED — anchors corrected to the verifier's derivation; the method claim corrected honestly in the Surface line |
| A5 | armed-tripwires binding unadjudicated | FIXED — stated as DELEGATED to the plan-review's watching-surface class (its :137) |
| A6 | battery-red escape hatch hunt | CLEAN — none found (3 exit branches checked) |
| A7 | unbounded-wait hunt | CLEAN — none found (4 wait sites, all bounded with named escapes) |
