# Epic 1 — Zitadel Umbrella IdP Deployment (plan)

Status: DRAFT

Author the two hub artifacts that make `fabrik apply` stand up **Zitadel v4** as the umbrella OIDC IdP at
`auth.ocoron.com`: the hand-authored deploy spec `specs/services/zitadel.yaml` and the reference/runbook
`docs/reference/zitadel.md`. This is an **artifact-authoring** plan — the live `fabrik apply` deploy and the
epic's live Success-Criteria verification are the operator-gated **deploy triad** (`/fabrik-deploy-plan` →
`/fabrik-deploy` → `/fabrik-deploy-verify`) downstream, NOT this plan's code. Source of truth: the epic
`docs/development/epics/2026-08-27-epic-1-zitadel-umbrella-idp.md` + the Infrastructure Decisions spec
`docs/superpowers/specs/2026-08-27-umbrella-sso-infrastructure-decisions.md`. Produces the OIDC issuer +
per-RP client-cred surface + Authorization-v2 grant API that Epic 2 consumes.

## Global Constraints

Every phase inherits these verbatim.

- **Deploy model:** `fabrik apply specs/services/zitadel.yaml` (SSH + Docker Compose, hub-side, operator-gated);
  the VPS `git pull`s nothing for a `source.type: docker` service — the image is pulled. Deploy is
  trigger-not-execute; **this plan does NOT run `fabrik apply`.** `fabrik plan <spec>` (read-only preview) IS a
  valid gate in the hub.
- **Infra invariants (agents-fabrik.md):** shared DB reached as `postgres-main:5432` (never `localhost`);
  external `fabrik` network; **no host `ports:`** (Traefik routes by label); `container_name: zitadel` mandatory;
  `deploy.resources.limits.memory` mandatory (`_validate_compose()` refuses a service without it); stable
  container DNS (`zitadel`), never UUID.
- **12-Factor (binding on what the spec may STEP):** logs = unbuffered JSON to stdout only (Zitadel logs to
  stdout by default — never add a logfile); config = granular env vars, no grouped set, no secret in the spec
  literal (secrets minted via `secrets.generate` or `from_env`); releases immutable (pin the image digest at
  deploy); no daemonize/PID file; the image ships its own binary (no shell — scratch/distroless).
- **Zitadel v4 grounded config (official v4.17.0 source `cmd/defaults.yaml` + `cmd/setup/steps.yaml` + docs,
  fetched 2026-08-28 — cited in Evidence; corroborated by a `fabrik-researcher` read of the raw source):**
  image `ghcr.io/zitadel/zitadel:v4.x` (FROM scratch, amd64, 512 MiB min / **1 GiB recommended**); container
  command `start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode external` (`start-from-init` =
  init+setup+start one-shot); **masterkey EXACTLY 32 chars, stable-forever** (fabrik's 32-char `[a-zA-Z0-9]`
  `secrets.generate` satisfies it — never rotate: it decrypts stored data). **TLS behind Traefik:**
  `--tlsMode external` + `ZITADEL_EXTERNALSECURE=true` (advertise https) + **`ZITADEL_TLS_ENABLED=false`**
  (Zitadel serves plain HTTP internally; Traefik terminates TLS). Internal listen `ZITADEL_PORT=8080`,
  `ZITADEL_EXTERNALPORT=443`, `ZITADEL_EXTERNALDOMAIN=auth.ocoron.com`.
  **DB:** the fabrik postgres registrar PRE-CREATES the `zitadel` DB owned by the injected role, so Zitadel's
  `init` only creates its SCHEMA inside the existing DB (no `CREATE DATABASE` needed) — set
  `ZITADEL_DATABASE_POSTGRES_ADMIN_EXISTINGDATABASE=zitadel` and both the ADMIN (init) and USER (runtime) blocks
  to the ONE registrar role that owns the DB (`HOST=postgres-main`, `PORT=5432`, `DATABASE=zitadel`,
  `USER_USERNAME`/`USER_PASSWORD` + `ADMIN_USERNAME`/`ADMIN_PASSWORD` = the injected creds,
  `*_SSL_MODE=disable` — correct for the internal `fabrik` net). **SMTP** env at first-init
  (`ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_SMTP_*` → Resend `smtp.resend.com:465`/`resend`/api-key/`TLS=true`;
  ongoing changes are Console/API). **First admin** non-interactive via `ZITADEL_FIRSTINSTANCE_ORG_HUMAN_*`
  (NOT `DEFAULTINSTANCE`). **Health/metrics (CONFIRMED against source):** liveness `/debug/healthz`, readiness
  `/debug/ready` (DB-checked), metrics `/debug/metrics` (Prometheus, **enabled by default** via
  `ZITADEL_METRICS_TYPE: otel` — no enabling needed), none behind Zitadel auth. **i18n:** `tr` is shipped in
  v4.17.0 (`internal/api/ui/login/static/i18n/tr.yaml`) — Criterion #5 is met natively; branding is post-deploy
  Console/Management-API.
