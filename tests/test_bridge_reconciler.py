"""Behavior contract for reconcile_user_grants — the idempotent billing→grant reconciler.

Converges the user's ONE Zitadel authorization (a per-user-per-project grant carrying role_keys) to
exactly the role_keys that the entitled products imply (``role_map`` = product → role_keys). The
security-critical property is IDEMPOTENCY: a second run on unchanged billing makes ZERO Zitadel
mutations (no double-grant), and a create that failed is repaired on re-run (no paid-but-locked-out).
Audit events are emitted per PRODUCT (grant/revoke), not per role_key.

Faked at the ZitadelClient seam; async via stdlib asyncio.run.
"""

import asyncio

from libs.product_entitlements_bridge.reconciler import reconcile_user_grants

ROLE_MAP = {"pro": ["pro_user"], "vault": ["vault_user"], "studio": ["studio_user", "studio_admin"]}


class _FakeClient:
    """Simulates one user-grant per user on the project: create/update/delete mutate `authz`."""

    def __init__(self, authz=None):
        # authz: list of {"id":.., "roleKeys":[..]} — the user's current authorizations
        self.authz = [dict(a) for a in (authz or [])]
        self.creates = []
        self.updates = []
        self.deletes = []
        self._next = len(self.authz) + 1

    async def list_authorizations(self, user_id):
        return [dict(a) for a in self.authz]

    async def create_authorization(self, user_id, role_keys=None):
        aid = f"a{self._next}"
        self._next += 1
        self.authz.append({"id": aid, "roleKeys": list(role_keys or [])})
        self.creates.append((user_id, sorted(role_keys or [])))
        return aid

    async def update_authorization(self, auth_id, role_keys):
        for a in self.authz:
            if a["id"] == auth_id:
                a["roleKeys"] = list(role_keys)
        self.updates.append((auth_id, sorted(role_keys)))

    async def delete_authorization(self, auth_id):
        self.authz = [a for a in self.authz if a["id"] != auth_id]
        self.deletes.append(auth_id)


class _RecordingAudit:
    def __init__(self):
        self.events = []

    async def record(self, action, *, user_id, product):
        self.events.append((action, user_id, product))


def test_first_run_creates_missing_grant_and_audits():
    client = _FakeClient(authz=[])
    audit = _RecordingAudit()
    res = asyncio.run(reconcile_user_grants(client, "u1", {"pro"}, ROLE_MAP, audit=audit))
    assert client.creates == [("u1", ["pro_user"])]
    assert res.created == 1 and res.updated == 0 and res.deleted == 0
    assert ("entitlement.grant", "u1", "pro") in audit.events


def test_second_run_unchanged_makes_zero_mutations():
    # THE idempotency proof (criterion #4): converged state + same billing → no Zitadel writes.
    client = _FakeClient(authz=[{"id": "a1", "roleKeys": ["pro_user"]}])
    audit = _RecordingAudit()
    res = asyncio.run(reconcile_user_grants(client, "u1", {"pro"}, ROLE_MAP, audit=audit))
    assert client.creates == [] and client.updates == [] and client.deletes == []
    assert res.created == 0 and res.updated == 0 and res.deleted == 0 and res.unchanged == 1
    assert audit.events == []  # nothing changed → nothing audited


def test_failed_create_is_repaired_on_rerun():
    # A prior run that never landed the grant (authz empty) is repaired — no paid-but-locked-out.
    client = _FakeClient(authz=[])
    asyncio.run(reconcile_user_grants(client, "u1", {"pro"}, ROLE_MAP))
    assert [a["roleKeys"] for a in client.authz] == [["pro_user"]]


def test_role_drift_updates_not_duplicates():
    # billing now entitles studio (2 roles); the existing grant had only pro_user → UPDATE the one
    # authorization to the new role set, never create a second.
    client = _FakeClient(authz=[{"id": "a1", "roleKeys": ["pro_user"]}])
    audit = _RecordingAudit()
    res = asyncio.run(
        reconcile_user_grants(client, "u1", {"pro", "studio"}, ROLE_MAP, audit=audit)
    )
    assert client.creates == []
    assert client.updates == [("a1", ["pro_user", "studio_admin", "studio_user"])]
    assert res.updated == 1
    assert ("entitlement.grant", "u1", "studio") in audit.events  # only the NEW product audited


def test_billing_downgrade_removes_role_and_audits_revoke():
    # was entitled pro+studio; now only pro → the studio roles drop (UPDATE), revoke audited.
    client = _FakeClient(
        authz=[{"id": "a1", "roleKeys": ["pro_user", "studio_user", "studio_admin"]}]
    )
    audit = _RecordingAudit()
    res = asyncio.run(reconcile_user_grants(client, "u1", {"pro"}, ROLE_MAP, audit=audit))
    assert client.updates == [("a1", ["pro_user"])]
    assert res.updated == 1
    assert ("entitlement.revoke", "u1", "studio") in audit.events


def test_full_revocation_deletes_the_authorization():
    # no entitled products at all → the whole authorization is deleted (not left as an empty grant).
    client = _FakeClient(authz=[{"id": "a1", "roleKeys": ["pro_user"]}])
    audit = _RecordingAudit()
    res = asyncio.run(reconcile_user_grants(client, "u1", set(), ROLE_MAP, audit=audit))
    assert client.deletes == ["a1"]
    assert res.deleted == 1
    assert ("entitlement.revoke", "u1", "pro") in audit.events


