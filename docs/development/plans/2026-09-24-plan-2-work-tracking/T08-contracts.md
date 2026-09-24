# T08 — both contracts carry the short work-items rule

## Scope

Implements the contract rows of spec § Documentation landing sites: "`CLAUDE.md` +
`templates/governance/CLAUDE.md` (both § FINAL OUTPUT copies): one short rule". The rule is one
paragraph, placed directly after the `**`DONE:`/`NEXT:` discipline:**` paragraph of § FINAL OUTPUT
(hub `CLAUDE.md:631` onward; the template's two copies at `templates/governance/CLAUDE.md:629` and
`:701` — the template carries § FINAL OUTPUT twice by a routed, known duplication that
`tests/test_governance_template_split.py:1122` pins at exactly two, so BOTH copies get the paragraph).
The hub text, verbatim:

> **Work items.** A repo with a `.fabrik/work/` store keeps its open work there (`python3 scripts/work.py`;
> `docs/reference/work-tracking.md`): `NEXT:` names the item id (`W-` and 8 hex) when one exists, a
> DECISION block the Stop hook accepts becomes an `awaiting-operator` item on its own, and the agent the
> operator answers closes it with `work.py answer <id> --note "<their words>"`. Item files are ordinary
> files: commit the ones your verbs or your `NEXT:` lines changed with your task. `NEXT: none — terminal` stays legal and
> nothing counts, scores or rewards items (D-392).

In the template the only change is `(hub D-392)` for `(D-392)`, the fleet copy's convention for a hub id.
It adds no gate and no Stop-hook check: D-392 refuses a NEXT gate.

DO-NOT: any other contract text; the duplicate-section cleanup (routed elsewhere).

Depends: T04, T05, T06
Parallel: ⚡
Complexity: never-route
Gate: .venv/bin/python -m pytest tests/test_work_contract_rule.py tests/test_governance_template_split.py -q
Docs: CLAUDE.md, templates/governance/CLAUDE.md (a governance-sync path — the merge distributes)

## Touches
- templates/governance/CLAUDE.md — PRIMARY PATH
- CLAUDE.md
- tests/test_work_contract_rule.py (new)

## Behavior Contract
- **Given** the merged contracts, **When** each `## ⚠️ FINAL OUTPUT` section is isolated (one in the hub, two in the template), **Then** each holds the work-items paragraph exactly once, after the `DONE:`/`NEXT:` discipline paragraph (spec § Documentation landing sites)
- **Given** the paragraph, **When** its text is compared across the three copies, **Then** they are identical except the template's `hub D-392` for the hub's `D-392` (spec § Documentation landing sites)
- **Given** the merged contracts, **When** the governance parity suite runs, **Then** it stays green (tests/test_governance_template_split.py:1122)

## Context Files
- .windsurf/rules/core/40-documentation.md
- docs/development/plans/2026-09-24-plan-2-work-tracking/T01b-claims-and-hook-api.md — the `answer` verb the paragraph names
