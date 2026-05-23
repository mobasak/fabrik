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

**Two-faced scaffold:** the client (React Native app) builds via EAS and ships to stores. The backend (python-api + Supabase) deploys to VPS via Coolify with full registrar set. This file covers the **client lane**. Backend rules: `10-python.md`, `30-ops.md`, `55-observability.md`. For planning-level decisions (architecture, monetization, distribution, attribution), see `00-domain-mobile-app.md`.

---

## Architecture

- React Native with TypeScript is the mobile framework. The New Architecture (Fabric/JSI) is preferred when available — do not generate code relying on the legacy asynchronous JSON bridge.
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
  - **Supabase (primary backend):** use `supabase-js` wrapped in React Query hooks. Run `supabase gen types typescript` after every schema change and commit the generated types. Validate at the React Query boundary with Zod when input/output crosses a trust boundary.
  - **FastAPI (custom backend on VPS):** mirror Zod schemas with Pydantic to keep types aligned across the network boundary. Reserved for AI workflows, scraping, scheduled jobs, and anything that should not run client-side.
- **Global UI state:** Zustand. Avoid Redux boilerplate and standalone `React.Context` for high-frequency updates.
- **Local persistence:** `react-native-mmkv` for fast, synchronous key-value storage (30× faster than AsyncStorage via JSI memory-mapped files). Reserve `expo-sqlite` + Drizzle ORM for complex offline relational queries only.
- Never call Supabase or FastAPI directly from a screen component — wrap in a typed React Query hook.

---

## Backend Integration

- **Supabase is the primary data layer**: auth, app data, RLS, realtime, storage, edge functions.
- **Self-hosted Supabase on Coolify/Fabrik VPS for production**. Supabase Cloud is acceptable only for the first 2 weeks of prototyping while schema is unstable.
- All tables must have RLS enabled before any client query. No exceptions. Tables without RLS are blocked at code review.
- Auth: Supabase Auth with `expo-auth-session` for OAuth flows and `expo-secure-store` for token storage. Never store JWTs in AsyncStorage or MMKV.
- **FastAPI on VPS** is reserved for: AI workflows, scraping, third-party integrations requiring secrets, scheduled jobs, anything that should not run client-side.
- Auth handoff between Supabase and FastAPI: pass Supabase JWT in the `Authorization` header, validate server-side via Supabase JWKS.
- Default Supabase region: **`eu-central-1` (Frankfurt)** — satisfies GDPR, KVKK alignment, acceptable latency to USA and worldwide.
- Multi-region only when justified: deploy a second project (e.g., `us-east-1`) and route by user region at signup once any non-home region exceeds 5K MAU. Do not pre-shard.

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
- NativeWind / Tailwind for React Native is not recommended due to significant runtime overhead on mobile (up to 4× slower than raw `StyleSheet`).
- For complex adaptive theming with design tokens, `react-native-unistyles` (C++/JSI, zero re-render overhead) is the approved alternative.

### Ocoron Design System (Mobile)

- Apply Ocoron Design System color tokens (`ocoron-design-system.md`) via `react-native-unistyles` theme configuration. Same hex values as web, mapped to the unistyles theme object.
- Load **Space Grotesk** and **Inter** as custom fonts via `expo-font` or manual linking. Use **JetBrains Mono** for data/metrics displays only.
- Dark mode is the default. Light mode uses the Ocoron light surface token set, toggled via unistyles theme switching.
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
- Time zones: store all timestamps in **UTC** server-side. Render in user locale on the client via `date-fns-tz` or Temporal.
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

- **Unit / component:** `@testing-library/react-native` + Jest.
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
- **Builds**: EAS Build for all production iOS and Android binaries. No local Xcode/Android Studio builds for release. Define EAS profiles in `eas.json` (development, preview, production).
- **Submission**: EAS Submit to TestFlight and Play Console Internal Testing as the default first ring.
- **OTA updates**: Expo Updates for JS-only patches. Reserve full EAS rebuilds for native module changes. Channel strategy must match EAS profiles.
- **CI/CD**: trigger EAS builds via GitHub Actions on tag push. No manual builds in production.
- For backend Docker deployments (FastAPI on VPS), use `python:<version>-slim-bookworm`. Never use `alpine` (musl libc compilation failures, missing pre-built wheels).

---

## Monetization

See `81-mobile-billing.md` for the full mobile billing discipline: RevenueCat integration, entitlement architecture, server-side verification, Turkey GPB-mandatory constraint, Teknokent tax treatment, and launch checklist.

Key points for the client-side agent:

- **RevenueCat** is the entitlement server — free up to $2.5K MTR.
- Paywall components must support **remote config** via RevenueCat dashboard — never hardcode pricing or offering IDs.
- **"Restore Purchases" button is mandatory** on the paywall — omission = store rejection.
- Client-side entitlement checks are for UX only. **Server-side is the source of truth** (webhook → PostgreSQL).

---

## Push Notifications

- Use `expo-notifications` for cross-platform push. APNs (iOS) and FCM (Android) credentials managed via EAS.
- Never request push permission on first app launch. Defer until the user has experienced value (post-onboarding, after first meaningful action).
- Store device tokens in Supabase keyed to `user_id`. Send via Supabase Edge Function or FastAPI using the Expo Push API.
- Always include a deep link payload so taps route correctly via React Navigation `linking`.

