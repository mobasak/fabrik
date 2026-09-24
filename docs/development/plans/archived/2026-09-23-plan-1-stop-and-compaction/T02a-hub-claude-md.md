# T02a — hub `CLAUDE.md`: the DECISION block, the bar bullet, `# Compact instructions`

## Scope
Implements spec § C2 (the DECISION block's one home is § FINAL OUTPUT, with two examples — graft G-c), § C4 (`# Compact instructions`) and § Contract deltas (the `operator-decision-bar` bullet names the block; the no-fresh-session sentence, D-374). The "`NEXT: operator decision` HAS A BAR" paragraph (`CLAUDE.md:661`) keeps every rule it states — the three grounds as `gate · underivable · owned` (D-054 kept whole, D-372) — and loses only the narrative the hook now enforces (D-331: no rule lost). DO-NOT: touch `templates/governance/CLAUDE.md` (T02b); reword any UNIVERSAL governance-marker anchor (the `operator-decision-bar` anchor text stays byte-identical, `CLAUDE.md:385`); change any other section.

Depends: —
Parallel: ⚡
Complexity: simple
Gate: uv run pytest tests/test_governance_template_split.py -q
Docs: CHANGELOG (Deltas)

## Touches
- CLAUDE.md — PRIMARY PATH
- tests/test_governance_template_split.py

## Behavior Contract
- **Given** hub `CLAUDE.md`, **When** T02a lands, **Then** § FINAL OUTPUT carries the DECISION block with one legitimate and one refused example, the `operator-decision-bar` bullet keeps its anchor and names the block, and a `# Compact instructions` section lists the five things a summary must carry (spec § C2, § C4)

## Steps (the coder's order)
1. Red first: in `tests/test_governance_template_split.py`, add a hub-side grader: § FINAL OUTPUT (`CLAUDE.md:631`) contains `DECISION NEEDED (ground: gate|underivable|owned)` and the four labelled lines; the section contains exactly two example blocks, one marked legitimate and one refused; the `operator-decision-bar` bullet (`CLAUDE.md:385`) still contains its anchor substring verbatim and now contains `DECISION NEEDED`; a heading `# Compact instructions` exists whose body names the live command and its terminal, the file and plan/spec paths, the operator's rulings in their words, the pending DECISION block and the last `NEXT:`, plus "never summarise a pending operator question as settled". Watch it FAIL.
2. Write the DECISION block and its grounds text (spec § C2 verbatim for the field list and the three grounds with `asked:`/`scope:`) into the HAS A BAR paragraph at `CLAUDE.md:661`; keep the paragraph's rules, cut its story to one sentence per rule.
3. Add the two examples beside it: legitimate — `ground: gate`, a deploy; refused — an (a)/(b) ordering of two agreed tasks, with the one-line reason it is refused.
4. Edit the `:385` bullet's trailing description to name the block, anchor untouched.
5. Add `# Compact instructions` as a top-level heading at the end of the file (the summarizer reads the root CLAUDE.md, spec E5), with the five lines and the settled-question sentence, and the sentence "Context is never a reason to stop, and a fresh session is never the remedy" (D-374).
6. Gate green; CHANGELOG line into the Deltas block.
7. `/fabrik-review` on this ticket's changed surface to a coverage-adjudicated exit; every finding FIXED or REFUTED.
8. Commit with explicit pathspecs + provenance trailers (`Agent-Role: subagent`, `Agent-Task: T02a`).

## Context Files
- .windsurf/rules/core/40-documentation.md
- CLAUDE.md
- docs/superpowers/specs/2026-09-23-stop-and-compaction-enforcement-design.md
- tests/test_governance_template_split.py
