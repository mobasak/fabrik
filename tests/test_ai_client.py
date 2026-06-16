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

    def test_default_models_have_pricing(self) -> None:
        # Highest-risk path: _calculate_cost silently returns $0 for any model
        # not in PRICING, so every default MUST have a pricing entry. Also pin
        # the Claude default to the current 4.x family (regression guard against
        # the stale claude-3-5-sonnet-20241022 default fixed 2026-06-16).
        from fabrik.ai.client import DEFAULT_MODELS, PRICING

        for provider, model in DEFAULT_MODELS.items():
            assert model in PRICING, f"default model {model} for {provider} missing from PRICING"
        assert DEFAULT_MODELS[LLMProvider.CLAUDE] == "claude-sonnet-4-6"


class TestUsageTracker:
    def test_init_creates_db(self, tmp_path: Path) -> None:
        database_path = tmp_path / "test.db"
        UsageTracker(database_path=str(database_path))
        assert database_path.exists()

    def test_record_and_get(self, tmp_path: Path) -> None:
        database_path = tmp_path / "usage.db"
        tracker = UsageTracker(database_path=str(database_path))
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
