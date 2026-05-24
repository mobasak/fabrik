---
activation: glob
globs: ["**/metro.config.*", "**/react-native.config.*", "**/app.json", "**/eas.json"]
description: Ocoron Mobile Design System — component patterns, navigation, interaction specs for React Native
trigger: glob
---
<!-- CONSUMER: Coding agents building React Native mobile UI
     GOAL: Mobile-specific component patterns, navigation, interaction — extends ocoron-design-system.md
     TRAYCER USAGE: Injects as Context File for mobile client-lane UI tickets.
     AGENT USAGE: Use alongside ocoron-design-system.md. This file specifies mobile deltas only. -->

# Ocoron Mobile Design System

> Mobile-specific component patterns and interaction specs. Extends `ocoron-design-system.md` — all tokens (colors, typography, spacing, motion) are inherited from there. This file defines **how** those tokens manifest on mobile surfaces.

**Applies to:** React Native projects using `react-native-unistyles` for theming. Both dark and light mode are mandatory (see `80-mobile.md` § Styling for detection + toggle + persistence mechanism). See `80-mobile.md` for architecture rules and `ocoron-design-system.md` for the full token system.

---

## 1. List Item Anatomy

The fundamental mobile UI unit. Every data list, settings screen, and feed uses this pattern.

### Structure

```
┌─────────────────────────────────────────────────────────┐
│ [Leading]  Title                          [Trailing]    │
│            Subtitle (optional)                          │
├─────────────────────────────────────────────────────────┤  ← 1px inset separator
```

- **Leading:** icon (20px) OR avatar (36px circle) OR checkbox
- **Content:** title (Inter 500, 15px, `--text-primary`) + optional subtitle (Inter 400, 13px, `--text-body`)
- **Trailing:** value/meta text (Inter 400, 13px, `--text-muted`) OR chevron (16px) OR toggle OR badge
- **Separator:** 1px `--border`, inset from leading edge (not full-width)
- **Press feedback:** `translateY(1px) scale(0.98)` + light haptic

### Heights

| Variant | Height | When |
|---|---|---|
| Single-line | 48px | Title only (settings, simple lists) |
| Two-line | 64px | Title + subtitle (contacts, notifications) |
| Three-line | 80px | Title + subtitle + thumbnail preview |

### Section Headers

- Font: Inter 500, 13px, uppercase, letter-spacing 1px, `--text-muted`
- Background: `--surface-0`, sticky top within scroll view
- Padding: 8px 16px

### Swipe Actions

- **Left swipe:** destructive action (delete/archive) — `--color-danger` background, white icon
- **Right swipe:** primary action (pin/mark read) — `--color-accent` background, white icon
- Max 1 action per direction. No multi-action swipe drawers
- Swipe threshold: 80px before action commits
- Haptic: medium impact at threshold

### List Item Rules

- **LI1:** Every list item must meet 48px minimum height (touch target).
- **LI2:** Chevron (›) means "navigates to detail screen." No chevron = action is inline (toggle, checkbox, or non-navigating).
- **LI3:** Swipe actions must also be accessible via long-press context menu (accessibility fallback).
- **LI4:** Destructive swipe requires undo toast (4s), not a confirmation dialog.
- **LI5:** Loading state: skeleton rows matching the list item height. Never show a spinner in place of a list.
- **LI6:** Empty list: centered empty state (icon 48px + heading + subtitle + CTA). Never show a blank scroll view.

---

## 2. Bottom Sheet

Replaces modal and drawer on mobile. Used for filters, forms, detail views, confirmations.

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

- **Drag handle:** 36px x 4px, `--border` color, centered, border-radius 2px, 8px from top
- **Background:** `--surface-2`
- **Border-radius:** 12px top-left/right, 0 bottom
- **Scrim:** `rgba(0,0,0,0.6)`, tap to dismiss
- **Max height:** 90% of screen. Content scrolls internally
- **Snap points:** half (50%) and full (90%). No arbitrary heights