def test_works_without_audit_sink():
    client = _FakeClient(authz=[])
    res = asyncio.run(reconcile_user_grants(client, "u1", {"pro"}, ROLE_MAP))  # audit=None
    assert res.created == 1


# --- regression tests for the Phase-B review findings ---------------------

SHARED_MAP = {"pro": ["base"], "plus": ["base", "extra"]}  # pro's role is a subset of plus's


def test_shared_roles_no_phantom_revoke_on_unchanged_run():
    # Review finding #1: with shared roles, only `plus` entitled, the converged grant carries
    # [base, extra]. `pro` is incidentally satisfied but was never entitled — an unchanged run must
    # make ZERO mutations AND emit ZERO audit events (no phantom "revoke pro").
    client = _FakeClient(authz=[{"id": "a1", "roleKeys": ["base", "extra"]}])
    audit = _RecordingAudit()
    res = asyncio.run(reconcile_user_grants(client, "u1", {"plus"}, SHARED_MAP, audit=audit))
    assert client.creates == [] and client.updates == [] and client.deletes == []
    assert res.unchanged == 1
    assert audit.events == []  # NO phantom revoke for the incidentally-satisfied `pro`


def test_shared_roles_downgrade_audits_only_the_dropped_product():
    # entitled plus→pro: `extra` drops, but `base` stays (pro still needs it). Only plus's loss is
    # audited (revoke plus), and pro is NOT re-granted (it was already satisfied).
    client = _FakeClient(authz=[{"id": "a1", "roleKeys": ["base", "extra"]}])
    audit = _RecordingAudit()
    res = asyncio.run(reconcile_user_grants(client, "u1", {"pro"}, SHARED_MAP, audit=audit))
    assert client.updates == [("a1", ["base"])]
    assert res.updated == 1
    assert ("entitlement.revoke", "u1", "plus") in audit.events
    assert ("entitlement.grant", "u1", "pro") not in audit.events  # pro stayed satisfied


def test_empty_role_product_never_audited_as_phantom():
    # Review finding #3: a product mapped to [] has no Zitadel representation → always "satisfied",
    # never a per-run phantom grant/revoke.
    client = _FakeClient(authz=[{"id": "a1", "roleKeys": ["pro_user"]}])
    audit = _RecordingAudit()
    role_map = {"pro": ["pro_user"], "free": []}
    res = asyncio.run(reconcile_user_grants(client, "u1", {"pro", "free"}, role_map, audit=audit))
    assert res.unchanged == 1
    assert audit.events == []  # `free` (empty roles) produces no phantom event


def test_raising_audit_sink_does_not_block_the_grant():
    # Review finding #2: a contract-violating sink that RAISES must not abort the reconcile — the
    # entitled user's grant must still land (no paid-but-locked-out).
    class _RaisingAudit:
        async def record(self, action, *, user_id, product):
            raise RuntimeError("audit transport down")

    client = _FakeClient(authz=[])
    res = asyncio.run(reconcile_user_grants(client, "u1", {"pro"}, ROLE_MAP, audit=_RaisingAudit()))
    assert res.created == 1
    assert client.creates == [("u1", ["pro_user"])]  # grant landed despite the audit raising


def test_shared_roles_audit_is_symmetric_grant_then_revoke():
    # Confirming-review Finding A: the audit must be symmetric — a product incidentally satisfied by
    # a shared role that is audited as GRANTED on create must also be REVOKED on teardown (never a
    # revoke without a matching prior grant). Grant `plus` → both pro+plus become satisfied (base
    # grants pro too); full revoke → both lose access.
    client = _FakeClient(authz=[])
    grant_audit = _RecordingAudit()
    asyncio.run(reconcile_user_grants(client, "u1", {"plus"}, SHARED_MAP, audit=grant_audit))
    granted = {p for (a, _u, p) in grant_audit.events if a == "entitlement.grant"}
    assert granted == {"pro", "plus"}  # both gained access via the shared `base` role

    revoke_audit = _RecordingAudit()
    asyncio.run(reconcile_user_grants(client, "u1", set(), SHARED_MAP, audit=revoke_audit))
    revoked = {p for (a, _u, p) in revoke_audit.events if a == "entitlement.revoke"}
    assert revoked == {"pro", "plus"}  # symmetric — every revoke matches a prior grant


def test_subset_retained_role_emits_no_revoke():
    # The SAFE missed-revoke semantics: losing `trial` while keeping `plus` removes NO role (plus
    # still needs `base`), so `trial` stays satisfied → zero revoke events, zero mutation. Nothing
    # was actually revoked in Zitadel, so nothing is audited (correct, not a missed revoke).
    client = _FakeClient(authz=[{"id": "a1", "roleKeys": ["base", "extra"]}])
    audit = _RecordingAudit()
    res = asyncio.run(
        reconcile_user_grants(client, "u1", {"plus"}, SHARED_MAP, audit=audit)
    )
    assert res.unchanged == 1
    assert audit.events == []  # base retained via plus → trial not revoked, no phantom
