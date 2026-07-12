---
activation: glob
globs: ["**/auth/**", "**/security/**", "**/middleware/**", "**/.env", "**/.env.*", "**/secrets/**", "**/.ssh/**", "**/internal_auth.py", "**/*.key", "**/*.pem"]
description: Security & auth discipline — JWT rules, CORS policy, secret handling, CSP, session patterns, sensitive-file backup, generated-password policy, M2M internal-auth canonical pattern
trigger: glob
---
<!-- CONSUMER: Coding agents (all) + Traycer (tech-plan step)
     GOAL: Auth architecture (Pattern A: FastAPI / Pattern B: Supabase Auth), CORS, CSP, token storage, M2M auth
     TRAYCER USAGE: Referenced during tech-plan to decide auth pattern. Injects Pattern A or B into ticket ACs.
     AGENT USAGE: Follow the pattern specified in the ticket. Both patterns documented here. -->

# Security & Auth Rules

Apply when working on authentication, authorization, CORS, security headers, or session management. Skip for pure UI layout, database models, or infrastructure files.

---

## Identity Provider (project-type dependent)

The auth architecture depends on the project's scaffold type and domain module decisions. Two canonical patterns exist:

### Pattern A — FastAPI as sole IdP (self-hosted auth) — **DEFAULT**

**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — Argon2 + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `AGENTS.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.

- FastAPI owns credential hashing (Argon2), user state, token issuance, and validation.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- All clients (Next.js, React Native, Chrome Extension) are API consumers only.

### Pattern A-compat — FastAPI IdP on a Supabase-shaped schema (migration off Supabase Auth)

Use when a project is **migrating off Supabase Auth** but wants to retain its existing `auth.uid()`-based RLS policies, `auth.users` FKs/triggers, and `authenticated`/`service_role` grants **unchanged** — a verified zero-rewrite, zero-loss migration. This is a third, legitimate position ("Pattern A, Supabase-schema-compatible"), **not** a fork of Pattern A's token rules: FastAPI becomes the sole IdP and the token lifecycle is **exactly Pattern A** (Argon2 / 15-min HS256 access / 7-day opaque PG refresh / Redis denylist). The database keeps Supabase's **PostgreSQL contract**, now owned natively:

- **`auth` schema + `auth.users`** table — own it natively (`encrypted_password` holds the Argon2 hash). Existing FKs to `auth.users(id)` and triggers keep working with zero edits.
- **`auth.uid()` / `auth.jwt()` / `auth.role()`** SQL helpers, reimplemented over the `request.jwt.claims` GUC with Supabase-faithful semantics (definitions in `95-multi-tenant-saas.md` § compat mode).
- **`anon` / `authenticated` / `service_role`** roles — `NOLOGIN NOINHERIT`; `service_role` carries `BYPASSRLS`, mirroring Supabase's privileged key for M2M.
- **The GUC contract** — the app sets, per transaction, exactly what Supabase's PostgREST set from the JWT:
  ```sql
  SET LOCAL role = 'authenticated';   -- or 'service_role' for M2M
  SET LOCAL request.jwt.claims = '{"sub":"<user-uuid>","role":"authenticated"}';
  ```
  With these set, `auth.uid()` resolves to `<user-uuid>` and every existing policy enforces as before. Unset/invalid → `auth.uid()` returns `NULL` → deny (the invariant below).

Tenant isolation, the dual-mode RLS contract, the `auth.*` helper definitions, `fabrik_admin`, and the cross-tenant probe live in `95-multi-tenant-saas.md`. The canonical reference build is trade-intelligence's `000_native_auth.sql` (auth schema + helpers) + `053_force_rls_and_admin.sql` (FORCE RLS + `fabrik_admin`).

> **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).

### Pattern B — Supabase Auth + FastAPI backend (legacy / migration-only)

Use ONLY when a project **already runs on Supabase Auth** (a legacy or in-flight project). **Not for new work** — new user-facing products use Pattern A (`fabrik-lib/fastapi-user-auth`). A project still on Pattern B should plan its move to Pattern A / Pattern A-compat (see `AGENTS.md § Supabase`). The Supabase-JWT-validation guidance below remains authoritative for such projects.

- **Supabase Auth** handles user registration, login, password hashing, OAuth providers (including Sign in with Apple — mandatory on iOS if any social login is offered), email verification, and password reset.
- **FastAPI** handles custom business logic, M2M auth, and any endpoints that need data beyond what Supabase exposes. FastAPI validates Supabase JWTs per the Supabase JWT validation section below — it does not issue its own user tokens.
- **Authelia** protects admin/back-office dashboards via Traefik forward-auth. Not for end-user auth.
- For multi-tenant SaaS: Supabase RLS enforces tenant isolation at the database level. See `95-multi-tenant-saas.md` for full patterns.

**Which pattern?** **Pattern A by default** — every new project, including `saas-skeleton` / `mobile-app`. Use Pattern B only if the project *already* runs on Supabase Auth (its `spec.shape` / domain module says so and it hasn't migrated yet), and plan its move to Pattern A / Pattern A-compat.

---

## Token Lifecycle

### Pattern A (FastAPI-issued tokens)

- Issue **short-lived JWT access tokens** (15 minutes) signed with HS256.
- Issue **long-lived opaque refresh tokens** (7 days) stored in PostgreSQL alongside user and device metadata. Refresh tokens are not JWTs — they are cryptographically random strings.
- Deleting the refresh token ends the session — no new access tokens issue. The outstanding access token stays valid until its 15-min expiry (HS256 is stateless). For true instant revocation, add a short-TTL token denylist in Redis.
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- Use HS256 unless third-party external services must verify tokens without the signing key (only then consider RS256).

### Pattern B (Supabase-issued tokens)

- Supabase issues JWTs automatically on login. Token lifecycle is managed by Supabase — do not override.
- Refresh is handled by the Supabase client SDK (`supabase-js`, `supabase-py`). Do not build custom refresh logic.
- For server-side operations that need elevated privileges, use the Supabase `service_role` key (env var, never exposed to clients).

### Supabase JWT Validation (Pattern B) — canonical

- Confirm which signing algorithm the project uses BEFORE writing validation code. Supabase's default shifted from symmetric HS256 (legacy/older projects) to asymmetric ES256/RSA (new JWT signing keys). The two are NOT interchangeable.
- **Preferred:** validate via the Supabase client's `getClaims()` (`supabase-py` / `supabase-js`). It verifies asymmetric tokens LOCALLY against the JWKS public keys and automatically falls back to server-side `getUser()` for legacy HS256 tokens or an unknown `kid`. One call handles both signing models — no branching.
- **If hand-rolling** (no client lib): fetch JWKS from `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`, match the `kid` from the token header, verify the ES256/RSA signature, cache keys (respect the 10-min edge cache; re-fetch on unknown `kid` for rotation). **Warning:** this endpoint is EMPTY on HS256 projects — JWKS validation will silently fail. For HS256 projects, verify with the legacy JWT secret (symmetric) instead.
- **Signature is not validation.** EVERY path MUST also assert: `aud == "authenticated"`, `iss == https://<project-ref>.supabase.co/auth/v1`, and `exp` not passed. Verifying only the signature accepts tokens minted for other audiences.
- Do NOT call `getUser()` (a network round-trip) on every protected request when asymmetric keys are available — use local `getClaims()`; reserve the round-trip for the HS256 fallback.

