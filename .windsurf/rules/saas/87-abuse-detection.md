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
     AGENT USAGE: wire the controls into the scaffold's own signup doors (§ Where it goes). Phase 1 at launch, Phase 2 before public launch, Phase 3 reactively. -->

# Abuse Detection — SaaS Anti-Fraud Playbook

Prevent free-tier farming, multi-account abuse, and credit/quota exploitation without adding friction for legitimate users. Applies to every SaaS project with a free tier or trial.

**Referenced by:** `saas/88-saas-launch-checklist.md` § Abuse Prevention

---

## The Problem

Free tiers attract abuse. A bad actor creates 100 accounts with disposable emails, farms 10 credits each (= 1,000 free credits), and gets the equivalent of a paid plan for $0. At small scale the infrastructure cost is noise; the real cost is **third-party API quota** (paid or daily-capped upstreams) that fake accounts burn.

---

## Where It Goes — the scaffold's signup doors

A saas-skeleton's identity provider is the vendored `fastapi-user-auth` module (`server/src/fastapi_user_auth/`, wired in `server/src/<pkg>/auth.py` by `build_auth_router(...)`). **Never add a second registration endpoint** — put the controls on the doors that already exist:

| Door | Route | Hook for the controls |
|---|---|---|
| Passwordless auto-signup (default: `passwordless_auto_signup=True`) | `POST /auth/passwordless/verify` | `on_signup_attempt` (refuse → `429`) and `on_signup_complete(uid)` (store metadata), passed to `build_auth_router` |
| Password signup | `POST /auth/signup` | **none yet** — the router has no seam and no per-IP cap on this door. Until the module adds one, a project that enables it adds a path-scoped dependency and tests that it refuses; never claim Phase 1 on this door otherwise |

Read the module README's § Consumer signup seams before wiring: both hooks **fail open** on an unexpected error (a bug in `on_signup_attempt` lets the signup through, unrecorded), a refusal has already spent the single-use code, and the hooks can double-fire under a create race, so make them idempotent.

**The client IP is the module's `client_ip(request, settings.trusted_proxy_hops)` — never the raw `X-Forwarded-For` header and never its left-most entry.** Every proxy appends the peer it saw, so the left-most value is whatever the client sent; keying a limit on it lets one attacker mint unlimited distinct keys. On the fleet, Traefik is the only proxy (Cloudflare DNS is unproxied — `docs/infrastructure/vps-urls.md`), so `trusted_proxy_hops=1`. Putting a domain behind a CDN adds a hop — re-derive the count then, never raise it blindly. The hooks take no `Request`: bind the resolved IP in a request-scoped `ContextVar` and read it inside the hook.

---

## Defense Layers

### Layer 1: Registration Gate

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **Email verification** | Account activates only once the address is proven (passwordless: the code itself is the proof) | Low | $0 |
| **Per-IP account cap** | Max 2 new accounts per IP per rolling 24h (`ABUSE_MAX_REG_PER_IP`) | None for most users | $0 |
| **Disposable email block** | Reject throwaway-inbox domains | None for real users | $0 |

- Credits/quota are granted only **after** verification — never on registration alone.
- Store `registration_ip` (INET) and, once collected, `registration_fingerprint` (VARCHAR 64) on the user row.
- **The cap is a blunt instrument.** An office, a university or a mobile carrier's CGNAT puts many real users behind one IPv4 address, and one IPv6 user controls a whole /64 — so an exact-address count over-blocks the first and under-counts the second. Count IPv6 by its /64 prefix, return a message that says what to do next, and keep the default low only while the free tier is worth farming.
- **Normalise before comparing, never before storing.** Gmail ignores dots and a `+suffix` in the local part, so `a.b+1@gmail.com` and `ab@gmail.com` are one inbox: compare a normalised form when clustering accounts, and keep the address the user typed as the login.

### Layer 2: Progressive Resource Unlock

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **Progressive unlock** | 30% of the free-tier quota on verification, the remaining 70% 24h later | Low | $0 |

**Why it works:** a farm that automates signup and verification in minutes has to wait a day for each batch's full quota, which removes most of its return; a real user who signs up today finds the rest there tomorrow. The split and delay are env-tunable in the module (`ABUSE_IMMEDIATE_FRACTION`, `ABUSE_DELAY_HOURS`).

