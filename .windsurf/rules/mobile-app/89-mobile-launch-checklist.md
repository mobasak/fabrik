---
activation: glob
globs: ["**/metro.config.*", "**/react-native.config.*", "**/app.json", "**/app.config.*", "**/eas.json"]
description: Mobile app launch checklist — Turkish LLC, store accounts and compliance, review traps, beta, staged rollout, post-launch
trigger: glob
currency_pass: 2026-10-01
---
<!-- CONSUMERS: /fabrik-release runs every gate here (PASS-with-evidence or BLOCKED); planning reaches it through
     00-domain-mobile-app.md, which cites § App Identity, § Privacy Compliance, § Account Deletion & Restore,
     § Beta Metrics Gates, § Staged Rollout and § OTA Updates & Forced Upgrade by name — keep those headings.
     Store fees, Teknokent tax and US withholding are OWNED by 81-mobile-billing.md; this pack lists the gate and cites it. -->

# Mobile App Launch Checklist

Apply when planning or building a mobile app — especially during epic decomposition and release. This pack answers "what must a mobile app include for launch?" not "how to code it." Skip for web-only SaaS, internal tools, or services with no mobile distribution.

Specific to a React Native / Expo client with the repo's own `server/` FastAPI backend on the fleet (Pattern A; `core/35-security-auth.md`), published by a Turkish Teknokent LLC.

## Five Phases

- **Phase 0:** Pre-development — legal entity, store accounts, tax forms. Blocks everything.
- **Phase 1:** Pre-submission — store assets, privacy compliance, review traps. Blocks go-live.
- **Phase 2:** Beta — testing tracks, metrics validation. Blocks production release.
- **Phase 3:** Production launch — staged rollout, monitoring, OTA readiness.
- **Phase 4:** Post-launch (first 30 days) — optimization, retention, scale.

Phase 0-1 items belong in the first release's epics; Phase 2-4 in later ones. At release, `/fabrik-release` gives every Phase 0-3 checklist item a verdict with evidence. Phase 0 facts live outside the repo (a D-U-N-S number, a store enrolment, a filed tax form), so their evidence is the row in the project's `docs/DECISIONS.md` where the operator recorded each one — record them as they happen. Phase 4 holds post-launch follow-ups, written as plain bullets: they are not release gates.

---

## Phase 0: Pre-Development (Legal Architecture)

### Store Account Setup

- [ ] **D-U-N-S number obtained** via Dun & Bradstreet. Required for Organization accounts on both stores.
  - **Turkish character trap:** register the company name and address in Roman characters (ü→u, ş→s, ı→i, ğ→g, ç→c, ö→o). Apple's enrolment form rejects other character sets, and a name that differs from the D&B record fails enrolment with a profile-mismatch error.
- [ ] **Google Play Console** registered as **Organization** (not Personal) — a personal account created after November 2023 must run a closed test (12 testers for 14 days) before production access. Verification needs a chamber-of-commerce registration certificate or a tax certificate (Vergi Levhası) plus an authorized representative's photo ID, matching the payments profile.
- [ ] **Apple Developer Program** enrolled as **Organization** (annual fee). Requires a D-U-N-S number for the legal entity (no trade names or branches) and an enrolling person with legal authority to bind it — an officer, or an employee granted that authority.
- [ ] **Payment card for the program fee** — Turkish debit and virtual cards are often declined; a physical credit card whose billing address matches the account works more reliably.

### Small Business Program Enrollment (15% Fee)

**Neither store's small-developer rate is automatic.** The rates, what applies to subscriptions, and the enrolment steps are `81-mobile-billing.md` § Store Fee Enrollment.

- [ ] **Apple SBP enrolled** — App Store Connect → Agreements, Tax, and Banking, after the Paid Apps agreement; all Associated Developer Accounts declared.
- [ ] **Google small-developer tier enrolled** — Play Console → Associated developer accounts: Account Group created, every associated account declared, terms accepted.

### Cross-Border Tax (W-8BEN-E)

