"""ZitadelGrantSource — the product-entitlements ``GrantSource`` backed by Zitadel Authorization v2.

The product-entitlements gate calls ``product_access(user_id)`` on a cache miss (coarse,
security-critical) and treats ANY raise as fail-CLOSED. This adapter reads the user's Zitadel
authorizations (role assignments on the RP's project) and maps their role_keys to the RP's product
ids via ``role_products`` (per-RP config — the inverse of the reconciler's ``role_map``).

Fail-closed by construction: it does NOT catch the client's errors — a Zitadel/transport failure
propagates so the gate can distinguish "no access" from "source unavailable" and deny on the latter
(product_entitlements/protocols.py:25). Never return an empty set on error.
"""

from __future__ import annotations

from typing import Any, Protocol


class _ListsAuthorizations(Protocol):
    async def list_authorizations(self, user_id: str) -> list[dict[str, Any]]: ...


class ZitadelGrantSource:
    """Adapts Zitadel user-grants to ``product_entitlements.protocols.GrantSource``."""

    def __init__(self, client: _ListsAuthorizations, role_products: dict[str, str]) -> None:
        """``role_products`` maps a Zitadel role_key → a product id the RP recognises."""
        self._client = client
        self._role_products = dict(role_products)

    async def product_access(self, user_id: str) -> frozenset[str]:
        # list_authorizations RAISES on a real Zitadel/transport error → propagates (fail-closed).
        authorizations = await self._client.list_authorizations(user_id)
        products: set[str] = set()
        for auth in authorizations:
            for role_key in auth.get("roleKeys") or []:
                product = self._role_products.get(role_key)
                if product is not None:
                    products.add(product)
        return frozenset(products)
