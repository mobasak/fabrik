"""Tests for ImageBrokerClient HTTP driver.

All tests mock httpx.Client to avoid live service calls.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from fabrik.drivers.image_broker import ImageBrokerClient


@patch("fabrik.drivers.image_broker.httpx.Client")
def test_auto_download_success(mock_client_cls):
    """auto_download returns the response dict when success=True."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "success": True,
        "selected": [{"local_url": "/cache/img.jpg"}],
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.request.return_value = mock_response

    client = ImageBrokerClient(base_url="http://test:18016")
    result = client.auto_download("saas pricing")

    assert result is not None
    assert result["success"] is True
    assert len(result["selected"]) == 1


@patch("fabrik.drivers.image_broker.httpx.Client")
def test_auto_download_returns_none_on_failure(mock_client_cls):
    """auto_download returns None when success=False."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {"success": False}
    mock_response.raise_for_status = MagicMock()
    mock_client.request.return_value = mock_response

    client = ImageBrokerClient(base_url="http://test:18016")
    result = client.auto_download("no results query")

    assert result is None


@patch("fabrik.drivers.image_broker.httpx.Client")
def test_auto_download_returns_none_on_http_error(mock_client_cls):
    """auto_download returns None on httpx.HTTPError (graceful failure)."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_client.request.side_effect = httpx.HTTPError("Connection refused")

    client = ImageBrokerClient(base_url="http://test:18016")
    result = client.auto_download("broken query")

    assert result is None