- [ ] **W-8BEN-E filed with Apple** (App Store Connect tax section) and **with Google** (Play Console payments profile). Chapter 4 status: **Active NFFE**. How each store withholds, with and without the form, is `81-mobile-billing.md` § US Withholding Tax.

### Teknokent Tax Documentation

The rules are `81-mobile-billing.md` § Teknokent Tax Treatment; confirm each with the mali müşavir before the first payout.

- [ ] **Gross invoicing** for both stores' payouts, with the store commission self-assessed via **KDV2**.
- [ ] **Exemption split agreed** — for an app sold serially through the stores, rulings exempt only the intangible-right (licence) share.
- [ ] **Invoice wording** — an exempt sale's invoice states its legal basis (KDVK temporary article 20/1 for in-zone software; article 11 for exports). The Teknokent project code on the invoice is common audit practice, not a statutory requirement; no specific description wording is mandated.
- [ ] **Ad revenue on a separate ledger** — it is outside the exemption.

### App Identity

- [ ] `ios.bundleIdentifier` and `android.package` set in the app config (the scaffold's `app.config.ts`, from `env.ts`) — **cannot be changed** after the first store upload without a new listing.
- [ ] Namespaces align with the deep-link domains to prevent asset verification failures.
- [ ] Google Play App Signing configured — upload keystore generated, app signing key held by Google.
- [ ] iOS distribution certificate and provisioning profiles managed via `eas credentials`.

---

## Phase 1: Pre-Submission (Blocks Go-Live)

### Store Listing Assets

**Apple App Store:**
- [ ] **6.9" iPhone screenshots** (1260×2736, 1290×2796 or 1320×2868 px). App Store Connect scales them to smaller iPhones; the 5.5" set is no longer required.
- [ ] **13" iPad screenshots** (2064×2752 or 2048×2732 px) whenever the app runs on iPad.
- [ ] 1024×1024 app icon (no alpha channel).
- [ ] Subtitle (30 chars max) + description + keywords (100 chars, comma-separated, no duplicates with title).

**Google Play:**
- [ ] App icon 512×512, feature graphic 1024×500 (required to publish), 2–8 screenshots per device type, short description (80 chars max) + full description.
- [ ] No ranking or promotional claims ("#1 App", "Best") in the listing's title, icon or screenshots.

**Both stores:**
- [ ] Localized listings for `en` and `tr`. Turkish metadata must use local search terms, not direct translations of English ASO keywords.
- [ ] Age rating accurate — an app with user-generated content or chat is never rated 4+ / PEGI 3.

### Privacy Compliance

- [ ] **Apple Privacy Manifest** — declare every required-reason API category your code and SDKs use (for example UserDefaults, FileTimestamp) through `ios.privacyManifests` in the app config.
- [ ] **App Store privacy details** ("nutrition labels") in App Store Connect — answer for every data type the app and its SDKs collect; they must match the Data safety answers below and the privacy policy.
- [ ] **Google Play Data safety form** — declare every SDK that collects data (the scaffold ships Sentry and PostHog; add RevenueCat, and an MMP if one is added). The repo's own backend is first-party, not a third-party SDK. Claiming "no data collected" while shipping such SDKs gets the listing rejected or removed.
- [ ] **Privacy Policy URL** — publicly accessible (no geo-blocking), linked in both store listings AND in-app Settings.
- [ ] **ATT prompt** (iOS) — before any tracking SDK starts (an MMP, if added). See `80-mobile.md` § Compliance.
- [ ] **GDPR consent gate** — blocks analytics and non-essential SDKs for EU/EEA/UK users until consent. See `80-mobile.md` § Compliance.

### Account Deletion & Restore

- [ ] **Account deletion** — users can start deleting the whole account in the app (deactivation alone is not enough). Backend: authenticated request → FastAPI endpoint → delete the user row on `postgres-main` (`ON DELETE CASCADE` purges relational data) and the user's data held by third-party SDKs. Never client-side deletion.
- [ ] **Active subscriptions** — neither the backend nor RevenueCat can cancel an Apple subscription. Before deleting, tell the user their billing continues until they cancel it, and link to the store's subscription management (RevenueCat's customer info carries a management URL).
- [ ] **Sign in with Apple** — if the app offers it, revoke the user's Apple tokens through Apple's REST API when the account is deleted.
- [ ] **Google: web deletion link** — a web page where users can request account and data deletion without the app, entered in the Data safety form.
- [ ] **"Restore Purchases" button** on paywall — mandatory on both stores. Apple is especially strict. Omission = rejection.

