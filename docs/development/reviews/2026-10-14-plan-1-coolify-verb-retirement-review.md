# Review — 2026-10-14-plan-1-coolify-verb-retirement

**Status:** CONVERGED
**Surface:** `git rev-parse HEAD` = 074617a865d9f22543a3c3b1d3965b1f24e3387c; range tip 074617a865d9f22543a3c3b1d3965b1f24e3387c; `git diff 8bd934f3d..HEAD -- src/fabrik/cli.py src/fabrik/registry.py tests/test_cli_apply_flags.py tests/test_projects_sync.py tests/test_reconcile_all_deployed_set.py tests/test_cli_status_live.py src/fabrik/orchestrator/__init__.py src/fabrik/orchestrator/deployer_ssh.py src/fabrik/orchestrator/rollback.py src/fabrik/orchestrator/context.py src/fabrik/state.py src/fabrik/config.py src/fabrik/health_app.py src/fabrik/drivers/__init__.py src/fabrik/drivers/postgres.py tests/orchestrator/test_refresh_infrastructure.py tests/orchestrator/test_deployer_probe.py tests/orchestrator/test_e2e_rollback.py tests/orchestrator/test_infrastructure.py tests/orchestrator/test_rollback.py tests/test_state.py tests/test_health_app.py src/fabrik/portability.py scripts/enforcement/check_health.py scripts/proof_run.py scripts/snapshot_vps_state.py scripts/update_vps_docs.py scripts/vps_sync.py tests/test_portability.py tests/test_proof_run_guard.py tests/test_hub_write_root.py compose.yaml .env.example README.md agents-fabrik.md docs/CONFIGURATION.md docs/DEPLOYMENT_ARCHITECTURE.md docs/SERVICES.md docs/TROUBLESHOOTING.md docs/operations/deployment.md docs/reference/apis/EXTERNAL_SYSTEMS.md docs/reference/architecture.md docs/reference/fabrik-cli-reference.md docs/reference/health-monitoring.md docs/reference/modules/deployment-orchestrator.md docs/reference/modules/drivers.md docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md docs/FEATURES.md docs/development/capability-defects.md` md5 bdb7f7d2678f6b4d8e1a805821e6f51c (350934 bytes)
**Command:** /fabrik-review · **Changed:** `src/fabrik/cli.py`, `src/fabrik/registry.py`, `tests/test_cli_apply_flags.py`, `tests/test_projects_sync.py`, `tests/test_reconcile_all_deployed_set.py`, `tests/test_cli_status_live.py`, `src/fabrik/orchestrator/__init__.py`, `src/fabrik/orchestrator/deployer_ssh.py`, `src/fabrik/orchestrator/rollback.py`, `src/fabrik/orchestrator/context.py`, `src/fabrik/state.py`, `src/fabrik/config.py`, `src/fabrik/health_app.py`, `src/fabrik/drivers/__init__.py`, `src/fabrik/drivers/postgres.py`, `tests/orchestrator/test_refresh_infrastructure.py`, `tests/orchestrator/test_deployer_probe.py`, `tests/orchestrator/test_e2e_rollback.py`, `tests/orchestrator/test_infrastructure.py`, `tests/orchestrator/test_rollback.py`, `tests/test_state.py`, `tests/test_health_app.py`, `src/fabrik/portability.py`, `scripts/enforcement/check_health.py`, `scripts/proof_run.py`, `scripts/snapshot_vps_state.py`, `scripts/update_vps_docs.py`, `scripts/vps_sync.py`, `tests/test_portability.py`, `tests/test_proof_run_guard.py`, `tests/test_hub_write_root.py`, `compose.yaml`, `.env.example`, `README.md`, `agents-fabrik.md`, `docs/CONFIGURATION.md`, `docs/DEPLOYMENT_ARCHITECTURE.md`, `docs/SERVICES.md`, `docs/TROUBLESHOOTING.md`, `docs/operations/deployment.md`, `docs/reference/apis/EXTERNAL_SYSTEMS.md`, `docs/reference/architecture.md`, `docs/reference/fabrik-cli-reference.md`, `docs/reference/health-monitoring.md`, `docs/reference/modules/deployment-orchestrator.md`, `docs/reference/modules/drivers.md`, `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md`, `docs/FEATURES.md`, `docs/development/capability-defects.md`
**Plan:** `docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md`

## Coverage Checklist

Rubric invocation (verbatim output — the gate reads the generated header, never a prose mention):

```text
$ python scripts/review_rubric.py --changed src/fabrik/cli.py src/fabrik/registry.py tests/test_cli_apply_flags.py tests/test_projects_sync.py tests/test_reconcile_all_deployed_set.py tests/test_cli_status_live.py src/fabrik/orchestrator/__init__.py src/fabrik/orchestrator/deployer_ssh.py src/fabrik/orchestrator/rollback.py src/fabrik/orchestrator/context.py src/fabrik/state.py src/fabrik/config.py src/fabrik/health_app.py src/fabrik/drivers/__init__.py src/fabrik/drivers/postgres.py tests/orchestrator/test_refresh_infrastructure.py tests/orchestrator/test_deployer_probe.py tests/orchestrator/test_e2e_rollback.py tests/orchestrator/test_infrastructure.py tests/orchestrator/test_rollback.py tests/test_state.py tests/test_health_app.py src/fabrik/portability.py scripts/enforcement/check_health.py scripts/proof_run.py scripts/snapshot_vps_state.py scripts/update_vps_docs.py scripts/vps_sync.py tests/test_portability.py tests/test_proof_run_guard.py tests/test_hub_write_root.py compose.yaml .env.example README.md agents-fabrik.md docs/CONFIGURATION.md docs/DEPLOYMENT_ARCHITECTURE.md docs/SERVICES.md docs/TROUBLESHOOTING.md docs/operations/deployment.md docs/reference/apis/EXTERNAL_SYSTEMS.md docs/reference/architecture.md docs/reference/fabrik-cli-reference.md docs/reference/health-monitoring.md docs/reference/modules/deployment-orchestrator.md docs/reference/modules/drivers.md docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md docs/FEATURES.md docs/development/capability-defects.md
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

### ai/50-agentic.md  (hit: src/fabrik/orchestrator/__init__.py, src/fabrik/orchestrator/context.py, src/fabrik/orchestrator/deployer_ssh.py)
- is never the only thing between the agent and an irreversible act.
- **Auth boundary.** Agents run on the subscription's OAuth through the unmodified CLI, never `ANTHROPIC_API_KEY` (ai/00). Never pass `bare=True` on that lane: bare mode never reads OAuth credentials and fails with "Not logged in". A deployed service declares `shape.uses_claude_cli` and mounts the rotated `~/.claude`, never a static token. Anthropic's terms say subscription OAuth is for ordinary, individual use of Claude Code and its own apps; developers building products or services, including with the Agent SDK, should use an API key, and Anthropic does not permit routing requests through Free, Pro or Max credentials on behalf of their users, reserving the right to enforce that without notice. The operator's own development and automation through the unmodified CLI is the closest fit to that … (wrapped further — read the pack)
- output, and some models never return them. Pick the rate per model from the bake-off browser (hub-only), using its tools chip.

### core/10-python.md  (hit: scripts/enforcement/check_health.py, scripts/proof_run.py, scripts/snapshot_vps_state.py)
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

### core/40-documentation.md  (hit: README.md, agents-fabrik.md, docs/CONFIGURATION.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In the hub (`/opt/fabrik`) `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it there; change the generator. A project has no such generator; an `llms.txt` it ships, hand-written or built by its own code, is its own.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/orchestrator/test_deployer_probe.py, tests/orchestrator/test_e2e_rollback.py, tests/orchestrator/test_infrastructure.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
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

### core/55-observability.md  (hit: docs/reference/health-monitoring.md, src/fabrik/health_app.py)
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

### core/58-resilience.md  (hit: docs/reference/health-monitoring.md, src/fabrik/health_app.py)
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

