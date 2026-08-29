"""ZitadelClient — a minimal async client for Zitadel v2, machine-authenticated by Private-Key JWT.

Talks the Connect protocol as plain JSON-over-HTTP (``Connect-Protocol-Version: 1``) to the
Authorization service, and the REST-ish Session v2 endpoints for the revocation teardown loop. No
generated gRPC/Connect stub — raw ``httpx`` POST/DELETE, so tests mock the HTTP layer via
``httpx.MockTransport`` (no respx needed).

Grounded 2026-08-29 (paths, methods, perms):
- Auth: Private-Key JWT (RS256 over the SA key) exchanged at ``/oauth/v2/token`` for an access
  token requesting the reserved scope ``urn:zitadel:iam:org:project:id:zitadel:aud``; token cached
  to expiry. SA user needs ``user.grant.write/read/delete`` + ``session.read`` + ``session.delete``.
- Authorization v2: ``POST /zitadel.authorization.v2.AuthorizationService/{Method}``.
- Session v2 teardown: ``POST /v2/sessions/search`` (list by user) → ``DELETE /v2/sessions/{id}``
  (each Delete fires the RP's back-channel logout — the criterion-#3 linchpin).

Resilience (core/58-resilience.md) comes from the vendored ``_vendor_http`` circuit breaker + the
injected/default httpx client's own timeout — never hand-rolled here.

⚠️ The Connect/Session JSON FIELD names below (``userIdFilter``/``roleKeys``/``userIdQuery``/…) are
the documented Zitadel v2 shapes; confirm them against the live API when an RP first wires this
(the tests mock the transport, so they prove this client's request-building + response-parsing
logic, not the remote wire contract). See README § Integration checks.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

try:  # jwt is required for the default (real) auth path; tests that inject a token skip it.
    import jwt
except ImportError:  # pragma: no cover - PyJWT is a declared dep; guarded so import never hard-fails
    jwt = None  # type: ignore[assignment]

from ._vendor_http.circuit_breaker import CircuitBreakerRegistry

_AUTH_SVC = "/zitadel.authorization.v2.AuthorizationService"
_TOKEN_LEEWAY_S = 30.0
_ASSERTION_TTL_S = 3600
_SESSION_PAGE_LIMIT = 100  # sessions per search page (Zitadel v2 default is smaller; be explicit)
_MAX_SESSION_PAGES = 100  # backstop against a pathological drain loop; drains-with-success up to
#                           _SESSION_PAGE_LIMIT × (_MAX_SESSION_PAGES − 1), else fails CLOSED


class ZitadelError(Exception):
    """Any non-2xx from Zitadel, or a transport failure. Propagates to the caller (fail-closed).

    ``status_code`` + ``phase`` let a caller distinguish a specific API response (``phase="request"``)
    from a token-mint failure (``phase="token"``) — so ``delete_authorization`` can treat a genuine
    DeleteAuthorization 404 as idempotent WITHOUT swallowing a token-endpoint 404 (an auth outage).
    """

    def __init__(
        self, message: str, *, status_code: int | None = None, phase: str = "request"
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.phase = phase


class ZitadelClient:
    def __init__(
        self,
        issuer: str,
        sa_key: dict[str, Any],
        project_id: str,
        org_id: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
        breaker: CircuitBreakerRegistry | None = None,
    ) -> None:
        self.issuer = issuer.rstrip("/")
        self.sa_key = sa_key
        self.project_id = project_id
        self.org_id = org_id
        self._own_client = http_client is None
        self._client = http_client or httpx.AsyncClient(base_url=self.issuer, timeout=timeout)
        self._breaker = breaker or CircuitBreakerRegistry()
        self._token: str | None = None
        self._token_exp: float = 0.0

    async def aclose(self) -> None:
        if self._own_client:
            await self._client.aclose()

    # -- auth ---------------------------------------------------------------

    def _build_assertion(self) -> str:
        if jwt is None:  # pragma: no cover
            raise ZitadelError("PyJWT not installed — cannot mint the Private-Key-JWT assertion")
        now = int(time.time())
        user_id = self.sa_key["userId"]
        payload = {
            "iss": user_id,
            "sub": user_id,
            "aud": self.issuer,
            "iat": now,
            "exp": now + _ASSERTION_TTL_S,
        }
        return jwt.encode(
            payload, self.sa_key["key"], algorithm="RS256", headers={"kid": self.sa_key["keyId"]}
        )

    async def _access_token(self) -> str:
        now = time.time()
        if self._token is not None and now < self._token_exp - _TOKEN_LEEWAY_S:
            return self._token
        assertion = self._build_assertion()
        resp = await self._client.post(
            "/oauth/v2/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
                "scope": "openid urn:zitadel:iam:org:project:id:zitadel:aud",
            },
        )
        if resp.status_code != 200:
            raise ZitadelError(
                f"token exchange failed: {resp.status_code} {resp.text}",
                status_code=resp.status_code,
                phase="token",
            )
        data = resp.json()
        self._token = data["access_token"]
        self._token_exp = now + float(data.get("expires_in", _ASSERTION_TTL_S))
        return self._token

    async def _auth_headers(self) -> dict[str, str]:
        token = await self._access_token()
        return {"Authorization": f"Bearer {token}", "Connect-Protocol-Version": "1"}

    # -- transport (breaker-wrapped) ---------------------------------------

    async def _send(self, method: str, url: str, **kw: Any) -> httpx.Response:
        if not await self._breaker.allow(self.issuer):
            raise ZitadelError(f"circuit open for {self.issuer}", phase="breaker")
        try:
            resp = await self._client.request(method, url, **kw)
        except httpx.HTTPError as e:
            # No transport bucket in the registry — a transport failure is an outage signal → "5xx".
            await self._breaker.record_failure(self.issuer, kind="5xx")
            raise ZitadelError(f"{method} {url} transport error: {e}") from e
        # The registry only recognises kind "429" and "5xx" (circuit_breaker.py record_failure); any
        # other kind is a silent no-op, so use exactly those. A 429 (rate-limit) MUST record failure
        # so the breaker backs off; a 4xx client error is not an outage → record success (neutral).
        if resp.status_code == 429:
            await self._breaker.record_failure(self.issuer, kind="429")
        elif resp.status_code >= 500:
            await self._breaker.record_failure(self.issuer, kind="5xx")
        else:
            await self._breaker.record_success(self.issuer)
        return resp

    async def _post_connect(self, method: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = await self._auth_headers()
        resp = await self._send("POST", f"{_AUTH_SVC}/{method}", json=body, headers=headers)
        if resp.status_code >= 400:
            raise ZitadelError(
                f"{method} -> {resp.status_code} {resp.text}",
                status_code=resp.status_code,
                phase="request",
            )
        return resp.json() if resp.content else {}

    # -- Authorization v2 --------------------------------------------------

    async def list_authorizations(self, user_id: str) -> list[dict[str, Any]]:
        body = {"filters": [{"userIdFilter": {"id": user_id}}], "projectId": self.project_id}
        data = await self._post_connect("ListAuthorizations", body)
        auths = data.get("authorizations", [])
        # NORMALIZE HERE, once: the live v2 RESPONSE carries `roles: [{key, displayName, group}]`
        # — `roleKeys` exists only on the Create/Update REQUEST. Every consumer
        # (grant_source, reconciler) reads `roleKeys`, and before this normalization that read
        # was ALWAYS None against real Zitadel: the fail-closed entitlements gate denied
        # everyone, silently, and the reconciler mutated + emitted phantom grant events on every
        # run. The 35 mocked tests matched the bug, not the wire (fabrik-lib 01M16TVAD1, caught
        # promoting this module — their live re-fetch of the API doc found it; the hub's own
        # README had predicted exactly this mock-not-wire trap).
        for auth in auths:
            if "roleKeys" not in auth:
                auth["roleKeys"] = [
                    r.get("key") for r in (auth.get("roles") or []) if r.get("key")
                ]
        return auths

    async def create_authorization(
        self, user_id: str, role_keys: list[str] | None = None
    ) -> str:
        body: dict[str, Any] = {
            "userId": user_id,
            "projectId": self.project_id,
            "organizationId": self.org_id,
        }
        if role_keys:
            body["roleKeys"] = role_keys
        data = await self._post_connect("CreateAuthorization", body)
        return data.get("id", "")

    async def delete_authorization(self, auth_id: str) -> None:
        # Idempotent ONLY on a genuine DeleteAuthorization 404 (the grant is already gone). Keyed on
        # the API RESPONSE status + phase — never a substring of the message, which would also
        # swallow a token-mint 404 (phase="token") or a 5xx whose body contains "not found".
        try:
            await self._post_connect("DeleteAuthorization", {"id": auth_id})
        except ZitadelError as e:
            if e.phase == "request" and e.status_code == 404:
                return
            raise

    async def update_authorization(self, auth_id: str, role_keys: list[str]) -> None:
        await self._post_connect("UpdateAuthorization", {"id": auth_id, "roleKeys": role_keys})

    # -- Session v2 teardown (criterion-#3 linchpin) -----------------------

    async def terminate_user_sessions(self, user_id: str) -> int:
        """Delete EVERY live Zitadel session for ``user_id`` → each Delete fires back-channel logout.

        Drains ALL pages of the session search — a first-page-only delete would silently leave live
        sessions and still report success (the criterion-#3 fail-open). Returns the count deleted;
        RAISES on a real error so a revoke that could not tear down live sessions is never reported
        as done. Bounded by ``_MAX_SESSION_PAGES`` against a pathological cursor loop.
        """
        headers = await self._auth_headers()
        deleted = 0
        # We DELETE what we page, so the live set shrinks under us — offset-based paging would skip
        # the sessions that shift forward. Instead always re-query from the FRONT and stop when the
        # search returns EMPTY (everything drained). A page that returns sessions we cannot make
        # progress on (all un-deletable) re-appears and eventually trips the page cap → we RAISE
        # rather than return a partial count as success (fail-closed teardown).
        for _ in range(_MAX_SESSION_PAGES):
            resp = await self._send(
                "POST",
                "/v2/sessions/search",
                json={
                    "query": {"limit": _SESSION_PAGE_LIMIT},
                    "queries": [{"userIdQuery": {"id": user_id}}],
                },
                headers=headers,
            )
            if resp.status_code >= 400:
                raise ZitadelError(
                    f"session search -> {resp.status_code} {resp.text}",
                    status_code=resp.status_code,
                )
            sessions = resp.json().get("sessions", []) if resp.content else []
            if not sessions:
                return deleted  # fully drained — no live sessions remain
            for sess in sessions:
                sid = sess.get("id") or sess.get("sessionId")
                if not sid:
                    continue
                dresp = await self._send("DELETE", f"/v2/sessions/{sid}", headers=headers)
                if dresp.status_code == 404:
                    continue  # already gone
                if dresp.status_code >= 400:
                    raise ZitadelError(
                        f"delete session {sid} -> {dresp.status_code} {dresp.text}",
                        status_code=dresp.status_code,
                    )
                deleted += 1
        # Cap hit while the search still returns sessions → we could NOT prove the user's sessions
        # are gone. Fail closed: a revoke that cannot guarantee teardown must not report success.
        raise ZitadelError(
            f"session teardown for {user_id} exceeded {_MAX_SESSION_PAGES} pages — "
            "live sessions may remain (un-drainable set)"
        )
