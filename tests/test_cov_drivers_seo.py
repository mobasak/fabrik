"""Coverage sweep for fabrik.drivers.seo.SEOClient (hermetic: httpx.Client is faked)."""

import logging
from unittest.mock import MagicMock

import httpx
import pytest

from fabrik.drivers import seo as seo_mod
from fabrik.drivers.seo import SEOClient


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("SEO_API_URL", raising=False)
    monkeypatch.delenv("SEO_API_KEY", raising=False)


@pytest.fixture
def http(monkeypatch):
    """Patch httpx.Client; return (client_cls_mock, instance_mock)."""
    inst = MagicMock()
    resp = MagicMock()
    resp.json.return_value = {}
    inst.request.return_value = resp
    cls = MagicMock(return_value=inst)
    monkeypatch.setattr(seo_mod.httpx, "Client", cls)
    inst.cls = cls
    inst.resp = resp
    return inst


@pytest.fixture
def client(http):
    return SEOClient(base_url="http://seo.test", token="tok")


# --- constructor -----------------------------------------------------------


def test_defaults_from_env(monkeypatch, http):
    monkeypatch.setenv("SEO_API_URL", "http://env-seo:1")
    monkeypatch.setenv("SEO_API_KEY", "envkey")
    c = SEOClient()
    assert c.base_url == "http://env-seo:1"
    assert c.token == "envkey"
    assert http.cls.call_args.kwargs["headers"]["Authorization"] == "Bearer envkey"


def test_default_url_when_unset(http):
    assert SEOClient(token="t").base_url == "http://localhost:8016"


def test_explicit_args_override_env(monkeypatch, http):
    monkeypatch.setenv("SEO_API_URL", "http://env")
    monkeypatch.setenv("SEO_API_KEY", "envkey")
    c = SEOClient(base_url="http://arg", token="argtok", timeout=7.5)
    assert (c.base_url, c.token, c.timeout) == ("http://arg", "argtok", 7.5)
    kw = http.cls.call_args.kwargs
    assert kw["timeout"] == 7.5
    assert kw["headers"]["Authorization"] == "Bearer argtok"


def test_headers_json(http):
    SEOClient(token="t")
    h = http.cls.call_args.kwargs["headers"]
    assert h["Accept"] == "application/json"
    assert h["Content-Type"] == "application/json"


def test_no_token_warns_and_omits_auth(http, caplog):
    with caplog.at_level(logging.WARNING, logger="fabrik.drivers.seo"):
        SEOClient()
    assert "Authorization" not in http.cls.call_args.kwargs["headers"]
    assert "SEO_API_KEY not set" in caplog.text


def test_token_present_no_warning(http, caplog):
    with caplog.at_level(logging.WARNING, logger="fabrik.drivers.seo"):
        SEOClient(token="t")
    assert "SEO_API_KEY" not in caplog.text


# --- _request ---------------------------------------------------------------


def test_request_builds_url_and_returns_json(client, http):
    http.resp.json.return_value = {"ok": 1}
    assert client._request("GET", "/x", params={"a": 1}) == {"ok": 1}
    http.request.assert_called_once_with("GET", "http://seo.test/x", params={"a": 1})


def test_request_propagates_http_error(client, http):
    http.resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "409", request=MagicMock(), response=MagicMock()
    )
    with pytest.raises(httpx.HTTPStatusError):
        client._request("POST", "/x")
    http.resp.json.assert_not_called()


# --- sites -------------------------------------------------------------------


def test_get_site_by_domain_queries_active_sites(client, http):
    http.resp.json.return_value = {"sites": []}
    client.get_site_by_domain("a.com")
    http.request.assert_called_once_with(
        "GET", "http://seo.test/api/v1/sites", params={"active": True}
    )


def test_get_site_by_domain_missing_sites_key(client, http):
    http.resp.json.return_value = {}
    assert client.get_site_by_domain("a.com") is None


def test_get_site_by_domain_site_without_domain_skipped(client, http):
    http.resp.json.return_value = {"sites": [{"site_id": "1"}, {"site_id": "2", "domain": "A.com"}]}
    assert client.get_site_by_domain("a.com")["site_id"] == "2"


def test_register_site_minimal_payload(client, http):
    client.register_site("c", "N", "d.com", "en-US", "us", "en")
    args, kwargs = http.request.call_args
    assert args == ("POST", "http://seo.test/api/v1/sites")
    assert kwargs["json"] == {
        "code": "c",
        "name": "N",
        "domain": "d.com",
        "default_locale": "en-US",
        "country_code": "us",
        "language_code": "en",
        "rendering_mode": "ssr",
    }


def test_register_site_optional_fields(client, http):
    client.register_site(
        "c",
        "N",
        "d.com",
        "en-US",
        "us",
        "en",
        rendering_mode="ssg",
        category="saas",
        author_profile_url="https://d.com/about",
        knowledge_base={"indexnow_api_key": "k"},
    )
    p = http.request.call_args.kwargs["json"]
    assert p["rendering_mode"] == "ssg"
    assert p["category"] == "saas"
    assert p["author_profile_url"] == "https://d.com/about"
    assert p["knowledge_base"] == {"indexnow_api_key": "k"}


def test_register_site_empty_knowledge_base_still_sent(client, http):
    client.register_site("c", "N", "d.com", "en-US", "us", "en", knowledge_base={})
    assert http.request.call_args.kwargs["json"]["knowledge_base"] == {}


def test_ensure_site_returns_existing_without_registering(client, http):
    http.resp.json.return_value = {"sites": [{"site_id": 42, "domain": "d.com"}]}
    assert client.ensure_site("d.com", "D") == "42"
    assert http.request.call_count == 1


