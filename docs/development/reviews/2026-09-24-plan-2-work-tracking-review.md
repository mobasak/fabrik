# Review — 2026-09-24-plan-2-work-tracking

**Status:** CONVERGED
**Surface:** `git rev-parse HEAD` = 64721143818a8e2e68c7ca3652cd4a321f8a2a3c; range tip 64721143818a8e2e68c7ca3652cd4a321f8a2a3c; `git diff 48d006707..HEAD -- scripts/work.py scripts/thread_anchor.py .claude/hooks/final_gate_stop.py scripts/final_gate.py scripts/fabrik_synced_manifest.py .pre-commit-config.yaml .claude/settings.json scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py templates/governance/CLAUDE.md templates/governance/.worktreeinclude CLAUDE.md tests/test_work.py tests/test_work_claims.py tests/test_work_sync.py tests/test_work_migrate.py tests/test_work_hook_seam.py tests/test_work_distribution.py tests/test_work_contract_rule.py tests/test_work_doc_verbs.py tests/test_final_gate_work_row.py tests/test_thread_anchor.py tests/test_claude_fleet.py tests/test_governance_template_split.py` md5 2286596cf45ffa1015dc81ac870f87c3 (450583 bytes)
**Command:** /fabrik-review · **Changed:** `scripts/work.py`, `scripts/thread_anchor.py`, `.claude/hooks/final_gate_stop.py`, `scripts/final_gate.py`, `scripts/fabrik_synced_manifest.py`, `.pre-commit-config.yaml`, `.claude/settings.json`, `scripts/sysadmin/claude_rotate.py`, `scripts/aro-wake/claude_rotate.py`, `templates/governance/CLAUDE.md`, `templates/governance/.worktreeinclude`, `CLAUDE.md`, `tests/test_work.py`, `tests/test_work_claims.py`, `tests/test_work_sync.py`, `tests/test_work_migrate.py`, `tests/test_work_hook_seam.py`, `tests/test_work_distribution.py`, `tests/test_work_contract_rule.py`, `tests/test_work_doc_verbs.py`, `tests/test_final_gate_work_row.py`, `tests/test_thread_anchor.py`, `tests/test_claude_fleet.py`, `tests/test_governance_template_split.py`
**Plan:** `docs/development/plans/2026-09-24-plan-2-work-tracking/2026-09-24-plan-2-work-tracking.md`

## Integration receipts (T10) — pasted verbatim

Plan baseline `48d006707` (the CONVERGED plan set, D-401); the range also carries two sibling plans' commits (audit-log, rules currency), so each check below names what it examined.

### Doc receipts over the plan range

```text
$ .venv/bin/python scripts/enforcement/check_doc_sync.py --range 48d006707..HEAD   # rc 0
WARNING: Retry/backoff/circuit-breaker code changed but docs/RESILIENCE.md not updated.
$ .venv/bin/python scripts/enforcement/check_doc_stubs.py --range 48d006707..HEAD  # rc 0
```

The RESILIENCE.md advisory does not apply: the hub carries no `docs/RESILIENCE.md` (a project-template doc, `templates/scaffold/docs/RESILIENCE_TEMPLATE.md`). `/fabrik-docs-review` ran over the plan's docs: rounds 6 → 0 → 0, six claims fixed in 4d9095a86; `docs_updater.py --check` is red on 125 whole-tree findings, 0 of 125 naming a doc this plan touched (backlog item W-1d80827c).

### Seam tests together

```text
$ .venv/bin/python -m pytest -q tests/test_thread_anchor.py tests/test_work_hook_seam.py tests/test_final_gate_work_row.py
144 passed in 22.65s
```

### V1 — two Stops, two awaiting items every session sees

```text
$ .venv/bin/python -m pytest -v tests/test_work_hook_seam.py -k v1
tests/test_work_hook_seam.py::test_v1_two_stops_become_two_awaiting_items_every_session_sees PASSED [100%]
======================= 1 passed, 22 deselected in 0.87s =======================
```