- **NOT authelia** (Zitadel IS the auth) · **NOT redis** · **NOT meilisearch**. Registrars that DO fire:
  postgres (needs_database) · gatus (is_public+domain) · prometheus (exposes_metrics+domain) · backrest
  (has_persistent_data) · grafana (always) · glitchtip (kind=service).
- **Watchdog OFF** — `watchdog: { enabled: false }` explicit (the resolver defaults ON; a missing block would
  wrongly enable a paid-AI sidecar on a third-party image).

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/30-ops.md` (ACTIVE) | Docker/compose/Traefik: no host `ports:`, mandatory `container_name` + memory limit, Traefik-label routing | `core/30-ops.md:135-137` |
| `.windsurf/rules/core/35-security-auth.md` (ACTIVE) | secret handling (32-char generated policy), no secret in code, JWT/OIDC discipline | `core/35-security-auth.md` (generated-password + secret-handling) |
| `.windsurf/rules/core/55-observability.md` (ACTIVE) | `/health` (real dep), `/metrics`, GlitchTip DSN injection, stdout-only logs; scratch image → verify env via `docker inspect` not `docker exec` | `core/55-observability.md` § Error Reporting + health/metrics |
| `.windsurf/rules/core/58-resilience.md` + `core/self-healing.md` (ACTIVE) | `docs/RESILIENCE.md` row per failure class (OOM, DB-pool, upstream-timeout) for a `kind:service` | `core/self-healing.md:14-21` |
| `specs/services/evolution-api.yaml` (template) | the single-image `source.type:docker` spec shape: `depends.postgres`, `secrets.generate`, `expose`, `watchdog:false`, `backup` | `specs/services/evolution-api.yaml:1-70` |
| `src/fabrik/spec_loader.py::Shape` | the valid `shape.*` flags the spec must set | `spec_loader.py:205-380` |
| `src/fabrik/orchestrator/infrastructure.py` | the postgres registrar honors `depends.postgres`, provisions the DB + injects `DATABASE_URL`; `exposes_metrics`+domain → prometheus | `infrastructure.py:521-578,308-317` |
| Infrastructure Decisions spec (FROZEN context) | DB strategy (own DB on postgres-main), auth (Zitadel v4 issuer), email (SMTP→Resend), observability, domain, shape, env, watchdog-off | `docs/superpowers/specs/2026-08-27-umbrella-sso-infrastructure-decisions.md` |
| **fabrik-lib consult** | no reusable module applies — Zitadel is a third-party IMAGE, not a capability we build; `oauth-login`/`product-entitlements` are **Epic-2** consumers, out of scope here. No vendor, no fresh build, **no 🆕 candidate.** | `fabrik-lib/README.md` (checked; N/A for a third-party deploy) |

## Phase A — Author `specs/services/zitadel.yaml` (the deploy spec)

**Deliverable:** a hand-authored single-image (`source.type: docker`) service spec whose `shape:` matches the
epic exactly and whose `env:` carries the grounded Zitadel v4 config, so `fabrik apply` provisions the 6
registrars and deploys a Zitadel that self-inits its schema, bootstraps an admin, and wires SMTP→Resend.

**Steps:**
1. **Confirm the registrar's DB-provisioning contract, then map to Zitadel's decomposed keys** (GROUNDED — the
   researcher resolved the nuance): read `infrastructure.py:566-590` and confirm the postgres registrar
   PRE-CREATES the `zitadel` DB owned by the injected role and injects a single `DATABASE_URL` DSN. Because the
   DB already exists (registrar-created) and the scratch image can't shell-parse a DSN, write the DECOMPOSED
   Zitadel keys: `ZITADEL_DATABASE_POSTGRES_HOST=postgres-main`, `PORT=5432`, `DATABASE=zitadel`,
   `USER_USERNAME`/`USER_PASSWORD` = the injected role creds, `USER_SSL_MODE=disable`,
   `ADMIN_USERNAME`/`ADMIN_PASSWORD` = the SAME role, `ADMIN_SSL_MODE=disable`, and
   **`ADMIN_EXISTINGDATABASE=zitadel`** — the registrar's own DB, so `init` creates only the SCHEMA inside it (no
   `CREATE DATABASE`, no superuser needed; the owning role has DDL). The injected creds reach the env via the
   registrar (same mechanism `DATABASE_URL` uses); Phase A wires the decomposed keys to those creds (a small
   `.env`-mapping note in the spec, resolved with the registrar author if the decomposed form isn't
   auto-injected — the fallback is `ZITADEL_DATABASE_POSTGRES_DSN=${DATABASE_URL}` for the USER block + the
   ADMIN block from the same creds).
2. Author `specs/services/zitadel.yaml` mirroring `evolution-api.yaml`'s shape, with:
   - `id: zitadel` · `kind: service` · `domain: auth.ocoron.com`
   - `shape:` `kind: service`, `is_public: true`, `is_admin_dashboard: false`, `has_bearer_api: false`,
     `has_persistent_data: true`, `needs_database: true`, `has_search_feature: false`, `needs_cache: false`,
     `exposes_metrics: true`
   - `expose: { http: true }` (public — NOT `internal_only`)
   - `source: { type: docker, image: ghcr.io/zitadel/zitadel:v4.x, image_port: 8080 }`
   - `command: start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode external`
   - `depends: { postgres: zitadel }`
   - `env:` the grounded ZITADEL_* block (externaldomain/port/secure, **`ZITADEL_TLS_ENABLED: "false"`**,
     PORT=8080, the decomposed DB keys incl. `ADMIN_EXISTINGDATABASE=zitadel`,
     `ZITADEL_FIRSTINSTANCE_ORG_NAME`/`_ORG_HUMAN_USERNAME`/`_ORG_HUMAN_EMAIL_ADDRESS`/`_ORG_HUMAN_PASSWORD=${ZITADEL_ADMIN_PASSWORD}`/`_ORG_HUMAN_PASSWORDCHANGEREQUIRED=true`/`_DEFAULTLANGUAGE=en`,
     the `ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_SMTP_HOST=smtp.resend.com:465`/`_SMTP_USER=resend`/`_SMTP_PASSWORD=${RESEND_API_KEY}`/`_TLS=true`/`_FROM`/`_FROMNAME` block)
   - `secrets: { required: [], generate: [ZITADEL_MASTERKEY, ZITADEL_ADMIN_PASSWORD], from_env: [RESEND_API_KEY], from_file: {} }`
   - `resources: { memory: 1G, cpu: '0.5' }` · `health: { disabled: true }` (scratch image has no curl for a
     compose HEALTHCHECK — Gatus does the external HTTP probe on `/debug/ready`) · `volumes: []` ·
     `companion_services: []` · `backup: { enabled: true, frequency: daily, retention: 30 }` ·
     `watchdog: { enabled: false }` · `infra: { glitchtip: true }` (inject the DSN env per epic Criterion #6 —
     present-but-unused; verify with `docker inspect` at deploy)
3. **Behavior Contract** (below) — assert the spec parses and its shape/registrar footprint match the epic.
4. Run the phase gate → fix to green.
5. `python scripts/enforcement/check_doc_sync.py` + no doc owed by the SPEC file itself (the reference doc is Phase B).
6. `/fabrik-review` on `specs/services/zitadel.yaml` — a BLOCKING gate, run to its coverage-adjudicated exit
   (every class CLEAN/FIXED/REFUTED). Dispatch policy: pool-default `fanout("review", …)` for breadth + native
   Opus on the security-sensitive env/secret block (masterkey length, no plaintext secret, SMTP creds).
7. Commit the phase (explicit path + provenance trailers).

**Phase A Behavior Contract:**
- **Given** the authored spec, **When** `python3 -c "from fabrik.spec_loader import load_spec; s=load_spec('specs/services/zitadel.yaml'); print(s.shape.needs_database, s.shape.is_public, s.shape.exposes_metrics, s.shape.has_persistent_data)"`, **Then** it loads without error and prints `True True True True` (spec_loader.py:205).
- **Given** the spec's shape, **When** `fabrik plan specs/services/zitadel.yaml` (read-only preview), **Then** the resolved registrars are exactly postgres + gatus + prometheus + backrest + grafana + glitchtip, and NOT authelia/redis/meilisearch (infrastructure.py:308-317).
- **Given** the spec `env`, **When** grepped, **Then** it contains no plaintext secret value — `ZITADEL_MASTERKEY`/`ZITADEL_ADMIN_PASSWORD` resolve via `secrets.generate` and `RESEND_API_KEY` via `from_env` (`grep -E ':\s*(sk-|resend_)' specs/services/zitadel.yaml` returns nothing; core/35).
- **Given** `watchdog`, **When** read, **Then** `enabled: false` is explicitly present (a missing block defaults ON — infrastructure.py `_register_watchdog`).

**Gate:** `python3 -c "from fabrik.spec_loader import load_spec; load_spec('specs/services/zitadel.yaml')"` exits 0 AND `fabrik plan specs/services/zitadel.yaml` prints the 6 expected registrars.

## Phase B — Author `docs/reference/zitadel.md` (the deploy reference + runbook)

**Deliverable:** the operator-facing reference doc that a deploy agent + the deploy triad read: what the spec
provisions, the grounded config explained, the post-deploy steps env can't do (custom **branding** + the login
UI **language switch (en/tr)** verification — both Console/Management-API, per grounding), the **RESILIENCE**
rows (OOM · DB-pool-exhaustion · upstream-timeout, per `core/self-healing.md`), and the **verification method
for each of the epic's 7 Success Criteria** (incl. the `docker inspect` env check for the scratch image, the
`/debug/ready` DB-dependent health probe, the OIDC discovery + `backchannel_logout_supported` check, and the
Resend delivery test).

**Steps:**
1. `ls docs/reference/zitadel.md` — confirm ABSENT (check-before-create; grounded ABSENT in Evidence).
2. Author `docs/reference/zitadel.md`: § Overview · § What `fabrik apply` provisions (the 6 registrars) · §
   Grounded config (the env block explained + cited Zitadel doc URLs) · § Deploy runbook (the triad + `docker
   inspect` env verification for the scratch image) · § Post-deploy Console steps (custom branding; confirm the
   login-UI en↔tr language switch renders — native i18n; SMTP is env-set so it needs only a delivery test) · §
   Health/metrics (`/debug/ready` DB-checked → Gatus; `/debug/metrics` → Prometheus) · § RESILIENCE rows (3
   failure classes) · § Success-Criteria verification table (all 7, each with its exact command/probe) · §
   Produces-for-Epic-2 (issuer URL, per-RP client-cred surface, Authorization-v2 grant API, `ZITADEL_ISSUER`).
3. **Behavior Contract** (below) — the doc documents every Success Criterion's verification method.
4. Run the phase gate → fix to green.
5. `python scripts/enforcement/check_doc_sync.py` + the doc-sync steps THIS phase owns: add the `INDEX.md` row
   (new file), the `docs/README.md` docs-index row, a `CHANGELOG.md` `### Added` entry, and the
   `docs/PROJECT_CATALOG.md` row for the new deployed service (fleet beat). No `PORTS.md` row (no host port —
   Traefik-routed). No `.env.example`/`CONFIGURATION.md` (the env lives in the spec + is registrar/secret-minted,
   not a hub env var).
