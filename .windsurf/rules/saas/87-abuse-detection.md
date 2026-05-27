---
activation: glob
globs: ["**/auth/**", "**/register/**", "**/signup/**", "**/users/**"]
description: Abuse detection discipline — registration gating, progressive unlock, fingerprinting, disposable email blocking for SaaS free tiers
trigger: glob
---
<!-- CONSUMER: Coding agents building registration/signup flows
     GOAL: 4-layer anti-abuse system for SaaS free tiers — IP rate limit, disposable email block, progressive unlock, fingerprint
     TRAYCER USAGE: Injects as Context File for auth/registration tickets. Phase 1 items are launch-blocking.
     AGENT USAGE: Follow the 4 layers. Implement Phase 1 at launch, Phase 2 before public launch, Phase 3 reactively. -->

# Abuse Detection — SaaS Anti-Fraud Playbook

Prevent free-tier farming, multi-account abuse, and credit/quota exploitation without adding friction for legitimate users. Applies to every Ocoron/Tojlo SaaS project with a free tier or trial.

**Referenced by:** `saas/88-saas-launch-checklist.md` § Abuse Prevention

---

## The Problem

Free tiers attract abuse. A bad actor creates 100 accounts with disposable emails, farms 10 credits each (= 1,000 free credits), and gets the equivalent of a paid plan for $0. At scale this bleeds revenue, exhausts API quotas, and wastes infrastructure.

---

## Defense Layers

### Layer 1: Registration Gate (blocks 80% of abuse)

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **Email verification** | Must click link before account activates | Low | $0 |
| **IP rate limit** | Max 2 registrations per IP per 24h | None | $0 |
| **Disposable email block** | Reject mailinator, guerrillamail, tempmail, etc. | None for real users | $0 |

**Implementation:**

```python
# FastAPI registration endpoint
@router.post("/api/auth/register")
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    ip = request.headers.get("X-Forwarded-For", request.client.host)
    email = body.email.lower()

    # 1. Check disposable email domain
    domain = email.split("@")[-1]
    if domain in DISPOSABLE_DOMAINS:
        raise HTTPException(status_code= 422, detail="Please use a permanent email address")

    # 2. Check IP rate limit (max 2 per IP per 24h)
    result = await db.execute(
        text("SELECT COUNT(*) FROM users WHERE registration_ip = :ip AND created_at > NOW() - INTERVAL '24 hours'"),
        {"ip": ip}
    )
    if result.scalar() >= 2:
        raise HTTPException(status_code=429, detail="Too many accounts from this network. Try again later.")

    # 3. Create user with IP + fingerprint stored
    user = User(
        email=email,
        registration_ip=ip,
        registration_fingerprint=body.fingerprint,  # client-side FingerprintJS hash
    )
    # ... continue with creation, email verification send
```

