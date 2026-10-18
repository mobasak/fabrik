# saas-skeleton chat that only a signed-in, rate-limited user can spend — design spec

Status: DRAFT
Review: /fabrik-plan-review round 1 (2026-10-18) confirmed a foundation error and scope beyond `Size: small`. The Size line was removed per that command's escape hatch. Findings F1-F14: `docs/development/reviews/2026-10-18-plan-2-saas-chat-auth-round1-findings.md`. Next: amend this spec, then `/fabrik-spec-review`.
Profile: full (the rate limit and the backend chat route have no code behind them today)
Work item: W-ab242b11 · owner fleet · coordinator-scored HIGH (security), the major in flight

## Personas

- **Primary — the scaffolded app's owner**, whose key is at stake. In the work item's words, *"any visitor can stream completions on the app's own OPENROUTER_API_KEY"*. They pay OpenRouter for every token the route streams.
- **The signed-in end user** of a scaffolded SaaS app. They are the only person who should be able to start a chat.
- **The anonymous visitor or abuse bot.** Today they can `POST /api/chat` with no account, no cookie and no limit.
- **The tenant (paying account).** Per-tenant rate limiting is mandatory for SaaS (`.windsurf/rules/saas/00-domain-saas.md:75`). One tenant's users must not starve another.
- **Automated consumers:**
  - `fabrik scaffold --type saas-skeleton`, which emits the template and the backend. It holds the duty to ship the fixed shape.
  - The six live projects' agents, who were mailed an interim warning (recorded on W-ab242b11). They hold the duty to patch their own copies.
  - The coordinator, who scores and assigns this and the follow-up per-project items.

**The primary's minimal loop, counted (the step budget is 4):** (1) the user signs in through the existing `/auth/login/web`; (2) opens a page that mounts `ChatUI`; (3) sends a message; (4) reads the streamed reply. An anonymous request ends at step 3 with a 401, and an over-limit one with a 429. No new step is added for the user.

Every feature below traces to a named persona. The auth gate traces to the owner and the visitor, the per-tenant and per-user buckets to the tenant and the owner, the key's move into the backend to the owner, and the route removal to the owner.

## Goal

A scaffolded saas-skeleton app never spends its OpenRouter key on an unauthenticated or unlimited request.

## Why this exists

`templates/saas-skeleton/app/api/chat/route.ts` (the POST handler) reads `message` from any request body and streams an OpenRouter completion on `process.env.OPENROUTER_API_KEY`. It checks no session, no origin and no rate.

The template's frontend has no auth wiring:
- there is no `middleware.ts`;
- `templates/saas-skeleton/app/(app)/app/layout.tsx` renders only `<AppShell>`;
- `ChatUI`, the route's only caller, is mounted by no page. It appears only in `templates/saas-skeleton/components/chat/index.ts` and in the README example at `templates/saas-skeleton/README.md:76-80`.

So every scaffold ships a public, key-burning endpoint that nothing in the product even uses. Six live projects carry a copy (web-ecommerce-factory, test-saas-scaffold, ai-model-catalog, compliance-ops, fabrik-test-saas-skeleton, exam-coach). D-977 recorded the gap and routed it here.

How the chosen approach resolves it:
- **Slice 1** deletes the endpoint from the template, so nothing is exposed.
- **Slice 2** re-adds chat as a backend route behind the existing authenticating dependency and a Redis token bucket, so the key never sits in the frontend and every request carries an identity and a budget.

## What exists today (grounded)

- **The backend is the IdP (Pattern A).**
  - `src/fabrik/scaffold.py` emits `server/`. `_SAAS_MAIN_PY` (`src/fabrik/scaffold.py:3098`) mounts the vendored fastapi-user-auth router at `/auth` (`src/fabrik/scaffold.py:3201`).
  - It installs `CsrfOriginMiddleware` (`src/fabrik/scaffold.py:3187`).
  - It adds `CORSMiddleware` with `allow_credentials=True` and exact origins from env (`src/fabrik/scaffold.py:3188-3196`).
  - It has a `v1 = APIRouter(prefix="/api/v1")` (`src/fabrik/scaffold.py:3250`) whose routes depend on `require_user` (`src/fabrik/scaffold.py:2737`).
  - `require_user` only checks the claims `TenantMiddleware` decoded from an `Authorization: Bearer` header (`src/fabrik/scaffold.py:2529-2539`). The session cookie is never read on `v1` routes today.
