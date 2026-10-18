# saas-skeleton chat that only a signed-in, rate-limited user can spend — design spec

Status: DRAFT
Amended: 2026-10-18 (night). The joint plan-review's round 1 confirmed a foundation error (F1: the default topology is same-host) and 14 findings, all in `docs/development/reviews/2026-10-18-plan-2-saas-chat-auth-round1-findings.md`. This amendment re-grounds the design on them. Slice 1 has shipped (D-1005). This spec now designs slice 2.
Profile: full (the backend chat route and the rate limiter have no code behind them today)
Work item: W-ab242b11 · owner fleet · coordinator-scored HIGH (security), the major in flight

## Personas

- **Primary — the scaffolded app's owner**, whose key is at stake. In the work item's words, *"any visitor can stream completions on the app's own OPENROUTER_API_KEY"*. They pay OpenRouter for every token a chat streams.
- **The signed-in end user** of a scaffolded SaaS app. They are the only person who may start a chat.
- **The anonymous visitor or abuse bot.** After slice 1 there is no endpoint for them. Slice 2 must not reopen one.
- **The tenant (paying account).** Per-tenant rate limiting is mandatory for SaaS (`.windsurf/rules/saas/95-multi-tenant-saas.md:166`). One tenant's users must not starve another.
- **Automated consumers:**
  - `fabrik scaffold` (saas-skeleton, static-site, office-extension), which emits the backend and the template and holds the duty to ship the fixed shape.
  - The six live projects' agents, who were mailed an interim warning and hold the duty to adopt slice 2 in their own copies.
  - The coordinator, who files one adoption item per live project after slice 2 merges.

**The primary's minimal loop, counted (the step budget is 4):**
1. The user signs in through the existing `/auth/login/web`.
2. They open a page that mounts `ChatUI`.
3. They send a message.
4. They read the streamed reply.

An anonymous request ends at step 3 with a 401, an over-limit one with a 429, and one sent while Redis is down with a 503. No step is added for the user.

Every feature below traces to a named persona:
- the auth gate to the owner and the visitor;
- the tenant, user and IP buckets to the tenant and the owner;
- the backend-only key path to the owner.

## Goal

A scaffolded saas-skeleton app can offer chat that spends its OpenRouter key only on a signed-in user's request, within per-tenant, per-user and per-IP limits, and fails closed.

## Why this exists

Before slice 1, `templates/saas-skeleton/app/api/chat/route.ts` streamed OpenRouter completions on the app's key for any caller. Slice 1 deleted it (D-1005), so today the template ships the `ChatUI`/`SSEStream` components and no chat endpoint. A project that wants chat must write its own endpoint, and the easiest one to write is the same public hole.

Slice 2 ships the safe endpoint, so the default is right:
- the backend that already authenticates users serves chat;
- every request carries an identity and a budget;
- the key is read only by the backend's code.

## What exists today (grounded)

- **Topology, same-host by default.** The emitted compose routes `Host(fqdn) && (PathPrefix(/api) || PathPrefix(/auth))` to the backend at priority 100, and everything else on the same host to Next (`src/fabrik/scaffold.py:3398`, comment `:3322`). So the browser's `__Host-session` cookie (host-only, `/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/cookies.py:85-103`) reaches both, and a backend route under `/api` is same-origin with the app.
- **Identity.**
  - `build_current_user` is exported by the vendored fastapi-user-auth (`/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/__init__.py:48-81`). It reads the bearer header first, then the session cookie (`dependencies.py:36-47`), then awaits `denylist.contains(jti)` unguarded (`dependencies.py:98`). It returns `AuthedUser(user_id, tenant_id: str | None, role, jti, access_exp)` (`dependencies.py:13-18`).
  - `tenant_id` is None for passwordless logins (on by default) and for password logins without a tenant (`router.py:53`, `:391`, `:1203-1205`).
  - The scaffold's own `require_user` reads only claims `TenantMiddleware` decoded from `Authorization: Bearer` (`src/fabrik/scaffold.py:2529-2539`, `:2737`), so it cannot authenticate a browser session.