### V2 — the migration round-trip against an independent reader

```text
$ (tests/test_work_migrate.py::_independent_scan over the pre-migration hub backlog, md5 54116246342395499523a1c956ae4a77, vs the store after migrate-backlog)
V2 independent reader (tests/test_work_migrate.py::_independent_scan) over the pre-migration backlog md5 5411624634…: {'open': 314, 'resolved': 22} rows 336
V2 store after migrate-backlog: {'open': 314, 'resolved': 22} items 336
owner x state equal: True
open-by-owner store: {'unassigned': 35, 'fleet': 48, 'infra': 217, 'intel': 10, 'operator': 4}
```

The spec's 253/36 was a stale snapshot (D-396); V2 is re-derived: 336 rows, 314 open, 22 resolved, owner by state equal. The test `test_migrate_backlog_then_render_matches_an_independent_reader_on_the_hub_backlog` now reads this pre-adoption blob (`git show 24fbac770:docs/STRATEGIC_BACKLOG.md`).

### V5 — `work.py status` drift lists against an independent reader of the hub tree

```text
$ python3 scripts/work.py status | grep ^DRIFT   # at 4d9095a86, after the D-412 fix
DRIFT 1 (advisory)  docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md
DRIFT 1 (advisory)  docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md
DRIFT 1 (advisory)  docs/superpowers/specs/2026-09-17-review-scoped-scope-growth-exit-design.md
DRIFT 1 (advisory)  docs/superpowers/specs/2026-09-19-enforcement-git-decoder-design.md
DRIFT 2 (blocking)  docs/development/plans/2026-06-29-plan-empire-operating-model.md
DRIFT 2 (blocking)  docs/development/plans/2026-07-06-plan-1-universal-watchdog.md
DRIFT 2 (blocking)  docs/development/plans/2026-07-12-plan-1-wavespeed-integration.md
DRIFT 2 (blocking)  docs/development/plans/2026-08-11-plan-1-knowledge-ratchet.md
DRIFT 2 (blocking)  docs/development/plans/2026-08-22-plan-1-fabrik-mail-loop-safety.md
DRIFT 2 (blocking)  docs/development/plans/2026-08-25-plan-2-payments-ingest-role.md
DRIFT 2 (blocking)  docs/development/plans/2026-09-05-plan-2-glitchtip-deny-by-default/2026-09-05-plan-2-glitchtip-deny-by-default.md
DRIFT 2 (blocking)  docs/development/plans/2026-09-06-plan-1-session-history-retention.md
DRIFT 8 (advisory)  docs/development/plans/2026-06-29-plan-watchdog-deploy-side.md
DRIFT 8 (advisory)  docs/development/plans/2026-08-11-plan-deploy-tryton-crm.md
DRIFT 8 (advisory)  docs/development/plans/2026-08-27-plan-1-certification-denominator.md
```

