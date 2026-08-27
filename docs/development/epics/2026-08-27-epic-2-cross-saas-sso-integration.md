---
kind: story
title: "Epic 2 — Cross-SaaS SSO Integration + Entitlements"
status: 0
epic_n: 2
slug: cross-saas-sso-integration
depends_on: [1]
parallel_with: []
owned_paths: ["libs/**/product_entitlements_bridge/**", "docs/reference/umbrella-sso-integration.md"]
scaffold: none
port: 0
target_vps: vps1
---
## Epic 2 — Cross-SaaS SSO Integration + Entitlements

### Summary
Federate every relying-party SaaS to the umbrella issuer and enforce cross-product entitlements consistently.
Each RP gains a `LocalAuthBridge` (mints its own `fastapi-user-auth` session from the umbrella
`VerifiedIdentity`), vendors the fabrik-lib `product-entitlements` module for a source-checked grant gate, and
an **idempotent billing→grant reconciler** keeps Zitadel Authorization-v2 grants in sync with `payments` /
`credits` / `revenuecat` so no paying user is ever locked out. Revoking a grant or an umbrella logout tears
down **live** product sessions (OIDC back-channel logout / short local TTL). ⚠️ **Cross-repo:** the per-RP
integrations live in each product's own repo (youtube, transdoc, web-ecommerce-factory, + future) and dispatch
to those projects' agents; this hub epic owns the shared reconciler/bridge pattern and coordinates the rollout.

### Scope
**In:**
- **#5** Per-SaaS `LocalAuthBridge` — each RP implements the `oauth-login` `LocalAuthBridge` protocol
  (create-or-get user + mint local session + set the tenant GUC) from the umbrella `VerifiedIdentity`.
- **#6** Idempotent billing→grant reconciler — `payments`/`credits`/`revenuecat` success → a Zitadel
  **Authorization v2** grant (⚠️ v1 `AddUserGrant` is deprecated); re-runnable without double-granting.
- **#7** Revocation → live-session teardown — OIDC back-channel logout (or short local-session TTL + periodic
  re-check) so a grant-revoke / umbrella logout kills live product sessions, not just the next login.
- **#8** Standalone coexistence — an RP still accepts its own `fastapi-user-auth` login (incl. passwordless);
  `product-entitlements` decides access either way.

**Out:**
- Deploying the IdP / login UI — handled by Epic 1.
- Building the `oauth-login` OIDC adapter + `product-entitlements` module — external (fabrik-lib).

### Success Criteria
1. **Deploy/gate:** for each integrated RP, `fabrik apply` succeeds with **`shape.needs_cache: true`** set (the
   Redis registrar fires and injects `REDIS_URL`) AND `python scripts/final_gate.py --json` returns
   `"status":"success"` for the modified scope.
2. **Feature (Delivers):** one umbrella login at `auth.ocoron.com` lands the user in **every entitled product**
   with a valid local session, and is **denied** in a non-entitled one.
3. **Revocation (HARD constraint):** revoking a user's Zitadel grant blocks the **next boundary check** within
   the short-TTL cache window AND tears down the user's **live** product session (back-channel logout observed
   or the local session expires within its TTL) — not merely the next login.
4. **Reconciler:** a `payments`/`credits`/`revenuecat` success whose grant-creation initially fails is
   reconciled with **no paid-but-locked-out** user, and re-running the reconciler does **not** double-grant
   (idempotent — verified by re-run).
5. **Cache correctness:** coarse product-access is source-checked via the short-TTL `redis-main` cache and is
   **never** a long-lived JWT claim (a revoked grant is not honored past the cache TTL).
6. **Standalone:** a user who never touched the umbrella still logs into an RP via its own `fastapi-user-auth`
   and is gated by that product's own plan.
7. **Federation security:** a tampered / wrong-audience ID token is rejected (auth-code + PKCE + full JWKS
   validation).
8. **Audit:** every grant mutation + revocation writes to the hash-chained audit log (`core/app-audit-log.md`).

