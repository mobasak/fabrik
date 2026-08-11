# Finder-shape A/B — decision record (plan-2 Phase A)

Executed: 2026-08-11 · Orchestrator: /fabrik-execute-plan on
`docs/development/plans/2026-08-10-plan-2-review-loop-overhaul.md` · Raw results:
session scratchpad `ph_a_results.json` (arm walls, per-unit latencies, statuses, full texts;
flywheel rows recorded under project `review-loop-ab`, scored post-adjudication).

## Surface (pinned + adjudicated at execution)

The plan left the review surface to the executor; adjudication recorded here: the freshest
unreviewed-by-this-session diff — `3b66faa1..fde0cc1f` (the deploy-triad sibling's late Phase-A
waves + Phase-B pipeline wiring: `commands/` + `.claude/hooks/skill_router.py` + both `CLAUDE.md`
copies; 99,702 diff chars, 9 files, +475/−294). Chosen for freshness, size, and live-tree
adjudicability. **Known limitation, stated plainly:** this artifact had already survived ~57
sibling review rounds before landing, and the adjudicated ground truth came out EMPTY — the
surface is defect-poor, so the experiment separates the arms on cost/wall/parallelism and
behavior, NOT on recall.

## Protocol (per plan Phase A steps 1-5)

Pinned roster, identical class briefs across arms 1 and 2
(`pick_models("review", n=4)` → `deepseek/deepseek-v3.2-exp`, `google/gemini-3-flash-preview`,
`qwen/qwen3-max`, `deepseek/deepseek-v4-flash`); 4 class-partitioned briefs (contradiction ·
gate-integration · fail-direction · grounding). All candidates from all arms pooled with arm
labels stripped; each adjudicated ONCE by the orchestrator by execution (probe outputs below);
verdicts attributed back to arms only afterward.

## Arm results

arm 1 (read-only single-shot, diff inline) — raised: 5 real: 0 wall-clock: 122 s
  precision 0/5 = 0.00 · recall N/A (empty ground-truth union) · 4/4 units done, none capped.
arm 2 (tool-enabled finders, per-finder report paths) — raised: 6 real: 0 wall-clock: 413 s
  precision 0/6 = 0.00 · recall N/A · **parallelism ACHIEVED and asserted**: wall 413 s == max
  unit latency (413 s), vs 727 s summed latencies — the disjoint write scopes worked exactly as
  `workspace.disjoint()` predicts. **All 4 units CAPPED at the matched budget** ($0.30 / 18
  turns): tool access costs more wall and budget for partial-coverage reports on this surface.
arm 3 (read-only FIND + tool-enabled VERIFY over candidates) — raised: 5 real: 0 wall-clock: 375 s
  (= arm-1 find 122 s + verify 253 s) · post-verify precision 0/1 (one verifier wrongly CONFIRMED
  the wordpress candidate; the other correctly REFUTED catchup by executing the probe).

## Adjudication ledger (every pooled candidate, execution-verdicts)

Post-adjudication arm attribution (the protocol's final step — added after a phase-review verifier
correctly flagged that the anonymised ledger alone leaves the 5/6/5 counts unauditable): items
1-5 were raised by ARM 1 (its gate-integration unit raised 1-3's claims — its other five numbered
lines were citation observations asserting no defect, not candidates; its grounding unit raised
4-5); items 6-7 by ARM 2 (its gate-integration unit); arm 2's count of 6 additionally includes
its fail-direction unit's 4 self-refuted candidates (counted per the found-counts-refuted rule);
ARM 3's raised = the 5 arm-1 candidates its verify stage processed.

1. "`catchup` keyword mapping missing from KEYWORD_STEMS" — **REFUTED**: live
   `skill_router.py:341` carries the catchup regex; the finder saw only the diff (the entry
   pre-existed) — the read-only-inline diff-scope illusion.
