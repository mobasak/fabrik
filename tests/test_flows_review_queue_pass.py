"""/fabrik-flows-review feedback queue answered in one pass (D-735, D-783).

The dispatch line names the exact budget invocation, checked against the axes the file defines; the
re-freeze rule bumps once per review run.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-flows-review.md"


def _norm() -> str:
    return re.sub(r"\s+", " ", SRC.read_text())


def test_the_dispatch_line_names_the_exact_invocation_and_it_counts_the_axes() -> None:
    """Row 1790702929."""
    axes = re.findall(r"^\*\*([A-Z][0-9]*)\)", SRC.read_text(), flags=re.M)
    assert axes == ["A", "B", "C", "D", "E", "E2", "F", "G"]
    assert f"dispatch_headroom.py --units {len(axes)} --mechanical 2 --risky 2` — one unit per axis A–G plus E2" in _norm()


def test_the_description_names_every_axis() -> None:
    """Mail 01M4S7EX4S: the frontmatter named 6 of the 8 lettered axes, without E2 and F."""
    desc = next(line for line in SRC.read_text().splitlines() if line.startswith("description:"))
    for axis in ("Success-Criterion tracing", "persona completeness", "SECOND-ACTOR completeness",
                 "async-boundary gap states", "[PRIMARY PATH]", "per-call resilience",
                 "life-cycle arcs (UI types)", "discipline + exclusions", "cross-artifact truth"):
        assert axis in desc, axis


def test_the_ui_design_review_description_names_axis_f() -> None:
    """Same drift in the sibling: its description listed axes A-E and left out F."""
    src = ROOT / "commands" / "_sources" / "fabrik-ui-design-review.md"
    desc = next(line for line in src.read_text().splitlines() if line.startswith("description:"))
    assert "consistency + internal contradictions" in desc