## Factor VI (Processes) — Sticky Sessions

**CRITICAL: 12-Factor mandate.**

"Sticky sessions are a violation of twelve-factor and should never be used or relied upon."

"Session state belongs in 'a datastore that offers time-expiration, such as Memcached or Redis.'"

=> Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.

### ✅ Correct

```python
# Session state in Redis with TTL
session_data = redis_main.get(f"user_session:{session_id}")
if not session_data:
    redis_main.setex(f"user_session:{session_id}", 3600, user_data)
```

### ❌ Banned

```python
# Sticky session - process-specific state
user_cache[user_id] =  # In-process memory - VIOLATION
session_store[process_id][user_id] =  # Local disk - VIOLATION
```

## Token Storage by Client

| Client | Pattern A (FastAPI) | Pattern B (Supabase) |
|--------|---------------------|----------------------|
| **Next.js (Web)** | HttpOnly, Secure, SameSite=Lax cookie | `supabase-js` manages via cookie or localStorage (configure SSR cookie strategy) |
| **React Native** | `expo-secure-store` | `expo-secure-store` via `supabase-js` custom storage adapter |
| **Chrome Extension (MV3)** | `chrome.storage.session` | `chrome.storage.session` via `supabase-js` custom storage adapter |

- **Pattern A:** The FastAPI `/auth/login/web` endpoint returns a `Set-Cookie` header with `httponly=True`, `secure=True`, `samesite="lax"`. Mobile/extension endpoints return the token in the JSON response body. **CSRF:** cookie auth requires explicit CSRF defense — use `SameSite=Strict` on state-changing endpoints, or a double-submit CSRF token. `SameSite=Lax` alone does not cover all CSRF vectors (e.g., top-level GET navigations with side effects).
- **Pattern B:** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.

---

## Next.js Defense-in-Depth

- **Never rely solely on `middleware.ts` for access control.** CVE-2025-29927 allows complete middleware bypass via header manipulation.
- Use middleware only for UX redirects (e.g. redirect to `/login` if cookie missing).
- All Server Actions, Route Handlers, and Server Components that access sensitive data or perform mutations must call a `verifySession()` Data Access Layer utility that cryptographically validates the token with the backend (FastAPI or Supabase JWKS).

