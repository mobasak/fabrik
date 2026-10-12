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


def test_one_bump_and_one_row_per_review_run() -> None:
    """Row 1791511001."""
    assert "Bump at the run's first edit and keep editing under that version until the closing round re-freezes it — one bump and one row per review run, a hold and its resume included" in _norm()
