---
activation: glob
globs: ["**/metro.config.*", "**/react-native.config.*", "**/app.json", "**/eas.json"]
description: Mobile app launch checklist — Turkish LLC, store compliance, Teknokent tax, staged rollout, beta testing, post-launch
trigger: glob
---
<!-- CONSUMER: Traycer (primary) + coding agents (verification)
     GOAL: Mobile launch-blocking gates — store accounts, legal, tax, review traps, rollout, post-launch
     TRAYCER USAGE: PRIMARY CONSUMER. Reads during epic decomposition to ensure every gate maps to a ticket.
     AGENT USAGE: Verify completeness at epic closure. Check items against Done When list. -->

# Mobile App Launch Checklist

Apply when planning or building a mobile app — especially during epic decomposition, epic-brief, and ticket creation. This pack answers "what must a mobile app include for launch?" not "how to code it." Skip for web-only SaaS, internal tools, or services with no mobile distribution.

**Source:** Gemini Deep Research (2026-05-24), validated against `80-mobile.md`, `81-mobile-billing.md`, and production experience. Specific to a React Native / Expo / Supabase / FastAPI stack deployed from a Turkish Teknokent LLC.

## Five Phases

- **Phase 0:** Pre-development — legal entity, store accounts, tax forms. Blocks everything.
- **Phase 1:** Pre-submission — store assets, privacy compliance, review traps. Blocks go-live.
- **Phase 2:** Beta — testing tracks, metrics validation. Blocks production release.
- **Phase 3:** Production launch — staged rollout, monitoring, OTA readiness.
- **Phase 4:** Post-launch (first 30 days) — optimization, retention, scale.

Traycer must ensure every Phase 0-1 item maps to a ticket during planning. Phase 2-4 items should appear in later epics.

---

## Phase 0: Pre-Development (Legal Architecture)

### Store Account Setup

- [ ] **D-U-N-S number obtained** via Dun & Bradstreet. Required for Organization accounts on both stores.
  - **Turkish character trap:** transliterate company name and address to ASCII (ü→u, ş→s, ı→i, ğ→g, ç→c, ö→o) during D-U-N-S registration. Apple and D&B legacy systems fail on Turkish characters, causing silent "entity mismatch" errors downstream.
- [ ] **Google Play Console** registered as **Organization** (not Personal) — bypasses the 14-day / 12-tester closed testing mandate (reduced from 20 in Dec 2024). Requires D-U-N-S + authorized representative ID + address matching Vergi Levhası.
- [ ] **Apple Developer Program** enrolled as **Organization** ($99/yr). Requires D-U-N-S + Account Holder with legal authority to bind the LLC.
  - Virtual offices without verifiable utility bills are heavily scrutinized. Ensure the D-U-N-S profile address is fully verifiable.

### Small Business Program Enrollment (15% Fee)

Both stores offer 15% commission (vs 30%) for the first $1M/year. **Neither is automatic.**

- [ ] **Apple SBP enrolled** — via App Store Connect → Agreements, Tax, and Banking. Must be completed AFTER accepting the Paid Apps agreement. Declare all Associated Developer Accounts. 15% rate begins 15 days after the end of the fiscal month of approval.
- [ ] **Google 15% enrolled** — via Play Console → Associated Developer Accounts. Create Account Group, declare all associated accounts (even suspended legacy ones), accept ToS.

> See `81-mobile-billing.md` § Store Fee Enrollment for full procedure.

### Cross-Border Tax (W-8BEN-E)

- [ ] **W-8BEN-E filed with Apple** via App Store Connect tax portal.
- [ ] **W-8BEN-E filed with Google** via Play Console tax portal.
- Chapter 4 status: **Active NFFE** (not Passive NFFE — that triggers complex substantial US owner reporting).
- Claim **Article 7** of the US-Turkey Tax Treaty (Business Profits) for 0% withholding. Confirm no US Permanent Establishment.
- Apple generally applies 0% on sales regardless of treaty claims (they classify revenues as "sales/commission" not "royalties"), but the form must still be filed accurately.

### Teknokent Tax Documentation