### Sizes

| Size | Use case | Behavior |
|---|---|---|
| **Small** | Confirmation, single action | Content-height, no snap, max 30% |
| **Medium** | Filters, short forms | Snaps to 50%, expandable to 90% |
| **Large** | Detail views, long forms | Opens at 90% |

### Animation

- **Enter:** `translateY(100%) → snap point`, `--motion-slow` (250ms), `--ease-emphasis`
- **Dismiss:** reverse, or swipe-down velocity dismiss (threshold: 500px/s)
- **Scrim:** opacity `0 → 0.6` in `--motion-fast` (100ms)

### Bottom Sheet Rules

- **BS1:** Bottom sheets are NEVER nested. If a sheet needs sub-navigation, use an in-sheet tab bar or push to a new screen.
- **BS2:** Destructive actions inside a sheet require inline confirmation (red button + "Are you sure?" text), not a nested sheet.
- **BS3:** Form sheets save on explicit "Done" button (top-right). Dismiss = discard with "Discard changes?" prompt if dirty state detected.
- **BS4:** Sheet must be dismissible by: drag down, tap scrim, or back gesture. Never trap the user.
- **BS5:** Sheet title (Inter 500, 16px, `--text-primary`) is required. Centered, with optional close (X) icon top-right.

---

## 3. Action Sheet

Replaces dropdown menus and context menus on mobile. Triggered by overflow button, long-press, or explicit "More" action.

### Structure

```
┌────────────────────────────────────┐
│          ━━━━━━━━━━━━━             │
│                                    │
│  [icon]  Option label              │  48px
│  [icon]  Option label              │  48px
│  [icon]  Delete                    │  48px, --color-danger
│                                    │  8px gap
│          Cancel                    │  48px, --text-muted
└────────────────────────────────────┘
```

- Appears as a bottom sheet (small size, content-height)
- **Option rows:** 48px height, leading icon (20px, `--text-body`) + label (Inter 400, 15px, `--text-primary`)
- **Cancel button:** separated by 8px gap at bottom, Inter 500, `--text-muted`, full-width, center-aligned
- **Destructive option:** always last before cancel, text and icon in `--color-danger`

### Animation

Same as bottom sheet small — slide up from bottom, `--motion-slow`, `--ease-emphasis`.

### Action Sheet Rules

- **AS1:** Max 6 options. More than 6 = redesign the feature, not the sheet.
- **AS2:** Icons are optional, but if one option has an icon, all must have one.
- **AS3:** Destructive options get `--color-danger` text + matching icon. Never place destructive actions first.
- **AS4:** Cancel is always present. Hardware back gesture also dismisses.
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

- **Full-screen overlay** on `--surface-0`
- **Top bar:** back arrow (←, `--color-accent`) + search input (auto-focused, full width) + clear (X) button when input has text
- **Input:** Inter 400, **16px** (prevents iOS zoom), `--surface-1` background, 40px height, border-radius 8px, no border
- **Results:** list items (using § List Item Anatomy), grouped by category with section headers
- **Recent searches:** shown before typing, max 5, individually clearable (× button), stored in MMKV
- **Empty state:** "No results for '[query]'" centered, `--text-muted`, with suggestion text below

### Animation

- **Enter:** push from right (standard stack navigation transition)
- **Keyboard:** opens immediately on screen enter

### Mobile Search Rules

- **SR1:** Input font must be >= 16px to prevent iOS Safari-style auto-zoom on focus.
- **SR2:** Results update as user types with 300ms debounce for server queries. Local/cached results appear instantly.
- **SR3:** Recent searches persist in MMKV (max 10, FIFO eviction). Clear all via "Clear recent" link.
- **SR4:** "Cancel" / back arrow clears input AND dismisses search screen.
- **SR5:** If search supports multiple categories (contacts, invoices, settings), show category tabs below the input bar.

---

## 5. Navigation Header

