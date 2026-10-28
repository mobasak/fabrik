"""Coverage for fabrik.ai.tracker.UsageTracker (hermetic, sqlite under tmp_path)."""

import sqlite3
from datetime import datetime, timedelta

import pytest

from fabrik.ai.tracker import UsageTracker


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "sub" / "dir" / "usage.db")


@pytest.fixture
def tracker(db_path):
    return UsageTracker(db_path)


def _insert(path, *, ts, model="m1", tin=10, tout=5, cost=0.5, project=None, kind="llm"):
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO ai_usage (timestamp, provider, model, tokens_in, tokens_out,"
            " cost_usd, duration_ms, project, kind) VALUES (?,?,?,?,?,?,?,?,?)",
            (ts, "p", model, tin, tout, cost, 1, project, kind),
        )


def _cols(path):
    with sqlite3.connect(path) as conn:
        return {r[1] for r in conn.execute("PRAGMA table_info(ai_usage)")}


def _rows(path):
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM ai_usage").fetchall()


# --- construction / schema -------------------------------------------------


def test_init_creates_parent_dirs_and_db(db_path):
    UsageTracker(db_path)
    assert sqlite3.connect(db_path).execute("SELECT count(*) FROM ai_usage").fetchone() == (0,)


def test_init_stores_database_path(tracker, db_path):
    assert tracker.database_path == db_path


def test_schema_has_all_columns(tracker, db_path):
    assert {"kind", "workload", "session_id", "timestamp", "cost_usd", "project"} <= _cols(db_path)


def test_timestamp_index_created(tracker, db_path):
    with sqlite3.connect(db_path) as conn:
        names = {r[1] for r in conn.execute("PRAGMA index_list(ai_usage)")}
    assert "idx_timestamp" in names


def test_init_is_idempotent_and_preserves_rows(tracker, db_path):
    _insert(db_path, ts="2026-01-01T00:00:00")
    UsageTracker(db_path)
    UsageTracker(db_path)
    assert len(_rows(db_path)) == 1


def test_migration_adds_missing_columns_to_legacy_table(tmp_path):
    path = str(tmp_path / "legacy.db")
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE ai_usage (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,"
            " provider TEXT NOT NULL, model TEXT NOT NULL, tokens_in INTEGER NOT NULL,"
            " tokens_out INTEGER NOT NULL, cost_usd REAL NOT NULL, duration_ms INTEGER, project TEXT)"
        )
        conn.execute(
            "INSERT INTO ai_usage (timestamp, provider, model, tokens_in, tokens_out, cost_usd)"
            " VALUES ('2026-01-01T00:00:00','p','m',1,1,0.1)"
        )
    UsageTracker(path)
    assert {"kind", "workload", "session_id"} <= _cols(path)
    assert _rows(path)[0]["kind"] == "llm"  # legacy rows default to llm


# --- get_usage -------------------------------------------------------------


def test_get_usage_empty(tracker):
    assert tracker.get_usage() == {
        "total_calls": 0,
        "total_cost": 0.0,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "by_model": {},
    }


def test_get_usage_totals_and_by_model(tracker, db_path):
    _insert(db_path, ts="2026-01-01T00:00:00", model="a", tin=10, tout=1, cost=1.0)
    _insert(db_path, ts="2026-01-02T00:00:00", model="a", tin=20, tout=2, cost=2.0)
    _insert(db_path, ts="2026-01-03T00:00:00", model="b", tin=5, tout=3, cost=0.25)
    u = tracker.get_usage()
    assert u["total_calls"] == 3
    assert u["total_cost"] == pytest.approx(3.25)
    assert u["total_tokens_in"] == 35
    assert u["total_tokens_out"] == 6
    assert u["by_model"]["a"] == {"calls": 2, "cost": 3.0, "tokens_in": 30, "tokens_out": 3}
    assert u["by_model"]["b"]["calls"] == 1


def test_get_usage_month_filter(tracker, db_path):
    _insert(db_path, ts="2026-01-15T00:00:00", cost=1.0)
    _insert(db_path, ts="2026-02-15T00:00:00", cost=2.0)
    assert tracker.get_usage(month="2026-02")["total_cost"] == 2.0
    assert tracker.get_usage(month="2025-12")["total_calls"] == 0


def test_get_usage_project_filter(tracker, db_path):
    _insert(db_path, ts="2026-01-01T00:00:00", project="x", cost=1.0)
    _insert(db_path, ts="2026-01-01T00:00:00", project="y", cost=4.0)
    assert tracker.get_usage(project="y")["total_cost"] == 4.0


def test_get_usage_month_and_project_combined(tracker, db_path):
    _insert(db_path, ts="2026-01-01T00:00:00", project="x", cost=1.0)
    _insert(db_path, ts="2026-02-01T00:00:00", project="x", cost=2.0)
    _insert(db_path, ts="2026-02-01T00:00:00", project="y", cost=8.0)
    u = tracker.get_usage(month="2026-02", project="x")
    assert (u["total_calls"], u["total_cost"]) == (1, 2.0)


