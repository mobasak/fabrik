---
activation: manual
description: Mobile domain — PLANNING layer. The 17 vision-intake dimensions, the 3 forks (billing/distribution/platform-dependency), the attribution stack, and the epic-decomposition directives. Business formation, not code discipline — the sibling packs (80/81/89) own every code-time fact.
trigger: manual
currency_pass: 2026-09-30
---
<!-- ⚠️ NOT glob-activated ON PURPOSE: a `**/*.tsx` glob fired on every React file in the fleet. Its questions belong at
     VISION INTAKE, not mid-edit. Consumers load it BY PATH: /fabrik-vision (intake), /fabrik-epics (decomposition —
     it walks `#### Mandatory Epic Coverage` by name; tests/test_domain_pack_epic_headings.py pins it) and
     /fabrik-release (§8). Do not re-add a glob. -->
<!-- ⚠️ THE ONE RULE: this file FORCES A DECISION; it NEVER states an implementation. No value (store-fee percentages,
     vendor prices, rollout curves, SDK config) may be copied in from 80/81/89 or a vendor page — a second copy
     drifts. Cite the pack; never restate it. -->

# Mobile Domain — Planning Layer (vision intake + epic decomposition)

## Operating Lens (solo + AI fleet)

- **Build cost is cheap** — agents implement. One codebase only; never maintain two native apps.
- **Your time is the scarce resource** — every default optimizes **set-and-forget ops**, never quality.
- **Pro-grade is non-negotiable** — crash-free, fast cold start, store-compliant from v1.

## Mobile is not web — the 3 forks (do NOT inherit SaaS defaults here)

