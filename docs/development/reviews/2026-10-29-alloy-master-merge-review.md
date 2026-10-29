# Review — alloy-master-merge

**Status:** CONVERGED
**Surface:** `git rev-parse HEAD` = 0a1bb593f724408ef49e4d4f872d5398528c8b7f; range tip 0a1bb593f724408ef49e4d4f872d5398528c8b7f; `git diff 9f3061b8f..0a1bb593f -- .fabrik/plan-locks/2026-10-08-plan-1-promtail-to-alloy.json .fabrik/work/W-0913992c.json .fabrik/work/W-ede94e4e.json CHANGELOG.md INDEX.md PORTS.md README.md configs/alloy/config.alloy configs/gatus/README.md configs/gatus/apps/observability-agents.yaml configs/prometheus/prometheus.yml docs/DEPLOYMENT_ARCHITECTURE.md docs/LESSONS_LEARNT.md docs/README.md docs/SERVICES.md docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/2026-10-08-plan-1-promtail-to-alloy.md docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/T02-hub-compose-and-ceilings.md docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T01-review.md docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T02-review.md docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T05a-review.md docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md docs/infrastructure/alloy-noise-filter-setup.md docs/infrastructure/audit-prompts/01-full-system-audit.md docs/infrastructure/audit-prompts/02-container-health.md docs/infrastructure/audit-prompts/03-security-hardening.md docs/infrastructure/audit-prompts/04-performance-bottleneck.md docs/infrastructure/audit-prompts/05-observability-pipeline.md docs/infrastructure/audit-prompts/07-pre-production-checklist.md docs/infrastructure/audit-prompts/08-hardening-remediation.md docs/infrastructure/audit-prompts/README.md docs/infrastructure/glitchtip-sdk-integration-setup.md docs/infrastructure/grafana-dashboards-setup.md docs/infrastructure/grafana-provisioning-setup.md docs/infrastructure/prometheus-app-metrics-setup.md docs/infrastructure/promtail-noise-filter-setup.md docs/infrastructure/vps-ai-sysadmin.md docs/infrastructure/vps-bootstrap-plan.md docs/infrastructure/vps-complete-inventory.md docs/infrastructure/vps-fleet-architecture.md docs/infrastructure/vps-hub-rebuild.md docs/infrastructure/vps-spoke-rebuild.md docs/infrastructure/vps-status.md docs/infrastructure/vps-urls.md docs/operations/disaster-recovery.md docs/operations/hub-restore-inventory.md docs/operations/promtail-to-alloy-runbook.md docs/operations/spoke-restore-inventory.md docs/reference/apis/EXTERNAL_SYSTEMS.md docs/reference/architecture.md docs/reference/health-monitoring.md docs/reference/vps1-postgres-admin-rotation-runbook.md docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md docs/workflows/development-and-deployment-workflow.md infra/README.md infra/vps1/monitoring/compose.yaml infra/vps2/monitoring-agent/compose.yaml infra/vps3/monitoring-agent/compose.yaml scripts/audit/05-observability.sh scripts/audit/06-backup.sh scripts/bootstrap/README.md scripts/bootstrap/bootstrap-config.sh scripts/bootstrap/bootstrap-hub.sh scripts/bootstrap/bootstrap-spoke-restore.sh scripts/bootstrap/bootstrap-vps.sh scripts/bootstrap/templates/alloy.alloy.template scripts/bootstrap/templates/monitoring-agent.compose.yaml.template scripts/generate_vps_inventory.py scripts/sysadmin/proactive-check.sh scripts/sysadmin/system-prompt.txt scripts/sysadmin/vps1_ocoron_removal.py scripts/vps_apply_limits.sh scripts/vps_sync.py templates/file-worker/compose.yaml.j2 templates/scaffold/docs/RESILIENCE_TEMPLATE.md tests/test_alloy_configs.py tests/test_alloy_consumers.py tests/test_alloy_runbook.py tests/test_alloy_watchers.py tests/test_monitoring_agent_template.py tests/test_vps_apply_limits.py` md5 263e6482e0714ec5e71e77df813fae8e (649755 bytes)
**Command:** /fabrik-review · **Changed:** `.fabrik/plan-locks/2026-10-08-plan-1-promtail-to-alloy.json`, `.fabrik/work/W-0913992c.json`, `.fabrik/work/W-ede94e4e.json`, `CHANGELOG.md`, `INDEX.md`, `PORTS.md`, `README.md`, `configs/alloy/config.alloy`, `configs/gatus/README.md`, `configs/gatus/apps/observability-agents.yaml`, `configs/prometheus/prometheus.yml`, `docs/DEPLOYMENT_ARCHITECTURE.md`, `docs/LESSONS_LEARNT.md`, `docs/README.md`, `docs/SERVICES.md`, `docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/2026-10-08-plan-1-promtail-to-alloy.md`, `docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/T02-hub-compose-and-ceilings.md`, `docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T01-review.md`, `docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T02-review.md`, `docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T05a-review.md`, `docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md`, `docs/infrastructure/alloy-noise-filter-setup.md`, `docs/infrastructure/audit-prompts/01-full-system-audit.md`, `docs/infrastructure/audit-prompts/02-container-health.md`, `docs/infrastructure/audit-prompts/03-security-hardening.md`, `docs/infrastructure/audit-prompts/04-performance-bottleneck.md`, `docs/infrastructure/audit-prompts/05-observability-pipeline.md`, `docs/infrastructure/audit-prompts/07-pre-production-checklist.md`, `docs/infrastructure/audit-prompts/08-hardening-remediation.md`, `docs/infrastructure/audit-prompts/README.md`, `docs/infrastructure/glitchtip-sdk-integration-setup.md`, `docs/infrastructure/grafana-dashboards-setup.md`, `docs/infrastructure/grafana-provisioning-setup.md`, `docs/infrastructure/prometheus-app-metrics-setup.md`, `docs/infrastructure/promtail-noise-filter-setup.md`, `docs/infrastructure/vps-ai-sysadmin.md`, `docs/infrastructure/vps-bootstrap-plan.md`, `docs/infrastructure/vps-complete-inventory.md`, `docs/infrastructure/vps-fleet-architecture.md`, `docs/infrastructure/vps-hub-rebuild.md`, `docs/infrastructure/vps-spoke-rebuild.md`, `docs/infrastructure/vps-status.md`, `docs/infrastructure/vps-urls.md`, `docs/operations/disaster-recovery.md`, `docs/operations/hub-restore-inventory.md`, `docs/operations/promtail-to-alloy-runbook.md`, `docs/operations/spoke-restore-inventory.md`, `docs/reference/apis/EXTERNAL_SYSTEMS.md`, `docs/reference/architecture.md`, `docs/reference/health-monitoring.md`, `docs/reference/vps1-postgres-admin-rotation-runbook.md`, `docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md`, `docs/workflows/development-and-deployment-workflow.md`, `infra/README.md`, `infra/vps1/monitoring/compose.yaml`, `infra/vps2/monitoring-agent/compose.yaml`, `infra/vps3/monitoring-agent/compose.yaml`, `scripts/audit/05-observability.sh`, `scripts/audit/06-backup.sh`, `scripts/bootstrap/README.md`, `scripts/bootstrap/bootstrap-config.sh`, `scripts/bootstrap/bootstrap-hub.sh`, `scripts/bootstrap/bootstrap-spoke-restore.sh`, `scripts/bootstrap/bootstrap-vps.sh`, `scripts/bootstrap/templates/alloy.alloy.template`, `scripts/bootstrap/templates/monitoring-agent.compose.yaml.template`, `scripts/generate_vps_inventory.py`, `scripts/sysadmin/proactive-check.sh`, `scripts/sysadmin/system-prompt.txt`, `scripts/sysadmin/vps1_ocoron_removal.py`, `scripts/vps_apply_limits.sh`, `scripts/vps_sync.py`, `templates/file-worker/compose.yaml.j2`, `templates/scaffold/docs/RESILIENCE_TEMPLATE.md`, `tests/test_alloy_configs.py`, `tests/test_alloy_consumers.py`, `tests/test_alloy_runbook.py`, `tests/test_alloy_watchers.py`, `tests/test_monitoring_agent_template.py`, `tests/test_vps_apply_limits.py`
**Lane:** fabrik-task

## Coverage Checklist

Rubric invocation (verbatim output — the gate reads the generated header, never a prose mention):

