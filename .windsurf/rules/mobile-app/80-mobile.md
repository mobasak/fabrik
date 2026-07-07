---
activation: glob
globs: ["**/metro.config.*", "**/react-native.config.*", "**/app.json", "**/eas.json"]
description: React Native mobile discipline — architecture, backend, navigation, performance, monetization, compliance, and i18n for worldwide shipping
trigger: glob
---
<!-- CONSUMER: Coding agents building React Native mobile apps
     GOAL: RN/Expo architecture, navigation, state, styling, accessibility, compliance, i18n
     TRAYCER USAGE: Injects as Context File for mobile client-lane tickets.
     AGENT USAGE: Follow verbatim for client-side mobile code. Backend rules from 10-python apply. -->

# Mobile Rules (React Native)

Apply when working on React Native / TypeScript mobile projects. Skip for web frontend, Python, Docker, or infrastructure files. For general TypeScript discipline, see `20-typescript.md`.

Worldwide-shipping baseline. Compliance floor is GDPR + EU AI Act; other markets are regional addenda. i18n is built in from day 1, not retrofitted.

**Two-faced scaffold:** the client (React Native app) builds via EAS and ships to stores. The backend (FastAPI on `postgres-main`, auth via `fabrik-lib/fastapi-user-auth`) deploys to VPS via `fabrik apply` with full registrar set — the same self-hosted Pattern-A stack as web (see `AGENTS.md § Supabase`; Supabase is retired as a default). This file covers the **client lane**. Backend rules: `10-python.md`, `30-ops.md`, `55-observability.md`. For planning-level decisions (architecture, monetization, distribution, attribution), see `00-domain-mobile-app.md`.

---

## Screen Inventory (minimum viable mobile app)

Every mobile app project must ship these screens. Traycer derives additional project-specific screens during `core-flows` and `ticket-breakdown`.

### Auth & Onboarding

| Screen | Route/Name | Purpose |
|---|---|---|
| **Splash** | App launch | Brand splash (800ms max per design system § Motion). Checks auth state → routes to onboarding or home. |
| **Onboarding wizard** | `Onboarding` | 3-5 swipeable value screens. Skippable. Shows before signup for value-before-signup pattern. |
| **Login** | `Login` | FastAPI auth service (`fabrik-lib/fastapi-user-auth`) — email + social/OAuth handled server-side; client stores the app-issued JWT in `expo-secure-store`. Per Apple Guideline 4.8, if you offer any third-party/social login you must also offer an equivalent privacy-preserving option — Sign in with Apple (via the FastAPI auth service) is the canonical way to satisfy this. |
| **Signup** | `Signup` | Registration. Redirects to verify-email screen. |
| **Verify email** | `VerifyEmail` | "Check your email" — resend button, change email link. Cannot proceed until verified. |
| **Forgot password** | `ForgotPassword` | Email input → triggers reset flow. |
| **Permission priming** | `PermissionPriming` | Explains WHY before OS prompt (push, camera, location). Just-in-time, not at launch. |

### Core App (tab navigator)

| Screen | Route/Name | Purpose |
|---|---|---|
| **Home / Dashboard** | `Home` | Primary tab. Active status, quick actions, recent items. |
| **[Core feature screens]** | Project-specific | Defined per epic during `core-flows`. 2-4 tabs typical. |
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
| **Language** | `LanguageSettings` | Locale picker (en, tr, + future languages). |
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
- Core feature screens are project-specific — Traycer defines them during `core-flows`.
- Every screen follows the design system 5 states (loading, empty, error, success, disabled).
- Navigation: `NativeStackNavigator` for hierarchical flows, `BottomTabNavigator` for top-level (3-5 tabs).

---

## Architecture