- [ ] **Gross invoicing** for both Apple and Google payouts — invoice the gross 100% as a Service Export (0% KDV for non-TR users). Expense store commissions (15-30%) via KDV2 (Reverse Charge VAT). Invoicing net = under-reported revenue = tax evasion = forfeits Teknokent exemption.
- [ ] **KDV split** — sales to users outside Turkey: 0% KDV (service export). Sales to users inside Turkey: 20% KDV. Use store geographic breakdown reports for accurate per-region invoicing.
- [ ] **KVK exemption** — under Law 5746, software sales (IAP, subscriptions) qualify for 100% Corporate Tax exemption if the LLC is in a Teknokent. Ad revenue (AdMob, AppLovin) is **excluded** — standard corporate rate, separate ledgers.
- [ ] **Invoice annotations** — must cite Teknokent Ministry Project Code, Law No. 4691 (Teknokent), and Law No. 3065 (KDV). Invoice description: "Mobil Uygulama İçi Satın Alma Lisans Bedeli" (not generic "App Store Revenue").

<!-- NOTE: Some accounting firms apply an 80/20 intangible-right / marketing-share split instead of 100% KVK exemption. This is a conservative interpretation. Our packs use the 100% exemption per Law 5746. Confirm with your mali müşavir which interpretation applies to your specific Teknokent project code. -->

> See `81-mobile-billing.md` § Teknokent Tax Treatment for the full breakdown.

### App Identity

- [ ] `ios.bundleIdentifier` and `android.package` set in `app.json` — **cannot be changed** after first store submission without creating a new listing.
- [ ] Namespaces align with ChottuLink deep link domains to prevent asset verification failures.
- [ ] Google Play App Signing configured — upload keystore generated, app signing key held by Google.
- [ ] iOS distribution certificate and provisioning profiles managed via `eas credentials`.

---

## Phase 1: Pre-Submission (Blocks Go-Live)

### Store Listing Assets (May 2026)

**Apple App Store:**
- [ ] **6.9" iPhone screenshots** — 1320×2868px (iPhone 16/17 Pro Max). Mandatory — auto-scales to smaller iPhones. 5.5" dropped.
- [ ] **13" iPad screenshots** — 2064×2752px. Mandatory if the app is universal.
- [ ] 1024×1024 app icon (no alpha channel).
- [ ] Subtitle (30 chars max) + description + keywords (100 chars, comma-separated, no spaces, no duplicates with title).

**Google Play:**
- [ ] Screenshots at minimum 1080×1920px. At least 4 for algorithmic recommendation eligibility.
- [ ] 128px icon, promotional tile (440×280), short description (80 chars max) + full description.
- [ ] No promotional claims ("#1 App", "Best") in screenshots — metadata rejection.

**Both stores:**
- [ ] Localized listings for `en` and `tr`. Turkish metadata must use local search terms, not direct translations of English ASO keywords.

### Privacy Compliance

- [ ] **Apple Privacy Manifest** (`PrivacyInfo.xcprivacy`) — declare every Required Reason API (NSUserDefaults, NSFileTimestamp for Sentry/Expo). Injected via `expo.ios.privacyManifests` in `app.json`.
- [ ] **Google Play Data Safety form** — accurately declare all SDK data collection (Sentry, Tenjin, RevenueCat, Supabase). Claiming "no data collected" while using MMPs/crash reporters triggers automatic suspension.
- [ ] **Privacy Policy URL** — publicly accessible (no geo-blocking), linked in both store listings AND in-app Settings.
- [ ] **ATT prompt** (iOS) — fires before any IDFA collection or Tenjin initialization. See `80-mobile.md` § Compliance.
- [ ] **GDPR consent gate** — blocks analytics and non-essential SDKs for EU/EEA/UK users until consent. See `80-mobile.md` § Compliance.

### Account Deletion & Restore

- [ ] **Account deletion** — in-app mechanism accessible from Settings. Backend: authenticated request → FastAPI endpoint → business logic (cancel RevenueCat, log in GlitchTip) → Supabase Admin API delete → `ON DELETE CASCADE` purges relational data. Never client-side RPC deletion.
- [ ] **"Restore Purchases" button** on paywall — mandatory on both stores. Apple is especially strict. Omission = automatic rejection.

### Review Traps

- [ ] **IPv6 compatibility** — Apple reviews in an IPv6-only sandbox. FastAPI backend must bind to `::` (not just `0.0.0.0`). VPS DNS must have AAAA records. IPv4-only backends fail silently during review.
- [ ] **Paywall transparency** — Terms and Privacy links must be directly visible below the subscription button without scrolling.
- [ ] **Sign in with Apple** — mandatory if any third-party/social login is offered (Apple Guideline 4.8). See `80-mobile.md`.
- [ ] **Test credentials** — prepare demo account credentials for Apple/Google reviewers to bypass Supabase Auth during review.

### Deep Link Verification