---

## Compliance (Worldwide — GDPR / KVKK / CCPA / App Store)

The compliance baseline is **GDPR + EU AI Act** because they are the strictest. Apps that satisfy this floor satisfy KVKK, CCPA/CPRA, LGPD, and PIPEDA with regional addenda only.

### Mandatory in every build, every market

- Privacy policy and Terms of Service URLs configured in `app.json` and reachable from in-app Settings.
- Data export and account deletion endpoints implemented (Supabase Edge Function or FastAPI route), reachable from in-app Settings. Required by GDPR, CCPA, KVKK, and Apple App Store policy.
- **Apple Privacy Manifest** (`PrivacyInfo.xcprivacy`): declare every reason API and tracking domain. Required for App Store submission.
- **Play Data Safety form**: filled accurately in Play Console. Inaccuracies trigger removal.
- **Apple App Tracking Transparency (ATT)**: prompt before any IDFA collection or third-party tracking SDK fires. No exceptions, all markets.
- **GDPR consent gate**: no analytics, advertising, or non-essential third-party SDKs may fire before user consent. Use a CMP or built-in consent screen. Applies to all EU/EEA/UK users — detect via locale and IP.
- Encrypt PII at rest. Supabase handles this; for FastAPI VPS, use disk encryption + column-level encryption for sensitive fields.
- Never include PII in AI agent prompts or in any `chat text` sent to Gemini/Claude/OpenAI APIs from the app. Use `.aiexclude` and server-side redaction.
- Document the chosen Supabase region(s) in the privacy policy.

### Automated decision features (AI/ML)

If the app makes any AI-driven recommendation, score, match, classification, or auto-decision:

- Display a transparency notice ("This recommendation was generated automatically").
- Provide a manual override or "ask a human" path.
- Log override events server-side for regulator inquiries.
- Required by KVKK (Dec 2025 update), GDPR Art. 22, and EU AI Act. Treat as global default.

### Regional layers

- **EU/EEA/UK (GDPR + AI Act)**: full consent gate, DPA addendum required for any third-party processor, cookie/tracking notice on first launch in EU locales.
- **Turkey (KVKK)**: process Turkish-user PII on EU or Turkey-resident infrastructure. Manual override on automated decisions covered by global rule above.
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
| NativeWind / Tailwind CSS on mobile | `StyleSheet.create()` or `react-native-unistyles` |
| Legacy bridge-dependent native modules | New Architecture (Fabric/JSI) compatible modules |
| Manual edits to `android/` / `ios/` in Expo projects | Expo Config Plugins in `app.json` |
| Direct Supabase/FastAPI calls from screen components | Typed React Query hooks |
| Supabase tables without RLS | RLS enabled before any client query |
| Hardcoded user-facing strings | `i18next` translation files |
| Hardcoded prices or offering IDs | RevenueCat dashboard remote config |
| Push permission requested on first launch | Deferred until post-onboarding value moment |
| Tracking SDKs firing before ATT / GDPR consent | Gated behind explicit user consent |
| PII in AI agent prompts or external LLM calls | `.aiexclude` + server-side redaction |
| `any` type | `unknown` + type guards (per `20-typescript.md`) |
| `console.log()` in production builds | Sentry breadcrumbs or strip via babel plugin; dev-only in `__DEV__` guard |
| Firebase Dynamic Links | Dead (Aug 2025) — use ChottuLink or equivalent |

---

## Related Rule Packs

- `20-typescript.md` — TypeScript strict mode, type safety, module patterns
- `35-security-auth.md` — Pattern B (Supabase Auth), `expo-secure-store`, CORS
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
- [ ] Supabase types regenerated and committed (`supabase gen types`).
- [ ] All Supabase tables have RLS enabled.
- [ ] JWTs stored in `expo-secure-store`, not AsyncStorage or MMKV.
- [ ] EAS profiles defined in `eas.json` (development, preview, production).
- [ ] At least one MCP server wired and used in the verification loop.
- [ ] RevenueCat (or Adapty) integrated, paywall remote-configurable.
- [ ] Push permission requested post-onboarding, not on first launch.
- [ ] Privacy policy and ToS URLs in `app.json`, reachable from in-app Settings.
- [ ] Data export and account deletion endpoints implemented and reachable from in-app Settings.
- [ ] Apple Privacy Manifest (`PrivacyInfo.xcprivacy`) declares every reason API and tracking domain.
- [ ] Play Data Safety form filled accurately.
- [ ] ATT prompt fires before any IDFA / tracking SDK initializes (iOS).
- [ ] GDPR consent gate blocks analytics and non-essential SDKs until user consent (EU/EEA/UK locales).
- [ ] AI-driven decision features carry transparency notice + manual override path.
- [ ] All user-facing strings live in translation files — no hardcoded strings.
- [ ] App tested in `en-US`, `tr-TR`, and at least one RTL or non-Latin locale.
- [ ] Dates, numbers, currency rendered via `Intl` APIs with user locale.
- [ ] Pricing configured per country in RevenueCat dashboard.
- [ ] Single Supabase region documented in privacy policy; multi-region only deployed if user base justifies it.
- [ ] No PII in AI agent prompts or external LLM calls.