### Layer 3: Behavioral Signals (flag, never block)

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **Browser fingerprint** | A hash of canvas/WebGL/fonts/screen, clustered across accounts | None | $0 (open-source library) |
| **Usage pattern analysis** | Accounts that burn quota within minutes of signup | None | $0 |
| **Shared IP clustering** | IPs with 3+ accounts — flag, do not block (offices, universities) | None | $0 |

- **A fingerprint is a clustering signal, not an identity.** The open-source FingerprintJS reports 40–60% accuracy with common collisions and IDs that last weeks; that is fine for "these five accounts look alike, review them" and wrong as a block key. Use FingerprintJS v5+ (MIT again since v5; v4 was BSL 1.1 — never pin a v4 release) or ThumbmarkJS (MIT).
- **Collecting a fingerprint needs a legal basis first.** Fingerprinting reads the terminal, so ePrivacy Art. 5(3) applies — the same consent rule as cookies (EDPB Guidelines 2/2023, final v2.0 of 7 Oct 2024). Fraud prevention is a legitimate interest for the *processing* (GDPR Recital 47), but that does not answer the separate Art. 5(3) question, whose only consent-free route is "strictly necessary" for the service the user asked for — narrow and judged per member state. For EU users, gate collection on consent or get counsel's sign-off. KVKK has no fingerprint-specific guidance (its cookie guide excludes fingerprints), so treat the hash as personal data under the general law.
- Background job (weekly): cluster same fingerprint + different emails; show the clusters in an admin "Suspicious accounts" panel for manual review.

### Layer 4: Phone Verification (last resort)

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **SMS OTP** | Require a phone number for the free tier | High | a base per-message rate plus carrier fees in the US, far more in some countries; a managed verify product bills per successful verification |

**When to use:** only when Layers 1–3 fail to contain abuse, and for the free tier only (paid users already have an identity via their payment method). ⚠️ **An SMS field is itself an attack surface** — SMS pumping (artificially inflated traffic) uses exactly this input to send OTPs to premium numbers the attacker is paid for. Before enabling it: restrict destination countries to the ones you serve, turn on the provider's fraud guard, rate-limit sends per IP and per number, and alert on send volume.

---

## Implementation Phases

### Phase 1: Quick wins (at launch, $0)

- [ ] Controls wired into the scaffold's signup doors (§ Where it goes), client IP from `client_ip()`
- [ ] `registration_ip` (INET) stored on the user row
- [ ] Per-IP account cap (2 per IP per rolling 24h; IPv6 counted per /64)
- [ ] Disposable-email blocklist checked on every signup
- [ ] Verification required before quota/credits activate

### Phase 2: Smart detection (before public launch)

- [ ] Progressive quota unlock (30% immediate, 70% after 24h)
- [ ] Browser fingerprint collected — only where lawful (Layer 3)
- [ ] Admin panel: suspicious accounts (IP clusters, fingerprint matches)

### Phase 3: Reactive (only if abuse is detected post-launch)

- [ ] CAPTCHA on signup — Cloudflare Turnstile (free, unlimited, works on sites not proxied through Cloudflare) or hCaptcha's free tier
- [ ] Quota velocity alerting (accounts burning 100% of quota within 1h of creation)
- [ ] Phone verification for the free tier only (Layer 4's preconditions first)

---

## Database Schema

Add the columns through the project's migration path (`core/25-data-postgres.md`; a saas-skeleton that has no Alembic yet ships the idempotent `server/db/schema.sql`, where the module's statements go verbatim):

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_ip INET;
ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_fingerprint VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS quota_unlocked_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_registration_ip ON users(registration_ip);
CREATE INDEX IF NOT EXISTS idx_users_registration_fingerprint ON users(registration_fingerprint)
    WHERE registration_fingerprint IS NOT NULL;
