# W-ab242b11 — resume after plan-review round 1 (fleet, 2026-10-18)

## RESUME

Restart: `/fabrik-spec docs/superpowers/specs/2026-10-18-saas-skeleton-chat-auth-design.md` as an amendment. Re-ground the design on findings F1-F14 below, then run `/fabrik-spec-review`, then `/fabrik-plan-after-chat` (re-plan from the DRAFT plan `docs/development/plans/2026-10-18-plan-2-saas-chat-auth.md`), then `/fabrik-plan-review`.

Why the loop stopped:
- Round 1 of the joint spec+plan review confirmed a foundation error in the spec (F1).
- It also confirmed scope (F6, F7, F8) that outgrows `Size: small`, at more than 5 code files.
- Per `/fabrik-plan-review`'s escape hatch, the `Size: small` line was removed from the spec, and the spec goes to `/fabrik-spec-review` first.
- Quota: mob 5h at 84%, about 40 minutes to the wall, so the redesign could not fit this window.

Round-1 pins: spec md5 96147198da673d01f673ececd66b3f63 and plan md5 2faaf91bd6be15c8f9f862cbd9616109, at code commit aa680952c.

## Round 1 — confirmed findings

| F | Doc | Finding | Evidence |
|---|---|---|---|
| F1 | spec § Why, § Rejected B, § Open | **Foundation.** The emitted compose already serves `/api` and `/auth` on the APP host (Traefik `PathPrefix(/api)` or `PathPrefix(/auth)` on the same Host, priority 100). So the deployed Next `/api/chat` is shadowed and reachable only under `next dev`/`next start` or a custom topology. The `__Host-` cookies DO reach Next, which makes B's stated rejection reason false. A is same-origin, so its CORS/same-site paragraph describes a non-default shape. | `src/fabrik/scaffold.py:3392`; `tests/test_scaffold_saas_web_wiring.py::test_auth_urls_on_the_app_host_reach_the_backend` |
| F2 | spec slice 2 Client | The CSRF cookie is host-only, and `/auth/login/web` returns only `{"status":"ok"}`. The CSRF gate also needs an allowed `Origin` (`AUTH_ALLOWED_ORIGINS`, or `CORS_ORIGINS` plus `NEXT_PUBLIC_APP_URL`). Same-host (F1) resolves the cookie half; the tests must send `Origin` and the `__Host-` cookies over https. | `cookies.py:89-103`; `router.py:436`; `csrf.py:314-324`; `scaffold.py:2618-2627` |
| F3 | spec Limits | `AuthedUser.tenant_id` is None for passwordless logins (on by default) and for password logins without a tenant, so `chat:t:None` becomes one global bucket. A rule and a test row are needed. | `dependencies.py:15,57`; `router.py:53,391,1203-1205` |
| F4 | spec Degradation; plan B5 | `build_current_user` awaits `denylist.contains` unguarded, and `RedisDenylist.contains` raises when Redis is down, so a Redis outage gives a 500, not a 503. The scaffold's own `token_revoked` fails OPEN. Needed: a 503 adapter plus a down-Redis test. | `dependencies.py:98`; `tokens.py:118-119`; `scaffold.py:2702-2723` |
| F5 | plan Phase A, Touches | Deleting `route.ts` breaks `tests/test_saas_skeleton_chat_system_prompt.py` (D-977's grader; node 24 is present, so it runs). Port its behaviours (no client system prompt; the 400 matrix including invalid JSON and null) to the backend tests and retire the file. | `tests/test_saas_skeleton_chat_system_prompt.py:25-26` |
| F5a | slice 1 (done) | Slice 1 retired the route-executing tests. The owed list is the module docstring and the `SLICE2_HOSTILE_FIELDS` / `SLICE2_BAD_BODIES` constants of `tests/test_saas_skeleton_chat_system_prompt.py`; slice 2's backend tests import them. | W-ab242b11 slice 1 |
| F6 | plan Phase B step 1; spec § Validation | The hub `.venv` cannot import the emitted backend: argon2, uuid_utils, redis, asyncpg and email-validator are missing. No test drives `main.app`, and `test_scaffold_saas_web_wiring.py` loads vendored modules by path into a bare Starlette app. Decide between a per-test venv from `server/requirements-dev.txt` and the isolated-module pattern. Name the fake-Redis injection point (`_denylist()` builds its own client). | `find_spec` output; `tests/test_scaffold_saas_web_wiring.py:121-135` |
| F7 | plan B steps 2-3 | `main.py`'s imports lack `build_current_user` and the private `_denylist`. `client_ip` (`router.py:139`) is not exported, and re-implementing X-Forwarded-For parsing reopens the spoof class it documents. | `scaffold.py:3123-3130`; `router.py:139-145` |
| F8 | spec Env; plan Touches | There is ONE root `.env.example`, handed to web, api and worker by `env_file: .env`, so moving the key still lands it in the Next container. Also in scope: `templates/saas-skeleton/.env.example:26-29`, `README.md:26,56,85,138-140`, the orphaned `lib/config/chat.ts`, and the `ChatUI.tsx:65` comment. `docs/CONFIGURATION.md` comes from `CONFIGURATION_TEMPLATE.md` (`scaffold.py:300`). | seat greps |
| F9 | plan B6 | The emitted app maps `RequestValidationError` to 422. Either parse the raw body to keep 400 or accept 422. | `scaffold.py:3215-3217` |
| F10 | spec Lifecycle Growth | The 429-rate trigger has no data source: `REQUEST_COUNT` is declared and never incremented. | `scaffold.py:1712,1723,1731` |
| F11 | plan B rows | Missing rows: key unset (503 today); the OpenRouter non-2xx error frame; a revoked token (401); invalid JSON and null bodies; the stream through three `BaseHTTPMiddleware` layers. | `route.ts:30-37` |
| F12 | spec C4/C5 | C4 (`35:332`) governs the `/auth/*` routes only. C5 (`saas/95-multi-tenant-saas.md:166`) mandates middleware with plan-tier limits, and env per-route limits deviate. Record the deviation in a D-row, or wire tiers. | the pack lines |
| F13 | consistency | I4 says "four" where the body says six. The size lines disagree. The plan's httpx cite should be `scaffold.py:2255`, not `:2072`. The census `grep -l` lacks `-r`, and the "census in step 6" cross-reference is wrong. The spec's `ChatUI` reference list misattributes `index.ts`. | both seats |
| F14 | plan bucket | The defaults are unstated (circular with Phase C's D-row). INCR then EXPIRE is non-atomic, and a crash leaves a TTL-less key that blocks forever. Use one atomic op. | Sonnet seat |

## What still holds
- The direction: no key-bearing, unauthenticated chat in the template, the backend as the single auth stack, and Redis-backed, fail-closed limits. All three judges and both seats agree.
- Slice 1 (delete the Next route, with F5 folded in) is still right and small. It can ship alone as a /fabrik-task if the coordinator wants. F1 lowers its urgency: in the default deploy the route is shadowed.
