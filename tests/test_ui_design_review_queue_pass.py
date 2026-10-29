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
    headings = re.findall(r"^#{2,3} (.+)$", TEMPLATE.read_text(), re.M)
    for name in ("Forms and Inline Editing", "Permissions UX", "Forms (Accessibility)", "Accessibility (Enriched)"):
        assert name in headings, name