### Out of Scope (Epic Level)
- Zitadel deployment + login UI — handled by Epic 1.
- The fabrik-lib module builds (`oauth-login` adapter, `product-entitlements`) — external, fabrik-lib-owned.
- SAML federation, the website store as an RP — vision-level Out of Scope.

### Dependencies
- **Consumes from prior epics:** Epic 1's OIDC issuer `https://auth.ocoron.com` + discovery/JWKS; per-RP
  `ZITADEL_CLIENT_ID` / `ZITADEL_CLIENT_SECRET`; the Zitadel **Authorization v2** grant API. **[External,
  fabrik-lib]** the `oauth-login` generic-OIDC adapter + the `product-entitlements` module.
- **Produces for later epics:** per-RP `LocalAuthBridge`; the idempotent billing→grant reconciler; the
  revocation teardown hook; `shape.needs_cache: true` on every consuming RP spec (the short-TTL grant cache).
- **Depends on:** Epic 1 (hard — needs a live issuer). External hard: fabrik-lib `oauth-login` adapter +
  `product-entitlements` module.
- **Parallel with:** none. (Per-RP tickets WITHIN this epic parallelize in 05 with disjoint per-repo scopes.)
- **Owned paths:** hub-owned — the shared reconciler/bridge pattern module (`libs/**/product_entitlements_bridge/**`)
  + `docs/reference/umbrella-sso-integration.md`. ⚠️ Per-RP code
  (`<rp-repo>/src/**/auth_bridge`, `<rp-repo>/specs/services/<rp>.yaml`) is owned by **each RP's own repo/agents**
  (cross-repo) — the hub cannot write those files; the per-RP tickets dispatch to those projects.

### Metadata
- Scaffold: none (code in existing RP projects + vendored fabrik-lib modules; cross-repo).
- Port: none new (modifies existing services; each RP keeps its port).
- target_vps: vps1 (the shared reconciler/bridge pattern is hub-authored; per-RP wiring inherits each RP's own target).
- Shape: modifies existing RP shapes — the load-bearing change is **`shape.needs_cache: true` on EVERY
  consuming RP**. No new deploy unit of its own.
- Concurrency: the reconciler is **idempotent** (re-runnable without double-granting); async grant
  reconciliation rides each RP's PostgreSQL job queue (never inline >10s).
- i18n: inherited per-RP (no new UI surface built here).
- Responsive: inherited per-RP.
- Dark+Light: inherited per-RP.
- Rule Packs: saas/95-multi-tenant-saas, core/35-security-auth, core/85-payments-billing, core/58-resilience,
  core/45-testing-strategy.
- HAS_USER_GUIDE: per-RP (inherited).
- Registrars: **redis** (the NEW `needs_cache` per RP) + each RP's existing registrars. No new deploy unit of its own.
- Universal categories: 2, 5, 12, 13.
- Abuse Detection: inherited per-RP.
- Email: none new (Zitadel owns umbrella mail).
- FINANCIALS: N/A.

### Infrastructure
Inherited from the Infrastructure Decisions spec at
`docs/superpowers/specs/2026-08-27-umbrella-sso-infrastructure-decisions.md` — cited, not duplicated.

### Execution Order
Phase 2. **Sequential after Epic 1** (needs a live issuer) and after the external fabrik-lib prerequisite.
Per-RP integration tickets parallelize within the epic (05) with disjoint per-repo owned paths.

### Entry Point for epic-to-ticket-workflow
When dispatched, run `epic-to-ticket-workflow/00-trigger-fabrik` in multi-epic (consume) mode using this ticket
as the starting context — it verifies the 15-field Metadata block and emits the INFRA-CHECK, then hands to
`01-decisions-lock-fabrik`. Do NOT dispatch straight to `01`. ⚠️ Per-RP tickets are cross-repo and dispatch to
each product's own agents. The Infrastructure Decisions spec above provides the shared infra context.
