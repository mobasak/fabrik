"""Tests for languages stage."""

from fabrik.wordpress.stages import languages


def test_no_additional_languages_is_no_op(minimal_spec, mock_wp, mock_api, tmp_path):
    """Stage is a no-op when spec has no languages key."""
    result = languages.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success is True
    assert result.name == "languages"
    assert mock_wp.plugin_list.call_count == 0


def test_installs_core_translations(mock_wp, mock_api, tmp_path):
    """Stage installs additional locales and activates the primary locale."""
    spec = {
        "dry_run": False,
        "languages": {
            "primary": "tr_TR",
            "additional": ["tr_TR"],
        },
    }
    mock_wp.plugin_list.return_value = [{"name": "sitepress-multilingual-cms", "status": "active"}]

    result = languages.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success is True
    mock_wp.language_install.assert_called_once_with("tr_TR")
    mock_wp.language_activate.assert_called_once_with("tr_TR")


def test_warns_if_wpml_installed(mock_wp, mock_api, tmp_path):
    """Stage appends a warning when WPML is detected."""
    spec = {
        "dry_run": False,
        "languages": {
            "primary": "tr_TR",
            "additional": ["tr_TR"],
        },
    }
    mock_wp.plugin_list.return_value = [{"name": "sitepress-multilingual-cms", "status": "active"}]

    result = languages.apply(spec, mock_wp, mock_api, tmp_path)

    assert any("WPML" in w for w in result.warnings)


def test_fails_if_multilingual_plugin_missing(mock_wp, mock_api, tmp_path):
    """Stage fails when additional locales are requested but WPML is absent."""
    spec = {
        "dry_run": False,
        "languages": {
            "primary": "en_US",
            "additional": ["fr_FR"],
        },
    }
    mock_wp.plugin_list.return_value = []

    result = languages.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success is False
    assert len(result.errors) > 0


def test_polylang_plugin_succeeds_when_installed(mock_wp, mock_api, tmp_path):
    """Stage succeeds with polylang when spec selects it and it is installed."""
    spec = {
        "dry_run": False,
        "languages": {
            "primary": "fr_FR",
            "additional": ["fr_FR"],
            "plugin": "polylang",
        },
    }
    mock_wp.plugin_list.return_value = [{"name": "polylang", "status": "active"}]

    result = languages.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success is True
    mock_wp.language_install.assert_called_once_with("fr_FR")
    mock_wp.language_activate.assert_called_once_with("fr_FR")
    # No WPML warning when WPML is not installed
    assert not any("WPML" in w for w in result.warnings)


def test_polylang_plugin_fails_when_missing(mock_wp, mock_api, tmp_path):
    """Stage fails when polylang is configured but not installed."""
    spec = {
        "dry_run": False,
        "languages": {
            "primary": "en_US",
            "additional": ["fr_FR"],
            "plugin": "polylang",
        },
    }
    mock_wp.plugin_list.return_value = []

    result = languages.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success is False
    assert any("polylang" in e for e in result.errors)


def test_dry_run_no_calls(mock_wp, mock_api, tmp_path):
    """In dry-run mode, no WP-CLI calls are made."""
    spec = {
        "dry_run": True,
        "languages": {
            "primary": "fr_FR",
            "additional": ["fr_FR"],
        },
    }

    result = languages.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success is True
    assert mock_wp.plugin_list.call_count == 0
    assert mock_wp.language_install.call_count == 0
    assert mock_wp.language_activate.call_count == 0
