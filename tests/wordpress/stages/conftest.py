"""Shared fixtures for stage tests."""

from unittest.mock import MagicMock

import pytest

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient


@pytest.fixture
def mock_wp():
    """Mock WordPressClient."""
    wp = MagicMock(spec=WordPressClient)
    wp.plugin_list.return_value = []
    wp.run.return_value = ""
    return wp


@pytest.fixture
def mock_api():
    """Mock WordPressAPIClient."""
    return MagicMock(spec=WordPressAPIClient)


@pytest.fixture
def minimal_spec():
    """Minimal spec for testing stages."""
    return {
        "site": {
            "name": "test-site",
            "domain": "test.example.com",
        },
        "deployment": {
            "vps_ip": "192.0.2.1",
            "cloudflare_proxy": True,
        },
        "seo": {},
        "contact": {},
        "navigation": {},
        "dry_run": True,
    }
