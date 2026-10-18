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
import os
import re
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
        pytest.skip(
            "fabrik-lib/app-audit-log is not beside FABRIK_ROOT; the saas backend scaffold needs it"
        )
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
    yield out
    for name in [n for n in sys.modules if n.split(".")[0] in ("fua_chat", pkg_dir.name)]:
        del sys.modules[name]


@pytest.fixture(scope="module")
def redis_sock() -> str:
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip(
            "redis-server is not installed on this box; the chat route is proven only on a real server"
        )
    workdir = tempfile.mkdtemp(
        prefix="rc", dir="/tmp"
    )  # short: the socket path stays under 108 bytes
    sock = f"{workdir}/redis.sock"
    proc = subprocess.Popen(
        [
            binary,
            "--port",
            "0",
            "--unixsocket",
            sock,
            "--unixsocketperm",
            "700",
            "--save",
            "",
            "--appendonly",
            "no",
            "--dir",
            workdir,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_ready(proc, sock)
        yield sock
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        shutil.rmtree(workdir, ignore_errors=True)


def _wait_ready(proc: subprocess.Popen, sock: str) -> None:
    probe = redis.Redis(unix_socket_path=sock)
    try:
        deadline = time.monotonic() + 10
        while True:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"redis-server exited with {proc.returncode} before it was ready"
                )
            try:
                probe.ping()
                return
            except (redis.ConnectionError, FileNotFoundError):
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.05)
    finally:
        probe.close()


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
        self.calls: list[tuple[str, str | None]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        self.calls.append((str(request.url), request.headers.get("authorization")))
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


def _settings(mods: dict[str, types.ModuleType], **extra: Any) -> Any:
    return mods["settings"].Settings(
        database_url="postgresql://u:p@localhost/x",
        jwt_secret=SECRET,
        allowed_origins=ORIGIN,
        session_cookie_secure=True,
        **extra,
    )


def _app(
    mods: dict[str, types.ModuleType],
    redis_sock: str | None,
    upstream: Upstream,
    *,
    env: dict[str, str] | None = None,
    redis_override: Any = None,
    denylist_override: Any = None,
    settings_extra: dict[str, Any] | None = None,
) -> FastAPI:
    chat = mods["chat"]
    environ = {"OPENROUTER_API_KEY": "sk-test", "OPENROUTER_MODEL": MODEL}
    environ.update(env or {})
    client = None if redis_sock is None else aioredis.Redis(unix_socket_path=redis_sock)
    denylist = (
        mods["tokens"].NullDenylist() if client is None else mods["tokens"].RedisDenylist(client)
    )
    settings = _settings(mods, **(settings_extra or {}))
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


def _token(
    mods: dict[str, types.ModuleType], *, tenant: str | None = "t1", user: str | None = None
) -> str:
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
    r = _post(
        _app(mods, redis_sock, up), {"message": "hi"}, headers={"X-Forwarded-For": "203.0.113.7"}
    )
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
    headers = {
        "Cookie": f"{session}={_token(mods)}; {csrf}=tok123",
        "X-Forwarded-For": "203.0.113.8",
    }
    if csrf_header:
        headers["X-CSRF-Token"] = "tok123"
    if origin:
        headers["Origin"] = origin
    return headers


def test_a_cookie_request_with_the_token_and_an_allowed_origin_streams(
    mods, redis_sock, sync_redis
):
    r = _post(
        _app(mods, redis_sock, Upstream()),
        {"message": "hi"},
        headers=_cookie_headers(mods, csrf_header=True, origin=ORIGIN),
    )
    assert r.status_code == 200


@pytest.mark.parametrize(
    ("csrf_header", "origin"), [(False, ORIGIN), (True, "https://evil.example"), (True, None)]
)
def test_a_cookie_request_without_the_token_or_the_origin_is_403(
    mods, redis_sock, sync_redis, csrf_header, origin
):
    up = Upstream()
    r = _post(
        _app(mods, redis_sock, up),
        {"message": "hi"},
        headers=_cookie_headers(mods, csrf_header=csrf_header, origin=origin),
    )
    assert r.status_code == 403 and up.requests == []


def test_a_revoked_token_is_401(mods, redis_sock, sync_redis):
    token = _token(mods)
    jti = mods["tokens"].decode_access_token(token, secret=SECRET)["jti"]
    sync_redis.set(f"auth:denylist:{jti}", "1")
    r = _post(
        _app(mods, redis_sock, Upstream()),
        {"message": "hi"},
        headers={"Authorization": f"Bearer {token}", "X-Forwarded-For": "203.0.113.7"},
    )
    assert r.status_code == 401


def test_redis_unset_is_503_with_a_token_and_401_without(mods, sync_redis):
    app = _app(mods, None, Upstream())
    r = _post(app, {"message": "hi"}, headers=_bearer(mods))
    assert r.status_code == 503
    assert r.json()["detail"] == "Revocation check unavailable", (
        "the identity check refuses, before the limiter"
    )
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
    assert _post(app, {"message": "x" * 10}, headers=_bearer(mods)).status_code == 200


def test_a_body_exactly_at_the_byte_cap_is_accepted(mods, redis_sock, sync_redis):
    body = json.dumps({"message": "hi"}).encode()
    app = _app(mods, redis_sock, Upstream(), env={"CHAT_MAX_BODY_BYTES": str(len(body))})
    assert _post(app, raw=body, headers=_bearer(mods)).status_code == 200

    def chunks():
        yield body[:5]
        yield body[5:]

    r = _client(app).post("/api/v1/chat", content=chunks(), headers=_bearer(mods))
    assert r.status_code == 200


def test_an_invalid_content_length_is_400(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream())
    headers = {**_bearer(mods), "Content-Length": "twelve"}
    r = _post(app, raw=b'{"message": "hi"}', headers=headers)
    assert r.status_code == 400 and _keys(sync_redis) == set()


def test_a_body_over_the_byte_cap_is_413_with_or_without_content_length(
    mods, redis_sock, sync_redis
):
    app = _app(mods, redis_sock, Upstream(), env={"CHAT_MAX_BODY_BYTES": "64"})
    big = json.dumps({"message": "x" * 200}).encode()
    assert _post(app, raw=big, headers=_bearer(mods)).status_code == 413

    def chunks():
        yield big[:40]
        yield big[40:]

    r = _client(app).post(
        "/api/v1/chat", content=chunks(), headers=_bearer(mods)
    )  # chunked: no Content-Length
    assert r.status_code == 413
    assert _keys(sync_redis) == set()


def test_a_declared_content_length_over_the_cap_is_413_before_the_body_is_read(
    mods, redis_sock, sync_redis
):
    up = Upstream()
    app = _app(mods, redis_sock, up, env={"CHAT_MAX_BODY_BYTES": "64"})
    small = json.dumps({"message": "hi"}).encode()  # under the cap: only the header is over it
    r = _post(app, raw=small, headers={**_bearer(mods), "Content-Length": "1000"})
    assert r.status_code == 413 and up.requests == []


def test_hostile_fields_are_ignored_and_never_forwarded(mods, redis_sock, sync_redis):
    up = Upstream()
    body = {"message": "hi", **SLICE2_HOSTILE_FIELDS}
    r = _post(_app(mods, redis_sock, up), body, headers=_bearer(mods))
    assert r.status_code == 200
    assert set(up.requests[0]) == {"model", "messages", "stream", "max_tokens"}
    assert up.requests[0]["model"] == MODEL
    assert up.requests[0]["messages"] == [{"role": "user", "content": "hi"}]
    assert up.requests[0]["stream"] is True and up.requests[0]["max_tokens"] == 1024


@pytest.mark.parametrize(
    "raw",
    [
        b'{"message": "\\ud800"}',  # a lone surrogate: valid JSON, not encodable text
        b"[" * 30000 + b"]" * 30000,  # nested past the parser's recursion limit, under the cap
    ],
    ids=["lone-surrogate", "deep-nesting"],
)
def test_a_body_json_accepts_but_python_cannot_use_is_400(mods, redis_sock, sync_redis, raw):
    up = Upstream()
    app = _app(mods, redis_sock, up, env={"CHAT_MAX_BODY_BYTES": "65536"})
    assert _post(app, raw=raw, headers=_bearer(mods)).status_code == 400
    assert _keys(sync_redis) == set() and up.requests == []


def test_a_set_system_prompt_is_sent_first_verbatim(mods, redis_sock, sync_redis, monkeypatch):
    monkeypatch.setattr(mods["chat"], "CHAT_SYSTEM_PROMPT", "Be brief.")
    up = Upstream()
    _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert up.requests[0]["messages"] == [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": "hi"},
    ]


@pytest.mark.parametrize(
    "env",
    [
        {"OPENROUTER_API_KEY": ""},
        {"OPENROUTER_API_KEY": "  "},
        {"OPENROUTER_MODEL": ""},
        {"OPENROUTER_MODEL": "  "},
    ],
)
def test_the_key_or_model_unset_is_503_with_a_token_and_401_without(
    mods, redis_sock, sync_redis, env
):
    up = Upstream()
    app = _app(mods, redis_sock, up, env=env)
    assert _post(app, {"message": "hi"}, headers=_bearer(mods)).status_code == 503
    assert _post(app, {"message": "hi"}, headers={}).status_code == 401
    # the config check comes before the limiter: an unconfigured app spends no bucket
    assert _keys(sync_redis) == set() and up.requests == []


def test_identity_is_checked_before_the_body_and_the_body_before_the_config(
    mods, redis_sock, sync_redis
):
    app = _app(mods, redis_sock, Upstream(), env={"OPENROUTER_API_KEY": ""})
    assert _post(app, raw=b"{not json", headers={}).status_code == 401
    assert _post(app, raw=b"{not json", headers=_bearer(mods)).status_code == 400


def test_the_app_key_goes_only_to_openrouter(mods, redis_sock, sync_redis):
    up = Upstream()
    _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert up.calls == [("https://openrouter.ai/api/v1/chat/completions", "Bearer sk-test")]


def test_chat_max_tokens_reaches_the_upstream(mods, redis_sock, sync_redis):
    up = Upstream()
    _post(
        _app(mods, redis_sock, up, env={"CHAT_MAX_TOKENS": "77"}),
        {"message": "hi"},
        headers=_bearer(mods),
    )
    assert up.requests[0]["max_tokens"] == 77


def test_a_malformed_rate_fails_at_start(mods):
    with pytest.raises(ValueError, match="CHAT_RATE_USER"):
        mods["chat"].load_chat_settings({"CHAT_RATE_USER": "sixty"})


@pytest.mark.parametrize("raw", ["1/9000000000000000", "1/31622401"])
def test_a_rate_window_past_a_year_fails_at_start(mods, raw):
    # PEXPIRE takes milliseconds: an absurd window would 503 every request instead of failing here
    with pytest.raises(ValueError, match="CHAT_RATE_USER"):
        mods["chat"].load_chat_settings({"CHAT_RATE_USER": raw})
    assert mods["chat"].load_chat_settings({"CHAT_RATE_USER": "1/31622400"}).rate_user.window_s


@pytest.mark.parametrize("value", ["nan", "inf", "0", "-1"])
def test_a_read_timeout_that_is_not_a_positive_finite_number_fails_at_start(mods, value):
    with pytest.raises(ValueError, match="CHAT_UPSTREAM_READ_TIMEOUT"):
        mods["chat"].load_chat_settings({"CHAT_UPSTREAM_READ_TIMEOUT": value})


def test_a_huge_integer_cap_is_accepted_not_an_overflow(mods):
    # an int never overflows a finiteness check: only the float knob is checked for nan/inf
    huge = "9" * 400
    assert mods["chat"].load_chat_settings({"CHAT_MAX_BODY_BYTES": huge}).max_body_bytes == int(
        huge
    )


# --- limiter -------------------------------------------------------------------------------


@pytest.mark.parametrize("bucket", ["app", "tenant", "user", "ip"])
def test_each_full_bucket_is_429_with_retry_after_and_names_it(
    mods, redis_sock, sync_redis, bucket
):
    env = {f"CHAT_RATE_{bucket.upper()}": "1/3600"}
    app = _app(mods, redis_sock, Upstream(), env=env)
    user = str(uuid.uuid4())
    first = _bearer(mods, user=user)
    assert _post(app, {"message": "hi"}, headers=first).status_code == 200
    # the app bucket refuses a fresh user on a fresh IP; the others the same user, tenant or IP
    second = (
        _bearer(mods, ip="198.51.100.9")
        if bucket == "app"
        else (
            _bearer(mods, user=user, ip="198.51.100.9") if bucket in ("tenant", "user") else first
        )
    )
    if bucket == "tenant":
        second = _bearer(mods, ip="198.51.100.10")  # another user, same tenant t1
    r = _post(app, {"message": "hi"}, headers=second)
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1
    assert f"({bucket})" in r.json()["detail"]


def test_retry_after_rounds_the_ttl_up(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), env={"CHAT_RATE_USER": "1/3600"})
    user = str(uuid.uuid4())
    headers = _bearer(mods, user=user)
    assert _post(app, {"message": "hi"}, headers=headers).status_code == 200
    sync_redis.pexpire(f"global:chat:user:{user}", 1900)  # 900 ms of slack before "1"
    r = _post(app, {"message": "hi"}, headers=headers)
    assert r.status_code == 429 and r.headers["retry-after"] == "2"


