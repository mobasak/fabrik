"""
Tests for WordPress Manifest Generators

Verifies manifest generation without network calls.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from fabrik.wordpress.manifests import checks, menus, pages, plugins
from fabrik.wordpress.resolved_spec import ResolvedSpec


@pytest.fixture
def minimal_spec():
    """Minimal ResolvedSpec for testing."""
    return ResolvedSpec(
        site_id="test.com",
        data={
            "domain": "test.com",
            "title": "Test Site",
            "plugins": {
                "base": ["contact-form-7", "yoast-seo"],
                "add": ["akismet"],
                "skip": [],
            },
            "pages": [
                {
                    "title": "Home",
                    "slug": "",
                    "sections": [{"type": "hero", "heading": "Welcome"}],
                },
                {
                    "title": "Contact Us",
                    "slug": "contact",
                    "sections": [{"type": "form", "fields": ["name", "email"]}],
                },
            ],
            "navigation": {
                "primary": [
                    {"label": "Home", "url": "/"},
                    {"label": "Contact", "url": "/contact"},
                ],
                "footer": [{"label": "Privacy", "url": "/privacy"}],
            },
            "checks": {
                "urls": ["/", "/contact"],
                "require_ssl": True,
                "require_sitemap": True,
            },
            "languages": {"primary": "en_US"},
        },
        spec_hash="test_hash",
    )


@pytest.fixture
def spec_with_empty_checks():
    """Spec with empty checks config to test defaults."""
    return ResolvedSpec(
        site_id="test.com",
        data={"checks": {}},
        spec_hash="test_hash",
    )


def test_plugins_manifest_valid_json(minimal_spec, tmp_path):
    """Test that plugins manifest is valid JSON with required fields."""
    manifest_path = plugins.generate(minimal_spec, tmp_path)

    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Should have entries
    assert len(manifest) >= 1
    assert isinstance(manifest, list)

    # Each entry has required fields
    for entry in manifest:
        assert "slug" in entry
        assert "version" in entry  # May be null
        assert "source" in entry
        assert entry["source"] in ["wordpress.org", "zip"]
        assert "zip_path" in entry
        assert "installed_slug" in entry

        # zip_path is set only for zip sources
        if entry["source"] == "zip":
            assert entry["zip_path"] is not None
            assert entry["slug"].endswith(".zip")
            # installed_slug must not contain a path or .zip extension
            assert "/" not in entry["installed_slug"]
            assert not entry["installed_slug"].endswith(".zip")
        else:
            assert entry["zip_path"] is None
            # For wordpress.org plugins, installed_slug == slug
            assert entry["installed_slug"] == entry["slug"]


def test_pages_manifest_non_empty(minimal_spec, tmp_path):
    """Test that pages manifest contains pages."""
    manifest_path = pages.generate(minimal_spec, tmp_path)

    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Should have at least one page
    assert len(manifest) >= 1
    assert isinstance(manifest, list)


def test_menus_manifest_structure(minimal_spec, tmp_path):
    """Test that menus manifest matches spec structure."""
    manifest_path = menus.generate(minimal_spec, tmp_path)

    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Should match navigation keys
    assert "primary" in manifest
    assert "footer" in manifest
    assert isinstance(manifest["primary"], list)
    assert isinstance(manifest["footer"], list)

    # Verify content
    assert len(manifest["primary"]) == 2
    assert manifest["primary"][0]["label"] == "Home"
    assert manifest["primary"][1]["label"] == "Contact"


def test_checks_manifest_defaults(spec_with_empty_checks, tmp_path):
    """Test that checks manifest uses schema defaults."""
    manifest_path = checks.generate(spec_with_empty_checks, tmp_path)

    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Should have default URLs
    assert "urls" in manifest
    assert len(manifest["urls"]) == 2
    assert any(check["url"] == "/" for check in manifest["urls"])
    assert any(check["url"] == "/contact" for check in manifest["urls"])

    # All checks have expected_status
    for check in manifest["urls"]:
        assert check["expected_status"] == 200

    # Should have SSL and sitemap flags
    assert "require_ssl" in manifest
    assert "require_sitemap" in manifest
    assert manifest["require_ssl"] is True
    assert manifest["require_sitemap"] is True


def test_no_network_calls(minimal_spec, tmp_path):
    """Test that manifest generation makes no network calls."""
    # Mock network libraries to ensure they're never called
    with (
        patch("httpx.Client") as mock_httpx,
        patch("urllib.request.urlopen") as mock_urllib,
    ):
        # Generate all manifests
        plugins.generate(minimal_spec, tmp_path)
        pages.generate(minimal_spec, tmp_path)
        menus.generate(minimal_spec, tmp_path)
        checks.generate(minimal_spec, tmp_path)

        # Verify no network calls were made
        mock_httpx.assert_not_called()
        mock_urllib.assert_not_called()


def test_plugins_manifest_with_zip(tmp_path):
    """Test that zip plugins are handled correctly."""
    spec = ResolvedSpec(
        site_id="test.com",
        data={
            "plugins": {
                "base": [],
                "add": [
                    "regular-plugin",
                    "premium-plugin.zip",
                    "path/to/custom-plugin.zip",
                ],
                "skip": [],
            }
        },
        spec_hash="test",
    )

    manifest_path = plugins.generate(spec, tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Find the zip plugins
    zip_plugins = [p for p in manifest if p["source"] == "zip"]
    assert len(zip_plugins) == 2

    for plugin in zip_plugins:
        assert plugin["slug"].endswith(".zip")
        assert plugin["zip_path"] == plugin["slug"]
        assert plugin["version"] is None
        # installed_slug must be the normalized base name (no .zip, no path)
        assert "installed_slug" in plugin
        assert not plugin["installed_slug"].endswith(".zip")
        assert "/" not in plugin["installed_slug"]

    # Verify specific installed slugs
    slug_map = {p["slug"]: p["installed_slug"] for p in zip_plugins}
    assert slug_map["premium-plugin.zip"] == "premium-plugin"
    assert slug_map["path/to/custom-plugin.zip"] == "custom-plugin"


def test_menus_manifest_uses_navigation_fallback(tmp_path):
    """Test that menus generator tries both 'navigation' and 'menus' keys."""
    # Spec with 'menus' key instead of 'navigation'
    spec = ResolvedSpec(
        site_id="test.com",
        data={
            "menus": {
                "primary": [{"label": "About", "url": "/about"}],
            }
        },
        spec_hash="test",
    )

    manifest_path = menus.generate(spec, tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert "primary" in manifest
    assert len(manifest["primary"]) == 1
    assert manifest["primary"][0]["label"] == "About"


def test_checks_manifest_custom_urls(tmp_path):
    """Test that custom check URLs are preserved."""
    spec = ResolvedSpec(
        site_id="test.com",
        data={
            "checks": {
                "urls": ["/", "/about", "/blog", "/shop"],
                "require_ssl": False,
                "require_sitemap": False,
            }
        },
        spec_hash="test",
    )

    manifest_path = checks.generate(spec, tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert len(manifest["urls"]) == 4
    assert manifest["require_ssl"] is False
    assert manifest["require_sitemap"] is False

    urls = [check["url"] for check in manifest["urls"]]
    assert urls == ["/", "/about", "/blog", "/shop"]