```text
$ python scripts/review_rubric.py --changed .fabrik/plan-locks/2026-10-08-plan-1-promtail-to-alloy.json .fabrik/work/W-0913992c.json .fabrik/work/W-ede94e4e.json CHANGELOG.md INDEX.md PORTS.md README.md configs/alloy/config.alloy configs/gatus/README.md configs/gatus/apps/observability-agents.yaml configs/prometheus/prometheus.yml docs/DEPLOYMENT_ARCHITECTURE.md docs/LESSONS_LEARNT.md docs/README.md docs/SERVICES.md docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/2026-10-08-plan-1-promtail-to-alloy.md docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/T02-hub-compose-and-ceilings.md docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T01-review.md docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T02-review.md docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T05a-review.md docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md docs/infrastructure/alloy-noise-filter-setup.md docs/infrastructure/audit-prompts/01-full-system-audit.md docs/infrastructure/audit-prompts/02-container-health.md docs/infrastructure/audit-prompts/03-security-hardening.md docs/infrastructure/audit-prompts/04-performance-bottleneck.md docs/infrastructure/audit-prompts/05-observability-pipeline.md docs/infrastructure/audit-prompts/07-pre-production-checklist.md docs/infrastructure/audit-prompts/08-hardening-remediation.md docs/infrastructure/audit-prompts/README.md docs/infrastructure/glitchtip-sdk-integration-setup.md docs/infrastructure/grafana-dashboards-setup.md docs/infrastructure/grafana-provisioning-setup.md docs/infrastructure/prometheus-app-metrics-setup.md docs/infrastructure/promtail-noise-filter-setup.md docs/infrastructure/vps-ai-sysadmin.md docs/infrastructure/vps-bootstrap-plan.md docs/infrastructure/vps-complete-inventory.md docs/infrastructure/vps-fleet-architecture.md docs/infrastructure/vps-hub-rebuild.md docs/infrastructure/vps-spoke-rebuild.md docs/infrastructure/vps-status.md docs/infrastructure/vps-urls.md docs/operations/disaster-recovery.md docs/operations/hub-restore-inventory.md docs/operations/promtail-to-alloy-runbook.md docs/operations/spoke-restore-inventory.md docs/reference/apis/EXTERNAL_SYSTEMS.md docs/reference/architecture.md docs/reference/health-monitoring.md docs/reference/vps1-postgres-admin-rotation-runbook.md docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md docs/workflows/development-and-deployment-workflow.md infra/README.md infra/vps1/monitoring/compose.yaml infra/vps2/monitoring-agent/compose.yaml infra/vps3/monitoring-agent/compose.yaml scripts/audit/05-observability.sh scripts/audit/06-backup.sh scripts/bootstrap/README.md scripts/bootstrap/bootstrap-config.sh scripts/bootstrap/bootstrap-hub.sh scripts/bootstrap/bootstrap-spoke-restore.sh scripts/bootstrap/bootstrap-vps.sh scripts/bootstrap/templates/alloy.alloy.template scripts/bootstrap/templates/monitoring-agent.compose.yaml.template scripts/generate_vps_inventory.py scripts/sysadmin/proactive-check.sh scripts/sysadmin/system-prompt.txt scripts/sysadmin/vps1_ocoron_removal.py scripts/vps_apply_limits.sh scripts/vps_sync.py templates/file-worker/compose.yaml.j2 templates/scaffold/docs/RESILIENCE_TEMPLATE.md tests/test_alloy_configs.py tests/test_alloy_consumers.py tests/test_alloy_runbook.py tests/test_alloy_watchers.py tests/test_monitoring_agent_template.py tests/test_vps_apply_limits.py
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: a default turns one bad/empty JWT into a cross-tenant read, and a raise turns a deny into a 500. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- `POST /auth/passwordless/request` is ALREADY capped per email and per IP in Redis by the library (`AUTH_PASSWORDLESS_REQUEST_CAP`, `AUTH_PASSWORDLESS_IP_REQUEST_CAP`): tune those, add no second limiter, and never answer it with 429 — it returns 202 either way, so throttling never reveals an account. `POST /auth/passwordless/verify` has a per-code attempt cap (`AUTH_PASSWORDLESS_ATTEMPT_CAP`) but no per-IP bound; the project adds that bucket.
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- A dedicated admin host on its own domain — never the customer-facing app's domain — behind 2FA: set `shape.is_admin_dashboard: true` there. The Authelia registrar adds a per-domain `two_factor` rule on `fabrik apply`, so every path on that domain sits behind 2FA except the standing `/health` and `/metrics` bypasses (D-366, `saas/60-saas-ui.md` § Admin). API services with bearer auth: set `shape.has_bearer_api: true` — the registrar inserts an Authelia **bypass** rule *before* the `two_factor` catch-all so machine/bearer callers aren't hit with interactive 2FA. Don't add Traefik `authelia-forward` middlewares manually — the scaffolder + registrars emit them.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: the plain upstream PostgreSQL Alpine image, `plpgsql` only — `CLAIMS.yaml` row `fleet-postgres-main-no-pgvector`); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- remove it` on the hub) names a plan that protects nothing. Never add a service-named plan.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (probed 2026-09-01: the plain upstream PostgreSQL Alpine image at the fleet major recorded in `CLAIMS.yaml` row `pg-fleet-major` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- `docker compose run --rm <svc> alembic upgrade head` (against deployed environment) — `<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/10-python.md  (hit: scripts/generate_vps_inventory.py, scripts/sysadmin/vps1_ocoron_removal.py, scripts/vps_sync.py)
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Type the package, never `.`: the root walks the hub-synced `scripts/`, where mypy finds the same file under two module names and stops on every fresh project. file-worker types `mypy --explicit-package-bases worker`; a `server/` backend (saas-skeleton, static-site, office-extension, chrome-extension, mobile-app) runs `mypy src` from `server/` (D-605).
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (`<svc>` is a service that declares `.env.owner` (a `migrate` service), never the app service — the owner DSN is not in the app service's environment after the owner split (D-754), and `run` replaces the service's `command`, so a hand-off written there is bypassed) (see `30-ops.md` § Release & Admin Processes).
| `alembic upgrade head` in `lifespan` / startup hook | One-off admin process against the deployed release: `docker compose run --rm <svc> alembic upgrade head`, `<svc>` a service that declares `.env.owner` (a `migrate` service), never the app service (D-754) (concurrent replicas race the version table) |

### core/40-documentation.md  (hit: CHANGELOG.md, INDEX.md, PORTS.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
| `Agent-Role` | `primary` · `orchestrator` · `subagent` · `review-fix` · `ci-fix` | every AI commit (`ci-fix` ONLY when one of the hub's two unattended writers made the commit — the CI-fix dispatcher's `claude -p` run in THIS repo after a GitHub Actions failure, or the hub's own rules-version cron; any other session never writes it) |
| `Agent-Name` | the name the operator gave your window — your `CLAUDE.md` § Agent Provenance Trailers owns the rule (in a project: write it by hand; never invent one) | every AI commit |
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_alloy_configs.py, tests/test_alloy_consumers.py, tests/test_alloy_runbook.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A subagent seat runs no package-manager verb and runs `.venv/bin/python -m pytest` instead (`10-python.md` § Package Manager). A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests pass the throwaway guard before connecting — `require_throwaway(TEST_DATABASE_URL)` where the scaffold emitted `tests/conftest.py`; where it did not (an unscaffolded repo has no such helper), this anchored predicate, verbatim: `dbname = urlparse(url).path.lstrip('/'); assert dbname.lower().endswith(('_test', 'throwaway', 'scratch')), dbname` — never point them at a dev/shared DB.

### core/55-observability.md  (hit: docs/infrastructure/glitchtip-sdk-integration-setup.md, docs/reference/health-monitoring.md, infra/vps1/monitoring/compose.yaml)
- ⚠️ **The shipper is Promtail today and Promtail reached END OF LIFE (2026-03-02)** — no updates, no support. Grafana Alloy is the successor (`alloy convert` migrates the config). Fleet migration is an infra action, not a per-project one; until it lands, nothing about the rules below changes.
- **The label set is the PIPELINE's, not yours** — live: `container_name`, `filename`, `host`, `job`, `service_name`, `stream`. An app cannot add labels by logging a field; a JSON field is queried with `| json`, never as a label.
- > *"A twelve-factor app never concerns itself with routing or storage of its output stream. It should not attempt to write to or manage logfiles."*
**Mandate.** The app writes structured events, unbuffered, to `stdout` and **nothing else**. The app MUST NEVER write, rotate, append to, truncate, compress, age out, or otherwise manage a logfile, and MUST NEVER decide where logs are stored, how long they are kept, or how they are routed. Routing, rotation, retention, and storage are exclusively the **execution environment's** concern.
**BANNED in app code:**
- The scaffolded logger (structlog / pino — see § Pre-Scaffolded Logging) writes to stdout. Do not add a second handler, sink, or transport alongside the stdout one.
- ❌ **BANNED — in-app file logging:**
- > **⚠️ THE SERVER'S OWN LOGGERS ARE NOT YOURS — and they leak plain text by default.**
**Chrome extension frontend:** Use `chrome.storage.local` buffer pattern per the Chrome Extension Telemetry section below. Do not use pino directly in service workers.
- Every `python-api` and `node-api` scaffold emits a pre-configured `/metrics` endpoint. DO NOT create custom metrics modules. **A VENDORED module (fabrik-lib copies) never constructs its own `Counter`/`Histogram` either:** the scaffold serves `/metrics` from a PRIVATE `CollectorRegistry` (`scaffold.py::metrics_app`), so a module-made metric on the global default registry is invisible on most `/metrics` surfaces and the module cannot know which registry its host scrapes. A module exposes an injectable callback (`on_<event>: Callable | None`) and a structured log-once; the HOST wires the callback to the registry it owns in one line. Precedent: fabrik-lib `async-http-client` (01M1GVYN, 01M1GY91).
- Name metrics with `snake_case` and a **base-unit** suffix (`_seconds`, `_bytes`); `_total` is the COUNTER suffix and composes with units (`process_cpu_seconds_total`). ⚠️ `prometheus_client` appends `_total` to a Counter itself — declare `Counter("requests", …)`, never `Counter("requests_total", …)`, and never `_count` (an OpenMetrics reserved suffix).
- ⚠️ **Know which failure YOUR stack gives you — they are not the same.** Under an OTel SDK, a metric that overflows its cardinality limit fails SILENTLY: totals stay correct while queries that *filter or group by* an attribute UNDERCOUNT, so dashboards and SLOs keep rendering numbers that are quietly too low. **Our scaffolded stack is `prometheus_client`, which has no such limit** — here a blowup is memory/TSDB growth, and Prometheus's own `sample_limit` fails the whole scrape LOUDLY (`up=0`) rather than skewing a breakdown. Loud is survivable; the reason to care about both is that a service moving to OTel inherits the silent one.
- is named, never dropped because someone remembered to remove it — and `_keep()` additionally enforces LEAF SHAPE: an allowlisted key holding an unexpected container is nulled. That last rule is what closes a channel nobody enumerated, which is the whole reason this is a shape rather than a list.
- `include_local_variables=False`, `max_request_body_size="never"`, `include_source_context=False`, `max_breadcrumbs=0`, and the fleet logging default `LoggingIntegration(event_level=logging.ERROR, level=None)` (D-126).
- ⚠️ **That last one is COUPLED to the allowlist and the two must move together.** The upstream reference uses `event_level=None`, which closes the log channel by never creating an event. The fleet keeps ERROR records as events — we want them in GlitchTip — so the channel is open, and what NARROWS it (it does not close it) is `_ALLOWED_LOGENTRY_KEYS == {"message"}`: the message TEMPLATE survives, `params` and `formatted` (the interpolated text) do not. Verified: `logger.error("otp=%s", secret)` yields one event with `logentry == {'message': 'otp=%s'}` and no secret. That holds for DEFERRED interpolation only: an eagerly built message (an f-string, `.format`, `+` or `%` inside the call) IS the template and ships its … (wrapped further — read the pack)
- Every `sentry_sdk.init` / `Sentry.init` in the fleet MUST still set both:
| `max_request_body_size="never"` | **n/a — see below** | the request BODY, attached irrespective of `send_default_pii` (that flag gates COOKIES). Every auth, payments-webhook and token-exchange route is exposed the moment it logs an error while handling its request. **PYTHON ONLY** |
- ⚠️ **The two SDKs are NOT symmetric.** `maxRequestBodySize` is a PYTHON option name; `@sentry/node` has no such init key, so a project that dutifully added it got a silently-ignored unknown key — a line that reads like a fix and does nothing. In `@sentry/node` the body channel is already closed by `sendDefaultPii: false`, which makes the SDK report body **size only, never content**. If a project wants it structural regardless of PII, the real control is `httpIntegration({ maxIncomingRequestBodySize: 'none' })` — note `'none'`, not `'never'`. `includeLocalVariables: false` IS correct and needed for Node (locals default ON for Node runtimes).
**Never port an option name across SDKs by symmetry; check that SDK's own docs.**
- `api_key`/`token`/`secret` BY KEY. ⚠️ **This section used to conclude "so the HTTP-header channel is closed out of the box". That was wrong and is corrected here.** The scrubber matches a FIXED list of NAMES — 37 in sentry-sdk 2.68.1 (`DEFAULT_DENYLIST` 33 + `DEFAULT_PII_DENYLIST` 4), of which about a dozen are header-shaped (`authorization`, `cookie`, `token`, `api_key`, `secret`, `x_csrftoken`, …) — so a header the fleet invents sails straight through it. Measured, not assumed: `X-Signing-Secret` matches nothing in that list. Sentry maintaining the list does not help when the name is ours. The header channel is closed by the vendored scrubber's header ALLOWLIST, not by the SDK: unknown header names are … (wrapped further — read the pack)
- message, or a span name is the residual, and it ships. Never interpolate a secret into either. That is the honest boundary — not "only free-text remains after two flags", which was the claim that left four channels open.
**Verify on the CAPTURED EVENT, never the init kwarg.** Swap the SDK transport in a test, make a real dependency raise, and assert on what the event actually contains — asserting the kwarg was passed proves you configured it, not that nothing leaks. The hub's own guard is the pattern to copy: `tests/test_scaffold_glitchtip_security.py` swaps `capture_envelope`, raises inside a real request with six secrets in play, and substring-searches everything the transport would ship — never a field list — asserting the TRANSACTION event as well as the error, since `before_send` never sees it.
- ⚠️ **A project scaffolded before 2026-09-05 has the OLD init — the two flags at best, and the four channels above open.** Nothing back-fills it. Vendor `templates/scaffold/python/glitchtip_init.py` from the hub over your own `src/{package}/glitchtip_init.py`, keeping your `{pkg}` import line and your service name, then prove it with the captured-event guard rather than by reading the diff.
- This is intentional: services without DSN configured never pay for SDK runtime cost
- ⚠️ **Outside that set nothing captures it.** A deliberate 401/403/429 you WANT audited reaches GlitchTip never — widen `failed_request_status_codes` in the init rather than sprinkling `capture_exception` through handlers.
- For `chrome-extension`: use `@sentry/browser` in the popup/options/side-panel (trusted extension pages). **In content scripts, never call the global `Sentry.init`** — a content script shares the host page's `window`, so global-state integrations hijack host-page errors. Build an isolated `BrowserClient` + `Scope` (drop `GlobalHandlers` / `Breadcrumbs`) and wrap with `makeBrowserOfflineTransport` (IndexedDB buffer/flush). Service workers use the `chrome.storage.local` buffer pattern (see Chrome Extension Telemetry below).
- **Caught-and-handled** exceptions: log with stack traces via `exc_info=True` in Python (dedicated JSON attribute, never raw multi-line text). **Unhandled** exceptions (FastAPI 500s, uncaught throws): do NOT log tracebacks — GlitchTip auto-captures them. Log a short event name + `correlation_id` only. See § Error Reporting above.
- In FastAPI: use `contextvars` + ASGI middleware to bind the ID to `structlog` context. Never use `threading.local()` in async code.
- ⚠️ **Why this fleet stops at a correlation ID, and what to name the field.** Probed across ALL THREE fleet hosts (vps1/vps2/vps3): Loki + Prometheus + Grafana only — **no DEDICATED trace backend (Tempo/Jaeger) and no OTel collector on any of them**, and Grafana carries exactly two datasources (loki, prometheus). ⚠️ Not "no spans at all": Sentry-SDK services already emit performance transactions to GlitchTip at `GLITCHTIP_TRACES_SAMPLE_RATE` (§ config above) — that is the only span-shaped signal here, and it is not a queryable trace store. So do NOT instrument distributed tracing here: spans with nowhere to go are cost without a consumer, and "add OpenTelemetry" is over-engineering until a backend exists. A request-scoped correlation ID … (wrapped further — read the pack)
- Never rely on downstream log processors (Promtail, Logstash) for redaction — unredacted data may persist in transport buffers.
- **Never** use high-cardinality values as Loki stream labels. `request_id`, `user_id`, `session_id`, `client_ip` must remain inside the JSON payload only.
- ⚠️ **The label set is the PIPELINE's — an app cannot create one by logging a field.** See § Loki above for the LIVE set; `service`, `environment` and `level` are *not* labels on this fleet, they are JSON fields queried with `| json`.
- `/health` is Authelia-bypassed on all services. The bypass is **resource-based, not domain-bound** — `/health`, `/healthz`, `/metrics`, `/api/health` are bypassed on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file`). Never protect these paths.
- Never use UUID or timestamp-suffixed container names in Gatus configs or inter-service URLs — they drift per redeploy.
- MV3 service workers are ephemeral (terminated after ~30s idle). Do not hold logs in memory waiting for a batch window.
- Do not propose OTel instrumentation for a fleet service without new evidence. Measured against this stack: OTel **logs** remain the weakest-maturity signal in both Python and JS — exactly the one Loki already serves well — and adoption would mean a stateful Collector on memory-constrained VPSes plus re-instrumenting every project to gain distributed tracing nobody has asked for. The logs + metrics + errors triad stays.
- GlitchTip DSN comes from `GLITCHTIP_DSN` env var injected by the orchestrator from the GlitchTip registrar — do NOT hardcode the DSN in the repo.