### Review Traps

- [ ] **IPv6-only networks** — App Review tests on an IPv6-only network with DNS64/NAT64. The app must reach its backend by hostname, never by an IPv4 literal; an IPv4-only backend stays reachable through NAT64, so no AAAA record or `::` bind is needed for review.
- [ ] **Subscription disclosure** — the purchase flow shows the subscription's title, length and price, with working links to the Terms of Use (EULA) and the privacy policy; the same links go in the App Store metadata.
- [ ] **Equivalent login option** — if the primary account uses a third-party or social login, iOS must also offer a login option meeting Guideline 4.8's privacy criteria. See `00-domain-mobile-app.md` §4.
- [ ] **Reviewer sign-in** — a demo account in App Review Information (or a full demo mode). With passwordless sign-in (the `core/35-security-auth.md` default) the reviewer cannot read an inbox: give one allow-listed review account a fixed code, or ship a demo mode. `fabrik-lib/fastapi-user-auth` has no reviewer path today — build it in the backend until the module offers one.

### Deep Link Verification

- [ ] **iOS AASA file** — `/.well-known/apple-app-site-association` served with `application/json` content-type over HTTPS, no redirect. `ios.associatedDomains` set in the app config.
- [ ] **Android assetlinks.json** — `/.well-known/assetlinks.json` with the SHA-256 fingerprint of the **Google Play App Signing key** (not the local EAS upload key). `autoVerify: true` in Android intent filters.

### Billing Integration

- [ ] The billing gates pass (`81-mobile-billing.md` § Billing Launch Gates): products configured on both stores, Restore Purchases, the entitlement webhook live, no forbidden external billing links, small-developer rates and W-8BEN-E in place.
- [ ] A supported Play Billing Library and StoreKit 2, through a current RevenueCat SDK (`81-mobile-billing.md` § Store API Versions).

---

## Phase 2: Beta Testing

### Google Play Track Progression

Progression: Internal Testing → Closed Testing → Open Testing → Production. Organization accounts are not held to the personal-account closed-test rule.

- [ ] Submit build to Internal Testing track first for team validation.
- [ ] Optionally run Closed/Open Testing to gather external feedback.
- [ ] Check user-perceived crash and ANR rates in Play Console before promoting to Production.

### Apple TestFlight Progression

- [ ] **Internal Testing** (up to 100 team members) — no App Review required. Rapid iteration.
- [ ] **External Testing** (up to 10,000 testers) — the first build of a version needs Beta App Review; give the reviewer the same sign-in path as above.
- [ ] Testers join through the TestFlight app, by email invitation or a public link.

### Beta Metrics Gates

Before authorizing production release, validate:

