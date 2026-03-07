"""Tests for SEO stage."""

from unittest.mock import MagicMock, patch

from fabrik.wordpress.stages import seo


def test_seo_dry_run(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test SEO stage in dry-run mode."""
    result = seo.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.name == "seo"


def test_seo_no_settings(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test SEO stage with no SEO settings."""
    spec = minimal_spec.copy()
    spec["seo"] = {}

    result = seo.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success


@patch("fabrik.wordpress.stages.seo.SEOApplicator")
def test_seo_exception(mock_applicator_class, minimal_spec, mock_wp, mock_api, tmp_path):
    """Test SEO stage handles exceptions."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False
    spec["seo"] = {"title": "Test Site"}

    mock_applicator = MagicMock()
    mock_applicator.detect_seo_plugin.side_effect = RuntimeError("SEO error")
    mock_applicator_class.return_value = mock_applicator

    result = seo.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert len(result.errors) > 0
