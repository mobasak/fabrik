<!-- Mobile App Domain Module — paste into Traycer workflow GUI.
     Part 1: paste with mega-epic-breakdown (00 + 02)
     Part 2: paste when starting my-workflow for a mobile epic
     Auto-select when scaffold signal includes mobile-app.
     Consumer: Traycer planning LLM (NOT coding agents).
     Coding agents use .windsurf/rules/80-mobile.md instead. -->

# Mobile App Domain Module (17 dimensions)

## Operating Lens (solo + AI fleet)

- **Build cost is cheap** — agents implement. One codebase only; never maintain two native apps.
- **Your time is the scarce resource** — every default optimizes **set-and-forget ops**, never quality.
- **Pro-grade is non-negotiable** — crash-free, fast cold start, store-compliant from v1.

## Mobile is not web — the 3 forks (do NOT inherit SaaS defaults here)

1. **Billing is forced IAP** — Apple/Google mandate StoreKit/Play Billing for in-app digital goods (15-30% cut). **Paddle does NOT apply in-app.** Paddle only for physical goods/services consumed *outside* the app.
2. **The app ships outside Fabrik** — the binary goes through EAS to stores, **not Coolify**. Only the **backend** (python-api + Supabase) follows the 4-stage VPS lifecycle. State this explicitly in the Vision Summary.
3. **Platform dependency is existential** — Apple/Google can reject, delay, or remove you. This is the #1 mobile risk, not a footnote.

## Completeness Test (apply per dimension)

A dimension belongs at intake **only if** wrong = **irreversible** or **kills before build**. Else it's downstream. Resolve each or log as Open Question. **No "TBD" survives confirmation.**

---

## Part 1 — Mega-Epic (paste with 00 + 02)

### 1A. Vision Intake Dimensions

#### 1. Market & Positioning

**Force:** named ICP, the one job-to-be-done, app category, 3-5 named competitor apps, positioning + moat sentence.

**Default:** vertical wedge with unfair depth; moat = data/domain depth, never features.

**Why now:** category + positioning drive ASO keywords, screenshots, and the entire funnel.

#### 2. Geographic Market & Soft-Launch

**Force:** launch geo + store-country availability + soft-launch market.

**Default:** build international-grade (en-first); soft-launch one small geo to tune retention before global.

**Why now:** localized store listings + currency are set per market; retrofitting i18n is a rebuild.

#### 3. Buyer / User / App Category

**Force:** consumer vs B2B; who pays (user vs employer); free vs paid-download vs subscription.

**Default:** consumer subscription or B2B-issued. If B2B-procured, store IAP may not fit (use web checkout + login).

**Why now:** this gates the entire monetization fork (IAP vs external billing).

#### 4. Platform, Framework & Architecture (irreversibles)

Reference `.windsurf/rules/80-mobile.md` for implementation detail. At intake, force:

- **Framework: React Native + Expo + EAS** (decided — do not reopen). One codebase, managed build/submit/OTA, TypeScript synergy with web stack, Ocoron design system mapping via unistyles, MCP verification loop. **Never dual-native. Never Flutter** (evaluated and rejected — RN+Expo is the Fabrik standard; switching would discard the entire 80-mobile ruleset, i18n pipeline, and TS ecosystem).
- **Backend:** **Supabase** (auth, db, realtime, storage — first-class mobile SDKs) + python-api for custom logic; postgres-main for non-Supabase data.
- **Auth: Supabase Auth** (decided — do not reopen). Firebase Auth was evaluated and rejected: Supabase Auth serves the same "managed IdP" role but keeps identity + data + RLS + realtime on one platform, avoids dual-UID systems, and the JWKS verification flow is identical. See `35-security-auth.md` Pattern B. **Sign in with Apple is mandatory** if you offer any other social login on iOS; tokens in `expo-secure-store`.
- **Offline/sync:** online-first + offline-read cache by default; full offline-write+sync only if the use case demands it (large maintenance lift).
- **Attribution plumbing (build-time mandate):** MMP SDK (Tenjin — 2k conv/mo free, flat $200 after) + Universal Links (iOS AASA) / App Links (Android assetlinks.json) wired as **Expo config plugins at prebuild, tested via EAS dev build — not Expo Go.** Deep-link routing via ChottuLink (25k MAU free). **Firebase Dynamic Links is dead (Aug 2025) — never reference it.** Retrofit = full binary re-review + permanently lost early-cohort attribution.