The independent reader (a Sonnet seat that never opened `work.py`; `<scratch>/v5/drift_reader.py`) first found `work.py`'s class 1 listing 28 specs, 24 of them carried by an ARCHIVED plan — a real defect, fixed in e4c578608 (D-412; the lines above are after it). Every remaining difference was executed and is the reader's: class 1 — it counts any prose mention in any plan file, which would exclude the decoder spec the spec names as the class-1 example (this plan's own T10 ticket mentions it); class 2 and class 8 — its status parser returns `None` on the `**Status:**` bold form (executed on the three plans it missed), and it includes `archived/` plans, which D-412 keeps live-only for classes 2, 3 and 8. Classes 3–6 are 0 on both sides; class 7 is not tree-derivable for the reader.

### Every ticket's Behavior-Contract tests and every seam test, together

```text
$ .venv/bin/python -m pytest -q tests/test_work.py tests/test_work_claims.py tests/test_work_sync.py tests/test_work_migrate.py tests/test_work_hook_seam.py tests/test_work_distribution.py tests/test_work_contract_rule.py tests/test_work_doc_verbs.py tests/test_final_gate_work_row.py tests/test_thread_anchor.py tests/test_claude_fleet.py tests/test_governance_template_split.py tests/test_synced_manifest.py   # at 41f65b01e, after the D7 fixes (676 at 0c0b410ec before them)
680 passed in 207.45s (0:03:27)
```

The first run of this set (at 4d9095a86) was 1 failed, 674 passed: the V2 hub test read the live backlog, which adoption had made the rendered view. That exposed a real defect, a second `migrate-backlog` re-importing the kept context, fixed in 43412df1a (D-414, its own review receipt `docs/development/reviews/2026-09-24-plan-2-work-tracking-T10-migrate-once-review.md`).


## Coverage Checklist

Rubric invocation (verbatim output — the gate reads the generated header, never a prose mention):

```text
$ python scripts/review_rubric.py --changed scripts/work.py scripts/thread_anchor.py .claude/hooks/final_gate_stop.py scripts/final_gate.py scripts/fabrik_synced_manifest.py .pre-commit-config.yaml .claude/settings.json scripts/sysadmin/claude_rotate.py scripts/aro-wake/claude_rotate.py templates/governance/CLAUDE.md templates/governance/.worktreeinclude CLAUDE.md tests/test_work.py tests/test_work_claims.py tests/test_work_sync.py tests/test_work_migrate.py tests/test_work_hook_seam.py tests/test_work_distribution.py tests/test_work_contract_rule.py tests/test_work_doc_verbs.py tests/test_final_gate_work_row.py tests/test_thread_anchor.py tests/test_claude_fleet.py tests/test_governance_template_split.py
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

### core/10-python.md  (hit: .claude/hooks/final_gate_stop.py, scripts/aro-wake/claude_rotate.py, scripts/fabrik_synced_manifest.py)
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

### core/40-documentation.md  (hit: CLAUDE.md, templates/governance/CLAUDE.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_claude_fleet.py, tests/test_final_gate_work_row.py, tests/test_governance_template_split.py)
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

| Class | Status |
|---|---|
| Hunt: `scripts/work.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (class 4 resolves a pre-archive plan link to its archived copy, W2-S1; a rescued slot keeps its owner as creator via `own_session`, W4-O6; the store, lock, claims, drift classes, migrate/render and every verb hunted by four slices W1-W4) |
| Hunt: `scripts/thread_anchor.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (the busy-store warning says not re-checked, W4-O1; WHERE YOU ARE keeps the OPEN DECISION when the work block was skipped, W4-O2; the rescue docstring, W4-S2 then W4-O8 r2) |
| Hunt: `.claude/hooks/final_gate_stop.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (the fail-open catch-all stores an accepted DECISION, W4-O4; 1,302 tests across the 23 files naming the hook pass) |
| Hunt: `scripts/final_gate.py` — every changed hunk, its enclosing function, its callers | CLEAN (`_work_sync_row` reds only on exit 1 with a blocking DRIFT line and no traceback; NOT RUN otherwise; 304-line row test) |
| Hunt: `scripts/fabrik_synced_manifest.py` — every changed hunk, its enclosing function, its callers | CLEAN (work.py and thread_anchor.py both in CORE_SCRIPTS, 2 of 15) |
| Hunt: `.pre-commit-config.yaml` — every changed hunk, its enclosing function, its callers | CLEAN (the governance-sync regex carries `work`; the sync ran 47/0 on every synced merge) |
| Hunt: `.claude/settings.json` — every changed hunk, its enclosing function, its callers | CLEAN (the Task-tools env pair, D-397) |
| Hunt: `scripts/sysadmin/claude_rotate.py` — every changed hunk, its enclosing function, its callers | CLEAN (tasks in both tuples; every reader iterates them; T10 part 1 receipt) |
| Hunt: `scripts/aro-wake/claude_rotate.py` — every changed hunk, its enclosing function, its callers | CLEAN (byte-identical to the sysadmin copy) |
| Hunt: `templates/governance/CLAUDE.md` — every changed hunk, its enclosing function, its callers | CLEAN (both § FINAL OUTPUT copies carry the work-items paragraph with the absolute hub doc path, D-411) |
| Hunt: `templates/governance/.worktreeinclude` — every changed hunk, its enclosing function, its callers | CLEAN (`.fabrik/work/` rides into linked worktrees) |
| Hunt: `CLAUDE.md` — every changed hunk, its enclosing function, its callers | CLEAN (the work-items paragraph and the re-anchored GATE cites; the hub test count updated by the docs review) |
| Hunt: `tests/test_work.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted by slice T or C for tests that pass against broken code; every test D7 added red on revert) |
| Hunt: `tests/test_work_claims.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted by slice T or C for tests that pass against broken code; every test D7 added red on revert) |
| Hunt: `tests/test_work_sync.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (a test for the pre-archive link, red on revert) |
| Hunt: `tests/test_work_migrate.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted by slice T or C for tests that pass against broken code; every test D7 added red on revert) |
| Hunt: `tests/test_work_hook_seam.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (a test for the catch-all store, red on revert) |
| Hunt: `tests/test_work_distribution.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted by slice T or C for tests that pass against broken code; every test D7 added red on revert) |
| Hunt: `tests/test_work_contract_rule.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted by slice T or C for tests that pass against broken code; every test D7 added red on revert) |
| Hunt: `tests/test_work_doc_verbs.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted by slice T or C for tests that pass against broken code; every test D7 added red on revert) |
| Hunt: `tests/test_final_gate_work_row.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted by slice T or C for tests that pass against broken code; every test D7 added red on revert) |
| Hunt: `tests/test_thread_anchor.py` — every changed hunk, its enclosing function, its callers | FIXED r1 (the busy-store test asserted the false warning, T-L1; three tests added, red on revert) |
| Hunt: `tests/test_claude_fleet.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted by slice T or C for tests that pass against broken code; every test D7 added red on revert) |
| Hunt: `tests/test_governance_template_split.py` — every changed hunk, its enclosing function, its callers | CLEAN (hunted by slice T or C for tests that pass against broken code; every test D7 added red on revert) |
| Recurrence: fail-open/fail-closed — a swallowed error or an absent check that reads as success | FIXED r1 (two accepted-DECISION loss paths closed, W4-O4 and W4-O2; W4-O3, both locks busy at once, filed as W-e64aa44a) |
| Recurrence: cost/quota accounting — pool units scored, native seats counted, a limit at its edges | CLEAN (the hook budgets hold: the Stop harvest's 5 s kill, the 2 s store lock, the 3 s prompt store budget) |
| Recurrence: boundary/sentinel/prefix — an off-by-one, a sentinel value, a prefix-vs-exact match | CLEAN (ids are `W-` + 8 lowercase hex; plan refs matched after normalisation, now archive-aware) |
| Recurrence: behavior-without-a-test — a contract row no test kills (mutation asserted) | CLEAN (680 BC and seam tests pass together at 41f65b01e; every D7 fix red on revert) |
| Recurrence: denominator on every count — bounded searches state their bound | CLEAN (28 candidates from 22 seats; 7 confirmed, 1 own-fix at pass 2) |
| Recurrence: proxy-as-evidence — the real check EXECUTED, not read | CLEAN (every candidate executed by a refuter and adjudicated by execution or reachability) |

Verdict grammar (the gate refuses anything else): `CLEAN (<the paths/lines hunted>)` — a CLEAN row
must name a path and run past 70 characters · `FIXED r<n> (<what changed>)` · `REFUTED (<the
disproving line>)` · `RECORDED — unexecuted (<why>)` · `RECORDED — by design`, parenthesising the
owning row's first-cell id and the EARLIER round that adjudicated it, or a `D-nnn` with no round
(the § Residual block below shows the shape) · `RECORDED — measured (<why>)` ·
`RECORDED — hygiene false positive (<why>)` — every RECORDED reason is PARENTHESISED, never
colon-delimited (a colon would spell the `unexecuted: N` counter the ledger refuses). `UNCHECKED`
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
| Pass 1 | native opus×1 + sonnet×7 + haiku×7 (W1-W3: work.py by section, sonnet+haiku; W4: the hook API + thread_anchor.py + final_gate_stop.py seam, sonnet+haiku+opus; G: gate row, manifest, sync regex, settings, rotate; C: contracts + four tests; T: eight test files) + refuters | found: 28, new: 28, confirmed: 7, fixed: 7, unexecuted: 0 | citation — the D7 whole-plan pass (workflow wf_274b2e71-87f) over 48d006707..0c0b410ec on the plan's paths; every candidate run by a refuter and adjudicated by execution or reachability; CONFIRMED — class 4 missed an item linking a plan by its pre-archive path (W2-S1); a slot rescued for another session took the rescuer's agent name as creator (W4-O6, W4-S1 its duplicate); a busy store printed NOT tracked under a line showing the item awaiting (W4-O1); a compaction past the store budget hid the OPEN DECISION entirely (W4-O2); the Stop hook's fail-open catch-all dropped an accepted DECISION (W4-O4); the rescue docstring contradicted its code (W4-S2); REFUTED W1-H1, W1-H3, W1-H4, W1-H5, W3-H1, W3-S1, W3-S2, W3-S3, G-S1, T-S2; RECORDED the rest below; the run record says confirmed 8 because W4-O5 was counted before it was reclassified as by design; seats: W1-sonnet 0/3 · W1-haiku 0/5 · W2-sonnet 1/1 · W2-haiku 0/0 · W3-sonnet 0/3 · W3-haiku 0/1 · W4-opus 4/6 · W4-sonnet 2/3 · W4-haiku 0/0 · G-sonnet 0/2 · G-haiku 0/0 · C-sonnet 0/1 · C-haiku 0/0 · T-sonnet 0/3 · T-haiku 0/0 (confirmed by my adjudication, raised from the candidate ids); stop: confirmed 7; fix: +134 -11 lines for 7 confirmed (cdd1b2e9c) |
| Pass 2 | native opus×1 + sonnet×3 + haiku×3 (W2, W4, T — the slices with fixes; W1, W3, G, C closed at pass 1 with only refuted or recorded rows) + refuters | found: 3, new: 3, confirmed: 1, fixed: 1, unexecuted: 0 | citation — the round-1 owners over the fix diff plus one hop (workflow wf_00cb27b1-6d3); all 7 ledger claims re-executed NOW_FALSE, each test red against 0c0b410ec; CONFIRMED — the rewritten rescue docstring was still inaccurate (W4-O8, own-fix 1 of 1); RECORDED W4-O7 and T-S1 (one version-skew case); seats: W2-sonnet 0/0 · W2-haiku 0/0 · W4-opus 1/2 · W4-sonnet 0/0 · W4-haiku 0/0 · T-sonnet 0/1 · T-haiku 0/0; stop: confirmed 1; fix: +3 -3 lines for 1 confirmed (79e6541f5) |
| Pass 3 | native opus×1 + sonnet×1 + haiku×1 (W4, the one edited docstring, under the scope-growth stop) + refuter | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0 | citation — workflow wf_af1d25f6-bb5; W4-O8 re-executed NOW_FALSE; CONFIRMED — the enumerated list of cases left out an exception before the slot read (W4-S1 r3, own-fix 1 of 1); the site had confirmed defects two passes running, so it was REWRITTEN as a rule, not patched; seats: W4-opus 0/0 · W4-sonnet 1/1 · W4-haiku 0/0; stop: confirmed 1; fix: +2 -3 lines for 1 confirmed (a1ef84aa1) |
| Pass 4 | native opus×1 + sonnet×1 + haiku×1 (W4, the round-1 owners of the one open slice) | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation — the closing pass on the pin of a1ef84aa1 (workflow wf_72b4d0bb-349); W4-S1 re-executed NOW_FALSE on 15 return paths (seen is the slot's msg in 5 of 5 usable-slot cases, None in 10 of 10 others); the six other slices closed earlier with every row fixed, refuted or recorded; seats: W4-opus 0/0 · W4-sonnet 0/0 · W4-haiku 0/0; stop: confirmed 0 |

Row shapes (quoted here, so the gate does not read them as passes):

```text
| Pass 1 | native opus×1 + sonnet×2 | found: N, new: N, confirmed: C, fixed: X, unexecuted: U | citation |
| Pass 2 | native opus×1 + sonnet×2 | found: 0, new: 0, confirmed: 0, fixed: 0, unexecuted: 0 | method: re-derivation |
```

## Residual

Every candidate that did not enter `confirmed:` is recorded here, one row each, in the verdict
grammar of `/fabrik-review` § Phase 2 (the fenced block under the next heading is an EXAMPLE, never rows).

### Verdict grammar — an EXAMPLE, never rows

(quoted so no reader — human or scan — takes this template's own sample rows for the receipt's residuals):

```text
| F12 | RECORDED — unexecuted (3 probe attempts timed out) |
| F19 | RECORDED — by design (F4, round 3; D-203) |
| F31 | RECORDED — measured (a prevalence figure; makes no code or doc claim) |
```

`RECORDED — by design` names the OWNING row's first-cell id and the EARLIER round that adjudicated
it (or a `D-nnn` with no round); the gate refuses an absent owner and a round that is not below the
closing `Pass N`. `RECORDED — measured` and `RECORDED — unexecuted` never enter `confirmed:`;
`unexecuted:` on the closing row is what keeps an unexecuted CODE candidate from closing the loop.

| W1-S1 | RECORDED — measured (the umask fallback runs only when /proc/self/status is unreadable, and every caller is a single-threaded CLI or hook subprocess) |
| W1-S2 | RECORDED — measured (8 retries of a 32-bit id against 338 items; the chance of exhausting them is negligible) |
| W1-S3 | RECORDED — measured (lock and git waits stack inside the Stop harvest's 5 s subprocess kill, which fails open; the T02 A-O11 trade-off) |
| W1-H2 | RECORDED — measured (a redundant None check with no behaviour) |
| W4-O3 | RECORDED — measured (both the session and the store lock contended at once; filed as item W-e64aa44a) |
| W4-O5 | RECORDED — measured (the prompt path never takes the store lock but for the second chance, the T04 review's A-O3; a NEXT whose Stop text was not yet flushed does not update the item) |
| W4-S3 | RECORDED — measured (0 of 9 prior thread_anchor.py revisions mention --repo without implementing it; synced copies are byte-identical to the hub) |
| W4-O7 | RECORDED — measured (a new thread_anchor.py against an old work.py disables the rescue until both match; both are CORE_SCRIPTS and ship in one sync run, and the rescue fails open) |
| T-S1 | RECORDED — measured (the same version-skew case as W4-O7) |
| T-S3 | RECORDED — by design (D-407) |
| C-S1 | RECORDED — measured (the GATE rule tells agents to read the gate's advisory key, where the Work items (sync) row appears while advisory) |
| G-S2 | RECORDED — unexecuted (a future change to work.py's traceback format; the row is advisory and says NOT RUN on a crash today) |

## Per-phase verdicts

### Phase 1 — D7, the whole work-tracking plan: CONVERGED — 4 passes, confirmed 7 → 1 → 1 → 0; the T10 integration receipts above

## Gate

`final_gate.py --check --json`, pasted verbatim at the flip (check_convergence reads the fenced
`"status": "success"`):

```json
$ .venv/bin/python scripts/final_gate.py --check --json   # main checkout, HEAD aa7eb9b9d (the D7 fixes merged 41f65b01e and synced 47/0; 680 BC and seam tests passed at 41f65b01e)
{
  "status": "success",
  "tier": 2,
  "passed": 67,
  "failed": 0,
  "skipped_checks": [
    "bandit",
    "semgrep",
    "pytest"
  ],
  "failures": []
}
```
