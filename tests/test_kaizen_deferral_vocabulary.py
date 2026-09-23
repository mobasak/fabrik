"""T01b: the kaizen vocabulary carries `decision_block` and `deferral` (spec § Contract
deltas; A-O19).

Both additions are inert until T03 wires the hook to emit them — this ticket only
proves the vocabulary itself, and that the existing causes it sits beside survive.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "sysadmin"))

import kaizen_collect_v2  # noqa: E402
import kaizen_events  # noqa: E402


def test_decision_block_is_a_registered_event_type() -> None:
    """`decision_block` (carrying `ground`) must be in EVENT_TYPES or emit() warns on
    every line the hook writes for it (kaizen_events.py:559-560)."""
    assert "decision_block" in kaizen_events.EVENT_TYPES


def test_deferral_is_a_premature_stop_cause() -> None:
    """T03 relabels today's permission stall and every DEFERRAL from
    `cause="promise-stall"` to `cause="deferral"` — PREMATURE_CAUSES must include it
    or kaizen_outcomes.py silently drops those stops from the metric (review round 2,
    A-O19)."""
    assert "deferral" in kaizen_collect_v2.PREMATURE_CAUSES


def test_existing_premature_causes_survive() -> None:
    """The addition must not displace the causes already counted."""
    assert "promise-stall" in kaizen_collect_v2.PREMATURE_CAUSES
    assert "run-record" in kaizen_collect_v2.PREMATURE_CAUSES