- Store `registration_ip` (INET) and `registration_fingerprint` (VARCHAR 64) in `users` table
- Credits/quota granted only **after** email verification — never on registration alone
- Disposable domain list: load from file on app startup (~5,000 domains from [disposable-email-domains](https://github.com/disposable-email-domains/disposable-email-domains))

### Layer 2: Progressive Resource Unlock (blocks 15% more)

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **Progressive unlock** | Partial quota/credits immediate, full after 24h | Low | $0 |
| **Delayed full grant** | Full quota unlocks 24h after email verification | Medium | $0 |

**Why it works:** Bot farms automate registration + email verification in minutes. A 24h delay makes the attack 100x slower and unprofitable. Real users sign up today, come back tomorrow, quota is there.

**Recommended pattern:** Progressive unlock — grant 30% of free-tier quota immediately (lets real users try the product), remaining 70% unlocks 24h after email verification.

```python
# After email verification succeeds
async def on_email_verified(user_id: str, db: AsyncSession):
    # Immediate: 30% of free tier quota
    await grant_quota(db, user_id, amount=FREE_TIER_QUOTA * 0.3, reason="signup_immediate")
    # Delayed: remaining 70% after 24h
    await schedule_delayed_grant(db, user_id, amount=FREE_TIER_QUOTA * 0.7, delay_hours=24)
```

### Layer 3: Behavioral Detection (blocks remaining 5%)

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **Browser fingerprint** | Detect same browser across accounts | None | $0 (FingerprintJS open-source) |
| **Usage pattern analysis** | Flag accounts that consume quota immediately after registration without browsing | None | $0 |
| **Shared IP clustering** | Flag IPs with 3+ accounts (not block — legitimate: office, university) | None | $0 |

**Implementation:**

- Client-side: generate fingerprint hash (canvas, WebGL, fonts, screen resolution) via FingerprintJS open-source, send on registration
- Store as `registration_fingerprint` in users table
- Background job (weekly): scan for clusters — same fingerprint + different emails = likely same person
- Admin dashboard: "Suspicious accounts" panel showing clusters, flagged for manual review

### Layer 4: Phone Verification (nuclear option)

| Control | What it does | Friction | Cost |
|---|---|---|---|
| **SMS OTP** | Require phone number for free tier | High | ~$0.01/SMS |

**When to use:** Only if Layers 1-3 fail to contain abuse. Phone verification eliminates 99%+ of bot farms but adds significant registration friction. Apply only to free tier — paid users already have identity via payment method.

---

## Implementation Phases

### Phase 1: Quick wins (implement at launch, $0 cost)

- [ ] Store `registration_ip` (INET) in users table
- [ ] IP rate limit on registration endpoint (max 2 per IP per 24h)
- [ ] Disposable email domain blocklist (check on registration)
- [ ] Email verification required before quota/credits activate

### Phase 2: Smart detection (implement before public launch)

- [ ] Browser fingerprint collected on registration (client-side hash stored)
- [ ] Progressive quota unlock (30% immediate, 70% after 24h)
- [ ] Admin panel: suspicious accounts view (IP clusters, fingerprint matches)

### Phase 3: Reactive (implement only if abuse detected post-launch)

- [ ] Phone verification for free tier only
- [ ] CAPTCHA on registration (hCaptcha — free tier available)
- [ ] Quota velocity alerting (flag accounts burning 100% quota within 1h of creation)

---

## Database Schema

```sql
-- Add to users table (Supabase or direct PostgreSQL)
ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_ip INET;
ALTER TABLE users ADD COLUMN IF NOT EXISTS registration_fingerprint VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS quota_unlocked_at TIMESTAMPTZ;

-- Indexes for rate limiting queries
CREATE INDEX IF NOT EXISTS idx_users_registration_ip ON users(registration_ip);
CREATE INDEX IF NOT EXISTS idx_users_registration_fingerprint ON users(registration_fingerprint);
```

---

## Disposable Email Domain Blocklist

Source: https://github.com/disposable-email-domains/disposable-email-domains

Top domains to block immediately (load full list from file):

```
mailinator.com, guerrillamail.com, tempmail.com, throwaway.email,
yopmail.com, sharklasers.com, guerrillamailblock.com, grr.la,
dispostable.com, mailnesia.com, tempr.email, temp-mail.org,
fakeinbox.com, getnada.com, emailondeck.com, mohmal.com,
trashmail.com, maildrop.cc, 10minutemail.com, minutemail.com
```

Full list: ~5,000 domains. Store in `data/disposable-email-domains.txt` in the project. Load into a set on app startup. Check on every registration.

---

## Monitoring Metrics

| Metric | Healthy | Alert threshold |
|---|---|---|
| Registrations per IP per day | 1-2 | > 3 |
| Accounts per fingerprint | 1 | > 2 |
| Time from registration to first resource use | > 5 min | < 30 sec (bot) |
| Free tier quota burn rate | Spread over days | 100% in < 1 hour |
| Disposable email rejection rate | 0-1/day | > 10/day (attack in progress) |

Log these via `structlog` (per `core/55-observability.md`). Alert via Apprise on threshold breach.

---

## Cost of Abuse vs Cost of Prevention

| Scale | Abuse cost | Prevention cost |
|---|---|---|
| 100 fake accounts | ~$0.20 infra | $0 (IP + email block) |
| 1,000 fake accounts | ~$2.00 infra | $0 (same controls) |
| 10,000 fake accounts (bot farm) | ~$20 infra + API quota exhaustion | ~$0.01/SMS if phone needed |

At small scale, abuse is cheap to absorb. The real cost is **API quota exhaustion** (third-party APIs with daily limits). IP rate limiting alone prevents this.

---

## Reusable Module

**Do not implement from scratch.** Vendor from `/opt/fabrik-lib/abuse-prevention/`:

```bash
cp -r /opt/fabrik-lib/abuse-prevention /opt/my-project/libs/abuse-prevention
```

The module provides: `abuse_detection.py` (IP rate limit, disposable email check, metadata storage), `progressive_unlock.py` (30%/70% split), `data/disposable-email-domains.txt` (~5,400 domains), `schema.sql` (columns + indexes). See its README for integration guide (Flask + FastAPI examples).

## Adaptation Checklist (after vendoring)

1. Run `schema.sql` against your database
2. Wire `check_disposable_email()` + `check_ip_rate_limit()` into your registration endpoint
3. Wire `split_quota()` + `schedule_delayed_grant()` if the project has a credit/quota system
4. Add fingerprint collection to the registration form (client-side FingerprintJS)
5. Add "Suspicious accounts" section to admin dashboard (Phase 2)
