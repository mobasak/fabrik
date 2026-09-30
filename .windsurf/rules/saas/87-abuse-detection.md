---
activation: glob
globs: ["**/register/**", "**/signup/**", "**/fastapi_user_auth/**", "**/server/src/*/auth.py"]
description: Abuse detection discipline — registration gating, progressive unlock, fingerprinting, disposable email blocking for SaaS free tiers
trigger: glob
currency_pass: 2026-09-30
---
<!-- CONSUMER: Coding agents building registration/signup flows; planning (the launch checklist maps its phases to tickets)
     GOAL: layered anti-abuse for SaaS free tiers — verified email, per-IP account cap, disposable-email block, progressive unlock, then signals
     PLANNING USAGE: saas/88-saas-launch-checklist.md § Abuse Prevention cites this pack. Phase 1 items are launch-blocking.
     AGENT USAGE: guard the signup door the scaffold actually has open (§ Where it goes). Phase 1 at launch, Phase 2 before public launch, Phase 3 reactively. -->

# Abuse Detection — SaaS Anti-Fraud Playbook

Prevent free-tier farming, multi-account abuse, and credit/quota exploitation without adding friction for legitimate users. Applies to every SaaS project with a free tier or trial.

**Referenced by:** `saas/88-saas-launch-checklist.md` § Abuse Prevention

---

## The Problem

Free tiers attract abuse. A bad actor creates 100 accounts with disposable emails, farms 10 credits each (= 1,000 free credits), and gets the equivalent of a paid plan for $0. At small scale the infrastructure cost is noise; the real cost is **third-party API quota** (paid or daily-capped upstreams) that fake accounts burn.

---

## Where It Goes — the scaffold's signup doors

A saas-skeleton's identity provider is the vendored `fastapi-user-auth` module (`server/src/fastapi_user_auth/`), mounted by `build_saas_auth_router()` in `server/src/<pkg>/auth.py`. **Never add a second registration endpoint.** Its two doors, as the scaffold emits them:

| Door | State as emitted | Where the controls go |
|---|---|---|
| Password signup — `POST /auth/signup` → `201 {"user_id": …}` | **Always open.** No setting disables it, and it has no consumer hook and no per-IP bound | a pure ASGI middleware on this one path (below) |
| Passwordless auto-signup — inside `POST /auth/passwordless/verify` | **Closed**: the scaffold passes no `pending_store`, so the module falls back to a store that never matches. It opens only once a `RedisPendingLoginStore` is injected | the `on_signup_attempt` / `on_signup_complete` hooks of `build_auth_router(...)` |