def test_a_refusal_on_the_user_bucket_spends_no_bucket(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), env={"CHAT_RATE_USER": "1/3600"})
    user = str(uuid.uuid4())
    headers = _bearer(mods, user=user)
    _post(app, {"message": "hi"}, headers=headers)
    r = _post(app, {"message": "hi"}, headers=headers)
    assert r.status_code == 429 and "(user)" in r.json()["detail"]
    for key in (
        "global:chat:app",
        "t:t1:chat:rate",
        f"global:chat:user:{user}",
        "global:chat:ip:203.0.113.7",
    ):
        assert sync_redis.get(key) == b"1", key


def test_the_route_arms_each_bucket_with_its_full_window(mods, redis_sock, sync_redis):
    user = str(uuid.uuid4())
    _post(_app(mods, redis_sock, Upstream()), {"message": "hi"}, headers=_bearer(mods, user=user))
    # CHAT_RATE_USER defaults to 60/3600: an hour, in milliseconds
    assert 3_590_000 <= sync_redis.pttl(f"global:chat:user:{user}") <= 3_600_000


def test_the_ip_bucket_honours_trusted_proxy_hops(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), settings_extra={"trusted_proxy_hops": 2})
    _post(app, {"message": "hi"}, headers=_bearer(mods, ip="198.51.100.4, 203.0.113.9"))
    assert "global:chat:ip:198.51.100.4" in _keys(sync_redis)


