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


def test_three_copies_identical_except_hub_prefix_on_the_decision_id() -> None:
    hub = _work_paragraph(_sections(HUB)[0])
    copies = [_work_paragraph(s) for s in _sections(TEMPLATE)]
    assert "(D-392)" in hub and "hub D-392" not in hub
    for copy in copies:
        assert "(hub D-392)" in copy
        assert copy.replace("(hub D-392)", "(D-392)") == hub


def test_paragraph_names_the_answer_verb_and_keeps_next_none_legal() -> None:
    hub = _work_paragraph(_sections(HUB)[0])
    assert "work.py answer <id> --note" in hub
    assert "`NEXT: none — terminal` stays legal" in hub
    assert "`awaiting-operator`" in hub
