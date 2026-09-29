# Review — 2026-09-29-plan-1-hub-worktree-cutover

**Status:** CONVERGED
**Surface:** `git rev-parse HEAD` = 85a55422c170e8ceb427b935ce412ad79ca9f087; the plan's own commits from `086269f2d` (T01) to `85a55422c` (the docs review) — 55 paths, listed in the rubric invocation below; the range also carries sibling sessions' commits, which this review did not grade
**Command:** /fabrik-review · **Changed:** the 55 paths of the rubric invocation below
**Plan:** `docs/development/plans/2026-09-29-plan-1-hub-worktree-cutover/2026-09-29-plan-1-hub-worktree-cutover.md`

## Integration receipts (T07) — pasted verbatim

Every ticket's own review closed before its merge (receipts `2026-09-29-plan-1-hub-worktree-cutover-T01-review.md`, `-T03a-`, `-T04a-`, `-T06a-`, `-T06c-review.md`; the other tickets closed inside their wave's review). T07's own acts: the post-merge hook installed, the corpus rendered from the main checkout (T06a), the `MERGE OWNER: infra` row D-453, fleet and intel moved into `.claude/worktrees/{fleet,intel}` with `.env` and a `claudeMdExcludes` entry each, and a hand-run sync after every plumbing commit on a sync path (47 projects, 0 failed, each time).

### V1 — who owns the uncommitted paths

```text
$ git -C /opt/fabrik status --porcelain
 M CHANGELOG.md
 M PORTS.md
 M docs/DECISIONS.md
 M docs/PROJECT_CATALOG.md
 M docs/development/capability-defects.md
 M docs/reference/agents/kaizen-log-fleet.md
 M docs/reference/agents/kaizen-log-infra.md
 M libs/subagents/agent.py
 M libs/subagents/select.py
?? .fabrik/work/W-00934cdf.json
?? .fabrik/work/W-8a6d3d7f.json
?? .fabrik/work/W-b395b4d0.json
?? err.txt
?? out.txt
$ git -C .claude/worktrees/fleet status --porcelain   # branch worktree-fleet
$ git -C .claude/worktrees/intel status --porcelain   # branch worktree-intel
```

