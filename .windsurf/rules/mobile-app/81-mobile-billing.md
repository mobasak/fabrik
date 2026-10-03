---
activation: glob
globs: ["**/revenuecat/**", "**/iap/**", "**/app.json", "**/app.config.*", "**/eas.json"]
description: Mobile billing discipline — store billing via RevenueCat, the entitlement webhook, receipt validation, store fees, Turkey constraints, Teknokent tax
trigger: glob
currency_pass: 2026-09-30
---
<!-- CONSUMER: coding agents building mobile billing (client + the scaffold's `server/` backend) and the planning pack
     00-domain-mobile-app.md, which cites § Store Fee Enrollment, § Turkey and § Teknokent Tax Treatment by name.
     This pack OWNS the store-fee numbers and the Teknokent rules; other packs cite them. Every dated value here has a
     row in CLAIMS.yaml with a re-verify window. -->

# Mobile Billing Rules

Apply when working on in-app purchases, subscriptions, entitlements, or billing-related backend endpoints in a mobile app project. This pack co-activates with `80-mobile.md`.

**Scope:** Mobile IAP (Google Play Billing, App Store StoreKit) mediated by RevenueCat. For SaaS web billing (Paddle, iyzico), see `core/85-payments-billing.md` — different model, different pack. Launch gates (store accounts, listing assets, privacy forms, review traps) live in `89-mobile-launch-checklist.md`.

---

## Turkey: Store Billing Is Mandatory (Both Stores)

### Google Play

**Google Play Billing is the only permitted payment method for digital goods sold to users in Turkey.** Turkey is not on the User Choice Billing country list, and the External Offers Program covers the EEA only.

- **Paddle, iyzico, Stripe, or any web-steer link for a digital unlock = rejection.** Do not embed external checkout links for digital goods in any app distributed in Turkey.
- **Monitor, don't act on:** the Turkish Competition Authority (Rekabet Kurumu) opened an investigation into Google Play Billing's mandate and anti-steering rules on 7 August 2025; no decision or interim measure had been published by September 2026. Google's rollout of its billing choice program and new fee model names no date for Turkey; its "rest of world" tranche is dated 30 September 2027. Until either changes the rule, Play Billing stays mandatory.

### Apple App Store

Turkey is outside the EU, so Apple's DMA terms do not apply: **all digital goods use Apple IAP (StoreKit)**, and external purchase links for digital goods are not permitted for Turkish users.

- **Physical goods and services consumed outside the app** are exempt on both stores — they may use any payment processor.

### Other markets (for an app that also sells outside Turkey)

| Market | Google Play | Apple App Store |
|---|---|---|
| Turkey | Play Billing mandatory | IAP mandatory |
| EU/EEA | Alternative billing or external links through Google's billing choice program; from 30 June 2026 the fee is split into a service fee plus a billing fee charged only on Play Billing | Link-out, an alternative payment provider or alternative distribution allowed; new terms from 1 October 2026 (see § Store Fee Enrollment) |
| US | Link-outs and alternative billing allowed under the Epic v. Google remedies, with a service fee on linked purchases and the billing fee only on Play Billing | Link-outs to web checkout allowed with no Apple commission under the Epic v. Apple injunction — in force, but under Supreme Court review |
| Default | Play Billing via RevenueCat | StoreKit via RevenueCat |

Whether to sell outside store billing anywhere is a planning decision: `00-domain-mobile-app.md` §5 forces it and defaults a v1 to store billing only. **RevenueCat abstracts both stores** — the agent codes one integration; RevenueCat routes to Play Billing or StoreKit per platform.

---

## RevenueCat as Entitlement Server

RevenueCat abstracts Google Play Billing and StoreKit into one subscription backend. It validates receipts, processes state transitions, acknowledges purchases and normalizes transaction data. **Do not build a custom receipt validation or RTDN listener for an MVP** — the edge cases (grace periods, billing retries, account holds, pause/resume, upgrade/downgrade, family sharing) cost hundreds of engineering hours.

**Pricing:** free while monthly tracked revenue stays under $2,500; above it, 1% of that month's tracked revenue. No per-user fee.

### Client-Side Integration

```typescript
// React Native (react-native-purchases) — configure ONCE at app start; configure() is synchronous
import { Platform } from 'react-native';
import Purchases from 'react-native-purchases';
import Env from 'env'; // the scaffold's zod-validated env — declare both keys in its schema

Purchases.configure({
  apiKey: Platform.OS === 'ios'
    ? Env.EXPO_PUBLIC_REVENUECAT_IOS_KEY      // appl_… — one public key per platform
    : Env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY, // goog_…
});

// After sign-in: tie purchases to the backend's user id; on sign-out, Purchases.logOut()
await Purchases.logIn(user.id);

// Entitlement check — UX only; the backend is the source of truth
const info = await Purchases.getCustomerInfo();
const isPremium = info.entitlements.active['premium'] !== undefined;
```

- RevenueCat issues **one public SDK key per platform** (`appl_…` for the App Store, `goog_…` for Google Play). The scaffold's `.env.example` ships both slots. When you wire billing, add both to `env.ts` (the schema and `_env`), and refuse an empty key before calling `configure`: `env.ts` runs its zod check only under `STRICT_ENV_VALIDATION=1` (the `prebuild:*` scripts), so at runtime a missing key otherwise reaches `configure` as `undefined`.
- Real purchases need an EAS development build — Expo Go only mocks the store.
- The RevenueCat app user id is the backend's `users.id` (the table `fabrik-lib/fastapi-user-auth` creates on `postgres-main`), set with `Purchases.logIn` after sign-in.
- **Never trust client-side entitlement state for gating premium content.** Client checks drive UX only.
- Paywalls load offerings from RevenueCat (and the scaffold's `/app-config` `paywall_id` pointer) — never hardcode prices or offering ids.

### Server-Side Verification (FastAPI backend)

Point RevenueCat's webhook at the backend and keep entitlement state in PostgreSQL:

```python
# POST /api/webhooks/revenuecat
@router.post("/api/webhooks/revenuecat")
async def revenuecat_webhook(
    request: Request, db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)
):
    # 1. RevenueCat sends the Authorization value exactly as configured in its dashboard. Compare it verbatim,
    #    in constant time, against a REQUIRED Settings field (core/10) — the app refuses to start without it,
    #    where os.getenv would have compared against "Bearer None".
    if not hmac.compare_digest(request.headers.get("Authorization", ""), settings.revenuecat_webhook_auth):
        raise HTTPException(status_code=401, detail="Invalid authorization")

    event = (await request.json())["event"]
    if event.get("environment") == "SANDBOX" and settings.app_env == "production":
        return {"status": "ignored"}  # sandbox purchases never grant production access

    # 2. Delivery is at-least-once and retried: record the event id and sync in ONE transaction. If the re-read
    #    fails, the event row rolls back with it and RevenueCat's retry processes the event again.
    async with db.begin():
        if not await record_event_once(db, event["id"]):  # INSERT … ON CONFLICT (event_id) DO NOTHING
            return {"status": "duplicate"}
        if event["type"] == "TEST":
            return {"status": "ok"}

        # 3. Events can arrive out of order and differ in shape: never infer state from event["type"].
        #    Re-read the customer from RevenueCat and store its active entitlements + expiry.
        #    TRANSFER carries transferred_from / transferred_to instead of app_user_id — sync every id it names.
        for user_id in event_user_ids(event):
            await sync_entitlements(db, user_id)  # GET /v1/subscribers/{user_id} → entitlement rows with expires_at

    return {"status": "ok"}
```

- **The webhook needs a database and two settings.** The scaffold's `server/` ships with no database and no auth; billing is the moment to flip `needs_database` and `has_bearer_api` (`00-domain-mobile-app.md` §4) and add two tables — entitlement rows (`user_id`, `entitlement_id`, `expires_at`) and `webhook_events` with a unique `event_id` — plus two required fields on the backend's `Settings` (`core/10-python.md`): `revenuecat_webhook_auth: str` and `app_env: str`.
- Answer RevenueCat quickly (it retries a slow or failed delivery); the single re-read is the only work done inline.
- **CANCELLATION means auto-renew is off (or a refund) — never revoke on it.** Access follows the entitlement's expiry, which the re-read returns; with grace periods on, BILLING_ISSUE and CANCELLATION arrive together and EXPIRATION only if the grace period lapses.
- Gate premium API routes on the stored entitlement (`expires_at > now()`), not on a RevenueCat call per request.
- **Do NOT poll the RevenueCat REST API per request.** Its limits vary by endpoint and load; read the `RevenueCat-Rate-Limit-Current-Limit` / `-Current-Usage` headers and honor `Retry-After` on 429. The only REST calls are the webhook-triggered re-reads.
- **Do NOT store granular transaction histories in PostgreSQL** — RevenueCat and the stores keep them.

### The Acknowledgment Rule

Google Play refunds and revokes any purchase not acknowledged within three days. RevenueCat acknowledges automatically; if you ever bypass it for a direct Play Billing integration, you must acknowledge every purchase yourself within that window.

---

## Receipt Validation & Piracy Prevention

Client-side receipt validation is fundamentally insecure — modified APKs (Lucky Patcher, etc.) bypass local checks entirely.

- **Server-side validation is mandatory.** The backend verifies entitlements via RevenueCat (webhook + re-read) or the Google Play Developer API — never the client's claim.
- **Play Integrity API** (optional): for high-value operations RevenueCat does not cover (e.g. unlocking server-side content by device), check its device, app and account verdicts. It replaced SafetyNet.
- RevenueCat validates receipts automatically through its SDK. Custom validation only if you bypass RevenueCat.

---

## Store API Versions

Both stores enforce SDK floors. RevenueCat abstracts both — keep the RevenueCat SDK current and it tracks them.

- **Google Play Billing Library:** Google retires one major version a year (deadline 31 August, extendable to 1 November). New apps and updates must use a supported major; read the current floor from Google's deprecation page, never from this file.
- **Apple StoreKit:** the original In-App Purchase API is deprecated (since iOS 18, receipts included); use StoreKit 2, which RevenueCat's SDK uses by default.
- **Minimum Xcode/SDK:** Apple raises the required SDK each spring; submissions built on an older SDK are rejected at upload. Read the current rule from Apple's upcoming-requirements page before a release.

---

## Store Fee Enrollment (15% Small Business Programs)

Fees depend on where the **user** is. **Neither store's small-developer rate is automatic** — enrol on both before the first paid submission.

### Google Play

- **Regions still on the legacy fee (Turkey included — Google dates the rest-of-world rollout 30 September 2027):** auto-renewing subscriptions are 15% from day one whatever you earn; other transactions are 15% on the first $1M a year only after enrolment, 30% without it or above it.
- **US, UK and EEA (from 30 June 2026), Australia and Japan (30 September 2026), Korea (31 December 2026):** a 10% service fee on the first $1M and on all auto-renewing subscriptions, 20–25% on other transactions, plus a 5% billing fee only when Google Play Billing is used.
- **Enrol:** Play Console → Payments profile → Associated developer accounts → create an Account Group under the LLC's full legal name, declare every associated account (even a solo one), accept the terms.

### Apple App Store Small Business Program

1. In App Store Connect (Agreements, Tax, and Banking — after the Paid Apps agreement), the Account Holder enrols.
2. Disclose all Associated Developer Accounts — their proceeds are combined for the $1M threshold.
3. Accept the program terms.
4. The reduced rate starts **15 days after the end of the fiscal month** in which Apple approves enrolment.

- SBP: 15% on the first $1M of proceeds a year; above $1M the standard rate applies for the rest of that year, and falling back under $1M re-qualifies you the next year.
- Without SBP, an auto-renewing subscription drops from 30% to 15% after a subscriber's first year of paid service.
- **EU (from 1 October 2026):** IAP 26% (15% for SBP members); link-out to the web 15% (10% SBP); an alternative in-app payment provider 20% (10% SBP); apps distributed through an alternative marketplace or the web pay a flat 5% Core Technology Commission. An SBP member keeps a 5-point difference by leaving IAP in the EU — whether that is worth a second billing path is `00-domain-mobile-app.md` §5's decision.

### Both Stores — Failure to Enroll

| Store | Without enrolment | With enrolment |
|---|---|---|
| Google Play (legacy regions) | 30% on non-subscription sales (subscriptions 15% regardless) | 15% on the first $1M |
| Apple App Store | 30% (subscriptions 15% after a subscriber's first paid year) | 15% on the first $1M |

---

## Teknokent Tax Treatment (applies to BOTH Apple and Google payouts)

<!-- Accounting-compliance guidance from primary sources and GİB rulings; confirm with your mali müşavir before treating it as binding. -->

Turkish tax law treats app-store income the same for Apple and Google. The rules below apply to both.

### Corporate Tax (KVK)

- **Law No. 4691 (Teknoloji Geliştirme Bölgeleri Kanunu), temporary article 2** exempts income derived exclusively from software, design and R&D work done in the zone from corporate tax, **until 31 December 2028**. Law No. 5746 is a separate R&D incentive and cannot be combined with this exemption for the same project's income.
- **Advertising revenue (AdMob, AppLovin, etc.) is excluded** — a GİB ruling (2022) treats app ad income as ordinary commercial income. Keep separate ledgers.
- For an app sold serially through the stores, GİB rulings exempt only the share attributable to the intangible right (the licence), not the whole sale — agree the split with the accountant before the first filing.
- A company whose exempt gain reaches the statutory threshold must set part of it aside into the fund the law names (4691 additional article 3) — have the accountant compute it.

### VAT (KDV)

- Sales to users **outside Turkey** through the stores are service exports — **0% KDV** (KDVK art. 11/1-a).
- Sales to users **inside Turkey:** mobile application software produced in the zone is KDV-exempt under KDVK temporary article 20/1 (until 31 December 2028), with the same intangible-right split for serial sales; anything outside the exemption carries the standard rate (20%). How the domestic portion is invoiced between you and the stores is disputed among practitioners — settle it with the accountant.
- The **digital services tax (DHV)** falls on the platforms (Apple, Google), not on the developer.

### The Gross Invoicing Rule (both stores)

Both stores remit the net amount after their fee. The prevailing administrative practice:

- Invoice the **gross** sale as a service export (0% KDV for non-Turkish users).
- Book the store's commission as an **expense** and self-assess KDV on it as an imported service via **KDV2** (reverse charge).
- Invoicing only the net deposit understates revenue — the accountant confirms the method before the first payout.
- Use each store's geographic payout reports for per-region invoicing.

### US Withholding Tax

File a **W-8BEN-E** with **both Google (Play Console) and Apple (App Store Connect)**. Without it, Google withholds on US-user earnings (backup or statutory withholding, up to 30%); Apple treats App Store proceeds as sales and generally withholds nothing, but still requires the form. With it, the rate depends on how the store classifies the income under the US-Turkey treaty — business profits (Article 7, no US permanent establishment) can be 0%, copyright royalties 10%. Chapter 4 status: Active NFFE.

### Payout Routing

Consider a multi-currency business account to hold USD/EUR before converting to TRY, rather than letting the store's payout convert automatically.

---

## Billing Launch Gates

The full launch protocol is `89-mobile-launch-checklist.md`. The billing gates, checked before the first paid submission:

- [ ] RevenueCat SDK integrated; the same products configured in **both** Play Console and App Store Connect.
- [ ] **"Restore Purchases" on the paywall** — omitting it is a rejection on both stores.
- [ ] Webhook → PostgreSQL entitlement sync live (auth check, event-id dedupe, re-read).
- [ ] No external billing links for digital goods where the store forbids them (Turkey: both stores).
- [ ] Small-developer rates enrolled on both stores; W-8BEN-E filed with both.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Paddle / iyzico / Stripe / web-steer for digital goods on mobile (Turkey) | Play Billing + Apple IAP via RevenueCat |
| The original StoreKit API in new iOS code | StoreKit 2 (the original API is deprecated) |
| Custom receipt validation / RTDN listener for an MVP | RevenueCat SDK + webhooks |
| Client-side entitlement trust for premium gating | Server-side entitlement rows synced from RevenueCat |
| Inferring entitlement state from the webhook event type | Dedupe on the event id, then re-read the customer |
| `os.getenv` for the webhook secret | A required Settings field compared verbatim — a missing secret must stop the app, not become "Bearer None" |
| One RevenueCat key for both platforms | One public SDK key per platform |
| Polling the RevenueCat REST API per request | Webhook-driven sync to PostgreSQL |
| Storing granular transaction history in PostgreSQL | Leave it to the stores + RevenueCat |
| Hardcoded prices or offering ids | RevenueCat offerings (remote) |
| Invoicing only the net store deposit (Turkish entity) | Invoice gross; expense the commission via KDV2 |
| Mixing ad revenue with IAP revenue in Teknokent filings | Separate ledgers — ad revenue is outside the exemption |
| Skipping small-developer enrolment | Enrol on both stores before the first paid submission |
| Missing "Restore Purchases" on the paywall | Mandatory on both stores |

---

## Related Rule Packs

- `80-mobile.md` — client-side mobile architecture, styling, compliance, i18n
- `core/85-payments-billing.md` — SaaS web billing (Paddle/iyzico) — different model, do not mix
- `core/35-security-auth.md` — Pattern A (`fabrik-lib/fastapi-user-auth`, default), token storage in `expo-secure-store`
- `core/55-observability.md` — backend structlog + GlitchTip; client Sentry RN SDK
- `core/10-python.md` — backend FastAPI patterns for webhook endpoints
- `00-domain-mobile-app.md` — planning-level decisions (monetization §5, finance §14)
- `89-mobile-launch-checklist.md` — the full go-to-market protocol (store accounts, listing, legal, review traps, staged rollout, post-launch)

---

## Done When

- [ ] RevenueCat configured once with one public key per platform; users tied to `users.id` via `Purchases.logIn`.
- [ ] Products configured in **both** Play Console and App Store Connect; "Restore Purchases" on the paywall.
- [ ] Webhook endpoint (`/api/webhooks/revenuecat`) compares the configured Authorization value verbatim (a required setting), drops sandbox events in production, dedupes on event id, and re-reads the customer into entitlement rows.
- [ ] Premium API routes gated on stored entitlement expiry, not on a RevenueCat call per request.
- [ ] No external billing links for digital goods where the store forbids them (Turkey: both stores).
- [ ] **Both stores:** small-developer rates enrolled before the first paid submission; W-8BEN-E filed.
- [ ] Ad revenue and IAP revenue on separate Teknokent ledgers; gross invoicing with the commission expensed via KDV2.
- [ ] A supported Play Billing Library major and StoreKit 2 (via a current RevenueCat SDK).
