"""Tests for settings stage."""

from unittest.mock import MagicMock, patch

from fabrik.wordpress.stages import settings


def test_settings_dry_run(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test settings stage in dry-run mode."""
    result = settings.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.name == "settings"


@patch("fabrik.wordpress.stages.settings.SettingsApplicator")
def test_settings_exception(mock_applicator_class, minimal_spec, mock_wp, mock_api, tmp_path):
    """Test settings stage handles exceptions."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False

    mock_applicator = MagicMock()
    mock_applicator.cleanup_defaults.side_effect = RuntimeError("Settings error")
    mock_applicator_class.return_value = mock_applicator

    result = settings.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert len(result.errors) > 0
