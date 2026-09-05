"""check_review_coverage — BOTH sanctioned BLOCKED exits are evidenced sections.

/fabrik-review sanctions two BLOCKED exits: the per-finding escalation (a finding that
survived 3 consecutive fix attempts) and the loop-level stop (`## BLOCKED: NON-CONVERGENCE`
naming the suspected foundation error). `_blocked_sections` knew only the first, so an honest
loop stop graded as an unconverged review and the exit-round message offered three
dispositions that were all wrong for it (web-ecommerce-factory 01M1QHAC, 2026-09-05).
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "crc", ROOT / "scripts" / "enforcement" / "check_review_coverage.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_per_finding_three_attempts_section_still_counts():
    crc = _load()
    text = (
        "# Review\n\n## BLOCKED: T03 guard\n"
        "3 consecutive fix attempts failed: rounds 4, 5 and 6 each re-raised it.\n"
    )
    assert crc._blocked_sections(text) == 1


def test_non_convergence_section_naming_a_foundation_error_counts():
    crc = _load()
    text = (
        "# Review\n\n## BLOCKED: NON-CONVERGENCE\n"
        "Rounds 7, 8 and 9 each raised fresh HIGHs (new: 3, 3, 3). Suspected foundation "
        "error: the contract names a class the grammar cannot express.\n"
    )
    assert crc._blocked_sections(text) == 1, (
        "the loop-level exit is a sanctioned, evidenced BLOCKED"
    )


def test_non_convergence_without_a_named_foundation_error_is_not_evidence():
    crc = _load()
    text = "# Review\n\n## BLOCKED: NON-CONVERGENCE\nThe loop oscillated; giving up.\n"
    assert crc._blocked_sections(text) == 0, (
        "the command mandates NAMING the suspected foundation error — the bare heading is a claim"
    )


def test_exit_round_message_names_the_loop_level_exit():
    """The message that fires on a committed non-quiet review must offer the third,
    correct disposition — an agent following the old three either lied (IN-PROGRESS on a
    stopped loop) or forged a per-finding escalation."""
    crc = _load()
    src = inspect.getsource(crc)
    i = src.index("COMMITTED with a non-quiet exit round")
    window = src[i : i + 900]
    assert "NON-CONVERGENCE" in window and "foundation" in window
