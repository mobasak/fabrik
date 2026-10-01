---
description: Tojlo Mobile Design System — the Tojlo-specific mobile patterns (module switcher, module-aware tab bar, module cards, activity feed, embedded module frame, quick actions, onboarding, push grouping) on top of mobile-app/ocoron-mobile-design-system.md. Read for mobile UI in a Tojlo project — one whose docs/design-system.md declares the Tojlo house identity (D-051); never for any other mobile app.
currency_pass: 2026-10-01
---
<!-- CONSUMER: coding agents building React Native UI in a Tojlo-declared mobile project
     GOAL: the Tojlo mobile deltas — module switching, module-aware chrome, embedded vendor modules, push grouping
     AGENT USAGE: read beside core/tojlo-design-system.md (the brand) and mobile-app/ocoron-mobile-design-system.md (the component patterns). -->

# Tojlo Mobile Design System

> The Tojlo mobile patterns. **A house identity, chosen — never defaulted** (D-051): this file applies only when the project's `docs/design-system.md` declares Tojlo, which is why it loads by description, not by file glob. Every generic mobile pattern — list items, bottom and action sheets, search, navigation header, onboarding, forms — is `mobile-app/ocoron-mobile-design-system.md`'s (titled Mobile Component Patterns) and applies unchanged; this file adds what only a Tojlo app has.

**Inheritance chain:**
1. `core/design-system-template.md` — the token slots and their roles (both modes, contrast, motion)
2. `core/ocoron-design-system.md` — the values Tojlo inherits (colours, fonts)
3. `core/tojlo-design-system.md` — the Tojlo brand: module naming, layer colour coding, module icons, voice
4. `mobile-app/ocoron-mobile-design-system.md` — the mobile component patterns (LI1-LI6, BS1-BS5, AS1-AS5, SR1-SR5, NH1-NH4, ON1-ON6, MF1-MF6)
5. **This file** — the Tojlo mobile additions

**Type and colour** follow the components pack's rules: font roles (heading, body, mono — Tojlo's are Ocoron's), sizes in pt/dp that follow the OS text size, and no type below 13 on a mobile surface (`80-mobile.md` § Styling; core Tojlo allows 11–13 for module chrome, so mobile uses 13). An accent, state or layer colour used AS TEXT or an icon on a surface is its `-text` slot; text or an icon ON a fill is its `-fg` slot. Tojlo's layer colours use Ocoron's current slot names: Core `--color-accent`, Intelligence `--color-ai`, Growth `--color-warning` (`core/tojlo-design-system.md` § Module Color Coding still writes the retired `--color-purple` and `--color-secondary`, which `core/ocoron-design-system.md` maps to these).

---

## Inherited Unchanged from `ocoron-mobile-design-system.md`

All 37 rules (LI1-LI6, BS1-BS5, AS1-AS5, SR1-SR5, NH1-NH4, ON1-ON6, MF1-MF6) apply without modification, and these sections are not re-specified here: List Item Anatomy, Bottom Sheet, Action Sheet, Mobile Search, Navigation Header, Mobile Form Inputs. Both dark and light mode are mandatory (`80-mobile.md` § Styling — OS-following with a manual override persisted in MMKV).

If a pattern is not in this document, the components pack's rule applies.

---

## 1. Module Switcher (Mobile)

The primary way to switch between Tojlo's modules on mobile. Replaces the web sidebar's module list. It lists every module of the canonical list in `core/tojlo-design-system.md` § Module Naming except AUTH (a backend service) and the Dashboard (the home screen).

### Trigger

- The **bottom tab bar's** first tab (grid icon, labelled "Modules"), OR a long-press on the current module name in the navigation header.

### Structure

```
┌────────────────────────────────────┐
│          ━━━━━━━━━━━━━             │  ← drag handle
│                                    │
│  Modules                           │  ← sheet title
│                                    │
│  ┌──────┐  ┌──────┐  ┌──────┐     │
│  │ icon │  │ icon │  │ icon │     │  ← module grid (3 columns)
│  │ OPS  │  │ HUB  │  │ CHAT │     │
│  └──────┘  └──────┘  └──────┘     │
│  ┌──────┐  ┌──────┐  ┌──────┐     │
│  │ icon │  │ icon │  │ icon │     │
│  │ MAIL │  │ TI   │  │ WEB  │     │
│  └──────┘  └──────┘  └──────┘     │
│            ...                     │
└────────────────────────────────────┘
```

