"""Behavior contract for revoke_and_teardown — make a revoke kill LIVE sessions, not just the next login.

The criterion-#3 linchpin: deleting a Zitadel authorization is NOT a session-termination event, so
back-channel logout only fires when the session is actually terminated. So teardown must, IN ORDER:
(1) remove the user's Zitadel grant, (2) invalidate the short-TTL access cache (next boundary denies
within the TTL window), (3) terminate the user's live Zitadel sessions (each Delete fires back-channel
logout). This is the FULL-revoke / de-provision path; a partial single-product downgrade goes through
reconcile_user_grants (Phase B) with the reduced entitled set — see the integration reference doc.
"""

import asyncio

from libs.product_entitlements_bridge.teardown import revoke_and_teardown


class _RecordingClient:
    def __init__(self, authz=None):
        self.authz = list(authz or [])
        self.calls = []

    async def list_authorizations(self, user_id):
        self.calls.append(("list", user_id))
        return [dict(a) for a in self.authz]

    async def delete_authorization(self, auth_id):
        self.calls.append(("delete_auth", auth_id))

    async def terminate_user_sessions(self, user_id):
        self.calls.append(("terminate", user_id))
        return 2  # pretend 2 live sessions were killed


class _RecordingGate:
    def __init__(self):
        self.revokes = []

    async def revoke(self, user_id, product=None):
        self.revokes.append((user_id, product))


def test_teardown_deletes_grant_busts_cache_then_kills_sessions_in_order():
    client = _RecordingClient(authz=[{"id": "a1", "roleKeys": ["pro_user"]}])
    gate = _RecordingGate()
    n = asyncio.run(revoke_and_teardown(client, gate, "u1", "pro"))
    # ORDER matters: grant removed → cache busted → sessions terminated.
    kinds = [c[0] for c in client.calls]
    assert kinds == ["list", "delete_auth", "terminate"]
    # Full grant removal → the WHOLE-USER cache prefix is busted (product=None), never a single
    # product — else the user's OTHER products stay allowed until TTL (fail-open).
    assert gate.revokes == [("u1", None)]
    # cache-bust happens BEFORE the session kill (so a session that re-checks mid-teardown denies)
    assert client.calls.index(("terminate", "u1")) == len(client.calls) - 1
    assert n == 2  # returns the count of sessions torn down


def test_teardown_terminates_sessions_even_with_no_grant():
    # No authorization to delete (already gone) must NOT skip the session kill — a revoked user with
    # a lingering live session is exactly the fail-open this exists to close.
    client = _RecordingClient(authz=[])
    gate = _RecordingGate()
    asyncio.run(revoke_and_teardown(client, gate, "u1", "pro"))
    assert ("terminate", "u1") in client.calls
    assert gate.revokes == [("u1", None)]  # whole-user bust


def test_teardown_deletes_all_of_the_users_authorizations():
    client = _RecordingClient(authz=[{"id": "a1", "roleKeys": ["pro_user"]}, {"id": "a2", "roleKeys": ["x"]}])
    gate = _RecordingGate()
    asyncio.run(revoke_and_teardown(client, gate, "u1", "pro"))
    deleted = [c[1] for c in client.calls if c[0] == "delete_auth"]
    assert deleted == ["a1", "a2"]


def test_cache_bust_precedes_session_kill():
    # The cache-bust must land before the session termination: order proven via a shared log.
    order = []

    class _Client(_RecordingClient):
        async def terminate_user_sessions(self, user_id):
            order.append("terminate")
            return 0

    class _Gate(_RecordingGate):
        async def revoke(self, user_id, product=None):
            order.append("revoke")

    asyncio.run(revoke_and_teardown(_Client(authz=[]), _Gate(), "u1", "pro"))
    assert order == ["revoke", "terminate"]


def test_grant_delete_precedes_cache_bust():
    # Review finding #4: the grant must be deleted BEFORE the cache is busted — else a boundary check
    # racing the teardown could re-populate the cache from a still-present grant.
    order = []

    class _Client(_RecordingClient):
        async def delete_authorization(self, auth_id):
            order.append("delete")

        async def terminate_user_sessions(self, user_id):
            return 0

    class _Gate(_RecordingGate):
        async def revoke(self, user_id, product=None):
            order.append("revoke")

    asyncio.run(revoke_and_teardown(_Client(authz=[{"id": "a1", "roleKeys": []}]), _Gate(), "u1", "pro"))
    assert order == ["delete", "revoke"]


def test_teardown_raises_when_session_kill_fails():
    # The fail-closed contract: if terminating sessions raises, the teardown must NOT report success
    # (a revoke that could not kill live sessions is not done).
    class _Client(_RecordingClient):
        async def terminate_user_sessions(self, user_id):
            raise RuntimeError("zitadel session API down")

    import pytest

    with pytest.raises(RuntimeError):
        asyncio.run(revoke_and_teardown(_Client(authz=[]), _RecordingGate(), "u1", "pro"))
