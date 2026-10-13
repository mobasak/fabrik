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
    assert "the run's first edit bumps `Version`, every later edit stays under that version, and the closing round re-freezes it" in _norm()
    assert "one bump and one row per review run, a run closed `blocked` and resumed included, never a bump per round" in _norm()


def test_the_description_names_every_axis() -> None:
    """Mail 01M4S7EX4S: the frontmatter listed 7 of the 8 axes, without E2 and F."""
    head = SRC.read_text().split("\n---\n", 1)[0]
    for axis in ("Success-Criterion tracing", "persona completeness", "SECOND-ACTOR completeness",
                 "async-boundary gap states", "[PRIMARY PATH]", "per-call resilience",
                 "life-cycle arcs (UI types)", "discipline + exclusions", "contract-input routing"):
        assert axis in head, axis
