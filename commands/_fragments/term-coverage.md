## ⚠️ Termination contract — coverage-adjudicated (READ FIRST — the rule agents skip)

This is a LOOP with a **deterministic exit: full coverage, not a lucky empty pass**. An empty finder round proves that *sample* found nothing — not that nothing exists — so "a pass found nothing" is NEVER the exit test by itself. The exit is a fully-adjudicated **Coverage Checklist**:

**Before Pass 1**, print the Coverage Checklist — one row per failure class from `python scripts/review_rubric.py --changed <paths>` (FLOOR + MATCHED + workflow checklist), PLUS the standing recurrence classes: **fail-open vs fail-closed on every gate/guard · cost/quota/limit accounting edges (unknown≠0, per-call vs batch) · boundary/sentinel/prefix collisions · behavior-without-a-test**. Every row starts `UNCHECKED`.

Loop passes as specified (finders → refute → prove & fix → regression-guard), updating rows as you go. **You are DONE only when ALL of these hold:**
- **Every row is adjudicated** — `CLEAN` (hunted this run, with what/where evidence), `FIXED(n)`, or `REFUTED(n, proof)`. No `UNCHECKED` rows. An in-scope CONFIRMED or PLAUSIBLE finding terminates FIXED or REFUTED — never silently passed.{{RESIDUAL}}
- **The last code-changing pass was followed by a confirming re-check** of every class its fixes touched (fixes introduce defects — the pass that changed code is never the last look at those classes).
- **Mechanical gates are green** (`final_gate`) — lint/type/test classes are the gates' job; do not spend finder passes re-discovering what a gate catches.
- **Ledger reproduced** — numbered passes with `found:` (counting every raised candidate, INCLUDING later-refuted ones) and `fixed:` per pass.

**Minimum two full rounds, ALWAYS** — the round that first completes the checklist is never the exit round: a fresh, independent round must re-adjudicate it (and may re-open classes). Accuracy outranks pass-count.

**Budget: hard cap {{PASS_CAP}} passes.** If the cap lands with rows still churning, STOP — do not keep looping. Declare the residual explicitly in the report: which classes remain hot, the risk you are accepting, and why. **A declared residual is an honest exit; a lucky empty pass sold as proof-of-absence is not.** Re-invoking this command on unchanged code re-adjudicates this SAME checklist — free-hunting outside it must be justified as a new class, which is a rubric gap to report.

Run every owed pass **UNPROMPTED, inside THIS ONE invocation** — never end the turn with `UNCHECKED` rows or an unconfirmed fix for the operator to re-invoke. You return control EXACTLY ONCE: at the fully-adjudicated checklist.
