"""Behavior contract for ZitadelClient — the Connect/Session HTTP layer, mocked via MockTransport.

Covers the request-building + response-parsing + fail-closed behaviors the GrantSource/reconciler/
teardown all rest on: token mint (Private-Key JWT → access token, cached), ListAuthorizations parse,
a >=400 RAISES (never a silent empty), DeleteAuthorization idempotency (404 = success), and the
Session-v2 search→delete teardown loop returning a count. No respx/pytest-asyncio — stdlib
``asyncio.run`` + a generated RSA key so the real jwt.encode path runs.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from libs.product_entitlements_bridge import zitadel_client as zc
from libs.product_entitlements_bridge.zitadel_client import ZitadelClient, ZitadelError

_ISSUER = "https://auth.ocoron.com"


def _sa_key() -> dict:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return {"type": "application", "keyId": "k1", "key": pem, "userId": "sa-user-1"}


def _client(handler) -> ZitadelClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(base_url=_ISSUER, transport=transport)
    return ZitadelClient(_ISSUER, _sa_key(), project_id="proj-1", org_id="org-1", http_client=http)


def _token_response(request: httpx.Request) -> httpx.Response | None:
    if request.url.path == "/oauth/v2/token":
        return httpx.Response(200, json={"access_token": "tok-abc", "expires_in": 3600})
    return None


def test_list_authorizations_mints_token_then_parses():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        tok = _token_response(request)
        if tok is not None:
            return tok
        if request.url.path.endswith("/ListAuthorizations"):
            seen["auth_header"] = request.headers.get("authorization")
            seen["body"] = json.loads(request.content)
            # THE REAL WIRE SHAPE (live Zitadel Authorization-v2 ListAuthorizations, fetched
            # 2026-08-29 by fabrik-lib, mail 01M16TVAD1): the response carries
            # `roles: [{key, displayName, group}]` — `roleKeys` exists ONLY on the
            # Create/Update REQUEST. The original mock returned `roleKeys`, matching the
            # buggy pass-through instead of the API: against real Zitadel every consumer
            # read None -> the fail-closed gate denied EVERYONE, silently.
            return httpx.Response(200, json={"authorizations": [
                {"id": "a1", "roles": [{"key": "pro_user", "displayName": "Pro"}]}
            ]})
        return httpx.Response(404)

    c = _client(handler)
    got = asyncio.run(c.list_authorizations("u1"))
    # The client NORMALIZES wire `roles:[{key}]` -> `roleKeys:[str]` so every consumer's
    # Protocol stays valid; the raw roles list is preserved alongside.
    assert got[0]["id"] == "a1"
    assert got[0]["roleKeys"] == ["pro_user"]
    assert seen["auth_header"] == "Bearer tok-abc"  # token was minted + attached
    assert seen["body"]["filters"][0]["userIdFilter"]["id"] == "u1"


def test_error_status_raises_not_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        tok = _token_response(request)
        if tok is not None:
            return tok
        return httpx.Response(503, text="unavailable")

    c = _client(handler)
    with pytest.raises(ZitadelError):
        asyncio.run(c.list_authorizations("u1"))


def test_delete_authorization_is_idempotent_on_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        tok = _token_response(request)
        if tok is not None:
            return tok
        return httpx.Response(404, text="authorization not found")

    c = _client(handler)
    # a 404 delete must NOT raise — the grant is already gone.
    assert asyncio.run(c.delete_authorization("missing")) is None


def test_delete_authorization_raises_on_real_error():
    def handler(request: httpx.Request) -> httpx.Response:
        tok = _token_response(request)
        if tok is not None:
            return tok
        return httpx.Response(500, text="boom")

    c = _client(handler)
    with pytest.raises(ZitadelError):
        asyncio.run(c.delete_authorization("a1"))


def _stateful_session_handler(live_ids, *, delete_status=200, page_limit=None):
    """A STATEFUL Zitadel session mock: DELETE actually removes the id from the live set, so a
    re-query-from-front drain terminates on empty. This is what makes the pagination test able to
    catch under-termination (a static mock cannot — reviewer Finding 3). ``deleted`` records the
    delete order; ``searches`` counts search calls.
    """
    live = list(live_ids)
    log = {"deleted": [], "searches": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        tok = _token_response(request)
        if tok is not None:
            return tok
        if request.url.path == "/v2/sessions/search":
            log["searches"] += 1
            body = json.loads(request.content)
            query = body.get("query", {})
            limit = query.get("limit", len(live))
            if page_limit is not None:
                limit = min(limit, page_limit)
            # Honor offset too, so this mock is a REAL regression guard: the correct client sends NO
            # offset (always front), but if offset-based paging were reintroduced, slicing at a live
            # offset while deletes shrink the set would skip sessions → the drain test would fail.
            offset = query.get("offset", 0)
            page = live[offset : offset + limit]
            return httpx.Response(200, json={"sessions": [{"id": s} for s in page]})
        if request.method == "DELETE" and request.url.path.startswith("/v2/sessions/"):
            sid = request.url.path.rsplit("/", 1)[-1]
            log["deleted"].append(sid)
            if sid in live:
                live.remove(sid)  # deletion shrinks the live set
            return httpx.Response(delete_status, json={})
        return httpx.Response(404)

    return handler, log


def test_terminate_user_sessions_search_then_delete_loop():
    handler, log = _stateful_session_handler(["s1", "s2"])
    c = _client(handler)
    n = asyncio.run(c.terminate_user_sessions("u1"))
    assert n == 2
    assert log["deleted"] == ["s1", "s2"]


def test_terminate_user_sessions_tolerates_already_gone_session():
    # DELETE returns 404 (raced — already terminated); the stateful mock still removes it so the
    # re-query terminates. A 404 is not counted as a termination, not an error.
    handler, log = _stateful_session_handler(["s1"], delete_status=404)
    c = _client(handler)
    assert asyncio.run(c.terminate_user_sessions("u1")) == 0
    assert log["deleted"] == ["s1"]


# --- regression tests for the Phase-A review findings ---------------------


def test_token_is_cached_across_calls():
    # Review finding #5: the access token must be minted ONCE and reused, not re-minted per call.
    token_hits = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/v2/token":
            token_hits["n"] += 1
            return httpx.Response(200, json={"access_token": "tok-abc", "expires_in": 3600})
        return httpx.Response(200, json={"authorizations": []})

    c = _client(handler)

    async def two_calls():
        await c.list_authorizations("u1")
        await c.list_authorizations("u2")

    asyncio.run(two_calls())
    assert token_hits["n"] == 1  # cached — not re-minted on the second call


def test_breaker_trips_after_5xx_failures_then_fails_closed():
    # Review findings #2/#3: the breaker must actually record 5xx failures and OPEN. Default
    # FAIL_5XX_THRESHOLD is 3 → after 3 5xx, the 4th call short-circuits WITHOUT hitting Zitadel.
    endpoint_hits = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        tok = _token_response(request)
        if tok is not None:
            return tok
        endpoint_hits["n"] += 1
        return httpx.Response(503, text="down")

    c = _client(handler)

    async def hammer():
        for _ in range(3):
            with pytest.raises(ZitadelError):
                await c.list_authorizations("u1")
        # 4th call: circuit should be OPEN → raises before touching the endpoint
        with pytest.raises(ZitadelError) as ei:
            await c.list_authorizations("u1")
        return ei.value

    err = asyncio.run(hammer())
    assert err.phase == "breaker"  # short-circuited, not another 503
    assert endpoint_hits["n"] == 3  # the 4th never reached the endpoint


def test_delete_authorization_does_not_swallow_token_404():
    # Review finding #1: a token-endpoint 404 must RAISE from delete_authorization, never be
    # misread as "grant already gone" (which would report an auth outage as a successful delete).
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/v2/token":
            return httpx.Response(404, text="not found")  # token mint fails with a 404
        return httpx.Response(200, json={})

    c = _client(handler)
    with pytest.raises(ZitadelError) as ei:
        asyncio.run(c.delete_authorization("a1"))
    assert ei.value.phase == "token"  # correctly attributed, not swallowed as idempotent


def test_terminate_user_sessions_drains_all_pages():
    # Review finding #4 + confirming-review finding 1: with 5 live sessions and a page limit of 2,
    # a correct re-query-from-front drain removes ALL 5. The STATEFUL mock removes deleted ids, so
    # the old offset-advance bug (which skipped sessions that shifted forward) would leave live
    # sessions and return n<5 — this test would then fail. It passes ONLY if every page is drained.
    handler, log = _stateful_session_handler(["s1", "s2", "s3", "s4", "s5"], page_limit=2)
    c = _client(handler)
    with patch.object(zc, "_SESSION_PAGE_LIMIT", 2):
        n = asyncio.run(c.terminate_user_sessions("u1"))
    assert n == 5
    assert sorted(log["deleted"]) == ["s1", "s2", "s3", "s4", "s5"]  # every session drained
    assert log["searches"] >= 3  # 2+2+1 across pages, then the terminating empty query


def test_terminate_user_sessions_raises_when_undrainable():
    # Confirming-review finding 2: if the search keeps returning sessions that cannot be drained
    # (here: DELETE returns 200 but the mock's set never shrinks, so the front-query keeps seeing
    # "stuck"), the page cap must be hit and RAISE, never return a partial count as success.
    def handler(request: httpx.Request) -> httpx.Response:
        tok = _token_response(request)
        if tok is not None:
            return tok
        if request.url.path == "/v2/sessions/search":
            return httpx.Response(200, json={"sessions": [{"id": "stuck"}]})  # never shrinks
        if request.method == "DELETE":
            return httpx.Response(200, json={})  # "succeeds" but the set never changes
        return httpx.Response(404)

    c = _client(handler)
    with patch.object(zc, "_MAX_SESSION_PAGES", 5):
        with pytest.raises(ZitadelError, match="exceeded"):
            asyncio.run(c.terminate_user_sessions("u1"))
