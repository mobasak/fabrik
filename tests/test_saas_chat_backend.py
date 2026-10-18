"""The saas chat route, driven end to end in the hub (W-ab242b11 slice 2, spec § Validation).

A fresh saas-skeleton is scaffolded into a temp dir. Its emitted ``chat.py`` (with the emitted
``logger.py`` and ``metrics.py`` it imports) and the vendored fastapi-user-auth leaf modules
(``cookies``, ``passwordless``, ``settings``, ``tokens``, ``dependencies``, ``csrf``) are loaded by
path under stub packages: the vendored package root needs argon2, which the hub venv lacks. They
are mounted on a bare FastAPI app behind the vendored ``CsrfOriginMiddleware`` and two stand-in
``BaseHTTPMiddleware`` layers (the emitted Correlation/SecurityHeaders/Tenant layers import the
emitted ``auth.py``, so the emitted ``server/tests/test_chat.py`` runs the real stack).

Redis is a real throwaway ``redis-server`` (TCP off, a unix socket, no persistence, killed in
teardown; ``45-testing-strategy.md:176-177``, D-1013). OpenRouter is an ``httpx.MockTransport``.
``client_ip`` is a verbatim copy of ``fastapi_user_auth/router.py:139-154`` (``router.py`` imports
``uuid_utils`` and argon2); the emitted test proves the real import.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
import types
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest
import redis
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

import fabrik.scaffold as scaffold
from tests.test_saas_skeleton_chat_system_prompt import SLICE2_BAD_BODIES, SLICE2_HOSTILE_FIELDS

SECRET = "s" * 40
ORIGIN = "https://app.example.com"
MODEL = "test/model"
_VENDORED = ("cookies", "passwordless", "settings", "tokens", "dependencies", "csrf")


def client_ip(request: Request, trusted_proxy_hops: int) -> str:
    """Verbatim copy of fastapi_user_auth/router.py:139-154 (body only)."""
    hops = max(1, trusted_proxy_hops)
    parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if len(parts) >= hops:
        return parts[-hops]
    return request.client.host if request.client else ""


def _load(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _stub_package(name: str, path: Path) -> None:
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = pkg


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if not (scaffold.FABRIK_LIB_DIR / "app-audit-log").is_dir():
        pytest.skip("fabrik-lib/app-audit-log is not beside FABRIK_ROOT; the saas backend scaffold needs it")
    base = tmp_path_factory.mktemp("chatbackend")
    scaffold.create_project(
        name="p-chat", description="d", base=base, project_type="saas-skeleton", generate_spec=False
    )
    return base / "p-chat"


@pytest.fixture(scope="module")
def mods(project: Path) -> dict[str, types.ModuleType]:
    """The emitted chat module and the vendored leaf modules, loaded by path."""
    fua_root = project / "server" / "src" / "fastapi_user_auth"
    _stub_package("fua_chat", fua_root)
    out = {n: _load(f"fua_chat.{n}", fua_root / f"{n}.py") for n in _VENDORED}
    pkg_dir = next(p for p in (project / "server" / "src").iterdir() if (p / "chat.py").is_file())
    _stub_package(pkg_dir.name, pkg_dir)
    _load(f"{pkg_dir.name}.logger", pkg_dir / "logger.py")
    out["metrics"] = _load(f"{pkg_dir.name}.metrics", pkg_dir / "metrics.py")
    out["chat"] = _load(f"{pkg_dir.name}.chat", pkg_dir / "chat.py")
    return out


@pytest.fixture(scope="module")
def redis_sock() -> str:
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("redis-server is not installed on this box; the chat route is proven only on a real server")
    workdir = tempfile.mkdtemp(prefix="rc", dir="/tmp")  # short: the socket path stays under 108 bytes
    sock = f"{workdir}/redis.sock"
    proc = subprocess.Popen(
        [binary, "--port", "0", "--unixsocket", sock, "--unixsocketperm", "700",
         "--save", "", "--appendonly", "no", "--dir", workdir],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        probe = redis.Redis(unix_socket_path=sock)
        deadline = time.monotonic() + 10
        while True:
            try:
                probe.ping()
                break
            except (redis.ConnectionError, FileNotFoundError):
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.05)
        probe.close()
        yield sock
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(workdir, ignore_errors=True)


@pytest.fixture
def sync_redis(redis_sock: str) -> redis.Redis:
    conn = redis.Redis(unix_socket_path=redis_sock)
    conn.flushdb()
    yield conn
    conn.close()


class Upstream:
    """An httpx.MockTransport stand-in for OpenRouter that records every request."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.status = 200
        self.lines = [
            ": OPENROUTER PROCESSING",
            ':    {"choices":[{"delta":{"content":"NOT SENT"}}]}',  # a comment whose tail is JSON
            'data: {"choices":[{"delta":{"content":"Hel"}}]}',
            'data: {"choices":[{"delta":{"content":"lo"}}]}',
            'data: {"choices":[],"usage":{"total_tokens":3}}',
            "data: [DONE]",
        ]
        self.raise_exc: Exception | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        if self.raise_exc is not None:
            raise self.raise_exc
        body = "\n".join(self.lines) + "\n"
        return httpx.Response(self.status, text=body, headers={"content-type": "text/event-stream"})


