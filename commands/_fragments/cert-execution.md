**Done ONLY when a full round reports `new inventory: 0 · new findings: 0 · fixes applied: 0` —
TWO consecutive dry discovery sweeps** (the loop-until-dry rule: one clean round can be luck).
**Grader honesty — which exit conditions are machine-read and which are yours:** board shape,
dispositions, evidence-paths-exist and the registry/ledger are graded by
`check_certification_coverage.py` (mix-ups BLOCK; coverage quality is advisory); the HANDOFF
grammar and NOT-QUIET/RESUME pairing by `check_review_coverage.py`; the round ledger by
`command_run.py round`. The TWO-dry-sweeps count, the ×2 reproduction rule and the T2 batch cap
are read by NO check — they bind you on honour, which is exactly why the ledger rows exist.
A matrix cell deliberately skipped is listed SKIPPED with a reason — silent shrinkage of the
inventory or matrix is the exact failure this command exists to prevent.

## Phase 6 — EXECUTE the routed fixes (same run, FRESH contexts — a handoff is deferred sequencing, not exported work)

Discovery first, fixes second — **and the fixes DO happen in this run, but never in this context.** The
gauntlet's own context is depleted by the sweeps; the deep work runs in clean contexts while YOU stay the
orchestrator ("you dispatch and judge — you do not drive"). Work the HANDED-OFF list on a **hard schedule**
(no budget-feel exits): **T3 doc re-freezes first** (cheap, bounded) → **T1 leftovers** → **T2 risk-ordered**.

1. **Code-wrong rows (T2)** — for each row, **dispatch a FRESH native subagent** (clean context; seeded with
   exactly: the committed red repro path, the owning module path, the rubric output) that invokes
   `/fabrik-review` with `repro: <path>` — the review may not exit until that repro is GREEN (its contract).
   When it returns, **verify yourself before closing** (a subagent's success is a claim): re-run the repro AND
   the affected journeys end-to-end (surface truth AND system truth). **T2 batch cap:** more than 3 distinct owning modules on the list is a
   SYSTEMIC signal (the phase-boundary reviews failed upstream) — emit that finding and route the batch to a
   plan instead of serial review loops.
2. **Doc-stale rows (T3)**: run the re-freeze now, close the row.
3. **Design-wrong/missing rows (T4)** — **write a DESIGN-GAP BRIEF, do not run the pipeline**: persist
   `docs/development/reviews/YYYY-MM-DD-design-gap-<slug>.md` carrying the blocked journey, the missing
   screen/endpoint/job/contract field, the contract line that should exist, the evidence, and the exact `/fabrik-spec`
   invocation to start it — then stop that row at `DESIGN-GAP (operator decision)`, surfaced in the report's
   TOP section. `/fabrik-spec` is built around collaborative Q&A + per-section human approval; an autonomous
   run driving it must either stall or self-approve the product question — both forbidden. The operator
   decides whether a spec is warranted; the brief makes that a 2-minute decision.

**No unfalsifiable exits:** if rows remain when this session genuinely cannot continue, the report's final
ledger row is marked **`NOT-QUIET (routes outstanding)`** and a `## RESUME` block names every open row, its
repro path, and the verbatim re-invocation command. A truncated run may NEVER present itself as quiet.

## Phase 7 — CONFIRMING ROUND (the code-changing pass is never the last)

After the last code-changing row closes, run **one full Phase-5 round** (fresh discovery sweep + full
reconcile — not just affected journeys): Phase 6's fixes are the deepest changes in the run and get the
deepest re-verification. **The report's final ledger row must be THIS round's** `new inventory: 0 · new
findings: 0 · fixes applied: 0` — a quiet exit recorded before Phase 6 ran is void.
