---
activation: glob
globs: ["**/metro.config.*", "**/react-native.config.*", "**/app.json", "**/app.config.*", "**/eas.json"]
description: Mobile component patterns for every mobile-app project — list items, bottom and action sheets, search, navigation header, onboarding, forms — built on the template's token slots; a house brand's values (Ocoron's fonts) apply only where the project declares it
trigger: glob
currency_pass: 2026-10-01
---
<!-- CONSUMER: coding agents building React Native UI in a mobile-app project
     GOAL: the mobile component patterns — how the template's slots and structure become touch UI
     AGENT USAGE: build against the slot NAMES (`--surface-2`, `--color-danger-text`, heading font, body font); the VALUES come from the project's docs/design-system.md. -->

# Mobile Component Patterns

> The mobile component patterns: how `core/design-system-template.md`'s slots and structure become touch UI in a React Native app. `mobile-app/80-mobile.md` owns the architecture (styling engine, navigation, accessibility, platform patterns); this file owns the components.

**Applies to:** every mobile-app project. The patterns are brand-neutral: they name the template's slots (`--surface-1`, `--text-muted`, `--color-danger-text`, the heading and body font roles) and the project's design system fills them — resolved by the ladder in `saas/60-saas-ui.md`, a house brand only by explicit declaration (D-051). On an Ocoron-declared project the heading font is Space Grotesk and the body font Inter (`core/ocoron-design-system.md` § Typography); the scaffold embeds Inter only, so add `@expo-google-fonts/space-grotesk` and list its 600 and 700 weights in the `expo-font` plugin block of `app.config.ts`. The file name is historical: the Tojlo mobile pack extends this file by name.

**The emitted theme is not yet this contract.** The scaffold's `src/global.css` fills its `@theme` with Ocoron's values by default and predates the template's `-fg`, `-text` and `--border-control` slots. Before building these patterns, re-fill that `@theme` from the project's resolved design system — colours and fonts — and add the missing slots (`80-mobile.md` § Styling).

**Sizes** are density-independent (pt on iOS, dp on Android) at the default text size. Type follows the OS text-size setting (`80-mobile.md` § Accessibility): never `allowFontScaling={false}`, and let rows grow with their text. **Colours** follow the template's slot roles: an accent or state colour used AS TEXT or an icon on a surface is its `-text` slot (`--color-accent-text`, `--color-danger-text`); text or an icon ON a fill is its `-fg` slot; a control's boundary is `--border-control`. No raw hex, no "white".

---

## 1. List Item Anatomy

The fundamental mobile UI unit. Every data list, settings screen, and feed uses this pattern, rendered through the scaffold's `List` (`@shopify/flash-list`, `src/components/ui/list.tsx`).

### Structure

```
┌─────────────────────────────────────────────────────────┐
│ [Leading]  Title                          [Trailing]    │
│            Subtitle (optional)                          │
├─────────────────────────────────────────────────────────┤  ← 1px inset separator
```

- **Leading:** icon (20) OR avatar (36, circle) OR checkbox
- **Content:** title (body font 500, 15, `--text-primary`) + optional subtitle (body font 400, 13, `--text-body`)
- **Trailing:** value/meta text (body font 400, 13, `--text-muted`) OR chevron (16) OR toggle OR badge
- **Separator:** 1px `--border`, inset from leading edge (not full-width)
- **Press feedback:** `translateY(1px) scale(0.98)` + light haptic (`expo-haptics`, template § Motion Language)

### Heights

| Variant | Minimum height | When |
|---|---|---|
| Single-line | 48 | Title only (settings, simple lists) |
| Two-line | 64 | Title + subtitle (contacts, notifications) |
| Three-line | 80 | Title + subtitle + thumbnail preview |

### Section Headers

- Body font 500, 13, uppercase, letter-spacing 1, `--text-muted`
- Background: `--surface-0`, sticky top within scroll view
- Padding: 8 vertical, 16 horizontal

### Swipe Actions

Built with `ReanimatedSwipeable` (`react-native-gesture-handler/ReanimatedSwipeable` — the older `Swipeable` is deprecated). Directions are for a left-to-right layout; mirror them under RTL (the scaffold ships Arabic).

- **Trailing actions** (the row slides left, `renderRightActions`): destructive (delete/archive) — `--color-danger` fill, icon in `--color-danger-fg`
- **Leading actions** (the row slides right, `renderLeftActions`): the primary action (pin/mark read) — `--color-accent` fill, icon in `--color-accent-fg`
- Max 1 action per direction. No multi-action swipe drawers
- Swipe threshold: 80 before the action commits (`leftThreshold` / `rightThreshold`)
- Haptic: medium impact at threshold

### List Item Rules

- **LI1:** Every list item meets the 48 minimum height — the Material touch-target floor, above iOS's 44 (`80-mobile.md` § Accessibility).
- **LI2:** Chevron (›) means "navigates to detail screen." No chevron = action is inline (toggle, checkbox, or non-navigating).
- **LI3:** Every swipe action is also reachable without the gesture: in a long-press menu AND as an `accessibilityActions` entry handled by `onAccessibilityAction`, so a screen-reader user gets it from the actions rotor. Apple asks for an alternative to every gesture.
- **LI4:** A reversible destructive swipe (archive, soft delete) gets an undo toast (4s), not a confirmation dialog. An irreversible one (permanent deletion of data or the account) confirms first — Material's confirmation guidance keeps the dialog for actions that cannot be undone.
- **LI5:** Loading state: skeleton rows matching the list item height. Never a spinner in place of a list — the scaffold's `EmptyList` shows an `ActivityIndicator` while loading; replace it.
- **LI6:** Empty list: centered empty state (icon 48 + heading + subtitle + CTA). Never show a blank scroll view.

---

## 2. Bottom Sheet

Replaces modal and drawer on mobile. Used for filters, forms, detail views, confirmations. The scaffold's `Modal` (`src/components/ui/modal.tsx`) wraps `@gorhom/bottom-sheet`'s `BottomSheetModal`: it defaults to a single 60% snap point (pass `snapPoints`), forces `enableDynamicSizing={false}`, leaves drag-to-dismiss off (`enablePanDownToClose` defaults to false — pass it) and draws its own scrim at 0.4 that closes on tap. Raise the scrim to the template's 0.6; a content-height sheet needs `BottomSheetModal` directly or a wrapper that stops forcing dynamic sizing off.

### Structure

```
┌────────────────────────────────────┐
│          ━━━━━━━━━━━━━             │  ← drag handle
│                                    │
│  [Sheet content]                   │
│                                    │
│                                    │
└────────────────────────────────────┘
```

- **Drag handle:** 36 × 4, `--border`, centered, radius 2, 8 from top
- **Background:** `--surface-2`
- **Corner radius:** 12 top-left/right, 0 bottom
- **Scrim:** black at 0.6 opacity (template § Motion Language — the modal scrim), tap to dismiss
- **Max height:** 90% of screen. Content scrolls internally
- **Snap points:** half (50%) and full (90%), with `enableDynamicSizing={false}`. No arbitrary heights

### Sizes

| Size | Use case | Behavior |
|---|---|---|
| **Small** | Confirmation, single action | Content-height (dynamic sizing), no snap, max 30% |
| **Medium** | Filters, short forms | Snaps to 50%, expandable to 90% |
| **Large** | Detail views, long forms | Opens at 90% |

### Animation

- **Enter:** `translateY(100%) → snap point`, `--motion-slow`, `--ease-emphasis` (template § Motion Language)
- **Dismiss:** reverse, or swipe-down velocity dismiss (threshold: 500/s)
- **Scrim:** opacity `0 → 0.6` in `--motion-fast`

### Bottom Sheet Rules

- **BS1:** Bottom sheets are NEVER nested. If a sheet needs sub-navigation, use an in-sheet tab bar or push to a new screen. (The library can stack modals; this house rule forbids it.)
- **BS2:** Destructive actions inside a sheet require inline confirmation (a `--color-danger` fill button with `--color-danger-fg` text + an "Are you sure?" line), not a nested sheet.
- **BS3:** Form sheets save on explicit "Done" button (top-right). Dismiss = discard with "Discard changes?" prompt if dirty state detected.
- **BS4:** A sheet is dismissible by drag down (`enablePanDownToClose`), tap on the scrim, and the Android back gesture. `@gorhom/bottom-sheet` does not handle back itself: register a `BackHandler` listener while the sheet is open that closes it and returns `true`. Current Android makes predictive back the default for apps targeting its API level; the scaffold leaves Expo's `android.predictiveBackGestureEnabled` off — before turning it on, re-verify the sheet's back-close on a device at that API level. Never trap the user.
- **BS5:** Sheet title (body font 500, 16, `--text-primary`) is required. Centered, with optional close (X) icon top-right.

---

## 3. Action Sheet

Replaces dropdown menus and context menus on mobile. Triggered by overflow button, long-press, or explicit "More" action. The scaffold's `Select` (`src/components/ui/select.tsx`) is the starting point — options in the bottom-sheet `Modal` — but has no Cancel row, no destructive row, no icons and shorter rows: add them.

### Structure

```
┌────────────────────────────────────┐
│          ━━━━━━━━━━━━━             │
│                                    │
│  [icon]  Delete                    │  48, --color-danger-text
│ ────────────────────────────────── │
│  [icon]  Option label              │  48
│  [icon]  Option label              │  48
│                                    │  8 gap
│          Cancel                    │  48, --text-muted
└────────────────────────────────────┘
```

- Appears as a bottom sheet (small size, content-height)
- **Option rows:** 48 high, leading icon (20, `--text-body`) + label (body font 400, 15, `--text-primary`)
- **Cancel button:** separated by an 8 gap at the bottom, body font 500, `--text-muted`, full-width, center-aligned
- **Destructive option:** first, separated from the rest by a divider, text and icon in `--color-danger-text`

### Animation

Same as bottom sheet small — slide up from bottom, `--motion-slow`, `--ease-emphasis`.

### Action Sheet Rules

- **AS1:** Max 6 options — an action sheet should never scroll. More than 6 = redesign the feature, not the sheet.
- **AS2:** Icons are optional, but if one option has an icon, all must have one.
- **AS3:** Destructive options go first, where they are most noticeable (Apple's placement), in `--color-danger-text` with a matching icon, set apart by a divider. This deliberately differs from the web row-action menu, where Delete is last (`design-system-template.md` § Row Actions).
- **AS4:** Cancel is always present, at the bottom. The back gesture also dismisses (BS4).
- **AS5:** Option labels are verbs or verb phrases: "Delete", "Share", "Copy link" — never nouns alone.

---

## 4. Mobile Search

Full-screen search replacing the command palette. Triggered by search icon in tab bar or navigation header.

### Structure

```
┌────────────────────────────────────┐
│ ← │ 🔍 Search…                  X │  ← top bar, auto-focused input
├────────────────────────────────────┤
│ Recent searches                    │  ← section header
│   [clock] Previous query     ×     │
│   [clock] Previous query     ×     │
├────────────────────────────────────┤
│ Results                            │
│   [icon] Result item         ›     │  ← uses list item anatomy
│   [icon] Result item         ›     │
└────────────────────────────────────┘
```

- **Full-screen screen** on `--surface-0`
- **Top bar:** back arrow (←, `--color-accent-text`) + search input (auto-focused, full width) + clear (X) button when input has text
- **Input:** body font 400, 16, `--surface-1` background, 40 high, radius `--radius-button`, 1px `--border-control` boundary
- **Results:** list items (§ 1), grouped by category with section headers
- **Recent searches:** the latest 5 shown before typing, individually clearable (× button)
- **Empty state:** "No results for '[query]'" centered, `--text-muted`, with suggestion text below

### Animation

- **Enter:** push from right (standard stack navigation transition)
- **Keyboard:** opens immediately on screen enter

### Mobile Search Rules

- **SR1:** Search input text is at least 16. A native `TextInput` never zooms, but react-native-web in iOS Safari zooms the page on focus below 16 — and 16 is the form size anyway (§ 7).
- **SR2:** Results update as user types with 300ms debounce for server queries. Local/cached results appear instantly.
- **SR3:** Recent searches persist in MMKV (`react-native-mmkv`, through the scaffold's `src/lib/storage.tsx`): keep 10, FIFO eviction, show 5. Clear all via "Clear recent" link.
- **SR4:** "Cancel" / back arrow clears input AND dismisses search screen.
- **SR5:** If search supports multiple categories (contacts, invoices, settings), show category tabs below the input bar.

---

## 5. Navigation Header

Top bar for stack screens — the native header of expo-router's `Stack` (react-native-screens), configured through screen `options`. Never hand-roll a header bar: the platform sets its height (44 on iOS; 64 for Material's current top app bar — 56 is its old height), safe-area inset and back behaviour.

### Structure

```
┌────────────────────────────────────────────────┐
│ [safe area inset top]                          │
├────────────────────────────────────────────────┤
│  ← Back    Screen Title         [action] [⋮]  │  platform height
├────────────────────────────────────────────────┤
│  [optional border-bottom 1px --border]         │
```

- **Background:** `--surface-1` OR transparent (`headerTransparent`, for hero-scroll patterns where content scrolls under)
- **Back button:** the native one, tinted `--color-accent-text`
  - iOS: the previous screen's title, which the system shortens to "Back" or the arrow alone when space runs out (`headerBackButtonDisplayMode`); set `headerBackTitle` only to replace a long title
  - Android: arrow only, no label
- **Title:** centered (iOS) / leading-aligned after back (Android — Material's small top app bar), body font 500, 16, `--text-primary`
- **Right actions:** max 2 icon buttons (20, `--text-body`), 44 touch target each. Overflow → action sheet
- **Border bottom:** 1px `--border` (omit if transparent header with hero-scroll)

### Large Title (Scroll-Collapse Pattern)

Used on root/primary screens (Home, Settings) for hierarchy emphasis.

- iOS: `headerLargeTitleEnabled: true` — the system collapses the large title into the inline one as the screen scrolls; the content must be a scroll view (`ScrollView`, the `List`) that fills the screen, is the screen's first child (or sits in a wrapper with `collapsable={false}`) and sets `contentInsetAdjustmentBehavior="automatic"`. `<Stack.Title large>` is the composition-API equivalent; `headerLargeTitle` is the deprecated name. Style it with the heading font, 700, via `headerLargeTitleStyle`
- Android has no large-title header: the title stays in the bar

### Navigation Header Rules

- **NH1:** Never put more than 2 action icons in the header. Third+ actions go in ⋮ → action sheet.
- **NH2:** Back button must always be present on non-root screens. Never rely on swipe-back gesture alone (accessibility).
- **NH3:** Title must reflect the current screen content. Never show the app name on stack screens — only root/tab screens show the product name.
- **NH4:** Transparent headers must transition to opaque `--surface-1` with border on scroll (threshold: 1). Content must never be illegible under the header.

---

## 6. Swipeable Onboarding

First-run experience for new users before signup. Replaces the web stepper wizard. The scaffold's `src/features/onboarding/onboarding-screen.tsx` is a one-page placeholder that then opens `/login`; replace its content with these pages, keeping that order.

### Structure

```
┌────────────────────────────────────┐
│                              Skip  │  ← top-right
│                                    │
│         [illustration]             │  ← top 40%, max 200
│                                    │
│     Heading (24, bold)             │
│     Body text (15, max 2 lines)    │
│                                    │
│           ● ○ ○ ○ ○               │  ← dot indicators
│                                    │
│     [ Get started ]                │  ← final page only: full-width CTA
└────────────────────────────────────┘
```

- **Full-screen pages:** 3-5, horizontal swipe (scroll snap)
- **Illustration:** top 40% of screen, max 200 high, monochrome line-art matching the icon set. Optional — text-only is acceptable for MVP
- **Heading:** heading font 700, 24, `--text-primary`, center-aligned
- **Body:** body font 400, 15, `--text-body`, center-aligned, max 2 lines, padding 0 32
- **Dot indicators:** bottom-center, 8 inactive dots (`--text-muted` — they carry state, so not the decorative `--border`), active dot = 16 pill (`--color-accent`)
- **Skip button:** top-right, body font 400, 14, `--text-muted`, "Skip"
- **Final page:** CTA button replaces skip — "Get started" primary button, full-width (with 16 horizontal padding), 48 high

### Animation

- **Page transition:** horizontal scroll snap, `ScrollView` with `pagingEnabled`
- **Dot indicator:** width animation inactive 8 → active 16 pill, `--motion-fast`
- **Illustration:** optional fade-in per page, `--motion-default`

### Onboarding Rules

- **ON1:** Max 5 pages. If you need more content, cut — users skip verbose onboarding.
- **ON2:** Every page is skippable. Never gate signup behind reading all pages.
- **ON3:** Illustrations are optional. Never block shipping because illustrations aren't ready. Text-only is fine for v1.
- **ON4:** Value before signup — show onboarding BEFORE asking for account creation. The user should understand the product's value proposition before committing credentials.
- **ON5:** Dot indicators are tap-navigable (tap a dot to jump to that page).
- **ON6:** Do not auto-advance pages. The user controls the pace.

---

## 7. Mobile Form Inputs

Adapts `design-system-template.md` § Forms and Inline Editing for touch interaction. Only **deltas from web** are specified here — all other form rules (labels above, validation on blur, error messages below, dirty state) apply unchanged. Form state uses the scaffold's `@tanstack/react-form` (`80-mobile.md`).

### Input Sizing

| Property | Web | Mobile | Why |
|---|---|---|---|
| Input height | 40 | **48** | Touch target minimum |
| Font size | 14 | **16** | Legible while typing; also stops react-native-web's iOS Safari zoom |
| Field spacing | 12 | **16** (`--space-md`) | Thumb-friendly tap targets |

### Pickers and Selectors

| Web pattern | Mobile replacement | Why |
|---|---|---|
| `<select>` dropdown | **Action sheet** (§ 3 — the scaffold's `Select`) | Dropdowns are unusable on mobile |
| Date picker (calendar widget) | **Native platform picker** — `@react-native-community/datetimepicker` (Android: a calendar dialog; iOS: compact, inline or spinner); not in the scaffold — `npx expo install @react-native-community/datetimepicker`, or `@expo/ui`'s drop-in `DateTimePicker` (Compose and SwiftUI, Material's current look on Android) | Users know their platform's picker |
| Multi-select dropdown | **Full-screen selection list** with checkboxes + "Done" button | Need space for many options |
| Color picker | **Grid of swatches** in a bottom sheet | No freeform color on mobile |

### Keyboard Configuration

- `keyboardType` must match the field: `email-address`, `phone-pad`, `numeric`, `decimal-pad`, `url`
- `returnKeyType`: "next" for all fields except the last, which uses "done" or "send"; pair "next" with `submitBehavior="submit"` and focus the next field in `onSubmitEditing` (`blurOnSubmit` is deprecated)
- `autoCapitalize`: "none" for email/username, "sentences" for free text, "words" for names
- `autoComplete` on every standard field (email, password, name, phone) — it drives autofill on both platforms. Set the iOS-only `textContentType` only to override it, never both: `textContentType` wins when both are set

### Keyboard Avoidance

- Use `react-native-keyboard-controller` (`80-mobile.md` § Platform-Aware Patterns — the core `KeyboardAvoidingView` misbehaves under Android edge-to-edge): `KeyboardAwareScrollView` for a form, `KeyboardStickyView` for a footer that rides above the keyboard, `KeyboardToolbar` for previous/next/done between fields
- Submit button must remain visible above the keyboard at all times
- Tapping outside any input dismisses the keyboard (`keyboardShouldPersistTaps="handled"` on the scroll view)

### Mobile Form Rules

- **MF1:** Never use a custom date/time picker when the native platform one exists. Users know their platform's picker — custom pickers add friction.
- **MF2:** Form submit button must be above the keyboard, never hidden behind it. Use `react-native-keyboard-controller`'s `KeyboardAwareScrollView` or a `KeyboardStickyView` footer.
- **MF3:** Tapping outside an input dismisses the keyboard. Never trap keyboard focus.
- **MF4:** Long forms (>5 fields) use sections with sticky section headers, not one infinite scroll.
- **MF5:** Numeric inputs (amount, quantity) use `keyboardType="decimal-pad"` — never the full keyboard for numbers.
- **MF6:** Password fields include a show/hide toggle (eye icon, trailing, 44 touch target).

---

## Relation to the template

`design-system-template.md` § Scaffold Adaptation Matrix keeps one mobile-app row and hands the mobile mapping to `80-mobile.md` and this file; this file is the full mobile component spec.

---

## Rules Summary (Quick Reference)

| ID | Rule |
|---|---|
| LI1 | List items >= 48 high |
| LI2 | Chevron = navigates; no chevron = inline action |
| LI3 | Swipe actions also in long-press menu and accessibility actions |
| LI4 | Reversible destructive swipe → undo toast; irreversible → confirm |
| LI5 | Loading = skeleton rows |
| LI6 | Empty list = centered empty state with CTA |
| BS1 | Never nest bottom sheets |
| BS2 | Destructive actions = inline confirmation |
| BS3 | Form sheets need explicit "Done" |
| BS4 | Always dismissible (drag/scrim/back — wire BackHandler) |
| BS5 | Sheet title required |
| AS1 | Max 6 options, never scrolls |
| AS2 | All icons or no icons |
| AS3 | Destructive first, in the danger text colour |
| AS4 | Cancel always present, at the bottom |
| AS5 | Labels are verbs |
| SR1 | Search input >= 16 |
| SR2 | 300ms debounce on server queries |
| SR3 | Recent searches in MMKV, keep 10, show 5 |
| SR4 | Cancel dismisses search screen |
| SR5 | Category tabs for multi-type search |
| NH1 | Max 2 header actions |
| NH2 | Back button always present (non-root) |
| NH3 | Title = screen content, not app name |
| NH4 | Transparent headers → opaque on scroll |
| ON1 | Max 5 onboarding pages |
| ON2 | Every page skippable |
| ON3 | Illustrations optional |
| ON4 | Value before signup |
| ON5 | Dots are tap-navigable |
| ON6 | No auto-advance |
| MF1 | Use native pickers |
| MF2 | Submit button above keyboard |
| MF3 | Tap outside dismisses keyboard |
| MF4 | Long forms use sectioned layout |
| MF5 | Numeric fields use numeric keyboard |
| MF6 | Password fields have show/hide toggle |

## Draft Persistence — nothing typed or AI-generated is EVER lost (fleet mandate 2026-08-13)

Every form/wizard/editor/AI-populated surface persists its full working state **continuously on
change** (debounce ≤1s + flush on blur/hide/background) to MMKV (the scaffold's `src/lib/storage.tsx`; drafts only — tokens stay in `expo-secure-store`); **restore is automatic and
silent** on every return path (Back, reopened app, crash, days-old session) — the
user continues down to the last letter typed. The draft clears on exactly ONE event: successful
creation/submission of the entity (or explicit user discard). Canonical detail:
`core/design-system-template.md` § Save Behavior.
