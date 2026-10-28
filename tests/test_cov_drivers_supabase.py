"""Hermetic behaviour tests for fabrik.drivers.supabase.SupabaseClient (no network)."""

from __future__ import annotations

import httpx
import pytest

from fabrik.drivers import supabase as sb
from fabrik.drivers.supabase import SupabaseClient

URL = "https://proj.supabase.test"


class FakeResp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload if payload is not None else []
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "boom", request=httpx.Request("GET", URL), response=httpx.Response(self.status_code)
            )


class FakeHttp:
    """Records calls; replies from a queue (or a default)."""

    def __init__(self, replies=None, exc=None):
        self.calls = []
        self.replies = list(replies or [])
        self.exc = exc
        self.closed = False

    def _do(self, method, url, **kw):
        self.calls.append((method, url, kw))
        if self.exc:
            raise self.exc
        return self.replies.pop(0) if self.replies else FakeResp()

    def get(self, url, **kw):
        return self._do("GET", url, **kw)

    def post(self, url, **kw):
        return self._do("POST", url, **kw)

    def patch(self, url, **kw):
        return self._do("PATCH", url, **kw)

    def delete(self, url, **kw):
        return self._do("DELETE", url, **kw)

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY"):
        monkeypatch.delenv(k, raising=False)


def make(replies=None, exc=None, service="svc-key"):
    c = SupabaseClient(url=URL, anon_key="anon-key", service_role_key=service)
    c._client.close()
    c._client = FakeHttp(replies, exc)
    return c


# --- validators ---


@pytest.mark.parametrize("name", ["users", "_t", "A1_b2"])
def test_validators_accept_identifiers(name):
    sb._validate_table_name(name)
    sb._validate_column_name(name)


@pytest.mark.parametrize("bad", ["", "1abc", "a-b", "a b", "a;drop", "a/b", "a\n", "a.b"])
def test_validators_reject_bad_names(bad):
    with pytest.raises(ValueError, match="Invalid table name"):
        sb._validate_table_name(bad)
    with pytest.raises(ValueError, match="Invalid column name"):
        sb._validate_column_name(bad)


# --- construction ---


def test_init_reads_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "a")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "s")
    with SupabaseClient() as c:
        assert (c.url, c.anon_key, c.service_role_key) == (URL, "a", "s")
        assert c.rest_url == f"{URL}/rest/v1"
        assert c.auth_url == f"{URL}/auth/v1"
        assert c.timeout == 30.0


def test_init_explicit_args_override_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://env.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "env")
    with SupabaseClient(url=URL, anon_key="x", timeout=5) as c:
        assert c.url == URL and c.anon_key == "x" and c.timeout == 5
        assert c.service_role_key == ""


def test_init_requires_url():
    with pytest.raises(ValueError, match="SUPABASE_URL"):
        SupabaseClient(anon_key="a")


def test_init_requires_anon_key():
    with pytest.raises(ValueError, match="SUPABASE_ANON_KEY"):
        SupabaseClient(url=URL)


def test_context_manager_closes_client():
    c = make()
    fake = c._client
    with c:
        pass
    assert fake.closed


# --- headers ---


def test_headers_anon_default():
    h = make()._headers()
    assert h["apikey"] == "anon-key"
    assert h["Authorization"] == "Bearer anon-key"
    assert h["Prefer"] == "return=representation"


def test_headers_service_role():
    h = make()._headers(True)
    assert h["apikey"] == "svc-key" and h["Authorization"] == "Bearer svc-key"


def test_headers_service_role_missing_raises():
    with pytest.raises(ValueError, match="SERVICE_ROLE"):
        make(service="")._headers(True)


# --- health / verify_jwt ---


def test_health_healthy_and_unhealthy():
    c = make([FakeResp(200), FakeResp(503)])
    assert c.health() == {"status": "healthy", "url": URL}
    assert c.health()["status"] == "unhealthy"
    assert c._client.calls[0][1] == f"{URL}/rest/v1/"


def test_health_swallows_exception_as_error():
    out = make(exc=RuntimeError("down")).health()
    assert out == {"status": "error", "error": "down"}


def test_verify_jwt_valid_uses_token_not_anon_bearer():
    c = make([FakeResp(200, {"id": "u1"})])
    assert c.verify_jwt("tok") == {"valid": True, "user": {"id": "u1"}}
    method, url, kw = c._client.calls[0]
    assert url == f"{URL}/auth/v1/user"
    assert kw["headers"]["Authorization"] == "Bearer tok"
    assert kw["headers"]["apikey"] == "anon-key"