- A **bottom sheet (medium)** — snaps to 50%, expandable to 90% (components pack § 2)
- **Grid layout:** 3 columns, 80 per cell, 12 gap
- **Each cell:** the module's icon (24, monochrome — `core/tojlo-design-system.md` § Module Icons) centred above its name (body font 500, uppercase, 13, letter-spacing 1)
- **Layer indicator:** a 3 dot below the name, filled with the layer colour (Core `--color-accent`, Intelligence `--color-ai`, Growth `--color-warning`)
- **Active module:** icon and name in `--text-primary`, cell on a `--color-accent-muted` fill — the icon stays monochrome (MS3)
- **Inactive module:** icon and name in `--text-muted`
- **Disabled module** (not provisioned for the tenant): icon at 30% opacity, name `--text-muted`, not tappable; a long-press shows a "Contact admin to enable [MODULE]" toast

### Animation

- The sheet enters per the components pack's bottom-sheet rules (`--motion-slow`, `--ease-emphasis`)
- Selecting a module: press feedback (`scale(0.95)`, light haptic), dismiss the sheet, navigate to the module's root screen

### Module Switcher Rules

- **MS1:** The module switcher is always a bottom sheet, never a full-screen page. Operators should feel they are *switching context*, not *leaving* the app.
- **MS2:** Module order follows the canonical list in `core/tojlo-design-system.md` § Module Naming. Never reorder by usage frequency — consistency builds muscle memory.
- **MS3:** Module icons are monochrome. Colour goes on the layer dot only — never on the icon glyph (`core/tojlo-design-system.md` § Module Color Coding).
- **MS4:** Selecting a module navigates to that module's root screen and sets it as the active context for the bottom tab bar.

---

## 2. Module-Aware Bottom Tab Bar

The persistent bottom navigation for Tojlo mobile; tabs change with the active module. Built on expo-router's `Tabs` (the scaffold's `src/app/(app)/_layout.tsx`), whose tab-bar library sets the bar's height and safe-area inset — do not hard-code them; read the height with `useBottomTabBarHeight()` where a component must sit above the bar.

### Structure

```
┌────────────────────────────────────────────────┐
│ [Modules]  [Tab 1]  [Tab 2]  [Tab 3]  [More]  │  platform height + safe area
└────────────────────────────────────────────────┘
```

- **Background:** `--surface-1`
- **Border top:** 1px `--border`
- **Fixed first tab:** "Modules" (grid icon) — opens the module switcher sheet. Always present regardless of active module.
- **Tabs 1-3:** module-specific primary screens (e.g., OPS → Orders / Inventory / Suppliers). Defined per module.
- **Fixed last tab:** "More" (ellipsis icon) — opens an action sheet with: Settings, Profile, Notifications, Help. Always present.
- **Active tab:** icon and label in `--color-accent-text`. Inactive: `--text-muted`.
- **Labels:** always shown, under the icon (TB2).

### Per-Module Tab Configurations

Modules follow the canonical list in `core/tojlo-design-system.md` § Module Naming.

| Module | Tab 1 | Tab 2 | Tab 3 |
|---|---|---|---|
| **OPS** | Orders | Inventory | Suppliers |
| **HUB** | Workflows | Runs | Triggers |
| **CHAT** | Conversations | Contacts | Templates |
| **MAIL** | Inbox | Drafts | Sent |
| **PORTAL** | Pages | Access | Activity |
| **VAULT** | Documents | Folders | Shared |
| **TI** | Insights | Reports | Alerts |
| **WEB** | Pages | Media | Analytics |
| **MARKETS** | Campaigns | Audiences | Performance |
| **REACH** | Prospects | Sequences | Lists |
| **OUTREACH** | Campaigns | Templates | Analytics |