Top bar for stack navigation screens (non-root screens pushed onto the navigation stack).

### Structure

```
┌────────────────────────────────────────────────┐
│ [safe area inset top]                          │
├────────────────────────────────────────────────┤
│  ← Back    Screen Title         [action] [⋮]  │  44px (iOS) / 56px (Android)
├────────────────────────────────────────────────┤
│  [optional border-bottom 1px --border]         │
```

- **Height:** 44px content (iOS) / 56px content (Android) — safe area insets above
- **Background:** `--surface-1` OR transparent (for hero-scroll patterns where content scrolls under)
- **Back button:** left-aligned, chevron icon (‹) 24px, `--color-accent`
  - iOS: optional previous screen title as label (truncated to 12 chars)
  - Android: arrow only, no label
- **Title:** centered (iOS) / left-aligned after back (Android), Inter 500, 16px, `--text-primary`
- **Right actions:** max 2 icon buttons (20px, `--text-body`), 44px touch target each. Overflow → action sheet
- **Border bottom:** 1px `--border` (omit if transparent header with hero-scroll)

### Large Title (Scroll-Collapse Pattern)

Used on root/primary screens (Home, Settings) for hierarchy emphasis.

- Title starts large: Space Grotesk 700, 28px, left-aligned, below the standard header bar
- On scroll: collapses into the standard centered/left title in the header bar
- Collapse threshold: 60px scroll offset
- Animation: crossfade title between positions, `--motion-fast` (100ms)

### Navigation Header Rules

- **NH1:** Never put more than 2 action icons in the header. Third+ actions go in ⋮ → action sheet.
- **NH2:** Back button must always be present on non-root screens. Never rely on swipe-back gesture alone (accessibility).
- **NH3:** Title must reflect the current screen content. Never show the app name on stack screens — only root/tab screens show the product name.
- **NH4:** Transparent headers must transition to opaque `--surface-1` with border on scroll (threshold: 1px). Content must never be illegible under the header.

---

## 6. Swipeable Onboarding

First-run experience for new users before signup. Replaces the web stepper wizard.

### Structure

```
┌────────────────────────────────────┐
│                              Skip  │  ← top-right
│                                    │
│         [illustration]             │  ← top 40%, max 200px
│                                    │
│     Heading (24px, bold)           │
│     Body text (15px, max 2 lines)  │
│                                    │
│           ● ○ ○ ○ ○               │  ← dot indicators
│                                    │
│     [ Get started ]                │  ← final page only: full-width CTA
└────────────────────────────────────┘
```

- **Full-screen pages:** 3-5, horizontal swipe (scroll snap)
- **Illustration:** top 40% of screen, max 200px height, monochrome line-art matching Lucide style. Optional — text-only is acceptable for MVP
- **Heading:** Space Grotesk 700, 24px, `--text-primary`, center-aligned
- **Body:** Inter 400, 15px, `--text-body`, center-aligned, max 2 lines, padding 0 32px
- **Dot indicators:** bottom-center, 8px inactive dots (`--border`), active dot = 16px pill (`--color-accent`)
- **Skip button:** top-right, Inter 400, 14px, `--text-muted`, "Skip"
- **Final page:** CTA button replaces skip — "Get started" primary button, full-width (with 16px horizontal padding), 48px height

### Animation

- **Page transition:** horizontal scroll snap, native `ScrollView` paging
- **Dot indicator:** width animation inactive 8px → active 16px pill, `--motion-fast` (100ms)
- **Illustration:** optional fade-in per page, `--motion-default` (150ms)

### Onboarding Rules

- **ON1:** Max 5 pages. If you need more content, cut — users skip verbose onboarding.
- **ON2:** Every page is skippable. Never gate signup behind reading all pages.
- **ON3:** Illustrations are optional. Never block shipping because illustrations aren't ready. Text-only is fine for v1.
- **ON4:** Value before signup — show onboarding BEFORE asking for account creation. The user should understand the product's value proposition before committing credentials.
- **ON5:** Dot indicators are tap-navigable (tap a dot to jump to that page).
- **ON6:** Do not auto-advance pages. The user controls the pace.

