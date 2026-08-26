# Epic 2 — Umbrella SSO + entitlements: the HUB DEPLOY units (1 + 4–7)

**Status:** KICKED-OFF (accepted by fleet 2026-08-26) · **Owner:** fleet (deploy/provisioning beat)
**Grounding design (CONVERGED, md5 `57dc62e0`):** `fabrik-lib:docs/superpowers/specs/2026-08-22-umbrella-sso-entitlements-design.md`
**Split agreed with fabrik-lib (mail `01M0YTDDYP` / `01M0Z30G89`):** unit 3 (the `product-entitlements`
client module) is **fabrik-lib's and DONE — not a ticket here**. This epic is the hub-side deploy work only.
**Execution vehicle:** the hub epic-to-ticket workflow — `docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik.md`
(run by the orchestrator agent through stages 01–08). This file is that workflow's **input epic ticket**.

## Why (one line)
Sign in once, reach every entitled product across the Fabrik SaaS suite (or use any product standalone),
with entitlements enforced consistently — self-hosted Zitadel as the umbrella IdP, on the existing fleet.

## Scale note
The umbrella *rollout* is epic-scale (a new IdP service + every SaaS integrated + billing reconciled). The
grounding spec is the feature-scale ARCHITECTURE; this epic is its hub-side build, decomposed below.

## ⚠️ Two HARD acceptance constraints (verified in the design — every ticket inherits them)
1. **`needs_cache: true` on EVERY consuming relying-party spec** (§ Shape/infra). The short-TTL grant cache
   lives in `redis-main`; if an RP spec omits it, `fabrik apply` **skips the Redis registrar** and the cache
   silently does not exist → a broken deploy. A ticket that adds an RP without this fails acceptance.
2. **Revocation MUST tear down LIVE product sessions** (§ Security / § revocation), not merely block the next
   login. Local sessions are minted per-product, so umbrella logout or a grant revoke uses **OIDC
   back-channel logout** (Zitadel → each RP) **or** a short local-session TTL + periodic entitlement re-check.
   Coarse product-access is **source-checked per boundary via the short-TTL cache, NEVER a long-lived JWT
   claim** (a claim stays valid until token expiry — revocation wouldn't bite).

## Units → tickets (build order; Unit 1 gates 4–7 — they need a live issuer)

### Ticket 1 — Deploy Zitadel as the umbrella IdP (hub-side spec + `fabrik apply`)
- `specs/services/zitadel.yaml`: `shape.needs_database: true` (its own **PostgreSQL 14–18** DB on
  `postgres-main` — no CockroachDB, dropped in Zitadel v3), Traefik-routed **`auth.ocoron.com`**,
  `deploy.resources.limits.memory` set, **no host `ports:`**, official **distroless amd64** image.
- Zitadel config via env only (issuer/keys as config, 12-Factor III/IV); no logfiles (XI).
- **Zitadel SMTP → the fleet transactional stream (Resend)**, NOT the disabled Authelia SMTP.
- AGPL note: self-host unmodified + API use carries no copyleft; only modifying Zitadel's code would.
- Acceptance: `fabrik apply specs/services/zitadel.yaml` brings Zitadel up healthy; a live OIDC discovery
  doc at `https://auth.ocoron.com/.well-known/openid-configuration`; its Postgres DB + Gatus endpoint
  registered; `/health`-class path Authelia-bypassed.

### Ticket 2 — Brand + i18n the Zitadel hosted login UI (customer surface)
- Zitadel custom branding / Login v2: brand it, enable **i18n (en+tr)**, responsive. Outside `/fabrik-ui-design`
  (it's Zitadel's hosted surface) but it IS a customer surface — treat as an epic deploy-ticket item.

### Tickets 3–6 — per-SaaS `LocalAuthBridge` integration + the billing→grant reconciler (Units 4–7)
- Each relying-party SaaS: `oauth-login` config (issuer / client-id / secret via env), `needs_auth`, and —
  **HARD constraint #1** — `shape.needs_cache: true`. `oauth-login`'s `LocalAuthBridge` mints the app's own
  `fastapi-user-auth` session from the `VerifiedIdentity` (one umbrella login → a local session per product).
  Federation is auth-code + PKCE + full ID-token/JWKS validation (blocks nOAuth).
- **Idempotent billing→grant reconciler:** `payments` (Paddle intl / iyzico TR) · `credits` · `revenuecat`
  (mobile) → Zitadel **user-grants** (`AddUserGrant`, NOT project-grant) so there is **no paid-but-locked-out**
  user; re-runnable without double-granting. Plan/feature stays authoritative in the billing modules; coarse
  product-access is the Zitadel grant, source-checked via the short-TTL cache.
- Standalone coexistence: a product still accepts its own `fastapi-user-auth` login (incl. passwordless);
  `product-entitlements` (fabrik-lib, done) decides access either way.

## Handoff
Run `docs/orchestrator/epic-to-ticket-workflow/00-trigger-fabrik.md` against this epic ticket to expand
Tickets 1–6 into executable plans (it grounds Zitadel's deploy specifics LIVE via MCP + gates each stage).
Start with Ticket 1 — Units 4–7 all depend on a live Zitadel issuer.
