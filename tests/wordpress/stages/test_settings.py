"""Tests for settings stage."""

import json
import os
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


@patch("fabrik.wordpress.stages.settings.secrets.token_urlsafe", return_value="generated-password")
@patch("fabrik.wordpress.stages.settings.SettingsApplicator")
def test_settings_creates_editor_when_email_present(
    mock_applicator_class, mock_token, minimal_spec, mock_wp, mock_api, tmp_path
):
    """Test settings stage creates editor when contact email exists."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False
    spec["contact"] = {"email": "editor@example.com"}

    mock_applicator = MagicMock()
    mock_applicator_class.return_value = mock_applicator
    mock_wp.run.side_effect = [RuntimeError("WP-CLI failed: User editor does not exist."), ""]

    result = settings.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_applicator.cleanup_defaults.assert_called_once()
    mock_applicator.apply_settings.assert_called_once_with(spec)
    mock_wp.run.assert_called_once_with("user get editor --format=json")
    mock_wp.user_create.assert_called_once_with(
        username="editor",
        email="editor@example.com",
        role="editor",
        password="generated-password",
    )


@patch("fabrik.wordpress.stages.settings.SettingsApplicator")
def test_settings_skips_if_user_exists(
    mock_applicator_class, minimal_spec, mock_wp, mock_api, tmp_path
):
    """Test settings stage skips editor creation when user already exists."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False
    spec["contact"] = {"email": "existing.user@example.com"}

    mock_applicator = MagicMock()
    mock_applicator_class.return_value = mock_applicator
    mock_wp.run.return_value = '{"ID": 7, "user_login": "existing_user"}'

    result = settings.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_wp.run.assert_called_once_with("user get existing_user --format=json")
    mock_wp.user_create.assert_not_called()


@patch("fabrik.wordpress.stages.settings.logger")
@patch("fabrik.wordpress.stages.settings.SettingsApplicator")
def test_settings_skips_if_no_email(
    mock_applicator_class, mock_logger, minimal_spec, mock_wp, mock_api, tmp_path
):
    """Test settings stage warns and skips editor provisioning without contact email."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False

    mock_applicator = MagicMock()
    mock_applicator_class.return_value = mock_applicator

    result = settings.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.warnings == ["Skipping editor provisioning: contact.email not provided"]
    mock_logger.warning.assert_called_once_with(
        "Skipping editor provisioning: contact.email not provided"
    )
    mock_wp.run.assert_not_called()
    mock_wp.user_create.assert_not_called()


@patch("fabrik.wordpress.stages.settings.os.chmod")
@patch("fabrik.wordpress.stages.settings.secrets.token_urlsafe", return_value="generated-password")
@patch("fabrik.wordpress.stages.settings.SettingsApplicator")
def test_settings_credentials_file_written(
    mock_applicator_class, mock_token, mock_chmod, minimal_spec, mock_wp, mock_api, tmp_path
):
    """Test settings stage writes credentials artifact with secure permissions."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False
    spec["contact"] = {"email": "editor@example.com"}

    mock_applicator = MagicMock()
    mock_applicator_class.return_value = mock_applicator
    mock_wp.run.side_effect = RuntimeError("WP-CLI failed: User editor does not exist.")

    result = settings.apply(spec, mock_wp, mock_api, tmp_path)

    credentials_path = tmp_path / "reports" / "credentials.json"
    assert credentials_path.exists()
    assert str(credentials_path) in result.artifacts_written

    payload = json.loads(credentials_path.read_text())
    assert payload == {
        "username": "editor",
        "email": "editor@example.com",
        "role": "editor",
        "created": True,
        "password": "generated-password",
    }
    mock_chmod.assert_called_once_with(credentials_path, 0o600)
    assert os.stat(credentials_path).st_mode & 0o777 != 0