### Tab Bar Rules

- **TB1:** Maximum 5 tabs total (Modules + 3 module tabs + More). Never 6+ — Material caps its navigation bar at five, and Apple recommends three to five on iPhone, folding the rest into a More tab.
- **TB2:** Tab labels are always visible — no icon-only tabs. Material requires a label on every destination; B2B operators need them for discoverability.
- **TB3:** The "Modules" tab shows a badge with the count of modules that have pending attention items (unread messages, overdue tasks, failed workflows), max "9+" — `tabBarBadge`, styled through `tabBarBadgeStyle` with a `--color-danger` fill and `--color-danger-fg` text.
- **TB4:** Switching modules via the module switcher updates tabs 1-3 immediately. No loading state for the tab bar itself — only the content area loads.

---

## 3. Module Card (Mobile)

Adaptation of the web Module Card (`core/tojlo-design-system.md` § Module Card) for the mobile home screen.

### Structure

```
┌─────────────────────────────────────┐
│ [layer dot]  MODULE NAME       [›]  │  ← header row
│                                     │
│  KPI value          Status pill     │  ← content row
│  KPI label                          │
└─────────────────────────────────────┘
```

- Uses the inherited list item anatomy (two-line, 64) with these overrides:
- **Leading:** a 3 dot filled with the layer colour (not a module icon — too small at list-item scale)
- **Title:** module name, body font 500, uppercase, 13, letter-spacing 1, `--text-primary`
- **Subtitle:** primary KPI (mono font 400, 15, `--text-primary`) + KPI label (body font 400, 13, `--text-muted`)
- **Trailing:** status pill (Active/Syncing/Error) using the inherited pill pattern + chevron
- **Press:** navigates to module root (same as module switcher selection)

### Dashboard Grid (Home Screen)

```
┌────────────────────────────────────┐
│ Tojlo                        [🔔]  │  ← large title header
│                                    │
│ Good morning, [first name]         │  ← greeting
│                                    │
│ ┌────────────────────────────────┐ │
│ │ ● MAIL               Active › │ │  ← module card
│ │ 12 unread    ○ 3 drafts       │ │
│ └────────────────────────────────┘ │
│ ┌────────────────────────────────┐ │
│ │ ● OPS                Active › │ │
│ │ 4 orders pending  ○ 2 overdue │ │
│ └────────────────────────────────┘ │
│                                    │
│ Activity                           │  ← section header
│ ┌────────────────────────────────┐ │
│ │ [feed items...]                │ │
│ └────────────────────────────────┘ │
└────────────────────────────────────┘
```

- **Single column** layout — module cards stack vertically
- **Greeting:** personalized, body font 400, 16, `--text-body`. Time-aware: "Good morning" / "Good afternoon" / "Good evening"
- **Module cards:** only modules with pending attention (unread, overdue, failed). Quiet modules collapse into an "X modules — all clear" summary row at the bottom
- **Activity section:** below the module cards, using the inherited list item anatomy with module attribution (§ 4)

### Module Card Rules

- **MC1:** Module cards on the home screen show only modules with actionable status. Never show every module — operators see what needs attention.
- **MC2:** KPI values use the mono font for numeric alignment. Never the body font for numbers in module cards.
- **MC3:** Status pills follow the semantic slots: Active = success, Syncing = info, Error = danger (each pill a `--color-<state>-muted` fill with `--color-<state>-text` text), Inactive = `--text-muted`.
- **MC4:** Tapping a module card navigates to the module root AND sets the bottom tab bar to that module's tabs.

---

## 4. Activity Feed (Mobile)

Adaptation of the web Activity Feed Item (`core/tojlo-design-system.md` § Activity Feed Item) for mobile. Module attribution is mandatory — every entry names the module that produced the event.

### Structure

Uses the inherited list item anatomy (two-line, 64) with these specifics:

