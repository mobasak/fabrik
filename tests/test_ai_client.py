from pathlib import Path

import pytest

from fabrik.ai import UsageTracker


class TestUsageTracker:
    def test_init_creates_db(self, tmp_path: Path) -> None:
        database_path = tmp_path / "test.db"
        UsageTracker(database_path=str(database_path))
        assert database_path.exists()

    def test_record_gpu_and_get(self, tmp_path: Path) -> None:
        # Highest-risk path: GPU rentals flow through the same SQLite table and
        # must show up in get_usage()/today_total() so daily-cost enforcement
        # in gpu_rent.rent() reads correct totals.
        database_path = tmp_path / "usage.db"
        tracker = UsageTracker(database_path=str(database_path))

        tracker.record_gpu(
            session_id="sess-1",
            kind="A100",
            workload="smoke-test",
            cost_usd=0.25,
            duration_seconds=120,
            provider="runpod",
        )

        usage = tracker.get_usage()
        assert usage["total_calls"] == 1
        assert usage["total_cost"] == pytest.approx(0.25, rel=1e-6)
        assert tracker.today_total() == pytest.approx(0.25, rel=1e-6)
        assert tracker.today_total(kind="gpu") == pytest.approx(0.25, rel=1e-6)
