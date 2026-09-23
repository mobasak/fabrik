# T01 — gate-ending command sources state their gate as a DECISION block

## Scope
Implements spec § Contract deltas ("The command corpus") and § C1 ("The exemption is a well-formed DECISION block"). Six sources end a run at a human gate. Each states that gate in the DECISION block's shape (spec § C2), with `ground: gate`, the class named on the "Why it is yours" line, the options with what each changes, and a recommendation. `commands/_sources/fabrik-deploy.md:29` currently tells the agent to put `operator decision: <the act>` on its `NEXT:` line because "the hook exemption is line-scoped"; that instruction is replaced by the block. DO-NOT: render the corpus (the orchestrator renders from master on merge), touch any other source, or change a gate's substance (who approves what stays as it is).

Depends: —
Parallel: ⚡
Complexity: native
Gate: uv run pytest tests/test_gate_decision_blocks.py -q
Docs: CHANGELOG (Deltas)

## Touches
- commands/_sources/fabrik-spec-review.md — PRIMARY PATH
- commands/_sources/fabrik-flows-review.md
- commands/_sources/fabrik-ui-design-review.md
- commands/_sources/fabrik-deploy-plan-review.md
- commands/_sources/fabrik-release.md
- commands/_sources/fabrik-deploy.md
- tests/test_gate_decision_blocks.py

## Behavior Contract
- **Given** the six gate-ending command sources, **When** T01 lands, **Then** each states its human gate as a `DECISION NEEDED (ground: gate)` block and none tells the agent to write `operator decision: <the act>` as the exemption (spec § Contract deltas)

## Steps (the coder's order)
1. Red first: `tests/test_gate_decision_blocks.py` asserts, for each of the six sources, that it contains `DECISION NEEDED (ground: gate)` followed within 12 lines by `- Question:`, `- Why it is yours:`, `- Options:` and `- Recommendation:`; and that no source under `commands/_sources/` contains the phrase `the hook exemption is line-scoped`. Watch it FAIL on all six.
2. At each gate site, replace the prose that tells the agent to ask for approval with the block, stated once. Sites: `fabrik-spec-review.md:282` (design approval), `fabrik-flows-review.md:161` (journey freeze approval), `fabrik-ui-design-review.md:169` (UI design approval), `fabrik-deploy-plan-review.md:245` (Gate 2), `fabrik-release.md:6` (the hand-off to Gate 2), `fabrik-deploy.md:29` (the deploy act). Keep each section's other obligations (the comparison table, the Pass Ledger, what the operator is shown first) exactly as they are.
3. Gate green; CHANGELOG line into the Deltas block.
4. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit; every finding FIXED or REFUTED.
5. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T01`).

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md