def test_ensure_site_creates_when_missing(client, http):
    http.resp.json.side_effect = [{"sites": []}, {"site_id": "new-1"}]
    sid = client.ensure_site(
        "my.example.com", "My", country_code="gb", language_code="en", category="saas"
    )
    assert sid == "new-1"
    assert http.request.call_count == 2
    p = http.request.call_args.kwargs["json"]
    assert p["code"] == "my-example-com"
    assert p["default_locale"] == "en-GB"
    assert p["country_code"] == "gb"
    assert p["category"] == "saas"
    assert p["name"] == "My"
    assert p["domain"] == "my.example.com"


def test_ensure_site_default_locale(client, http):
    http.resp.json.side_effect = [{"sites": []}, {"site_id": "n"}]
    client.ensure_site("d.com", "D")
    assert http.request.call_args.kwargs["json"]["default_locale"] == "en-US"


# --- jobs ----------------------------------------------------------------------


def test_create_job_minimal(client, http):
    client.create_job("s1", ["topic"])
    args, kwargs = http.request.call_args
    assert args == ("POST", "http://seo.test/api/v1/sites/s1/seo/jobs")
    assert kwargs["json"] == {"seed_topics": ["topic"]}


def test_create_job_all_options(client, http):
    client.create_job(
        "s1",
        ["a", "b"],
        country_code="de",
        language_code="de",
        page_type_override="pricing",
        provider_config={"x": 1},
    )
    assert http.request.call_args.kwargs["json"] == {
        "seed_topics": ["a", "b"],
        "country_code": "de",
        "language_code": "de",
        "page_type_override": "pricing",
        "provider_config": {"x": 1},
    }


def test_run_job_and_get_job_endpoints(client, http):
    client.run_job("j1")
    assert http.request.call_args.args == ("POST", "http://seo.test/api/v1/seo/jobs/j1/run")
    client.get_job("j1")
    assert http.request.call_args.args == ("GET", "http://seo.test/api/v1/seo/jobs/j1")


@pytest.fixture
def no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(seo_mod.time, "sleep", sleeps.append)
    return sleeps


def test_wait_for_job_completes_after_polling(client, http, no_sleep):
    http.resp.json.side_effect = [
        {"status": "running"},
        {"status": "running"},
        {"status": "completed", "id": "j"},
    ]
    assert client.wait_for_job("j", poll_interval=3)["id"] == "j"
    assert no_sleep == [3, 3]


def test_wait_for_job_immediate_complete_no_sleep(client, http, no_sleep):
    http.resp.json.return_value = {"status": "completed"}
    client.wait_for_job("j")
    assert no_sleep == []


def test_wait_for_job_failed_raises_with_message(client, http, no_sleep):
    http.resp.json.return_value = {"status": "failed", "error_message": "boom"}
    with pytest.raises(RuntimeError, match="j failed: boom"):
        client.wait_for_job("j")


def test_wait_for_job_timeout(client, http, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(seo_mod.time, "time", lambda: now[0])
    monkeypatch.setattr(seo_mod.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    http.resp.json.return_value = {"status": "running"}
    with pytest.raises(TimeoutError, match="did not complete within 20s"):
        client.wait_for_job("j", timeout=20, poll_interval=5)
    assert http.request.call_count == 4


# --- briefs --------------------------------------------------------------------


def test_list_ready_briefs_params_and_default(client, http):
    http.resp.json.return_value = {}
    assert client.list_ready_briefs("s1") == []
    http.request.assert_called_once_with(
        "GET", "http://seo.test/api/v1/briefs", params={"status": "ready", "site_id": "s1"}
    )


def test_list_briefs_without_status(client, http):
    http.resp.json.return_value = {"briefs": [{"brief_id": "b"}]}
    assert client.list_briefs("s1") == [{"brief_id": "b"}]
    assert http.request.call_args.kwargs["params"] == {"site_id": "s1"}


def test_list_briefs_with_status(client, http):
    client.list_briefs("s1", status="draft")
    assert http.request.call_args.kwargs["params"] == {"site_id": "s1", "status": "draft"}


def test_get_brief_endpoint(client, http):
    http.resp.json.return_value = {"brief_id": "b"}
    assert client.get_brief("b") == {"brief_id": "b"}
    assert http.request.call_args.args == ("GET", "http://seo.test/api/v1/briefs/b")


def test_claim_release_submit_payloads(client, http):
    client.claim_brief("b", "w")
    assert http.request.call_args.args == ("POST", "http://seo.test/api/v1/briefs/b/claim")
    assert http.request.call_args.kwargs["json"] == {"worker_id": "w"}
    client.release_brief("b", "w")
    assert http.request.call_args.args == ("POST", "http://seo.test/api/v1/briefs/b/release")
    assert http.request.call_args.kwargs["json"] == {"worker_id": "w"}
    client.submit_brief("b", "w", {"final_slug": "s"})
    assert http.request.call_args.args == ("POST", "http://seo.test/api/v1/briefs/b/submit")
    assert http.request.call_args.kwargs["json"] == {
        "worker_id": "w",
        "submission": {"final_slug": "s"},
    }


def test_claim_conflict_propagates(client, http):
    http.resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "409", request=MagicMock(), response=MagicMock()
    )
    with pytest.raises(httpx.HTTPStatusError):
        client.claim_brief("b", "w")


# --- lifecycle -------------------------------------------------------------------


def test_close_closes_http_client(client, http):
    client.close()
    http.close.assert_called_once_with()


def test_context_manager_closes_and_returns_self(http):
    with SEOClient(token="t") as c:
        assert isinstance(c, SEOClient)
        http.close.assert_not_called()
    http.close.assert_called_once_with()


def test_context_manager_closes_on_exception(http):
    with pytest.raises(ValueError):
        with SEOClient(token="t"):
            raise ValueError("x")
    http.close.assert_called_once_with()