- [ ] **iOS AASA file** — `/.well-known/apple-app-site-association` served with `application/json` content-type over HTTPS. `ios.associatedDomains` set in `app.json`.
- [ ] **Android assetlinks.json** — `/.well-known/assetlinks.json` with SHA256 fingerprint from **Google Play App Signing key** (not local EAS upload key). `autoVerify: true` in Android intent filters.

### Billing Integration

- [ ] RevenueCat SDK integrated; subscription products configured in **both** Play Console and App Store Connect.
- [ ] Server-side entitlement verification via RevenueCat webhooks → PostgreSQL. See `81-mobile-billing.md`.
- [ ] No external billing links for digital goods (Turkey excluded from UCB/EOP; Apple IAP mandatory). See `81-mobile-billing.md` § Turkey.
- [ ] PBL 8.0 and StoreKit 2 (RevenueCat SDK handles both if kept updated).

---

## Phase 2: Beta Testing

### Google Play Track Progression

Organization accounts skip the 14-day closed testing mandate. Progression: Internal Testing → Closed Testing (optional) → Open Testing → Production.

- [ ] Submit build to Internal Testing track first for team validation.
- [ ] Optionally run Closed/Open Testing to gather external feedback.
- [ ] Verify crash-free rate and ANR rate in Play Console before promoting to Production.

### Apple TestFlight Progression

- [ ] **Internal Testing** (up to 100 team members) — no App Review required. Rapid iteration.
- [ ] **External Testing** (up to 10,000 testers) — requires Beta App Review. Provide test credentials for Supabase Auth bypass.
- [ ] Testers must accept invitation via the TestFlight app — email delivery alone is insufficient.

### Beta Metrics Gates

Before authorizing production release, validate:

- [ ] **Crash-free rate >99.5%** (Sentry) across low-end Android + flagship iOS. Below 99.5% triggers algorithmic penalties reducing store visibility.
- [ ] **API error rate near zero** (GlitchTip) — FastAPI 5xx errors profiled under concurrent load.
- [ ] **Activation rate** — `user_completed_onboarding` event firing in structured logs. If activation is poor, adjust onboarding before spending on acquisition.
- [ ] Source maps uploaded via EAS for readable Sentry stack traces.

---

## Phase 3: Production Launch

### Staged Rollout

- [ ] **Android:** release to **10%** of users initially. Monitor crash logs + ANR rates for 24h. Increase to 50%, then 100%.
- [ ] **iOS:** opt into **Phased Release** (7-day: 1%→2%→5%→10%→20%→50%→100%). Note: new app submissions are immediately searchable; phased release throttles automatic updates only.
- [ ] **Marketing campaigns** must NOT be scheduled until both binaries are in "Ready for Sale" / "Published" state.

### Day-1 Monitoring

- [ ] **ANR rate** (Android) — monitored via Play Console + Sentry. High ANR rates severely penalize store ranking.
- [ ] **Store ratings and uninstalls** — spike in early uninstalls indicates crash-on-launch or misleading listing.
- [ ] **Revenue validation** — RevenueCat webhooks → FastAPI → PostgreSQL entitlement updates verified end-to-end. Test a real purchase on both stores.

### OTA Updates & Forced Upgrade

- [ ] **EAS Update configured** — channel strategy matches EAS profiles (development, preview, production). Enables JS-only bug fixes without store review.
- [ ] **Forced upgrade gate** — client fetches `min_required_version` from FastAPI on startup. If client version is below threshold, show blocking modal directing to store. Must fail gracefully if backend is unreachable (never lock users out during downtime).

> EAS Update cannot modify native code. Native changes require a full binary rebuild + store submission.

### Rating Prompt

- [ ] **StoreReview API** triggered only after a "moment of delight" (first task completed, streak achieved, file downloaded). Never on first launch, never on app open. Centralize timing logic in a custom React hook tracking user milestones.

---

## Phase 4: Post-Launch (First 30 Days)

### Retention & Churn Analysis

- [ ] **RevenueCat cohort charts** — monitor free trial → paid conversion rate and first-renewal drop-off. High churn = re-evaluate onboarding + paywall value proposition.
- [ ] **Retention benchmarks** — D1: 30-40%, D7: 10-15% for utility/productivity apps. D1 below 20% indicates disconnect between store listing and in-app experience.
- [ ] **Turkish market involuntary churn** — monitor specifically. Turkish bank cards occasionally fail on recurring international billing.

### ASO Iteration

- [ ] **Google Play Store Listing Experiments** — A/B test icon, screenshots, short description against live traffic. Test one variable at a time.
- [ ] **Review response** — respond to all 1-3 star reviews within 24 hours. Address specific technical issues. Mention if a fix was pushed via EAS Update.