- **Cookies.** Web sessions are `__Host-session` (HttpOnly), `__Host-refresh` and `__Host-csrf_token`. All are SameSite=Lax and Path=/, with no `Domain`, so they are host-only (`/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/cookies.py:85-103`).
- **The current-user dependency** reads the bearer header first and the session cookie second (`/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/dependencies.py:64-67`).
- **No `/auth/me` endpoint exists.** The only rate limiter is passwordless login's, which is Redis-backed (`/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/settings.py:105-108`).
- **Redis** reaches the backend as `REDIS_URL`, and its client is already a backend dependency (`src/fabrik/scaffold.py:2266`, `src/fabrik/scaffold.py:2655-2658`).
- **The frontend** is Next ^15 (`templates/saas-skeleton/package.json`) with no Redis or auth library.

## Constraints digest

| # | Quote | Source |
|---|---|---|
| C1 | "All Server Actions, Route Handlers, and Server Components that access sensitive data or perform mutations must call a `verifySession()` Data Access Layer utility that cryptographically validates the token with the backend (FastAPI or Supabase JWKS)." | .windsurf/rules/core/35-security-auth.md:188 |
| C2 | "Use `proxy.ts` (older majors: `middleware.ts`) only for UX redirects (e.g. redirect to `/login` if cookie missing)." | .windsurf/rules/core/35-security-auth.md:187 |
| C3 | "STICKY SESSIONS ARE BANNED (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory" | .windsurf/rules/core/35-security-auth.md:149 |
| C4 | "Hard rate limits, as **Redis-backed** token buckets, on every other route `fastapi-user-auth` mounts" | .windsurf/rules/core/35-security-auth.md:332 |
| C5 | "Per-tenant API rate limiting — counters keyed by tenant, limits from the plan tier" | .windsurf/rules/saas/00-domain-saas.md:75 |

## Chosen approach — D then A, two slices

**Slice 1 — remove the public route (D).**
- Delete `templates/saas-skeleton/app/api/chat/route.ts`.
- Drop `ChatUI` from the template's `components/chat/index.ts` export surface, keeping the component file for slice 2.
- Replace the README example at `templates/saas-skeleton/README.md:76-80` with a note that chat arrives with slice 2.
- A scaffold test asserts that a fresh saas-skeleton has no `app/api/chat/route.ts` and that no Next route names `OPENROUTER_API_KEY`.
- No page used the route, so no user-visible feature is lost.

**Slice 2 — authenticated backend chat (A).** `_SAAS_MAIN_PY` gains `POST /api/v1/chat` on the existing `v1` router.
- **Identity:** `Depends(chat_user)`, where `chat_user` is an instance of the vendored `build_current_user` (`/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/dependencies.py:64`). It reads the bearer header first and the `__Host-session` cookie second, validates the JWT and the jti denylist, and returns an `AuthedUser` with `user_id` and `tenant_id` (`dependencies.py:13-18`).
  - It is NOT `require_user`. That dependency reads claims `TenantMiddleware` decoded from the `Authorization: Bearer` header only (`src/fabrik/scaffold.py:2529-2539`), so a cookie-authenticated browser request would always be 401 behind it.
  - The handler is never reached anonymously, which meets C1 because the backend itself validates the token.
  - A cookie-borne POST must carry the double-submit CSRF token, because `CsrfOriginMiddleware` gates every cookie-borne non-bearer mutation app-wide (`/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/csrf.py:307`).
