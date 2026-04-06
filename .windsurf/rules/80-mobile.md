---
activation: glob
globs: ["**/metro.config.*", "**/react-native.config.*"]
description: React Native mobile discipline — navigation, list performance, accessibility, platform-aware patterns
trigger: glob
---

# Mobile UI Rules (React Native)

Apply when working on React Native / TypeScript mobile projects. Skip for web frontend, Python, Docker, or infrastructure files. For general TypeScript discipline, see `TS_CORE` pack.

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
- Configure deep linking via React Navigation's `linking` prop. Prefer Universal Links (iOS) and App Links (Android) over custom URL schemes.
- Use tabs for three to five top-level destinations; reserve modals for short focused tasks.

---

## State Management

- Use unidirectional data flow: state flows down, events flow up.
- **Server/API state:** Use TanStack React Query for caching, deduplication, and optimistic updates against the FastAPI backend.
- **Global UI state:** Use Zustand. Avoid Redux boilerplate and standalone `React.Context` for high-frequency updates.
- **Local persistence:** Use `react-native-mmkv` for fast, synchronous key-value storage (30× faster than AsyncStorage via JSI memory-mapped files). Reserve `expo-sqlite` + Drizzle ORM only for complex offline relational queries.

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

## Ocoron Design System (Mobile)

- Apply Ocoron Design System color tokens (`ocoron-design-system.md`) via `react-native-unistyles` theme configuration. Same hex values as web, mapped to the unistyles theme object.
- Load **Space Grotesk** and **Inter** as custom fonts via `expo-font` or manual linking. Use **JetBrains Mono** for data/metrics displays only.
- Dark mode is the default. Light mode uses the Ocoron light surface token set, toggled via unistyles theme switching.
- Cards → `Pressable` list items with `translateY(1)` + `scale(0.98)` press feedback (`0.15s` duration).
- Tab bar → bottom navigation using `--color-accent` (`#00D4AA`) for the active tab indicator.
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
- Handle keyboard avoidance with `KeyboardAvoidingView` — use `behavior="padding"` on iOS, `behavior="height"` on Android.
- Never assume identical shadow rendering, status bar behavior, or keyboard dismiss behavior across platforms.

---

## Forms

- Use `react-hook-form` with `zod` resolvers for form validation. Uncontrolled components prevent full-form re-renders on every keystroke.
- Mirror Zod schemas with backend Pydantic schemas to maintain type alignment across the network boundary.

---

## Testing

- **Unit / component:** `@testing-library/react-native` + Jest.
- **E2E automation:** Maestro (declarative YAML flows targeting `testID` attributes, stored in `.maestro/` directory). Maestro handles implicit waits for network and animations, reducing flakiness vs Detox/Appium.

---

## Build & Dev Workflow

- Use Metro bundler for development (`npx react-native start`).
- Test on physical devices for performance-critical features — simulators hide real-world frame drops and thermal throttling.
- For backend Docker deployments, use `python:<version>-slim-bookworm`. Never use `alpine` (musl libc compilation failures, missing pre-built wheels).

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
| NativeWind / Tailwind CSS on mobile | `StyleSheet.create()` or `react-native-unistyles` |
| Legacy bridge-dependent native modules | New Architecture (Fabric/JSI) compatible modules |
| Manual edits to `android/` / `ios/` in Expo projects | Expo Config Plugins in `app.json` |
| `any` type | `unknown` + type guards (per `TS_CORE`) |

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