def test_a_tenantless_user_touches_no_tenant_key(mods, redis_sock, sync_redis):
    _post(_app(mods, redis_sock, Upstream()), {"message": "hi"}, headers=_bearer(mods, tenant=None))
    assert not any(k.startswith("t:") for k in _keys(sync_redis))


@pytest.mark.parametrize("raw_ip", ["", "unknown", "1.2.3.4:5678"])
def test_an_empty_or_unparseable_client_ip_touches_no_ip_key(mods, raw_ip):
    assert mods["chat"].ip_key(raw_ip) is None


def test_a_request_with_an_unparseable_ip_spends_no_ip_bucket(mods, redis_sock, sync_redis):
    r = _post(
        _app(mods, redis_sock, Upstream()), {"message": "hi"}, headers=_bearer(mods, ip="unknown")
    )
    assert r.status_code == 200
    assert not any(k.startswith("global:chat:ip:") for k in _keys(sync_redis))


def test_ipv6_is_keyed_on_its_64_and_ipv4_mapped_on_its_ipv4(mods):
    ip_key = mods["chat"].ip_key
    assert ip_key("2001:db8:1:2::1") == ip_key("2001:db8:1:2:ffff::9") == "2001:db8:1:2::/64"
    assert ip_key("::ffff:203.0.113.7") == "203.0.113.7"
    assert ip_key("203.0.113.7") == "203.0.113.7"


