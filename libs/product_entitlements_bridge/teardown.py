"""revoke_and_teardown — make a revocation kill LIVE product sessions, not just the next login.

The criterion-#3 linchpin (grounded 2026-08-29): deleting a Zitadel authorization is NOT a
session-termination event — back-channel logout fires only when the session itself is terminated. So
a revoke that only removes the grant leaves the user's live RP sessions alive until natural expiry.
This hook does all three, in order:

 1. remove the user's Zitadel grant(s) — ``delete_authorization`` per authorization;
 2. invalidate the short-TTL access cache (``gate.revoke``) so the next boundary check DENIES within
    the TTL window (fail-closed);
 3. terminate the user's live Zitadel sessions — each ``DeleteSession`` fires the RP's back-channel
    logout, tearing down the live product session.

This is the FULL de-provision / hard-revoke path (it removes the user's whole authorization). A
PARTIAL single-product downgrade (the user keeps other products) goes through
``reconcile_user_grants`` (Phase B) with the reduced entitled set — see the integration reference doc.
The ``product`` argument scopes the cache-bust and identifies what triggered the teardown.
"""

from __future__ import annotations

from typing import Any, Protocol


class _Client(Protocol):
    async def list_authorizations(self, user_id: str) -> list[dict[str, Any]]: ...
    async def delete_authorization(self, auth_id: str) -> None: ...
    async def terminate_user_sessions(self, user_id: str) -> int: ...


class _Gate(Protocol):
    async def revoke(self, user_id: str, product: str | None = None) -> None: ...


async def revoke_and_teardown(
    client: _Client, gate: _Gate, user_id: str, product: str | None
) -> int:
    """Revoke the user's grant, bust the access cache, and tear down live sessions. Returns the
    count of sessions terminated. Raises if the grant delete or the session teardown fails (a revoke
    that could not tear down live sessions must not report success)."""
    # 1. Remove the Zitadel grant(s). delete_authorization is idempotent (a not-found = success).
    for authorization in await client.list_authorizations(user_id):
        await client.delete_authorization(authorization["id"])
    # 2. Invalidate the ENTIRE user's access cache BEFORE the session kill. The grant removal above
    #    is TOTAL (all authorizations deleted → the source now denies EVERY product), so busting only
    #    `product`'s cache entry would leave the user's OTHER products reading `access=true` until
    #    their TTL — a fail-open. gate.revoke(user_id, None) busts the whole-user prefix. (`product`
    #    identifies what triggered the teardown; it does not scope the bust.)
    await gate.revoke(user_id, None)
    # 3. Terminate live Zitadel sessions → each fires back-channel logout (kills the live RP session).
    return await client.terminate_user_sessions(user_id)
