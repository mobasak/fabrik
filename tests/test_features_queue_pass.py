"""/fabrik-features feedback queue answered in one pass (D-735, D-765).

Each test pins one sentence in the section that owns it; the plan-template terms the scoped mode names
are checked against the plan command that defines them.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-features.md"
PLAN = ROOT / "commands" / "_sources" / "fabrik-plan-after-chat.md"


def _section(start: str, end: str) -> str:
    text = re.sub(r"\s+", " ", SRC.read_text())
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_early_rows_cite_symbols_and_resolve_work_items() -> None:
    """Rows 1790688007, 1789583713, 1791507475."""
    p0 = _section("## Phase 0", "## Phase 1")
    assert "cites a SYMBOL in a named file (`src/billing.py::charge`), never a line number" in p0
    assert "resolves to `.fabrik/work/W-xxxxxxxx.json`" in p0
    assert "a Planned row's symbol in a named file" in _section("## Guardrails", "{{include:subagents-core}}")


def test_scoped_refresh_names_its_denominator() -> None:
    """Rows 1791028841, 1791015873, 1790950308: the terms it names are the plan template's own."""
    p0 = _section("## Phase 0", "## Phase 1")
    assert "**Scoped REFRESH (after a plan, or one stale section):**" in p0
    assert "every row the plan's Deltas blocks wrote — Planned or not" in p0
    plan = PLAN.read_text()
    assert "## Behavior Contract" in plan and "Deltas block" in plan


def test_rows_cover_every_route_mode_and_point_at_backlog_for_defects() -> None:
    """Rows 1791227229, 1790961162."""
    p2 = _section("## Phase 2", "## Phase 3")
    assert "holds for every mode the route serves — its default and each query-parameter variant" in p2
    assert "a known defect is a pointer to its backlog row or work item, never an enumeration of its cases" in p2


def test_coverage_names_each_population_before_counting() -> None:
    """Row 1790692088."""
    p3 = _section("## Phase 3", "## Guardrails")
    assert "name each denominator's expected population and where it comes from" in p3