6. `/fabrik-review` on `docs/reference/zitadel.md` — BLOCKING, to a coverage-adjudicated exit (verify each
   documented probe is real + each Success-Criterion verification is executable, not prose).
7. `python scripts/final_gate.py --check --json` (Tier-2, expect `"status":"success"`) **and**
   `python scripts/enforcement/check_convergence.py`. State plainly: a green gate proves format/citations, NOT
   that the design is sound — the real proof is the Evidence.
8. Commit the phase (explicit paths + trailers).

**Phase B Behavior Contract:**
- **Given** the reference doc, **When** grepped for each of the epic's 7 Success Criteria, **Then** each has a named, executable verification method (not prose) — e.g. the `/.well-known/openid-configuration` + `backchannel_logout_supported` check for #2, the `docker inspect` env check for #6 (scratch image, no `docker exec`).
- **Given** the doc, **When** read, **Then** it carries a RESILIENCE row for each of OOM · DB-pool-exhaustion · upstream-timeout (core/self-healing.md:14).
- **Given** `INDEX.md` after this phase, **When** grepped, **Then** it has a `docs/reference/zitadel.md` row (Doc Sync Matrix: file added → INDEX).

**Gate:** `python scripts/final_gate.py --check --json` → `"status":"success"` AND `python scripts/enforcement/check_convergence.py` passes.

