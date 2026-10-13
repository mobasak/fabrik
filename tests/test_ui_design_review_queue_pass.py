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
    assert "§ Forms and Inline Editing, § Forms (Accessibility) or § Permissions UX" in axes
    assert "§ Forms (Accessibility) under § Accessibility (Enriched)" in p5
    headings = re.findall(r"^#{2,3} (.+)$", TEMPLATE.read_text(), re.M)
    for name in ("Forms and Inline Editing", "Permissions UX", "Forms (Accessibility)", "Accessibility (Enriched)"):
        assert name in headings, name
    p2 = _section(REVIEW, "## Phase 2", "## Phase 3")
    assert "form controls, where the screen has forms" in p2


def test_built_navigation_grounds_ia_claims() -> None:
    """Row 1790728892."""
    axes = _section(REVIEW, "## Phase 1", "## Phase 2")
    assert "its navigation is a fifth binding source, read this session: ground each menu/IA claim against it" in axes


def test_trimmed_seats_carry_several_axes_and_report_the_rest() -> None:
    """Row 1790706010."""
    axes = _section(REVIEW, "## Phase 1", "## Phase 2")
    assert "dispatch exactly the seats it prints, one axis each; the seatless axes are named" in axes
    assert "swept by further full-pass waves before any delta pass" in axes
    assert "reports the screens or sections it did not reach" in axes


def test_cross_references_resolve_to_the_design_they_name() -> None:
    """Row 1789036381."""
    p2 = _section(REVIEW, "## Phase 2", "## Phase 3")
    assert "**Every cross-reference resolves to the DESIGN it names**" in p2


def test_an_in_loop_edit_is_not_an_in_place_edit_finding() -> None:
    """Row 1791028573."""
    conv = _section(REVIEW, "## Convergence", "## After the attestation")
    assert "this review made is not an in-place-edit finding" in conv
    assert "The bump is the LAST edit, made before the closing round" in conv
    p2 = _section(REVIEW, "## Phase 2", "## Phase 3")
    assert "owed by the orchestrator, not a seat finding" in p2


def test_seats_name_the_ranges_they_read_over_the_ceiling() -> None:
    """Row 1789038515."""
    p0 = _section(REVIEW, "## Phase 0", "## Phase 1")
    assert "names the line ranges it read; a range no seat names is unread" in p0