- React Native with TypeScript is the mobile framework. The New Architecture (Fabric/JSI) is the default since React Native 0.76 and Expo SDK 53; the legacy bridge was frozen in June 2025 and removed in RN 0.82 (Oct 2025). Expo SDK 55 (current stable, Feb 2026) made it mandatory — `newArchEnabled: false` no longer exists. Never generate code relying on the legacy asynchronous JSON bridge.
- Web DOM elements (`<div>`, `<span>`, `<p>`, `<img>`, `<a>`) are **strictly forbidden**. Use React Native primitives: `<View>`, `<Text>`, `<Pressable>`, `<Image>`.
- Minimize direct modifications to `android/` and `ios/` directories. Prefer config plugins or autolinking where possible.
- If the project uses Expo Managed Workflow, never suggest `npx expo eject` or manual native file edits. All native configuration belongs in `app.json` config plugins.

---

## Navigation

- Use React Navigation (`@react-navigation/native`) for all navigation.
- Use `NativeStackNavigator` for hierarchical screen flows and `BottomTabNavigator` for top-level sections.
- Extract route names and param types into a shared type file (e.g., `NavigationTypes.ts`) to keep navigation type-safe.
- Configure deep linking via React Navigation's `linking` prop. Use Universal Links (iOS AASA) and App Links (Android assetlinks.json) — wired as Expo config plugins at prebuild. Custom URL schemes are fallback only.
- Deep-link routing via ChottuLink (or equivalent) for attribution. See `00-domain-mobile-app.md` § Attribution for the full stack (ChottuLink + Tenjin + RevenueCat).
- Use tabs for three to five top-level destinations; reserve modals for short focused tasks.

---

## State Management

- Use unidirectional data flow: state flows down, events flow up.
- **Server/API state:** TanStack React Query for caching, deduplication, and optimistic updates.
  - **FastAPI backend (primary data layer):** the client talks only to FastAPI endpoints (Pattern A, same client model as web). Wrap each endpoint in a typed React Query hook; mirror the backend Pydantic schemas with Zod and validate at the React Query boundary when input/output crosses a trust boundary. Generate/maintain the client types from the FastAPI OpenAPI schema (e.g. `openapi-typescript`) — never `supabase gen types`, and never a `supabase-js` client.
  - The client never talks to Postgres or any data store directly — all data goes through FastAPI, which owns `postgres-main` access, AI workflows, scraping, and scheduled jobs.
