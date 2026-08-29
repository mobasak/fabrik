"""product_entitlements_bridge — the ocoron Zitadel composition every relying-party SaaS vendors.

A Zitadel Authorization-v2 ``GrantSource`` adapter (feeding the fabrik-lib ``product-entitlements``
gate), an idempotent billing→grant reconciler, and a revocation→live-session teardown hook. See
README.md for the vendoring contract + per-RP wiring.
"""

from __future__ import annotations

from .grant_source import ZitadelGrantSource
from .reconciler import ReconcileResult, reconcile_user_grants
from .teardown import revoke_and_teardown
from .zitadel_client import ZitadelClient, ZitadelError

__all__ = [
    "ReconcileResult",
    "ZitadelClient",
    "ZitadelError",
    "ZitadelGrantSource",
    "reconcile_user_grants",
    "revoke_and_teardown",
]
