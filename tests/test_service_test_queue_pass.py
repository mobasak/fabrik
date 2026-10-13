"""/fabrik-service-test feedback queue answered in one pass (D-735, D-771).

The NOT-QUIET example the cert-execution fragment gives is run through the grader's own NOT_QUIET
pattern, together with the two shapes the fragment says it refuses.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAG = ROOT / "commands" / "_fragments" / "cert-execution.md"
sys.path.insert(0, str(ROOT / "scripts" / "enforcement"))

import check_review_coverage  # noqa: E402


def test_the_not_quiet_example_is_the_line_the_grader_accepts() -> None:
    """Row 1789492795 (second half): one literal accepted declaration line."""
    text = FRAG.read_text()
    example = re.search(r"``(ledger: \*\*`NOT-QUIET \(routes outstanding\)`\*\*)``", text).group(1)
    assert check_review_coverage.NOT_QUIET.search(example)
    assert not check_review_coverage.NOT_QUIET.search("NOT-QUIET (routes outstanding) — see RESUME")
    assert not check_review_coverage.NOT_QUIET.search("NOT-QUIET rows must name a RESUME block")
