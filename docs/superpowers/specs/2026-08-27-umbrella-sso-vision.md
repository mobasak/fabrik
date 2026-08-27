# Vision Summary: Umbrella SSO + Cross-Product Entitlements — Fabrik SaaS Suite

**Status:** LOCKED 2026-08-27
**Mode:** EXISTING (fleet-level) · **Grounding:** fabrik-lib design md5 57dc62e0 + fresh N3k re-verification 2026-08-27 · **Owner-directed:** operator invoked /fab-mega for the umbrella-SSO mega-epic
## Product Vision
The Fabrik SaaS suite is several independently-deployed products (youtube, transdoc, web-ecommerce-factory,
+ future). Today each has its own login and its own notion of who may use it. This vision adds **one umbrella
account**: a user signs in ONCE at a self-hosted IdP and reaches **every product they're entitled to** — or
uses any product **standalone** — with entitlements (which products, which plan/features) enforced
consistently across the suite. Self-hosted on the existing fleet, reusing what we already have.

## Personas
- **Suite subscriber** — pays for one or more products; wants one login, and to land only in products their
  plan entitles them to.
- **Standalone user** — uses a single product, never touches the umbrella; keeps that product's own login
  (incl. passwordless) and its own billing plan.
- **Operator (Özgür)** — provisions the IdP, grants/revokes product access, needs revocation to bite fast
  (not "until the JWT expires").
- **Billing system (machine persona)** — a `payments`/`credits`/`revenuecat` success must reconcile into a
  product-access grant so a paying user is never locked out.

## Value Streams
- **Reduced signup friction → higher cross-sell** — one account lowers the barrier to adopting a second
  product in the suite.
- **Consistent, fast entitlement enforcement** — coarse product-access is source-checked (revocation-fast),
  so access reflects billing reality within a bounded cache TTL, not token expiry.
- **Lower per-product auth maintenance** — federation + a shared entitlements module replaces bespoke
  cross-product access logic in each SaaS.
- **Self-host cost control** — no per-MAU managed-IdP bill at suite scale.

## Full Feature Inventory
*(NEW capabilities only — the existing per-product logins/billing are not re-planned.)*
1. **Umbrella IdP** — self-hosted Zitadel as the central OIDC provider (the one account) (large)
2. **IdP hosted login UI** — branded, i18n (en+tr), responsive; SMTP → the fleet transactional stream (medium)
3. **`oauth-login` OIDC-provider enhancement** — add a generic self-hosted-OIDC adapter (the closed
   `Provider` Literal → add `oidc`) so each SaaS can federate to the umbrella (medium) *(fabrik-lib)*
4. **`product-entitlements` module** — reads Zitadel grant + local plan → a compact entitlement claim +
   boundary re-validation via a short-TTL `redis-main` cache (large) *(fabrik-lib — 🆕 candidate)*
5. **Per-SaaS `LocalAuthBridge`** — each relying-party SaaS mints its own local `fastapi-user-auth` session
   from the umbrella `VerifiedIdentity` + sets the tenant GUC (medium × N products)
6. **Idempotent billing→grant reconciler** — `payments`/`credits`/`revenuecat` success → a Zitadel
   **Authorization v2** grant (⚠️ v1 `AddUserGrant` deprecated); re-runnable without double-granting; no paid-but-locked-out (large)
7. **Revocation → live-session teardown** — OIDC back-channel logout (or short local TTL + periodic
   re-check) so a grant-revoke/umbrella-logout kills live product sessions, not just the next login (large)
8. **Standalone coexistence** — a product still accepts its own login (incl. passwordless); entitlements
   decide access either way (small — mostly inherited)

## Backing Services (from VPS)
- **postgres-main:5432** — Zitadel's own DB (needs_database), and the RP grant reads.
- **redis-main:6379** — the short-TTL product-access grant cache (needs_cache on EVERY consuming RP).
- **Traefik** — routes `auth.ocoron.com` (Zitadel) + the RP domains; no host ports.
- **Prometheus / Gatus / Backrest / Grafana** — standard registrars for the Zitadel service.

## External Services
*(Live-grounded THIS run, 2026-08-27, via pool `fanout` research + a native `fabrik-researcher` Opus
citation-verify pass. ⚠️ This re-verification CORRECTED two stale facts in the 2026-08-22 design.)*