def test_an_ipv6_address_carrying_an_ipv4_one_is_keyed_on_that_ipv4(mods):
    ip_key = mods["chat"].ip_key
    assert ip_key("64:ff9b::cb00:7107") == "203.0.113.7"  # NAT64
    assert ip_key("::203.0.113.7") == "203.0.113.7"  # IPv4-compatible
    assert ip_key("::1") == "::1"  # loopback is itself, never the shared ::/64


def test_two_ipv6_addresses_in_one_64_share_the_ip_bucket(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), env={"CHAT_RATE_IP": "1/3600"})
    assert (
        _post(app, {"message": "hi"}, headers=_bearer(mods, ip="2001:db8:1:2::1")).status_code
        == 200
    )
    r = _post(app, {"message": "hi"}, headers=_bearer(mods, ip="2001:db8:1:2:ffff::9"))
    assert r.status_code == 429 and "(ip)" in r.json()["detail"]


def test_a_redis_error_in_the_limiter_is_503(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), redis_override=_RaisingRedis())
    assert _post(app, {"message": "hi"}, headers=_bearer(mods)).status_code == 503


# --- upstream ------------------------------------------------------------------------------


@pytest.mark.parametrize("status", [301, 401, 429, 502])
def test_a_non_2xx_upstream_is_an_error_frame(mods, redis_sock, sync_redis, status):
    up = Upstream()
    up.status = status
    r = _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert [f["type"] for f in _frames(r.text)] == ["error"]


