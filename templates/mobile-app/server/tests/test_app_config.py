"""Backend route tests — /health + /app-config (Phase B, Behavior Contract 169).

Runnable in WSL and the scaffolded project's CI (pure Python + FastAPI TestClient,
no RN toolchain). Proves the client↔backend /app-config contract: platform+version
are required, the server owns the force-update verdict (incl. the 1.10.0>1.9.0
numeric-not-string comparison), and malformed operator config fails open.
"""

from __future__ import annotations

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_app_config_requires_platform_and_version():
    # The client MUST send both — a bare GET (the pre-fix bug) is a 422.
    assert client.get("/app-config").status_code == 422
    assert client.get("/app-config", params={"platform": "ios"}).status_code == 422
    assert client.get("/app-config", params={"version": "1.0.0"}).status_code == 422


def test_app_config_blocks_below_min(monkeypatch):
    monkeypatch.setenv("APP_MIN_VERSION", "2.0.0")
    r = client.get("/app-config", params={"platform": "ios", "version": "1.0.0"})
    assert r.status_code == 200
    body = r.json()
    assert body["update_required"] is True
    assert body["store_urls"] == {"android": "", "ios": ""}


def test_app_config_numeric_semver_not_string(monkeypatch):
    # 1.10.0 > 1.9.0 numerically — a string compare would wrongly force an update.
    monkeypatch.setenv("APP_MIN_VERSION", "1.9.0")
    r = client.get("/app-config", params={"platform": "ios", "version": "1.10.0"})
    assert r.json()["update_required"] is False


def test_app_config_no_gate_never_blocks():
    # No APP_MIN_VERSION configured → never blocks entry.
    r = client.get("/app-config", params={"platform": "android", "version": "0.0.1"})
    assert r.status_code == 200
    assert r.json()["update_required"] is False


def test_app_config_malformed_flags_fail_open(monkeypatch):
    monkeypatch.setenv("APP_FEATURE_FLAGS", "{not valid json")
    r = client.get("/app-config", params={"platform": "ios", "version": "1.0.0"})
    assert r.status_code == 200
    assert r.json()["features"] == {}