### core/57-external-data-sourcing.md  (hit: docs/reference/apis/EXTERNAL_SYSTEMS.md)
- API clients, connectors, webhook handlers). ⚠️ `58-resilience` does NOT auto-load on `connectors/`, `ingest/`, `webhooks/` or `scrapers/` paths — when this pack fires, read 58 explicitly; every rule below that says "the 58 contract" assumes you have.
**Never scrape when an API exists** — an API is a contract you can PROFILE (limits, resume, deprecation channel) and be authorised under; a scraper has no contract, breaks on markup change, and may violate ToS. (APIs still deprecate and break — field 10 exists because they do.)
- ⚠️ **Two lanes, and conflating them is the mistake this ladder invites.** An MCP server is an
- ⚠️ **Check the roster before naming one — do not cite from memory**: the roster is SPLIT (user-level + per-repo `.mcp.json`), canonical at `/opt/fabrik/docs/workstation/mcp-roster.md`, probed by `python3 /opt/fabrik/scripts/sysadmin/mcp_health.py`.
- (pluggable, Anti-Captcha — ⚠️ a BYPASS capability, not a default; see § Hard constraints, "the bypass line") · `adaptive-dispatch` (learns which fetch strategy works per domain) · `web-tools` (env-keyed Exa/Brave/Firecrawl executors — the RUNTIME answer to rung 1) · `proxy-pool` (Postgres-backed proxy pool — ⚠️ same caveat as `captcha-solve`: a bypass capability, never a default) · `api-quota` (`QuotaTracker` parses rate-limit headers, persists quota state and gates calls at the cap; `KeyPool` rotates across many keys — the RUNTIME half of profile fields 1, 2, 7 and 9) · `webhooks` (**outgoing** delivery with HMAC signing — it does … (wrapped further — read the pack)
- (⚠️ OpenRouter-only, see § Hard constraints), `ai-image`, `ai-audio`, `ai-translate`, `search`, `scrape`, `captcha`, `proxy`, `domains`, `email`, `storage`, `backup`, `research-data`, `media-stock`, `infra-platform`, `comms`, `dev-tools`, `unidentified`.
**Derive the count and the category set from the FILE, never from this list** — the file has a non-dict `_README` key, so the guard is not optional: `python3 -c "import json,collections;d=json.load(open('scripts/service_catalog.json'));print(collections.Counter(v['category'] for v in d.values() if isinstance(v,dict)))"`. Grep it by `category` before adding any new vendor; detailed contracts live in `docs/reference/apis/**`. Key via env var, never in code.
**An UNKNOWN never waives the design decision — design to the conservative reading**: unknown cap behaviour ⇒ assume silent truncation and verify counts yourself; unknown idempotency ⇒ assume non-idempotent; unknown resume ⇒ checkpoint on your side; unknown health signal ⇒ treat every 5xx burst as *possibly them* and pause rather than hammer; unknown key expiry ⇒ rotate on a schedule anyway; unknown deprecation channel ⇒ watch the headers; unknown schema stability ⇒ validate strictly at the boundary.
| 4 | **Identity posture** — limits per-key, per-account or per-IP? does the ToS permit multiple accounts/orgs — **cite the clause + URL, or UNKNOWN** | decides whether horizontal scale is even available — see the ⚠️ below |
| 9 | **Credential lifecycle** — does the key/token EXPIRE, on what schedule; can it be rotated with an overlap (two keys valid at once) or only by a hard cut; what does an expired key LOOK like (401? 403? a silent empty 200?) | decides whether rotation can be automated at all, and whether the connector can even tell a dead credential from a dead vendor — an expired key is the failure a retry loop can never fix |
| 11 | **Data contract + EXPECTED YIELD** — the response schema pinned at profile time, and the yield the surface must return; what the vendor changes WITHOUT a version bump (nullable flips, new enum values, added fields, pagination shape); freshness/lag and eventual-consistency window; how deletion shows (tombstone vs vanish); a sample kept for diffing | decides the validation posture: a `200` with a different shape is the failure that corrupts silently — outages page you, drift does not ⚠️ **and the EXPECTED YIELD per page** — a number, or `0 is terminal` — and terminal is a POSITION, never a surface. Zero rows is the contract only where a predecessor proves you are past the data: page N+1 after page N returned rows, a delta past a non-empty cursor, a section index that listed N items. Zero on the FIRST page or a cold cursor is a failed fetch ONLY where the surface also states a `≥1` floor for that position — a listing whose first page always has rows. It is NOT a failure on a search or a filtered section, where an empty first page is the honest answer; those declare `0 is terminal` and nothing else. The incident this closes is the listing case: a challenge page on page 1 of a surface that promised rows, read as "crawl complete, 0 rows". A zero-row page is only a failure against a stated `≥1`; undeclared, it is not one (the scraper-failure-classes bullet under § The Capability Profile). |
- ⚠️ **Field 4 is where an operational question becomes a legal one.** Asking "are multiple accounts permitted, and are limits per-key or per-IP?" is ordinary capacity planning, and the answer is sometimes an explicit yes (separate billing orgs, per-project keys). Provisioning extra accounts or rotating IPs **in order to evade a cap the vendor set** is the circumvention shape from § Hard constraints, and it is an operator decision with the ToS quoted — never an engineering convenience. (That exit is legitimate here on the contractual-gate ground — an authorisation, not a menu.) Record what the ToS actually says; do not infer permission from the absence of a block.
- expiry never happens in production; the `58` last-resort rung that died of an expired credential is this row unfilled.
- model (pydantic `strict=True` / zod `.strict()`, unknown keys rejected deliberately), never silently drop an invalid record, and export the invalid-record RATE as a metric — a spike is the upstream change announcing itself, and a `missing` cluster on one field says which one.
- signature outside the timestamp tolerance. ⚠️ **And it runs a reconciliation poll** — a scheduled pull of "what did you send since <cursor>" against the vendor's list endpoint — because a delivery the provider gave up on during your deploy is otherwise unrecoverable by construction. No list endpoint in field 12 ⇒ say so, and treat every missed webhook as a known gap in §9.
- row 22 alarms on, never the fetch count. A **bot-block** (`403`, a challenge page) is a pause condition, not a retry and not a bypass: `58` says never retry a 403, and § Hard constraints says never solve the challenge — the legal move is `adaptive-dispatch`'s strategy switch (static → rendered), then a pause, then an operator decision.
- ONCE, never hot-looping, and named as human-gated in §2b so nobody expects the queue to wake itself.
- ⚠️ **One subject, one home.** The profile records the VENDOR's contract (measured, dated). YOUR handling of it — timeout/retry config, fallback, pause keys — stays in the per-dependency detail card in `docs/RESILIENCE.md`; that card LINKS the profile and never copies its numbers.
- ⚠️ **Not gate-enforced yet, deliberately — and measured 2026-09-02: 0 of the 6 hub vendor docs in `docs/reference/apis/` carry a profile.** This is a new obligation; per the FIX directive a detector ships after its fire rate is measured, not before. Until then the profile's teeth are the `Profile:` line on the dependency's card in `docs/RESILIENCE.md` — **§2b where the doc has one, otherwise the project's equivalent per-dependency row or section** (the scaffold template does carry the slot, verified at `templates/scaffold/docs/RESILIENCE_TEMPLATE.md:63` § 2b Detail Card Per Dependency, whose first field is `Profile`; but a project scaffolded before it, or one whose … (wrapped further — read the pack)
- **LLM data = OpenRouter ONLY** — never a direct vendor LLM SDK (`openai`, `@anthropic-ai/sdk`). Non-LLM vendor APIs are fine directly.
- **Vendor keys are env vars** (`os.getenv`), never constants; the repo must stay open-sourceable (12F-III).
- Honour a TDM reservation even when your own UA is not the one named. ⚠️ **The token set churns and vendors now run SEVERAL bots each** — Anthropic retired `anthropic-ai` and `Claude-Web` for `ClaudeBot` (training) / `Claude-User` (user-initiated fetch) / `Claude-SearchBot` (indexing), and OpenAI/Perplexity document their user-initiated fetchers (`ChatGPT-User`, `Perplexity-User`) as *not* governed by robots.txt. Read a site's file for the group matching YOUR token, not a 2024 block-list. The machine-readable successor is the IETF AIPREF `Content-Usage` rule (robots.txt directive + HTTP header, a draft that updates RFC 9309 if approved) — honour it … (wrapped further — read the pack)
- **⚠️ THE BYPASS LINE IS THE LEGAL LINE, and it runs straight through our own toolbox.** Reading a logged-out public page is a different act from defeating a control. The moment a pipeline solves a CAPTCHA, replays a session, rotates IPs to beat a block, or evades a hard rate limit, it leaves "public data" territory — and the live litigation wave targets the
- catalog's `proxy` and `captcha` categories are therefore **capabilities, never defaults**: reach for them only where a human operator has decided the specific source warrants it, and say so in the plan.
- on a page you never agreed to are weak against a logged-out fetcher; terms you click through, or accept by creating an account, are an ordinary contract and scraping in breach of them is a straightforward claim. So "we have an account there" changes the answer — check before assuming the public-page reasoning applies.
- ⚠️ **Where the profile lives differs between hub and project** — `EXTERNAL_SYSTEMS.md` is a hub-only index; do not send a project at it.
- `cost` · `capability` · `url` · `status` · `match` · `hosts` · `merged_match`), never the envelope — the twelve profile fields live in the vendor doc, dated and re-verifiable.
- the handler, never onto Authelia. It does not ride the health-path bypass either. **The mechanism is the spec, not a hope:** route the receiver under the service's `shape.bearer_bypass_prefix` (a path-regex, default `^/api/` for `has_bearer_api` services, narrowable) — that IS the explicit public route; there is no per-path bypass field to invent. An UNSIGNED provider that must write cross-tenant is the `needs_payments_ingest` shape.