def test_an_error_chunk_mid_stream_ends_with_an_error_frame(mods, redis_sock, sync_redis):
    up = Upstream()
    up.lines = [
        'data: {"choices":[{"delta":{"content":"par"}}]}',
        'data: {"error":{"message":"provider overloaded"}}',
        "data: [DONE]",
    ]
    before = _count(mods, "upstream_error")
    r = _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert _frames(r.text) == [
        {"type": "text_delta", "text": "par"},
        {"type": "error", "error": "The model service reported an error"},
    ]
    assert _count(mods, "upstream_error") == before + 1


def test_an_empty_content_delta_sends_no_frame(mods, redis_sock, sync_redis):
    up = Upstream()
    up.lines = ['data: {"choices":[{"delta":{"content":""}}]}', "data: [DONE]"]
    r = _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert _frames(r.text) == [{"type": "done"}]


@pytest.mark.parametrize(
    "lines",
    [
        ['{"error": {"message": "bad key"}}'],  # a 200 JSON body, not SSE
        ['data: {"choices":[{"delta":{"content":"par"}}]}'],  # the connection closes early
    ],
    ids=["json-body", "no-done"],
)
def test_an_upstream_that_ends_without_done_is_an_error(mods, redis_sock, sync_redis, lines):
    up = Upstream()
    up.lines = lines
    before = _count(mods, "upstream_error")
    r = _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert _frames(r.text)[-1] == {
        "type": "error",
        "error": "The model service ended the reply early",
    }
    assert _count(mods, "upstream_error") == before + 1


def test_an_upstream_timeout_is_an_error_frame(mods, redis_sock, sync_redis):
    up = Upstream()
    up.raise_exc = httpx.ReadTimeout("stalled")
    r = _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert _frames(r.text) == [{"type": "error", "error": "The model took too long to respond"}]


