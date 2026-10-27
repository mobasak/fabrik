"""Coverage for fabrik.drivers.r2 (R2Client) — hermetic, no network."""

import hashlib
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from fabrik.drivers import r2
from fabrik.drivers.r2 import R2Client

ENV = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_URL")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ENV:
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def http(monkeypatch):
    """Replace httpx.Client with a mock so no socket is ever opened."""
    mock = MagicMock()
    monkeypatch.setattr(r2.httpx, "Client", MagicMock(return_value=mock))
    return mock


@pytest.fixture
def client(http):
    return R2Client("acct", "AKID", "SECRET", bucket="bkt", public_url="https://cdn.example.com/")


def _resp(status=200, text="", content=b"", headers=None):
    m = MagicMock()
    m.status_code = status
    m.text = text
    m.content = content
    m.headers = headers or {}
    if status >= 400:
        m.raise_for_status.side_effect = httpx.HTTPStatusError(
            "boom", request=MagicMock(), response=m
        )
    return m


# --- construction -----------------------------------------------------------


def test_init_explicit_args(client, http):
    assert client.endpoint == "https://acct.r2.cloudflarestorage.com"
    assert client.region == "auto"
    assert client.bucket == "bkt"
    assert client.timeout == 30.0
    assert client._client is http


def test_init_reads_env(monkeypatch, http):
    monkeypatch.setenv("R2_ACCOUNT_ID", "envacct")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "envkey")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "envsecret")
    monkeypatch.setenv("R2_BUCKET", "envbkt")
    monkeypatch.setenv("R2_PUBLIC_URL", "https://pub")
    c = R2Client()
    assert (c.account_id, c.access_key_id, c.secret_access_key) == (
        "envacct",
        "envkey",
        "envsecret",
    )
    assert c.bucket == "envbkt"
    assert c.public_url == "https://pub"


def test_init_explicit_overrides_env(monkeypatch, http):
    monkeypatch.setenv("R2_ACCOUNT_ID", "envacct")
    c = R2Client("explicit", "k", "s")
    assert c.account_id == "explicit"


@pytest.mark.parametrize("missing", ["account_id", "access_key_id", "secret_access_key"])
def test_init_requires_credentials(http, missing):
    kwargs = {"account_id": "a", "access_key_id": "k", "secret_access_key": "s"}
    kwargs.pop(missing)
    with pytest.raises(ValueError, match="required"):
        R2Client(**kwargs)


def test_init_passes_timeout_to_httpx(monkeypatch):
    factory = MagicMock()
    monkeypatch.setattr(r2.httpx, "Client", factory)
    R2Client("a", "k", "s", timeout=5.0)
    factory.assert_called_once_with(timeout=5.0)


# --- _sign ------------------------------------------------------------------


def test_sign_adds_auth_headers(client):
    h = client._sign("GET", "/bkt/x", {"Host": "h"})
    assert h["x-amz-content-sha256"] == "UNSIGNED-PAYLOAD"
    assert len(h["x-amz-date"]) == 16 and h["x-amz-date"].endswith("Z")
    auth = h["Authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKID/")
    assert "/auto/s3/aws4_request" in auth
    assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in auth
    assert len(auth.rsplit("Signature=", 1)[1]) == 64


def test_sign_custom_payload_hash(client):
    h = client._sign("PUT", "/p", {"Host": "h"}, payload_hash="abc")
    assert h["x-amz-content-sha256"] == "abc"


def test_sign_deterministic_for_fixed_time(client, monkeypatch):
    class FixedDT:
        @staticmethod
        def now(tz=None):
            from datetime import datetime

            return datetime(2026, 1, 2, 3, 4, 5, tzinfo=tz)

    monkeypatch.setattr(r2, "datetime", FixedDT)
    a = client._sign("GET", "/p", {"Host": "h"}, query_params={"a": "1"})["Authorization"]
    b = client._sign("GET", "/p", {"Host": "h"}, query_params={"a": "1"})["Authorization"]
    c = client._sign("GET", "/p", {"Host": "h"}, query_params={"a": "2"})["Authorization"]
    assert a == b != c
    assert "Credential=AKID/20260102/auto/s3/aws4_request" in a