**Why now:** framework, backend, auth, sync model, and attribution plumbing are schema/SDK-level — retrofit = rewrite.

#### 5. Monetization & Store Billing

Reference `.windsurf/rules/81-mobile-billing.md` for full billing discipline. At intake, force:

**Force:** IAP product types (consumable / subscription / one-time), tiers, trial, entitlement model.

**Default:** **RevenueCat over StoreKit/Play Billing** — set-and-forget receipts, entitlements, cross-platform. Apple Small Business Program = 15% under $1M. **EU rule:** stay on SBP 15% IAP in the EU — the 2026 Core Technology Commission makes EU external link-out approximately 18% effective, which is *worse*. External web billing only pays off in US/unregulated regions.

**Turkey constraint:** Google Play Billing is mandatory for digital goods — Turkey is excluded from UCB and EOP. Paddle/iyzico/Stripe web-steer = instant rejection. See `81-mobile-billing.md`. Ad revenue is taxed separately from subscription revenue under Teknokent — maintain separate ledgers.

**Why now:** in-app billing is the forced path; entitlement gating must exist before paywalled features.

#### 6. Push & Re-engagement

Reference `.windsurf/rules/80-mobile.md` § Push Notifications. At intake, force:

**Force:** push provider + permission strategy + the re-engagement triggers (mobile's retention engine, replacing email-first).

**Default:** FCM via Expo Push or OneSignal; **prime before the OS permission prompt**; trigger on activation/expansion/win-back.

**Why now:** push opt-in is a one-shot ask; lose it at install and re-engagement is gone.

#### 7. Permissions & Device Capabilities

**Force:** which capabilities (camera, location, contacts, biometrics, notifications) — minimize.

**Default:** request **just-in-time with priming**, never at launch; declare privacy labels honestly.

**Why now:** each permission = friction + review scrutiny; over-asking tanks install-to-activation.

#### 8. Distribution, Updates & API Versioning

Reference `.windsurf/rules/80-mobile.md` § Build & Dev Workflow. At intake, force:

**Force:** release cadence, staged rollout, **forced-upgrade gate**, OTA strategy, backend backward-compat.

**Default:** store release + **OTA (EAS Update / Shorebird) for JS/Dart-only fixes**; versioned API; backend supports old clients; forced upgrade only for breaking changes.

**Why now:** old app versions live on phones forever — you can't deprecate an endpoint v1.0 still calls; review delays block hotfixes unless OTA exists.

#### 9. ASO & Acquisition

**Force:** ONE primary channel + ASO assets (title, keywords, screenshots, review strategy).

**Default:** **ASO + content** (compounding, low-cost); ratings drive ranking, prompt for review at the activation moment. **Short-video** (TikTok / YouTube Shorts / Reels) — the primary B2C app-discovery channel; **GEO/AI-answer optimization** ("best app for X" queries — mandatory pairing with ASO); **web-to-app** (SEO/GEO landing page that drives installs via deferred deep link + ChottuLink routing — ties to MMP attribution in §12); Product Hunt launch.

**Partner / creator / referral channels:**

- **Partner/creator payouts** — **programmatic App Store Offer Codes + Google Play Promo Codes via API (deterministic — default).** 100% accurate, bypasses ATT entirely, no MMP needed. Fingerprinting/deep-link matching decays 5-10%/yr and is unsafe for paying partners — you'd systematically underpay your best creators.
- **Referral (user-to-user)** — **RevenueCat custom attributes + webhooks (serverless, set-and-forget).** No separate referral platform needed.
- **Paid UA** — MMP (Tenjin) + deep-link routing (ChottuLink). This is the *only* place MMP belongs. Platforms: Apple Search Ads, Meta, TikTok. Retargeting via MMP. Post-PMF only.
- **CPI networks** — **avoid.** $41.4B fraud ecosystem; needs enterprise fraud tooling you can't justify solo.

**Why now:** mobile CAC is paid-heavy — without an organic engine you burn cash; "no channel" kills the app.

#### 10. Onboarding, Retention & Support

**Force:** first-session value, permission-priming flow, retention triggers (D1/D7/D30), low-touch support.

**Default:** value before signup where possible; automate onboarding; in-app support + docs.

**Why now:** mobile retention curves are brutal; D1 is decided by the first 60 seconds.

#### 11. Performance & UX Quality (pro-grade)

Reference `.windsurf/rules/80-mobile.md` § Lists, Styling, Accessibility, Platform-Aware. At intake, force:

**Force:** cold-start target, app size budget, crash-free-rate target, offline UX, accessibility, native feel.

**Default:** crash-free >=99.5%, lean bundle, no jank; accessibility from v1.

**Why now:** store ranking weights crashes/ANR; janky apps get uninstalled and 1-starred — hard to recover.

#### 12. Analytics, Attribution & Crash/Stability

**Force:** funnel events, install attribution, crash/ANR reporting.

**Default:** product analytics + **Sentry/Crashlytics** (pro-grade). Attribution stack: **AdAttributionKit (AAK)** replaces SKAdNetwork (aggregate/coarse; Apple Search Ads now flows through AAK). **Android Install Referrer = deterministic; iOS = aggregate-only.** MMP (Tenjin) for paid-UA attribution and deep-link routing only — partner attribution comes from offer codes (§9), not the MMP. Never reference Firebase Dynamic Links (dead Aug 2025).

**Why now:** post-ATT attribution is hard and must be wired before spend; crashes you don't see, you can't fix.

#### 13. Legal, Compliance & Store Policy

Reference `.windsurf/rules/80-mobile.md` § Compliance (Worldwide). At intake, force:

**Force:** Apple privacy nutrition labels, ATT prompt, Play Data Safety form, **in-app account deletion (Apple-mandated)**, KVKK/GDPR.

**Default:** Supabase handles data terms; account-delete flow built in v1; honest data disclosures.

**Why now:** missing account-deletion or false privacy labels = guaranteed rejection.

#### 14. Finance & Unit Economics

**Force:** store-cut-adjusted LTV (15-30% off the top), CAC target, payback <12mo, LTV:CAC >=3, backend COGS. **Partner economics:** 15% store + 25% partner commission = approximately 60% gross margin, which then absorbs infra + LLM API costs + Turkey's 7.5% DST. Model before committing to any paid partner channel.

**Default:** price assuming 30% cut (15% if SBP-eligible); know the paid-UA payback before spending.

**Why now:** the store cut materially changes the LTV math vs your SaaS/Paddle defaults.

#### 15. Risk Register

**Force:** top 5 risks + mitigation — **platform deplatform/rejection (existential)**, review-delay-blocks-hotfix, IAP dependency, single-channel, key-person.

**Default:** OTA to mitigate review delay; web fallback for critical flows; named owner-action per risk.

**Why now:** Apple/Google control your distribution — plan for rejection, not around it.

#### 16. Ops & Solo-Dev Load

**Force:** what's automated (build, submit, OTA, entitlements, alerting) vs needs you; version-support matrix; review-response load.

**Default:** EAS + RevenueCat + Supabase + Sentry = near-zero recurring ops; set-and-forget bias.

**Why now:** two store accounts + version sprawl scales to burnout if not automated from day 1.

#### 17. Sequencing & Kill Criteria

**Force:** internal test, closed beta, soft-launch (one geo), public; explicit kill/pivot criteria **with a date**.

**Default:** validate retention in soft-launch before paid scale; ship the wedge, then expand.

**Why now:** the structural defense against the Forex pattern — prove retention before spending on growth.

#### Vision Summary Gate

Vision Summary may confirm only when **all 17 are resolved or logged as Open Questions**. Map onward:

- Decisions to `Technology Decisions` + `Value Streams`.
- Unresolved to `Open Questions` (block confirmation).
- **Fabrik-fit:** backend = `python-api` + Supabase follows the 4-stage VPS lifecycle. App binary goes through EAS to stores, **outside Coolify** — state this in the summary. App + backend = multi-epic, route to `02-epic-decomposition-command`.

### 1B. Epic Decomposition Directives

When decomposing a mobile app vision into epics, these dimensions shape boundaries:

#### Mandatory Epic Coverage

Every mobile mega-epic MUST have dedicated coverage for:

| Dimension | Epic boundary rule |
|---|---|
| §4 Backend + Auth + Data model | Foundation epic (Epic 1) — Supabase schema, RLS, auth (incl. Sign in with Apple), API scaffold. Everything else depends on this. |
| §4 App skeleton + Navigation | Own epic or first part of foundation — framework setup, navigation structure, design system, platform config. |
| §5 Monetization (RevenueCat + IAP) | Own epic or explicitly assigned. Entitlement gating must exist before paywalled features. |
| §6 Push + Re-engagement | Belongs in the epic that owns notification triggers, not deferred to "polish." |
| §8 Distribution + OTA | Belongs in the epic that sets up EAS Build/Submit/Update pipeline. Usually foundation or integration epic. |
| §10 Onboarding | Belongs in the epic that owns the first-session experience. Never deferred past v1. |
| §13 Compliance | Account deletion, privacy labels, ATT prompt — belongs in foundation epic. Store-blocking if missing. |

#### Two-Lane Split

Mobile projects naturally split into two parallel lanes after the foundation epic:

- **Backend lane** (python-api + Supabase) — deploys to VPS via Coolify. Follows Fabrik 4-stage lifecycle.
- **Client lane** (React Native app) — builds via EAS, submits to stores. Does NOT deploy via Coolify.

These lanes are naturally parallel. Each lane can have multiple agents working simultaneously. The integration point is the API contract — define it in the foundation epic, both lanes implement against it.

#### Parallel Lane Opportunities

After foundation:

- **Core feature screens** — independent of monetization after API contract exists
- **Monetization (RevenueCat + paywall)** — independent of core features after schema exists
- **Push + re-engagement** — independent after notification triggers are defined
- **Onboarding wizard** — independent after auth + first screen exist
- **Analytics instrumentation** — belongs inside each feature ticket, not a separate epic

#### Anti-Patterns

- Do NOT create separate iOS and Android epics — one codebase, one lane.
- Do NOT defer monetization to "later" — entitlement gating shapes the feature tree.
- Do NOT defer push permission strategy — it's a one-shot ask, design it upfront.
- Do NOT create a "testing epic" — testing is per-ticket (Maestro flows, reference `80-mobile.md` § Testing).
- Do NOT skip compliance in foundation — account deletion + privacy labels = store-blocking.

#### Phase Mapping

- **Internal test:** EAS development build on team devices.
- **Closed beta:** TestFlight (iOS) + Play Internal Testing (Android).
- **Soft-launch:** one small geo, measure D1/D7/D30 retention before global.
- **Public launch:** full store availability after retention validated.

---

## Part 2 — Per-Epic (paste when starting my-workflow for a mobile epic)

These directives apply throughout all my-workflow steps when the epic belongs to a mobile app project. Traycer carries them from epic-brief through ticket-breakdown and into execution plans.

### 2A. Epic Brief (my-workflow/01)

When creating the epic brief for a mobile epic:

- State which of the 17 dimensions this epic addresses (by number).
- Carry forward resolved decisions from the Vision Summary — do not re-decide.
- **State the lane:** is this a backend epic, a client epic, or a cross-cutting epic? This determines the agent's working environment (VPS/Docker vs Expo/EAS).
- If this epic is the foundation epic (§4), the brief must include: framework choice, Supabase schema, auth provider (incl. Sign in with Apple mandate), API contract shape, navigation structure.
- If this epic touches monetization (§5), the brief must include: IAP product types, RevenueCat offering IDs, entitlement gating matrix, pricing tiers. The coding agent implements a decided design.
- If this epic touches compliance (§13), the brief must include: which privacy labels, which permissions, account deletion flow.

### 2B. Core Flows (my-workflow/02)

When mapping core flows for a mobile epic, include these mobile-specific flows if the epic touches them:

- **First-session flow:** app launch, permission priming, onboarding wizard (value before signup if possible), activation event. Map the exact screen sequence. Name the activation event.
- **Monetization flow:** free experience, paywall trigger, plan selection, IAP purchase (StoreKit/Play Billing via RevenueCat), entitlement granted, subscription management.
- **Push permission flow:** value moment reached, priming screen ("here's what you'll get"), OS prompt, opt-in/opt-out handling.
- **Offline/reconnect flow:** cached data display, sync indicator, conflict resolution (if offline-write supported), reconnection sync.
- **Update flow:** app version check, soft prompt for update, forced upgrade gate for breaking changes, OTA silent update for JS-only patches.
- **Account deletion flow:** in-app Settings, confirm intent, data export option, deletion executed, confirmation (Apple-mandated).

Each flow must identify the `[PRIMARY PATH]` — the happy path. These become Maestro E2E test targets.

**Screen inventory:** `.windsurf/rules/80-mobile.md` § Screen Inventory lists the 17 mandatory screens every mobile app ships. Core-flows must map to these screens + derive any project-specific screens not in the inventory.

### 2C. Tech Plan (my-workflow/03)

When creating the tech plan for a mobile epic, enforce:

- **Two-lane architecture:** backend (Supabase + python-api on VPS) and client (React Native + EAS) are separate build/deploy units. API contract is the bridge — define versioned endpoints.
- **Auth architecture:** Supabase Auth with `expo-auth-session` for OAuth, `expo-secure-store` for tokens. Sign in with Apple mandatory if any social login offered on iOS. Reference `.windsurf/rules/80-mobile.md` § Backend Integration.
- **State management:** React Query for server state, Zustand for UI state, MMKV for local persistence. Reference `.windsurf/rules/80-mobile.md` § State Management.
- **Monetization architecture:** RevenueCat SDK, server-side entitlement verification via RevenueCat webhook to Supabase, paywall remote-configurable. Reference `.windsurf/rules/80-mobile.md` § Monetization.
- **Push architecture:** `expo-notifications`, APNs/FCM via EAS credentials, device tokens in Supabase, deep link payloads. Reference `.windsurf/rules/80-mobile.md` § Push Notifications.
- **Offline architecture:** online-first + MMKV read cache. Full offline-write+sync only if Vision Summary explicitly required it (large maintenance cost).
- **API versioning:** backend supports N and N-1 API versions simultaneously. Forced upgrade gate in client for breaking changes.
- **Compliance architecture:** Privacy Manifest, ATT prompt before tracking, GDPR consent gate, account deletion endpoint. Reference `.windsurf/rules/80-mobile.md` § Compliance.

### 2D. Ticket Outline (my-workflow/05)

When creating the ticket outline for a mobile epic, verify coverage:

- If this epic owns auth: tickets for Supabase Auth setup + Sign in with Apple + secure token storage + org model (if B2B).
- If this epic owns the app skeleton: tickets for Expo config + navigation structure + design system (Ocoron via unistyles) + safe area handling.
- If this epic owns monetization: tickets for RevenueCat integration + IAP product config + paywall UI + entitlement gating middleware + server-side verification.
- If this epic owns push: tickets for `expo-notifications` setup + permission priming + token storage + deep link routing.
- If this epic owns onboarding: tickets for first-session flow + permission priming + activation event tracking.
- If this epic owns compliance: tickets for Privacy Manifest + ATT prompt + GDPR consent gate + account deletion + data export.
- If this epic owns distribution: tickets for EAS profiles (dev/preview/prod) + CI/CD (GitHub Actions) + OTA channel config.
- Analytics instrumentation is NOT a separate ticket — it belongs inside each feature ticket as an AC.
- Every ticket that touches UI must have `80-mobile.md` in its Rule Packs.
- E2E test target: every `[PRIMARY PATH]` flow gets a Maestro YAML (reference `80-mobile.md` § Testing).

### 2E. Ticket Breakdown (my-workflow/06)

When Traycer creates full ticket specs and agent execution plans for a mobile epic:

#### Per-Ticket Injection Rules

For every ticket, check which dimensions apply and inject into Acceptance Criteria and Context Files:

| If ticket touches... | Inject |
|---|---|
| Supabase schema | RLS on every table before client queries; `supabase gen types` committed; reference `80-mobile.md` § Backend |
| Auth / signup | Supabase Auth + `expo-secure-store`; Sign in with Apple if social login exists; activation event instrumented |
| Any API endpoint | Versioned endpoint; backward-compat with N-1; correlation IDs; rate limiting |
| Monetization / paywall | RevenueCat SDK; server-side entitlement check (not client-trusted); paywall remote-configurable; reference `80-mobile.md` § Monetization |
| Push notifications | Permission priming before OS prompt; deep link payload; token stored in Supabase; reference `80-mobile.md` § Push |
| UI screen / component | React Native primitives (no DOM); Ocoron design system via unistyles; 44pt/48dp touch targets; accessibility labels; reference `80-mobile.md` § Styling + Accessibility |
| List / scrolling | FlatList or FlashList (no ScrollView+map); stable keyExtractor; reference `80-mobile.md` § Lists |
| Offline / caching | MMKV for read cache; sync indicator in UI; graceful offline UX |
| Onboarding flow | First-session value; activation event tracked; D1 retention target in AC |
| Analytics event | Funnel stage tag; attribution source captured; Sentry for crashes |
| Permissions | Just-in-time with priming; privacy labels declared; minimal permissions |
| Compliance | Privacy Manifest entry; ATT before tracking; account deletion reachable from Settings; reference `80-mobile.md` § Compliance |
| Distribution / build | EAS profile used; OTA channel configured; CI/CD trigger defined |
| Email / push / notification template | MJML + Jinja2 pipeline (backend email); push: FCM localized + deep-linked + PII-free; reference `86-email-templates.md` |

#### Agent Context Files

Every mobile ticket's Context Files section must include (in addition to category-specific rule packs):

```text
.windsurf/rules/80-mobile.md — mobile implementation patterns (architecture, styling, nav, monetization, compliance, i18n)
```

For backend tickets within a mobile project, also include:

```text
.windsurf/rules/15-api-contracts.md — API endpoint patterns
.windsurf/rules/58-resilience.md   — timeout/retry/circuit-breaker
.windsurf/rules/86-email-templates.md — email/push/notification templates (if ticket creates or edits templates)
```

#### Plan Directives for Coding Agents

When Traycer creates the execution plan (the plan the coding agent follows), embed these constraints:

1. **No web DOM elements.** `<View>`, `<Text>`, `<Pressable>`, `<Image>` only. No `<div>`, `<span>`, `<p>`, `<img>`.
2. **Every table has RLS enabled.** No Supabase table is queryable from the client without RLS. No exceptions.
3. **Every token in secure storage.** JWTs in `expo-secure-store`, never AsyncStorage or MMKV.
4. **Every paywalled feature checks entitlements.** RevenueCat server-side verification, not client-trusted state.
5. **Every permission is just-in-time.** No permission requests at app launch. Prime, then prompt.
6. **Every user-facing string is in locale files.** No hardcoded text. `en.json` + `tr.json` minimum. RTL-ready layouts.
7. **Every external call has resilience.** Timeout + retry + graceful offline fallback. Reference `.windsurf/rules/58-resilience.md`.
8. **Every screen meets touch targets.** 44pt (iOS) / 48dp (Android) minimum. `accessibilityLabel` on icon-only controls.
9. **Every PRIMARY PATH has a Maestro flow.** E2E test YAML in `.maestro/` directory.
10. **Backend supports old clients.** API versioned, N-1 backward-compat. Forced upgrade only for breaking changes.