- **Zitadel (self-hosted OIDC IdP)** — the umbrella identity provider.
  - **Version: v4** (latest stable **v4.17.1**, released 2026-08-14) — ⚠️ the design said "v3"; **v3→v4 is a
    stale premise**, though all v3 architectural facts (PostgreSQL-only, AGPL, no CockroachDB) carry forward.
    **source:** https://github.com/zitadel/zitadel/releases (fetched 2026-08-27). *Pin the exact tag at
    deploy time — a pool grounder reported a v3.4.x maintenance line, so the deploy ticket re-verifies the
    current tag rather than trusting this number.*
  - **Image:** `ghcr.io/zitadel/zitadel:v4.x` (pin the tag), **`FROM scratch`** final stage (more minimal
    than distroless — Go binary + CA certs, non-root `USER zitadel`), **linux/amd64** (+arm64). Cost: free
    (self-host). **source:** zitadel `apps/api/Dockerfile` + build workflow (fetched 2026-08-27).
  - **DB:** PostgreSQL **14–18** required (CockroachDB dropped in v3). **source:**
    https://zitadel.com/docs/self-hosting/manage/database (fetched 2026-08-27).
  - **Revocation primitive:** OIDC **back-channel logout** + RP-initiated logout both supported
    (`backchannel_logout_supported`; `end_session_endpoint` at `/oidc/v1/end_session`). **source:**
    https://zitadel.com/docs/guides/integrate/back-channel-logout (fetched 2026-08-27).
  - **Product-access grant:** user↔project↔roles "authorization" (NOT project-grant, which is org→org).
    ⚠️ **v1 `AddUserGrant` is DEPRECATED** — use the **Authorization v2** service. **source:**
    https://zitadel.com/docs/reference/api/management/…AddUserGrant (deprecation note, fetched 2026-08-27).
  - **SMTP:** generic SMTP provider configurable → **Resend** (verification/passwordless mail). **source:**
    https://zitadel.com/docs/guides/manage/customize/notification-providers (fetched 2026-08-27).
  - **License:** AGPL-3.0 (since v3) — **no copyleft obligation** for unmodified self-host + API use (Zitadel's
    own statement). **source:** https://zitadel.com/blog/zitadel-v3-announcement (fetched 2026-08-27).
  - **Memory:** ~512 MB small / **1 GiB recommended** → compose `deploy.resources.limits.memory: 1g` (bump to
    1.5–2g under heavy password hashing). **source:** https://help.zitadel.com/what-are-zitadel-minimum-self-hosted-specs (fetched 2026-08-27).
- **Resend** — the fleet transactional email stream (already owned); Zitadel SMTP points at it. Cost: existing
  free tier (3k/mo). **source:** inherited (`scripts/service_catalog.json`, owned-active).

## Technology Decisions
**Inherited (locked — do NOT re-decide):**
- Each RP SaaS keeps its own `fastapi-user-auth` login + its own billing module (`payments`/`credits`/`revenuecat`).
- Existing per-product tenancy (`tenancy`) unchanged.
- Billing routing: Paddle (intl) / iyzico (TR) / RevenueCat (mobile) — no Stripe.

**New decisions (per current ruleset):**
- **Identity:** self-hosted **Zitadel** as the umbrella OIDC IdP (hub-side `specs/services/zitadel.yaml`).
- **Federation:** `oauth-login` (enhanced with a generic OIDC adapter) — auth-code + PKCE + full
  ID-token/JWKS validation (blocks nOAuth).
- **Entitlements:** hybrid — **Zitadel user↔project authorizations** (Authorization v2 API; `AddUserGrant` v1 deprecated) for coarse product-access (source-checked via a
  short-TTL `redis-main` cache, NEVER a long-lived JWT claim); **billing modules** for plan/feature; unified
  by the new **`product-entitlements`** module.
- **Revocation:** OIDC back-channel logout OR short local-session TTL + periodic re-check (design requirement).
- **Email (transactional):** Zitadel SMTP → Resend; NOT the disabled Authelia SMTP.
- **Watchdog + cost-budget:** Zitadel is not an LLM caller → `watchdog: {enabled: false}` on its spec (opt-out;
  no paid-AI loop). The reconciler calls no LLM either. [confirm at spec time]
- **Target host:** `vps1` (hub) — Zitadel is shared-infra-coupled (postgres-main).
- **Scaffold types:** none new — Zitadel is a deployed third-party service (its own spec), RP work is code in
  existing projects + a fabrik-lib module.

## Locked Decisions (Existing-mode extra section)
- Per-product `fastapi-user-auth` logins — locked (live users, issued tokens).
- Per-product billing (Paddle/iyzico/RevenueCat) — locked (paying customers).
- postgres-main / redis-main as the fleet backing services — locked.
- No Stripe (TR entity) — locked.

## Compliance Report (Existing-mode extra section)
*(Fleet-level; the RP integration epic re-checks per-product. No blocking mechanical gaps at vision level;
the two HARD cross-cutting constraints below are acceptance criteria, not legacy gaps.)*

| Gap / constraint | Source | Decision | Epic action |
|---|---|---|---|
| Every consuming RP spec MUST set `shape.needs_cache: true` | design § Shape/infra (or `fabrik apply` skips Redis registrar → broken deploy) | Fix-now | folded into the integration epic's per-SaaS ticket acceptance |
| Revocation MUST tear down LIVE sessions | design § Security/revocation | Fix-now | folded into the revocation epic/ticket acceptance |