---

## 7. Mobile Form Inputs

Adapts `ocoron-design-system.md` § Forms for touch interaction. Only **deltas from web** are specified here — all other form rules (labels above, validation on blur, error messages below, dirty state) apply unchanged.

### Input Sizing

| Property | Web | Mobile | Why |
|---|---|---|---|
| Input height | 40px | **48px** | Touch target minimum |
| Font size | 14px | **16px** | Prevents iOS auto-zoom on focus |
| Field spacing | 12px | **16px** (`--space-md`) | Thumb-friendly tap targets |

### Pickers and Selectors

| Web pattern | Mobile replacement | Why |
|---|---|---|
| `<select>` dropdown | **Action sheet** (bottom sheet with options) | Dropdowns are unusable on mobile |
| Date picker (calendar widget) | **Native platform picker** (iOS wheel / Android calendar dialog) | Users know their platform's picker |
| Multi-select dropdown | **Full-screen selection list** with checkboxes + "Done" button | Need space for many options |
| Color picker | **Grid of swatches** in a bottom sheet | No freeform color on mobile |

### Keyboard Configuration

- `keyboardType` must match the field: `email-address`, `phone-pad`, `numeric`, `decimal-pad`, `url`
- `returnKeyType`: "next" for all fields except the last, which uses "done" or "send"
- `autoCapitalize`: "none" for email/username, "sentences" for free text, "words" for names
- `textContentType` (iOS) / `autoComplete` (Android): set for all standard fields (email, password, name, phone) to enable autofill

### Keyboard Avoidance

- Use `KeyboardAvoidingView` with `behavior="padding"` (iOS) / `behavior="height"` (Android)
- Submit button must remain visible above the keyboard at all times
- Tapping outside any input dismisses the keyboard (`keyboardShouldPersistTaps="handled"`)

### Mobile Form Rules

- **MF1:** Never use a custom date/time picker when the native platform one exists. Users know their platform's picker — custom pickers add friction.
- **MF2:** Form submit button must be above the keyboard, never hidden behind it. Use `KeyboardAvoidingView` or sticky footer.
- **MF3:** Tapping outside an input dismisses the keyboard. Never trap keyboard focus.
- **MF4:** Long forms (>5 fields) use sections with sticky section headers, not one infinite scroll.
- **MF5:** Numeric inputs (amount, quantity) use `keyboardType="decimal-pad"` — never the full keyboard for numbers.
- **MF6:** Password fields include a show/hide toggle (eye icon, trailing, 44px touch target).

---

## Scaffold Adaptation Note

This file replaces the brief `mobile-app` section in `ocoron-design-system.md` § Scaffold Adaptation Matrix. That section remains for token mapping reference; this file is the full mobile component spec.

---

## Rules Summary (Quick Reference)

| ID | Rule |
|---|---|
| LI1 | List items >= 48px height |
| LI2 | Chevron = navigates; no chevron = inline action |
| LI3 | Swipe actions also in long-press menu |
| LI4 | Destructive swipe → undo toast, not confirm dialog |
| LI5 | Loading = skeleton rows |
| LI6 | Empty list = centered empty state with CTA |
| BS1 | Never nest bottom sheets |
| BS2 | Destructive actions = inline confirmation |
| BS3 | Form sheets need explicit "Done" |
| BS4 | Always dismissible (drag/scrim/back) |
| BS5 | Sheet title required |
| AS1 | Max 6 options |
| AS2 | All icons or no icons |
| AS3 | Destructive last, in danger color |
| AS4 | Cancel always present |
| AS5 | Labels are verbs |
| SR1 | Input >= 16px (prevent iOS zoom) |
| SR2 | 300ms debounce on server queries |
| SR3 | Recent searches in MMKV, max 10 |
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
