# AFTER-EDIT: check_daily_refresh_freshness.py, docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md
"""Phase A.0 — the ranker's OUTPUT must be watched, not just the pipeline heartbeat.

The hole this closes: `daily_refresh.sh` writes `daily_refresh_last_success.txt` even when
`rank_task_subagents` exits non-zero (its call site ends `|| true`; the script has no
`set -e`), and since Phase A.0 a BROKEN flywheel read deliberately KEEPS the previous doc
instead of overwriting it with a stub. Both behaviours are correct individually, and
together they make a permanently broken flywheel completely silent while the fleet drifts
onto an ever-staler selection doc — past select.py's 14-day gate every vendored
`pick_models` falls back to the baked-in `_TABLE`.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_daily_refresh_freshness as chk  # noqa: E402

NOW = datetime(2026, 8, 13, tzinfo=UTC)


def _doc(tmp_path: Path, body: str) -> Path:
    f = tmp_path / "TASK_SUBAGENT_SELECTION.md"
    f.write_text(body, encoding="utf-8")
    return f


def test_a_fresh_doc_is_fresh(tmp_path):
    d = _doc(tmp_path, "Last refresh: 2026-08-12\n\n| m | s |\n")
    assert chk.check_selection_doc(d, now=NOW)["status"] == "fresh"


def test_a_doc_that_stopped_being_refreshed_is_stale(tmp_path):
    """THE case the pipeline heartbeat cannot see."""
    d = _doc(tmp_path, "Last refresh: 2026-07-20\n\n| m | s |\n")
    r = chk.check_selection_doc(d, now=NOW)
    assert r["status"] == "stale"
    assert r["age_days"] > 3


def test_the_failure_stub_is_reported_even_when_freshly_dated(tmp_path):
    """A stub stamped today is the worst case: it forges freshness past select.py's gate."""
    d = _doc(tmp_path, "Last refresh: 2026-08-13\n\nAGGREGATION FAILED\n")
    assert chk.check_selection_doc(d, now=NOW)["status"] == "stub"


def test_an_undated_doc_is_not_silently_fresh(tmp_path):
    """A renderer change that drops the header must not read as healthy."""
    d = _doc(tmp_path, "# Selection\n\n| m | s |\n")
    assert chk.check_selection_doc(d, now=NOW)["status"] == "undated"


def test_a_far_future_stamp_is_not_silently_fresh(tmp_path):
    """select.py's 14-day gate reads this same date, so a bogus future stamp would make the
    doc look permanently fresh to every vendored pick_models. Local-vs-UTC skew (up to ~1 day)
    is still tolerated."""
    assert chk.check_selection_doc(_doc(tmp_path, "Last refresh: 2099-01-01\n"), now=NOW)[
        "status"
    ] == "future"
    assert chk.check_selection_doc(_doc(tmp_path, "Last refresh: 2026-08-14\n"), now=NOW)[
        "status"
    ] == "fresh", "ordinary local-vs-UTC skew must stay fresh"


def test_a_missing_doc_does_not_alert(tmp_path):
    """A fresh clone / first run is not a failure — the mirror assertion."""
    r = chk.check_selection_doc(tmp_path / "nope.md", now=NOW)
    assert r["status"] == "missing"
    assert chk.maybe_alert_selection_doc(r) is False


def test_alerting_fires_for_every_unhealthy_state(monkeypatch, tmp_path):
    """Every unhealthy state must actually REACH send_alert, driven by the REAL producer.

    The earlier version hand-built `{"status": s, "age_days": 9.0, ...}` for all three
    statuses — a shape `check_selection_doc` only ever emits for "stale". Fed the producer's
    real output, "stub" and "undated" carry `age_days: None` and the alert body raised
    TypeError, so the two worst cases delivered nothing. Hand-written inputs the pipeline
    never emits is precisely the anti-pattern this suite exists to replace, so drive it from
    real files on disk.
    """
    sent = []
    mod = type(sys)("alerting")
    mod.send_alert = lambda **kw: sent.append(kw) or True
    monkeypatch.setitem(sys.modules, "alerting", mod)

    cases = {
        "stale": "Last refresh: 2026-07-20\n\n| m | s |\n",
        "stub": "Last refresh: 2026-08-13\n\nAGGREGATION FAILED\n",
        "undated": "# Selection\n\n| m | s |\n",
    }
    for expected, body in cases.items():
        result = chk.check_selection_doc(_doc(tmp_path, body), now=NOW)
        assert result["status"] == expected
        assert chk.maybe_alert_selection_doc(result), f"{expected} must fire an alert"

    assert len(sent) == 3
    assert all(k["severity"] == "critical" for k in sent)
    assert all(k["body"] for k in sent), "an empty body is a silent alert"


def test_the_whole_cli_survives_every_state(tmp_path, monkeypatch):
    """End-to-end: main() must exit 0 for each state, not raise.

    The crash surfaced only through main(); daily_refresh.sh swallows a non-zero exit into a
    logfile with no MAILTO, so an exception here is invisible in production.
    """
    # Only the pipeline heartbeat is stubbed. maybe_alert_selection_doc is deliberately NOT
    # mocked — mocking it removed the exact call that raised, making this test decorative.
    # `alerting` is stubbed instead, so the real body-building code runs.
    monkeypatch.setattr(chk, "maybe_alert", lambda *_a, **_k: False)
    mod = type(sys)("alerting")
    mod.send_alert = lambda **kw: True
    monkeypatch.setitem(sys.modules, "alerting", mod)
    for body in (
        "Last refresh: 2026-07-20\n",
        "AGGREGATION FAILED\n",
        "# no date\n",
        "Last refresh: 2099-01-01\n",
    ):
        doc = _doc(tmp_path, body)
        # NOT --quiet: the print path formats age_days and was itself untested.
        monkeypatch.setattr(sys, "argv", ["x", "--selection-doc", str(doc)])
        assert chk.main() == 0
