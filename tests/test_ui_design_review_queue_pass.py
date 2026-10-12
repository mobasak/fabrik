"""/fabrik-ui-design-review feedback queue answered in one pass (D-735, D-764).

Each test pins one sentence in the section that owns it.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "commands" / "_sources" / "fabrik-ui-design-review.md"
DESIGN = ROOT / "commands" / "_sources" / "fabrik-ui-design.md"
TEMPLATE = ROOT / ".windsurf" / "rules" / "core" / "design-system-template.md"


def _section(path: Path, start: str, end: str) -> str:
    text = re.sub(r"\s+", " ", path.read_text())
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_form_controls_follow_the_templates_named_sections() -> None:
    """Row 1790753997: the author pass and axis A both name sections the template really has."""
    p5 = _section(DESIGN, "## Phase 5", "## Phase 6")
    assert "§ Forms and Inline Editing" in p5 and "§ Permissions UX" in p5
    axes = _section(REVIEW, "## Phase 1", "## Phase 2")
    assert "breaks `design-system-template.md` § Forms and Inline Editing or § Permissions UX" in axes
    headings = re.findall(r"^## (.+)$", TEMPLATE.read_text(), re.M)
    assert "Forms and Inline Editing" in headings and "Permissions UX" in headings


def test_built_navigation_grounds_ia_claims() -> None:
    """Row 1790728892."""
    axes = _section(REVIEW, "## Phase 1", "## Phase 2")
    assert "ground each menu/IA claim against the built navigation" in axes


def test_trimmed_seats_carry_several_axes_and_report_the_rest() -> None:
    """Row 1790706010."""
    axes = _section(REVIEW, "## Phase 1", "## Phase 2")
    assert "each seat carries several axes, its brief names them, and it returns the screens or sections" in axes


def test_cross_references_resolve_to_the_design_they_name() -> None:
    """Row 1789036381."""
    p2 = _section(REVIEW, "## Phase 2", "## Phase 3")
    assert "**Every cross-reference resolves to the DESIGN it names**" in p2


def test_an_in_loop_edit_is_not_an_in_place_edit_finding() -> None:
    """Row 1791028573."""
    conv = _section(REVIEW, "## Convergence", "## After the attestation")
    assert "an edit this review made, pending its bump at the closing round, is not an in-place-edit finding" in conv
