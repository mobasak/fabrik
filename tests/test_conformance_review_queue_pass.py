"""/fabrik-conformance-review feedback queue answered in one pass (D-735, D-768).

Each test pins one sentence in the phase that owns it; the ROUTED(n) test also checks the token the
coverage gate parses is the one the sentence defines.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "commands" / "_sources" / "fabrik-conformance-review.md"


def _phase(start: str, end: str) -> str:
    text = re.sub(r"\s+", " ", SRC.read_text())
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def test_spot_runs_print_their_target_and_read_fixtures_for_writes() -> None:
    """Rows 1790887637, 1790886150."""
    p1 = _phase("## PHASE 1", "## PHASE 2")
    assert "print the database or service target the suite's seeder, provisioner or fixtures actually resolve" in p1
    assert "call a run read-only only after reading its shared fixtures for writes" in p1


def test_a_class_re_sweep_stays_inside_the_inventory() -> None:
    """Row 1788875405."""
    p4 = _phase("## PHASE 4", "## OUTPUT")
    assert "an instance found outside it is recorded and routed to the spec that owns it, never counted" in p4


def test_routed_n_says_what_it_counts() -> None:
    """Row 1790889401: the count is the author's; the gate parses the token."""
    p4 = _phase("## PHASE 4", "## OUTPUT")
    assert "`n` counts the work items and mails the row's findings were routed to, pre-existing ones included" in p4
    assert "an operator gate is not a route (it stays open)" in p4
    gate = (ROOT / "scripts" / "enforcement" / "check_review_coverage.py").read_text()
    assert r"ROUTED\s*\(?\d*\)?" in gate
