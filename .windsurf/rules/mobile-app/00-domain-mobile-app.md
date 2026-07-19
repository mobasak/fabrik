---
activation: manual
description: Mobile domain — PLANNING layer. The 17 vision-intake dimensions, the 3 forks (billing/distribution/platform-dependency), the attribution stack, and the epic-decomposition directives. Business formation, not code discipline — the sibling packs (80/81/89) own every code-time fact.
trigger: manual
---
<!-- ⚠️ NOT glob-activated ON PURPOSE. It previously globbed `**/*.tsx`, which fires on EVERY React file in
     the fleet — a saas-skeleton web dev editing a component was getting 264 lines of App Store / IAP / ATT
     questions injected. Its questions ("who is the ICP?", "what is the kill criteria?") belong at VISION
     INTAKE, not to an agent mid-edit. Real consumers load it BY PATH: docs/traycer/mega-epic-breakdown/
     00-trigger-*.md and 02-epic-decomposition-*.md. Do not re-add a glob. -->
<!-- ⚠️ THE ONE RULE: this file FORCES A DECISION; it NEVER states an implementation. No value (store-fee
     percentages, SDK names, API config) may be copied in from 80/81/89 — a second copy drifts, and that is
     exactly why docs/traycer/**/domain-modules/ was deleted 2026-07-13. Cite the pack; never restate it. -->

<!-- CONSUMER: the mega-epic planner (vision intake + epic decomposition) and any agent scoping mobile work.
     GOAL: decide the irreversible, business-shaping things BEFORE epics exist. This pack is deliberately
           NOT code discipline — 80-mobile.md, 81-mobile-billing.md and 89-mobile-launch-checklist.md own that.
     PROVENANCE: promoted from docs/traycer/mega-epic-breakdown/domain-modules/mobile-app.md (2026-07-13).
           80-mobile.md:18/:94/:356, 81-mobile-billing.md:293 and 89-mobile-launch-checklist.md:237 have
           referenced this file by name since before it existed; this promotion resolves those 5 dangling refs.
     ⚠️ SINGLE SOURCE OF TRUTH: every code-time fact (framework, router, auth, billing SDK, push, testing)
           lives in 80/81/89. Cite them; never restate them here — a second copy is how the old domain-module
           inverted its build-tool default and shipped a false EU fee number. -->

# Mobile Domain — Planning Layer (vision intake + epic decomposition)

## Operating Lens (solo + AI fleet)

- **Build cost is cheap** — agents implement. One codebase only; never maintain two native apps.
- **Your time is the scarce resource** — every default optimizes **set-and-forget ops**, never quality.
- **Pro-grade is non-negotiable** — crash-free, fast cold start, store-compliant from v1.

## Mobile is not web — the 3 forks (do NOT inherit SaaS defaults here)

1. **Billing is forced IAP** — Apple/Google mandate StoreKit/Play Billing for in-app digital goods, and the store takes a cut off the top. **Paddle does NOT apply in-app** — only to physical goods/services consumed *outside* the app. (Fee percentages, Small Business Program enrolment and the EU rules are owned by **`81-mobile-billing.md` § Store Fee Enrollment** — read them there; they change, and a copy here would rot.)
2. **The app ships outside Fabrik** — the binary goes through EAS to stores, **not the VPS deploy pipeline**. Only the **backend** (python-api + postgres-main) follows the 4-stage VPS lifecycle. State this explicitly in the Vision Summary.
3. **Platform dependency is existential** — Apple/Google can reject, delay, or remove you. This is the #1 mobile risk, not a footnote.

## Completeness Test (apply per dimension)

A dimension belongs at intake **only if** wrong = **irreversible** or **kills before build**. Else it's downstream. Resolve each or log as Open Question. **No "TBD" survives confirmation.**

---

## Part 1 — Mega-Epic Decomposition Guidance

*Consumed by `02-epic-decomposition-command` (and `00-trigger-workflow-command` Step E4 in EXISTING mode) to drive mobile-specific epic patterns.*

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

