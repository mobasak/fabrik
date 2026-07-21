## ⚠️ Termination contract — coverage-adjudicated (READ FIRST — the rule agents skip)

This is a LOOP that runs **until no issues remain to raise AND every class is proven hunted** — two conditions, BOTH required, neither sufficient alone. A quiet round alone is not the exit (that *sample* found nothing ≠ nothing exists). A fully-adjudicated checklist alone is not the exit either (adjudication without a confirming quiet round is premature). The exit needs BOTH:

**Before Pass 1 — three mechanical obligations, in order:**
1. **Anchor:** read the NEWEST `docs/development/reviews/*-review.md` for this scope (if any). Compute the surface hash: `git rev-parse HEAD` + `git diff HEAD | md5sum`. If it matches the prior report's recorded `Surface:` line, this run **re-adjudicates THAT report's checklist** (verification + delta only — a new finding must name the rubric class it belongs to, or it is a rubric gap to report). Unchanged surface + previously fully-adjudicated checklist = a short verification report, honestly.
2. **Rubric:** run `python scripts/review_rubric.py --changed <paths>` and paste its verbatim output into the report inside a fenced block — the class rows derive from IT, never from memory.
3. **Persist:** create `docs/development/reviews/YYYY-MM-DD-<scope>-review.md` NOW, with the `Surface:` hash line and the Coverage Checklist skeleton. **A review that exists only in chat does not exist** — `check_review_coverage.py` (run by `final_gate` and the stop-hook) reads only this file; the review is INVALID until the adjudicated checklist + Pass Ledger live in it.

The Coverage Checklist: one row per failure class from the rubric output (FLOOR + MATCHED + workflow checklist), PLUS the standing recurrence classes: **fail-open vs fail-closed on every gate/guard · cost/quota/limit accounting edges (unknown≠0, per-call vs batch) · boundary/sentinel/prefix collisions · behavior-without-a-test**. Every row starts `UNCHECKED`.

Loop passes as specified (finders → refute → prove & fix → regression-guard), updating rows as you go. **You are DONE only when ALL of these hold:**
- **The final round raised NOTHING — `found: 0, fixed: 0`**, where `found` counts every candidate any finder RAISED, **including ones you refute in triage** (a round that raised 3 and refuted all 3 is NOT quiet — run the next full round). Keep hunting while anything is still turning up; the loop, not the checklist, decides when the hunting stops.
- **Every row is adjudicated** — `CLEAN` (hunted this run, with what/where evidence), `FIXED(n)`, or `REFUTED(n, proof)`. No `UNCHECKED` rows. An in-scope CONFIRMED or PLAUSIBLE finding terminates FIXED or REFUTED — never silently passed.{{RESIDUAL}}
- **The last code-changing pass was followed by a confirming re-check** of every class its fixes touched (fixes introduce defects — the pass that changed code is never the last look at those classes).
- **Mechanical gates are green** (`final_gate`) — lint/type/test classes are the gates' job; do not spend finder passes re-discovering what a gate catches.
- **Ledger reproduced** — numbered passes with `found:` (counting every raised candidate, INCLUDING later-refuted ones) and `fixed:` per pass.

**Minimum two full rounds, ALWAYS** — the round that first completes the checklist is never the exit round: a fresh, independent round must re-adjudicate it (and may re-open classes). Accuracy outranks pass-count.

**Budget: hard cap {{PASS_CAP}} passes.** If the cap lands with rows still churning, STOP — do not keep looping. Declare the residual explicitly in the report: which classes remain hot, the risk you are accepting, and why. **A declared residual is an honest exit; a lucky empty pass sold as proof-of-absence is not.** Re-invoking this command on unchanged code re-adjudicates this SAME checklist — free-hunting outside it must be justified as a new class, which is a rubric gap to report.

Run every owed pass **UNPROMPTED, inside THIS ONE invocation** — never end the turn with `UNCHECKED` rows or an unconfirmed fix for the operator to re-invoke. You return control EXACTLY ONCE: at the fully-adjudicated checklist.