- **The emitted auth module** (`_SAAS_AUTH_PY`, `src/fabrik/scaffold.py:2585`) exposes `get_settings` (JWT secret, Redis URL) and `_denylist()`. The latter builds a `RedisDenylist`, or a `NullDenylist` with a loud warning when `REDIS_URL` is unset (`src/fabrik/scaffold.py:2650-2664`).
- **CSRF.** `CsrfOriginMiddleware` gates every cookie-borne non-bearer mutation app-wide. It requires the double-submit token (cookie == `X-CSRF-Token` header) and an Origin or Referer in `allowed_origin_set` (`/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/csrf.py:202-231`, `:307-324`).
- **Middleware.** It wraps every route, in request order: CORS (when origins are set), Csrf, Correlation, SecurityHeaders, Tenant (`src/fabrik/scaffold.py:3179-3196`). The last four are `BaseHTTPMiddleware`.
  - Executed in this run: a `StreamingResponse` of `text/event-stream` passed through four `BaseHTTPMiddleware` layers with its media type and all three frames intact (Starlette 1.6.0; probe below).
- **Rate limiting.** None exists outside passwordless login, whose atomic counter is internal to `/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/passwordless.py:174-178`. fabrik-lib has no general limiter. `client_ip(request, trusted_proxy_hops)` lives at `/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/router.py:139` and is not exported.
- **Env.** web, api and worker all read the ONE root `.env` (`src/fabrik/scaffold.py:3336-3417`). Every backend secret (`DATABASE_URL`, `JWT_SECRET`) therefore already sits in the Next container's environment. Only the audit-jobs companion gets a second file, `.env.owner`.
- **Tests.** The hub `.venv` cannot import the emitted backend whole: argon2, uuid_utils, redis, asyncpg and email-validator are absent. The hub loads vendored modules by path into a bare Starlette app (`tests/test_scaffold_saas_web_wiring.py:121-135`). The emitted backend ships `server/tests/` and `server/requirements-dev.txt` (`src/fabrik/scaffold.py:2271-2278`, `:3621-3622`).
- **Error mapping.** The emitted app maps `RequestValidationError` to 422 (`src/fabrik/scaffold.py:3215-3217`).

```text
$ .venv/bin/python <run scratch>/probe_stream.py
200 text/event-stream; charset=utf-8 [b'data: 0\n\ndata: 1\n\ndata: 2\n\n']
```

## Constraints digest

| # | Quote | Source |
|---|---|---|
| C1 | "All Server Actions, Route Handlers, and Server Components that access sensitive data or perform mutations must call a `verifySession()` Data Access Layer utility that cryptographically validates the token with the backend (FastAPI or Supabase JWKS)." | .windsurf/rules/core/35-security-auth.md:188 |
| C2 | "Use `proxy.ts` (older majors: `middleware.ts`) only for UX redirects (e.g. redirect to `/login` if cookie missing)." | .windsurf/rules/core/35-security-auth.md:187 |
| C3 | "STICKY SESSIONS ARE BANNED (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory" | .windsurf/rules/core/35-security-auth.md:149 |
| C4 | "Hard rate limits, as **Redis-backed** token buckets, on every other route `fastapi-user-auth` mounts" | .windsurf/rules/core/35-security-auth.md:332 |
| C5 | "Rate-limit per tenant so a noisy neighbour cannot exhaust the VPS — counters keyed by tenant id, applied in middleware before business logic, limits from the plan tier" | .windsurf/rules/saas/95-multi-tenant-saas.md:166 |
| C6 | "Redis keys carry the tenant: `t:{tenant_id}:settings`; unprefixed keys are reserved for explicitly global data (`global:`)." | .windsurf/rules/saas/95-multi-tenant-saas.md:161 |

C4 governs the routes fastapi-user-auth mounts (`/auth/*`). It is cited here for the limiter's shape (Redis-backed), not as a mandate on `/api/v1/chat`. C5's "limits from the plan tier" is a deviation this slice records (§ Decisions taken).