### core/58-resilience.md  (hit: docs/reference/health-monitoring.md)
- indexed here, never restated; "can actually suffer" is decided by § Per-Scaffold Applicability above. An N/A with a reason is a complete answer, a silent gap is not.
- ⚠️ **Rows 9 and 22 make "autorecovery" honest.** Everything else recovers a *call*; row 9 recovers the
- **`httpx.AsyncClient`** is the only HTTP client for async FastAPI. Never use `requests` (sync, blocks the event loop).
**`wait_random_exponential` / `wait_exponential_jitter`, never bare `wait_exponential`**. Not a style preference: tenacity's own docstring says `wait_exponential`'s intervals "are fixed (i.e. there is no jitter) … *not* suitable for resolving contention between multiple processes for a shared resource". N workers that fail together retry in lockstep and re-hammer the dependency exactly as it recovers — the thundering herd. Every worker fleet here is that "multiple processes" case.
- 400/401/403/404/422 — a permanent client error retried is just load. ⚠️ **`429` and `408` are the exceptions and they matter most**: `429` is the commonest retryable response from a rate-limited vendor and `408` is transient by definition, so a flat "never retry 4xx" makes an agent give up on precisely the failure backoff exists for.
- curve does. ⚠️ **Two legal formats**: delay-seconds (`120`) *or* an HTTP-date (`Wed, 21 Oct 2026 07:28:00 GMT`). Parse both, **clamp both ends** (a hostile `86400` must not park a worker for a day; a hostile `-1` must not raise out of your retry machinery), and fall back to jittered backoff when absent or unparseable. `tenacity.wait_exception` exposes the response for this.
- **⚠️ Inline retry vs PAUSE — and `429` is where they meet.** An inline retry handles a **blip**; a pause handles a **condition**, where every job will hit the same wall and retrying inline just multiplies load across the queue. The test is not the status code but **whether the next job would fail for the same reason**: a single `429` with a short `Retry-After` → honour it inline; repeated `429`s, or a `Retry-After` beyond your inline budget → `set_pause(key, ttl)` so one worker's discovery spares the whole queue. ⚠️ **Clamp that TTL too** (§7a): the inline cap stops a hostile `86400` parking ONE worker for a day; the same unvalidated value in a pause key parks the ENTIRE … (wrapped further — read the pack)
- **⚠️ Retry at ONE layer.** Retries compose multiplicatively: tenacity ×3 in a job, a queue retry ×3 around it, your caller ×3 = up to **27** upstream calls per logical operation, long before a breaker sees a pattern. Pick the owning layer; make the inner ones fail fast. For worker jobs the queue retry IS the retry — do not also wrap the call in `@retry`.
- **⚠️ Retrying a non-idempotent write can double-charge, double-send or double-create.** A `POST` (or non-idempotent `PATCH`) needs an `Idempotency-Key` before it gets a retry — otherwise retrying after a timeout you never saw the response to is a second real mutation. `PUT`/`DELETE` are idempotent by HTTP semantics. `15-api-contracts` owns the SERVING side; this pack owns the caller's question —
- **Graceful fallback** — cached data, a default, or a clear error. Never let an external failure crash your endpoint. ⚠️ That includes the *parse*: a `200` with malformed JSON raises `JSONDecodeError`, which is not an `httpx.HTTPError` and will sail straight past the `except` above.
- Clients call a **self-hosted FastAPI backend** (Pattern A — `fabrik-lib/fastapi-user-auth`), never a database-as-a-service SDK directly. Browser `fetch` / mobile HTTP clients have no built-in timeout or retry — wire them explicitly:
- **Backend outage fallback:** cached data (MMKV on mobile, localStorage on web) or a clear error state — never a blank screen or crash.
- **Auth token refresh:** the app's auth client owns the refresh flow (`35-security-auth.md` Pattern A). Never scatter ad-hoc refresh logic across service calls.
| **`open` returns the fallback IMMEDIATELY**, never a queued timeout wait | you re-pay the read timeout on every call to a dead dependency |
- distributed breaker: never back it with Redis to "share" state. ⚠️ Corollary: with N workers, up to `N × failure_threshold` calls hit a dead dependency first. When that matters the fleet-wide stop is a
- **Never auto-run migrations at startup** — a one-shot deploy step (`30-ops` § Release & Admin).
- ⚠️ **The "fail readiness first, then drain" step in every Kubernetes guide does NOT apply here by default** — it lets a load balancer deregister one replica while its siblings serve, and this stack does not set `deploy.replicas` on app services (`30-ops`). Add it only with real multi-replica Traefik routing; unconditionally it buys a longer outage per deploy, not a shorter one.
- **The signal must arrive.** Shell-form `CMD` makes `/bin/sh` PID 1, which never forwards SIGTERM — exec-form, or `sh -c "exec ..."` (`30-ops`).
- stampedes the origin — a herd from your own cache, not a retry loop, so jitter and backoff never touch it. Coalesce behind a single-flight lock, or refresh before expiry.
| **Backblaze B2** (S3 API, `boto3`) | 30s connect / 120s read | return an error; never block a request on an upload |
- B2 uploads go async via the job queue, never inline in a handler. **boto3 is sync** — keep it in the worker or a thread executor, never inside an `async def` route.
- B2 downloads use server-side presigned URLs (generation is local, no I/O — safe in async). Never proxy file bytes through FastAPI.
- ⚠️ **Never point `HEALTHCHECK` at the dependency-checking endpoint** — one `postgres-main` blip would flip every container on the fleet to `unhealthy` at once. A DB blip degrades readiness; it must never mark the container unhealthy.
- Both endpoints are Authelia-bypassed on all services. Never protect them.
- ⚠️ **Docker does NOT restart an unhealthy container.** `restart: unless-stopped` acts on process EXIT only; health status feeds `up --wait`, `depends_on: service_healthy` and Traefik routing — never a restart. A process that is **wedged but alive** is recovered by nothing in compose: that is the watchdog's Tier A `restart_container` (`60-watchdog`), and it is why the watchdog exists. Never design as if the daemon will do it.
- see pause state without it firing Gatus alerts. ⚠️ That deliberate green is exactly why a long pause must escalate on its own (§ The Four Properties, property 2).
- 1. **Detection is proactive AND reactive.** Beat tasks poll vendor balance APIs *before* workers fail; error classifiers map exceptions to pause keys on the way through. Never one without the other for a critical dependency.
- ⚠️ **So a pause carries its FIRST-set time and escalates exactly once past N× its TTL** (`self-healing` row 4). ⚠️ **`fabrik-lib/alerting/` does NOT give you that property, and the provider-death row 3 of § Provider-death resilience points here rather than repeating it** — NOT the coverage map's row 3, which is the circuit-breaker row. Read at `/opt/fabrik-lib/alerting/__init__.py`, its dedup is a module-level `_last_sent` dict, so it is per-process — and a forked child INHERITS the parent's, rather than starting clean. Four things it is not. (1) Not a latch: the window is `ALERT_MIN_INTERVAL` … (wrapped further — read the pack)
- boot). Sliding TTL: every detection event calls `set_pause(...)` with a fresh TTL — never `setnx`, never permanent. Scope (§2c of the project's RESILIENCE.md):
- your dependencies, never inline at a call site.
- The classifier maps transient signals → pause. Its mirror-image rule is just as load-bearing: **an operational failure must never be written as a terminal *content* verdict.** Model the outcome on two axes — **(transport outcome) × (content evidence)** — and record a content terminal (`deleted`, `private`, `unavailable`…) only on **positive content evidence**. Everything else is transient.
| 1 | **No single point of death** — one model or endpoint dying must not stop the loop | **Declare** the mechanism in §2b. Outage-aware routing is step 1 of OpenRouter's default strategy and a `models` array falls back on **any** error. ⚠️ **The trap: setting `sort` or `order` DISABLES load balancing, and the outage step is *part of* it** — pinning silently opts you out of the protection you think you have (claims row `openrouter-pin-disables-failover`); if you pin, you owe the `models` array explicitly | **Build it**: probe the quality-ordered candidates **once at run start** (never per item) and rebuild the chain from live survivors, best first, so it self-restores on recovery. Base it on `fabrik-lib/health-probe/`; the chain-rebuild helper is `health_probe.live_chain()` (fabrik-lib `health-probe/`, vendored to projects as `libs/health_probe/` by the governance sync). Needs **intra-provider** (2+ models of one provider) AND **cross-provider** diversity |
| 3 | **Absence of progress is alarmed** — N minutes of zero progress fires ONE alert, cleared on recovery | No gateway provides this. Export a monotonically-increasing **progress** counter (rows done, items classified) and alert on *it*, not on error codes. Threshold ≥ 2 full loop runs, a §7a knob. ⚠️ The exactly-one half is YOURS to build — `fabrik-lib/alerting/` does not provide it; see the pause-escalation bullet under § Advanced: Autonomous Pause-State Pipeline → The Four Properties for what it actually does and why — this file's own section, not `RESILIENCE.md` §7 | Same |
| Worker clears `dispatched:<id>` flag when paused | Worker MUST keep the flag on pause-skip (queue bloat) |
| Backup that has never been restored to staging | Run §10 drill within 30 days or it doesn't exist |
| A fallback chain whose **bottom rung has never been executed** | Exercise the last resort on a schedule — an untested fallback is a silently-dead one, and the chain is a rung shorter than its author believes |
- one-shot migration step boot must never do
- [ ] Retries use **jittered** backoff (`wait_random_exponential`/`wait_exponential_jitter`, never bare `wait_exponential`) on transient errors only.
- naming only `TimeoutException`/`ConnectError` never retries a 429.
- state — never a blank screen.

### core/90-bootstrap-scripts.md  (hit: docs/infrastructure/vps-bootstrap-plan.md, docs/infrastructure/vps-hub-rebuild.md, docs/infrastructure/vps-spoke-rebuild.md)
**If you see this message, switch to `ozgur@<ip>` and re-run. Do not retry with `root@<ip>`.**
- `ozgur@<ip>`. Do not test root first.
- the single-quoted remote program as one string literal and never parses it, so the remote-bash syntax error WILL NOT be caught by `bash -n` of the local script — only by an actual ssh execution.
- Every dependency-install step (apt, npm, pip, systemd-unit creation) MUST be a no-op when its outcome is already present. Probe with `command -v` (the POSIX builtin, which looks a name up the way the shell will) — not `which`, which is non-standard:
- already-bootstrapped VPS — every step should print `already installed` or `already configured`, never re-do work.
- higher unused number). Do not use `vps-drill` or other free-form names — the script will reject them.
**Prevention:** fail2ban never bans an address in `ignoreip`. Adding the operator's IP and the mesh range in a `/etc/fail2ban/jail.d/*.local` drop-in (or at runtime with `sudo fail2ban-client set sshd addignoreip <ip>`) retires this whole lockout class; the bootstrap scripts do not do it yet.
- the log, the script never runs, and the absent log looks like "it ran and printed nothing". Cron runs the line with `/bin/sh`; the shell's error goes to cron's mail (the crontab owner, or `MAILTO`), and on a box with no mail agent cron discards it. The journal (`journalctl -t CRON`) then shows only that the job ran and that its output was discarded — never the shell's error — so the writability probe below is the diagnostic, not the log.
- Founding incident: `scripts/sysadmin/liveness_audit.py:10-11` — the Claude-config DR backup had never once run from cron for exactly this reason. Reproduced again 2026-08-29 (`touch /var/log/x` → `Permission denied` for the WSL user), when a plan copied an existing `>> /var/log/…` line verbatim from a working precedent and shipped the same defect; only a native Opus reviewer caught it.
- naming — letters, digits, underscores and hyphens only), so a template installed as `vps-sysadmin.cron` never runs.
- ⚠️ **Not mechanically gated, deliberately.** Dozens of `>> /var/log/` redirects exist across this repo's docs, scripts and templates, and most are correct — VPS root cron writing pre-created files. A check flagging all of them would fire mostly on legitimate lines, and a rule that is routinely waived teaches agents that the gate's findings are advisory. Writability depends on the user and the host; only the author can resolve it, which is why this is a rule you apply rather than a check that fires.

### core/self-healing.md  (hit: docs/reference/health-monitoring.md)
- AGENT USAGE: Pick the failure class, walk the ladder top-to-bottom, stop at the first step that resolves. Never invent a step. Never skip a step. -->
- [`60-watchdog`](60-watchdog.md) — the escalation engine and the owner of its tiers. Tier A acts automatically (it registers `restart_container`, `clear_file_cache`, `pause_worker`); Tier B is opt-in; Tier C escalates — and carries the **approved-write lane** (`drop_queue_items`, `rotate_locks`), off by default and autonomous once configured; **Tier D** (opt-in, Telegram-gated) applies a tested code fix with auto-rollback. ⚠️ Registered is not runnable — see **What the sidecar can execute today** below.
- Each row reads left-to-right: **Symptom** (an observable signal) → **First response** (a `58-resilience` primitive or the module that implements it) → **Fallback** (another primitive or a `60-watchdog` action) → **Escalate** (operator-bound). The agent picks the row matching the active failure, walks left-to-right, and **stops at the first step that resolves**. Never skip rightward.
| 11 | **Postgres allocation registry drift** (HUB-side, not a service: a database in `pg_database` with no `allocations.json` entry) | the hourly drift cron (`scripts/audit_all_registrars.py`) finds a database no registry row claims | Additive reconcile (`src/fabrik/registry_reconcile.py`, D-500): registers it in-lock, never overwrites or deletes; `report` (writes nothing) unless the cron line sets `FABRIK_REGISTRY_RECONCILE=apply` | Refuse, never guess, and write nothing: a name two specs claim is counted as `fabrik_registry_heal_total{outcome="shared"}`; any other refusal (an incomplete claim map, an unresolved owner, an error) as `fabrik_registry_heal_failed{spec_id,db,reason}` | `FabrikRegistryHealFailed` (a `heal_failed` refusal standing 2 h; a shared claim alerts on neither) or `FabrikAuditStale` (no clean audit run in 3 h, or none recorded) — `configs/prometheus/rules/fabrik-drift.yml` |
| 12 | **Unkillable worker child** (a fork-pool child stuck in uninterruptible kernel sleep, e.g. a kernel netlink wedge) | a worker child is still alive after SIGKILL + join; `/proc/<pid>/stat` state `D` (wchan e.g. `rtnl_dumpit`) | Do NOT replace it: re-check `is_alive()` after the kill, hold the child against the pool's live-child cap ([75-workers-jobs § Adaptive Worker Pool](75-workers-jobs.md) — never exceed `max_workers`), count it in a wedged-child counter and log it — the counter is the project's to build | Keep the pool serving under its cap with the live children ([75-workers-jobs § Adaptive Worker Pool](75-workers-jobs.md)); a sweep grouping the D-state children by wchan, the project's to build, makes one episode read as one event | ONE operator alert per episode — its deduplication is the project's to build, as row 10's is; the operator reboots the host (on WSL, `wsl --shutdown`) — no automated step can unwedge a kernel |
**⚠️ Row 10 is NOT the deadman timer, and the difference is the whole point.** The Tier-C deadman below (`spec.watchdog.deadman_timeout_seconds`, 60–3600, default 300 s, rendered as `WATCHDOG_DEADMAN_TIMEOUT`) measures **operator silence** — it arms only
- **Tier C approved-write (opt-in per project, through the project `.env` only):** rows 2 and 8 name `drop_queue_items` and `rotate_locks` — app-DB mutations, so the model is offered one only when the project's `.env` lists it in `WATCHDOG_LLM_ACTIONS`, gives it a `WATCHDOG_DB_WRITE_ALLOWLIST` entry, sets `WATCHDOG_ALLOW_DB_WRITES=true` AND a writable `WATCHDOG_DB_URL_RW` exists (`fabrik apply` provisions the DML-only role; nothing sets the switch or the allowlist for you). Short of that, it is not offered and the row escalates. "Approved" means the operator approved the lane by setting those four, never per call: once offered, a proposal that passes `check_proposal` runs at once and escalates afterwards, arming the deadman restart below like any Tier C escalation (fabrik-lib D-471), so the checklist's layer count takes it as autonomous.
- If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first, then the response logic to the code.** Never silently invent a self-healing response — it'll diverge from the operator's mental model and break the ladder's discipline.
- 4. **Self-healing without a visible signal.** A pause flag, breaker, or rate-limit reject that doesn't increment a counter and emit a structured log line is invisible — when it misfires, you can't tell. Every ladder step MUST emit a counter AND a `structlog.info()` (or `pino.info()`) row carrying the resource name + reason; without that, the next operator audit has no way to tell the difference between "step fired and recovered" and "step never ran". **Tier-D steps (stabilize / remediate / apply / rollback) are held to the same bar:** each MUST emit a counter + structured log AND write the `incidents` / `approvals` / `deploys` tables — an unaudited or irreversible code-remediation is not self-healing, it's an unreviewed deploy.
- 2. **Fallback — `pause-state` (Redis-backed).** When `signups_per_ip_per_minute` for a specific IP stays high after the first defense's per-IP cap fires, the worker emits an incident; the watchdog sidecar reads the inbox and proposes Tier A `pause_worker` with `resource=signup_<ip_hash>` (the action accepts `^[a-z][a-z0-9_]{0,31}$` and a TTL of 5–3600 s, so truncate the hash to fit — and it runs only once the spec lists `watchdog.llm_actions: [pause_worker]`, above; until then that step escalates and the app sets this pause itself with `pause_state.set_global_pause(...)`). Every signup-handling worker checks `pause_state.is_paused("signup_<ip_hash>")` from the vendored fabrik-lib `pause-state` (the scaffold's own `pause_state.py` has no `is_paused`), with `PAUSE_KEY_PREFIX` equal to `<project_id>:pause:`, and bails without touching the DB. Never gate other workers on `is_globally_paused()` while per-IP keys share the prefix — it reports ANY key under it, so one IP would stop them all.