@pytest.mark.parametrize(
    "line",
    [
        'data: {"choices":"abc"}',
        'data: {"choices":["x"]}',
        'data: {"choices":[{"delta":"x"}]}',
        'data: {"choices":[{"delta":{"content":5}}]}',
    ],
)
def test_a_malformed_upstream_chunk_is_skipped(mods, redis_sock, sync_redis, line):
    up = Upstream()
    up.lines = [line, 'data: {"choices":[{"delta":{"content":"ok"}}]}', "data: [DONE]"]
    r = _post(_app(mods, redis_sock, up), {"message": "hi"}, headers=_bearer(mods))
    assert _frames(r.text) == [{"type": "text_delta", "text": "ok"}, {"type": "done"}]


def _relay_outcome(mods, transport: httpx.MockTransport) -> tuple[list[dict[str, Any]], list[str]]:
    outcomes: list[str] = []

    async def run() -> list[dict[str, Any]]:
        gen = mods["chat"]._relay(httpx.AsyncClient(transport=transport), {}, "k", outcomes.append)
        return [json.loads(f[6:]) async for f in gen]

    return asyncio.run(run()), outcomes


def test_any_other_upstream_failure_is_an_error_frame_never_ok(mods):
    def boom(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("the client was closed")

    frames, outcomes = _relay_outcome(mods, httpx.MockTransport(boom))
    assert [f["type"] for f in frames] == ["error"] and outcomes == ["upstream_error"]


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

    outcomes: list[str] = []

    async def run_labelled() -> None:
        gen = mods["chat"]._relay(httpx.AsyncClient(transport=transport), {}, "k", outcomes.append)
        await gen.__anext__()
        await gen.aclose()

    asyncio.run(run())
    assert stream.closed
    asyncio.run(run_labelled())
    assert outcomes == ["disconnected"], "a stream closed before its done frame is never ok"


# --- observability -------------------------------------------------------------------------


def _count(mods, outcome: str) -> float:
    return (
        mods["metrics"].REGISTRY.get_sample_value("chat_requests_total", {"outcome": outcome})
        or 0.0
    )


def test_refusals_and_successes_are_counted_by_outcome(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream())
    before = {o: _count(mods, o) for o in ("unauthenticated", "bad_body", "ok")}
    _post(app, {"message": "hi"}, headers={})
    _post(app, {"message": ""}, headers=_bearer(mods))
    _post(app, {"message": "hi"}, headers=_bearer(mods))
    assert _count(mods, "unauthenticated") == before["unauthenticated"] + 1
    assert _count(mods, "bad_body") == before["bad_body"] + 1
    assert _count(mods, "ok") == before["ok"] + 1


def _limited(mods, bucket: str) -> float:
    return (
        mods["metrics"].REGISTRY.get_sample_value("chat_rate_limited_total", {"bucket": bucket})
        or 0.0
    )


def _timeout_upstream() -> Upstream:
    up = Upstream()
    up.raise_exc = httpx.ReadTimeout("stalled")
    return up


def _bad_gateway() -> Upstream:
    up = Upstream()
    up.status = 502
    return up


@pytest.mark.parametrize(
    ("outcome", "make"),
    [
        ("too_large", lambda m, s: (_app(m, s, Upstream(), env={"CHAT_MAX_BODY_BYTES": "8"}), {})),
        ("no_config", lambda m, s: (_app(m, s, Upstream(), env={"OPENROUTER_API_KEY": ""}), {})),
        ("redis_down", lambda m, s: (_app(m, s, Upstream(), redis_override=_RaisingRedis()), {})),
        ("upstream_error", lambda m, s: (_app(m, s, _bad_gateway()), {})),
        ("timeout", lambda m, s: (_app(m, s, _timeout_upstream()), {})),
    ],
)
def test_each_refusal_and_failure_is_counted_by_its_outcome(
    mods, redis_sock, sync_redis, outcome, make
):
    app, _ = make(mods, redis_sock)
    before = _count(mods, outcome)
    _post(app, {"message": "hi"}, headers=_bearer(mods))
    assert _count(mods, outcome) == before + 1


def test_a_limited_request_is_counted_with_its_bucket(mods, redis_sock, sync_redis):
    app = _app(mods, redis_sock, Upstream(), env={"CHAT_RATE_USER": "1/3600"})
    headers = _bearer(mods, user=str(uuid.uuid4()))
    before, before_bucket = _count(mods, "limited:user"), _limited(mods, "user")
    _post(app, {"message": "hi"}, headers=headers)
    _post(app, {"message": "hi"}, headers=headers)
    assert _count(mods, "limited:user") == before + 1
    assert _limited(mods, "user") == before_bucket + 1


# --- the emitted error handler keeps headers ------------------------------------------------


def _emitted_problem_handlers(project: Path) -> dict[str, Any]:
    main = next(project.glob("server/src/*/main.py"))
    tree = ast.parse(main.read_text())
    keep = [
        n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name in ("_problem", "_http_exc")
    ]
    for node in keep:
        node.decorator_list = []
    ns: dict[str, Any] = {
        "JSONResponse": JSONResponse,
        "Request": Request,
        "StarletteHTTPException": StarletteHTTPException,
        "PROBLEM_JSON": "application/problem+json",
        "Any": Any,
    }
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


def test_the_scaffold_emits_the_projects_own_chat_tests(project):
    """The project's CI runs the real stack (the hub cannot: no argon2/uuid_utils); it must be emitted."""
    emitted = project / "server" / "tests" / "test_chat.py"
    text = emitted.read_text()
    assert "TEST_REDIS_URL" in text and "_require_throwaway" in text and "/api/v1/chat" in text


def test_the_emitted_app_wires_the_read_timeout_into_its_chat_client(project):
    main = next(project.glob("server/src/*/main.py")).read_text()
    assert "httpx.Timeout(10.0, read=_chat_settings.read_timeout_s)" in main


_GUARD_FUNCTIONS = ("_db", "_server_id", "_require_throwaway", "_dotenv_redis_urls")


def _emitted_guard_ns(project: Path, app_redis_urls: tuple[str, ...]) -> dict[str, Any]:
    """The emitted test's guard functions, run here against redis-py."""
    emitted = project / "server" / "tests" / "test_chat.py"
    tree = ast.parse(emitted.read_text())
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in _GUARD_FUNCTIONS]
    assert len(keep) == len(_GUARD_FUNCTIONS), [n.name for n in keep]
    ns: dict[str, Any] = {"_APP_REDIS_URLS": app_redis_urls, "Path": Path, "re": re}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(emitted), "exec"), ns)  # noqa: S102
    return ns


