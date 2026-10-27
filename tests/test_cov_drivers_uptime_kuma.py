"""Hermetic tests for fabrik.drivers.uptime_kuma (no network, API fully mocked)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from fabrik.drivers import uptime_kuma as uk


@pytest.fixture
def api(monkeypatch):
    """Patch the module so UptimeKumaApi(...) returns one shared MagicMock."""
    fake = MagicMock()
    fake.get_monitors.return_value = []
    fake.add_monitor.return_value = {"monitorID": 7}
    ctor = MagicMock(return_value=fake)
    monkeypatch.setattr(uk, "HAS_UPTIME_KUMA", True)
    monkeypatch.setattr(uk, "UptimeKumaApi", ctor)
    monkeypatch.setattr(uk, "MonitorType", SimpleNamespace(HTTP="http", PORT="port"))
    fake.ctor = ctor
    return fake


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("UPTIME_KUMA_URL", "UPTIME_KUMA_USERNAME", "UPTIME_KUMA_PASSWORD"):
        monkeypatch.delenv(k, raising=False)


# --- construction -----------------------------------------------------------


def test_defaults_without_env():
    c = uk.UptimeKumaClient()
    assert c.url == "https://status.vps1.ocoron.com"
    assert c.username is None and c.password is None
    assert c.timeout == 30
    assert c._api is None


def test_env_values_used(monkeypatch):
    monkeypatch.setenv("UPTIME_KUMA_URL", "https://k.example")
    monkeypatch.setenv("UPTIME_KUMA_USERNAME", "envuser")
    monkeypatch.setenv("UPTIME_KUMA_PASSWORD", "envpw")
    c = uk.UptimeKumaClient()
    assert (c.url, c.username, c.password) == ("https://k.example", "envuser", "envpw")


def test_explicit_args_override_env(monkeypatch):
    monkeypatch.setenv("UPTIME_KUMA_URL", "https://env")
    monkeypatch.setenv("UPTIME_KUMA_USERNAME", "envuser")
    c = uk.UptimeKumaClient(url="https://x", username="u", password="p", timeout=5)
    assert (c.url, c.username, c.password, c.timeout) == ("https://x", "u", "p", 5)


# --- connection -------------------------------------------------------------


def test_missing_dependency_raises_import_error(monkeypatch):
    monkeypatch.setattr(uk, "HAS_UPTIME_KUMA", False)
    with pytest.raises(ImportError, match="uptime-kuma-api not installed"):
        uk.UptimeKumaClient()._ensure_connected()


def test_get_api_propagates_import_error(monkeypatch):
    monkeypatch.setattr(uk, "HAS_UPTIME_KUMA", False)
    with pytest.raises(ImportError):
        uk.UptimeKumaClient().get_monitors()


def test_connect_logs_in_with_credentials_and_timeout(api):
    c = uk.UptimeKumaClient(url="https://x", username="u", password="p", timeout=9)
    c._ensure_connected()
    api.ctor.assert_called_once_with("https://x", timeout=9)
    api.login.assert_called_once_with("u", "p")


def test_connection_is_reused(api):
    c = uk.UptimeKumaClient(username="u", password="p")
    c.get_monitors()
    c.get_monitors()
    assert api.ctor.call_count == 1
    assert api.login.call_count == 1


def test_get_api_returns_connected_client(api):
    assert uk.UptimeKumaClient(username="u", password="p")._get_api() is api


def test_get_api_runtime_error_when_not_initialised(monkeypatch):
    monkeypatch.setattr(uk, "HAS_UPTIME_KUMA", True)
    c = uk.UptimeKumaClient()
    monkeypatch.setattr(c, "_ensure_connected", lambda: None)
    with pytest.raises(RuntimeError, match="not initialized"):
        c._get_api()


def test_login_failure_propagates(api):
    api.login.side_effect = RuntimeError("bad creds")
    with pytest.raises(RuntimeError, match="bad creds"):
        uk.UptimeKumaClient(username="u", password="p").get_monitors()


def test_disconnect_closes_and_resets(api):
    c = uk.UptimeKumaClient(username="u", password="p")
    c._ensure_connected()
    c.disconnect()
    api.disconnect.assert_called_once()
    assert c._api is None


def test_disconnect_without_connection_is_noop(api):
    uk.UptimeKumaClient().disconnect()
    api.disconnect.assert_not_called()


def test_reconnects_after_disconnect(api):
    c = uk.UptimeKumaClient(username="u", password="p")
    c._ensure_connected()
    c.disconnect()
    c._ensure_connected()
    assert api.ctor.call_count == 2


# --- monitors ---------------------------------------------------------------


def test_get_monitors_returns_api_list(api):
    api.get_monitors.return_value = [{"name": "a"}]
    assert uk.UptimeKumaClient().get_monitors() == [{"name": "a"}]


def test_add_http_monitor_creates(api):
    out = uk.UptimeKumaClient().add_http_monitor("Svc", "https://s/health", interval=30, retries=5)
    assert out == {"status": "created", "monitor": {"monitorID": 7}}
    api.add_monitor.assert_called_once_with(
        type="http", name="Svc", url="https://s/health", interval=30,
        retryInterval=20, maxretries=5,
    )


def test_add_http_monitor_defaults(api):
    uk.UptimeKumaClient().add_http_monitor("Svc", "https://s")
    kw = api.add_monitor.call_args.kwargs
    assert kw["interval"] == 60 and kw["maxretries"] == 3


def test_add_http_monitor_existing_not_recreated(api):
    existing = {"name": "Svc", "id": 1}
    api.get_monitors.return_value = [{"name": "other", "id": 2}, existing]
    out = uk.UptimeKumaClient().add_http_monitor("Svc", "https://s")
    assert out == {"status": "exists", "monitor": existing}
    api.add_monitor.assert_not_called()


def test_add_tcp_monitor_creates(api):
    out = uk.UptimeKumaClient().add_tcp_monitor("PG", "postgres-main", 5432, interval=15)
    assert out["status"] == "created"
    api.add_monitor.assert_called_once_with(
        type="port", name="PG", hostname="postgres-main", port=5432, interval=15,
        retryInterval=20, maxretries=3,
    )


def test_add_tcp_monitor_existing(api):
    existing = {"name": "PG", "id": 3}
    api.get_monitors.return_value = [existing]
    out = uk.UptimeKumaClient().add_tcp_monitor("PG", "h", 1)
    assert out == {"status": "exists", "monitor": existing}
    api.add_monitor.assert_not_called()


def test_delete_monitor_found(api):
    api.get_monitors.return_value = [{"name": "a", "id": 1}, {"name": "b", "id": 2}]
    assert uk.UptimeKumaClient().delete_monitor("b") is True
    api.delete_monitor.assert_called_once_with(2)


def test_delete_monitor_missing(api):
    api.get_monitors.return_value = [{"name": "a", "id": 1}]
    assert uk.UptimeKumaClient().delete_monitor("zzz") is False
    api.delete_monitor.assert_not_called()


def test_add_service_monitor_builds_url_and_name(api):
    uk.UptimeKumaClient().add_service_monitor("translator", "vps1.ocoron.com")
    kw = api.add_monitor.call_args.kwargs
    assert kw["name"] == "Translator API"
    assert kw["url"] == "https://translator.vps1.ocoron.com/health"


def test_add_service_monitor_custom_endpoint(api):
    uk.UptimeKumaClient().add_service_monitor("x", "d.com", health_endpoint="/healthz")
    assert api.add_monitor.call_args.kwargs["url"] == "https://x.d.com/healthz"


# --- helper function --------------------------------------------------------


def test_helper_adds_and_disconnects(api, monkeypatch):
    monkeypatch.setenv("UPTIME_KUMA_USERNAME", "u")
    monkeypatch.setenv("UPTIME_KUMA_PASSWORD", "p")
    out = uk.add_fabrik_service_to_monitoring("svc")
    assert out["status"] == "created"
    assert api.add_monitor.call_args.kwargs["url"] == "https://svc.vps1.ocoron.com/health"
    api.login.assert_called_once_with("u", "p")
    api.disconnect.assert_called_once()


def test_helper_disconnects_on_error(api):
    api.add_monitor.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        uk.add_fabrik_service_to_monitoring("svc", domain="d.com", health_endpoint="/h")
    api.disconnect.assert_called_once()