### core/self-healing.md  (hit: docs/reference/health-monitoring.md, src/fabrik/health_app.py)
- AGENT USAGE: Pick the failure class, walk the ladder top-to-bottom, stop at the first step that resolves. Never invent a step. Never skip a step. -->
- [`60-watchdog`](60-watchdog.md) — the escalation engine and the owner of its tiers. Tier A acts automatically (it registers `restart_container`, `clear_file_cache`, `scale_concurrency`, `pause_worker`); Tier B is opt-in; Tier C escalates — and carries the **approved-write lane** (`drop_queue_items`, `rotate_locks`), off by default; **Tier D** (opt-in, Telegram-gated) applies a tested code fix with auto-rollback. ⚠️ Registered is not runnable — see **What the sidecar can execute today** below.
- Each row reads left-to-right: **Symptom** (an observable signal) → **First response** (a `58-resilience` primitive or the module that implements it) → **Fallback** (another primitive or a `60-watchdog` action) → **Escalate** (operator-bound). The agent picks the row matching the active failure, walks left-to-right, and **stops at the first step that resolves**. Never skip rightward.
| 11 | **Postgres allocation registry drift** (HUB-side, not a service: a database in `pg_database` with no `allocations.json` entry) | the hourly drift cron (`scripts/audit_all_registrars.py`) finds a database no registry row claims | Additive reconcile (`src/fabrik/registry_reconcile.py`, D-500): registers it in-lock, never overwrites or deletes; `report` (writes nothing) unless the cron line sets `FABRIK_REGISTRY_RECONCILE=apply` | Refuse, never guess, and write nothing: a name two specs claim is counted as `fabrik_registry_heal_total{outcome="shared"}`; any other refusal (an incomplete claim map, an unresolved owner, an error) as `fabrik_registry_heal_failed{spec_id,db,reason}` | `FabrikRegistryHealFailed` (a `heal_failed` refusal standing 2 h; a shared claim alerts on neither) or `FabrikAuditStale` (no clean audit run in 3 h, or none recorded) — `configs/prometheus/rules/fabrik-drift.yml` |
**⚠️ Row 10 is NOT the deadman timer, and the difference is the whole point.** The Tier-C deadman below (`spec.watchdog.deadman_timeout_seconds`, 60–3600, default 300 s, rendered as `WATCHDOG_DEADMAN_TIMEOUT`) measures **operator silence** — it arms only
- **What the sidecar can execute today:** the model returns each action with its params, and `check_proposal` refuses anything off the offered menu, or with a bad or missing param, before a side effect (fabrik-lib D-412). The model's menu is `restart_container` + `escalate_apprise` until the spec lists more in `watchdog.llm_actions` (fabrik-lib D-412): `clear_file_cache` and `pause_worker` (Tier A) run once listed; `wipe_redis_cache` and `reset_db_pool` (Tier B, port defaulting to 8000) run once listed AND `auto_tier_b: true`. `scale_concurrency`, `drop_queue_items`, `rotate_locks` and `install_log_drop_rule` are never offered, and `create_fix_pr` has its own lane (`propose_fix_prs`) — this ladder names three of the never-offered ones (`scale_concurrency` and `drop_queue_items` in row 2, `rotate_locks` in row 8): in those rows the watchdog step resolves to Tier C escalate plus the deadman restart. Treat each row's first response as the step that actually heals.
- If a failure class doesn't appear in the table above, the rule is: **add the row to this pack first, then the response logic to the code.** Never silently invent a self-healing response — it'll diverge from the operator's mental model and break the ladder's discipline.
- 4. **Self-healing without a visible signal.** A pause flag, breaker, or rate-limit reject that doesn't increment a counter and emit a structured log line is invisible — when it misfires, you can't tell. Every ladder step MUST emit a counter AND a `structlog.info()` (or `pino.info()`) row carrying the resource name + reason; without that, the next operator audit has no way to tell the difference between "step fired and recovered" and "step never ran". **Tier-D steps (stabilize / remediate / apply / rollback) are held to the same bar:** each MUST emit a counter + structured log AND write the `incidents` / `approvals` / `deploys` tables — an unaudited or irreversible code-remediation is not self-healing, it's an unreviewed deploy.
- 2. **Fallback — `pause-state` (Redis-backed).** When `signups_per_ip_per_minute` for a specific IP stays high after the first defense's per-IP cap fires, the worker emits an incident; the watchdog sidecar reads the inbox and proposes Tier A `pause_worker` with `resource=signup_<ip_hash>` (the action accepts `^[a-z][a-z0-9_]{0,31}$` and a TTL of 5–3600 s, so truncate the hash to fit — and it is unreachable today, above, so until upstream carries parameters the app sets this pause itself with `pause_state.set_global_pause(...)`). Every signup-handling worker checks `pause_state.is_paused("signup_<ip_hash>")` from the vendored fabrik-lib `pause-state` (the scaffold's own `pause_state.py` has no `is_paused`), with `PAUSE_KEY_PREFIX` equal to `<project_id>:pause:`, and bails without touching the DB. Never gate other workers on `is_globally_paused()` while per-IP keys share the prefix — it reports ANY key under it, so one IP would stop them all.
- [ ] The per-project ladder does not count on a watchdog step that is never offered (`scale_concurrency`, `drop_queue_items`, `rotate_locks`): each such row's healing step is the app's own first response, and the doc says the watchdog step escalates. If the approved-write lane is wanted once it is reachable, the project `.env` sets `WATCHDOG_ALLOW_DB_WRITES=true` and the RW DSN is provisioned.