- [ ] **Crash-free rate ≥99.5%** (Sentry) across low-end Android + flagship iOS — the house gate, set well inside Google Play's bad-behavior thresholds (user-perceived crash rate 1.09%, ANR rate 0.47%, 8% on any single phone model), above which Play makes the app less discoverable. Apple publishes no equivalent threshold.
- [ ] **API error rate near zero** (GlitchTip) — FastAPI 5xx errors profiled under concurrent load.
- [ ] **Activation rate** — `user_completed_onboarding` event firing in structured logs. If activation is poor, adjust onboarding before spending on acquisition.
- [ ] Source maps uploaded during EAS Build by the Sentry Expo config plugin (`SENTRY_AUTH_TOKEN` as an EAS environment variable with `sensitive` visibility in every environment your build profiles use — `eas env:set --name SENTRY_AUTH_TOKEN --value … --environment production --visibility sensitive`, and an older EAS CLI without `env:set` takes the same flags on the now-deprecated `eas env:create`; always pass `--visibility`, since a non-interactive `env:set` stores a new variable as `plaintext`. Not `secret`, even if you only run EAS Build today: Expo's guide sets it `sensitive` because the same token also uploads source maps for `eas update` (`npx sentry-expo-upload-sourcemaps dist`, run where `eas update` runs, outside EAS servers), and a secret cannot be read there. Never an `EXPO_PUBLIC_` name, which is inlined into the bundle; organization and project set) for readable stack traces.

---

## Phase 3: Production Launch

### Staged Rollout

- [ ] **Android:** release updates as a staged rollout — **10%** first, 24h of crash and ANR monitoring, then 50%, then 100% (house schedule; a rollout can be halted at any point). A first release cannot be staged.
- [ ] **iOS:** opt into **Phased Release** for every update (7-day: 1%→2%→5%→10%→20%→50%→100%, pausable). A first release cannot be phased, and phased release throttles automatic updates only; new downloads and manual updates get the new version at once.
- [ ] **Marketing campaigns** must NOT be scheduled until both binaries are in "Ready for Sale" / "Published" state.

### Day-1 Monitoring

- [ ] **ANR and crash rates** (Android) — Play Console vitals + Sentry; above Play's bad-behavior thresholds the app loses visibility.
- [ ] **Store ratings and uninstalls** — spike in early uninstalls indicates crash-on-launch or misleading listing.
- [ ] **Revenue validation** — RevenueCat webhooks → FastAPI → PostgreSQL entitlement updates verified end-to-end. Test a real purchase on both stores.

### OTA Updates & Forced Upgrade

- [ ] **EAS Update configured** — the `preview` and `production` build profiles carry update channels (the scaffold's `development` profile has none). Enables JS-only bug fixes without store review.
- [ ] **Forced upgrade gate and kill-switch** — on startup the client calls the scaffold's `GET /app-config?platform=…&version=…` (`fabrik-lib/mobile-config`); the server compares versions and returns `update_required`, `update_available`, `kill_switch` and `store_urls`. Block on `update_required` with a link to the store; show the kill-switch message when it is set. Fail open when the backend is unreachable (never lock users out during downtime).

> EAS Update cannot modify native code. Native changes require a full binary rebuild + store submission.

### Rating Prompt

- [ ] **Store review prompt** (`expo-store-review`) only after a "moment of delight" (first task completed, streak achieved, file downloaded) — never on first launch or app open. iOS shows the prompt at most three times a year per user, so spend it well. Centralize timing logic in a custom React hook tracking user milestones.

---

## Phase 4: Post-Launch (First 30 Days)

### Retention & Churn Analysis

- **RevenueCat cohort charts** — monitor free trial → paid conversion rate and first-renewal drop-off. High churn = re-evaluate onboarding + paywall value proposition.
- **Retention** — track D1/D7/D30 against a published benchmark for your category, naming the source; published ranges vary widely by category, so no single number is a target.
- **Turkish market involuntary churn** — monitor specifically. Turkish bank cards occasionally fail on recurring international billing.

### ASO Iteration

- **Google Play Store Listing Experiments** — A/B test icon, screenshots, short description against live traffic. Test one variable at a time.
- **Review response** — respond to all 1-3 star reviews within 24 hours. Address specific technical issues. Mention if a fix was pushed via EAS Update.

### Paid User Acquisition (when ready)

- Deploy paid UA (Apple Search Ads, Meta) only after organic CAC and ARPU are known — the decision and its timing are `00-domain-mobile-app.md` §4 and §9.
- **MMP** (default Tenjin) maps ad spend to RevenueCat subscription events for ROAS.
- iOS: SKAdNetwork attribution configured (AdAttributionKit too if the app ships through an EU alternative marketplace).

### Performance Drift

- **Bundle size budget** — CI/CD check in EAS pipeline warns if JS bundle exceeds threshold. Bundle drift degrades cold start time.
- **Cold start <2 seconds** — lazy-load non-initial route screens. Minimize synchronous operations on main thread.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Launch without Privacy Policy + Terms | Ship legal pages before first store submission |
| Personal Play Console account | Organization account (no personal-account closed-test hold, corporate listing) |
| Skip small-developer enrollment on either store | Explicit enrollment before first submission on each store |
| Missing W-8BEN-E on either store | File before the first payout (`81-mobile-billing.md` § US Withholding Tax) |
| Invoice net store deposit (Turkish entity) | Invoice gross; expense commission via KDV2 |
| Client-side account deletion | Authenticated FastAPI endpoint → `postgres-main` delete → `ON DELETE CASCADE` |
| Deleting an account without telling the user their store subscription continues | Warn and link to the store's subscription management first |
| Missing "Restore Purchases" on paywall | Mandatory — omission = store rejection |
| IPv4 address literals in the app | Hostnames only — App Review runs on IPv6-only DNS64/NAT64 |
| Rating prompt on first launch | Trigger after user milestone / moment of delight |
| 100% day-one rollout | Staged: 10% → 50% → 100% (Android updates), phased release (iOS) |
| Marketing campaign before "Published" state | Wait until both binaries are live |
| An exempt invoice with no legal basis stated | State the exemption article (`81-mobile-billing.md` § Teknokent Tax Treatment) |
| Mixing ad revenue + subscription revenue in tax filings | Separate ledgers — ad revenue is outside the exemption |

---

## Related Rule Packs

- `80-mobile.md` — client-side architecture, styling, compliance, i18n, ATT, GDPR consent
- `81-mobile-billing.md` — RevenueCat, entitlements, Turkey billing, Teknokent tax, store fee enrollment, US withholding
- `core/35-security-auth.md` — Pattern A (`fabrik-lib/fastapi-user-auth`, passwordless default), token storage, CORS
- `core/55-observability.md` — Sentry, GlitchTip, health endpoints, Gatus
- `core/86-email-templates.md` — transactional email pipeline (verify, reset, dunning)
- `ocoron-mobile-design-system.md` — mobile component patterns
- `00-domain-mobile-app.md` — planning-level decisions (17 dimensions)

---

## Done When (`/fabrik-release` checks each; Phase 0's evidence is the operator's `docs/DECISIONS.md` row)

### Phase 0

- [ ] D-U-N-S number obtained (Roman-character name and address)
- [ ] Google Play Organization account verified
- [ ] Apple Developer Organization account enrolled
- [ ] Small-developer rate enrolled on both stores
- [ ] W-8BEN-E filed on both stores
- [ ] Teknokent invoicing set up (gross invoicing, KDV2, exemption split, legal basis on exempt invoices, separate ad ledger)
- [ ] App identity locked (`bundleIdentifier` + `android.package`)

### Phase 1

- [ ] Store listing assets at current specs (6.9" iPhone, 13" iPad if the app runs on iPad, Play icon + feature graphic + screenshots)
- [ ] Localized store listings (en + tr)
- [ ] Privacy Manifest + App Store privacy details (iOS) and Data safety form (Android) completed
- [ ] Privacy Policy URL accessible and linked in stores + in-app Settings
- [ ] ATT prompt + GDPR consent gate implemented
- [ ] Account deletion in the app and (Google) on the web, with the subscription warning
- [ ] "Restore Purchases" on paywall
- [ ] No IPv4 literals in the app; reachable on an IPv6-only network
- [ ] Deep links verified (AASA + assetlinks.json)
- [ ] Billing launch gates passed (`81-mobile-billing.md`)
- [ ] Reviewer sign-in prepared (demo account or demo mode that works with passwordless sign-in)

### Phase 2

- [ ] Beta tested via TestFlight (iOS) + Play Console tracks (Android)
- [ ] Crash-free rate ≥99.5%
- [ ] Source maps uploaded to Sentry
- [ ] Activation rate measured

### Phase 3

- [ ] Staged rollout configured (not 100% day-one)
- [ ] EAS Update channels configured
- [ ] Forced upgrade gate on `/app-config` implemented, failing open
- [ ] Rating prompt on milestone, not first launch
- [ ] Revenue flow verified end-to-end (purchase → webhook → PostgreSQL entitlement)
