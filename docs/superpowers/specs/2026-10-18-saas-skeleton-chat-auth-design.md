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
- **Automated consumers and duty holders:**
  - `fabrik scaffold` (saas-skeleton, static-site, office-extension), which emits the backend and the template and holds the duty to ship the fixed shape.
  - The live projects' agents. The work item counts 7 scaffolded projects with the route: six carry the current route header and one an older variant. They hold the duty to adopt slice 2 in their own copies; four were mailed an interim warning, as the item's tags record.
  - The coordinator, who files one adoption item per live project after slice 2 merges.
  - The fabrik-lib agent, who holds the `client_ip` export request (§ Open unknowns).
  - The hub deployer (`fabrik apply`), which provisions Redis only when `shape.needs_cache` is true and writes the `secrets.from_env` keys into the root `.env`.

**The owner's own setup loop, counted (the step budget is 3):**
1. Set `OPENROUTER_API_KEY` (and, optionally, `OPENROUTER_MODEL` and the three `CHAT_RATE_*` values) in the spec's `secrets.from_env` or the project `.env`.
2. Keep `shape.needs_cache: true` (the saas-skeleton default), so `REDIS_URL` is set.
3. Deploy. Optionally, set a USD `limit` on the OpenRouter key itself (E3), which caps spend on OpenRouter's side whatever the app does.

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

C4 governs the routes fastapi-user-auth mounts (`/auth/*`). It is cited here for the limiter's storage (Redis-backed), not as a mandate on `/api/v1/chat`. Its shape, token buckets, is not followed: this slice uses fixed windows, a recorded departure (§ Decisions taken). C5's "limits from the plan tier" is a deviation this slice records too. C6's key form is followed inside an app namespace, because redis-main's DB 0 is shared by every app (`REDIS_URL=redis://redis-main:6379/0`, `src/fabrik/scaffold.py:1478`).

## Chosen approach — A: a backend chat route

The emitted backend gains a chat module, `server/src/<pkg>/chat.py`, emitted by `src/fabrik/scaffold.py` beside `_SAAS_AUTH_PY`. It is mounted as `POST /api/v1/chat` on the existing `v1` router (`src/fabrik/scaffold.py:3250`).

- **Identity.**
  - `chat_user = build_current_user(secret=get_settings().jwt_secret, denylist=<fail-closed denylist>, session_cookie_secure=get_settings().session_cookie_secure)`. Because it reads the cookie as well as the header, a same-origin browser session authenticates (F1, F7).
  - The denylist passed in is a small adapter around the emitted denylist. Any Redis error in `contains` raises `HTTPException(503)`, so an outage is never a 500 (F4) and never a pass. When `REDIS_URL` is unset the emitted denylist is a `NullDenylist`, which never raises; the adapter therefore raises 503 itself for a `NullDenylist`, so a revoked token can never pass because Redis is unconfigured. An anonymous request still gets 401, because `build_current_user` refuses a missing token before it consults the denylist (`dependencies.py:98`).
  - The emitted `auth.py` gains two public names, and `chat.py` imports nothing private:
    - `redis_client()`, an lru-cached accessor for the one async Redis client. `_denylist()` is changed to build its `RedisDenylist` on it, and `aclose()` closes it, so the limiter and the denylist share one client and nothing is left unclosed (`src/fabrik/scaffold.py:2725-2735` closes only `_denylist()._client` today).
    - `denylist()`, a public alias of `_denylist()`. `_denylist` itself keeps its name, because `build_saas_auth_router`, `token_revoked` and `aclose` call it.
- **CSRF.** A cookie-borne POST carries `X-CSRF-Token` (read from `__Host-csrf_token`, same host) and the browser's own Origin. `CsrfOriginMiddleware` already enforces both. A bearer request is exempt, as everywhere (F2).
- **The order of checks**, each refusing before the next costs anything:
  1. CSRF, in the middleware (403).
  2. Identity (401; 503 on a denylist outage or an unset `REDIS_URL`).
  3. The body (400). A malformed request spends no bucket.
  4. `OPENROUTER_API_KEY` unset (503). It comes after identity, so an anonymous caller learns nothing about the app's config.
  5. The limiter (429; 503 on a Redis error).
  6. The upstream stream.