class _Passthrough(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):  # type: ignore[no-untyped-def]
        return await call_next(request)


class _RaisingRedis:
    async def eval(self, *args: Any) -> Any:
        raise redis.ConnectionError("redis is down")


def _settings(mods: dict[str, types.ModuleType]) -> Any:
    return mods["settings"].Settings(
        database_url="postgresql://u:p@localhost/x",
        jwt_secret=SECRET,
        allowed_origins=ORIGIN,
        session_cookie_secure=True,
    )


def _app(
    mods: dict[str, types.ModuleType],
    redis_sock: str | None,
    upstream: Upstream,
    *,
    env: dict[str, str] | None = None,
    redis_override: Any = None,
    denylist_override: Any = None,
) -> FastAPI:
    chat = mods["chat"]
    environ = {"OPENROUTER_API_KEY": "sk-test", "OPENROUTER_MODEL": MODEL}
    environ.update(env or {})
    client = None if redis_sock is None else aioredis.Redis(unix_socket_path=redis_sock)
    denylist = (
        mods["tokens"].NullDenylist() if client is None else mods["tokens"].RedisDenylist(client)
    )
    settings = _settings(mods)
    router = chat.build_chat_router(
        chat_settings=chat.load_chat_settings(environ),
        auth_settings=settings,
        redis=redis_override if redis_override is not None else client,
        denylist=denylist_override if denylist_override is not None else denylist,
        client_ip=client_ip,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(upstream.handler)),
        build_current_user=mods["dependencies"].build_current_user,
    )
    app = FastAPI()
    app.include_router(router)
    app.add_middleware(_Passthrough)
    app.add_middleware(_Passthrough)
    app.add_middleware(mods["csrf"].CsrfOriginMiddleware, settings=settings, auth_prefix="/auth")
    return app


def _token(mods: dict[str, types.ModuleType], *, tenant: str | None = "t1", user: str | None = None) -> str:
    return mods["tokens"].issue_access_token(
        subject=user or str(uuid.uuid4()), tenant_id=tenant, secret=SECRET, ttl_seconds=900
    )


def _bearer(mods, ip: str = "203.0.113.7", **kw: Any) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(mods, **kw)}", "X-Forwarded-For": ip}


_OPEN_CLIENTS: list[TestClient] = []


@pytest.fixture(autouse=True)
def _close_clients():
    yield
    while _OPEN_CLIENTS:
        _OPEN_CLIENTS.pop().__exit__(None, None, None)


def _client(app: FastAPI) -> TestClient:
    """One TestClient session per app: the async redis client binds to that session's loop."""
    tc = getattr(app.state, "tc", None)
    if tc is None:
        tc = TestClient(app, base_url="https://testserver")
        tc.__enter__()
        app.state.tc = tc
        _OPEN_CLIENTS.append(tc)
    return tc


def _post(app: FastAPI, body: Any = None, *, headers: dict[str, str], raw: bytes | None = None):
    tc = _client(app)
    if raw is not None:
        return tc.post("/api/v1/chat", content=raw, headers=headers)
    return tc.post("/api/v1/chat", content=json.dumps(body), headers=headers)