## File Scope (owned paths)

- specs/services/zitadel.yaml
- docs/reference/zitadel.md

(The shared-append governance surfaces — `CHANGELOG.md`, `INDEX.md`, `docs/README.md`, `docs/FEATURES.md`,
`docs/LESSONS_LEARNT.md`, and `docs/PROJECT_CATALOG.md` — are updated per the Doc Sync Matrix but are OUTSIDE
the plan lock, per the shared-tree rules. This plan's scope is disjoint from the sibling
`2026-08-28-plan-1-provider-death-enforcement` set.)

## Evidence

**Phase A (the spec):**
- Read `specs/services/evolution-api.yaml:1-70` — the single-image `source.type:docker` template (shape,
  `depends.postgres`, `secrets.generate`, `expose`, `watchdog:false`, `backup`).
- Read `src/fabrik/spec_loader.py:205-380` — the `Shape` flags (`needs_database`, `is_public`,
  `exposes_metrics`, `has_persistent_data` all valid).
- Read `src/fabrik/orchestrator/infrastructure.py:521-578` — the postgres registrar honors `depends.postgres`
  and injects `DATABASE_URL`; `:308-317` — `exposes_metrics`+domain → prometheus.
- Grounded Zitadel v4 config (official docs, fetched 2026-08-28):
```
start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode external   (masterkey = 32 chars, stable)
ZITADEL_EXTERNALDOMAIN / ZITADEL_EXTERNALPORT=443 / ZITADEL_EXTERNALSECURE=true / ZITADEL_PORT=8080
ZITADEL_DATABASE_POSTGRES_DSN  OR decomposed HOST/PORT/DATABASE/USER_*/ADMIN_* (Admin==User for an existing DB)
ZITADEL_FIRSTINSTANCE_ORG_HUMAN_{USERNAME,EMAIL_ADDRESS,PASSWORD,PASSWORDCHANGEREQUIRED} / _DEFAULTLANGUAGE=en
ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_SMTP_{HOST,USER,PASSWORD} / _TLS / _FROM  (→ Resend, env at init)
metrics: /debug/metrics
```
  Sources: https://zitadel.com/docs/self-hosting/manage/configure/configure · https://zitadel.com/docs/self-hosting/manage/database ·
  https://zitadel.com/docs/self-hosting/manage/tls_modes · https://zitadel.com/docs/apis/observability/health ·
  raw v4.17.0 source `cmd/defaults.yaml` + `cmd/setup/steps.yaml` (github.com/zitadel/zitadel/tree/v4.17.0) — the
  `fabrik-researcher` read the raw tagged source and confirmed every key + the `ZITADEL_TLS_ENABLED=false`,
  `ADMIN_EXISTINGDATABASE`, `/debug/*` paths, and `tr`-shipped facts.