- **Limits:** a Redis token bucket keyed on `chat:t:<tid>` (tenant), `chat:u:<sub>` (user) and `chat:ip:<client ip>` (behind the module's `trusted_proxy_hops`). Each bucket's capacity and window come from env (`CHAT_TENANT_RATE`, `CHAT_USER_RATE`, `CHAT_IP_RATE`).
- **When a bucket is empty:** a 429 with `Retry-After`. This meets C3, C4 and C5.
- **Redis down or `REDIS_URL` unset:** the route returns 503, closed, never unlimited.
- **The key and the stream:** `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` move to the backend's env. The handler keeps the slice-0 body rules (only `message`, a non-empty string; the system prompt is server code, D-977) and streams the same `{type: text_delta | done | error}` SSE frames.
- **The client:** `ChatUI` posts to `${NEXT_PUBLIC_API_URL}/api/v1/chat` with `credentials: "include"` and the `X-CSRF-Token` header read from `__Host-csrf_token`, as every other cookie-authenticated mutation does.
- **CORS:** it is already credentialed with exact origins. The app origin must be in `CORS_ORIGINS`, and app and API hosts must be same-site (for example `app.x.com` and `api.x.com`), the same requirement `/auth/login/web` already carries.

## Rejected alternatives

- **B — keep the Next route handler and add a `verifySession()`.**
  - As B1 it verifies the HS256 JWT in Next, sharing `JWT_SECRET` with the frontend.
  - As B2 it forwards the cookie to a new backend `/auth/me`.
  - Rejected by all three judges. The host-only cookies (E1) never reach a Next host separate from the API without same-host path routing.
  - B1 widens the secret's blast radius, and both forms duplicate auth in a second stack and add a Redis client to the frontend.
- **C — a Next-side limiter alone.** Cut before the panel. It contradicts C1 (no identity check) and C3/C4 (in-process state).
- **A without D.** One judge ranked A first. All three favoured D first while A takes longer than one change. Slice 1 is a deletion that closes the exposure for every new scaffold now, so it ships first.
- **A per-key OpenRouter spend limit as the only control (E3).** Kept as a recommended owner-side backstop, not a design element. It caps damage but does not stop anonymous use, and it is an account action no scaffold can perform.
- **Next middleware/proxy as the gate.** C2 bans it as a security boundary.
- **Per-request limits only, without the tenant bucket.** C5 makes tenant keying mandatory.

## Lifecycle

- **Adoption:** new scaffolds get slice 1 the day it merges and slice 2 when it ships. Existing projects stay on their copies until their owners act, per their interim mails. The coordinator files one follow-up item per live project once slice 2 lands, so each can adopt the backend route.
- **Growth:** the bucket sizes are env, so a project raises them per plan tier without a code change. The escalation trigger is a project whose 429 rate on `/api/v1/chat` exceeds 1% of requests over a day, read from the backend's request metrics. That is the measured signal to wire limits to the plan tier from the database instead of from env.
- **Degradation:**
  - Redis unavailable: 503, closed, never unlimited.
  - OpenRouter error: an `error` SSE frame, unchanged from today.
  - A revoked token: 401 through the existing denylist.
- **Retirement:** if a project drops chat, it deletes the route and `ChatUI`. Slice 1's grader keeps the Next side from re-growing a key-bearing route.

## External dependencies

- **E1 — cookie prefixes.** "`__Host-`" cookies must be Secure, carry no `Domain`, and have `Path=/`, so they are "only sent to the host that set them". https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie (read 2026-10-18).
- **E2 — Next.js 15 route handlers.**
  - They read cookies through `request.cookies` / `cookies()` and stream through `new Response(new ReadableStream(...))`. https://nextjs.org/docs/app/api-reference/file-conventions/route (read 2026-10-18).
  - `middleware` was renamed `proxy` in v16.0.0, so 15.x keeps `middleware.ts`. https://nextjs.org/docs/app/api-reference/file-conventions/proxy (read 2026-10-18).
- **E3 — OpenRouter API keys.** A key takes an optional `limit` ("spending limit for the API key in USD"), and creating keys by API needs a management key. https://openrouter.ai/docs/api-reference/api-keys/create-api-key (read 2026-10-18).
- **Method:** grounded by a fabrik-researcher seat through WebFetch. The tier-2 engines (exa, firecrawl, brave) failed to connect this session, so no tier-2 cross-check exists. `/fabrik-plan-review` re-verifies these facts live.

## fabrik-lib verdict

| Capability | Verdict | Module | Why |
|---|---|---|---|
| End-user auth (identity on the chat request) | vendor (already vendored) | `/opt/fabrik-lib/fastapi-user-auth` | its `build_current_user` reads the header then the session cookie and checks the denylist; the scaffold's bearer-only `require_user` cannot serve a browser |
| Rate limiting (token bucket) | build, in the scaffold's backend | — | fabrik-lib has no general limiter. The only one is passwordless-specific inside fastapi-user-auth. A ~40-line Redis bucket on the existing client is smaller than a new module. Upstream note to fabrik-lib: a general limiter would serve every FastAPI scaffold |
| OpenRouter streaming | build (moved) | — | The existing Next handler's logic, ported to the backend |

## Shape and infra implications

- **Scaffold type:** `saas-skeleton`.
- **Redis:** slice 2 needs `REDIS_URL`, so `shape.needs_cache: true`. The backend already uses it for the jti denylist. A spec without it gets the 503-closed chat.
- **Env and Doc Sync:** `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` move from the frontend's env to the backend's. `CHAT_TENANT_RATE`, `CHAT_USER_RATE` and `CHAT_IP_RATE` are new. These are the Doc Sync rows for `.env.example` and `docs/CONFIGURATION.md` in the scaffold output.
- **No new port and no new service.**

## Documentation landing sites

- **The scaffolded project:**
  - `README.md` gets a chat section with the endpoint, the env vars and the same-site/CORS requirement.
  - `.env.example` and `docs/CONFIGURATION.md` get the moved and new env vars.
- **The hub:**
  - `CHANGELOG.md`, one entry per slice.
  - A `docs/DECISIONS.md` row for the D-then-A decision.
  - The `docs/reference/` scaffold page that describes saas-skeleton's backend routes, where one exists. Otherwise the plan names it.

## Validation

- **Slice 1:** a scaffold test asserts that a fresh saas-skeleton has no `app/api/chat/route.ts` and that no file under `app/api/` reads `OPENROUTER_API_KEY`. It is red on today's template.
- **Slice 2:** backend tests on the emitted app, through FastAPI's TestClient with a fake Redis and a fake OpenRouter.
  - Anonymous request: 401.
  - Valid session: 200 and a stream.
  - Each bucket exhausted: 429 with `Retry-After`.
  - `REDIS_URL` unset: 503.
  - A body that is not `{message: string}`: 400.
  - Every grader is proven red on a mutant that drops its guard.

## Decisions taken

- **DECISION (reversible):** D then A. Remove the unauthenticated Next chat route from the template now. Re-add chat as an authenticated, Redis-rate-limited backend route on the existing `v1` router. The panel ranked D, A, B twice and A, D, B once, and all three judges proposed this sequence.

## Open / blocking unknowns

- **Resolved:** whether the session cookie can reach a Next host. It can't (E1, cookies.py), which is why chat moves to the backend.
- **Resolved:** whether CORS permits credentialed calls. It does, with exact env origins (`src/fabrik/scaffold.py:3188-3196`).
- **Open:** whether SSE streams cleanly through `CsrfOriginMiddleware` and `CORSMiddleware`. Resolution step: slice 2's TestClient stream test, plus a scaffold-and-run probe in the plan.
- **Open:** the default bucket sizes. Resolution step: the plan proposes the defaults, derived from the OpenRouter model's per-token price and a stated daily budget, and records them in the D-row.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "the unauthenticated saas-skeleton /api/chat that spends an app's OpenRouter key" (coordinator, 2026-10-18) | IN | § Why this exists, § Chosen approach |
| I2 | "it's security" | IN | Constraints digest; full review in the plan |
| I3 | "the design trade-off you laid out (backend route vs /auth/me check vs Next-side limiter)" | IN | § Chosen approach (A), § Rejected alternatives (B = the /auth/me check, C = the Next-side limiter) |
| I4 | "The four live projects' interim mails are already out and recorded on the item" | IN | § Lifecycle, Adoption (a per-project follow-up after slice 2) |
| I5 | "needs a session/auth check and a rate limit before a scaffolded app goes public" (W-ab242b11) | IN | § Chosen approach, slice 2 (identity and three buckets) |
| I6 | "design the auth hook against the template's auth story (fastapi-user-auth / D-xxx)" (W-ab242b11 next) | IN | § What exists today (`require_user`, the cookie story) |
| I7 | "If the spec won't fit, get it to a resumable checkpoint and hand it off cleanly." | IN | met; the spec fits, and the checkpoint is kept in the run's scratch |

Intake: 7 items — 7 IN, 0 OUT-OF-SCOPE, 0 ASK.
