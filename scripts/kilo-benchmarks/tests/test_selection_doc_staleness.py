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


def test_a_missing_doc_does_not_alert(tmp_path):
    """A fresh clone / first run is not a failure — the mirror assertion."""
    r = chk.check_selection_doc(tmp_path / "nope.md", now=NOW)
    assert r["status"] == "missing"
    assert chk.maybe_alert_selection_doc(r) is False


def test_alerting_fires_for_every_unhealthy_state(monkeypatch):
    """The states must actually reach send_alert — a body-less state would KeyError."""
    sent = []
    monkeypatch.setitem(
        sys.modules, "alerting", type(sys)("alerting")
    )
    sys.modules["alerting"].send_alert = lambda **kw: sent.append(kw) or True
    for status in ("stale", "stub", "undated"):
        assert chk.maybe_alert_selection_doc(
            {"status": status, "age_days": 9.0, "stamped": "2026-07-20", "threshold_days": 3}
        ), f"{status} must fire an alert"
    assert len(sent) == 3
    assert all(k["severity"] == "critical" for k in sent)