def test_get_usage_month_is_bound_parameter_not_sql(tracker, db_path):
    _insert(db_path, ts="2026-01-01T00:00:00")
    assert tracker.get_usage(month="' OR '1'='1")["total_calls"] == 0


def test_get_usage_includes_gpu_rows(tracker):
    tracker.record_gpu(session_id="s", kind="gpu-a", workload="w", cost_usd=2.0)
    u = tracker.get_usage()
    assert u["total_calls"] == 1 and u["by_model"]["gpu-a"]["cost"] == 2.0


# --- today_total -----------------------------------------------------------


def test_today_total_empty_is_zero_float(tracker):
    r = tracker.today_total()
    assert r == 0.0 and isinstance(r, float)


def test_today_total_only_counts_today(tracker, db_path):
    now = datetime.utcnow()
    _insert(db_path, ts=now.isoformat(), cost=1.5)
    _insert(db_path, ts=(now - timedelta(days=2)).isoformat(), cost=100.0)
    assert tracker.today_total() == pytest.approx(1.5)


def test_today_total_kind_filter(tracker, db_path):
    now = datetime.utcnow().isoformat()
    _insert(db_path, ts=now, cost=1.0, kind="llm")
    _insert(db_path, ts=now, cost=3.0, kind="gpu")
    assert tracker.today_total(kind="gpu") == pytest.approx(3.0)
    assert tracker.today_total(kind="llm") == pytest.approx(1.0)
    assert tracker.today_total() == pytest.approx(4.0)
    assert tracker.today_total(kind="other") == 0.0


def test_today_total_empty_kind_means_no_filter(tracker, db_path):
    _insert(db_path, ts=datetime.utcnow().isoformat(), cost=1.0, kind="llm")
    assert tracker.today_total(kind="") == pytest.approx(1.0)


# --- record_gpu ------------------------------------------------------------


def test_record_gpu_row_contents(tracker, db_path):
    tracker.record_gpu(
        session_id="sess1", kind="a100", workload="fine-tune", cost_usd=1.25, duration_seconds=2.5
    )
    (row,) = _rows(db_path)
    assert row["session_id"] == "sess1"
    assert row["model"] == "a100"  # kind label reused in model column
    assert row["kind"] == "gpu"
    assert row["workload"] == "fine-tune"
    assert row["cost_usd"] == 1.25
    assert row["duration_ms"] == 2500
    assert row["provider"] == "runpod"
    assert (row["tokens_in"], row["tokens_out"], row["project"]) == (0, 0, None)


def test_record_gpu_custom_provider(tracker, db_path):
    tracker.record_gpu(session_id="s", kind="k", workload="w", cost_usd=0.1, provider="vast")
    assert _rows(db_path)[0]["provider"] == "vast"


def test_record_gpu_no_duration_is_null(tracker, db_path):
    tracker.record_gpu(session_id="s", kind="k", workload="w", cost_usd=0.1)
    assert _rows(db_path)[0]["duration_ms"] is None


def test_record_gpu_timestamp_is_parseable_and_recent(tracker, db_path):
    tracker.record_gpu(session_id="s", kind="k", workload="w", cost_usd=0.1)
    ts = datetime.fromisoformat(_rows(db_path)[0]["timestamp"])
    assert abs((datetime.utcnow() - ts).total_seconds()) < 60


def test_record_gpu_is_keyword_only(tracker):
    with pytest.raises(TypeError):
        tracker.record_gpu("s", "k", "w", 1.0)  # type: ignore[misc]


def test_record_gpu_feeds_today_total(tracker):
    tracker.record_gpu(session_id="s1", kind="k", workload="w", cost_usd=1.0)
    tracker.record_gpu(session_id="s2", kind="k", workload="w", cost_usd=2.0)
    assert tracker.today_total(kind="gpu") == pytest.approx(3.0)


def test_record_gpu_missing_required_raises(tracker):
    with pytest.raises(TypeError):
        tracker.record_gpu(session_id="s", kind="k", workload="w")  # type: ignore[call-arg]


def test_record_gpu_persists_across_instances(tracker, db_path):
    tracker.record_gpu(session_id="s", kind="k", workload="w", cost_usd=0.7)
    assert UsageTracker(db_path).get_usage()["total_cost"] == pytest.approx(0.7)


@pytest.mark.xfail(
    strict=True, reason="tracker.py:127 `if duration_seconds` maps 0.0 to NULL, not 0 ms"
)
def test_record_gpu_zero_duration_is_zero_ms(tracker, db_path):
    tracker.record_gpu(session_id="s", kind="k", workload="w", cost_usd=0.1, duration_seconds=0.0)
    assert _rows(db_path)[0]["duration_ms"] == 0


def test_get_usage_on_unwritable_path_error_path(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(OSError):
        UsageTracker(str(blocker / "child" / "db.sqlite"))
