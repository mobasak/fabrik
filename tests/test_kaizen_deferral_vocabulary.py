"""T01b: the kaizen vocabulary carries `decision_block` and `deferral` (spec § Contract
deltas; A-O19).

Both additions are inert until T03 wires the hook to emit them — this ticket only
proves the vocabulary itself, and that the existing causes it sits beside survive.

Review round 1 (S1/H1/H2/O1/O3/O6/O4): the premature_stop_rate registry formula and
its MetricResult detail are HUMAN-FACING TEXT that feeds `_def_hash` — a hand-typed
`{run-record, promise-stall}` naming only two of the three members would silently
widen the counted population while the definition hash stayed the same, splicing the
published series. This file also proves the REAL metric counts a `deferral` cause,
and that `kaizen_events.emit("decision_block", ...)` writes without the
unknown-event warning.
"""

from __future__ import annotations

import io
import re
import sys
from contextlib import redirect_stderr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "sysadmin"))

import kaizen_collect_v2  # noqa: E402
import kaizen_events  # noqa: E402


@pytest.fixture
def _isolated_events_dir(tmp_path, monkeypatch):
    """Every test writes into its own events dir and never the operator's real one
    (same isolation pattern as tests/test_kaizen_events.py)."""
    d = tmp_path / "events"
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(d))
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    kaizen_events.reset_cache()
    yield d
    kaizen_events.reset_cache()


def test_decision_block_is_a_registered_event_type() -> None:
    """`decision_block` (carrying `ground`) must be in EVENT_TYPES or emit() warns on
    every line the hook writes for it (kaizen_events.py:559-560)."""
    assert "decision_block" in kaizen_events.EVENT_TYPES


def test_decision_block_emits_without_unknown_event_warning(_isolated_events_dir) -> None:
    """The hook's `decision_block` emit (T03) must never trip the unknown-event warn —
    proven red-on-revert: with `decision_block` pulled out of EVENT_TYPES this same
    call prints `kaizen_events: unknown event type 'decision_block' (emitted
    anyway)` to stderr; with it registered, stderr is empty."""
    buf = io.StringIO()
    with redirect_stderr(buf):
        ok = kaizen_events.emit("decision_block", sid="s1", ground="gate")
    assert ok
    assert "unknown event type" not in buf.getvalue()


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


def test_premature_stop_rate_formula_names_every_premature_cause() -> None:
    """The registry formula must RENDER PREMATURE_CAUSES, never hand-type a subset —
    a hand-typed `{run-record, promise-stall}` would under-count the population that
    `_def_hash` signs for, silently splicing the published series (S1/H1/H2/O1/O3)."""
    formula = kaizen_collect_v2.registry()["premature_stop_rate"]["formula"]
    for cause in kaizen_collect_v2.PREMATURE_CAUSES:
        assert cause in formula, f"formula text is missing premature cause {cause!r}"


def test_premature_stop_rate_detail_names_every_premature_cause() -> None:
    """The MetricResult detail rendered by compute_metrics must ALSO name every
    member — the formula and the detail are two independent hand-typed strings and
    both drifted before this fix (O6)."""
    row = {
        "events": {"stop_pass": 1, "stop_block": 1},
        "stop_causes": {"run-record": 1},
    }
    detail = kaizen_collect_v2.compute_metrics([row], holes=0)["premature_stop_rate"].detail
    for cause in kaizen_collect_v2.PREMATURE_CAUSES:
        assert cause in detail, f"detail text is missing premature cause {cause!r}"


def test_premature_stop_rate_counts_a_deferral_cause() -> None:
    """O4: drive the REAL metric — a derived row whose stop_block cause is
    `deferral` must land in premature_stop_rate's numerator. Proven red-on-revert:
    with PREMATURE_CAUSES reverted to its pre-T01b two members the same row scores
    numerator 0; with `deferral` a member it scores 1."""
    row = {
        "events": {"stop_pass": 0, "stop_block": 1},
        "stop_causes": {"deferral": 1},
    }
    result = kaizen_collect_v2.compute_metrics([row], holes=0)["premature_stop_rate"]
    assert result.numerator == 1
    assert result.denominator == 1


def test_every_event_the_stop_hook_emits_is_registered() -> None:
    """A-S1/A-S2 (whole-plan review, T06): an unregistered name warns "unknown event type" on
    every emit, into a stderr the hook silences — so the only place the gap shows is here."""
    hook_src = (
        Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
    ).read_text(encoding="utf-8")
    names = set(re.findall(r'_kaizen\(\s*"([a-z_]+)"', hook_src))
    assert {"stop_block", "anchor_harvest", "stop_allowed_quota_hold"} <= names, names
    assert names - set(kaizen_events.EVENT_TYPES) == set()
