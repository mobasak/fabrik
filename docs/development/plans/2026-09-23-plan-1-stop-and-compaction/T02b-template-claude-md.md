# T02b — `templates/governance/CLAUDE.md`: the same, in every § FINAL OUTPUT copy

## Scope
Implements spec § Contract deltas for the fleet contract: the same DECISION block, examples, bar-bullet wording and `# Compact instructions` as T02a, in EVERY copy — the template carries § FINAL OUTPUT twice at the base (`templates/governance/CLAUDE.md:629`, `:672`) and "HAS A BAR" at `:359` (the index line), `:650` and `:702`. The duplication itself is not removed here: it is routed to `docs/STRATEGIC_BACKLOG.md` by T06. DO-NOT: edit hub `CLAUDE.md` (T02a); change the template's sanctioned divergences from the hub (`tests/test_governance_template_split.py` lists them); run the governance sync (T06 does, once).

Depends: T02a
Parallel: ⛓️
Complexity: simple
Gate: uv run pytest tests/test_governance_template_split.py -q
Docs: CHANGELOG (Deltas)

## Touches
- templates/governance/CLAUDE.md — PRIMARY PATH
- tests/test_governance_template_split.py

## Behavior Contract
- **Given** `templates/governance/CLAUDE.md`, **When** T02b lands, **Then** every § FINAL OUTPUT copy and the index line carry the same DECISION block, examples and `# Compact instructions` as the hub, byte-identical where the parity test compares (spec § Contract deltas)

## Steps (the coder's order)
1. Red first: extend T02a's grader to the template, asserting the DECISION block text is byte-identical to the hub's in BOTH § FINAL OUTPUT copies (`:629`, `:672`), the index line at `:359` names the block, and `# Compact instructions` matches the hub's. Watch it FAIL.
2. Apply T02a's text to `:650` and `:702`, the `:359` line and the end of the file.
3. Gate green; CHANGELOG line into the Deltas block.
4. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit; every finding FIXED or REFUTED.
5. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T02b`).

## Context Files
- .windsurf/rules/core/40-documentation.md
- templates/governance/CLAUDE.md
- CLAUDE.md
- tests/test_governance_template_split.py
