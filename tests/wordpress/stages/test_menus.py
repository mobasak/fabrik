"""Tests for menus stage."""

from unittest.mock import MagicMock, patch

from fabrik.wordpress.stages import menus


def test_menus_dry_run(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test menus stage in dry-run mode."""
    result = menus.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.name == "menus"


def test_menus_no_navigation(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test menus stage with no navigation defined."""
    spec = minimal_spec.copy()
    spec["navigation"] = {}

    result = menus.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success


@patch("fabrik.wordpress.stages.menus.MenuCreator")
def test_menus_exception(mock_creator_class, minimal_spec, mock_wp, mock_api, tmp_path):
    """Test menus stage handles exceptions."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False
    spec["navigation"] = {"primary": [{"title": "Home", "url": "/"}]}

    mock_creator = MagicMock()
    mock_creator.create_all.side_effect = RuntimeError("Menu error")
    mock_creator_class.return_value = mock_creator

    result = menus.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert len(result.errors) > 0