def _frames(text: str) -> list[dict[str, Any]]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def _keys(conn: redis.Redis) -> set[str]:
    return {k.decode() for k in conn.keys("*")}


# --- identity and CSRF ---------------------------------------------------------------------


def test_an_anonymous_request_is_401_and_spends_nothing(mods, redis_sock, sync_redis):
    up = Upstream()
    r = _post(_app(mods, redis_sock, up), {"message": "hi"}, headers={"X-Forwarded-For": "203.0.113.7"})
    assert r.status_code == 401
    assert _keys(sync_redis) == set() and up.requests == []


def test_a_bearer_request_streams_the_frames(mods, redis_sock, sync_redis):
    up = Upstream()
    r = _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert _frames(r.text) == [
        {"type": "text_delta", "text": "Hel"},
        {"type": "text_delta", "text": "lo"},
        {"type": "done"},
    ], "comment lines and the usage-only chunk are skipped, [DONE] ends the stream"


def _cookie_headers(mods, *, csrf_header: bool, origin: str | None) -> dict[str, str]:
    cookies = mods["cookies"]
    session = cookies.cookie_name(cookies.SESSION, secure=True)
    csrf = cookies.cookie_name(cookies.CSRF, secure=True)
    headers = {"Cookie": f"{session}={_token(mods)}; {csrf}=tok123", "X-Forwarded-For": "203.0.113.8"}
    if csrf_header:
        headers["X-CSRF-Token"] = "tok123"
    if origin:
        headers["Origin"] = origin
    return headers


def test_a_cookie_request_with_the_token_and_an_allowed_origin_streams(mods, redis_sock, sync_redis):
    r = _post(_app(mods, redis_sock, Upstream()), {"message": "hi"},
              headers=_cookie_headers(mods, csrf_header=True, origin=ORIGIN))
    assert r.status_code == 200


@pytest.mark.parametrize(("csrf_header", "origin"), [(False, ORIGIN), (True, "https://evil.example")])
def test_a_cookie_request_without_the_token_or_the_origin_is_403(mods, redis_sock, sync_redis, csrf_header, origin):
    up = Upstream()
    r = _post(_app(mods, redis_sock, up), {"message": "hi"},
              headers=_cookie_headers(mods, csrf_header=csrf_header, origin=origin))
    assert r.status_code == 403 and up.requests == []


def test_a_revoked_token_is_401(mods, redis_sock, sync_redis):
    token = _token(mods)
    jti = mods["tokens"].decode_access_token(token, secret=SECRET)["jti"]
    sync_redis.set(f"auth:denylist:{jti}", "1")
    r = _post(_app(mods, redis_sock, Upstream()), {"message": "hi"},
              headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": "203.0.113.7"})
    assert r.status_code == 401


def test_redis_unset_is_503_with_a_token_and_401_without(mods, sync_redis):
    app = _app(mods, None, Upstream())
    r = _post(app, {"message": "hi"}, headers=_bearer(mods))
    assert r.status_code == 503
    assert r.json()["detail"] == "Revocation check unavailable", "the identity check refuses, before the limiter"
    assert _post(app, {"message": "hi"}, headers={}).status_code == 401


class _DownDenylist:
    async def contains(self, jti: str) -> bool:
        raise redis.ConnectionError("down")


def test_a_denylist_outage_is_503_never_a_pass(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), denylist_override=_DownDenylist())
    r = _post(app, {"message": "hi"}, headers=_bearer(mods))
    assert r.status_code == 503 and r.json()["detail"] == "Revocation check unavailable"


# --- body ----------------------------------------------------------------------------------


@pytest.mark.parametrize("body", SLICE2_BAD_BODIES, ids=lambda b: repr(b)[:30])
def test_every_bad_body_is_400_and_spends_nothing(mods, redis_sock, sync_redis, body):
    up = Upstream()
    raw = b"{not json" if body == "__INVALID_JSON__" else json.dumps(body).encode()
    r = _post(_app(mods, redis_sock, up), raw=raw, headers=_bearer(mods))
    assert r.status_code == 400
    assert _keys(sync_redis) == set() and up.requests == []


