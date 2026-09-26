"""T08 (plan 2026-09-24-plan-2-work-tracking): both contracts carry the short work-items rule.

The hub CLAUDE.md has one § FINAL OUTPUT section, templates/governance/CLAUDE.md has two (a known,
routed duplication pinned by tests/test_governance_template_split.py). Each section must hold the
work-items paragraph exactly once, directly after the `DONE:`/`NEXT:` discipline paragraph, and the
three copies must be identical except the template's `hub D-392` for the hub's `D-392`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HUB = REPO / "CLAUDE.md"
TEMPLATE = REPO / "templates" / "governance" / "CLAUDE.md"

_SECTION_START = "## ⚠️ FINAL OUTPUT"
_MARKER = "**Work items.**"
_DISCIPLINE = "**`DONE:`/`NEXT:`"


def _sections(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split(_SECTION_START)[1:]
    return [p.split("\n## ", 1)[0] for p in parts]


def _paragraphs(section: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", section) if p.strip()]


def _work_paragraph(section: str) -> str:
    paras = _paragraphs(section)
    hits = [i for i, p in enumerate(paras) if p.startswith(_MARKER)]
    assert len(hits) == 1, f"expected the work-items paragraph once, found {len(hits)}"
    assert section.count(_MARKER) == 1, "the work-items marker appears more than once"
    i = hits[0]
    assert i > 0 and _DISCIPLINE in paras[i - 1], (
        "the work-items paragraph must directly follow the DONE:/NEXT: discipline paragraph"
    )
    return " ".join(paras[i].split())


def test_hub_has_one_final_output_section_with_the_paragraph_after_done_next() -> None:
    sections = _sections(HUB)
    assert len(sections) == 1, f"hub: expected 1 § FINAL OUTPUT section, found {len(sections)}"
    _work_paragraph(sections[0])


def test_template_has_the_paragraph_in_both_final_output_copies() -> None:
    sections = _sections(TEMPLATE)
    assert len(sections) == 2, f"template: expected 2 § FINAL OUTPUT copies, found {len(sections)}"
    for section in sections:
        _work_paragraph(section)


# The canonical text, pinned HERE so an identical drift in all three copies still reds. COBRA: the
# cheapest green after a wording change is to paste the new wording below; that edit is a visible
# change of meaning in review, which is the point of pinning it.
_CANONICAL = (
    "**Work items.** A repo with a `.fabrik/work/` store keeps its open work there "
    "(`python3 scripts/work.py`; `docs/reference/work-tracking.md`): `NEXT:` names the item id "
    "(`W-` and 8 lowercase hex) when one exists, a DECISION block the Stop hook accepts becomes an "
    "`awaiting-operator` item on its own, and the agent the operator answers closes it with "
    '`work.py answer <id> --note "<their words>"`. Item files are ordinary files: commit the ones '
    "your verbs changed with your task. End a turn on work with `NEXT: <item id>` to claim that "
    "item for your "
    "session (the first item it names that is open, ready, not a `next` item and held by no "
    "other session); "
    "`mail.py claim` run in the mailbox's own repo creates the mail's item, and `mail.py ack` there "
    "closes it. "
    "`NEXT: none — terminal` stays legal and nothing counts, scores or "
    "rewards items (D-392, D-394)."
)


def _template_form(hub: str) -> str:
    """The two sanctioned substitutions: the fleet sync never ships the hub doc, so projects get
    its absolute hub path; and a hub decision id carries the `hub ` prefix in the fleet copy."""
    return hub.replace(
        "`docs/reference/work-tracking.md`", "`/opt/fabrik/docs/reference/work-tracking.md`"
    ).replace("(D-392, D-394)", "(hub D-392, hub D-394)")


def test_hub_copy_equals_the_pinned_canonical_text() -> None:
    assert _work_paragraph(_sections(HUB)[0]) == _CANONICAL


def test_each_template_copy_equals_canonical_after_the_two_sanctioned_substitutions() -> None:
    expected = _template_form(_CANONICAL)
    assert expected != _CANONICAL, "a substitution no longer applies to the canonical text"
    for copy in (_work_paragraph(s) for s in _sections(TEMPLATE)):
        assert copy == expected