## Chosen approach — A: a backend chat route

The emitted backend gains a chat module, `server/src/<pkg>/chat.py`, emitted by `src/fabrik/scaffold.py` beside `_SAAS_AUTH_PY`. It is mounted as `POST /api/v1/chat` on the existing `v1` router (`src/fabrik/scaffold.py:3250`).

- **Identity.**
  - `chat_user = build_current_user(secret=get_settings().jwt_secret, denylist=<fail-closed denylist>, session_cookie_secure=get_settings().session_cookie_secure)`. Because it reads the cookie as well as the header, a same-origin browser session authenticates (F1, F7).
  - The denylist passed in is a small adapter around `_denylist()`. Any Redis error in `contains` raises `HTTPException(503)`, so an outage is never a 500 (F4) and never a pass.
  - `_denylist` is exposed from the emitted `auth.py` under a public name (`build_denylist`), so `chat.py` imports nothing private.
- **CSRF.** A cookie-borne POST carries `X-CSRF-Token` (read from `__Host-csrf_token`, same host) and the browser's own Origin. `CsrfOriginMiddleware` already enforces both. A bearer request is exempt, as everywhere (F2).
- **Limits.** One atomic Redis transaction per request: a redis-py pipeline (MULTI/EXEC) of `INCR key` then `EXPIRE key <window> NX` per bucket. That is Redis ≥ 7.0 (E4, E5), and redis-main is Redis 7 (`infra/vps1/redis/compose.yaml:3`). There is no non-atomic INCR-then-EXPIRE (F14). The buckets, all of which must pass:
  - `t:{tenant_id}:chat:rate`, when `tenant_id` is set (C6);
  - `u:{user_id}:chat:rate`, always. A tenantless user (F3) gets this bucket and the IP bucket, and never shares a global one;
  - `ip:{client_ip}:chat:rate`, through the vendored `client_ip(request, trusted_proxy_hops)`, imported from `fastapi_user_auth.router` and never re-implemented. An upstream request asks fabrik-lib to export it (§ Open unknowns).
  - Each bucket is `<count>/<seconds>` from `CHAT_RATE_TENANT` (default `600/3600`), `CHAT_RATE_USER` (`60/3600`) and `CHAT_RATE_IP` (`120/3600`). A malformed value fails the app at start.
  - A full bucket returns 429 with `Retry-After` set to the key's TTL.
  - No Redis returns 503, closed; with `REDIS_URL` unset the limiter refuses rather than passes.
- **Body.** The handler reads the raw JSON body itself and keeps the deleted route's contract: only `message`, a non-empty string. Anything else, invalid JSON and `null` included, is a 400, not the app's 422 (F9). This holds the D-977 red-list: `SLICE2_HOSTILE_FIELDS` and `SLICE2_BAD_BODIES` in `tests/test_saas_skeleton_chat_system_prompt.py`.
- **The system prompt** is a server constant, `CHAT_SYSTEM_PROMPT` in `chat.py`. When empty, no system message is sent; when set, it is sent verbatim before the user message.
- **Upstream.** An `httpx.AsyncClient` stream to `https://openrouter.ai/api/v1/chat/completions` with exactly `{model, messages, stream: true}`. It is relayed as the same `{type: text_delta|done|error}` SSE frames `SSEStream` already consumes.
  - With `OPENROUTER_API_KEY` unset: a 503 JSON response, before any limiter cost.
  - A non-2xx upstream gives an `error` frame.
- **Key placement.** `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` are read only by `chat.py`. They live in the root `.env`, like every other backend secret, so they are present in the Next container's environment as `DATABASE_URL` and `JWT_SECRET` already are. Per-service env files are a fleet-wide hardening, not this slice (§ Rejected alternatives; F8).
- **Client.** `SSEStream` sends `credentials: "same-origin"` and the `X-CSRF-Token` header. The README example uses `endpoint="/api/v1/chat"`.

