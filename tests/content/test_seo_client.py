"""Tests for SEOClient HTTP driver.

All tests mock httpx.Client to avoid live service calls.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from fabrik.drivers.seo import SEOClient


@patch("fabrik.drivers.seo.httpx.Client")
def test_get_site_by_domain_found(mock_client_cls):
    """get_site_by_domain returns the site dict when domain matches."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {"sites": [{"site_id": "abc", "domain": "example.com"}]}
    mock_response.raise_for_status = MagicMock()
    mock_client.request.return_value = mock_response

    client = SEOClient(base_url="http://test:8016", token="tok")
    result = client.get_site_by_domain("example.com")

    assert result is not None
    assert result["site_id"] == "abc"
    assert result["domain"] == "example.com"


@patch("fabrik.drivers.seo.httpx.Client")
def test_get_site_by_domain_not_found(mock_client_cls):
    """get_site_by_domain returns None when no domain matches."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {"sites": []}
    mock_response.raise_for_status = MagicMock()
    mock_client.request.return_value = mock_response

    client = SEOClient(base_url="http://test:8016", token="tok")
    result = client.get_site_by_domain("missing.com")

    assert result is None


@patch("fabrik.drivers.seo.httpx.Client")
def test_get_site_by_domain_case_insensitive(mock_client_cls):
    """get_site_by_domain performs case-insensitive domain matching."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {"sites": [{"site_id": "abc", "domain": "Example.COM"}]}
    mock_response.raise_for_status = MagicMock()
    mock_client.request.return_value = mock_response

    client = SEOClient(base_url="http://test:8016", token="tok")
    result = client.get_site_by_domain("example.com")

    assert result is not None
    assert result["site_id"] == "abc"


@patch("fabrik.drivers.seo.httpx.Client")
def test_list_ready_briefs(mock_client_cls):
    """list_ready_briefs returns a list of brief dicts."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {"briefs": [{"brief_id": "x"}]}
    mock_response.raise_for_status = MagicMock()
    mock_client.request.return_value = mock_response

    client = SEOClient(base_url="http://test:8016", token="tok")
    result = client.list_ready_briefs("site-123")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["brief_id"] == "x"


@patch("fabrik.drivers.seo.httpx.Client")
def test_claim_brief(mock_client_cls):
    """claim_brief returns a dict containing status."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "brief_id": "x",
        "status": "claimed",
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.request.return_value = mock_response

    client = SEOClient(base_url="http://test:8016", token="tok")
    result = client.claim_brief("x", "worker-1")

    assert "status" in result
    assert result["status"] == "claimed"


@patch("fabrik.drivers.seo.httpx.Client")
def test_release_brief(mock_client_cls):
    """release_brief returns a dict containing status."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "brief_id": "x",
        "status": "ready",
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.request.return_value = mock_response

    client = SEOClient(base_url="http://test:8016", token="tok")
    result = client.release_brief("x", "worker-1")

    assert "status" in result
    assert result["status"] == "ready"


@patch("fabrik.drivers.seo.httpx.Client")
def test_submit_brief(mock_client_cls):
    """submit_brief returns a dict containing status."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "brief_id": "x",
        "status": "submitted",
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.request.return_value = mock_response

    client = SEOClient(base_url="http://test:8016", token="tok")
    submission = {"final_url": "https://example.com/page", "final_slug": "page"}
    result = client.submit_brief("x", "worker-1", submission)

    assert "status" in result
    assert result["status"] == "submitted"