def test_a_message_over_the_character_cap_is_400(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), env={"CHAT_MAX_MESSAGE_CHARS": "10"})
    assert _post(app, {"message": "x" * 11}, headers=_bearer(mods)).status_code == 400


def test_a_body_over_the_byte_cap_is_413_with_or_without_content_length(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), env={"CHAT_MAX_BODY_BYTES": "64"})
    big = json.dumps({"message": "x" * 200}).encode()
    assert _post(app, raw=big, headers=_bearer(mods)).status_code == 413

    def chunks():
        yield big[:40]
        yield big[40:]

    r = _client(app).post("/api/v1/chat", content=chunks(), headers=_bearer(mods))  # chunked: no Content-Length
    assert r.status_code == 413
    assert _keys(sync_redis) == set()


def test_hostile_fields_are_ignored_and_never_forwarded(mods, redis_sock, sync_redis):
    up = Upstream()
    body = {"message": "hi", **SLICE2_HOSTILE_FIELDS}
    r = _post(_app(mods, redis_sock, up), body, headers=_bearer(mods))
    assert r.status_code == 200
    assert set(up.requests[0]) == {"model", "messages", "stream", "max_tokens"}
    assert up.requests[0]["model"] == MODEL
    assert up.requests[0]["messages"] == [{"role": "user", "content": "hi"}]


def test_a_set_system_prompt_is_sent_first_verbatim(mods, redis_sock, sync_redis, monkeypatch):
    monkeypatch.setattr(mods["chat"], "CHAT_SYSTEM_PROMPT", "Be brief.")
    up = Upstream()
    _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert up.requests[0]["messages"] == [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "hi"},
    ]


@pytest.mark.parametrize("env", [{"OPENROUTER_API_KEY": ""}, {"OPENROUTER_MODEL": "  "}])
def test_the_key_or_model_unset_is_503_with_a_token_and_401_without(mods, redis_sock, sync_redis, env):
    app = _app(mods, redis_sock, Upstream(), env=env)
    assert _post(app, {"message": "hi"}, headers=_bearer(mods)).status_code == 503
    assert _post(app, {"message": "hi"}, headers={}).status_code == 401


def test_a_malformed_rate_fails_at_start(mods):
    with pytest.raises(ValueError, match="CHAT_RATE_USER"):
        mods["chat"].load_chat_settings({"CHAT_RATE_USER": "sixty"})


# --- limiter -------------------------------------------------------------------------------


@pytest.mark.parametrize("bucket", ["app", "tenant", "user", "ip"])
def test_each_full_bucket_is_429_with_retry_after_and_names_it(mods, redis_sock, sync_redis, bucket):
    env = {f"CHAT_RATE_{bucket.upper()}": "1/3600"}
    app = _app(mods, redis_sock, Upstream(), env=env)
    user = str(uuid.uuid4())
    first = _bearer(mods, user=user)
    assert _post(app, {"message": "hi"}, headers=first).status_code == 200
    # the app bucket refuses a fresh user on a fresh IP; the others the same user, tenant or IP
    second = _bearer(mods, ip="198.51.100.9") if bucket == "app" else (
        _bearer(mods, user=user, ip="198.51.100.9") if bucket in ("tenant", "user") else first
    )
    if bucket == "tenant":
        second = _bearer(mods, ip="198.51.100.10")  # another user, same tenant t1
    r = _post(app, {"message": "hi"}, headers=second)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1
    assert f"({bucket})" in r.json()["detail"]


def test_a_refusal_on_the_user_bucket_leaves_the_tenant_and_ip_counts(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), env={"CHAT_RATE_USER": "1/3600"})
    user = str(uuid.uuid4())
    headers = _bearer(mods, user=user)
    _post(app, {"message": "hi"}, headers=headers)
    assert _post(app, {"message": "hi"}, headers=headers).status_code == 429
    assert sync_redis.get("t:t1:chat:rate") == b"1"
    assert sync_redis.get("global:chat:ip:203.0.113.7") == b"1"


def test_a_tenantless_user_touches_no_tenant_key(mods, redis_sock, sync_redis):
    _post(_app(mods, redis_sock, Upstream()), {"message": "hi"}, headers=_bearer(mods, tenant=None))
    assert not any(k.startswith("t:") for k in _keys(sync_redis))