**Phase B (the doc):**
- `ls docs/reference/zitadel.md` → ABSENT (check-before-create):
```
$ ls docs/reference/zitadel.md 2>/dev/null || echo ABSENT
ABSENT
```
- Read `.windsurf/rules/core/self-healing.md:14-21` — the RESILIENCE-row-per-failure-class mandate for a `kind:service`.

## Self-audit

- **Grounding passes:** (1) spec template — read `evolution-api.yaml` in full; (2) Shape schema — read
  `spec_loader.py`; (3) registrar behavior — read `infrastructure.py`; (4) Zitadel v4 config — live-grounded via
  the official docs (context7 + WebFetch), a `fabrik-researcher` corroborating in parallel (fold its verdict at
  plan-review). (5) rule packs — `select_rules.py` (26 active; the 4 deploy-relevant read).
- **(a) Coverage of "what we agreed":** the epic's 2 in-scope items + 7 Success Criteria all map — #1/#3 → the
  spec's `/debug/ready` + Gatus (Phase A spec + Phase B verification); #2 → OIDC discovery (Phase B); #4 → Zitadel
  event store (Phase B doc — native); #5 → i18n en/tr (Phase B post-deploy verify — native); #6 → prometheus +
  glitchtip DSN inject + `docker inspect` (Phase A spec + Phase B); #7 → SMTP→Resend (Phase A env). Branding + the
  admin bootstrap are Phase A env (admin) + Phase B doc (branding, Console). No gap.
