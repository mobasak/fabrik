# Epic 1 — Zitadel Umbrella IdP Deployment (plan)

Status: EXECUTED

Stand up **Zitadel v4** as the umbrella OIDC IdP at `auth.ocoron.com`. **A re-review (native-Opus pass)
un-converged the original 2-file plan: the fabrik docker-compose emitter `_generate_docker_compose`
(deployer_ssh.py:880) DROPS `source.image_command` and ALWAYS emits a `wget --spider` healthcheck ignoring
`health.disabled` — so a hand-authored zitadel.yaml alone would deploy BROKEN (default command, and a
healthcheck the FROM-scratch image can't run).** Zitadel REQUIRES a custom `start-from-init` command and no
shell-based healthcheck, so this plan now has THREE phases: **Phase 0 enhances the emitter** (fleet deploy
machinery), then **Phase A authors `specs/services/zitadel.yaml`**, then **Phase B authors
`docs/reference/zitadel.md`**. The live `fabrik apply` deploy + Success-Criteria verification remain the
operator-gated **deploy triad** downstream. Source of truth: the epic
`docs/development/epics/2026-08-27-epic-1-zitadel-umbrella-idp.md` + the CONVERGED Infrastructure Decisions
spec. Produces the OIDC issuer + per-RP client-cred surface + Authorization-v2 grant API that Epic 2 consumes.
**Scope note:** Phase 0 touches `src/fabrik/orchestrator/deployer_ssh.py` (fleet deploy machinery), beyond the
epic's declared owned_paths — justified: it is the blocking prerequisite that makes ANY custom-command /
scratch-image docker deploy work, and it is squarely fleet's beat.

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
  image `ghcr.io/zitadel/zitadel:v4.17.1` (FROM scratch, amd64, 512 MiB min / **1 GiB recommended**); container
  command `start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode external` (`start-from-init` =
  init+setup+start one-shot); **masterkey EXACTLY 32 chars, stable-forever** (fabrik's 32-char `[a-zA-Z0-9]`
  `secrets.generate` satisfies it — never rotate: it decrypts stored data). **TLS behind Traefik:**
  `--tlsMode external` + `ZITADEL_EXTERNALSECURE=true` (advertise https) + **`ZITADEL_TLS_ENABLED=false`**
  (Zitadel serves plain HTTP internally; Traefik terminates TLS). Internal listen `ZITADEL_PORT=8080`,
  `ZITADEL_EXTERNALPORT=443`, `ZITADEL_EXTERNALDOMAIN=auth.ocoron.com`.
  **DB (GROUNDED against the registrar — infrastructure.py:588): the postgres registrar injects ONLY a single
  `DATABASE_URL` DSN, never decomposed `POSTGRES_*` keys.** So the spec sets exactly
  **`ZITADEL_DATABASE_POSTGRES_USER_SSL_MODE=disable`** + **`ZITADEL_DATABASE_POSTGRES_DSN: ${DATABASE_URL}`** —
  the DSN form is the correct one here because the registrar PRE-CREATES the `zitadel` DB owned by the DSN's role,
  so Zitadel `init` (DSN-only) SKIPS DB/user creation (it can't, and doesn't need to — the researcher confirmed
  DSN-only means "init does not create a separate DB/user") and creates only its SCHEMA as the owning role, which
  has DDL. No decomposed `ADMIN_*`/`USER_*` block is authored (the registrar gives one credential, one role, one
  DSN — a static scratch-image env cannot shell-split it). Init-succeeds-against-the-pre-created-DB is a
  deploy-verify assertion (the deploy triad runs `fabrik apply`), not this authoring plan's gate. **SMTP** env at first-init
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

## Phase 0 — Enhance `_generate_docker_compose` (the blocking deploy-machinery prerequisite)

**Deliverable:** teach the docker-source compose emitter to (1) emit `command:` from `source.image_command`
when set, and (2) OMIT the healthcheck block when `health.disabled: true` — the two gaps that make Zitadel
undeployable today. Grounded: `_generate_docker_compose` (deployer_ssh.py:880-944) references neither
`image_command` (dropped everywhere — grep-confirmed) nor `health.disabled` (the `wget --spider` healthcheck
at :911-916 is unconditional). This is fleet deploy machinery.

**Steps (test-first for the risky path):**
1. **Watched-fail-first:** add `tests/test_docker_compose_emitter.py` asserting (a) when `source.image_command`
   is set, the emitted compose contains a `command:` line with that value; (b) when `health.disabled: true`, the
   emitted compose contains NO `healthcheck:` block. Run → confirm BOTH FAIL red against the current emitter.
2. Enhance `_generate_docker_compose(name, image, port, domain, spec)`:
   - read `source = spec.get("source", {})`; if `source.get("image_command")`, append `f"    command: {image_command}"`
     to `lines` (Docker Compose interpolates `${VAR}` in `command:` from `env_file: .env` at `up` time, exactly
     as it does for env — so `${ZITADEL_MASTERKEY}` expands from the secrets-minted `.env`).
   - read `health = spec.get("health", {})`; if `health.get("disabled")`, SKIP emitting the `healthcheck:` block
     entirely (the service then reports `running` not `healthy` — `docker compose up --wait` waits on `running`,
     and Gatus does the external readiness probe). Preserve the existing wget healthcheck for the non-disabled case.
3. Behavior Contract (below).
4. Run the phase gate → fix to green (both tests now pass; existing emitter tests still green).
5. `python scripts/enforcement/check_doc_sync.py` — CHANGELOG entry for the emitter change.
6. `/fabrik-review` on `deployer_ssh.py` + the test — BLOCKING, to a coverage-adjudicated exit. Dispatch:
   pool-default `fanout("review")` breadth + native Opus on the emitter change (deploy machinery is high-risk).
7. Commit (explicit paths + trailers).

**Phase 0 Behavior Contract:**
- **Given** a spec with `source.image_command: "start-from-init --masterkey X --tlsMode external"`, **When** `_generate_docker_compose(...)` runs, **Then** the emitted compose contains a `command:` line carrying that string (deployer_ssh.py:880).
- **Given** a spec with `health: { disabled: true }`, **When** the emitter runs, **Then** the output contains no `healthcheck:` key (deployer_ssh.py:911).
- **Given** a spec with NEITHER, **When** the emitter runs, **Then** output is unchanged (the existing wget healthcheck + no command — no regression for evolution-api-style specs).

**Gate:** `python -m pytest tests/test_docker_compose_emitter.py -q` → all pass; `python scripts/final_gate.py --check --json` → success.

## Phase A — Author `specs/services/zitadel.yaml` (the deploy spec)

**Deliverable:** a hand-authored single-image (`source.type: docker`) service spec whose `shape:` matches the
epic exactly and whose `env:` carries the grounded Zitadel v4 config, so `fabrik apply` provisions the 6
registrars and deploys a Zitadel that self-inits its schema, bootstraps an admin, and wires SMTP→Resend.

**Steps:**
1. **DB config is DSN-only** (GROUNDED — `infrastructure.py:588` injects ONLY `DATABASE_URL`, never decomposed
   keys; verify by reading it): set `ZITADEL_DATABASE_POSTGRES_DSN: ${DATABASE_URL}` +
   `ZITADEL_DATABASE_POSTGRES_USER_SSL_MODE: disable`. Do NOT author decomposed `ADMIN_*`/`USER_*` keys — the
   registrar provides one credential/role/DSN, and a static scratch-image env cannot split it. The registrar
   pre-creates the `zitadel` DB owned by that role, so Zitadel `init` (DSN-only) creates only the schema (it has
   DDL); DSN-only init does NOT attempt DB/user creation (grounded via the researcher's source read). That init
   actually succeeds is a **deploy-verify** assertion, downstream of this authoring plan.
2. Author `specs/services/zitadel.yaml` mirroring `evolution-api.yaml`'s shape, with:
   - `id: zitadel` · `kind: service` · `domain: auth.ocoron.com`
   - `shape:` `kind: service`, `is_public: true`, `is_admin_dashboard: false`, `has_bearer_api: false`,
     `has_persistent_data: true`, `needs_database: true`, `has_search_feature: false`, `needs_cache: false`,
     `exposes_metrics: true`
   - `expose: { http: true }` (public — NOT `internal_only`)
   - `source: { type: docker, image: ghcr.io/zitadel/zitadel:v4.17.1, image_port: 8080,
     image_command: 'start-from-init --masterkey "${ZITADEL_MASTERKEY}" --tlsMode external' }` — **`image_command`
     is the real spec_loader field (Source model, spec_loader.py:114); a top-level `command:` is dropped.** Now
     emitted by Phase 0.
   - `depends: { postgres: zitadel }`
   - `env:` the grounded ZITADEL_* block (externaldomain/port/secure, **`ZITADEL_TLS_ENABLED: "false"`**,
     PORT=8080, **`ZITADEL_DATABASE_POSTGRES_DSN: ${DATABASE_URL}`** + `ZITADEL_DATABASE_POSTGRES_USER_SSL_MODE: disable`,
     `ZITADEL_FIRSTINSTANCE_ORG_NAME`/`_ORG_HUMAN_USERNAME`/`_ORG_HUMAN_EMAIL_ADDRESS`/`_ORG_HUMAN_PASSWORD=${ZITADEL_ADMIN_PASSWORD}`/`_ORG_HUMAN_PASSWORDCHANGEREQUIRED=true`/`_DEFAULTLANGUAGE=en`,
     the `ZITADEL_DEFAULTINSTANCE_SMTPCONFIGURATION_SMTP_HOST=smtp.resend.com:465`/`_SMTP_USER=resend`/`_SMTP_PASSWORD=${RESEND_API_KEY}`/`_TLS=true`/`_FROM`/`_FROMNAME` block)
   - `secrets: { required: [], generate: [ZITADEL_MASTERKEY, ZITADEL_ADMIN_PASSWORD], from_env: [RESEND_API_KEY], from_file: {} }`
   - `resources: { memory: 1G, cpu: '0.5' }` · `health: { disabled: true }` (scratch image has no curl for a
     compose HEALTHCHECK — Gatus does the external HTTP probe on `/debug/ready`) · `volumes: []` ·
     `companion_services: []` · `backup: { enabled: true, frequency: daily, retention: 30 }` ·
     `watchdog: { enabled: false }`. **Do NOT set `infra: { glitchtip: true }`** — `infra:` is
     negative-override-ONLY (there is no `true` opt-in; infrastructure.py:5-7). glitchtip already fires by DEFAULT
     for `kind: service` and injects `GLITCHTIP_DSN`; `verify_dsn_injection` (glitchtip.py:417) then checks the
     env is PRESENT via `docker inspect` (env-presence, not event-delivery) — which the scratch image satisfies
     (the DSN is injected as env, unused by Zitadel), so the fatal-registrar rollback does NOT trigger, and this
     IS epic Criterion #6's "DSN injected, verified via docker inspect". Omit the `infra:` block entirely.
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
- **Given** the authored spec, **When** the REAL docker emitter renders it — `python3 -c "import yaml; from fabrik.orchestrator.deployer_ssh import _generate_docker_compose; s=yaml.safe_load(open('specs/services/zitadel.yaml')); print(_generate_docker_compose('zitadel', s['source']['image'], s['source']['image_port'], s['domain'], s))"` — **Then** the output CONTAINS a `command:` line carrying `start-from-init … --tlsMode external` AND contains NO `healthcheck:` block. **This is the load-bearing gate the original plan lacked: `fabrik plan` renders the TEMPLATE path, NOT `_generate_docker_compose`, so it is blind to a dropped command / forced healthcheck (native-Opus finding #3). This assertion exercises the real emitter Phase 0 fixed.**
- **Given** the spec `env`, **When** grepped, **Then** it contains no plaintext secret value — `ZITADEL_MASTERKEY`/`ZITADEL_ADMIN_PASSWORD` resolve via `secrets.generate` and `RESEND_API_KEY` via `from_env` (`grep -E ':\s*(sk-|resend_)' specs/services/zitadel.yaml` returns nothing; core/35).
- **Given** `watchdog`, **When** read, **Then** `enabled: false` is explicitly present (a missing block defaults ON — infrastructure.py `_register_watchdog`).

**Gate:** `python3 -c "from fabrik.spec_loader import load_spec; load_spec('specs/services/zitadel.yaml')"` exits 0 AND `fabrik plan specs/services/zitadel.yaml` prints the 6 expected registrars AND the real-emitter render (the Behavior-Contract command above) shows `command:` present + no `healthcheck:` — the last is the load-bearing assertion `fabrik plan` cannot make.

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

- src/fabrik/orchestrator/deployer_ssh.py
- tests/test_docker_compose_emitter.py
- specs/services/zitadel.yaml
- docs/reference/zitadel.md

(The shared-append governance surfaces — `CHANGELOG.md`, `INDEX.md`, `docs/README.md`, `docs/FEATURES.md`,
`docs/LESSONS_LEARNT.md`, and `docs/PROJECT_CATALOG.md` — are updated per the Doc Sync Matrix but are OUTSIDE
the plan lock, per the shared-tree rules. This plan's scope is disjoint from the sibling
`2026-08-28-plan-1-provider-death-enforcement` set.)

## Coverage Checklist

Armed by `review_rubric.py --changed specs/services/zitadel.yaml docs/reference/zitadel.md` (FLOOR:
core/35-security-auth + core/30-ops; MATCHED: deploy/ops packs on the `specs/services/*.yaml` glob):

```
$ python scripts/review_rubric.py --changed specs/services/zitadel.yaml docs/reference/zitadel.md
# REVIEW RUBRIC — FLOOR: core/35-security-auth (no hardcoded secret; config = env vars only) ·
#   core/30-ops (no host ports; container_name mandatory; memory limit; Authelia health-bypass) ·
#   MATCHED: core/55-observability + core/58-resilience (specs/services + docs/reference globs)
# + standing recurrence: fail-open/closed · cost/quota edges · boundary/prefix · behavior-without-a-test
```

| # | Class | Verdict |
|---|---|---|
| 1 | core/35 — no plaintext secret in the spec (config = env only) | CLEAN — `ZITADEL_MASTERKEY`/`ZITADEL_ADMIN_PASSWORD` via `secrets.generate`, `RESEND_API_KEY` via `from_env`; Phase-A Behavior Contract greps for a plaintext secret and asserts none. |
| 2 | core/30-ops — deploy invariants (no host ports, `container_name`, memory limit, Traefik) | CLEAN — Global Constraints + Phase A spec: `source.type:docker`, no `ports:`, `container_name` = the id `zitadel`, `resources.memory: 1G`, Traefik-routed on the domain. |
| 3 | core/55 — health/metrics/GlitchTip | CLEAN — `/debug/ready` (DB-checked) → Gatus, `/debug/metrics` (default-on) → Prometheus, `GLITCHTIP_DSN` injected + `verify_dsn_injection` (docker inspect) — all grounded (infrastructure.py:17,308,827). |
| 4 | core/58 — resilience rows | CLEAN — Phase B step 2 authors a `docs/RESILIENCE.md`-style row per failure class (OOM · DB-pool · upstream-timeout) per core/self-healing.md:14. |
| 5 | fail-open vs fail-closed (the health guard) | CLEAN — `/debug/ready` returns non-200 when `postgres-main` is unreachable (Criterion #3, fail-CLOSED on a dead DB — the correct direction); grounded as DB-checked readiness. |
| 6 | cost/quota/limit accounting | CLEAN — N/A: no paid LLM / metered API (Zitadel self-host + Resend free tier; Infra Decisions § Cost Guardrails = N/A). |
| 7 | boundary/sentinel/prefix collisions | REFUTED — the one candidate (Zitadel's `/debug/*` paths vs the fabrik Authelia-bypass list) is a non-issue: Zitadel is NOT behind Authelia (it IS the auth; no authelia registrar), so Gatus/Prometheus hit `/debug/*` directly; recorded in the doc so nobody wrongly adds a bypass. |
| 8 | behavior-without-a-test | CLEAN — both phases carry a Behavior Contract (Phase A: spec loads + registrar footprint + no-plaintext-secret + watchdog-off; Phase B: each of the 7 Success Criteria has an executable verification + the RESILIENCE rows). |
| 9 | plan↔reality drift (the DB-injection seam) | FIXED — Pass 1 grounded that the registrar injects ONLY `DATABASE_URL` (infrastructure.py:588); the plan now uses `ZITADEL_DATABASE_POSTGRES_DSN=${DATABASE_URL}` (DSN-only), not the decomposed keys it originally assumed. |
| 10 | 12-Factor XII — migrations not from startup | CLEAN — Zitadel's `start-from-init` is a one-shot init+setup+start (the documented single-container command), not an app-`lifespan` migration; no Alembic-race pattern. |
| 11 | deploy-machinery gap — the docker emitter drops the custom command + forces a shell healthcheck | FIXED(2) — the native-Opus re-review grounded that `_generate_docker_compose` (deployer_ssh.py:880) emits neither `command:` (image_command dropped, grep-confirmed) nor honors `health.disabled` (unconditional `wget --spider` at :911). Phase 0 fixes both with red-first tests; without it the spec deploys broken. This is why the original CONVERGED was wrong. |
| 12 | gate-blindness — the authoring gates never render the real compose | FIXED — native-Opus #3: `fabrik plan` renders the TEMPLATE path, not `_generate_docker_compose`, so a broken compose passes every gate green. Phase A's Behavior Contract + Gate now render the REAL emitter and assert `command:` present + no `healthcheck:`. |
| 13 | glitchtip fatal-registrar + `infra:` opt-in that doesn't exist | FIXED/REFUTED — native-Opus #5: `infra:{glitchtip:true}` is a no-op (`infra:` is negative-override-only) — REMOVED it. The rollback risk is REFUTED: `verify_dsn_injection` (glitchtip.py:417) checks env-PRESENCE via `docker inspect` (which the injected DSN satisfies), not event delivery — no rollback; glitchtip fires by the `kind:service` default and meets Criterion #6. |
| 14 | placeholder image tag | FIXED — native-Opus #7: `:v4.x` is not a pullable tag → `:v4.17.1` (real tag; digest pinned at deploy). |

## Evidence

**Phase 0 (the emitter — the re-review's finding):**
- Read `src/fabrik/orchestrator/deployer_ssh.py:880-944` — `_generate_docker_compose` emits image /
  container_name / env_file / deploy.resources / **an unconditional `wget --spider` healthcheck (:911-916)** /
  networks / traefik labels — but NO `command:`, and no `health.disabled` check:
```
$ grep -rnE 'image_command' src/fabrik/ | grep -v spec_loader
$   # (empty — image_command is dropped by every compose path)
$ grep -nE 'health.*disabled' src/fabrik/orchestrator/deployer_ssh.py
$   # (empty — the healthcheck is unconditional)
```
- `specs/services/evolution-api.yaml` has NO `image_command` (grep count 0) and a Node image WITH wget — which
  is exactly why mirroring it hid both gaps at the first convergence.
- `spec_loader.py:114` — `image_command` is a real `Source` field (so the spec parses); the emitter simply
  ignores it. `spec_loader.py:105` confirms it lives under `source:`.

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
  the `/debug/*` health/metrics paths, and the `tr`-shipped facts. (The plan uses the DSN-only DB form —
  `ZITADEL_DATABASE_POSTGRES_DSN=${DATABASE_URL}` — because the registrar injects only that DSN; the decomposed
  `ADMIN_*`/`USER_*` keys the researcher also documented are NOT used here.)

- **Masterkey length match (grounded):** `src/fabrik/orchestrator/secrets.py:12-22` — `generate_secret(length=32)`
  emits EXACTLY 32 `[a-zA-Z0-9]` chars = Zitadel's hard "masterkey must be 32 chars" requirement. So
  `secrets.generate: [ZITADEL_MASTERKEY]` is correct with no length override.
- **Deploy prerequisite (grounded present):** `RESEND_API_KEY` IS in the hub `.env`, so the spec's
  `secrets.from_env: [RESEND_API_KEY]` resolves at `fabrik apply`. Named here so the deploy triad does not hit a
  missing-key failure. (Not an authoring blocker — the spec declares the dependency; the value already exists.)

**Phase B (the doc):**
- `ls docs/reference/zitadel.md` → ABSENT (check-before-create):
```
$ ls docs/reference/zitadel.md 2>/dev/null || echo ABSENT
ABSENT
```
- Read `.windsurf/rules/core/self-healing.md:14-21` — the RESILIENCE-row-per-failure-class mandate for a `kind:service`.

## Self-audit

- **Grounding passes:** (1) spec template — read `evolution-api.yaml` in full; (2) Shape schema — read
  `spec_loader.py` (incl. `source.image_command:114`); (3) registrar behavior — read `infrastructure.py`
  (`DATABASE_URL`-only injection :588, glitchtip fatal-registrar); (4) Zitadel v4 config — live-grounded via the
  official v4.17.0 source (context7 + WebFetch + a `fabrik-researcher`); (5) rule packs — `select_rules.py`;
  **(6) the DEPLOY EMITTER — a native-Opus re-review that EXECUTED `_generate_docker_compose` + docker compose
  2.40.3 and proved the dropped-command / forced-healthcheck defects that un-converged the first pass (Phase 0
  now fixes them), refuted the `${VAR}`-literal fear (interpolation works), and caught the glitchtip-no-op +
  placeholder-tag.** The re-review is why this plan grew a Phase 0 and a real-emitter gate — the first CONVERGED
  was wrong because it mirrored evolution-api, which never exercises `image_command` or a shell-less image.
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

**Resolved (grounded against the v4.17.0 source + the fabrik registrar):** the spec template, Shape flags,
registrar behavior; masterkey 32-char = fabrik's generated policy; health/readiness/metrics paths (`/debug/ready`
DB-checked, `/debug/healthz` live, `/debug/metrics` Prometheus default-on via `ZITADEL_METRICS_TYPE: otel`);
`ZITADEL_TLS_ENABLED=false` behind Traefik; SMTP-via-env-at-first-init; `tr` shipped natively (Criterion #5).
**The DB seam is RESOLVED (grounded infrastructure.py:588):** the registrar injects ONLY `DATABASE_URL`, so the
spec uses `ZITADEL_DATABASE_POSTGRES_DSN=${DATABASE_URL}` (DSN-only) — the registrar pre-creates the DB, so init
creates only the schema as the owning role; DSN-only init does not attempt DB/user creation. **glitchtip is
RESOLVED (grounded infrastructure.py:17,827):** the registrar fires for `shape.kind in {service,worker,wordpress}`
and injects `GLITCHTIP_DSN` + verifies via `verify_dsn_injection` (docker inspect) — exactly Criterion #6 (the DSN
is present-but-unused; the scratch image runs no SDK).

**Still open (each with a resolution step, none silently deferred) — all are DEPLOY-VERIFY assertions, downstream
of this authoring plan, not execution-blockers for the authoring/emitter phases:**
1. **Zitadel `init` succeeds against the registrar's pre-created DB with DSN-only config** — grounded as correct
   (owning role has DDL; DSN-only skips DB/user creation) but PROVEN only at deploy. **Resolution:** the
   deploy-verify phase asserts the container reaches healthy + `/debug/ready` returns 200; if init fails for want
   of an Admin block, the contingency is a one-time manual schema-init or a registrar note to infra — a
   deploy-triad contingency, not an authoring blocker.
2. **Authelia-bypass path mismatch (non-issue, recorded in the doc):** Zitadel's `/debug/*` paths don't match the
   fabrik bypass list (`/health`,`/healthz`,`/metrics`,`/api/health`) — but Zitadel is NOT behind Authelia (it IS
   the auth; no authelia registrar), so Gatus/Prometheus probe `/debug/ready` + `/debug/metrics` directly. The
   reference doc records this so a future reader doesn't wrongly add an Authelia bypass.
3. **First-deploy DSN ordering (native-Opus #8, deploy-verify):** on the FIRST `fabrik apply`, `.env` is written
   before the postgres registrar injects `DATABASE_URL`, so `${DATABASE_URL}` interpolates empty for the initial
   `compose up`; the registrar injects post-deploy + restarts. evolution-api (the live template) shares this exact
   pattern and tolerates it via the orchestration order — and Phase 0's `health.disabled` fix removes the
   healthcheck that would otherwise make the first `--wait` fail before injection. The deploy-verify phase asserts
   Zitadel reaches `/debug/ready` 200 after the registrar's inject+restart; if the ordering bites, the contingency
   is a second `fabrik apply` (env-sync), the documented pattern. A deploy-triad item, not an authoring blocker.
