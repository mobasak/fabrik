---
activation: glob
globs: ["**/auth/**", "**/security/**", "**/middleware/**", "**/.env", "**/.env.*", "**/secrets/**", "**/.ssh/**", "**/internal_auth.py", "**/*.key", "**/*.pem"]
description: Security & auth discipline — JWT rules, CORS policy, secret handling, CSP, session patterns, sensitive-file backup, generated-password policy, M2M internal-auth canonical pattern
---

# Security & Auth Rules

Apply when working on authentication, authorization, CORS, security headers, or session management. Skip for pure UI layout, database models, or infrastructure files.

## Identity Provider

- FastAPI is the **sole identity provider**. It owns credential hashing (Argon2), user state, token issuance, and validation.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth. All clients (Next.js, React Native, Chrome Extension) are API consumers only.

## Token Lifecycle

- Issue **short-lived JWT access tokens** (15 minutes) signed with HS256.
- Issue **long-lived opaque refresh tokens** (7 days) stored in PostgreSQL alongside user and device metadata. Refresh tokens are not JWTs — they are cryptographically random strings.
- To revoke access instantly, delete the refresh token from the database.
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via environment variable. Never hardcode it.
- Use HS256 unless third-party external services must verify tokens without the signing key (only then consider RS256).

## Token Storage by Client

| Client | Storage | Transmission | Threat Mitigated |
|--------|---------|-------------|-----------------|
| **Next.js (Web)** | HttpOnly, Secure, SameSite=Lax cookie | Automatic (Cookie header) | XSS exfiltration |
| **React Native** | OS secure enclave (`react-native-keychain`) | `Authorization: Bearer` | Device compromise |
| **Chrome Extension (MV3)** | `chrome.storage.session` | `Authorization: Bearer` | Ephemeral worker state / XSS |

- The FastAPI `/auth/login/web` endpoint returns a `Set-Cookie` header with `httponly=True`, `secure=True`, `samesite="lax"`.
- The FastAPI `/auth/login/mobile` and `/auth/login/extension` endpoints return the token in the JSON response body.

## Next.js Defense-in-Depth

- **Never rely solely on `middleware.ts` for access control.** CVE-2025-29927 allows complete middleware bypass via header manipulation.
- Use middleware only for UX redirects (e.g. redirect to `/login` if cookie missing).
- All Server Actions, Route Handlers, and Server Components that access sensitive data or perform mutations must call a `verifySession()` Data Access Layer utility that cryptographically validates the token with the FastAPI backend.

## CORS Policy

- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `allow_origins=["*"]` combined with `allow_credentials=True` is **banned** — browsers reject this combination and it signals misconfiguration.

| Client | Origin Pattern | Notes |
|--------|---------------|-------|
| **Next.js** | `https://app.example.com` | Exact match, no trailing slash |
| **React Native** | N/A (no browser CORS) | Native HTTP client — not subject to CORS |
| **Chrome Extension** | `chrome-extension://<id>` | Use `allow_origin_regex` in dev; exact ID in production |

## Content Security Policy

- Next.js `middleware.ts` must generate a per-request cryptographic nonce (`crypto.randomUUID()`) and inject it into the `Content-Security-Policy` header.
- Only `<script>` tags with the matching `nonce` attribute execute. This forces dynamic SSR for protected routes — an acceptable trade-off for XSS protection.

## FastAPI Security Headers

Apply via ASGI middleware with **precomputed constants** (no per-request string building):

- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`

## Internal Service Auth (M2M)

Every Fabrik HTTP service uses the canonical internal-auth pattern. Docker-to-Docker communication within the Coolify network must NOT rely on network isolation alone.

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
import os, httpx
headers = {"X-Internal-Token": os.environ["SERVICE_INTERNAL_SECRET_KEY"]}
resp = httpx.get("https://<service>.vps1.ocoron.com/api/endpoint", headers=headers)
```

## Sensitive Data Protection

Before editing `.env`, `*.key`, `*.pem`, files under `secrets/`, or `.ssh/`:

```bash
cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)
```

- Destructive scripts on prod data → dry-run first, show diff.
- Credentials change → full diff approval before applying.

## Password Policy

For **programmatically generated** passwords (service accounts, DB users, internal tokens — NOT user-input passwords):

- **32 characters**, charset `[a-zA-Z0-9]` only (no symbols — survives `.env` round-trip + shell quoting).
- Generator: Python `secrets.choice(string.ascii_letters + string.digits)`.
- Banned literals: `postgres`, `admin`, `password`, `password123`, and any default vendor credential.

Applies to: Authelia bootstrap, `fabrik scaffold` credential generation, ops scripts.

## Rate Limiting

- Hard rate limits on `/auth/login`, `/auth/register`, `/auth/reset` endpoints using Redis or in-memory token buckets.
- Credential stuffing and brute-force attacks are the primary threats these limits address.

## Transactional Email

- Use **Fabrik Email Gateway** (Resend + SES, already deployed at port 3000) for password resets and verification emails. Do not introduce additional email providers.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| `localStorage` / `sessionStorage` for JWTs | HttpOnly cookies (web), secure enclave (mobile), `chrome.storage.session` (ext) |
| Middleware-only authorization in Next.js | Verify session in Server Actions / Server Components via DAL |
| `allow_origins=["*"]` + `allow_credentials=True` | Explicit origin list from env vars |
| NextAuth.js / Clerk / Firebase Auth | FastAPI as sole IdP |
| RS256 for single-service signing + verification | HS256 with 256-bit secret |
| Direct SMTP / additional email providers | Fabrik Email Gateway (port 3000) |
| Hardcoded JWT secret in source | `os.getenv("JWT_SECRET_KEY")` |
| Trusting Docker network isolation alone | `X-Internal-Token` + shared secret |

---

## Done When

- [ ] FastAPI is the sole token issuer — no frontend auth libraries handle identity.
- [ ] Web login endpoint sets HttpOnly + Secure + SameSite=Lax cookie.
- [ ] Mobile/extension login endpoints return token in JSON body only.
- [ ] All Next.js Server Actions and data-fetching Server Components call `verifySession()`.
- [ ] CORS origins loaded from environment variables — no wildcards with credentials.
- [ ] CSP nonce injected per-request in Next.js middleware.
- [ ] FastAPI responses include HSTS, X-Content-Type-Options, X-Frame-Options headers.
- [ ] Auth endpoints have rate limiting configured.
- [ ] Internal service calls use `X-Internal-Token` header validation.

## Spec contract — auth registrars

Public services with admin UI behind 2FA: set `shape.is_admin_dashboard: true` — the Authelia registrar will add a per-domain rule on `fabrik apply`. API services with bearer auth on `/api/*`: set `shape.has_bearer_api: true`. Don't add Traefik `authelia-forward` middlewares manually — the scaffolder + registrars emit them.
