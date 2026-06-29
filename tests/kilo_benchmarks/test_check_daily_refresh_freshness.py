"""Regression tests for check_daily_refresh_freshness.py (Phase 5 heartbeat)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_daily_refresh_freshness", SCRIPT_DIR / "check_daily_refresh_freshness.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_first_run_when_file_missing(tmp_path: Path) -> None:
    """No timestamp file → first_run status (no alert)."""
    mod = _load()
    missing = tmp_path / "nope.txt"
    result = mod.check(missing, max_age_hours=36)
    assert result["status"] == "first_run"
    assert result["age_hours"] is None
    assert result["timestamp"] is None


def test_fresh_when_recent(tmp_path: Path) -> None:
    """Timestamp within max_age → fresh (no alert)."""
    mod = _load()
    f = tmp_path / "ts.txt"
    now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
    recent = now - timedelta(hours=24)  # 24h < 36h threshold
    f.write_text(recent.isoformat())
    result = mod.check(f, max_age_hours=36, now=now)
    assert result["status"] == "fresh"
    assert abs(result["age_hours"] - 24.0) < 0.1


def test_stale_when_older_than_threshold(tmp_path: Path) -> None:
    """Timestamp older than max_age → stale (alert-eligible)."""
    mod = _load()
    f = tmp_path / "ts.txt"
    now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
    old = now - timedelta(hours=48)  # 48h > 36h threshold
    f.write_text(old.isoformat())
    result = mod.check(f, max_age_hours=36, now=now)
    assert result["status"] == "stale"
    assert abs(result["age_hours"] - 48.0) < 0.1


def test_boundary_exact_threshold(tmp_path: Path) -> None:
    """Exactly at the threshold counts as fresh (off-by-one guard)."""
    mod = _load()
    f = tmp_path / "ts.txt"
    now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
    exactly = now - timedelta(hours=36)
    f.write_text(exactly.isoformat())
    result = mod.check(f, max_age_hours=36, now=now)
    assert result["status"] == "fresh", "exactly at threshold should be fresh, not stale"


def test_naive_timestamp_treated_as_utc(tmp_path: Path) -> None:
    """If the file has a naive ISO timestamp (no tz suffix), interpret as UTC."""
    mod = _load()
    f = tmp_path / "ts.txt"
    f.write_text("2026-06-30T11:00:00")  # naive
    now = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)
    result = mod.check(f, max_age_hours=36, now=now)
    assert result["status"] == "fresh"
    assert abs(result["age_hours"] - 1.0) < 0.1


def test_corrupt_timestamp_treated_as_first_run(tmp_path: Path) -> None:
    """A garbage timestamp file is treated as first-run (defensive)."""
    mod = _load()
    f = tmp_path / "ts.txt"
    f.write_text("not a date")
    result = mod.check(f, max_age_hours=36)
    assert result["status"] == "first_run"


def test_empty_file_treated_as_first_run(tmp_path: Path) -> None:
    mod = _load()
    f = tmp_path / "ts.txt"
    f.write_text("")
    result = mod.check(f, max_age_hours=36)
    assert result["status"] == "first_run"


def test_maybe_alert_no_op_when_fresh() -> None:
    mod = _load()
    fired = mod.maybe_alert({
        "status": "fresh", "age_hours": 5.0,
        "timestamp": "2026-06-30T07:00:00+00:00", "threshold_hours": 36,
    })
    assert fired is False


def test_maybe_alert_no_op_when_first_run() -> None:
    mod = _load()
    fired = mod.maybe_alert({
        "status": "first_run", "age_hours": None,
        "timestamp": None, "threshold_hours": 36,
    })
    assert fired is False


def test_maybe_alert_swallows_send_alert_exception(capsys) -> None:
    """Adversarial review of e586de77: send_alert was called without
    try/except. If alerting raises (network blip, malformed config), the
    heartbeat script would crash and daily_refresh.sh's wrapper `|| echo`
    would mask that crash as a generic "non-fatal" error. Now wrapped:
    on exception, log to stderr + return False so the heartbeat exits
    cleanly."""
    mod = _load()
    # Inject a fake `alerting` module that raises on send_alert
    import types
    fake = types.ModuleType("alerting")
    def _boom(**kw):
        raise RuntimeError("simulated alerting failure")
    fake.send_alert = _boom  # type: ignore[attr-defined]
    sys.modules["alerting"] = fake
    try:
        fired = mod.maybe_alert({
            "status": "stale", "age_hours": 48.0,
            "timestamp": "2026-06-28T00:00:00+00:00", "threshold_hours": 36,
        })
        assert fired is False
        # The error should be logged to stderr
        captured = capsys.readouterr()
        assert "send_alert raised" in captured.err
        assert "simulated alerting failure" in captured.err
    finally:
        del sys.modules["alerting"]
