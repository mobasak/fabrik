"""/fabrik-plan-review feedback queue answered in one pass (D-735): the panel's ACCEPTED delta round, recorded.

The rule lives in the shared design-critique fragment, inside the clause scoped to spec-review and plan-review.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAG = ROOT / "commands" / "_fragments" / "design-critique.md"


def test_the_accepted_delta_round_is_recorded_and_its_advisory_expected() -> None:
    """Row 1791770042 (and spec-review's 1791303387): the delta is the next Pass, slices restated, 0->k->0 expected."""
    text = re.sub(r"\s+", " ", FRAG.read_text())
    start = text.index("in spec-review and plan-review it re-opens the loop")
    clause = text[start : text.index("in `/fabrik-task`", start)]
    assert (
        "it is recorded as the next Pass with every round-1 slice re-stated in `--slices`" in clause
    )
    assert (
        "the oscillation advisory that round may print (0 → k → 0) is expected there, not drift"
        in clause
    )