# promote-to-check_*: 177 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `fabrik-lib/fastapi-user-auth` `DELETE … RETURNING` `jti` `agents-fabrik.md § Supabase`
- `chrome-extension` `chrome.identity.launchWebAuthFlow` `https://<ext-id>.chromiumapp.org/` `chrome.storage.session`
- `desktop-app` `safeStorage` `desktop-app/72-desktop.md`
- `fabrik` `X-Internal-Token` `internal_auth.py` `hmac.compare_digest` `APIKeyHeader`
- `auth.uid()` `current_tenant_id()` `NULL` `EXCEPTION WHEN OTHERS THEN RETURN NULL` `SELECT auth.uid()` `NULL`
- `openssl rand -hex 32`
- `algorithms=["HS256"]` `alg` `alg: none`
- `redis-main`
- `expo-secure-store` `80-mobile.md`
- `localStorage` `sessionStorage`
- `chrome.storage.session` `TRUSTED_CONTEXTS` `chrome.runtime.sendMessage` `chrome.identity.launchWebAuthFlow` `code_verifier` `crypto.subtle` `storage.session`
- `x-middleware-subrequest` `middleware.ts` `proxy.ts` `middleware.ts`
- `CORSMiddleware` `allow_origins`
- `X-Frame-Options: DENY` `frame-ancestors`
- `APIKeyHeader` `require_api_key` `SERVICE_API_KEY` `PROXY_API_KEY` `python-api` `internal_auth.py` `metrics.py` `/metrics` `SERVICE_INTERNAL_SECRET_KEY`
- `os.getenv("KEY", "default")` `config/production.yml` `settings.production`
- `POST /auth/passwordless/request` `AUTH_PASSWORDLESS_REQUEST_CAP` `AUTH_PASSWORDLESS_IP_REQUEST_CAP` `POST /auth/passwordless/verify`
- `expo-secure-store`
- `shape.is_admin_dashboard: true` `two_factor` `fabrik apply` `/health` `/metrics` `saas/60-saas-ui.md` `shape.has_bearer_api: true` `two_factor`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
```

| Class | Status |
|---|---|
| Hunt: `.fabrik/plan-locks/2026-10-08-plan-1-promtail-to-alloy.json` — every changed hunk, its enclosing function, its callers | CLEAN (`.fabrik/plan-locks/2026-10-08-plan-1-promtail-to-alloy.json` — a work-item/plan-lock record, not reviewed code: the branch's copy is master's at the merge or a status record this review's own commits wrote; no hunt class applies) |
| Hunt: `.fabrik/work/W-0913992c.json` — every changed hunk, its enclosing function, its callers | CLEAN (`.fabrik/work/W-0913992c.json` — a work-item/plan-lock record, not reviewed code: the branch's copy is master's at the merge or a status record this review's own commits wrote; no hunt class applies) |
| Hunt: `.fabrik/work/W-ede94e4e.json` — every changed hunk, its enclosing function, its callers | CLEAN (`.fabrik/work/W-ede94e4e.json` — a work-item/plan-lock record, not reviewed code: the branch's copy is master's at the merge or a status record this review's own commits wrote; no hunt class applies) |
| Hunt: `CHANGELOG.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (blank line the conflict resolution dropped before master's first ### heading) |
| Hunt: `INDEX.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (alloy-noise-filter-setup.md tree entry sorted ahead of archive) |
| Hunt: `PORTS.md` — every changed hunk, its enclosing function, its callers | CLEAN (`PORTS.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `README.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (Loki + Promtail -> Loki + Alloy with the rollback note) |
| Hunt: `configs/alloy/config.alloy` — every changed hunk, its enclosing function, its callers | CLEAN (`configs/alloy/config.alloy` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `configs/gatus/README.md` — every changed hunk, its enclosing function, its callers | CLEAN (`configs/gatus/README.md` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `configs/gatus/apps/observability-agents.yaml` — every changed hunk, its enclosing function, its callers | CLEAN (`configs/gatus/apps/observability-agents.yaml` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `configs/prometheus/prometheus.yml` — every changed hunk, its enclosing function, its callers | CLEAN (`configs/prometheus/prometheus.yml` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/DEPLOYMENT_ARCHITECTURE.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/DEPLOYMENT_ARCHITECTURE.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/LESSONS_LEARNT.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (blank line the conflict resolution dropped before master's first ## heading) |
| Hunt: `docs/README.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/README.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/SERVICES.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/SERVICES.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/2026-10-08-plan-1-promtail-to-alloy.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/2026-10-08-plan-1-promtail-to-alloy.md` — slice C1: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/T02-hub-compose-and-ceilings.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/T02-hub-compose-and-ceilings.md` — slice C1: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T01-review.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T01-review.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T02-review.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T02-review.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T05a-review.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-T05a-review.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/development/reviews/2026-10-08-plan-1-promtail-to-alloy-review.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/alloy-noise-filter-setup.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (spoke Loki endpoint) · FIXED r3 (rollback restatement replaced by a pointer to runbook § 4) |
| Hunt: `docs/infrastructure/audit-prompts/01-full-system-audit.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/audit-prompts/01-full-system-audit.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/audit-prompts/02-container-health.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/audit-prompts/02-container-health.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/audit-prompts/03-security-hardening.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/audit-prompts/03-security-hardening.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/audit-prompts/04-performance-bottleneck.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/audit-prompts/04-performance-bottleneck.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/audit-prompts/05-observability-pipeline.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/audit-prompts/05-observability-pipeline.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/audit-prompts/07-pre-production-checklist.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/audit-prompts/07-pre-production-checklist.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/audit-prompts/08-hardening-remediation.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/audit-prompts/08-hardening-remediation.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/audit-prompts/README.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/audit-prompts/README.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/glitchtip-sdk-integration-setup.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/glitchtip-sdk-integration-setup.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/grafana-dashboards-setup.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (spokes push to 10.99.0.1:3100, not loki:3100; the 2026-06-07 check no longer credited to Alloy) |
| Hunt: `docs/infrastructure/grafana-provisioning-setup.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/grafana-provisioning-setup.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/prometheus-app-metrics-setup.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (pushgateway :126 -> :131 twice; truth check no longer names promtail-spokes live at :70) |
| Hunt: `docs/infrastructure/promtail-noise-filter-setup.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/promtail-noise-filter-setup.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/vps-ai-sysadmin.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/vps-ai-sysadmin.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/vps-bootstrap-plan.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/vps-bootstrap-plan.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/vps-complete-inventory.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/vps-complete-inventory.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/vps-fleet-architecture.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/vps-fleet-architecture.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/vps-hub-rebuild.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/vps-hub-rebuild.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/vps-spoke-rebuild.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/vps-spoke-rebuild.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/vps-status.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/infrastructure/vps-status.md` — slice C2: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/infrastructure/vps-urls.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (pushgateway :126 -> :131) |
| Hunt: `docs/operations/disaster-recovery.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/operations/disaster-recovery.md` — slice C1: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/operations/hub-restore-inventory.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/operations/hub-restore-inventory.md` — slice C1: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/operations/promtail-to-alloy-runbook.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (step (a) live-vs-master-mirror check, keep-first backup, D3 on origin/master, ORPHAN not a stop, spoke volume cite, infra-mail files+grep instead of moved line numbers) · FIXED r2 (one backup rule; rollback moves the backup) · FIXED r3 (mirror check first attempt only; re-run-only-up note) |
| Hunt: `docs/operations/spoke-restore-inventory.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/operations/spoke-restore-inventory.md` — slice C1: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/reference/apis/EXTERNAL_SYSTEMS.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/reference/apis/EXTERNAL_SYSTEMS.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/reference/architecture.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/reference/architecture.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/reference/health-monitoring.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/reference/health-monitoring.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/reference/vps1-postgres-admin-rotation-runbook.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (master-new line named promtail as the shipper and cited compose:35) |
| Hunt: `docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md` — slice C1: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `docs/workflows/development-and-deployment-workflow.md` — every changed hunk, its enclosing function, its callers | CLEAN (`docs/workflows/development-and-deployment-workflow.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `infra/README.md` — every changed hunk, its enclosing function, its callers | CLEAN (`infra/README.md` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `infra/vps1/monitoring/compose.yaml` — every changed hunk, its enclosing function, its callers | CLEAN (`infra/vps1/monitoring/compose.yaml` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `infra/vps2/monitoring-agent/compose.yaml` — every changed hunk, its enclosing function, its callers | CLEAN (`infra/vps2/monitoring-agent/compose.yaml` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `infra/vps3/monitoring-agent/compose.yaml` — every changed hunk, its enclosing function, its callers | CLEAN (`infra/vps3/monitoring-agent/compose.yaml` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/audit/05-observability.sh` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/audit/05-observability.sh` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/audit/06-backup.sh` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/audit/06-backup.sh` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/bootstrap/README.md` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/bootstrap/README.md` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/bootstrap/bootstrap-config.sh` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/bootstrap/bootstrap-config.sh` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/bootstrap/bootstrap-hub.sh` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/bootstrap/bootstrap-hub.sh` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/bootstrap/bootstrap-spoke-restore.sh` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/bootstrap/bootstrap-spoke-restore.sh` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/bootstrap/bootstrap-vps.sh` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/bootstrap/bootstrap-vps.sh` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/bootstrap/templates/alloy.alloy.template` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/bootstrap/templates/alloy.alloy.template` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/bootstrap/templates/monitoring-agent.compose.yaml.template` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/bootstrap/templates/monitoring-agent.compose.yaml.template` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/generate_vps_inventory.py` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/generate_vps_inventory.py` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/sysadmin/proactive-check.sh` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/sysadmin/proactive-check.sh` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/sysadmin/system-prompt.txt` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/sysadmin/system-prompt.txt` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/sysadmin/vps1_ocoron_removal.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (KNOWN_BENIGN names the log shipper's drop filter, Promtail then Alloy) |
| Hunt: `scripts/vps_apply_limits.sh` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/vps_apply_limits.sh` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `scripts/vps_sync.py` — every changed hunk, its enclosing function, its callers | CLEAN (`scripts/vps_sync.py` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `templates/file-worker/compose.yaml.j2` — every changed hunk, its enclosing function, its callers | CLEAN (`templates/file-worker/compose.yaml.j2` — slice A: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `templates/scaffold/docs/RESILIENCE_TEMPLATE.md` — every changed hunk, its enclosing function, its callers | CLEAN (`templates/scaffold/docs/RESILIENCE_TEMPLATE.md` — slice D: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `tests/test_alloy_configs.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (docstring cited a non-existent § skip discipline) |
| Hunt: `tests/test_alloy_consumers.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (network cite named by definition, not drifted lines 244-246) |
| Hunt: `tests/test_alloy_runbook.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (D3 test requires the three-file pass bullet + nothing else, ORPHAN rule, origin/master — mutant deleting the bullet red at :163) · FIXED r2 (rollback pins the mv) |
| Hunt: `tests/test_alloy_watchers.py` — every changed hunk, its enclosing function, its callers | CLEAN (`tests/test_alloy_watchers.py` — slice B: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Hunt: `tests/test_monitoring_agent_template.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (stale grep -q docstring; either-arm Loki assertion tightened to the exact phrase) |
| Hunt: `tests/test_vps_apply_limits.py` — every changed hunk, its enclosing function, its callers | CLEAN (`tests/test_vps_apply_limits.py` — slice B: its Sonnet and Haiku finders read every change.diff hunk of it against master's copy at pins-1m digest 88431016086a96e6f580240683556202 (base 9f3061b8f, tip 381d034ea); every candidate they raised on it is in § Residual) |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | CLEAN (scripts/bootstrap/bootstrap-vps.sh step-11 verify double sample and `rm -sf promtail` (probed rc 0, compose 2.40.3), scripts/vps_sync.py verify_limits, scripts/vps_apply_limits.sh MISSING, runbook STOP rules — A2/A3/A4 refuted with execution) |
| Recurrence: cost/quota accounting — pool units scored, native seats counted, a limit at its edges | CLEAN (scripts/vps_apply_limits.sh ceilings 3,008 MiB re-derived; infra/vps1/monitoring/compose.yaml cpus tiers vs D-1324 — alloy takes promtail's 0.5; no pool units: every seat native) |
| Recurrence: boundary/sentinel/prefix — an off-by-one, a sentinel value, a prefix-vs-exact match | FIXED r1 (configs/prometheus/prometheus.yml line shift +5 past :70 broke three pushgateway cites; the class sweep over live docs found 3 and no other) — runbook `^alloy` / ORPHAN/DRIFT prefixes otherwise clean |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | FIXED r1 (tests/test_alloy_runbook.py D3 test could not fail — mutant deleting the pass bullet green before, red after at :163; tests/test_monitoring_agent_template.py either-arm assertion) |
| Recurrence: denominator on every count — bounded searches state their bound | CLEAN (docs/reference/apis/EXTERNAL_SYSTEMS.md 143+6=149 re-derived; prometheus.yml grep -c job_name 19 on master and branch; master-side 17/16 prose filed W-ede94e4e) |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | CLEAN (docs/operations/promtail-to-alloy-runbook.md claims executed: compose rm -sf probe, alloy listener probe /proc/net/tcp, image curl/wget probe, keep-first and backup-move shell probes, D3 two-dot diff run; pytest 236 + 18 + 43 passed) |

Verdict grammar (the gate refuses anything else): `CLEAN (<the paths/lines hunted>)` — a CLEAN row
must name a path and run past 70 characters · `FIXED r<n> (<what changed>)` · `REFUTED (<the
disproving line>)` · `RECORDED — unexecuted (<why>)` · `RECORDED — measured (<why>)` ·
`RECORDED — hygiene false positive (<why>)` · `RECORDED — by design`, whose parentheses hold owner ids
only — each the owning row's first-cell id and the EARLIER round that adjudicated it, or a `D-nnn`
row of this checkout's ledger with no round, `;`-joined — with its reason AFTER the closing
parenthesis and an em dash (the § Residual block below shows the shape). Every OTHER RECORDED reason
is PARENTHESISED, never colon-delimited (a colon would spell the `unexecuted: N` counter the ledger
refuses). `UNCHECKED`
may survive only under a `## BLOCKED` escalation (a finding + 3 failed attempts).

## Pass Ledger

ONE table, one row per pass, counts punctuated (`found: F, new: N, confirmed: C, fixed: X,
unexecuted: U`) — the gate reads the LAST row as the exit round and refuses a second ledger group.
`found:` counts raw candidates, `new:` is prose the graders do not parse, `confirmed:` counts the
candidates EXECUTED and reproduced (the exit counter — a round is quiet at `confirmed: 0` and
`fixed: 0` with `unexecuted:` 0 or absent), `unexecuted:` counts code candidates RECORDED
unexecuted. Minimum two passes; the fixing pass is never the last; the closing pass re-derives
every count and anchor and says so in its Method cell, and its Finders cell names the seats that
read it by model token (`opus×1`, `sonnet×2`) — a round the orchestrator alone read cannot close.

| Pass | Finders | Counters | Method |
|---|---|---|---|
| Pass 1 | native sonnet×5 + haiku×6 | found: 77, new: 77, confirmed: 21, fixed: 21, unexecuted: 0 | method: citation — full partitioned pass, shape: agent-tool (D-961), waves of 3 (box_cap 3): slices A code/configs, B tests, C1 runbook/plan/restore, C2 infrastructure docs, D root/reference/ledgers, one per slice Sonnet + Haiku, plus one Haiku class seat X (master-added Promtail-as-live text outside the surface); every candidate executed or read by the orchestrator; seats: A-sonnet 0/4 · A-haiku 0/5 · X-haiku 3/24 · B-sonnet 2/5 · B-haiku 3/8 · C1-sonnet 5/5 · C1-haiku 1/6 · C2-sonnet 3/7 · C2-haiku 1/6 · D-sonnet 2/3 · D-haiku 1/4; hygiene run at start: 126 hits, INDEX table-parity 81 identical on master, template-residue are documented placeholders, stale-phrase in dated CHANGELOG/receipts — RECORDED — hygiene false positive; pin 88431016086a96e6f580240683556202 base 9f3061b8f; stop: confirmed 21; fix: +99 -34 lines for 21 confirmed (be296f364) |
| Pass 2 | native sonnet×5 | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | method: citation — delta over be296f364 plus one hop, the round-1 Sonnet owners resumed on their own ledgers: A 1/1, B 5/5, C2 4/4, D 5/5 absent; C1 6/6 absent plus N1-N3 (own-fix: round 1 — the mirror check blocked a retry, the hub remedy was one-directional, a stale backup survived a rollback); pin 3ceca899c728ed6d903f2906278b2bed; stop: confirmed 3; fix: +29 -16 lines for 3 confirmed (0d7c3e379) |
| Pass 3 | native sonnet×1 | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0 | method: citation — delta over 0d7c3e379, slice C1 owner: N1-N3 absent; N4-N6 (own-fix: round 2 — the noise-filter doc restated the old cp rollback, a half-done rollback could not be re-run, an unreachable retry branch); class rewrite — runbook step (a) mirror check and § 4 rollback (rounds 2, 3), done as a deletion; pin b16ca6a118cf9aec4973c41c573cc4ab; stop: scope-growth advisory; fix: +10 -9 lines for 3 confirmed (0a1bb593f) |
| Pass 4 | native sonnet×1 | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — closing pass over the scope-growth fixed set alone: the round-1 C1 owner re-executed N4-N6 against pin ec36b78cf109d29ed17ca448f2bc00a4 (all absent, nothing new); slices A, B, C2, D re-executed their whole ledgers at pass 2 and no fix touched them since; slices A 1/1 · B 5/5 · C1 12/12 · C2 4/4 · D 5/5; every class standing clean |

Row shapes (quoted here, so the gate does not read them as passes):

```text
| Pass 1 | native opus×1 + sonnet×2 | found: N, new: N, confirmed: C, fixed: X, unexecuted: U | method: citation |
| Pass 2 | native opus×1 + sonnet×2 | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation |
```

## Residual

Every candidate that did not enter `confirmed:` is recorded here, one row each, in the verdict
grammar of `/fabrik-review` § Phase 2 (the fenced block under the next heading is an EXAMPLE, never rows).

| Id | Verdict |
|---|---|
| A1 | REFUTED (scripts/audit/05-observability.sh is T04b's primary path; master 9f3061b8f still runs `--network coolify`, renamed 2026-05-31 — the hunk fixes a master defect in scope) |
| A2 | REFUTED (probe: `docker compose rm -sf promtail` on a profile-gated service, compose 2.40.3 — no container: rc 0; running container: stopped and removed, rc 0) |
| A3 | REFUTED (a restart inside the 15 s double sample is the failure the gate exists to catch; slower loops filed W-0913992c) |
| A4 | REFUTED (promtail stays a defined rollback service until Gate S, infra/vps1/monitoring/compose.yaml:27-33; a stopped promtail reads no false drift) |
| AH1 | RECORDED — by design (D-656) — plan ticket T04a renames promtail to alloy in configs/gatus/README.md and tests/test_alloy_watchers.py:121-127 pins that phrase |
| AH2 | REFUTED (rendered template example; master's vps3 header has the same `vps3 e.g. vps2` shape) |
| AH3 | REFUTED (same as A2, the executed probe) |
| AH4 | REFUTED (tests/test_alloy_configs.py ran, 4 passed 0 skipped: V1 byte-diffs config.alloy against `alloy convert`, V2 loads it under `alloy run`) |
| AH5 | REFUTED (probe: the grafana/alloy:v1.20.1 image has no curl or wget at /usr/bin or /bin, as proactive-check.sh:396-400 says) |
| AH6 | REFUTED (generate_vps_inventory.py and system-prompt.txt name promtail as the rollback service it stays until Gate S) |
| B1 | REFUTED (pytest -rs tests/test_alloy_configs.py: 4 passed, 0 skipped) |
| B3 | REFUTED (the runbook prescribes that worktree; fleet-alloy is fast-forwarded to the reviewed tip before the window is re-boarded) |
| B4 | REFUTED (IS_UP's status feeds the assertion message only; the assertion tests RC=1 and ERR:) |
| BH-B4 | REFUTED (pytest -rs tests/test_alloy_consumers.py -k live: 1 passed, 0 skipped) |
| BH-B5 | REFUTED (rc 128 means no git checkout to grade; in the repo the test runs) |
| BH-B6 | REFUTED (promtail is the rollback service until Gate S) |
| BH-B8 | RECORDED — measured (master's own test, not on this diff; filed W-ede94e4e) |
| BH-B9 | REFUTED (§ 2 delegates its steps to § 1 by design; step order is asserted on § 1 and § 3) |
| X2-X5, X8-X22, X24 | RECORDED — by design (D-651) — spec D3 sends agents-fabrik.md, .windsurf/rules/, CLAIMS.yaml and commands/_sources/ to infra by the runbook's mail after the window; x-origin probe: fork-era text |
| X7 | RECORDED — by design (D-651) — docs/reference/prebuilt-app-containers.md is already named in the runbook's infra mail |
| C1H-1 | REFUTED (docs describe the fleet after the window by design, spec D8; the branch merges only after it) |
| C1H-3 | REFUTED (fleet-alloy at 1105c9be3 is an ancestor of the reviewed tip and is fast-forwarded before the window) |
| C1H-4 | REFUTED (the EXECUTED plan's :56 cite anchors the promtail 256 row alloy sits beside) |
| C1H-5 | REFUTED (the EXECUTED plan's :738 cite opens the step-11 ship block :738-739) |
| C1H-6 | REFUTED (alloy takes promtail's D-1324 tier 0.5, docs/DECISIONS.md:1319) |
| C2-1b | RECORDED — measured (master-side: prometheus.yml has 19 job_name lines on master too; the 17/16 prose filed W-ede94e4e) |
| C2-3 | RECORDED — measured (master-side stale spoke-job lines, identical at 9f3061b8f; filed W-ede94e4e) |
| C2-5 | RECORDED — measured (ocoron-com counts true until the operator runs vps1_ocoron_removal.py; destination W-959a36f3) |
| C2-6 | REFUTED (spec measured 83 MiB under a 96 MiB cap, docs/superpowers/specs/2026-10-05-promtail-to-alloy-design.md:326) |
| C2H-1 | RECORDED — measured (master carries live rows under the same historical heading; filed W-ede94e4e) |
| C2H-4 | REFUTED (post-window truth by design, spec D8) |
| C2H-5 | REFUTED (probe: grafana/alloy:v1.20.1 with the pinned config lists one listener, :3039 = 12345) |
| C2H-6 | RECORDED — measured (master's own DOCKER-USER claim, same for node-exporter and cadvisor; filed W-ede94e4e) |
| C2H-7 | REFUTED (config.alloy's stage.json extracts `tag`, so the `{{.Name}}` tag is the one Alloy reads) |
| D3 | REFUTED (the branch merges after the window, so its entries sit atop `[Unreleased]`) |
| DH-C2 | REFUTED (post-window truth by design, spec D8) |
| DH-C3 | REFUTED (143 blocks + 6 retired rows = 149, re-derived by two seats) |
| DH-C4 | REFUTED (the `core/<pack>` shorthand is the repo convention) |
| HYG | RECORDED — hygiene false positive (INDEX table-parity identical on master; template-residue are documented placeholders; stale-phrase only in dated CHANGELOG entries and receipts) |

### Verdict grammar — an EXAMPLE, never rows

(quoted so no reader — human or scan — takes this template's own sample rows for the receipt's residuals):

```text
| F12 | RECORDED — unexecuted (3 probe attempts timed out) |
| F19 | RECORDED — by design (F4, round 3; D-203) — <why> |
| F31 | RECORDED — measured (a prevalence figure; makes no code or doc claim) |
```

`RECORDED — by design` names the OWNING row's first-cell id and the EARLIER round that adjudicated
it (or a `D-nnn` with no round); each `;`-part of a by-design parenthetical is an owner, never a
reason — the reason follows the closing parenthesis. What the gate refuses in a by-design verdict is the
message list of `check_review_coverage.py::_residual_errors`, read there and never restated here;
whether a `D-nnn` is a row of the ledger is checked only where `_ledger_ids` reads a `docs/DECISIONS.md`
with rows, and is not checked otherwise. `RECORDED — measured` and `RECORDED — unexecuted` never enter
`confirmed:`; `unexecuted:` on the closing row is what keeps an unexecuted CODE candidate from closing the loop.

## Per-phase verdicts

### Phase 0 — Establish scope: CLEAN
Surface master 9f3061b8f..0a1bb593f (80 paths), hub repo, synced paths reviewed through a fleet lens (templates/scaffold/docs/RESILIENCE_TEMPLATE.md one cell, correct for every project).

### Phase 1 — Independent finders: CLEAN
11 seats over 5 disjoint slices plus one class seat, all returned and adjudicated.

### Phase 2 — Execute every candidate: CLEAN
Every confirmed candidate reproduced (mutant, probe or pinned read); every refutation executed or cited.

### Phase 3 — Prove and fix: FIXED
27 confirmed across four rounds, all fixed in be296f364, 0d7c3e379, 0a1bb593f.

### Phase 4 — Converge: CONVERGED
Pass 4 quiet (confirmed 0), every slice verified, scope-growth stop honoured after round 3.

## Gate

`final_gate.py --check --json`, run in this worktree at the close:

```json
{
 "status": "success",
 "tier": 2,
 "passed": 57,
 "failed": 0,
 "skipped": 1,
 "skipped_checks": [
  "static tier"
 ],
 "advisory": [
  {
   "check": "Vendored Drift (sync-excluded repos)",
   "output": "⚠ check_vendored_drift ADVISORY — sync-excluded repos PULL, nothing is pushed to them; undeclared divergence below is invisible debt until someone opens it:\n  ⚠ fabrik-lib: 41 identical · 13 declared-design · 35 UNREVIEWED diff · 12 local-only\n    ⚠ fabrik-lib/scripts/enforcement/check_decisions_unique.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_doc_sprawl.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_duplicates.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_env_vars.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_feedback_duty.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_imports_resolvable.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fa\n… [truncated: ~26 line(s) omitted — tail follows — run `python scripts/enforcement/check_vendored_drift.py` for the FULL set; NEVER scope a fix to this preview] …\nre it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/.windsurf/rules/saas/95-multi-tenant-saas.md: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/review_rubric.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/mail.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist",
   "truncated": true,
   "omitted_lines": 26,
   "rerun": "python scripts/enforcement/check_vendored_drift.py"
  },
  {
   "check": "Routing Policy (operator deny + allowlist)",
   "output": "check_routing_policy: OK — 6 of 6 task kinds have a routing section, 30 routable model entries, all allowed and none denied",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Governance Tables (rules must render)",
   "output": "check_governance_tables: OK — every table row renders at its header width and no code span carries a table-escaped pipe across 2 contract(s) + 58 pack(s)",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Plan-lock release",
   "output": "0 stale | 0 likely-stale | 0 half-applied | 0 plan-field-stale | 0 orphan | 0 foreign | 0 unknown-status | 0 unevaluable\nOK - 0 stale of 102 plan lock(s) examined (3 non-terminal evaluated | 99 terminal/unevaluable | 0 foreign)",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Rivals dossier",
   "output": "",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Spec convergence",
   "output": "spec convergence: 68 CONVERGED spec(s) examined, 17 with findings (artifact-only; citations not re-fetched)\n  SILENT-1a: 2026-07-15-autonomous-factory-driver-design.md no cited source and no 'no external facts' statement - indistinguishable from skipping the research gate\n  ... 32 more finding(s) - rerun with --all, or name the spec(s)\n  -> run /fabrik-spec-review to a no-op; a spec with no external facts must SAY so, and a converged spec must enumerate its residual unknowns",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Rule grounding (plans)",
   "output": "rule grounding: 4 CONVERGED in-window plan(s) examined, 0 with findings (artifact-only; reading quality is the review's)",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Citations resolve (path:line lands)",
   "output": "",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Feedback duty",
   "output": "feedback duty: 271 close(s) in 14d, all carried a verdict",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Trigger routing (advertised phrase -> its own command)",
   "output": "WARN trigger routing: 0 phrase(s) reach a DIFFERENT command, 1 command(s) promise bare-prose routing no stem backs (of 163; 108 correct, 55 nowhere - not graded)\n  fabrik-reverse-engineer: promises bare-prose routing; no advertised phrase reaches it\n  -> add a NARROW stem above the broad one in skill_router.py KEYWORD_STEMS (a noun from the target's own domain in the same clause as the verb), or change the advertised phrase",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Corpus Weight (byte ratchet)",
   "output": "corpus-weight: CLAUDE.md 125220 B · baseline 98610 (+26610) · base origin/fleet-alloy-sync (—)\ncorpus-weight: templates/governance/CLAUDE.md 121430 B · baseline 91060 (+30370) · base origin/fleet-alloy-sync (—)\ncorpus-weight: commands/_sources 1228321 B · baseline 1053408 (+174913) · base origin/fleet-alloy-sync (—)\ncorpus-weight: commands/_fragments 221485 B · baseline 119777 (+101708) · base origin/fleet-alloy-sync (—)\ncorpus-weight: commands/_agents 41788 B · baseline 24465 (+17323) · base origin/fleet-alloy-sync (—)\ncorpus-weight: .windsurf/rules 1836680 B · baseline 1319893 (+516787) · base origin/fleet-alloy-sync (—)\ncorpus-weight: OK — no owned surface grew vs origin/fleet-alloy-sync\ncorpus-weight: worktree — reporting only, nothing written",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Frozen Chain (contract pins)",
   "output": "",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Data Contract Backing Legend",
   "output": "",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Mutation (opt-in FABRIK_MUTMUT)",
   "output": "MUTATION (advisory): skipped in the per-commit gate — mutation testing is diff-scoped + nightly (45-testing-strategy.md), not per-PR blocking. Run it on changed code with:\n    FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Doc stub fill",
   "output": "",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Script Coupling Header",
   "output": "",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "User-Level Hooks Registered",
   "output": "user-level hooks: present in every account dir",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Retired-Tech Tripwire",
   "output": "WARN: docs/CAPABILITIES.md:63: unmarked retired-tech mention: - [authelia](SERVICES.md) (owner: fleet): Authelia access-control rule provisioning for the Coolify-managed container.\nWARN: docs/CAPABILITIES.md:72: unmarked retired-tech mention: - [meilisearch](SERVICES.md) (owner: fleet): MeiliSearch index provisioning on the shared Coolify-managed instance.\nWARN: docs/CAPABILITIES.md:231: unmarked retired-tech mention: - [scripts/kilo_terminal_runner.py](../INDEX.md) (owner: infra): Kilo Terminal Runner - Rich TUI for Kilo CLI agent wrap\nWARN: docs/CONFIGURATION.md:990: unmarked retired-tech mention: DATABASE_URL = os.getenv('DATABASE_URL')  # Supabase provides this, for the exception path only\nWARN: docs/DEPLOYMENT_ARCHITECTURE.md:393: unmarked retired-tech mention: | `/etc/iptables/add-docker-user-rules.sh` | DOCKER-USER chain rules. Only 80/443 serve traffic; the script also RETURNs\nWARN: docs/DEPLOYMENT_ARCHITECTURE.md:424: unmarked retired-tech mention: - **Allowed public TCP ports:** 80, 443 (the only ports serving traffic). The iptables script also still allows 6001/600\nWARN: docs/DEPLOYMENT_ARCHITECTURE.md:469: unmarked retired-tech mention: | **Iptables DOCKER-USER** | All Docker ports | `/etc/iptables/add-docker-user-rules.sh`. 80/443 serve traffic; 6001/600\nWARN: docs/PROJECT_CATALOG.md:32: unmarked retired-tech mention: | **obsidian-agents** | Obsidian plugin: right-\n… [truncated: ~29 line(s) omitted — tail follows — run `python scripts/enforcement/check_retired_terms.py` for the FULL set; NEVER scope a fix to this preview] …\ntion: - **Kilo CLI Health Check** - `check_kilo_health.sh` (shared with Tier 2, `tier >= 2`)\nWARN: docs/workflows/FINAL_GATE_WORKFLOW.md:516: unmarked retired-tech mention: - `scripts/check_kilo_health.sh` — Kilo CLI Health Check (Tier 2/3; appended outside `run_optional_check` — appended dir\nWARN: docs/workstation/WSL2-DNS-FIX.md:24: unmarked retired-tech mention: 5. Node.js relies on `getaddrinfo()`, so Kilo CLI fails\nWARN: docs/workstation/WSL2-DNS-FIX.md:157: unmarked retired-tech mention: Verified by: Kilo CLI connectivity test\ncheck_retired_terms: 40 WARN(s) — advisory only, not blocking",
   "truncated": true,
   "omitted_lines": 29,
   "rerun": "python scripts/enforcement/check_retired_terms.py"
  },
  {
   "check": "Rule-pack reachability",
   "output": "⏭  Offline scaffold: python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt (provisioning not requested)\n⏭  Offline scaffold: python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt (provisioning not requested)\n⏭  Offline scaffold: python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt (provisioning not requested)\n  reachable: core/75-workers-jobs.md @ file-worker — via worker\n  reachable: core/app-audit-log.md @ saas-skeleton — via server/db/schema.sql\n  reachable: core/app-audit-log.md @ python-api — via db/schema.sql\n  reachable: core/app-audit-log.md @ python-api-gpu — via db/schema.sql\n  reachable: core/app-audit-log.md @ node-api — via db/schema.sql\n  reachable: core/app-audit-log.md @ file-api — via db/schema.sql\n  reachable: core/app-audit-log.md @ file-worker — via db/schema.sql\n  reachable: core/app-audit-log.md @ office-extension — via server/db/schema.sql\n  reachable: core/app-audit-log.md @ chrome-extension — via db/schema.sql\n  reachable: core/app-audit-log.md @ mobile-app — via db/schema.sql\n  reachable: core/app-audit-log.md @ desktop-app — via db/schema.sql\n  reachable: core/app-audit-log.md @ static-site — via server/db/schema.sql\n  reachable: core/app-audit-log.md @ docusaurus — via db/schema.sql\n  reachable: saas/88-saas-launch-checklist.md @ saas-skeleton — via app/(marketing)/terms\n  reachable: saas/95-multi-tena\n… [truncated: ~10 line(s) omitted — tail follows — run `python scripts/enforcement/check_pack_reachability.py` for the FULL set; NEVER scope a fix to this preview] …\noffice-extension\nCoordinator: open it as `CLAUDE_AGENT=coordinator claude -n probe-python-api-coordinator` in /tmp/pack-layout-audit-t60rhbbf/probe-python-api\nCoordinator: open it as `CLAUDE_AGENT=coordinator claude -n probe-python-api-gpu-coordinator` in /tmp/pack-layout-audit-wvd35nov/probe-python-api-gpu\nCoordinator: open it as `CLAUDE_AGENT=coordinator claude -n probe-saas-skeleton-coordinator` in /tmp/pack-layout-audit-ptw2hyq4/probe-saas-skeleton\nCoordinator: open it as `CLAUDE_AGENT=coordinator claude -n probe-static-site-coordinator` in /tmp/pack-layout-audit-4mfladui/probe-static-site",
   "truncated": true,
   "omitted_lines": 10,
   "rerun": "python scripts/enforcement/check_pack_reachability.py"
  },
  {
   "check": ".env.example Completeness",
   "output": "✅ .env.example check PASSED (no Python files)",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Phase Tests (plan-window)",
   "output": "WARNING: plan window f5a481f8..HEAD (docs/development/plans/2026-10-22-plan-1-least-operator-approval.md) declares 14 Behavior-Contract row(s) and touched 2 source file(s) with ZERO test changes. Per-row coverage is the phase-boundary /fabrik-review's to adjudicate; a window that CLOSES like this shipped behavior without tests.\n  declared: **Given** both contracts, **When** the grader reads the gate paragraph, **Then** each names the panel-decided classes (plan approval, Gate 1, Gate 2 to our own \n  declared: **Given** both contracts, **When** the grader reads the gate paragraph, **Then** each names the label `operator-kept:` with its five tokens, the spend-and-irrev\n  declared: **Given** the hub contract, **When** the grader reads § Autonomy, **Then** it cites D-1110, the clarifying-question, classifier and seat-steps-aside sentences, \n  declared: **Given** both contracts, **When** the grader compares their gate paragraphs, **Then** they are identical apart from \"hub D-054\" (A4)\n  declared: **Given** the template's hub-request bullet, **When** the grader reads it, **Then** it sends a gate to the panel or, when kept, to the operator through the coor\n  declared: **Given** `fabrik-deploy.md`, `fabrik-deploy-plan-review.md`, `fabrik-release.md`, `deploy-chain.md` and the NEXT map, **When** the grader reads them, **Then**,\n  declared: **Given** `design-gate-panel.md`, **When** the \n… [truncated: ~2 line(s) omitted — tail follows — run `python scripts/enforcement/check_phase_tests.py` for the FULL set; NEVER scope a fix to this preview] …\nhen** the hook parses it, **Then** it passes as `gate` (B2)\n  declared: **Given** autonomy mode and an unpaneled block carrying the label — written five ways: \"operator-kept: public\", \"Operator-kept: public\", \"**operator-kept:** pub\n  declared: **Given** autonomy mode and an unpaneled block naming spend (\"spend — $5 of API credits\", \"spend — inside the ceiling\") or \"irreversible — drop and recreate the\n  declared: **Given** autonomy mode OFF (a project repo), **When** the hook parses the B1 block and a block carrying `operator-kept: whatever`, **Then** each passes as toda\n  … and 2 more row(s)",
   "truncated": true,
   "omitted_lines": 2,
   "rerun": "python scripts/enforcement/check_phase_tests.py"
  },
  {
   "check": "Ticket Breadth (plan sets)",
   "output": "",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  }
 ],
 "blocking": 34,
 "checks": [
  {
   "name": "static tier (diff-sensed skip)",
   "outcome": "skipped"
  },
  {
   "name": "Convergence Evidence (plans + reviews)",
   "outcome": "pass"
  },
  {
   "name": "Coverage Checklist (reviews)",
   "outcome": "pass"
  },
  {
   "name": "Vendored Drift (sync-excluded repos)",
   "outcome": "advisory"
  },
  {
   "name": "Review hygiene",
   "outcome": "pass"
  },
  {
   "name": "Routing Policy (operator deny + allowlist)",
   "outcome": "advisory"
  },
  {
   "name": "Governance Tables (rules must render)",
   "outcome": "advisory"
  },
  {
   "name": "Certification Coverage (advisory; board mix-up BLOCKS)",
   "outcome": "pass"
  },
  {
   "name": "Plan-lock release",
   "outcome": "advisory"
  },
  {
   "name": "Rivals dossier",
   "outcome": "advisory"
  },
  {
   "name": "Spec convergence",
   "outcome": "advisory"
  },
  {
   "name": "Rule grounding (plans)",
   "outcome": "advisory"
  },
  {
   "name": "Citations resolve (path:line lands)",
   "outcome": "advisory"
  },
  {
   "name": "Feedback duty",
   "outcome": "advisory"
  },
  {
   "name": "Trigger routing (advertised phrase -> its own command)",
   "outcome": "advisory"
  },
  {
   "name": "Secrets (Zero Hardcoding)",
   "outcome": "pass"
  },
  {
   "name": "Hardcoded localhost/127.0.0.1 Ban",
   "outcome": "pass"
  },
  {
   "name": "Imports Resolvable (clean checkout)",
   "outcome": "pass"
  },
  {
   "name": "Lint Ratchet (repo-wide, no new debt)",
   "outcome": "pass"
  },
  {
   "name": "Corpus Weight (byte ratchet)",
   "outcome": "advisory"
  },
  {
   "name": "Frozen Chain (contract pins)",
   "outcome": "advisory"
  },
  {
   "name": "Data Contract Backing Legend",
   "outcome": "advisory"
  },
  {
   "name": "Doc Sync Matrix",
   "outcome": "pass"
  },
  {
   "name": "Subagent Flywheel (pool-or-declare — BLOCKING)",
   "outcome": "pass"
  },
  {
   "name": "Mutation (opt-in FABRIK_MUTMUT)",
   "outcome": "advisory"
  },
  {
   "name": "Doc stub fill",
   "outcome": "advisory"
  },
  {
   "name": "Script Coupling Header",
   "outcome": "advisory"
  },
  {
   "name": "Doc-Script Links",
   "outcome": "pass"
  },
  {
   "name": "Doc-Script Coverage (ratchet)",
   "outcome": "pass"
  },
  {
   "name": "Print/Console.log Ban",
   "outcome": "pass"
  },
  {
   "name": "No Host Ports on Traefik Services",
   "outcome": "pass"
  },
  {
   "name": "Full Traefik Label Set (§7)",
   "outcome": "pass"
  },
  {
   "name": "Spec <-> Project DB Name Match (Phase 1c)",
   "outcome": "pass"
  },
  {
   "name": "Mail Ownership Map (beat-owners.json)",
   "outcome": "pass"
  },
  {
   "name": "Undeclared Imports (requirements.txt)",
   "outcome": "pass"
  },
  {
   "name": "Fabrik-Synced Files Unmodified",
   "outcome": "pass"
  },
  {
   "name": "Project Structure",
   "outcome": "pass"
  },
  {
   "name": "Hooks Index Fresh",
   "outcome": "pass"
  },
  {
   "name": "MCP Scope (.mcp.json ⊆ ruling)",
   "outcome": "pass"
  },
  {
   "name": "User-Level Hooks Registered",
   "outcome": "advisory"
  },
  {
   "name": "Sync Trigger Coverage",
   "outcome": "pass"
  },
  {
   "name": "Doc Link Integrity (live tree)",
   "outcome": "pass"
  },
  {
   "name": "INDEX.md ↔ docs tree drift",
   "outcome": "pass"
  },
  {
   "name": "Retired-Tech Tripwire",
   "outcome": "advisory"
  },
  {
   "name": "Rule-pack reachability",
   "outcome": "advisory"
  },
  {
   "name": "Behavior Contract Proposal",
   "outcome": "pass"
  },
  {
   "name": "Plan-Set Contract (Spine+Tickets)",
   "outcome": "pass"
  },
  {
   "name": "Stage-Skip Artifact Gate (spec freshness + FROZEN header shape)",
   "outcome": "pass"
  },
  {
   "name": "README.md (Primary Entry Point)",
   "outcome": "pass"
  },
  {
   "name": ".env.example Completeness",
   "outcome": "advisory"
  },
  {
   "name": "User Guide Presence",
   "outcome": "pass"
  },
  {
   "name": "Phase Tests (plan-window)",
   "outcome": "advisory"
  },
  {
   "name": "Command Corpus (references resolve — BLOCKING)",
   "outcome": "pass"
  },
  {
   "name": "Ticket Breadth (plan sets)",
   "outcome": "advisory"
  },
  {
   "name": "Work items (sync)",
   "outcome": "pass"
  },
  {
   "name": "epic_order --check",
   "outcome": "pass"
  },
  {
   "name": "Kilo CLI Health Check",
   "outcome": "pass"
  }
 ],
 "failures": [],
 "warnings": [
  {
   "check": "static tier (diff-sensed skip)",
   "output": "⚠ static checks skipped — only .md files in the diff; this green asserts nothing about lint/type debt",
   "truncated": false,
   "omitted_lines": 0,
   "rerun": null
  },
  {
   "check": "Coverage Checklist (reviews)",
   "output": "⚠ check_review_coverage ADVISORY — committed review(s) needing attention:\n  ⚠ docs/development/reviews/2026-08-10-hub-governance-gates-review.md: COMMITTED with a non-quiet exit round (found: 10) — committing a review does not converge it. Finish the loop; BLOCKED-escalate the stuck finding (`## BLOCKED: <finding>` with its 3 attempts); when the LOOP itself failed (3 rounds of non-decreasing, nonzero `new:`), emit `## BLOCKED: NON-CONVERGENCE` naming the suspected foundation error; or mark the report `Status: IN-PROGRESS`.\n  ⚠ docs/development/reviews/2026-08-19-plan-1-kaizen-m1-event-stream-review.md: COMMITTED with a Pass-shaped ledger line that does not parse ('Pass 1 (WIDE) — finders: pool fanout ×3 (deepseek-v3.2 raised 9 on the') — punctuate the counts or fence the quote\n  ⚠ docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T01-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T02-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T03-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026\n… [truncated: ~13 line(s) omitted — tail follows — run `python scripts/enforcement/check_review_coverage.py` for the FULL set; NEVER scope a fix to this preview] …\nit `## BLOCKED: NON-CONVERGENCE` naming the suspected foundation error; or mark the report `Status: IN-PROGRESS`.\n  ⚠ docs/development/reviews/2026-10-09-w-b63ffe1a-gate-scope-wording-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\n  ⚠ docs/development/reviews/2026-10-18-seat-guard-network-review.md: COMMITTED as Status: IN-PROGRESS — the loop that opened it has not closed; finish it, or this line stands forever\ncheck_review_coverage: OK — 0 unproven coverage claims across 1 changed + 4 unintegrated review artifact(s)",
   "truncated": true,
   "omitted_lines": 13,
   "rerun": "python scripts/enforcement/check_review_coverage.py"
  },
  {
   "check": "Vendored Drift (sync-excluded repos)",
   "output": "⚠ check_vendored_drift ADVISORY — sync-excluded repos PULL, nothing is pushed to them; undeclared divergence below is invisible debt until someone opens it:\n  ⚠ fabrik-lib: 41 identical · 13 declared-design · 35 UNREVIEWED diff · 12 local-only\n    ⚠ fabrik-lib/scripts/enforcement/check_decisions_unique.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_doc_sprawl.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_duplicates.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_env_vars.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_feedback_duty.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/enforcement/check_imports_resolvable.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fa\n… [truncated: ~26 line(s) omitted — tail follows — run `python scripts/enforcement/check_vendored_drift.py` for the FULL set; NEVER scope a fix to this preview] …\nre it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/.windsurf/rules/saas/95-multi-tenant-saas.md: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/review_rubric.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    ⚠ fabrik-lib/scripts/mail.py: differs from hub with no declaration — debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist",
   "truncated": true,
   "omitted_lines": 26,
   "rerun": "python scripts/enforcement/check_vendored_drift.py"
  },
  {
   "check": "Work items (sync)",
   "output": "⚠ work-store drift (advisory until blocking):\nDRIFT 1 (advisory)  docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md\nDRIFT 1 (advisory)  docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md\nDRIFT 1 (advisory)  docs/superpowers/specs/2026-09-17-review-scoped-scope-growth-exit-design.md\nDRIFT 1 (advisory)  docs/superpowers/specs/2026-09-19-enforcement-git-decoder-design.md\nDRIFT 2 (blocking)  docs/development/plans/2026-10-06-plan-1-worktree-venv-isolation.md\nDRIFT 2 (blocking)  docs/development/plans/2026-10-14-plan-2-one-door-lane.md\nDRIFT 2 (blocking)  docs/development/plans/2026-10-15-plan-2-review-seat-write-isolation.md\nDRIFT 3 (blocking)  docs/development/plans/2026-09-06-plan-1-session-history-retention.md\nDRIFT 3 (blocking)  docs/development/plans/2026-10-25-plan-1-lean-command-corpus/2026-10-25-plan-1-lean-command-corpus.md\nDRIFT 4 (blocking)  docs/development/plans/2026-10-08-plan-1-promtail-to-alloy/2026-10-08-plan-1-promtail-to-alloy.md\nDRIFT 4 (blocking)  docs/development/plans/archived/2026-08-22-plan-1-fabrik-mail-loop-safety.md\nDRIFT 4 (blocking)  docs/development/plans/archived/2026-10-01-plan-1-docusaurus-static-runtime.md\nDRIFT 4 (blocking)  docs/development/plans/archived/2026-10-03-plan-1-scaffold-retired-agent-surface.md\nDRIFT 4 (blocking)  docs/development/plans/archived/2026-10-17-plan-1-command-centre-dashboard/2026\n… [truncated: ~16 line(s) omitted — tail follows — run `python scripts/work.py` for the FULL set; NEVER scope a fix to this preview] …\nads EXECUTED, and check_convergence then wants it to cite its whole-plan review under docs/development/reviews/ with a quiet Pass row (confirmed: 0); a superseded or abandoned plan moves to plans/archived/\nDRIFT 8 (advisory)  docs/development/plans/2026-10-02-plan-3-coordinator-assignment.md  — Status 'SUPERSEDED' is none of DRAFT, IN-PROGRESS, CONVERGED, EXECUTED, BLOCKED; a finished plan reads EXECUTED, and check_convergence then wants it to cite its whole-plan review under docs/development/reviews/ with a quiet Pass row (confirmed: 0); a superseded or abandoned plan moves to plans/archived/",
   "truncated": true,
   "omitted_lines": 16,
   "rerun": "python scripts/work.py"
  }
 ]
}
```
