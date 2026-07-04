---
activation: glob
globs: ["**/revenuecat/**", "**/iap/**", "**/app.json", "**/eas.json"]
description: Mobile billing discipline — Google Play Billing, RevenueCat entitlements, receipt validation, Turkey GPB-mandatory, Teknokent tax, launch checklist
trigger: glob
---
<!-- CONSUMER: Coding agents building mobile billing + Traycer (epic-brief for mobile)
     GOAL: Google Play Billing + Apple IAP via RevenueCat, Turkey constraints, Teknokent tax, launch checklist
     TRAYCER USAGE: Shapes billing epic. Injects Turkey GPB-mandatory constraint. Launch checklist gates planning.
     AGENT USAGE: Follow verbatim for billing integration. RevenueCat webhook pattern is the implementation reference. -->

# Mobile Billing Rules

Apply when working on in-app purchases, subscriptions, entitlements, or billing-related backend endpoints in a mobile app project. This pack co-activates with `80-mobile.md`.

**Scope:** Mobile IAP (Google Play Billing, App Store StoreKit) mediated by RevenueCat. For SaaS web billing (Paddle, iyzico), see `85-payments-billing.md` — different model, different pack.

---

## Turkey: Store Billing Is Mandatory (Both Stores)

### Google Play

**Turkey is excluded from both User Choice Billing (UCB) and the External Offers Program (EOP)** as of May 2026. Google Play Billing is the only permitted payment method for digital goods sold via mobile apps to Turkish users.

