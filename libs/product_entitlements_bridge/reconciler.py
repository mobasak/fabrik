"""reconcile_user_grants — idempotent billing→grant reconciler for the umbrella entitlements bridge.

Converges the user's Zitadel authorization (one user-grant on the RP's project, carrying role_keys)
to exactly the role_keys the entitled products imply. Re-runnable with NO double-grant: a second run
on unchanged billing makes ZERO Zitadel mutations; a grant that never landed is repaired (no
paid-but-locked-out user). Audit events are per PRODUCT (grant/revoke), best-effort.

The RP supplies both inputs (neither is derived here): ``entitled_products`` (billing resolved it)
and ``role_map`` (product → the Zitadel role_keys it grants — per-RP config). See the reference doc.

Model: at most one authorization per user per project. If Zitadel returns several (drift/legacy),
the first is converged and the extras are deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class _AuditSink(Protocol):
    async def record(self, action: str, *, user_id: str, product: str | None) -> None: ...


class _Client(Protocol):
    async def list_authorizations(self, user_id: str) -> list[dict[str, Any]]: ...
    async def create_authorization(
        self, user_id: str, role_keys: list[str] | None = None
    ) -> str: ...
    async def update_authorization(self, auth_id: str, role_keys: list[str]) -> None: ...
    async def delete_authorization(self, auth_id: str) -> None: ...


@dataclass
class ReconcileResult:
    created: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0


async def reconcile_user_grants(
    client: _Client,
    user_id: str,
    entitled_products: set[str] | frozenset[str],
    role_map: dict[str, list[str]],
    audit: _AuditSink | None = None,
) -> ReconcileResult:
    entitled = set(entitled_products)
    # Desired role_keys = the union of every entitled product's roles (deterministic order).
    desired_roles = sorted({r for p in entitled for r in role_map.get(p, [])})

    authorizations = await client.list_authorizations(user_id)
    result = ReconcileResult()

    # Audit on the SATISFIED TRANSITION, not on entitled-vs-inferred-products. A product is
    # "satisfied" iff its role_keys are all present in a given role set; we compare satisfaction
    # against the CURRENT roles vs the DESIRED roles. This is what correctly handles SHARED roles:
    # if `pro=[base]` and `plus=[base,extra]` and only plus is entitled, `pro` is satisfied both
    # before AND after (base stays present for plus) → no phantom revoke, and an unchanged run
    # audits nothing. (Inferring "current products" from subset membership is ambiguous when role
    # sets overlap — the classic reconciler audit bug.)
    current_roles: set[str] = set()
    for a in authorizations:
        current_roles.update(a.get("roleKeys") or [])
    desired_set = set(desired_roles)

    def _satisfied(roles_present: set[str]) -> set[str]:
        return {p for p, roles in role_map.items() if set(roles).issubset(roles_present)}

    # Audit reflects ACCESS transitions, symmetrically: the gate grants access to any product whose
    # roles are satisfied, so a product becoming satisfied = access gained (grant), becoming
    # unsatisfied = access lost (revoke) — regardless of whether it was the *entitled* product or
    # incidentally satisfied via a shared role. Anchoring only one side (e.g. grant to `entitled`)
    # produces a revoke with no matching prior grant — the same phantom class, asymmetric. Both
    # sides are the pure satisfied-transition, so an unchanged run (before == after) audits nothing.
    before = _satisfied(current_roles)
    after = _satisfied(desired_set)
    granted = sorted(after - before)
    revoked = sorted(before - after)

    # Emit audit BEFORE mutating so a mutation failure can't leave an un-audited grant/revoke — but
    # the sink is BEST-EFFORT (protocols.py:54 "MUST NOT raise"): guard it so a contract-violating
    # sink that DOES raise can never abort the reconcile and leave a paid user locked out.
    if audit is not None:
        for product in granted:
            try:
                await audit.record("entitlement.grant", user_id=user_id, product=product)
            except Exception:  # noqa: BLE001 - audit is best-effort, never fails entitlement
                pass
        for product in revoked:
            try:
                await audit.record("entitlement.revoke", user_id=user_id, product=product)
            except Exception:  # noqa: BLE001 - audit is best-effort, never fails entitlement
                pass

    if not desired_roles:
        # No entitled products → remove the grant entirely (never leave an empty authorization).
        for a in authorizations:
            await client.delete_authorization(a["id"])
            result.deleted += 1
        return result

    if not authorizations:
        await client.create_authorization(user_id, desired_roles)
        result.created += 1
        return result

    # Converge the FIRST authorization; delete any extras (there should be at most one).
    primary, *extras = authorizations
    if sorted(primary.get("roleKeys") or []) != desired_roles:
        await client.update_authorization(primary["id"], desired_roles)
        result.updated += 1
    else:
        result.unchanged += 1
    for extra in extras:
        await client.delete_authorization(extra["id"])
        result.deleted += 1
    return result
