---
kind: story
title: "Epic 1 — Zitadel Umbrella IdP Deployment"
status: 0
epic_n: 1
slug: zitadel-umbrella-idp
depends_on: []
parallel_with: []
owned_paths: ["specs/services/zitadel.yaml", "docs/reference/zitadel.md"]
scaffold: none
port: 8080
target_vps: vps1
---
## Epic 1 — Zitadel Umbrella IdP Deployment

### Summary
Deploy self-hosted **Zitadel v4** as the umbrella OIDC identity provider at `auth.ocoron.com` — the single
account the whole Fabrik SaaS suite federates to. This epic stands up the service (its own PostgreSQL DB on
`postgres-main`, Traefik-routed, no host ports), brands + internationalizes (en+tr) its hosted login UI, and
wires its SMTP to Resend. It is the identity **foundation**: nothing in Epic 2 can federate until this issuer
is live. It delivers a login the operator can create an account on and sign into today.

### Scope
**In:**
- **#1** Umbrella IdP — deploy Zitadel v4 (`ghcr.io/zitadel/zitadel:v4.x`, FROM-scratch amd64 image) via a
  hand-authored `specs/services/zitadel.yaml`; its own database on `postgres-main` (PostgreSQL 14–18);
  Traefik route `auth.ocoron.com`; `deploy.resources.limits.memory: 1g`; **no host `ports:`**;
  `watchdog: { enabled: false }`.
- **#2** IdP hosted login UI — Zitadel custom branding + **i18n (en+tr)** + responsive (Login v2); SMTP
  configured to **Resend** (generic SMTP) for verification/passwordless mail.

**Out:**
- Per-SaaS federation / LocalAuthBridge / entitlements — handled by Epic 2.
- The fabrik-lib `oauth-login` OIDC adapter + `product-entitlements` module — external (fabrik-lib), not this epic.

### Success Criteria
1. **Deploy/gate:** `fabrik apply specs/services/zitadel.yaml` succeeds; the Zitadel container is healthy and
   its `/health` (real DB dep) returns 200 behind the Authelia-bypass.
2. **Feature (Delivers):** the operator opens `https://auth.ocoron.com`, creates an account, and signs in; the
   OIDC discovery doc at `https://auth.ocoron.com/.well-known/openid-configuration` and JWKS are reachable and
   advertise `backchannel_logout_supported`.
3. **Resilience:** when `postgres-main` is unreachable, Zitadel's `/health` returns non-200 (Gatus flags it) —
   it does not report healthy against a dead DB.
4. **Audit:** account-creation and admin actions are captured in Zitadel's own event store (queryable).
5. **i18n:** the login UI renders in both `en` and `tr` (locale switch observable).
6. **Observability:** the Gatus probe on `auth.ocoron.com` is green; the Prometheus scrape target for Zitadel
   `/metrics` is registered (requires `spec.domain` + `exposes_metrics`); GlitchTip DSN injected (verified via
   `docker inspect`, not `docker exec` — scratch image has no shell).
7. **SMTP:** a verification email is delivered through Resend from the Zitadel SMTP config.

### Out of Scope (Epic Level)
- Per-SaaS integration, the billing→grant reconciler, revocation teardown — handled by Epic 2.
- SAML / enterprise-IdP federation INTO the umbrella (vision-level Out of Scope) — not in this product.
- The website store (`/opt/web-ecommerce-factory`) as a relying party — vision-level Out of Scope.

### Dependencies
- **Consumes from prior epics:** none — root epic.
- **Produces for later epics:** the OIDC issuer `https://auth.ocoron.com` + discovery/JWKS endpoints; a Zitadel
  project+app per RP yielding `ZITADEL_CLIENT_ID` / `ZITADEL_CLIENT_SECRET`; the **Authorization v2** grant API
  surface; env `ZITADEL_ISSUER`.
- **Depends on:** none — root epic. (External: the fabrik-lib `oauth-login` adapter is consumed by Epic 2, not here.)
- **Parallel with:** none.
- **Owned paths:** `specs/services/zitadel.yaml`, `docs/reference/zitadel.md`. No RP code.

### Metadata
- Scaffold: none (third-party `service` via a hand-authored spec; not one of the 11 scaffold types).
- Port: `:8080` container-internal (Zitadel default); Traefik-routed on `auth.ocoron.com`; **no host `ports:`**.
- target_vps: vps1
- Shape: `kind: service` · is_public: true · is_admin_dashboard: false · has_bearer_api: false ·
  has_persistent_data: true · needs_database: true · has_search_feature: false · needs_cache: false ·
  exposes_metrics: true · watchdog.enabled: **false**.
- Concurrency: none (managed third-party service).
- i18n: en+tr — **Zitadel-native** custom-branding/i18n (NOT `scripts/validate_i18n.py` — that ships only to
  the 5 I18N_ENABLED_TYPES; this is a third-party service, so the mandate is met by Zitadel's own i18n).
- Responsive: yes (Zitadel Login v2).
- Dark+Light: Zitadel branding (best-effort; third-party UI).
- Rule Packs: core/30-ops, core/35-security-auth, core/55-observability, core/58-resilience.
- HAS_USER_GUIDE: false.
- Registrars: postgres (needs_database) · gatus (is_public + domain) · prometheus (exposes_metrics + domain) ·
  backrest (has_persistent_data) · grafana (always) · glitchtip (kind=service). NOT redis, NOT authelia
  (Zitadel *is* the auth), NOT meilisearch.
- Universal categories: 1, 2, 3, 8, 10, 11, 12, 13.
- Abuse Detection: N/A — Zitadel owns its own registration hardening.
- Email: transactional — Zitadel SMTP → Resend.
- FINANCIALS: N/A.

### Infrastructure
Inherited from the Infrastructure Decisions spec at
`docs/superpowers/specs/2026-08-27-umbrella-sso-infrastructure-decisions.md` — cited, not duplicated.

### Execution Order
Phase 1 (root). Runs after the external fabrik-lib prerequisite; **gates Epic 2** (which needs this live issuer).

### Entry Point for epic-to-ticket-workflow
When dispatched, run `epic-to-ticket-workflow/00-trigger-fabrik` in multi-epic (consume) mode using this ticket
as the starting context — it verifies the 15-field Metadata block and emits the INFRA-CHECK, then hands to
`01-decisions-lock-fabrik`. Do NOT dispatch straight to `01`. The Infrastructure Decisions spec above provides
the shared infra context.