- **Leading:** module icon (20, monochrome, `--text-muted`)
- **Line 1:** module label (body font 500, uppercase, 13, letter-spacing 1.5, the layer colour's `-text` slot) + event description (body font 400, 14, `--text-body`)
- **Line 2:** detail text (body font 400, 13, `--text-muted`)
- **Trailing:** relative timestamp (body font 400, 13, `--text-muted`)

### Examples

```
[mail-icon]  MAIL · New message from Kandil Glass
             Re: Q3 Pricing Proposal                      2m ago

[hub-icon]   HUB · Workflow completed
             Weekly commission calculation — 142 records   15m ago

[ops-icon]   OPS · Order overdue
             Atlas Trading — PO #1042 shipment delayed     1h ago
```

### Activity Feed Rules

- **AF1:** Every activity entry MUST name the source module. "Workflow completed" alone is forbidden — the module label (`HUB`) or "Tojlo HUB:" in prose is required (`core/tojlo-design-system.md` § Activity Feed Item).
- **AF2:** The module label uses its layer colour as text — `--color-accent-text`, `--color-ai-text` or `--color-warning-text` — not `--text-muted`.
- **AF3:** The activity feed is the catch-all surface. If a notification was missed, the activity feed has it. It is the permanent record.
- **AF4:** Tapping an activity entry navigates to the relevant record in the relevant module.

---

## 5. Embedded Module Frame (Mobile)

When Tojlo embeds a third-party module (ERPNext for OPS, n8n for HUB, Wati for CHAT — `core/tojlo-design-system.md` § Module Naming), the app shows it in a `react-native-webview` `WebView` under the native stack header. The scaffold does not ship it: `npx expo install react-native-webview`.

### Structure

```
┌────────────────────────────────────┐
│ ← OPS                   [⋮] [×]   │  ← the native stack header
├────────────────────────────────────┤
│                                    │
│  [WebView: ERPNext content]        │  ← full-bleed WebView
│                                    │
│                                    │
└────────────────────────────────────┘
```

- **Header:** the screen's native stack header (components pack § 5), configured through Stack `options` — never a hand-rolled bar
  - `headerLeft`: a back button that runs EF2, then the module name (body font 500, uppercase, 13)
  - `headerRight`: overflow (⋮) → action sheet (Refresh, Open in browser, Report issue) + close (×)
- **WebView:** full-bleed, no padding. Renders the vendor's mobile-responsive web UI
- **Loading:** a skeleton shimmer in the WebView area while loading. Never a blank white or black screen
- **Error:** if the WebView fails to load, show the standard error state (icon + "Failed to load [MODULE]" + "Retry" button) instead of the WebView

### Embedded Frame Rules

- **EF1:** The Tojlo header is always visible above the WebView. Hide the vendor's own navigation bar with `injectedJavaScript` (its before-content variant is experimental on Android) or URL parameters where the vendor offers them — `core/tojlo-design-system.md` § Embedded Module Frame.
- **EF2:** Back navigates within the WebView first: track `canGoBack` from `onNavigationStateChange` and call the WebView's `goBack()`; only when its history is exhausted does it pop the native stack screen. A custom `headerLeft` does not stop the iOS swipe-back gesture, so set `gestureEnabled: false` while the WebView can go back, and handle Android back the same way through `BackHandler`.
- **EF3:** Pull-to-refresh reloads the embedded content. `pullToRefreshEnabled` is documented for iOS only; on Android offer Refresh in the overflow sheet.
- **EF4:** Deep links into embedded modules open the WebView at the correct URL path. Never show the module root and make the user navigate.
- **EF5:** A connection line in the header reflects state: "Connected" (hidden, the default), "Syncing..." (shown, `--color-info-text`), "Offline" (shown, `--color-danger-text`).

---

## 6. Operator Quick Actions (Mobile)

A floating action button (FAB) for the most common operator actions, scoped to the active module. The FAB is Material's pattern; Apple's guidelines have none, so on iOS it is a house choice kept for one muscle memory across platforms — one per screen, as Material asks.

### Structure

```
                              ┌─────┐
                              │  +  │  ← FAB, 56
                              └─────┘
                         16 above the tab bar, 16 from the edge
```

- **Size:** 56, a rounded square — Material's current FAB shape (the circle was the older one)
- **Fill:** `--color-accent`
- **Icon:** Lucide `Plus` (core Tojlo's icon library — `lucide-react-native`, not in the scaffold; its `react-native-svg` dependency is), 24, `--color-accent-fg`
- **Elevation:** no shadow in dark mode — the accent fill on the surfaces is the separation (`design-system-template.md` § Visual Rules — no shadows in dark mode); in light mode the brand's subtle shadow through the `boxShadow` style (New Architecture, both platforms)
- **Position:** fixed, 16 from the trailing edge, 16 above the bottom tab bar
- **Accessibility:** `accessibilityRole="button"` and an `accessibilityLabel` naming the action ("New order")

### Behavior

- **Single tap:** if the module has one primary creation action (MAIL → "Compose", CHAT → "New conversation"), execute it directly — navigate to the creation screen. For an embedded module (OPS, HUB, CHAT) that screen is the module's WebView opened at the vendor's create URL (EF4).
- **Single tap (multi-action module):** if the module has 2-3 creation actions, open an **action sheet** with options. Example: OPS → "New order" / "New product" / "New supplier".
- **Long press:** always opens the action sheet with all available quick actions for the active module.

### Per-Module Quick Actions

| Module | Primary action (single tap) | Secondary actions (action sheet) |
|---|---|---|
| **OPS** | New order | New product, New supplier |
| **HUB** | Run workflow | New workflow, New trigger |
| **CHAT** | New conversation | New template |
| **MAIL** | Compose | — |
| **VAULT** | Upload document | New folder |
| **TI** | New report | New alert |
| **REACH** | New prospect | New sequence |
| **OUTREACH** | New campaign | New template |

A module with no row here (PORTAL, WEB, MARKETS) has no FAB.

### FAB Rules

- **FAB1:** The FAB is visible only on module root screens and list screens. Hide it on detail screens, forms, and settings.
- **FAB2:** The FAB stays in place on scroll — Material's rule for a regular FAB; only an extended FAB (icon + label) may collapse to the icon on scroll.
- **FAB3:** The FAB must not overlap the bottom tab bar. Position it 16 above the tab bar's top edge, using `useBottomTabBarHeight()`.
- **FAB4:** If the user lacks permission to create records in the active module, hide the FAB entirely — don't show a disabled button.

---

## 7. Tojlo Onboarding (Mobile Override)

Extends `ocoron-mobile-design-system.md` § Swipeable Onboarding with Tojlo-specific content and a module setup step.

### Pages (5 total)

1. **Welcome** — Tojlo wordmark + "The B2B Operating System" tagline. No illustration needed — the wordmark is the visual.
2. **Value prop 1** — "Twelve modules. One login." + brief description of the unified platform.
3. **Value prop 2** — "AI in every workflow." + brief description of Tojlo TI.
4. **Module selection** — "Which modules do you use?" Grid of module icons with checkboxes. Pre-select the modules provisioned for this tenant. This is informational (personalization), not gating — all provisioned modules are accessible regardless.
5. **Get started** — "Your workspace is ready." + "Open Dashboard" CTA button.

### Onboarding Overrides

- Page 1 uses the Tojlo wordmark (SVG asset, not text font) centred at 80 wide
- Page 4 (module selection) uses the module switcher grid layout (3 columns, 80 cells) but with checkboxes
- Final CTA reads "Open Dashboard" (not "Get started") — domain-specific
- Footer on every page: "Tojlo, by Ocoron" in body font 400, 13, `--text-muted`
- All inherited ON1-ON6 rules apply (skippable, max 5 pages, no auto-advance)

---

## 8. Push Notification Grouping

Tojlo groups push notifications by module so the modules do not feel like separate apps. Push uses `expo-notifications`, which the scaffold does not ship (`npx expo install expo-notifications`).

### Grouping Rules

- **iOS — one stack per module:** send each module's notifications with its own `threadId` (Expo's push message; APNs `thread-id`), and iOS groups each thread by itself.
- **Android — one channel per module:** send with the module's `channelId` (created with `setNotificationChannelAsync`). A channel is the user's settings switch (PN2), not a visual stack: Android bundles all of the app's notifications together once four or more arrive, and Expo's push message has no per-module group key.
- **Summary:** when 3+ notifications from the same module are pending, the server replaces them with one summary — "Tojlo MAIL — 5 new messages" — sent with `collapseId` (both platforms) or Android's `tag` set to the module; it is never an OS group
- **Icon:** the Tojlo monogram (T mark) for all push notifications. The module name in the title provides context.
- **Title format:** "Tojlo [MODULE]: [event summary]" — e.g., "Tojlo OPS: New order received"
- **Body:** one-line detail. The deep-link payload routes to the relevant record.

### Push Rules

- **PN1:** Never send push notifications from more than 3 modules within a 1-minute window. Queue and stagger. Operators will disable notifications entirely if they feel bombarded.
- **PN2:** Per-module mute in Settings → Notifications: muting a module suppresses its push but keeps its in-app activity feed entries. One Android channel per module makes the OS's own per-channel switch match this setting.
- **PN3:** Quiet hours belong to the OS first — Focus on iOS, Do Not Disturb on Android, both set by the user. An in-app quiet-hours setting (default 22:00-08:00 user-local) may suppress further. An event that needs immediate action (a system outage, a failed payment, an account-security issue) is sent at the `time-sensitive` interruption level (iOS; Apple's bar is an event happening now or within the hour), which breaks through Focus only if the user allows it; never `critical`, which Apple reserves for health and safety, and never `time-sensitive` for marketing.
- **PN4:** The push title always includes the module name. "[MODULE]: [event]" — never just "[event]".

---

## Rules Summary (Quick Reference)

All 37 components-pack rules (LI1-LI6, BS1-BS5, AS1-AS5, SR1-SR5, NH1-NH4, ON1-ON6, MF1-MF6) are inherited. Tojlo adds:

| ID | Rule |
|---|---|
| MS1 | Module switcher is always a bottom sheet, never a page |
| MS2 | Module order follows canonical list — never reorder |
| MS3 | Module icons monochrome; color on layer dot only |
| MS4 | Module selection sets bottom tab bar context |
| TB1 | Max 5 tabs (Modules + 3 module tabs + More) |
| TB2 | Tab labels always visible — no icon-only tabs |
| TB3 | Modules tab badge shows pending attention count |
| TB4 | Module switch updates tabs immediately |
| MC1 | Home shows only modules with actionable status |
| MC2 | KPI values use the mono font |
| MC3 | Status pills follow the semantic slots |
| MC4 | Module card tap navigates + sets tab bar |
| AF1 | Every activity entry names the source module |
| AF2 | Module label uses the layer colour as text |
| AF3 | Activity feed is the permanent record |
| AF4 | Activity tap navigates to relevant record |
| EF1 | Tojlo header always visible above WebView |
| EF2 | Back navigates WebView history first, then native stack |
| EF3 | Pull-to-refresh reloads embedded content (iOS; Refresh in the sheet on Android) |
| EF4 | Deep links open correct WebView URL path |
| EF5 | Header connection line reflects state |
| FAB1 | FAB on root/list screens only |
| FAB2 | FAB stays in place on scroll |
| FAB3 | FAB above tab bar, never overlapping |
| FAB4 | Hide FAB if user lacks create permission |
| PN1 | Max 3 modules pushing within 1 minute |
| PN2 | Per-module mute, one Android channel per module |
| PN3 | OS Focus/DND first; time-sensitive at most, never critical |
| PN4 | Push title always includes module name |

## Draft Persistence — nothing typed or AI-generated is EVER lost (fleet mandate 2026-08-13)

Every form/wizard/editor/AI-populated surface persists its full working state **continuously on
change** (debounce ≤1s + flush on blur/hide/background) to MMKV (the scaffold's `src/lib/storage.tsx`; drafts only — tokens stay in `expo-secure-store`); **restore is automatic and
silent** on every return path (Back, reopened app, crash, days-old session) — the
user continues down to the last letter typed. The draft clears on exactly ONE event: successful
creation/submission of the entity (or explicit user discard). Canonical detail:
`core/design-system-template.md` § Save Behavior.
