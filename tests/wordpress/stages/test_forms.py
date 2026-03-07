"""Tests for forms stage."""

from unittest.mock import MagicMock, patch

from fabrik.wordpress.stages import forms


def test_forms_dry_run(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test forms stage in dry-run mode."""
    result = forms.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.name == "forms"


def test_forms_no_contact(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test forms stage with no contact info."""
    spec = minimal_spec.copy()
    spec["contact"] = {}

    result = forms.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success


@patch("fabrik.wordpress.stages.forms.FormCreator")
def test_forms_exception(mock_creator_class, minimal_spec, mock_wp, mock_api, tmp_path):
    """Test forms stage handles exceptions."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False
    spec["contact"] = {"email": "test@example.com"}

    mock_creator = MagicMock()
    mock_creator.detect_form_plugin.side_effect = RuntimeError("Form error")
    mock_creator_class.return_value = mock_creator

    result = forms.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert len(result.errors) > 0
