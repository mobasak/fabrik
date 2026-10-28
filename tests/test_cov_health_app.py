"""Coverage tests for fabrik.health_app (hermetic: DNSClient and directories mocked)."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from fabrik import health_app


class _DNS:
    def __init__(self, result=None, exc=None):
        self._result = result
        self._exc = exc

    def health(self):
        if self._exc:
            raise self._exc
        return self._result


def _patch_dns(monkeypatch, result=None, exc=None):
    monkeypatch.setattr(health_app, "DNSClient", lambda: _DNS(result, exc))


# ---- _normalize_status ----


@pytest.mark.parametrize("value", ["ok", "healthy", "pass", "success", "OK", "Healthy"])
def test_normalize_dict_healthy_values(value):
    payload = {"status": value, "x": 1}
    assert health_app._normalize_status(payload) == ("healthy", payload)


@pytest.mark.parametrize("payload", [{"status": "down"}, {}, {"status": None}, {"other": "ok"}])
def test_normalize_dict_unhealthy(payload):
    state, details = health_app._normalize_status(payload)
    assert state == "unhealthy"
    assert details is payload


def test_normalize_bool_true():
    assert health_app._normalize_status(True) == ("healthy", {"status": "healthy"})


def test_normalize_bool_false():
    assert health_app._normalize_status(False) == ("unhealthy", {"status": "unhealthy"})


@pytest.mark.parametrize("s", ["ok", "PASS", "Success", "healthy"])
def test_normalize_str_healthy(s):
    assert health_app._normalize_status(s) == ("healthy", {"status": s})


def test_normalize_str_unhealthy():
    assert health_app._normalize_status("bad") == ("unhealthy", {"status": "bad"})


@pytest.mark.parametrize("payload", [None, 5, [1, 2], 1.5])
def test_normalize_other_types_unknown(payload):
    assert health_app._normalize_status(payload) == (
        "unhealthy",
        {"status": "unknown", "detail": payload},
    )


# ---- _check_dns_sync ----


def test_check_dns_sync_healthy(monkeypatch):
    _patch_dns(monkeypatch, {"status": "ok"})
    assert health_app._check_dns_sync() == {
        "status": "healthy",
        "details": {"status": "ok"},
    }


def test_check_dns_sync_unhealthy_payload(monkeypatch):
    _patch_dns(monkeypatch, {"status": "down"})
    out = health_app._check_dns_sync()
    assert out["status"] == "unhealthy"
    assert out["details"] == {"status": "down"}


def test_check_dns_sync_health_raises(monkeypatch, caplog):
    _patch_dns(monkeypatch, exc=RuntimeError("boom"))
    with caplog.at_level(logging.WARNING, logger=health_app.logger.name):
        out = health_app._check_dns_sync()
    assert out == {"status": "unhealthy", "error": "boom"}
    assert "boom" in caplog.text


def test_check_dns_sync_constructor_raises(monkeypatch):
    def _bad():
        raise ValueError("no config")

    monkeypatch.setattr(health_app, "DNSClient", _bad)
    assert health_app._check_dns_sync() == {"status": "unhealthy", "error": "no config"}


# ---- endpoints ----


def test_health_endpoint_ok(monkeypatch):
    _patch_dns(monkeypatch, "healthy")
    r = TestClient(health_app.app).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "fabrik"
    assert body["status"] == "ok"
    assert body["checks"]["dns"]["status"] == "healthy"


def test_health_endpoint_degraded_on_exception(monkeypatch):
    _patch_dns(monkeypatch, exc=ConnectionError("dns down"))
    r = TestClient(health_app.app).get("/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["checks"]["dns"] == {"status": "unhealthy", "error": "dns down"}


def test_health_endpoint_degraded_on_bad_status(monkeypatch):
    _patch_dns(monkeypatch, {"status": "fail"})
    r = TestClient(health_app.app).get("/health")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"


def test_root_endpoint():
    r = TestClient(health_app.app).get("/")
    assert r.status_code == 200
    assert r.json() == {"service": "fabrik", "status": "ready"}


def test_app_metadata():
    assert health_app.app.title == "Fabrik"
    assert health_app.app.version == "0.1.0"
    paths = {route.path for route in health_app.app.routes}
    assert {"/health", "/"} <= paths


def test_lifespan_calls_ensure_directories(monkeypatch):
    calls = []
    monkeypatch.setattr(health_app, "ensure_directories", lambda: calls.append(1))
    with TestClient(health_app.app) as client:
        assert calls == [1]
        assert client.get("/").status_code == 200