---

## CORS Policy

- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `allow_origins=["*"]` combined with `allow_credentials=True` is **banned** — browsers reject this combination and it signals misconfiguration.

| Client | Origin Pattern | Notes |
|--------|---------------|-------|
| **Next.js** | `https://app.example.com` | Exact match, no trailing slash |
| **React Native** | N/A (no browser CORS) | Native HTTP client — not subject to CORS |
| **Chrome Extension** | `chrome-extension://<id>` | Use `allow_origin_regex` in dev; exact ID in production |

---

## Content Security Policy

- Next.js `middleware.ts` must generate a per-request cryptographic nonce (`crypto.randomUUID()`) and build the full directive: `Content-Security-Policy: script-src 'nonce-{n}' 'strict-dynamic'; object-src 'none'; base-uri 'none'`.
- A bare nonce without `'strict-dynamic'` and locked-down fallbacks (`object-src 'none'`, `base-uri 'none'`) gives weaker protection than implied — always include the full directive.
- Only `<script>` tags with the matching `nonce` attribute execute. This forces dynamic SSR for protected routes — an acceptable trade-off for XSS protection.

---

## FastAPI Security Headers

Apply via ASGI middleware with **precomputed constants** (no per-request string building):

- `Strict-Transport-Security: max-age=31536000; includeSubDomains` — add `preload` **only** if deliberately submitting to the HSTS preload list (all-subdomains-HTTPS-forever, hard to reverse; not a safe blanket default)
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`

---

## Internal Service Auth (M2M)

Every Fabrik HTTP service uses the canonical internal-auth pattern. Docker-to-Docker communication within the `fabrik` network must NOT rely on network isolation alone.

| Aspect | Value |
|---|---|
| Header | `X-Internal-Token` |
| Env var | `SERVICE_INTERNAL_SECRET_KEY` (same value as `/opt/fabrik/.env`) |
| Module | `internal_auth.py` (copy into `app/` or `src/` of every service) |
| Import | `from internal_auth import require_internal_token` |
| Validation | `hmac.compare_digest` (constant-time) |
| Reject status | 403 |

**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.

**Calling another internal service (client side):**

```python
import httpx
from src.config import get_settings

async def call_internal_service():
    headers = {"X-Internal-Token": get_settings().service_internal_secret_key}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get("https://<service>.vps1.ocoron.com/api/endpoint", headers=headers)
    return resp.json()
```

Note: use internal Docker DNS (`http://<service>:<port>/api/endpoint`) for `fabrik`-network calls, NOT the public Traefik edge URL. Use `https://<service>.vps1.ocoron.com` only for genuinely cross-network calls. Always async, always with timeout, config via Pydantic Settings. See `58-resilience.md` for full timeout/retry/CB patterns.

**Blast radius warning:** the shared `SERVICE_INTERNAL_SECRET_KEY` is identical across all services — compromise of any one service exposes the M2M credential for all. Document a rotation procedure, and issue a **per-service token** (not the shared key) for any internet-exposed service or one ingesting untrusted input.

## Factor III (Config) — Environment Variables Only

**CRITICAL: 12-Factor mandate.**

"config is stored 'in environment variables'"

"litmus test: 'whether the codebase could be made open source at any moment, without compromising any credentials'"

"'env vars are granular controls, each fully orthogonal to other env vars' — 12F explicitly REJECTS batching config into named groups like 'development'/ 'production'."

=> Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)

### ✅ Correct

```python
# Environment variables only - granular and orthogonal
import os

database_url = os.getenv("DATABASE_URL", "postgresql://localhost:5432/default")
jwt_secret_key = os.getenv("JWT_SECRET_KEY")
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")

# Never: settings.production.database_url or config.production.yml
# Never: hardcoded defaults or secrets in source
```

### ❌ Banned

```python
# Grouped/named config sets - VIOLATION
from app.config.production import database_url  # BANNED
from settings import production as config       # BANNED

# Secrets in code - VIOLATION  
JWT_SECRET_KEY = "hardcoded-secret-value"     # BANNED
DATABASE_PASSWORD = "secret123"               # BANNED

# Cannot open source without compromising credentials - VIOLATION
```

---

## Sensitive Data Protection

Before editing `.env`, `*.key`, `*.pem`, files under `secrets/`, or `.ssh/`:

```bash
cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
```

- Destructive scripts on prod data: dry-run first, show diff.
- Credentials change: full diff approval before applying.

---

## Password Policy

For **programmatically generated** passwords (service accounts, DB users, internal tokens — NOT user-input passwords):