- **Limits.** One Lua script per request, run with `EVAL` (Redis guarantees a script's atomic execution, E8). It checks every bucket before it increments any:
  - For each key it reads the count. If any count is at its limit, it increments nothing and returns that bucket's name and its `PTTL`.
  - Otherwise it `INCR`s every key, and `EXPIRE`s each key whose count became 1.
  - So a request refused on one bucket spends no other bucket. One user looping at 429 cannot drain their tenant's or their NAT neighbours' budget.
  - This is the pattern of the vendored passwordless limiter (`/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/passwordless.py:174-180`), widened to several keys. It needs no Redis 7 feature, and there is no non-atomic INCR-then-EXPIRE (F14).
  - Every key starts with the project id, which the scaffold writes into `chat.py` as a constant, because DB 0 is shared by every app on redis-main. The buckets, all of which must pass:
    - `<project>:t:{tenant_id}:chat:rate`, when `tenant_id` is set (C6);
    - `<project>:global:chat:user:{user_id}`, always. A tenantless user (F3) gets this bucket and the IP bucket, and never shares a global one;
    - `<project>:global:chat:ip:{client_ip}`, through the vendored `client_ip(request, trusted_proxy_hops)`, imported from `fastapi_user_auth.router` and never re-implemented. The hop count is the vendored settings' `trusted_proxy_hops`, set by `AUTH_TRUSTED_PROXY_HOPS` (default 1, `/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/settings.py:112`). When `client_ip` returns `""` (no forwarded header and no socket peer, `router.py:155-156`), the IP bucket is skipped, never keyed on the empty string, which would make one bucket shared by everyone. An upstream request asks fabrik-lib to export `client_ip` (§ Open unknowns).
  - Each bucket is `<count>/<seconds>` from `CHAT_RATE_TENANT` (default `600/3600`), `CHAT_RATE_USER` (`60/3600`) and `CHAT_RATE_IP` (`120/3600`). A malformed value fails the app at start.
  - A full bucket returns 429 with `Retry-After` set to that key's remaining TTL, rounded up to whole seconds.
  - A Redis error returns 503, closed.
  - A fixed window, by choice. Its known edge, a client spending one window's quota at its end and the next window's at its start (up to twice the rate across the boundary), is accepted here (E6). The user bucket is the primary key, not the IP, which is weak behind NAT (E6). A sliding window is the Growth path if the boundary burst ever shows in the metrics.
- **Body.** The handler reads the raw JSON body itself and keeps the deleted route's contract.
  - `message` must be a string that is non-empty after `.strip()` and at most `CHAT_MAX_MESSAGE_CHARS` long (default 4000).
  - Unknown keys are ignored and never forwarded.
  - A missing or invalid `message`, invalid JSON, `null`, or a non-object body is a 400, not the app's 422 (F9).
  - This holds the D-977 red-list: `SLICE2_HOSTILE_FIELDS` and `SLICE2_BAD_BODIES` in `tests/test_saas_skeleton_chat_system_prompt.py` (whose bad bodies include `{"message": "   "}`).
- **The system prompt** is a server constant, `CHAT_SYSTEM_PROMPT` in `chat.py`. When empty, no system message is sent; when set, it is sent verbatim before the user message.
- **Upstream.** An `httpx.AsyncClient` stream to `https://openrouter.ai/api/v1/chat/completions`.
  - We send exactly `{model, messages, stream: true, max_tokens}`. `max_tokens` is `CHAT_MAX_TOKENS` (default 1024). With the message cap it bounds one request's cost, so the user bucket bounds a user's hourly spend.
  - It is relayed as the same `{type: text_delta|done|error}` SSE frames `SSEStream` already consumes. The parser reads only `data:` lines. It skips SSE comment lines such as `: OPENROUTER PROCESSING`, and a final chunk that carries only `usage`, and it ends on `data: [DONE]` (E9).
  - The client has an explicit `httpx.Timeout` (connect 10 s; read 60 s between chunks, from `CHAT_UPSTREAM_READ_TIMEOUT`). A timeout gives an `error` frame, so a stalled provider cannot hold a connection open without bound.
  - A non-2xx upstream gives an `error` frame.
  - A client disconnect cancels the upstream stream. The generator's close closes the `httpx` stream (E7). OpenRouter stops billing on an aborted stream only for providers that support cancellation (E9), so a disconnect bounds spend at best effort. `max_tokens` is the hard bound.
- **Observability.** One structured log line per request, carrying the outcome (`ok`, `unauthenticated`, `bad_body`, `no_key`, `limited:<bucket>`, `redis_down`, `upstream_error`, `timeout`) and the user id, never the message text. The same outcome increments `chat_requests_total{outcome}` (§ Lifecycle).
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
- **Growth, a USD budget:** a project that wants a dollar cap rather than a request count vendors `cost-budget/` and wraps the upstream call in `reserve`/`settle`, settling on the stream's `usage` chunk (E9).
- **Growth, the counters:** there is no request metrics counter today; `REQUEST_COUNT` is declared and never incremented (`src/fabrik/scaffold.py:1731`). So slice 2 adds `chat_rate_limited_total{bucket}` and `chat_requests_total{outcome}` counters to the backend's metrics registry. The escalation trigger is a project whose `chat_rate_limited_total{bucket="tenant"}` exceeds 1% of `chat_requests_total` over a day. That is the signal to source limits from the plan tier (C5) (F10).
- **Degradation:**
  - Redis down gives 503 (denylist and limiter both).
  - The key unset gives 503.
  - An OpenRouter error gives an `error` frame.
  - A revoked token gives 401.
  - An upstream timeout gives an `error` frame.
  - None of these spends the key without a check.
- **Residual risk, accepted:** redis-main runs `--maxmemory-policy allkeys-lru` (`infra/vps1/redis/compose.yaml:6`). Under memory pressure Redis may evict a bucket key, which resets that window early, or a denylist key, which un-revokes a token early. That risk already applies to every app's denylist. It is recorded, not fixed here; a no-evict policy is a fleet Redis change.
- **Retirement:** a project drops chat by deleting `chat.py`'s mount. The slice-1 graders keep the Next side from re-growing a key-bearing route.

## External dependencies

- **E1 — cookie prefixes.** `__Host-` cookies must be Secure, carry no Domain, and have Path=/, so they are "only sent to the host that set them". https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie (read 2026-10-18).
- **E2 — Next.js 15 route handlers** read cookies and stream through a ReadableStream. `middleware` was renamed `proxy` in v16.0.0. https://nextjs.org/docs/app/api-reference/file-conventions/route · https://nextjs.org/docs/app/api-reference/file-conventions/proxy (read 2026-10-18).
- **E3 — OpenRouter key limits.** A key takes an optional `limit`, "spending limit for the API key in USD". https://openrouter.ai/docs/api-reference/api-keys/create-api-key (read 2026-10-18). Calling it the owner's backstop is this spec's use of it, not the page's words.
- **E6 — the fixed-window pattern** for per-user Redis limits, found by WebSearch on 2026-10-18 and read raw with curl: "Fixed window rate limiting with Redis requires just two commands - `INCR` and `EXPIRE`" and "The main drawback is the boundary burst problem: a user can make `limit` requests at the end of one window and `limit` more at the start of the next, effectively doubling the rate". https://oneuptime.com/blog/post/2026-03-31-redis-fixed-window-rate-limiting/markdown. That source's non-atomic pipeline is what the Lua script (E8) replaces.
- **E7 — Starlette `StreamingResponse`**, read raw with curl on 2026-10-18: it "Takes an async generator or a normal generator/iterator and streams the response body". https://raw.githubusercontent.com/encode/starlette/master/docs/responses.md. That this works through the app's `BaseHTTPMiddleware` stack was executed here (the probe above).
- **E8 — Lua scripts are atomic.** "Redis guarantees the script's atomic execution", and such scripts "can perform conditional updates across multiple keys". https://raw.githubusercontent.com/redis/docs/main/content/develop/programmability/eval-intro.md, the source of redis.io's eval-intro page, read raw with curl on 2026-10-18. `EVAL` predates Redis 7, so the design needs no Redis 7 feature. redis-main is a standalone Redis 7 (`infra/vps1/redis/compose.yaml:3`), not a cluster, so a multi-key script runs as one unit.
- **E9 — OpenRouter streaming.** Each payload is a `data: ` line of JSON, and the stream ends with `data: [DONE]`. Comment lines such as `: OPENROUTER PROCESSING` appear and must be skipped. A final chunk can carry only `usage`. On cancelling a stream: "For supported providers, this immediately stops model processing and billing"; for unsupported providers the model keeps running and the request is billed in full. https://openrouter.ai/docs/api-reference/streaming (read 2026-10-18).
- **Method:** E1-E3 and E9 came from fabrik-researcher via WebFetch. openrouter.ai returns 403 to curl, so E3 and E9 rest on the WebFetch summariser alone. The quotes in E6, E7 and E8 were read raw with curl. exa, firecrawl and brave failed to connect this session, so there is no tier-2 cross-check.

## fabrik-lib verdict

| Capability | Verdict | Module | Why |
|---|---|---|---|
| Identity on the chat request | vendor (already vendored) | `/opt/fabrik-lib/fastapi-user-auth` `build_current_user` | It reads the header, then the cookie, then the denylist. The scaffold's bearer-only `require_user` cannot serve a browser |
| Client IP behind proxies | vendor (already vendored) | `fastapi_user_auth.router.client_ip` | Handles `trusted_proxy_hops`. Upstream note to fabrik-lib: export it |
| Rate limiting | build, in the emitted backend | — | No general Redis limiter exists in fabrik-lib (passwordless's `_RATE_LUA` is internal and single-key). About 40 lines on the shared `redis_client()`. Upstream note: a general limiter would serve every FastAPI scaffold |
| Rate limiting, the two existing modules | reject | `abuse-prevention/` (README:16), `api-auth/` (README:20) | `abuse-prevention`'s per-IP limit is DB-backed, registration-only and fails open (`abuse_detection.py:117-148`). `api-auth`'s per-tier limit counts usage in the DB, keyed on an API key (`auth.py:66-135`). Neither keys on a session user or fails closed |
| USD spend cap | defer (recorded deviation) | `cost-budget/` (README:28; the rule at README:175: "Any project that … calls paid LLM/AI APIs needs `cost-budget/`") | Its fail-closed `reserve()` admits a run against a per-tenant daily cap and an app-global monthly USD budget. It needs a tenant on every call, which passwordless users lack (`router.py:53`), and a USD estimate per call. This slice bounds spend by request count × `CHAT_MAX_TOKENS` instead, plus E3's key limit. Adopting it is a Growth path below |
| OpenRouter streaming | build | — | The deleted Next route's logic, ported to the backend. `ai-consult/` (README:18) is an OpenRouter client built for long consults with a durable JSONL store; a chat relay needs none of that |
| Upstream HTTP pool | build (a module-level `httpx.AsyncClient`) | `async-http-client/` (README:23; the rule at README:175) | Its circuit breaker would also suit this route. Not vendored by this slice: one upstream and one route, where a timeout plus an error frame cover provider death. Recorded as a deviation from the README:175 rule |

## Shape and infra implications

- **Scaffold type:** `saas-skeleton` (also emitted for static-site and office-extension through the shared template).
- **Redis:** `shape.needs_cache: true` is required for chat to work. Without `REDIS_URL` the route is a closed 503.
- **Env:** `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `CHAT_RATE_TENANT`, `CHAT_RATE_USER`, `CHAT_RATE_IP`, `CHAT_MAX_TOKENS`, `CHAT_MAX_MESSAGE_CHARS` and `CHAT_UPSTREAM_READ_TIMEOUT` go into the emitted `.env.example` and `docs/CONFIGURATION.md`. New specs list `OPENROUTER_API_KEY` under `secrets.from_env` again.
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

- **The slice-1 graders change with it.** `tests/test_saas_skeleton_chat_system_prompt.py` bans "openrouter" from the emitted `.env.example` and from every template file. Slice 2 needs the key in `.env.example`. So the `.env.example` assertion narrows to forbidding `NEXT_PUBLIC_OPENROUTER`. The template-file scan keeps its ban on `templates/saas-skeleton/app/**`. A new assertion requires that the only emitted file reading `OPENROUTER_API_KEY` is `server/src/<pkg>/chat.py`. The Next side stays guarded, and no assertion is deleted.
- **Hub tests.** These run where the hub can run them (F6). `tests/test_saas_chat_backend.py` scaffolds a saas-skeleton into `tmp_path`, loads the emitted `chat.py` and the vendored modules by path into a bare Starlette app (the pattern of `tests/test_scaffold_saas_web_wiring.py:121-135`), and drives it with TestClient. Redis is a fake implementing the limiter script's semantics (check every key, then increment), INCR, EXPIRE and PTTL; OpenRouter is an `httpx.MockTransport`. The cases:
  - anonymous: 401;
  - bearer: 200 and frames;
  - cookie with token and Origin: 200;
  - cookie without token, or without an allowed Origin: 403 (each tested separately, so neither passes for the other's reason);
  - each bucket full: 429 plus `Retry-After`;
  - a request refused on the user bucket leaves the tenant and IP counts unchanged;
  - every key starts with the project id;
  - an empty client IP: no IP key touched;
  - a body refused with 400: no bucket touched;
  - a tenantless user: no `t:` key touched;
  - Redis raising: 503 from the denylist and from the limiter;
  - `REDIS_URL` unset: 503 with a token, 401 without one;
  - key unset: 503 with a token, 401 without one;
  - a message over `CHAT_MAX_MESSAGE_CHARS`: 400;
  - an upstream that stalls past the read timeout: an `error` frame;
  - an upstream stream with `: OPENROUTER PROCESSING` comment lines and a usage-only chunk: the frames are unchanged;
  - upstream non-2xx: an `error` frame;
  - a revoked jti: 401;
  - every `SLICE2_BAD_BODIES` body: 400;
  - `SLICE2_HOSTILE_FIELDS`: a 200, and the upstream payload is exactly `{model, messages, stream, max_tokens}`;
  - the system-constant rows;
  - the stream through the app's four `BaseHTTPMiddleware` layers.
- **The emitted tests.** `server/tests/test_chat.py` carries the same core cases for a project's own CI (`pip install -r requirements-dev.txt && pytest tests`).
- **Mutants.** Every grader is proven red on a mutant that drops its guard.

## Decisions taken

- **DECISION (reversible):** A, the backend chat route. On the corrected facts, the panel of three judges ranked A, B2, B1 unanimously. B's prior rejection reason (cookies never reach Next) was false (F1); the re-ranking stands on single-stack auth, no frontend dependency, and hub test feasibility.
- Deviations recorded in the D-row:
  - C5's middleware placement (a route dependency instead);
  - C5's plan-tier limits (env defaults until the Growth trigger);
  - the key in the shared `.env` (the fleet-wide per-service env hardening is filed separately);
  - C4's token-bucket shape (fixed windows instead);
  - C6's key form inside a `<project>:` namespace, because DB 0 is shared;
  - README:175's `cost-budget/` and `async-http-client/` (request count × `max_tokens`, and a timeout, instead; each has its Growth path).

## Open / blocking unknowns

- **Resolved:**
  - same-host topology (`src/fabrik/scaffold.py:3398`);
  - SSE through `BaseHTTPMiddleware` (probe above);
  - the atomic, check-before-increment bucket (E8);
  - the tenantless rule;
  - outage fail-closed;
  - the hub test pattern.
- **Open: the fabrik-lib export of `client_ip`.** Resolution step: a request mail to fabrik-lib at plan time. The same mail reports that passwordless's default `key_prefix="auth:pwdless:"` (`passwordless.py:187`) carries no app namespace on a Redis DB that apps share. Until it lands, `chat.py` imports it from `fastapi_user_auth.router` (vendored, so the import is pinned per scaffold).
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