### Paid User Acquisition (when ready)

- [ ] Deploy paid UA (Apple Search Ads, Meta) only after organic CAC and ARPU are known.
- [ ] **Tenjin MMP** maps ad spend to RevenueCat subscription events for accurate ROAS.
- [ ] iOS: SKAdNetwork integration configured for attribution.

### Performance Drift

- [ ] **Bundle size budget** — CI/CD check in EAS pipeline warns if JS bundle exceeds threshold. Bundle drift degrades cold start time.
- [ ] **Cold start <2 seconds** — lazy-load non-initial route screens. Minimize synchronous operations on main thread.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Launch without Privacy Policy + Terms | Ship legal pages before first store submission |
| Personal Play Console account | Organization account (bypass 14-day tester mandate, corporate listing) |
| Skip 15% fee enrollment on either store | Explicit enrollment before first submission on each store |
| Missing W-8BEN-E on either store | File before first payout to avoid 30% US withholding |
| Invoice net store deposit (Turkish entity) | Invoice gross 100%; expense commission via KDV2 |
| Client-side account deletion (RPC) | Authenticated FastAPI endpoint → Supabase Admin API |
| Missing "Restore Purchases" on paywall | Mandatory — omission = store rejection |
| IPv4-only backend (no AAAA records) | Dual-stack (IPv4 + IPv6), FastAPI binds to `::` |
| Rating prompt on first launch | Trigger after user milestone / moment of delight |
| 100% day-one rollout | Staged: 10% → 50% → 100% (Android), phased release (iOS) |
| Marketing campaign before "Published" state | Wait until both binaries are live |
| Net invoicing or generic "App Store Revenue" description | Gross invoicing with specific Teknokent invoice annotations |
| Mixing ad revenue + subscription revenue in tax filings | Separate ledgers — ad revenue excluded from KVK exemption |

---

## Related Rule Packs

- `80-mobile.md` — client-side architecture, styling, compliance, i18n, ATT, GDPR consent
- `81-mobile-billing.md` — RevenueCat, entitlements, Turkey GPB-mandatory, Teknokent tax, store fee enrollment
- `35-security-auth.md` — Pattern B (Supabase Auth), token storage, CORS
- `55-observability.md` — Sentry, GlitchTip, health endpoints, Gatus
- `86-email-templates.md` — transactional email pipeline (verify, reset, dunning)
- `ocoron-mobile-design-system.md` — mobile component patterns
- `00-domain-mobile-app.md` — planning-level decisions (17 dimensions)

---

## Done When (Traycer reads this during decomposition)

During epic decomposition or epic-brief, verify these map to features or tickets:

### Phase 0

- [ ] D-U-N-S number obtained (ASCII-transliterated for Turkish entities)
- [ ] Google Play Organization account verified
- [ ] Apple Developer Organization account enrolled
- [ ] 15% Small Business Program enrolled on both stores
- [ ] W-8BEN-E filed on both stores
- [ ] Teknokent invoicing setup (gross invoicing, KDV split, separate ledgers)
- [ ] App identity locked (`bundleIdentifier` + `android.package`)

### Phase 1

- [ ] Store listing assets at current specs (6.9" iPhone, 13" iPad if universal, Play 1080×1920)
- [ ] Localized store listings (en + tr)
- [ ] Privacy Manifest (iOS) + Data Safety form (Android) completed
- [ ] Privacy Policy URL accessible and linked in stores + in-app Settings
- [ ] ATT prompt + GDPR consent gate implemented
- [ ] Account deletion endpoint (FastAPI → Supabase Admin API → CASCADE)
- [ ] "Restore Purchases" on paywall
- [ ] IPv6 dual-stack backend (AAAA records + `::` binding)
- [ ] Deep links verified (AASA + assetlinks.json)
- [ ] RevenueCat integrated, products configured on both stores
- [ ] Test credentials prepared for store reviewers

### Phase 2

- [ ] Beta tested via TestFlight (iOS) + Play Console tracks (Android)
- [ ] Crash-free rate >99.5%
- [ ] Source maps uploaded to Sentry
- [ ] Activation rate measured

### Phase 3

- [ ] Staged rollout configured (not 100% day-one)
- [ ] EAS Update channels configured
- [ ] Forced upgrade gate implemented
- [ ] Rating prompt on milestone, not first launch
- [ ] Revenue flow verified end-to-end (purchase → webhook → PostgreSQL entitlement)
