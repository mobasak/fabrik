# Umbrella SSO integration — the per-RP recipe

How a relying-party (RP) SaaS federates to the umbrella Zitadel IdP (`auth.ocoron.com`) and enforces
cross-product entitlements. This is the reference the per-RP agents follow (youtube, transdoc,
web-ecommerce-factory, + future). The shared machinery lives in `libs/product_entitlements_bridge/`
(hub) + three fabrik-lib modules; each RP vendors them and supplies its own config + wiring.

> **Status:** hub bridge module + this reference shipped (Epic-2 hub slice). The per-RP wiring below is
> **dispatched to each RP's own repo** — the hub cannot write RP files.

## 1. Vendor the modules

On the shared box, vendor by copy (fabrik-lib is vendor-by-copy, never import):

```bash
cp -r /opt/fabrik-lib/oauth-login            <rp>/vendored/oauth_login
cp -r /opt/fabrik-lib/product-entitlements   <rp>/vendored/product_entitlements
cp -r /opt/fabrik-lib/app-audit-log          <rp>/vendored/app_audit_log
# the bridge (until promoted to a fabrik-lib module — see its README):
cp -r /opt/fabrik/libs/product_entitlements_bridge  <rp>/vendored/product_entitlements_bridge
```

The bridge bundles its own HTTP resilience (`_vendor_http/`, a copy of `async-http-client`) — do not
vendor that separately. Add `httpx` + `PyJWT` to the RP's `requirements.txt`.

## 2. Set `shape.needs_cache: true`

On the RP's `specs/services/<id>.yaml`, `shape.needs_cache: true` — else `fabrik apply` skips the Redis
registrar and `REDIS_URL` is never injected, so the entitlements gate has no cache and every boundary
check hits Zitadel (or fails closed). This is a HARD per-RP acceptance constraint.

## 3. Config (env, never in code)

`ZITADEL_ISSUER=https://auth.ocoron.com` · `ZITADEL_BRIDGE_SA_KEY` (the JWT-profile SA key JSON) ·
`ZITADEL_PROJECT_ID` · `ZITADEL_ORG_ID` · `REDIS_URL` (injected by the registrar). The Zitadel service
user needs `user.grant.write`/`read`/`delete` **and** `session.read` + `session.delete` (the last two for
the revocation teardown loop). Two per-RP config maps:

- `role_products: dict[role_key, product]` — for `ZitadelGrantSource` (which products a user's roles grant).
- `role_map: dict[product, list[role_key]]` — its inverse, for `reconcile_user_grants`.

## 4. Login: the `LocalAuthBridge`

Implement `oauth_login`'s `LocalAuthBridge` (`create_or_get_user_from_verified_identity` + `mint_app_session`):
federate via auth-code + PKCE, validate the ID token against Zitadel's JWKS, key the local user on the
**provider subject** (never email — blocks nOAuth), create-or-get the RP user, mint the RP's own
`fastapi-user-auth` session, and set the tenant GUC from the `VerifiedIdentity`. One umbrella login then
lands the user in every product they're entitled to.

## 5. The entitlements gate

Wire `product_entitlements`' gate with the bridge's `ZitadelGrantSource(client, role_products)` as the
`GrantSource`, a `RedisGrantCache(REDIS_URL)`, and (optional) an `AuditSink` (§7). Access is **fail-CLOSED**:
`product_access` RAISES on a Zitadel/Redis error and the gate DENIES — access is source-checked per
boundary via the short-TTL cache, **never a long-lived JWT claim**.

```python
client = ZitadelClient(ZITADEL_ISSUER, sa_key, ZITADEL_PROJECT_ID, ZITADEL_ORG_ID)
gate = EntitlementsGate(grant_source=ZitadelGrantSource(client, role_products), cache=RedisGrantCache(REDIS_URL), audit=audit)
if not await gate.has_access(user_id, "pro"): raise HTTPException(403)
```

## 6. The reconciler — enqueue seam (billing → grant)

The reconciler is a pure async function; it runs on the RP's **PostgreSQL job queue**, never inline in a
request (>10s), idempotent so a retry is safe (12-Factor IX).

- **Trigger:** on every billing event — the `payments` / `credits` / RevenueCat webhook handler — ENQUEUE
  a job.
- **Payload:** `{user_id, entitled_products, role_map}`. The RP resolves `entitled_products` from billing;
  `role_map` is the per-RP config constant.
- **Worker:** builds a `ZitadelClient(...)` from env and `await reconcile_user_grants(client, user_id,
  entitled_products, role_map, audit=audit)`. Idempotent: a second run on unchanged billing makes zero
  Zitadel mutations; a never-landed grant is repaired (no paid-but-locked-out).

## 7. Audit — the async↔sync impedance

`product_entitlements`' `AuditSink.record(action, *, user_id, product)` is **async**, but `app-audit-log`'s
`record_event(conn, …)` is **synchronous + connection-based**. The RP's `AuditSink` impl must inject a DB
`conn` and offload the sync call so it does not block the async worker/gate event loop:

```python
# app_audit_log.record_event(conn, *, actor, action, target_type=None, target_id=None, details=None)
class AppAuditSink:
    def __init__(self, conn): self._conn = conn
    async def record(self, action, *, user_id, product):
        await asyncio.to_thread(
            record_event, self._conn,
            actor=user_id, action=action, target_type="product", target_id=product,
        )
```

Grant/revoke events are emitted best-effort — the reconciler never fails an entitlement on an audit error.
(Add the `entitlement.grant` / `entitlement.revoke` actions to the vendored `app-audit-log` vocabulary +
its schema CHECK — it is customize-on-vendor.)

## 8. Revocation → live-session teardown

Deleting a Zitadel grant does **NOT** tear down live RP sessions — back-channel logout fires only on
session termination. So:

- Register a `backchannel_logout_uri` on the RP's Zitadel OIDC app AND validate the received logout token
  (`sid` / `aud` / `events`) before killing the local session.
- On a full de-provision / hard revoke, call `revoke_and_teardown(client, gate, user_id, product)` — it
  deletes the grant, busts the cache, and runs the Session-v2 `ListSessions`→`DeleteSession` loop (each
  Delete fires back-channel logout). A **partial** single-product downgrade (the user keeps other products)
  goes through `reconcile_user_grants` with the reduced entitled set instead — then, if the product had a
  live session, call `client.terminate_user_sessions(user_id)`.

## 9. Standalone coexistence

An RP keeps working if the umbrella IdP is unreachable: the gate fails CLOSED on coarse access (deny), but
the RP's own `fastapi-user-auth` login remains its session authority. Umbrella federation is additive.