2. "wordpress in SCAFFOLD_TYPES contradicts 'out of fabrik'" — **REFUTED**: the registry
   deliberately keeps `wordpress` as a recognised deploy/shape type while the scaffold path is
   retired (`agents-fabrik.md` scaffold-types table states exactly this split); both CLAUDE.md
   copies carry identical caveat text.
3. "deploy-verify's manual-`fabrik apply` path contradicts Gate-2" — **REFUTED**: deliberate —
   Gate-2 gates the TRIAD executor; a direct operator `fabrik apply` remains the operator's own
   sanctioned act, and verify covers both by design.
4. "'repo' vs 'repository' mismatch in fabrik-deploy-plan-review.md" — **REFUTED-FABRICATED**:
   `grep -n 'any repo other than\|any repository other than'` returns NOTHING — neither phrase
   exists; the read-only finder invented both the claim and its counter-evidence.
5. "(Gate 2) /fabrik-deploy notation inconsistent with the NEXT map" — **REFUTED**: the notation
   means "Gate 2 precedes deploy", exactly what the NEXT map encodes
   (`fabrik-deploy-plan-review` → "Gate 2 — human approval; on the operator's explicit go:
   /fabrik-deploy").
6. "check_plan_quality.py lacks deploy-plan stem scope" — **REFUTED**: the command prose cites
   the gate's pillar list, not stem coverage; deploy plans use the `-plan-deploy-` stem that
   passes both plan-name gates (gate-proven during triad planning).
7. "TR generic-plan pattern could intercept Turkish deploy prompts" — **REFUTED BY EXECUTION**:

```
$ for p in 'dağıtımı planla' 'plan the deployment' 'deploy it' 'dağıtım planını gözden geçir'; do
>   echo "{\"prompt\": \"$p\", \"cwd\": \"/opt/fabrik\"}" | .venv/bin/python .claude/hooks/skill_router.py; done
dağıtımı planla            → matches /fabrik-deploy-plan (Stage: 6-release)
plan the deployment        → matches /fabrik-deploy-plan (Stage: 6-release)
deploy it                  → matches /fabrik-deploy (Stage: 6-release)
dağıtım planını gözden geçir → matches /fabrik-deploy-plan-review (Stage: gate)
```

(qwen's four fail-direction self-refuted items counted in arm-2's `raised` per the
found-counts-refuted rule; its bounded-quantifier backtracking worry REFUTED — `{0,30}` is
bounded by construction.)

## Which factor dominates

On a defect-poor surface, **budget and grounding behavior separate the arms, recall does not**:
tool-enabled finders (arm 2) cost 3.4× the wall and capped at matched budget, but their claims
carried probe outputs and NONE fabricated; the read-only arm was 3× faster and complete, but
produced the run's only fabricated evidence (candidate 4) and its diff-scope illusion
(candidate 1). Tools helped the VERIFY role (arm 3's gemini unit refuted by execution — the only
verifier that resolved a candidate correctly), which matches the corpus's existing division:
finders raise, the ORCHESTRATOR verifies by execution.

CHOSEN SHAPE: arm 1 — the read-only status quo; Phase B ships the loop changes WITHOUT a
dispatch change (the plan's own decision rule: no arm beat arm 1 on precision AND recall at
comparable wall-clock — none did; recall could not be measured on this surface and precision was
0 everywhere). The observed tool-advantage lives in the VERIFY/adjudication role, which the
corpus already assigns to the orchestrator's execution-verdicts — no fragment change needed to
keep it.

## Residual honesty

- Recall is N/A here, not measured-and-equal: re-running the A/B on a defect-RICH surface (a
  pre-review build diff) would be needed to rank recall — the union denominator this run is
  empty. That re-run is NOT scheduled by this plan (Phase B proceeds on the no-dispatch-change
  outcome, which a richer surface could only overturn toward a FUTURE pack addition, not a loop
  change).
- Arm-2 caps mean its precision/recall are lower bounds under the matched budget — also stated
  as a budget finding, not a model-quality finding.
