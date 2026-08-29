"""Behavior contract for ZitadelGrantSource — the coarse, security-critical access source.

The product-entitlements gate calls ``GrantSource.product_access`` on a cache miss and treats ANY
error as fail-CLOSED (deny). So the two load-bearing behaviors are: (1) it maps a user's Zitadel
authorizations (role_keys on the RP's project) to the product ids the RP recognises, and (2) on a
Zitadel/transport error it RAISES — never returns an empty set that the gate would read as
"no access" (which would silently downgrade a source outage into a deny-that-looks-like-a-verdict,
the exact distinction product_entitlements/protocols.py:25 requires).

No pytest-asyncio / respx in the interpreter → async is driven via stdlib ``asyncio.run`` and the
Zitadel client is faked at its own seam (the ZitadelClient HTTP layer is tested separately in
test_bridge_zitadel_client via httpx.MockTransport).
"""

import asyncio

import pytest
from libs.product_entitlements_bridge.grant_source import ZitadelGrantSource


class _FakeClient:
    """Stands in for ZitadelClient at the list_authorizations seam."""

    def __init__(self, *, authorizations=None, raises=None):
        self._authorizations = authorizations or []
        self._raises = raises
        self.calls = []

    async def list_authorizations(self, user_id):
        self.calls.append(user_id)
        if self._raises is not None:
            raise self._raises
        return self._authorizations


# role_key → product id (the inverse of the reconciler's role_map; per-RP config)
ROLE_PRODUCTS = {"pro_user": "pro", "vault_user": "vault", "studio_user": "studio"}


def test_product_access_maps_role_keys_to_products():
    client = _FakeClient(
        authorizations=[
            {"id": "a1", "roleKeys": ["pro_user"]},
            {"id": "a2", "roleKeys": ["vault_user", "studio_user"]},
        ]
    )
    gs = ZitadelGrantSource(client, ROLE_PRODUCTS)
    got = asyncio.run(gs.product_access("u1"))
    assert got == frozenset({"pro", "vault", "studio"})
    assert client.calls == ["u1"]


def test_unmapped_role_keys_are_ignored_not_errored():
    # a role with no product mapping is simply not a product — never a crash.
    client = _FakeClient(authorizations=[{"id": "a1", "roleKeys": ["pro_user", "some_internal_role"]}])
    gs = ZitadelGrantSource(client, ROLE_PRODUCTS)
    assert asyncio.run(gs.product_access("u1")) == frozenset({"pro"})


def test_no_authorizations_returns_empty_frozenset():
    gs = ZitadelGrantSource(_FakeClient(authorizations=[]), ROLE_PRODUCTS)
    got = asyncio.run(gs.product_access("u1"))
    assert got == frozenset()
    assert isinstance(got, frozenset)


def test_source_error_raises_never_returns_empty():
    # THE fail-closed contract: a transport/Zitadel error must propagate so the gate denies on
    # "source unavailable", not silently treat it as "no products".
    client = _FakeClient(raises=RuntimeError("zitadel 503"))
    gs = ZitadelGrantSource(client, ROLE_PRODUCTS)
    with pytest.raises(RuntimeError):
        asyncio.run(gs.product_access("u1"))


def test_missing_role_keys_field_is_tolerated():
    # an authorization with no roleKeys (project-level grant, no roles) contributes nothing.
    client = _FakeClient(authorizations=[{"id": "a1"}, {"id": "a2", "roleKeys": ["pro_user"]}])
    gs = ZitadelGrantSource(client, ROLE_PRODUCTS)
    assert asyncio.run(gs.product_access("u1")) == frozenset({"pro"})