1. **Billing is forced IAP** — Apple/Google mandate StoreKit/Play Billing for in-app digital goods in most markets, and the store takes a cut off the top. **Paddle does NOT apply in-app** — only to physical goods/services consumed *outside* the app. (Fee percentages, Small Business Program enrolment and the EU rules are owned by **`81-mobile-billing.md` § Store Fee Enrollment** — read them there; they change, and a copy here would rot.)
2. **The app ships outside Fabrik** — the binary goes through EAS to stores, **not the VPS deploy pipeline**. Only the **backend** (the scaffold's `server/`) follows the 4-stage VPS lifecycle. State this explicitly in the Vision Summary.
3. **Platform dependency is existential** — Apple/Google can reject, delay, or remove you. This is the #1 mobile risk, not a footnote.

## Completeness Test (apply per dimension)

A dimension belongs at intake **only if** wrong = **irreversible** or **kills before build**. Else it's downstream. Resolve each or log as Open Question. **No "TBD" survives confirmation.**

---

## Part 1 — Mega-Epic Decomposition Guidance

*Consumed by `/fabrik-vision` at intake and `/fabrik-epics` at decomposition to drive mobile-specific epic patterns.*

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

Reference `.windsurf/rules/mobile-app/80-mobile.md` for implementation detail. At intake, force:

- **Framework: React Native + Expo + EAS** (decided — do not reopen). One codebase, managed build/submit/OTA, TypeScript synergy with web stack, design-system tokens through the scaffold's styling engine (`80-mobile.md` § Styling), MCP verification loop. **Never dual-native. Never Flutter** (evaluated and rejected — switching would discard the entire 80-mobile ruleset, i18n pipeline, and TS ecosystem).
- **Backend: the scaffold's companion FastAPI service in the same repo (`server/`)**, deployed by `fabrik apply` like any Pattern-A service. It ships minimal — `GET /health` and `GET /app-config` (force-update, kill-switch, feature toggles via the vendored `fabrik-lib/mobile-config`) with **no database and no auth**. Decide at intake whether v1 needs accounts or stored data; if yes, flip both `needs_database` and `has_bearer_api` (the scaffold's `defaults.yaml` says how) and add `fabrik-lib/fastapi-user-auth` + `postgres-main`. Object storage is `fabrik-lib/storage`; realtime (redis-main pubsub + WS/SSE) only if the product needs it. The app talks to this backend over HTTPS — never a hosted-BaaS SDK (`supabase-js` / `supabase-py`) directly.
- **Auth (when v1 has accounts): Pattern A — the FastAPI backend is the sole identity provider, via `fabrik-lib/fastapi-user-auth`, passwordless by default, native RLS mode** (decided, do not reopen; `core/35-security-auth.md` § Pattern A and § Passwordless — they own the rule, the module's README owns the mechanics). Firebase Auth was evaluated and rejected: self-hosting keeps identity, data and row-level security on one platform. **A social login is a decision, not a default:** it adds `fabrik-lib/oauth-login` and App Store Guideline 4.8 — iOS must then also offer a login option meeting 4.8's privacy criteria, which Sign in with Apple (an `oauth-login` provider) satisfies. Tokens in `expo-secure-store`.
- **App identity:** bundle ID, Android package name and the publishing entity cannot change after the first store upload — decide them here; `89-mobile-launch-checklist.md` § App Identity owns the setup.
- **Offline/sync:** online-first + offline-read cache by default; full offline-write+sync only if the use case demands it (large maintenance lift).
- **Link plumbing (build-time mandate):** Universal Links (iOS AASA) / App Links (Android `assetlinks.json`) wired as **Expo config plugins at prebuild, tested via an EAS dev build — not Expo Go**, plus deferred deep-link routing (default: ChottuLink). **Firebase Dynamic Links shut down on 25 August 2025 — never reference it.** Retrofit = a new store binary and permanently lost early-cohort routing.
- **Measurement SDK (decide, don't default):** an MMP SDK (default: Tenjin) earns its keep only for paid-UA attribution (§9). Decide at intake whether paid UA starts within the first release cycle: **yes → ship the SDK in v1**, because a native SDK needs a store build and cannot arrive by OTA; **no → leave it out** and add it with the first paid-UA release.

**Why now:** framework, backend, auth, sync model, and link plumbing are schema/SDK-level — retrofit = rewrite.

#### 5. Monetization & Store Billing

Reference `.windsurf/rules/mobile-app/81-mobile-billing.md` for full billing discipline. At intake, force:

**Force:** IAP product types (consumable / subscription / one-time), tiers, trial, entitlement model.

**Default:** **RevenueCat over raw StoreKit/Play Billing** — set-and-forget receipts, entitlements, cross-platform.

**EU billing outside the store — decide once, at intake, from current numbers:** store billing only · link-out to web checkout · alternative in-app payment provider. Under the DMA both stores allow all three in the EU/EEA, and their terms change often (Apple's change again on 1 October 2026). Read the current rates in **`81-mobile-billing.md` § Store Fee Enrollment** and the stores' own EU pages, then weigh the fee difference against the cost of a second billing path (web checkout, tax, entitlement sync with RevenueCat). The default for a v1 is **store billing only**; revisit when EU revenue makes the difference worth a second path.

**Turkey constraint:** store billing is mandatory for digital goods on both stores; a Paddle/iyzico/Stripe web-steer is rejected. Why, and the Teknokent separate-ledger rule for ad versus subscription revenue: `81-mobile-billing.md` § Turkey.

**Why now:** in-app billing is the forced path; entitlement gating must exist before paywalled features.

#### 6. Push & Re-engagement

Reference `.windsurf/rules/mobile-app/80-mobile.md` § Push Notifications. At intake, force:

**Force:** push provider + permission strategy + the re-engagement triggers (mobile's retention engine, replacing email-first).

**Default:** **Expo Push** (FCM and APNs underneath) with the backend side vendored from `fabrik-lib/expo-push` (token registry, receipts, dead-token pruning); **prime before the OS permission prompt**; trigger on activation/expansion/win-back.

**Why now:** push opt-in is a one-shot ask; lose it at install and re-engagement is gone.

#### 7. Permissions & Device Capabilities

**Force:** which capabilities (camera, location, contacts, biometrics, notifications) — minimize.

**Default:** request **just-in-time with priming**, never at launch; declare privacy labels honestly.

**Why now:** each permission = friction + review scrutiny; over-asking tanks install-to-activation.

#### 8. Distribution, Updates & API Versioning

Reference `.windsurf/rules/mobile-app/80-mobile.md` § Build & Dev Workflow and `89-mobile-launch-checklist.md` § Staged Rollout + § OTA Updates & Forced Upgrade. At intake, force:

**Force:** release cadence, staged rollout, **forced-upgrade gate**, OTA strategy, backend backward-compat.

**Default:** store release + **OTA via EAS Update for JavaScript and asset fixes only** — any native change is a store build; versioned API; backend supports old clients; forced upgrade only for breaking changes, through the scaffold's `/app-config` gate (`fabrik-lib/mobile-config`), which also carries the kill-switch.

**Staged rollout (mandatory):** both stores, with the schedule in `89-mobile-launch-checklist.md` § Staged Rollout. Consequence for epic decomposition: the kill-switch / feature-flag path and crash/ANR dashboards must exist *before* stage 1 — bake them into the epic that ships the first release build.

**Why now:** old app versions live on phones forever — you can't deprecate an endpoint v1.0 still calls; review delays block hotfixes unless OTA exists.

#### 9. ASO & Acquisition

**Force:** ONE primary channel + ASO assets (title, keywords, screenshots, review strategy).

**Default:** **ASO + content** (compounding, low-cost); ratings drive ranking, prompt for review at the activation moment. **Short-video** (TikTok / YouTube Shorts / Reels) — the primary B2C app-discovery channel; **GEO/AI-answer optimization** ("best app for X" queries — mandatory pairing with ASO); **web-to-app** (SEO/GEO landing page that drives installs via deferred deep link — ties to §12); Product Hunt launch.

**Partner / creator / referral channels:**

- **Partner/creator payouts — deterministic codes, never matching.** iOS: App Store offer codes, generated through the App Store Connect API. Android: Play promo codes are Console-only (no API) and limited to trials and one-time items, so attribute Android partners with a partner code the app captures and stores as a RevenueCat custom attribute. Both bypass ATT and need no MMP. Never pay partners on fingerprint or click matching — Apple prohibits fingerprinting, and probabilistic matching loses accuracy within hours, so you would underpay your best creators.
- **Referral (user-to-user)** — **RevenueCat custom attributes + webhooks (serverless, set-and-forget).** No separate referral platform needed.
- **Paid UA** — MMP (§4) + deep-link routing. This is the *only* place the MMP belongs. Platforms: Apple Search Ads, Meta, TikTok. Retargeting via MMP. Post-PMF only.
- **CPI networks** — **avoid.** Install fraud is endemic there and needs enterprise fraud tooling you can't justify solo.

**Why now:** mobile CAC is paid-heavy — without an organic engine you burn cash; "no channel" kills the app.

#### 10. Onboarding, Retention & Support

**Force:** first-session value, permission-priming flow, retention triggers (D1/D7/D30), low-touch support.

**Default:** value before signup where possible; automate onboarding; in-app support + docs.

**Why now:** mobile retention curves are brutal; D1 is decided by the first 60 seconds.

#### 11. Performance & UX Quality (pro-grade)

Reference `.windsurf/rules/mobile-app/80-mobile.md` § Lists, Styling, Accessibility, Platform-Aware. At intake, force:

**Force:** cold-start target, app size budget, crash-free-rate target, offline UX, accessibility, native feel.

**Default:** the crash-free gate in `89-mobile-launch-checklist.md` § Beta Metrics Gates, lean bundle, no jank; accessibility from v1.

**Why now:** store ranking weights crashes/ANR; janky apps get uninstalled and 1-starred — hard to recover.

#### 12. Analytics, Attribution & Crash/Stability

**Force:** funnel events, install attribution, crash/ANR reporting.

**Default:** product analytics behind the scaffold's consent gate, on a region you can disclose (`80-mobile.md` § Compliance), + **Sentry** for crashes — the scaffold ships both; Crashlytics would add the Firebase dependency §4 rejects.

**Attribution stack — the asymmetry is the decision:** **Android Install Referrer is deterministic; iOS is aggregate-only.** Build the model around that gap, not around a specific SDK. On iOS, **SKAdNetwork remains the working default** — Apple has announced no deprecation timeline, and AdAttributionKit runs beside it with uneven network adoption. AdAttributionKit is the only Apple attribution that covers installs from EU alternative marketplaces and web distribution, so adopt it if you ship there; otherwise monitor it, don't chase it ([Apple — apps in the EU](https://developer.apple.com/support/apps-in-the-eu/)). The launch-time config is owned by **`89-mobile-launch-checklist.md` § Privacy Compliance**. **Partner** attribution comes from codes (§9), never the MMP. Never reference Firebase Dynamic Links (shut down 25 August 2025).

**Why now:** post-ATT attribution is hard and must be wired before spend; crashes you don't see, you can't fix.

#### 13. Legal, Compliance & Store Policy

Reference `.windsurf/rules/mobile-app/80-mobile.md` § Compliance (Worldwide). At intake, force:

**Force (the intake decision):** what data you collect and what you will publicly claim about it — that choice is irreversible once shipped, and it drives the store forms. The forms and mechanics themselves (privacy nutrition labels, ATT prompt, Play Data Safety, in-app account deletion) are **owned by `89-mobile-launch-checklist.md` § Privacy Compliance + § Account Deletion & Restore** and are **store-blocking** — ship them from there.

**Default:** the FastAPI backend owns data terms and the account-delete flow, built in v1 whenever the app has accounts; honest data disclosures.

**Why now:** missing account-deletion or false privacy labels = guaranteed rejection.

#### 14. Finance & Unit Economics

**Force:** **store-cut-adjusted** LTV (the store takes its cut off the top — model net, never gross) · CAC target · payback <12mo · LTV:CAC ≥3 · backend COGS. **Partner economics:** store cut **+** partner commission compound, and what survives must still absorb infra, LLM API costs and Turkey's DST — model the stacked take-rate *before* committing to any paid partner channel, because a channel that looks profitable on gross revenue can be loss-making on net. Current rates: **`81-mobile-billing.md` § Store Fee Enrollment**.

**Default:** price against the **worst-case** store cut (assume you are not SBP-eligible until you have enrolled and confirmed it), and know the paid-UA payback before you spend a lira.

**Why now:** the store cut materially changes the LTV math vs your SaaS/Paddle defaults.

#### 15. Risk Register

**Force:** top 5 risks + mitigation — **platform deplatform/rejection (existential)**, review-delay-blocks-hotfix, IAP dependency, single-channel, key-person.

**Default:** OTA + the kill-switch to mitigate review delay; web fallback for critical flows; named owner-action per risk.

**Why now:** Apple/Google control your distribution — plan for rejection, not around it.

#### 16. Ops & Solo-Dev Load

**Force:** what's automated (build, submit, OTA, entitlements, alerting) vs needs you; version-support matrix; review-response load.

**Default:** EAS + RevenueCat + the self-hosted `server/` backend (with `fastapi-user-auth` + `postgres-main` once it has accounts) + Sentry = near-zero recurring ops; set-and-forget bias.

**Why now:** two store accounts + version sprawl scales to burnout if not automated from day 1.

#### 17. Sequencing & Kill Criteria

**Force:** internal test, closed beta, soft-launch (one geo), public; explicit kill/pivot criteria **with a date**.

**Default:** validate retention in soft-launch before paid scale; ship the wedge, then expand.

**Why now:** spending on growth before retention is proven buys users who leave — prove retention first.

#### Vision Summary Gate

Vision Summary may confirm only when **all 17 are resolved or logged as Open Questions**. Map onward:

- Decisions to `Technology Decisions` + `Value Streams`.
- Unresolved to `Open Questions` (block confirmation).
- **Fabrik-fit:** the backend is the repo's own `server/` (FastAPI; add `fabrik-lib/fastapi-user-auth` + `postgres-main` when v1 has accounts) and follows the 4-stage VPS lifecycle. The app binary goes through EAS to stores, **outside the VPS deploy pipeline** — state this in the summary. App + backend = multi-epic, route to `/fabrik-epics`.

### 1B. Epic Decomposition Directives

When decomposing a mobile app vision into epics, these dimensions shape boundaries:

#### Mandatory Epic Coverage

Every mobile mega-epic MUST have dedicated coverage for:

| Dimension | Epic boundary rule |
|---|---|
| §4 Backend + Auth + Data model | Foundation epic (Epic 1) — the `server/` API contract and, when v1 has accounts, the postgres-main schema, row-level security and `fabrik-lib/fastapi-user-auth` (plus `oauth-login` and a 4.8-compliant option such as Sign in with Apple when a social login is chosen). Everything else depends on this. |
| §4 App skeleton + Navigation | Own epic or first part of foundation — framework setup, navigation structure, design system, platform config, link plumbing. |
| §5 Monetization (RevenueCat + IAP) | Own epic or explicitly assigned. Entitlement gating must exist before paywalled features. |
| §6 Push + Re-engagement | Belongs in the epic that owns notification triggers, not deferred to "polish." |
| §8 Distribution + OTA | Belongs in the epic that sets up EAS Build/Submit/Update and the `/app-config` force-update + kill-switch. Usually foundation or integration epic. |
| §10 Onboarding | Belongs in the epic that owns the first-session experience. Never deferred past v1. |
| §13 Compliance | Account deletion, privacy labels, ATT prompt — belongs in foundation epic. Store-blocking if missing. |

#### Two-Lane Split

Mobile projects naturally split into two parallel lanes after the foundation epic:

- **Backend lane** (the repo's `server/`, plus postgres-main when it has data) — deploys to the VPS via `fabrik apply` (SSH + Docker Compose). Follows the Fabrik 4-stage lifecycle.
- **Client lane** (React Native app) — builds via EAS, submits to stores. Does NOT deploy to the VPS.

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
- Do NOT create a "testing epic" — testing is per-ticket (Maestro flows, reference `mobile-app/80-mobile.md` § Testing).
- Do NOT skip compliance in foundation — account deletion + privacy labels = store-blocking.

#### Phase Mapping

- **Internal test:** EAS development build on team devices.
- **Closed beta:** TestFlight (iOS) + Play Internal Testing (Android).
- **Soft-launch:** one small geo, measure D1/D7/D30 retention before global.
- **Public launch:** full store availability after retention validated.

---