Main checkout: `CHANGELOG.md` and `docs/DECISIONS.md` carry orphaned reorder hunks older than the cut-over; `PORTS.md`, `docs/PROJECT_CATALOG.md`, `docs/development/capability-defects.md` and both kaizen logs are pipeline output (the kaizen rows are the digest's, identical in the fleet and infra logs); `libs/subagents/*` is fabrik-lib's re-vendor output (restore gated on mail 01M3PTHG, W-745042ab); `err.txt`/`out.txt` date from 2026-09-24; `.fabrik/work/*` are infra's items. None is fleet's or intel's; both worktrees are clean.

### U1 — `.env` in each worktree

```text
$ ls -l .claude/worktrees/fleet/.env; cmp with /opt/fabrik/.env
-rw------- 25275 .claude/worktrees/fleet/.env
identical
$ ls -l .claude/worktrees/intel/.env; cmp with /opt/fabrik/.env
-rw------- 25275 .claude/worktrees/intel/.env
identical
```

### V7 / V10 — merge owners

```text
$ python3 scripts/decisions.py --merge-owner /opt/fabrik
infra
rc=0
$ python3 scripts/decisions.py --merge-owner /opt/trade-intelligence
agent-1
rc=0
$ python3 scripts/decisions.py --merge-owner /opt/fabrik-lib
UNDECLARED
rc=3
```

The hub reads `infra` (D-453) and trade-intelligence `agent-1` (its D-029/D-038). fabrik-lib reads UNDECLARED: its adoption row is the sentinel's to write in its own window (spec § D8; the hub may not edit another repo). Requested by fabrik-mail 01M3Q192 and 01M3QM3G with the operator's words (D-444/D-445); fabrik-lib's reply 01M3QNZG took it after its CLAUDE.md lean pass, and its dev1 and dev2 sessions relayed a live reminder to the sentinel on 2026-09-30. The plan is not archived until that row lands.

### The plan's docs — `/fabrik-docs-review`

Seven native seats (opus×1, sonnet×3, haiku×3), one unit each over the plan's hunks in seven docs (the model doc and agent identity · the hooks index, the kaizen event stream and the epics-review source · both CLAUDE.md contracts). Pass 1 raised 14, confirmed 12, all fixed at `85a55422c`: five line cites the plan's own edits moved and `_worktree_base`'s range in the hooks index; the claim that a rebase fires no hook, wrong in three places (executed: a rebase fires post-commit once per replayed local commit, the commits a `pull --rebase` brings in fire nothing); the merge-owner advisory's blind spot for an unattributed commit, in the hooks index and the kaizen stream; hub identity from a worktree and `check_doc_links.py`'s worktree resolution, both undocumented; `command_feedback_report.py:46-68`; and `docs/workflows/DATA_SYNC_WORKFLOW.md` crediting the boot hook with `sync_projects.py`. Two candidates were refuted by execution (the template carries all 14 anchor phrases, which is what `check_governance_drift.py:45` matches; the worktree directories exist, gitignored). The closing pass, the same seven seats over their own docs, confirmed 0 with the docs byte-unchanged since the pin.

```text
$ python3 scripts/enforcement/check_doc_sync.py --range 086269f2d^..HEAD
rc=0
$ python3 scripts/enforcement/check_doc_stubs.py --range 086269f2d^..HEAD
rc=0
$ python3 scripts/enforcement/check_doc_links.py
check_doc_links: OK — 0 broken of 2944 refs across 246 docs
$ python3 scripts/docs_updater.py --check
125 issues listed, 0 in the plan's docs (126 at the plan's base 086269f2d^ — the repo's standing backlog, not this plan's)
```

## Coverage Checklist

Rubric invocation (verbatim output — the gate reads the generated header, never a prose mention):

```text
$ python scripts/review_rubric.py --changed CHANGELOG.md .claude/hooks/final_gate_stop.py .claude/hooks/session_orient.py CLAUDE.md commands/assemble_commands.py commands/_sources/fabrik-epics-review.md docs/DECISIONS.md docs/LESSONS_LEARNT.md docs/reference/multi-agent-operating-model.md docs/workstation/agent-identity.md docs/workstation/hooks-index.md docs/workstation/kaizen-event-stream.md .gitignore INDEX.md scripts/check_commit_trailers.py scripts/command_feedback_report.py scripts/decisions.py scripts/enforcement/check_doc_links.py scripts/enforcement/check_vendored_drift.py scripts/final_gate.py scripts/governance_sync_postcommit.sh scripts/install_post_commit_hook.sh scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py scripts/sync_projects.py scripts/sysadmin/kaizen_events.py scripts/vps_sync.py scripts/wsl_startup_hook.sh src/fabrik/config.py templates/governance/CLAUDE.md tests/enforcement/test_check_doc_links.py tests/enforcement/test_governance_sync_postcommit.py tests/test_assemble_worktree_guard.py tests/test_automated_writers.py tests/test_governance_template_split.py tests/test_hub_identity_worktree.py tests/test_hub_write_root.py tests/test_merge_sync.py tests/test_session_orient_hook.py tests/test_stop_hook_push_attribution.py tests/test_stop_hook_worktree_push.py tests/test_vision_reads_work_stores.py .worktreeinclude
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
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
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
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and archives nothing.  If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
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

### core/10-python.md  (hit: .claude/hooks/final_gate_stop.py, .claude/hooks/session_orient.py, commands/assemble_commands.py)
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
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### core/40-documentation.md  (hit: CHANGELOG.md, CLAUDE.md, INDEX.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py, tests/enforcement/test_check_doc_links.py, tests/enforcement/test_governance_sync_postcommit.py)
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
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_*: 82 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
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
- `^/api/` `/api/*` `/api/v1` `/api/*` `shape.bearer_bypass_prefix: "^/api/v1"` `fabrik apply` `^/` `orchestrator/verifier.check_api_bypass` `/api/*` `^/api/`
- `postgres-main` `fabrik-lib/rag` `postgres:16-alpine` `plpgsql` `postgres-main`
- `postgres-main` `docs/DECISIONS.md`
```

| Class | Verdict |
|---|---|
| Hunt: `CHANGELOG.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (T01 allowlist count 101 → 103, the ALLOWLIST literal counted) |
| Hunt: `.claude/hooks/final_gate_stop.py` — every changed hunk, its enclosing function, its callers | CLEAN (the worktree push rule `_worktree_base` :694-743 and its two block texts; test_stop_hook_worktree_push.py passes) |
| Hunt: `.claude/hooks/session_orient.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (UNDECLARED read token-exact; both move lines order the .worktreeinclude check) · FIXED r2 (a full stop after UNDECLARED is punctuation, `UNDECLARED.team` an owner; red on revert) |
| Hunt: `CLAUDE.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (a worktree commit distributes nothing until merged; --force from the main checkout; claudeMdExcludes named) · FIXED r2 (the --force reason matches sync_enforcement_to_projects.py:43-44, :1525) |
| Hunt: `commands/assemble_commands.py` — every changed hunk, its enclosing function, its callers | CLEAN (main_checkout_refusal :1369-1414 fails closed, exit 3; test_assemble_worktree_guard.py passes) |
| Hunt: `commands/_sources/fabrik-epics-review.md` — every changed hunk, its enclosing function, its callers | CLEAN (the mint step names --reserve-id; rendered from the main checkout (T06a)) |
| Hunt: `docs/DECISIONS.md` — every changed hunk, its enclosing function, its callers | CLEAN (D-447..D-453 rows; decisions.py --merge-owner /opt/fabrik prints infra) |
| Hunt: `docs/LESSONS_LEARNT.md` — every changed hunk, its enclosing function, its callers | CLEAN (the plan’s lesson rows; no code claim) |
| Hunt: `docs/reference/multi-agent-operating-model.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (launch-form bullet, D-453 cites, R1 observed both ways) · FIXED docs-review (rebase-hook sentence, hub identity and check_doc_links worktree behaviour documented, command_feedback_report.py:46-68) |
| Hunt: `docs/workstation/agent-identity.md` — every changed hunk, its enclosing function, its callers | CLEAN (live bindings scoped to the git common dir, session_orient.py:459-476, :540) |
| Hunt: `docs/workstation/hooks-index.md` — every changed hunk, its enclosing function, its callers | FIXED docs-review (five moved line cites, `_worktree_base` :694-743, the rebase-hook sentence, the advisory never sees an unattributed commit) |
| Hunt: `docs/workstation/kaizen-event-stream.md` — every changed hunk, its enclosing function, its callers | FIXED docs-review (the merge-owner event fires only for a commit with a parsable Agent-Role:) |
| Hunt: `.gitignore` — every changed hunk, its enclosing function, its callers | FIXED r1 (`.claude/worktrees/` tracked-ignored, was only in .git/info/exclude) |
| Hunt: `INDEX.md` — every changed hunk, its enclosing function, its callers | CLEAN (rows for the plan’s new files; check_doc_index green in the gate) |
| Hunt: `scripts/check_commit_trailers.py` — every changed hunk, its enclosing function, its callers | CLEAN (the merge-owner advisory :677-714 and its silences; the unattributed-commit path documented at hooks-index) |
| Hunt: `scripts/command_feedback_report.py` — every changed hunk, its enclosing function, its callers | CLEAN (_resolve_fabrik_root :46-68 replicates config.py) |
| Hunt: `scripts/decisions.py` — every changed hunk, its enclosing function, its callers | CLEAN (--reserve-id reserves (two calls, two ids), --next-id skips a live reservation; the UNDECLARED un-adoption read filed as W-8a6d3d7f) |
| Hunt: `scripts/enforcement/check_doc_links.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (core.worktree main checkout; a `../` escape re-resolved from the main checkout) · FIXED r2 (an in-repo `../` ref is never re-resolved; the bound holds; mutants M3 and the X-10 revert killed) |
| Hunt: `scripts/enforcement/check_vendored_drift.py` — every changed hunk, its enclosing function, its callers | CLEAN (_is_hub :130-155 grades the worktree’s own governance set; test_hub_identity_worktree.py passes) |
| Hunt: `scripts/final_gate.py` — every changed hunk, its enclosing function, its callers | CLEAN (_is_hub :3204-3226, git failure reads not-the-hub; the pytest-leg cites :1281-1291 still frame the condition) |
| Hunt: `scripts/governance_sync_postcommit.sh` — every changed hunk, its enclosing function, its callers | FIXED docs-review (header: a rebase fires post-commit per replayed local commit; executed in a scratch repo) |
| Hunt: `scripts/install_post_commit_hook.sh` — every changed hunk, its enclosing function, its callers | CLEAN (installs post-commit and post-merge, refuses core.hooksPath; test_merge_sync.py passes (7)) |
| Hunt: `scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh` — every changed hunk, its enclosing function, its callers | CLEAN (signs Agent-Name: kilo-pipeline :275; the advisory exempts it) |
| Hunt: `scripts/kilo-benchmarks/tests/test_commit_trailer_guard.py` — every changed hunk, its enclosing function, its callers | CLEAN (the kilo-pipeline signing case) |
| Hunt: `scripts/sync_projects.py` — every changed hunk, its enclosing function, its callers | CLEAN (_resolve_fabrik_root :45-67; no longer run by the boot hook (DATA_SYNC_WORKFLOW row fixed by the docs review)) |
| Hunt: `scripts/sysadmin/kaizen_events.py` — every changed hunk, its enclosing function, its callers | CLEAN (commit_merge_owner_warning in EVENT_TYPES :135) |
| Hunt: `scripts/vps_sync.py` — every changed hunk, its enclosing function, its callers | CLEAN (_resolve_fabrik_root :36-58) |
| Hunt: `scripts/wsl_startup_hook.sh` — every changed hunk, its enclosing function, its callers | CLEAN (sync_projects.py removed from the main-checkout boot :44, :183) |
| Hunt: `src/fabrik/config.py` — every changed hunk, its enclosing function, its callers | CLEAN (_resolve_fabrik_root :34-65, the invoker-toplevel write root; test_hub_write_root.py passes (24)) |
| Hunt: `templates/governance/CLAUDE.md` — every changed hunk, its enclosing function, its callers | FIXED r1 (§ Orient (d) orders the .worktreeinclude arrival check; grader seen red) |
| Hunt: `tests/enforcement/test_check_doc_links.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (sibling-repo and submodule cases, seen red) · FIXED r2 (branch-deleted target and out-of-bound climb, red on revert) |
| Hunt: `tests/enforcement/test_governance_sync_postcommit.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted for tests that pass against broken code; the sync-script tests pass) |
| Hunt: `tests/test_assemble_worktree_guard.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted for tests that pass against broken code; passes) |
| Hunt: `tests/test_automated_writers.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted for tests that pass against broken code; passes) |
| Hunt: `tests/test_governance_template_split.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (orient-d grader asserts the check-it-arrived wording; seen red before the template edit) |
| Hunt: `tests/test_hub_identity_worktree.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted for tests that pass against broken code; passes) |
| Hunt: `tests/test_hub_write_root.py` — every changed hunk, its enclosing function, its callers | CLEAN (24 tests, the 103-entry allowlist; passes) |
| Hunt: `tests/test_merge_sync.py` — every changed hunk, its enclosing function, its callers | CLEAN (ORIG_HEAD..HEAD extraction; 7 passed) |
| Hunt: `tests/test_session_orient_hook.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (undeclared-team parity case, move-line grader) · FIXED r2 (full-stop cases, grammar pin; red on revert) |
| Hunt: `tests/test_stop_hook_push_attribution.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted for tests that pass against broken code; passes) |
| Hunt: `tests/test_stop_hook_worktree_push.py` — every changed hunk, its enclosing function, its callers | CLEAN (the no-upstream worktree branch message; passes) |
| Hunt: `tests/test_vision_reads_work_stores.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted for tests that pass against broken code; passes) |
| Hunt: `.worktreeinclude` — every changed hunk, its enclosing function, its callers | CLEAN (lists .env; both worktrees received it (U1 below)) |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | FIXED r2 (check_doc_links' main-checkout re-resolution green-lit a branch-deleted in-repo target, X-10; the guard now refuses any ref landing inside the main checkout) |
| Recurrence: cost/quota accounting — pool units scored, native seats counted, a limit at its edges | CLEAN (the pool stayed OFF; native seats stamped with dispatch before every round; hook budgets hold, SessionStart 93-95 ms of 10 s) |
| Recurrence: boundary/sentinel/prefix — an off-by-one, a sentinel value, a prefix-vs-exact match | FIXED r1 (UNDECLARED read as a word prefix, C-2) · FIXED r2 (a trailing full stop read as part of a name, X-11) |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | FIXED r2 (the bound in _escapes_from_main_checkout had no negative case, NEW-2; mutant M3 now killed; M11 refuted by execution, git realpaths the common dir) |
| Recurrence: denominator on every count — bounded searches state their bound | CLEAN (24 candidates across three D7 passes from 3 seats; 11 confirmed; the docs review 15 candidates from 7 seats, 12 confirmed) |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | CLEAN (every candidate executed by its seat and re-executed here: scratch repos for the rebase and pull hooks, mutants in a throwaway worktree, parity tables against decisions.py) |

## Pass Ledger

ONE table, one row per pass, counts punctuated — the closing row is the exit round.

| Pass | Finders | Counters | Method |
|---|---|---|---|
| Pass 1 | native opus×1 + sonnet×2 (X: cross-ticket integration, opus; C: code, sonnet; D: contracts and docs, sonnet) | found: 15, new: 15, confirmed: 7, fixed: 10, unexecuted: 0 | citation — the pin of 17da4988e; X-1..X-4, C-1, C-2, D-2 confirmed by execution, X-5..X-7 plausible and fixed with them, X-8 refuted; fixes at c47b34fbe (this pass was not logged as a round on the run record — the record's round 19 is pass 2) |
| Pass 2 | native opus×1 + sonnet×2 (the round-1 owners X, C, D over their own claim ledgers plus the fix diff and one hop) | found: 6, new: 6, confirmed: 4, fixed: 4, unexecuted: 0 | citation — the pin of c47b34fbe; X-9, X-10, X-11 and C NEW-2 confirmed by execution, C NEW-1 refuted; fixes at 45d900ecc, every new test seen red |
| Pass 3 | native opus×1 + sonnet×2 (the same owners X, C, D) | found: 3, new: 3, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — the closing pass on the pin of 45d900ecc; X-9..X-11 and NEW-2 re-executed NOW_FALSE with revert proofs (3 failed on revert); C M11 refuted by execution (git realpaths the common dir), C NEW-1 recorded measured, X's gitignored-ref candidate refuted (0 of 2943 refs change) |

## Residual

| X-8 | RECORDED — measured (PORTS.md and docs/PROJECT_CATALOG.md in the main checkout are rewritten by a writer not yet found, the content still the pipeline's uncommitted diff; md5 snapshot kept for the next rewrite) |
| C-3 | RECORDED — measured (session_orient._is_hub checks the manifest before the hub-path short-circuit; no reachable input flips the result, documented in its docstring) |
| C-4 | RECORDED — measured (two tests/test_kaizen_events.py failures in scratch copies depend on the environment; kaizen_events.py is untouched by the plan) |
| D-3 | RECORDED — measured (the 2026-09-03 spec's hub-deferral sentence is a frozen historical spec) |
| C-NEW-1 | RECORDED — measured (a mixed up/down ref such as a/../../../../sib/README.md stays broken from a worktree while it resolves from the main checkout; no author writes one, and no wrong file resolves) |
| X-MO | RECORDED — measured (decisions.py and docs_updater.py read an un-adoption row as owner UNDECLARED at rc 0; predates the plan, filed as W-8a6d3d7f) |
| X-BARE | RECORDED — measured (_main_checkout for a worktree of a bare repo answers the bare repo's parent, as common.parent did before this plan) |

## Per-phase verdicts

### Phase 1 — D7, the whole hub-worktree-cutover plan: CONVERGED — 3 passes, confirmed 7 → 4 → 0; the docs review 12 → 0; the T07 integration receipts above (V1 and U1 hold, V10 holds for the hub and trade-intelligence and waits on fabrik-lib's own row)

## Gate

`final_gate.py --check --json`, run in the main checkout at HEAD 85a55422c (the status and skip keys pasted; the hub's pytest leg is off by design, and the touched slices were run by hand: 180, 154, 62 and 7 passed):

```json
{
  "status": "success",
  "skipped_checks": [
    "bandit",
    "bandit scripts/",
    "semgrep",
    "pytest"
  ]
}
```
