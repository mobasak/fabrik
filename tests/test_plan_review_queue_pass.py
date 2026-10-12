"""/fabrik-plan-review feedback queue answered in one pass (D-735): the panel's ACCEPTED delta round, recorded.

The rule lives in the shared design-critique fragment; the advisory it calls expected is executed against command_run.
"""

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAG = ROOT / "commands" / "_fragments" / "design-critique.md"


def _accepted_clause() -> str:
    text = re.sub(r"\s+", " ", FRAG.read_text())
    start = text.index("in spec-review and plan-review it re-opens the loop")
    return text[start : text.index("in `/fabrik-task`", start)]


def test_the_accepted_delta_round_is_recorded_and_its_advisory_expected() -> None:
    """Row 1791770042 (and spec-review's 1791303387): the delta is the next Pass, slices restated, advisory expected."""
    clause = _accepted_clause()
    assert (
        "recorded as the next Pass with every slice an earlier round stated re-stated in `--slices`"
        in clause
    )
    assert (
        "an OSCILLATING advisory naming that round's count after an earlier 0 is expected there, not drift"
        in clause
    )


def test_the_advisory_the_clause_expects_is_what_command_run_prints() -> None:
    """A quiet round then a panel delta confirming k: from round 5 the advisory on that round names `0 → k`."""
    spec = importlib.util.spec_from_file_location(
        "command_run", ROOT / "scripts" / "command_run.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    warning = mod.convergence_warning([5, 3, 1, 0, 4])
    assert "OSCILLATING" in warning and "0 → 4" in warning
    assert (
        mod.convergence_warning([3, 0, 4]) == ""
    )  # below the heuristic's minimum rounds it stays silent