## Rejected alternatives

- **B2 — a Next route that forwards the cookie to a new backend `/me`.** Ranked second by all three judges on the corrected facts. It is two stacks for one feature (a JS Redis client for the bucket, plus a new backend endpoint), needs a non-`/api` path, and has no hub test pattern for its Next half.
- **B1 — a Next route that verifies the HS256 JWT itself.** Ranked last by all three. It duplicates verification, the denylist and CSRF in JS, puts `JWT_SECRET` to active use in the frontend, and arguably fails C1's "validates the token with the backend".
- **C — a Next-side limiter alone.** Contradicts C1 and C3.
- **Middleware placement for the limiter**, per C5's "applied in middleware": a chat-only limit in an app-wide middleware runs on every request. A route dependency applied before the upstream call is "before business logic" for the only route it guards. Recorded as a deviation in the D-row.
- **Limits from the plan tier** (C5): the skeleton has no plan-tier table. Env defaults, overridable per project, are this slice's. Wiring to the plan tier is the Growth trigger below.
- **A per-service `.env.api`** carrying the key to the api container only. It needs a deployer change to write a second secret file, and it closes a gap every backend secret already shares. Filed as its own hardening item for fleet, not this slice (F8).
- **Re-implementing `client_ip`**: it reopens the spoof class the vendored helper documents (`router.py:145`).

## Lifecycle

- **Adoption:** new scaffolds get the route when slice 2 merges. The coordinator then files one adoption item per live project.
- **Growth:** there is no request metrics counter today; `REQUEST_COUNT` is declared and never incremented (`src/fabrik/scaffold.py:1731`). So slice 2 adds `chat_rate_limited_total{bucket}` and `chat_requests_total{outcome}` counters to the backend's metrics registry. The escalation trigger is a project whose `chat_rate_limited_total{bucket="tenant"}` exceeds 1% of `chat_requests_total` over a day. That is the signal to source limits from the plan tier (C5) (F10).
- **Degradation:**
  - Redis down gives 503 (denylist and limiter both).
  - The key unset gives 503.
  - An OpenRouter error gives an `error` frame.
  - A revoked token gives 401.
  - None of these spends the key without a check.
- **Retirement:** a project drops chat by deleting `chat.py`'s mount. The slice-1 graders keep the Next side from re-growing a key-bearing route.

## External dependencies

- **E1 — cookie prefixes.** `__Host-` cookies must be Secure, carry no Domain, and have Path=/, so they are "only sent to the host that set them". https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie (read 2026-10-18).
- **E2 — Next.js 15 route handlers** read cookies and stream through a ReadableStream. `middleware` was renamed `proxy` in v16.0.0. https://nextjs.org/docs/app/api-reference/file-conventions/route · https://nextjs.org/docs/app/api-reference/file-conventions/proxy (read 2026-10-18).
- **E3 — OpenRouter key limits.** A key takes an optional `limit`, "spending limit for the API key in USD", which an owner can set as a backstop. https://openrouter.ai/docs/api-reference/api-keys/create-api-key (read 2026-10-18).
- **E4 — `EXPIRE … NX`** is "Set the expiry only when the key has no expiry", added in 7.0.0. https://raw.githubusercontent.com/redis/docs/main/content/commands/expire.md, the source of redis.io/docs/latest/commands/expire, which returned 403 to this box (read 2026-10-18).
- **E5 — MULTI/EXEC.** "A request sent by another client will never be served in the middle of the execution of a Redis Transaction". https://raw.githubusercontent.com/redis/docs/main/content/develop/using-commands/transactions.md. A redis-py `pipeline()` is transactional (MULTI/EXEC) by default: https://redis.readthedocs.io/en/stable/advanced_features.html (read 2026-10-18).
- **Method:** fabrik-researcher via WebFetch. exa, firecrawl and brave failed to connect this session, so there is no tier-2 cross-check. `/fabrik-spec-review` re-verifies these facts.

## fabrik-lib verdict

