"""Tests for analytics stage."""

from unittest.mock import MagicMock, patch

from fabrik.wordpress.stages import analytics


def test_analytics_dry_run(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test analytics stage in dry-run mode."""
    result = analytics.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.name == "analytics"


def test_analytics_no_ids(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test analytics stage with no analytics IDs."""
    spec = minimal_spec.copy()
    spec["seo"] = {"analytics": {}}

    result = analytics.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success


@patch("fabrik.wordpress.stages.analytics.AnalyticsInjector")
def test_analytics_exception(mock_injector_class, minimal_spec, mock_wp, mock_api, tmp_path):
    """Test analytics stage handles exceptions."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False
    spec["seo"] = {"ga4_id": "G-TEST123"}

    mock_injector = MagicMock()
    mock_injector.apply_from_spec.side_effect = RuntimeError("Analytics error")
    mock_injector_class.return_value = mock_injector

    result = analytics.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert len(result.errors) > 0