- **Framework: React Native + Expo + EAS** (decided — do not reopen). One codebase, managed build/submit/OTA, TypeScript synergy with web stack, Ocoron design system mapping via unistyles, MCP verification loop. **Never dual-native. Never Flutter** (evaluated and rejected — RN+Expo is the Fabrik standard; switching would discard the entire 80-mobile ruleset, i18n pipeline, and TS ecosystem).
- **Backend:** **python-api (FastAPI)** — owns auth (`fabrik-lib/fastapi-user-auth`), business logic, and all client data access; **postgres-main** (shared VPS PostgreSQL 16, `postgres-main:5432`) for data; **`fabrik-lib/storage`** (Backblaze B2 backend) for object storage; **redis-main** pubsub + WS/SSE for realtime only if the product needs it (currently unused fleet-wide). The app talks to this FastAPI backend over HTTPS — never a hosted-BaaS SDK (`supabase-js` / `supabase-py`) directly.
- **Auth: `fabrik-lib/fastapi-user-auth` (Pattern A — decided, do not reopen).** The FastAPI backend issues its own JWTs (Argon2, refresh-token rotation, `jti` denylist, tenant-isolation RLS on `postgres-main` with the `auth` schema owned natively — `auth.uid()` over the `request.jwt.claims` GUC). Pattern A is THE default per `core/35-security-auth.md`; Supabase Auth is legacy/migration-only (see `agents-fabrik.md § Supabase`). Firebase Auth was evaluated and rejected: self-hosting keeps identity + data + RLS on one platform, avoids dual-UID systems. The app calls the backend's auth endpoints — never `supabase-js` / `getClaims()` / a hosted JWKS. **Sign in with Apple is mandatory** if you offer any other social login on iOS; tokens in `expo-secure-store`.
- **Offline/sync:** online-first + offline-read cache by default; full offline-write+sync only if the use case demands it (large maintenance lift).
- **Attribution plumbing (build-time mandate):** MMP SDK (Tenjin — 2k conv/mo free, flat $200 after) + Universal Links (iOS AASA) / App Links (Android assetlinks.json) wired as **Expo config plugins at prebuild, tested via EAS dev build — not Expo Go.** Deep-link routing via ChottuLink (25k MAU free). **Firebase Dynamic Links is dead (Aug 2025) — never reference it.** Retrofit = full binary re-review + permanently lost early-cohort attribution.

**Why now:** framework, backend, auth, sync model, and attribution plumbing are schema/SDK-level — retrofit = rewrite.

#### 5. Monetization & Store Billing

Reference `.windsurf/rules/mobile-app/81-mobile-billing.md` for full billing discipline. At intake, force:

**Force:** IAP product types (consumable / subscription / one-time), tiers, trial, entitlement model.

**Default:** **RevenueCat over raw StoreKit/Play Billing** — set-and-forget receipts, entitlements, cross-platform.

**EU external link-out — decide once, at intake: DON'T.** Under the DMA you *may* bill outside the store, but for a Small-Business-Program member below the $1M threshold the alternative terms come out to **the same effective rate as standard IAP — no cost advantage, only added complexity**. External web billing only pays off in unregulated regions at volume. ⚠️ The rates, thresholds and enrolment mechanics are owned by **`81-mobile-billing.md` § Store Fee Enrollment** — go read the numbers there, never from this file.

**Turkey constraint:** Google Play Billing is mandatory for digital goods — Turkey is excluded from UCB and EOP. Paddle/iyzico/Stripe web-steer = instant rejection. See `mobile-app/81-mobile-billing.md`. Ad revenue is taxed separately from subscription revenue under Teknokent — maintain separate ledgers.

**Why now:** in-app billing is the forced path; entitlement gating must exist before paywalled features.

#### 6. Push & Re-engagement

Reference `.windsurf/rules/mobile-app/80-mobile.md` § Push Notifications. At intake, force:

