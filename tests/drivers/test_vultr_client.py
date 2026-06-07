"""Unit tests for the Vultr API v2 driver (fabrik.drivers.vultr).

All HTTP is mocked — no network, no spend. Covers the ground-truth-critical paths:
instance vs bare-metal dispatch, sshkey_id/tags body shape, 4xx-no-retry vs
5xx-retry, and the non-monotonic wait_for_active (status==active before ready).
"""

from unittest.mock import MagicMock, patch

import pytest

from fabrik.drivers.vultr import VultrClient, VultrError


def _resp(status_code: int, payload: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.content = b"" if payload is None else b"{}"
    r.json.return_value = payload or {}
    r.text = "" if payload is None else str(payload)
    return r


def _client(mock_client_cls, **kw) -> VultrClient:
    mock_client_cls.return_value = MagicMock()
    return VultrClient(api_key="test-token", **kw)


@patch("fabrik.drivers.vultr.httpx.Client")
def test_create_cloud_instance_dispatch_and_body(mock_cls):
    c = _client(mock_cls)
    c._client.request.return_value = _resp(202, {"instance": {"id": "i-1", "status": "pending"}})

    kind, obj = c.create_instance(
        region="lax", plan="vc2-1c-2gb", hostname="h", label="L",
        sshkey_ids=["k1"], tags=["t1", "t2"],
    )

    assert kind == "instance"
    assert obj["id"] == "i-1"
    method, path = c._client.request.call_args[0]
    body = c._client.request.call_args.kwargs["json"]
    assert method == "POST" and path == "/instances"
    assert body["sshkey_id"] == ["k1"]          # array field name
    assert body["tags"] == ["t1", "t2"]         # plural — never singular `tag`
    assert "tag" not in body
    assert body["os_id"] == 2284                # Ubuntu 24.04 default


@patch("fabrik.drivers.vultr.httpx.Client")
def test_create_bare_metal_dispatch(mock_cls):
    c = _client(mock_cls)
    c._client.request.return_value = _resp(202, {"bare_metal": {"id": "bm-1"}})

    kind, obj = c.create_instance(region="lax", plan="vbm-4c-32gb", hostname="h", sshkey_ids=["k1"])

    assert kind == "bare_metal"
    assert obj["id"] == "bm-1"
    _, path = c._client.request.call_args[0]
    assert path == "/bare-metals"               # separate endpoint family


@patch("fabrik.drivers.vultr.httpx.Client")
def test_4xx_fails_fast_no_retry(mock_cls):
    c = _client(mock_cls, max_retries=3)
    c._client.request.return_value = _resp(400, {"error": "bad plan"})

    with pytest.raises(VultrError) as ei:
        c.get_instance("i-x")

    assert ei.value.status == 400
    assert c._client.request.call_count == 1    # 4xx = our bug, no retry


@patch("fabrik.drivers.vultr.httpx.Client")
def test_5xx_retries_then_succeeds(mock_cls, monkeypatch):
    monkeypatch.setattr("fabrik.drivers.vultr.time.sleep", lambda *_: None)
    c = _client(mock_cls, max_retries=3)
    c._client.request.side_effect = [
        _resp(503, {"error": "try later"}),
        _resp(200, {"instance": {"id": "i-1"}}),
    ]

    out = c.get_instance("i-1")

    assert out["id"] == "i-1"
    assert c._client.request.call_count == 2    # retried once on 5xx


@patch("fabrik.drivers.vultr.httpx.Client")
def test_5xx_exhausts_retries_raises(mock_cls, monkeypatch):
    monkeypatch.setattr("fabrik.drivers.vultr.time.sleep", lambda *_: None)
    c = _client(mock_cls, max_retries=3)
    c._client.request.return_value = _resp(500, {"error": "down"})

    with pytest.raises(VultrError) as ei:
        c.list_instances()

    assert ei.value.status == 500
    assert c._client.request.call_count == 3


@patch("fabrik.drivers.vultr.httpx.Client")
def test_wait_for_active_instance_rejects_stopped_locked(mock_cls, monkeypatch):
    """status==active while power=stopped/server=locked must NOT count as ready."""
    monkeypatch.setattr("fabrik.drivers.vultr.time.sleep", lambda *_: None)
    c = _client(mock_cls)
    c._client.request.side_effect = [
        _resp(200, {"instance": {"status": "pending", "power_status": "running",
                                 "server_status": "none", "main_ip": "0.0.0.0"}}),
        _resp(200, {"instance": {"status": "active", "power_status": "stopped",
                                 "server_status": "locked", "main_ip": "1.2.3.4"}}),
        _resp(200, {"instance": {"status": "active", "power_status": "running",
                                 "server_status": "ok", "main_ip": "1.2.3.4"}}),
    ]

    obj = c.wait_for_active("instance", "i-1", timeout=120, interval=0)

    assert obj["main_ip"] == "1.2.3.4"
    assert c._client.request.call_count == 3    # only the 3rd poll is truly ready


@patch("fabrik.drivers.vultr.httpx.Client")
def test_wait_for_active_bare_metal_uses_status_and_ip_only(mock_cls, monkeypatch):
    """Bare metal has no power/server fields -> status==active + main_ip is enough."""
    monkeypatch.setattr("fabrik.drivers.vultr.time.sleep", lambda *_: None)
    c = _client(mock_cls)
    c._client.request.side_effect = [
        _resp(200, {"bare_metal": {"status": "pending", "main_ip": "0.0.0.0"}}),
        _resp(200, {"bare_metal": {"status": "active", "main_ip": "5.6.7.8"}}),
    ]

    obj = c.wait_for_active("bare_metal", "bm-1", timeout=120, interval=0)

    assert obj["main_ip"] == "5.6.7.8"
    assert c._client.request.call_count == 2


@patch("fabrik.drivers.vultr.httpx.Client")
def test_get_account_unwraps_account_key(mock_cls):
    c = _client(mock_cls)
    c._client.request.return_value = _resp(200, {"account": {"name": "Acct", "balance": -305}})
    assert c.get_account()["name"] == "Acct"


@patch("fabrik.drivers.vultr.httpx.Client")
def test_destroy_sends_delete(mock_cls):
    c = _client(mock_cls)
    c._client.request.return_value = _resp(204)
    c.destroy("instance", "i-1")
    method, path = c._client.request.call_args[0]
    assert method == "DELETE" and path == "/instances/i-1"


def test_is_bare_metal_classification():
    assert VultrClient.is_bare_metal("vbm-4c-32gb") is True
    assert VultrClient.is_bare_metal("vc2-1c-2gb") is False
    assert VultrClient.is_bare_metal("vcg-a16-2c-8g-2vram") is False
