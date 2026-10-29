"""Coverage sweep for fabrik.drivers.tco.TCOClient (hermetic: httpx is mocked)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from fabrik.drivers import tco
from fabrik.drivers.tco import TCOClient


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("TCO_API_URL", raising=False)
    monkeypatch.delenv("TCO_API_KEY", raising=False)


@pytest.fixture
def httpx_client():
    with patch("fabrik.drivers.tco.httpx.Client") as cls:
        inst = MagicMock()
        inst.request.return_value.json.return_value = {"ok": True}
        cls.return_value = inst
        cls.inst = inst
        yield cls


# --- construction ---------------------------------------------------------


def test_default_base_url_and_no_token(httpx_client):
    c = TCOClient()
    assert c.base_url == "http://localhost:8025"
    assert c.token is None
    assert c.timeout == 300.0


def test_env_vars_used(httpx_client, monkeypatch):
    monkeypatch.setenv("TCO_API_URL", "http://env:1")
    monkeypatch.setenv("TCO_API_KEY", "envtok")
    c = TCOClient()
    assert c.base_url == "http://env:1"
    assert c.token == "envtok"


def test_args_override_env(httpx_client, monkeypatch):
    monkeypatch.setenv("TCO_API_URL", "http://env:1")
    monkeypatch.setenv("TCO_API_KEY", "envtok")
    c = TCOClient(base_url="http://arg:2", token="argtok")
    assert c.base_url == "http://arg:2"
    assert c.token == "argtok"


def test_auth_header_set_when_token(httpx_client):
    TCOClient(token="abc")
    headers = httpx_client.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer abc"
    assert headers["Accept"] == "application/json"
    assert headers["Content-Type"] == "application/json"


def test_no_auth_header_without_token(httpx_client):
    TCOClient()
    assert "Authorization" not in httpx_client.call_args.kwargs["headers"]


def test_empty_token_means_no_auth_header(httpx_client):
    TCOClient(token="")
    assert "Authorization" not in httpx_client.call_args.kwargs["headers"]


def test_timeout_passed_to_httpx(httpx_client):
    TCOClient(timeout=12.5)
    assert httpx_client.call_args.kwargs["timeout"] == 12.5


# --- requests -------------------------------------------------------------


def test_generate_posts_brief_to_endpoint(httpx_client):
    c = TCOClient(base_url="http://t:9")
    brief = {"brief_id": "x"}
    assert c.generate_from_brief(brief) == {"ok": True}
    httpx_client.inst.request.assert_called_once_with(
        "POST", "http://t:9/ai-content/generate-from-brief", json=brief
    )


def test_health_gets_endpoint(httpx_client):
    c = TCOClient(base_url="http://t:9")
    assert c.health() == {"ok": True}
    httpx_client.inst.request.assert_called_once_with("GET", "http://t:9/ai-content/health")


def test_health_http_error_propagates(httpx_client):
    resp = httpx_client.inst.request.return_value
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=MagicMock(), response=resp
    )
    with pytest.raises(httpx.HTTPStatusError):
        TCOClient().health()


def test_transport_error_propagates(httpx_client):
    httpx_client.inst.request.side_effect = httpx.ConnectError("down")
    with pytest.raises(httpx.ConnectError):
        TCOClient().generate_from_brief({})


def test_invalid_json_propagates(httpx_client):
    httpx_client.inst.request.return_value.json.side_effect = ValueError("bad json")
    with pytest.raises(ValueError):
        TCOClient().health()


def test_raise_for_status_called_before_json(httpx_client):
    resp = httpx_client.inst.request.return_value
    resp.raise_for_status.side_effect = RuntimeError("status")
    with pytest.raises(RuntimeError):
        TCOClient().health()
    resp.json.assert_not_called()


def test_request_builds_url_from_base_and_endpoint(httpx_client):
    TCOClient(base_url="http://h")._request("PUT", "/x", data=1)
    httpx_client.inst.request.assert_called_once_with("PUT", "http://h/x", data=1)


# --- lifecycle ------------------------------------------------------------


def test_close_closes_client(httpx_client):
    TCOClient().close()
    httpx_client.inst.close.assert_called_once_with()


def test_context_manager_returns_self_and_closes(httpx_client):
    with TCOClient() as c:
        assert isinstance(c, TCOClient)
        httpx_client.inst.close.assert_not_called()
    httpx_client.inst.close.assert_called_once_with()


def test_context_manager_closes_on_exception(httpx_client):
    with pytest.raises(KeyError):
        with TCOClient():
            raise KeyError("x")
    httpx_client.inst.close.assert_called_once_with()


def test_exported_from_drivers_package():
    from fabrik import drivers

    assert drivers.TCOClient is tco.TCOClient


def test_real_httpx_client_via_mock_transport():
    """End-to-end through a real httpx.Client with a MockTransport (no network)."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"status": "up"})

    c = TCOClient(base_url="http://svc", token="t")
    c._client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer t"}
    )
    assert c.health() == {"status": "up"}
    assert seen == {"url": "http://svc/ai-content/health", "auth": "Bearer t"}
    c.close()
