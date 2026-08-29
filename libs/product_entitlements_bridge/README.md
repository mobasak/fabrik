# product_entitlements_bridge

The ocoron-specific Zitadel composition every relying-party (RP) SaaS vendors to enforce **cross-product
entitlements** against the umbrella IdP (`auth.ocoron.com`). It supplies the `GrantSource` the fabrik-lib
`product-entitlements` gate needs, plus the two operations that keep Zitadel and billing in sync.

## What it does

| Unit | Responsibility |
|---|---|
| `ZitadelGrantSource` | `product_access(user_id) -> frozenset[str]` — reads the user's Zitadel authorizations (role assignments on the RP's project) and maps role_keys → product ids. **Fail-CLOSED**: raises on a Zitadel/transport error, never returns an empty set. Feeds `product_entitlements`' gate. |
| `ZitadelClient` | Async Zitadel v2 client, Private-Key-JWT authed. Authorization v2 (`create`/`delete`/`list`/`update`) over Connect (JSON-over-HTTP) + the Session-v2 `ListSessions`→`DeleteSession` teardown loop. |
| `reconcile_user_grants` | Idempotent billing→grant reconciler (List→Create/Update/Delete). Re-runnable, no double-grant. Enqueue on the RP's PG job queue on billing events. |
| `revoke_and_teardown` | Delete the grant + invalidate the gate cache + terminate the user's live Zitadel sessions (→ back-channel logout). Makes a revoke kill LIVE sessions, not just the next login. |

## How an RP vendors it

The bridge currently lives in the **hub** (`/opt/fabrik/libs/product_entitlements_bridge/`). Until it is
promoted to a fabrik-lib module, vendor it cross-repo on the shared box (same pattern as the fabrik-lib
modules, different source path):

```bash
cp -r /opt/fabrik/libs/product_entitlements_bridge <rp>/vendored/product_entitlements_bridge
# alongside the fabrik-lib modules it composes with:
cp -r /opt/fabrik-lib/product-entitlements  <rp>/vendored/
cp -r /opt/fabrik-lib/oauth-login           <rp>/vendored/
cp -r /opt/fabrik-lib/app-audit-log         <rp>/vendored/
```

It bundles its HTTP resilience (`_vendor_http/`, a copy of fabrik-lib `async-http-client`) — do not
re-vendor that separately.

## Dependencies

`httpx` and `PyJWT` (RS256). Both are already present in the hub `.venv`; an RP adds them to its own
`requirements.txt` when vendoring. No DB table (grants live in Zitadel, the access cache in `redis-main`).

## Configuration (env, never in code)

`ZITADEL_ISSUER` · `ZITADEL_BRIDGE_SA_KEY` (the JWT-profile key JSON) · `ZITADEL_PROJECT_ID` ·
`ZITADEL_ORG_ID`. The SA user needs `user.grant.write`/`read`/`delete` **and** `session.read` +
`session.delete` (the latter two for the teardown loop). Two per-RP config maps: `role_products`
(role_key → product, for `ZitadelGrantSource`) and its inverse `role_map` (product → role_keys, for the
reconciler).

## Wiring

The full per-RP recipe — the `LocalAuthBridge`, `shape.needs_cache: true`, the reconciler enqueue seam,
the `AuditSink` async↔sync offload, `backchannel_logout_uri` — is in
[`docs/reference/umbrella-sso-integration.md`](../../docs/reference/umbrella-sso-integration.md).

## Integration checks

The Connect/Session JSON field names (`userIdFilter`, `roleKeys`, `userIdQuery`, …) are the documented
Zitadel v2 shapes; the test suite mocks the transport, so it proves this client's request-building +
response-parsing logic, not the remote wire contract. Confirm the field names against the live Zitadel v2
API the first time an RP wires this.

## Promotion note

This module is a fabrik-lib **promotion candidate** — it is reused by ≥3 RP types with a small clean
interface. The architecturally-correct home is a fabrik-lib module RPs vendor like the other three; that
promotion is a non-blocking follow-up (it cannot be done from the hub — cross-repo).
