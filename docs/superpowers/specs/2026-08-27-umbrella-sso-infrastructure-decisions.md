# Infrastructure Decisions — Umbrella SSO (shared across all epics)

**Status:** CONVERGED 2026-08-28 (validated by `mega-04-validate` — `docs/development/reviews/2026-08-27-mega-umbrella-sso-validation-review.md` § "Infrastructure Decisions: PASS", cross-epic no-op) · **Source:** docs/superpowers/specs/2026-08-27-umbrella-sso-epic-proposal.md
Made ONCE here; each epic ticket **references** this file (never duplicates it). Do NOT re-decide in
epic-to-ticket-workflow.

## Database Strategy
- **postgres-main** holds everything. Zitadel gets its **own database** on `postgres-main` (PostgreSQL 14–18;
  CockroachDB dropped in Zitadel v3+). RP grant reads go through the Zitadel API, not direct DB access.
- No Supabase. No new DB host.

## Auth Strategy
- **Zitadel v4** is the umbrella OIDC IdP (`auth.ocoron.com`). Federation via the fabrik-lib `oauth-login`
  generic-OIDC adapter (auth-code + PKCE + full ID-token/JWKS validation — blocks nOAuth).
- Each RP keeps its own `fastapi-user-auth` local session (standalone path unchanged); a per-RP
  `LocalAuthBridge` mints it from the umbrella `VerifiedIdentity`.
- Coarse product-access = **Zitadel Authorization v2** grants (⚠️ v1 `AddUserGrant` deprecated), source-checked
  per boundary via a short-TTL `redis-main` cache — **never a long-lived JWT claim**.
- **Universal category #12 — Security.** Grant mutations, auth events, and revocations write to the
  hash-chained audit log per `core/app-audit-log.md` (vendor the audit-log module from the fabrik-lib index).

## Email Strategy
- **Transactional only:** Zitadel SMTP → **Resend** (generic SMTP provider) for verification/passwordless mail.
- No marketing stream in scope.

## Background Processing
- The **billing→grant reconciler** runs async on each RP's PostgreSQL job queue (`core/75-workers-jobs.md`) —
  **idempotent, re-runnable without double-granting**; never inline >10s in a request handler.

## Self-Healing Ladder
- Zitadel (`kind: service`) carries a `docs/RESILIENCE.md` row per failure class per `core/self-healing.md`
  (OOM, DB pool exhaustion, upstream timeout). Primitives from fabrik-lib (resolve from the index) + Watchdog
  Tier A. Not designed here — coverage asserted.

## Watchdog Wiring
- **Zitadel spec: `watchdog: { enabled: false }`** (explicit opt-out — no paid-AI loop; the resolver is ON by
  default, so the opt-out must be declared). The reconciler calls no LLM either.

## Observability Defaults
- Zitadel exposes `/health` (real dep — its own DB) + `/metrics`; Gatus probes `auth.ocoron.com`; GlitchTip DSN
  injected by the registrar. Per `core/55-observability.md`. (Distroless/scratch image → verify env via
  `docker inspect`, never `docker exec printenv`.)

## Cost Guardrails
- **N/A** — no epic calls a paid LLM or metered third-party API. (Zitadel self-host + Resend free tier.)

## Backing Services
- postgres-main (Zitadel DB + RP grant reads) · redis-main (the short-TTL grant cache — `needs_cache` on every
  consuming RP) · Traefik (routes `auth.ocoron.com` + RP domains) · Resend (Zitadel SMTP).

## External Services
- **Zitadel v4** (self-host, `ghcr.io/zitadel/zitadel:v4.x`, FROM scratch, amd64, ~1 GiB) — AGPL, no copyleft
  for unmodified self-host. **Resend** — transactional email (owned). Full grounding + cited sources: the
  vision's § External Services (fetched 2026-08-27).
- **Universal category #5 — External integrations.** Each RP's `docs/RESILIENCE.md` carries a row for the
  Zitadel API call (timeout, retry, circuit-breaker, fallback, error classifier) per `core/58-resilience.md`.

## Domain Structure
- `auth.ocoron.com` → Zitadel (the umbrella issuer). RP domains unchanged; each federates to the issuer.

## Shared Environment Variables
- `ZITADEL_ISSUER=https://auth.ocoron.com` (all RPs) · per-RP `ZITADEL_CLIENT_ID` / `ZITADEL_CLIENT_SECRET`
  (from Zitadel project/app) · `REDIS_URL` (grant cache, per RP) · Zitadel's own DB + SMTP env (Epic 1).

## Shared Shape Decisions
- Epic 1 (Zitadel): needs_database, is_public, has_persistent_data, exposes_metrics; registrars
  postgres/gatus/prometheus/backrest/grafana/glitchtip; NOT authelia (Zitadel *is* the auth), NOT redis.
- Epic 2: the load-bearing change is **`shape.needs_cache: true` on EVERY consuming RP spec** — or
  `fabrik apply` skips the Redis registrar and the grant cache silently doesn't exist (HARD constraint).

## Deferred Compliance (not actioned this run)
All vision-level constraints are folded into Epic 2's acceptance criteria; nothing deferred.