def test_verify_jwt_invalid_returns_body():
    out = make([FakeResp(401, text="expired")]).verify_jwt("t")
    assert out == {"valid": False, "error": "expired"}


def test_verify_jwt_network_error():
    out = make(exc=RuntimeError("net")).verify_jwt("t")
    assert out == {"valid": False, "error": "net"}


# --- query ---


def test_query_default_url_and_result():
    c = make([FakeResp(200, [{"a": 1}])])
    assert c.query("users") == [{"a": 1}]
    method, url, kw = c._client.calls[0]
    assert (method, url) == ("GET", f"{URL}/rest/v1/users?select=*")
    assert kw["headers"]["apikey"] == "anon-key"


def test_query_filters_order_limit_encoded():
    c = make()
    c.query(
        "t",
        select="id,name",
        filters={"email": "a&b=c d"},
        order="priority.desc,created_at.asc",
        limit=5,
    )
    url = c._client.calls[0][1]
    assert url == (
        f"{URL}/rest/v1/t?select=id,name&email=eq.a%26b%3Dc%20d"
        "&order=priority.desc,created_at.asc&limit=5"
    )


def test_query_limit_zero_is_applied():
    c = make()
    c.query("t", limit=0)
    assert c._client.calls[0][1].endswith("&limit=0")


def test_query_negative_limit_rejected_before_request():
    c = make()
    with pytest.raises(ValueError, match="non-negative"):
        c.query("t", limit=-1)
    assert c._client.calls == []


def test_query_rejects_bad_table_and_column_before_request():
    c = make()
    with pytest.raises(ValueError):
        c.query("t;x")
    with pytest.raises(ValueError):
        c.query("t", filters={"a&b": 1})
    assert c._client.calls == []


def test_query_service_role_header():
    c = make()
    c.query("t", use_service_role=True)
    assert c._client.calls[0][2]["headers"]["apikey"] == "svc-key"


def test_query_http_error_propagates():
    with pytest.raises(httpx.HTTPStatusError):
        make([FakeResp(500)]).query("t")


# --- insert / update / delete ---


def test_insert_wraps_dict_in_list():
    c = make([FakeResp(201, [{"id": 1}])])
    assert c.insert("t", {"a": 1}) == [{"id": 1}]
    method, url, kw = c._client.calls[0]
    assert (method, url) == ("POST", f"{URL}/rest/v1/t")
    assert kw["json"] == [{"a": 1}]


def test_insert_list_passthrough_and_error():
    c = make([FakeResp(400)])
    with pytest.raises(httpx.HTTPStatusError):
        c.insert("t", [{"a": 1}, {"a": 2}])
    assert c._client.calls[0][2]["json"] == [{"a": 1}, {"a": 2}]


def test_insert_invalid_table():
    with pytest.raises(ValueError):
        make().insert("bad-name", {})


def test_update_builds_filter_url():
    c = make([FakeResp(200, [{"id": 1}])])
    assert c.update("t", {"x": 1}, {"id": "a/b", "s": "p"}) == [{"id": 1}]
    method, url, kw = c._client.calls[0]
    assert method == "PATCH"
    assert url == f"{URL}/rest/v1/t?id=eq.a%2Fb&s=eq.p"
    assert kw["json"] == {"x": 1}


def test_update_empty_filters_refused():
    c = make()
    with pytest.raises(ValueError, match="filters required"):
        c.update("t", {"x": 1}, {})
    assert c._client.calls == []


def test_update_bad_column_refused():
    with pytest.raises(ValueError, match="Invalid column"):
        make().update("t", {"x": 1}, {"i d": 1})


def test_delete_builds_url_and_returns_rows():
    c = make([FakeResp(200, [{"id": 9}])])
    assert c.delete("t", {"id": 9}) == [{"id": 9}]
    assert c._client.calls[0][:2] == ("DELETE", f"{URL}/rest/v1/t?id=eq.9")


def test_delete_empty_filters_refused():
    c = make()
    with pytest.raises(ValueError, match="filters required"):
        c.delete("t", {})
    assert c._client.calls == []


def test_delete_http_error():
    with pytest.raises(httpx.HTTPStatusError):
        make([FakeResp(403)]).delete("t", {"id": 1})