- **(b) Cross-phase signature consistency:** Phase A produces `specs/services/zitadel.yaml`; Phase B's
  verification table references the SAME env keys + endpoints Phase A sets (`/debug/ready`, `/debug/metrics`,
  `ZITADEL_ISSUER=https://auth.ocoron.com`). Consistent.
- Not a fixed point yet — `/fabrik-plan-review` converges it; the researcher's DB-Admin/User + health-path
  confirmation folds in there.

## Residual unknowns

**Resolved (grounded against the v4.17.0 source):** the spec template, Shape flags, registrar behavior; masterkey
32-char = fabrik's generated policy; the health/readiness/metrics paths (`/debug/ready` DB-checked, `/debug/healthz`
live, `/debug/metrics` Prometheus default-on via `ZITADEL_METRICS_TYPE: otel`); the DB model (registrar
pre-creates the DB → `ADMIN_EXISTINGDATABASE=zitadel`, Admin==User==the owning role, `sslmode=disable` internal);
`ZITADEL_TLS_ENABLED=false` behind Traefik; SMTP-via-env-at-first-init; `tr` shipped natively (Criterion #5).

**Still open (each with a resolution step, none silently deferred):**
1. **How the decomposed DB creds reach the container** — the registrar injects `DATABASE_URL` (a DSN); Zitadel
   needs the DECOMPOSED `ZITADEL_DATABASE_POSTGRES_USER_*`/`ADMIN_*` keys (scratch image can't split a DSN).
   **Resolution:** Phase A step 1 confirms whether the registrar can inject the decomposed keys or the spec must
   map them; if neither, the fallback `ZITADEL_DATABASE_POSTGRES_DSN=${DATABASE_URL}` (USER) + an ADMIN block is
   authored. This is a fabrik-registrar seam, resolved at plan-review with the registrar author (infra) if the
   decomposed injection isn't supported — a named seam, not a silent defer.
2. **glitchtip DSN inject for a `source.type:docker` service** — the epic wants it injected (Criterion #6) but a
   scratch image can't run the Sentry SDK. **Resolution:** `infra.glitchtip: true` requests the env; the
   deploy-verify phase confirms via `docker inspect` that `GLITCHTIP_DSN` is present (Criterion #6 is "injected +
   inspectable", not "sending events").
3. **Authelia-bypass path mismatch (non-issue, noted for the doc):** Zitadel's `/debug/*` paths don't match the
   fabrik bypass list (`/health`,`/healthz`,`/metrics`,`/api/health`) — but Zitadel is NOT behind Authelia (it IS
   the auth; no authelia registrar), so Gatus/Prometheus probe `/debug/ready` + `/debug/metrics` directly. The
   reference doc records this so a future reader doesn't wrongly add an Authelia bypass.
