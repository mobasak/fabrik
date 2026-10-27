"""Hermetic coverage for fabrik.drivers.cloudflare (httpx.MockTransport, no network)."""

import json

import httpx
import pytest

from fabrik.drivers.cloudflare import CloudflareClient

BASE = "https://api.cloudflare.com/client/v4"


def ok(result):
    return {"success": True, "errors": [], "result": result}


def make_client(handler, account_id="acc1", token="tok"):
    # Swap only the transport: base URL and headers stay the production client's, so a wrong
    # API version or a dropped Authorization header reaches the handler and fails the test.
    cf = CloudflareClient(api_token=token, account_id=account_id)
    real = cf._client
    cf._client = httpx.Client(
        base_url=real.base_url,
        transport=httpx.MockTransport(handler),
        headers=real.headers,
        timeout=real.timeout,
    )
    real.close()
    return cf


class Recorder:
    """Route (method, path) -> payload; records every request."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        params = dict(request.url.params)
        self.calls.append((request.method, request.url.path, params, body))
        key = (request.method, request.url.path)
        route = self.routes[key]
        if callable(route):
            route = route(params, body)
        return httpx.Response(200, json=route)


# --- construction ---


def test_init_requires_token(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="CLOUDFLARE_API_TOKEN"):
        CloudflareClient()


def test_init_reads_env(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "envtok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "envacc")
    cf = CloudflareClient()
    try:
        assert cf.api_token == "envtok"
        assert cf.account_id == "envacc"
        assert cf._client.headers["Authorization"] == "Bearer envtok"
    finally:
        cf.close()


def test_init_explicit_args_override_env(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "envtok")
    cf = CloudflareClient(api_token="explicit", account_id="a", timeout=5)
    try:
        assert cf.api_token == "explicit"
        assert cf.account_id == "a"
        assert cf.timeout == 5
    finally:
        cf.close()


def test_context_manager_closes():
    with CloudflareClient(api_token="t") as cf:
        assert not cf._client.is_closed
    assert cf._client.is_closed


# --- _request ---


def test_request_returns_result():
    cf = make_client(Recorder({("GET", "/client/v4/x"): ok({"a": 1})}))
    assert cf._request("GET", "/x") == {"a": 1}


def test_request_error_joins_messages():
    body = {"success": False, "errors": [{"message": "bad"}, {"message": "worse"}]}
    cf = make_client(Recorder({("GET", "/client/v4/x"): body}))
    with pytest.raises(Exception, match="Cloudflare API error: bad; worse"):
        cf._request("GET", "/x")


def test_request_error_without_message_uses_str():
    body = {"success": False, "errors": [{"code": 7}]}
    cf = make_client(Recorder({("GET", "/client/v4/x"): body}))
    with pytest.raises(Exception, match="code"):
        cf._request("GET", "/x")


def test_request_missing_success_is_error():
    cf = make_client(Recorder({("GET", "/client/v4/x"): {"result": 1}}))
    with pytest.raises(Exception, match="Cloudflare API error"):
        cf._request("GET", "/x")


# --- token / health ---


def test_verify_token_uses_account_endpoint():
    rec = Recorder({("GET", "/client/v4/accounts/acc1/tokens/verify"): ok({"status": "active"})})
    assert make_client(rec).verify_token() == {"status": "active"}


def test_verify_token_user_endpoint_without_account(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    rec = Recorder({("GET", "/client/v4/user/tokens/verify"): ok({"status": "active"})})
    assert make_client(rec, account_id=None).verify_token()["status"] == "active"


def test_health_healthy():
    rec = Recorder(
        {("GET", "/client/v4/accounts/acc1/tokens/verify"): ok({"status": "active", "id": "i"})}
    )
    assert make_client(rec).health() == {
        "status": "healthy",
        "token_status": "active",
        "token_id": "i",
    }


def test_health_unhealthy_swallows_error_into_dict():
    body = {"success": False, "errors": [{"message": "Invalid token"}]}
    rec = Recorder({("GET", "/client/v4/accounts/acc1/tokens/verify"): body})
    out = make_client(rec).health()
    assert out["status"] == "unhealthy"
    assert "Invalid token" in out["error"]


# --- zones ---


def test_list_zones_with_and_without_name():
    rec = Recorder({("GET", "/client/v4/zones"): ok([])})
    cf = make_client(rec)
    cf.list_zones()
    cf.list_zones(name="a.com")
    assert rec.calls[0][2] == {}
    assert rec.calls[1][2] == {"name": "a.com"}


def test_create_zone_payload():
    rec = Recorder({("POST", "/client/v4/zones"): ok({"id": "z"})})
    assert make_client(rec).create_zone("a.com") == {"id": "z"}
    assert rec.calls[0][3] == {"name": "a.com", "account": {"id": "acc1"}, "type": "full"}


def test_create_zone_requires_account(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    cf = make_client(Recorder({}), account_id=None)
    with pytest.raises(ValueError, match="CLOUDFLARE_ACCOUNT_ID"):
        cf.create_zone("a.com")


def test_get_zone_and_status():
    zone = {"id": "z", "status": "active", "name_servers": ["n1", "n2"], "paused": True}
    cf = make_client(Recorder({("GET", "/client/v4/zones/z"): ok(zone)}))
    assert cf.get_zone("z") == zone
    assert cf.get_zone_status("z") == {
        "status": "active",
        "name_servers": ["n1", "n2"],
        "paused": True,
    }


def test_get_zone_status_defaults():
    cf = make_client(Recorder({("GET", "/client/v4/zones/z"): ok({"id": "z"})}))
    assert cf.get_zone_status("z") == {"status": None, "name_servers": [], "paused": False}


def test_ensure_zone_existing():
    z = {"id": "z", "status": "active", "name_servers": ["n"]}
    rec = Recorder({("GET", "/client/v4/zones"): ok([z])})
    out = make_client(rec).ensure_zone("a.com")
    assert out == {"zone_id": "z", "status": "active", "name_servers": ["n"], "created": False}
    assert len(rec.calls) == 1


def test_ensure_zone_creates_when_missing():
    rec = Recorder(
        {
            ("GET", "/client/v4/zones"): ok([]),
            ("POST", "/client/v4/zones"): ok({"id": "new", "status": "pending"}),
        }
    )
    out = make_client(rec).ensure_zone("a.com")
    assert out == {"zone_id": "new", "status": "pending", "name_servers": [], "created": True}


def test_get_zone_id_direct():
    rec = Recorder({("GET", "/client/v4/zones"): ok([{"id": "z1"}])})
    assert make_client(rec).get_zone_id("a.com") == "z1"


def test_get_zone_id_walks_up_subdomains():
    def zones(params, body):
        return ok([{"id": "root"}] if params["name"] == "a.com" else [])

    rec = Recorder({("GET", "/client/v4/zones"): zones})
    assert make_client(rec).get_zone_id("x.y.a.com") == "root"
    assert [c[2]["name"] for c in rec.calls] == ["x.y.a.com", "y.a.com", "a.com"]


def test_get_zone_id_not_found_never_queries_bare_tld():
    rec = Recorder({("GET", "/client/v4/zones"): ok([])})
    with pytest.raises(ValueError, match="Zone not found for domain: x.a.com"):
        make_client(rec).get_zone_id("x.a.com")
    assert "com" not in [c[2]["name"] for c in rec.calls]


# --- records ---


def test_list_records_filters():
    rec = Recorder({("GET", "/client/v4/zones/z/dns_records"): ok([])})
    cf = make_client(rec)
    cf.list_records("z")
    cf.list_records("z", record_type="A", name="h.a.com")
    assert rec.calls[0][2] == {}
    assert rec.calls[1][2] == {"type": "A", "name": "h.a.com"}


def test_get_record():
    cf = make_client(Recorder({("GET", "/client/v4/zones/z/dns_records/r"): ok({"id": "r"})}))
    assert cf.get_record("z", "r") == {"id": "r"}


def test_create_record_minimal_payload():
    rec = Recorder({("POST", "/client/v4/zones/z/dns_records"): ok({"id": "r"})})
    make_client(rec).create_record("z", "A", "h", "1.2.3.4")
    assert rec.calls[0][3] == {
        "type": "A",
        "name": "h",
        "content": "1.2.3.4",
        "ttl": 1,
        "proxied": False,
    }


def test_create_record_optional_fields():
    rec = Recorder({("POST", "/client/v4/zones/z/dns_records"): ok({})})
    make_client(rec).create_record(
        "z", "MX", "h", "m.a.com", ttl=300, proxied=True, priority=0, comment="c"
    )
    body = rec.calls[0][3]
    assert body["priority"] == 0  # 0 is a valid priority, must not be dropped
    assert body["comment"] == "c"
    assert body["ttl"] == 300 and body["proxied"] is True


def test_update_record_put_with_optionals():
    rec = Recorder({("PUT", "/client/v4/zones/z/dns_records/r"): ok({"id": "r"})})
    make_client(rec).update_record("z", "r", "A", "h", "9.9.9.9", priority=5, comment="x")
    body = rec.calls[0][3]
    assert rec.calls[0][0] == "PUT"
    assert body["content"] == "9.9.9.9" and body["priority"] == 5 and body["comment"] == "x"


def test_update_record_omits_unset_optionals():
    rec = Recorder({("PUT", "/client/v4/zones/z/dns_records/r"): ok({})})
    make_client(rec).update_record("z", "r", "A", "h", "1.1.1.1")
    assert "priority" not in rec.calls[0][3] and "comment" not in rec.calls[0][3]


def test_delete_record():
    rec = Recorder({("DELETE", "/client/v4/zones/z/dns_records/r"): ok({"id": "r"})})
    assert make_client(rec).delete_record("z", "r") == {"id": "r"}


# --- high-level helpers ---

ZONES = ("GET", "/client/v4/zones")
RECS = ("GET", "/client/v4/zones/z/dns_records")


def existing_record(**over):
    r = {"id": "r1", "content": "1.1.1.1", "proxied": False, "ttl": 1}
    r.update(over)
    return r


def test_ensure_record_creates_with_full_name():
    rec = Recorder(
        {
            ZONES: ok([{"id": "z"}]),
            RECS: ok([]),
            ("POST", "/client/v4/zones/z/dns_records"): ok({"id": "new"}),
        }
    )
    out = make_client(rec).ensure_record("a.com", "A", "app", "1.1.1.1", comment="c")
    assert out == {"action": "created", "record": {"id": "new"}}
    assert rec.calls[1][2] == {"type": "A", "name": "app.a.com"}
    assert rec.calls[2][3]["name"] == "app.a.com" and rec.calls[2][3]["comment"] == "c"


def test_ensure_record_unchanged():
    rec = Recorder({ZONES: ok([{"id": "z"}]), RECS: ok([existing_record()])})
    out = make_client(rec).ensure_record("a.com", "A", "app", "1.1.1.1")
    assert out["action"] == "unchanged"
    assert all(c[0] == "GET" for c in rec.calls)


def test_ensure_record_unchanged_when_ttl_matches():
    rec = Recorder({ZONES: ok([{"id": "z"}]), RECS: ok([existing_record(ttl=300)])})
    assert make_client(rec).ensure_record("a.com", "A", "app", "1.1.1.1", ttl=300)["action"] == (
        "unchanged"
    )


@pytest.mark.parametrize(
    "existing,kwargs",
    [
        (existing_record(content="2.2.2.2"), {}),
        (existing_record(proxied=True), {}),
        (existing_record(ttl=60), {"ttl": 300}),
    ],
)
def test_ensure_record_updates_on_difference(existing, kwargs):
    rec = Recorder(
        {
            ZONES: ok([{"id": "z"}]),
            RECS: ok([existing]),
            ("PUT", "/client/v4/zones/z/dns_records/r1"): ok({"id": "r1", "upd": True}),
        }
    )
    out = make_client(rec).ensure_record("a.com", "A", "app", "1.1.1.1", **kwargs)
    assert out == {"action": "updated", "record": {"id": "r1", "upd": True}}
    assert rec.calls[-1][0] == "PUT"


def test_ensure_record_empty_name_is_apex():
    rec = Recorder(
        {
            ZONES: ok([{"id": "z"}]),
            RECS: ok([]),
            ("POST", "/client/v4/zones/z/dns_records"): ok({}),
        }
    )
    make_client(rec).ensure_record("a.com", "A", "", "1.1.1.1")
    assert rec.calls[2][3]["name"] == "a.com"


def test_ensure_record_name_already_qualified_not_doubled():
    rec = Recorder(
        {
            ZONES: ok([{"id": "z"}]),
            RECS: ok([]),
            ("POST", "/client/v4/zones/z/dns_records"): ok({}),
        }
    )
    make_client(rec).ensure_record("a.com", "A", "app.a.com", "1.1.1.1")
    assert rec.calls[2][3]["name"] == "app.a.com"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="cloudflare.py:296 name.endswith(domain) treats label 'myappa.com' as already qualified",
)
def test_ensure_record_label_ending_with_domain_text_is_still_subdomain():
    rec = Recorder(
        {
            ZONES: ok([{"id": "z"}]),
            RECS: ok([]),
            ("POST", "/client/v4/zones/z/dns_records"): ok({}),
        }
    )
    make_client(rec).ensure_record("a.com", "A", "myappa.com", "1.1.1.1")
    assert rec.calls[2][3]["name"] == "myappa.com.a.com"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="cloudflare.py:335 name.endswith(domain) treats label 'myappa.com' as already qualified",
)
def test_delete_record_by_name_label_ending_with_domain_text_is_still_subdomain():
    rec = Recorder({ZONES: ok([{"id": "z"}]), RECS: ok([])})
    out = make_client(rec).delete_record_by_name("a.com", "A", "myappa.com")
    assert out["name"] == "myappa.com.a.com"


def test_requests_carry_the_production_bearer_header():
    seen = []

    def handler(request):
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json=ok([{"id": "z"}]))

    make_client(handler, token="sekret").get_zone_id("a.com")
    assert seen and set(seen) == {"Bearer sekret"}


def test_ensure_record_zone_missing_propagates():
    rec = Recorder({ZONES: ok([])})
    with pytest.raises(ValueError, match="Zone not found"):
        make_client(rec).ensure_record("a.com", "A", "app", "1.1.1.1")


def test_delete_record_by_name_not_found():
    rec = Recorder({ZONES: ok([{"id": "z"}]), RECS: ok([])})
    assert make_client(rec).delete_record_by_name("a.com", "A", "app") == {
        "action": "not_found",
        "name": "app.a.com",
    }


def test_delete_record_by_name_deletes_first_match():
    rec = Recorder(
        {
            ZONES: ok([{"id": "z"}]),
            RECS: ok([{"id": "r1"}, {"id": "r2"}]),
            ("DELETE", "/client/v4/zones/z/dns_records/r1"): ok({"id": "r1"}),
        }
    )
    out = make_client(rec).delete_record_by_name("a.com", "A", "app")
    assert out == {"action": "deleted", "record_id": "r1", "name": "app.a.com"}
    assert rec.calls[-1][1].endswith("/r1")


def test_add_subdomain_delegates_to_ensure_record(monkeypatch):
    cf = make_client(Recorder({}))
    seen = {}

    def fake(**kw):
        seen.update(kw)
        return {"action": "created"}

    monkeypatch.setattr(cf, "ensure_record", fake)
    assert cf.add_subdomain("a.com", "app.vps1", "1.2.3.4", proxied=True) == {"action": "created"}
    assert seen == {
        "domain": "a.com",
        "record_type": "A",
        "name": "app.vps1",
        "content": "1.2.3.4",
        "proxied": True,
        "comment": "Created by Fabrik",
    }
