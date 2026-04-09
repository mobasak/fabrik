"""Tests for TCOClient HTTP driver.

All tests mock httpx.Client to avoid live service calls.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from fabrik.drivers.tco import TCOClient


@patch("fabrik.drivers.tco.httpx.Client")
def test_generate_from_brief_success(mock_client_cls):
    """generate_from_brief returns a dict with page_payload key."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "brief_id": "b1",
        "page_payload": {"page_type": "service", "slug": "test"},
        "rendered_sections": [],
        "json_ld": [],
        "validation": {"is_valid": True},
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.request.return_value = mock_response

    client = TCOClient(base_url="http://test:8025", token="tok")
    result = client.generate_from_brief({"brief_id": "b1"})

    assert "page_payload" in result
    assert result["page_payload"]["page_type"] == "service"


@patch("fabrik.drivers.tco.httpx.Client")
def test_generate_from_brief_http_error(mock_client_cls):
    """generate_from_brief propagates httpx.HTTPStatusError (not swallowed)."""
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        message="Validation failed",
        request=MagicMock(),
        response=mock_response,
    )
    mock_client.request.return_value = mock_response

    client = TCOClient(base_url="http://test:8025", token="tok")
    with pytest.raises(httpx.HTTPStatusError):
        client.generate_from_brief({"bad": "brief"})
