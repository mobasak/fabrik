# Plan — saas-skeleton chat only a signed-in, rate-limited user can spend (W-ab242b11)

Status: DRAFT
Profile: small
**Owner:** fleet
**Surface:** `git rev-parse HEAD` = c948d00ba at authoring, plus the spec amendment in this commit.

Spec: `docs/superpowers/specs/2026-10-18-saas-skeleton-chat-auth-design.md` (DRAFT, `Size: small`, `Profile: full`; D then A). `/fabrik-plan-review` grades its sections together with this plan and flips both at its approval gate.

Estimated diff: about 260 code lines across 4 code files:
- `src/fabrik/scaffold.py`: the chat route, the bucket and the env, in the emitted backend;
- `templates/saas-skeleton/components/chat/SSEStream.tsx`: credentials and the CSRF header;
- `templates/saas-skeleton/components/chat/index.ts`;
- `templates/saas-skeleton/README.md`;
- one deletion, `templates/saas-skeleton/app/api/chat/route.ts`.

Tests: about 300 lines in two new files.

## What this plan is

Two slices, in order:
- **Phase A** (spec § Chosen approach, slice 1) removes the public, key-burning Next route from the template.
- **Phase B** (spec § Chosen approach, slice 2) re-adds chat as an authenticated, Redis-rate-limited backend route.
- **Phase C** is the integration review and the ledgers.

The six live projects keep their copies until their own follow-up items (spec § Lifecycle).

## Intake Inventory

The spec's Intake Inventory: 7 items, all IN (spec § Intake Inventory). This plan adds none and drops none.

## What we already agreed (citations, not restatement)
- The goal: spec § Goal.
- The two-slice approach and its order: spec § Chosen approach; the panel result is in spec § Decisions taken.
- Identity is the vendored `build_current_user`, not `require_user`: spec § Chosen approach, slice 2 (amended at authoring, after `src/fabrik/scaffold.py:2529-2539` showed `TenantMiddleware` is bearer-only).
- The rejected alternatives: spec § Rejected alternatives.
- The external facts: spec § External dependencies (E1-E3).

## Global Constraints (every phase inherits these)
- The rows of spec § Constraints digest (C1-C5) bind every phase.
- Never edit another repo; the six live projects are out of scope (spec § Lifecycle).
- Every test runs through `/opt/fabrik/scripts/capped_run.sh`.
- Every grader is red-proven on a mutant in a throwaway worktree, never in this checkout.

## Phase A — remove the public chat route (slice 1)

Appetite: 30

**Steps:**
1. Write `tests/test_saas_chat_route_removed.py` first, and see it red on today's template. It scaffolds a fresh saas-skeleton into `tmp_path` with `create_project` and asserts three things:
   - no `app/api/chat/route.ts` exists;
   - no file under `app/api/` contains `OPENROUTER_API_KEY`;
   - `components/chat/index.ts` does not export `ChatUI`.
2. Delete `templates/saas-skeleton/app/api/chat/route.ts`, and drop the `ChatUI` export from `templates/saas-skeleton/components/chat/index.ts` (the component file stays for Phase B).
3. Replace the README example at `templates/saas-skeleton/README.md:76-80` with one line: chat is served by the backend `POST /api/v1/chat` once Phase B lands.
4. Run the new test green, then the existing saas-skeleton scaffold tests (`command grep -l saas-skeleton tests/` gives the census), one file at a time.

**Behavior Contract:**
| # | Behaviour | Test | Spec |
|---|---|---|---|
| A1 | A fresh scaffold ships no Next chat route | `test_a_fresh_scaffold_has_no_next_chat_route` | spec § Chosen approach, slice 1 |
| A2 | No Next API route reads the OpenRouter key | `test_no_next_api_route_reads_the_openrouter_key` | spec § Validation |

**Gate:** `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q tests/test_saas_chat_route_removed.py`

## Phase B — authenticated, rate-limited backend chat (slice 2)

