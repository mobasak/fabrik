# Zitadel — umbrella OIDC identity provider (`auth.ocoron.com`)

Self-hosted **Zitadel v4** is the umbrella OIDC IdP for the Fabrik SaaS suite: one account, federated to by
every relying-party product (Epic 2). This doc is the deploy runbook + verification reference for the
`specs/services/zitadel.yaml` deploy. Grounded against the Zitadel v4.17.0 source (`cmd/defaults.yaml` +
`cmd/setup/steps.yaml`) and the docs (fetched 2026-08-28).

## What `fabrik apply specs/services/zitadel.yaml` provisions

`shape:` drives six registrars (verified against `infrastructure.py`): **postgres** (`needs_database` → creates
the `zitadel` DB on `postgres-main` + injects `DATABASE_URL`), **gatus** (`is_public`+`domain` → uptime probe),
**prometheus** (`exposes_metrics`+`domain` → scrape target), **backrest** (`has_persistent_data` → daily
backup), **grafana** (always), **glitchtip** (`kind:service` → mints a project + injects `GLITCHTIP_DSN`,
verified via `docker inspect`). **NOT** authelia (Zitadel *is* the auth), **NOT** redis, **NOT** meilisearch.

## Grounded config (the `env:` block, explained)

- **TLS behind Traefik:** `--tlsMode external` (in `source.image_command`) + `ZITADEL_EXTERNALSECURE=true` +
  `ZITADEL_TLS_ENABLED=false` — Zitadel serves plain HTTP internally; Traefik terminates HTTPS. `EXTERNALPORT=443`
  (the port end users reach), `PORT=8080` (internal listen).
- **Masterkey:** `secrets.generate` mints `ZITADEL_MASTERKEY` = exactly 32 `[a-zA-Z0-9]` chars (Zitadel's hard
  requirement). **Never rotate it** — it decrypts stored data. `start-from-init` = init+setup+start one-shot;
  the compose emitter (`_generate_docker_compose`) interpolates `${ZITADEL_MASTERKEY}` from `.env` at up-time.
- **DB (DSN-only):** the postgres registrar injects only a single `DATABASE_URL`, so the spec uses
  `ZITADEL_DATABASE_POSTGRES_DSN=${DATABASE_URL}` (+ `_USER_SSL_MODE=disable` for the internal `fabrik` net).
  The registrar pre-creates the `zitadel` DB owned by the DSN's role, so `init` (DSN-only) creates only the
  schema (it has DDL) — no separate `ADMIN_*` block.
- **First admin (non-interactive):** `ZITADEL_FIRSTINSTANCE_ORG_HUMAN_{USERNAME,EMAIL_ADDRESS,PASSWORD}` +
  `PASSWORDCHANGEREQUIRED=true`; password is `secrets.generate`d — retrieve it from the deployed `.env`, sign in,
  change it. `DEFAULTLANGUAGE=en`.
- **SMTP → Resend:** `ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_SMTP_{HOST=smtp.resend.com:465,USER=resend,PASSWORD=${RESEND_API_KEY}}`
  + `_TLS=true` + `_FROM=noreply@ocoron.com`. Applied at first-init; ongoing changes are Console/Admin-API.

Sources: <https://zitadel.com/docs/self-hosting/manage/configure/configure> ·
<https://zitadel.com/docs/self-hosting/manage/tls_modes> · <https://zitadel.com/docs/apis/observability/health>.

## Deploy runbook (operator-gated — the deploy triad)

