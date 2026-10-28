"""Coverage for fabrik.notifications: best-effort n8n webhook helpers (hermetic, httpx mocked)."""

import logging
import sys

import httpx
import pytest

from fabrik import notifications
from fabrik.notifications import _post, notify_content, notify_deploy


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("N8N_WEBHOOK_DEPLOY", "N8N_WEBHOOK_CONTENT", "N8N_WEBHOOK_TIMEOUT"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def calls(monkeypatch):
    rec = []

    def fake_post(url, **kw):
        rec.append((url, kw))

    monkeypatch.setattr(httpx, "post", fake_post)
    return rec


# ---- _post ----


def test_post_sends_json_with_default_timeout(calls):
    _post("http://h/x", {"event": "e"})
    assert calls == [("http://h/x", {"json": {"event": "e"}, "timeout": 5.0})]


def test_post_timeout_from_env(calls, monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_TIMEOUT", "2.5")
    _post("http://h/x", {})
    assert calls[0][1]["timeout"] == 2.5


def test_post_swallows_http_error_and_warns(monkeypatch, caplog):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", boom)
    with caplog.at_level(logging.WARNING, logger="fabrik.notifications"):
        _post("http://h/x", {"event": "e"})
    assert any(
        "Webhook delivery failed" in r.message and "down" in r.message for r in caplog.records
    )


def test_post_bad_timeout_env_is_swallowed(calls, monkeypatch, caplog):
    monkeypatch.setenv("N8N_WEBHOOK_TIMEOUT", "abc")
    with caplog.at_level(logging.WARNING, logger="fabrik.notifications"):
        _post("http://h/x", {})
    assert calls == []
    assert any("Webhook delivery failed" in r.message for r in caplog.records)


def test_post_swallows_missing_httpx(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "httpx", None)  # import httpx -> ImportError
    with caplog.at_level(logging.WARNING, logger="fabrik.notifications"):
        _post("http://h/x", {})
    assert any("Webhook delivery failed" in r.message for r in caplog.records)


def test_post_debug_logs_event(calls, caplog):
    with caplog.at_level(logging.DEBUG, logger="fabrik.notifications"):
        _post("http://h/x", {"event": "deploy.success"})
    assert any("deploy.success" in r.getMessage() for r in caplog.records)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="notifications.py:24 never checks the status: a 5xx from the webhook is a silent failure",
)
def test_post_warns_on_server_error(monkeypatch, caplog):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(500))
    with caplog.at_level(logging.WARNING, logger="fabrik.notifications"):
        assert _post("http://h/x", {}) is None
    assert any(r.levelno == logging.WARNING for r in caplog.records)


# ---- notify_deploy ----


def test_deploy_noop_without_env(calls):
    assert notify_deploy(project="p", domain="d", success=True) is None
    assert calls == []


def test_deploy_empty_env_is_noop(calls, monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_DEPLOY", "")
    notify_deploy(project="p", domain="d", success=True)
    assert calls == []


def test_deploy_success_payload(calls, monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_DEPLOY", "http://n8n/deploy")
    notify_deploy(project="p", domain="d.com", success=True, url="https://d.com")
    url, kw = calls[0]
    assert url == "http://n8n/deploy"
    assert kw["json"] == {
        "event": "deploy.success",
        "project": "p",
        "domain": "d.com",
        "url": "https://d.com",
        "error": None,
        "error_step": None,
    }


def test_deploy_failure_payload(calls, monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_DEPLOY", "http://n8n/deploy")
    notify_deploy(project="p", domain="d", success=False, error="bad", error_step="compose")
    payload = calls[0][1]["json"]
    assert payload["event"] == "deploy.failure"
    assert payload["error"] == "bad"
    assert payload["error_step"] == "compose"
    assert payload["url"] is None


def test_deploy_does_not_use_content_webhook(calls, monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_CONTENT", "http://n8n/content")
    notify_deploy(project="p", domain="d", success=True)
    assert calls == []


def test_deploy_keyword_only():
    with pytest.raises(TypeError):
        notify_deploy("p", "d", True)  # type: ignore[misc]


def test_deploy_requires_args():
    with pytest.raises(TypeError):
        notify_deploy(project="p")  # type: ignore[call-arg]


def test_deploy_never_raises_on_network_failure(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_DEPLOY", "http://n8n/deploy")

    def boom(*a, **k):
        raise RuntimeError("x")

    monkeypatch.setattr(httpx, "post", boom)
    assert notify_deploy(project="p", domain="d", success=True) is None


# ---- notify_content ----


def test_content_noop_without_env(calls):
    assert notify_content(domain="d", published=1, failed=0) is None
    assert calls == []


def test_content_payload_defaults(calls, monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_CONTENT", "http://n8n/content")
    notify_content(domain="d.com", published=3, failed=1)
    url, kw = calls[0]
    assert url == "http://n8n/content"
    assert kw["json"] == {
        "event": "content.published",
        "domain": "d.com",
        "published": 3,
        "failed": 1,
        "dry_run": False,
    }


def test_content_dry_run_flag(calls, monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_CONTENT", "http://n8n/content")
    notify_content(domain="d", published=0, failed=0, dry_run=True)
    assert calls[0][1]["json"]["dry_run"] is True


def test_content_does_not_use_deploy_webhook(calls, monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_DEPLOY", "http://n8n/deploy")
    notify_content(domain="d", published=1, failed=0)
    assert calls == []


def test_content_keyword_only():
    with pytest.raises(TypeError):
        notify_content("d", 1, 0)  # type: ignore[misc]


def test_content_never_raises_on_network_failure(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_CONTENT", "http://n8n/content")

    def boom(*a, **k):
        raise httpx.TimeoutException("t")

    monkeypatch.setattr(httpx, "post", boom)
    assert notify_content(domain="d", published=1, failed=0) is None


def test_module_logger_name():
    assert notifications.logger.name == "fabrik.notifications"