# --- file / job helpers ---


def test_create_file_record_payload_and_service_role():
    c = make([FakeResp(201, [{"id": "f1"}])])
    out = c.create_file_record("ten", "a.txt", "text/plain", 3, "k/a.txt")
    assert out == {"id": "f1"}
    kw = c._client.calls[0][2]
    assert kw["json"] == [
        {
            "tenant_id": "ten",
            "filename": "a.txt",
            "content_type": "text/plain",
            "size_bytes": 3,
            "r2_key": "k/a.txt",
            "visibility": "private",
            "status": "pending",
        }
    ]
    assert kw["headers"]["apikey"] == "svc-key"


def test_create_file_record_uploaded_by_and_empty_result():
    c = make([FakeResp(201, [])])
    assert c.create_file_record("t", "f", "c", 1, "k", visibility="public", uploaded_by="u1") == {}
    row = c._client.calls[0][2]["json"][0]
    assert row["uploaded_by"] == "u1" and row["visibility"] == "public"


def test_create_file_record_needs_service_key():
    with pytest.raises(ValueError, match="SERVICE_ROLE"):
        make(service="").create_file_record("t", "f", "c", 1, "k")


def test_create_processing_job_payload():
    c = make([FakeResp(201, [{"id": "j"}])])
    assert c.create_processing_job("f1", "ocr", priority=3) == {"id": "j"}
    assert c._client.calls[0][1].endswith("/processing_jobs")
    assert c._client.calls[0][2]["json"] == [
        {"file_id": "f1", "job_type": "ocr", "status": "pending", "priority": 3}
    ]


def test_create_processing_job_empty_result():
    assert make([FakeResp(201, [])]).create_processing_job("f", "ocr") == {}


def test_claim_next_job_claims_first_pending():
    c = make([FakeResp(200, [{"id": "j1"}]), FakeResp(200, [{"id": "j1", "status": "processing"}])])
    job = c.claim_next_job(["ocr", "transcribe"], "w1")
    assert job == {"id": "j1", "status": "processing"}
    get, patch = c._client.calls
    assert "job_type=eq.ocr" in get[1] and "status=eq.pending" in get[1]
    assert "order=priority.desc,created_at.asc" in get[1] and get[1].endswith("&limit=1")
    assert patch[0] == "PATCH" and "id=eq.j1" in patch[1] and "status=eq.pending" in patch[1]
    assert patch[2]["json"] == {"status": "processing", "worker_id": "w1"}


def test_claim_next_job_falls_through_to_next_type_when_none_pending():
    c = make([FakeResp(200, []), FakeResp(200, [{"id": "j2"}]), FakeResp(200, [{"id": "j2"}])])
    assert c.claim_next_job(["a", "b"], "w") == {"id": "j2"}
    assert "job_type=eq.b" in c._client.calls[1][1]


def test_claim_next_job_lost_race_tries_next_type():
    c = make(
        [
            FakeResp(200, [{"id": "j1"}]),
            FakeResp(200, []),
            FakeResp(200, []),
        ]
    )
    assert c.claim_next_job(["a", "b"], "w") is None
    assert [m for m, *_ in c._client.calls] == ["GET", "PATCH", "GET"]


def test_claim_next_job_no_types():
    c = make()
    assert c.claim_next_job([], "w") is None
    assert c._client.calls == []


def test_complete_job_success():
    c = make([FakeResp(200, [{"id": "j", "status": "completed"}])])
    out = c.complete_job("j", True, result_data={"n": 1})
    assert out["status"] == "completed"
    body = c._client.calls[0][2]["json"]
    assert body["status"] == "completed" and body["result_data"] == {"n": 1}
    assert "error_message" not in body
    assert body["completed_at"].endswith("+00:00")
    assert "id=eq.j" in c._client.calls[0][1]


def test_complete_job_failure_with_error_and_empty_result():
    c = make([FakeResp(200, [])])
    assert c.complete_job("j", False, error_message="bad") == {}
    body = c._client.calls[0][2]["json"]
    assert body["status"] == "failed" and body["error_message"] == "bad"
    assert "result_data" not in body


def test_complete_job_keeps_falsy_result_data():
    c = make()
    c.complete_job("j", True, result_data={}, error_message="")
    body = c._client.calls[0][2]["json"]
    assert body["result_data"] == {} and body["error_message"] == ""
