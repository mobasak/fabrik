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
    assert "`python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units 7 --mechanical 2` — one unit per axis A–G" in _norm()
    axes = re.findall(r"^\*\*([A-Z])\)", SRC.read_text(), flags=re.M)
    assert axes == list("ABCDEFG")


def test_one_bump_and_one_row_per_review_run() -> None:
    """Row 1791511001."""
    assert "One bump and one row per review run: every round's edits land under the version the closing round re-freezes, never a bump per round" in _norm()
