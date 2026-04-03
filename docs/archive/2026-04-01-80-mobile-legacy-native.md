# ARCHIVED: Legacy Native Mobile UI Rules (Kotlin/Swift)

> **Superseded on 2026-04-01** by the React Native / TypeScript rewrite of `.windsurf/rules/80-mobile.md` (BUG-8).
> This file preserves the original Jetpack Compose / SwiftUI ruleset for historical reference.

---
activation: glob
globs: ["**/*.kt", "**/*.swift"]
description: Mobile UI patterns — Android (Compose/Material 3) and iOS (SwiftUI/HIG)
trigger: glob
---

# Mobile UI Rules

Apply when working on Android (Kotlin/Compose) or iOS (Swift/SwiftUI) code. Skip for Python, Docker, and web frontend files.

## Platform UI Framework

- Use Jetpack Compose with Material 3 on Android.
- Use SwiftUI with Apple Human Interface Guidelines on iOS.
- Share only non-UI logic through Kotlin Multiplatform when a shared mobile domain layer is needed.
- Do not share UI code across platforms unless Compose Multiplatform is an explicit project decision with platform-idiom discipline.

## State Management

- Use unidirectional data flow: state moves down and events move up.
- On Android, use `ViewModel` with `StateFlow` and collect with `collectAsStateWithLifecycle()`.
- On iOS, use an `@Observable` store, `@State` for transient UI state, and `@Binding` to pass source-of-truth state.
- Keep side effects out of view code and route them through scoped effect APIs.

## Navigation

- Use the Navigation component with Compose `NavHost` on Android.
- Use an adaptive Android scaffold that switches between bottom bar, navigation rail, and drawer by window size.
- Use `NavigationStack` for hierarchical iOS flows and avoid new `NavigationView` usage on iOS 16+.
- Use `NavigationSplitView` for multi-column iOS layouts that collapse cleanly on narrow sizes.
- Use tabs for three to five top-level domains and reserve modals for short focused tasks.

## Touch Targets

- Keep Android interactive controls at or above 48x48 dp hit area, expanding the target with padding when needed.
- Keep iOS interactive controls at or above 44x44 pt hit area.
- Never rely on color alone to convey state; combine text, iconography, and haptic feedback when appropriate.

## Lists & Scrolling

- Use `LazyColumn` and `LazyRow` for Android lists; do not use `Column` for large data sets.
- Provide stable `key` lambdas for Android lazy lists to reduce unnecessary recomposition.
- Use Paging 3 with `collectAsLazyPagingItems()` for paginated Android data.
- Use `LazyVStack` for large SwiftUI lists.
- In React Native surfaces, tune `FlatList` with `windowSize` and `initialNumToRender`, and avoid heavy rows or synchronous image decoding.

## Adaptive Layouts

- Apply Android window size classes from the start of the feature, not as a later retrofit.
- Use `Material3Adaptive` patterns that switch navigation structure automatically across compact, medium, and expanded sizes.
- Let `NavigationSplitView` collapse automatically on narrow iOS size classes.
- Never hardcode pixel sizes; use adaptive constraints and platform layout systems.

## Accessibility

- Meet minimum touch target sizes on both platforms: 48 dp on Android and 44 pt on iOS.
- Give every icon-only control a content description or `accessibilityLabel`.
- Use Compose `semantics {}` for Android accessibility metadata.
- Use SwiftUI `.accessibilityLabel()` and `.accessibilityRole()` for iOS accessibility metadata.
- Provide an accessible fallback control for any custom gesture interaction.
- Support Dynamic Type on iOS and font scaling on Android.

## Performance

- Ship Android Baseline Profiles for critical flows.
- Reduce unnecessary Android recomposition with `remember`, `derivedStateOf`, and stable state holders.
- Scope iOS `@Observable` objects narrowly so updates do not invalidate broad view trees.
- Use lazy stacks and lower update frequency on list-heavy iOS screens.
- Measure mobile performance with Macrobenchmark on Android and MetricKit on iOS.

## Done When

- [ ] All interactive controls meet minimum touch target sizes.
- [ ] Every icon-only control has an accessibility label.
- [ ] `LazyColumn` or `LazyVStack` is used for every large list surface.
- [ ] State is immutable `UiState` driven by a ViewModel or store.
- [ ] Navigation uses platform-recommended APIs such as `NavHost` and `NavigationStack`.
- [ ] Android Baseline Profiles ship for critical flows.
- [ ] No hardcoded pixel sizes remain in adaptive UI work.