def _emitted_redis_guard(project: Path, app_redis_url: str) -> Any:
    return _emitted_guard_ns(project, (app_redis_url,) if app_redis_url else ())[
        "_require_throwaway"
    ]


def test_the_emitted_guard_reads_the_apps_redis_url_from_its_env_files(project, tmp_path):
    """Compose delivers the root .env and WSL dev keeps .env.local; neither is exported into the
    test process, so the guard reads them itself."""
    files = {
        "plain": "# app\nREDIS_URL=redis://h:6379/5\nOTHER=1\n",
        "export": 'export REDIS_URL="redis://h:6379/6"\n',
        "bom": "\ufeffREDIS_URL=redis://h:6379/7\n",
        "tab": "export\tREDIS_URL=redis://h:6379/8\n",
        "comment": 'REDIS_URL = "rediss://h:6380/9" # the app\n',
        "crlf": "REDIS_URL=unix:///run/r.sock?db=10\r\n",
        "ignored": "# REDIS_URL=redis://h:6379/1\nTEST_REDIS_URL=redis://h:6379/2\nREDIS_URL=\n",
        "interpolated": "REDIS_URL=${REDIS_BASE}/5\n",
    }
    paths = []
    for name, text in files.items():
        (tmp_path / name).write_bytes(text.encode())
        paths.append(tmp_path / name)
    # a latin-1 file (not valid UTF-8) is still read, never skipped
    (tmp_path / "latin1").write_bytes("# caf\xe9\nREDIS_URL=redis://h:6379/11\n".encode("latin-1"))
    paths.append(tmp_path / "latin1")
    read = _emitted_guard_ns(project, ())["_dotenv_redis_urls"]
    assert read([*paths, tmp_path / "absent"]) == [
        "redis://h:6379/5",
        "redis://h:6379/6",
        "redis://h:6379/7",
        "redis://h:6379/8",
        "rediss://h:6380/9",
        "unix:///run/r.sock?db=10",
        "${REDIS_BASE}/5",
        "redis://h:6379/11",
    ]


