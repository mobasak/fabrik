# AFTER-EDIT: ../rank_task_subagents.py
"""G2 — the provider-stall signal, and the incident floor that an earlier design had backwards.

`capped` conflates a provider that streamed nothing (0 turns, $0 — theirs) with a run that hit OUR
`max_turns` ceiling (ours). Only the first is a model signal. These tests pin the RULE, not today's
roster, so a future sweep cannot quietly restore a sampling-breadth floor.
"""

from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS = TESTS_DIR.parent
sys.path.insert(0, str(SCRIPTS))

from rank_task_subagents import (  # noqa: E402
    _STALL_MIN_DAYS,
    _STALL_MIN_SPAN_DAYS,
    STALL_QUERY,
    stall_signal,
)


def test_two_incidents_six_weeks_apart_are_routable():
    """The case the earlier design would have SUPPRESSED. stepfun/step-3.5-flash: 20 stalls of 60,
    on two days that are 46 days apart. Two independent incidents is stronger evidence than a dense
    single-day sample, not weaker."""
    rate, routable = stall_signal(20, 60, 2, 46)
    assert round(rate, 1) == 33.3
    assert routable is True


def test_a_single_incident_is_displayed_but_never_routed():
    """poolside/laguna-m.1: 19.3% — higher than minimax-m3's 6.4% — but all on ONE day. One outage
    must not demote a model, which is the `max_price` mistake at a new layer."""
    rate, routable = stall_signal(11, 57, 1, 0)
    assert round(rate, 1) == 19.3, "the rate is still computed and shown"
    assert routable is False, "a single incident must never route"


def test_a_low_rate_reproduced_across_many_incidents_is_routable():
    """minimax-m3: only 6.4%, but 5 stall days spanning 56 — a real, persistent property."""
    _, routable = stall_signal(44, 688, 5, 56)
    assert routable is True


def test_two_days_close_together_do_not_qualify():
    """Two consecutive days is one incident wearing two dates — the span floor is what catches it."""
    _, routable = stall_signal(20, 60, 2, 1)
    assert routable is False


def test_zero_stalls_is_never_routable_and_never_divides_by_zero():
    assert stall_signal(0, 60, 0, 0) == (0.0, False)
    assert stall_signal(0, 0, 0, 0) == (0.0, False)


def test_the_floors_are_incident_shaped_not_breadth_shaped():
    """If someone later raises _STALL_MIN_DAYS to 3+ without a span, the reproduced 2-day/46-apart
    signals silently vanish. The pairing is the design."""
    assert _STALL_MIN_DAYS == 2
    assert _STALL_MIN_SPAN_DAYS == 7


def test_the_query_states_its_denominator():
    """A rate without its population is not routed on — the plan's own Global Constraint. Blank-status
    rows (2,727 of them) and `scored` quality deltas must both be excluded, explicitly."""
    assert "status <> ''" in STALL_QUERY
    assert "status <> 'scored'" in STALL_QUERY
    assert "coalesce(turns, 0) = 0" in STALL_QUERY, (
        "the stall predicate must be NULL-safe — every stalled row carries turns/cost NULL, not 0"
    )
