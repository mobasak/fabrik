"""Tests for dependency-aware health endpoint."""

from fastapi.testclient import TestClient

from fabrik import health_app


class _HealthyCoolify:
    def __init__(self, *args, **kwargs):
        pass

    def health(self):
        return {"status": "ok"}


class _HealthyDNS:
    def __init__(self, *args, **kwargs):
        pass

    def health(self):
        return {"status": "healthy"}


class _FailingCoolify:
    def __init__(self, *args, **kwargs):
        raise ValueError("missing COOLIFY_API_TOKEN")


class _FailingDNS:
    def __init__(self, *args, **kwargs):
        pass

    def health(self):
        raise RuntimeError("dns service down")


def test_health_reports_ok_when_dependencies_healthy(monkeypatch):
    monkeypatch.setattr(health_app, "CoolifyClient", _HealthyCoolify)
    monkeypatch.setattr(health_app, "DNSClient", _HealthyDNS)

    client = TestClient(health_app.app)
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["coolify"]["status"] == "healthy"
    assert body["checks"]["dns"]["status"] == "healthy"


def test_health_degrades_when_dependencies_fail(monkeypatch):
    monkeypatch.setattr(health_app, "CoolifyClient", _FailingCoolify)
    monkeypatch.setattr(health_app, "DNSClient", _FailingDNS)

    client = TestClient(health_app.app)
    response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["coolify"]["status"] == "unhealthy"
    assert body["checks"]["dns"]["status"] == "unhealthy"