# promote-to-check_*: 164 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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
- `expo-secure-store`
- `shape.is_admin_dashboard: true` `two_factor` `fabrik apply` `/health` `/metrics` `saas/60-saas-ui.md` `shape.has_bearer_api: true` `two_factor`
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `plpgsql` `CLAIMS.yaml` `fleet-postgres-main-no-pgvector` `postgres-main`
```

| Class | Status |
|---|---|
| Hunt: `src/fabrik/cli.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (src/fabrik/cli.py: `projects --status` help names both registry vocabularies — ready/development from `fabrik scan`, production/development/archived/paused from --sync; the status verb's redundant non-dict guard went with state.load's new contract; apply/status/reconcile-all/import options checked against the reference doc by two seats) |
| Hunt: `src/fabrik/registry.py` — every changed hunk, its enclosing function, its callers | CLEAN (Project/from_dict/to_dict carry no coolify keys and a row holding them loads its other fields unchanged; read whole by the S1 Haiku seat — src/fabrik/registry.py) |
| Hunt: `tests/test_cli_apply_flags.py` — every changed hunk, its enclosing function, its callers | CLEAN (every patch target resolves and the four retired apply flags each exit 2; 72 S1 tests pass on the pinned copy, run by both S1 seats — tests/test_cli_apply_flags.py) |
| Hunt: `tests/test_projects_sync.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (tests/test_projects_sync.py: the help grader now asserts both vocabularies and was run RED against HEAD's unfixed cli.py in a throwaway worktree, then green) |
| Hunt: `tests/test_reconcile_all_deployed_set.py` — every changed hunk, its enclosing function, its callers | CLEAN (the refresh probe-routing, host-error and basename graders at :334-:448 kill the Opus seat's M1 and M6 mutants; the 17-case exit matrix matches cli.py — tests/test_reconcile_all_deployed_set.py) |
| Hunt: `tests/test_cli_status_live.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (tests/test_cli_status_live.py: the odd-shapes docstring no longer claims state.load returns any JSON; the record-not-an-object case still drives the verb through CliRunner) |
| Hunt: `src/fabrik/orchestrator/__init__.py` — every changed hunk, its enclosing function, its callers | CLEAN (refresh_infrastructure swaps hosts only around the probe walk, raises naming the host on a probe error and sets app_name from the matched app_dir; the Opus seat killed 9 named mutants over this file and deployer_ssh.py — src/fabrik/orchestrator/__init__.py) |
| Hunt: `src/fabrik/orchestrator/deployer_ssh.py` — every changed hunk, its enclosing function, its callers | CLEAN (probe_app and list_compose_projects quote every path (a `a b'c;$(id)` directory probed without injection), _host_env restores on every exit path and vps1 is a no-op; V2 true — src/fabrik/orchestrator/deployer_ssh.py) |
| Hunt: `src/fabrik/orchestrator/rollback.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (src/fabrik/orchestrator/rollback.py: the Raises clause and the Phase-4i comment no longer claim _rollback_dns raises RollbackError — since the Coolify handler went every handler is best-effort; a coolify resource still falls to the unknown-type warning, V7 true) |
| Hunt: `src/fabrik/orchestrator/context.py` — every changed hunk, its enclosing function, its callers | CLEAN (the app_name/coolify_uuid alias is consistent with its callers; grep of the module finds only the historical key — src/fabrik/orchestrator/context.py) |
| Hunt: `src/fabrik/state.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (src/fabrik/state.py: load returns None for a non-object or non-UTF-8 record — its callers in status, destroy --use-state and audit-registrars all call .get — proven red-first by five parametrised cases; the coolify_uuid description now says spec name on apply, matched /opt directory on refresh) |
| Hunt: `src/fabrik/config.py` — every changed hunk, its enclosing function, its callers | CLEAN (only VPS_HOST and VPS_USER of compose.yaml's six env entries are read here, no COOLIFY_* setting survives — src/fabrik/config.py) |
| Hunt: `src/fabrik/health_app.py` — every changed hunk, its enclosing function, its callers | CLEAN (/health aggregates checks.dns alone and returns 200/503; V5 true by the Opus seat's run — src/fabrik/health_app.py) |
| Hunt: `src/fabrik/drivers/__init__.py` — every changed hunk, its enclosing function, its callers | CLEAN (no CoolifyClient import or __all__ entry; every `import fabrik.drivers.<x>` resolves — src/fabrik/drivers/__init__.py) |
| Hunt: `src/fabrik/drivers/postgres.py` — every changed hunk, its enclosing function, its callers | CLEAN (T07a's docstring-only change; no behaviour touched, grep finds no Coolify call — src/fabrik/drivers/postgres.py) |
| Hunt: `tests/orchestrator/test_refresh_infrastructure.py` — every changed hunk, its enclosing function, its callers | CLEAN (the app_dir walk and fallback graders pass; the host-error and spoke branches a seat called untested are graded in tests/test_reconcile_all_deployed_set.py — tests/orchestrator/test_refresh_infrastructure.py) |
| Hunt: `tests/orchestrator/test_deployer_probe.py` — every changed hunk, its enclosing function, its callers | CLEAN (candidate order, /opt-parent rule and _host_env restore are graded; 184 S2 tests pass on the pinned copy — tests/orchestrator/test_deployer_probe.py) |
| Hunt: `tests/orchestrator/test_e2e_rollback.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (tests/orchestrator/test_e2e_rollback.py: the mocked-client docstring no longer says a DNS error flips the final state to FAILED or calls _rollback_dns a hard stop) |
| Hunt: `tests/orchestrator/test_infrastructure.py` — every changed hunk, its enclosing function, its callers | CLEAN (T07a's coolify-parameter removals only; the suite passes on the pinned copy — tests/orchestrator/test_infrastructure.py) |
| Hunt: `tests/orchestrator/test_rollback.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (tests/orchestrator/test_rollback.py:412 comment no longer calls the dns handler a hard stop) |
| Hunt: `tests/test_state.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (tests/test_state.py adds test_load_returns_none_for_a_record_that_is_not_a_json_object over array, string, number, null and non-UTF-8 records — four of the five failed before the fix) |
| Hunt: `tests/test_health_app.py` — every changed hunk, its enclosing function, its callers | CLEAN (the dns-only /health contract is asserted for 200 and 503 — tests/test_health_app.py) |
| Hunt: `src/fabrik/portability.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (src/fabrik/portability.py: import_bundle finds manifest.json and secrets-redacted.json through one ./-normalised member map, so a `tar -C dir .` bundle reports its manifest and secrets; _collect_state's docstring says the compose app name is re-derived from the spec on import, as spec D9 words it) |
| Hunt: `scripts/enforcement/check_health.py` — every changed hunk, its enclosing function, its callers | CLEAN (fleet-synced; GOOD_PATTERNS drops check_coolify, which no file in the pin calls; T09's run found 0 of 37 fleet /health handlers change verdict — scripts/enforcement/check_health.py) |
| Hunt: `scripts/proof_run.py` — every changed hunk, its enclosing function, its callers | CLEAN (worker_running reads probe_app's exists/ps/error keys; the apply argv carries no retired flag; never executed, read and graded by tests/test_proof_run_guard.py — scripts/proof_run.py) |
| Hunt: `scripts/snapshot_vps_state.py` — every changed hunk, its enclosing function, its callers | CLEAN (diff() skips a legacy snapshot's coolify key without error; no Coolify call remains — scripts/snapshot_vps_state.py) |
| Hunt: `scripts/update_vps_docs.py` — every changed hunk, its enclosing function, its callers | CLEAN (ssh argv read, no Coolify column or call remains; never executed — scripts/update_vps_docs.py) |
| Hunt: `scripts/vps_sync.py` — every changed hunk, its enclosing function, its callers | CLEAN (the 10-point audit wording matches its 10 sections and CONTAINER_COUNT_PATTERN accepts the reworded count; the meilisearch exact-name lookup replaced a label R1 measured absent on vps1 — scripts/vps_sync.py) |
| Hunt: `tests/test_portability.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (tests/test_portability.py adds test_dot_slash_manifest_and_secrets_are_read, red against the raw-name lookup, green after; 36 tests pass) |
| Hunt: `tests/test_proof_run_guard.py` — every changed hunk, its enclosing function, its callers | CLEAN (the worker, replica, restarting and no-spec cases pass on the pinned copy (99 S3 tests, 2 seats) — tests/test_proof_run_guard.py) |
| Hunt: `tests/test_hub_write_root.py` — every changed hunk, its enclosing function, its callers | CLEAN (the vps-status pin matches vps_sync's count output; 30 of 30 pass once the gitignored scratch file is force-tracked in the copy — tests/test_hub_write_root.py) |
| Hunt: `compose.yaml` — every changed hunk, its enclosing function, its callers | CLEAN (four COOLIFY_* env lines removed, no required variable left unset; the remaining six entries are read by config and other modules — compose.yaml) |
| Hunt: `.env.example` — every changed hunk, its enclosing function, its callers | CLEAN (no COOLIFY_* line among its 432 lines; docs/CONFIGURATION.md:57-60 counts the nine removed names, verified against the pre-change file — .env.example) |
| Hunt: `README.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (README.md export paragraph words the pre-retirement sample without the `26 apps` a bundle can no longer carry; README.md:9 checked by both S4 seats) |
| Hunt: `agents-fabrik.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (agents-fabrik.md state-driven destroy bullet drops the nonexistent --keep-files flag; cli.py hard-codes keep_files=True) |
| Hunt: `docs/CONFIGURATION.md` — every changed hunk, its enclosing function, its callers | CLEAN (status, reconcile-all, projects --sync and logs described as they run; the nine removed COOLIFY_* names counted against the pre-change .env.example — docs/CONFIGURATION.md) |
| Hunt: `docs/DEPLOYMENT_ARCHITECTURE.md` — every changed hunk, its enclosing function, its callers | CLEAN (nine CLI line anchors match the cli.py def lines; its registrar counts and :525 anchor predate the plan and are recorded on W-44c60d21 — docs/DEPLOYMENT_ARCHITECTURE.md) |
| Hunt: `docs/SERVICES.md` — every changed hunk, its enclosing function, its callers | CLEAN (the six unimported driver modules and the removed-modules sentence checked against src/fabrik/drivers — docs/SERVICES.md) |
| Hunt: `docs/TROUBLESHOOTING.md` — every changed hunk, its enclosing function, its callers | CLEAN (spec_generator.py:381 and :548 anchors match; removed files named as removed — docs/TROUBLESHOOTING.md) |
| Hunt: `docs/operations/deployment.md` — every changed hunk, its enclosing function, its callers | CLEAN (reconcile-all is a live command with its dry-run default; the rollback coolify type falls to the unknown-type warning per rollback.py — docs/operations/deployment.md) |
| Hunt: `docs/reference/apis/EXTERNAL_SYSTEMS.md` — every changed hunk, its enclosing function, its callers | CLEAN (the DNS row cites DeploymentOrchestrator._provision_dns at orchestrator/__init__.py:574 and agents-fabrik.md:142 — docs/reference/apis/EXTERNAL_SYSTEMS.md) |
| Hunt: `docs/reference/architecture.md` — every changed hunk, its enclosing function, its callers | CLEAN (module counts 20 and 25 re-counted by ls; pipeline step d names add_subdomain — docs/reference/architecture.md) |
| Hunt: `docs/reference/fabrik-cli-reference.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (docs/reference/fabrik-cli-reference.md: import documents --apply, not the nonexistent --real-run (a CliRunner run of --real-run exits 2); the reconcile-all section states the Compose deployed rule and the exit contract from cli.py's docstring) |
| Hunt: `docs/reference/health-monitoring.md` — every changed hunk, its enclosing function, its callers | CLEAN (/health reports the DNS manager alone, matching health_app.py:74 — docs/reference/health-monitoring.md) |
| Hunt: `docs/reference/modules/deployment-orchestrator.md` — every changed hunk, its enclosing function, its callers | CLEAN (the banner names deployer_coolify.py removed at 9c02e8c86; its infrastructure.py:136-147 anchor predates the plan and is recorded on W-44c60d21 — docs/reference/modules/deployment-orchestrator.md) |
| Hunt: `docs/reference/modules/drivers.md` — every changed hunk, its enclosing function, its callers | CLEAN (25 modules and 16 test modules re-counted; the preflight row matches preflight.py — docs/reference/modules/drivers.md) |
| Hunt: `docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md` — every changed hunk, its enclosing function, its callers | CLEAN (destroy flags match cli.py's destroy options; scaffold tables say Compose — docs/workflows/FABRIK_SCAFFOLD_WORKFLOW.md) |
| Hunt: `docs/FEATURES.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (docs/FEATURES.md: the state-consumer table gains fabrik status and fabrik projects --sync rows, the reconcile-all bullet states the Compose deployed rule and exit contract, and the destroy Phase 2 bullet drops --keep-files) |
| Hunt: `docs/development/capability-defects.md` — every changed hunk, its enclosing function, its callers | CLEAN (regenerated by scripts/audit_capability_docs.py from the current capabilities.json; no Coolify row remains — docs/development/capability-defects.md) |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | FIXED r1 (state.load now fails closed to None on a non-object or non-UTF-8 record instead of raising or returning a list; rollback.py's docstrings now say every handler is best-effort, which is the code's real behaviour — src/fabrik/state.py, src/fabrik/orchestrator/rollback.py) |
| Recurrence: cost/quota accounting — pool units scored, native seats counted, a limit at its edges | CLEAN (no metered calls on this surface; nine native finder seats stamped with dispatch --seats 9 and four re-verify seats with --seats 4 — scripts/command_run.py record of this run) |
| Recurrence: boundary/sentinel/prefix — an off-by-one, a sentinel value, a prefix-vs-exact match | FIXED r1 (the `./` member-name prefix: import_bundle normalised names for sections and legacy but looked up the manifest and secrets by raw name; one normalised map now serves all three — src/fabrik/portability.py) |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | FIXED r1 (state.load's non-object and non-UTF-8 cases and the ./ manifest lookup gained red-first graders; the refresh host-error and spoke branches were already graded in tests/test_reconcile_all_deployed_set.py, proven by the Opus seat's named mutant kills) |
| Recurrence: denominator on every count — bounded searches state their bound | CLEAN (V8 census 0 of 1373 tracked files under src, scripts, tests and templates, 908 of them .py; vulture 0 items; 1321 passed and 2 skipped in the plan test set; 0 of 69 spec stems differ from their id) |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | CLEAN (every confirmed candidate was reproduced by a command — the ./ bundle probe, the UnicodeDecodeError probe, a CliRunner run of --real-run — and every fix proven by a red run before its green — commands in the Pass Ledger) |

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
| Pass 1 | native opus×1 + sonnet×4 + haiku×4 | found: 36, new: 36, confirmed: 11, fixed: 11, unexecuted: 0 | method: citation — shape: agent-tool; whole-plan Finish review over the ten ticket commits e7057ec0a..074617a86 (baseline 8bd934f3d), file partition S1 cli verbs (6 files), S2 orchestrator/state/rollback (16), S3 portability and the hub VPS scripts (11), S4 docs (16); one Sonnet and one Haiku per slice plus the plan's Opus floor on S2; the orchestrator executed every candidate (the ./ bundle probe, the UnicodeDecodeError probe, a CliRunner run of --real-run) and refuted the refresh-untested claim against tests/test_reconcile_all_deployed_set.py:334-448; confirmed S1 1, S2 3, S3 2, S4 5, all fixed with red-first graders where code changed; plan test set 1321 passed, 2 skipped; stop: open claims S1 0/1, S2 0/3, S3 0/2, S4 0/5 |
| Pass 2 | native opus×1 + sonnet×3 | found: 5, new: 5, confirmed: 3, fixed: 3, unexecuted: 0 | method: re-derivation — the round-1 seats re-verified their own slices over pin 17867ba3f and the fix diff (md5 e6aa4799): S1 1/1 and S3 2/2 hold (S3 mutant-proven), S2 2/3 and S4 4/5; 3 confirmed, all own-fix (round 1): state.py's parenthetical missed the /opt/fabrik-<name> case, rollback.py's "No handler raises" overstated and sat after Args, and agents-fabrik.md:413 kept a --keep-files clause; round-zero probe — every state.load caller read, the status verb's stale ANY-JSON comment and test docstring corrected · mirrors: 3 read; stop: open claims S2 1, S4 1 |
| Pass 3 | native opus×1 + sonnet×1 | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — the round-1 S2 Opus and S4 Sonnet seats re-verified their open claims over pin 59d40008a and the round-2 fix diff (md5 cab4a8ec): state.py's parenthetical re-derived from app_dir's three candidate shapes by an executed probe, rollback.py's best-effort paragraph proven by patching every driver to raise (0 of 14 resource types raised), agents-fabrik.md:413 checked clause by clause against cli.py destroy and destroyer.destroy_from_state; slices S1 1/1, S2 3/3, S3 2/2, S4 5/5; 0 new defects in either fix hunk; stop: closable |

Row shapes (quoted here, so the gate does not read them as passes):

```text
| Pass 1 | native opus×1 + sonnet×2 | found: N, new: N, confirmed: C, fixed: X, unexecuted: U | method: citation |
| Pass 2 | native opus×1 + sonnet×2 | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation |
```

## Residual

Every candidate that did not enter `confirmed:` is recorded here, one row each, in the verdict
grammar of `/fabrik-review` § Phase 2 (the fenced block under the next heading is an EXAMPLE, never rows).

### Verdict grammar — an EXAMPLE, never rows

(quoted so no reader — human or scan — takes this template's own sample rows for the receipt's residuals):

```text
| F12 | RECORDED — unexecuted (3 probe attempts timed out) |
| F19 | RECORDED — by design (F4, round 3; D-203) — <why> |
| F31 | RECORDED — measured (a prevalence figure; makes no code or doc claim) |
```

`RECORDED — by design` names the OWNING row's first-cell id and the EARLIER round that adjudicated
it (or a `D-nnn` with no round); each `;`-part of a by-design parenthetical is an owner, never a
reason — the reason follows the closing parenthesis. The gate refuses an absent owner, a `D-nnn` this
checkout's `docs/DECISIONS.md` has no row for, and a round that is not below the closing `Pass N`. `RECORDED — measured` and `RECORDED — unexecuted` never enter `confirmed:`;
`unexecuted:` on the closing row is what keeps an unexecuted CODE candidate from closing the loop.

| R1 | REFUTED (refresh_infrastructure's host-error raise and spoke-only probe swap are graded at tests/test_reconcile_all_deployed_set.py:334-448; the S2 Opus seat killed both mutants by name) |
| R2 | REFUTED (docs naming 9c02e8c86 dangle only on a squash merge; this branch reaches master through scripts/merge_request.py:946, a `git merge --no-ff`, so the commit stays reachable) |
| R3 | REFUTED (scripts/enforcement/check_health.py dropping check_coolify: no file in the pin calls it and T09's run over 37 fleet /health handlers changed 0 verdicts) |
| R4 | REFUTED (docs/development/capability-defects.md losing the fabrik_synced_manifest.py row: the file is generated by scripts/audit_capability_docs.py and capabilities.json now marks that script ok) |
| R5 | REFUTED (tests/test_state.py's null case does not exercise the new non-object branch — JSON null already loads as None — but it pins the None path and costs nothing; kept, labelled by its id) |
| R6 | RECORDED — measured (scripts/vps_sync.py's meilisearch lookup by exact container name replaced a label filter that R1 measured absent on vps1 (781e95b43); the empty-match silence is on backlog W-44c60d21) |
| R7 | RECORDED — measured (portability._collect_authelia keeps the Coolify-era volume paths as fallbacks after /opt/authelia/config; spec D6 defers them to U5) |
| R8 | RECORDED — measured (registrar counts in fabrik-cli-reference.md (7), DEPLOYMENT_ARCHITECTURE.md, README.md and deployment-orchestrator.md (9) disagree with _REGISTRAR_ORDER's 10, and two infrastructure.py:136 anchors are stale; pre-existing — backlog W-44c60d21) |
| R9 | RECORDED — measured (apply records coolify_uuid as the spec name and refresh as the matched directory, and apply's inject_env targets /opt/<spec name>; deploy-side, pre-existing — backlog W-44c60d21) |
| R10 | RECORDED — measured (a spoke app with glitchtip fails refresh because verify_dsn_injection runs docker inspect on the hub; T03 made spoke refresh reachable — backlog W-1ee6341d) |
| R11 | RECORDED — measured (scripts/sync_projects.py and portability._collect_state call .get/.pop on a non-object state file; specs/services/wpf.yaml:36 and scripts/provision_glitchtip_project.sh still name COOLIFY_API_*; probe_app's cd runs before sudo; proof_run's worker proof is single-shot; reconcile-all --filter matches the file stem; audit-registrars' join breaks on a null registrar — backlog W-44c60d21) |
| R12 | RECORDED — measured (destroy --use-state on a corrupt state file prints "No state file" though the file exists; it still exits 1 — backlog W-44c60d21) |
| R13 | RECORDED — measured (src/fabrik/state.py:27 says refresh records "the matched /opt directory" where the code records its basename (orchestrator/__init__.py:519); wording only, outside round 2's fix hunks — backlog W-44c60d21) |
| R14 | RECORDED — measured (orchestrator/destroyer.py has no HANDLER_FUNCS entry for watchdog, so destroy --use-state over a record listing it reports an error action and skips the state archive; pre-existing — backlog W-44c60d21) |

## Per-phase verdicts

### Phase 1 — Finish review of plan 2026-10-14-plan-1-coolify-verb-retirement: PASS — the ten ticket commits re-read as one change across four slices; 14 confirmed defects (11 in round 1, 3 own-fix in round 2) fixed — state.load fails closed on a non-object or undecodable record, import reads ./-prefixed bundles, the projects --status help names both vocabularies, rollback and state docstrings match the code, and five doc gaps closed; V8 census 0 of 1373, vulture 0 items, plan test set 1321 passed and 2 skipped.

## Gate

`final_gate.py --check --json`, pasted verbatim (check_convergence reads the fenced
`"status": "success"`). Close order per `/fabrik-review` § Reporting: run it while this receipt reads
`Status: IN-PROGRESS`, paste it here, flip to CONVERGED, re-run and paste that run in place of the first:

```json
{
  "status": "success",
  "tier": 2,
  "passed": 69,
  "failed": 0,
  "skipped": 3,
  "skipped_checks": [
    "bandit scripts/",
    "semgrep",
    "pytest"
  ],
  "advisory": [
    {
      "check": "pytest (NOT RUN)",
      "output": "this repo's CI does not invoke pytest, so the gate does not either \u2014 PERMANENT, not a per-diff skip. Deliberate (a CI that never reds has no red to prevent, and a hub-scale suite would brick every completion gate), but it means THIS GREEN ASSERTS NOTHING ABOUT THE TEST SUITE. Run it yourself: `python -m pytest tests/ -q`, or make the gate run it every time with `mkdir -p .fabrik && touch .fabrik/run-pytest` \u2014 required if this repo retires its GitHub workflows, since deleting them otherwise disarms this check \u2014 the suite is OUTSIDE this gate",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Vendored Drift (sync-excluded repos)",
      "output": "\u26a0 check_vendored_drift ADVISORY \u2014 sync-excluded repos PULL, nothing is pushed to them; undeclared divergence below is invisible debt until someone opens it:\n  \u26a0 fabrik-lib: 50 identical \u00b7 11 declared-design \u00b7 28 UNREVIEWED diff \u00b7 13 local-only\n    \u26a0 fabrik-lib/scripts/enforcement/check_decisions_unique.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/enforcement/check_doc_sprawl.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/enforcement/check_duplicates.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/enforcement/check_env_vars.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/enforcement/check_feedback_duty.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/enforcement/check_imports_resolvable.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fa\n\u2026 [truncated: ~19 line(s) omitted \u2014 tail follows \u2014 run `python scripts/enforcement/check_vendored_drift.py` for the FULL set; NEVER scope a fix to this preview] \u2026\nor declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/.windsurf/rules/core/self-healing.md: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/review_rubric.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/mail.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist",
      "truncated": true,
      "omitted_lines": 19,
      "rerun": "python scripts/enforcement/check_vendored_drift.py"
    },
    {
      "check": "Routing Policy (operator deny + allowlist)",
      "output": "check_routing_policy: OK \u2014 6 of 6 task kinds have a routing section, 30 routable model entries, all allowed and none denied",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Governance Tables (rules must render)",
      "output": "check_governance_tables: OK \u2014 every table row renders at its header width across 2 contract(s)",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Plan-lock release",
      "output": "",
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
      "output": "spec convergence: 56 CONVERGED spec(s) examined, 17 with findings (artifact-only; citations not re-fetched)\n  SILENT-1a: 2026-07-15-autonomous-factory-driver-design.md no cited source and no 'no external facts' statement - indistinguishable from skipping the research gate\n  ... 32 more finding(s) - rerun with --all, or name the spec(s)\n  -> run /fabrik-spec-review to a no-op; a spec with no external facts must SAY so, and a converged spec must enumerate its residual unknowns",
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
      "output": "\u26a0 check_citations_resolve ADVISORY \u2014 12 citation(s) do not land, of 105 examined across 3 docs (a wrong `path:line` reads as verified and is not) \u2014 105 graded of 144 found (5 bare filename, 22 ambiguous, 12 not under root /opt/fabrik/.claude/worktrees/fleet):\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET vps_sync.py:412 (\u2192 scripts/vps_sync.py) \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET cli.py:1581 (\u2192 src/fabrik/cli.py) \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET cli.py:1581 (\u2192 src/fabrik/cli.py) \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BEYOND-EOF scripts/proof_run.py:843 (file has 833 lines)\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET cli.py:1581 (\u2192 src/fabrik/cli.py) \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET deployer_ssh.py:122 (\u2192 src/fabrik/orchestrator/deployer_ssh.py) \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coo\n\u2026 [truncated: ~2 line(s) omitted \u2014 tail follows \u2014 run `python scripts/enforcement/check_citations_resolve.py` for the FULL set; NEVER scope a fix to this preview] \u2026\n-retirement.md: BLANK-TARGET src/fabrik/orchestrator/__init__.py:435 \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET rollback.py:40 (\u2192 src/fabrik/orchestrator/rollback.py) \u2192 ''\n   - docs/development/reviews/2026-10-14-plan-1-coolify-verb-retirement-review.md: BLANK-TARGET infrastructure.py:136 (\u2192 src/fabrik/orchestrator/infrastructure.py) \u2192 ''\n   - docs/development/reviews/2026-10-14-plan-1-coolify-verb-retirement-review.md: BLANK-TARGET infrastructure.py:136 (\u2192 src/fabrik/orchestrator/infrastructure.py) \u2192 ''",
      "truncated": true,
      "omitted_lines": 2,
      "rerun": "python scripts/enforcement/check_citations_resolve.py"
    },
    {
      "check": "Feedback duty",
      "output": "feedback duty: 24 close(s) in 14d, all carried a verdict",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Trigger routing (advertised phrase -> its own command)",
      "output": "trigger routing: 157 advertised phrase(s) - 108 reach their own command, 49 route nowhere, 0 mis-routed (sees whether an advertised phrase reaches its own command; cannot tell whether the phrase is one an operator would ever type, and deliberately does not grade phrases that route nowhere)",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Corpus Weight (byte ratchet)",
      "output": "corpus-weight: CLAUDE.md 116596 B \u00b7 baseline 98610 (+17986) \u00b7 base origin/worktree-fleet (\u2014)\ncorpus-weight: templates/governance/CLAUDE.md 112878 B \u00b7 baseline 91060 (+21818) \u00b7 base origin/worktree-fleet (\u2014)\ncorpus-weight: commands/_sources 1211373 B \u00b7 baseline 1053408 (+157965) \u00b7 base origin/worktree-fleet (\u2014)\ncorpus-weight: commands/_fragments 195430 B \u00b7 baseline 119777 (+75653) \u00b7 base origin/worktree-fleet (\u2014)\ncorpus-weight: commands/_agents 32568 B \u00b7 baseline 24465 (+8103) \u00b7 base origin/worktree-fleet (\u2014)\ncorpus-weight: .windsurf/rules 1803492 B \u00b7 baseline 1319893 (+483599) \u00b7 base origin/worktree-fleet (\u2014)\ncorpus-weight: OK \u2014 no owned surface grew vs origin/worktree-fleet\ncorpus-weight: worktree \u2014 reporting only, nothing written",
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
      "output": "MUTATION (advisory): skipped in the per-commit gate \u2014 mutation testing is diff-scoped + nightly (45-testing-strategy.md), not per-PR blocking. Run it on changed code with:\n    FABRIK_MUTMUT=1 python scripts/enforcement/check_mutation.py",
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
      "output": "WARN: docs/CAPABILITIES.md:63: unmarked retired-tech mention: - [authelia](SERVICES.md) (owner: fleet): Authelia access-control rule provisioning for the Coolify-managed container.\nWARN: docs/CAPABILITIES.md:72: unmarked retired-tech mention: - [meilisearch](SERVICES.md) (owner: fleet): MeiliSearch index provisioning on the shared Coolify-managed instance.\nWARN: docs/CAPABILITIES.md:228: unmarked retired-tech mention: - [scripts/kilo_terminal_runner.py](../INDEX.md) (owner: infra): Kilo Terminal Runner - Rich TUI for Kilo CLI agent wrap\nWARN: docs/CONFIGURATION.md:859: unmarked retired-tech mention: DATABASE_URL = os.getenv('DATABASE_URL')  # Supabase provides this, for the exception path only\nWARN: docs/DEPLOYMENT_ARCHITECTURE.md:390: unmarked retired-tech mention: | `/etc/iptables/add-docker-user-rules.sh` | DOCKER-USER chain rules. Only 80/443 serve traffic; the script also RETURNs\nWARN: docs/DEPLOYMENT_ARCHITECTURE.md:421: unmarked retired-tech mention: - **Allowed public TCP ports:** 80, 443 (the only ports serving traffic). The iptables script also still allows 6001/600\nWARN: docs/DEPLOYMENT_ARCHITECTURE.md:466: unmarked retired-tech mention: | **Iptables DOCKER-USER** | All Docker ports | `/etc/iptables/add-docker-user-rules.sh`. 80/443 serve traffic; 6001/600\nWARN: docs/PROJECT_CATALOG.md:32: unmarked retired-tech mention: | **obsidian-agents** | Obsidian plugin: right-\n\u2026 [truncated: ~28 line(s) omitted \u2014 tail follows \u2014 run `python scripts/enforcement/check_retired_terms.py` for the FULL set; NEVER scope a fix to this preview] \u2026\ntion: - **Kilo CLI Health Check** - `check_kilo_health.sh` (shared with Tier 2, `tier >= 2`)\nWARN: docs/workflows/FINAL_GATE_WORKFLOW.md:515: unmarked retired-tech mention: - `scripts/check_kilo_health.sh` \u2014 Kilo CLI Health Check (Tier 2/3; appended outside `run_optional_check` \u2014 appended dir\nWARN: docs/workstation/WSL2-DNS-FIX.md:24: unmarked retired-tech mention: 5. Node.js relies on `getaddrinfo()`, so Kilo CLI fails\nWARN: docs/workstation/WSL2-DNS-FIX.md:150: unmarked retired-tech mention: Verified by: Kilo CLI connectivity test\ncheck_retired_terms: 39 WARN(s) \u2014 advisory only, not blocking",
      "truncated": true,
      "omitted_lines": 28,
      "rerun": "python scripts/enforcement/check_retired_terms.py"
    },
    {
      "check": "Rule-pack reachability",
      "output": "reachable: core/75-workers-jobs.md @ file-worker \u2014 via worker\n  reachable: core/app-audit-log.md @ saas-skeleton \u2014 via server/db/schema.sql\n  reachable: core/app-audit-log.md @ python-api \u2014 via db/schema.sql\n  reachable: core/app-audit-log.md @ python-api-gpu \u2014 via db/schema.sql\n  reachable: core/app-audit-log.md @ node-api \u2014 via db/schema.sql\n  reachable: core/app-audit-log.md @ file-api \u2014 via db/schema.sql\n  reachable: core/app-audit-log.md @ file-worker \u2014 via db/schema.sql\n  reachable: core/app-audit-log.md @ office-extension \u2014 via server/db/schema.sql\n  reachable: core/app-audit-log.md @ chrome-extension \u2014 via db/schema.sql\n  reachable: core/app-audit-log.md @ mobile-app \u2014 via db/schema.sql\n  reachable: core/app-audit-log.md @ desktop-app \u2014 via db/schema.sql\n  reachable: core/app-audit-log.md @ static-site \u2014 via server/db/schema.sql\n  reachable: core/app-audit-log.md @ docusaurus \u2014 via db/schema.sql\n  reachable: saas/88-saas-launch-checklist.md @ saas-skeleton \u2014 via app/(marketing)/terms\n  reachable: saas/95-multi-tenant-saas.md @ saas-skeleton \u2014 via server/src/fastapi_user_auth/rls\nExamined 4 pack(s) / 15 claim-pair(s) declaring applies_to for a checked type (of 13 scaffold type(s) checked).\nOK \u2014 every VERIFIABLE applies_to claim reaches at least one emitted path (15 of 4 examined pack(s) verified).",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": ".env.example Completeness",
      "output": "\u2705 .env.example check PASSED (no new env vars)",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Phase Tests (plan-window)",
      "output": "PHASE-TESTS (advisory): OK \u2014 no active plan window shipping behavior without tests.",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Ticket Breadth (plan sets)",
      "output": "\u26a0 TICKET BREADTH \u2014 13 of 13 ticket(s) graded score \u2265 5 independent risk classes (advisory)\n  T01 (/opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T01-deployer-helpers.md): score 9\n    components: areas=1 (src) [+1 test surface(s), not counted] \u00b7 behaviors=8 \u00b7 code+governance mix=no\n    predicted review cost: ~4-14 rounds (basis: this repo's review ledgers \u2014 4.2 rounds/plan (n=14/22, max 16); per-ticket receipts n=14 give rounds ~= 1.0 x score (spread 0.3x-1.6x))\n    split: split the 8 Behavior-Contract rows into tickets of <=2 behaviours each (one review class apiece)\n  T03 (/opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T03-reconcile-all-rebase.md): score 9\n    components: areas=1 (src) [+1 test surface(s), not counted] \u00b7 behaviors=8 \u00b7 code+governance mix=no\n    predicted review cost: ~4-14 rounds (basis: this repo's review ledgers \u2014 4.2 rounds/plan (n=14/22, max 16); per-ticket receipts n=14 give rounds ~= 1.0 x score (spread 0.3x-1.6x))\n    split: split the 8 Behavior-Contract rows into tickets of <=2 behaviours each (one review class apiece)\n  T02 (/opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T02-status-rebase.md): score 8\n    components: areas=1 (src) [+1 test surface(s), not counted] \u00b7 behaviors=7 \u00b7 code+governa\n\u2026 [truncated: ~41 line(s) omitted \u2014 tail follows \u2014 run `python scripts/enforcement/check_ticket_breadth.py` for the FULL set; NEVER scope a fix to this preview] \u2026\nticket receipts n=14 give rounds ~= 1.0 x score (spread 0.3x-1.6x))\n    split: split the 4 Behavior-Contract rows into tickets of <=2 behaviours each (one review class apiece)\n  Calibration honesty: in the n=14 retroactive set, 2 of 4 flags with round receipts matched a ticket that actually ran >=4 rounds (score-vs-rounds Spearman rho=0.45). Treat a flag as a prompt to LOOK, not a verdict.\n  Advisory only \u2014 the threshold is provisional (docs/reference/ticket-breadth.md). Narrowing is the operator's call.\n\u26a0 TICKET BREADTH \u2014 13 of 13 ticket(s) graded score \u2265 5 independent risk classes (advisory)",
      "truncated": true,
      "omitted_lines": 41,
      "rerun": "python scripts/enforcement/check_ticket_breadth.py"
    }
  ],
  "blocking": 44,
  "checks": [
    {
      "name": "ruff-format (--check)",
      "outcome": "pass"
    },
    {
      "name": "ruff",
      "outcome": "pass"
    },
    {
      "name": "check json",
      "outcome": "pass"
    },
    {
      "name": "check yaml",
      "outcome": "pass"
    },
    {
      "name": "mypy",
      "outcome": "pass"
    },
    {
      "name": "bandit",
      "outcome": "pass"
    },
    {
      "name": "bandit scripts/ (diff-sensed skip \u2014 no scripts/ changes)",
      "outcome": "skipped"
    },
    {
      "name": "semgrep (NOT RUN \u2014 timed out after 30s)",
      "outcome": "skipped"
    },
    {
      "name": "pytest (NOT RUN)",
      "outcome": "skipped"
    },
    {
      "name": "sqlfluff-lint",
      "outcome": "pass"
    },
    {
      "name": "vulture",
      "outcome": "pass"
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
      "name": "Schema Sync (DB Models)",
      "outcome": "pass"
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
      "name": "Decision Ledger (unique ids)",
      "outcome": "pass"
    },
    {
      "name": "Subagent Flywheel (pool-or-declare \u2014 BLOCKING)",
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
      "name": "Full Traefik Label Set (\u00a77)",
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
      "name": "MCP Scope (.mcp.json \u2286 ruling)",
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
      "name": "INDEX.md \u2194 docs tree drift",
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
      "name": "Command Corpus (references resolve \u2014 BLOCKING)",
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
      "check": "Coverage Checklist (reviews)",
      "output": "\u26a0 check_review_coverage ADVISORY \u2014 committed review(s) needing attention:\n  \u26a0 docs/development/reviews/2026-08-10-hub-governance-gates-review.md: COMMITTED with a non-quiet exit round (found: 10) \u2014 committing a review does not converge it. Finish the loop; BLOCKED-escalate the stuck finding (`## BLOCKED: <finding>` with its 3 attempts); when the LOOP itself failed (3 rounds of non-decreasing, nonzero `new:`), emit `## BLOCKED: NON-CONVERGENCE` naming the suspected foundation error; or mark the report `Status: IN-PROGRESS`.\n  \u26a0 docs/development/reviews/2026-08-19-plan-1-kaizen-m1-event-stream-review.md: COMMITTED with a Pass-shaped ledger line that does not parse ('Pass 1 (WIDE) \u2014 finders: pool fanout \u00d73 (deepseek-v3.2 raised 9 on the') \u2014 punctuate the counts or fence the quote\n  \u26a0 docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T01-review.md: COMMITTED as Status: IN-PROGRESS \u2014 the loop that opened it has not closed; finish it, or this line stands forever\n  \u26a0 docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T02-review.md: COMMITTED as Status: IN-PROGRESS \u2014 the loop that opened it has not closed; finish it, or this line stands forever\n  \u26a0 docs/development/reviews/2026-08-25-plan-1-inert-rule-packs-T03-review.md: COMMITTED as Status: IN-PROGRESS \u2014 the loop that opened it has not closed; finish it, or this line stands forever\n  \u26a0 docs/development/reviews/2026\n\u2026 [truncated: ~13 line(s) omitted \u2014 tail follows \u2014 run `python scripts/enforcement/check_review_coverage.py` for the FULL set; NEVER scope a fix to this preview] \u2026\nerge it. Finish the loop; BLOCKED-escalate the stuck finding (`## BLOCKED: <finding>` with its 3 attempts); when the LOOP itself failed (3 rounds of non-decreasing, nonzero `new:`), emit `## BLOCKED: NON-CONVERGENCE` naming the suspected foundation error; or mark the report `Status: IN-PROGRESS`.\n  \u26a0 docs/development/reviews/2026-10-09-w-b63ffe1a-gate-scope-wording-review.md: COMMITTED as Status: IN-PROGRESS \u2014 the loop that opened it has not closed; finish it, or this line stands forever\ncheck_review_coverage: OK \u2014 0 unproven coverage claims across 1 changed + 3 unintegrated review artifact(s)",
      "truncated": true,
      "omitted_lines": 13,
      "rerun": "python scripts/enforcement/check_review_coverage.py"
    },
    {
      "check": "Vendored Drift (sync-excluded repos)",
      "output": "\u26a0 check_vendored_drift ADVISORY \u2014 sync-excluded repos PULL, nothing is pushed to them; undeclared divergence below is invisible debt until someone opens it:\n  \u26a0 fabrik-lib: 50 identical \u00b7 11 declared-design \u00b7 28 UNREVIEWED diff \u00b7 13 local-only\n    \u26a0 fabrik-lib/scripts/enforcement/check_decisions_unique.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/enforcement/check_doc_sprawl.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/enforcement/check_duplicates.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/enforcement/check_env_vars.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/enforcement/check_feedback_duty.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/enforcement/check_imports_resolvable.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fa\n\u2026 [truncated: ~19 line(s) omitted \u2014 tail follows \u2014 run `python scripts/enforcement/check_vendored_drift.py` for the FULL set; NEVER scope a fix to this preview] \u2026\nor declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/.windsurf/rules/core/self-healing.md: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/review_rubric.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist\n    \u26a0 fabrik-lib/scripts/mail.py: differs from hub with no declaration \u2014 debt or design, nobody knows. Re-vendor it, or declare it in .fabrik/vendored-divergence-allowlist",
      "truncated": true,
      "omitted_lines": 19,
      "rerun": "python scripts/enforcement/check_vendored_drift.py"
    },
    {
      "check": "Citations resolve (path:line lands)",
      "output": "\u26a0 check_citations_resolve ADVISORY \u2014 12 citation(s) do not land, of 105 examined across 3 docs (a wrong `path:line` reads as verified and is not) \u2014 105 graded of 144 found (5 bare filename, 22 ambiguous, 12 not under root /opt/fabrik/.claude/worktrees/fleet):\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET vps_sync.py:412 (\u2192 scripts/vps_sync.py) \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET cli.py:1581 (\u2192 src/fabrik/cli.py) \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET cli.py:1581 (\u2192 src/fabrik/cli.py) \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BEYOND-EOF scripts/proof_run.py:843 (file has 833 lines)\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET cli.py:1581 (\u2192 src/fabrik/cli.py) \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET deployer_ssh.py:122 (\u2192 src/fabrik/orchestrator/deployer_ssh.py) \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coo\n\u2026 [truncated: ~2 line(s) omitted \u2014 tail follows \u2014 run `python scripts/enforcement/check_citations_resolve.py` for the FULL set; NEVER scope a fix to this preview] \u2026\n-retirement.md: BLANK-TARGET src/fabrik/orchestrator/__init__.py:435 \u2192 ''\n   - docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md: BLANK-TARGET rollback.py:40 (\u2192 src/fabrik/orchestrator/rollback.py) \u2192 ''\n   - docs/development/reviews/2026-10-14-plan-1-coolify-verb-retirement-review.md: BLANK-TARGET infrastructure.py:136 (\u2192 src/fabrik/orchestrator/infrastructure.py) \u2192 ''\n   - docs/development/reviews/2026-10-14-plan-1-coolify-verb-retirement-review.md: BLANK-TARGET infrastructure.py:136 (\u2192 src/fabrik/orchestrator/infrastructure.py) \u2192 ''",
      "truncated": true,
      "omitted_lines": 2,
      "rerun": "python scripts/enforcement/check_citations_resolve.py"
    },
    {
      "check": "Imports Resolvable (clean checkout)",
      "output": "\u26a0 scripts/.archive/2026-06-17-coolify-era-cleanup/delete_uptime_kuma.py: imports 'fabrik.drivers.coolify', which resolves ONLY via a path NOT IN THE REPO '/opt/fabrik/src/fabrik/drivers/coolify.py'. It exists on this machine and NOT in the repository \u2014 a PHANTOM DEPENDENCY. It will ModuleNotFoundError in CI and in the deployed container. Dev tooling only \u2014 never deployed. Guard the import if you want it silent.\nOK: no phantom (gitignored-only) imports in src/tests \u2014 5898 imports checked",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "INDEX.md \u2194 docs tree drift",
      "output": "\u26a0 added code file not in INDEX.md: .fabrik/work/W-1ee6341d.json (Doc Sync Matrix: File added/removed/renamed \u2192 INDEX.md; the row must name the PATH, not just the basename)",
      "truncated": false,
      "omitted_lines": 0,
      "rerun": null
    },
    {
      "check": "Plan-Set Contract (Spine+Tickets)",
      "output": "\u26a0 [plan_tickets] /opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T10b-root-docs.md: commit 074617a8 touches T10b's Touches without an 'Agent-Task: T10b' trailer\n  \u2192 Fix: Ticket work lands with its own Agent-Task trailer (the same-commit Board-flip discipline)\n\u26a0 [plan_tickets] /opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T11-integration.md: commit 074617a8 touches T11's Touches without an 'Agent-Task: T11' trailer\n  \u2192 Fix: Ticket work lands with its own Agent-Task trailer (the same-commit Board-flip discipline)\n\u26a0 [plan_tickets] /opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T04-projects-sync-rebase.md: commit 9c02e8c8 touches T04's Touches without an 'Agent-Task: T04' trailer\n  \u2192 Fix: Ticket work lands with its own Agent-Task trailer (the same-commit Board-flip discipline)\n\u26a0 [plan_tickets] /opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T05-apply-legacy-retired.md: commit 9c02e8c8 touches T05's Touches without an 'Agent-Task: T05' trailer\n  \u2192 Fix: Ticket work lands with its own Agent-Task trailer (the same-commit Board-flip discipline)\n\u26a0 [plan_tickets] /opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T10a-reference-\n\u2026 [truncated: ~34 line(s) omitted \u2014 tail follows \u2014 run `python scripts/enforcement/check_plan_tickets.py` for the FULL set; NEVER scope a fix to this preview] \u2026\nclaude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T10a-reference-docs.md: commit 51ec71ae touches T10a's Touches without an 'Agent-Task: T10a' trailer\n  \u2192 Fix: Ticket work lands with its own Agent-Task trailer (the same-commit Board-flip discipline)\n\u26a0 [plan_tickets] /opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T10b-root-docs.md: commit 51ec71ae touches T10b's Touches without an 'Agent-Task: T10b' trailer\n  \u2192 Fix: Ticket work lands with its own Agent-Task trailer (the same-commit Board-flip discipline)",
      "truncated": true,
      "omitted_lines": 34,
      "rerun": "python scripts/enforcement/check_plan_tickets.py"
    },
    {
      "check": "Ticket Breadth (plan sets)",
      "output": "\u26a0 TICKET BREADTH \u2014 13 of 13 ticket(s) graded score \u2265 5 independent risk classes (advisory)\n  T01 (/opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T01-deployer-helpers.md): score 9\n    components: areas=1 (src) [+1 test surface(s), not counted] \u00b7 behaviors=8 \u00b7 code+governance mix=no\n    predicted review cost: ~4-14 rounds (basis: this repo's review ledgers \u2014 4.2 rounds/plan (n=14/22, max 16); per-ticket receipts n=14 give rounds ~= 1.0 x score (spread 0.3x-1.6x))\n    split: split the 8 Behavior-Contract rows into tickets of <=2 behaviours each (one review class apiece)\n  T03 (/opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T03-reconcile-all-rebase.md): score 9\n    components: areas=1 (src) [+1 test surface(s), not counted] \u00b7 behaviors=8 \u00b7 code+governance mix=no\n    predicted review cost: ~4-14 rounds (basis: this repo's review ledgers \u2014 4.2 rounds/plan (n=14/22, max 16); per-ticket receipts n=14 give rounds ~= 1.0 x score (spread 0.3x-1.6x))\n    split: split the 8 Behavior-Contract rows into tickets of <=2 behaviours each (one review class apiece)\n  T02 (/opt/fabrik/.claude/worktrees/fleet/docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/T02-status-rebase.md): score 8\n    components: areas=1 (src) [+1 test surface(s), not counted] \u00b7 behaviors=7 \u00b7 code+governa\n\u2026 [truncated: ~41 line(s) omitted \u2014 tail follows \u2014 run `python scripts/enforcement/check_ticket_breadth.py` for the FULL set; NEVER scope a fix to this preview] \u2026\nticket receipts n=14 give rounds ~= 1.0 x score (spread 0.3x-1.6x))\n    split: split the 4 Behavior-Contract rows into tickets of <=2 behaviours each (one review class apiece)\n  Calibration honesty: in the n=14 retroactive set, 2 of 4 flags with round receipts matched a ticket that actually ran >=4 rounds (score-vs-rounds Spearman rho=0.45). Treat a flag as a prompt to LOOK, not a verdict.\n  Advisory only \u2014 the threshold is provisional (docs/reference/ticket-breadth.md). Narrowing is the operator's call.\n\u26a0 TICKET BREADTH \u2014 13 of 13 ticket(s) graded score \u2265 5 independent risk classes (advisory)",
      "truncated": true,
      "omitted_lines": 41,
      "rerun": "python scripts/enforcement/check_ticket_breadth.py"
    },
    {
      "check": "Work items (sync)",
      "output": "\u26a0 work-store drift (advisory until blocking):\nDRIFT 1 (advisory)  docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md\nDRIFT 1 (advisory)  docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md\nDRIFT 1 (advisory)  docs/superpowers/specs/2026-09-17-review-scoped-scope-growth-exit-design.md\nDRIFT 1 (advisory)  docs/superpowers/specs/2026-09-19-enforcement-git-decoder-design.md\nDRIFT 2 (blocking)  docs/development/plans/2026-10-06-plan-1-worktree-venv-isolation.md\nDRIFT 3 (blocking)  docs/development/plans/2026-09-06-plan-1-session-history-retention.md\nDRIFT 4 (blocking)  docs/development/plans/2026-10-06-plan-1-postgresql-18-upgrade/2026-10-06-plan-1-postgresql-18-upgrade.md\nDRIFT 4 (blocking)  docs/development/plans/2026-10-12-plan-1-owner-dsn-split.md\nDRIFT 4 (blocking)  docs/development/plans/2026-10-13-plan-1-mail-routing.md\nDRIFT 4 (blocking)  docs/development/plans/2026-10-14-plan-1-coolify-verb-retirement/2026-10-14-plan-1-coolify-verb-retirement.md\nDRIFT 4 (blocking)  docs/development/plans/2026-10-15-plan-1-scratch-lifecycle.md\nDRIFT 4 (blocking)  docs/development/plans/archived/2026-08-22-plan-1-fabrik-mail-loop-safety.md\nDRIFT 4 (blocking)  docs/development/plans/archived/2026-09-25-plan-1-work-store-single-tracker/2026-09-25-plan-1-work-store-single-tracker.md\nDRIFT 4 (blocking)  docs/development/plans/archived/2026-09-30-plan-1-merg\n\u2026 [truncated: ~11 line(s) omitted \u2014 tail follows \u2014 run `python scripts/work.py` for the FULL set; NEVER scope a fix to this preview] \u2026\nocking)  .fabrik/work/W-be89830e.json\nDRIFT 6 (blocking)  .fabrik/work/W-da7adc2a.json\nDRIFT 6 (blocking)  .fabrik/work/W-ec5b4795.json\nDRIFT 7 (advisory)  docs/STRATEGIC_BACKLOG.md\nDRIFT 8 (advisory)  docs/development/plans/2026-06-29-plan-watchdog-deploy-side.md\nDRIFT 8 (advisory)  docs/development/plans/2026-07-06-plan-1-universal-watchdog.md\nDRIFT 8 (advisory)  docs/development/plans/2026-07-12-plan-1-wavespeed-integration.md\nDRIFT 8 (advisory)  docs/development/plans/2026-08-11-plan-deploy-tryton-crm.md\nDRIFT 8 (advisory)  docs/development/plans/2026-10-02-plan-3-coordinator-assignment.md",
      "truncated": true,
      "omitted_lines": 11,
      "rerun": "python scripts/work.py"
    }
  ]
}
```

A red caused only by another lane's work is pasted as is, with ONE line beside it (`/fabrik-review` § Reporting):
`GATE-SCOPE: out-of-surface — <failing check>; findings naming this surface: 0 of <N>; measured by: <command>`,
`<N>` the failing check's total findings (at least 1).
