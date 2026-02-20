"""Property-based tests using Hypothesis."""

from hypothesis import assume, given
from hypothesis import strategies as st
from scripts.droid_models import (
    DEFAULT_MODEL,
    TASK_MODEL_MAP,
    TaskCategory,
    get_default_model,
    load_models_config,
    recommend_model,
)
from src.fabrik.scaffold import _get_package_name


class TestGetPackageName:
    """Property tests for _get_package_name."""

    @given(st.text(min_size=0, max_size=100))
    def test_get_package_name_replaces_hyphens(self, name: str) -> None:
        """Property: hyphens are replaced with underscores, length preserved."""
        result = _get_package_name(name)

        assert result == name.replace("-", "_")
        assert len(result) == len(name)
        assert "-" not in result


class TestRecommendModel:
    """Property tests for recommend_model."""

    @given(st.sampled_from(list(TaskCategory)))
    def test_recommend_model_returns_valid_candidate(self, cat: TaskCategory) -> None:
        """Property: returned model is in TASK_MODEL_MAP or is DEFAULT_MODEL."""
        result = recommend_model(cat)

        assert result in TASK_MODEL_MAP[cat] or result == DEFAULT_MODEL
        assert isinstance(result, str) and len(result) > 0


class TestGetDefaultModel:
    """Property tests for get_default_model."""

    @given(st.just(None))
    def test_get_default_model_in_models_yaml(self, _: None) -> None:
        """Property: default model is a non-empty string present in models.yaml."""
        result = get_default_model()
        config = load_models_config()

        assume(config.get("models"))

        assert isinstance(result, str) and len(result) > 0
        assert result in config.get("models", {})
