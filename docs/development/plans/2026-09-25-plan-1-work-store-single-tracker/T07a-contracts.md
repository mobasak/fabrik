# T07a — The contract sentence in all three copies

## Scope

Implements spec § The delta D7: every copy of the `**Work items.**` paragraph gains one sentence —
end a turn on work with `NEXT: <item id>`, which claims it; claiming a mail creates its item. The
copies are `CLAUDE.md:661` (one, in its § FINAL OUTPUT) and `templates/governance/CLAUDE.md:650` and
`:739` (two, one per § FINAL OUTPUT). The hub copy is pinned byte for byte by `_CANONICAL` at
`tests/test_work_contract_rule.py:59-68`, and both template copies must equal it after exactly the two
sanctioned substitutions `_template_form` encodes (`tests/test_work_contract_rule.py:71-75`: the doc
path gains `/opt/fabrik/`, `D-` becomes `hub D-`). So:

1. Insert the sentence, word for word, after "…and rides your next commit." and before
   "`NEXT: none — terminal` stays legal…", in the hub copy:
   `End a turn on work with \`NEXT: <item id>\`, which claims it for your session; claiming a mail with \`mail.py claim\` creates its item, and \`mail.py ack\` closes it.`
2. Insert the identical sentence at the same place in both template copies (it carries no doc path
   and no D-id, so the two substitutions leave it unchanged).
3. Update `_CANONICAL` to the new wording in the same commit — the pin's own COBRA note
   (`tests/test_work_contract_rule.py:56-58`) names that edit as the visible change of meaning.
4. `scripts/enforcement/check_corpus_weight.py` is an advisory ratchet on both files (never
   `--strict` in the gate); the growth is one sentence per copy, and the D-row the orchestrator mints
   for this plan's merge records it.

The template is a governance-sync path: its merge distributes to ~46 repos at merge, so the full
`/fabrik-review` closes before the merge.

DO-NOT: any other paragraph of either contract; the hub's `docs/reference/work-tracking.md` (T07b).

Depends: T05b
Parallel: ⚡
Complexity: never-route
Gate: .venv/bin/python -m pytest tests/test_work_contract_rule.py tests/test_governance_template_split.py -q
Docs: the three contract copies (spec § Documentation landing sites)

## Touches
- templates/governance/CLAUDE.md — PRIMARY PATH
- CLAUDE.md
- tests/test_work_contract_rule.py

## Behavior Contract
- **Given** the hub contract and the template after this ticket, **When** `tests/test_work_contract_rule.py` runs, **Then** all three copies carry the new sentence at the same place and equal the pinned canonical text after the two sanctioned substitutions (spec § The delta D7)
- **Given** the pinned canonical text reverted to the old wording, **When** the same test runs, **Then** it fails on all three copies (spec § The delta D7)

## Context Files
- .windsurf/rules/core/40-documentation.md
- tests/test_work_contract_rule.py