This is a deployed service: the hub runs `fabrik apply` (SSH + Docker Compose); Zitadel is a third-party image
pulled from `ghcr.io`. The plan authors the spec + this doc; **the deploy itself is the operator-gated triad**
(`/fabrik-deploy-plan → /fabrik-deploy → /fabrik-deploy-verify`). ⚠️ **KNOWN DEPLOY BLOCKER (D1):** `start-from-init`
has **no DB-connection retry** and fabrik injects `DATABASE_URL` only *after* the first `docker compose up`, so a
plain `fabrik apply` crashes before the DSN arrives and rolls back before the DB is created. A **bootstrap**
(pre-create the `zitadel` DB+role + pre-seed the DSN into the remote `.env` before first `up`) is required — see
the deploy plan's ⚠️ BLOCKING FINDING. ⚠️ **The image is FROM scratch — no shell.**
Verify injected env with `docker inspect` (`sudo docker inspect zitadel --format '{{range .Config.Env}}{{println .}}{{end}}'`),
**never** `docker exec … printenv`.

## Health / metrics (non-standard paths — NOT behind Authelia)

- Liveness `/debug/healthz` · **readiness `/debug/ready`** (DB-checked — returns non-200 when `postgres-main` is
  unreachable) · metrics `/debug/metrics` (Prometheus, enabled by default via `ZITADEL_METRICS_TYPE: otel`).
- ⚠️ These `/debug/*` paths do **not** match the fabrik Authelia-bypass list (`/health`,`/healthz`,`/metrics`,
  `/api/health`) — but Zitadel is NOT behind Authelia (no authelia registrar), so Gatus/Prometheus probe them
  directly. **Do not add an Authelia bypass** for these.

## Post-deploy Console steps (what env can't do)

- **Branding** (logo/colors/custom texts) — Console → private-labeling, or the Management API. Env cannot seed it.
- **i18n en/tr** — `tr` ships natively in v4.17.0 (`internal/api/ui/login/static/i18n/tr.yaml`); confirm the login
  UI language switch renders both (Criterion #5). `DEFAULTLANGUAGE=en`.
- **SMTP** — env-seeded at first-init, so only a delivery test is needed post-deploy.

## Resilience (self-healing rows — `core/58-resilience.md`)

| Failure class | First response | Escalate |
|---|---|---|
| OOM (>1 GiB) | container restart (`restart: unless-stopped`); raise `resources.memory` if recurrent | Watchdog Tier A alert |
| DB-pool exhaustion / `postgres-main` unreachable | `/debug/ready` goes non-200 → Gatus flags; Zitadel retries its own pool | Gatus ContainerDown / probe-fail alert |
| Upstream (Resend SMTP) timeout | verification mail retried by Zitadel; login/OIDC unaffected | GlitchTip event (DSN injected) |

## Success-Criteria verification (the epic's 7 — each with its probe)

| # | Criterion | Verification |
|---|---|---|
| 1 | deploy/gate | `fabrik apply …` succeeds; `curl -fsS https://auth.ocoron.com/debug/ready` → 200 |
| 2 | feature (login + OIDC) | open `https://auth.ocoron.com`, create/sign-in; `curl -s https://auth.ocoron.com/.well-known/openid-configuration \| jq .backchannel_logout_supported` → true; JWKS reachable |
| 3 | resilience (dead DB) | with `postgres-main` unreachable, `/debug/ready` returns non-200 (Gatus flags it) |
| 4 | audit | account-creation + admin actions appear in Zitadel's event store (Console → events, or the events API) |
| 5 | i18n | login UI renders `en` and `tr` (locale switch observable) |
| 6 | observability | Gatus probe green; Prometheus scrape target for `/debug/metrics` registered; `docker inspect zitadel` shows `GLITCHTIP_DSN` present |
| 7 | SMTP | a verification email is delivered through Resend |

## Produces (for Epic 2 — cross-SaaS SSO)

- OIDC issuer `https://auth.ocoron.com` + discovery/JWKS.
- A Zitadel project+app per relying party → `ZITADEL_CLIENT_ID` / `ZITADEL_CLIENT_SECRET`.
- The **Authorization v2** grant API (⚠️ v1 `AddUserGrant` is deprecated).
- Shared env `ZITADEL_ISSUER=https://auth.ocoron.com` (every RP).

---

_Deploy spec: `specs/services/zitadel.yaml`. Epic: `docs/development/epics/2026-08-27-epic-1-zitadel-umbrella-idp.md`._