## fabrik-lib Verdict
*(Inherited from the CONVERGED design, md5 57dc62e0 — re-verified as current.)*

| Capability | Verdict | Module + why |
|---|---|---|
| Federated sign-in to the umbrella | **VENDOR + ENHANCE (core)** | `oauth-login` — add a generic `providers/oidc.py` adapter + extend the closed `Provider` Literal; folded upstream, not a fork |
| Per-app local session + bridge | **VENDOR + per-SaaS glue** | `fastapi-user-auth` mints the session; `LocalAuthBridge` is a Protocol each SaaS implements |
| Product access ("which products") | **VENDOR (Zitadel)** | Zitadel user-grants — native multi-tenant product-access store |
| Plan/feature within a product | **VENDOR** | `payments` · `credits` · `revenuecat-entitlements` — already authoritative |
| **Cross-product entitlement gate** | **🆕 BUILD (candidate)** | `product-entitlements` · reads grant + plan → claim + boundary validator; every umbrella SaaS gates on it |
| Orgs/teams within a product | **VENDOR** | `tenancy` — unchanged |
| The IdP itself | **DEPLOYED SERVICE** | Zitadel — hub-side spec, not a module |

## Rejected Alternatives
*(Inherited — do not re-litigate.)*
- **Keycloak** — rejected: heavy Java veteran, higher operational burden than Zitadel.
- **Ory (Kratos+Hydra+Keto+Oathkeeper)** — rejected: headless, "substantially more developer effort."
- **Authentik** — rejected: multi-tenancy "not a core feature."
- **A dedicated central entitlements SERVICE** — rejected as the STARTING point (kept as scale-up path): a
  whole new stateful service to run/back up/sync when Zitadel + billing modules already own the sources; the
  `product-entitlements` MODULE unifies them without a new service.
- **Stripe** — rejected: not available to the TR entity.
- **Long-lived JWT product-access claim** — rejected: revocation wouldn't bite until token expiry.

## Constraints (20 checks, scoped to the delta)
1. x86_64 — all clear (Zitadel official amd64 image). 2. Budget — all clear (self-host, free; Resend already
owned). 3. Existing services — postgres-main/redis-main/Traefik/Resend. 4. Duplicate — all clear (no existing
IdP). 5. Port conflicts — Zitadel gets a PORTS.md allocation at spec time [E-time]. 6. fabrik apply — yes
(Zitadel = Go + Postgres, standard compose). 7. No Alpine — all clear: Zitadel official image is `FROM scratch` (Go binary), linux/amd64 [grounded]. 8. 12-Factor — all clear (env-config IdP, no logfiles, stateless). 9. Solo-dev — achievable
(deploy + module + per-SaaS glue, sequenced). 10. Observability — Zitadel /health + metrics via Gatus/Prom.
11. Vector DB — N/A. 12. Email streams — transactional (Resend) only; no marketing. 13. Compose invariants —
enforced on zitadel.yaml [E-time]. 14. Billing — inherited (Paddle/iyzico/RevenueCat), reconciler consumes
them. 15. LLM gateway — N/A (no LLM). 16. i18n — Zitadel login UI en+tr. 17. target_vps — vps1 (hub).
18. KVKK — Zitadel stores identity PII on self-hosted postgres-main (hub); acceptable. 19. Watchdog — opt-out
(no paid-AI loop). 20. Node/Python floors — RP glue follows each project's existing floor.

## Out of Scope (Vision Level)
- Migrating existing per-product logins away from `fastapi-user-auth` (standalone stays).
- Re-planning any product's existing billing or tenancy.
- SAML / enterprise-IdP federation INTO the umbrella (OIDC only for now).
- The website side (`/opt/web-ecommerce-factory` Astro store) — not an SSO relying party in this run.
- unit 3's fabrik-lib module BUILD detail (fabrik-lib owns it; infra says largely DONE).

## Open Questions
- None blocking. Two design requirements are carried as HARD acceptance constraints (needs_cache on every RP;
  live-session teardown on revoke). Per-SaaS integration order (which RP first) is a 02/03 decomposition detail.

## Scale Assessment
- New feature count: 8 (1 small, 3 medium, 4 large).
- Classification: **multi-epic (~3 epics)** — (A) fabrik-lib module + oauth-login enhancement [largely done];
  (B) Zitadel IdP deploy foundation [hub]; (C) cross-SaaS integration + billing→grant reconciler + revocation
  [hub, N products, depends on B].
- Reasoning: a self-contained IdP deploy (B) and a multi-product rollout (C) with a hard live-issuer
  dependency between them, plus a cross-repo module (A) — cannot be one shippable unit.
- Next step: **Proceed to `02-epic-decomposition-fabrik`** to define epic boundaries + dependency graph.