Appetite: 120

**Steps:**
1. Write `tests/test_saas_chat_backend.py` first. It scaffolds a saas-skeleton, imports the emitted `server` app (as the existing saas backend tests do; the census is in step 6), fakes Redis with a fake that implements the commands the bucket uses, and fakes the OpenRouter HTTP call with an `httpx` mock. Its cases:
   - anonymous: 401;
   - bearer-authenticated: 200 with `text_delta` and `done` frames;
   - cookie-authenticated without the CSRF header: 403;
   - cookie-authenticated with it: 200;
   - each of the tenant, user and IP buckets exhausted: 429 with `Retry-After`;
   - `REDIS_URL` unset: 503;
   - a body that is not a non-empty `message` string: 400.

   See them red before step 2.
2. In `_SAAS_MAIN_PY` (`src/fabrik/scaffold.py:3098`), add `chat_user = build_current_user(secret=…, denylist=…, session_cookie_secure=…)`, built from the same settings the auth router uses (`src/fabrik/scaffold.py:2631-2660`). Then add `@v1.post("/chat")` before `app.include_router(v1)` (`src/fabrik/scaffold.py:3290`), depending on `chat_user`.
3. In the same emitted module, add the token bucket: one Redis `INCR` plus `EXPIRE` window counter per key (`chat:t:<tenant_id>`, `chat:u:<user_id>`, `chat:ip:<client ip>`). The capacity and window come from `CHAT_TENANT_RATE`, `CHAT_USER_RATE` and `CHAT_IP_RATE` (`<count>/<seconds>`, with defaults stated in the D-row). The client IP honours the module's `trusted_proxy_hops`. When Redis is absent it returns 503 and never passes.
4. Port the OpenRouter streaming from the deleted Next route: the body rule (only `message`, a non-empty string), the server-side system prompt, and the same SSE frame shapes. Stream with `httpx.AsyncClient` (already a backend dependency, `src/fabrik/scaffold.py:2072`). `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` are read from the backend env. The emitted `.env.example` and `docs/CONFIGURATION.md` gain them and the three rate vars.
5. Client: `SSEStream.tsx`'s fetch (`templates/saas-skeleton/components/chat/SSEStream.tsx:32`) sends `credentials: "include"` and the `X-CSRF-Token` header read from the `__Host-csrf_token` cookie. Re-export `ChatUI`. The README documents the endpoint, the env vars and the same-site plus `CORS_ORIGINS` requirement (spec § Chosen approach).
6. Run the new test green, then the existing saas backend scaffold tests one file at a time, and `ruff` on the scaffold.

**Behavior Contract:**
| # | Behaviour | Test | Spec |
|---|---|---|---|
| B1 | An anonymous chat request is refused | `test_anonymous_chat_is_401` | spec § Chosen approach, slice 2 (Identity) |
| B2 | A signed-in user (bearer or cookie with CSRF) streams a reply | `test_signed_in_chat_streams` | spec § Chosen approach, slice 2 |
| B3 | A cookie-borne request without the CSRF token is refused | `test_cookie_chat_without_csrf_is_403` | spec § Chosen approach, slice 2 (Identity) |
| B4 | Each bucket, when exhausted, answers 429 with Retry-After | `test_each_bucket_exhausted_is_429` | spec § Chosen approach, slice 2 (Limits) |
| B5 | No Redis means closed, never unlimited | `test_no_redis_is_503` | spec § Lifecycle, Degradation |
| B6 | Only a non-empty string `message` is accepted | `test_bad_body_is_400` | spec § Validation |

**Gate:** `/opt/fabrik/scripts/capped_run.sh -- .venv/bin/python -m pytest -q tests/test_saas_chat_backend.py`

## Phase C — integration review and ledgers

Appetite: 60