| Capability | Verdict | Module | Why |
|---|---|---|---|
| Identity on the chat request | vendor (already vendored) | `/opt/fabrik-lib/fastapi-user-auth` `build_current_user` | It reads the header, then the cookie, then the denylist. The scaffold's bearer-only `require_user` cannot serve a browser |
| Client IP behind proxies | vendor (already vendored) | `fastapi_user_auth.router.client_ip` | Handles `trusted_proxy_hops`. Upstream note to fabrik-lib: export it |
| Rate limiting | build, in the emitted backend | — | No general limiter exists in fabrik-lib (passwordless's is internal). ~40 lines on the existing redis client. Upstream note: a general limiter would serve every FastAPI scaffold |
| OpenRouter streaming | build | — | The deleted Next route's logic, ported to the backend |

## Shape and infra implications

- **Scaffold type:** `saas-skeleton` (also emitted for static-site and office-extension through the shared template).
- **Redis:** `shape.needs_cache: true` is required for chat to work. Without `REDIS_URL` the route is a closed 503.
- **Env:** `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `CHAT_RATE_TENANT`, `CHAT_RATE_USER` and `CHAT_RATE_IP` go into the emitted `.env.example` and `docs/CONFIGURATION.md`. New specs list `OPENROUTER_API_KEY` under `secrets.from_env` again.
- **No new port, service or path prefix:** `/api` already routes to the backend.

## Documentation landing sites

- **The scaffolded project:**
  - `README.md`: the chat section (endpoint, env, limits, same-host requirement);
  - `.env.example` and `docs/CONFIGURATION.md`: the new vars;
  - `server/tests/test_chat.py`: the emitted tests.
- **The hub:**
  - `CHANGELOG.md` and a `docs/DECISIONS.md` row (the decision, the C5 deviations, the defaults);
  - the slice-2 plan.

## Validation

- **Hub tests.** These run where the hub can run them (F6). `tests/test_saas_chat_backend.py` scaffolds a saas-skeleton into `tmp_path`, loads the emitted `chat.py` and the vendored modules by path into a bare Starlette app (the pattern of `tests/test_scaffold_saas_web_wiring.py:121-135`), and drives it with TestClient. Redis is a fake implementing MULTI/EXEC, INCR, EXPIRE NX and TTL; OpenRouter is an `httpx.MockTransport`. The cases:
  - anonymous: 401;
  - bearer: 200 and frames;
  - cookie with token and Origin: 200;
  - cookie without token, or without an allowed Origin: 403 (each tested separately, so neither passes for the other's reason);
  - each bucket full: 429 plus `Retry-After`;
  - a tenantless user: no `t:` key touched;
  - Redis raising: 503 from the denylist and from the limiter;
  - `REDIS_URL` unset: 503;
  - key unset: 503;
  - upstream non-2xx: an `error` frame;
  - a revoked jti: 401;
  - every `SLICE2_BAD_BODIES` body: 400;
  - `SLICE2_HOSTILE_FIELDS`: the upstream payload is exactly `{model, messages, stream}`;
  - the system-constant rows;
  - the stream through the app's four `BaseHTTPMiddleware` layers.
- **The emitted tests.** `server/tests/test_chat.py` carries the same core cases for a project's own CI (`pip install -r requirements-dev.txt && pytest tests`).
- **Mutants.** Every grader is proven red on a mutant that drops its guard.

## Decisions taken

- **DECISION (reversible):** A, the backend chat route. On the corrected facts, the panel of three judges ranked A, B2, B1 unanimously. B's prior rejection reason (cookies never reach Next) was false (F1); the re-ranking stands on single-stack auth, no frontend dependency, and hub test feasibility.
- Deviations recorded in the D-row:
  - C5's middleware placement (a route dependency instead);
  - C5's plan-tier limits (env defaults until the Growth trigger);
  - the key in the shared `.env` (the fleet-wide per-service env hardening is filed separately).

## Open / blocking unknowns

- **Resolved:**
  - same-host topology (`src/fabrik/scaffold.py:3398`);
  - SSE through `BaseHTTPMiddleware` (probe above);
  - the atomic bucket (E4, E5);
  - the tenantless rule;
  - outage fail-closed;
  - the hub test pattern.
- **Open: the fabrik-lib export of `client_ip`.** Resolution step: a request mail to fabrik-lib at plan time. Until it lands, `chat.py` imports it from `fastapi_user_auth.router` (vendored, so the import is pinned per scaffold).
- **Open: the default bucket sizes** (600/60/120 per hour). Resolution step: the plan's D-row derives them from `OPENROUTER_MODEL`'s per-token price and a stated daily budget. They stay env-overridable.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "the unauthenticated saas-skeleton /api/chat that spends an app's OpenRouter key" (coordinator, 2026-10-18) | IN | § Why this exists (slice 1 shipped, D-1005; slice 2 here) |
| I2 | "it's security" | IN | Constraints digest; full review at spec-review and in the plan |
| I3 | "the design trade-off you laid out (backend route vs /auth/me check vs Next-side limiter)" | IN | § Chosen approach (A); § Rejected alternatives (B2 = the /auth/me check, C = the Next-side limiter) |
| I4 | "The four live projects' interim mails are already out and recorded on the item" — the item carries four interim-mail tags; six live projects carry the route | IN | § Lifecycle, Adoption |
| I5 | "needs a session/auth check and a rate limit before a scaffolded app goes public" (W-ab242b11) | IN | § Chosen approach (Identity, Limits) |
| I6 | "design the auth hook against the template's auth story (fastapi-user-auth / D-xxx)" | IN | § What exists today |
| I7 | "If the spec won't fit, get it to a resumable checkpoint and hand it off cleanly." | IN (met earlier, round-1 findings) | header |
| I8 | F1 "the emitted compose already serves /api and /auth on the APP host" | IN | § What exists today; § Rejected alternatives re-ranked |
| I9 | F2 "the CSRF gate also needs an allowed Origin … tests must send Origin and the __Host- cookies over https" | IN | § Chosen approach, CSRF; § Validation |
| I10 | F3 "`chat:t:None` becomes one global bucket" | IN | § Chosen approach, Limits |
| I11 | F4 "a Redis outage gives a 500, not a 503" | IN | § Chosen approach, Identity; § Lifecycle |
| I12 | F5/F5a "port its behaviours … the owed list is the docstring + SLICE2_* constants" | IN | § Chosen approach, Body; § Validation |
| I13 | F6 "the hub .venv cannot import the emitted backend" | IN | § Validation |
| I14 | F7 "main.py's imports lack build_current_user … client_ip is not exported" | IN | § Chosen approach, Identity and Limits; § Open unknowns |
| I15 | F8 "ONE root .env handed to web, api and worker" | IN | § Chosen approach, Key placement; § Rejected alternatives |
| I16 | F9 "RequestValidationError maps to 422" | IN | § Chosen approach, Body |
| I17 | F10 "the 429-rate trigger has no data source" | IN | § Lifecycle, Growth |
| I18 | F11 "missing rows: key unset, error frame, revoked token, invalid JSON/null, stream through 3 middlewares" | IN | § Validation |
| I19 | F12 "C4 governs /auth/* only; C5 mandates middleware with plan-tier limits" | IN | § Constraints digest note; § Decisions taken |
| I20 | F13 "I4 says four … size lines disagree … citations" | IN | I4 reworded; no Size line; citations re-grounded |
| I21 | F14 "defaults are unstated … INCR then EXPIRE is non-atomic" | IN | § Chosen approach, Limits; § Open unknowns |
| I22 | Coordinator 2026-10-18: "ship slice 1 first … Then the W-ab242b11 spec amendment, then /fabrik-spec-review and the re-plan" | IN (slice 1 DONE, D-1005) | header |

Intake: 22 items — 22 IN, 0 OUT-OF-SCOPE, 0 ASK.
