---
activation: glob
globs: ["**/metro.config.*", "**/react-native.config.*", "**/app.json", "**/app.config.*", "**/eas.json"]
description: React Native mobile discipline — architecture, backend, navigation, performance, monetization, compliance, and i18n for worldwide shipping
trigger: glob
currency_pass: 2026-09-30
---
<!-- CONSUMER: Coding agents building React Native mobile apps
     GOAL: RN/Expo architecture, navigation, state, styling, accessibility, compliance, i18n
     PLANNING USAGE: /fabrik-flows and /fabrik-epics derive project screens from the inventory below.
     AGENT USAGE: Follow for client-side mobile code; the emitted mobile-app scaffold is the reference. Backend rules from 10-python apply. -->

# Mobile Rules (React Native)

Apply when working on React Native / TypeScript mobile projects. Skip for web frontend, Python, Docker, or infrastructure files. For general TypeScript discipline, see `20-typescript.md`.

Worldwide-shipping baseline. Compliance floor is GDPR + EU AI Act; other markets are regional addenda. i18n is built in from day 1, not retrofitted.

**Two-faced scaffold:** the client (React Native app) builds via EAS and ships to stores. The backend (the repo's own `server/` FastAPI service — no database and no auth until you opt into `postgres-main` + `fabrik-lib/fastapi-user-auth`) deploys to VPS via `fabrik apply` — the same self-hosted Pattern-A stack as web (see `agents-fabrik.md § Supabase`; Supabase is retired as a default). This file covers the **client lane**. Backend rules: `10-python.md`, `30-ops.md`, `55-observability.md`. For planning-level decisions (architecture, monetization, distribution, attribution), see `00-domain-mobile-app.md`.

---

## Screen Inventory (minimum viable mobile app)

Every mobile app project must ship these screens. `/fabrik-flows` and `/fabrik-epics` derive the project-specific screens.

### Auth & Onboarding

| Screen | Route/Name | Purpose |
|---|---|---|
| **Splash** | App launch | Brand splash (`expo-splash-screen`), held only until auth state resolves → routes to onboarding or home. |
| **Onboarding wizard** | `Onboarding` | 3-5 swipeable value screens. Skippable. Shows before signup for value-before-signup pattern. |
| **Login** | `Login` | FastAPI auth service (`fabrik-lib/fastapi-user-auth`) — **PASSWORDLESS by default** (`35-security-auth.md` § Passwordless): one email field → OTP code entry, with the magic link landing via the Universal Links / App Links wiring § Deep linking already mandates. A password field is an ADDITIONAL affordance the project justifies, never the default. Social/OAuth handled server-side; client stores the app-issued JWT in `expo-secure-store`. Apple Guideline 4.8 applies only if the app offers a third-party/social login for the primary account: it must then also offer an equivalent login service that limits data to name and email, lets the user keep the email private, and collects no interactions for advertising without consent — add Sign in with Apple via the FastAPI auth service. ⚠️ The scaffold's `src/features/auth/components/login-form.tsx` is a **demo email+password form** with hard-coded English copy — replace it with the passwordless flow before the foundation epic closes, keeping only its `@tanstack/react-form` + Zod + keyboard-controller shape. |
| **Signup** | `Signup` | Registration. Redirects to verify-email screen. |
| **Verify email** | `VerifyEmail` | "Check your email" — resend button, change email link. Cannot proceed until verified. |
| **Forgot password** | `ForgotPassword` | Email input → triggers reset flow. |
| **Permission priming** | `PermissionPriming` | Explains WHY before OS prompt (push, camera, location). Just-in-time, not at launch. |

### Core App (tab navigator)

| Screen | Route/Name | Purpose |
|---|---|---|
| **Home / Dashboard** | `Home` | Primary tab. Active status, quick actions, recent items. |
| **[Core feature screens]** | Project-specific | Defined per epic during `/fabrik-flows`. 2-4 tabs typical. |
| **Profile / Settings** | `Settings` | Account info, locale, notifications, linked accounts, app version. |

### Billing & Subscription

| Screen | Route/Name | Purpose |
|---|---|---|
| **Paywall** | `Paywall` | Plan comparison, pricing, trial CTA. "Restore Purchases" button mandatory. Remote-configurable via RevenueCat. |
| **Subscription management** | `ManageSubscription` | Current plan, usage, links to store subscription settings. |

### Settings (nested under Settings tab)

| Screen | Route/Name | Purpose |
|---|---|---|
| **Edit profile** | `EditProfile` | Display name, avatar, email (change triggers verification). |
| **Notification preferences** | `NotificationPreferences` | Per event-type toggle (push on/off). |
| **Language** | `LanguageSettings` | Locale picker (en, tr, ar, + future languages). |
| **Privacy & data** | `PrivacyData` | Privacy policy link, data export, account deletion. |
| **About** | `About` | App version, licenses, support link. |

### System

| Screen | Route/Name | Purpose |
|---|---|---|
| **Offline fallback** | `Offline` | Shown when network unavailable. Cached data display + retry. |
| **Force update** | `ForceUpdate` | Shown when app version is below minimum. Links to store. |

**Rules:**
- Auth + onboarding screens ship in the foundation epic — launch-blocking.
- Paywall ships in the billing epic. "Restore Purchases" is store-mandatory.
- Core feature screens are project-specific — `/fabrik-flows` defines them.
- Every screen follows the design system 5 states (loading, empty, error, success, disabled).
- Navigation: **expo-router** file-based routing — `Stack` for hierarchical flows, `Tabs` for top-level (3-5 tabs).

---

## Architecture

- React Native with TypeScript on Expo is the mobile framework. React Native now runs **only** on the New Architecture (Fabric/JSI): the opt-out is gone and current Expo ignores `newArchEnabled` (the scaffold's `newArchEnabled: true` in `app.config.ts` is inert). Never set it `false`, and never generate code relying on the legacy asynchronous bridge. The SDK version is whatever the project's `package.json` pins (`expo`); move it with the Expo SDK upgrade guide and `npx expo install --fix`, never by hand-editing individual package versions.
- Web DOM elements (`<div>`, `<span>`, `<p>`, `<img>`, `<a>`) are **strictly forbidden**. Use React Native primitives: `<View>`, `<Text>`, `<Pressable>`, `<Image>`.
- Minimize direct modifications to `android/` and `ios/` directories. Prefer config plugins or autolinking where possible.
- If the project uses Expo Managed Workflow, never suggest `npx expo eject` or manual native file edits. All native configuration belongs in config plugins in `app.config.ts` (the scaffold's) or `app.json`.

---

## Navigation

- Use **`expo-router`** (file-based routing; the scaffold keeps screens under `src/app/`) for all navigation — Expo's recommended router and the `create-expo-app` default. **expo-router no longer depends on React Navigation**: app code imports navigation primitives from expo-router's own entry points, and importing `@react-navigation/*` in app code is a **Metro bundler error** (not an `expo-doctor` warning). Expo ships a codemod that rewrites old imports; `EXPO_ROUTER_DISABLE_RN_NAVIGATION_CHECK=1` only silences the check and risks two navigation copies in the bundle. Do NOT add `@react-navigation/*` packages.
- Use expo-router's `Stack` for hierarchical screen flows and `Tabs` for top-level sections (defined by the file layout in `src/app/`, e.g. `_layout.tsx`).
- Keep **typed routes** on (`experiments.typedRoutes: true` — Expo's current templates ship it enabled) for type-safe hrefs and route params — no hand-maintained route-name file.
- Deep linking is handled by expo-router's file-based routes. Use Universal Links (iOS AASA) and App Links (Android assetlinks.json) — wired as Expo config plugins at prebuild. Custom URL schemes are fallback only.
- Deep-link routing via ChottuLink (or equivalent) for attribution. See `00-domain-mobile-app.md` § 12. Analytics, Attribution & Crash/Stability for the full stack (ChottuLink + Tenjin + RevenueCat).
- Use tabs for three to five top-level destinations; reserve modals for short focused tasks.

---

## State Management

- Use unidirectional data flow: state flows down, events flow up.
- **Server/API state:** TanStack React Query for caching, deduplication, and optimistic updates.
  - **FastAPI backend (primary data layer):** the client talks only to FastAPI endpoints (Pattern A, same client model as web). Wrap each endpoint in a typed React Query hook; mirror the backend Pydantic schemas with Zod and validate at the React Query boundary when input/output crosses a trust boundary. Generate the typed client from the FastAPI OpenAPI schema with **`@hey-api/openapi-ts`** (FastAPI's own docs name Hey API as the purpose-built TypeScript generator) plus its **`@tanstack/react-query`** plugin (typed React Query hooks) and **`zod`** plugin (Zod validators). The scaffold still lists `axios`, `react-query-kit` and `@tanstack/zod-form-adapter`, which nothing uses since the Hey API client replaced them — never import them. Wire validation through on the `@hey-api/sdk` plugin — plugin-scoped, `{ name: '@hey-api/sdk', validator: true }` as the scaffold's `openapi-ts.config.ts` does (`true` resolves to the configured Zod plugin; `validator: 'zod'` is the explicit form) — never a top-level `sdk.validator`. One config emits the hooks + validators, unlike `openapi-typescript` (types only → every hook and Zod schema hand-written). Never `supabase gen types`, and never a `supabase-js` client.
  - The client never talks to Postgres or any data store directly — all data goes through FastAPI, which owns `postgres-main` access, AI workflows, scraping, and scheduled jobs.
- **Global UI state:** Zustand. Avoid Redux boilerplate and standalone `React.Context` for high-frequency updates.
- **Local persistence:** `react-native-mmkv` for fast, synchronous key-value storage (its README claims ~30× AsyncStorage, via JSI memory-mapped files). Reserve `expo-sqlite` + Drizzle ORM for complex offline relational queries only.
  - **The current (Nitro) API renamed the constructor and one method** — never copy an older snippet: create a store with `createMMKV(...)` (not `new MMKV(...)`; MMKV is now a native Nitro/JSI HybridObject) and delete a key with `.remove(key)` (not `.delete(key)`); the Info.plist key `AppGroup` became `AppGroupIdentifier`. It needs `react-native-nitro-modules` (the scaffold ships both). See [the upgrade guide](https://github.com/mrousavy/react-native-mmkv/blob/main/docs/V4_UPGRADE_GUIDE.md).
- Never call the FastAPI backend directly from a screen component — wrap in a typed React Query hook.

---

## Backend Integration

The RN client is a **Pattern-A client** (same model as web): it talks to a **self-hosted FastAPI backend**, never to a data store or an external BaaS. See `agents-fabrik.md § Supabase` (self-hosted by default) and `35-security-auth.md` § Pattern A. Supabase is retired as a default; treat any Supabase-native path below as **legacy only — migrate to self-hosted**.

- **FastAPI + `postgres-main` is the primary data layer**: app data, tenant-isolation RLS, storage routing, realtime. Auth is `fabrik-lib/fastapi-user-auth`.
- **Auth (Pattern A):** the FastAPI auth service (`fabrik-lib/fastapi-user-auth`) issues the app's own JWT and owns registration, **passwordless sign-in (the default — OTP code and/or magic link)**, login, password reset (password mode only), email verification, and OAuth/social — including **Sign in with Apple** (handled server-side, not by Supabase). The client stores the app-issued JWT in `expo-secure-store` and sends it in the `Authorization` header. Never store JWTs in AsyncStorage or MMKV. Token lifecycle (Argon2, 15-min access, refresh-token rotation, denylist) is exactly per `35-security-auth.md` § Pattern A.
- **Data:** the client uses typed React Query hooks against FastAPI endpoints. No `supabase-js`, no direct-from-client DB access, no Supabase Edge Functions. Anything needing secrets, AI workflows, scraping, or scheduled jobs runs behind FastAPI.
- **RLS:** keep tenant-isolation RLS on `postgres-main`, set up exactly as `saas/95-multi-tenant-saas.md` specifies. All tables enforce RLS before any query. No exceptions.
- **Vector / RAG:** pgvector on `postgres-main` + `fabrik-lib/rag`. **Storage:** `fabrik-lib/storage` (Backblaze B2), fronted by FastAPI presigned URLs. **Realtime:** `redis-main` pub/sub with WS/SSE from FastAPI — only if a feature actually needs it; default to React Query polling.
- **Hosting region:** `postgres-main` runs on the Fabrik VPS (EU) — satisfies GDPR and KVKK alignment with acceptable worldwide latency. Data residency is a VPS-placement decision, not a per-project BaaS region setting.
- **Legacy (Pattern B / Supabase Auth):** for a project that *already* runs on Supabase Auth and has not yet migrated, pass the Supabase JWT in the `Authorization` header and validate server-side per `35-security-auth.md` § Pattern B (confirm signing method — ES256 JWKS vs legacy HS256 shared secret; prefer `getClaims()`; always assert `aud == "authenticated"`, `iss`, `exp`). Such projects should plan their move to Pattern A / Pattern A-compat. Do not use this path for new work.

---

## Lists & Scrolling Performance

- Use `FlatList` for dynamic lists. Tune `windowSize`, `initialNumToRender`, `maxToRenderPerBatch`, and `removeClippedSubviews` based on profiling.
- Provide stable `keyExtractor` functions — never use array index as key for dynamic lists.
- For long lists or complex/heterogeneous rows, use `@shopify/flash-list` (view recycling; the scaffold ships it). Its current major runs on the New Architecture only and drops `estimatedItemSize` — never copy an older snippet that sets it.
- Never use `<ScrollView>` with `.map()` for dynamic data — it renders all items simultaneously.
- Avoid heavy computation or synchronous image decoding inside list item render functions.

---

## Styling

- **The scaffold styles with Uniwind** (`uniwind`) — a build-time Tailwind compiler for React Native (MIT, from the Unistyles team): `className` on RN primitives, compiled at build time with no runtime style parsing, variants via `tailwind-variants`, tokens fed through Tailwind's CSS-first `@theme` block in `src/global.css`. Keep it unless the project records a reason to change.
- `className` is only valid through a build-time compiler (Uniwind, or NativeWind). Never assume web CSS behaviour: no `hover`, no media queries, and Flexbox defaults to `flexDirection: 'column'`.
- `StyleSheet.create()` is the fallback for a one-off style a utility class cannot express — never inline objects recreated every render.
- **Alternatives, and when:** the free Uniwind re-renders on a theme change (a rare, deliberate event — acceptable); when zero-re-render synchronous theming is a hard requirement, use `react-native-unistyles` (New Architecture only, a C++/JSI core) or the paid, proprietary Uniwind Pro. NativeWind's stable line targets the previous Tailwind major; its line for the current Tailwind is still a release candidate — not for production.

### Component sources — where a component COMES FROM (the engine above only styles it)

- **Default: React Native Reusables** (`founded-labs/react-native-reusables` — MIT): shadcn/ui's copy-paste model for React Native, with starters for Uniwind or NativeWind. Components are STRUCTURE; the project's design system (resolved by the ladder in `saas/60-saas-ui.md` — BIC identity first, a house brand only by explicit declaration) is the SKIN. Four of the five fabrik-lib `rn-*-kit` modules ship UI on Uniwind (`rn-analytics-kit` has none).
- **One set spanning web and RN: gluestack-ui** (MIT per its README and GitHub's licence badge) — verify at adoption per the filter below.
- ⚠️ **THE LICENCE FILTER (load-bearing — a Fabrik scaffold IS a starter kit).** Premium UI-kit licences (Tailwind Plus, Flowbite Pro, shadcnblocks) forbid redistributing their components in a starter kit or website builder; their "unlimited end products" grant covers one app, never an emitted starter. So for anything a scaffold or template emits: **permissive OSI licences only** (MIT / Apache-2.0 / BSD), read at adoption from the raw licence file (never the marketing page), with the SPDX id and read-date recorded in the project's `docs/design-system.md` header. Terms you cannot retrieve = not an option.
- **Produced-artifact mirror:** components adopted here serve the app's OWN UI — artifacts the product generates for its customers never inherit them (same boundary as the web rule).

### Design system (mobile)

- Token SLOTS, both colour modes, the contrast contract, motion and states come from `core/design-system-template.md`; the VALUES come from the design system the ladder in `saas/60-saas-ui.md` resolves — a house brand only when the project declares it (Ocoron: values in `core/ocoron-design-system.md`; Tojlo likewise). The component patterns — list items, sheets, search, header, onboarding, forms — are `mobile-app/ocoron-mobile-design-system.md`'s, for every mobile project whatever its brand. Never copy hex values or a spacing scale into this pack or into components.
- Map the tokens into the styling engine's theme (Uniwind: `@theme` variables in `src/global.css`) — no raw hex values in components.
- **Both dark and light mode are mandatory**: follow the OS with a manual override in Settings, persisted in MMKV — the scaffold's `src/lib/hooks/use-selected-theme.tsx` does this with `Uniwind.setTheme('light' | 'dark' | 'system')`.
- Font size floor: 13px on any mobile surface; touch-target and motion rules per the template.

---

## Accessibility

- Interactive touch targets must be at minimum **44×44 pt** (iOS) / **48×48 dp** (Android). Expand with `hitSlop` if the visual element is smaller.
- Every icon-only control must have an `accessibilityLabel`.
- Use `accessibilityRole` to convey control purpose (e.g., `"button"`, `"link"`, `"header"`).
- Never rely on color alone to convey state — combine with text, icons, or haptic feedback.
- Support Dynamic Type (iOS) and font scaling (Android) — do not hardcode font sizes in absolute pixel values.

---

## Platform-Aware Patterns

- Use `Platform.OS === 'ios'` or `Platform.select()` for platform-specific behavior (shadows, keyboard, haptics).
- Always use `useSafeAreaInsets()` from `react-native-safe-area-context` instead of hardcoded top/bottom padding.
- Handle the keyboard with `react-native-keyboard-controller` (the scaffold ships it; Expo recommends it over the core `KeyboardAvoidingView` because Android apps now draw edge-to-edge — enforced for apps targeting Android 16, and the Expo default). Use its `KeyboardAvoidingView` / `KeyboardAwareScrollView`, not the core component; it needs `<KeyboardProvider>` at the root (the scaffold's `src/app/_layout.tsx` has it). Edge-to-edge itself comes from `react-native-edge-to-edge` (dependency + config plugin in the scaffold) — never re-add status-bar padding by hand.
- Never assume identical shadow rendering, status bar behavior, or keyboard dismiss behavior across platforms.

---

## Localization (i18n)

- Use `expo-localization` to detect device locale and `i18next` + `react-i18next` for translations. The app loads translation JSON from `src/translations/<lang>.json` (imported by `src/lib/i18n/resources.ts` in the scaffold).
- ⚠️ **The scaffold carries two unrelated translation sets.** The app's live strings are `src/translations/<lang>.json` (`en`, `ar` — the RTL exemplar), while `static/i18n/` holds the i18n-kit's own key set (`en.json`, `_context.json` and `*.example.json` seeds), which the app does not load; the two use different keys, so never copy files between them, and `scripts/sync_rn_locales.py` (which writes `src/locales/`) and `--init` do not apply. Until the scaffold unifies them, add each language in `src/translations/` with exactly the keys of `src/translations/en.json`, and register it in `resources.ts`. `scripts/validate_i18n.py` checks `static/i18n/` only, so it says nothing about the live set.
- All user-facing strings live in translation files. No hardcoded strings in components — caught at code review.
- Supported languages from day 1: **English (en), Turkish (tr)** — the scaffold ships no `tr` in the live set, so author `src/translations/tr.json`. Add Spanish (es), German (de), French (fr) and Portuguese-BR (pt-BR) as markets prove out.
- Dates and numbers: `Intl.DateTimeFormat` and `Intl.NumberFormat` with the user's locale. Never hardcode `MM/DD/YYYY` or `1,000.00` formats.
- Time zones: store all timestamps in **UTC** server-side. Render in user locale on the client via `date-fns-tz`. Before adopting `Temporal`, confirm the project's Hermes build supports it; otherwise add `@js-temporal/polyfill`.
- Currency display: `Intl.NumberFormat` with locale + currency code. Pricing source-of-truth is RevenueCat (see Monetization).
- Phone numbers: `libphonenumber-js` for parsing, formatting, and validation. Never assume a national format.
- RTL readiness: structure all Flexbox layouts to flip correctly under `I18nManager.isRTL`. Use `start`/`end` instead of `left`/`right` in styles. Even if Arabic ships later, design for it now.
- Pseudo-localization in dev builds (`zz` locale) to catch hardcoded strings and layout breakage before native-speaker QA.

---

## Forms

- Use `@tanstack/react-form` with Zod validators (the scaffold's forms, e.g. `src/features/auth/components/login-form.tsx`) — field-level subscriptions avoid whole-form re-renders on every keystroke.
- Reuse the Zod schemas generated from the FastAPI OpenAPI contract (§ State Management) so client and server validation cannot drift.

---

## Testing

- **Unit / component:** `@testing-library/react-native` + Jest (`jest-expo`).
  - **Its current major is async** — `render`, `renderHook`, `fireEvent` and `act` return Promises and MUST be awaited, and the previous major's `renderAsync`/`fireEventAsync`/`renderHookAsync` are gone (codemod `rntl-v14-async-functions`, [migration guide](https://oss.callstack.com/react-native-testing-library/docs/start/migration-v14)). ⚠️ The scaffold still pins the previous major, whose `render` is synchronous — write tests for the version in `package.json`, and migrate with the codemod when you upgrade.
- **E2E automation:** Maestro (declarative YAML flows targeting `testID` attributes, stored in `.maestro/`). Maestro handles implicit waits for network and animations, reducing flakiness vs Detox/Appium.

---

## MCP Servers (Mobile Automation)

- The MCP roster (`/opt/fabrik/docs/workstation/mcp-roster.md`, hub-local) assigns every mobile-app repo **`mobile-mcp`** (Mobile Next — iOS/Android simulators, emulators and devices through the accessibility tree) and **`maestro`** (runs the `.maestro/` flows); the hub writes them into `.mcp.json`. Use them for verification.
- Optional: **Expo MCP** (Expo-hosted, OAuth; current docs, EAS build/log inspection, simulator screenshots) and `appium/appium-mcp` for device farms — add them only through the MCP roster's process, never by hand-editing `.mcp.json`.
- After every non-trivial feature, prompt the agent to verify against the simulator via MCP. Manual click-testing is a smell — automate the verification loop.

---

## Build & Dev Workflow

- Use Metro bundler for development (`npx expo start` for managed projects, `npx react-native start` otherwise).
- Test on physical devices for performance-critical features — simulators hide real-world frame drops and thermal throttling.

### Builds — pick by distribution surface (this is the load-bearing decision)

The right build path depends on WHO consumes the binary, not on personal preference. Pick before wiring CI:

- **Store / team distribution** (App Store, Play Store, TestFlight, Play Console Internal Testing, RevenueCat-gated releases) → **EAS Build is primary.** Managed signing, CI, shareable install links, quota is a non-issue at this scale. Define EAS profiles in `eas.json` (`development`, `preview`, `production`). Trigger from GitHub Actions on tag push. **EAS Submit** to TestFlight and Play Console Internal Testing is the default first ring.
- **Sideload / solo / personal APK** (one-operator dev builds, personal utility apps, non-store distribution) → **Local `expo prebuild` + `./gradlew assembleRelease` is primary; EAS is the backup.** After the first toolchain download, repeat local builds come from the Gradle cache and need no account or build quota.

### Local Android toolchain (one-time setup — required for sideload builds AND for anything with a native C++ module)

Install exactly what the project's React Native version requests — never a version copied from a doc, which goes stale with every RN release:

- **JDK** — the version React Native's "Set Up Your Environment" page names (the Android build compiles against it).
- **Android SDK** — platform + build-tools matching `compileSdkVersion` in the prebuilt `android/` project.
- **NDK** — MANDATORY for any app with a native/C++ module (MMKV's Nitro module is one). A managed app has no `android/` folder: run a throwaway `npx expo prebuild --platform android` and read `ndkVersion` in `android/build.gradle` (set by React Native's version catalog). Google Play requires 16 KB page-size support for new apps and updates targeting Android 15+ (since 1 Nov 2025), which that NDK provides.
- **CMake** — the version React Native's Android build requests: `cmakeVersion` in `node_modules/react-native/ReactAndroid/build.gradle.kts` (overridable with `CMAKE_VERSION`); a mismatch is a common source of native build failures.

Install NDK + CMake via `sdkmanager` with those values (the CLI installs exact versions):

```bash
sdkmanager --install "ndk;<ndkVersion>" "cmake;<cmakeVersion>"
```

### Bundled-assets rule (the .gitignore gotcha that killed our first EAS upload)

**EAS Build uploads the project minus what `.gitignore` excludes** (a `.easignore`, when present, replaces `.gitignore` rather than adding to it) — a gitignored runtime asset is silently missing from the cloud build and fails at runtime. Concrete rule:

- **Runtime assets (images, fonts, seed data, on-device DBs) MUST be git-tracked**, not gitignored. Do not rely on `.easignore` when the app lives in a subdirectory of a parent git repo: eas-cli has been observed reading the git-root ignore file instead of the one beside `eas.json` (expo/eas-cli#4259).
- **Local Gradle builds are immune** — they read from the working tree, so gitignored assets still land in the APK. This is a second reason the sideload path is easier for solo work.
- If a large binary asset genuinely does not belong in git, host it externally and download on first run — do NOT rely on `.easignore` overrides.

### Shared rules (both build paths)

- **OTA updates**: Expo Updates for JS-only patches. Reserve full rebuilds (EAS or local) for native module changes. Channel strategy must match your build profiles.
- **CI/CD**: on the store path, trigger EAS via GitHub Actions on tag push. No manual production builds. On the sideload path, `./gradlew assembleRelease` from a clean checkout is sufficient — commit the APK output path to `.gitignore`, not the artifact.
- For backend Docker deployments (FastAPI on VPS), use `python:<version>-slim-<debian_codename>` (both placeholders for values in `.windsurf/rules/versions.yaml` — write the values, not the angle-bracket names). Never use `alpine` (musl libc compilation failures, missing pre-built wheels).

---

## Monetization

See `81-mobile-billing.md` for the full mobile billing discipline: RevenueCat integration, entitlement architecture, server-side verification, Turkey GPB-mandatory constraint, Teknokent tax treatment, and launch checklist.

Key points for the client-side agent:

- **RevenueCat** is the entitlement server — free ≤ $2.5K MTR, then 1% (per `81-mobile-billing.md`).
- Paywall components must support **remote config** via RevenueCat dashboard — never hardcode pricing or offering IDs.
- **"Restore Purchases" button is mandatory** on the paywall — omission = store rejection.
- Client-side entitlement checks are for UX only. **Server-side is the source of truth** (webhook → PostgreSQL).

---

## Push Notifications

- Use `expo-notifications` for cross-platform push. APNs (iOS) and FCM (Android) credentials managed via EAS.
- Never request push permission on first app launch. Defer until the user has experienced value (post-onboarding, after first meaningful action).
- Store device tokens in `postgres-main` keyed to `user_id`. Send via a FastAPI endpoint using the Expo Push API.
- Always include a deep link payload so taps route correctly via expo-router's file-based routes.

---

## Compliance (Worldwide — GDPR / KVKK / CCPA / App Store)

The compliance baseline is **GDPR + EU AI Act** because they are the strictest. Apps that satisfy this floor satisfy KVKK, CCPA/CPRA, LGPD, and PIPEDA with regional addenda only.

### Mandatory in every build, every market

- Privacy policy and Terms of Service URLs configured in `app.json` and reachable from in-app Settings.
- Data export and account deletion implemented as authenticated FastAPI routes (→ `postgres-main`), reachable from in-app Settings. Apple requires in-app account deletion for any app that supports account creation (Guideline 5.1.1(v)); Google Play requires an in-app deletion path **and** a web link to request deletion (entered in Play Console). Also required by GDPR, CCPA and KVKK.
- **Apple Privacy Manifest** (`PrivacyInfo.xcprivacy`): declare every required-reason API and tracking domain. Since 1 May 2024 App Store Connect rejects a new or updated app whose newly added SDK from Apple's commonly-used-SDK list lacks its privacy manifest and signature.
- **Play Data Safety form**: filled accurately in Play Console. Inaccuracies trigger removal.
- **Apple App Tracking Transparency (ATT)**: prompt before any IDFA collection or third-party tracking SDK fires. No exceptions, all markets.
- **GDPR consent gate**: no analytics, advertising, or non-essential third-party SDKs may fire before user consent. The scaffold's gate is `src/lib/consent` (PostHog analytics opted out by default; every capture checks `hasAnalyticsConsent()`) — wire the consent screen to its opt-in/opt-out, never build a second gate. Set `EXPO_PUBLIC_POSTHOG_HOST` to PostHog's EU endpoint (the default is the US one) and list PostHog as a processor in the privacy policy and DPA. Applies to all EU/EEA/UK users — detect via locale and IP.
- Encrypt PII at rest on the FastAPI VPS: use disk encryption + column-level encryption on `postgres-main` for sensitive fields.
- Crash reporting: the client's `Sentry.init` (`src/lib/crash.tsx`) must meet `core/55-observability.md`'s two flags — `includeLocalVariables: false` and a deny-by-default `beforeSend` scrubber; the scaffold's copy does not set them yet.
- Never include PII in AI agent prompts or in any `chat text` sent to Gemini/Claude/OpenAI APIs from the app. Enforce via server-side redaction (the durable control). `.aiexclude` only applies to Google/Gemini tooling that honors it — it is not a cross-vendor guarantee.
- Document the data-hosting region (Fabrik VPS, EU) in the privacy policy.

### Automated decision features (AI/ML)

If the app makes any AI-driven recommendation, score, match, classification, or auto-decision:

- Display a transparency notice ("This recommendation was generated automatically").
- Provide a manual override or "ask a human" path.
- Log override events server-side for regulator inquiries.
- This is a house default, stricter than the law for most features: GDPR Art. 22 binds only a solely-automated decision with legal or similarly significant effects; KVKK Art. 11(1)(g) gives a right to object to a detrimental result of exclusively automated analysis (KVKK's generative-AI guide, Nov 2025); the EU AI Act's Art. 50 transparency duties (from 2 Aug 2026) cover chatbots and AI-generated content, and plain recommendation features are minimal-risk under it. A chat assistant or generated content in the app must disclose that it is AI. <!-- Confirm exact KVKK obligations with legal counsel. -->

### Regional layers

- **EU/EEA/UK (GDPR + AI Act)**: full consent gate, DPA addendum required for any third-party processor, cookie/tracking notice on first launch in EU locales.
- **Turkey (KVKK)**: processing Turkish-user PII on the EU-hosted Fabrik VPS (`postgres-main`) is a cross-border transfer. Since 1 June 2024 (Law 7499) it needs an adequacy decision, an appropriate safeguard — e.g. the Board's standard contract, notified to the Authority within 5 business days of signing — or one of the incidental-transfer grounds; being in the EU is not itself a basis. <!-- Confirm the transfer basis with counsel. -->
- **California, USA (CCPA/CPRA)**: "Do Not Sell or Share My Personal Information" link/toggle in Settings if any data is shared with third parties. Honor Global Privacy Control (GPC) signal.
- **Brazil (LGPD)**: equivalent to GDPR — covered by the GDPR baseline.
- **Children**: if the app could be used by under-13s (under-16 in some EU states), comply with COPPA — the FTC's amended Rule is in force, compliance date 22 Apr 2026 — and Apple/Google child-directed app rules. Default to no third-party tracking SDKs.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Web DOM elements (`<div>`, `<span>`, `<p>`, `<img>`) | React Native primitives (`<View>`, `<Text>`, `<Pressable>`, `<Image>`) |
| Web CSS assumptions (`hover`, media queries, `className` without a build-time compiler) | Uniwind utility classes (the scaffold's engine) or `StyleSheet.create()` + Flexbox |
| `<ScrollView>` + `.map()` for dynamic data | `FlatList` or `@shopify/flash-list` |
| Array index as `key` in dynamic lists | Stable unique ID via `keyExtractor` |
| Hardcoded top/bottom padding for notches | `useSafeAreaInsets()` from `react-native-safe-area-context` |
| `AsyncStorage` for performance-critical data | `react-native-mmkv` (synchronous JSI) |
| JWTs in AsyncStorage or MMKV | `expo-secure-store` |
| A runtime-parsing styling library (old NativeWind lines) | Uniwind (the scaffold's), NativeWind's current stable line, or `react-native-unistyles` |
| Legacy bridge-dependent native modules | New Architecture (Fabric/JSI) compatible modules |
| Manual edits to `android/` / `ios/` in Expo projects | Expo Config Plugins in `app.json` |
| Direct FastAPI calls from screen components | Typed React Query hooks |
| `supabase-js` / direct-Supabase-from-client / `supabase gen types` | FastAPI endpoints via typed React Query hooks; client generated with `@hey-api/openapi-ts` (react-query + zod plugins) |
| `@react-navigation/*` in app code; hand-written navigation | **expo-router** entry points (`@react-navigation/*` app-code imports are a bundler error) |
| `openapi-typescript` (types only → hand-written hooks/Zod) | `@hey-api/openapi-ts` — hooks + Zod validators from one config (`validator` on the `@hey-api/sdk` plugin) |
| `postgres-main` tables without RLS | RLS enabled before any query |
| Hardcoded user-facing strings | `i18next` translation files |
| Hardcoded prices or offering IDs | RevenueCat dashboard remote config |
| Push permission requested on first launch | Deferred until post-onboarding value moment |
| Tracking SDKs firing before ATT / GDPR consent | Gated behind explicit user consent |
| PII in AI agent prompts or external LLM calls | Server-side redaction (durable control); `.aiexclude` is Google/Gemini-only, not cross-vendor |
| `any` type | `unknown` + type guards (per `20-typescript.md`) |
| `console.log()` in production builds | Sentry breadcrumbs or strip via babel plugin; dev-only in `__DEV__` guard |
| Firebase Dynamic Links | Shut down 25 Aug 2025 — use ChottuLink or equivalent |
| Core `KeyboardAvoidingView` on Android | `react-native-keyboard-controller` (edge-to-edge) |
| `react-hook-form` in a scaffolded app | `@tanstack/react-form` + Zod (the scaffold's forms) |

---

## Related Rule Packs

- `20-typescript.md` — TypeScript strict mode, type safety, module patterns
- `35-security-auth.md` — Pattern A (`fabrik-lib/fastapi-user-auth`, default), `expo-secure-store`, CORS; Pattern B (Supabase Auth) legacy-only
- `45-testing-strategy.md` — Maestro E2E, `@testing-library/react-native` + Jest
- `55-observability.md` — backend structlog + GlitchTip; client Sentry RN SDK
- `58-resilience.md` — backend external call resilience (timeout/retry/CB)
- `design-system-template.md` — token slots, motion, accessibility, states
- `ocoron-mobile-design-system.md` — the mobile component patterns (list items, sheets, search, header, onboarding, forms), for every mobile project
- `core/ocoron-design-system.md` (and the Tojlo packs) — a house brand's values and Tojlo's module patterns, only for a project that declares it
- `00-domain-mobile-app.md` — planning-level decisions (17 dimensions, attribution stack, distribution)

---

## Done When

- [ ] No web DOM elements in any React Native component.
- [ ] All interactive controls meet minimum touch target sizes (44 pt iOS / 48 dp Android).
- [ ] Every icon-only control has an `accessibilityLabel`.
- [ ] `FlatList` or `FlashList` used for all dynamic lists — no `<ScrollView>` + `.map()`.
- [ ] Safe areas handled via `useSafeAreaInsets()`, not hardcoded padding.
- [ ] Platform-specific behavior uses `Platform.OS` or `Platform.select()`.
- [ ] Styles through Uniwind classes (or `StyleSheet.create()` for one-offs) — no web CSS assumptions, no per-render inline style objects.
- [ ] TypeScript strict mode enabled — no `any` types.
- [ ] Navigation uses **expo-router** file-based routes with typed routes enabled — no `@react-navigation/*` in app code.
- [ ] Design tokens from the resolved design system mapped into the styling engine's theme — no raw hex values in components.
- [ ] Client generated with `@hey-api/openapi-ts` (react-query + zod plugins) from the FastAPI OpenAPI schema and committed — no `supabase-js`, no `supabase gen types`, no hand-written hooks.
- [ ] All `postgres-main` tables have RLS enabled.
- [ ] App-issued JWT stored in `expo-secure-store`, not AsyncStorage or MMKV.
- [ ] EAS profiles defined in `eas.json` (development, preview, production).
- [ ] `mobile-mcp` or `maestro` used in the verification loop.
- [ ] RevenueCat integrated (free ≤ $2.5K MTR, then 1% — see `81-mobile-billing.md`), paywall remote-configurable.
- [ ] Push permission requested post-onboarding, not on first launch.
- [ ] Privacy policy and ToS URLs in `app.json`, reachable from in-app Settings.
- [ ] Data export and account deletion endpoints implemented and reachable from in-app Settings.
- [ ] Apple Privacy Manifest (`PrivacyInfo.xcprivacy`) declares every reason API and tracking domain.
- [ ] Play Data Safety form filled accurately.
- [ ] ATT prompt fires before any IDFA / tracking SDK initializes (iOS).
- [ ] GDPR consent gate blocks analytics and non-essential SDKs until user consent (EU/EEA/UK locales).
- [ ] AI-driven decision features carry transparency notice + manual override path.
- [ ] All user-facing strings live in translation files — no hardcoded strings.
- [ ] Every `src/translations/<lang>.json` carries exactly the keys of `src/translations/en.json` (the live set); `python scripts/validate_i18n.py` passes clean for `static/i18n/` if the project uses that set. Run after any ticket that adds or changes UI strings.
- [ ] App tested in `en-US`, `tr-TR`, and at least one RTL or non-Latin locale.
- [ ] Dates, numbers, currency rendered via `Intl` APIs with user locale.
- [ ] Pricing configured per country in RevenueCat dashboard.
- [ ] Data-hosting region (Fabrik VPS, EU) documented in privacy policy.
- [ ] No PII in AI agent prompts or external LLM calls.
- [ ] Both dark and light mode implemented. OS preference detected + manual toggle in Settings + preference persists in MMKV.

## Draft Persistence — nothing typed or AI-generated is EVER lost (fleet mandate 2026-08-13)

Every form/wizard/editor/AI-populated surface persists its full working state **continuously on
change** (debounce ≤1s + flush on blur/hide/background) to MMKV/AsyncStorage (drafts only — tokens stay in `expo-secure-store`); **restore is automatic and
silent** on every return path (refresh, Back, reopened tab/app, crash, days-old session) — the
user continues down to the last letter typed. The draft clears on exactly ONE event: successful
creation/submission of the entity (or explicit user discard). Canonical detail:
`core/design-system-template.md` § Save Behavior.
