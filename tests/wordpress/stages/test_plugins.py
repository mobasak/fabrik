"""Tests for plugins stage."""

import json

from fabrik.wordpress.stages import plugins

SLUG = "my-plugin"


def _write_manifest(tmp_path, entries):
    """Write a plugins.json manifest under tmp_path/manifests/."""
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    (manifests_dir / "plugins.json").write_text(json.dumps(entries), encoding="utf-8")


def test_install_missing_plugin(minimal_spec, mock_wp, mock_api, tmp_path):
    """Plugin not yet installed: plugin_install called with slug and activate=True."""
    mock_wp.plugin_list.return_value = []
    _write_manifest(tmp_path, [{"slug": SLUG, "source": "wordpress.org", "version": "1.0"}])

    spec = {**minimal_spec, "dry_run": False}
    result = plugins.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_wp.plugin_install.assert_called_once_with(SLUG, activate=True)
    mock_wp.plugin_activate.assert_not_called()


def test_skip_active_plugin(minimal_spec, mock_wp, mock_api, tmp_path):
    """Plugin already active: neither install nor activate is called."""
    mock_wp.plugin_list.return_value = [{"name": SLUG, "status": "active"}]
    _write_manifest(tmp_path, [{"slug": SLUG, "source": "wordpress.org", "version": "1.0"}])

    spec = {**minimal_spec, "dry_run": False}
    result = plugins.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_wp.plugin_install.assert_not_called()
    mock_wp.plugin_activate.assert_not_called()


def test_activate_inactive_plugin(minimal_spec, mock_wp, mock_api, tmp_path):
    """Plugin installed but inactive: plugin_activate called; plugin_install not called."""
    mock_wp.plugin_list.return_value = [{"name": SLUG, "status": "inactive"}]
    _write_manifest(tmp_path, [{"slug": SLUG, "source": "wordpress.org", "version": "1.0"}])

    spec = {**minimal_spec, "dry_run": False}
    result = plugins.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_wp.plugin_activate.assert_called_once_with(SLUG)
    mock_wp.plugin_install.assert_not_called()


def test_fail_on_missing_zip_path(minimal_spec, mock_wp, mock_api, tmp_path):
    """source=zip with no zip_path: result fails and plugin_install not called."""
    mock_wp.plugin_list.return_value = []
    _write_manifest(tmp_path, [{"slug": SLUG, "source": "zip", "zip_path": None}])

    spec = {**minimal_spec, "dry_run": False}
    result = plugins.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert result.errors
    mock_wp.plugin_install.assert_not_called()


def test_dry_run_no_calls(minimal_spec, mock_wp, mock_api, tmp_path):
    """dry_run=True: no WP calls made at all."""
    # minimal_spec already has dry_run=True; no manifest needed
    result = plugins.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_wp.plugin_list.assert_not_called()
    mock_wp.plugin_install.assert_not_called()


def test_wp_none_fails(minimal_spec, mock_api, tmp_path):
    """wp=None with dry_run=False: result fails with a descriptive error."""
    spec = {**minimal_spec, "dry_run": False}
    result = plugins.apply(spec, None, mock_api, tmp_path)

    assert not result.success
    assert result.errors


# ---------------------------------------------------------------------------
# ZIP plugin idempotency tests
# ---------------------------------------------------------------------------

ZIP_SLUG = "premium-plugin.zip"
ZIP_INSTALLED_SLUG = "premium-plugin"


def test_zip_plugin_skip_when_active(minimal_spec, mock_wp, mock_api, tmp_path):
    """ZIP plugin already active: neither install nor activate is called."""
    mock_wp.plugin_list.return_value = [{"name": ZIP_INSTALLED_SLUG, "status": "active"}]
    _write_manifest(
        tmp_path,
        [
            {
                "slug": ZIP_SLUG,
                "source": "zip",
                "zip_path": ZIP_SLUG,
                "installed_slug": ZIP_INSTALLED_SLUG,
                "version": None,
            }
        ],
    )

    spec = {**minimal_spec, "dry_run": False}
    result = plugins.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_wp.plugin_install.assert_not_called()
    mock_wp.plugin_activate.assert_not_called()


def test_zip_plugin_activate_when_inactive(minimal_spec, mock_wp, mock_api, tmp_path):
    """ZIP plugin installed but inactive: activate called with installed slug, not zip path."""
    mock_wp.plugin_list.return_value = [{"name": ZIP_INSTALLED_SLUG, "status": "inactive"}]
    _write_manifest(
        tmp_path,
        [
            {
                "slug": ZIP_SLUG,
                "source": "zip",
                "zip_path": ZIP_SLUG,
                "installed_slug": ZIP_INSTALLED_SLUG,
                "version": None,
            }
        ],
    )

    spec = {**minimal_spec, "dry_run": False}
    result = plugins.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_wp.plugin_activate.assert_called_once_with(ZIP_INSTALLED_SLUG)
    mock_wp.plugin_install.assert_not_called()


def test_zip_plugin_installs_when_absent(minimal_spec, mock_wp, mock_api, tmp_path):
    """ZIP plugin not yet installed: plugin_install called with zip_path."""
    mock_wp.plugin_list.return_value = []
    _write_manifest(
        tmp_path,
        [
            {
                "slug": ZIP_SLUG,
                "source": "zip",
                "zip_path": ZIP_SLUG,
                "installed_slug": ZIP_INSTALLED_SLUG,
                "version": None,
            }
        ],
    )

    spec = {**minimal_spec, "dry_run": False}
    result = plugins.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_wp.plugin_install.assert_called_once_with(ZIP_SLUG, activate=True)
    mock_wp.plugin_activate.assert_not_called()


def test_zip_plugin_skip_active_without_installed_slug(minimal_spec, mock_wp, mock_api, tmp_path):
    """Backwards-compat: manifest without installed_slug falls back to slug for lookup."""
    # Simulate old manifest format (no installed_slug field) where the slug
    # happens to match what WordPress reports (rare, but must not crash).
    old_slug = "my-plugin"
    mock_wp.plugin_list.return_value = [{"name": old_slug, "status": "active"}]
    _write_manifest(
        tmp_path,
        [
            {
                "slug": old_slug,
                "source": "zip",
                "zip_path": f"{old_slug}.zip",
                # no "installed_slug" key at all
                "version": None,
            }
        ],
    )

    spec = {**minimal_spec, "dry_run": False}
    result = plugins.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_wp.plugin_install.assert_not_called()
    mock_wp.plugin_activate.assert_not_called()


def test_zip_plugin_path_strip(minimal_spec, mock_wp, mock_api, tmp_path):
    """ZIP with a directory path: installed_slug is just the base name (no path, no .zip)."""
    path_zip = "uploads/plugins/path-prefix-my-plugin-1.2.3.zip"
    installed_slug_from_path = "my-plugin"
    mock_wp.plugin_list.return_value = [{"name": installed_slug_from_path, "status": "active"}]
    _write_manifest(
        tmp_path,
        [
            {
                "slug": path_zip,
                "source": "zip",
                "zip_path": path_zip,
                "installed_slug": installed_slug_from_path,
                "version": None,
            }
        ],
    )

    spec = {**minimal_spec, "dry_run": False}
    result = plugins.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    mock_wp.plugin_install.assert_not_called()
    mock_wp.plugin_activate.assert_not_called()