@pytest.mark.parametrize("app_url", ["${REDIS_BASE}/5", "redis://:pa"])
def test_the_emitted_guard_refuses_an_app_url_it_cannot_read(project, redis_sock, app_url):
    # an interpolation, or a URL cut at a `#` in its password: unprovable, so refused
    guard = _emitted_guard_ns(project, (app_url,))["_require_throwaway"]
    with pytest.raises(RuntimeError, match="cannot read the app's REDIS_URL"):
        guard(f"unix://{redis_sock}?db=3")


def test_the_emitted_guard_checks_every_app_url_it_found(project, redis_sock):
    # the app's URL from an env file is the second candidate; it alone matches and is refused
    guard = _emitted_guard_ns(
        project, ("redis://other.invalid:6379/2", f"unix://{redis_sock}?db=3")
    )["_require_throwaway"]
    with pytest.raises(RuntimeError, match="own REDIS_URL"):
        guard(f"unix://{redis_sock}?db=3")


def test_the_emitted_guard_scans_the_projects_env_files(project):
    text = (project / "server" / "tests" / "test_chat.py").read_text()
    assert '[_SERVER.parent / ".env", _SERVER.parent / ".env.local", _SERVER / ".env"]' in text


@pytest.mark.parametrize(
    "url",
    [
        "redis://h:6379",
        "redis://h:6379/0",
        "redis://h:6379/00",
        "redis://h:6379/1?db=0",
        "unix:///tmp/r.sock",
    ],
)
def test_the_emitted_throwaway_guard_refuses_db_0(project, url):
    with pytest.raises(RuntimeError, match="not DB 0"):
        _emitted_redis_guard(project, "")(url)


def test_the_emitted_throwaway_guard_refuses_the_apps_db_under_any_name(
    project, redis_sock, tmp_path
):
    """The same server and DB, reached by another name, is refused: here a hard link to the
    socket, which no path normalisation folds. The guard asks the servers for their run_id."""
    alias = tmp_path / "alias.sock"
    os.link(redis_sock, alias)
    guard = _emitted_redis_guard(project, f"unix://{redis_sock}?db=3")
    for url in (f"unix://{redis_sock}?db=3", f"unix://{alias}?db=3"):
        with pytest.raises(RuntimeError, match="own REDIS_URL"):
            guard(url)


def test_the_emitted_throwaway_guard_refuses_the_apps_db_when_the_app_is_unreachable(
    project, redis_sock
):
    guard = _emitted_redis_guard(project, "unix:///nonexistent/app.sock?db=3")
    with pytest.raises(RuntimeError, match="own REDIS_URL"):
        guard(f"unix://{redis_sock}?db=3")


def test_the_emitted_throwaway_guard_allows_another_db_on_the_same_server(project, redis_sock):
    _emitted_redis_guard(project, f"unix://{redis_sock}?db=3")(f"unix://{redis_sock}?db=1")


def test_the_emitted_throwaway_guard_refuses_a_test_user_denied_info(project, redis_sock):
    """A Redis user without INFO hides its server's run_id; on the app's DB that is refused."""
    admin = redis.Redis(unix_socket_path=redis_sock)
    try:
        admin.acl_setuser(
            "noinfo", enabled=True, passwords=["+pw"], keys=["*"], commands=["+@all", "-info"]
        )
        guard = _emitted_redis_guard(project, f"unix://{redis_sock}?db=3")
        with pytest.raises(RuntimeError, match="own REDIS_URL"):
            guard(f"unix://noinfo:pw@{redis_sock}?db=3")
    finally:
        admin.acl_deluser("noinfo")
        admin.close()