def test_sign_signature_depends_on_secret(http, monkeypatch):
    class FixedDT:
        @staticmethod
        def now(tz=None):
            from datetime import datetime

            return datetime(2026, 1, 2, 3, 4, 5, tzinfo=tz)

    monkeypatch.setattr(r2, "datetime", FixedDT)
    a = R2Client("a", "k", "s1")._sign("GET", "/", {"Host": "h"})["Authorization"]
    b = R2Client("a", "k", "s2")._sign("GET", "/", {"Host": "h"})["Authorization"]
    assert a != b


def test_sign_matches_the_aws_published_sigv4_example(http, monkeypatch):
    # Known answer from AWS's SigV4 documentation, "Example: GET Object" at
    # https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sig-v4-header-based-auth.html —
    # an independent value, so a wrong key derivation or canonical request turns this red where
    # the shape/determinism tests above stay green.
    class FixedDT:
        @staticmethod
        def now(tz=None):
            from datetime import datetime

            return datetime(2013, 5, 24, 0, 0, 0, tzinfo=tz)

    monkeypatch.setattr(r2, "datetime", FixedDT)
    c = R2Client("acct", "AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    c.region = "us-east-1"
    empty_sha = hashlib.sha256(b"").hexdigest()
    h = c._sign(
        "GET",
        "/test.txt",
        {"host": "examplebucket.s3.amazonaws.com", "range": "bytes=0-9"},
        payload_hash=empty_sha,
    )
    assert h["Authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request, "
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date, "
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )


# --- health -----------------------------------------------------------------


def test_health_healthy(client, http):
    http.get.return_value = _resp(200)
    out = client.health()
    assert out == {"status": "healthy", "endpoint": client.endpoint}
    url = http.get.call_args.args[0]
    assert url == client.endpoint
    assert "Authorization" in http.get.call_args.kwargs["headers"]


def test_health_unhealthy_on_non_200(client, http):
    http.get.return_value = _resp(403)
    assert client.health()["status"] == "unhealthy"


def test_health_swallows_exception_into_error(client, http):
    http.get.side_effect = httpx.ConnectError("no route")
    out = client.health()
    assert out["status"] == "error"
    assert "no route" in out["error"]


# --- presigned URLs ---------------------------------------------------------


def _q(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_presigned_get_shape(client):
    url = client.generate_presigned_url("dir/file.txt", expires_in=60)
    p = urlparse(url)
    assert f"{p.scheme}://{p.netloc}" == client.endpoint
    assert p.path == "/bkt/dir/file.txt"
    q = _q(url)
    assert q["X-Amz-Algorithm"] == "AWS4-HMAC-SHA256"
    assert q["X-Amz-Expires"] == "60"
    assert q["X-Amz-SignedHeaders"] == "host"
    assert q["X-Amz-Credential"].startswith("AKID/") and q["X-Amz-Credential"].endswith(
        "/auto/s3/aws4_request"
    )
    assert len(q["X-Amz-Signature"]) == 64


def test_presigned_put_with_content_type_signs_it(client):
    q = _q(client.generate_presigned_url("k", method="PUT", content_type="image/png"))
    assert q["X-Amz-SignedHeaders"] == "content-type;host"


def test_presigned_content_type_ignored_for_get(client):
    q = _q(client.generate_presigned_url("k", method="GET", content_type="image/png"))
    assert q["X-Amz-SignedHeaders"] == "host"


def test_presigned_put_without_content_type(client):
    q = _q(client.generate_presigned_url("k", method="PUT"))
    assert q["X-Amz-SignedHeaders"] == "host"


def test_presigned_bucket_override(client):
    assert urlparse(client.generate_presigned_url("k", bucket="other")).path == "/other/k"


def test_presigned_requires_bucket(http):
    c = R2Client("a", "k", "s")
    with pytest.raises(ValueError, match="Bucket"):
        c.generate_presigned_url("k")


def test_presigned_content_type_changes_signature(client, monkeypatch):
    class FixedDT:
        @staticmethod
        def now(tz=None):
            from datetime import datetime

            return datetime(2026, 1, 2, 3, 4, 5, tzinfo=tz)

    monkeypatch.setattr(r2, "datetime", FixedDT)
    a = _q(client.generate_presigned_url("k", "PUT", content_type="a/b"))["X-Amz-Signature"]
    b = _q(client.generate_presigned_url("k", "PUT", content_type="c/d"))["X-Amz-Signature"]
    assert a != b


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="object key is not percent-encoded in the presigned path",
)
def test_presigned_key_with_space_is_encoded(client):
    url = client.generate_presigned_url("my file.txt")
    assert " " not in url


# --- public url -------------------------------------------------------------


def test_public_url_strips_trailing_slash(client):
    assert client.get_public_url("a/b.png") == "https://cdn.example.com/a/b.png"


def test_public_url_fallback_to_endpoint(http):
    c = R2Client("acct", "k", "s", bucket="bkt")
    assert c.get_public_url("x") == "https://acct.r2.cloudflarestorage.com/bkt/x"


# --- put / get / delete -----------------------------------------------------


def test_put_object(client, http):
    http.put.return_value = _resp(200, headers={"ETag": '"abc"'})
    out = client.put_object("k.bin", b"hello", content_type="text/plain")
    assert out == {"key": "k.bin", "bucket": "bkt", "size": 5, "etag": '"abc"'}
    call = http.put.call_args
    assert call.args[0] == f"{client.endpoint}/bkt/k.bin"
    assert call.kwargs["content"] == b"hello"
    h = call.kwargs["headers"]
    assert h["x-amz-content-sha256"] == hashlib.sha256(b"hello").hexdigest()
    assert h["Content-Type"] == "text/plain"
    assert h["Content-Length"] == "5"


def test_put_object_default_content_type_and_missing_etag(client, http):
    http.put.return_value = _resp(200)
    out = client.put_object("k", b"", bucket="b2")
    assert out["etag"] == "" and out["bucket"] == "b2" and out["size"] == 0
    assert http.put.call_args.kwargs["headers"]["Content-Type"] == "application/octet-stream"


def test_put_object_http_error_propagates(client, http):
    http.put.return_value = _resp(500)
    with pytest.raises(httpx.HTTPStatusError):
        client.put_object("k", b"x")


def test_get_object(client, http):
    http.get.return_value = _resp(200, content=b"data")
    assert client.get_object("k") == b"data"
    assert http.get.call_args.args[0] == f"{client.endpoint}/bkt/k"


def test_get_object_404_raises(client, http):
    http.get.return_value = _resp(404)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_object("missing", bucket="b2")


@pytest.mark.parametrize("status,expected", [(200, True), (204, True), (404, False), (500, False)])
def test_delete_object(client, http, status, expected):
    http.delete.return_value = _resp(status)
    assert client.delete_object("k") is expected
    assert http.delete.call_args.args[0] == f"{client.endpoint}/bkt/k"


# --- list_objects -----------------------------------------------------------

XML = (
    "<ListBucketResult>"
    "<Contents><Key>a.txt</Key><LastModified>x</LastModified><Size>10</Size></Contents>"
    "<Contents><Key>dir/b.txt</Key><Size>2048</Size></Contents>"
    "</ListBucketResult>"
)


def test_list_objects_parses_xml(client, http):
    http.get.return_value = _resp(200, text=XML)
    assert client.list_objects() == [
        {"key": "a.txt", "size": 10},
        {"key": "dir/b.txt", "size": 2048},
    ]


def test_list_objects_empty(client, http):
    http.get.return_value = _resp(200, text="<ListBucketResult/>")
    assert client.list_objects() == []


def test_list_objects_query_params(client, http):
    http.get.return_value = _resp(200, text="")
    client.list_objects(prefix="logs/", max_keys=5)
    url = http.get.call_args.args[0]
    assert urlparse(url).path == "/bkt"
    assert _q(url) == {"list-type": "2", "max-keys": "5", "prefix": "logs/"}


def test_list_objects_no_prefix_omits_param(client, http):
    http.get.return_value = _resp(200, text="")
    client.list_objects()
    assert "prefix" not in _q(http.get.call_args.args[0])


def test_list_objects_http_error(client, http):
    http.get.return_value = _resp(403)
    with pytest.raises(httpx.HTTPStatusError):
        client.list_objects()


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="URL uses urlencode ('+') but signature uses quote ('%20') for spaces",
)
def test_list_objects_url_query_matches_signed_query(client, http):
    http.get.return_value = _resp(200, text="")
    client.list_objects(prefix="a b")
    assert "+" not in urlparse(http.get.call_args.args[0]).query


# --- lifecycle --------------------------------------------------------------


def test_close_closes_http_client(client, http):
    client.close()
    http.close.assert_called_once_with()


def test_context_manager_closes(http):
    with R2Client("a", "k", "s") as c:
        assert isinstance(c, R2Client)
    http.close.assert_called_once_with()