```

`registration_ip` and `registration_fingerprint` are personal data: name the purpose (fraud prevention) and a retention period in the privacy policy, and null both columns when it lapses (the data-retention TTL of `saas/88-saas-launch-checklist.md`).

---

## Disposable Email Domain Blocklist

Source: https://github.com/disposable-email-domains/disposable-email-domains — the module ships a copy as `data/disposable-email-domains.txt`, loaded into a set once at import. The upstream list grows continuously, so a vendored copy goes stale: refresh it on a schedule and restart the service after each refresh. Never hand-maintain a short list in code.

---

## Monitoring Metrics

Count every refusal and every fail-open as a Prometheus counter in `server/src/<pkg>/metrics.py` (per `core/55-observability.md`), e.g. `signup_refused_total{reason="ip_cap|disposable|..."}` and `abuse_check_failed_open_total` — the module fails open on a database error, so an unmonitored failure silently turns the cap off. Alert through Alertmanager. Starting thresholds (tune per product):

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

**Do not implement from scratch.** Vendor from `/opt/fabrik-lib/abuse-prevention/`:

```bash
cp -r /opt/fabrik-lib/abuse-prevention server/libs/abuse_prevention
```

It provides `abuse_detection.py` (`check_ip_rate_limit`, `check_disposable_email`, `store_registration_metadata`), `progressive_unlock.py` (`split_quota`, `grant_immediate_quota`, `schedule_delayed_grant`, `release_due_grants`), `data/disposable-email-domains.txt` and `schema.sql`.

## Adaptation Checklist (after vendoring)

1. Apply `schema.sql` through the migration path (§ Database Schema). ⚠️ Its `delayed_grants.user_id` is `BIGINT`; a saas-skeleton's `users.id` is `UUID` — change the column type before applying.
2. The module takes a **synchronous** DB-API connection (psycopg); the scaffold's request path is async. Call it through `asyncio.to_thread(...)` with a psycopg connection, never directly inside an async hook, or port its two queries to the async session.
3. Pass it the IP from `client_ip()` — the module README's own client-IP snippet takes the left-most `X-Forwarded-For` entry and is spoofable; do not copy it.
4. Wire `check_disposable_email()` + `check_ip_rate_limit()` into `on_signup_attempt`, and `store_registration_metadata()` into `on_signup_complete` (§ Where it goes).
5. Wire `split_quota()` + `schedule_delayed_grant()` if the project has a credit/quota system; run `release_due_grants()` from the worker's schedule.
6. Fingerprint collection and the suspicious-accounts panel: Phase 2, lawful basis first.

---

## Banned Patterns

| Pattern | Instead |
|---|---|
| Keying a limit on the raw `X-Forwarded-For` header or its left-most entry | `client_ip(request, settings.trusted_proxy_hops)` |
| A second registration endpoint beside the IdP's | the `on_signup_attempt` / `on_signup_complete` seams |
| Granting credits or quota on registration alone | grant on verification; progressive unlock |
| Blocking on a fingerprint match or a shared IP | flag for review; block only on the per-IP cap and the blocklist |
| Collecting a fingerprint from EU users with no consent and no counsel sign-off | gate it on consent (Layer 3) |
| A hand-kept short list of disposable domains in code | the upstream list, refreshed on a schedule |
| Enabling SMS OTP with no country allow-list, fraud guard or send rate limit | Layer 4's preconditions |
| An abuse check that fails open with no counter | `abuse_check_failed_open_total` + an alert |

## Related Rule Packs

- `saas/88-saas-launch-checklist.md` — the launch gate that cites this pack's phases
- `core/35-security-auth.md` — request rate limits on the auth endpoints (Redis token buckets); this pack's cap counts ACCOUNTS, not requests
- `core/25-data-postgres.md` — the migration path for the schema additions
- `core/55-observability.md` — counters and alerting
- `saas/95-multi-tenant-saas.md` — per-tenant rate limiting once the account exists

## Done When

- [ ] Every signup door the project enables carries the Phase 1 controls, with a test that the cap and the blocklist refuse
- [ ] The client IP comes from `client_ip()`, and `trusted_proxy_hops` matches the proxies actually in front
- [ ] No credit or quota is granted before verification
- [ ] Refusals and fail-opens are counted, and an alert fires on a sustained fail-open
- [ ] Fingerprinting, if enabled, has its lawful basis recorded; IP and fingerprint columns have a retention period
