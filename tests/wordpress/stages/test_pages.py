"""Tests for pages stage."""

from unittest.mock import MagicMock, patch

from fabrik.wordpress.stages import pages


@patch("fabrik.wordpress.stages.pages.generate_pages")
def test_pages_empty_dry_run(mock_generate, minimal_spec, mock_wp, mock_api, tmp_path):
    """Test pages stage succeeds even with no pages."""
    mock_generate.return_value = []

    result = pages.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.name == "pages"


@patch("fabrik.wordpress.stages.pages.generate_pages")
def test_pages_dry_run(mock_generate, minimal_spec, mock_wp, mock_api, tmp_path):
    """Test pages stage in dry-run mode."""
    mock_generate.return_value = [{"slug": "about", "title": "About Us", "content": "Test content"}]

    result = pages.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.name == "pages"


@patch("fabrik.wordpress.stages.pages.PageCreator")
@patch("fabrik.wordpress.stages.pages.generate_pages")
def test_pages_exception(
    mock_generate, mock_creator_class, minimal_spec, mock_wp, mock_api, tmp_path
):
    """Test pages stage handles exceptions."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False
    mock_generate.return_value = [{"slug": "about", "title": "About", "content": "Test"}]

    mock_creator = MagicMock()
    mock_creator.create_all.side_effect = RuntimeError("Page creation error")
    mock_creator_class.return_value = mock_creator

    result = pages.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert len(result.errors) > 0