@pytest.mark.parametrize("raw_ip", ["", "unknown", "1.2.3.4:5678"])
def test_an_empty_or_unparseable_client_ip_touches_no_ip_key(mods, raw_ip):
    assert mods["chat"].ip_key(raw_ip) is None


def test_ipv6_is_keyed_on_its_64_and_ipv4_mapped_on_its_ipv4(mods):
    ip_key = mods["chat"].ip_key
    assert ip_key("2001:db8:1:2::1") == ip_key("2001:db8:1:2:ffff::9") == "2001:db8:1:2::/64"
    assert ip_key("::ffff:203.0.113.7") == "203.0.113.7"
    assert ip_key("203.0.113.7") == "203.0.113.7"


def test_a_redis_error_in_the_limiter_is_503(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), redis_override=_RaisingRedis())
    assert _post(app, {"message": "hi"}, headers=_bearer(mods)).status_code == 503


# --- upstream ------------------------------------------------------------------------------


def test_a_non_2xx_upstream_is_an_error_frame(mods, redis_sock, sync_redis):
    up = Upstream()
    up.status = 502
    r = _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert [f["type"] for f in _frames(r.text)] == ["error"]


def test_an_upstream_timeout_is_an_error_frame(mods, redis_sock, sync_redis):
    up = Upstream()
    up.raise_exc = httpx.ReadTimeout("stalled")
    r = _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert _frames(r.text) == [{"type": "error", "error": "The model took too long to respond"}]


class _TrackedStream(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.closed = False

    async def __aiter__(self):
        yield b'data: {"choices":[{"delta":{"content":"a"}}]}\n'
        await asyncio.sleep(3600)  # the model keeps going; only a close stops it
        yield b""

    async def aclose(self) -> None:
        self.closed = True


def test_closing_the_stream_closes_the_upstream_stream(mods):
    stream = _TrackedStream()
    transport = httpx.MockTransport(lambda req: httpx.Response(200, stream=stream))

    async def run() -> None:
        gen = mods["chat"]._relay(httpx.AsyncClient(transport=transport), {}, "k", lambda o: None)
        assert json.loads((await gen.__anext__())[6:]) == {"type": "text_delta", "text": "a"}
        await gen.aclose()  # what a client disconnect does to a StreamingResponse body

    asyncio.run(run())
    assert stream.closed


# --- observability -------------------------------------------------------------------------


def _count(mods, outcome: str) -> float:
    return mods["metrics"].REGISTRY.get_sample_value("chat_requests_total", {"outcome": outcome}) or 0.0


def test_refusals_and_successes_are_counted_by_outcome(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream())
    before = {o: _count(mods, o) for o in ("unauthenticated", "bad_body", "ok")}
    _post(app, {"message": "hi"}, headers={})
    _post(app, {"message": ""}, headers=_bearer(mods))
    _post(app, {"message": "hi"}, headers=_bearer(mods))
    assert _count(mods, "unauthenticated") == before["unauthenticated"] + 1
    assert _count(mods, "bad_body") == before["bad_body"] + 1
    assert _count(mods, "ok") == before["ok"] + 1


# --- the emitted error handler keeps headers ------------------------------------------------


def _emitted_problem_handlers(project: Path) -> dict[str, Any]:
    main = next(project.glob("server/src/*/main.py"))
    tree = ast.parse(main.read_text())
    keep = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name in ("_problem", "_http_exc")]
    for node in keep:
        node.decorator_list = []
    ns: dict[str, Any] = {"JSONResponse": JSONResponse, "Request": Request,
                          "StarletteHTTPException": StarletteHTTPException,
                          "PROBLEM_JSON": "application/problem+json", "Any": Any}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(main), "exec"), ns)  # noqa: S102
    return ns


def test_the_emitted_http_exception_handler_keeps_retry_after(project):
    ns = _emitted_problem_handlers(project)
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, ns["_http_exc"])

    @app.post("/limited")
    async def limited() -> None:
        raise HTTPException(429, "limited", headers={"Retry-After": "30"})

    r = TestClient(app).post("/limited")
    assert r.status_code == 429 and r.headers["content-type"] == "application/problem+json"
    assert r.headers["retry-after"] == "30"
