import os
from pathlib import Path
from unittest.mock import patch

import pytest

from fabrik.ai import LLMClient, LLMProvider, LLMResponse, UsageTracker


class TestLLMClient:
    def test_init_requires_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                LLMClient(provider=LLMProvider.CLAUDE, track_usage=False)

    def test_calculate_cost(self) -> None:
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test"}, clear=True):
            client = LLMClient(track_usage=False)
            cost = client._calculate_cost(1000, 500)
            assert cost == pytest.approx(0.0105, rel=1e-6)


class TestUsageTracker:
    def test_init_creates_db(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        UsageTracker(db_path=str(db_path))
        assert db_path.exists()

    def test_record_and_get(self, tmp_path: Path) -> None:
        db_path = tmp_path / "usage.db"
        tracker = UsageTracker(db_path=str(db_path))
        response = LLMResponse(
            content="ok",
            tokens_in=100,
            tokens_out=50,
            cost=0.001,
            model="claude-3-5-sonnet-20241022",
            provider=LLMProvider.CLAUDE,
            duration_ms=123,
        )

        tracker.record(response, project="test-project")
        usage = tracker.get_usage()

        assert usage["total_calls"] == 1
        assert usage["total_cost"] == pytest.approx(0.001, rel=1e-6)
