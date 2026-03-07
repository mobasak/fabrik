"""Tests for theme stage."""

from unittest.mock import MagicMock, patch

from fabrik.wordpress.stages import theme


def test_theme_dry_run(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test theme stage in dry-run mode."""
    result = theme.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.name == "theme"


@patch("fabrik.wordpress.stages.theme.ThemeCustomizer")
def test_theme_exception(mock_customizer_class, minimal_spec, mock_wp, mock_api, tmp_path):
    """Test theme stage handles exceptions."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False

    mock_customizer = MagicMock()
    mock_customizer.apply_from_spec.side_effect = RuntimeError("Theme error")
    mock_customizer_class.return_value = mock_customizer

    result = theme.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert len(result.errors) > 0
