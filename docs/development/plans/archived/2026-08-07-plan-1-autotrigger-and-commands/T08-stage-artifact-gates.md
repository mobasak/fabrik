# T08 — Stage-skip artifact gates

Depends: —
Parallel: ⚡
Complexity: never-route
Docs: CHANGELOG entry via Deltas
Gate: python -m pytest tests/enforcement/test_check_stage_artifacts.py -q && python scripts/final_gate.py --lean --check --json

## Scope

The deepest auto-trigger layer: skills can be skipped at the front door, but each stage's OUTPUT
artifact is mechanically checkable — extend the proven pattern (EXECUTED-needs-review-doc in
`check_convergence.py`; release-needs-certification in `fabrik-release`'s preconditions).
**Step 1 (audit, recorded in this ticket's section of the spine Evidence at execution):** build
the full stage→artifact→existing-gate table (1-design: spec CONVERGED · 2-contract:
data-contract/ui-design FROZEN · 3-plan: plan CONVERGED + review · 4-build: phase/ticket commits +
review docs · 5-certify: user/service-test reports · 6-release: release receipts). **Step 2
(implement the top TWO unguarded gaps only** — the pre-analysis candidates, to be confirmed by the
audit: (a) a plan flipping CONVERGED whose SPEC is still DRAFT (stage-1→3 skip); (b) a
certification report claimed by a release precondition without gate-side existence/shape checking
(5-certify's artifact has no enforcement outside prose)) as `scripts/enforcement/
check_stage_artifacts.py`, registered in `final_gate.py` Tier-2 ONLY — matching its cited
precedent exactly (`check_convergence.py` is final_gate-wired, NOT in validate_conventions'
per-file dispatch; a cross-file audit doesn't fit that mechanism) — with red-on-revert tests. DO-NOT: gate more than two gaps (scope discipline); DO-NOT re-gate what
check_convergence already owns (extend or reference, never duplicate); DRAFT/PLANNED downgrade
semantics follow the plan-gates' context-severity precedent.

## Touches

- scripts/enforcement/check_stage_artifacts.py
- scripts/enforcement/check_convergence.py
- scripts/final_gate.py
- tests/enforcement/test_check_stage_artifacts.py

## Behavior Contract

- **Given** the pipeline's stage→artifact map, **When** T08's audit runs, **Then** the spine Evidence records the full table and the top TWO unguarded stages gain gate checks with red-on-revert tests (scripts/enforcement/check_stage_artifacts.py:1).

## Context Files

- scripts/enforcement/check_convergence.py (:418-470 — the EXECUTED-citation pattern to extend, incl. the per-ticket-review discrimination)
- scripts/final_gate.py (:935-943 — Tier-2 registration block)
- commands/_sources/fabrik-release.md (the certification-precondition prose whose artifact side gets teeth)
- tests/test_check_convergence.py (fixture style for flip/artifact tests)
- .windsurf/rules/core/45-testing-strategy.md (red-on-revert discipline)
