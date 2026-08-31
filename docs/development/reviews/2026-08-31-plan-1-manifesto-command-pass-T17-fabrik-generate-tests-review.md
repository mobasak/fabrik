# T17 — /fabrik-generate-tests: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-generate-tests.md (150 lines post-fix, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-generate-tests.md` (282 lines at evaluation: run-record :14-47 · the loop incl. test-generation-loop fragment :67-171 · close-feedback :189-282 — all spans verifier-confirmed exact; re-rendered at merge). The five-step shape renders from commands/_fragments/test-generation-loop.md — dual-render into this command and /fabrik-review verified (:38 here, fabrik-review.md:324).
Outcome: 2 source fixes (scoped-commit discipline at step 3; fanout=None stated fail-mode) + one refuted angle recorded.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS (honestly characterized) — a BOUNDED five-step pipeline, not a convergence loop: termination = survivors applied + verdicts back-filled, traced through the run-record round ledger. Mechanical teeth at the edges: `check_subagent_flywheel.py` BLOCKS (verifier-confirmed exit-1, Layer 1) a substantial code change with zero pool runs — declarable via the `NO-POOL:` trailer/env waiver, which puts native-only ON THE RECORD rather than un-gating it (:148-150); `check_mutation.py` is advisory (verifier-confirmed always-0, FABRIK_MUTMUT=1-gated, :106-108); authors self-verify collection in the bwrap sandbox before returning (:89-90); the fanout=None path now STOPS with a stated fail-mode instead of a bare mid-pipeline TypeError (:34-37) |
| (b) ledger routing + one-way field block | N/A because the command mints no decision-shaped events — no Status flips, approvals, or retirements; curation is a technical-editorial act, step-3 commits are routine code commits (CHANGELOG's beat, the carve-out class), and the rendered close-feedback decision line covers any ruling received. One-way field block N/A — test files are reversible diffs applied only after review (:90, :106) |
| (c) rigor scales with irreversibility | CONFORMS — curation RISK-ORDERs the behavior list (:60); the risky behaviors stay implementer-TDD'd while the pool fills the rest (:137-138); "never degrade shared or paid infrastructure to make it provable" (:105); scoring targets the author's JUDGMENT because a weak test scored 4/5 poisons pick_models (:120-121) |
| (d) labeled verified/assumption evidence | CONFORMS — the review question is falsifiability itself: "would the test FAIL if the behavior broke?" (:101-102); "could it fail in THIS environment at all?" — environment-blind green is flagged, not banked (:103-105); fanout captures diffs, NEVER auto-applies (:90); the mutation check is labeled advisory (:108) |
| (e) captured disorder | CONFORMS — weak/environment-blind tests FLAGGED rather than silently banked (:105); every dispatched run recorded UNSCORED with the NULL-score failure mode named (:110-123, :142-150); straggler recovery bounded to ONE re-dispatch, persistent flakiness handled statistically, never reactively (:91-95); close-feedback rides the render |
| (f) most-reversible default under ambiguity | CONFORMS (post-fix) — review-before-apply is the default posture (:90); step-3 commits are now SCOPED: explicit pathspecs + trailers, never `git add -A`, because "mid-pipeline is exactly when a sibling's WIP gets swept in" (:76-78); the worktree-sweep guard hierarchy is explicit — PID-aware library sweep preferred, manual rm -rf conditioned on no-siblings + age named a WEAK guard (:125-132); empty $ARGUMENTS default stated — infer from the diff (:11-12). Salvage-before-destroy (the T13/D6 class) examined and REFUTED here: a killed pool author's partial test file is cents-scale, fully reproducible by re-dispatch — unlike D6's ticket-scale coder work; adding capture would be unmeasured over-engineering (FIX DIRECTIVE #5) |

6/6 adjudicated: 4 CONFORMS, 1 FIXED-under-(f)/(a), 1 N/A.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 4 PLAUSIBLE candidates, 0 CONFIRMED — the first artifact in the plan with all-clean anchors (20/20 re-derived exact, both line counts exact, fragment dual-render verified, flywheel-gate blocking behavior verified exit-1, all 3 auto-fire call sites corroborated). Adjudication: **2 adopted as REAL source gaps** (unscoped "commit it now" on the shared tree → scoped-commit clause :76-78; fanout=None un-guarded crash path → stated fail-mode STOP :34-37) · **1 REFUTED with recorded reasoning** (worktree destruction vs the T13/D6 salvage precedent — the irreversibility-scaling distinction now argued explicitly in (f)) · **1 adopted as artifact completeness** ((a) now names the NO-POOL declarable waiver — on-the-record, not un-gated) | 2 source edits + artifact re-grounding; anchors re-derived post-edit (+5 line shift absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — all cited anchors re-grepped against the 150-line source (:34-37, :60, :76-78, :90-95, :101-108, :125-132, :137-138, :148-150 confirmed verbatim) | TERMINAL no-op |

Verifier falsification streak: 17-for-17 on substance (zero CONFIRMED anchor defects this round — the grep-derive discipline finally held — but all four reasoning gaps were real enough that two became source fixes).

## Per-finding disposition ledger

1. Worktree destruction vs T13/D6 precedent (PLAUSIBLE) → REFUTED with recorded reasoning: cents-scale reproducible pool work vs ticket-scale coder work; the scaling argument is now IN the (f) cell.
2. Unscoped "commit it now" (PLAUSIBLE→REAL) → source fix: explicit pathspecs + trailers, never `git add -A` (:76-78).
3. fanout=None crash path (PLAUSIBLE→REAL) → source fix: STOP with stated fail-mode before step 1 (:34-37).
4. NO-POOL waiver omission in (a) (low-confidence) → artifact completeness: the waiver named as on-the-record declaration.