- **Global UI state:** Zustand. Avoid Redux boilerplate and standalone `React.Context` for high-frequency updates.
- **Local persistence:** `react-native-mmkv` (V4+) for fast, synchronous key-value storage (30× faster than AsyncStorage via JSI memory-mapped files). Reserve `expo-sqlite` + Drizzle ORM for complex offline relational queries only.
  - **V4 API — the constructor and one method were renamed** (do not copy pre-V3 snippets): create a store with `createMMKV(...)` (not `new MMKV(...)` — the JS class was removed, MMKV is now a purely native Nitro/JSI HybridObject) and delete a key with `.remove(key)` (not `.delete(key)` — `delete` is a reserved keyword in C++). Also `AppGroup` in Info.plist was renamed to `AppGroupIdentifier`. V4 requires `react-native-nitro-modules` and RN ≥ 0.75. See [react-native-mmkv V4_UPGRADE_GUIDE.md](https://github.com/mrousavy/react-native-mmkv/blob/main/docs/V4_UPGRADE_GUIDE.md).
- Never call the FastAPI backend directly from a screen component — wrap in a typed React Query hook.

---

## Backend Integration

The RN client is a **Pattern-A client** (same model as web): it talks to a **self-hosted FastAPI backend**, never to a data store or an external BaaS. See `AGENTS.md § Supabase` (self-hosted by default) and `35-security-auth.md` § Pattern A. Supabase is retired as a default; treat any Supabase-native path below as **legacy only — migrate to self-hosted**.

- **FastAPI + `postgres-main` is the primary data layer**: app data, tenant-isolation RLS, storage routing, realtime. Auth is `fabrik-lib/fastapi-user-auth`.
- **Auth (Pattern A):** the FastAPI auth service (`fabrik-lib/fastapi-user-auth`) issues the app's own JWT and owns registration, login, password reset, email verification, and OAuth/social — including **Sign in with Apple** (handled server-side, not by Supabase). The client stores the app-issued JWT in `expo-secure-store` and sends it in the `Authorization` header. Never store JWTs in AsyncStorage or MMKV. Token lifecycle (Argon2, 15-min access, refresh-token rotation, denylist) is exactly per `35-security-auth.md` § Pattern A.
- **Data:** the client uses typed React Query hooks against FastAPI endpoints. No `supabase-js`, no direct-from-client DB access, no Supabase Edge Functions. Anything needing secrets, AI workflows, scraping, or scheduled jobs runs behind FastAPI.
- **RLS:** keep tenant-isolation RLS on `postgres-main`. `fabrik-user-auth` owns the `auth` schema; policies use `auth.uid()` reimplemented over the `request.jwt.claims` GUC (per `35-security-auth.md` § Pattern A-compat and `95-multi-tenant-saas.md`). All tables enforce RLS before any query. No exceptions.
- **Vector / RAG:** pgvector on `postgres-main` + `fabrik-lib/rag`. **Storage:** `fabrik-lib/storage` (Backblaze B2), fronted by FastAPI presigned URLs. **Realtime:** `redis-main` pub/sub with WS/SSE from FastAPI — only if a feature actually needs it; default to React Query polling.
- **Hosting region:** `postgres-main` runs on the Fabrik VPS (EU) — satisfies GDPR and KVKK alignment with acceptable worldwide latency. Data residency is a VPS-placement decision, not a per-project BaaS region setting.
- **Legacy (Pattern B / Supabase Auth):** for a project that *already* runs on Supabase Auth and has not yet migrated, pass the Supabase JWT in the `Authorization` header and validate server-side per `35-security-auth.md` § Pattern B (confirm signing method — ES256 JWKS vs legacy HS256 shared secret; prefer `getClaims()`; always assert `aud == "authenticated"`, `iss`, `exp`). Such projects should plan their move to Pattern A / Pattern A-compat. Do not use this path for new work.

---

## Lists & Scrolling Performance

- Use `FlatList` for dynamic lists. Tune `windowSize`, `initialNumToRender`, `maxToRenderPerBatch`, and `removeClippedSubviews` based on profiling.
- Provide stable `keyExtractor` functions — never use array index as key for dynamic lists.
- For lists exceeding ~50 items with complex rows, use `@shopify/flash-list` for native view recycling at 60 fps.
- Never use `<ScrollView>` with `.map()` for dynamic data — it renders all items simultaneously.
- Avoid heavy computation or synchronous image decoding inside list item render functions.

---

## Styling

- Use React Native `StyleSheet.create()` as the default styling approach.
- React Native Flexbox defaults to `flexDirection: 'column'` — do not assume web CSS behavior.
- Never use web CSS properties (`className`, media queries, `hover`) in React Native components.
- **NativeWind v4** moved to build-time compilation (Metro plugin) — static styles compile to `StyleSheet.create()` objects at build, so static-style performance is equivalent to raw StyleSheet. However, **dynamic styles (theming, responsive, state-driven)** still require React context/bridge; `react-native-unistyles` (C++/JSI, synchronous) is faster for these. **Recommendation:** use `react-native-unistyles` for projects with deep theming (Ocoron Design System dark/light switching) or frequent dynamic style updates. NativeWind v4 is acceptable for static-heavy UIs if the team prefers Tailwind DX. NativeWind v5 (aligns with Tailwind CSS v4 Rust engine) is in preview — not production-ready.
- For complex adaptive theming with design tokens, `react-native-unistyles` (C++/JSI, zero re-render overhead) is the approved alternative.

### Ocoron Design System (Mobile)

- Apply Ocoron Design System color tokens (`ocoron-design-system.md`) via `react-native-unistyles` theme configuration. Same hex values as web, mapped to the unistyles theme object.
- Load **Space Grotesk** and **Inter** as custom fonts via `expo-font` or manual linking. Use **JetBrains Mono** for data/metrics displays only.
- **Both dark and light mode are mandatory.** Dark is default. Detect OS preference via `Appearance.getColorScheme()` + `addEventListener('change')` on mount. Manual override in Settings screen. Persist preference in MMKV. Switch via `react-native-unistyles` theme.
- Cards → `Pressable` list items with `translateY(1)` + `scale(0.98)` press feedback (`0.15s` duration).
- Tab bar → bottom navigation using `--color-accent` (`#5B5BF7`) for the active tab indicator.
- Font size floor: 13px. No text smaller than this on any mobile surface.
- Spacing follows the Ocoron token scale (`xs: 4, sm: 8, md: 16, lg: 24, xl: 32, 2xl: 48`) mapped to unistyles spacing.
- Component patterns (cards with 1px borders, tags, pills, buttons) follow canonical design system specs adapted for touch targets.

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
- Handle keyboard avoidance with `KeyboardAvoidingView` — `behavior="padding"` on iOS, `behavior="height"` on Android.
- Never assume identical shadow rendering, status bar behavior, or keyboard dismiss behavior across platforms.

---

## Localization (i18n)

- Use `expo-localization` to detect device locale and `i18next` + `react-i18next` for translations. Translation JSON in `src/locales/<lang>.json`.
- **Source-of-truth JSON lives at `static/i18n/en.json`** (same format across all fabrik GUI projects). Sync to `src/locales/` via `python scripts/sync_rn_locales.py`. First-time setup: `python scripts/sync_rn_locales.py --init` generates `src/locales/i18n.ts` with expo-localization + i18next config.
- All user-facing strings live in translation files. No hardcoded strings in components — caught at code review.
- Supported languages from day 1: **English (en), Turkish (tr)**. Add Spanish (es), German (de), French (fr), Portuguese-BR (pt-BR), Arabic (ar) as markets prove out.
- Dates and numbers: `Intl.DateTimeFormat` and `Intl.NumberFormat` with the user's locale. Never hardcode `MM/DD/YYYY` or `1,000.00` formats.
- Time zones: store all timestamps in **UTC** server-side. Render in user locale on the client via `date-fns-tz`. (Temporal is not yet implemented in Hermes — if used, add `@js-temporal/polyfill`; `date-fns-tz` is the zero-dependency default.)
- Currency display: `Intl.NumberFormat` with locale + currency code. Pricing source-of-truth is RevenueCat (see Monetization).
- Phone numbers: `libphonenumber-js` for parsing, formatting, and validation. Never assume a national format.
- RTL readiness: structure all Flexbox layouts to flip correctly under `I18nManager.isRTL`. Use `start`/`end` instead of `left`/`right` in styles. Even if Arabic ships later, design for it now.
- Pseudo-localization in dev builds (`zz` locale) to catch hardcoded strings and layout breakage before native-speaker QA.

---

## Forms

- Use `react-hook-form` with `zod` resolvers for form validation. Uncontrolled components prevent full-form re-renders on every keystroke.
- Mirror Zod schemas with backend Pydantic schemas (FastAPI) to maintain type alignment across the network boundary.

---

## Testing

- **Unit / component:** `@testing-library/react-native` (v14+) + Jest.
  - **v14 API is async** — `render`, `renderHook`, `fireEvent`, and `act` all return Promises and MUST be awaited. Tests written against v13 or earlier that used `const { getByText } = render(<Comp/>)` without `await` will now leak the Promise and fail on Suspense boundaries / the React 19 `use()` hook. If you migrated the v13.3 `renderAsync` / `fireEventAsync` / `renderHookAsync` APIs, rename them to their non-`Async` counterparts (they were the preview, now the default). Codemod: `rntl-v14-async-functions`. See [migration-v14](https://oss.callstack.com/react-native-testing-library/docs/start/migration-v14).
- **E2E automation:** Maestro (declarative YAML flows targeting `testID` attributes, stored in `.maestro/`). Maestro handles implicit waits for network and animations, reducing flakiness vs Detox/Appium.

---

## MCP Servers (Mobile Automation)

- Configure these MCP servers in the AI agent (Claude Code / Cursor) for autonomous verification:
  - **Expo MCP**: SDK docs, EAS build inspection, simulator screenshots.
  - **Mobile Next MCP**: native iOS/Android accessibility tree interaction for end-to-end UI verification.
  - **iOS Simulator MCP** (idb-based): boot, focus, control simulator windows.
  - **Appium MCP**: cross-platform automation against simulators and physical devices when needed.
- After every non-trivial feature, prompt the agent to verify against the simulator via MCP. Manual click-testing is a smell — automate the verification loop.

---

## Build & Dev Workflow

- Use Metro bundler for development (`npx expo start` for managed projects, `npx react-native start` otherwise).
- Test on physical devices for performance-critical features — simulators hide real-world frame drops and thermal throttling.

### Builds — pick by distribution surface (this is the load-bearing decision)

The right build path depends on WHO consumes the binary, not on personal preference. Pick before wiring CI:

- **Store / team distribution** (App Store, Play Store, TestFlight, Play Console Internal Testing, RevenueCat-gated releases) → **EAS Build is primary.** Managed signing, CI, shareable install links, quota is a non-issue at this scale. Define EAS profiles in `eas.json` (`development`, `preview`, `production`). Trigger from GitHub Actions on tag push. **EAS Submit** to TestFlight and Play Console Internal Testing is the default first ring.
- **Sideload / solo / personal APK** (one-operator dev builds, personal utility apps, non-store distribution) → **Local `expo prebuild` + `./gradlew assembleRelease` is primary; EAS is the backup.** First build is 15–40 min (Gradle downloads the toolchain), repeat builds are 2–5 min from Gradle cache; EAS is a constant ~15 min per run + account + monthly quota. For the solo path, local is strictly faster and has no external dependency once the toolchain is set up.

### Local Android toolchain (one-time setup — required for sideload builds AND for anything with a native C++ module)

Pinned versions (verified against the RN 0.76 android template):

- **JDK 17** (`openjdk-17-jdk` or Temurin 17).
- **Android SDK** — install via Android Studio SDK Manager (platform + build-tools matching your `compileSdkVersion`).
- **NDK 27.1.12297006** — MANDATORY for any app with a native/C++ module. RN 0.76+ defaults to NDK 27 for 16KB page-size support (Play Store requirement from Nov 2025). `react-native-mmkv` V4 is a Nitro/JSI C++ module, so if MMKV is in the tree you WILL exercise the NDK path.
- **CMake 3.22.1** — the version RN 0.76's android template pins. Newer CMakes work in general but the template hardcodes this one; matching avoids a class of surprising build failures.

Install NDK + CMake via `sdkmanager` (not Android Studio — the CLI pins the exact versions):

```bash
sdkmanager --install "ndk;27.1.12297006" "cmake;3.22.1"
```

### Bundled-assets rule (the .gitignore gotcha that killed our first EAS upload)

**EAS Build honors `.gitignore` — anything gitignored is silently dropped from the uploaded tarball.** We shipped a first cloud upload of 1.6 MB instead of ~20 MB because the deck-media directory was gitignored (working-tree-only), so the bundle would fail at runtime. Concrete rule:

- **Runtime assets (images, decks, fonts, seed data, on-device DBs) MUST be git-tracked**, not gitignored. `.easignore` is unreliable when the app lives in a subdir of a parent git repo — the parent-repo `.gitignore` wins.
- **Local Gradle builds are immune** — they read from the working tree, so gitignored assets still land in the APK. This is a second reason the sideload path is easier for solo work.
- If a large binary asset genuinely does not belong in git, host it externally and download on first run — do NOT rely on `.easignore` overrides.

### Shared rules (both build paths)

- **OTA updates**: Expo Updates for JS-only patches. Reserve full rebuilds (EAS or local) for native module changes. Channel strategy must match your build profiles.
- **CI/CD**: on the store path, trigger EAS via GitHub Actions on tag push. No manual production builds. On the sideload path, `./gradlew assembleRelease` from a clean checkout is sufficient — commit the APK output path to `.gitignore`, not the artifact.
- For backend Docker deployments (FastAPI on VPS), use `python:<version>-slim-bookworm`. Never use `alpine` (musl libc compilation failures, missing pre-built wheels).

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
- Always include a deep link payload so taps route correctly via React Navigation `linking`.

---

## Compliance (Worldwide — GDPR / KVKK / CCPA / App Store)

The compliance baseline is **GDPR + EU AI Act** because they are the strictest. Apps that satisfy this floor satisfy KVKK, CCPA/CPRA, LGPD, and PIPEDA with regional addenda only.

### Mandatory in every build, every market

- Privacy policy and Terms of Service URLs configured in `app.json` and reachable from in-app Settings.
- Data export and account deletion endpoints implemented as authenticated FastAPI routes (→ `postgres-main`, `ON DELETE CASCADE`), reachable from in-app Settings. Required by GDPR, CCPA, KVKK, and Apple App Store policy.
- **Apple Privacy Manifest** (`PrivacyInfo.xcprivacy`): declare every reason API and tracking domain. Required for App Store submission.
- **Play Data Safety form**: filled accurately in Play Console. Inaccuracies trigger removal.
- **Apple App Tracking Transparency (ATT)**: prompt before any IDFA collection or third-party tracking SDK fires. No exceptions, all markets.
- **GDPR consent gate**: no analytics, advertising, or non-essential third-party SDKs may fire before user consent. Use a CMP or built-in consent screen. Applies to all EU/EEA/UK users — detect via locale and IP.
- Encrypt PII at rest on the FastAPI VPS: use disk encryption + column-level encryption on `postgres-main` for sensitive fields.
- Never include PII in AI agent prompts or in any `chat text` sent to Gemini/Claude/OpenAI APIs from the app. Enforce via server-side redaction (the durable control). `.aiexclude` only applies to Google/Gemini tooling that honors it — it is not a cross-vendor guarantee.
- Document the data-hosting region (Fabrik VPS, EU) in the privacy policy.

### Automated decision features (AI/ML)

If the app makes any AI-driven recommendation, score, match, classification, or auto-decision:

- Display a transparency notice ("This recommendation was generated automatically").
- Provide a manual override or "ask a human" path.
- Log override events server-side for regulator inquiries.
- Required by GDPR Art. 22 (prohibition on solely-automated decisions) and the EU AI Act; under Turkish law, KVKK Art. 11/1-g gives data subjects a right to object to decisions made solely by automated systems (see KVKK's Nov 2025 Generative AI guidance and its Apr 2025 AI recommendations). Treat the transparency + override path as a global default. <!-- Confirm exact KVKK obligations with legal counsel. -->

### Regional layers

- **EU/EEA/UK (GDPR + AI Act)**: full consent gate, DPA addendum required for any third-party processor, cookie/tracking notice on first launch in EU locales.
- **Turkey (KVKK)**: processing Turkish-user PII on the EU-hosted Fabrik VPS (`postgres-main`) is a cross-border transfer under KVKK and requires a lawful transfer basis — it is not automatically compliant by virtue of being in the EU. <!-- Confirm the transfer basis with counsel. --> Manual override on automated decisions covered by the global rule above.
- **California, USA (CCPA/CPRA)**: "Do Not Sell or Share My Personal Information" link/toggle in Settings if any data is shared with third parties. Honor Global Privacy Control (GPC) signal.
- **Brazil (LGPD)**: equivalent to GDPR — covered by the GDPR baseline.
- **Children**: if app could be used by under-13s (under-16 in some EU states), comply with COPPA and follow Apple/Google child-directed app rules. Default to no third-party tracking SDKs.

---

## Banned Patterns

| Pattern | Use Instead |
|---------|-------------|
| Web DOM elements (`<div>`, `<span>`, `<p>`, `<img>`) | React Native primitives (`<View>`, `<Text>`, `<Pressable>`, `<Image>`) |
| Web CSS (`className`, `hover`, media queries) | React Native `StyleSheet.create()` + Flexbox |
| `<ScrollView>` + `.map()` for dynamic data | `FlatList` or `@shopify/flash-list` |
| Array index as `key` in dynamic lists | Stable unique ID via `keyExtractor` |
| Hardcoded top/bottom padding for notches | `useSafeAreaInsets()` from `react-native-safe-area-context` |
| `AsyncStorage` for performance-critical data | `react-native-mmkv` (synchronous JSI) |
| JWTs in AsyncStorage or MMKV | `expo-secure-store` |
| NativeWind v2/v3 (runtime parsing) | NativeWind v4+ (build-time) or `react-native-unistyles` (preferred for dynamic theming) |
| Legacy bridge-dependent native modules | New Architecture (Fabric/JSI) compatible modules |
| Manual edits to `android/` / `ios/` in Expo projects | Expo Config Plugins in `app.json` |
| Direct FastAPI calls from screen components | Typed React Query hooks |
| `supabase-js` / direct-Supabase-from-client / `supabase gen types` | FastAPI endpoints via typed React Query hooks; types from the FastAPI OpenAPI schema |
| `postgres-main` tables without RLS | RLS enabled before any query |
| Hardcoded user-facing strings | `i18next` translation files |
| Hardcoded prices or offering IDs | RevenueCat dashboard remote config |
| Push permission requested on first launch | Deferred until post-onboarding value moment |
| Tracking SDKs firing before ATT / GDPR consent | Gated behind explicit user consent |
| PII in AI agent prompts or external LLM calls | Server-side redaction (durable control); `.aiexclude` is Google/Gemini-only, not cross-vendor |
| `any` type | `unknown` + type guards (per `20-typescript.md`) |
| `console.log()` in production builds | Sentry breadcrumbs or strip via babel plugin; dev-only in `__DEV__` guard |
| Firebase Dynamic Links | Dead (Aug 2025) — use ChottuLink or equivalent |

---

## Related Rule Packs

- `20-typescript.md` — TypeScript strict mode, type safety, module patterns
- `35-security-auth.md` — Pattern A (`fabrik-lib/fastapi-user-auth`, default), `expo-secure-store`, CORS; Pattern B (Supabase Auth) legacy-only
- `45-testing-strategy.md` — Maestro E2E, `@testing-library/react-native` + Jest
- `55-observability.md` — backend structlog + GlitchTip; client Sentry RN SDK
- `58-resilience.md` — backend external call resilience (timeout/retry/CB)
- `ocoron-design-system.md` — visual tokens, motion, accessibility, states
- `00-domain-mobile-app.md` — planning-level decisions (17 dimensions, attribution stack, distribution)

---

## Done When

- [ ] No web DOM elements in any React Native component.
- [ ] All interactive controls meet minimum touch target sizes (44 pt iOS / 48 dp Android).
- [ ] Every icon-only control has an `accessibilityLabel`.
- [ ] `FlatList` or `FlashList` used for all dynamic lists — no `<ScrollView>` + `.map()`.
- [ ] Safe areas handled via `useSafeAreaInsets()`, not hardcoded padding.
- [ ] Platform-specific behavior uses `Platform.OS` or `Platform.select()`.
- [ ] `StyleSheet.create()` used for all styles — no inline web CSS patterns.
- [ ] TypeScript strict mode enabled — no `any` types.
- [ ] Navigation is type-safe with explicit route/param types.
- [ ] Ocoron color tokens applied via `react-native-unistyles` theme — no raw hex values in components.
- [ ] Client types generated from the FastAPI OpenAPI schema and committed — no `supabase-js`, no `supabase gen types`.
- [ ] All `postgres-main` tables have RLS enabled.
- [ ] App-issued JWT stored in `expo-secure-store`, not AsyncStorage or MMKV.
- [ ] EAS profiles defined in `eas.json` (development, preview, production).
- [ ] At least one MCP server wired and used in the verification loop.
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
- [ ] `python scripts/validate_i18n.py` passes clean (Level 1: no MISSING_KEY, no PLACEHOLDER_MISMATCH across all locale files). Run after any ticket that adds or changes UI strings.
- [ ] App tested in `en-US`, `tr-TR`, and at least one RTL or non-Latin locale.
- [ ] Dates, numbers, currency rendered via `Intl` APIs with user locale.
- [ ] Pricing configured per country in RevenueCat dashboard.
- [ ] Data-hosting region (Fabrik VPS, EU) documented in privacy policy.
- [ ] No PII in AI agent prompts or external LLM calls.
- [ ] Both dark and light mode implemented. OS preference detected + manual toggle in Settings + preference persists in MMKV.