**Force:** push provider + permission strategy + the re-engagement triggers (mobile's retention engine, replacing email-first).

**Default:** FCM via Expo Push or OneSignal; **prime before the OS permission prompt**; trigger on activation/expansion/win-back.

**Why now:** push opt-in is a one-shot ask; lose it at install and re-engagement is gone.

#### 7. Permissions & Device Capabilities

**Force:** which capabilities (camera, location, contacts, biometrics, notifications) — minimize.

**Default:** request **just-in-time with priming**, never at launch; declare privacy labels honestly.

**Why now:** each permission = friction + review scrutiny; over-asking tanks install-to-activation.

#### 8. Distribution, Updates & API Versioning

Reference `.windsurf/rules/mobile-app/80-mobile.md` § Build & Dev Workflow. At intake, force:

**Force:** release cadence, staged rollout, **forced-upgrade gate**, OTA strategy, backend backward-compat.

**Default:** store release + **OTA (EAS Update / Shorebird) for JS/Dart-only fixes**; versioned API; backend supports old clients; forced upgrade only for breaking changes.

**Staged rollout (mandatory, per `mobile-app/89-mobile-launch-checklist.md:160-161`):** Android **10% → 50% → 100%** with 24h crash/ANR observation between stages; iOS **Phased Release** (Apple's built-in 7-day curve: 1% → 2% → 5% → 10% → 20% → 50% → 100%). Brief consequence for Epic decomposition: a kill-switch / feature-flag path and crash/ANR dashboards must exist *before* stage 1, not after — bake this into the Epic that ships the first release build.

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

Reference `.windsurf/rules/mobile-app/80-mobile.md` § Lists, Styling, Accessibility, Platform-Aware. At intake, force:

**Force:** cold-start target, app size budget, crash-free-rate target, offline UX, accessibility, native feel.

**Default:** crash-free >=99.5%, lean bundle, no jank; accessibility from v1.

**Why now:** store ranking weights crashes/ANR; janky apps get uninstalled and 1-starred — hard to recover.

#### 12. Analytics, Attribution & Crash/Stability

**Force:** funnel events, install attribution, crash/ANR reporting.

**Default:** product analytics + **Sentry/Crashlytics** (pro-grade).

**Attribution stack — the asymmetry is the decision:** **Android Install Referrer is deterministic; iOS is aggregate-only.** Build the model around that gap, not around a specific SDK. On iOS, **SKAdNetwork remains the working default** — Apple has announced **no deprecation timeline**, and AdAttributionKit, though the stated long-term direction, still has negligible adoption as of 2026 ([Kochava, 2026](https://www.kochava.com/blog/your-ios-attribution-strategy-2026-reality-check/); [Adjust](https://www.adjust.com/blog/adattributionkit/)). Adopt AAK when you ship into an EU alternative marketplace, where it is required — otherwise monitor it, don't chase it. The launch-time config is owned by **`89-mobile-launch-checklist.md` § Privacy Compliance**. An MMP (Tenjin) earns its keep only for paid-UA attribution and deep-link routing — **partner** attribution comes from offer codes (§9), never the MMP. Never reference Firebase Dynamic Links (dead Aug 2025).

> ⚠️ Corrected 2026-07-14. This file previously asserted "AdAttributionKit **replaces** SKAdNetwork." That was false — inherited unverified from the retired `domain-modules/mobile-app.md`, and it contradicted `89:200`, which was right all along. Live-verify any store/platform API claim before writing it here; they move, and a synced pack propagates the error to every project.

**Why now:** post-ATT attribution is hard and must be wired before spend; crashes you don't see, you can't fix.

#### 13. Legal, Compliance & Store Policy

Reference `.windsurf/rules/mobile-app/80-mobile.md` § Compliance (Worldwide). At intake, force:

**Force (the intake decision):** what data you collect and what you will publicly claim about it — that choice is irreversible once shipped, and it drives the store forms. The forms and mechanics themselves (privacy nutrition labels, ATT prompt, Play Data Safety, in-app account deletion) are **owned by `89-mobile-launch-checklist.md` § Privacy Compliance + § Account Deletion & Restore** and are **store-blocking** — ship them from there.

**Default:** the FastAPI backend owns data terms + the account-delete flow (hard-deletes rows on `postgres-main` and purges `fabrik-lib/storage` blobs); account-delete built in v1; honest data disclosures.

**Why now:** missing account-deletion or false privacy labels = guaranteed rejection.

#### 14. Finance & Unit Economics

**Force:** **store-cut-adjusted** LTV (the store takes its cut off the top — model net, never gross) · CAC target · payback <12mo · LTV:CAC ≥3 · backend COGS. **Partner economics:** store cut **+** partner commission compound, and what survives must still absorb infra, LLM API costs and Turkey's DST — model the stacked take-rate *before* committing to any paid partner channel, because a channel that looks profitable on gross revenue can be loss-making on net. Current rates: **`81-mobile-billing.md` § Store Fee Enrollment**.

**Default:** price against the **worst-case** store cut (assume you are not SBP-eligible until you have enrolled and confirmed it), and know the paid-UA payback before you spend a lira.

**Why now:** the store cut materially changes the LTV math vs your SaaS/Paddle defaults.

#### 15. Risk Register

**Force:** top 5 risks + mitigation — **platform deplatform/rejection (existential)**, review-delay-blocks-hotfix, IAP dependency, single-channel, key-person.

**Default:** OTA to mitigate review delay; web fallback for critical flows; named owner-action per risk.

**Why now:** Apple/Google control your distribution — plan for rejection, not around it.

#### 16. Ops & Solo-Dev Load

**Force:** what's automated (build, submit, OTA, entitlements, alerting) vs needs you; version-support matrix; review-response load.

**Default:** EAS + RevenueCat + self-hosted FastAPI backend (`fastapi-user-auth` + postgres-main) + Sentry = near-zero recurring ops; set-and-forget bias.

**Why now:** two store accounts + version sprawl scales to burnout if not automated from day 1.

#### 17. Sequencing & Kill Criteria

**Force:** internal test, closed beta, soft-launch (one geo), public; explicit kill/pivot criteria **with a date**.

**Default:** validate retention in soft-launch before paid scale; ship the wedge, then expand.

**Why now:** the structural defense against the Forex pattern — prove retention before spending on growth.

#### Vision Summary Gate

Vision Summary may confirm only when **all 17 are resolved or logged as Open Questions**. Map onward:

- Decisions to `Technology Decisions` + `Value Streams`.
- Unresolved to `Open Questions` (block confirmation).
- **Fabrik-fit:** backend = `python-api` + postgres-main (auth via `fabrik-lib/fastapi-user-auth`) follows the 4-stage VPS lifecycle. App binary goes through EAS to stores, **outside the VPS deploy pipeline** — state this in the summary. App + backend = multi-epic, route to `02-epic-decomposition-command`.

### 1B. Epic Decomposition Directives

When decomposing a mobile app vision into epics, these dimensions shape boundaries:

#### Mandatory Epic Coverage

Every mobile mega-epic MUST have dedicated coverage for:

| Dimension | Epic boundary rule |
|---|---|
| §4 Backend + Auth + Data model | Foundation epic (Epic 1) — postgres-main schema, RLS, `fabrik-lib/fastapi-user-auth` (incl. Sign in with Apple), API scaffold. Everything else depends on this. |
| §4 App skeleton + Navigation | Own epic or first part of foundation — framework setup, navigation structure, design system, platform config. |
| §5 Monetization (RevenueCat + IAP) | Own epic or explicitly assigned. Entitlement gating must exist before paywalled features. |
| §6 Push + Re-engagement | Belongs in the epic that owns notification triggers, not deferred to "polish." |
| §8 Distribution + OTA | Belongs in the epic that sets up EAS Build/Submit/Update pipeline. Usually foundation or integration epic. |
| §10 Onboarding | Belongs in the epic that owns the first-session experience. Never deferred past v1. |
| §13 Compliance | Account deletion, privacy labels, ATT prompt — belongs in foundation epic. Store-blocking if missing. |

#### Two-Lane Split

Mobile projects naturally split into two parallel lanes after the foundation epic:

- **Backend lane** (python-api + postgres-main) — deploys to VPS via `fabrik apply` (SSH + Docker Compose). Follows Fabrik 4-stage lifecycle.
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