- **Paddle, iyzico, Stripe, or any web-steer link for digital feature unlocks = instant rejection.** Do not embed external checkout links for digital goods in any app distributed via Google Play in Turkey.
- **Monitor:** Rekabet Kurumu opened an antitrust investigation into Google Play Billing on **Aug 7, 2025** (announced Aug 22) — alleging Article 6 abuse of dominance by forcing GPB and blocking alternative payment info. A separate investigation into Google's ad-tech billing practices opened **Apr 3, 2026** (not Play Store). No ruling, decision, or interim measure as of May 2026. Standard timeline: **12-18 months** → decision expected **Aug 2026 – Feb 2027**. Google has made no changes to Turkey billing in response. GPB remains mandatory until a ruling forces otherwise.
- **Horizon (does not change today's rule):** Google's March 2026 "Own Billing" / app-to-web rollout reaches EEA/UK/US by June 30 2026, Australia by Sept 30 2026, Korea/Japan by Dec 31 2026, and rest of world — including Turkey — by **Sept 30 2027**. This may eventually permit app-to-web purchase flows in Turkey, but it is not live for Turkey now; GPB remains mandatory until then. <!-- Re-verify Turkey status after Sept 2027 -->

### Apple App Store

Turkey is **not** in the EU/EEA, so the DMA alternative payment provisions do not apply. Apple's standard IAP rules apply: **all digital goods must use Apple IAP** (StoreKit). External purchase links for digital goods are not permitted for Turkish users.

- In the **EU only**, Apple offers alternative payment entitlements under the DMA. The per-install CTF was sunset Jan 2026, replaced by a modular fee system: 5% Core Technology Commission (CTC) on revenue + Store Services fee (Tier 2: 13%, Tier 1: 5%) + 2% Initial Acquisition Fee (first 6 months of new users). **SBP members (<$1M):** Initial Acquisition Fee = 0%, Tier 2 = 10%, so total = **15% (10% + 5% CTC)** — same as standard IAP 15%. No benefit to switching unless you need external payment methods for other reasons. Default: stay on standard IAP + SBP 15%.
- **Physical goods and services consumed outside the app** are exempt on both stores — they may use any payment processor.

### Both Stores — Summary

| Market | Google Play | Apple App Store |
|---|---|---|
| Turkey | GPB mandatory (UCB/EOP excluded) | Standard IAP mandatory (no DMA) |
| EU/EEA | UCB available (reduced service fee) | DMA alternative payments (complex fee stack) |
| US | UCB available | Standard IAP (external links via court order, evolving) |
| Default | GPB via RevenueCat | StoreKit via RevenueCat |

**RevenueCat abstracts both stores.** The agent codes one integration; RevenueCat routes to GPB or StoreKit per platform.

---

## RevenueCat as Entitlement Server

RevenueCat abstracts Google Play Billing and App Store StoreKit into a unified subscription backend. It validates receipts, processes state transitions, handles purchase acknowledgments, and normalizes transaction data. **Do not build a custom receipt validation or RTDN webhook listener for an MVP** — the edge cases (grace periods, billing retries, account holds, pause/resume, upgrade/downgrade, family sharing) require hundreds of engineering hours.

**Pricing:** Free up to **$2,500 MTR** (Monthly Tracked Revenue). Above that threshold, RevenueCat charges **1%** of tracked revenue. No per-user fee, no setup cost.

### Client-Side Integration

```typescript
// React Native (react-native-purchases) — initialize once at app start
import Purchases from 'react-native-purchases';

await Purchases.configure({ apiKey: 'your_rc_public_key' });

// Check entitlement (UX only — backend is source of truth)
const info = await Purchases.getCustomerInfo();
const isPremium = info.entitlements.active['premium'] !== undefined;
```

- Sync RevenueCat user IDs to the app's user ID (`auth.users.id` on `postgres-main`, owned by `fabrik-lib/fastapi-user-auth`) on first launch.
- **Never trust client-side entitlement state for gating premium content.** Client-side checks are for UX only. Backend is the source of truth.
- Paywall components must support remote config via RevenueCat dashboard — never hardcode pricing or offering IDs.

### Server-Side Verification (FastAPI backend)

Configure RevenueCat to send webhooks to a secure FastAPI endpoint:

```python
# POST /api/webhooks/revenuecat
@router.post("/api/webhooks/revenuecat")
async def revenuecat_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    # 1. Verify shared-secret Authorization header (constant-time compare)
    auth_header = request.headers.get("Authorization", "")
    expected = f"Bearer {os.getenv('REVENUECAT_WEBHOOK_SECRET')}"
    if not hmac.compare_digest(auth_header, expected):
        raise HTTPException(status_code=401, detail="Invalid authorization")

    # 2. Parse and process
    body = await request.body()
    event = json.loads(body)
    event_type = event["event"]["type"]
    app_user_id = event["event"]["app_user_id"]

    # 3. Update subscription status in PostgreSQL
    if event_type in ("INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION"):
        await update_subscription_status(db, app_user_id, status="active")
    elif event_type == "EXPIRATION":
        # Only EXPIRATION revokes access — fired when the subscription actually ends
        await update_subscription_status(db, app_user_id, status="expired")
    elif event_type == "CANCELLATION":
        # Auto-renew turned off; user KEEPS access until EXPIRATION. Do not revoke here.
        # Optionally flag for win-back, but leave subscription_status unchanged.
        await mark_auto_renew_off(db, app_user_id)
    elif event_type == "BILLING_ISSUE":
        # With grace periods enabled, keep access; EXPIRATION fires if grace period lapses.
        await update_subscription_status(db, app_user_id, status="grace_period")

    return {"status": "ok"}
```

**CANCELLATION = auto-renew off, access continues until EXPIRATION.** Never revoke on CANCELLATION. With grace periods enabled, BILLING_ISSUE and CANCELLATION (`cancel_reason: BILLING_ERROR`) fire together — keep access; EXPIRATION arrives only if the grace period lapses.

- Gate premium API routes at the database level: `WHERE subscription_status = 'active'`. Near-zero latency, no external API call per request.
- **Do NOT poll RevenueCat REST API per request.** v2 rate limits are per-domain and much lower than they look: most endpoints default to ~60 req/min (variable by load); the `/customers` endpoint is the generous outlier at 480/min. Read the `RevenueCat-Rate-Limit-Current-Limit` / `-Current-Usage` response headers; on 429, honor `Retry-After`. Webhook-to-PostgreSQL sync is the pattern — per-request polling will rate-limit you almost immediately at scale.
- **Do NOT store granular transaction histories in PostgreSQL** — offload compliance, transaction logging, and state resolution to Google Play and RevenueCat.

### The 72-Hour Acknowledgment Rule

Google Play automatically refunds any purchase not acknowledged within 72 hours. RevenueCat handles this automatically. If you ever bypass RevenueCat for direct PBL integration, you must call `acknowledgePurchase()` within 72 hours or the user gets refunded.

---

## Receipt Validation & Piracy Prevention

Client-side receipt validation is fundamentally insecure — modified APKs (Lucky Patcher, etc.) bypass local checks entirely.

- **Server-side validation is mandatory.** The backend must independently verify receipts via RevenueCat webhooks or the Google Play Developer API — never trust the client's claim of entitlement.
- **Play Integrity API:** integrate Play Integrity checks for high-value operations (purchase verification, premium content access). It detects rooted devices, modified APKs, and non-genuine Play Store installs.
- RevenueCat performs receipt validation automatically when using their SDK. Only implement custom validation if you bypass RevenueCat.

---

## Store API Versions

Both stores enforce SDK version requirements. RevenueCat abstracts both — keep the RevenueCat SDK updated and it handles compliance.

### Google Play Billing Library (PBL)

- **PBL 7.0+** was required as of August 31, 2025. **PBL 8.0** released June 30, 2025 and is current; Google runs an annual deprecation cycle with a Play Console extension form to continue distributing on an older version until November 1. **Target PBL 8.0 for new work.** RevenueCat's SDK tracks the latest PBL — keep it updated and it stays compliant.
<!-- Verify annually: search "Google Play Billing Library version deprecation" -->

### Apple StoreKit

- **StoreKit 2** is the recommended API for all new implementations. StoreKit 1 (original) is **not formally deprecated** — Apple continues to maintain and patch it, but adds no new features. No migration deadline exists. Treat it as legacy for new code.
- RevenueCat uses StoreKit 2 internally when available, falling back to StoreKit 1 for older iOS versions.
- **Minimum SDK:** as of April 28, 2026, all App Store submissions must be built with the **iOS 26 SDK** (Xcode 26+). Submissions on older SDKs are rejected at upload.

---

## Store Fee Enrollment (15% Small Business Programs)

Both stores offer reduced commission (15% vs 30%) for the first $1M USD/year. **Neither is automatic** — explicit enrollment required on each.

### Google Play 15% Fee

1. Open Play Console → Associated developer accounts.
2. Create an Account Group using the full legal name of the Turkish LLC.
3. Declare Associated Developer Accounts (even if solo with one account — declaration is mandatory).
4. Accept the 15% service fee Terms of Service.

### Apple App Store Small Business Program

1. Sign in to [Apple's SBP enrollment page](https://developer.apple.com/app-store/small-business-program/) with the Account Holder Apple ID.
2. Disclose all Associated Developer Accounts — proceeds from ALL associated accounts are combined for the $1M threshold.
3. Accept the program terms.
4. The 15% rate begins **15 days after the end of the fiscal month** Apple approves enrollment (not immediately).

**If you exceed $1M in a calendar year:** standard 30% applies to remaining sales that year. If proceeds fall below $1M the following year, you re-qualify automatically.

**EU note:** For SBP members, EU alternative terms total = 15% (10% Store Services + 5% CTC) — same as standard IAP 15%. No cost advantage to switching for small developers.

### Both Stores — Failure to Enroll

| Store | Without enrollment | With enrollment |
|---|---|---|
| Google Play | 30% from day one | 15% on first $1M |
| Apple App Store | 30% from day one | 15% on first $1M (10% EU subs after year 1) |

Enroll on BOTH stores before first submission.

---

## Teknokent Tax Treatment (applies to BOTH Apple and Google payouts)

<!-- These are accounting-compliance assertions derived from research. Verify with your mali müşavir before treating as binding rules. -->

Turkish tax law treats "software exports via platforms" generically — the KVK exemption, KDV rules, and gross invoicing requirements are identical for Apple App Store and Google Play payouts. The rules below apply to both.

### Corporate Tax (KVK)

- Under Law No. 5746, revenues from **software sales** (IAP, subscriptions) qualify for 100% Corporate Tax exemption if the LLC is in a Teknokent.
- **Advertising revenue (AdMob, AppLovin, etc.) is EXCLUDED** from this exemption. Ad income is standard commercial gain — taxed at the standard corporate rate. Maintain separate ledgers.

### VAT (KDV)

- Sales to users **outside Turkey** via Google Play or App Store qualify as "Service Exports" — **0% KDV**.
- Sales to users **inside Turkey** are subject to **20% KDV**.
- Use each store's geographic breakdown reports (Google Play financial reports / App Store Connect payments and financial reports) for accurate invoicing per region.

### The Gross Invoicing Rule (critical — both stores)

Both Apple and Google remit the net amount (e.g., 85% after the 15% fee). **Turkish accounting law prohibits invoicing only the net deposit.**

- Invoice the **gross** 100% as a Service Export (0% KDV for non-TR users).
- Document Apple's/Google's 15-30% commission as an **expense** via KDV2 (Reverse Charge VAT) declarations.
- Invoicing net = "under-reported revenue" = **tax evasion** = forfeits the entire Teknokent exemption.
- Both stores provide financial reports with geographic breakdown — use these for accurate per-region invoicing.

### US Withholding Tax

File a **W-8BEN-E** form with **both Google (Play Console) and Apple (App Store Connect)** to claim reduced withholding under the US-Turkey tax treaty. Without it, each store withholds 30% on US-sourced revenue.

### Payout Routing

Consider multi-currency corporate accounts (e.g., WorldFirst) to hold USD/EUR before converting to TRY — avoids unfavorable automatic FX conversions by Google.

---

## Mobile Launch Checklist (Both Stores)

Process-level gates — complete before first submission on each store.

### Account Setup

**Google Play:**
- [ ] Play Console registered as **Organization** (not Personal) — bypasses the 14-day / 12-tester closed testing mandate (reduced from 20 in Dec 2024). Requires D-U-N-S number from Dun & Bradstreet + LLC documentation.
- [ ] 15% Small Business fee enrolled (Account Group created, ADAs declared, ToS accepted).
- [ ] W-8BEN-E filed with Google for US-Turkey treaty benefits.

**Apple App Store:**
- [ ] Apple Developer Program enrolled as **Organization** ($99/yr). Requires D-U-N-S number + Account Holder with legal authority to bind the LLC.
- [ ] Apple Small Business Program enrolled (associated accounts declared, terms accepted). 15% rate begins 15 days after fiscal month of approval.
- [ ] W-8BEN-E filed with Apple via App Store Connect for US-Turkey treaty benefits.
- [ ] Payment info configured in App Store Connect — Turkish bank cards may be rejected; use Wise/Revolut/Payoneer if needed.

### Store Listing

**Google Play:**
- [ ] 128px icon, 1280x800 screenshots (min 1, max 5), promotional tile (440x280).
- [ ] Short description (132 chars max) + detailed description.

**Apple App Store:**
- [ ] 1024x1024 app icon (no alpha). Screenshots: **6.9" iPhone** (1290×2796 or 1320×2868, mandatory — auto-scales to all smaller iPhones; 5.5" dropped), **13" iPad** (2064×2752 or 2048×2732, mandatory if universal).
- [ ] Subtitle (30 chars max) + description + keywords (100 chars).

**Both stores:**
- [ ] Privacy Policy URL in store listing AND accessible from in-app Settings.
- [ ] Age rating accurate — if app has UGC or chat, do NOT rate 4+/PEGI 3.

### Billing Integration

- [ ] RevenueCat SDK integrated; subscription products configured in **both** Play Console and App Store Connect.
- [ ] **"Restore Purchases" button on paywall** — omitting this = automatic rejection on BOTH stores. Apple is especially strict.
- [ ] Server-side entitlement verification via RevenueCat webhooks → PostgreSQL.
- [ ] PBL 8.0 and StoreKit 2 (RevenueCat SDK handles both if kept updated).
- [ ] No external billing links for digital goods (Turkey excluded from UCB/EOP; Apple IAP mandatory globally except EU DMA).

### Compliance

- [ ] In-app account deletion functional (**Apple and Google both mandate this**). See `80-mobile.md` § Compliance.
- [ ] **Google:** Data Safety form filled accurately — declare ALL SDK telemetry (Analytics, Crashlytics, RevenueCat).
- [ ] **Apple:** Privacy Manifest (`PrivacyInfo.xcprivacy`) declares every reason API and tracking domain.
- [ ] **Apple:** ATT prompt fires before IDFA/tracking. See `80-mobile.md`.
- [ ] GDPR consent gate for EU users (both stores). See `80-mobile.md` § Compliance.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Paddle / iyzico / Stripe / web-steer for digital goods on mobile (Turkey) | Google Play Billing + Apple IAP via RevenueCat — Turkey excluded from UCB/EOP and DMA |
| StoreKit 1 for new iOS implementations | StoreKit 2 (StoreKit 1 is legacy — no new features) |
| Custom receipt validation / RTDN webhook listener for MVP | RevenueCat SDK + webhooks |
| Client-side entitlement trust for premium gating | Server-side: RevenueCat webhook → PostgreSQL `subscription_status` |
| Polling RevenueCat REST API per request | Webhook-driven sync to PostgreSQL |
| Storing granular transaction history in PostgreSQL | Offload to Google Play + RevenueCat |
| Hardcoded pricing or offering IDs | RevenueCat dashboard remote config |
| Invoicing net Google deposit (Turkish entity) | Invoice gross; expense Google's cut via KDV2 |
| Mixing ad revenue with subscription revenue in Teknokent tax filings | Separate ledgers — ad revenue excluded from KVK exemption |
| Personal Play Console account | Organization account (bypass 14-day tester mandate) |
| Skipping 15% fee enrollment | Explicit enrollment in Play Console |
| Missing "Restore Purchases" on paywall | Mandatory — omission = store rejection |

---

## Related Rule Packs

- `80-mobile.md` — client-side mobile architecture, styling, compliance, i18n
- `85-payments-billing.md` — SaaS web billing (Paddle/iyzico) — different model, do not mix
- `35-security-auth.md` — Pattern A (`fabrik-lib/fastapi-user-auth`, default), token storage in `expo-secure-store`; Pattern B (Supabase Auth) legacy-only
- `55-observability.md` — backend structlog + GlitchTip; client Sentry RN SDK
- `10-python.md` — backend FastAPI patterns for webhook endpoints
- `00-domain-mobile-app.md` — planning-level decisions (monetization §5, finance §14)
- `89-mobile-launch-checklist.md` — full mobile go-to-market protocol (store accounts, legal, tax, review traps, staged rollout, post-launch)

---

## Done When

- [ ] RevenueCat SDK initialized; subscription products configured in **both** Play Console and App Store Connect.
- [ ] "Restore Purchases" button present on paywall (both stores — Apple is especially strict).
- [ ] Webhook endpoint (`/api/webhooks/revenuecat`) verifies shared-secret auth, updates `subscription_status` in PostgreSQL.
- [ ] Premium API routes gated at DB level (`WHERE subscription_status = 'active'`), not by polling RevenueCat.
- [ ] No external billing links for digital goods (Turkey: GPB + Apple IAP mandatory).
- [ ] **Google:** Play Console registered as Organization with D-U-N-S number.
- [ ] **Apple:** Developer Program enrolled as Organization ($99/yr) with D-U-N-S number.
- [ ] **Both stores:** 15% Small Business fee enrolled before first submission.
- [ ] **Both stores:** W-8BEN-E filed for US-Turkey treaty benefits.
- [ ] Ad revenue and subscription revenue on separate Teknokent ledgers.
- [ ] Gross invoicing for both Apple and Google payouts — commission expensed via KDV2.
- [ ] PBL 8.0 and StoreKit 2 (via RevenueCat SDK).
- [ ] Play Integrity API integrated for high-value operations.
- [ ] **Google:** Data Safety form accurately declares all SDK telemetry.
- [ ] **Apple:** Privacy Manifest declares every reason API and tracking domain.