**The password door is the one to guard first — it is the open one.** The module offers no seam there yet (upstream request filed from this pack's turn), so the guard is a pure ASGI middleware added in `main.py` that acts only on `POST /auth/signup`:

1. Buffer the JSON body and read `email`; resolve the client IP (next paragraph).
2. Run the Layer 1 checks; refuse with `422` (disposable domain) or `429` (per-IP cap) **before** the router runs.
3. Wrap `send`: when the router answers `201`, read `user_id` from the body and store `registration_ip` (and a fingerprint header, once Phase 2 collects one) on that user — without this write, the cap counts rows that never carry an IP and refuses nothing.
4. Test end to end: the third signup from one IP inside 24h returns `429`, and a disposable address returns `422`. A mocked count proves nothing here.

When a project opens the passwordless door, wire the same checks into the hooks, and read the module README's § Consumer signup seams first. `on_signup_attempt` takes **no arguments**: it receives neither the request nor the email, so bind both in a `ContextVar` from a pure ASGI middleware or an async dependency (a sync `def` dependency runs in a threadpool and its `.set()` never reaches the handler). Both hooks **fail open** on an unexpected error, a refusal has already spent the single-use code, and the hooks can double-fire under a create race — so every write they make must be idempotent. A disposable-domain refusal belongs at `POST /auth/passwordless/request` instead, before a code is minted and mailed.

**The client IP is the module's `client_ip(request, settings.trusted_proxy_hops)` — never the raw `X-Forwarded-For` header and never its left-most entry.** Every proxy appends the peer it saw, so the left-most value is whatever the client sent; keying a limit on it lets one attacker mint unlimited distinct keys. On the fleet, Traefik is the only public proxy (Cloudflare DNS is unproxied — `docs/infrastructure/vps-urls.md`), so `trusted_proxy_hops=1`. Putting a domain behind a CDN adds a hop — re-derive the count then, never raise it blindly. In a pure ASGI middleware, build `Request(scope)` and pass it to `client_ip`.

---

## Defense Layers

### Layer 1: Registration Gate

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **Email verification** | Account activates only once the address is proven (passwordless: the code itself is the proof) | Low | $0 |
| **Per-IP account cap** | Max 2 new accounts per IP per rolling 24h (`ABUSE_MAX_REG_PER_IP`) | None for most users | $0 |
| **Disposable email block** | Reject throwaway-inbox domains | None for real users | $0 |

- Credits/quota are granted only **after** verification — never on registration alone. On the password door that grant site is `POST /auth/verify-email`, which has no hook either: grant from the same kind of path-scoped middleware on its success response, or from the first authenticated request of a verified user.
- Store `registration_ip` (INET) and, once collected, `registration_fingerprint` (VARCHAR 64) on the user row.
- **The cap is a blunt instrument.** An office, a university or a mobile carrier's CGNAT puts many real users behind one IPv4 address, and one IPv6 user controls a whole /64 — so an exact-address count over-blocks the first and under-counts the second. Count IPv6 by its /64 prefix (the query in § Adaptation Checklist), return a message that says what to do next, and keep the default low only while the free tier is worth farming.
- **Never strip dots or a `+suffix` before storing.** Consumer Gmail (`gmail.com`) ignores dots and a `+suffix` in the local part, so `a.b+1@gmail.com` and `ab@gmail.com` are one inbox — but a Google Workspace domain does not ignore dots. Compare a normalised form when clustering accounts (dots only for `gmail.com`), and keep the address the user typed as the login.

### Layer 2: Progressive Resource Unlock

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **Progressive unlock** | 30% of the free-tier quota on verification, the remaining 70% 24h later | Low | $0 |

**Why it works:** a farm that automates signup and verification in minutes has to wait a day for each batch's full quota, which removes most of its return; a real user who signs up today finds the rest there tomorrow. The split and delay are env-tunable in the module (`ABUSE_IMMEDIATE_FRACTION`, `ABUSE_DELAY_HOURS`). Grant at most once per user: gate the immediate grant on `quota_unlocked_at IS NULL` in one conditional `UPDATE`, and queue the delayed row with `ON CONFLICT (user_id) DO NOTHING`.

### Layer 3: Behavioral Signals (flag, never block)

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **Browser fingerprint** | A hash of canvas/WebGL/fonts/screen, clustered across accounts | None | $0 (open-source library) |
| **Usage pattern analysis** | Accounts that burn quota within minutes of signup | None | $0 |
| **Shared IP clustering** | IPs with 3+ accounts — flag, do not block (offices, universities) | None | $0 |

- **A fingerprint is a clustering signal, not an identity.** The open-source FingerprintJS's own README puts its accuracy at 40–60%, with common collisions and IDs that last weeks; fine for "these five accounts look alike, review them", wrong as a block key. It is MIT-licensed again from its current major on; the major before it was BSL — never pin that one. ThumbmarkJS (MIT) is the maintained alternative. The signup bodies carry no fingerprint field, so send it as a request header and bind it in the middleware.
- **Collecting a fingerprint needs a legal basis first.** Fingerprinting reads the terminal, so ePrivacy Art. 5(3) applies — the same consent rule as cookies (EDPB Guidelines 2/2023, final version adopted 7 Oct 2024). Fraud prevention is a legitimate interest for the *processing* (GDPR Recital 47), but that does not answer the separate Art. 5(3) question, whose only relevant consent-free route is "strictly necessary" for the service the user asked for — narrow and judged per member state. For EU users, gate collection on consent or get counsel's sign-off. KVKK's cookie guide does not address fingerprints, so treat the hash as personal data under the general law.
- Background job (weekly): cluster same fingerprint + different emails; show the clusters in an admin "Suspicious accounts" panel for manual review.

### Layer 4: Phone Verification (last resort)

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **SMS OTP** | Require a phone number for the free tier | High | a base per-message rate plus carrier fees in the US, far more in some countries; a managed verify product bills per successful verification |

**When to use:** only when Layers 1–3 fail to contain abuse, and for the free tier only (paid users already have an identity via their payment method). ⚠️ **An SMS field is itself an attack surface** — SMS pumping (artificially inflated traffic) uses exactly this input to send OTPs to premium numbers the attacker is paid for. Before enabling it: restrict destination countries to the ones you serve, turn on the provider's fraud guard, rate-limit sends per IP and per number, and alert on send volume.

---

## Implementation Phases

### Phase 1: Quick wins (at launch, $0)

- [ ] The open signup door guarded (§ Where it goes), client IP from `client_ip()`, with the end-to-end test
- [ ] `registration_ip` (INET) stored on every new user row
- [ ] Per-IP account cap (2 per IP per rolling 24h; IPv6 counted per /64)
- [ ] Disposable-email blocklist checked on every signup
- [ ] Verification required before quota/credits activate

### Phase 2: Smart detection (before public launch)

- [ ] Progressive quota unlock (30% immediate, 70% after 24h), granted at most once
- [ ] Browser fingerprint collected — only where lawful (Layer 3)
- [ ] Admin panel: suspicious accounts (IP clusters, fingerprint matches)

### Phase 3: Reactive (only if abuse is detected post-launch)

- [ ] CAPTCHA on signup — Cloudflare Turnstile (free tier; works on sites not proxied through Cloudflare — check its current widget and hostname limits) or hCaptcha's free tier
- [ ] Quota velocity alerting (accounts burning 100% of quota within 1h of creation)
- [ ] Phone verification for the free tier only (Layer 4's preconditions first)

---

## Database Schema

`core/25-data-postgres.md` requires Alembic, but a saas-skeleton ships no Alembic baseline yet: until it has one, the idempotent `server/db/schema.sql` is its only DDL path, and the first baseline must absorb what was added there. Copy the module's `schema.sql` in whole — the block below is an excerpt — with the `delayed_grants.user_id` fix:

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_ip INET;
ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_fingerprint VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS quota_unlocked_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_users_registration_ip ON users(registration_ip);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- delayed_grants: the module ships user_id BIGINT; a saas-skeleton's users.id is UUID
CREATE TABLE IF NOT EXISTS delayed_grants (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    UUID        NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    amount     INTEGER     NOT NULL,
    release_at TIMESTAMPTZ NOT NULL,
    granted    BOOLEAN     NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

`registration_ip` and `registration_fingerprint` are personal data: name the purpose (fraud prevention) and a retention period in the privacy policy, and null both columns when it lapses (the data-retention TTL of `saas/88-saas-launch-checklist.md`).

---

## Disposable Email Domain Blocklist

Source: https://github.com/disposable-email-domains/disposable-email-domains (CC0; bot commits add domains most days; it also ships an `allowlist.conf` of domains often mistaken for disposable). The module ships a copy as `data/disposable-email-domains.txt`, loaded into a set once at import — and a vendored copy goes stale fast: the module's copy of 2026-06-29 held 5,477 domains when upstream held about 9,200 (2026-09-30). Refresh it on a schedule (or depend on the `disposable-email-domains` PyPI package, which mirrors the list) and restart the service after each refresh. Never hand-maintain a short list in code.

---

## Monitoring Metrics

Declare the counters on the private `REGISTRY` in `server/src/<pkg>/metrics.py` (per `core/55-observability.md` — name them without `_total`; the client appends it): e.g. `Counter("signup_refused", …, ["reason"], registry=REGISTRY)` and `Counter("abuse_check_failed_open", …, registry=REGISTRY)`. The fail-open counter only works if **your** code owns the failure path — the vendored `check_ip_rate_limit` returns `None` for both "allowed" and "database error", and the IdP swallows a hook's exception into a log line — which is why the checks are ported (§ Adaptation Checklist). Alert through Alertmanager. Starting thresholds (tune per product):

| Metric | Healthy | Alert threshold |
|---|---|---|
| New accounts per IP per day | 1–2 | > 3 |
| Accounts per fingerprint | 1 | > 2 |
| Time from registration to first resource use | > 5 min | < 30 sec |
| Free-tier quota burn | spread over days | 100% in < 1 hour |
| Disposable-email refusals | 0–1/day | > 10/day (attack in progress) |
| Abuse checks failed open | 0 | any, sustained 10 min |

---

## Reusable Module

**Do not implement from scratch.** Vendor from `/opt/fabrik-lib/abuse-prevention/`, without its caches and tests:

```bash
rsync -a --exclude='.*cache' --exclude='__pycache__' --exclude='test_*.py' \
  /opt/fabrik-lib/abuse-prevention/ server/libs/abuse_prevention/
```

Import it by its own directory, the way the scaffold imports `server/libs/audit_log` (`sys.path.insert` of that directory, then `import abuse_detection`) — the module README's `from libs.abuse_prevention import …` does not resolve in the scaffold. It provides `abuse_detection.py` (`check_ip_rate_limit`, `check_disposable_email`, `store_registration_metadata`), `progressive_unlock.py` (`split_quota`, `grant_immediate_quota`, `schedule_delayed_grant`, `release_due_grants`), `data/disposable-email-domains.txt` and `schema.sql`.

## Adaptation Checklist (after vendoring)

1. Apply the schema through `server/db/schema.sql` with the UUID `delayed_grants` (§ Database Schema).
2. **Port the two database checks to the async session; use the module for the domain set and the quota split.** The module speaks synchronous DB-API (psycopg) while the scaffold's request path is async SQLAlchemy on asyncpg, and its checks hide their own failures. The ported count, with IPv6 per /64:

   ```sql
   SELECT count(*) FROM users
   WHERE created_at > now() - interval '24 hours'
     AND registration_ip <<= network(set_masklen(CAST(:ip AS inet),
         CASE WHEN family(CAST(:ip AS inet)) = 6 THEN 64 ELSE 32 END))
   ```

   Wrap each ported query in a `try/except` that increments `abuse_check_failed_open` and allows the signup — a database hiccup must never block a real user, and must never go uncounted.
3. Use `check_disposable_email()` as-is (pure, in-memory). Never copy the module README's client-IP snippet: it takes the left-most `X-Forwarded-For` entry and is spoofable.
4. `split_quota()` + a delayed-grant insert with `ON CONFLICT (user_id) DO NOTHING` if the project has a credit/quota system; run the release from the worker's schedule, porting `release_due_grants()` to the async session the same way.
5. Fingerprint collection and the suspicious-accounts panel: Phase 2, lawful basis first.

---

## Banned Patterns

| Pattern | Instead |
|---|---|
| Keying a limit on the raw `X-Forwarded-For` header or its left-most entry | `client_ip(request, settings.trusted_proxy_hops)` |
| A second registration endpoint beside the IdP's | a path-scoped middleware on `POST /auth/signup`; the hooks on the passwordless door |
| Wiring only the passwordless hooks while `/auth/signup` stays open | guard the open door first |
| Granting credits or quota on registration alone, or twice | grant on verification, once (`quota_unlocked_at`, `ON CONFLICT`) |
| Blocking on a fingerprint match or a shared IP | flag for review; block only on the per-IP cap and the blocklist |
| Collecting a fingerprint from EU users with no consent and no counsel sign-off | gate it on consent (Layer 3) |
| A hand-kept short list of disposable domains in code | the upstream list, refreshed on a schedule |
| Enabling SMS OTP with no country allow-list, fraud guard or send rate limit | Layer 4's preconditions |
| An abuse check that fails open with no counter | own the failure path; `abuse_check_failed_open` + an alert |

## Related Rule Packs

- `saas/88-saas-launch-checklist.md` — the launch gate that cites this pack's phases
- `core/35-security-auth.md` — request rate limits on the auth endpoints (Redis token buckets); this pack's cap counts ACCOUNTS, not requests
- `core/25-data-postgres.md` — the migration path for the schema additions
- `core/55-observability.md` — counters and alerting
- `saas/95-multi-tenant-saas.md` — per-tenant rate limiting once the account exists

## Done When

- [ ] Every open signup door carries the Phase 1 controls, proven by the end-to-end test (third signup from one IP → `429`, disposable address → `422`)
- [ ] The client IP comes from `client_ip()`, and `trusted_proxy_hops` matches the proxies actually in front
- [ ] No credit or quota is granted before verification, or more than once
- [ ] Refusals and fail-opens are counted, and an alert fires on a sustained fail-open
- [ ] Fingerprinting, if enabled, has its lawful basis recorded; IP and fingerprint columns have a retention period