- **32 characters**, charset `[a-zA-Z0-9]` only (no symbols — survives `.env` round-trip + shell quoting).
- Generator: Python `secrets.choice(string.ascii_letters + string.digits)`.
- Banned literals: `postgres`, `admin`, `password`, `password123`, and any default vendor credential.

Applies to: Authelia bootstrap, `fabrik scaffold` credential generation, ops scripts.

---

## Rate Limiting

- Hard rate limits on `/auth/login`, `/auth/register`, `/auth/reset` endpoints using **Redis-backed** token buckets. In-memory buckets are per-process and bypassable behind multiple workers — single-process services only.
- Apply limits on **both** axes: per-IP (brute force) and per-account (credential stuffing).
- Credential stuffing and brute-force attacks are the primary threats these limits address.

---

## Transactional Email

For password resets, verification emails, receipts, and all transactional mail: use **Resend** via the MJML+Jinja2 pipeline defined in `86-email-templates.md`. Send compiled HTML via Resend API directly from FastAPI — no intermediate gateway.

Escalate mission-critical auth mail (reset, receipts) to **Postmark** only on measured deliverability issues. See `86-email-templates.md` § ESP Decision Log for rationale.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| `localStorage` / `sessionStorage` for JWTs | HttpOnly cookies (web), `expo-secure-store` (mobile), `chrome.storage.session` (ext) |
| `react-native-keychain` for Supabase tokens | `expo-secure-store` (Expo ecosystem standard) |
| AsyncStorage or MMKV for JWTs | `expo-secure-store` |
| Middleware-only authorization in Next.js | Verify session in Server Actions / Server Components via DAL |
| `allow_origins=["*"]` + `allow_credentials=True` | Explicit origin list from env vars |
| NextAuth.js / Clerk / Firebase Auth | FastAPI (Pattern A) or Supabase Auth (Pattern B) |
| RS256 for single-service signing + verification | HS256 with 256-bit secret (Pattern A only) |
| Hardcoded JWT secret in source | Pydantic Settings env var (`get_settings().jwt_secret_key`) |
| Trusting Docker network isolation alone | `X-Internal-Token` + shared secret |
| Custom refresh logic with Supabase Auth | Supabase client SDK handles refresh |
| `service_role` key exposed to client | Server-side only, via env var |
| `auth.uid()` / `current_tenant_id()` that raises or defaults on unset/invalid claims | `EXCEPTION WHEN OTHERS THEN RETURN NULL` (fail-closed deny) |
| Rewriting existing `auth.uid()` RLS policies when leaving Supabase Auth | Pattern A-compat — own `auth.*` + the `request.jwt.claims` GUC; policies stay unchanged |
| Broad `^/api/` Authelia bypass when only a sub-prefix is authenticated | `shape.bearer_bypass_prefix: "^/api/v1"` — bypass only the path the app authenticates |

---

## Related Rule Packs

- `10-python.md` — Pydantic Settings for secrets, `AsyncClient` for M2M calls
- `30-ops.md` — Authelia forward-auth Traefik labels, `/health` bypass, internal service DNS
- `55-observability.md` — GlitchTip for auth error tracking
- `58-resilience.md` — timeout/retry/CB for M2M inter-service calls
- `80-mobile.md` — Pattern B token storage (`expo-secure-store`), Sign in with Apple mandate
- `86-email-templates.md` — Resend pipeline for auth transactional email (ESP Decision Log in § ESP Decision Log)
- `95-multi-tenant-saas.md` — dual-mode RLS (native + Pattern A-compat) for tenant isolation; canonical `auth.uid()` / `current_tenant_id()` fail-closed helpers + `fabrik_admin`

---

## Done When

- [ ] Auth pattern (A or B) matches the project's domain module and scaffold type.
- [ ] Pattern A: FastAPI is the sole token issuer — no frontend auth libraries handle identity.
- [ ] Pattern B: Supabase Auth configured; FastAPI validates Supabase JWTs via JWKS; RLS enabled on tenant-scoped tables.
- [ ] Pattern A-compat: `auth` schema owned natively (`auth.users` + `auth.uid()/jwt()/role()` + `anon`/`authenticated`/`service_role`); app sets `role` + `request.jwt.claims` GUCs per transaction; token lifecycle stays Pattern A.
- [ ] Fail-closed verified: `auth.uid()` / `current_tenant_id()` return `NULL` on unset/invalid context (no-context probe → helper `NULL`, scoped read denies).
- [ ] Bearer bypass scoped: `shape.bearer_bypass_prefix` narrows the Authelia bypass to the actually-authenticated API prefix — no unauthenticated `/api/*` route left public by a default `^/api/` bypass.
- [ ] Web login uses HttpOnly + Secure + SameSite=Lax cookie (Pattern A) or Supabase SSR cookie strategy (Pattern B).
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- [ ] All Next.js Server Actions and data-fetching
…[truncated]