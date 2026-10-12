"""/fabrik-conformance-review feedback queue answered in one pass (D-735, D-768).

Each test pins one sentence in the phase that owns it; the operator-gate token the text names is run
through the coverage gate's own VERDICT pattern, so a row carrying it terminates.
"""

import re
import sys
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
    assert "print the database or service target the suite's seeder, provisioner or fixtures actually resolve and stop unless it is the throwaway one" in p1
    assert "call a run read-only only after reading its shared fixtures for writes" in p1


def test_a_class_re_sweep_stays_inside_the_inventory() -> None:
    """Row 1788875405."""
    p4 = _phase("## PHASE 4", "## OUTPUT")
    assert "routed by PHASE 3's table to its owning command (a work item or a mail), never counted" in p4


def test_routed_n_says_what_it_counts() -> None:
    """Row 1790889401: the count is the author's; the gate parses the token."""
    p4 = _phase("## PHASE 4", "## OUTPUT")
    assert "`n` counts the work items and mails the row's findings were routed to, pre-existing ones included" in p4
    token = re.search(r"`(RECORDED — measured \(operator gate: [^`]+\))`", p4).group(1)
    sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))
    import check_review_coverage

    assert check_review_coverage.VERDICT.search(token)
    assert check_review_coverage.VERDICT.search("ROUTED(3)")