1. Run the full `/fabrik-review` over Phase A and Phase B's commits. It is a heavy surface (auth), so it is never the scoped review. Seats are sized by `dispatch_headroom.py`, and the receipt goes under `docs/development/reviews/`.
2. Ledgers:
   - a `docs/DECISIONS.md` row with the D-then-A decision, the bucket defaults and their derivation (spec § Open / blocking unknowns);
   - a `CHANGELOG.md` entry per slice;
   - the work item closed on Phase B's code commit.
   The coordinator then files one follow-up item per live project (spec § Lifecycle).

**Gate:** `python3 scripts/final_gate.py --json` → `status: "success"`.

## Behavior Contract
- **Given** a fresh saas-skeleton scaffold, **When** its tree is listed, **Then** no `app/api/chat/route.ts` exists and no `app/api/` file reads `OPENROUTER_API_KEY` (A1, A2).
- **Given** no credentials, **When** `POST /api/v1/chat`, **Then** 401 and no OpenRouter call (B1).
- **Given** a valid bearer token, or the session cookie plus the matching `X-CSRF-Token`, **When** `POST /api/v1/chat {message}`, **Then** 200 with `text_delta` frames and a `done` frame (B2).
- **Given** the session cookie without the CSRF token, **When** `POST /api/v1/chat`, **Then** 403 (B3).
- **Given** the tenant, user or IP bucket is exhausted, **When** `POST /api/v1/chat`, **Then** 429 with `Retry-After` (B4).
- **Given** `REDIS_URL` is unset, **When** `POST /api/v1/chat`, **Then** 503, never an unlimited call (B5).
- **Given** a body that is not `{message: <non-empty string>}`, **When** `POST /api/v1/chat`, **Then** 400 (B6).
- **Mocked:** Redis (an in-memory fake implementing INCR/EXPIRE/TTL) and the OpenRouter HTTP endpoint (an httpx transport mock). Real: the emitted FastAPI app, the vendored fastapi-user-auth dependency, CSRF and CORS middleware, and JWTs signed with the test secret.

## Touches
- `templates/saas-skeleton/app/api/chat/route.ts` (deleted)
- `templates/saas-skeleton/components/chat/index.ts`
- `templates/saas-skeleton/components/chat/SSEStream.tsx`
- `templates/saas-skeleton/README.md`
- `src/fabrik/scaffold.py`
- `tests/test_saas_chat_route_removed.py` (new)
- `tests/test_saas_chat_backend.py` (new)

## Context Files
- `docs/superpowers/specs/2026-10-18-saas-skeleton-chat-auth-design.md`
- `/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/dependencies.py`
- `/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/csrf.py`
- `/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/cookies.py`

## Evidence
- `src/fabrik/scaffold.py:2529-2539`: `TenantMiddleware` reads only `Authorization: Bearer`. That is why Phase B depends on `build_current_user` and not on `require_user` (`src/fabrik/scaffold.py:2737`).
- `/opt/fabrik-lib/fastapi-user-auth/fastapi_user_auth/csrf.py:307`: the CSRF token gate covers every cookie-borne non-bearer mutation. That is why B3 exists.
- `src/fabrik/scaffold.py:3188-3196`: CORS is credentialed with exact env origins.

```text
$ python3 scripts/enforcement/check_spec_convergence.py <the spec copied with Status: CONVERGED>
spec convergence: 1 CONVERGED spec(s) examined of 1 named, 0 with findings (artifact-only; citations not re-fetched)
```

## Self-audit
- Every phase carries an Appetite (30, 120, 60), a Behaviour Contract that cites the spec, and a runnable Gate.
- The plan restates nothing the spec says; it only cites it.
- Open items carried from the spec: the bucket defaults (decided at Phase C's D-row from the model's price), and SSE through the two middlewares (settled by B2's stream test). Neither is deferred to the operator.

## Residual unknowns
- Whether the emitted backend's existing tests import `server` in a way the new Phase B test can reuse. The census is in Phase B step 6. If none does, the new test builds the app the same way the scaffold smoke tests do.
